"""Seed MOCK thống kê thực nghiệm (p_value, discrimination, times_used) cho câu Toán APPROVED — DEMO
vòng hiệu chỉnh kho câu (calibration loop). Random THEO SEED cố định để demo tái lập; ép sẵn vài
ca "xấu" (discrimination âm, độ khó lệch dự đoán) cho màn trình diễn.
Chạy: python scripts/seed_item_stats_toan.py
"""

import random
import sys
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from src.db.session import SessionLocal
from src.models import enums
from src.models.tables import QuestionItem, Subject, User

_RNG = random.Random(20260703)


def main() -> None:
    db = SessionLocal()
    try:
        admin = db.execute(select(User).where(User.role == enums.UserRole.ADMIN)).scalars().first()
        if admin is None:
            print("Không tìm thấy ADMIN.")
            sys.exit(1)
        subject = db.execute(
            select(Subject).where(Subject.code == "TOAN", Subject.school_id == admin.school_id)
        ).scalar_one_or_none()
        if subject is None:
            print("Thiếu môn TOAN.")
            sys.exit(1)

        items = list(
            db.execute(
                select(QuestionItem)
                .where(
                    QuestionItem.subject_id == subject.id,
                    QuestionItem.status == enums.ItemStatus.APPROVED,
                )
                .order_by(QuestionItem.created_at, QuestionItem.id)
            )
            .scalars()
            .all()
        )
        if not items:
            print("Chưa có câu APPROVED môn Toán — duyệt vài câu trước (scripts/approve_pending_questions_demo.py).")
            sys.exit(1)

        for i, qi in enumerate(items):
            # mặc định: độ khó thực nghiệm xoay quanh proxy Bloom, phân biệt tốt
            target_p = max(0.1, min(0.95, 1.0 - qi.bloom_level / 6.0 + _RNG.uniform(-0.12, 0.12)))
            qi.p_value = round(target_p, 3)
            qi.discrimination = round(_RNG.uniform(0.25, 0.55), 3)
            qi.times_used = _RNG.randint(1, 4)
            qi.exposure_at = datetime.now(UTC) - timedelta(days=_RNG.randint(10, 120))
            # ép ca demo: câu 1 phân biệt ÂM (HS giỏi sai nhiều hơn), câu 2 độ khó lệch xa dự đoán
            if i == 0:
                qi.discrimination = -0.18
            if i == 1:
                qi.p_value = 0.15 if qi.bloom_level <= 2 else 0.95
        db.commit()
        print(f"Đã mock thống kê cho {len(items)} câu Toán APPROVED (trong đó 2 ca 'xấu' để demo).")
    finally:
        db.close()


if __name__ == "__main__":
    main()
