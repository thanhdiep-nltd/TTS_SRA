# -*- coding: utf-8 -*-
"""
Import giáo án TOÁN 6 từ 2 file docx vào 7 bảng s360.cm_* + public.teaching_schedule.

Idempotent: xóa dữ liệu cũ của subject_id=106 trước khi insert.
Chạy: PYTHONPATH=. python docs_vsf/giao_an_toan_6/import_toan6_lesson_plans.py
"""

import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

_HERE = Path(__file__).resolve().parent
_PROJECT_ROOT = _HERE.parents[1]
sys.path.insert(0, str(_PROJECT_ROOT))

from src.db.session import SessionLocal
from sqlalchemy import text

# ============================================================================
# HẰNG SỐ
# ============================================================================
SUBJECT_ID = 106  # TOAN_6
SO_SCHOOL_ID = 1
COURSE_ID_BASE = 1000  # ID bắt đầu cho cm_course
UNIT_ID_BASE = 2000
LESSON_ID_BASE = 3000
LESSONPLAN_ID_BASE = 5000
TARGET_ID_BASE = 7000

DOCX_EXTRACTED = _HERE / "docx_extracted_v2.json"

# ============================================================================
# MAP TÊN BÀI (docx) → curriculum_units.id (lesson_id)
# Dựa trên kết quả check thực tế DB
# ============================================================================
LESSON_NAME_MAP = {
    # HK1 - Chương 1: SỐ TỰ NHIÊN
    "TẬP HỢP. PHẦN TỬ CỦA TẬP HỢP": 392,
    "TẬP HỢP SỐ TỰ NHIÊN. GHI SỐ TỰ NHIÊN": 393,
    "CÁC PHÉP TÍNH TRONG TẬP HỢP SỐ TỰ NHIÊN": 394,
    "LŨY THỪA VỚI SỐ MŨ TỰ NHIÊN": 395,
    "THỨ TỰ THỰC HIỆN CÁC PHÉP TÍNH": 396,
    "CHIA HẾT VÀ CHIA CÓ DƯ. TÍNH CHẤT CHIA HẾT CỦA MỘT TỔNG": 397,
    "DẤU HIỆU CHIA HẾT CHO 2, CHO 5": 398,
    "DẤU HIỆU CHIA HẾT CHO 3, CHO 9": 399,
    "ƯỚC VÀ BỘI": 400,
    "SỐ NGUYÊN TỐ. HỢP SỐ. PHÂN TÍCH MỘT SỐ RA THỪA SỐ NGUYÊN TỐ": 401,
    "HOẠT ĐỘNG THỰC HÀNH VÀ TRẢI NGHIỆM": 402,  # fallback — có nhiều bài TH
    "HOẠT ĐỘNG THỰC HÀNH VÀ TRẢI NGHIỆM:": 402,
    "ƯỚC CHUNG, ƯỚC CHUNG LỚN NHẤT": 403,
    "BỘI CHUNG, BỘI CHUNG NHỎ NHẤT": 404,
    "BÀI TẬP CUỐI CHƯƠNG 1": 406,
    # HK1 - Chương 2: SỐ NGUYÊN
    "SỐ NGUYÊN ÂM VÀ TẬP HỢP CÁC SỐ NGUYÊN": 408,
    "THỨ TỰ TRONG TẬP HỢP SỐ NGUYÊN": 409,
    "PHÉP CỘNG VÀ PHÉP TRỪ HAI SỐ NGUYÊN": 410,
    "PHÉP NHÂN VÀ PHÉP CHIA HAI SỐ NGUYÊN": 411,
    "VUI HỌC CÙNG SỐ NGUYÊN": 412,
    "BÀI TẬP CUỐI CHƯƠNG 2": 413,
    # HK1 - Chương 3: HÌNH PHẲNG
    "HÌNH VUÔNG - TAM GIÁC ĐỀU -  LỤC GIÁC ĐỀU": 415,
    "HÌNH VUÔNG - TAM GIÁC ĐỀU - LỤC GIÁC ĐỀU": 415,
    "HÌNH CHỮ NHẬT. HÌNH THOI. HÌNH BÌNH HÀNH. HÌNH THANG CÂN": 416,
    "CHU VI VÀ DIỆN TÍCH CỦA MỘT SỐ HÌNH TRONG THỰC TIỄN": 417,
    "TÍNH CHU VI VÀ DIỆN TÍCH CỦA MỘT SỐ HÌNH TRONG THỰC TIỄN": 418,
    "BÀI TẬP CUỐI CHƯƠNG 3": 419,
    # HK1 - Chương 4: THỐNG KÊ
    "THU THẬP VÀ PHÂN LOẠI DỮ LIỆU": 421,
    "BIỂU DIỄN DỮ LIỆU TRÊN BẢNG": 422,
    "BIỂU ĐỒ TRANH": 423,
    "BIỂU ĐỒ CỘT – BIỂU ĐỒ CỘT KÉP": 424,
    "THU THẬP DỮ LIỆU VỀ NHIỆT ĐỘ TRONG TUẦN TẠI ĐỊA PHƯƠNG": 425,
    "BÀI TẬP CUỐI CHƯƠNG 4": 426,
    # HK2 - Chương 5: PHÂN SỐ
    "PHÂN SỐ VỚI TỬ SỐ VÀ MẪU SỐ LÀ SỐ NGUYÊN": None,
    "TÍNH CHẤT CƠ BẢN CỦA PHÂN SỐ": None,
    "SO SÁNH PHÂN SỐ": None,
    "PHÉP CỘNG VÀ PHÉP TRỪ PHÂN SỐ": None,
    "PHÉP NHÂN VÀ PHÉP CHIA PHÂN SỐ": None,
    "GIÁ TRỊ PHÂN SỐ CỦA MỘT SỐ": None,
    "HỖN SỐ": None,
    "BÀI TẬP CUỐI CHƯƠNG 5": None,
    # HK2 - Chương 6: SỐ THẬP PHÂN
    "SỐ THẬP PHÂN": None,
    "CÁC PHÉP TÍNH VỚI SỐ THẬP PHÂN": None,
    "LÀM TRÒN SỐ THẬP PHÂN VÀ ƯỚC LƯỢNG KẾT QUẢ": None,
    "TỈ SỐ VÀ SỐ PHẦN TRĂM": None,
    "BÀI TOÁN VỀ TỈ SỐ PHẦN TRĂM": None,
    "BÀI TẬP CUỐI CHƯƠNG 6": None,
    # HK2 - Chương 7: TÍNH ĐỐI XỨNG
    "HÌNH CÓ TÂM ĐỐI XỨNG": None,
    "VAI TRÒ CỦ TÍNH ĐỐI XỨNG TRONG THẾ GIỚI TỰ NHIÊN": None,
    "BÀI TẬP CUỐI CHƯƠNG 7": None,
    # HK2 - Chương 8: HÌNH HỌC PHẲNG
    "ĐIỂM. ĐƯỜNG THẲNG": None,
    "BA ĐIỂM THẲNG HÀNG. BA ĐIỂM KHÔNG THẲNG HÀNG": None,
    "HAI ĐƯỜNG THẲNG CẮT NHAU, SONG SONH. TIA": None,
    "ĐOẠN THẲNG. ĐỘ DÀI ĐOẠN THẲNG": None,
    "TRUNG ĐIỂM CỦA ĐOẠN THẲNG": None,
    "GÓC": None,
    "SỐ ĐO GÓC. CÁC GÓC ĐẶC BIỆT": None,
    "BÀI TẬP CUỐI CHƯƠNG 8": None,
    # HK2 - Chương 9: XÁC SUẤT
    "PHÉP THỬ NGHIỆM – SỰ KIỆN": None,
    "XÁC SUẤT THỬ NGHIỆM": None,
    "BÀI TẬP CUỐI CHƯƠNG 9": None,
}

