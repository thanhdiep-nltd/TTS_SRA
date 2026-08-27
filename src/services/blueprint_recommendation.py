"""Gợi ý ma trận đề từ năng lực thực tế của trường (RCM cho AI Exam Generation).

Liên hệ các chức năng đã có: năng lực khối lấy từ TEVI (`exam_validity.py`), chỗ HS hay sai
lấy từ `misconceptions` + `p_value` kho câu, chương chưa được kiểm tra lấy từ `exam_competencies`
các đề cùng kỳ. Hệ CHỈ đề xuất — GV luôn xem/chỉnh `cells` rồi tự POST /exam-blueprints để lưu
thật (không tự động lưu ma trận). Xem docs/superpowers/plans/2026-07-06-exam-builder-from-bank.md §5.

Cơ cấu loại đề (TN/TL) được chốt SỐ CÂU + ĐIỂM ở cấp "rổ" (basket) TRƯỚC khi chia nhỏ tiếp
theo Bloom rồi theo đơn vị — tránh rổ nhỏ (vd tự luận khi total_questions ít) bị làm tròn về 0
mất hẳn qua nhiều tầng chia. Bloom 1-6 dùng trực tiếp (không qua band NB/TH/VD/VDC như trước —
cách cũ chỉ chạm được Bloom 1/2/3/5, bỏ sót 4/6).
"""

import math
import random
from uuid import UUID

from sqlalchemy import func, or_, select, text
from sqlalchemy.orm import Session

from src.models import enums
from src.models.tables import CurriculumUnit, ExamCompetency, ExamPaper, Grade, Misconception, QuestionItem
from src.schemas.exam_generation import BlueprintDraft, RecommendBlueprintRequest, RecommendCellDraft
from src.services import exam_assembly, exam_validity

# Tỉ lệ bài học được CHỌN NGẪU NHIÊN trong 1 chương khi GV chỉ tick cả chương (chưa tự mở rộng
# chọn bài cụ thể) — đỡ GV phải tick từng bài, đề vẫn bám sát bài học cụ thể thay vì cả chương
# chung chung. GV luôn xem/chỉnh lại được ở Step 2 nếu thấy chưa phù hợp.
_LESSON_SAMPLE_RATIO = 0.7

_DEFAULT_ABILITY = 6.5
_TARGET_BASE = 0.35
_TARGET_SLOPE = 0.05
_TARGET_MIN, _TARGET_MAX = 0.25, 0.60
_WEAK_P_VALUE_THRESHOLD = 0.5

_MISCONCEPTION_BOOST = 1.5
_WEAK_KHO_BOOST = 1.3
_COVERAGE_GAP_BOOST = 1.2

_MIN_POINTS_EACH = 0.25  # sàn điểm/câu (đơn vị làm tròn điểm)

# Độ rộng lân cận Gauss quanh tâm khi rải Bloom theo target_difficulty — lớn hơn = trải đều
# nhiều mức Bloom hơn (giữ "đầy đủ độ khó"), nhỏ hơn = tập trung sát 1-2 mức quanh tâm.
_BLOOM_SIGMA = 1.4
# Số vòng lặp hiệu chỉnh tâm Gauss để bù sai số do bị cắt cụt ở biên [1,6] (Bloom không thể
# vượt phạm vi này) — hội tụ rất nhanh (hàm gần tuyến tính quanh vùng target hợp lệ 0.25-0.60).
_BLOOM_FIT_ITERATIONS = 6

_TN_TYPES = {enums.QuestionType.MCQ, enums.QuestionType.TRUE_FALSE, enums.QuestionType.SHORT_ANSWER}
_TL_TYPES = {enums.QuestionType.ESSAY}

_EXAM_FORMAT_LABELS = {
    enums.ExamFormat.MCQ_ONLY: "100% trắc nghiệm",
    enums.ExamFormat.ESSAY_ONLY: "100% tự luận",
    enums.ExamFormat.MIXED: "kết hợp trắc nghiệm + tự luận",
}


