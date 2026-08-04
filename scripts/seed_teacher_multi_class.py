"""Thêm tài khoản giáo viên dạy NHIỀU LỚP để test RBAC (Dashboard EWS / Chatbot).

Idempotent: chạy lại an toàn (ON CONFLICT DO NOTHING). Không reset dữ liệu.

Tài khoản tạo:
  email     : teacher_gvbm_math_multi@vinschool.edu.vn
  password  : password123
  role      : SUBJECT_TEACHER
  phân công : môn Toán (subject_id=106) ở các lớp 6A1, 6A2, 7A1 (so_school_id=1)
"""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from sqlalchemy import text  # noqa: E402

from src.core.security import hash_password  # noqa: E402
from src.db.session import SessionLocal  # noqa: E402

EMAIL = "teacher_gvbm_math_multi@vinschool.edu.vn"
FULL_NAME = "Đỗ Minh Quân (GVBM Toán nhiều lớp)"
ROLE = "SUBJECT_TEACHER"
SUBJECT_ID = 106  # Toán học Khối 6
CLASS_NAMES = ["6A1", "6A2", "7A1"]
SCHOOL_ID = 1
ACADEMIC_YEAR = 2025


def main() -> None:
    with SessionLocal() as s:
        # 1. Tạo user nếu chưa có
        s.execute(
            text(
                """
                INSERT INTO public.users (so_school_id, email, hashed_password, full_name, role, is_active)
                VALUES (:sid, :email, :hpwd, :fname, CAST(:role AS public.user_role_enum), true)
                ON CONFLICT (email) DO NOTHING
                """
            ),
            {
                "sid": SCHOOL_ID,
                "email": EMAIL,
                "hpwd": hash_password("password123"),
                "fname": FULL_NAME,
                "role": ROLE,
            },
        )
        s.commit()

        user_id = s.execute(text("SELECT id FROM public.users WHERE email = :e"), {"e": EMAIL}).scalar()
        if user_id is None:
            print("❌ Không tìm thấy user vừa tạo.")
            return

        # 2. Lấy class_id thật theo fullname
        name_ph = ", ".join(f":n{i}" for i in range(len(CLASS_NAMES)))
        name_params = {f"n{i}": c for i, c in enumerate(CLASS_NAMES)}
        class_rows = s.execute(
            text(
                f"""
                SELECT id, fullname FROM s360.dim_homeroom_class
                WHERE so_school_id = :sid AND fullname IN ({name_ph})
                """
            ),
            {"sid": SCHOOL_ID, **name_params},
        ).fetchall()
        class_map = {r[1]: r[0] for r in class_rows}

        # 3. Gán phân công SUBJECT_TEACHER cho từng lớp
        added = 0
        for cname in CLASS_NAMES:
            cid = class_map.get(cname)
            if cid is None:
                print(f"   ⚠️ Không tìm thấy lớp {cname} (so_school_id={SCHOOL_ID}) — bỏ qua.")
                continue
            s.execute(
                text(
                    """
                    INSERT INTO public.teacher_assignments
                        (user_id, academic_year_id, role_context, class_id, grade_id, subject_id, is_active)
                    VALUES
                        (:uid, :ay, CAST(:rc AS public.role_context_enum), :cid, NULL, :sub, true)
                    ON CONFLICT DO NOTHING
                    """
                ),
                {"uid": user_id, "ay": ACADEMIC_YEAR, "rc": "SUBJECT_TEACHER", "cid": cid, "sub": SUBJECT_ID},
            )
            added += 1
        s.commit()

        print(
            f"✅ Đã tạo/đảm bảo user {EMAIL} (id={user_id}) với {added} phân công môn Toán (subject_id={SUBJECT_ID})."
        )
        print("   Lớp: " + ", ".join(CLASS_NAMES))
        print("   Mật khẩu: password123")


if __name__ == "__main__":
    main()
