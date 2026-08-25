"""src/schemas/knowledge_gap.py — DTO cho API lỗ hổng kiến thức (M2)."""

from pydantic import BaseModel, Field


class KnowledgeGapItem(BaseModel):
    """1 unit (Chương hoặc Bài học) hổng của 1 học sinh."""

    unit_id: int
    parent_id: int | None = None
    unit_name: str | None = None
    chapter: str | None = None
    lesson: str | None = None
    is_chapter: bool = False
    # Tóm tắt/từ khóa của unit (làm giàu khi nạp sách) — giúp giải thích "hổng khái niệm/mục nào".
    summary: str | None = None
    keywords: list[str] | None = None
    gap_score: float = Field(..., description="0..1, cao = hổng nặng")
    mastery: float = Field(..., description="0..1, mức thành thạo (adjusted)")
    confidence: str | None = None  # 'HIGH' | 'MEDIUM' | 'LOW' | 'INSUFFICIENT'
    coverage: float | None = None  # 0..1, độ phủ câu hỏi LMS cho chương này
    integrity_status: str | None = None  # 'OK' | 'LMS_EXCEEDS_EXAM' | 'LOW_ENGAGEMENT' | 'LMS_ONLY' | 'FLAGGED'
    evidence_source: str | None = None  # 'EXAM' | 'LMS' | 'HYBRID' | 'PRIOR' | 'INSUFFICIENT'
    evidence_detail: dict | None = None
    # Bằng chứng chi tiết (từ student_unit_mastery — giải thích "tại sao có kết quả này"):
    raw_mastery: float | None = None  # mastery LMS thô (Bloom-weighted, chưa đối soát)
    n_items: int | None = None  # số câu LMS hợp lệ của chương
    n_correct: int | None = None  # số câu đúng
    lm_weight: float | None = None  # trọng số LMS trong adjusted
    exam_weight: float | None = None  # trọng số điểm thi trong adjusted
    # Cây phân cấp Bài học con (nếu đây là node Chương):
    lessons: list["KnowledgeGapItem"] = Field(default_factory=list)
    gap_lessons_count: int = 0
    total_lessons_count: int = 0



class StudentKnowledgeGaps(BaseModel):
    """Danh sách unit hổng của 1 học sinh."""

    student_code: str
    subject_id: int
    school_year_id: int
    semester_index: int
    gaps: list[KnowledgeGapItem] = Field(default_factory=list)


class ClassKnowledgeGaps(BaseModel):
    """Unit hổng phổ biến của 1 lớp."""

    class_id: int
    subject_id: int
    school_year_id: int
    semester_index: int
    gaps: list[KnowledgeGapItem] = Field(default_factory=list)


class ClassOption(BaseModel):
    """1 lớp từ s360.dim_homeroom_class (chọn bộ lọc trên trang knowledge-gaps)."""

    class_id: int
    class_name: str
    grade_id: int | None = None
    code: str | None = None


class StudentOption(BaseModel):
    """1 học sinh từ s360.dim_homeroom_class_student (dropdown học sinh)."""

    student_code: str
    student_name: str


class LmsQuestionUnitRef(BaseModel):
    """1 bài mà câu hỏi LMS đóng góp vào (multi-bài có trọng số)."""

    unit_id: int
    unit_name: str | None = None
    chapter: str | None = None
    weight: float = 1.0


class LmsQuestionBankItem(BaseModel):
    """1 câu hỏi LMS (lms_question_bank) kèm thống kê làm bài từ lms_question_response."""

    question_id: int
    assignment_id: int
    subject_id: int
    so_school_id: int
    unit_id: int | None = None
    unit_name: str | None = None  # tên bài (curriculum_units.name) — unit_id trỏ bài con
    chapter: str | None = None  # tên node cha (chương) nếu unit là bài con
    lesson_id: int | None = None  # bài chính (bằng unit_id — khớp pipeline test câu hỏi)
    lesson_name: str | None = None  # tên bài chính
    bloom_level: int | None = None  # 1..6
    question_type: str | None = "MCQ"
    question_text: str | None = None  # nội dung đề bài câu hỏi (mock)
    item_weight: float | None = None
    is_active: int | None = 1
    n_responses: int | None = None  # số học sinh đã trả lời (best attempt)
    n_correct: int | None = None  # số học sinh trả lời đúng
    accuracy: float | None = None  # n_correct / n_responses (0..1)
    units: list[LmsQuestionUnitRef] = []  # map bài đầy đủ (multi-bài có weight)


class StudentRosterSummary(BaseModel):
    """Tổng hợp chẩn đoán lỗ hổng của 1 học sinh trong danh sách lớp."""

    student_code: str
    student_name: str
    avg_mastery: float = Field(..., description="Độ thành thạo trung bình các chương (0..1)")
    gap_count: int = Field(0, description="Số chương bị hổng kiến thức (< 0.60)")
    mastered_count: int = Field(0, description="Số chương đã nắm vững (>= 0.60)")
    total_units: int = Field(0, description="Tổng số chương được đánh giá")
    weak_units: list[str] = Field(default_factory=list, description="Danh sách tên các chương cần củng cố")
    integrity_status: str | None = "OK"  # 'OK' | 'LMS_EXCEEDS_EXAM' | 'LOW_ENGAGEMENT' | 'LMS_ONLY'
    confidence: str | None = "HIGH"
    evidence_source: str = "HYBRID"
    gaps: list[KnowledgeGapItem] = Field(default_factory=list, description="Chi tiết từng chương để mở Drawer")


class ClassRosterResponse(BaseModel):
    """Danh sách chẩn đoán toàn bộ học sinh trong lớp theo môn học."""

    class_id: int
    class_name: str
    subject_id: int
    subject_name: str
    school_year_id: int
    semester_index: int
    total_students: int
    mastered_all_count: int = Field(0, description="Số học sinh nắm vững toàn bộ các chương")
    need_support_count: int = Field(0, description="Số học sinh có ít nhất 1 chương bị hổng")
    cheating_alert_count: int = Field(0, description="Số học sinh có LMS vượt trội so với điểm thi chung")
    low_engagement_count: int = Field(0, description="Số học sinh có cảnh báo tham gia LMS thấp")
    students: list[StudentRosterSummary] = Field(default_factory=list)


class RecalcMasteryResult(BaseModel):
    """Kết quả tính toán lại student_unit_mastery từ LMS item-responses."""

    success: bool = True
    records_calculated: int = 0
    subject_id: int
    semester_index: int = 1
    message: str = "Tính toán lại năng lực thành công"