class RecommendationInputError(ValueError):
    """Đầu vào không hợp lệ để gợi ý ma trận: khối không thuộc trường của user, chương chọn
    không thuộc đúng môn/khối, hoặc số câu/tổng điểm không khả thi (vd quá nhiều câu so với
    tổng điểm cho phép ở sàn điểm/câu tối thiểu)."""


# ============================================================
# LOGIC THUẦN (không DB)
# ============================================================


def target_difficulty_from_ability(ability: float) -> float:
    """Năng lực càng cao -> đề càng khó hơn một chút để giữ phân hóa (kẹp 0.25..0.60)."""
    raw = _TARGET_BASE + (ability - _DEFAULT_ABILITY) * _TARGET_SLOPE
    return round(max(_TARGET_MIN, min(_TARGET_MAX, raw)), 3)


def _gaussian_bloom_weights(center: float, sigma: float = _BLOOM_SIGMA) -> dict[int, float]:
    """Trọng số Bloom (1-6, tổng=1) theo hình Gauss rời rạc quanh `center`."""
    raw = {b: math.exp(-((b - center) ** 2) / (2 * sigma * sigma)) for b in range(1, 7)}
    total = sum(raw.values())
    return {b: w / total for b, w in raw.items()}


def bloom_distribution_for_target(target_difficulty: float, sigma: float = _BLOOM_SIGMA) -> dict[int, float]:
    """Phân phối Bloom (1-6) sao cho CDI kỳ vọng (Σbloom·weight/6) XẤP XỈ đúng target_difficulty
    — CHUNG cho cả trắc nghiệm lẫn tự luận trong cùng 1 đề (không tách band năng lực + bảng TN/
    TL riêng như trước, vốn không liên kết với target_difficulty và gây CDI hiển thị lệch xa
    độ khó mục tiêu, vd 0.31 vs 0.53). Dùng Gauss rời rạc quanh center=target_difficulty*6, hiệu
    chỉnh tâm lặp lại vài vòng để bù sai số do bị cắt cụt ở biên [1,6] (Bloom không vượt phạm vi
    này) — nhờ đó CDI thực tế sau khi rải cells luôn bám sát target_difficulty đã hiện cho GV."""
    target_mean = target_difficulty * 6.0
    center = target_mean
    for _ in range(_BLOOM_FIT_ITERATIONS):
        weights = _gaussian_bloom_weights(center, sigma)
        mean = sum(b * w for b, w in weights.items())
        center += target_mean - mean
    return _gaussian_bloom_weights(center, sigma)


def normalize_unit_weights(raw: dict[UUID, float]) -> dict[UUID, float]:
    total = sum(raw.values())
    if total <= 0:
        n = len(raw)
        return dict.fromkeys(raw, 1.0 / n) if n else {}
    return {k: v / total for k, v in raw.items()}


def boosted_unit_weights(
    unit_ids: list[UUID],
    misconception_counts: dict[UUID, int],
    weak_units: set[UUID],
    uncovered_units: set[UUID],
) -> dict[UUID, float]:
    """Trọng số ban đầu đều nhau; boost chương có lỗi sai phổ biến / kho yếu / chưa kiểm tra
    gần đây — ưu tiên chỗ đáng kiểm tra hơn là xoay vòng nội dung cũ."""
    raw: dict[UUID, float] = {}
    for uid in unit_ids:
        weight = 1.0
        if misconception_counts.get(uid, 0) > 0:
            weight *= _MISCONCEPTION_BOOST
        if uid in weak_units:
            weight *= _WEAK_KHO_BOOST
        if uid in uncovered_units:
            weight *= _COVERAGE_GAP_BOOST
        raw[uid] = weight
    return normalize_unit_weights(raw)


def _round_to_quarter(value: float) -> float:
    return round(value * 4) / 4


