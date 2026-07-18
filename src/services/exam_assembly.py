"""Ráp đề chính thức từ ngân hàng câu hỏi (chỉ chọn câu APPROVED).

Tách 2 phần rõ ràng:
- LOGIC THUẦN (chọn câu, xếp ưu tiên, xáo mã đề) — không chạm DB, test offline được.
- TẦNG DB (assemble/finalize) — truy vấn ứng viên + ghi generated_exams/exam_papers.

Đề ráp xong tự sinh exam_papers + exam_competencies nên TEVI tính được CDI ngay,
không cần OCR. Xem docs/exam_generation_design.md §6.
"""

import random
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.models import enums
from src.models.tables import (
    CurriculumUnit,
    ExamBlueprint,
    ExamCompetency,
    ExamPaper,
    GeneratedExam,
    GeneratedExamItem,
    QuestionItem,
)
from src.services import notifications

_VARIANT_BASE = 101  # mã đề bắt đầu từ '101'
_NEUTRAL_DIFFICULTY = 0.5
_GRADE_CATEGORIES = {enums.ScoreCategory.MIDTERM, enums.ScoreCategory.FINAL}


class InsufficientItemsError(Exception):
    """Kho không đủ câu APPROVED cho một ô ma trận — KHÔNG tự bịa câu khi ráp."""

    def __init__(self, cell: dict, available: int) -> None:
        self.cell = cell
        self.available = available
        super().__init__(
            f"Thiếu câu cho ô (unit={cell.get('unit_id')}, bloom={cell.get('bloom_level')}, "
            f"loại={cell.get('question_type')}): cần {cell.get('num_questions')}, kho có {available}."
        )


# ============================================================
# LOGIC THUẦN (không DB)
# ============================================================


def item_difficulty(p_value: float | None, bloom_level: int) -> float:
    """Độ khó hiệu dụng 0..1 (cao = khó). Có thống kê -> 1−p_value; chưa có -> proxy Bloom/6."""
    if p_value is not None:
        return max(0.0, min(1.0, 1.0 - float(p_value)))
    return bloom_level / 6.0


def _priority_key(item, target: float) -> tuple:
    """Ưu tiên: gần target độ khó nhất, phân biệt cao, ít dùng, ít bị lộ gần đây."""
    diff = abs(item_difficulty(item.p_value, item.bloom_level) - target)
    disc = float(item.discrimination) if item.discrimination is not None else 0.0
    exposure = item.exposure_at.timestamp() if item.exposure_at is not None else 0.0
    return (round(diff, 4), -disc, item.times_used, exposure)


def select_for_cell(candidates: list, num_questions: int, target: float) -> list:
    """Chọn ``num_questions`` câu tốt nhất cho một ô. Thiếu -> InsufficientItemsError."""
    ranked = sorted(candidates, key=lambda it: _priority_key(it, target))
    return ranked[:num_questions]


def shuffle_options(options: list[dict] | None, rng: random.Random) -> tuple[list[dict] | None, list | None]:
    """Xáo thứ tự đáp án (giữ nguyên key gốc để map đáp án đúng). Trả (options_mới, thứ_tự_key)."""
    if not options:
        return options, None
    shuffled = options[:]
    rng.shuffle(shuffled)
    return shuffled, [o.get("key") for o in shuffled]


def build_variant_codes(num_variants: int) -> list[str]:
    return [str(_VARIANT_BASE + i) for i in range(num_variants)]


def build_variants(selected: list, num_variants: int, seed: int) -> list[dict]:
    """Sinh các mã đề: cùng tập câu, xáo thứ tự câu + thứ tự đáp án (tái lập theo seed).

    Mã đề đầu giữ thứ tự gốc (canonical). Trả list[{variant_code, items:[{position,item,option_order}]}].
    """
    variants = []
    for vi, code in enumerate(build_variant_codes(num_variants)):
        rng = random.Random(seed + vi)
        order = selected[:]
        if vi > 0:
            rng.shuffle(order)
        items = []
        for pos, item in enumerate(order, 1):
            _, option_order = shuffle_options(item.options, rng) if vi > 0 else (item.options, None)
            items.append({"position": pos, "item": item, "option_order": option_order})
        variants.append({"variant_code": code, "items": items})
    return variants


