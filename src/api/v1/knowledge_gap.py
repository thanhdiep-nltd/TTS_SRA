"""src/api/v1/knowledge_gap.py — API lỗ hổng kiến thức (M2).

Đọc exam_competencies (đề → unit + weight + bloom) + điểm tổng của học sinh từ
fact_gradebooks để ước lượng mastery từng unit (dùng service knowledge_gap thuần).
"""

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.api.deps import CurrentUser, get_db
from src.schemas.knowledge_gap import (
    AnalyzeLmsBankRequest,
    AnalyzeLmsBankResponse,
    BloomStatItem,
    ClassKnowledgeGaps,
    ClassOption,
    ClassRosterResponse,
    KnowledgeGapItem,
    LmsJobStatusResponse,
    LmsQuestionBankItem,
    LmsQuestionUnitRef,
    RecalcMasteryResult,
    StudentKnowledgeGaps,
    StudentOption,
    StudentRosterSummary,
    StudentUnitBloomDrilldownResponse,
    StudentUnitQuestionItem,
)
from src.services.item_mastery import generate_confidence_reason, recalc_unit_mastery
from src.services.knowledge_gap import UnitWeight, compute_unit_mastery
from src.services.lms_question_analyzer import job_manager, run_analysis_job_in_background

router = APIRouter(prefix="/knowledge-gaps", tags=["Knowledge Gaps"])

# student_unit_mastery.confidence là SMALLINT (1 LOW | 2 MEDIUM | 3 HIGH) theo DDL
# — map sang chuỗi API/frontend (HIGH/MEDIUM/LOW); chuỗi (test/fake) giữ nguyên.
_CONFIDENCE_LABELS = {1: "LOW", 2: "MEDIUM", 3: "HIGH"}

BLOOM_NAMES: dict[int, str] = {
    1: "Nhớ (Nhận biết)",
    2: "Hiểu (Thông hiểu)",
    3: "Vận dụng",
    4: "Phân tích",
    5: "Đánh giá",
    6: "Sáng tạo",
}


def _confidence_label(value) -> str:
    """Chuẩn hóa confidence từ SMALLINT (1/2/3) hoặc chuỗi → 'HIGH'/'MEDIUM'/'LOW'."""
    if isinstance(value, int):
        return _CONFIDENCE_LABELS.get(value, "LOW")
    return value or "LOW"


@router.get("/subject-options", response_model=list[dict])
def list_s360_subjects(db: Session = Depends(get_db)):
    """Danh sách môn học từ s360.dim_subject (danh mục dùng chung, 24 môn).

    KHÔNG dùng /ews/meta (chỉ trả môn có trong dự báo EWS — bảng risk_predictions
    có thể rỗng) hay /subjects public (model User thiếu school_id). Trả subject_id
    Integer đúng dạng API knowledge-gaps.
    """
    rows = db.execute(
        text("""
            SELECT id, code, name
            FROM s360.dim_subject
            WHERE is_active = 1
            ORDER BY id
        """)
    ).fetchall()
    return [{"id": r.id, "code": r.code, "name": r.name} for r in rows]


@router.get("/class-options", response_model=list[ClassOption])
def list_s360_classes(
    current_user: CurrentUser = None,
    db: Session = Depends(get_db),
):
    """Danh sách lớp từ s360.dim_homeroom_class (dữ liệu thật của học sinh/điểm).

    KHÔNG dùng /classes (public CRUD) vì DB dev dữ liệu thật nằm ở schema s360
    (public.classes rỗng) và model User không có school_id UUID. Lọc theo so_school_id.
    """
    school_id = getattr(current_user, "so_school_id", None)
    params: dict = {}
    cond = ""
    if school_id is not None:
        cond = "WHERE so_school_id = :sid"
        params["sid"] = school_id
    rows = db.execute(
        text(f"""
            SELECT id, code, fullname, grade_id
            FROM s360.dim_homeroom_class
            {cond}
            ORDER BY grade_id, id
        """),
        params,
    ).fetchall()
    return [
        ClassOption(
            class_id=int(r.id),
            class_name=r.fullname,
            grade_id=int(r.grade_id) if r.grade_id is not None else None,
            code=r.code,
        )
        for r in rows
    ]


@router.get("/classes/{class_id}/students", response_model=list[StudentOption])
def list_s360_students(
    class_id: int,
    current_user: CurrentUser = None,
    db: Session = Depends(get_db),
):
    """Học sinh của 1 lớp từ s360.dim_homeroom_class_student (lọc đúng lớp + trường)."""
    school_id = getattr(current_user, "so_school_id", None)
    params: dict = {"cid": class_id}
    cond = "homeroom_class_id = :cid"
    if school_id is not None:
        cond += " AND so_school_id = :sid"
        params["sid"] = school_id
    rows = db.execute(
        text(f"""
            SELECT student_code, student_name
            FROM s360.dim_homeroom_class_student
            WHERE {cond}
            ORDER BY student_name
        """),
        params,
    ).fetchall()
    return [
        StudentOption(student_code=r.student_code, student_name=r.student_name)
        for r in rows
        if r.student_name
    ]