def _reconcile_total(cells: list[dict], total_points: float, tolerance: float = 0.01) -> None:
    """Hiệu chỉnh CHÍNH XÁC Σ điểm khớp total_points (bắt buộc để lưu — _validate_cells_sum
    yêu cầu sai số ≤0.01). Chỉnh trực tiếp points_each của ĐÚNG 1 ô — ô có SỐ CÂU NHIỀU NHẤT
    (chia đều phần lệch cho nhiều câu nhất -> điểm/câu lệch đi ít nhất, ít gây chú ý nhất khi
    GV xem lại ở Step 2). Không dò bằng cách nhích ±1 câu như trước: cách đó có thể KHÔNG BAO
    GIỜ hội tụ nếu phần lệch không phải bội số của bất kỳ points_each nào đang có (bug thật đã
    gặp: lệch 0.25đ nhưng mọi ô đều 0.5đ/câu -> nhích ±1 câu dao động vĩnh viễn giữa +0.25/-0.25)."""
    if not cells:
        return
    summed = sum(c["num_questions"] * c["points_each"] for c in cells)
    diff = total_points - summed
    if abs(diff) <= tolerance:
        return
    valve = max(cells, key=lambda c: c["num_questions"])
    valve["points_each"] = round(max(valve["points_each"] + diff / valve["num_questions"], 0.01), 4)


def _validate_size_inputs(total_points: float, total_questions: int) -> None:
    """Số câu × sàn điểm/câu không được vượt tổng điểm đề — nếu không, ô nào cũng phải kẹp
    dưới sàn và Σ điểm sẽ không thể khớp total_points khi lưu (422 khó hiểu ở bước sau)."""
    floor_total = round(total_questions * _MIN_POINTS_EACH, 2)
    if floor_total > total_points:
        raise RecommendationInputError(
            f"{total_questions} câu với sàn {_MIN_POINTS_EACH} điểm/câu cần tối thiểu {floor_total} điểm — "
            f"vượt quá tổng điểm đề ({total_points}). Giảm số câu hoặc tăng tổng điểm."
        )


def _basket_plan(
    exam_format: enums.ExamFormat, total_points: float, total_questions: int, mix_ratio: float
) -> list[tuple[enums.QuestionType, float, int]]:
    """Chốt (loại câu, điểm rổ, số câu rổ) TRƯỚC khi chia nhỏ — basket-first. Với MIXED, đảm
    bảo rổ tự luận có ít nhất 1 câu nếu total_questions>=2 (tránh rổ nhỏ biến mất khi làm tròn
    nhiều tầng phía sau)."""
    if exam_format == enums.ExamFormat.MCQ_ONLY:
        return [(enums.QuestionType.MCQ, total_points, total_questions)]
    if exam_format == enums.ExamFormat.ESSAY_ONLY:
        return [(enums.QuestionType.ESSAY, total_points, total_questions)]
    mcq_questions = round(total_questions * mix_ratio)
    essay_questions = total_questions - mcq_questions
    if essay_questions < 1 and total_questions >= 2:
        essay_questions = 1
        mcq_questions = total_questions - 1
    mcq_points = total_points * mix_ratio
    essay_points = total_points - mcq_points
    return [
        (enums.QuestionType.MCQ, mcq_points, mcq_questions),
        (enums.QuestionType.ESSAY, essay_points, essay_questions),
    ]


def _apportion(total: int, weights: dict) -> dict:
    """Chia `total` (số nguyên) theo `weights` sao cho Σ kết quả CHÍNH XÁC bằng total — phương
    pháp số dư lớn nhất (Hare-Niemeyer): lấy phần nguyên của mỗi phần chia, rồi cấp phần dư
    (total - Σphần nguyên) cho các phần tử có phần dư lớn nhất. Tránh làm tròn ĐỘC LẬP từng
    phần tử (round() riêng lẻ) khiến nhiều phần tử cùng về 0 rồi cả tổng "biến mất" — bug thật
    gặp khi total nhỏ mà số phần tử nhiều (vd 7 câu chia đều cho 6 mức Bloom rồi mỗi mức ~1 câu
    chia tiếp cho 3 chương → round(1*0.33)=0 ở MỌI ô, cả rổ mất trắng)."""
    if total <= 0 or not weights:
        return dict.fromkeys(weights, 0)
    norm = normalize_unit_weights(weights)
    raw = {k: total * w for k, w in norm.items()}
    floors = {k: int(v) for k, v in raw.items()}
    remainder = total - sum(floors.values())
    order = sorted(raw, key=lambda k: raw[k] - floors[k], reverse=True)
    for k in order[:remainder]:
        floors[k] += 1
    return floors


