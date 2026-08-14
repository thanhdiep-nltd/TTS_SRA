"""Unit tests for Visual Contracts & Intent-Driven Visualization in Report Agent."""

import pytest
from src.agents.report_agent.visual_contracts import (
    AnalyticalIntent,
    ColumnAlignment,
    EDUCATIONAL_VISUAL_CONTRACTS,
    build_taxonomy_prompt_instructions,
    detect_cell_alignment,
    get_visual_contract,
    sanitize_delta_value,
)
from src.agents.report_agent.tools import render_markdown_to_docx, render_markdown_to_html


def test_visual_contracts_catalog_coverage():
    """Kiểm tra danh mục 7 Visual Contracts đầy đủ và hợp lệ."""
    expected_intents = [
        AnalyticalIntent.MULTI_ENTITY_COMPARE,
        AnalyticalIntent.RANKING_CHANGE,
        AnalyticalIntent.TREND_TIME_SERIES,
        AnalyticalIntent.RISK_DISTRIBUTION,
        AnalyticalIntent.AT_RISK_STUDENT_LIST,
        AnalyticalIntent.GAP_DIAGNOSTIC,
        AnalyticalIntent.SINGLE_METRIC_BREAKDOWN,
    ]
    for intent in expected_intents:
        contract = EDUCATIONAL_VISUAL_CONTRACTS.get(intent)
        assert contract is not None, f"Thiếu contract cho {intent}"
        assert len(contract.required_columns) > 0
        assert len(contract.column_specs) > 0
        assert contract.recommended_chart != ""
        assert len(contract.forbidden_charts) > 0
        assert len(contract.rules) > 0
        assert "|" in contract.sample_markdown


def test_get_visual_contract_by_string_and_enum():
    """Kiểm tra lấy contract bằng string hoặc enum."""
    c1 = get_visual_contract("multi_entity_compare")
    c2 = get_visual_contract(AnalyticalIntent.MULTI_ENTITY_COMPARE)
    assert c1 is not None
    assert c1 == c2
    assert c1.intent == AnalyticalIntent.MULTI_ENTITY_COMPARE

    invalid_c = get_visual_contract("non_existent_intent")
    assert invalid_c is None


def test_detect_cell_alignment():
    """Kiểm tra tự động suy đoán căn lề cho từng loại dữ liệu."""
    # STT / Mã / Hạng -> Center
    assert detect_cell_alignment("STT", "1") == ColumnAlignment.CENTER
    assert detect_cell_alignment("Mã HS", "HS0012") == ColumnAlignment.CENTER
    assert detect_cell_alignment("Lớp", "6A1") == ColumnAlignment.CENTER
    assert detect_cell_alignment("Mức Bloom", "Mức 3") == ColumnAlignment.CENTER

    # Điểm số / Chênh lệch / Tỷ lệ -> Right
    assert detect_cell_alignment("Lớp 6A1 (ĐTB)", "4.73") == ColumnAlignment.RIGHT
    assert detect_cell_alignment("Chênh lệch (Δ)", "+0.52") == ColumnAlignment.RIGHT
    assert detect_cell_alignment("Tỷ lệ (%)", "15.5%") == ColumnAlignment.RIGHT
    assert detect_cell_alignment("Số lượng", "35") == ColumnAlignment.RIGHT

    # Tên môn / Họ tên / Đánh giá -> Left
    assert detect_cell_alignment("Môn học", "Toán 6") == ColumnAlignment.LEFT
    assert detect_cell_alignment("Họ và tên", "Nguyễn Văn A") == ColumnAlignment.LEFT
    assert detect_cell_alignment("Đánh giá", "Lớp 6A2 cao hơn") == ColumnAlignment.LEFT


def test_sanitize_delta_value():
    """Kiểm tra chuẩn hóa giá trị chênh lệch (Delta)."""
    assert sanitize_delta_value("+0.52") == "+0.52"
    assert sanitize_delta_value("0.52") == "+0.52"
    assert sanitize_delta_value("-1.2") == "-1.20"
    assert sanitize_delta_value("0") == "0.00"
    assert sanitize_delta_value("Tương đương") == "Tương đương"


def test_build_taxonomy_prompt_instructions():
    """Kiểm tra tạo khối hướng dẫn prompt chứa đầy đủ 7 intent."""
    prompt_text = build_taxonomy_prompt_instructions()
    assert "VISUALIZATION TAXONOMY" in prompt_text
    for intent in AnalyticalIntent:
        assert intent.value in prompt_text


def test_render_markdown_to_docx_with_visual_contracts():
    """Kiểm tra xuất DOCX chứa bảng chuẩn hóa và căn lề đúng."""
    md_content = """# BÁO CÁO SO SÁNH KẾT QUẢ HỌC TẬP LỚP 6A1 VÀ 6A2
<center>**TRƯỜNG THCS NGUYỄN DU**</center>
---
I. THÔNG TIN CHUNG & BỐI CẢNH:
Báo cáo so sánh điểm số học kỳ 1 giữa lớp 6A1 và 6A2.

II. DỮ LIỆU & SỐ LIỆU THỰC TẾ:
| Môn học | Lớp 6A1 (ĐTB) | Lớp 6A2 (ĐTB) | Chênh lệch (Δ) | Đánh giá |
| :--- | :---: | :---: | :---: | :--- |
| **Toán 6** | 4.73 | 5.25 | 0.52 | Lớp 6A2 cao hơn |
| **Ngữ văn** | 3.83 | 4.06 | 0.23 | Tương đương |
| **Tiếng Anh** | 3.84 | 4.22 | 0.38 | Lớp 6A2 cao hơn |

III. ĐÁNH GIÁ & NHẬN XÉT:
Điểm trung bình các môn của lớp 6A2 đều nhỉnh hơn lớp 6A1.

IV. PHƯƠNG HƯỚNG XỬ LÝ / KIẾN NGHỊ:
Tăng cường phụ đạo môn Ngữ văn cho cả 2 lớp.
"""
    doc = render_markdown_to_docx("Báo cáo so sánh", md_content)
    assert doc is not None
    assert len(doc.tables) == 1
    table = doc.tables[0]
    assert len(table.rows) == 4
    # Header row
    header_cells = [c.text.strip() for c in table.rows[0].cells]
    assert "Môn học" in header_cells[0]
    assert "Lớp 6A1 (ĐTB)" in header_cells[1]
    assert "Chênh lệch (Δ)" in header_cells[3]

    # Data row 1 (Toán 6)
    row1_cells = [c.text.strip() for c in table.rows[1].cells]
    assert row1_cells[0] == "Toán 6"
    assert row1_cells[1] == "4.73"
    assert row1_cells[2] == "5.25"
    assert row1_cells[3] == "+0.52"  # Auto-sanitized delta


def test_render_markdown_to_html_with_visual_contracts():
    """Kiểm tra xuất HTML chứa bảng với CSS text-align đúng chuẩn."""
    md_content = """| Môn học | Lớp 6A1 (ĐTB) | Lớp 6A2 (ĐTB) | Chênh lệch (Δ) | Đánh giá |
| :--- | :---: | :---: | :---: | :--- |
| **Toán 6** | 4.73 | 5.25 | 0.52 | Lớp 6A2 cao hơn |
"""
    html = render_markdown_to_html("Báo cáo test", md_content)
    assert '<table class="report-table">' in html
    assert '<th style="text-align: center;">Môn học</th>' in html
    assert '<td style="text-align: left;"><strong>Toán 6</strong></td>' in html
    assert '<td style="text-align: right;">4.73</td>' in html
    assert '<td style="text-align: right;">+0.52</td>' in html  # Auto-sanitized delta