@router.get("/lms-question-bank", response_model=list[LmsQuestionBankItem])
def list_lms_question_bank(
    subject_id: int | None = Query(None, description="Lọc theo môn (s360.dim_subject.id)"),
    current_user: CurrentUser = None,
    db: Session = Depends(get_db),
):
    """Ngân hàng câu hỏi LMS (lms_question_bank) kèm thống kê làm bài.

    Trả về toàn bộ câu hỏi LMS đã map môn, kèm tên BÀI (curriculum_units — unit_id
    trỏ tới bài con, parent_id = chương) và thống kê từ lms_question_response
    (số học sinh đã trả lời best-attempt + độ đúng) để xem "ngân hàng câu hỏi"
    và hiệu quả từng câu. Câu tổng hợp nhiều bài có `units` với weight phân bổ.
    """
    school_id = getattr(current_user, "so_school_id", None)
    cond = "lqb.so_school_id = :school_id"
    params: dict = {"school_id": school_id} if school_id is not None else {}
    if not school_id:
        # Không có tenant filter (vd chưa login) — không nên trả toàn bộ; để rỗng.
        return []
    if subject_id:
        cond += " AND lqb.subject_id = :sid"
        params["sid"] = subject_id

    rows = db.execute(
        text(f"""
            SELECT lqb.question_id, lqb.assignment_id, lqb.so_school_id, lqb.subject_id,
                   lqb.unit_id, lqb.lesson_id, lqb.bloom_level, lqb.question_type, lqb.question_text,
                   lqb.item_weight, lqb.is_active,
                   cu.name AS unit_name, p.name AS chapter_name,
                   les.name AS lesson_name,
                   r.n_responses, r.n_correct
            FROM public.lms_question_bank lqb
            LEFT JOIN public.curriculum_units cu ON cu.id = lqb.unit_id
            LEFT JOIN public.curriculum_units p ON p.id = cu.parent_id
            LEFT JOIN public.curriculum_units les ON les.id = lqb.lesson_id
            LEFT JOIN (
                SELECT question_id,
                       COUNT(*) AS n_responses,
                       COUNT(*) FILTER (WHERE is_correct) AS n_correct
                FROM public.lms_question_response
                WHERE is_best_attempt = TRUE
                GROUP BY question_id
            ) r ON r.question_id = lqb.question_id
            WHERE {cond}
            ORDER BY lqb.subject_id, lqb.unit_id NULLS LAST, lqb.question_id
        """),
        params,
    ).fetchall()

    # Map câu → [(bài_id, weight)] — câu multi-bài đóng góp vào nhiều bài.
    unit_rows = db.execute(
        text("""
            SELECT lqu.question_id, lqu.unit_id, lqu.weight,
                   cu.name AS unit_name, p.name AS chapter_name
            FROM public.lms_question_unit lqu
            LEFT JOIN public.curriculum_units cu ON cu.id = lqu.unit_id
            LEFT JOIN public.curriculum_units p ON p.id = cu.parent_id
            ORDER BY lqu.question_id, lqu.weight DESC
        """)
    ).fetchall()
    units_by_q: dict[int, list[LmsQuestionUnitRef]] = {}
    for qid, uid, weight, uname, pname in unit_rows:
        units_by_q.setdefault(qid, []).append(
            LmsQuestionUnitRef(
                unit_id=int(uid),
                unit_name=uname,
                chapter=(pname if pname else uname) if uid is not None else None,
                weight=float(weight),
            )
        )

    items = []
    for r in rows:
        n_resp = int(r.n_responses) if r.n_responses is not None else None
        n_correct = int(r.n_correct) if r.n_correct is not None else None
        accuracy = round(n_correct / n_resp, 4) if n_resp else None
        items.append(
            LmsQuestionBankItem(
                question_id=int(r.question_id),
                assignment_id=int(r.assignment_id),
                subject_id=int(r.subject_id),
                so_school_id=int(r.so_school_id),
                unit_id=int(r.unit_id) if r.unit_id is not None else None,
                unit_name=r.unit_name,
                chapter=(r.chapter_name if r.chapter_name else r.unit_name) if r.unit_id is not None else None,
                lesson_id=int(r.lesson_id) if r.lesson_id is not None else None,
                lesson_name=r.lesson_name,
                bloom_level=int(r.bloom_level) if r.bloom_level is not None else None,
                question_type=r.question_type,
                question_text=r.question_text,
                item_weight=float(r.item_weight) if r.item_weight is not None else None,
                is_active=int(r.is_active) if r.is_active is not None else None,
                n_responses=n_resp,
                n_correct=n_correct,
                accuracy=accuracy,
                units=units_by_q.get(int(r.question_id), []),
            )
        )
    return items


def _resolve_school_year(db: Session, school_year_id: int | None) -> int:
    """Lấy năm học hiện hành nếu không truyền."""
    if school_year_id and school_year_id > 0:
        return school_year_id
    row = db.execute(text("SELECT id FROM s360.dim_school_year WHERE is_current = 1 LIMIT 1")).fetchone()
    return int(row.id) if row and row.id is not None else 2025


def _load_exam_units(
    db: Session, subject_id: int, semester_index: int, school_id: int | None = None
) -> list[UnitWeight]:
    """Load danh sách unit của đề (từ exam_competencies) cho môn + học kỳ.

    Ưu tiên đề CK (FINAL) nếu có, ngược lại MIDTERM. Có Tenant isolation theo trường.
    """
    school_filter = "AND (ep.so_school_id IS NULL OR ep.so_school_id = :school_id)" if school_id else ""
    params = {"sid": subject_id, "sem": semester_index}
    if school_id:
        params["school_id"] = school_id

    rows = db.execute(
        text(f"""
            SELECT ec.unit_id, ec.weight, ec.bloom_level
            FROM public.exam_competencies ec
            JOIN public.exam_papers ep ON ep.id = ec.exam_paper_id
            WHERE ep.subject_id = :sid
              AND ep.semester_id = :sem
              {school_filter}
            ORDER BY CASE ep.score_category WHEN 'FINAL' THEN 0 WHEN 'MIDTERM' THEN 1 ELSE 2 END
            LIMIT 100
        """),
        params,
    ).fetchall()
    return [
        UnitWeight(
            unit_id=r.unit_id,
            weight=float(r.weight) if r.weight is not None else 0.0,
            bloom_level=r.bloom_level or 3,
        )
        for r in rows
    ]


def _unit_meta(
    db: Session, unit_ids: list[int]
) -> dict[int, tuple[str | None, str | None, str | None, str | None, list[str] | None, int | None]]:
    """Map unit_id → (name, chapter, lesson, summary, keywords, parent_id).

    chapter = tên node cha (parent_id) nếu unit là bài con, ngược lại chính tên unit (node chương);
    lesson = tên unit nếu là bài con, None nếu là chương. summary/keywords là nội dung làm giàu
    khi nạp sách — giúp giải thích "hổng khái niệm/mục nào".
    """
    if not unit_ids:
        return {}
    rows = db.execute(
        text(
            """
            SELECT cu.id, cu.name, cu.parent_id, cu.summary, cu.keywords, p.name AS chapter_name
            FROM public.curriculum_units cu
            LEFT JOIN public.curriculum_units p ON p.id = cu.parent_id
            WHERE cu.id = ANY(:ids)
            """
        ),
        {"ids": unit_ids},
    ).fetchall()
    return {
        r.id: (
            r.name,
            (r.chapter_name if r.chapter_name else r.name) if r.parent_id else r.name,
            r.name if r.parent_id else None,
            r.summary,
            list(r.keywords) if r.keywords else None,
            r.parent_id,
        )
        for r in rows
    }