def allocate_cells(
    unit_weights: dict[UUID, float],
    total_points: float,
    total_questions: int,
    exam_format: enums.ExamFormat,
    target_difficulty: float,
    mix_ratio: float = 0.7,
) -> list[dict]:
    """Sinh cells (unit × Bloom × loại câu) theo loại đề + quy mô (total_points/total_questions)
    + `target_difficulty` (-> phân phối Bloom CHUNG cho cả TN/TL qua `bloom_distribution_for_target`,
    xem hàm đó để biết vì sao CDI thực tế sẽ bám sát target_difficulty). Mỗi tầng chia (rổ->Bloom,
    Bloom->unit) dùng `_apportion` (bảo toàn tổng chính xác) thay vì round() độc lập từng phần tử —
    ô nào apportion về 0 câu thì bỏ qua (hợp lệ: quá nhiều phần tử so với số câu ở tầng đó).
    points_each CHIA ĐỀU cho mọi câu trong CÙNG 1 rổ (TN hoặc TL) — không phân biệt Bloom: nếu
    tính theo bloom_dist (như cách cũ) thì mức Bloom nào bị target_difficulty cho trọng số nhỏ sẽ
    vừa ít câu vừa ít điểm/câu, khiến câu khó hơn lại ít điểm hơn (ngược quy ước đề thi VN) — bug
    thật đã gặp. Hiệu chỉnh cuối để Σ điểm khớp CHÍNH XÁC total_points (bắt buộc để lưu)."""
    bloom_dist = bloom_distribution_for_target(target_difficulty)
    cells: list[dict] = []
    for qtype, basket_points, basket_questions in _basket_plan(exam_format, total_points, total_questions, mix_ratio):
        if basket_questions < 1:
            continue
        points_each = max(_MIN_POINTS_EACH, _round_to_quarter(basket_points / basket_questions))
        bloom_counts = _apportion(basket_questions, bloom_dist)
        for bloom, bloom_questions in bloom_counts.items():
            if bloom_questions < 1:
                continue
            unit_counts = _apportion(bloom_questions, unit_weights)
            for unit_id, num_questions in unit_counts.items():
                if num_questions < 1:
                    continue
                cells.append(
                    {
                        "unit_id": unit_id,
                        "bloom_level": bloom,
                        "question_type": qtype,
                        "num_questions": num_questions,
                        "points_each": points_each,
                    }
                )
    _reconcile_total(cells, total_points)
    return cells


def derive_exam_format(cells: list[dict]) -> enums.ExamFormat | None:
    """Suy ra loại đề từ tập question_type THỰC TẾ dùng trong cells — luôn tính lại khi lưu
    (create/update blueprint), không tin giá trị client tự khai, tránh lệch khi GV tay sửa
    cells sau khi nhận gợi ý (vd chọn MCQ_ONLY rồi thêm tay 1 câu ESSAY)."""
    types_used = {c["question_type"] for c in cells}
    if not types_used:
        return None
    if types_used <= _TN_TYPES:
        return enums.ExamFormat.MCQ_ONLY
    if types_used <= _TL_TYPES:
        return enums.ExamFormat.ESSAY_ONLY
    if types_used & _TN_TYPES and types_used & _TL_TYPES:
        return enums.ExamFormat.MIXED
    return None