# ============================================================================
# CẤU TRÚC CHƯƠNG (từ phân tích docx)
# Mỗi chương: (tên, order, period, [(lesson_order, lesson_name, period_in_lesson)])
# ============================================================================
HK1_STRUCTURE = {
    "units": [
        {
            "order": 1,
            "name": "SỐ TỰ NHIÊN",
            "code": "TOAN6_HK1_C1",
            "period": 24,
            "lessons": [
                (1, "TẬP HỢP. PHẦN TỬ CỦA TẬP HỢP", 2, "TOAN6_HK1_C1_B1"),
                (2, "TẬP HỢP SỐ TỰ NHIÊN. GHI SỐ TỰ NHIÊN", 1, "TOAN6_HK1_C1_B2"),
                (3, "CÁC PHÉP TÍNH TRONG TẬP HỢP SỐ TỰ NHIÊN", 1, "TOAN6_HK1_C1_B3"),
                (4, "LŨY THỪA VỚI SỐ MŨ TỰ NHIÊN", 1, "TOAN6_HK1_C1_B4"),
                (5, "THỨ TỰ THỰC HIỆN CÁC PHÉP TÍNH", 2, "TOAN6_HK1_C1_B5"),
                (6, "CHIA HẾT VÀ CHIA CÓ DƯ. TÍNH CHẤT CHIA HẾT CỦA MỘT TỔNG", 2, "TOAN6_HK1_C1_B6"),
                (7, "DẤU HIỆU CHIA HẾT CHO 2, CHO 5", 1, "TOAN6_HK1_C1_B7"),
                (8, "DẤU HIỆU CHIA HẾT CHO 3, CHO 9", 1, "TOAN6_HK1_C1_B8"),
                (9, "ƯỚC VÀ BỘI", 2, "TOAN6_HK1_C1_B9"),
                (10, "SỐ NGUYÊN TỐ. HỢP SỐ. PHÂN TÍCH MỘT SỐ RA THỪA SỐ NGUYÊN TỐ", 2, "TOAN6_HK1_C1_B10"),
                (11, "HOẠT ĐỘNG THỰC HÀNH VÀ TRẢI NGHIỆM", 1, "TOAN6_HK1_C1_B11"),
                (12, "ƯỚC CHUNG, ƯỚC CHUNG LỚN NHẤT", 2, "TOAN6_HK1_C1_B12"),
                (13, "BỘI CHUNG, BỘI CHUNG NHỎ NHẤT", 2, "TOAN6_HK1_C1_B13"),
                (14, "HOẠT ĐỘNG THỰC HÀNH VÀ TRẢI NGHIỆM", 1, "TOAN6_HK1_C1_B14"),
                (15, "BÀI TẬP CUỐI CHƯƠNG 1", 3, "TOAN6_HK1_C1_B15"),
            ]
        },
        {
            "order": 2,
            "name": "SỐ NGUYÊN",
            "code": "TOAN6_HK1_C2",
            "period": 21,
            "lessons": [
                (1, "SỐ NGUYÊN ÂM VÀ TẬP HỢP CÁC SỐ NGUYÊN", 3, "TOAN6_HK1_C2_B1"),
                (2, "THỨ TỰ TRONG TẬP HỢP SỐ NGUYÊN", 2, "TOAN6_HK1_C2_B2"),
                (3, "PHÉP CỘNG VÀ PHÉP TRỪ HAI SỐ NGUYÊN", 6, "TOAN6_HK1_C2_B3"),
                (4, "PHÉP NHÂN VÀ PHÉP CHIA HAI SỐ NGUYÊN", 6, "TOAN6_HK1_C2_B4"),
                (5, "HOẠT ĐỘNG THỰC HÀNH VÀ TRẢI NGHIỆM", 1, "TOAN6_HK1_C2_B5"),
                (6, "BÀI TẬP CUỐI CHƯƠNG 2", 3, "TOAN6_HK1_C2_B6"),
            ]
        },
        {
            "order": 3,
            "name": "CÁC HÌNH PHẲNG TRONG THỰC TIỄN",
            "code": "TOAN6_HK1_C3",
            "period": 13,
            "lessons": [
                (1, "HÌNH VUÔNG - TAM GIÁC ĐỀU - LỤC GIÁC ĐỀU", 3, "TOAN6_HK1_C3_B1"),
                (2, "HÌNH CHỮ NHẬT. HÌNH THOI. HÌNH BÌNH HÀNH. HÌNH THANG CÂN", 4, "TOAN6_HK1_C3_B2"),
                (3, "CHU VI VÀ DIỆN TÍCH CỦA MỘT SỐ HÌNH TRONG THỰC TIỄN", 2, "TOAN6_HK1_C3_B3"),
                (4, "HOẠT ĐỘNG THỰC HÀNH VÀ TRẢI NGHIỆM", 1, "TOAN6_HK1_C3_B4"),
                (5, "BÀI TẬP CUỐI CHƯƠNG 3", 3, "TOAN6_HK1_C3_B5"),
            ]
        },
        {
            "order": 4,
            "name": "MỘT SỐ YẾU TỐ THỐNG KÊ",
            "code": "TOAN6_HK1_C4",
            "period": 15,
            "lessons": [
                (1, "THU THẬP VÀ PHÂN LOẠI DỮ LIỆU", 2, "TOAN6_HK1_C4_B1"),
                (2, "BIỂU DIỄN DỮ LIỆU TRÊN BẢNG", 3, "TOAN6_HK1_C4_B2"),
                (3, "BIỂU ĐỒ TRANH", 2, "TOAN6_HK1_C4_B3"),
                (4, "BIỂU ĐỒ CỘT – BIỂU ĐỒ CỘT KÉP", 4, "TOAN6_HK1_C4_B4"),
                (5, "HOẠT ĐỘNG THỰC HÀNH VÀ TRẢI NGHIỆM", 1, "TOAN6_HK1_C4_B5"),
                (6, "BÀI TẬP CUỐI CHƯƠNG 4", 3, "TOAN6_HK1_C4_B6"),
            ]
        },
    ]
}

