import uuid
from unittest.mock import MagicMock, patch

import pytest

from src.agents.context import current_user_school_id
from src.agents.report_agent.tools import (
    generate_custom_report_docx,
    generate_report_download_link,
    get_report_data_summary,
)


@pytest.fixture(autouse=True)
def mock_get_llm_reports():
    with patch("src.api.v1.reports.get_llm") as mock_get_llm:
        mock_chat = MagicMock()
        mock_chat.invoke = MagicMock(return_value=MagicMock(content="Nhận xét giả lập từ AI."))
        mock_get_llm.return_value = mock_chat
        yield mock_chat


@pytest.fixture(autouse=True)
def mock_db_and_functions():
    mock_data = {
        "total_students": 100,
        "total_classes": 5,
        "gpa": 8.0,
        "at_risk": 2,
        "selected_grade_name": "Khối 8",
        "selected_class_name": "Lớp 8A",
        "year_name": "2024-2025",
        "sem_name": "Học kỳ 1",
        "conduct_stats": {
            "TOT": 80,
            "KHA": 15,
            "TRUNG_BINH": 4,
            "YEU": 1,
        },
        "subject_averages": [
            {"Môn học": "Toán", "ĐTB": 8.2},
            {"Môn học": "Văn", "ĐTB": 7.8},
        ],
    }

    mock_db = MagicMock()

    mock_school = MagicMock()
    mock_school.name = "Trường THCS Test"

    mock_user = MagicMock()
    mock_user.school_id = uuid.UUID("cedf3fb6-564e-402c-9304-6ae485495301")
    mock_user.is_active = True

    mock_db.get.return_value = mock_school
    mock_db.execute.return_value.scalars.return_value.first.return_value = mock_user

    mock_session_local = MagicMock()
    mock_session_local.return_value.__enter__.return_value = mock_db

    mock_response = MagicMock()
    mock_response.body = b"dummy docx content"

    with (
        patch("src.agents.report_agent.tools.compute_report_data", return_value=mock_data),
        patch("src.agents.report_agent.tools.SessionLocal", mock_session_local),
        patch("src.agents.report_agent.tools.resolve_uuid_parameters", return_value=(None, None, None)),
        patch("src.api.v1.reports.export_analytics_report", return_value=mock_response),
    ):
        yield mock_db


@pytest.mark.asyncio
async def test_get_report_data_summary_no_context():
    current_user_school_id.set(None)
    res = get_report_data_summary.invoke({"report_type": "academic_conduct", "grade_level": "all"})
    assert "Lỗi" in res


@pytest.mark.asyncio
async def test_get_report_data_summary_with_context():
    mock_school_id = uuid.UUID("cedf3fb6-564e-402c-9304-6ae485495301")
    current_user_school_id.set(mock_school_id)

    res = get_report_data_summary.invoke({"report_type": "academic_conduct", "grade_level": "all"})

    assert "BÁO CÁO TỔNG KẾT KẾT QUẢ HỌC TẬP VÀ RÈN LUYỆN" in res
    assert "Sĩ số học sinh" in res


@pytest.mark.asyncio
async def test_generate_report_download_link():
    mock_school_id = uuid.UUID("cedf3fb6-564e-402c-9304-6ae485495301")
    current_user_school_id.set(mock_school_id)

    res = await generate_report_download_link.ainvoke(
        {"report_type": "academic_conduct", "format": "docx", "grade_level": "all", "include_ai_insights": False}
    )

    assert "tải trực tiếp" in res or "Tải Báo Cáo Tại Đây" in res
    assert "bao_cao_academic_conduct_" in res
    assert ".docx" in res


@pytest.mark.asyncio
async def test_generate_custom_report_docx():
    mock_school_id = uuid.UUID("cedf3fb6-564e-402c-9304-6ae485495301")
    current_user_school_id.set(mock_school_id)

    res = await generate_custom_report_docx.ainvoke(
        {
            "title": "Báo cáo thử nghiệm",
            "content_markdown": "# Tiêu đề 1\nNội dung chính tự do.\n- Danh sách 1\n- Danh sách 2\n\n| Cột A | Cột B |\n| --- | --- |\n| Giá trị 1 | Giá trị 2 |",
        }
    )

    assert "Tải Báo Cáo Word (.docx)" in res
    assert "Xem Bản Xem Trước Báo Cáo" in res
    assert "bao_cao_tu_do_" in res
    assert ".docx" in res
    assert ".html" in res