# ============================================================
# TẦNG DB
# ============================================================


def _grade_ability_from_ranking(
    db: Session, school_id: UUID, grade_id: UUID, semester_id: UUID, subject_id: UUID, score_category
) -> float | None:
    rows = exam_validity.content_adjusted_ranking(db, school_id, grade_id, semester_id, subject_id, score_category)
    if not rows:
        return None
    return sum(r.content_adjusted_ability for r in rows) / len(rows)


def _grade_raw_average(db: Session, grade_id: UUID, subject_id: UUID, semester_id: UUID) -> float | None:
    """Điểm thô TB của khối trong kỳ (mọi loại điểm) — dùng khi chưa có đề nào đã phân tích
    CDI cùng loại (đề GK/CK sắp ra thường chưa có dữ liệu chính loại đó)."""
    sql = text(
        """
        SELECT AVG(s.value) AS avg_score
        FROM scores s
        JOIN classes c ON c.id = s.class_id
        WHERE c.grade_id = :grade_id AND s.subject_id = :subject_id AND s.semester_id = :semester_id
          AND s.status = 'APPROVED'
        """
    )
    row = db.execute(sql, {"grade_id": grade_id, "subject_id": subject_id, "semester_id": semester_id}).first()
    return float(row.avg_score) if row is not None and row.avg_score is not None else None


def estimate_ability(
    db: Session, school_id: UUID, grade_id: UUID, subject_id: UUID, semester_id: UUID, score_category
) -> tuple[float, str]:
    """3 tầng fallback: (1) đã neo CDI cùng loại/kỳ, (2) điểm thô cùng kỳ (mọi loại), (3) mức
    chuẩn 6.5 khi trường chưa đủ dữ liệu — luôn trả kèm lý do để hiện trong rationale."""
    ability = _grade_ability_from_ranking(db, school_id, grade_id, semester_id, subject_id, score_category)
    if ability is not None:
        return round(ability, 2), "Năng lực khối tính từ điểm đã neo CDI (content_adjusted_ability) của các lớp."
    ability = _grade_raw_average(db, grade_id, subject_id, semester_id)
    if ability is not None:
        return round(ability, 2), "Chưa có đề đã phân tích CDI cùng loại — dùng điểm trung bình thô của khối trong kỳ."
    return _DEFAULT_ABILITY, "Chưa đủ dữ liệu điểm của khối — dùng mức năng lực chuẩn 6.5 làm khung tham chiếu."


def _validate_grade_in_school(db: Session, school_id: UUID, grade_id: UUID) -> None:
    grade = db.get(Grade, grade_id)
    if grade is None or grade.school_id != school_id:
        raise RecommendationInputError("Khối không tồn tại trong trường của bạn")


def _validate_units_belong(db: Session, subject_id: UUID, grade_number: int, unit_ids: list[UUID]) -> None:
    found = set(
        db.execute(
            select(CurriculumUnit.id).where(
                CurriculumUnit.subject_id == subject_id,
                CurriculumUnit.grade_number == grade_number,
                CurriculumUnit.id.in_(unit_ids),
            )
        )
        .scalars()
        .all()
    )
    missing = set(unit_ids) - found
    if missing:
        raise RecommendationInputError(
            f"Môn/khối này chưa có chuẩn chương trình cho {len(missing)} chương đã chọn — "
            "chưa hỗ trợ gợi ý tự động, dùng ma trận tự soạn."
        )