HK2_STRUCTURE = {
    "units": [
        {
            "order": 5,
            "name": "PHÂN SỐ",
            "code": "TOAN6_HK2_C5",
            "period": 20,
            "lessons": [
                (1, "PHÂN SỐ VỚI TỬ SỐ VÀ MẪU SỐ LÀ SỐ NGUYÊN", 2, "TOAN6_HK2_C5_B1"),
                (2, "TÍNH CHẤT CƠ BẢN CỦA PHÂN SỐ", 2, "TOAN6_HK2_C5_B2"),
                (3, "SO SÁNH PHÂN SỐ", 2, "TOAN6_HK2_C5_B3"),
                (4, "PHÉP CỘNG VÀ PHÉP TRỪ PHÂN SỐ", 2, "TOAN6_HK2_C5_B4"),
                (5, "PHÉP NHÂN VÀ PHÉP CHIA PHÂN SỐ", 2, "TOAN6_HK2_C5_B5"),
                (6, "GIÁ TRỊ PHÂN SỐ CỦA MỘT SỐ", 2, "TOAN6_HK2_C5_B6"),
                (7, "HỖN SỐ", 2, "TOAN6_HK2_C5_B7"),
                (8, "HOẠT ĐỘNG THỰC HÀNH VÀ TRẢI NGHIỆM", 2, "TOAN6_HK2_C5_B8"),
                (9, "BÀI TẬP CUỐI CHƯƠNG 5", 2, "TOAN6_HK2_C5_B9"),
            ]
        },
        {
            "order": 6,
            "name": "SỐ THẬP PHÂN",
            "code": "TOAN6_HK2_C6",
            "period": 16,
            "lessons": [
                (1, "SỐ THẬP PHÂN", 2, "TOAN6_HK2_C6_B1"),
                (2, "CÁC PHÉP TÍNH VỚI SỐ THẬP PHÂN", 3, "TOAN6_HK2_C6_B2"),
                (3, "LÀM TRÒN SỐ THẬP PHÂN VÀ ƯỚC LƯỢNG KẾT QUẢ", 2, "TOAN6_HK2_C6_B3"),
                (4, "TỈ SỐ VÀ SỐ PHẦN TRĂM", 2, "TOAN6_HK2_C6_B4"),
                (5, "BÀI TOÁN VỀ TỈ SỐ PHẦN TRĂM", 2, "TOAN6_HK2_C6_B5"),
                (6, "HOẠT ĐỘNG THỰC HÀNH VÀ TRẢI NGHIỆM", 2, "TOAN6_HK2_C6_B6"),
                (7, "BÀI TẬP CUỐI CHƯƠNG 6", 3, "TOAN6_HK2_C6_B7"),
            ]
        },
        {
            "order": 7,
            "name": "TÍNH ĐỐI XỨNG",
            "code": "TOAN6_HK2_C7",
            "period": 12,
            "lessons": [
                (1, "HÌNH CÓ TÂM ĐỐI XỨNG", 3, "TOAN6_HK2_C7_B2"),
                (2, "VAI TRÒ CỦ TÍNH ĐỐI XỨNG TRONG THẾ GIỚI TỰ NHIÊN", 3, "TOAN6_HK2_C7_B3"),
                (3, "HOẠT ĐỘNG THỰC HÀNH VÀ TRẢI NGHIỆM", 2, "TOAN6_HK2_C7_B4"),
                (4, "BÀI TẬP CUỐI CHƯƠNG 7", 2, "TOAN6_HK2_C7_B5"),
            ]
        },
        {
            "order": 8,
            "name": "HÌNH HỌC PHẲNG",
            "code": "TOAN6_HK2_C8",
            "period": 20,
            "lessons": [
                (1, "ĐIỂM. ĐƯỜNG THẲNG", 2, "TOAN6_HK2_C8_B1"),
                (2, "BA ĐIỂM THẲNG HÀNG. BA ĐIỂM KHÔNG THẲNG HÀNG", 2, "TOAN6_HK2_C8_B2"),
                (3, "HAI ĐƯỜNG THẲNG CẮT NHAU, SONG SONH. TIA", 2, "TOAN6_HK2_C8_B3"),
                (4, "ĐOẠN THẲNG. ĐỘ DÀI ĐOẠN THẲNG", 3, "TOAN6_HK2_C8_B4"),
                (5, "TRUNG ĐIỂM CỦA ĐOẠN THẲNG", 2, "TOAN6_HK2_C8_B5"),
                (6, "GÓC", 3, "TOAN6_HK2_C8_B6"),
                (7, "SỐ ĐO GÓC. CÁC GÓC ĐẶC BIỆT", 2, "TOAN6_HK2_C8_B7"),
                (8, "HOẠT ĐỘNG THỰC HÀNH VÀ TRẢI NGHIỆM", 2, "TOAN6_HK2_C8_B8"),
                (9, "BÀI TẬP CUỐI CHƯƠNG 8", 2, "TOAN6_HK2_C8_B9"),
            ]
        },
        {
            "order": 9,
            "name": "XÁC SUẤT",
            "code": "TOAN6_HK2_C9",
            "period": 10,
            "lessons": [
                (1, "PHÉP THỬ NGHIỆM – SỰ KIỆN", 3, "TOAN6_HK2_C9_B1"),
                (2, "XÁC SUẤT THỬ NGHIỆM", 3, "TOAN6_HK2_C9_B2"),
                (3, "HOẠT ĐỘNG THỰC HÀNH VÀ TRẢI NGHIỆM", 2, "TOAN6_HK2_C9_B3"),
                (4, "BÀI TẬP CUỐI CHƯƠNG 9", 2, "TOAN6_HK2_C9_B4"),
            ]
        },
    ]
}


