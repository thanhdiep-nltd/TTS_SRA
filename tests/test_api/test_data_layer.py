"""Offline test cho tầng data: validation schema + đăng ký route.

Không chạm DB (an toàn cho CI). Kiểm thử tích hợp với DB được làm riêng.
"""

import pytest
from pydantic import ValidationError

from src.main import app
from src.schemas.school import GradeCreate, SemesterCreate
from src.schemas.score import ScoreCreate

SCHOOL_ID = "00000000-0000-0000-0000-000000000001"


def test_score_rejects_value_out_of_range():
    base = dict(
        student_id=SCHOOL_ID,
        subject_id=SCHOOL_ID,
        class_id=SCHOOL_ID,
        semester_id=SCHOOL_ID,
        score_category="MIDTERM",
        column_index=1,
    )
    with pytest.raises(ValidationError):
        ScoreCreate(**base, value=15)
    with pytest.raises(ValidationError):
        ScoreCreate(**base, value=-1)
    assert ScoreCreate(**base, value=8.5).value == 8.5


def test_grade_number_must_be_1_to_12():
    with pytest.raises(ValidationError):
        GradeCreate(school_id=SCHOOL_ID, name="Khối 13", grade_number=13, school_level="HIGH")


def test_semester_number_must_be_1_or_2():
    with pytest.raises(ValidationError):
        SemesterCreate(
            academic_year_id=SCHOOL_ID,
            name="HK3",
            number=3,
            start_date="2025-09-01",
            end_date="2026-01-15",
        )


def test_invalid_score_category_rejected():
    with pytest.raises(ValidationError):
        ScoreCreate(
            student_id=SCHOOL_ID,
            subject_id=SCHOOL_ID,
            class_id=SCHOOL_ID,
            semester_id=SCHOOL_ID,
            score_category="QUIZ",
            column_index=1,
            value=5,
        )


def test_data_routes_registered():
    # Dùng OpenAPI schema (API công khai, ổn định qua các phiên bản FastAPI/Starlette)
    # thay vì duyệt app.routes — FastAPI mới bọc include_router trong _IncludedRouter không có .path.
    paths = set(app.openapi()["paths"].keys())
    for expected in (
        "/api/v1/grades",
        "/api/v1/classes",
        "/api/v1/subjects",
        "/api/v1/students",
        "/api/v1/students/search",
        "/api/v1/enrollments",
        "/api/v1/scores",
        "/api/v1/scores/batch",
    ):
        assert expected in paths, f"Thiếu route {expected}"
