import pytest
from unittest.mock import MagicMock, patch

from src.agents.context import current_user_school_id
from src.agents.report_agent import queries
from src.agents.report_agent.tools import get_report_data_summary


@pytest.fixture(autouse=True)
def mock_compute_report_data():
    """Mock compute_report_data trong tools.py (imported từ queries)."""
    mock_data = {
        "semester_id": "2025-1",
        "sem_name": "Học Kỳ 1",
        "year_name": "2025-2026",
        "selected_grade_name": "Khối 8",
        "selected_class_name": " - Lớp 8A",
        "total_students": 100,
        "total_classes": 5,
        "gpa": 8.0,
        "at_risk": 2,
        "subject_averages": [
            {"Môn học": "Toán", "ĐTB": 8.2},
            {"Môn học": "Văn", "ĐTB": 7.8},
        ],
        "conduct_stats": {"TOT": 80, "KHA": 15, "TRUNG_BINH": 4, "YEU": 1},
    }
    with patch("src.agents.report_agent.tools.compute_report_data", return_value=mock_data) as mock_crd:
        yield mock_crd


@pytest.fixture(autouse=True)
def set_school_id():
    token = current_user_school_id.set(1)
    yield
    current_user_school_id.reset(token)


def test_get_report_data_summary_success(mock_compute_report_data):
    # @tool wraps get_report_data_summary into a StructuredTool -> dùng .func
    result = get_report_data_summary.func(
        report_type="academic_conduct",
        grade_level="8",
        class_id="8A",
        semester_id="1",
        school_year_id="2025-2026",
    )
    assert "BÁO CÁO TỔNG KẾT KẾT QUẢ HỌC TẬP VÀ RÈN LUYỆN" in result
    assert "100 học sinh" in result
    assert "80 học sinh" in result  # conduct TOT
    mock_compute_report_data.assert_called_once()


def test_get_report_data_summary_no_school():
    # Reset school_id to None
    current_user_school_id.set(None)
    result = get_report_data_summary.func(report_type="academic_conduct")
    assert "Không xác định được trường học" in result


def test_queries_is_valid_int():
    assert queries.is_valid_int("123") is True
    assert queries.is_valid_int(456) is True
    assert queries.is_valid_int("abc") is False
    assert queries.is_valid_int(None) is False
    assert queries.is_valid_int("") is False