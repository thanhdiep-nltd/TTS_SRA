from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel


class GradeDistributionRow(BaseModel):
    name: str
    gioi: int
    kha: int
    trung_binh: int
    yeu: int


class GpaTrendPoint(BaseModel):
    name: str
    gpa: float


class GradeTrendPoint(BaseModel):
    name: str  # nhãn đợt đánh giá (TX1, Giữa kỳ, Cuối kỳ...)
    values: dict[str, float]  # tên khối -> điểm TB của khối tại đợt đó


class DashboardOverview(BaseModel):
    total_students: int
    total_classes: int
    average_gpa: float | None
    at_risk_classes: int
    grade_distribution: list[GradeDistributionRow]
    gpa_trend: list[GpaTrendPoint]
    grade_names: list[str]  # danh sách khối (để vẽ nhiều đường)
    grade_trend: list[GradeTrendPoint]


class AcademicDivergenceRow(BaseModel):
    class_name: str
    avg_subject_score: float
    avg_gpao: float
    delta_g: float


class GradeInflationRow(BaseModel):
    class_name: str
    gdi: float


class LearningMomentumRow(BaseModel):
    class_name: str
    positive_count: int
    stable_count: int
    negative_count: int


class StudentArchetypeRow(BaseModel):
    class_name: str
    consistent: int
    procrastinator: int
    high_effort: int
    high_risk: int
    others: int


class SemesterOption(BaseModel):
    id: UUID
    name: str
    academic_year: str
    is_current: bool


class SubjectOption(BaseModel):
    id: UUID
    name: str
    code: str


class ReportExportRequest(BaseModel):
    report_type: str  # 'academic_conduct' | 'subject_quality' | 'at_risk' | 'subject_report'
    format: str  # 'pdf' | 'xlsx' | 'docx'
    grade_level: str  # 'all' | '10' | '11' | '12'
    class_id: str | None = None
    semester_id: UUID | None = None
    subject_id: UUID | None = None
    include_charts: bool = True
    include_tables: bool = True
    include_ai_insights: bool = False
    include_signature: bool = True


class ReportExportRequestS360(BaseModel):
    """Request xuất báo cáo từ schema s360 (score_focused_schema.sql).

    Khác với ReportExportRequest cũ: dùng BIGINT/INTEGER ID thay vì UUID,
    semester dùng semester_index (1/2) + school_year_id.
    """

    report_type: Literal["academic_conduct", "subject_quality", "at_risk", "subject_report"]
    format: Literal["docx", "pdf", "html"]
    grade_level: str = "all"
    class_id: Optional[int] = None  # BIGINT — s360.dim_homeroom_class.id
    semester_index: Optional[int] = None  # 1 hoặc 2
    subject_id: Optional[int] = None  # INTEGER — s360.dim_subject.id
    school_year_id: Optional[int] = None  # INTEGER — s360.dim_school_year.id
    include_charts: bool = True
    include_tables: bool = True
    include_ai_insights: bool = True
    include_signature: bool = True
