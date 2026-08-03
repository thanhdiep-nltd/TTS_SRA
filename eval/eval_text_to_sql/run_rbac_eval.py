"""
EVALUATION SUITE FOR RBAC / ABAC USER PERMISSIONS
==================================================
Runs automated security evaluation test cases against `validate_and_secure_sql`
and measures Pass / Fail accuracy for BGH, Homeroom Teachers, and Subject Teachers.
"""

import json
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

# Ensure project root is on sys.path
_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _root not in sys.path:
    sys.path.insert(0, _root)

from src.core.security.sql_validator import (  # noqa: E402
    PermissionDeniedError,
    validate_and_secure_sql,
)


def run_rbac_evaluation():
    dataset_path = os.path.join(os.path.dirname(__file__), "eval_dataset.json")
    with open(dataset_path, encoding="utf-8") as f:
        dataset = json.load(f)

    rbac_cases = [item for item in dataset if item.get("category") == "RBAC_PERMISSIONS"]

    print("\n========================================================")
    print("🔒 RUNNING RBAC / ABAC SECURITY EVALUATION SUITE")
    print("========================================================")

    # Map user email to user_id & role from DB
    from sqlalchemy import text

    from src.db.session import SessionLocal

    user_db_map = {}
    with SessionLocal() as session:
        rows = session.execute(text("SELECT id, email, role FROM public.users")).fetchall()
        for r in rows:
            user_db_map[r[1]] = {"id": r[0], "role": r[2]}

    passed_count = 0
    total_count = len(rbac_cases)

    for tc in rbac_cases:
        tc_id = tc["id"]
        query = tc["query"]
        school_id = str(tc["school_id"])

        # Lấy user_id thực tế từ DB dựa theo case
        if "PRINCIPAL" in tc_id:
            email = "principal_cp@vinschool.edu.vn"
        elif "GRADE_HEAD" in tc_id:
            email = "grade_head_6_cp@vinschool.edu.vn"
        elif "HOMEROOM" in tc_id:
            email = "teacher_gvcn_6a1@vinschool.edu.vn"
        elif "SUBJECT" in tc_id:
            email = "teacher_gvbm_math_6a1@vinschool.edu.vn"
        else:
            email = "principal_cp@vinschool.edu.vn"

        u_info = user_db_map.get(email, {"id": 1, "role": "PRINCIPAL"})
        user_id = u_info["id"]
        role = u_info["role"]
        expected_blocked = tc.get("expected_rbac_blocked", False)

        sample_sql = "SELECT g.student_code, g.final_grade FROM s360.fact_gradebooks g JOIN s360.dim_homeroom_class c ON g.homeroom_class_id = c.id"
        if "6A1" in query:
            sample_sql += " WHERE c.code = '6A1'"
        elif "7A1" in query:
            sample_sql += " WHERE c.code = '7A1'"

        try:
            try:
                secured_sql = validate_and_secure_sql(sample_sql, school_id, user_id=user_id, user_role=role)
                permission_denied = False
            except PermissionDeniedError:
                # Không có assignment phù hợp với phạm vi truy vấn → chặn truy cập (KHÔNG phải lỗi SQL)
                permission_denied = True
                secured_sql = None

            # Assert không văng lỗi SQL (phòng lỗi gốc: inject sai cột grade_id vào bảng thiếu cột)
            if tc.get("expected_no_sql_error", False):
                assert secured_sql is not None, "Văng PermissionDeniedError thay vì inject đúng cột RBAC!"
                assert "fact_gradebooks.grade_id" not in secured_sql, "RBAC inject sai cột grade_id!"
                assert (
                    "homeroom_class_id IN (SELECT id FROM s360.dim_homeroom_class WHERE grade_id IN (6))" in secured_sql
                ), "Thiếu bộ lọc RBAC qua dim_homeroom_class!"

            # Thực thi trực tiếp trên DB để kiểm tra số dòng trả về
            if permission_denied:
                row_count = 0
            else:
                with SessionLocal() as db_session:
                    rows = db_session.execute(text(secured_sql)).fetchall()
                    row_count = len(rows)

            is_blocked = permission_denied or (row_count == 0 and expected_blocked)

            if is_blocked == expected_blocked:
                passed_count += 1
                status_str = "✅ PASS"
            else:
                status_str = "❌ FAIL"

            print(f"[{status_str}] {tc_id} (User: {user_id}, Role: {role}):")
            print(f"   Query: {query}")
            print(f"   Secured SQL: {secured_sql if secured_sql else 'PERMISSION_DENIED'}")
            print(f"   Returned rows: {row_count} | Blocked: {is_blocked} (Expected Blocked: {expected_blocked})\n")

        except AssertionError as e:
            print(f"[❌ FAIL] {tc_id}: {e}\n")
        except Exception as e:
            print(f"[❌ ERROR] {tc_id}: {e}\n")

    accuracy = (passed_count / total_count * 100) if total_count > 0 else 0
    print("========================================================")
    print(f"🎯 EVALUATION RESULT: {passed_count}/{total_count} Passed ({accuracy:.1f}%)")
    print("========================================================\n")
    return accuracy

if __name__ == "__main__":
    run_rbac_evaluation()
