# -*- coding: utf-8 -*-
"""
src/schemas/ews.py — Pydantic Schemas cho Early Warning System (EWS) Dashboard APIs
"""

from datetime import date, datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class EwsLevelCount(BaseModel):
    """Số lượng và tỷ lệ học sinh theo mức rủi ro."""
    level: str = Field(..., description="Mức rủi ro: LOW | MODERATE | HIGH | CRITICAL")
    count: int = Field(..., description="Số lượt dự báo")


class EwsPredictionRow(BaseModel):
    """Một bản ghi dự báo rủi ro chi tiết theo cặp (Học sinh - Môn học) chứa đủ 24 chỉ số đầu vào."""
    student_code: str
    student_name: Optional[str] = None
    class_name: Optional[str] = None
    grade_name: Optional[str] = None
    grade_level: Optional[int] = None
    subject_id: int
    subject_name: Optional[str] = None
    subject_code: Optional[str] = None
    subject_category: Optional[str] = None
    evaluated_at_week: int
    risk_score: float = Field(..., description="Thang điểm rủi ro [0.00, 100.00]")
    risk_level: str = Field(..., description="LOW | MODERATE | HIGH | CRITICAL")
    risk_probability: Optional[float] = None
    risk_factors: List[str] = Field(default_factory=list, description="Cờ nguyên nhân (backward compat): RISK_SCORE | RISK_LMS | RISK_ATTENDANCE | RISK_BEHAVIOR (giữ = primary_badge)")
    primary_badge: List[str] = Field(default_factory=list, description="1–4 Cờ chính (Multi-badge): domain có Contribution cao nhất + mọi domain có risk_i >= threshold_moderate (MODERATE trở lên, do BGH tinh chỉnh)")
    risk_factor_details: List[str] = Field(default_factory=list, description="Mảng chuỗi mô tả chi tiết nguyên nhân phụ (VD: 'Rủi ro Điểm số (đóng góp 0.24)', 'Rủi ro Học tập LMS (đóng góp 0.27)')")
    shap_drivers: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        description="Top 5 nhân tố tác động SHAP (Rank, feature, shap_value, value) — Signed SHAP, giữ dấu âm/dương",
    )
    evaluated_at_date: Optional[date] = None
    cutoff_date: Optional[date] = None  # Ngày cutoff dữ liệu dùng để trích xuất feature (khớp feature_extractor)
    join_date: Optional[date] = None  # Ngày chuyển tới / nhập học vào lớp (NULL = có mặt từ đầu) — M2-PIVOT
    model_version: Optional[str] = "v1_single"  # 'v1_single' | 'v2_ensemble' — M2-ENSEMBLE

    # Sub-scores & trọng số (chỉ có ở v2_ensemble)
    score_risk: Optional[float] = None
    lms_risk: Optional[float] = None
    attendance_risk: Optional[float] = None
    behavior_risk: Optional[float] = None
    weight_score: Optional[float] = None
    weight_lms: Optional[float] = None
    weight_attendance: Optional[float] = None
    weight_behavior: Optional[float] = None

    # 1. Temporal Scores (9)
    weighted_early_avg: Optional[float] = None
    weighted_late_avg: Optional[float] = None
    weighted_late_avg_imputed: Optional[bool] = Field(
        default=False,
        description="True nếu ĐTB Nửa Sau Kỳ bị impute (= ĐTB Nửa Đầu Kỳ) vì chưa có điểm thật — UI nên hiển thị '—'",
    )
    score_slope: Optional[float] = None
    score_volatility: Optional[float] = None
    max_drop: Optional[float] = None
    last_score: Optional[float] = None
    max_coefficient_so_far: Optional[float] = None
    high_weight_score_count: Optional[int] = None
    last_high_weight_score: Optional[float] = None

    # 2. LMS (5)
    lms_avg_score: Optional[float] = None
    lms_recent_drop: Optional[float] = None
    lms_submission_rate: Optional[float] = None
    lms_recent_submission_rate: Optional[float] = None
    lms_gradebook_gap: Optional[float] = None

    # 3. Attendance (4)
    daily_absence_rate: Optional[float] = None
    unexcused_absent_rate: Optional[float] = None
    excused_absent_days: Optional[int] = None
    total_late_count: Optional[int] = None

    # 4. Behavior (3)
    total_demerit_points: Optional[int] = None
    repeat_offense_count: Optional[int] = None
    severe_sanction_count: Optional[int] = None


class EwsOverview(BaseModel):
    """Dữ liệu KPI tổng quan phân hệ EWS."""
    school_year_id: int
    semester_index: int
    evaluated_at_week: int
    total_predictions: int
    total_students: int
    at_risk_count: int = Field(..., description="Tổng số lượt dự báo HIGH + CRITICAL")
    avg_risk_score: Optional[float] = None
    levels: List[EwsLevelCount] = Field(default_factory=list)
    top_risk_subjects: List[Dict[str, Any]] = Field(default_factory=list)
    top_risk_factors: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Tần suất các yếu tố (cờ nguyên nhân) khiến học sinh rơi vào rủi ro — dùng cho chart tròn",
    )


