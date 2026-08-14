"""Visual Contracts and Visualization Taxonomy for Report Agent.

Cung cấp bộ quy chuẩn thống nhất (Visual Contracts) cho từng ý đồ phân tích (Analytical Intent)
trong báo cáo tùy chỉnh (Custom / Ad-hoc Reports). Đảm bảo mọi bảng biểu, số liệu và biểu đồ
đều có cấu trúc cố định, chuẩn mực sư phạm và tính nhất quán 100%.
"""

from dataclasses import dataclass
from enum import Enum
import re
from typing import Dict, List, Optional


class AnalyticalIntent(str, Enum):
    """Danh mục các ý đồ phân tích tiêu chuẩn trong giáo dục."""
    MULTI_ENTITY_COMPARE = "multi_entity_compare"
    RANKING_CHANGE = "ranking_change"
    TREND_TIME_SERIES = "trend_time_series"
    RISK_DISTRIBUTION = "risk_distribution"
    AT_RISK_STUDENT_LIST = "at_risk_student_list"
    GAP_DIAGNOSTIC = "gap_diagnostic"
    SINGLE_METRIC_BREAKDOWN = "single_metric_breakdown"


class ColumnAlignment(str, Enum):
    """Căn lề cột trong bảng."""
    LEFT = "left"
    CENTER = "center"
    RIGHT = "right"


@dataclass
class ColumnSpec:
    """Đặc tả cho một cột trong bảng."""
    name: str
    alignment: ColumnAlignment = ColumnAlignment.LEFT
    is_numeric: bool = False
    is_delta: bool = False
    is_code_or_rank: bool = False
    description: str = ""


@dataclass
class VisualContractSpec:
    """Khế ước trực quan hóa cho một ý đồ phân tích cụ thể."""
    intent: AnalyticalIntent
    title: str
    description: str
    required_columns: List[str]
    column_specs: List[ColumnSpec]
    recommended_chart: str
    forbidden_charts: List[str]
    rules: List[str]
    sample_markdown: str


