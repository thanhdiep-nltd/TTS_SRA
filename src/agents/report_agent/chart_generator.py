"""Module Tự động Sinh Biểu đồ Chuẩn hóa (Deterministic Chart Generator) cho Report Agent.

Sử dụng Matplotlib (Agg backend) để render biểu đồ có độ phân giải cao (300 DPI)
dựa trên cấu trúc bảng dữ liệu thực tế trích xuất từ Mục II của báo cáo và
khớp 1-1 với từng Ý đồ Phân tích (Analytical Intent) trong Visual Contracts.
"""

import base64
import io
import os
import re
from typing import Dict, List, Optional, Tuple

import matplotlib
# Sử dụng Agg backend để render headless trên server/worker, không cần GUI
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from src.agents.report_agent.visual_contracts import AnalyticalIntent


# Thiết lập bảng màu sư phạm chuyên nghiệp (Educational Color Palette)
CHART_COLORS = {
    "primary": "#2563EB",     # Xanh dương đậm (Brand Primary)
    "secondary": "#10B981",   # Xanh lục ngọc (Emerald / Positive)
    "accent": "#F59E0B",      # Vàng hổ phách (Amber / Warning)
    "danger": "#EF4444",      # Đỏ tươi (Rose / Danger)
    "purple": "#8B5CF6",      # Tím thanh lịch
    "teal": "#14B8A6",        # Xanh mòng két
    "gray": "#64748B",        # Xám thanh lịch
    "safe": "#10B981",        # Mức An toàn
    "moderate": "#F59E0B",    # Mức Cần theo dõi
    "high": "#F97316",        # Mức Nguy cơ cao
    "critical": "#EF4444",    # Mức Báo động
}

PALETTE_SERIES = ["#2563EB", "#10B981", "#F59E0B", "#8B5CF6", "#14B8A6", "#EC4899", "#6366F1"]


def clean_num(val: str) -> Optional[float]:
    """Chuyển đổi chuỗi số (kèm +, %, điểm) thành số thực float an toàn."""
    if not val:
        return None
    # Bỏ markdown bold/italic, % và dấu cộng
    s = re.sub(r"[\*\*_~%]", "", str(val)).strip()
    s = s.replace("+", "")
    try:
        return float(s)
    except (ValueError, TypeError):
        return None


def detect_intent_from_table(headers: List[str], rows: List[List[str]]) -> AnalyticalIntent:
    """Tự động suy đoán chính xác AnalyticalIntent từ cấu trúc các cột trong bảng."""
    h_lower_list = [h.lower().strip() for h in headers]
    h_combined = " ".join(h_lower_list)

    # 1. So sánh 2 lớp / 2 đối tượng (multi_entity_compare)
    # Đặc điểm: Cột 1 là môn học/chỉ số, có >= 2 cột đối tượng (lớp/khối) và cột chênh lệch (Δ)
    if ("chênh lệch" in h_combined or "delta" in h_combined or "(δ)" in h_combined) and (
        "môn" in h_combined or "chỉ số" in h_combined or any("lớp" in h for h in h_lower_list)
    ):
        if "hạng" not in h_combined:
            return AnalyticalIntent.MULTI_ENTITY_COMPARE

    # 2. Biến động thứ hạng (ranking_change)
    # Đặc điểm: Có cột Hạng trước, Hạng sau, Thay đổi (▲/▼)
    if "hạng" in h_combined or ("thứ hạng" in h_combined and "thay đổi" in h_combined):
        return AnalyticalIntent.RANKING_CHANGE

    # 3. Chuỗi thời gian / Xu hướng (trend_time_series)
    # Đặc điểm: Có các cột đại diện cho mốc thời gian (HK1, HK2, Năm 1, Năm 2, Tháng 1...)
    time_markers = ["hk1", "hk2", "kỳ 1", "kỳ 2", "học kỳ", "năm học", "tháng", "tuần"]
    time_col_count = sum(1 for h in h_lower_list if any(tm in h for tm in time_markers))
    if time_col_count >= 2:
        return AnalyticalIntent.TREND_TIME_SERIES

    # 4. Phân tầng rủi ro (risk_distribution)
    if any(k in h_combined for k in ["mức rủi ro", "phân tầng", "safe", "moderate", "high", "critical", "nguy cơ"]):
        return AnalyticalIntent.RISK_DISTRIBUTION

    # 5. Danh sách học sinh cần hỗ trợ (at_risk_student_list)
    if "mã hs" in h_combined or "học sinh" in h_combined and "nguy cơ" in h_combined:
        return AnalyticalIntent.AT_RISK_STUDENT_LIST

    # 6. Chẩn đoán lỗ hổng kiến thức theo Bloom (gap_diagnostic)
    if "bloom" in h_combined or "mức bloom" in h_combined or "đơn vị kiến thức" in h_combined or "chuyên đề" in h_combined:
        return AnalyticalIntent.GAP_DIAGNOSTIC

    # 7. Mặc định là thống kê phân rã đơn chỉ số
    return AnalyticalIntent.SINGLE_METRIC_BREAKDOWN