def _expand_chapters_to_lessons(db: Session, unit_ids: list[UUID]) -> tuple[list[UUID], list[str]]:
    """Nếu GV chỉ tick cả CHƯƠNG (chưa tự mở rộng chọn bài cụ thể), chọn NGẪU NHIÊN một phần
    bài học con để dùng thay cho cả chương — cells bám sát bài học cụ thể thay vì cả chương
    chung chung, đỡ GV phải tự tick từng bài. Chương không có bài học con (chưa có dữ liệu bài,
    hoặc unit_id vốn đã là 1 bài học) giữ nguyên. GV luôn xem/chỉnh lại `cells` ở Step 2 nếu
    thấy chưa phù hợp — hàm này chỉ đề xuất phạm vi ban đầu, không ràng buộc gì thêm."""
    expanded: list[UUID] = []
    notes: list[str] = []
    for uid in unit_ids:
        children = list(
            db.execute(
                select(CurriculumUnit.id).where(CurriculumUnit.parent_id == uid, CurriculumUnit.is_active.is_(True))
            )
            .scalars()
            .all()
        )
        if not children:
            expanded.append(uid)
            continue
        k = max(1, math.ceil(len(children) * _LESSON_SAMPLE_RATIO))
        picked = random.sample(children, k)
        expanded.extend(picked)
        chapter = db.get(CurriculumUnit, uid)
        chap_name = chapter.name if chapter else "?"
        notes.append(
            f"Chưa chọn bài cụ thể trong '{chap_name}' — hệ tự chọn ngẫu nhiên {k}/{len(children)} bài "
            "(xem/chỉnh lại ở bảng ma trận nếu chưa phù hợp)."
        )
    return expanded, notes


def _misconception_counts(
    db: Session, school_id: UUID, subject_id: UUID, grade_number: int, unit_ids: list[UUID]
) -> dict[UUID, int]:
    stmt = (
        select(Misconception.unit_id, func.sum(Misconception.evidence_count))
        .where(
            Misconception.subject_id == subject_id,
            Misconception.grade_number == grade_number,
            Misconception.unit_id.in_(unit_ids),
            or_(Misconception.school_id.is_(None), Misconception.school_id == school_id),
        )
        .group_by(Misconception.unit_id)
    )
    return {row[0]: int(row[1]) for row in db.execute(stmt).all()}


def _weak_units(db: Session, school_id: UUID, subject_id: UUID, grade_number: int, unit_ids: list[UUID]) -> set[UUID]:
    """Chương có kho câu (CÙNG TRƯỜNG) đã dùng mà p_value TB thấp (HS làm sai nhiều) -> đáng kiểm lại."""
    stmt = (
        select(QuestionItem.unit_id, func.avg(QuestionItem.p_value))
        .where(
            QuestionItem.school_id == school_id,
            QuestionItem.subject_id == subject_id,
            QuestionItem.grade_number == grade_number,
            QuestionItem.unit_id.in_(unit_ids),
            QuestionItem.p_value.is_not(None),
        )
        .group_by(QuestionItem.unit_id)
    )
    return {row[0] for row in db.execute(stmt).all() if row[1] is not None and float(row[1]) < _WEAK_P_VALUE_THRESHOLD}


def _uncovered_units(
    db: Session, school_id: UUID, subject_id: UUID, grade_id: UUID, semester_id: UUID, unit_ids: list[UUID]
) -> set[UUID]:
    """Chương CHƯA xuất hiện trong đề nào cùng trường/môn/khối/kỳ (tránh dồn đề vào vài chương cũ)."""
    stmt = (
        select(ExamCompetency.unit_id)
        .join(ExamPaper, ExamPaper.id == ExamCompetency.exam_paper_id)
        .where(
            ExamPaper.so_school_id == school_id,
            ExamPaper.subject_id == subject_id,
            ExamPaper.grade_id == grade_id,
            ExamPaper.semester_id == semester_id,
            ExamCompetency.unit_id.in_(unit_ids),
        )
        .distinct()
    )
    covered = set(db.execute(stmt).scalars().all())
    return set(unit_ids) - covered


def _unit_names(db: Session, unit_ids: set[UUID]) -> dict[UUID, str]:
    if not unit_ids:
        return {}
    rows = db.execute(select(CurriculumUnit.id, CurriculumUnit.name).where(CurriculumUnit.id.in_(unit_ids))).all()
    return {row[0]: row[1] for row in rows}


