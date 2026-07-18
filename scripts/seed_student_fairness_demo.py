"""Seed demo cho cảnh báo công bằng đánh giá (student_fairness) ở cấp 2 (THCS, khối 6-9).

Dữ liệu điểm THCS hiện có quá đồng đều (độ lệch TX vs GK/CK chỉ dao động ±0.6 toàn trường) nên
KHÔNG có học sinh nào tự nhiên đạt ngưỡng cảnh báo (gap >= 3.0 điểm + TX/Periodic vượt 8.0/5.0 -
xem `src/services/student_fairness.py`). Script này chỉnh CHÍNH XÁC vài điểm số (theo `score.id`,
không tạo học sinh/điểm giả mới) của 2 học sinh CÓ SẴN trong dữ liệu demo để dựng 2 case:

- FAVORITISM: Mai Văn Khang, GDCD, lớp 8A1 — TX cao (8.5) trên đề TX đã được nâng CDI lên ~0.65
  (khó), GK/CK (đề chung khối, CDI ~0.49, không khó hơn) lại thấp (4.33) -> nghi "tủ đề" TX.
- SUPPRESSION: Nguyễn Ngọc Bình, Toán, lớp 9A4 — TX thấp (4.33), GK/CK (đề chung, không ai ưu ái)
  lại cao (~8.57) -> nghi học sinh bị đánh giá thấp bất công ở TX.

CHỈ update giá trị của các `score.id` đã xác định sẵn (điểm demo/mock có sẵn, không phải học sinh
thật) + CDI của các exam_papers `[MOCK]%` liên quan (đã được phép đụng tới theo quy ước ở
scripts/mock_cdi_secondary.py). KHÔNG tạo học sinh/lớp/điểm mới.

Idempotent: chạy lại nhiều lần ra cùng kết quả (luôn SET về đúng giá trị cố định, không cộng dồn).
Chạy: python scripts/seed_student_fairness_demo.py
"""

from sqlalchemy import text

from src.db.session import SessionLocal

# ============================================================
# CASE 1 — SUSPECT_FAVORITISM (Mai Văn Khang, GDCD, lớp 8A1, Khối 8)
# ============================================================
_FAVORITISM_TX_SCORES = {
    "8259447a-f28a-4897-b5cd-df746708c016": 8.5,
    "36a8528c-2939-49a4-a4cc-e8635b46d9c6": 9.0,
    "8c736e11-d908-430d-91b6-fc5682628148": 8.5,
    "0e19b5e2-a000-4d42-9cde-8bdfc37763b4": 8.0,
}  # avg = 8.5 (>=8.0)

_FAVORITISM_PERIODIC_SCORES = {
    "0ec3f174-872f-4e60-80d5-71d67341295b": 4.5,
    "7aae2ce7-d133-48ef-a7e2-f31dbb6b0746": 4.0,
    "dcf29788-88a8-4a61-83a7-c31ff1e720f5": 4.5,
}  # avg = 4.33 (<=5.0)

_FAVORITISM_TX_CDI = {
    "f2c3f59a-4fa1-4710-908c-179214dbee59": 0.65,  # TX1
    "ed5bc1e3-1fec-4e63-af82-451df4472526": 0.60,  # TX2
    "3b97ec56-70d6-47d5-9a35-9fa92d3db673": 0.65,  # TX3
    "9b7c347b-9d90-4c91-9582-04e55c455489": 0.70,  # TX4
}  # avg = 0.65 (>=0.6, "khó") — GK/CK của lớp này đã sẵn CDI ~0.49 (không khó hơn), không cần sửa.

# ============================================================
# CASE 2 — SUSPECT_SUPPRESSION (Nguyễn Ngọc Bình, Toán, lớp 9A4, Khối 9)
# ============================================================
_SUPPRESSION_TX_SCORES = {
    "cf0e2303-d985-4b63-b1a6-1b3b25d280bc": 4.5,
    "2c4ecbd2-d448-4381-83fc-6bedbca147bd": 4.0,
    "919b0dc0-27d2-4361-9a5c-d5dd794dfbc7": 4.5,
}  # avg = 4.33 (<=5.0). SUSPECT_SUPPRESSION không xét CDI, chỉ xét điểm.

_SUPPRESSION_PERIODIC_SCORES = {
    "a9355c35-710f-48ce-b2a7-fffd43aa054d": 8.5,  # MIDTERM cột 1 (trọng số 2)
    "8e0671b8-aa06-4599-941a-d9dda07925b6": 8.0,  # MIDTERM cột 2 (trọng số 2)
    "657a16e6-e048-4ac2-add2-063cd2638560": 9.0,  # FINAL cột 1 (trọng số 3)
}  # weighted avg = (8.5*2+8.0*2+9.0*3)/7 ≈ 8.57 (>=8.0)


def _set_scores(db, values: dict[str, float]) -> int:
    n = 0
    for score_id, value in values.items():
        result = db.execute(text("UPDATE scores SET value = :v WHERE id = :i"), {"v": value, "i": score_id})
        n += result.rowcount
    return n


def _set_cdi(db, values: dict[str, float]) -> int:
    n = 0
    for paper_id, cdi in values.items():
        result = db.execute(
            text("UPDATE exam_papers SET content_difficulty = :c WHERE id = :i AND title LIKE '[MOCK]%'"),
            {"c": cdi, "i": paper_id},
        )
        n += result.rowcount
    return n


def main() -> None:
    db = SessionLocal()
    try:
        n1 = _set_scores(db, _FAVORITISM_TX_SCORES)
        n2 = _set_scores(db, _FAVORITISM_PERIODIC_SCORES)
        n3 = _set_cdi(db, _FAVORITISM_TX_CDI)
        n4 = _set_scores(db, _SUPPRESSION_TX_SCORES)
        n5 = _set_scores(db, _SUPPRESSION_PERIODIC_SCORES)
        db.commit()
        print(
            f"FAVORITISM: {n1} diem TX + {n2} diem GK/CK + {n3} CDI de TX da cap nhat.\n"
            f"SUPPRESSION: {n4} diem TX + {n5} diem GK/CK da cap nhat."
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