def _configure_chart_style():
    """Cài đặt phong cách đồ họa trang trọng, phông chữ và lưới nhã nhặn."""
    plt.rcParams["font.sans-serif"] = ["DejaVu Sans", "Arial", "Times New Roman", "Helvetica"]
    plt.rcParams["axes.edgecolor"] = "#CBD5E1"
    plt.rcParams["axes.linewidth"] = 0.8
    plt.rcParams["grid.color"] = "#F1F5F9"
    plt.rcParams["grid.linestyle"] = "--"
    plt.rcParams["grid.alpha"] = 0.7


def _render_multi_entity_compare(headers: List[str], rows: List[List[str]], title: str) -> Optional[plt.Figure]:
    """Vẽ Grouped Bar Chart cho ý đồ so sánh đối sánh nhiều thực thể (Lớp 1 vs Lớp 2...)."""
    categories = []
    series_names = []
    numeric_col_indices = []

    # Tìm các cột số liệu để vẽ (loại bỏ cột đầu tiên là tên môn và cột chênh lệch/đánh giá ở cuối)
    for idx, h in enumerate(headers):
        if idx == 0:
            continue
        h_l = h.lower()
        if "chênh lệch" in h_l or "(δ)" in h_l or "đánh giá" in h_l or "ghi chú" in h_l:
            continue
        # Kiểm tra xem cột có chứa số không
        has_num = any(clean_num(r[idx]) is not None for r in rows if idx < len(r))
        if has_num:
            numeric_col_indices.append(idx)
            series_names.append(headers[idx])

    if not numeric_col_indices:
        return None

    # Lấy nhãn danh mục từ cột 0
    categories = [re.sub(r"[\*\*_~]", "", r[0]).strip() for r in rows if len(r) > 0]
    if not categories:
        return None

    series_data = {s_name: [] for s_name in series_names}
    for r in rows:
        for s_idx, col_idx in enumerate(numeric_col_indices):
            val = clean_num(r[col_idx]) if col_idx < len(r) else 0.0
            series_data[series_names[s_idx]].append(val if val is not None else 0.0)

    x = np.arange(len(categories))
    num_series = len(series_names)
    bar_width = min(0.35, 0.8 / max(num_series, 1))

    fig, ax = plt.subplots(figsize=(8.5, 4.2), dpi=300)
    fig.patch.set_facecolor("#FFFFFF")
    ax.set_facecolor("#FAFAFA")

    for i, s_name in enumerate(series_names):
        offset = (i - (num_series - 1) / 2) * bar_width
        vals = series_data[s_name]
        color = PALETTE_SERIES[i % len(PALETTE_SERIES)]
        bars = ax.bar(x + offset, vals, bar_width, label=s_name, color=color, edgecolor="#FFFFFF", linewidth=1.2, zorder=3)

        # Thêm nhãn số liệu trực tiếp trên đỉnh cột (Data Labels)
        for bar in bars:
            height = bar.get_height()
            if height > 0:
                ax.annotate(
                    f"{height:.2f}" if isinstance(height, float) and height < 10 else f"{height:g}",
                    xy=(bar.get_x() + bar.get_width() / 2, height),
                    xytext=(0, 3),
                    textcoords="offset points",
                    ha="center",
                    va="bottom",
                    fontsize=8.5,
                    fontweight="bold",
                    color="#1E293B",
                )

    ax.set_xticks(x)
    ax.set_xticklabels(categories, fontsize=9.5, fontweight="medium", rotation=15 if len(categories) > 5 else 0, ha="right" if len(categories) > 5 else "center")
    ax.set_ylabel("Điểm số / Giá trị", fontsize=9.5, fontweight="bold", color="#334155")
    ax.set_title(title or "Biểu đồ Đối sánh Kết quả Học tập", fontsize=11.5, fontweight="bold", pad=14, color="#0F172A")
    ax.legend(frameon=True, facecolor="#FFFFFF", edgecolor="#E2E8F0", fontsize=9, loc="upper right")
    ax.grid(axis="y", linestyle="--", alpha=0.5, zorder=0)

    # Đặt giới hạn trục Y hợp lý
    max_val = max([max(v) for v in series_data.values()] + [10])
    ax.set_ylim(0, max_val * 1.15)
    plt.tight_layout()
    return fig


