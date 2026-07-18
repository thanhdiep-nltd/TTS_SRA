"""Đồng bộ lại điểm TX/GK/CK (và Miệng) của MỌI học sinh cấp 2 (THCS) quanh 1 "mặt bằng năng
lực" ổn định + nhiễu nhỏ — cho dữ liệu test giống thật hơn (học sinh thật thường có điểm tương
đối nhất quán giữa các loại kiểm tra, không lệch ngẫu nhiên hoàn toàn như dữ liệu sinh thô).

Lý do cần chạy: dữ liệu điểm THCS hiện tại random độc lập theo từng cột điểm -> điểm TX và GK/CK
của CÙNG 1 học sinh không tương quan -> tính năng cảnh báo công bằng đánh giá
(`src/services/student_fairness.py`) bị flag tràn lan (734 HS) chỉ vì nhiễu ngẫu nhiên, không
phải vì học sinh thật bị tiêu cực. Sau khi chạy script này, hầu hết học sinh sẽ về mức bình
thường (KHÔNG bị flag); chạy tiếp `scripts/seed_fairness_demo_cases.py` để cấy lại một vài
trường hợp rõ ràng phục vụ demo.

CHẠY 1 LẦN cho mục đích demo — KHÔNG idempotent theo nghĩa giữ nguyên giá trị cũ (chạy lại sẽ
tiếp tục co điểm quanh mặt bằng hiện tại, vô hại nhưng không cần thiết chạy nhiều lần).
Chạy: python scripts/correlate_secondary_scores.py
"""

from sqlalchemy import text

from src.db.session import SessionLocal

_NOISE_HALF_RANGE = 0.6  # +-0.6 quanh "mặt bằng năng lực" của học sinh trong môn/kỳ đó.

_UPDATE = """
WITH baseline AS (
    SELECT sc.student_id, sc.subject_id, sc.semester_id, AVG(sc.value) AS ability
    FROM scores sc
    JOIN classes c ON c.id = sc.class_id
    JOIN grades g ON g.id = c.grade_id
    WHERE g.school_level = 'SECONDARY' AND sc.status = 'APPROVED'
    GROUP BY sc.student_id, sc.subject_id, sc.semester_id
)
UPDATE scores sc
SET value = LEAST(10, GREATEST(0, ROUND((b.ability + (random() - 0.5) * 2 * :half_range)::numeric, 2)))
FROM baseline b
WHERE sc.student_id = b.student_id AND sc.subject_id = b.subject_id AND sc.semester_id = b.semester_id
  AND sc.status = 'APPROVED'
RETURNING sc.id;
"""


def main() -> None:
    db = SessionLocal()
    try:
        updated = db.execute(text(_UPDATE), {"half_range": _NOISE_HALF_RANGE}).all()
        db.commit()
        print(f"Done. Da dong bo lai {len(updated)} dong diem (THCS, quanh mat bang nang luc tung HS).")
    finally:
        db.close()


if __name__ == "__main__":
    main()
