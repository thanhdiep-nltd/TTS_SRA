"""Cập nhật độ khó kho câu hỏi sau khi đề ráp từ ngân hàng được chấm (vòng hiệu chỉnh — §9).

DB hiện chỉ lưu điểm TỔNG mỗi cột (`scores`), không có điểm từng câu, nên KHÔNG thể tính
p_value/discrimination chính xác theo CTT chuẩn. v1 dùng xấp xỉ ở CẤP ĐỀ: lấy EDI thực nghiệm
(1 − TB điểm/10) của cả đề, phân bổ ngược về từng câu theo trọng số Bloom tương đối so với
Bloom trung bình của đề. discrimination KHÔNG được cập nhật (cần biết đúng/sai từng câu của
từng học sinh — ngoài phạm vi v1). Xem docs/exam_generation_design.md §9(b).
"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.models import enums
from src.models.tables import Class, ExamBlueprint, GeneratedExam, QuestionItem, Score
from src.services import exam_assembly


def _exam_edi(
    db: Session, subject_id: UUID, semester_id: UUID, score_category: enums.ScoreCategory, grade_id: UUID
) -> float | None:
    """EDI thực nghiệm = 1 − TB điểm/10, tính trực tiếp từ scores APPROVED (KHÔNG dùng view
    mv_exam_difficulty vì view này chưa có cơ chế refresh tự động — tránh đọc dữ liệu cũ)."""
    stmt = (
        select(Score.value)
        .join(Class, Class.id == Score.class_id)
        .where(
            Score.subject_id == subject_id,
            Score.semester_id == semester_id,
            Score.score_category == score_category,
            Class.grade_id == grade_id,
            Score.status == enums.ScoreStatus.APPROVED,
        )
    )
    values = [float(v) for v in db.execute(stmt).scalars().all()]
    if not values:
        return None
    return round(1.0 - (sum(values) / len(values)) / 10.0, 4)


def update_from_exam(db: Session, generated_exam_id: UUID) -> int:
    """Cập nhật p_value ước lượng cho các câu của 1 đề đã chốt. Trả số câu đã cập nhật
    (0 nếu đề chưa chốt, không sinh từ ngân hàng, hoặc chưa có điểm APPROVED nào)."""
    gen = db.get(GeneratedExam, generated_exam_id)
    if gen is None or gen.exam_paper_id is None:
        return 0
    blueprint = db.get(ExamBlueprint, gen.blueprint_id)
    if blueprint is None:
        return 0

    edi = _exam_edi(db, blueprint.subject_id, gen.semester_id, blueprint.score_category, gen.grade_id)
    if edi is None:
        return 0

    rows = exam_assembly._canonical_items(db, gen)
    item_ids = [r.item_id for r in rows]
    items = list(db.execute(select(QuestionItem).where(QuestionItem.id.in_(item_ids))).scalars().all())
    if not items:
        return 0

    avg_bloom = sum(qi.bloom_level for qi in items) / len(items)
    for qi in items:
        difficulty_estimate = max(0.0, min(1.0, edi * (qi.bloom_level / avg_bloom)))
        qi.p_value = round(1.0 - difficulty_estimate, 3)
    db.commit()
    return len(items)


def update_from_exam_paper(db: Session, exam_paper_id: UUID) -> int:
    """Tìm đề ráp (nếu có) khớp exam_paper_id rồi cập nhật kho — dùng khi 1 điểm liên kết đề
    vừa được duyệt. Đề KHÔNG sinh từ ngân hàng (upload trực tiếp) không có generated_exams
    tương ứng -> bỏ qua, không phải lỗi."""
    gen = db.execute(select(GeneratedExam).where(GeneratedExam.exam_paper_id == exam_paper_id)).scalar_one_or_none()
    if gen is None:
        return 0
    return update_from_exam(db, gen.id)