def _render_ranking_change(headers: List[str], rows: List[List[str]], title: str) -> Optional[plt.Figure]:
    """Vẽ Diverging Bar Chart cho biến động thứ hạng (Tăng / Giảm)."""
    categories = []
    deltas = []

    # Tìm cột đối tượng (cột 1/họ tên/lớp) và cột delta
    delta_idx = None
    for idx, h in enumerate(headers):
        if any(k in h.lower() for k in ["thay đổi", "chênh lệch", "delta", "(δ)"]):
            delta_idx = idx
            break

    if delta_idx is None and len(headers) >= 3:
        delta_idx = 3 if len(headers) > 3 else len(headers) - 1

    for r in rows:
        if not r or len(r) <= 1:
            continue
        name = re.sub(r"[\*\*_~]", "", r[1] if len(r) > 1 and "stt" in headers[0].lower() else r[0]).strip()
        val_str = r[delta_idx] if delta_idx < len(r) else "0"
        val = clean_num(val_str)
        if val is not None:
            categories.append(name)
            deltas.append(val)

    if not categories:
        return None

    y_pos = np.arange(len(categories))
    colors = [CHART_COLORS["secondary"] if d >= 0 else CHART_COLORS["danger"] for d in deltas]

    fig, ax = plt.subplots(figsize=(8.0, max(3.5, len(categories) * 0.45)), dpi=300)
    fig.patch.set_facecolor("#FFFFFF")
    ax.set_facecolor("#FAFAFA")

    bars = ax.barh(y_pos, deltas, color=colors, edgecolor="#FFFFFF", height=0.55, zorder=3)
    ax.axvline(0, color="#94A3B8", linewidth=1.0, linestyle="--", zorder=2)

    for bar in bars:
        width = bar.get_width()
        ha = "left" if width >= 0 else "right"
        offset = 4 if width >= 0 else -4
        prefix = "+" if width > 0 else ""
        ax.annotate(
            f"{prefix}{width:g}",
            xy=(width, bar.get_y() + bar.get_height() / 2),
            xytext=(offset, 0),
            textcoords="offset points",
            ha=ha,
            va="center",
            fontsize=8.5,
            fontweight="bold",
            color="#1E293B",
        )

    ax.set_yticks(y_pos)
    ax.set_yticklabels(categories, fontsize=9, fontweight="medium")
    ax.invert_yaxis()  # Đưa phần tử đầu lên trên cùng
    ax.set_xlabel("Mức độ Thay đổi (Thứ hạng / Điểm số)", fontsize=9.5, fontweight="bold", color="#334155")
    ax.set_title(title or "Biểu đồ Biến động Thứ hạng", fontsize=11.5, fontweight="bold", pad=12, color="#0F172A")
    ax.grid(axis="x", linestyle="--", alpha=0.5, zorder=0)
    plt.tight_layout()
    return fig


