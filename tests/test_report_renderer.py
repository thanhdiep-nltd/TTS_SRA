from src.api.v1.report_renderer import parse_ai_comment


def test_parse_ai_comment_standard():
    comment = """
    1. TÓM TẮT TÌNH HÌNH:
    Nhận xét tóm tắt.

    2. PHÂN TÍCH CHUYÊN MÔN:
    Phân tích chi tiết.

    3. ĐỀ XUẤT SƯ PHẠM VÀ PHƯƠNG HƯỚNG ĐIỀU CHỈNH:
    Khuyến nghị sư phạm.
    """
    p1, p2, p3 = parse_ai_comment(comment)
    assert p1 == "Nhận xét tóm tắt."
    assert p2 == "Phân tích chi tiết."
    assert p3 == "Khuyến nghị sư phạm."


def test_parse_ai_comment_with_english_fallbacks():
    comment = """
    1. Executive Summary:
    Some summary text.

    2. In-depth Analysis:
    Some in-depth analysis.

    3. Recommendations:
    Some recommendations.
    """
    p1, p2, p3 = parse_ai_comment(comment)
    assert p1 == "Some summary text."
    assert p2 == "Some in-depth analysis."
    assert p3 == "Some recommendations."


def test_parse_ai_comment_no_headings():
    comment = "Một nhận xét chung chung không có phân tách tiêu đề nào."
    p1, p2, p3 = parse_ai_comment(comment)
    assert p1 == "Một nhận xét chung chung không có phân tách tiêu đề nào."
    assert p2 == ""
    assert p3 == ""
