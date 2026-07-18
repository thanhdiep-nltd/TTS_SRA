from uuid import UUID

from pydantic import BaseModel


class StudentFairnessRow(BaseModel):
    """Tín hiệu cảnh báo — gợi ý rà soát thêm, KHÔNG phải kết luận tiêu cực đã xác nhận."""

    student_id: UUID
    student_code: str
    full_name: str
    class_id: UUID
    class_name: str
    subject_id: UUID
    subject_name: str
    semester_id: UUID
    tx_avg: float | None
    tx_cdi: float | None
    periodic_avg: float | None
    periodic_cdi: float | None
    gap: float | None
    flag: str
    confidence: str
    evidence: str