class EwsWeekOption(BaseModel):
    """Tổ hợp mốc thời gian có dữ liệu dự báo."""
    school_year_id: int
    semester_index: int
    evaluated_at_week: int
    school_year_name: Optional[str] = None


class EwsClassOption(BaseModel):
    """Tùy chọn lớp học kèm khối chủ quản — để bộ lọc Khối → Lớp liên kết đúng."""
    grade_id: Optional[int] = None
    grade_name: Optional[str] = None
    class_name: str = Field(..., description="Tên lớp (vd: 6A1, 10A2)")


class EwsRiskFactorOption(BaseModel):
    """Một tùy chọn cờ nguyên nhân (Risk Badge) cho bộ lọc."""
    code: str = Field(..., description="Mã cờ (vd: RISK_SCORE, RISK_LMS, RISK_ATTENDANCE, RISK_BEHAVIOR)")
    label: str = Field(..., description="Nhãn tiếng Việt")


class EwsMeta(BaseModel):
    """Dữ liệu metadata đổ dropdown bộ lọc."""
    weeks: List[EwsWeekOption] = Field(default_factory=list)
    subjects: List[Dict[str, Any]] = Field(default_factory=list)
    grades: List[Dict[str, Any]] = Field(default_factory=list)
    classes: List[EwsClassOption] = Field(default_factory=list)
    risk_factors: List[EwsRiskFactorOption] = Field(default_factory=list)


class EwsPagedResult(BaseModel):
    """Kết quả danh sách dự báo có phân trang Server-side."""
    items: List[EwsPredictionRow] = Field(default_factory=list)
    total: int
    limit: int
    offset: int


class EwsRawScore(BaseModel):
    """Một bản ghi điểm số gốc (đã khoá) của cặp (học sinh - môn)."""
    exam_name: Optional[str] = None
    exam_code: Optional[str] = None
    coefficient: Optional[float] = None
    final_grade: Optional[float] = None
    max_grade: Optional[float] = None
    created_at: Optional[date] = None
    source: str = "QUOC_TE"  # QUOC_TE (fact_gradebooks) | BO_GD (fact_gradebooks_moet)


class EwsRawLmsItem(BaseModel):
    """Một bài tập LMS trong cửa sổ hiện diện [join_date, cutoff]."""
    code: Optional[str] = None
    fullname: Optional[str] = None
    max_grade: Optional[float] = None
    due_date: Optional[date] = None
    submitted: bool = False
    final_grade: Optional[float] = None


class EwsRawAttendanceItem(BaseModel):
    """Trạng thái điểm danh 1 ngày của học sinh."""
    date: date
    total_periods: int = 0
    absent_periods: int = 0
    absent_no_permission: int = 0
    absent_with_permission: int = 0
    status: str = "CÓ MẶT"  # CÓ MẶT | VẮNG | VẮNG KHÔNG PHÉP | NGHỈ CÓ PHÉP


class EwsRawBehaviorItem(BaseModel):
    """Một bản ghi kỷ luật / hành vi."""
    comment_date: Optional[date] = None
    behavior_fullname: Optional[str] = None
    behavior_point: Optional[float] = None
    sanction_name: Optional[str] = None


class EwsRawDetail(BaseModel):
    """Dữ liệu gốc (raw) để đối chiếu dự báo EWS của cặp (học sinh - môn)."""
    student_code: str
    subject_id: int
    school_year_id: int
    semester_index: int
    cutoff_date: Optional[date] = None
    join_date: Optional[date] = None
    scores: List[EwsRawScore] = Field(default_factory=list)
    lms: List[EwsRawLmsItem] = Field(default_factory=list)
    lms_expected: int = 0
    lms_submitted: int = 0
    attendance: List[EwsRawAttendanceItem] = Field(default_factory=list)
    behavior: List[EwsRawBehaviorItem] = Field(default_factory=list)


class EwsGoldenSetCase(BaseModel):
    """Một case trong golden set: tình huống + dự đoán + kỳ vọng."""
    id: str
    description: str
    predicted: str
    expected: str
    passed: bool
    risk_score: float
    score_risk: Optional[float] = None
    lms_risk: Optional[float] = None
    attendance_risk: Optional[float] = None
    behavior_risk: Optional[float] = None
    weight_attendance: Optional[float] = None
    weight_behavior: Optional[float] = None
    # Bộ 24 thông số đầu vào (đã sanitize NaN -> None) để UI hiển thị chi tiết.
    # Giá trị có thể là số (numeric feature) hoặc string (categorical: subject_id, ...).
    features: Dict[str, Any] = Field(default_factory=dict)


