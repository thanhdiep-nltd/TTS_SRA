"""Seed MOCK ngân hàng lỗi sai phổ biến (misconceptions) môn Toán khối 6-9 cho DEMO.

Idempotent theo (unit, description). Dữ liệu MOCK mô phỏng kết quả khai thác từ bài làm học
sinh — pipeline khai thác thật (từ bảng scores/bài làm) là hạng mục tương lai.
Chạy: python scripts/seed_misconceptions_toan.py
"""

import sys

from sqlalchemy import select

from src.db.session import SessionLocal
from src.models import enums
from src.models.tables import CurriculumUnit, Misconception, Subject, User

# unit code -> [(mô tả lỗi sai, ví dụ bài làm sai, số bài ghi nhận mock)]
_DATA: dict[str, list[tuple[str, str, int]]] = {
    "TOAN6-TAPHOP": [
        ("Nhầm phần tử với tập hợp: viết 2 ⊂ N thay vì 2 ∈ N", "2 ⊂ N", 47),
        ("Coi 0 không phải số tự nhiên", "N = {1; 2; 3; ...}", 31),
    ],
    "TOAN6-SONGUYEN": [
        ("So sánh số âm ngược: cho rằng -5 > -2 vì 5 > 2", "-5 > -2", 58),
        ("Bỏ dấu khi cộng hai số âm: (-3) + (-4) = 7", "(-3) + (-4) = 7", 44),
        ("Nhân hai số âm ra số âm: (-2)·(-3) = -6", "(-2)·(-3) = -6", 39),
    ],
    "TOAN6-HINHPHANG": [
        ("Nhầm chu vi với diện tích hình chữ nhật", "S = 2(a+b)", 35),
        ("Đếm thiếu trục đối xứng của hình vuông (chỉ đếm 2)", "hình vuông có 2 trục đối xứng", 22),
    ],
    "TOAN7-SOHUUTI": [
        ("Cộng hai phân số bằng cách cộng tử với tử, mẫu với mẫu", "1/2 + 1/3 = 2/5", 63),
        ("Chia phân số mà quên nghịch đảo phân số thứ hai", "1/2 : 1/4 = 1/8", 41),
        ("Cho rằng số hữu tỉ âm không phải số hữu tỉ", "-0,5 ∉ Q", 18),
    ],
    "TOAN7-BIEUTHUC": [
        ("Cộng các đơn thức KHÔNG đồng dạng: 2x + 3y = 5xy", "2x + 3y = 5xy", 52),
        ("Bình phương tổng thiếu hạng tử kép: (a+b)² = a² + b²", "(a+b)² = a² + b²", 71),
    ],
    "TOAN7-TAMGIAC": [
        ("Áp dụng bất đẳng thức tam giác sai chiều (chỉ so 1 cặp cạnh)", "3, 4, 8 lập được tam giác", 33),
        ("Nhầm trường hợp bằng nhau c.g.c với g.c.g (góc không xen giữa)", "dùng c.g.c với góc không xen giữa", 27),
    ],
    "TOAN8-PHANTHUC": [
        ("Rút gọn phân thức bằng cách gạch hạng tử ở tử và mẫu", "(x+2)/(x+3) = 2/3", 49),
        ("Quy đồng thiếu điều kiện xác định của mẫu", "quên x ≠ 3", 38),
    ],
    "TOAN8-HAMSO": [
        ("Nhầm hệ số góc với tung độ gốc trong y = ax + b", "y = 2x + 3 có hệ số góc 3", 42),
        ("Cho rằng đồ thị y = ax luôn đi qua điểm (1; 0)", "(1; 0) thuộc y = 2x", 19),
    ],
    "TOAN8-DONGDANG": [
        ("Tỉ số diện tích hai tam giác đồng dạng bằng tỉ số đồng dạng (quên bình phương)", "S1/S2 = k", 45),
        ("Ghép cặp cạnh tương ứng sai khi viết tỉ lệ đồng dạng", "AB/DE = BC/DF", 29),
    ],
    "TOAN9-PHUONGTRINH": [
        ("Chia hai vế cho biểu thức chứa ẩn làm mất nghiệm", "x² = 3x -> x = 3", 56),
        ("Quên điều kiện xác định khi giải phương trình chứa ẩn ở mẫu", "nhận nghiệm làm mẫu bằng 0", 48),
    ],
    "TOAN9-HAMSOBAC2": [
        ("Cho rằng y = ax² luôn đồng biến khi a > 0 (quên xét x < 0)", "a > 0 thì hàm luôn đồng biến", 37),
        ("Tính delta sai dấu: Δ = b² + 4ac", "Δ = b² + 4ac", 51),
    ],
    "TOAN9-DUONGTRON": [
        ("Nhầm góc nội tiếp với góc ở tâm cùng chắn một cung (bằng nhau)", "góc nội tiếp = góc ở tâm", 40),
        ("Cho rằng tiếp tuyến cắt đường tròn tại 2 điểm", "tiếp tuyến có 2 giao điểm", 15),
    ],
}


def main() -> None:
    db = SessionLocal()
    try:
        admin = db.execute(select(User).where(User.role == enums.UserRole.ADMIN)).scalars().first()
        if admin is None:
            print("Không tìm thấy ADMIN — chạy scripts/create_admin.py trước.")
            sys.exit(1)
        subject = db.execute(
            select(Subject).where(Subject.code == "TOAN", Subject.school_id == admin.school_id)
        ).scalar_one_or_none()
        if subject is None:
            print("Thiếu môn TOAN — kiểm tra seed subjects.")
            sys.exit(1)

        created, skipped = 0, 0
        for code, entries in _DATA.items():
            unit = db.execute(
                select(CurriculumUnit).where(CurriculumUnit.subject_id == subject.id, CurriculumUnit.code == code)
            ).scalar_one_or_none()
            if unit is None:
                print(f"  ! bỏ qua {code}: chưa có curriculum_unit (chạy seed_demo_question_bank.py trước)")
                continue
            for description, example_wrong, evidence in entries:
                exists = db.execute(
                    select(Misconception).where(
                        Misconception.unit_id == unit.id, Misconception.description == description
                    )
                ).scalar_one_or_none()
                if exists:
                    skipped += 1
                    continue
                db.add(
                    Misconception(
                        school_id=admin.school_id,
                        subject_id=subject.id,
                        unit_id=unit.id,
                        grade_number=unit.grade_number,
                        description=description,
                        example_wrong=example_wrong,
                        evidence_count=evidence,
                    )
                )
                created += 1
        db.commit()
        print(f"Hoàn tất: +{created} misconception, bỏ qua {skipped} (đã có).")
    finally:
        db.close()


if __name__ == "__main__":
    main()
