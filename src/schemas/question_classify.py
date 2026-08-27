"""Schema công cụ test 1 câu hỏi — xác định câu hỏi thuộc chương/bài nào của SGK đã nạp.

Endpoint POST /api/v1/exam-difficulty/classify-question (tab "Kiểm tra câu hỏi" trong trang
Phân tích độ khó đề thi TEVI). Không trạng thái: không tạo exam_papers, không ghi DB.
"""

from pydantic import BaseModel


class ClassifiedItem(BaseModel):
    """1 khớp node chương trình của câu hỏi (có thể nhiều node với trọng số khác nhau)."""

    topic: str
    chapter: str | None = None
    lesson: str | None = None
    unit_code: str | None = None
    unit_name: str | None = None
    bloom_level: int
    weight: float
    confidence: float | None = None
    reason: str | None = None
    excerpt: str | None = None
    question_share: float | None = None
    is_primary: bool | None = None


class QuestionClassifyResult(BaseModel):
    """Kết quả phân loại 1 câu hỏi vào cây chương/bài (theo thứ tự trọng số giảm dần)."""

    text: str
    matched: bool
    off_curriculum: bool
    items: list[ClassifiedItem] = []
    candidates: list[str] = []