def _lookup_lesson_id(lesson_name: str) -> int | None:
    """Tra curriculum_units.id từ tên bài (dùng LESSON_NAME_MAP)."""
    clean = lesson_name.strip().rstrip(".")
    # Exact match
    if clean in LESSON_NAME_MAP:
        return LESSON_NAME_MAP[clean]
    # Try without leading "BÀI X: "
    import re
    m = re.match(r"BÀI\s+[\dIVXLCDM]+\s*[:\-–]\s*(.+)", clean)
    if m:
        key = m.group(1).strip()
        if key in LESSON_NAME_MAP:
            return LESSON_NAME_MAP[key]
    # "TIẾT X - BÀI Y. NAME" pattern
    m = re.match(r"TIẾT\s+[\d+]+\s*[-–]\s*BÀI\s+[\dIVXLCDM]+\s*[.\-]\s*(.+)", clean)
    if m:
        key = m.group(1).strip()
        if key in LESSON_NAME_MAP:
            return LESSON_NAME_MAP[key]
    # Try "TIẾT X - NAME"
    m = re.match(r"TIẾT\s+[\d+]+\s*[-–]\s*(.+)", clean)
    if m:
        key = m.group(1).strip()
        if key in LESSON_NAME_MAP:
            return LESSON_NAME_MAP[key]
    return None


