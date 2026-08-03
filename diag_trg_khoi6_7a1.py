# -*- coding: utf-8 -*-
"""Probe: tài khoản TRƯỞNG KHỐI 6 hỏi điểm lớp 7A1 (ngoài phạm vi) —
mục tiêu xác minh đường dẫn nào trả '0 dòng / không có dữ liệu' thay vì ACCESS_DENIED.
"""
import json

from sqlalchemy import text

from src.agents.context import current_user_id, current_user_role, current_user_school_id
from src.core.security.sql_validator import (
    PermissionDeniedError,
    get_user_assignment_constraints,
    validate_and_secure_sql,
)
from src.db.session import SessionLocal, engine


def main() -> None:
    with SessionLocal() as s:
        # 1. Danh sách user có phân công GRADE_HEAD
        rows = s.execute(
            text("""
                SELECT ta.user_id, ta.grade_id, ta.role_context::text
                FROM public.teacher_assignments ta
                WHERE ta.is_active = true AND ta.role_context::text ILIKE '%GRADE_HEAD%'
                ORDER BY ta.user_id, ta.grade_id
            """)
        ).fetchall()
        print("=== [1] User có phân công GRADE_HEAD ===")
        grade_head_users = []
        for r in rows:
            print(f"  user_id={r[0]} grade_id={r[1]} role_context={r[2]}")
            if r[0] not in grade_head_users:
                grade_head_users.append(r[0])

        # 2. Lớp 7A1 -> grade nào?
        c7 = s.execute(
            text("""
                SELECT id, code, fullname, grade_id
                FROM s360.dim_homeroom_class
                WHERE so_school_id = 1 AND (code ILIKE '7A1' OR fullname ILIKE '%7A1%')
                ORDER BY id LIMIT 10
            """)
        ).fetchall()
        print("\n=== [2] Lớp khớp '7A1' ===")
        for r in c7:
            print(f"  id={r[0]} code={r[1]} fullname={r[2]} grade_id={r[3]}")

        # 3. Môn Toán
        subj = s.execute(
            text("SELECT id, name FROM s360.dim_subject WHERE name ILIKE '%toán%' ORDER BY id LIMIT 10")
        ).fetchall()
        print("\n=== [3] Môn khớp 'toán' ===")
        for r in subj:
            print(f"  id={r[0]} name={r[1]}")

        # 4. Chọn user trưởng khối 6 (grade_id = 6)
        target_user = None
        target_grade = None
        for r in rows:
            if str(r[1]) == "6":
                target_user = r[0]
                target_grade = r[1]
                break
        if target_user is None and grade_head_users:
            target_user = grade_head_users[0]
            # xem grade_ids thực sự
            rbac0 = get_user_assignment_constraints(target_user, "GRADE_HEAD")
            target_grade = rbac0.get("grade_ids", [])
        print(f"\n=== [4] Chọn user probe: user_id={target_user} grade_target={target_grade} ===")

        if target_user is None:
            print("KHÔNG tìm thấy user trưởng khối -> không thể repro. Kiểm tra teacher_assignments.")
            return

        rbac = get_user_assignment_constraints(target_user, "GRADE_HEAD")
        print("  rbac_meta =", json.dumps(rbac, ensure_ascii=False, indent=2))

        # 5. Đường dẫn TEMPLATE: get_class_grades("7A1", subject='Toán')
        current_user_school_id.set(1)
        current_user_role.set("GRADE_HEAD")
        current_user_id.set(target_user)
        from src.agents.data_service_agent.tools import get_class_grades

        print("\n=== [5] Template path: get_class_grades('7A1', semester=2, subject='Toán') ===")
        tpl_res = get_class_grades.invoke({"class_name": "7A1", "semester": 2, "subject": "Toán"})
        print("  ->", tpl_res[:600])

        # 6. Đường dẫn DYNAMIC SQL: validate_and_secure_sql trên truy vấn 7A1/Toán
        raw = """
            SELECT g.student_code, s.name AS subject_name, c.fullname AS class_name,
                   g.semester_index, g.final_grade
            FROM s360.fact_gradebooks_moet g
            JOIN s360.dim_homeroom_class c ON g.homeroom_class_id = c.id
            JOIN s360.dim_subject s ON g.subject_id = s.id
            WHERE g.so_school_id = 1
              AND (c.code ILIKE '7A1' OR c.fullname ILIKE '%7A1%')
              AND s.name ILIKE '%toán%'
              AND g.semester_index = 2
        """
        print("\n=== [6] Dynamic SQL path: validate_and_secure_sql (7A1/Toán HK2) ===")
        try:
            secured = validate_and_secure_sql(raw, "1", user_id=target_user, user_role="GRADE_HEAD")
            print("  secured SQL (không raise!):")
            print("  ", secured)
            with engine.connect() as conn:
                conn.execute(text("SET statement_timeout = 5000;"))
                result = conn.execute(text(secured))
                rows_out = result.fetchall()
            print(f"  -> SỐ DÒNG = {len(rows_out)}")
        except PermissionDeniedError as e:
            print(f"  -> PermissionDeniedError: {e}")
        except Exception as e:
            print(f"  -> LỖI khác: {type(e).__name__}: {e}")

        # 7. So sánh hành vi tool execute_read_only_query với cùng truy vấn
        from src.agents.data_service_agent.tools import execute_read_only_query

        print("\n=== [7] execute_read_only_query (cùng truy vấn) ===")
        tool_res = execute_read_only_query.invoke({"sql_query": raw})
        print("  ->", tool_res[:800])


if __name__ == "__main__":
    main()
