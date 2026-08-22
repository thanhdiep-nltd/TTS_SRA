"""Seed mock Toan 6 (subject 106) — xoa de cu + re-mock day du luong danh gia.

Mock lai TU DAU du lieu mon Toan 6 khoi 6 (so_school_id=1, grade 6) de chay
full luong danh gia lo hong kien thuc (`/knowledge-gaps/students/{code}`):

  GĐ 0. Xóa sạch dữ liệu cũ subject 106 (chỉ môn 106, school 1 cho điểm trên lớp).
  GĐ 1. 6 đề thi khối 6 (GK1 MIDTERM có map unit; CK1 FINAL; TX1–TX4 REGULAR).
  GĐ 2. Re-mock điểm thi trên lớp (`fact_gradebooks`, so_exam_id 1061 TX + 1062 GK).
  GĐ 3. `lms_question_bank`: 34 bài LMS (16 tuần × 2 bài + tuần 8/16 ôn tập thêm 1)
        × 10 câu = 340 câu trắc nghiệm; mỗi câu map tới BÀI con (lms_question_unit,
        unit_id = bài, parent_id = chương) — câu tổng hợp 2 chương góp weight vào 2 bài.
  GĐ 4. `lms_question_response`: item-response hàng tuần cho học sinh khối 6
        (attempt, best-attempt, thời gian làm, cờ integrity, ngày theo tuần).
  GĐ 5. Tính `student_unit_mastery` bằng service thật (finalize_mastery +
        compute_unit_mastery) → upsert (theo BÀI con).
  GĐ 6. In bảng tổng kết để đối chiếu.

QUAN TRỌNG (chống vỡ khi chạy lại `generate_full_system_mock_v4.py`):
- Script v4 LUÔN TRUNCATE + seed lại `dim_homeroom_class_student`,
  `dim_homeroom_class`, `fact_gradebooks`, `public.users` — nhưng KHÔNG đụng
  `exam_papers`, `exam_competencies`, `curriculum_units`, `lms_question_*`,
  `student_unit_mastery`. → Script này phải chạy SAU v4, discover học sinh ĐỘNG
  theo rank (thứ tự student_code), không hardcode mã HS, tự dọn subject-106
  trước mỗi lần seed (idempotent).

GHI CHÚ CALIBRATION: `exam_competencies` dùng bloom_level đồng nhất = 3 cho cả
4 chương. Lý do: fallback/calibration dùng `compute_unit_mastery(total, 10,
units)` — nếu các unit có bloom khác nhau (vd 407 bloom 4, 420 bloom 2) thì
một điểm tổng duy nhất sẽ luôn cho mastery 407 thấp hơn/420 cao hơn → học sinh
giỏi LMS bị gắn cờ SUSPECTED_CHEATING oan ở chương khó/dễ. Bloom đa dạng 1–4
vẫn được giữ ở tầng câu hỏi LMS (`lms_question_bank.bloom_level`), nơi item-level
mastery dùng `_BLOOM_DIFFICULTY` — đúng thiết kế (LMS = chi tiết, đề = tổng).

Chạy:
    python scripts/seed_mock_toan6_gaps.py
"""

from __future__ import annotations

import os
import random
import sys
from datetime import datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv

