"""Script seed phân phối chương trình giảng dạy mẫu (Teaching Schedule) đầy đủ 35 tuần cho Toán 6.

Bao gồm:
- Học kỳ 1 (Tuần 1 - 18, 72 tiết): Số tự nhiên, Số nguyên, Hình học trực quan, Thống kê.
  + Tuần 9: Kiểm tra Giữa HK1.
  + Tuần 18: Kiểm tra Cuối HK1.
- Học kỳ 2 (Tuần 19 - 35, 68 tiết): Phân số, Số thập phân, Hình học phẳng, Xác suất thực nghiệm.
  + Tuần 27: Kiểm tra Giữa HK2.
  + Tuần 35: Kiểm tra Cuối HK2 (Cuối năm).

Chạy: `python scripts/seed_teaching_schedules_toan6.py`
"""

import sys
from pathlib import Path

if sys.platform.startswith("win"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text
from src.db.session import engine


def seed_toan6_schedule(school_year_id: int = 2025, subject_id: int = 106, grade: int = 6) -> None:
    print(f"[INFO] Bắt đầu seed Teaching Schedule đầy đủ 35 tuần cho Môn {subject_id}, Khối {grade}, Năm học {school_year_id}...")
    with engine.begin() as conn:
        # Lấy bản đồ code -> id của các unit đã có trong DB
        units = conn.execute(
            text("""
            SELECT id, code, name
            FROM public.curriculum_units
            WHERE subject_id = :subj AND grade_number = :grade
        """),
            {"subj": subject_id, "grade": grade},
        ).fetchall()
        code_to_id = {u.code: u.id for u in units}

        records = [
            # ===================== HỌC KỲ 1 (Tuần 1 -> 18) =====================
            {
                "school_year_id": school_year_id, "subject_id": subject_id, "grade_number": grade,
                "semester_number": 1, "week_number": 1, "unit_id": code_to_id.get("TOAN6_C1_B1"),
                "topic": "Bài 1: Tập hợp. Phần tử của tập hợp", "num_periods": 4, "notes": "Khái niệm tập hợp và các phần tử"
            },
            {
                "school_year_id": school_year_id, "subject_id": subject_id, "grade_number": grade,
                "semester_number": 1, "week_number": 2, "unit_id": code_to_id.get("TOAN6_C1_B2"),
                "topic": "Bài 2: Tập hợp số tự nhiên. Ghi số tự nhiên", "num_periods": 4, "notes": "Hệ thập phân và số La Mã"
            },
            {
                "school_year_id": school_year_id, "subject_id": subject_id, "grade_number": grade,
                "semester_number": 1, "week_number": 3, "unit_id": code_to_id.get("TOAN6_C1_B3"),
                "topic": "Bài 3: Các phép tính trong tập hợp số tự nhiên", "num_periods": 4, "notes": "Phép cộng, trừ, nhân, chia"
            },
            {
                "school_year_id": school_year_id, "subject_id": subject_id, "grade_number": grade,
                "semester_number": 1, "week_number": 4, "unit_id": code_to_id.get("TOAN6_C1_B4"),
                "topic": "Bài 4: Lũy thừa với số mũ tự nhiên", "num_periods": 4, "notes": "Nhân chia hai lũy thừa cùng cơ số"
            },
            {
                "school_year_id": school_year_id, "subject_id": subject_id, "grade_number": grade,
                "semester_number": 1, "week_number": 5, "unit_id": code_to_id.get("TOAN6_C1_B5"),
                "topic": "Bài 5: Thứ tự thực hiện các phép tính", "num_periods": 4, "notes": "Biểu thức có ngoặc và không ngoặc"
            },
            {
                "school_year_id": school_year_id, "subject_id": subject_id, "grade_number": grade,
                "semester_number": 1, "week_number": 6, "unit_id": code_to_id.get("TOAN6_C1_B6"),
                "topic": "Bài 6: Chia hết và chia có dư. Tính chất chia hết của một tổng", "num_periods": 4, "notes": "Tính chất chia hết"
            },
            {
                "school_year_id": school_year_id, "subject_id": subject_id, "grade_number": grade,
                "semester_number": 1, "week_number": 7, "unit_id": code_to_id.get("TOAN6_C1_B7"),
                "topic": "Bài 7: Dấu hiệu chia hết cho 2, cho 5 & Bài 8: Chia hết cho 3, cho 9", "num_periods": 4, "notes": "Dấu hiệu chia hết cơ bản"
            },
            {
                "school_year_id": school_year_id, "subject_id": subject_id, "grade_number": grade,
                "semester_number": 1, "week_number": 8, "unit_id": code_to_id.get("TOAN6_C1_B9"),
                "topic": "Bài 9: Ước và bội & Bài 10: Số nguyên tố, hợp số", "num_periods": 4, "notes": "Phân tích ra thừa số nguyên tố"
            },
            {
                "school_year_id": school_year_id, "subject_id": subject_id, "grade_number": grade,
                "semester_number": 1, "week_number": 9, "unit_id": None,
                "topic": "ÔN TẬP VÀ KIỂM TRA ĐÁNH GIÁ GIỮA HỌC KỲ 1", "num_periods": 4, "notes": "Kiểm tra định kỳ giữa kỳ 1 tập trung"
            },
            {
                "school_year_id": school_year_id, "subject_id": subject_id, "grade_number": grade,
                "semester_number": 1, "week_number": 10, "unit_id": code_to_id.get("TOAN6_C1_B12"),
                "topic": "Bài 12: Ước chung, ƯCLN & Bài 13: Bội chung, BCNN", "num_periods": 4, "notes": "Tìm ƯCLN và BCNN"
            },
            {
                "school_year_id": school_year_id, "subject_id": subject_id, "grade_number": grade,
                "semester_number": 1, "week_number": 11, "unit_id": code_to_id.get("TOAN6_C2_B1"),
                "topic": "Chương 2 - Bài 1: Số nguyên âm và tập hợp các số nguyên", "num_periods": 4, "notes": "Biểu diễn số nguyên trên trục số"
            },
            {
                "school_year_id": school_year_id, "subject_id": subject_id, "grade_number": grade,
                "semester_number": 1, "week_number": 12, "unit_id": code_to_id.get("TOAN6_C2_B3"),
                "topic": "Bài 2: Thứ tự số nguyên & Bài 3: Phép cộng và phép trừ số nguyên", "num_periods": 4, "notes": "Cộng trừ số nguyên có dấu"
            },
            {
                "school_year_id": school_year_id, "subject_id": subject_id, "grade_number": grade,
                "semester_number": 1, "week_number": 13, "unit_id": code_to_id.get("TOAN6_C2_B4"),
                "topic": "Bài 4: Phép nhân và phép chia hết hai số nguyên", "num_periods": 4, "notes": "Quy tắc dấu khi nhân chia số nguyên"
            },
            {
                "school_year_id": school_year_id, "subject_id": subject_id, "grade_number": grade,
                "semester_number": 1, "week_number": 14, "unit_id": code_to_id.get("TOAN6_C3_B1"),
                "topic": "Chương 3 - Bài 1: Hình vuông, Tam giác đều, Lục giác đều", "num_periods": 4, "notes": "Nhận biết các hình phẳng đều"
            },
            {
                "school_year_id": school_year_id, "subject_id": subject_id, "grade_number": grade,
                "semester_number": 1, "week_number": 15, "unit_id": code_to_id.get("TOAN6_C3_B2"),
                "topic": "Bài 2: Hình chữ nhật, Hình thoi, Hình bình hành, Hình thang cân", "num_periods": 4, "notes": "Đặc điểm các hình tứ giác đặc biệt"
            },
            {
                "school_year_id": school_year_id, "subject_id": subject_id, "grade_number": grade,
                "semester_number": 1, "week_number": 16, "unit_id": code_to_id.get("TOAN6_C3_B3"),
                "topic": "Bài 3: Chu vi và diện tích của một số hình trong thực tiễn", "num_periods": 4, "notes": "Công thức chu vi diện tích"
            },
            {
                "school_year_id": school_year_id, "subject_id": subject_id, "grade_number": grade,
                "semester_number": 1, "week_number": 17, "unit_id": code_to_id.get("TOAN6_C4_B1"),
                "topic": "Chương 4: Thu thập, phân loại dữ liệu & Biểu đồ tranh, biểu đồ cột", "num_periods": 4, "notes": "Xử lý bảng dữ liệu và biểu đồ"
            },
            {
                "school_year_id": school_year_id, "subject_id": subject_id, "grade_number": grade,
                "semester_number": 1, "week_number": 18, "unit_id": None,
                "topic": "ÔN TẬP VÀ KIỂM TRA ĐÁNH GIÁ CUỐI HỌC KỲ 1", "num_periods": 4, "notes": "Kiểm tra định kỳ cuối học kỳ 1"
            },

            # ===================== HỌC KỲ 2 (Tuần 19 -> 35) =====================
            {
                "school_year_id": school_year_id, "subject_id": subject_id, "grade_number": grade,
                "semester_number": 2, "week_number": 19, "unit_id": None,
                "topic": "Chương 5 - Phân số: Phân số với tử và mẫu là số nguyên", "num_periods": 4, "notes": "Mở rộng khái niệm phân số"
            },
            {
                "school_year_id": school_year_id, "subject_id": subject_id, "grade_number": grade,
                "semester_number": 2, "week_number": 20, "unit_id": None,
                "topic": "So sánh phân số & Hỗn số dương", "num_periods": 4, "notes": "Quy đồng mẫu số và so sánh"
            },
            {
                "school_year_id": school_year_id, "subject_id": subject_id, "grade_number": grade,
                "semester_number": 2, "week_number": 21, "unit_id": None,
                "topic": "Phép cộng và phép trừ phân số", "num_periods": 4, "notes": "Tính chất cộng phân số"
            },
            {
                "school_year_id": school_year_id, "subject_id": subject_id, "grade_number": grade,
                "semester_number": 2, "week_number": 22, "unit_id": None,
                "topic": "Phép nhân và phép chia phân số", "num_periods": 4, "notes": "Quy tắc nhân chia phân số"
            },
            {
                "school_year_id": school_year_id, "subject_id": subject_id, "grade_number": grade,
                "semester_number": 2, "week_number": 23, "unit_id": None,
                "topic": "Hai bài toán về phân số (Giá trị phân số và Tìm số biết giá trị)", "num_periods": 4, "notes": "Ứng dụng phân số thực tế"
            },
            {
                "school_year_id": school_year_id, "subject_id": subject_id, "grade_number": grade,
                "semester_number": 2, "week_number": 24, "unit_id": None,
                "topic": "Chương 6 - Số thập phân & Các phép tính với số thập phân", "num_periods": 4, "notes": "Số thập phân âm và dương"
            },
            {
                "school_year_id": school_year_id, "subject_id": subject_id, "grade_number": grade,
                "semester_number": 2, "week_number": 25, "unit_id": None,
                "topic": "Làm tròn số và ước lượng kết quả & Tỉ số phần trăm", "num_periods": 4, "notes": "Làm tròn chữ số thập phân"
            },
            {
                "school_year_id": school_year_id, "subject_id": subject_id, "grade_number": grade,
                "semester_number": 2, "week_number": 26, "unit_id": None,
                "topic": "Ôn tập và củng cố chủ đề Phân số & Số thập phân", "num_periods": 4, "notes": "Giải bài toán thực tế"
            },
            {
                "school_year_id": school_year_id, "subject_id": subject_id, "grade_number": grade,
                "semester_number": 2, "week_number": 27, "unit_id": None,
                "topic": "ÔN TẬP VÀ KIỂM TRA ĐÁNH GIÁ GIỮA HỌC KỲ 2", "num_periods": 4, "notes": "Kiểm tra giữa HK2 tập trung"
            },
            {
                "school_year_id": school_year_id, "subject_id": subject_id, "grade_number": grade,
                "semester_number": 2, "week_number": 28, "unit_id": None,
                "topic": "Chương 7 - Hình học trực quan: Điểm, đường thẳng, tia", "num_periods": 4, "notes": "Quan hệ giữa điểm và đường thẳng"
            },
            {
                "school_year_id": school_year_id, "subject_id": subject_id, "grade_number": grade,
                "semester_number": 2, "week_number": 29, "unit_id": None,
                "topic": "Đoạn thẳng. Độ dài đoạn thẳng & Trung điểm của đoạn thẳng", "num_periods": 4, "notes": "Thực hành đo đạc"
            },
            {
                "school_year_id": school_year_id, "subject_id": subject_id, "grade_number": grade,
                "semester_number": 2, "week_number": 30, "unit_id": None,
                "topic": "Góc. Số đo góc & Các góc đặc biệt (góc vuông, góc nhọn, góc tù)", "num_periods": 4, "notes": "Thực hành đo góc bằng thước đo độ"
            },
            {
                "school_year_id": school_year_id, "subject_id": subject_id, "grade_number": grade,
                "semester_number": 2, "week_number": 31, "unit_id": None,
                "topic": "Chương 8: Hình có trục đối xứng & Hình có tâm đối xứng trong tự nhiên", "num_periods": 4, "notes": "Nhận biết tính đối xứng"
            },
            {
                "school_year_id": school_year_id, "subject_id": subject_id, "grade_number": grade,
                "semester_number": 2, "week_number": 32, "unit_id": None,
                "topic": "Chương 9 - Xác suất thực nghiệm: Phép thử nghiệm & Sự kiện", "num_periods": 4, "notes": "Khái niệm biến cố và sự kiện"
            },
            {
                "school_year_id": school_year_id, "subject_id": subject_id, "grade_number": grade,
                "semester_number": 2, "week_number": 33, "unit_id": None,
                "topic": "Xác suất thực nghiệm trong một số trò chơi đơn giản (tung đồng xu, xúc xắc)", "num_periods": 4, "notes": "Tính tỉ số xuất hiện thực tế"
            },
            {
                "school_year_id": school_year_id, "subject_id": subject_id, "grade_number": grade,
                "semester_number": 2, "week_number": 34, "unit_id": None,
                "topic": "Hoạt động thực hành trải nghiệm & Ôn tập tổng kết cuối năm", "num_periods": 4, "notes": "Hệ thống hóa kiến thức lớp 6"
            },
            {
                "school_year_id": school_year_id, "subject_id": subject_id, "grade_number": grade,
                "semester_number": 2, "week_number": 35, "unit_id": None,
                "topic": "ÔN TẬP VÀ KIỂM TRA ĐÁNH GIÁ CUỐI HỌC KỲ 2 (CUỐI NĂM)", "num_periods": 4, "notes": "Kiểm tra học kỳ 2 toàn diện"
            },
        ]

        # Upsert vào teaching_schedules
        inserted = 0
        for r in records:
            conn.execute(
                text("""
                INSERT INTO public.teaching_schedules 
                    (school_year_id, subject_id, grade_number, semester_number, week_number, unit_id, topic, num_periods, notes)
                VALUES 
                    (:school_year_id, :subject_id, :grade_number, :semester_number, :week_number, :unit_id, :topic, :num_periods, :notes)
                ON CONFLICT (school_year_id, subject_id, grade_number, semester_number, week_number, unit_id)
                DO UPDATE SET
                    topic = EXCLUDED.topic,
                    num_periods = EXCLUDED.num_periods,
                    notes = EXCLUDED.notes,
                    updated_at = NOW();
            """),
                r,
            )
            inserted += 1

        print(f"[SUCCESS] Đã nạp thành công toàn bộ {inserted} tuần (35 tuần học) vào `teaching_schedules`!")


if __name__ == "__main__":
    seed_toan6_schedule()