def compute_cdi(points_blooms: list[tuple[float, int]]) -> float | None:
    """CDI nội dung của đề = Σ(điểm·bloom)/Σđiểm /6, chuẩn hóa 0..1 (TEVI §2.2).

    ``points_blooms``: danh sách (điểm_câu, bloom_level) của các câu trong đề.
    """
    total = sum(p for p, _ in points_blooms)
    if total <= 0:
        return None
    weighted = sum(p * b for p, b in points_blooms)
    return round(weighted / total / 6.0, 3)


def difficulty_band(value: float | None) -> enums.Difficulty | None:
    """Quy độ khó 0..1 về nhãn EASY/MEDIUM/HARD cho exam_papers.difficulty."""
    if value is None:
        return None
    if value < 0.40:
        return enums.Difficulty.EASY
    if value < 0.67:
        return enums.Difficulty.MEDIUM
    return enums.Difficulty.HARD


# ============================================================
# TẦNG DB
# ============================================================


def _cell_filters(school_id: UUID, subject_id: UUID, grade_number: int, cell: dict) -> tuple:
    """Điều kiện WHERE dùng chung để tìm câu APPROVED khớp một ô ma trận."""
    return (
        QuestionItem.school_id == school_id,
        QuestionItem.subject_id == subject_id,
        QuestionItem.grade_number == grade_number,
        QuestionItem.unit_id == UUID(str(cell["unit_id"])),
        QuestionItem.bloom_level == cell["bloom_level"],
        QuestionItem.question_type == enums.QuestionType(cell["question_type"]),
        QuestionItem.status == enums.ItemStatus.APPROVED,
    )


def _candidates_for_cell(db: Session, school_id: UUID, subject_id: UUID, grade_number: int, cell: dict) -> list:
    """Câu APPROVED khớp (môn, khối, chuẩn CT, Bloom, loại câu) trong cùng trường."""
    stmt = select(QuestionItem).where(*_cell_filters(school_id, subject_id, grade_number, cell))
    return list(db.execute(stmt).scalars().all())


def count_candidates_for_cell(db: Session, school_id: UUID, subject_id: UUID, grade_number: int, cell: dict) -> int:
    """Đếm câu APPROVED khớp một ô — dùng để báo thiếu câu KHI SOẠN ma trận (trước khi ráp)."""
    stmt = select(func.count()).select_from(QuestionItem).where(*_cell_filters(school_id, subject_id, grade_number, cell))
    return db.execute(stmt).scalar_one()


def _select_all_cells(db: Session, blueprint: ExamBlueprint) -> list:
    """Chọn câu cho toàn ma trận; gắn .points cho từng câu (từ points_each của ô)."""
    target = float(blueprint.target_difficulty) if blueprint.target_difficulty is not None else _NEUTRAL_DIFFICULTY
    chosen: list = []
    for cell in blueprint.cells:
        pool = _candidates_for_cell(db, blueprint.school_id, blueprint.subject_id, blueprint.grade_number, cell)
        if len(pool) < cell["num_questions"]:
            raise InsufficientItemsError(cell, len(pool))
        picked = select_for_cell(pool, cell["num_questions"], target)
        for item in picked:
            item.points = float(cell["points_each"])  # gắn điểm theo ô (thuộc tính tạm, không ghi DB)
            chosen.append(item)
    return chosen


def assemble(db: Session, user, req) -> GeneratedExam:
    """Ráp đề từ blueprint: chọn câu APPROVED + sinh mã đề, lưu generated_exams (DRAFT).

    ``req`` là AssembleRequest. Lỗi thiếu câu -> InsufficientItemsError (router map 409).
    """
    blueprint = db.get(ExamBlueprint, req.blueprint_id)
    if blueprint is None or blueprint.school_id != user.school_id:
        raise ValueError("Ma trận đề không tồn tại")
    if blueprint.score_category not in _GRADE_CATEGORIES:
        raise ValueError("Chỉ ráp đề chính thức Giữa kỳ/Cuối kỳ (MIDTERM/FINAL)")

    selected = _select_all_cells(db, blueprint)
    variants = build_variants(selected, req.num_variants, seed=random.randint(0, 10**9))

    gen = GeneratedExam(
        school_id=user.school_id,
        blueprint_id=blueprint.id,
        semester_id=req.semester_id,
        grade_id=req.grade_id,
        num_variants=req.num_variants,
        created_by=user.id,
    )
    db.add(gen)
    db.flush()  # lấy gen.id trước khi thêm item
    for variant in variants:
        for entry in variant["items"]:
            db.add(
                GeneratedExamItem(
                    generated_exam_id=gen.id,
                    variant_code=variant["variant_code"],
                    position=entry["position"],
                    item_id=entry["item"].id,
                    points=entry["item"].points,
                    option_order=entry["option_order"],
                )
            )
    db.commit()
    db.refresh(gen)
    return gen