if sys.platform.startswith("win"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

_ROOT = Path(__file__).resolve().parent.parent
env_path = _ROOT / ".env"
load_dotenv(dotenv_path=env_path)

DB_URL = os.getenv("DATABASE_URL")
if not DB_URL:
    print("[ERROR] DATABASE_URL is not set in .env")
    sys.exit(1)

sys.path.insert(0, str(_ROOT))
import psycopg  # noqa: E402
from psycopg.types.json import Jsonb  # noqa: E402

from src.services.item_mastery import (  # noqa: E402
    ItemResult,
    finalize_mastery,
)
from src.services.knowledge_gap import UnitWeight, compute_unit_mastery  # noqa: E402

# ============================================================================
# HẰNG SỐ MOCK
# ============================================================================
SUBJECT_ID = 106  # TOAN_6 (s360.dim_subject)
SO_SCHOOL_ID = 1
SCHOOL_YEAR_ID = 2025
SEMESTER = 1
MAX_GRADE = 10.0

# 4 chương Toán 6 (curriculum_units — node cha, tồn tại ổn định qua v4)
UNITS = [391, 407, 414, 420]
UNIT_NAMES = {391: "SỐ TỰ NHIÊN", 407: "SỐ NGUYÊN", 414: "HÌNH PHẲNG", 420: "THỐNG KÊ"}

# Map đề GK1 → (unit, weight) — bloom đồng nhất 3 (xem docstring calibration)
EXAM_COMPETENCIES = [(391, 0.40), (407, 0.30), (414, 0.20), (420, 0.10)]

# Lịch LMS HK1: 16 tuần (tuần 1 = 2025-09-01), mỗi tuần 2 bài; tuần 8, 16 có bài ôn tập
WEEK_START = datetime(2025, 9, 1, 8, 0, 0)
N_WEEKS = 16
REVIEW_WEEKS = {8, 16}
ASSIGNMENTS_PER_WEEK = 2  # +1 bài ôn tập ở tuần review
QUESTIONS_PER_ASSIGNMENT = 10

# Tuần trọng tâm chương: 1–4 → 391, 5–8 → 407, 9–12 → 414, 13–16 → 420
WEEK_FOCUS = {w: UNITS[(w - 1) // 4] for w in range(1, N_WEEKS + 1)}

# ============================================================================
# PROFILE HỌC SINH (gán theo rank — thứ tự student_code, không hardcode mã)
# ============================================================================
# p = {unit: xác suất đúng LMS}, gk = điểm Giữa HK1 (so_exam_id 1062).
PROFILES: list[dict] = [
    {"name": "GIOI_DEU", "p": {391: 0.95, 407: 0.93, 414: 0.96, 420: 0.97}, "gk": 9.2},
    {"name": "TE_407", "p": {391: 0.90, 407: 0.08, 414: 0.88, 420: 0.90}, "gk": 6.8},
    {"name": "TE_414", "p": {391: 0.88, 407: 0.85, 414: 0.15, 420: 0.87}, "gk": 6.8},
    {"name": "TE_420", "p": {391: 0.90, 407: 0.87, 414: 0.85, 420: 0.05}, "gk": 7.0},
    {"name": "TE_391", "p": {391: 0.10, 407: 0.88, 414: 0.86, 420: 0.90}, "gk": 6.8},
    {"name": "GIAN_LAN", "p": {391: 0.95, 407: 0.95, 414: 0.95, 420: 0.95}, "gk": 4.2, "cheat": True},
    {"name": "LUOI", "p": {391: 0.40, 407: 0.38, 414: 0.40, 420: 0.42}, "gk": 8.6},
    {"name": "HON_HOP", "p": {391: 1.00, 407: 0.60, 414: 0.50, 420: 1.00}, "gk": 7.1},
    {"name": "TB_KHA_1", "p": {391: 0.82, 407: 0.78, 414: 0.80, 420: 0.85}, "gk": 7.6},
    {"name": "TB_KHA_2", "p": {391: 0.76, 407: 0.80, 414: 0.72, 420: 0.80}, "gk": 7.3},
    {"name": "TB_KHA_3", "p": {391: 0.85, 407: 0.72, 414: 0.74, 420: 0.78}, "gk": 7.5},
    {"name": "TB_KHA_4", "p": {391: 0.72, 407: 0.74, 414: 0.76, 420: 0.70}, "gk": 7.0},
    {"name": "TB_1", "p": {391: 0.68, 407: 0.62, 414: 0.66, 420: 0.70}, "gk": 6.6},
    # rank 13: KHÔNG có item LMS → INSUFFICIENT → API fallback EXAM
    {"name": "NO_LMS", "p": None, "gk": 5.2},
]
AVERAGE_PROFILE = {"name": "TB_TRUNG_BINH", "p": {391: 0.78, 407: 0.74, 414: 0.72, 420: 0.78}, "gk": 7.2}

# Chuyển confidence (chuỗi từ service) → SMALLINT theo DDL student_unit_mastery
CONFIDENCE_INT = {"HIGH": 3, "MEDIUM": 2, "LOW": 1, "INSUFFICIENT": 1}

RNG = random.Random(20250901)

# ============================================================================
# NỘI DUNG MOCK CÂU HỎI (question_text) — mỗi câu KHÁC NHAU (số ngẫu nhiên theo cấp độ)
# ============================================================================
# Mỗi mẫu: (template_text, lesson_id, (min_a, max_a, min_b, max_b)).
# Template chứa placeholder {a}/{b} được điền số ngẫu nhiên trong dải phù hợp
# cấp độ (Bloom) + bài (lesson) — khớp pipeline "Kiểm tra câu hỏi" (AI xác định
# chương + bài trong SGK đã nạp). Dải () = câu định tính, không điền số.
# Bài con Toán 6 (curriculum_units):
#   391 SỐ TỰ NHIÊN: 392 Tập hợp | 393 Ghi số tự nhiên | 394 Phép tính | 395 Lũy thừa
#       396 Thứ tự thực hiện | 398 Dấu hiệu chia hết 2,5 | 399 Dấu hiệu 3,9 | 401 Số nguyên tố
#       403 ƯCLN | 404 BCNN | 406 BTCC
#   407 SỐ NGUYÊN: 408 Số nguyên âm | 409 Thứ tự | 410 Cộng-trừ | 411 Nhân-chia | 412 THTN
#   414 HÌNH PHẲNG: 415 Hình vuông-Tam giác-Lục giác | 416 HCN-Thoi-BH-Thang cân
#       417 Chu vi-Diện tích | 418 THTN
#   420 THỐNG KÊ: 421 Thu thập | 422 Biểu diễn bảng | 423 Biểu đồ tranh | 424 Biểu đồ cột | 425 THTN
# (text, lesson_id, ranges) — ranges = (a_min, a_max, b_min, b_max) hoặc ()
QUESTION_TEMPLATES: dict[int, dict[int, list[tuple[str, int, tuple[int, int, int, int] | tuple[()]]]]] = {
    391: {  # SỐ TỰ NHIÊN
        1: [
            ("Trong các số −{a}, {b}, {c}, số nào là số tự nhiên?", 393, (1, 9, 10, 99, 2, 9)),
            ("Tập hợp các số tự nhiên nhỏ hơn {a} gồm bao nhiêu phần tử?", 392, (2, 15)),
            ("Số tự nhiên liền sau của {a} là bao nhiêu?", 393, (1, 99)),
            ("Số tự nhiên liền trước của {a} là bao nhiêu?", 393, (2, 99)),
            ("Số tự nhiên nhỏ nhất có {a} chữ số là số nào?", 393, (2, 9)),
            ("Số tự nhiên lớn nhất có {a} chữ số là số nào?", 393, (1, 5)),
            ("Tập hợp {a}, {b}, {c} — phần tử nào thuộc tập hợp số tự nhiên?", 392, (1, 9, 10, 99, 2, 9)),
        ],
        2: [
            ("Kết quả của phép tính {a} + {b} bằng bao nhiêu?", 394, (10, 500, 10, 500)),
            ("Giá trị của biểu thức {a} − {b} × 3 là bao nhiêu?", 396, (50, 200, 2, 30)),
            ("Tính: {a} × {b} = ?", 394, (10, 99, 2, 9)),
            ("Giá trị của {a} + {b} : 2 là bao nhiêu?", 396, (10, 100, 10, 90)),
            ("Kết quả của {a} : {b} + 15 là bao nhiêu?", 394, (20, 90, 2, 9)),
            ("Tính nhanh: {a} + {b} + {c} = ?", 394, (10, 200, 10, 200, 10, 200)),
            ("Tính: {a} × 100 + {b} = ?", 394, (1, 9, 10, 99)),
            ("Một lớp có {a} học sinh, chia đều thành {b} nhóm — mỗi nhóm mấy bạn?", 394, (20, 45, 2, 9)),
            ("Kết quả của {a} − {b} + {c} là bao nhiêu?", 396, (50, 200, 10, 90, 1, 50)),
            ("Tính: {a} : {b} × {c} = ?", 394, (24, 96, 2, 8, 2, 9)),
        ],
        3: [
            ("Ước chung lớn nhất của {a} và {b} là bao nhiêu?", 403, (12, 96, 8, 60)),
            ("Trong các số {a}, {b}, {c}, số nào chia hết cho cả 2 và 3?", 399, (10, 90, 10, 90, 10, 90)),
            ("Ước chung của {a} và {b} gồm những số nào?", 403, (12, 48, 18, 60)),
            ("Trong các số {a}, {b}, {c}, số nào vừa chia hết cho 2 vừa chia hết cho 5?", 398, (10, 90, 10, 90, 10, 90)),
            ("Số nào trong các số {a}, {b}, {c} chia hết cho 9?", 399, (10, 90, 10, 90, 10, 90)),
            ("ƯCLN(12, {a}) bằng bao nhiêu?", 403, (18, 96)),
            ("Số {a} chia hết cho những số nào trong các số 2, 3, 5?", 398, (12, 90)),
            ("Tổng {a} + {b} chia hết cho mấy trong các số 2, 3, 5?", 398, (10, 90, 10, 90)),
        ],
        4: [
            ("Phân tích số {a} ra thừa số nguyên tố, kết quả nào đúng?", 401, (30, 120)),
            ("Bội chung nhỏ nhất của {a} và {b} là bao nhiêu?", 404, (4, 24, 6, 30)),
            ("Trong các số {a}, {b}, {c}, số nào là hợp số?", 401, (10, 90, 10, 90, 10, 90)),
            ("Tìm số nguyên tố nhỏ hơn {a}?", 401, (20, 100)),
            ("Số {a} có bao nhiêu ước nguyên tố?", 401, (12, 100)),
            ("BCNN(4, {a}) là bao nhiêu?", 404, (5, 30)),
        ],
        5: [
            ("Chứng minh nào sau đây đúng về tính chia hết của 10^n?", 395, ()),
            ("Nhận định nào đúng khi so sánh {a}^2 và {b}^2?", 395, (2, 9, 3, 9)),
            ("Giá trị của {a}^3 là bao nhiêu?", 395, (2, 9)),
            ("So sánh {a}^2 và {b}^3, khẳng định nào đúng?", 395, (3, 6, 2, 4)),
            ("Tính: {a}^2 × {b} = ?", 395, (2, 9, 2, 9)),
        ],
        6: [
            ("Bài toán nào cần vận dụng kết hợp nhiều quy tắc số tự nhiên để giải?", 406, ()),
            ("Bài toán thực tế nào dùng BCNN để giải quyết?", 406, ()),
            ("Để chia đều {a} viên kẹo cho các nhóm mà không thừa, cần dùng kiến thức gì?", 406, (24, 120)),
        ],
    },
    407: {  # SỐ NGUYÊN
        1: [
            ("Trong các số −{a}, 0, {b}, −{c}, số nguyên âm nào nhỏ hơn −3?", 408, (2, 20, 1, 9, 1, 9)),
            ("Số đối của −{a} là bao nhiêu?", 408, (1, 99)),
            ("Trong các số −{a}, 0, {b}, số nào là số nguyên âm?", 409, (5, 20, 2, 9)),
            ("Số nguyên nào nằm giữa −{a} và 0?", 409, (2, 20)),
            ("−{a} thuộc tập hợp nào sau đây?", 408, (1, 99)),
        ],
        2: [
            ("Kết quả của (−{a}) + (−{b}) bằng bao nhiêu?", 410, (3, 40, 3, 40)),
            ("Giá trị của (−{a}) − (−{b}) là bao nhiêu?", 410, (5, 50, 2, 40)),
            ("Tính: {a} + (−{b}) = ?", 410, (10, 60, 5, 50)),
            ("Tính: (−{a}) + {b} = ?", 410, (10, 60, 5, 50)),
            ("Tính: (−{a}) − {b} = ?", 410, (10, 60, 5, 50)),
            ("Tính: (−{a}) + 0 = ?", 410, (5, 90)),
            ("Tính: {a} − {b} − {c} = ?", 410, (20, 90, 5, 40, 5, 30)),
        ],
        3: [
            ("Tích của (−{a}) × (−{b}) bằng bao nhiêu?", 411, (2, 20, 2, 20)),
            ("Phép chia (−{a}) : {b} có kết quả là bao nhiêu?", 411, (20, 90, 2, 9)),
            ("Tính: (−{a}) × {b} = ?", 411, (2, 20, 2, 20)),
            ("Tính: {a} : (−{b}) = ?", 411, (20, 90, 2, 9)),
            ("Tính: (−{a}) × (−{b}) : {c} = ?", 411, (4, 20, 2, 10, 2, 5)),
            ("Dấu của tích (−{a}) × {b} là gì?", 411, (1, 20, 1, 20)),
        ],
        4: [
            ("Sắp xếp các số −{a}, 0, {b}, −{c} theo thứ tự tăng dần, kết quả nào đúng?", 409, (5, 20, 2, 9, 1, 9)),
            ("So sánh −{a} và −{b}, khẳng định nào đúng?", 409, (5, 30, 3, 20)),
            ("Số nào lớn nhất trong các số −{a}, −{b}, 0, {c}?", 409, (5, 20, 3, 15, 1, 9)),
        ],
        5: [
            ("Tính giá trị biểu thức chứa dấu ngoặc: (−{a} + {b}) × (−{c}) = ?", 411, (5, 40, 2, 30, 2, 9)),
            ("Tính: −[{a} − (−{b})] = ?", 411, (5, 40, 2, 30)),
            ("Biểu thức {a} − (−{b} + {c}) có giá trị bằng bao nhiêu?", 411, (20, 60, 5, 30, 2, 20)),
        ],
        6: [
            ("Bài toán thực tế nào dùng số nguyên để biểu diễn nhiệt độ âm?", 412, ()),
            ("Nhiệt độ buổi sáng là −{a}°C, buổi trưa tăng {b}°C — nhiệt độ trưa là bao nhiêu?", 412, (1, 9, 1, 9)),
            ("Tàu ngầm lặn ở độ sâu −{a} m, dâng lên {b} m — vị trí mới là bao nhiêu?", 412, (20, 90, 5, 40)),
        ],
    },
    414: {  # CÁC HÌNH PHẲNG TRONG THỰC TIỄN
        1: [
            ("Hình nào sau đây là hình tam giác đều?", 415, ()),
            ("Hình có 4 cạnh bằng nhau là hình gì?", 416, ()),
            ("Hình lục giác đều có mấy cạnh?", 415, ()),
            ("Hình bình hành có đặc điểm nào sau đây?", 416, ()),
            ("Hình tam giác đều có mấy góc bằng nhau?", 415, ()),
            ("Hình chữ nhật có mấy trục đối xứng?", 416, ()),
            ("Hình thang cân có mấy trục đối xứng?", 416, ()),
            ("Hình vuông có phải là hình thoi không?", 416, ()),
        ],
        2: [
            ("Chu vi hình vuông cạnh {a} cm bằng bao nhiêu?", 417, (3, 25)),
            ("Diện tích hình chữ nhật {a} cm × {b} cm bằng bao nhiêu?", 417, (3, 20, 4, 25)),
            ("Chu vi hình chữ nhật dài {a} cm, rộng {b} cm là bao nhiêu?", 417, (5, 30, 2, 15)),
            ("Diện tích hình vuông cạnh {a} cm là bao nhiêu?", 417, (3, 25)),
            ("Chu vi hình tam giác đều cạnh {a} cm là bao nhiêu?", 415, (3, 20)),
            ("Cạnh hình vuông có chu vi {a} cm là bao nhiêu?", 417, (8, 40)),
        ],
        3: [
            ("Chu vi hình thoi cạnh {a} cm là bao nhiêu?", 417, (5, 25)),
            ("Diện tích hình thang có tổng hai đáy {a} cm, chiều cao {b} cm là bao nhiêu?", 417, (8, 40, 3, 20)),
            ("Diện tích hình thoi có hai đường chéo {a} cm và {b} cm là bao nhiêu?", 417, (4, 30, 4, 30)),
            ("Chu vi hình bình hành cạnh {a} cm và {b} cm là bao nhiêu?", 416, (4, 20, 3, 15)),
            ("Chu vi hình thang cân có hai cạnh đáy {a} cm, {b} cm và cạnh bên {c} cm?", 416, (5, 20, 4, 15, 2, 10)),
            ("Diện tích tam giác có đáy {a} cm, chiều cao {b} cm là bao nhiêu?", 417, (4, 20, 3, 15)),
            ("Diện tích hình chữ nhật {a} cm × {b} cm, cạnh {a} tăng gấp đôi — diện tích mới?", 417, (3, 15, 4, 20)),
        ],
        4: [
            ("Phân biệt hình nào có trục đối xứng và hình nào không?", 415, ()),
            ("Hình thang cân có đặc điểm nào sau đây?", 416, ()),
            ("Hình nào có nhiều trục đối xứng hơn?", 415, ()),
            ("Hình chữ nhật và hình thoi khác nhau ở điểm nào?", 416, ()),
            ("Lục giác đều được tạo từ mấy tam giác đều?", 415, ()),
            ("Hình bình hành có chu vi {a} cm — nhận định nào đúng về cạnh?", 416, (8, 30)),
            ("Ghép 2 hình tam giác đều được hình gì?", 415, ()),
        ],
        5: [
            ("Ghép các mảnh ghép hình học để tạo thành hình lục giác đều, cách nào đúng?", 415, ()),
            ("Sắp xếp các hình theo thứ tự diện tích tăng dần, thứ tự nào đúng?", 417, ()),
            ("Lập luận nào đúng khi tính diện tích mảnh đất có hình dạng bất kỳ?", 417, ()),
            ("So sánh diện tích hình vuông cạnh {a} cm và hình chữ nhật {a} cm × {b} cm?", 417, (4, 12, 2, 8)),
            ("Cách nào hợp lý để tính diện tích hình H gồm 2 hình chữ nhật?", 417, ()),
        ],
        6: [
            ("Ứng dụng hình học phẳng vào bài toán lát gạch sân trường, cách tính nào hợp lý?", 418, ()),
            ("Thiết kế chuồng nuôi hình chữ nhật có chu vi {a} m để diện tích lớn nhất?", 418, (20, 100)),
            ("Đo đạc mảnh vườn hình thang {a} m, {b} m — cần biết thêm gì để tính diện tích?", 418, (5, 20, 4, 15)),
            ("Thực hành: ước lượng diện tích nền phòng học bằng cách nào?", 418, ()),
        ],
    },
    420: {  # MỘT SỐ YẾU TỐ THỐNG KÊ
        1: [
            ("Trong các dữ liệu sau, dữ liệu nào là dữ liệu định lượng?", 421, ()),
            ("Bảng thống kê gồm những thành phần nào?", 422, ()),
            ("Cách nào dùng để thu thập dữ liệu về sở thích của lớp?", 421, ()),
            ("Dữ liệu nào sau đây là dữ liệu định tính?", 421, ()),
            ("Phân loại dữ liệu: điểm kiểm tra thuộc loại nào?", 421, ()),
            ("Chiều cao của học sinh trong lớp thuộc loại dữ liệu nào?", 421, ()),
            ("Câu hỏi nào phù hợp để thu thập dữ liệu về môn thể thao yêu thích?", 421, ()),
            ("Màu sắc yêu thích của học sinh thuộc loại dữ liệu nào?", 421, ()),
            ("Cân nặng của học sinh thuộc loại dữ liệu nào?", 421, ()),
        ],
        2: [
            ("Cách đọc biểu đồ cột: cột cao nhất biểu thị điều gì?", 424, ()),
            ("Số học sinh thích môn Toán trong biểu đồ là {a} hay {b}?", 424, (10, 30, 5, 25)),
            ("Trong bảng tần số, dòng nào cho biết số lần xuất hiện?", 422, ()),
            ("Biểu đồ tranh dùng hình ảnh gì để biểu diễn dữ liệu?", 423, ()),
            ("Bảng số liệu dùng để làm gì?", 422, ()),
            ("Cột nào trong biểu đồ cột cho biết số lượng nhiều nhất?", 424, ()),
            ("Tên bảng thống kê thường đặt ở đâu?", 422, ()),
            ("Biểu đồ tranh: 1 hình tròn biểu thị {a} bạn — cần mấy hình cho {b} bạn?", 423, (2, 5, 6, 25)),
            ("Trong bảng thống kê, cột đầu tiên thường ghi gì?", 422, ()),
            ("Biểu đồ cột dùng để biểu diễn dữ liệu gì?", 424, ()),
        ],
        3: [
            ("Từ biểu đồ tranh, mỗi hình tròn biểu thị {a} bạn — có {b} hình thì có bao nhiêu bạn?", 423, (2, 5, 3, 15)),
            ("Tính tổng số học sinh từ bảng tần số: {a} + {b} + {c} = ?", 422, (3, 12, 4, 15, 2, 10)),
            ("Biểu đồ cột kép dùng để làm gì?", 424, ()),
            ("Từ biểu đồ cột, nhóm có số lượng {a} nhiều hơn nhóm {b} đúng không?", 424, (2, 9, 2, 9)),
            ("Biểu đồ tranh nào phù hợp để so sánh số lượng giữa 2 nhóm?", 423, ()),
            ("Từ bảng tần số, số học sinh đạt điểm {a} là bao nhiêu?", 422, (3, 12)),
            ("Từ biểu đồ cột, cột {a} thấp hơn cột {b} bao nhiêu đơn vị?", 424, (2, 8, 4, 12)),
            ("So sánh biểu đồ tranh và biểu đồ cột — cách nào cho số liệu chính xác hơn?", 423, ()),
            ("Từ biểu đồ cột kép, nhóm nào có tổng lớn hơn?", 424, ()),
        ],
        4: [
            ("Nhận xét nào đúng khi so sánh hai biểu đồ cột?", 424, ()),
            ("Biểu đồ nào biểu diễn tốt hơn sự thay đổi theo thời gian?", 424, ()),
            ("Từ biểu đồ cột kép, kết luận nào về hai nhóm là hợp lý?", 424, ()),
            ("Chọn dữ liệu phù hợp để vẽ biểu đồ cột?", 422, ()),
            ("Nhận xét nào đúng khi đọc biểu đồ cột có cột cao gấp đôi cột khác?", 424, ()),
            ("So sánh bảng thống kê và biểu đồ tranh — cách nào trực quan hơn?", 423, ()),
            ("Phân tích bảng tần số: nhóm nào chiếm nhiều nhất và tại sao?", 422, ()),
        ],
        5: [
            ("Dự đoán xu hướng từ chuỗi dữ liệu thời tiết, kết luận nào hợp lý?", 425, ()),
            ("Đánh giá cách trình bày dữ liệu bằng biểu đồ nào hiệu quả hơn?", 425, ()),
            ("Dự đoán số lượng từ bảng tần số đã thu thập, cách nào hợp lý?", 425, ()),
            ("Từ dữ liệu nhiệt độ {a} ngày, dự đoán ngày tiếp theo như thế nào?", 425, (5, 14)),
            ("Nhận xét xu hướng: số học sinh tham gia câu lạc bộ tăng qua các tuần, kết luận nào đúng?", 425, ()),
        ],
        6: [
            ("Thiết kế câu hỏi khảo sát hợp lý để thu thập dữ liệu về thói quen đọc sách.", 421, ()),
            ("Lập kế hoạch thu thập dữ liệu về chiều cao học sinh trong lớp.", 421, ()),
            ("Đề xuất cách thu thập dữ liệu về thời gian học bài mỗi ngày của học sinh.", 421, ()),
            ("Thiết kế bảng thống kê cho dữ liệu về món ăn yêu thích của lớp.", 422, ()),
        ],
    },
}
# Chương chưa có template → dùng mẫu chung (lesson None — không map được bài)
FALLBACK_TEMPLATES: dict[int, list[tuple[str, int | None, tuple[()]]]] = {
    1: [("Câu hỏi nhận biết chương này?", None, ()), ("Câu hỏi đúng/sai về khái niệm chương này?", None, ())],
    2: [("Tính toán cơ bản liên quan chương này?", None, ()), ("Bài tập vận dụng trực tiếp công thức chương này?", None, ())],
    3: [("Bài tập vận dụng mức vừa phải chương này?", None, ()), ("Tình huống cần áp dụng quy tắc chương này?", None, ())],
    4: [("Phân tích và so sánh các trường hợp trong chương này?", None, ()), ("Bài tập suy luận nhiều bước chương này?", None, ())],
    5: [("Đánh giá lời giải trong bài toán chương này?", None, ()), ("Chọn nhận định đúng về tính chất chương này?", None, ())],
    6: [("Bài toán sáng tạo/liên hệ thực tế chương này?", None, ()), ("Thiết kế phương án giải quyết vấn đề chương này?", None, ())],
}


def _fill_numbers(text: str, ranges: tuple[int, int, int, int] | tuple[()]) -> str:
    """Điền {a}/{b}/{c} bằng số ngẫu nhiên trong dải (a_min,a_max,b_min,b_max,...)."""
    nums: dict[str, int] = {}
    for key, (lo, hi) in zip(("a", "b", "c"), (ranges[i : i + 2] for i in range(0, len(ranges), 2))):
        if lo <= hi:
            nums[key] = RNG.randint(lo, hi)
    out = text
    for key, val in nums.items():
        out = out.replace("{" + key + "}", str(val))
    return out


def question_text_for(unit_id: int, bloom: int, seq: int) -> tuple[str, int | None]:
    """Nội dung mock + bài con (lesson_id) cho 1 câu — khớp pipeline test câu hỏi.

    Xoay vòng template theo seq và điền số ngẫu nhiên theo cấp độ/bài để mỗi câu khác nhau.
    """
    pool = QUESTION_TEMPLATES.get(unit_id, FALLBACK_TEMPLATES).get(bloom, FALLBACK_TEMPLATES[3])
    text, lesson_id, ranges = pool[seq % len(pool)]
    return _fill_numbers(text, ranges), lesson_id


def build_assignments() -> list[dict]:
    """34 bài LMS: (assignment_id, week, is_review, focus_unit)."""
    assignments: list[dict] = []
    n = 1
    for week in range(1, N_WEEKS + 1):
        count = ASSIGNMENTS_PER_WEEK + (1 if week in REVIEW_WEEKS else 0)
        for k in range(count):
            assignments.append(
                {
                    "assignment_id": 9000 + n,
                    "week": week,
                    "is_review": k >= ASSIGNMENTS_PER_WEEK,
                    "focus": WEEK_FOCUS[week],
                }
            )
            n += 1
    return assignments


def build_bank_questions(assignments: list[dict], lessons_by_chapter: dict[int, list[int]]) -> list[dict]:
    """340 câu: mỗi bài 6 câu chương trọng tâm + 4 câu ôn chương trước.

    Bloom 1–4 (ưu tiên 2–3) — đa dạng ở tầng câu LMS (item-level mastery).
    Một số câu ôn tập được map NHIỀU BÀI (multi-bài, lms_question_unit): câu tổng hợp
    2 chương → góp vào bài chính (weight 0.6) + 1 bài của chương kia (weight 0.4).
    `unit_id` = BÀI chính (weight cao nhất); `lesson_id` = bài chính (khớp pipeline
    "Kiểm tra câu hỏi"); `units` = [(bài_id, weight)] đầy đủ; `chapter_id` = chương
    gốc (tính xác suất đúng + chọn template nội dung).
    """
    questions: list[dict] = []
    qid = 70000
    prev_units: list[int] = []
    seq_by_chapter: dict[int, int] = {}  # đếm số câu/chương để xoay vòng template nội dung
    for a in assignments:
        focus = a["focus"]
        units: list[int] = []
        for _ in range(6):
            units.append(focus)
        pool = prev_units or [u for u in UNITS if u != focus]
        for _ in range(4):
            units.append(RNG.choice(pool))
        prev_units = list(dict.fromkeys(prev_units + [focus]))
        for chapter_id in units:
            # Bloom 1–4 chủ yếu + 5/6 thi thoảng (câu định tính của bài như Lũy thừa,
            # BTCC, HĐ trải nghiệm) — để bài nào cũng có câu hỏi (chia theo bài).
            bloom = RNG.choices([1, 2, 3, 4, 5, 6], weights=[15, 35, 35, 10, 3, 2])[0]
            qid += 1
            seq_by_chapter[chapter_id] = seq_by_chapter.get(chapter_id, 0) + 1
            text, lesson_id = question_text_for(chapter_id, bloom, seq_by_chapter[chapter_id])
            if lesson_id is None:
                lesson_id = chapter_id  # fallback: không map được bài → map chương
            # ~12% câu ôn tập thành câu tổng hợp 2 chương (multi-bài): bài chính 0.6
            # + 1 bài của chương kia 0.4 → đóng góp mastery vào cả 2 bài.
            is_multi = RNG.random() < 0.12 and chapter_id != focus
            if is_multi:
                other_ch = RNG.choice([u for u in UNITS if u != chapter_id])
                others = lessons_by_chapter.get(other_ch) or [other_ch]
                other_lesson = RNG.choice(others)
                unit_weights = [(lesson_id, 0.6), (other_lesson, 0.4)]
                text = f"{text} (tổng hợp: {UNIT_NAMES[other_ch]})"
            else:
                unit_weights = [(lesson_id, 1.0)]
            # Bài chính (unit_id) = bài có weight cao nhất; units sắp giảm dần weight.
            unit_weights.sort(key=lambda uw: uw[1], reverse=True)
            primary = unit_weights[0][0]
            questions.append(
                {
                    "question_id": qid,
                    "assignment_id": a["assignment_id"],
                    "unit_id": primary,
                    "lesson_id": primary,
                    "chapter_id": chapter_id,
                    "bloom_level": bloom,
                    "units": unit_weights,
                    "question_text": text,
                }
            )
    return questions


def discover_students(cur) -> list[dict]:
    """Học sinh khối 6 school 1 (động — chạy SAU v4). Order theo student_code."""
    cur.execute(
        """
        SELECT student_code, homeroom_class_id
        FROM s360.dim_homeroom_class_student
        WHERE so_school_id = %s AND grade_id = 6 AND school_year_id = %s
          AND (is_active IS NULL OR is_active = 1)
        ORDER BY student_code
        """,
        (SO_SCHOOL_ID, SCHOOL_YEAR_ID),
    )
    rows = cur.fetchall()
    if not rows:
        print("[ERROR] Không tìm thấy học sinh khối 6 school 1. Chạy generate_full_system_mock_v4.py trước!")
        sys.exit(1)
    return [{"student_code": r[0], "homeroom_class_id": r[1]} for r in rows]


def profile_for(rank: int) -> dict:
    if rank < len(PROFILES):
        return PROFILES[rank]
    return AVERAGE_PROFILE


def gd0_cleanup(cur) -> None:
    """GĐ 0 — Xóa sạch dữ liệu cũ subject 106 (idempotent, chạy đầu mỗi lần)."""
    print("[GĐ 0] Dọn dữ liệu cũ subject 106...")
    cur.execute("DELETE FROM public.lms_question_response;")
    cur.execute(
        "DELETE FROM public.lms_question_unit WHERE question_id IN (SELECT question_id FROM public.lms_question_bank WHERE subject_id = %s);",
        (SUBJECT_ID,),
    )
    cur.execute("DELETE FROM public.lms_question_bank WHERE subject_id = %s;", (SUBJECT_ID,))
    cur.execute("DELETE FROM public.student_unit_mastery WHERE subject_id = %s;", (SUBJECT_ID,))
    cur.execute(
        """DELETE FROM public.exam_competencies
           WHERE exam_paper_id IN (SELECT id FROM public.exam_papers WHERE subject_id = %s);""",
        (SUBJECT_ID,),
    )
    cur.execute("DELETE FROM public.exam_papers WHERE subject_id = %s;", (SUBJECT_ID,))
    cur.execute(
        "DELETE FROM s360.fact_gradebooks WHERE subject_id = %s AND so_school_id = %s;",
        (SUBJECT_ID, SO_SCHOOL_ID),
    )


def _split_even_preserving_total(weight: float, n: int) -> list[float]:
    """Chia đều `weight` cho `n` phần, bảo toàn tổng (largest-remainder, 3 số thập phân)."""
    if n <= 0:
        return []
    base = round(weight / n, 3)
    parts = [base] * n
    diff = round(weight - base * n, 3)
    for i in range(n):
        if abs(diff) < 1e-9:
            break
        step = 0.001 if diff > 0 else -0.001
        parts[i] = round(parts[i] + step, 3)
        diff = round(diff - step, 3)
    return parts


def gd1_exam_papers(cur, lessons_by_chapter: dict[int, list[int]]) -> int:
    """GĐ 1 — 6 đề khối 6 + map competencies cấp BÀI (chỉ GK1). Trả id đề GK1."""
    print("[GĐ 1] Seed 6 đề khối 6 (exam_papers)...")
    papers = [
        ("Đề thi Giữa kỳ 1 Toán 6 Khối 6 (GK1)", "MIDTERM", 10, 10.0),
        ("Đề thi Cuối kỳ 1 Toán 6 Khối 6 (CK1)", "FINAL", 10, 10.0),
        ("Kiểm tra 15' Toán 6 — Chương 1 Số tự nhiên", "REGULAR", 5, 5.0),
        ("Kiểm tra 15' Toán 6 — Chương 2 Số nguyên", "REGULAR", 5, 5.0),
        ("Kiểm tra 15' Toán 6 — Chương 3 Hình phẳng", "REGULAR", 5, 5.0),
        ("Kiểm tra 15' Toán 6 — Chương 4 Thống kê", "REGULAR", 5, 5.0),
    ]
    gk1_id: int | None = None
    for title, cat, nq, tp in papers:
        cur.execute(
            """
            INSERT INTO public.exam_papers
                (so_school_id, subject_id, semester_id, grade_id, score_category,
                 title, difficulty, difficulty_coefficient, num_questions, total_points, uploaded_by)
            VALUES (%s, %s, %s, 6, %s::public.score_category_enum, %s, 'MEDIUM', 1.0, %s, %s, 1)
            RETURNING id
            """,
            (SO_SCHOOL_ID, SUBJECT_ID, SEMESTER, cat, title, nq, tp),
        )
        pid = cur.fetchone()[0]
        if cat == "MIDTERM":
            gk1_id = pid

    assert gk1_id is not None, "Không tạo được đề GK1 (MIDTERM)"
    # Map competencies CHỈ trên GK1 (cấp BÀI): mỗi chương → các bài con, chia đều weight.
    # Tránh trùng unit khi API gộp competencies theo subject+semester.
    comp_rows: list[tuple] = []
    for chapter_id, weight in EXAM_COMPETENCIES:
        lessons = lessons_by_chapter.get(chapter_id) or [chapter_id]
        parts = _split_even_preserving_total(weight, len(lessons))
        for lesson_id, part in zip(lessons, parts, strict=False):
            comp_rows.append((gk1_id, lesson_id, part))
    cur.executemany(
        """
        INSERT INTO public.exam_competencies (exam_paper_id, unit_id, weight, bloom_level)
        VALUES (%s, %s, %s, 3)
        ON CONFLICT (exam_paper_id, unit_id) DO UPDATE
          SET weight = EXCLUDED.weight, bloom_level = EXCLUDED.bloom_level
        """,
        comp_rows,
    )
    print(f"  → {len(comp_rows)} competency (đề GK1, cấp bài, bloom=3)")
    return gk1_id


def gd2_gradebooks(cur, students: list[dict], profiles: list[dict]) -> None:
    """GĐ 2 — Re-mock điểm thi trên lớp (TX 1061 + GK 1062, đã khóa)."""
    print("[GĐ 2] Re-mock fact_gradebooks subject 106 (TX + GK)...")
    cur.execute("SELECT COALESCE(MAX(id), 0) FROM s360.fact_gradebooks")
    fid = cur.fetchone()[0]
    rows: list[tuple] = []
    for st, prof in zip(students, profiles, strict=False):
        gk = float(prof["gk"])
        tx = max(0.0, round(gk - RNG.uniform(0.3, 0.9), 1))
        for exam_id, score, created in [
            (1061, tx, "2025-09-05 10:00:00"),
            (1062, gk, "2025-10-10 10:00:00"),
        ]:
            fid += 1
            pct = round(score * 10.0, 2)
            rows.append(
                (
                    fid,
                    SO_SCHOOL_ID,
                    SCHOOL_YEAR_ID,
                    SEMESTER,
                    st["homeroom_class_id"],
                    st["student_code"],
                    SUBJECT_ID,
                    exam_id,
                    round(score, 2),
                    pct,
                    None,
                    "DAT" if score >= 5 else "CHUA_DAT",
                    "SCALE_10",
                    MAX_GRADE,
                    1,
                    created,
                    "SCHOOL_ONLINE_LMS",
                )
            )
    cur.executemany(
        """
        INSERT INTO s360.fact_gradebooks
            (id, so_school_id, school_year_id, semester_index, homeroom_class_id,
             student_code, subject_id, so_exam_id, final_grade, final_grade_percent,
             final_grade_letter, pass_fail_status, scale_name_used, max_grade,
             is_locked, created_at, source_system)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::public.pass_fail_enum, %s, %s, %s, %s, %s)
        """,
        rows,
    )
    print(f"  → {len(rows)} dòng điểm (TX + GK)")


def gd3_bank(cur, questions: list[dict]) -> None:
    """GĐ 3 — lms_question_bank (340 câu) + lms_question_unit (map BÀI, kể cả multi-bài)."""
    print("[GĐ 3] Seed lms_question_bank + lms_question_unit...")
    rows = [
        (
            q["question_id"],
            q["assignment_id"],
            SO_SCHOOL_ID,
            SUBJECT_ID,
            q["unit_id"],
            q["lesson_id"],
            q["bloom_level"],
            "MCQ",
            q.get("question_text"),
            1.0,
            1,
        )
        for q in questions
    ]
    cur.executemany(
        """
        INSERT INTO public.lms_question_bank
            (question_id, assignment_id, so_school_id, subject_id, unit_id,
             lesson_id, bloom_level, question_type, question_text, item_weight, is_active)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (question_id) DO UPDATE
          SET assignment_id = EXCLUDED.assignment_id, unit_id = EXCLUDED.unit_id,
              lesson_id = EXCLUDED.lesson_id, bloom_level = EXCLUDED.bloom_level,
              question_text = EXCLUDED.question_text, is_active = 1
        """,
        rows,
    )
    # Map câu → BÀI (lms_question_unit) — câu đơn 1 bài weight 1.0, câu tổng hợp
    # 2 chương có weight phân bổ (0.6/0.4) sang bài của chương kia.
    # lesson_id đã lưu riêng ở lms_question_bank.lesson_id (= bài chính);
    # mastery tính theo BÀI (chi tiết hơn chương, khớp yêu cầu "chia theo bài").
    unit_rows = [
        (q["question_id"], unit_id, weight)
        for q in questions
        for unit_id, weight in q["units"]
    ]
    cur.executemany(
        """
        INSERT INTO public.lms_question_unit (question_id, unit_id, weight)
        VALUES (%s, %s, %s)
        ON CONFLICT (question_id, unit_id) DO UPDATE
          SET weight = EXCLUDED.weight
        """,
        unit_rows,
    )
    n_multi = sum(1 for q in questions if len(q["units"]) > 1)
    print(f"  → {len(rows)} câu hỏi ({len(questions) // QUESTIONS_PER_ASSIGNMENT} bài), "
          f"{len(unit_rows)} dòng map bài, {n_multi} câu multi-bài")


def gd4_responses(cur, students: list[dict], profiles: list[dict], questions: list[dict], assignments: list[dict]) -> None:
    """GĐ 4 — lms_question_response: item-response hàng tuần (quá trình làm LMS).

    Mỗi HS × mỗi bài (trừ NO_LMS): trả lời 10 câu; yếu chương → thử lại (attempt 2)
    nhưng vẫn sai (effortful-but-lost); HS gian lận → trả lời siêu nhanh (< 2s,
    integrity_flag=1) kèm điểm cao.
    """
    print("[GĐ 4] Seed lms_question_response (quá trình làm LMS hàng tuần)...")
    by_assign: dict[int, list[dict]] = {}
    for q in questions:
        by_assign.setdefault(q["assignment_id"], []).append(q)
    week_of = {a["assignment_id"]: a["week"] for a in assignments}

    rows: list[tuple] = []
    for st, prof in zip(students, profiles, strict=False):
        if prof["p"] is None:  # NO_LMS — không có item nào
            continue
        p_map = prof["p"]
        cheat = bool(prof.get("cheat"))
        weak_units = {u for u in UNITS if p_map.get(u, 0.0) < 0.35}
        for assignment_id, qs in by_assign.items():
            week = week_of[assignment_id]
            attempt_date = WEEK_START + timedelta(weeks=week - 1, hours=RNG.randint(16, 21), minutes=RNG.randint(0, 59))
            for q in qs:
                chapter = q["chapter_id"]
                correct = RNG.random() < p_map.get(chapter, 0.7)
                # HS gian lận: trả lời siêu nhanh (integrity_flag=1) + luôn đúng
                if cheat:
                    correct = True
                    rtime = RNG.randint(1, 2)
                    flag = 1
                else:
                    rtime = RNG.randint(15, 600)
                    flag = 0
                # Effortful-but-lost: câu sai ở chương yếu → thử lại nhưng vẫn sai
                retry = not correct and chapter in weak_units and RNG.random() < 0.5
                rows.append(
                    (
                        SO_SCHOOL_ID,
                        st["student_code"],
                        assignment_id,
                        q["question_id"],
                        q["unit_id"],
                        q["bloom_level"],
                        "MCQ",
                        1,
                        not retry,  # is_best_attempt: chỉ đúng trên 1 dòng/câu
                        correct,
                        1.0 if correct else 0.0,
                        1.0,
                        rtime,
                        Jsonb({"chosen_option": RNG.choice(["A", "B", "C", "D"])}),
                        flag,
                        attempt_date,
                    )
                )
                if retry:
                    rows.append(
                        (
                            SO_SCHOOL_ID,
                            st["student_code"],
                            assignment_id,
                            q["question_id"],
                            q["unit_id"],
                            q["bloom_level"],
                            "MCQ",
                            2,
                            True,
                            False,
                            0.0,
                            1.0,
                            RNG.randint(60, 900),
                            Jsonb({"chosen_option": RNG.choice(["A", "B", "C", "D"])}),
                            flag,
                            attempt_date + timedelta(minutes=RNG.randint(2, 30)),
                        )
                    )
    cur.executemany(
        """
        INSERT INTO public.lms_question_response
            (so_school_id, student_code, assignment_id, question_id, unit_id,
             bloom_level, question_type, attempt_number, is_best_attempt, is_correct,
             score_received, max_score, response_time_seconds, response_payload,
             integrity_flag, attempt_date)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s)
        ON CONFLICT (student_code, assignment_id, question_id, attempt_number) DO NOTHING
        """,
        rows,
    )
    print(f"  → {len(rows)} response ({len(students)} HS × {len(by_assign)} bài)")


def gd5_mastery(cur, students: list[dict], profiles: list[dict], gk1_units: list[UnitWeight]) -> None:
    """GĐ 5 — Tính student_unit_mastery bằng service thật (finalize_mastery)."""
    print("[GĐ 5] Tính student_unit_mastery (finalize_mastery + compute_unit_mastery)...")
    # Map câu → [(bài_id, weight)] — câu multi-bài đóng góp vào nhiều bài theo trọng số.
    cur.execute("SELECT question_id, unit_id, weight FROM public.lms_question_unit")
    unit_map: dict[int, list[tuple[int, float]]] = {}
    for qid, uid, w in cur.fetchall():
        unit_map.setdefault(qid, []).append((uid, float(w)))

    cur.execute(
        """
        SELECT student_code, question_id, bloom_level, is_correct, score_received, max_score
        FROM public.lms_question_response
        WHERE so_school_id = %s AND is_best_attempt = TRUE
        ORDER BY student_code, question_id
        """,
        (SO_SCHOOL_ID,),
    )
    resp_rows = cur.fetchall()
    by_student: dict[str, list[ItemResult]] = {}
    for r in resp_rows:
        score = float(r[4]) if r[4] is not None else (1.0 if r[3] else 0.0)
        max_score = float(r[5]) if r[5] is not None else 1.0
        for uid, weight in unit_map.get(r[1], [(None, 1.0)]):
            if uid is None:
                continue  # câu chưa map chương → bỏ qua (không đóng góp mastery)
            by_student.setdefault(r[0], []).append(
                ItemResult(
                    unit_id=uid,
                    bloom_level=r[2],
                    score_received=score,
                    max_score=max_score,
                    unit_weight=weight,
                )
            )

    # exam_mastery theo chương từ điểm GK (1062) — khớp fallback EXAM của API
    gk_by_student: dict[str, float] = {}
    for st, prof in zip(students, profiles, strict=False):
        gk_by_student[st["student_code"]] = float(prof["gk"])

    # Lấy parent_id của các unit để gán điểm thi tương ứng từ chương cha
    cur.execute("SELECT id, parent_id FROM public.curriculum_units WHERE subject_id = %s", (SUBJECT_ID,))
    parent_map = {r[0]: r[1] for r in cur.fetchall()}

    upserts: list[tuple] = []
    skipped = 0
    for st in students:
        code = st["student_code"]
        if code not in by_student:
            skipped += 1  # NO_LMS → không insert → API fallback EXAM
            continue
        items = by_student[code]
        gk = gk_by_student[code]
        exam_list = compute_unit_mastery(gk, MAX_GRADE, gk1_units)
        exam_by_unit = {m.unit_id: m.mastery for m in exam_list}

        # Tính mastery cho toàn bộ unit (cả chương cha và bài con)
        all_uids = set(i.unit_id for i in items)
        for unit_id in all_uids:
            unit_items = [i for i in items if i.unit_id == unit_id]
            if not unit_items:
                continue
            parent_ch = parent_map.get(unit_id) or unit_id
            exam_m = exam_by_unit.get(parent_ch)
            m = finalize_mastery(unit_items, exam_m)
            upserts.append(
                (
                    code,
                    SUBJECT_ID,
                    SO_SCHOOL_ID,
                    unit_id,
                    SEMESTER,
                    m.raw_mastery,
                    m.n_items,
                    m.n_correct,
                    m.coverage,
                    m.lm_weight,
                    m.exam_weight,
                    m.adjusted_mastery,
                    CONFIDENCE_INT.get(m.confidence, 1),
                    m.evidence_source,
                    m.integrity_status,
                    Jsonb(m.evidence_detail) if m.evidence_detail else None,
                )
            )
    cur.executemany(
        """
        INSERT INTO public.student_unit_mastery
            (student_code, subject_id, so_school_id, unit_id, semester_index,
             raw_mastery, n_items, n_correct, coverage, lm_weight, exam_weight,
             adjusted_mastery, confidence, evidence_source, integrity_status,
             evidence_detail, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, NOW())
        ON CONFLICT (so_school_id, student_code, subject_id, unit_id, semester_index) DO UPDATE
          SET raw_mastery = EXCLUDED.raw_mastery, adjusted_mastery = EXCLUDED.adjusted_mastery,
              n_items = EXCLUDED.n_items, n_correct = EXCLUDED.n_correct,
              coverage = EXCLUDED.coverage, lm_weight = EXCLUDED.lm_weight,
              exam_weight = EXCLUDED.exam_weight, confidence = EXCLUDED.confidence,
              evidence_source = EXCLUDED.evidence_source,
              integrity_status = EXCLUDED.integrity_status,
              evidence_detail = EXCLUDED.evidence_detail, updated_at = NOW()
        """,
        upserts,
    )
    print(f"  → {len(upserts)} dòng mastery ({skipped} HS không có item → fallback EXAM)")


def gd6_summary(cur, students: list[dict], profiles: list[dict]) -> None:
    """GĐ 6 — In bảng tổng kết để đối chiếu (gộp mastery các bài con → chương)."""
    print("\n[GĐ 6] BẢNG TỔNG KẾT (HS | lớp | GK | LMS/chương | adjusted/chương | conf | integrity)")
    cur.execute("SELECT id, parent_id FROM public.curriculum_units WHERE subject_id = %s", (SUBJECT_ID,))
    parent_map = {r[0]: r[1] for r in cur.fetchall()}
    cur.execute(
        """
        SELECT student_code, unit_id, adjusted_mastery, raw_mastery, confidence, integrity_status
        FROM public.student_unit_mastery
        WHERE subject_id = %s AND so_school_id = %s AND semester_index = %s
        ORDER BY student_code, unit_id
        """,
        (SUBJECT_ID, SO_SCHOOL_ID, SEMESTER),
    )
    rows = cur.fetchall()
    by_code: dict[str, list] = {}
    for r in rows:
        by_code.setdefault(r[0], []).append(r)
    conf_str = {3: "HIGH", 2: "MEDIUM", 1: "LOW"}
    for st, prof in zip(students, profiles, strict=False):
        code = st["student_code"]
        gk = float(prof["gk"])
        mrows = by_code.get(code, [])
        if not mrows:
            print(f"{code}  lớp {st['homeroom_class_id']:<3} GK={gk:<5} → (không có item LMS → fallback EXAM)")
            continue
        # Gộp các dòng bài con theo chương cha (parent_id) để in gọn theo chương.
        ch_raw: dict[int, list[float]] = {}
        ch_adj: dict[int, list[float]] = {}
        for r in mrows:
            ch = parent_map.get(r[1]) or r[1]
            ch_raw.setdefault(ch, []).append(r[3])
            ch_adj.setdefault(ch, []).append(r[2])
        lms = " ".join(f"{UNIT_NAMES[c]}:{sum(v) / len(v):.2f}" for c, v in ch_raw.items())
        adj = " ".join(f"{UNIT_NAMES[c]}:{sum(v) / len(v):.2f}" for c, v in ch_adj.items())
        conf = conf_str.get(int(mrows[0][4]), "?")
        integ = mrows[0][5]
        print(f"{code}  lớp {st['homeroom_class_id']:<3} GK={gk:<5} LMS[{lms}] ADJ[{adj}] {conf} {integ}")
    print("\n[SUCCESS] Seed mock Toan 6 hoàn tất. Kiểm chứng: /knowledge-gaps/students/<HS>?subject_id=106")


def main() -> None:
    print(f"[INFO] Seeding Mock Toan 6 (subject 106, school 1) on: {DB_URL[:40]}...")
    conn = psycopg.connect(DB_URL, autocommit=True)
    cur = conn.cursor()
    try:
        students = discover_students(cur)
        n_profiles = min(len(students), len(PROFILES))
        print(f"[INFO] Tìm thấy {len(students)} HS khối 6 school 1; gán {n_profiles} profile mục tiêu theo rank.")
        if len(students) < len(PROFILES):
            print(f"[WARN] Chỉ có {len(students)} HS (< {len(PROFILES)} profile) — gán profile cho số có, phần còn lại trung bình.")
        profiles = [profile_for(i) for i in range(len(students))]

        gd0_cleanup(cur)

        # Bản đồ chương → các bài con (curriculum_units) — dùng cho ma trận đề cấp bài (gd1)
        # và chọn bài cho câu multi-bài (gd3).
        cur.execute(
            "SELECT id, parent_id FROM public.curriculum_units WHERE subject_id = %s",
            (SUBJECT_ID,),
        )
        lessons_by_chapter: dict[int, list[int]] = {}
        for uid, pid in cur.fetchall():
            if pid is not None:
                lessons_by_chapter.setdefault(pid, []).append(uid)

        gk1_id = gd1_exam_papers(cur, lessons_by_chapter)
        gd2_gradebooks(cur, students, profiles)

        assignments = build_assignments()
        questions = build_bank_questions(assignments, lessons_by_chapter)
        gd3_bank(cur, questions)
        gd4_responses(cur, students, profiles, questions, assignments)

        gk1_units = [
            UnitWeight(unit_id=u, weight=w, bloom_level=3)
            for u, w in EXAM_COMPETENCIES
        ]
        gd5_mastery(cur, students, profiles, gk1_units)
        gd6_summary(cur, students, profiles)
        print(f"[INFO] GK1 exam_paper id = {gk1_id} (competencies cấp bài theo 4 chương)")
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
