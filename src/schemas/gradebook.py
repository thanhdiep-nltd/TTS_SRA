from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from src.models import enums


class SubjectEvalUpsert(BaseModel):
    """GV bộ môn nhập đánh giá học tập cho 1 HS ở 1 môn/học kỳ."""

    student_id: UUID
    subject_id: UUID
    class_id: UUID
    semester_id: UUID
    result: enums.PassFail | None = None  # cho môn REMARK
    comment: str | None = None  # nhận xét (môn SCORED)


class TermReportUpsert(BaseModel):
    """GV chủ nhiệm nhập hạnh kiểm + đánh giá chung cho 1 HS ở 1 học kỳ."""

    student_id: UUID
    class_id: UUID
    semester_id: UUID
    conduct: enums.Conduct | None = None
    general_comment: str | None = None
    absent_days: int | None = None


class GradeCell(BaseModel):
    """Một ô điểm (kèm id để frontend biết PATCH hay POST)."""

    id: UUID | None = None
    value: float | None = None


class GradebookColumn(BaseModel):
    key: str  # "REGULAR_2"
    category: str  # ORAL / REGULAR / MIDTERM / FINAL
    index: int
    label: str  # "TX2", "GK1", "Cuối kỳ"...
    mappable: bool  # có cho phép map đề thi không (Miệng: false)


class HocLucStat(BaseModel):
    label: str
    count: int
    ratio: float  # %


class GradebookRow(BaseModel):
    student_id: UUID
    student_code: str
    full_name: str
    cells: dict[str, GradeCell]  # column_key -> ô điểm (học kỳ đang chọn)
    dtb_hk: float | None = None
    dtb_hk1: float | None = None
    dtb_hk2: float | None = None
    dtb_cn: float | None = None
    hoc_luc: str | None = None
    evaluation: str | None = None  # đánh giá học tập (nhận xét) của GV bộ môn
    result: str | None = None  # Đạt/Chưa đạt — cho môn REMARK


class ExamRef(BaseModel):
    """Đề thi đã map vào một cột (để preview/đổi/gỡ)."""

    mapping_id: UUID
    exam_paper_id: UUID
    title: str
    file_type: str | None = None
    # Độ khó nội dung (CDI, TEVI) — phân tích bằng LLM chạy nền sau khi upload, có thể chưa có ngay.
    content_difficulty: float | None = None
    content_analyzed_at: datetime | None = None


class GradebookResponse(BaseModel):
    class_id: UUID
    subject_id: UUID
    semester_id: UUID
    assessment_type: str = "SCORED"  # SCORED (điểm) hay REMARK (Đạt/Chưa đạt)
    columns: list[GradebookColumn]
    rows: list[GradebookRow]
    mappings: dict[str, ExamRef]  # column_key -> đề đã map (nếu có)
    total_students: int
    stats: list[HocLucStat]


class SubjectInfo(BaseModel):
    id: UUID
    name: str
    code: str
    assessment_type: str = "SCORED"


class SummaryRow(BaseModel):
    student_id: UUID
    student_code: str
    full_name: str
    averages: dict[str, float | None]  # subject_id (str) -> ĐTB môn (chỉ môn SCORED)
    remarks: dict[str, str] = {}  # subject_id (str) -> "Đạt"/"Chưa đạt" (môn REMARK)
    overall: float | None = None
    hoc_luc: str | None = None
    conduct: str | None = None  # hạnh kiểm (GV chủ nhiệm)
    general_comment: str | None = None  # đánh giá chung (GV chủ nhiệm)
    absent_days: int | None = None  # số ngày nghỉ (GV chủ nhiệm)


class ClassSummaryResponse(BaseModel):
    class_id: UUID
    semester_id: UUID
    subjects: list[SubjectInfo]
    rows: list[SummaryRow]
    total_students: int
    stats: list[HocLucStat]
    can_edit_report: bool = False  # FE biết có cho sửa hạnh kiểm/đánh giá chung không