def _enrich_gap_item_confidence(item: KnowledgeGapItem, total_score: float | None = None) -> KnowledgeGapItem:
    """Bổ sung confidence_score (%) và confidence_reason cho 1 KnowledgeGapItem."""
    if item.evidence_detail and "c_total" in item.evidence_detail:
        c_score = float(item.evidence_detail["c_total"])
    elif item.confidence == "HIGH":
        c_score = 0.85
    elif item.confidence == "MEDIUM":
        c_score = 0.60
    elif item.confidence == "LOW":
        c_score = 0.35 if (item.n_items and item.n_items > 0) else 0.30
    else:
        c_score = 0.0

    delta = None
    exam_score = None
    if item.evidence_detail:
        if "delta" in item.evidence_detail:
            delta = float(item.evidence_detail["delta"])
        if "exam_mastery" in item.evidence_detail:
            exam_score = float(item.evidence_detail["exam_mastery"]) * 10.0
    if exam_score is None and total_score is not None:
        exam_score = total_score

    item.confidence_score = round(c_score, 3)
    item.confidence_reason = generate_confidence_reason(
        confidence=item.confidence or "LOW",
        confidence_score=item.confidence_score,
        n_items=item.n_items or 0,
        coverage=item.coverage,
        evidence_source=item.evidence_source or "LMS",
        integrity_status=item.integrity_status or "OK",
        delta=delta,
        exam_score=exam_score,
        bloom_count=len(item.bloom_breakdown) if item.bloom_breakdown else None,
    )
    return item


def _build_mastery_tree(items: list[KnowledgeGapItem]) -> list[KnowledgeGapItem]:
    """Tổ chức danh sách các unit thành Cây Thành thạo (Chương -> Bài học con)."""
    if not items:
        return []

    chapters_by_id: dict[int, KnowledgeGapItem] = {}
    lessons_by_parent: dict[int, list[KnowledgeGapItem]] = {}

    for item in items:
        if item.parent_id is None:
            item.is_chapter = True
            chapters_by_id[item.unit_id] = item
        else:
            item.is_chapter = False
            lessons_by_parent.setdefault(item.parent_id, []).append(item)

    result_chapters: list[KnowledgeGapItem] = []
    for cid, ch_item in chapters_by_id.items():
        child_lessons = lessons_by_parent.get(cid, [])
        child_lessons.sort(key=lambda lesson: lesson.unit_id)
        ch_item.lessons = child_lessons
        ch_item.total_lessons_count = len(child_lessons)
        if child_lessons:
            ch_raw_sum = sum((l.raw_mastery if l.raw_mastery is not None else l.mastery) for l in child_lessons)
            ch_item.raw_mastery = round(ch_raw_sum / len(child_lessons), 3)
            ch_item.gap_lessons_count = sum(1 for l in child_lessons if (l.raw_mastery if l.raw_mastery is not None else l.mastery) < 0.60)
        else:
            ch_item.gap_lessons_count = 1 if (ch_item.raw_mastery if ch_item.raw_mastery is not None else ch_item.mastery) < 0.60 else 0
        result_chapters.append(ch_item)

    # Nếu có bài học mà chapter chưa có trong danh sách, tạo node chapter bao bọc
    for pid, ch_lessons in lessons_by_parent.items():
        if pid not in chapters_by_id:
            ch_name = ch_lessons[0].chapter or f"Chương {pid}"
            avg_m = round(sum(lesson.mastery for lesson in ch_lessons) / len(ch_lessons), 3) if ch_lessons else 0.0
            ch_raw_sum = sum((l.raw_mastery if l.raw_mastery is not None else l.mastery) for l in ch_lessons)
            avg_raw_m = round(ch_raw_sum / len(ch_lessons), 3) if ch_lessons else 0.0
            synthetic_ch = KnowledgeGapItem(
                unit_id=pid,
                parent_id=None,
                unit_name=ch_name,
                chapter=ch_name,
                lesson=None,
                is_chapter=True,
                gap_score=round(1.0 - avg_m, 3),
                mastery=avg_m,
                raw_mastery=avg_raw_m,
                confidence=ch_lessons[0].confidence,
                confidence_score=ch_lessons[0].confidence_score,
                confidence_reason=ch_lessons[0].confidence_reason,
                coverage=1.0,
                integrity_status=ch_lessons[0].integrity_status,
                evidence_source=ch_lessons[0].evidence_source,
                lessons=ch_lessons,
                gap_lessons_count=sum(1 for lesson in ch_lessons if (lesson.raw_mastery if lesson.raw_mastery is not None else lesson.mastery) < 0.60),
                total_lessons_count=len(ch_lessons),
            )
            result_chapters.append(synthetic_ch)

    result_chapters.sort(key=lambda c: c.unit_id)
    return result_chapters


