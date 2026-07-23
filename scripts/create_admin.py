"""Tạo tài khoản ADMIN khởi tạo (idempotent).

Dùng:
    python scripts/create_admin.py --email admin@truong.edu.vn --password "MatKhau123"
"""

import argparse
import sys

from sqlalchemy import select

from src.core.security import hash_password
from src.db.session import SessionLocal
from src.models import enums
from src.models.tables import User

DEFAULT_SO_SCHOOL_ID = 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Tạo tài khoản ADMIN.")
    parser.add_argument("--email", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--name", default="Quản trị viên")
    parser.add_argument("--so-school-id", type=int, default=DEFAULT_SO_SCHOOL_ID)
    args = parser.parse_args()

    db = SessionLocal()
    try:
        if db.execute(select(User).where(User.email == args.email)).scalar_one_or_none():
            print(f"[BỎ QUA] Tài khoản {args.email} đã tồn tại.")
            return 0
        user = User(
            so_school_id=args.so_school_id,
            email=args.email,
            hashed_password=hash_password(args.password),
            full_name=args.name,
            role=enums.UserRole.ADMIN,
        )
        db.add(user)
        db.commit()
        print(f"[OK] Đã tạo ADMIN: {args.email}")
        return 0
    finally:
        db.close()



if __name__ == "__main__":
    sys.exit(main())