def _render_trend_time_series(headers: List[str], rows: List[List[str]], title: str) -> Optional[plt.Figure]:
    """Vẽ Multi-line Trend Chart cho chuỗi thời gian."""
    time_markers = ["hk1", "hk2", "kỳ 1", "kỳ 2", "học kỳ", "năm học", "tháng", "tuần", "gpa"]
    time_cols = []
    time_labels = []

    for idx, h in enumerate(headers):
        if idx == 0:
            continue
        if any(tm in h.lower() for tm in time_markers) or "điểm" in h.lower():
            time_cols.append(idx)
            time_labels.append(headers[idx])

    if len(time_cols) < 2:
        return None

    fig, ax = plt.subplots(figsize=(8.5, 4.2), dpi=300)
    fig.patch.set_facecolor("#FFFFFF")
    ax.set_facecolor("#FAFAFA")

    for r_idx, r in enumerate(rows):
        entity_name = re.sub(r"[\*\*_~]", "", r[0]).strip()
        y_vals = []
        for c_idx in time_cols:
            val = clean_num(r[c_idx]) if c_idx < len(r) else None
            y_vals.append(val if val is not None else 0.0)

        color = PALETTE_SERIES[r_idx % len(PALETTE_SERIES)]
        ax.plot(time_labels, y_vals, marker="o", linewidth=2.2, markersize=6, label=entity_name, color=color, zorder=3)

        for x_pt, y_pt in zip(time_labels, y_vals):
            ax.annotate(
                f"{y_pt:.2f}" if isinstance(y_pt, float) and y_pt < 10 else f"{y_pt:g}",
                xy=(x_pt, y_pt),
                xytext=(0, 5),
                textcoords="offset points",
                ha="center",
                fontsize=8,
                fontweight="bold",
                color="#1E293B",
            )

    ax.set_title(title or "Biểu đồ Diễn biến Xu hướng Học tập", fontsize=11.5, fontweight="bold", pad=12, color="#0F172A")
    ax.set_ylabel("Điểm trung bình", fontsize=9.5, fontweight="bold", color="#334155")
    ax.legend(frameon=True, facecolor="#FFFFFF", edgecolor="#E2E8F0", fontsize=8.5, loc="best")
    ax.grid(True, linestyle="--", alpha=0.5, zorder=0)
    plt.tight_layout()
    return fig


def _render_risk_distribution(headers: List[str], rows: List[List[str]], title: str) -> Optional[plt.Figure]:
    """Vẽ Distribution Bar Chart cho phân tầng 4 mức rủi ro."""
    categories = []
    safe_vals, mod_vals, high_vals, crit_vals = [], [], [], []

    # Map các mức rủi ro theo cột
    safe_idx = next((i for i, h in enumerate(headers) if "an toàn" in h.lower() or "safe" in h.lower()), None)
    mod_idx = next((i for i, h in enumerate(headers) if "theo dõi" in h.lower() or "moderate" in h.lower()), None)
    high_idx = next((i for i, h in enumerate(headers) if "cao" in h.lower() or "high" in h.lower()), None)
    crit_idx = next((i for i, h in enumerate(headers) if "báo động" in h.lower() or "critical" in h.lower()), None)

    if safe_idx is None or high_idx is None:
        return None

    for r in rows:
        categories.append(re.sub(r"[\*\*_~]", "", r[0]).strip())
        safe_vals.append(clean_num(r[safe_idx]) if safe_idx < len(r) else 0)
        mod_vals.append(clean_num(r[mod_idx]) if mod_idx is not None and mod_idx < len(r) else 0)
        high_vals.append(clean_num(r[high_idx]) if high_idx < len(r) else 0)
        crit_vals.append(clean_num(r[crit_idx]) if crit_idx is not None and crit_idx < len(r) else 0)

    x = np.arange(len(categories))
    bar_width = 0.18

    fig, ax = plt.subplots(figsize=(8.5, 4.0), dpi=300)
    fig.patch.set_facecolor("#FFFFFF")
    ax.set_facecolor("#FAFAFA")

    ax.bar(x - 1.5 * bar_width, safe_vals, bar_width, label="An toàn", color=CHART_COLORS["safe"], zorder=3)
    ax.bar(x - 0.5 * bar_width, mod_vals, bar_width, label="Theo dõi", color=CHART_COLORS["moderate"], zorder=3)
    ax.bar(x + 0.5 * bar_width, high_vals, bar_width, label="Nguy cơ cao", color=CHART_COLORS["high"], zorder=3)
    ax.bar(x + 1.5 * bar_width, crit_vals, bar_width, label="Báo động", color=CHART_COLORS["critical"], zorder=3)

    ax.set_xticks(x)
    ax.set_xticklabels(categories, fontsize=9.5, fontweight="medium")
    ax.set_ylabel("Số lượng học sinh", fontsize=9.5, fontweight="bold", color="#334155")
    ax.set_title(title or "Biểu đồ Phân tầng Rủi ro Học tập", fontsize=11.5, fontweight="bold", pad=12, color="#0F172A")
    ax.legend(frameon=True, facecolor="#FFFFFF", edgecolor="#E2E8F0", fontsize=8.5, loc="upper right")
    ax.grid(axis="y", linestyle="--", alpha=0.5, zorder=0)
    plt.tight_layout()
    return fig