@router.get("/students/{student_code}", response_model=StudentKnowledgeGaps)
def get_student_knowledge_gaps(
    student_code: str,
    subject_id: int = Query(..., description="ID môn học (s360.dim_subject.id)"),
    school_year_id: int | None = Query(None, description="Năm học (để trống để lấy năm hiện tại)"),
    semester_index: int = Query(1),
    current_user: CurrentUser = None,
    db: Session = Depends(get_db),
):
    """Liệt kê các unit hổng kiến thức của 1 học sinh theo môn + học kỳ (dạng Cây Thành thạo).

    Nguồn 1: student_unit_mastery (mastery theo bài & chương từ LMS item-level + đối soát) — ưu tiên.
    Nguồn 2 (fallback): điểm tổng + exam_competencies khi chưa có LMS.
    """
    sy_id = _resolve_school_year(db, school_year_id)
    school_id = getattr(current_user, "so_school_id", None)

    # === Nguồn 1: student_unit_mastery (LMS item-level, đối soát) — ưu tiên nếu có. ===
    sum_cond = "AND sum.so_school_id = :school_id" if school_id else ""
    sum_params = {"sc": student_code, "sid": subject_id, "sem": semester_index}
    if school_id:
        sum_params["school_id"] = school_id
    sum_rows = db.execute(
        text(f"""
            SELECT sum.unit_id, sum.raw_mastery, sum.adjusted_mastery, sum.n_items,
                   sum.n_correct, sum.coverage, sum.confidence, sum.evidence_source,
                   sum.integrity_status, sum.evidence_detail, sum.lm_weight, sum.exam_weight
            FROM public.student_unit_mastery sum
            WHERE sum.student_code = :sc AND sum.subject_id = :sid
              AND sum.semester_index = :sem
              {sum_cond}
        """),
        sum_params,
    ).fetchall()

    mastery_units = [r for r in sum_rows if r.adjusted_mastery is not None]
    if mastery_units:
        meta = _unit_meta(db, [r.unit_id for r in mastery_units])

        # Lấy Bloom breakdown cho toàn bộ units của học sinh này
        bloom_by_unit: dict[int, list[BloomStatItem]] = {}
        try:
            uids = [int(r.unit_id) for r in mastery_units]
            bloom_rows = db.execute(
                text("""
                    SELECT 
                        qu.unit_id,
                        qb.bloom_level,
                        COUNT(qb.question_id) AS total_q,
                        COUNT(CASE WHEN qr.is_correct = true THEN 1 END) AS correct_q
                    FROM public.lms_question_bank qb
                    JOIN public.lms_question_unit qu ON qb.question_id = qu.question_id
                    LEFT JOIN public.lms_question_response qr 
                        ON qb.question_id = qr.question_id 
                       AND qr.student_code = :sc 
                       AND qr.is_best_attempt = true
                    WHERE qu.unit_id = ANY(:uids)
                    GROUP BY qu.unit_id, qb.bloom_level
                    ORDER BY qu.unit_id, qb.bloom_level
                """),
                {"sc": student_code, "uids": uids},
            ).fetchall()

            unit_bloom_map: dict[int, dict[int, tuple[int, int]]] = {}
            for br in bloom_rows:
                unit_bloom_map.setdefault(int(br.unit_id), {})[int(br.bloom_level)] = (int(br.total_q), int(br.correct_q))

            for uid in [r.unit_id for r in mastery_units]:
                stats = []
                for b in range(1, 7):
                    tot, corr = unit_bloom_map.get(uid, {}).get(b, (0, 0))
                    pct = round((corr / tot * 100.0), 1) if tot > 0 else 0.0
                    stats.append(
                        BloomStatItem(
                            bloom_level=b,
                            bloom_name=BLOOM_NAMES.get(b, f"Bloom {b}"),
                            total_questions=tot,
                            correct_count=corr,
                            incorrect_count=tot - corr,
                            accuracy_pct=pct,
                        )
                    )
                bloom_by_unit[uid] = stats
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning("Failed to calculate bloom_breakdown: %s", e)
            bloom_by_unit = {}

        raw_items = [
            _enrich_gap_item_confidence(
                KnowledgeGapItem(
                    unit_id=r.unit_id,
                    parent_id=meta.get(r.unit_id, (None, None, None, None, None, None))[5],
                    unit_name=meta.get(r.unit_id, (None, None, None, None, None, None))[0],
                    chapter=meta.get(r.unit_id, (None, None, None, None, None, None))[1],
                    lesson=meta.get(r.unit_id, (None, None, None, None, None, None))[2],
                    gap_score=round(1.0 - float(r.adjusted_mastery), 3),
                    mastery=round(float(r.adjusted_mastery), 3),
                    confidence=_confidence_label(r.confidence),
                    coverage=float(r.coverage) if r.coverage is not None else None,
                    integrity_status=r.integrity_status,
                    evidence_source=(r.evidence_source or "LMS"),
                    evidence_detail=dict(r.evidence_detail) if r.evidence_detail else None,
                    raw_mastery=float(r.raw_mastery) if r.raw_mastery is not None else None,
                    n_items=int(r.n_items) if r.n_items is not None else None,
                    n_correct=int(r.n_correct) if r.n_correct is not None else None,
                    lm_weight=float(r.lm_weight) if r.lm_weight is not None else None,
                    exam_weight=float(r.exam_weight) if r.exam_weight is not None else None,
                    bloom_breakdown=bloom_by_unit.get(r.unit_id, []),
                )
            )
            for r in mastery_units
        ]
        tree_gaps = _build_mastery_tree(raw_items)
        return StudentKnowledgeGaps(
            student_code=student_code,
            subject_id=subject_id,
            school_year_id=sy_id,
            semester_index=semester_index,
            gaps=tree_gaps,
        )

    # === Nguồn 2 (fallback): điểm tổng + exam_competencies — chỉ khi chưa có LMS mastery. ===
    units = _load_exam_units(db, subject_id, semester_index, school_id)
    score_row = _latest_locked_score(db, student_code, subject_id, sy_id, semester_index, school_id)
    if not units or score_row is None or score_row.final_grade is None:
        return StudentKnowledgeGaps(
            student_code=student_code,
            subject_id=subject_id,
            school_year_id=sy_id,
            semester_index=semester_index,
            gaps=[],
        )

    total_score = float(score_row.final_grade)
    max_score = float(score_row.max_grade) if score_row.max_grade else 10.0
    mastery_list = compute_unit_mastery(total_score, max_score, units)
    meta = _unit_meta(db, [m.unit_id for m in mastery_list])
    raw_items = [
        _enrich_gap_item_confidence(
            KnowledgeGapItem(
                unit_id=m.unit_id,
                parent_id=meta.get(m.unit_id, (None, None, None, None, None, None))[5],
                unit_name=meta.get(m.unit_id, (None, None, None, None, None, None))[0],
                chapter=meta.get(m.unit_id, (None, None, None, None, None, None))[1],
                lesson=meta.get(m.unit_id, (None, None, None, None, None, None))[2],
                summary=meta.get(m.unit_id, (None, None, None, None, None, None))[3],
                keywords=meta.get(m.unit_id, (None, None, None, None, None, None))[4],
                gap_score=m.gap_score,
                mastery=m.mastery,
                confidence="LOW",
                evidence_source="EXAM",
            ),
            total_score=total_score,
        )
        for m in mastery_list
    ]
    tree_gaps = _build_mastery_tree(raw_items)
    return StudentKnowledgeGaps(
        student_code=student_code,
        subject_id=subject_id,
        school_year_id=sy_id,
        semester_index=semester_index,
        gaps=tree_gaps,
    )



def _latest_locked_score(db: Session, student_code: str, subject_id: int, sy: int, sem: int, school_id: int | None):
    """Điểm tổng khóa gần nhất của học sinh (fallback EXAM khi chưa có item-level)."""
    school_cond = "AND fg.so_school_id = :school_id" if school_id else ""
    params = {"sc": student_code, "sid": subject_id, "sy": sy, "sem": sem}
    if school_id:
        params["school_id"] = school_id
    return db.execute(
        text(f"""
            SELECT fg.final_grade, fg.max_grade
            FROM s360.fact_gradebooks fg
            WHERE fg.student_code = :sc AND fg.subject_id = :sid
              AND fg.school_year_id = :sy AND fg.semester_index = :sem
              AND fg.is_locked = 1
              {school_cond}
            ORDER BY fg.created_at DESC
            LIMIT 1
        """),
        params,
    ).fetchone()