def _get_content_for_lesson(raw_lessons: list[dict], title: str) -> str:
    """Tìm nội dung từ extracted JSON theo title — chuẩn hóa khoảng trắng, match linh hoạt."""
    import re as _re
    title_clean = _re.sub(r'\s+', ' ', title.strip().rstrip("."))
    for ls in raw_lessons:
        t = _re.sub(r'\s+', ' ', ls["title"].strip())
        # Match theo substring (chuẩn hóa space)
        if title_clean.lower() in t.lower() or t.lower() in title_clean.lower():
            return ls.get("content", "")
        # Match 30 ký tự đầu
        if len(title_clean) > 20 and title_clean[:20].lower() in t.lower():
            return ls.get("content", "")
    return ""


def _extract_targets_from_content(content: str) -> list[str]:
    """Trích mục tiêu kiến thức từ nội dung giáo án."""
    import re
    targets = []
    in_target = False

    lines = []
    for line in content.split("\n"):
        line = re.sub(r'^\[.*?\]\s*', '', line.strip())
        lines.append(line)

    for line in lines:
        # Phát hiện phần MỤC TIÊU
        if "MỤC TIÊU" in line:
            in_target = True
            continue
        # Kết thúc
        if in_target and ("THIẾT BỊ" in line or "TIẾN TRÌNH" in line or line.startswith("II.")):
            in_target = False
            continue
        if not in_target:
            continue

        line = line.strip()
        if not line or len(line) < 8:
            continue
        # Bỏ dòng tiêu đề phụ
        if re.match(r'^[\d.]+\s*(Kiến thức|Năng lực|Phẩm chất)', line):
            continue
        if re.match(r'^[a-d][).]\s*', line):
            continue

        # Lấy dòng mục tiêu: bắt đầu bằng - hoặc + hoặc cụm "Biết...", "Nhận...", "Phát...", "Hiểu...", "Sử dụng...", "Vận dụng..."
        if line.startswith("- ") or line.startswith("+ "):
            t = line.lstrip("-+ ").strip()
            if len(t) > 10:
                targets.append(t[:200])
        elif any(line.startswith(x) for x in ["Biết ", "Nhận ", "Phát ", "Hiểu ", "Sử dụng ", "Vận dụng ", "Thực hiện "]):
            targets.append(line[:200])

    if not targets:
        targets.append("Nắm được kiến thức cơ bản của bài học")
    return targets[:4]


