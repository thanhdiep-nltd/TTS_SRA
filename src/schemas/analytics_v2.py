"""DTO cho Dashboard v2 (BI 4 tab: Executive / Drill-down / Trend / Cảnh báo).

Mọi chỉ số tính từ bảng `scores` (ĐTB môn qua hàm DB calc_subject_average) và
`student_term_reports` (hạnh kiểm). Các trường không có nguồn dữ liệu thật
(chuyên cần, điểm mục tiêu...) được đánh dấu `*_available=False` để FE hiện placeholder.
"""

from uuid import UUID

from pydantic import BaseModel


# ===== TAB 1 — Executive Overview =====
class ExecutiveKpi(BaseModel):
    avg_gpa: float | None
    total_graded: int  # số HS có ĐTB để xếp loại
    gioi: int
    kha: int
    trung_binh: int
    yeu: int
    at_risk_count: int  # HS ĐTB < 5.0
    conduct_good_ratio: float | None  # tỷ lệ hạnh kiểm Tốt+Khá (None nếu chưa có dữ liệu)
    attendance_available: bool  # luôn False — chưa có nguồn chuyên cần
    promotion_available: bool  # luôn False — chưa có nguồn lên lớp


class LevelDistributionRow(BaseModel):
    level: str  # nhãn cấp học (THCS/THPT/Tiểu học)
    gioi: int
    kha: int
    trung_binh: int
    yeu: int


class ClassRankRow(BaseModel):
    class_name: str
    grade_name: str
    gpa: float
    student_count: int


class ExecutiveSummary(BaseModel):
    semester_name: str
    academic_year: str
    kpi: ExecutiveKpi
    level_distribution: list[LevelDistributionRow]
    class_ranking: list[ClassRankRow]  # đã sort GPA giảm dần; FE cắt top/bottom


# ===== TAB 2 — Academic Drill-down =====
class SubjectMatrix(BaseModel):
    grades: list[str]  # tên khối (cột clustered)
    classes: list[str]  # tên lớp (hàng heatmap)
    subjects: list[str]  # tên môn
    grade_cells: list[dict]  # [{subject, <khối>: avg, ...}] cho clustered bar
    heatmap_cells: list[dict]  # [{class_name, <môn>: avg, ...}] cho heatmap
    subject_ranking: list[ClassRankRow]  # xếp hạng môn (class_name=tên môn, grade_name="")


# ===== TAB 4 — Early Warning =====
class RiskStudent(BaseModel):
    student_code: str
    full_name: str
    class_name: str
    gpa: float
    conduct: str | None
    weakest_subject: str | None
    weakest_score: float | None
    risk_level: str  # Critical / High / Medium


class TalentStudent(BaseModel):
    student_code: str
    full_name: str
    class_name: str
    gpa: float
    best_subject: str | None
    best_score: float | None


class ScatterPoint(BaseModel):
    process_gpa: float  # ĐTB quá trình (Miệng+TX+GK)
    final_score: float  # điểm cuối kỳ
    class_name: str
    risk_level: str


class RiskMatrixCell(BaseModel):
    level: str  # Low / Medium / High / Critical
    count: int


class WarningData(BaseModel):
    risk_students: list[RiskStudent]
    talent_students: list[TalentStudent]
    risk_matrix: list[RiskMatrixCell]
    scatter: list[ScatterPoint]


# ===== TAB 3 — Year over Year =====
class YearGpaRow(BaseModel):
    academic_year: str
    avg_gpa: float | None
    student_count: int


class YoYResponse(BaseModel):
    years: list[YearGpaRow]


class SemesterRef(BaseModel):
    id: UUID
    name: str
    academic_year: str