@router.get("/classes/{class_id}", response_model=ClassKnowledgeGaps)
def get_class_knowledge_gaps(
    class_id: int,
    subject_id: int = Query(..., description="ID môn học (s360.dim_subject.id)"),
    school_year_id: int | None = Query(None, description="Năm học (để trống để lấy năm hiện tại)"),
    semester_index: int = Query(1),
    current_user: CurrentUser = None,
    db: Session = Depends(get_db),
):
    """Unit hổng phổ biến của cả lớp (trung bình gap_score các học sinh)."""
    sy_id = _resolve_school_year(db, school_year_id)
    school_id = getattr(current_user, "so_school_id", None)

    units = _load_exam_units(db, subject_id, semester_index, school_id)
    if not units:
        return ClassKnowledgeGaps(
            class_id=class_id,
            subject_id=subject_id,
            school_year_id=sy_id,
            semester_index=semester_index,
            gaps=[],
        )

    # Điểm tổng của mọi học sinh trong lớp (fact_gradebooks) kèm Tenant isolation.
    school_cond = "AND fg.so_school_id = :school_id" if school_id else ""
    params = {"sid": subject_id, "sy": sy_id, "sem": semester_index, "cid": class_id}
    if school_id:
        params["school_id"] = school_id

    rows = db.execute(
        text(f"""
            SELECT fg.student_code, fg.final_grade, fg.max_grade
            FROM s360.fact_gradebooks fg
            WHERE fg.subject_id = :sid
              AND fg.school_year_id = :sy AND fg.semester_index = :sem
              AND fg.homeroom_class_id = :cid
              AND fg.is_locked = 1
              {school_cond}
        """),
        params,
    ).fetchall()

    if not rows:
        return ClassKnowledgeGaps(
            class_id=class_id,
            subject_id=subject_id,
            school_year_id=sy_id,
            semester_index=semester_index,
            gaps=[],
        )

    # Gộp gap_score theo unit.
    acc: dict[int, list[float]] = {}
    for r in rows:
        total = float(r.final_grade) if r.final_grade is not None else 0.0
        max_score = float(r.max_grade) if r.max_grade else 10.0
        for m in compute_unit_mastery(total, max_score, units):
            if m.gap_score > 0:
                acc.setdefault(m.unit_id, []).append(m.gap_score)

    meta = _unit_meta(db, list(acc.keys()))
    gaps = [
        KnowledgeGapItem(
            unit_id=uid,
            unit_name=meta.get(uid, (None, None, None, None, None))[0],
            chapter=meta.get(uid, (None, None, None, None, None))[1],
            lesson=meta.get(uid, (None, None, None, None, None))[2],
            summary=meta.get(uid, (None, None, None, None, None))[3],
            keywords=meta.get(uid, (None, None, None, None, None))[4],
            gap_score=round(sum(v) / len(v), 3),
            mastery=round(1.0 - sum(v) / len(v), 3),
            evidence_source="EXAM",
        )
        for uid, v in sorted(acc.items(), key=lambda kv: -sum(kv[1]) / len(kv[1]))
    ]
    return ClassKnowledgeGaps(
        class_id=class_id,
        subject_id=subject_id,
        school_year_id=sy_id,
        semester_index=semester_index,
        gaps=gaps,
    )