def _render_gap_diagnostic(headers: List[str], rows: List[List[str]], title: str) -> Optional[plt.Figure]:
    """Vẽ Horizontal Bar Chart cho chẩn đoán lỗ hổng kiến thức."""
    topics = []
    mastery_rates = []

    # Tìm cột tỷ lệ đạt hoặc điểm
    rate_idx = next((i for i, h in enumerate(headers) if "đạt" in h.lower() or "tỷ lệ" in h.lower() or "điểm" in h.lower()), None)
    if rate_idx is None:
        rate_idx = len(headers) - 1

    for r in rows:
        if not r:
            continue
        topic_name = re.sub(r"[\*\*_~]", "", r[1] if len(r) > 1 and "stt" in headers[0].lower() else r[0]).strip()
        val = clean_num(r[rate_idx]) if rate_idx < len(r) else None
        if val is not None:
            topics.append(topic_name)
            mastery_rates.append(val)

    if not topics:
        return None

    y_pos = np.arange(len(topics))
    # Đổi màu: Dưới 50% là đỏ (lỗ hổng), 50-70% là cam, >70% là xanh
    colors = [CHART_COLORS["danger"] if v < 50 else (CHART_COLORS["accent"] if v < 70 else CHART_COLORS["secondary"]) for v in mastery_rates]

    fig, ax = plt.subplots(figsize=(8.5, max(3.5, len(topics) * 0.45)), dpi=300)
    fig.patch.set_facecolor("#FFFFFF")
    ax.set_facecolor("#FAFAFA")

    bars = ax.barh(y_pos, mastery_rates, color=colors, height=0.55, zorder=3)
    ax.axvline(50, color=CHART_COLORS["danger"], linestyle=":", linewidth=1.2, label="Ngưỡng đạt chuẩn (50%)", zorder=2)

    for bar in bars:
        w = bar.get_width()
        ax.annotate(
            f"{w:g}%",
            xy=(w, bar.get_y() + bar.get_height() / 2),
            xytext=(4, 0),
            textcoords="offset points",
            va="center",
            fontsize=8.5,
            fontweight="bold",
            color="#1E293B",
        )

    ax.set_yticks(y_pos)
    ax.set_yticklabels(topics, fontsize=9, fontweight="medium")
    ax.invert_yaxis()
    ax.set_xlim(0, 115)
    ax.set_xlabel("Tỷ lệ Nắm vững Kiến thức (%)", fontsize=9.5, fontweight="bold", color="#334155")
    ax.set_title(title or "Chẩn đoán Lỗ hổng Kiến thức theo Chủ đề", fontsize=11.5, fontweight="bold", pad=12, color="#0F172A")
    ax.legend(frameon=True, facecolor="#FFFFFF", edgecolor="#E2E8F0", fontsize=8.5, loc="lower right")
    ax.grid(axis="x", linestyle="--", alpha=0.5, zorder=0)
    plt.tight_layout()
    return fig


