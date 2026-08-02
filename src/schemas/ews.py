# -*- coding: utf-8 -*-
"""
src/schemas/ews.py — Pydantic Schemas cho Early Warning System (EWS) Dashboard APIs
"""

from datetime import date
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
    risk_factors: List[str] = Field(default_factory=list, description="Cơ chế cờ rủi ro: SLOPE_DOWN | LAST_SCORE_LOW | ABSENTEEISM")
    evaluated_at_date: Optional[date] = None
    join_date: Optional[date] = None  # Ngày chuyển tới / nhập học vào lớp (NULL = có mặt từ đầu) — M2-PIVOT

    # 1. Temporal Scores (9)
    weighted_early_avg: Optional[float] = None
    weighted_late_avg: Optional[float] = None
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


class EwsMeta(BaseModel):
    """Dữ liệu metadata đổ dropdown bộ lọc."""
    weeks: List[EwsWeekOption] = Field(default_factory=list)
    subjects: List[Dict[str, Any]] = Field(default_factory=list)
    grades: List[Dict[str, Any]] = Field(default_factory=list)
    classes: List[EwsClassOption] = Field(default_factory=list)


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