@router.get("/classes/{class_id}/roster", response_model=ClassRosterResponse)
def get_class_diagnostic_roster(
    class_id: int,
    subject_id: int = Query(..., description="ID môn học (s360.dim_subject.id)"),
    school_year_id: int | None = Query(None, description="Năm học (để trống để lấy năm hiện tại)"),
    semester_index: int = Query(1),
    current_user: CurrentUser = None,
    db: Session = Depends(get_db),
):
    """Danh sách chẩn đoán toàn bộ học sinh trong lớp theo môn học + học kỳ.

    Phục vụ giao diện Roster tổng quan của lớp: hiển thị % thành thạo từng em,
    số chương hổng, cờ đối soát (nghi gian lận/tham gia LMS thấp) để giáo viên
    click vào xem chi tiết từng em.
    """
    sy_id = _resolve_school_year(db, school_year_id)
    school_id = getattr(current_user, "so_school_id", None)

    # 1. Lấy thông tin lớp và môn
    class_row = db.execute(
        text("SELECT id, fullname, code FROM s360.dim_homeroom_class WHERE id = :cid"),
        {"cid": class_id},
    ).fetchone()
    class_name = class_row.fullname if class_row else f"Lớp {class_id}"

    subject_row = db.execute(
        text("SELECT id, name FROM s360.dim_subject WHERE id = :sid"),
        {"sid": subject_id},
    ).fetchone()
    subject_name = subject_row.name if subject_row else f"Môn {subject_id}"

    # 2. Lấy danh sách học sinh của lớp
    school_cond = "AND s.so_school_id = :school_id" if school_id else ""
    st_params = {"cid": class_id, "sy": sy_id}
    if school_id:
        st_params["school_id"] = school_id
    students_rows = db.execute(
        text(f"""
            SELECT s.student_code, s.student_name
            FROM s360.dim_homeroom_class_student s
            WHERE s.homeroom_class_id = :cid AND s.school_year_id = :sy
              {school_cond}
            ORDER BY s.student_code ASC
        """),
        st_params,
    ).fetchall()

    if not students_rows:
        return ClassRosterResponse(
            class_id=class_id,
            class_name=class_name,
            subject_id=subject_id,
            subject_name=subject_name,
            school_year_id=sy_id,
            semester_index=semester_index,
            total_students=0,
            mastered_all_count=0,
            need_support_count=0,
            cheating_alert_count=0,
            low_engagement_count=0,
            students=[],
        )

    student_codes = [r.student_code for r in students_rows]

    # 3. Lấy dữ liệu student_unit_mastery của toàn bộ học sinh trong lớp (batch)
    sum_cond = "AND sum.so_school_id = :school_id" if school_id else ""
    sum_params = {"codes": student_codes, "sid": subject_id, "sem": semester_index}
    if school_id:
        sum_params["school_id"] = school_id
    sum_rows = db.execute(
        text(f"""
            SELECT sum.student_code, sum.unit_id, sum.raw_mastery, sum.adjusted_mastery,
                   sum.n_items, sum.n_correct, sum.coverage, sum.confidence,
                   sum.evidence_source, sum.integrity_status, sum.evidence_detail,
                   sum.lm_weight, sum.exam_weight
            FROM public.student_unit_mastery sum
            WHERE sum.student_code = ANY(:codes) AND sum.subject_id = :sid
              AND sum.semester_index = :sem
              {sum_cond}
        """),
        sum_params,
    ).fetchall()

    # Gom mastery theo student_code
    sum_by_student: dict[str, list] = {}
    all_unit_ids: set[int] = set()
    for r in sum_rows:
        if r.adjusted_mastery is not None:
            sum_by_student.setdefault(r.student_code, []).append(r)
            all_unit_ids.add(r.unit_id)

    # 4. Fallback: Đề thi cho học sinh chưa có LMS
    exam_units = _load_exam_units(db, subject_id, semester_index, school_id)
    all_unit_ids.update(u.unit_id for u in exam_units)

    # Metadata của toàn bộ unit
    meta = _unit_meta(db, list(all_unit_ids)) if all_unit_ids else {}

    # 4b. Lấy Bloom breakdown cho toàn bộ học sinh và unit trong lớp (batch aggregation)
    student_unit_bloom_map: dict[tuple[str, int], dict[int, tuple[int, int]]] = {}
    if student_codes and all_unit_ids:
        try:
            b_rows = db.execute(
                text("""
                    SELECT 
                        qr.student_code,
                        qu.unit_id,
                        qb.bloom_level,
                        COUNT(qb.question_id) AS total_q,
                        COUNT(CASE WHEN qr.is_correct = true THEN 1 END) AS correct_q
                    FROM public.lms_question_bank qb
                    JOIN public.lms_question_unit qu ON qb.question_id = qu.question_id
                    LEFT JOIN public.lms_question_response qr 
                        ON qb.question_id = qr.question_id 
                       AND qr.student_code = ANY(:codes)
                       AND qr.is_best_attempt = true
                    WHERE qu.unit_id = ANY(:uids)
                    GROUP BY qr.student_code, qu.unit_id, qb.bloom_level
                    ORDER BY qr.student_code, qu.unit_id, qb.bloom_level
                """),
                {"codes": student_codes, "uids": list(all_unit_ids)},
            ).fetchall()
            for br in b_rows:
                if br.student_code:
                    student_unit_bloom_map.setdefault((str(br.student_code), int(br.unit_id)), {})[int(br.bloom_level)] = (int(br.total_q), int(br.correct_q))
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning("Failed to calculate class bloom_breakdown: %s", e)

    def _get_student_bloom_stats(sc_code: str, u_id: int) -> list[BloomStatItem]:
        bm = student_unit_bloom_map.get((sc_code, u_id), {})
        stats = []
        for b in range(1, 7):
            tot, corr = bm.get(b, (0, 0))
            pct = round((corr / tot * 100.0), 1) if tot > 0 else 0.0
            stats.append(
                BloomStatItem(
                    bloom_level=b,
                    bloom_name=BLOOM_NAMES.get(b, f"Bloom {b}"),
                    total_questions=tot,
                    correct_count=corr,
                    incorrect_count=tot - corr,
                    accuracy_pct=pct,
                )
            )
        return stats

    # 5. Xây dựng hồ sơ chẩn đoán cho từng học sinh
    roster: list[StudentRosterSummary] = []
    for s in students_rows:
        sc = s.student_code
        s_name = s.student_name or sc
        s_sum_rows = sum_by_student.get(sc, [])

        raw_items: list[KnowledgeGapItem] = []
        if s_sum_rows:
            # Nguồn 1: student_unit_mastery
            raw_items = [
                _enrich_gap_item_confidence(
                    KnowledgeGapItem(
                        unit_id=r.unit_id,
                        parent_id=meta.get(r.unit_id, (None, None, None, None, None, None))[5],
                        unit_name=meta.get(r.unit_id, (None, None, None, None, None, None))[0],
                        chapter=meta.get(r.unit_id, (None, None, None, None, None, None))[1],
                        lesson=meta.get(r.unit_id, (None, None, None, None, None, None))[2],
                        gap_score=round(1.0 - float(r.adjusted_mastery), 3),
                        mastery=round(float(r.adjusted_mastery), 3),
                        confidence=_confidence_label(r.confidence),
                        coverage=float(r.coverage) if r.coverage is not None else None,
                        integrity_status=r.integrity_status,
                        evidence_source=(r.evidence_source or "LMS"),
                        evidence_detail=dict(r.evidence_detail) if r.evidence_detail else None,
                        raw_mastery=float(r.raw_mastery) if r.raw_mastery is not None else None,
                        n_items=int(r.n_items) if r.n_items is not None else None,
                        n_correct=int(r.n_correct) if r.n_correct is not None else None,
                        lm_weight=float(r.lm_weight) if r.lm_weight is not None else None,
                        exam_weight=float(r.exam_weight) if r.exam_weight is not None else None,
                        bloom_breakdown=_get_student_bloom_stats(sc, r.unit_id),
                    )
                )
                for r in s_sum_rows
            ]
        else:
            # Nguồn 2: Fallback điểm thi trên lớp
            score_row = _latest_locked_score(db, sc, subject_id, sy_id, semester_index, school_id)
            if exam_units and score_row and score_row.final_grade is not None:
                total_score = float(score_row.final_grade)
                max_score = float(score_row.max_grade) if score_row.max_grade else 10.0
                mastery_list = compute_unit_mastery(total_score, max_score, exam_units)
                raw_items = [
                    _enrich_gap_item_confidence(
                        KnowledgeGapItem(
                            unit_id=m.unit_id,
                            parent_id=meta.get(m.unit_id, (None, None, None, None, None, None))[5],
                            unit_name=meta.get(m.unit_id, (None, None, None, None, None, None))[0],
                            chapter=meta.get(m.unit_id, (None, None, None, None, None, None))[1],
                            lesson=meta.get(m.unit_id, (None, None, None, None, None, None))[2],
                            summary=meta.get(m.unit_id, (None, None, None, None, None, None))[3],
                            keywords=meta.get(m.unit_id, (None, None, None, None, None, None))[4],
                            gap_score=m.gap_score,
                            mastery=m.mastery,
                            confidence="LOW",
                            evidence_source="EXAM",
                        ),
                        total_score=total_score,
                    )
                    for m in mastery_list
                ]

        tree_gaps = _build_mastery_tree(raw_items)

        # Tính toán các chỉ số cho học sinh
        if tree_gaps:
            # Thu thập toàn bộ các bài học con hoặc chương để tính trung bình theo LMS
            all_leaf_units: list[KnowledgeGapItem] = []
            weak_u: list[str] = []
            for ch in tree_gaps:
                if ch.lessons:
                    all_leaf_units.extend(ch.lessons)
                    for lesson in ch.lessons:
                        l_val = lesson.raw_mastery if lesson.raw_mastery is not None else lesson.mastery
                        if l_val < 0.60:
                            weak_u.append(lesson.lesson or lesson.unit_name or f"Bài {lesson.unit_id}")
                else:
                    all_leaf_units.append(ch)
                    ch_val = ch.raw_mastery if ch.raw_mastery is not None else ch.mastery
                    if ch_val < 0.60:
                        weak_u.append(ch.unit_name or f"Chương {ch.unit_id}")

            total_u = len(all_leaf_units)
            # Ưu tiên năng lực LMS thực chất làm chỉ số chính
            avg_m = round(sum((g.raw_mastery if g.raw_mastery is not None else g.mastery) for g in all_leaf_units) / total_u, 3) if total_u > 0 else 0.0
            gap_c = sum(1 for g in all_leaf_units if (g.raw_mastery if g.raw_mastery is not None else g.mastery) < 0.60)
            mastered_c = sum(1 for g in all_leaf_units if (g.raw_mastery if g.raw_mastery is not None else g.mastery) >= 0.60)

            # Xác định trạng thái đối soát tổng thể theo Quy tắc Đa số (Majority Rule)
            n_low = sum(1 for g in raw_items if g.integrity_status == "LOW_ENGAGEMENT")
            n_exceed = sum(1 for g in raw_items if g.integrity_status in ("LMS_EXCEEDS_EXAM", "SUSPECTED_CHEATING"))
            n_ok = sum(1 for g in raw_items if g.integrity_status == "OK")

            if n_exceed > 0 and n_exceed >= n_ok:
                overall_integ = "LMS_EXCEEDS_EXAM"
            elif n_low > 0 and n_low >= n_ok:
                overall_integ = "LOW_ENGAGEMENT"
            elif any(g.integrity_status == "FLAGGED" for g in raw_items):
                overall_integ = "FLAGGED"
            elif any(g.integrity_status == "LMS_ONLY" for g in raw_items) and n_ok == 0:
                overall_integ = "LMS_ONLY"
            else:
                overall_integ = "OK"

            ev_src = raw_items[0].evidence_source if raw_items else "HYBRID"

            total_items = sum(g.n_items or 0 for g in raw_items)
            avg_cov = (sum(g.coverage or 0.0 for g in raw_items) / len(raw_items)) if raw_items else 0.0

            # Tính độ tin cậy trung bình thực tế từ các bài học của học sinh
            conf_scores = [g.confidence_score for g in raw_items if g.confidence_score is not None]
            if conf_scores:
                summary_conf_score = round(sum(conf_scores) / len(conf_scores), 3)
            elif ev_src == "EXAM":
                summary_conf_score = 0.30
            else:
                summary_conf_score = 0.50

            # Phân loại nhãn theo % tin cậy thực tế (>= 75% HIGH, 45-74% MEDIUM, < 45% LOW)
            if summary_conf_score >= 0.75:
                overall_conf = "HIGH"
            elif summary_conf_score >= 0.45:
                overall_conf = "MEDIUM"
            elif summary_conf_score > 0.0:
                overall_conf = "LOW"
            else:
                overall_conf = "INSUFFICIENT"

            summary_conf_reason = generate_confidence_reason(
                confidence=overall_conf,
                confidence_score=summary_conf_score,
                n_items=total_items,
                coverage=avg_cov,
                evidence_source=ev_src,
                integrity_status=overall_integ,
            )
        else:
            avg_m = 0.0
            gap_c = 0
            mastered_c = 0
            total_u = 0
            weak_u = []
            overall_integ = "INSUFFICIENT"
            overall_conf = "INSUFFICIENT"
            summary_conf_score = 0.0
            summary_conf_reason = "Chưa có dữ liệu bài tập hoặc bài thi."
            ev_src = "INSUFFICIENT"

        roster.append(
            StudentRosterSummary(
                student_code=sc,
                student_name=s_name,
                avg_mastery=avg_m,
                gap_count=gap_c,
                mastered_count=mastered_c,
                total_units=total_u,
                weak_units=weak_u,
                integrity_status=overall_integ,
                confidence=overall_conf,
                confidence_score=summary_conf_score,
                confidence_reason=summary_conf_reason,
                evidence_source=ev_src,
                gaps=tree_gaps,
            )
        )

    return ClassRosterResponse(
        class_id=class_id,
        class_name=class_name,
        subject_id=subject_id,
        subject_name=subject_name,
        school_year_id=sy_id,
        semester_index=semester_index,
        total_students=len(roster),
        mastered_all_count=sum(1 for s in roster if s.gap_count == 0 and s.total_units > 0),
        need_support_count=sum(1 for s in roster if s.gap_count > 0),
        cheating_alert_count=sum(1 for s in roster if s.integrity_status in ("LMS_EXCEEDS_EXAM", "SUSPECTED_CHEATING")),
        low_engagement_count=sum(1 for s in roster if s.integrity_status == "LOW_ENGAGEMENT"),
        students=roster,
    )