class EwsGoldenSetResult(BaseModel):
    """Kết quả chạy golden set: accuracy + danh sách case."""
    total: int
    passed: int
    accuracy: float
    cases: List[EwsGoldenSetCase] = Field(default_factory=list)
    # Metadata (Optional, non-breaking) — để dashboard hiển thị phiên bản model
    # và thời điểm sinh file cache tĩnh.
    model_version: Optional[str] = None
    generated_at: Optional[datetime] = None
    # school_id: trường được test (None = baseline YAML thuần). Chỉ dùng cho
    # file cache sinh ad-hoc khi BGH test thông số override; không ảnh hưởng API.
    school_id: Optional[int] = None


class EwsRiskBreakdownItem(BaseModel):
    """Mô tả phân bố rủi ro của 1 đơn vị (nhóm môn, môn học, hoặc lớp học)."""
    id: Optional[Any] = None
    name: str
    total_cnt: int = 0
    low_cnt: int = 0
    moderate_cnt: int = 0
    high_cnt: int = 0
    critical_cnt: int = 0
    low_pct: float = 0.0
    moderate_pct: float = 0.0
    high_pct: float = 0.0
    critical_pct: float = 0.0
    ch_pct: float = 0.0


class EwsStudentRiskDetailItem(BaseModel):
    """Bản ghi rủi ro từng học sinh khi drill-down tới level student."""
    student_code: str
    student_name: str
    week_label: str
    risk_level: str
    risk_score: float


class EwsSubjectDrilldownResponse(BaseModel):
    """Kết quả trả về cho API drill-down rủi ro theo môn học."""
    level: str  # 'group' | 'subject' | 'class' | 'student'
    breadcrumb: List[str] = Field(default_factory=list)
    items: List[EwsRiskBreakdownItem] = Field(default_factory=list)
    student_items: List[EwsStudentRiskDetailItem] = Field(default_factory=list)
    summary: Optional[EwsRiskBreakdownItem] = None


class EwsTopClassRiskItem(BaseModel):
    """Bản ghi thống kê trong Top 5 lớp rủi ro cao nhất."""
    rank: int
    class_name: str
    total_cnt: int = 0
    low_cnt: int = 0
    moderate_cnt: int = 0
    high_cnt: int = 0
    critical_cnt: int = 0
    low_pct: float = 0.0
    moderate_pct: float = 0.0
    high_pct: float = 0.0
    critical_pct: float = 0.0
    ch_pct: float = 0.0


# ============================================================================
# EWS CONTROL PANEL (BGH) — dự đoán theo tuần + tinh chỉnh trọng số
# ============================================================================


class EwsPredictRequest(BaseModel):
    """Yêu cầu chạy dự đoán EWS theo tuần (BGH)."""
    school_year_id: int = Field(..., description="Năm học (VD: 2025)")
    semester_index: int = Field(..., ge=1, le=2, description="Học kỳ (1 hoặc 2)")
    evaluated_at_week: int = Field(..., description="Tuần đánh giá")
    model_version: str = Field("v2_ensemble", description="'v1_single' hoặc 'v2_ensemble'")


class EwsJobRead(BaseModel):
    """Bản ghi job dự đoán EWS."""
    id: int
    so_school_id: int
    requested_by: int
    school_year_id: int
    semester_index: int
    evaluated_at_week: int
    cutoff_date: Optional[date] = None
    model_version: str
    status: str
    progress: int = 0
    rows_processed: Optional[int] = None
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    created_at: datetime


class EwsWeightConfig(BaseModel):
    """Override trọng số EWS theo trường (BGH tinh chỉnh). Mọi field đều optional."""
    weight_score: Optional[float] = None
    weight_lms: Optional[float] = None
    weight_attendance: Optional[float] = None
    weight_behavior: Optional[float] = None
    alpha_score: Optional[float] = None
    alpha_lms: Optional[float] = None
    alpha_attendance: Optional[float] = None
    alpha_behavior: Optional[float] = None
    weight_floor: Optional[float] = None
    worst_factor_beta: Optional[float] = None
    threshold_low: Optional[float] = None
    threshold_moderate: Optional[float] = None
    threshold_high: Optional[float] = None
    threshold_critical: Optional[float] = None


class EwsEffectiveConfig(BaseModel):
    """Config hiệu lực: baseline (YAML) + override (DB) + effective (đã merge)."""
    baseline: Dict[str, Any]
    override: Optional[EwsWeightConfig] = None
    effective: Dict[str, Any]


class EwsValidWeeks(BaseModel):
    """Các tuần hợp lệ để dự đoán theo học kỳ."""
    semester_1: List[int]
    semester_2: List[int]