def _render_single_metric_breakdown(headers: List[str], rows: List[List[str]], title: str) -> Optional[plt.Figure]:
    """Vẽ Bar Chart chuẩn cho phân rã đơn chỉ số."""
    categories = []
    values = []

    val_idx = next((i for i, h in enumerate(headers) if any(k in h.lower() for k in ["đtb", "gpa", "số lượng", "điểm", "tỷ lệ"])), 1)

    for r in rows:
        if not r:
            continue
        cat_name = re.sub(r"[\*\*_~]", "", r[1] if len(r) > 1 and "stt" in headers[0].lower() else r[0]).strip()
        val = clean_num(r[val_idx]) if val_idx < len(r) else None
        if val is not None:
            categories.append(cat_name)
            values.append(val)

    if not categories or len(categories) < 2:
        return None

    x = np.arange(len(categories))
    fig, ax = plt.subplots(figsize=(8.0, 4.0), dpi=300)
    fig.patch.set_facecolor("#FFFFFF")
    ax.set_facecolor("#FAFAFA")

    bars = ax.bar(x, values, color=CHART_COLORS["primary"], width=0.45, zorder=3)

    for bar in bars:
        h = bar.get_height()
        ax.annotate(
            f"{h:.2f}" if isinstance(h, float) and h < 10 else f"{h:g}",
            xy=(bar.get_x() + bar.get_width() / 2, h),
            xytext=(0, 3),
            textcoords="offset points",
            ha="center",
            va="bottom",
            fontsize=8.5,
            fontweight="bold",
            color="#1E293B",
        )

    ax.set_xticks(x)
    ax.set_xticklabels(categories, fontsize=9, fontweight="medium", rotation=15 if len(categories) > 5 else 0)
    ax.set_ylabel("Giá trị", fontsize=9.5, fontweight="bold", color="#334155")
    ax.set_title(title or "Biểu đồ Thống kê Số liệu", fontsize=11.5, fontweight="bold", pad=12, color="#0F172A")
    ax.grid(axis="y", linestyle="--", alpha=0.5, zorder=0)
    plt.tight_layout()
    return fig


def generate_chart_for_table(
    headers: List[str],
    rows: List[List[str]],
    report_title: str = "",
    output_png_path: Optional[str] = None,
) -> Optional[Tuple[str, str]]:
    """Hàm chính tự động nhận diện Intent và vẽ biểu đồ phù hợp 100%.

    Args:
        headers: Danh sách tiêu đề các cột trong bảng.
        rows: Danh sách các hàng dữ liệu.
        report_title: Tiêu đề báo cáo.
        output_png_path: Đường dẫn lưu file PNG (nếu None sẽ tạo file tạm).

    Returns:
        Tuple (file_path_png, base64_data_uri) hoặc None nếu bảng không đủ điều kiện vẽ biểu đồ.
    """
    if not headers or not rows or len(rows) < 1:
        return None

    _configure_chart_style()
    intent = detect_intent_from_table(headers, rows)

    fig = None
    try:
        if intent == AnalyticalIntent.MULTI_ENTITY_COMPARE:
            fig = _render_multi_entity_compare(headers, rows, report_title)
        elif intent == AnalyticalIntent.RANKING_CHANGE:
            fig = _render_ranking_change(headers, rows, report_title)
        elif intent == AnalyticalIntent.TREND_TIME_SERIES:
            fig = _render_trend_time_series(headers, rows, report_title)
        elif intent == AnalyticalIntent.RISK_DISTRIBUTION:
            fig = _render_risk_distribution(headers, rows, report_title)
        elif intent == AnalyticalIntent.GAP_DIAGNOSTIC:
            fig = _render_gap_diagnostic(headers, rows, report_title)
        elif intent == AnalyticalIntent.SINGLE_METRIC_BREAKDOWN:
            fig = _render_single_metric_breakdown(headers, rows, report_title)

        # Fallback nếu renderer đặc thù không tạo được figure
        if fig is None:
            fig = _render_multi_entity_compare(headers, rows, report_title) or _render_single_metric_breakdown(headers, rows, report_title)

        if fig is None:
            return None

        # Lưu ra file PNG
        if not output_png_path:
            import uuid
            os.makedirs("temp", exist_ok=True)
            output_png_path = os.path.join("temp", f"chart_{uuid.uuid4().hex[:8]}.png")

        fig.savefig(output_png_path, dpi=300, bbox_inches="tight", facecolor=fig.get_facecolor(), edgecolor="none")

        # Encode sang base64 data URI phục vụ render HTML xem trước
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=300, bbox_inches="tight", facecolor=fig.get_facecolor(), edgecolor="none")
        buf.seek(0)
        b64_str = base64.b64encode(buf.read()).decode("utf-8")
        data_uri = f"data:image/png;base64,{b64_str}"

        return output_png_path, data_uri

    except Exception as exc:
        print(f"[ChartGenerator] Lỗi khi tạo biểu đồ: {exc}")
        return None
    finally:
        if fig is not None:
            plt.close(fig)