# ============================================================================
# 7 VISUAL CONTRACTS CHUẨN CHO NGÀNH GIÁO DỤC
# ============================================================================
EDUCATIONAL_VISUAL_CONTRACTS: Dict[AnalyticalIntent, VisualContractSpec] = {
    AnalyticalIntent.MULTI_ENTITY_COMPARE: VisualContractSpec(
        intent=AnalyticalIntent.MULTI_ENTITY_COMPARE,
        title="So sánh Đa Thực thể (Lớp / Khối / Môn) tại cùng 1 mốc thời gian",
        description="Dùng khi so sánh ĐTB các môn giữa 2 hoặc nhiều lớp/khối trong cùng 1 học kỳ.",
        required_columns=["Môn học", "Lớp A", "Lớp B", "Chênh lệch (Δ)", "Đánh giá"],
        column_specs=[
            ColumnSpec(name="Môn học", alignment=ColumnAlignment.LEFT, description="Tên môn học"),
            ColumnSpec(name="Lớp A", alignment=ColumnAlignment.RIGHT, is_numeric=True, description="Điểm ĐTB lớp 1"),
            ColumnSpec(name="Lớp B", alignment=ColumnAlignment.RIGHT, is_numeric=True, description="Điểm ĐTB lớp 2"),
            ColumnSpec(name="Chênh lệch (Δ)", alignment=ColumnAlignment.RIGHT, is_numeric=True, is_delta=True, description="Hiệu số (Lớp B - Lớp A) có dấu +/-"),
            ColumnSpec(name="Đánh giá", alignment=ColumnAlignment.LEFT, description="Nhận xét tóm tắt xu thế so sánh"),
        ],
        recommended_chart="Grouped Bar Chart (Cột nhóm đôi)",
        forbidden_charts=["Pie Chart", "Single Line Chart"],
        rules=[
            "Cột 1 luôn là danh mục tiêu chí/môn học (căn trái).",
            "Các cột điểm số của từng lớp phải đặt liền kề nhau và căn phải, làm tròn 2 chữ số thập phân.",
            "Cột Chênh lệch (Δ) bắt buộc có dấu tiền tố '+' hoặc '-' rõ ràng.",
            "Cột Đánh giá đưa ra nhận định ngắn gọn (ví dụ: 'Lớp 6A2 cao hơn', 'Tương đương').",
        ],
        sample_markdown="""| Môn học | Lớp 6A1 (ĐTB) | Lớp 6A2 (ĐTB) | Chênh lệch (Δ) | Đánh giá |
| :--- | :---: | :---: | :---: | :--- |
| **Toán 6** | 4.73 | 5.25 | +0.52 | Lớp 6A2 cao hơn |
| **Ngữ văn** | 3.83 | 4.06 | +0.23 | Tương đương |
| **Tiếng Anh** | 3.84 | 4.22 | +0.38 | Lớp 6A2 cao hơn |
| **Vật lý** | 4.40 | 5.62 | +1.22 | Lớp 6A2 vượt trội |""",
    ),

    AnalyticalIntent.RANKING_CHANGE: VisualContractSpec(
        intent=AnalyticalIntent.RANKING_CHANGE,
        title="Biến động Thứ hạng Qua các Kỳ học (>= 2 mốc)",
        description="Dùng khi theo dõi thứ hạng của các lớp hoặc học sinh qua các kỳ/năm học.",
        required_columns=["Thực thể", "Kỳ 1 (Điểm - Hạng)", "Kỳ 2 (Điểm - Hạng)", "Thay đổi Hạng"],
        column_specs=[
            ColumnSpec(name="Thực thể", alignment=ColumnAlignment.LEFT, description="Tên lớp hoặc học sinh"),
            ColumnSpec(name="Kỳ 1", alignment=ColumnAlignment.CENTER, description="Điểm kèm hạng kỳ trước"),
            ColumnSpec(name="Kỳ 2", alignment=ColumnAlignment.CENTER, description="Điểm kèm hạng kỳ sau"),
            ColumnSpec(name="Thay đổi Hạng", alignment=ColumnAlignment.CENTER, is_delta=True, description="Số bậc tăng/giảm hạng (▲/▼/-)"),
        ],
        recommended_chart="Heatmap Matrix (Ma trận nhiệt) hoặc Bump Chart",
        forbidden_charts=["Pie Chart", "Line Chart > 8 nét"],
        rules=[
            "Bảng dạng Ma trận (Matrix): Hàng là Thực thể, Cột là các mốc thời gian liên tiếp.",
            "Giá trị ô ghi rõ 'Điểm số (Hạng X)'.",
            "Cột Thay đổi Hạng ghi rõ số bậc thăng/giảm (ví dụ: '▲ Tăng 2 bậc', '▼ Giảm 1 bậc', '▬ Giữ nguyên').",
            "TUYỆT ĐỐI KHÔNG gộp các thực thể vào nhóm 'Khác' làm mất tính xếp hạng.",
        ],
        sample_markdown="""| Lớp / Học sinh | HK1 (Điểm - Hạng) | HK2 (Điểm - Hạng) | Thay đổi Hạng |
| :--- | :---: | :---: | :---: |
| **Lớp 6A1** | 6.85 (Hạng 2) | 7.12 (Hạng 1) | ▲ Tăng 1 bậc |
| **Lớp 6A2** | 7.05 (Hạng 1) | 6.78 (Hạng 3) | ▼ Giảm 2 bậc |
| **Lớp 6A3** | 6.40 (Hạng 3) | 6.90 (Hạng 2) | ▲ Tăng 1 bậc |""",
    ),

    AnalyticalIntent.TREND_TIME_SERIES: VisualContractSpec(
        intent=AnalyticalIntent.TREND_TIME_SERIES,
        title="Diễn biến Xu hướng Theo Chuỗi Thời gian (>= 3 mốc)",
        description="Dùng khi theo dõi sự thay đổi của điểm số/chỉ số qua >= 3 mốc thời gian (Tuần 1, 2, 3... hoặc các Đợt thi).",
        required_columns=["Chỉ số / Môn", "Mốc 1", "Mốc 2", "Mốc 3", "Xu hướng Tổng quan"],
        column_specs=[
            ColumnSpec(name="Chỉ số / Môn", alignment=ColumnAlignment.LEFT),
            ColumnSpec(name="Mốc thời gian", alignment=ColumnAlignment.RIGHT, is_numeric=True),
            ColumnSpec(name="Xu hướng Tổng quan", alignment=ColumnAlignment.CENTER),
        ],
        recommended_chart="Line Chart / Multi-line Chart (Tối đa 5 đường)",
        forbidden_charts=["Stacked Bar Chart (che khuất xu hướng riêng)", "Pie Chart"],
        rules=[
            "Cần tối thiểu 3 mốc thời gian mới được gọi là chuỗi xu hướng.",
            "Các mốc thời gian phải được sắp xếp tuần tự từ trái sang phải theo thứ tự thời gian tăng dần.",
            "Cột Xu hướng Tổng quan ghi nhận định: 'Tăng trưởng ổn định', 'Suy giảm', 'Biến động mạnh'.",
        ],
        sample_markdown="""| Môn học | Tuần 2 (TX1) | Tuần 5 (Giữa kỳ) | Tuần 8 (TX2) | Tuần 12 (Cuối kỳ) | Xu hướng Tổng quan |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Toán** | 6.50 | 5.80 | 5.20 | 4.60 | ▼ Suy giảm liên tục |
| **Ngữ văn** | 6.20 | 6.30 | 6.50 | 6.80 | ▲ Tăng trưởng đều |
| **Tiếng Anh** | 7.00 | 7.10 | 6.90 | 7.05 | ▬ Ổn định |""",
    ),

    AnalyticalIntent.RISK_DISTRIBUTION: VisualContractSpec(
        intent=AnalyticalIntent.RISK_DISTRIBUTION,
        title="Phân tầng Rủi ro và Phổ điểm Học sinh (Risk Stratification)",
        description="Dùng khi thống kê phân bổ học sinh theo các mức độ cảnh báo sớm EWS hoặc phân loại học lực.",
        required_columns=["Phân tầng Rủi ro", "Tiêu chí Điểm / EWS", "Số lượng (HS)", "Tỷ lệ (%)", "Mức độ Ưu tiên Can thiệp"],
        column_specs=[
            ColumnSpec(name="Phân tầng Rủi ro", alignment=ColumnAlignment.LEFT),
            ColumnSpec(name="Tiêu chí", alignment=ColumnAlignment.LEFT),
            ColumnSpec(name="Số lượng (HS)", alignment=ColumnAlignment.RIGHT, is_numeric=True),
            ColumnSpec(name="Tỷ lệ (%)", alignment=ColumnAlignment.RIGHT, is_numeric=True),
            ColumnSpec(name="Mức độ Ưu tiên", alignment=ColumnAlignment.CENTER),
        ],
        recommended_chart="Stacked Bar Chart / Donut Chart",
        forbidden_charts=["Line Chart"],
        rules=[
            "Bắt buộc chia thành 4 tầng rủi ro chuẩn: SAFE (An toàn), MODERATE (Cảnh báo nhẹ), HIGH (Rủi ro cao), CRITICAL (Khủng hoảng).",
            "Cột Số lượng và Tỷ lệ % phải có dòng TỔNG CỘNG ở cuối (tổng tỷ lệ = 100%).",
            "Cột Mức độ Ưu tiên nêu rõ: 'Theo dõi thường quy', 'Nhắc nhở GVBM', 'Lập kế hoạch IEP', 'Can thiệp khẩn cấp BGH'.",
        ],
        sample_markdown="""| Phân tầng Rủi ro | Tiêu chí Điểm số / Chuyên cần | Số lượng (HS) | Tỷ lệ (%) | Mức độ Ưu tiên Can thiệp |
| :--- | :--- | :---: | :---: | :---: |
| **CRITICAL (Khủng hoảng)** | ĐTB < 3.5 hoặc Vắng > 20% | 3 | 8.6% | Khẩn cấp (Lập IEP & BGH) |
| **HIGH (Rủi ro cao)** | ĐTB 3.5 - 4.9 hoặc sụt giảm mạnh | 5 | 14.3% | Cao (GVCN & GVBM phụ đạo) |
| **MODERATE (Cảnh báo nhẹ)** | ĐTB 5.0 - 6.4 hoặc nộp LMS chậm | 8 | 22.8% | Trung bình (Theo dõi tuần) |
| **SAFE (An toàn)** | ĐTB >= 6.5, chuyên cần tốt | 19 | 54.3% | Thường quy |
| **TỔNG CỘNG** | **Toàn bộ học sinh trong phạm vi** | **35** | **100.0%** | — |""",
    ),

    AnalyticalIntent.AT_RISK_STUDENT_LIST: VisualContractSpec(
        intent=AnalyticalIntent.AT_RISK_STUDENT_LIST,
        title="Danh sách Học sinh Cần Hỗ trợ Sư phạm / Can thiệp Sớm",
        description="Dùng khi xuất danh sách cụ thể từng học sinh gặp rủi ro học thuật, chuyên cần hoặc tâm lý.",
        required_columns=["STT", "Mã HS", "Họ và tên", "Lớp", "Điểm ĐTB", "Số buổi vắng", "Nguyên nhân Rủi ro", "Hành động Can thiệp"],
        column_specs=[
            ColumnSpec(name="STT", alignment=ColumnAlignment.CENTER, is_numeric=True),
            ColumnSpec(name="Mã HS", alignment=ColumnAlignment.CENTER, is_code_or_rank=True),
            ColumnSpec(name="Họ và tên", alignment=ColumnAlignment.LEFT),
            ColumnSpec(name="Lớp", alignment=ColumnAlignment.CENTER),
            ColumnSpec(name="Điểm ĐTB", alignment=ColumnAlignment.RIGHT, is_numeric=True),
            ColumnSpec(name="Số buổi vắng", alignment=ColumnAlignment.RIGHT, is_numeric=True),
            ColumnSpec(name="Nguyên nhân Rủi ro", alignment=ColumnAlignment.LEFT),
            ColumnSpec(name="Hành động Can thiệp", alignment=ColumnAlignment.LEFT),
        ],
        recommended_chart="Bảng chi tiết (Data Table)",
        forbidden_charts=["Pie Chart", "Line Chart"],
        rules=[
            "STT và Mã HS căn giữa; Họ tên căn trái; Điểm số và Số buổi vắng căn phải.",
            "Phải nêu rõ nguyên nhân cốt lõi (LMS không nộp, vắng không phép, sụt giảm điểm thi, biến cố gia đình).",
            "Mỗi học sinh phải có phương án xử lý sư phạm cụ thể, khả thi.",
        ],
        sample_markdown="""| STT | Mã HS | Họ và tên | Lớp | Điểm ĐTB | Số buổi vắng | Nguyên nhân Rủi ro | Hành động Can thiệp |
| :---: | :---: | :--- | :---: | :---: | :---: | :--- | :--- |
| 1 | HS0012 | Nguyễn Văn A | 6A1 | 3.20 | 6 buổi | Sụt giảm điểm Toán, vắng nhiều | Họp phụ huynh, kèm 1-1 môn Toán |
| 2 | HS0045 | Trần Thị B | 6A1 | 4.10 | 1 buổi | Hổng kiến thức Lý & KHTN | Phụ đạo sau giờ học nhóm Tự nhiên |
| 3 | HS0078 | Lê Văn C | 6A2 | 3.80 | 4 buổi | Không nộp bài tập LMS 3 tuần | GVCN đôn đốc nộp bù LMS |""",
    ),

    AnalyticalIntent.GAP_DIAGNOSTIC: VisualContractSpec(
        intent=AnalyticalIntent.GAP_DIAGNOSTIC,
        title="Chẩn đoán Lỗ hổng Kiến thức theo Chủ đề & Mức Bloom",
        description="Dùng khi phân tích các đơn vị kiến thức, bài học hoặc mức nhận thức mà học sinh bị hổng.",
        required_columns=["Chủ đề Kiến thức", "Môn học - Khối", "Mức Bloom", "Tỷ lệ Làm sai (%)", "Mức độ Nghiêm trọng", "Nội dung Cần Ôn tập"],
        column_specs=[
            ColumnSpec(name="Chủ đề Kiến thức", alignment=ColumnAlignment.LEFT),
            ColumnSpec(name="Môn học - Khối", alignment=ColumnAlignment.CENTER),
            ColumnSpec(name="Mức Bloom", alignment=ColumnAlignment.CENTER, is_code_or_rank=True),
            ColumnSpec(name="Tỷ lệ Làm sai (%)", alignment=ColumnAlignment.RIGHT, is_numeric=True),
            ColumnSpec(name="Mức độ Nghiêm trọng", alignment=ColumnAlignment.CENTER),
            ColumnSpec(name="Nội dung Cần Ôn tập", alignment=ColumnAlignment.LEFT),
        ],
        recommended_chart="Radar Chart (Biểu đồ mạng nhện) hoặc Heatmap",
        forbidden_charts=["Pie Chart"],
        rules=[
            "Chủ đề phải gắn liền với chuẩn chương trình hoặc bài học cụ thể.",
            "Mức Bloom ghi rõ số và tên (ví dụ: 'Mức 3 - Vận dụng').",
            "Mức độ Nghiêm trọng phân thành: 'Thấp (< 20%)', 'Trung bình (20-40%)', 'Cao (40-60%)', 'Nghiêm trọng (> 60%)'.",
        ],
        sample_markdown="""| Chủ đề Kiến thức | Môn học - Khối | Mức Bloom | Tỷ lệ Làm sai (%) | Mức độ Nghiêm trọng | Nội dung Cần Ôn tập |
| :--- | :---: | :---: | :---: | :---: | :--- |
| **Phân số & Số thập phân** | Toán 6 | Mức 3 (Vận dụng) | 68.5% | Nghiêm trọng | Ôn tập phép cộng trừ phân số khác mẫu |
| **Chuyển động & Vận tốc** | KHTN 6 | Mức 2 (Hiểu) | 45.2% | Cao | Bài tập quy đổi đơn vị km/h sang m/s |
| **Văn biểu cảm** | Ngữ văn 6 | Mức 4 (Phân tích) | 35.0% | Trung bình | Rèn luyện kỹ năng lập dàn ý bài văn |""",
    ),

    AnalyticalIntent.SINGLE_METRIC_BREAKDOWN: VisualContractSpec(
        intent=AnalyticalIntent.SINGLE_METRIC_BREAKDOWN,
        title="Thống kê Phân rã 1 Chỉ số Học thuật theo Danh mục",
        description="Dùng khi thống kê tỷ lệ đạt/chưa đạt, phân loại hạnh kiểm, hoặc cơ cấu theo danh mục đơn.",
        required_columns=["Danh mục / Phân loại", "Số lượng", "Tỷ lệ (%)", "Ghi chú Đánh giá"],
        column_specs=[
            ColumnSpec(name="Danh mục / Phân loại", alignment=ColumnAlignment.LEFT),
            ColumnSpec(name="Số lượng", alignment=ColumnAlignment.RIGHT, is_numeric=True),
            ColumnSpec(name="Tỷ lệ (%)", alignment=ColumnAlignment.RIGHT, is_numeric=True),
            ColumnSpec(name="Ghi chú Đánh giá", alignment=ColumnAlignment.LEFT),
        ],
        recommended_chart="Bar Chart / Donut Chart",
        forbidden_charts=["Line Chart"],
        rules=[
            "Cột Số lượng và Tỷ lệ % căn phải.",
            "Có dòng Tổng cộng ở cuối, tổng tỷ lệ đúng 100%.",
        ],
        sample_markdown="""| Phân loại Học lực | Số lượng (HS) | Tỷ lệ (%) | Ghi chú Đánh giá |
| :--- | :---: | :---: | :--- |
| **Xuất sắc** | 12 | 15.0% | Tăng 3 học sinh so với đầu năm |
| **Giỏi** | 28 | 35.0% | Đạt chỉ tiêu chuyên môn |
| **Khá** | 30 | 37.5% | Phân bổ tập trung nhất |
| **Trung bình** | 10 | 12.5% | Cần đôn đốc để lên Khá |
| **TỔNG CỘNG** | **80** | **100.0%** | **Toàn bộ khối** |""",
    ),
}