def _to_cell_draft(db: Session, school_id: UUID, req: RecommendBlueprintRequest, cell: dict, names: dict) -> RecommendCellDraft:
    available = exam_assembly.count_candidates_for_cell(db, school_id, req.subject_id, req.grade_number, cell)
    return RecommendCellDraft(
        unit_id=cell["unit_id"],
        unit_name=names.get(cell["unit_id"], "?"),
        bloom_level=cell["bloom_level"],
        question_type=cell["question_type"],
        num_questions=cell["num_questions"],
        points_each=cell["points_each"],
        available=available,
        shortfall=max(0, cell["num_questions"] - available),
    )


def _build_rationale(
    ability: float,
    target: float,
    ability_note: str,
    misconceptions: dict,
    weak: set,
    uncovered: set,
    req: RecommendBlueprintRequest,
    cells: list[dict],
) -> list[str]:
    rationale = [ability_note, f"Mức năng lực ước tính: {ability}/10 -> độ khó mục tiêu {target}."]
    actual_total = sum(c["num_questions"] for c in cells)
    format_label = _EXAM_FORMAT_LABELS[req.exam_format]
    rationale.append(f"Loại đề: {format_label}. Mục tiêu {req.total_questions} câu -> đã phân bổ {actual_total} câu.")
    if req.exam_format == enums.ExamFormat.MIXED:
        tn_pct = round(req.mix_mcq_ratio * 100)
        rationale.append(f"Tỉ lệ điểm trắc nghiệm/tự luận: {tn_pct}%/{100 - tn_pct}%.")
    if misconceptions:
        rationale.append(f"Ưu tiên {len(misconceptions)} chương có lỗi sai phổ biến ghi nhận trong ngân hàng.")
    if weak:
        rationale.append(f"Ưu tiên {len(weak)} chương có kho câu p_value thấp (HS từng làm sai nhiều).")
    if uncovered:
        rationale.append(f"Ưu tiên {len(uncovered)} chương chưa xuất hiện trong đề nào cùng kỳ.")
    return rationale


def recommend(db: Session, school_id: UUID, req: RecommendBlueprintRequest) -> BlueprintDraft:
    """Gợi ý ma trận — KHÔNG ghi DB. GV xem/chỉnh `cells` rồi tự POST /exam-blueprints để lưu."""
    _validate_grade_in_school(db, school_id, req.grade_id)
    _validate_units_belong(db, req.subject_id, req.grade_number, req.unit_ids)
    _validate_size_inputs(req.total_points, req.total_questions)

    ability, ability_note = estimate_ability(
        db, school_id, req.grade_id, req.subject_id, req.semester_id, req.score_category
    )
    target = target_difficulty_from_ability(ability)

    unit_ids, expansion_notes = _expand_chapters_to_lessons(db, req.unit_ids)

    misconceptions = _misconception_counts(db, school_id, req.subject_id, req.grade_number, unit_ids)
    weak = _weak_units(db, school_id, req.subject_id, req.grade_number, unit_ids)
    uncovered = _uncovered_units(db, school_id, req.subject_id, req.grade_id, req.semester_id, unit_ids)
    weights = boosted_unit_weights(unit_ids, misconceptions, weak, uncovered)

    cells = allocate_cells(weights, req.total_points, req.total_questions, req.exam_format, target, req.mix_mcq_ratio)
    names = _unit_names(db, {c["unit_id"] for c in cells})
    drafts = [_to_cell_draft(db, school_id, req, c, names) for c in cells]
    expected_cdi = exam_assembly.compute_cdi([(d.points_each * d.num_questions, d.bloom_level) for d in drafts])

    return BlueprintDraft(
        subject_id=req.subject_id,
        grade_number=req.grade_number,
        target_difficulty=target,
        ability_used=ability,
        expected_cdi=expected_cdi,
        cells=drafts,
        rationale=_build_rationale(ability, target, ability_note, misconceptions, weak, uncovered, req, cells)
        + expansion_notes,
    )
