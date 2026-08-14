"""Unit tests for Deterministic Chart Generator & Document Embedding in Report Agent."""

import os
import pytest
from docx.enum.shape import WD_INLINE_SHAPE_TYPE
from src.agents.report_agent.chart_generator import (
    clean_num,
    detect_intent_from_table,
    generate_chart_for_table,
)
from src.agents.report_agent.visual_contracts import AnalyticalIntent
from src.agents.report_agent.tools import render_markdown_to_docx, render_markdown_to_html


def test_clean_num():
    """Kiểm tra làm sạch chuỗi số float."""
    assert clean_num("4.73") == 4.73
    assert clean_num("+0.52") == 0.52
    assert clean_num("-1.20") == -1.20
    assert clean_num("**8.5%**") == 8.5
    assert clean_num("abc") is None
    assert clean_num("") is None


def test_detect_intent_from_table():
    """Kiểm tra suy đoán Intent từ tiêu đề cột."""
    # Multi-entity compare
    h1 = ["Môn học", "Lớp 6A1 (ĐTB)", "Lớp 6A2 (ĐTB)", "Chênh lệch (Δ)", "Đánh giá"]
    assert detect_intent_from_table(h1, []) == AnalyticalIntent.MULTI_ENTITY_COMPARE

    # Ranking change
    h2 = ["STT", "Họ và tên", "Hạng HK1", "Hạng HK2", "Thay đổi (Δ)", "Ghi chú"]
    assert detect_intent_from_table(h2, []) == AnalyticalIntent.RANKING_CHANGE

    # Trend time series
    h3 = ["Môn học", "HK1 2023", "HK2 2023", "HK1 2024", "HK2 2024"]
    assert detect_intent_from_table(h3, []) == AnalyticalIntent.TREND_TIME_SERIES

    # Risk distribution
    h4 = ["Khối / Lớp", "An toàn (Safe)", "Cần theo dõi (Mod)", "Nguy cơ cao (High)", "Báo động (Crit)"]
    assert detect_intent_from_table(h4, []) == AnalyticalIntent.RISK_DISTRIBUTION

    # Gap diagnostic
    h5 = ["Chuyên đề", "Mức Bloom", "Tỷ lệ nắm vững (%)", "Đánh giá"]
    assert detect_intent_from_table(h5, []) == AnalyticalIntent.GAP_DIAGNOSTIC


def test_generate_chart_multi_entity_compare(tmp_path):
    """Kiểm tra sinh biểu đồ cột đôi cho ý đồ so sánh 2 lớp."""
    headers = ["Môn học", "Lớp 6A1 (ĐTB)", "Lớp 6A2 (ĐTB)", "Chênh lệch (Δ)", "Đánh giá"]
    rows = [
        ["Toán 6", "4.73", "5.25", "+0.52", "6A2 cao hơn"],
        ["Ngữ văn", "3.83", "4.06", "+0.23", "Tương đương"],
        ["Tiếng Anh", "3.84", "4.22", "+0.38", "6A2 cao hơn"],
    ]
    out_file = str(tmp_path / "test_compare.png")
    res = generate_chart_for_table(headers, rows, report_title="So sánh 6A1 vs 6A2", output_png_path=out_file)

    assert res is not None
    file_path, data_uri = res
    assert os.path.exists(file_path)
    assert os.path.getsize(file_path) > 1000
    assert data_uri.startswith("data:image/png;base64,")


def test_generate_chart_ranking_change(tmp_path):
    """Kiểm tra sinh biểu đồ biến động thứ hạng."""
    headers = ["STT", "Họ và tên", "Hạng HK1", "Hạng HK2", "Thay đổi (Δ)", "Ghi chú"]
    rows = [
        ["1", "Nguyễn Văn A", "1", "1", "0", "Giữ vững"],
        ["2", "Trần Thị B", "5", "2", "+3", "Tiến bộ"],
        ["3", "Lê Văn C", "2", "6", "-4", "Giảm sút"],
    ]
    out_file = str(tmp_path / "test_rank.png")
    res = generate_chart_for_table(headers, rows, report_title="Biến động thứ hạng", output_png_path=out_file)

    assert res is not None
    file_path, data_uri = res
    assert os.path.exists(file_path)
    assert os.path.getsize(file_path) > 1000


def test_generate_chart_trend_time_series(tmp_path):
    """Kiểm tra sinh biểu đồ đường xu hướng thời gian."""
    headers = ["Lớp", "HK1 2023", "HK2 2023", "HK1 2024", "HK2 2024"]
    rows = [
        ["6A1", "6.2", "6.5", "6.8", "7.1"],
        ["6A2", "5.8", "6.1", "6.4", "6.9"],
    ]
    out_file = str(tmp_path / "test_trend.png")
    res = generate_chart_for_table(headers, rows, report_title="Xu hướng điểm số", output_png_path=out_file)

    assert res is not None
    file_path, data_uri = res
    assert os.path.exists(file_path)
    assert os.path.getsize(file_path) > 1000


def test_render_markdown_to_docx_with_embedded_chart():
    """Kiểm tra nhúng ảnh biểu đồ vào tài liệu Word (.docx)."""
    md_content = """# BÁO CÁO SO SÁNH KẾT QUẢ HỌC TẬP LỚP 6A1 VÀ 6A2
<center>**TRƯỜNG THCS NGUYỄN DU**</center>
---
I. THÔNG TIN CHUNG & BỐI CẢNH:
So sánh điểm số học kỳ 1.

II. DỮ LIỆU & SỐ LIỆU THỰC TẾ:
| Môn học | Lớp 6A1 (ĐTB) | Lớp 6A2 (ĐTB) | Chênh lệch (Δ) | Đánh giá |
| :--- | :---: | :---: | :---: | :--- |
| **Toán 6** | 4.73 | 5.25 | +0.52 | Lớp 6A2 cao hơn |
| **Ngữ văn** | 3.83 | 4.06 | +0.23 | Tương đương |
| **Tiếng Anh** | 3.84 | 4.22 | +0.38 | Lớp 6A2 cao hơn |

III. ĐÁNH GIÁ & NHẬN XÉT:
Nhận xét chi tiết.
"""
    doc = render_markdown_to_docx("Báo cáo so sánh", md_content)
    assert doc is not None
    assert len(doc.tables) == 1

    # Kiểm tra xem có paragraph chứa ảnh không
    # python-docx nhúng ảnh vào paragraph thông qua runs và xml element w:drawing
    has_image = False
    for p in doc.paragraphs:
        if "w:drawing" in p._p.xml:
            has_image = True
            break
    assert has_image is True, "Tài liệu DOCX không chứa hình ảnh biểu đồ được nhúng"


def test_render_markdown_to_html_with_embedded_chart():
    """Kiểm tra nhúng ảnh Base64 vào HTML."""
    md_content = """| Môn học | Lớp 6A1 (ĐTB) | Lớp 6A2 (ĐTB) | Chênh lệch (Δ) | Đánh giá |
| :--- | :---: | :---: | :---: | :--- |
| **Toán 6** | 4.73 | 5.25 | +0.52 | Lớp 6A2 cao hơn |
| **Ngữ văn** | 3.83 | 4.06 | +0.23 | Tương đương |
"""
    html = render_markdown_to_html("Báo cáo test", md_content)
    assert '<table class="report-table">' in html
    assert '<img src="data:image/png;base64,' in html
    assert 'Hình: Biểu đồ trực quan hóa dữ liệu thống kê' in html