# ============================================================================
# HELPER FUNCTIONS & PROMPT BUILDER
# ============================================================================

def get_visual_contract(intent: str | AnalyticalIntent) -> Optional[VisualContractSpec]:
    """Lấy VisualContractSpec theo intent string hoặc enum."""
    if isinstance(intent, str):
        try:
            intent_enum = AnalyticalIntent(intent.lower().strip())
        except ValueError:
            return None
    else:
        intent_enum = intent
    return EDUCATIONAL_VISUAL_CONTRACTS.get(intent_enum)


def build_taxonomy_prompt_instructions() -> str:
    """Tạo khối văn bản hướng dẫn Visual Contracts để nhúng vào Prompt của Report Agent."""
    instructions = [
        "## QUY TẮC BẮT BUỘC VỀ BẢNG BIỂU & TRỰC QUAN HÓA (VISUALIZATION TAXONOMY)",
        "Khi lập Phần II (DỮ LIỆU & SỐ LIỆU THỰC TẾ) trong báo cáo tùy chỉnh, bạn BẮT BUỘC phải xác định đúng Ý đồ Phân tích (Analytical Intent) và áp dụng ĐÚNG 100% CẤU TRÚC BẢNG tương ứng dưới đây:\n",
    ]

    for idx, (intent, contract) in enumerate(EDUCATIONAL_VISUAL_CONTRACTS.items(), 1):
        instructions.append(f"### {idx}. Intent `{intent.value}`: {contract.title}")
        instructions.append(f"- **Mục đích**: {contract.description}")
        instructions.append(f"- **Biểu đồ khuyến nghị**: {contract.recommended_chart} | **Tránh dùng**: {', '.join(contract.forbidden_charts)}")
        instructions.append(f"- **Các quy tắc chuẩn hóa**:")
        for r in contract.rules:
            instructions.append(f"  * {r}")
        instructions.append(f"- **Mẫu bảng Markdown bắt buộc**:\n{contract.sample_markdown}\n")

    instructions.append(
        "TUYỆT ĐỐI KHÔNG tự ý đảo hàng/cột, không dùng định dạng bảng ngẫu hứng. Mọi báo cáo có cùng ý đồ phân tích PHẢI có cấu trúc bảng giống hệt nhau."
    )
    return "\n".join(instructions)


