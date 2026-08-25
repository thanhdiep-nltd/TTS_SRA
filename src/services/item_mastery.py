"""src/services/item_mastery.py — Độ thành thạo theo chương từ LMS Item-Level + đối soát chống gian lận.

Mục tiêu: từ dữ liệu item-response (mỗi câu hỏi trắc nghiệm LMS) của 1 học sinh, ước lượng
mức độ thành thạo (mastery) cho TỪNG chương (curriculum_units), sau đó đối soát với điểm thi
trên lớp (giám thị) để hạ nhiệt gian lận và xuất confidence/integrity.

Khác `src/services/knowledge_gap.py` (chỉ dùng điểm tổng → ill-posed): module này dùng
Item-Response Matrix để giải bài toán dưới xác định bằng nhiều phép đo trên cùng chương.

Module này là hàm THUẦN (không DB, không LLM) → dễ unit test.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

# Tái dùng bảng hệ số khó Bloom của knowledge_gap (không import để tránh phụ thuộc vòng tròn).
_BLOOM_DIFFICULTY = {1: 0.5, 2: 0.7, 3: 1.0, 4: 1.3, 5: 1.6, 6: 2.0}

# Ngưỡng: số câu tối thiểu trên 1 chương để coi là có đủ dữ liệu.
MIN_ITEMS = 5
COVERAGE_MIN = 0.6  # dưới mức này → INSUFFICIENT / confidence LOW
GAP_MASTERY_THRESHOLD = 0.6  # đồng nhất với knowledge_gap

# Ngưỡng đối soát Δ = raw − exam.
DELTA_MATCH = 0.15  # |Δ| ≤ 0.15 → khớp chặt (HIGH)
DELTA_WARN = 0.30   # |Δ| trên mức này → lệch mạnh (gian lận / lười)

Confidence = Literal["HIGH", "MEDIUM", "LOW", "INSUFFICIENT"]


@dataclass(frozen=True)
class ItemResult:
    """1 câu response hợp lệ (đã lọc nhiễu) dùng để tính mastery.

    unit_id: chương được tính (với câu multi-chapter, mỗi chương có 1 ItemResult riêng).
    unit_weight: trọng số của câu này đóng góp vào chương (mặc định 1.0 = câu 1 chương).
        Với câu map nhiều chương (lms_question_unit), weight phân bổ theo trọng số
        (vd câu 60% chương A + 40% chương B) và tổng các weight của 1 câu = 1.0.
    """

    unit_id: int
    bloom_level: int = 3
    score_received: float = 0.0
    max_score: float = 1.0
    unit_weight: float = 1.0


@dataclass
class UnitMastery:
    """Mastery 1 chương của 1 học sinh từ item-response + đối soát."""

    unit_id: int
    raw_mastery: float | None = None  # None = thiếu dữ liệu
    n_items: int = 0
    n_correct: int = 0
    coverage: float = 0.0
    lm_weight: float = 0.0
    exam_weight: float = 0.0
    adjusted_mastery: float | None = None
    confidence: str = "INSUFFICIENT"
    evidence_source: str = "LMS"
    integrity_status: str = "INSUFFICIENT"
    is_gap: bool = False
    evidence_detail: dict = field(default_factory=dict)


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def raw_unit_mastery(items: list[ItemResult]) -> UnitMastery:
    """Tính mastery thô Bloom-weighted + coverage cho 1 chương từ các item đã lọc.

    items: các câu response của học sinh thuộc 1 unit (đã chọn is_best, bỏ nhiễu);
    với câu multi-chapter, mỗi chương có ItemResult riêng với unit_weight theo lms_question_unit.
    raw_u = Σ(score_received × bloom_factor × unit_weight) / Σ(max_score × bloom_factor × unit_weight).
    """
    n = len(items)
    if n == 0:
        return UnitMastery(unit_id=0)
    total_max = sum(
        i.max_score * _BLOOM_DIFFICULTY.get(i.bloom_level, 1.0) * i.unit_weight for i in items
    )
    if total_max <= 0:
        return UnitMastery(unit_id=items[0].unit_id, n_items=n)
    total_earned = sum(
        i.score_received * _BLOOM_DIFFICULTY.get(i.bloom_level, 1.0) * i.unit_weight for i in items
    )
    n_correct = sum(1 for i in items if i.score_received > 0)
    coverage = min(1.0, n / MIN_ITEMS)
    raw = _clamp01(total_earned / total_max)
    confidence: str = "HIGH" if coverage >= COVERAGE_MIN else "MEDIUM"
    return UnitMastery(
        unit_id=items[0].unit_id,
        raw_mastery=round(raw, 4),
        n_items=n,
        n_correct=n_correct,
        coverage=round(coverage, 3),
        confidence=confidence,
        integrity_status="OK",
        evidence_detail={"n_items": n, "coverage": round(coverage, 3)},
    )


def merge_onclass_adjustment(
    raw: UnitMastery,
    exam_mastery: float | None,
    delta_match: float = DELTA_MATCH,
    delta_warn: float = DELTA_WARN,
) -> UnitMastery:
    """Đối soát LMS ↔ điểm thi trên lớp (bất cân xứng) → adjusted + confidence + integrity.

    exam_mastery: mastery của unit từ compute_unit_mastery (điểm thi trên lớp, giám thị);
                  None nếu không có đề/điểm thi trên lớp.
    """
    if raw.raw_mastery is None:
        raw.integrity_status = "INSUFFICIENT"
        raw.confidence = "INSUFFICIENT"
        return raw

    if exam_mastery is None:
        raw.lm_weight, raw.exam_weight = 1.0, 0.0
        raw.adjusted_mastery = raw.raw_mastery
        raw.confidence = raw.confidence if raw.confidence == "HIGH" else "LOW"
        raw.evidence_source = "LMS"
        raw.integrity_status = "LMS_ONLY"
        return raw

    delta = raw.raw_mastery - exam_mastery
    raw.evidence_detail["delta"] = round(delta, 4)
    raw.evidence_detail["exam_mastery"] = round(exam_mastery, 4)

    if abs(delta) <= delta_match:
        lm, ex, conf, status = 0.8, 0.2, "HIGH", "OK"
    elif abs(delta) <= delta_warn:
        lm, ex, conf, status = 0.6, 0.4, "MEDIUM", "OK"
    elif delta > delta_warn:
        # LMS ≫ thi → LMS vượt trội so với bài thi chung: kết hợp cân bằng, ghi nhận nỗ lực bài tập.
        lm, ex, conf, status = 0.5, 0.5, "MEDIUM", "LMS_EXCEEDS_EXAM"
    else:  # delta < -delta_warn: LMS ≪ thi → ít luyện tập trên LMS, ưu tiên điểm thi thực tế.
        lm, ex, conf, status = 0.4, 0.6, "MEDIUM", "LOW_ENGAGEMENT"

    raw.lm_weight, raw.exam_weight = lm, ex
    raw.confidence = conf
    raw.integrity_status = status
    raw.evidence_source = "HYBRID"
    raw.adjusted_mastery = round(_clamp01(lm * raw.raw_mastery + ex * exam_mastery), 4)
    raw.is_gap = bool(raw.adjusted_mastery < GAP_MASTERY_THRESHOLD)
    return raw


def finalize_mastery(items: list[ItemResult], exam_mastery: float | None) -> UnitMastery:
    """Pipeline đầy đủ: raw → đối soát → trả UnitMastery hoàn chỉnh cho 1 chương.

    items: item-response đã lọc của 1 unit (best attempt, không nhiễu).
    exam_mastery: mastery từ điểm thi trên lớp (None nếu không có).
    """
    raw = raw_unit_mastery(items)
    if raw.raw_mastery is not None:
        raw = merge_onclass_adjustment(raw, exam_mastery)
    return raw


def compute_evidence_source(student_total_items: int) -> str:
    """Phân loại nguồn bằng chứng tổng thể của 1 học sinh/môn:
    'INSUFFICIENT_STUDENT' nếu chưa có item nào → báo 'chưa đủ dữ liệu để đánh giá học sinh'."""
    if student_total_items == 0:
        return "INSUFFICIENT_STUDENT"
    return "VALID"


CONFIDENCE_TO_INT: dict[str, int] = {
    "LOW": 1,
    "MEDIUM": 2,
    "HIGH": 3,
    "INSUFFICIENT": 1,
}


def recalc_unit_mastery(
    db: any,
    subject_id: int,
    semester_index: int,
    school_id: int | None = None,
) -> int:
    """Tính lại và ghi student_unit_mastery từ lms_question_response + lms_question_unit.

    1. Map câu hỏi sang unit_id qua lms_question_unit (weight).
    2. Đọc responses sạch (is_best_attempt = TRUE, integrity_flag = 0).
    3. Nhóm theo (student_code, unit_id) -> list[ItemResult].
    4. Tính finalize_mastery cho từng unit của từng học sinh.
    5. UPSERT vào public.student_unit_mastery.
    6. Trả về tổng số bản ghi đã tính toán và cập nhật.
    """
    import json
    from sqlalchemy import text

    # 1. Map câu → [(unit_id, weight)]
    unit_rows = db.execute(text("SELECT question_id, unit_id, weight FROM public.lms_question_unit")).fetchall()
    unit_map: dict[int, list[tuple[int, float]]] = {}
    for r in unit_rows:
        unit_map.setdefault(int(r.question_id), []).append((int(r.unit_id), float(r.weight)))

    # 2. Đọc responses sạch của môn (kèm tenant nếu có) qua JOIN lms_question_bank
    school_cond = "AND lqr.so_school_id = :school_id" if school_id else ""
    params: dict = {"sid": subject_id}
    if school_id:
        params["school_id"] = school_id

    resp_rows = db.execute(
        text(f"""
            SELECT lqr.student_code, lqr.so_school_id, lqr.question_id,
                   lqr.bloom_level, lqr.is_correct, lqr.score_received, lqr.max_score
            FROM public.lms_question_response lqr
            JOIN public.lms_question_bank lqb ON lqr.question_id = lqb.question_id
            WHERE lqb.subject_id = :sid
              AND lqr.is_best_attempt = TRUE
              AND (lqr.integrity_flag IS NULL OR lqr.integrity_flag = 0)
              {school_cond}
            ORDER BY lqr.student_code, lqr.question_id
        """),
        params,
    ).fetchall()

    if not resp_rows:
        return 0

    # 3. Gom nhóm theo (student_code, so_school_id, unit_id)
    by_student_unit: dict[tuple[str, int, int], list[ItemResult]] = {}
    for r in resp_rows:
        st_code = r.student_code
        st_school = int(r.so_school_id) if r.so_school_id is not None else (school_id or 1)
        score = float(r.score_received) if r.score_received is not None else (1.0 if r.is_correct else 0.0)
        max_s = float(r.max_score) if r.max_score is not None else 1.0
        bloom = int(r.bloom_level) if r.bloom_level is not None else 3

        units_for_q = unit_map.get(int(r.question_id), [])
        for uid, w in units_for_q:
            if uid is None:
                continue
            by_student_unit.setdefault((st_code, st_school, uid), []).append(
                ItemResult(
                    unit_id=uid,
                    bloom_level=bloom,
                    score_received=score,
                    max_score=max_s,
                    unit_weight=w,
                )
            )

    if not by_student_unit:
        return 0

    # 3.1 Đọc điểm thi gần nhất từ sổ điểm (fact_gradebooks & fact_gradebooks_moet)
    # để tính exam_mastery (0..1) phục vụ đối soát chéo LMS ↔ Thi.
    exam_mastery_by_student: dict[str, float] = {}
    try:
        grade_cond = "AND fg.so_school_id = :school_id" if school_id else ""
        g_params: dict = {"sid": subject_id, "sem": semester_index}
        if school_id:
            g_params["school_id"] = school_id

        grade_rows = db.execute(
            text(f"""
                SELECT fg.student_code, fg.final_grade, fg.max_grade
                FROM (
                    SELECT student_code, final_grade, COALESCE(max_grade, 10.0) AS max_grade, so_school_id, subject_id, semester_index, created_at
                    FROM s360.fact_gradebooks
                    WHERE final_grade IS NOT NULL
                    UNION ALL
                    SELECT fgm.student_code, fgm.final_grade, COALESCE(dem.max_grade, 10.0) AS max_grade, fgm.so_school_id, fgm.subject_id, fgm.semester_index, fgm.created_at
                    FROM s360.fact_gradebooks_moet fgm
                    LEFT JOIN s360.dim_exam_moet dem ON fgm.gradebook_type_item_id = dem.gradebook_type_item_id
                    WHERE fgm.final_grade IS NOT NULL
                ) fg
                WHERE fg.subject_id = :sid
                  AND fg.semester_index = :sem
                  {grade_cond}
                ORDER BY fg.created_at DESC
            """),
            g_params,
        ).fetchall()

        for gr in grade_rows:
            sc = gr.student_code
            if sc not in exam_mastery_by_student and gr.final_grade is not None:
                fg = float(gr.final_grade)
                mg = float(gr.max_grade) if gr.max_grade and float(gr.max_grade) > 0 else 10.0
                exam_mastery_by_student[sc] = max(0.0, min(1.0, round(fg / mg, 4)))
    except Exception:
        # Nếu lỗi query sổ điểm, rollback transaction để không làm bẩn session và fallback
        try:
            db.rollback()
        except Exception:
            pass
        exam_mastery_by_student = {}

    # 4. Tính toán & UPSERT theo batch
    upsert_sql = text("""
        INSERT INTO public.student_unit_mastery
            (student_code, subject_id, so_school_id, unit_id, semester_index,
             raw_mastery, n_items, n_correct, coverage, lm_weight, exam_weight,
             adjusted_mastery, confidence, evidence_source, integrity_status,
             evidence_detail, updated_at)
        VALUES
            (:st_code, :subject_id, :so_school_id, :unit_id, :semester_index,
             :raw_mastery, :n_items, :n_correct, :coverage, :lm_weight, :exam_weight,
             :adjusted_mastery, :confidence, :evidence_source, :integrity_status,
             CAST(:evidence_detail AS jsonb), NOW())
        ON CONFLICT (so_school_id, student_code, subject_id, unit_id, semester_index) DO UPDATE
          SET raw_mastery = EXCLUDED.raw_mastery,
              adjusted_mastery = EXCLUDED.adjusted_mastery,
              n_items = EXCLUDED.n_items,
              n_correct = EXCLUDED.n_correct,
              coverage = EXCLUDED.coverage,
              lm_weight = EXCLUDED.lm_weight,
              exam_weight = EXCLUDED.exam_weight,
              confidence = EXCLUDED.confidence,
              evidence_source = EXCLUDED.evidence_source,
              integrity_status = EXCLUDED.integrity_status,
              evidence_detail = EXCLUDED.evidence_detail,
              updated_at = NOW()
    """)

    count = 0
    for (st_code, st_school, uid), items in by_student_unit.items():
        exam_m = exam_mastery_by_student.get(st_code)
        m = finalize_mastery(items, exam_mastery=exam_m)
        if m.raw_mastery is None:
            continue

        conf_int = CONFIDENCE_TO_INT.get(m.confidence, 1)
        db.execute(
            upsert_sql,
            {
                "st_code": st_code,
                "subject_id": subject_id,
                "so_school_id": st_school,
                "unit_id": uid,
                "semester_index": semester_index,
                "raw_mastery": m.raw_mastery,
                "n_items": m.n_items,
                "n_correct": m.n_correct,
                "coverage": m.coverage,
                "lm_weight": m.lm_weight,
                "exam_weight": m.exam_weight,
                "adjusted_mastery": m.adjusted_mastery,
                "confidence": conf_int,
                "evidence_source": m.evidence_source,
                "integrity_status": m.integrity_status,
                "evidence_detail": json.dumps(m.evidence_detail) if m.evidence_detail else "{}",
            },
        )
        count += 1

    db.commit()
    return count