def main():
    print("=" * 60)
    print("IMPORT GIÁO ÁN TOÁN 6 (CTST) VÀO 7 BẢNG cm_*")
    print("=" * 60)

    # Đọc dữ liệu extract từ docx
    if not DOCX_EXTRACTED.exists():
        print(f"[ERROR] Không tìm thấy file {DOCX_EXTRACTED}")
        print("Chạy python docs_vsf/giao_an_toan_6/extract_docx_v2.py trước để extract dữ liệu từ docx.")
        sys.exit(1)

    with open(DOCX_EXTRACTED, encoding="utf-8") as f:
        extracted = json.load(f)

    raw_hk1 = extracted["HK1"]["lessons"]
    raw_hk2 = extracted["HK2"]["lessons"]
    print(f"  HK1: {len(raw_hk1)} bài, HK2: {len(raw_hk2)} bài")

    # Kết nối DB
    db = SessionLocal()
    try:
        # === XÓA DỮ LIỆO CŨ ===
        print("\n[1] Xóa dữ liệu cũ subject_id=106...")
        db.execute(text("DELETE FROM s360.cm_courseassessmentunit WHERE course_assessment_id IN (SELECT id FROM s360.cm_courseassessment WHERE course_id IN (SELECT id FROM s360.cm_course WHERE subject_id=106))"))
        db.execute(text("DELETE FROM s360.cm_courseassessment WHERE course_id IN (SELECT id FROM s360.cm_course WHERE subject_id=106)"))
        db.execute(text("DELETE FROM s360.cm_lessontarget WHERE lesson_id IN (SELECT id FROM s360.cm_lesson WHERE unit_id IN (SELECT id FROM s360.cm_unit WHERE course_id IN (SELECT id FROM s360.cm_course WHERE subject_id=106)))"))
        db.execute(text("DELETE FROM s360.cm_lessonplan WHERE lesson_id IN (SELECT id FROM s360.cm_lesson WHERE unit_id IN (SELECT id FROM s360.cm_unit WHERE course_id IN (SELECT id FROM s360.cm_course WHERE subject_id=106)))"))
        db.execute(text("DELETE FROM s360.cm_lesson WHERE unit_id IN (SELECT id FROM s360.cm_unit WHERE course_id IN (SELECT id FROM s360.cm_course WHERE subject_id=106))"))
        db.execute(text("DELETE FROM s360.cm_unit WHERE course_id IN (SELECT id FROM s360.cm_course WHERE subject_id=106)"))
        db.execute(text("DELETE FROM s360.cm_course WHERE subject_id=106"))
        db.commit()
        print("  OK")

        # === INSERT CM_COURSE ===
        print("\n[2] Insert cm_course...")
        courses = [
            (COURSE_ID_BASE, SO_SCHOOL_ID, SUBJECT_ID, 6, 73,
             "TOAN6_HK1", "Toán 6 - Học kỳ 1 (CTST)",
             "Chương trình Toán 6 Học kỳ 1 theo sách Chân Trời Sáng Tạo. Gồm 4 chương: Số tự nhiên, Số nguyên, Hình phẳng, Thống kê.",
             1, False, 1),
            (COURSE_ID_BASE + 1, SO_SCHOOL_ID, SUBJECT_ID, 6, 105,
             "TOAN6_HK2", "Toán 6 - Học kỳ 2 (CTST)",
             "Chương trình Toán 6 Học kỳ 2 theo sách Chân Trời Sáng Tạo. Gồm 5 chương: Phân số, Số thập phân, Tính đối xứng, Hình học phẳng, Xác suất.",
             2, False, 1),
        ]
        for cid, sid, subj_id, grade, period, code, name, desc, order_n, is_sub, status in courses:
            db.execute(
                text("""
                    INSERT INTO s360.cm_course (id, content1, subject_id, grade_id, period, is_subcourse, subcode, subname, main_course_id, code, name, description, order_number, status, created_by_id, created_at, is_deleted)
                    VALUES (:id, '', :subject_id, :grade_id, :period, :is_subcourse, NULL, NULL, NULL, :code, :name, :description, :order_number, :status, 'import', NOW(), FALSE)
                    ON CONFLICT (id) DO UPDATE SET code=:code, name=:name, description=:description, period=:period
                """),
                {"id": cid, "subject_id": subj_id, "grade_id": grade, "period": period,
                 "is_subcourse": is_sub, "code": code, "name": name, "description": desc,
                 "order_number": order_n, "status": status}
            )
        print(f"  Inserted {len(courses)} courses")

        # === INSERT CM_UNIT + CM_LESSON + CM_LESSONPLAN + CM_LESSONTARGET ===
        uid_counter = UNIT_ID_BASE
        lid_counter = LESSON_ID_BASE
        lpid_counter = LESSONPLAN_ID_BASE
        tid_counter = TARGET_ID_BASE

        structure_semesters = [
            (COURSE_ID_BASE, 1, HK1_STRUCTURE, raw_hk1, "HK1"),
            (COURSE_ID_BASE + 1, 2, HK2_STRUCTURE, raw_hk2, "HK2"),
        ]

        total_units = 0
        total_lessons = 0
        total_plans = 0
        total_targets = 0

        for course_id, semester, structure, raw_lessons, sem_label in structure_semesters:
            for unit in structure["units"]:
                # Insert cm_unit
                uid_counter += 1
                total_units += 1
                db.execute(
                    text("""
                        INSERT INTO s360.cm_unit (id, content1, course_id, code, name, description, order_number, period, status, created_by_id, created_at, is_deleted)
                        VALUES (:id, '', :course_id, :code, :name, :description, :order_number, :period, 1, 'import', NOW(), FALSE)
                        ON CONFLICT (id) DO UPDATE SET name=:name, description=:description, period=:period
                    """),
                    {"id": uid_counter, "course_id": course_id, "code": unit["code"],
                     "name": unit["name"],
                     "description": f"Chương {unit['order']}: {unit['name']}. {unit['period']} tiết.",
                     "order_number": unit["order"], "period": unit["period"]}
                )

                for lo, lesson_name, lesson_period, lesson_code in unit["lessons"]:
                    lid_counter += 1
                    lpid_counter += 1
                    total_lessons += 1
                    total_plans += 1

                    # Tìm nội dung từ extracted JSON
                    raw_content = _get_content_for_lesson(raw_lessons, lesson_name)

                    # Trích mục tiêu
                    target_texts = _extract_targets_from_content(raw_content)

                    # Xây description từ mục tiêu
                    lesson_desc = "; ".join(target_texts[:3]) if target_texts else lesson_name

                    # Insert cm_lesson
                    db.execute(
                        text("""
                            INSERT INTO s360.cm_lesson (id, unit_id, code, name, description, order_number, period, status, created_by_id, created_at, is_deleted)
                            VALUES (:id, :unit_id, :code, :name, :description, :order_number, :period, 1, 'import', NOW(), FALSE)
                            ON CONFLICT (id) DO UPDATE SET name=:name, description=:description, period=:period
                        """),
                        {"id": lid_counter, "unit_id": uid_counter, "code": lesson_code,
                         "name": lesson_name, "description": lesson_desc,
                         "order_number": lo, "period": lesson_period}
                    )

                    # Insert cm_lessonplan
                    plan_name = f"Giáo án {lesson_name}"
                    db.execute(
                        text("""
                            INSERT INTO s360.cm_lessonplan (id, lesson_id, school_id, school_year_id, code, name, description, order_number, status, created_by_id, created_at, content_own, period, period_lesson, is_deleted)
                            VALUES (:id, :lesson_id, :school_id, '2025', :code, :name, :description, :order_number, 1, 'import', NOW(), :content_own, :period, :period, FALSE)
                            ON CONFLICT (id) DO UPDATE SET content_own=:content_own, name=:name
                        """),
                        {"id": lpid_counter, "lesson_id": lid_counter, "school_id": SO_SCHOOL_ID,
                         "code": f"{lesson_code}_LP", "name": plan_name,
                         "description": f"Giáo án {lesson_name}",
                         "order_number": lo, "content_own": raw_content or "",
                         "period": lesson_period}
                    )

                    # Insert targets
                    for ti, t_text in enumerate(target_texts):
                        tid_counter += 1
                        total_targets += 1
                        t_code = f"TGT_{lesson_code}_{ti+1:02d}"
                        db.execute(
                            text("""
                                INSERT INTO s360.cm_lessontarget (id, lesson_id, code, name, description, order_number, status, created_by_id, created_at, is_deleted)
                                VALUES (:id, :lesson_id, :code, :name, :description, :order_number, 1, 'import', NOW(), FALSE)
                                ON CONFLICT (id) DO UPDATE SET name=:name, description=:description
                            """),
                            {"id": tid_counter, "lesson_id": lid_counter, "code": t_code,
                             "name": t_text[:100], "description": t_text,
                             "order_number": ti + 1}
                        )

            print(f"  {sem_label}: {len(structure['units'])} units, "
                  f"sum {sum(u['period'] for u in structure['units'])} tiết")

        db.commit()
        print(f"\n[SUCCESS] Đã import:")
        print(f"  - {total_units} units (chương)")
        print(f"  - {total_lessons} lessons (bài học)")
        print(f"  - {total_plans} lessonplans (giáo án)")
        print(f"  - {total_targets} targets (mục tiêu)")

    except Exception as e:
        db.rollback()
        print(f"\n[ERROR] {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()