@router.post("/recalc-mastery", response_model=RecalcMasteryResult)
def recalc_mastery_endpoint(
    subject_id: int = Query(..., description="ID môn học cần tính lại năng lực"),
    semester_index: int = Query(1, description="Học kỳ"),
    current_user: CurrentUser = None,
    db: Session = Depends(get_db),
):
    """Tính toán lại toàn bộ student_unit_mastery từ lms_question_response cho môn học."""
    school_id = getattr(current_user, "so_school_id", None)
    count = recalc_unit_mastery(db, subject_id=subject_id, semester_index=semester_index, school_id=school_id)
    return RecalcMasteryResult(
        success=True,
        records_calculated=count,
        subject_id=subject_id,
        semester_index=semester_index,
        message=f"Đã tính toán và cập nhật thành công {count} bản ghi năng lực học sinh",
    )


@router.post("/lms-question-bank/analyze", response_model=AnalyzeLmsBankResponse)
def analyze_lms_question_bank_endpoint(
    req: AnalyzeLmsBankRequest,
    background_tasks: BackgroundTasks,
    current_user: CurrentUser = None,
    db: Session = Depends(get_db),
):
    """Khởi tạo Background Job phân tích câu hỏi LMS bằng AI và gán mức độ Bloom."""
    job_id = job_manager.create_job(subject_id=req.subject_id, total_questions=req.limit or 0)
    background_tasks.add_task(
        run_analysis_job_in_background,
        job_id=job_id,
        subject_id=req.subject_id,
        model_name=req.model_name,
        re_analyze=req.re_analyze,
        limit=req.limit,
    )
    return AnalyzeLmsBankResponse(
        success=True,
        job_id=job_id,
        status="running",
        processed_count=0,
        unclassified_remaining=0,
        bloom_distribution={},
        items=[],
        message=f"Đã bắt đầu tác vụ phân tích AI (Mã Job: {job_id})",
    )