def detect_cell_alignment(header_name: str, value: str) -> ColumnAlignment:
    """Tự động suy đoán căn lề cho một ô/cột dựa vào tên cột và giá trị."""
    h_lower = header_name.lower().strip()
    val_clean = value.strip()

    # Căn phải cho số, điểm số, phần trăm, chênh lệch (Ưu tiên kiểm tra metric / điểm)
    if any(k in h_lower for k in ["đtb", "gpa", "chênh lệch", "số lượng", "tỷ lệ", "buổi", "%", "(δ)", "delta"]):
        return ColumnAlignment.RIGHT
    if "điểm" in h_lower and "hạng" not in h_lower:
        return ColumnAlignment.RIGHT
    if re.match(r"^[\+\-]?[0-9]+(\.[0-9]+)?%?$", val_clean):
        # Nếu là STT thì căn giữa
        if h_lower == "stt" or h_lower.startswith("stt"):
            return ColumnAlignment.CENTER
        return ColumnAlignment.RIGHT

    # Căn giữa cho STT, Mã, Khối, Lớp (cột danh mục lớp), Hạng, Mức Bloom, Trạng thái ngắn
    if any(k in h_lower for k in ["stt", "mã", "code", "hạng", "bloom", "thay đổi", "thực hiện", "mức độ"]):
        return ColumnAlignment.CENTER
    if h_lower in ["lớp", "khối", "học kỳ", "kỳ"]:
        return ColumnAlignment.CENTER
    if re.match(r"^(hs\d+|stt|\d{1,2}[a-z]\d?|mức \d+|▲|▼|▬)$", val_clean, re.IGNORECASE):
        return ColumnAlignment.CENTER

    # Mặc định căn trái cho văn bản
    return ColumnAlignment.LEFT


def sanitize_delta_value(val: str) -> str:
    """Tự động chuẩn hóa giá trị chênh lệch (Delta): gắn dấu +/- và format thập phân."""
    val_clean = val.strip()
    match = re.match(r"^([\+\-]?)(\d+(\.\d+)?)$", val_clean)
    if match:
        sign, num_str, _ = match.groups()
        try:
            num = float(num_str)
            if sign == "-" or num < 0:
                return f"-{abs(num):.2f}"
            elif num > 0:
                return f"+{num:.2f}"
            else:
                return "0.00"
        except ValueError:
            pass
    return val_clean