def _canonical_items(db: Session, gen: GeneratedExam) -> list[GeneratedExamItem]:
    """Câu của mã đề đầu (canonical) — đại diện nội dung đề để sinh exam_competencies."""
    code = build_variant_codes(gen.num_variants)[0]
    stmt = (
        select(GeneratedExamItem)
        .where(GeneratedExamItem.generated_exam_id == gen.id, GeneratedExamItem.variant_code == code)
        .order_by(GeneratedExamItem.position)
    )
    return list(db.execute(stmt).scalars().all())


def _build_competencies(rows: list[GeneratedExamItem], item_map: dict, total: float) -> list[dict]:
    """Gộp theo unit: weight = Σđiểm_unit/tổng; bloom = trung bình có trọng số (làm tròn)."""
    agg: dict[UUID, dict] = {}
    for row in rows:
        qi = item_map[row.item_id]
        cur = agg.setdefault(qi.unit_id, {"points": 0.0, "weighted_bloom": 0.0})
        cur["points"] += float(row.points)
        cur["weighted_bloom"] += float(row.points) * qi.bloom_level
    out = []
    for unit_id, data in agg.items():
        bloom = round(data["weighted_bloom"] / data["points"]) if data["points"] else None
        out.append({"unit_id": unit_id, "weight": round(data["points"] / total, 3), "bloom_level": bloom})
    return out


def finalize(db: Session, user, generated_exam_id: UUID) -> GeneratedExam:
    """Chốt đề: sinh exam_papers + exam_competencies (TEVI-ready) và nối vào luồng chấm."""
    gen = db.get(GeneratedExam, generated_exam_id)
    if gen is None or gen.school_id != user.school_id:
        raise ValueError("Đề ráp không tồn tại")
    if gen.status != enums.GenExamStatus.DRAFT:
        raise ValueError("Đề đã được chốt trước đó")

    blueprint = db.get(ExamBlueprint, gen.blueprint_id)
    rows = _canonical_items(db, gen)
    item_map = {
        qi.id: qi
        for qi in db.execute(select(QuestionItem).where(QuestionItem.id.in_([r.item_id for r in rows]))).scalars().all()
    }
    cdi = compute_cdi([(float(r.points), item_map[r.item_id].bloom_level) for r in rows])
    total = float(blueprint.total_points)

    paper = ExamPaper(
        school_id=user.school_id,
        subject_id=blueprint.subject_id,
        semester_id=gen.semester_id,
        grade_id=gen.grade_id,
        score_type=None,
        title=blueprint.title,
        difficulty=difficulty_band(float(blueprint.target_difficulty) if blueprint.target_difficulty else cdi),
        num_questions=len(rows),
        total_points=total,
        topics=_unit_names(db, item_map),
        content_difficulty=cdi,
        content_analyzed_at=datetime.now(UTC),
        uploaded_by=user.id,
        ai_analysis={"source": "exam_generation", "generated_exam_id": str(gen.id)},
    )
    db.add(paper)
    db.flush()
    for comp in _build_competencies(rows, item_map, total):
        db.add(ExamCompetency(exam_paper_id=paper.id, **comp))

    _mark_exposed(db, list(item_map.values()))
    gen.exam_paper_id = paper.id
    gen.status = enums.GenExamStatus.FINALIZED
    db.commit()
    db.refresh(gen)
    notifications.notify_exam_finalized(db, gen, blueprint)
    return gen


def _unit_names(db: Session, item_map: dict) -> list[str]:
    unit_ids = {qi.unit_id for qi in item_map.values()}
    rows = db.execute(select(CurriculumUnit.name).where(CurriculumUnit.id.in_(unit_ids))).scalars().all()
    return list(rows)


def _mark_exposed(db: Session, items: list[QuestionItem]) -> None:
    """Đánh dấu câu vừa được dùng (chống lộ + đếm lần dùng) tại thời điểm chốt đề."""
    now = datetime.now(UTC)
    for qi in items:
        qi.exposure_at = now
        qi.times_used = (qi.times_used or 0) + 1