@router.get("/lms-question-bank/analyze/status", response_model=LmsJobStatusResponse)
def get_lms_analysis_status_endpoint(
    subject_id: int = Query(..., description="ID môn học"),
    job_id: str | None = Query(None, description="Mã job cụ thể (nếu có)"),
    current_user: CurrentUser = None,
):
    """Lấy trạng thái và tiến độ thời gian thực của job phân tích câu hỏi LMS."""
    if job_id:
        job = job_manager.get_job(job_id)
    else:
        job = job_manager.get_latest_job(subject_id)

    if not job:
        return LmsJobStatusResponse(status="idle", message="Chưa có tác vụ nào đang chạy.")

    return LmsJobStatusResponse(
        job_id=job.job_id,
        subject_id=job.subject_id,
        status=job.status,
        total_questions=job.total_questions,
        processed_questions=job.processed_questions,
        progress_percent=job.progress_percent,
        bloom_distribution=job.bloom_distribution,
        unclassified_remaining=job.unclassified_remaining,
        error_message=job.error_message,
        started_at=job.started_at,
        finished_at=job.finished_at,
        message=job.message,
    )


BLOOM_NAMES: dict[int, str] = {
    1: "Nhớ (Nhận biết)",
    2: "Hiểu (Thông hiểu)",
    3: "Vận dụng",
    4: "Phân tích",
    5: "Đánh giá",
    6: "Sáng tạo",
}


@router.get("/students/{student_code}/units/{unit_id}/drilldown", response_model=StudentUnitBloomDrilldownResponse)
def get_student_unit_bloom_drilldown(
    student_code: str,
    unit_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = None,
) -> StudentUnitBloomDrilldownResponse:
    """Drilldown chi tiết phân tích thang Bloom và danh sách câu hỏi trắc nghiệm của 1 học sinh theo bài học."""
    # 1. Lấy thông tin bài học & chương
    unit_sql = text("""
        SELECT u.id, u.name AS unit_name, COALESCE(cu.name, 'Chương') AS chapter_name
        FROM public.curriculum_units u
        LEFT JOIN public.curriculum_units cu ON u.parent_id = cu.id
        WHERE u.id = :unit_id
    """)
    unit_row = db.execute(unit_sql, {"unit_id": unit_id}).fetchone()
    unit_name = unit_row.unit_name if unit_row else f"Bài học {unit_id}"
    chapter_name = unit_row.chapter_name if unit_row else "Chương"

    # 2. Lấy thông tin student_unit_mastery
    mastery_sql = text("""
        SELECT raw_mastery, n_items, n_correct
        FROM public.student_unit_mastery
        WHERE student_code = :student_code AND unit_id = :unit_id
        ORDER BY semester_index DESC LIMIT 1
    """)
    m_row = db.execute(mastery_sql, {"student_code": student_code, "unit_id": unit_id}).fetchone()
    raw_mastery = float(m_row.raw_mastery) if m_row and m_row.raw_mastery is not None else 0.0

    # 3. Lấy toàn bộ câu hỏi trắc nghiệm của bài học này mà học sinh đã làm
    q_sql = text("""
        SELECT 
            qb.question_id,
            qb.assignment_id,
            dsa.fullname AS assignment_name,
            qb.question_text,
            qb.bloom_level,
            qr.is_correct,
            qr.score_received,
            qr.max_score,
            qr.response_time_seconds,
            qr.attempt_number,
            qr.integrity_flag,
            qr.response_payload
        FROM public.lms_question_bank qb
        JOIN public.lms_question_unit qu ON qb.question_id = qu.question_id AND qu.unit_id = :unit_id
        LEFT JOIN s360.dim_so_assignment dsa ON qb.assignment_id = dsa.assignment_id
        LEFT JOIN public.lms_question_response qr
            ON qb.question_id = qr.question_id
           AND qr.student_code = :student_code
           AND qr.is_best_attempt = true
        ORDER BY qb.bloom_level ASC, qb.question_id ASC
    """)
    rows = db.execute(q_sql, {"unit_id": unit_id, "student_code": student_code}).fetchall()

    questions: list[StudentUnitQuestionItem] = []
    bloom_counts: dict[int, dict[str, int]] = {
        b: {"total": 0, "correct": 0, "incorrect": 0} for b in range(1, 7)
    }

    for r in rows:
        b_level = r.bloom_level if r.bloom_level in range(1, 7) else 2
        is_corr = bool(r.is_correct) if r.is_correct is not None else None
        
        bloom_counts[b_level]["total"] += 1
        if is_corr is True:
            bloom_counts[b_level]["correct"] += 1
        elif is_corr is False:
            bloom_counts[b_level]["incorrect"] += 1

        chosen_opt = None
        options = None
        corr_opt = None
        explanation = None

        if r.response_payload and isinstance(r.response_payload, dict):
            chosen_opt = r.response_payload.get("chosen_option")
            options = r.response_payload.get("options")
            corr_opt = r.response_payload.get("correct_option")
            explanation = r.response_payload.get("explanation")

        questions.append(
            StudentUnitQuestionItem(
                question_id=r.question_id,
                assignment_id=r.assignment_id,
                assignment_name=r.assignment_name,
                question_text=r.question_text or f"Câu hỏi {r.question_id}",
                bloom_level=b_level,
                is_correct=is_corr,
                score_received=float(r.score_received or 0.0),
                max_score=float(r.max_score or 1.0),
                response_time_seconds=r.response_time_seconds,
                attempt_number=r.attempt_number or 1,
                integrity_flag=r.integrity_flag or 0,
                chosen_option=chosen_opt,
                options=options,
                correct_option=corr_opt,
                explanation=explanation,
            )
        )

    # 4. Tính toán BloomStatItem
    bloom_stats = []
    for b in range(1, 7):
        bc = bloom_counts[b]
        tot = bc["total"]
        corr = bc["correct"]
        pct = round((corr / tot * 100.0), 1) if tot > 0 else 0.0
        bloom_stats.append(
            BloomStatItem(
                bloom_level=b,
                bloom_name=BLOOM_NAMES.get(b, f"Bloom {b}"),
                total_questions=tot,
                correct_count=corr,
                incorrect_count=bc["incorrect"],
                accuracy_pct=pct,
            )
        )

    total_items = len(questions)
    total_correct = sum(1 for q in questions if q.is_correct is True)

    return StudentUnitBloomDrilldownResponse(
        student_code=student_code,
        unit_id=unit_id,
        unit_name=unit_name,
        chapter_name=chapter_name,
        total_items=total_items,
        total_correct=total_correct,
        raw_mastery=raw_mastery,
        bloom_stats=bloom_stats,
        questions=questions,
    )


