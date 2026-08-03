# -*- coding: utf-8 -*-
"""Mô phỏng query /raw của HS160051 môn 106 với cutoff=2025-10-20 (sau fix)."""
import os
import sys

import psycopg

sys.stdout.reconfigure(encoding="utf-8")

url = os.environ.get("DATABASE_URL") or "postgresql://postgres:postgres@localhost:5432/neondb"

with psycopg.connect(url) as conn:
    with conn.cursor() as cur:
        # Lấy context học sinh
        cur.execute("""
            SELECT DISTINCT ON (student_code) student_code, so_school_id, grade_id, join_date
            FROM s360.dim_homeroom_class_student
            WHERE student_code = 'HS160051' AND school_year_id = 2025
            ORDER BY student_code, is_active DESC, homeroom_class_id
        """)
        sg = cur.fetchone()
        print("Context:", sg)
        sc, school_id, gid, jdate = sg[0], sg[1], sg[2], sg[3] or "2025-09-05"

        cutoff = "2025-10-20"  # cutoff_date thật của tuần 8 (sau fix)

        cur.execute("""
            SELECT dsa.code, dsa.due_date, fag.final_grade, (fag.id IS NOT NULL) AS submitted
            FROM s360.dim_so_assignment dsa
            LEFT JOIN s360.fact_so_assignment_grade fag
                ON fag.assignment_id = dsa.assignment_id AND fag.student_code = %s
            WHERE dsa.subject_id = 106
              AND dsa.semester_index = 1
              AND dsa.so_school_id = %s
              AND dsa.grade_id = %s
              AND dsa.due_date <= CAST(%s AS DATE)
              AND dsa.due_date >= CAST(%s AS DATE)
            ORDER BY dsa.due_date, dsa.assignment_id
        """, (sc, school_id, gid, cutoff, jdate))
        rows = cur.fetchall()
        print(f"\n/raw với cutoff={cutoff} → {len(rows)} bài (W14 hạn 12/12 KHÔNG còn xuất hiện):")
        for r in rows:
            print(f"  {r[0]} | hạn {r[1]} | final={r[2]} | submitted={r[3]}")
