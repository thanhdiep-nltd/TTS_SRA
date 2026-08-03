# -*- coding: utf-8 -*-
"""Probe: tài khoản TRƯỞNG KHỐI 6 hỏi 'điểm lớp 6A1 Văn học kỳ 2' —
6A1 THUỘC khối 6 (TRONG phạm vi quyền), nhưng hệ thống trả lời ảo giác
'Các truy vấn liên tiếp đều bị cắt ở giữa / danh sách chưa hiển thị đầy đủ'.

Mục tiêu: xác thực ground truth để phân biệt giả thuyết:
  H1: hệ thống KHÔNG có dữ liệu 6A1/Ngữ văn/HK2 (trong fact_gradebooks_moet)
  H2: statement_timeout=5000ms làm truy vấn bị hủy giữa chừng -> 'bị cắt ở giữa'
  H3: không lọc môn -> số dòng quá lớn + LIMIT -> 'chưa hiển thị đầy đủ'
  H4: LLM Tier 2 tự bịa chuyện (không do data/timeout)
"""
import json
import time

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
        # ---------- [1] Tìm user trưởng khối 6 ----------
        rows = s.execute(
            text("""
                SELECT ta.user_id, ta.grade_id, ta.role_context::text
                FROM public.teacher_assignments ta
                WHERE ta.is_active = true AND ta.role_context::text ILIKE '%GRADE_HEAD%'
                ORDER BY ta.user_id, ta.grade_id
            """)
        ).fetchall()
        print("=== [1] User có phân công GRADE_HEAD ===")
        target_user = None
        for r in rows:
            print(f"  user_id={r[0]} grade_id={r[1]} role_context={r[2]}")
            if target_user is None and str(r[1]) == "6":
                target_user = r[0]
        if target_user is None:
            print("  KHÔNG tìm thấy user trưởng khối 6 -> dừng.")
            return
        rbac = get_user_assignment_constraints(target_user, "GRADE_HEAD")
        print(f"  -> user probe = {target_user}")
        print("  rbac_meta =", json.dumps(rbac, ensure_ascii=False, indent=2))

        # ---------- [2] Lớp 6A1 ----------
        c6 = s.execute(
            text("""
                SELECT id, code, fullname, grade_id
                FROM s360.dim_homeroom_class
                WHERE so_school_id = 1 AND (code ILIKE '6A1' OR fullname ILIKE '%6A1%')
                ORDER BY id LIMIT 10
            """)
        ).fetchall()
        print("\n=== [2] Lớp khớp '6A1' ===")
        class_id_6a1 = None
        for r in c6:
            print(f"  id={r[0]} code={r[1]} fullname={r[2]} grade_id={r[3]}")
            if class_id_6a1 is None:
                class_id_6a1 = r[0]

        # ---------- [3] Môn khớp 'văn' ----------
        subs = s.execute(
            text("SELECT id, name FROM s360.dim_subject WHERE name ILIKE '%văn%' ORDER BY id LIMIT 20")
        ).fetchall()
        print("\n=== [3] Môn khớp 'văn' ===")
        van_ids = []
        for r in subs:
            print(f"  id={r[0]} name={r[1]}")
            van_ids.append(r[0])

        # ---------- [4] GROUND TRUTH: dữ liệu 6A1 HK2 ----------
        if class_id_6a1 is not None:
            print(f"\n=== [4] GROUND TRUTH: lớp id={class_id_6a1} (6A1) ===")
            q4a = s.execute(
                text("""
                    SELECT g.subject_id, s.name, COUNT(*) AS n_rows,
                           COUNT(DISTINCT g.student_code) AS n_students,
                           COUNT(DISTINCT g.gradebook_type_item_id) AS n_items,
                           MIN(g.final_grade) AS min_g, MAX(g.final_grade) AS max_g
                    FROM s360.fact_gradebooks_moet g
                    JOIN s360.dim_subject s ON g.subject_id = s.id
                    WHERE g.so_school_id = 1 AND g.homeroom_class_id = :cid
                      AND g.semester_index = 2
                    GROUP BY g.subject_id, s.name
                    ORDER BY n_rows DESC
                """),
                {"cid": class_id_6a1},
            ).fetchall()
            print("  fact_gradebooks_moet HK2 (theo môn):")
            for r in q4a:
                print(f"    subject_id={r[0]} name={r[1]} rows={r[2]} students={r[3]} items={r[4]} min_g={r[5]} max_g={r[6]}")

            if van_ids:
                vids_ph = ", ".join(map(str, van_ids))
                q4b = s.execute(
                    text(f"""
                        SELECT COUNT(*) AS n_rows, COUNT(DISTINCT g.student_code) AS n_students,
                               COUNT(DISTINCT g.gradebook_type_item_id) AS n_items
                        FROM s360.fact_gradebooks_moet g
                        WHERE g.so_school_id = 1 AND g.homeroom_class_id = :cid
                          AND g.semester_index = 2 AND g.subject_id IN ({vids_ph})
                    """),
                    {"cid": class_id_6a1},
                ).fetchone()
                print(f"  -> Ngữ văn HK2 (subject IN {van_ids}): rows={q4b[0]} students={q4b[1]} items={q4b[2]}")

            # năm học hiện diện
            yrs = s.execute(
                text("""
                    SELECT DISTINCT g.school_year_id, g.semester_index
                    FROM s360.fact_gradebooks_moet g
                    WHERE g.so_school_id = 1 AND g.homeroom_class_id = :cid
                    ORDER BY g.school_year_id, g.semester_index
                """),
                {"cid": class_id_6a1},
            ).fetchall()
            print("  (school_year_id, semester_index) có dữ liệu:")
            for r in yrs:
                print(f"    year={r[0]} sem={r[1]}")

            # fact_gradebooks (Vinschool) 6A1 HK2 — xác nhận prompt 'Ngữ văn không nằm ở đây'
            q4c = s.execute(
                text("""
                    SELECT g.subject_id, s.name, COUNT(*) AS n_rows, COUNT(DISTINCT g.student_code) AS n_students
                    FROM s360.fact_gradebooks g
                    JOIN s360.dim_subject s ON g.subject_id = s.id
                    WHERE g.so_school_id = 1 AND g.homeroom_class_id = :cid AND g.semester_index = 2
                    GROUP BY g.subject_id, s.name ORDER BY n_rows DESC
                """),
                {"cid": class_id_6a1},
            ).fetchall()
            print("  fact_gradebooks (Vinschool) HK2 (theo môn):")
            for r in q4c:
                print(f"    subject_id={r[0]} name={r[1]} rows={r[2]} students={r[3]}")

        # ---------- [5] TEMPLATE path (ground truth 'câu truy vấn đúng') ----------
        current_user_school_id.set(1)
        current_user_role.set("GRADE_HEAD")
        current_user_id.set(target_user)
        from src.agents.data_service_agent.tools import get_class_grades

        print("\n=== [5] Template path: get_class_grades('6A1', semester=2, subject='Văn') ===")
        tpl = get_class_grades.invoke({"class_name": "6A1", "semester": 2, "subject": "Văn"})
        print("  ->", tpl[:900])

        # ---------- [6] DYNAMIC SQL path (giả lập SQL mà Tier 2 sinh theo prompt) ----------
        # SQL theo Ví dụ 1 của prompt: fact_gradebooks_moet + subject_id filter
        raw_van = f"""
            SELECT fgm.student_code, st.student_name, sub.name AS subject_name,
                   dem.gradebook_type_items_fullname AS exam_name, fgm.final_grade
            FROM s360.fact_gradebooks_moet fgm
            LEFT JOIN s360.dim_homeroom_class_student st ON fgm.student_code = st.student_code AND fgm.homeroom_class_id = st.homeroom_class_id
            LEFT JOIN s360.dim_subject sub ON fgm.subject_id = sub.id
            LEFT JOIN s360.dim_exam_moet dem ON fgm.gradebook_type_item_id = dem.gradebook_type_item_id
            WHERE fgm.so_school_id = 1 AND fgm.homeroom_class_id = {class_id_6a1}
              AND fgm.semester_index = 2 AND fgm.subject_id = {van_ids[0] if van_ids else 2}
        """
        # Cùng SQL nhưng KHÔNG lọc môn -> đo số dòng nếu LLM quên filter môn (H3)
        raw_no_subj = raw_van.split("AND fgm.subject_id")[0].rstrip() + "\n"

        for label, raw in (("lọc môn Văn (đúng)", raw_van), ("KHÔNG lọc môn", raw_no_subj)):
            print(f"\n=== [6] Dynamic SQL path ({label}) — max_rows=2000 (như tool Tier 2) ===")
            try:
                t0 = time.perf_counter()
                secured = validate_and_secure_sql(raw, "1", user_id=target_user, user_role="GRADE_HEAD", max_rows=2000)
                t1 = time.perf_counter()
                print(f"  validate_and_secure_sql OK ({t1 - t0:.3f}s)")
                print("  LIMIT trong secured:", "LIMIT 2000" if "LIMIT 2000" in secured else
                      ("LIMIT 100" if "LIMIT 100" in secured else "không có LIMIT"))
                with engine.connect() as conn:
                    conn.execute(text("SET statement_timeout = 5000;"))
                    t2 = time.perf_counter()
                    result = conn.execute(text(secured))
                    rows_out = result.fetchall()
                    t3 = time.perf_counter()
                print(f"  -> SỐ DÒNG = {len(rows_out)}  (thực thi {t3 - t2:.3f}s)")
                if rows_out:
                    print("  -> dòng đầu:", dict(rows_out[0]._mapping) if hasattr(rows_out[0], "_mapping") else rows_out[0])
            except PermissionDeniedError as e:
                print(f"  -> PermissionDeniedError: {e}")
            except Exception as e:
                print(f"  -> LỖI: {type(e).__name__}: {e}")

        # ---------- [7] execute_read_only_query (đúng đường dẫn Tier 2) ----------
        from src.agents.data_service_agent.tools import execute_read_only_query

        print("\n=== [7] execute_read_only_query (lọc môn Văn HK2) ===")
        tool_res = execute_read_only_query.invoke({"sql_query": raw_van})
        try:
            parsed = json.loads(tool_res)
            print(f"  -> SỐ DÒNG JSON = {len(parsed)}")
            print("  -> dòng đầu:", parsed[0] if parsed else "[]")
        except Exception:
            print("  -> (không phải JSON list):", tool_res[:900])


if __name__ == "__main__":
    main()
