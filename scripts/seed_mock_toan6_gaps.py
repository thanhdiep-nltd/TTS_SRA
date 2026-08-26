"""Seed mock Toan 6 (subject 106) — Tích hợp EWS & Lỗ Hổng Kiến Thức.

Nguồn dữ liệu:
  - 35 tuần từ `public.teaching_schedules` (Toán 6, HK1 & HK2) -> ~86 bài tập LMS (dim_so_assignment)
  - ~1100 câu hỏi trắc nghiệm chuẩn Bloom 1-6 từ `data/question_templates_toan6.json`
  - 3 phân loại bài tập LMS:
      * Regular (~70% = 60 bài): 10-12 câu từ pool của unit tuần hiện tại (đủ Bloom 1-6)
      * Review (~20% = 17 bài): 15-20 câu tổng hợp từ 2-3 unit trước đó
      * Advanced (~10% = 9 bài): 10-12 câu vận dụng cao (Bloom 4-6)
  - Sinh item-response (lms_question_response) + tính điểm bài tập (fact_so_assignment_grade)
  - Tính toán và upsert `student_unit_mastery` bằng service chuẩn.

Chạy:
    python scripts/seed_mock_toan6_gaps.py
"""

from __future__ import annotations

import json
import os
import random
import sys
from datetime import datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv

if sys.platform.startswith("win"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(dotenv_path=_ROOT / ".env")

DB_URL = os.getenv("DATABASE_URL")
if not DB_URL:
    print("[ERROR] DATABASE_URL is not set in .env")
    sys.exit(1)

sys.path.insert(0, str(_ROOT))
import psycopg  # noqa: E402
from psycopg.types.json import Jsonb  # noqa: E402

from src.services.item_mastery import (  # noqa: E402
    ItemResult,
    finalize_mastery,
)
from src.services.knowledge_gap import UnitWeight, compute_unit_mastery  # noqa: E402

# ============================================================================
# HẰNG SỐ CƠ BẢN
# ============================================================================
SUBJECT_ID = 106  # TOAN_6 (s360.dim_subject)
SO_SCHOOL_ID = 1
SCHOOL_YEAR_ID = 2025
SEMESTER = 1
MAX_GRADE = 10.0

# 4 chương HK1 Toán 6 (curriculum_units cha)
UNITS = [391, 407, 414, 420]
UNIT_NAMES = {391: "SỐ TỰ NHIÊN", 407: "SỐ NGUYÊN", 414: "HÌNH PHẲNG", 420: "THỐNG KÊ"}

# Map đề GK1 -> (unit_cha, weight)
EXAM_COMPETENCIES = [(391, 0.40), (407, 0.30), (414, 0.20), (420, 0.10)]

# Khởi đầu năm học: 2025-09-01 (Tuần 1 HK1)
WEEK_START = datetime(2025, 9, 1, 8, 0, 0)
HK2_START = datetime(2026, 1, 19, 8, 0, 0)

# ============================================================================
# PROFILE HỌC SINH (gán theo rank - thứ tự student_code)
# ============================================================================
# p = {chapter_id: xác suất đúng LMS}, gk = điểm Giữa HK1.
PROFILES: list[dict] = [
    {"name": "GIOI_DEU", "p": {391: 0.95, 407: 0.93, 414: 0.96, 420: 0.97}, "gk": 9.2},
    {"name": "TE_407", "p": {391: 0.90, 407: 0.08, 414: 0.88, 420: 0.90}, "gk": 6.8},
    {"name": "TE_414", "p": {391: 0.88, 407: 0.85, 414: 0.15, 420: 0.87}, "gk": 6.8},
    {"name": "TE_420", "p": {391: 0.90, 407: 0.87, 414: 0.85, 420: 0.05}, "gk": 7.0},
    {"name": "TE_391", "p": {391: 0.10, 407: 0.88, 414: 0.86, 420: 0.90}, "gk": 6.8},
    {"name": "GIAN_LAN", "p": {391: 0.95, 407: 0.95, 414: 0.95, 420: 0.95}, "gk": 4.2, "cheat": True},
    {"name": "LUOI", "p": {391: 0.40, 407: 0.38, 414: 0.40, 420: 0.42}, "gk": 8.6},
    {"name": "HON_HOP", "p": {391: 1.00, 407: 0.60, 414: 0.50, 420: 1.00}, "gk": 7.1},
    {"name": "TB_KHA_1", "p": {391: 0.82, 407: 0.78, 414: 0.80, 420: 0.85}, "gk": 7.6},
    {"name": "TB_KHA_2", "p": {391: 0.76, 407: 0.80, 414: 0.72, 420: 0.80}, "gk": 7.3},
    {"name": "TB_KHA_3", "p": {391: 0.85, 407: 0.72, 414: 0.74, 420: 0.78}, "gk": 7.5},
    {"name": "TB_KHA_4", "p": {391: 0.72, 407: 0.74, 414: 0.76, 420: 0.70}, "gk": 7.0},
    {"name": "TB_1", "p": {391: 0.68, 407: 0.62, 414: 0.66, 420: 0.70}, "gk": 6.6},
    {"name": "NO_LMS", "p": None, "gk": 5.2},
]
AVERAGE_PROFILE = {"name": "TB_TRUNG_BINH", "p": {391: 0.78, 407: 0.74, 414: 0.72, 420: 0.78}, "gk": 7.2}

CONFIDENCE_INT = {"HIGH": 3, "MEDIUM": 2, "LOW": 1, "INSUFFICIENT": 1}
RNG = random.Random(20250901)


def load_question_templates() -> dict[str, dict]:
    """Đọc ngân hàng câu hỏi đã sinh từ file JSON."""
    json_path = _ROOT / "data" / "question_templates_toan6.json"
    if not json_path.exists():
        print(f"[ERROR] Không tìm thấy file {json_path}. Chạy scripts/generate_question_templates.py trước!")
        sys.exit(1)
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    total_qs = sum(len(v.get("questions", [])) for v in data.values())
    print(f"[INFO] Đã nạp {len(data)} bài học với tổng cộng {total_qs} câu hỏi trắc nghiệm từ JSON.")
    return data


def discover_students(cur) -> list[dict]:
    """Học sinh khối 6 trường 1."""
    cur.execute(
        """
        SELECT student_code, homeroom_class_id
        FROM s360.dim_homeroom_class_student
        WHERE so_school_id = %s AND grade_id = 6 AND school_year_id = %s
          AND (is_active IS NULL OR is_active = 1)
        ORDER BY student_code
        """,
        (SO_SCHOOL_ID, SCHOOL_YEAR_ID),
    )
    rows = cur.fetchall()
    if not rows:
        print("[ERROR] Không tìm thấy học sinh khối 6. Cần chạy generate_full_system_mock_v4.py trước!")
        sys.exit(1)
    return [{"student_code": r[0], "homeroom_class_id": r[1]} for r in rows]


def profile_for(rank: int) -> dict:
    if rank < len(PROFILES):
        return PROFILES[rank]
    return AVERAGE_PROFILE


def gd0_cleanup(cur) -> None:
    """GĐ 0 — Xóa dữ liệu cũ subject 106 school 1."""
    print("[GĐ 0] Dọn dữ liệu cũ subject 106...")
    # 1. LMS responses & question bank
    cur.execute("DELETE FROM public.lms_question_response WHERE assignment_id IN (SELECT assignment_id FROM s360.dim_so_assignment WHERE subject_id = %s AND so_school_id = %s);", (SUBJECT_ID, SO_SCHOOL_ID))
    cur.execute("DELETE FROM public.lms_question_unit WHERE question_id IN (SELECT question_id FROM public.lms_question_bank WHERE subject_id = %s AND so_school_id = %s);", (SUBJECT_ID, SO_SCHOOL_ID))
    cur.execute("DELETE FROM public.lms_question_bank WHERE subject_id = %s AND so_school_id = %s;", (SUBJECT_ID, SO_SCHOOL_ID))
    # 2. Assignment grades & assignments
    cur.execute("DELETE FROM s360.fact_so_assignment_grade WHERE assignment_id IN (SELECT assignment_id FROM s360.dim_so_assignment WHERE subject_id = %s AND so_school_id = %s);", (SUBJECT_ID, SO_SCHOOL_ID))
    cur.execute("DELETE FROM s360.dim_so_assignment WHERE subject_id = %s AND so_school_id = %s;", (SUBJECT_ID, SO_SCHOOL_ID))
    # 3. Mastery
    cur.execute("DELETE FROM public.student_unit_mastery WHERE subject_id = %s;", (SUBJECT_ID,))
    # 4. Exam papers
    cur.execute("DELETE FROM public.exam_competencies WHERE exam_paper_id IN (SELECT id FROM public.exam_papers WHERE subject_id = %s);", (SUBJECT_ID,))
    cur.execute("DELETE FROM public.exam_papers WHERE subject_id = %s AND so_school_id = %s;", (SUBJECT_ID, SO_SCHOOL_ID))
    # 5. Gradebooks
    cur.execute("DELETE FROM s360.fact_gradebooks WHERE subject_id = %s AND so_school_id = %s;", (SUBJECT_ID, SO_SCHOOL_ID))


def _split_even_preserving_total(weight: float, n: int) -> list[float]:
    if n <= 0:
        return []
    base = round(weight / n, 3)
    parts = [base] * n
    diff = round(weight - base * n, 3)
    for i in range(n):
        if abs(diff) < 1e-9:
            break
        step = 0.001 if diff > 0 else -0.001
        parts[i] = round(parts[i] + step, 3)
        diff = round(diff - step, 3)
    return parts


def gd1_exam_papers(cur, lessons_by_chapter: dict[int, list[int]]) -> int:
    """GĐ 1 — Tạo 6 đề thi khối 6 (exam_papers) và map competencies đề GK1."""
    print("[GĐ 1] Seed 6 đề khối 6 (exam_papers)...")
    papers = [
        ("Đề thi Giữa kỳ 1 Toán 6 Khối 6 (GK1)", "MIDTERM", 10, 10.0),
        ("Đề thi Cuối kỳ 1 Toán 6 Khối 6 (CK1)", "FINAL", 10, 10.0),
        ("Kiểm tra 15' Toán 6 — Chương 1 Số tự nhiên", "REGULAR", 5, 5.0),
        ("Kiểm tra 15' Toán 6 — Chương 2 Số nguyên", "REGULAR", 5, 5.0),
        ("Kiểm tra 15' Toán 6 — Chương 3 Hình phẳng", "REGULAR", 5, 5.0),
        ("Kiểm tra 15' Toán 6 — Chương 4 Thống kê", "REGULAR", 5, 5.0),
    ]
    gk1_id: int | None = None
    for title, cat, nq, tp in papers:
        cur.execute(
            """
            INSERT INTO public.exam_papers
                (so_school_id, subject_id, semester_id, grade_id, score_category,
                 title, difficulty, difficulty_coefficient, num_questions, total_points, uploaded_by)
            VALUES (%s, %s, %s, 6, %s::public.score_category_enum, %s, 'MEDIUM', 1.0, %s, %s, 1)
            RETURNING id
            """,
            (SO_SCHOOL_ID, SUBJECT_ID, SEMESTER, cat, title, nq, tp),
        )
        pid = cur.fetchone()[0]
        if cat == "MIDTERM":
            gk1_id = pid

    assert gk1_id is not None, "Không tạo được đề GK1"
    comp_rows: list[tuple] = []
    for chapter_id, weight in EXAM_COMPETENCIES:
        lessons = lessons_by_chapter.get(chapter_id) or [chapter_id]
        parts = _split_even_preserving_total(weight, len(lessons))
        for lesson_id, part in zip(lessons, parts, strict=False):
            comp_rows.append((gk1_id, lesson_id, part))
    cur.executemany(
        """
        INSERT INTO public.exam_competencies (exam_paper_id, unit_id, weight, bloom_level)
        VALUES (%s, %s, %s, 3)
        ON CONFLICT (exam_paper_id, unit_id) DO UPDATE
          SET weight = EXCLUDED.weight, bloom_level = EXCLUDED.bloom_level
        """,
        comp_rows,
    )
    print(f"  → {len(comp_rows)} competency (đề GK1, bloom=3)")
    return gk1_id


def gd2_gradebooks(cur, students: list[dict], profiles: list[dict]) -> None:
    """GĐ 2 — Seed điểm fact_gradebooks (TX 1061 + GK 1062)."""
    print("[GĐ 2] Re-mock fact_gradebooks subject 106 (TX + GK)...")
    cur.execute("SELECT COALESCE(MAX(id), 0) FROM s360.fact_gradebooks")
    fid = cur.fetchone()[0]
    rows: list[tuple] = []
    for st, prof in zip(students, profiles, strict=False):
        gk = float(prof["gk"])
        tx = max(0.0, round(gk - RNG.uniform(0.3, 0.9), 1))
        for exam_id, score, created in [
            (1061, tx, "2025-09-05 10:00:00"),
            (1062, gk, "2025-10-10 10:00:00"),
        ]:
            fid += 1
            pct = round(score * 10.0, 2)
            rows.append(
                (
                    fid,
                    SO_SCHOOL_ID,
                    SCHOOL_YEAR_ID,
                    SEMESTER,
                    st["homeroom_class_id"],
                    st["student_code"],
                    SUBJECT_ID,
                    exam_id,
                    round(score, 2),
                    pct,
                    None,
                    "DAT" if score >= 5 else "CHUA_DAT",
                    "SCALE_10",
                    MAX_GRADE,
                    1,
                    created,
                    "SCHOOL_ONLINE_LMS",
                )
            )
    cur.executemany(
        """
        INSERT INTO s360.fact_gradebooks
            (id, so_school_id, school_year_id, semester_index, homeroom_class_id,
             student_code, subject_id, so_exam_id, final_grade, final_grade_percent,
             final_grade_letter, pass_fail_status, scale_name_used, max_grade,
             is_locked, created_at, source_system)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::public.pass_fail_enum, %s, %s, %s, %s, %s)
        """,
        rows,
    )
    print(f"  → {len(rows)} dòng điểm sổ điểm (TX + GK)")


def build_assignments_and_bank(
    cur,
    templates: dict[str, dict],
    lessons_by_chapter: dict[int, list[int]],
) -> tuple[list[dict], list[dict]]:
    """GĐ 3 — Đọc 35 tuần teaching_schedules, sinh ~86 assignment và phân bổ câu hỏi từ templates JSON."""
    print("[GĐ 3] Xây dựng Assignments (35 tuần) và Question Bank (~1100 câu)...")
    
    # 1. Đọc teaching_schedules
    cur.execute("""
        SELECT 
            ts.semester_number,
            ts.week_number,
            ts.unit_id,
            ts.topic,
            cu.name AS unit_name,
            cu.parent_id AS chapter_id,
            COALESCE(pcu.name, 'CHƯƠNG TỔNG HỢP') AS chapter_name
        FROM public.teaching_schedules ts
        LEFT JOIN public.curriculum_units cu ON ts.unit_id = cu.id
        LEFT JOIN public.curriculum_units pcu ON cu.parent_id = pcu.id
        WHERE ts.subject_id = %s AND ts.grade_number = 6
        ORDER BY ts.semester_number, ts.week_number, ts.unit_id
    """, (SUBJECT_ID,))
    schedule_rows = cur.fetchall()

    # Nhóm theo (semester, week)
    weeks_map: dict[tuple[int, int], list[dict]] = {}
    for r in schedule_rows:
        key = (r[0], r[1])
        weeks_map.setdefault(key, []).append({
            "semester": r[0],
            "week": r[1],
            "unit_id": r[2],
            "topic": r[3],
            "unit_name": r[4] or "Bài học",
            "chapter_id": r[5] or 391,
            "chapter_name": r[6],
        })

    assignments: list[dict] = []
    questions: list[dict] = []
    
    assign_id = 106001
    qid = 70001
    all_past_unit_ids: list[int] = []

    # Danh sách các tuần ôn tập / kiểm tra
    REVIEW_WEEKS_SET = {(1, 9), (1, 18), (2, 9), (2, 17)}  # Tuần 9, 18 HK1; Tuần 27, 35 toàn năm

    for (sem, week), u_list in sorted(weeks_map.items()):
        primary_u = u_list[0]
        unit_id = primary_u["unit_id"]
        if unit_id is None:
            unit_id = all_past_unit_ids[-1] if all_past_unit_ids else 392

        unit_name = primary_u["unit_name"] or "Bài học"
        chapter_id = primary_u["chapter_id"] or 391
        chapter_name = primary_u["chapter_name"] or "TOÁN 6"

        if unit_id not in all_past_unit_ids:
            all_past_unit_ids.append(unit_id)

        # Tính due_date cơ sở
        start_date = WEEK_START if sem == 1 else HK2_START
        week_due_base = start_date + timedelta(weeks=week - 1)

        # Số bài trong tuần: tuần ôn tập = 2 bài ôn; tuần thường = 2-3 bài
        if (sem, week) in REVIEW_WEEKS_SET:
            num_assigns = 2
            plan = [("review", "Ôn tập tổng hợp"), ("review", "Luyện đề đánh giá năng lực")]
        elif week % 4 == 0:
            num_assigns = 3
            plan = [
                ("regular", f"Bài tập: {unit_name}"),
                ("review", f"Ôn tập chuyên đề {chapter_name}"),
                ("advanced", f"Thử thách Nâng cao: {unit_name}"),
            ]
        else:
            num_assigns = 2
            plan = [
                ("regular", f"Bài tập 1: {unit_name}"),
                ("regular", f"Bài tập 2: {unit_name}"),
            ]

        for k, (atype, aname_suffix) in enumerate(plan):
            due_date = week_due_base + timedelta(days=2 * k + 3)
            fullname = f"[Toán 6 - W{week:02d}] {aname_suffix}"
            code = f"LMS_T6_S{sem}_W{week:02d}_A{k+1}"

            assign_dict = {
                "assignment_id": assign_id,
                "so_school_id": SO_SCHOOL_ID,
                "grade_id": 6,
                "semester_index": sem,
                "subject_id": SUBJECT_ID,
                "code": code,
                "fullname": fullname,
                "max_grade": 10.0,
                "date_assigned": due_date - timedelta(days=5),
                "due_date": due_date.date(),
                "week": week,
                "semester": sem,
                "type": atype,
                "unit_id": unit_id,
                "chapter_id": chapter_id,
            }
            assignments.append(assign_dict)

            # Lấy pool câu hỏi từ JSON
            unit_data = templates.get(str(unit_id), {})
            pool = unit_data.get("questions", [])

            selected_qs: list[tuple[int, dict]] = []

            if atype == "regular":
                # 10-12 câu, lấy từ pool của unit chính tuần này (đảm bảo Bloom 1-6)
                target_count = 10
                if pool:
                    by_bloom: dict[int, list[dict]] = {}
                    for q in pool:
                        by_bloom.setdefault(q.get("bloom_level", 2), []).append(q)
                    
                    for b in range(1, 7):
                        if by_bloom.get(b):
                            selected_qs.append((unit_id, RNG.choice(by_bloom[b])))
                    
                    remaining_pool = [q for q in pool if not any(sq[1] == q for sq in selected_qs)]
                    needed = target_count - len(selected_qs)
                    if needed > 0 and remaining_pool:
                        for item in RNG.sample(remaining_pool, min(needed, len(remaining_pool))):
                            selected_qs.append((unit_id, item))
                else:
                    for b in [1, 2, 2, 3, 3, 4, 5, 6]:
                        selected_qs.append((unit_id, {
                            "text": f"Câu hỏi {unit_name} cấp độ Bloom {b}",
                            "bloom_level": b,
                            "options": ["A. Đúng", "B. Sai", "C. Chưa đủ dữ kiện", "D. Khác"],
                            "correct": 0,
                            "explanation": "Lời giải tự động",
                        }))

            elif atype == "review":
                # 15-18 câu từ 2-3 unit khác nhau
                target_count = 16
                candidate_units = all_past_unit_ids[-4:] if len(all_past_unit_ids) >= 4 else all_past_unit_ids
                for cand_id in candidate_units:
                    c_pool = templates.get(str(cand_id), {}).get("questions", [])
                    if c_pool:
                        for item in RNG.sample(c_pool, min(4, len(c_pool))):
                            selected_qs.append((cand_id, item))
                if len(selected_qs) < target_count and pool:
                    rem = [q for q in pool if not any(sq[1] == q for sq in selected_qs)]
                    for item in RNG.sample(rem, min(target_count - len(selected_qs), len(rem))):
                        selected_qs.append((unit_id, item))

            else:  # advanced
                # 10-12 câu, ưu tiên Bloom 4-6
                target_count = 10
                adv_pool = [q for q in pool if q.get("bloom_level", 1) >= 4]
                if len(adv_pool) >= 6:
                    for item in RNG.sample(adv_pool, min(target_count, len(adv_pool))):
                        selected_qs.append((unit_id, item))
                if len(selected_qs) < target_count and pool:
                    rem = [q for q in pool if not any(sq[1] == q for sq in selected_qs)]
                    for item in RNG.sample(rem, min(target_count - len(selected_qs), len(rem))):
                        selected_qs.append((unit_id, item))

            # Đăng ký vào bank questions
            for q_uid, q_item in selected_qs:
                qid += 1
                q_bloom = q_item.get("bloom_level", 2)
                q_text = q_item.get("text", f"Câu hỏi {qid}")
                
                questions.append({
                    "question_id": qid,
                    "assignment_id": assign_id,
                    "unit_id": q_uid,
                    "lesson_id": q_uid,
                    "chapter_id": chapter_id,
                    "bloom_level": q_bloom,
                    "units": [(q_uid, 1.0)],
                    "question_text": q_text,
                })

            assign_id += 1

    # Insert dim_so_assignment
    cur.executemany(
        """
        INSERT INTO s360.dim_so_assignment
            (assignment_id, so_school_id, grade_id, semester_index, subject_id,
             code, fullname, max_grade, date_assigned, due_date, allow_attempts, time_limit_sec, source_system)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 2, 1800, 'LMS')
        ON CONFLICT (assignment_id) DO UPDATE
          SET fullname = EXCLUDED.fullname, due_date = EXCLUDED.due_date
        """,
        [
            (
                a["assignment_id"],
                a["so_school_id"],
                a["grade_id"],
                a["semester_index"],
                a["subject_id"],
                a["code"],
                a["fullname"],
                a["max_grade"],
                a["date_assigned"],
                a["due_date"],
            )
            for a in assignments
        ],
    )
    print(f"  → Đã tạo {len(assignments)} bài tập LMS (dim_so_assignment) cho 35 tuần.")

    # Insert lms_question_bank
    cur.executemany(
        """
        INSERT INTO public.lms_question_bank
            (question_id, assignment_id, so_school_id, subject_id, unit_id,
             lesson_id, bloom_level, question_type, question_text, item_weight, is_active)
        VALUES (%s, %s, %s, %s, %s, %s, %s, 'MCQ', %s, 1.0, 1)
        ON CONFLICT (question_id) DO UPDATE
          SET assignment_id = EXCLUDED.assignment_id, unit_id = EXCLUDED.unit_id,
              lesson_id = EXCLUDED.lesson_id, bloom_level = EXCLUDED.bloom_level,
              question_text = EXCLUDED.question_text, is_active = 1
        """,
        [
            (
                q["question_id"],
                q["assignment_id"],
                SO_SCHOOL_ID,
                SUBJECT_ID,
                q["unit_id"],
                q["lesson_id"],
                q["bloom_level"],
                q["question_text"],
            )
            for q in questions
        ],
    )

    # Insert lms_question_unit
    unit_rows = [
        (q["question_id"], uid, weight)
        for q in questions
        for uid, weight in q["units"]
    ]
    cur.executemany(
        """
        INSERT INTO public.lms_question_unit (question_id, unit_id, weight)
        VALUES (%s, %s, %s)
        ON CONFLICT (question_id, unit_id) DO UPDATE
          SET weight = EXCLUDED.weight
        """,
        unit_rows,
    )
    print(f"  → Đã nạp {len(questions)} câu hỏi vào lms_question_bank + lms_question_unit.")

    return assignments, questions


def gd4_responses_and_grades(
    cur,
    students: list[dict],
    profiles: list[dict],
    assignments: list[dict],
    questions: list[dict],
) -> None:
    """GĐ 4 — Sinh lms_question_response và tính fact_so_assignment_grade chi tiết."""
    print("[GĐ 4] Sinh item-responses & fact_so_assignment_grade...")
    by_assign: dict[int, list[dict]] = {}
    for q in questions:
        by_assign.setdefault(q["assignment_id"], []).append(q)

    cur.execute("SELECT COALESCE(MAX(id), 0) FROM s360.fact_so_assignment_grade")
    grade_id_seq = cur.fetchone()[0]

    resp_rows: list[tuple] = []
    grade_rows: list[tuple] = []

    for st, prof in zip(students, profiles, strict=False):
        if prof["p"] is None:  # NO_LMS
            continue
        p_map = prof["p"]
        cheat = bool(prof.get("cheat"))
        weak_units = {u for u in UNITS if p_map.get(u, 0.0) < 0.35}

        for a in assignments:
            assignment_id = a["assignment_id"]
            qs = by_assign.get(assignment_id, [])
            if not qs:
                continue

            due_d = a["due_date"]
            attempt_date = datetime.combine(due_d, datetime.min.time()) - timedelta(hours=RNG.randint(2, 24), minutes=RNG.randint(0, 59))

            correct_count = 0
            total_time = 0

            for q in qs:
                chapter = q["chapter_id"]
                correct = RNG.random() < p_map.get(chapter, 0.75)
                if cheat:
                    correct = True
                    rtime = RNG.randint(1, 2)
                    flag = 1
                else:
                    rtime = RNG.randint(15, 450)
                    flag = 0

                total_time += rtime
                if correct:
                    correct_count += 1

                retry = not correct and chapter in weak_units and RNG.random() < 0.5
                resp_rows.append(
                    (
                        SO_SCHOOL_ID,
                        st["student_code"],
                        assignment_id,
                        q["question_id"],
                        q["unit_id"],
                        q["bloom_level"],
                        "MCQ",
                        1,
                        not retry,
                        correct,
                        1.0 if correct else 0.0,
                        1.0,
                        rtime,
                        Jsonb({"chosen_option": RNG.choice(["A", "B", "C", "D"])}),
                        flag,
                        attempt_date,
                    )
                )

                if retry:
                    retry_time = RNG.randint(60, 600)
                    total_time += retry_time
                    resp_rows.append(
                        (
                            SO_SCHOOL_ID,
                            st["student_code"],
                            assignment_id,
                            q["question_id"],
                            q["unit_id"],
                            q["bloom_level"],
                            "MCQ",
                            2,
                            True,
                            False,
                            0.0,
                            1.0,
                            retry_time,
                            Jsonb({"chosen_option": RNG.choice(["A", "B", "C", "D"])}),
                            flag,
                            attempt_date + timedelta(minutes=RNG.randint(2, 30)),
                        )
                    )

            # Tính điểm bài tập
            final_grade = round((correct_count / len(qs)) * 10.0, 1)
            grade_id_seq += 1
            grade_rows.append(
                (
                    grade_id_seq,
                    SO_SCHOOL_ID,
                    assignment_id,
                    st["student_code"],
                    final_grade,
                    1,
                    attempt_date - timedelta(seconds=total_time),
                    attempt_date,
                    2 if any(chapter in weak_units for q in qs) else 1,
                    total_time,
                    total_time,
                    0,
                    0,
                    0 if cheat else 1,
                )
            )

    cur.executemany(
        """
        INSERT INTO public.lms_question_response
            (so_school_id, student_code, assignment_id, question_id, unit_id,
             bloom_level, question_type, attempt_number, is_best_attempt, is_correct,
             score_received, max_score, response_time_seconds, response_payload,
             integrity_flag, attempt_date)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s)
        """,
        resp_rows,
    )

    cur.executemany(
        """
        INSERT INTO s360.fact_so_assignment_grade
            (id, so_school_id, assignment_id, student_code, final_grade, is_locked,
             started_at, submitted_at, attempt_count, time_spent_sec, active_time_sec,
             tab_hidden_count, idle_sec, rte)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (id) DO NOTHING
        """,
        grade_rows,
    )
    print(f"  → Đã sinh {len(resp_rows)} item-response và {len(grade_rows)} dòng điểm fact_so_assignment_grade.")


def gd5_mastery(cur, students: list[dict], profiles: list[dict], lessons_by_chapter: dict[int, list[int]]) -> None:
    """GĐ 5 — Tính và upsert student_unit_mastery theo từng BÀI con."""
    print("[GĐ 5] Tính student_unit_mastery qua service chuẩn...")
    
    # 1. Đọc responses
    cur.execute(
        """
        SELECT r.student_code, r.unit_id, r.bloom_level, r.is_correct,
               r.response_time_seconds, r.integrity_flag, r.attempt_number, r.attempt_date
        FROM public.lms_question_response r
        WHERE r.so_school_id = %s AND r.is_best_attempt = true
        ORDER BY r.student_code, r.unit_id, r.attempt_date
        """,
        (SO_SCHOOL_ID,),
    )
    resp_rows = cur.fetchall()

    student_items: dict[tuple[str, int], list[ItemResult]] = {}
    for sc, uid, bloom, corr, rtime, flag, att_n, dt in resp_rows:
        student_items.setdefault((sc, uid), []).append(
            ItemResult(
                unit_id=uid,
                bloom_level=bloom or 2,
                score_received=1.0 if corr else 0.0,
                max_score=1.0,
                unit_weight=1.0,
            )
        )

    # 2. Đọc điểm GK1
    cur.execute(
        """
        SELECT student_code, final_grade
        FROM s360.fact_gradebooks
        WHERE so_school_id = %s AND subject_id = %s AND so_exam_id = 1062
        """,
        (SO_SCHOOL_ID, SUBJECT_ID),
    )
    gk_scores = {r[0]: float(r[1]) for r in cur.fetchall()}

    mastery_rows: list[tuple] = []
    mastery_rows: list[tuple] = []
    for st, prof in zip(students, profiles, strict=False):
        sc = st["student_code"]
        gk = gk_scores.get(sc)
        gk_mastery = (gk / 10.0) if gk is not None else None

        for ch_id, l_list in lessons_by_chapter.items():
            for lesson_id in l_list:
                items = student_items.get((sc, lesson_id), [])
                if items:
                    fm = finalize_mastery(items, gk_mastery)
                    mastery_val = fm.raw_mastery if fm.raw_mastery is not None else 0.5
                    adj_val = fm.adjusted_mastery if fm.adjusted_mastery is not None else mastery_val
                    conf_str = fm.confidence
                    src_str = fm.evidence_source
                    integ_str = fm.integrity_status
                    n_items = fm.n_items
                    n_correct = fm.n_correct
                    cov = fm.coverage
                    lm_w = fm.lm_weight
                    ex_w = fm.exam_weight
                    evidence = fm.evidence_detail
                else:
                    mastery_val = gk_mastery if gk_mastery is not None else 0.5
                    adj_val = mastery_val
                    conf_str = "INSUFFICIENT"
                    src_str = "EXAM"
                    integ_str = "EXAM_ONLY"
                    n_items = 0
                    n_correct = 0
                    cov = 0.0
                    lm_w = 0.0
                    ex_w = 1.0
                    evidence = {"fallback": "EXAM_ONLY"}

                conf_int = CONFIDENCE_INT.get(conf_str, 1)
                mastery_rows.append(
                    (
                        SO_SCHOOL_ID,
                        sc,
                        SUBJECT_ID,
                        lesson_id,
                        SEMESTER,
                        round(mastery_val, 4),
                        n_items,
                        n_correct,
                        round(cov, 4),
                        round(lm_w, 2),
                        round(ex_w, 2),
                        round(adj_val, 4),
                        conf_int,
                        src_str,
                        integ_str,
                        Jsonb(evidence),
                        datetime.now(),
                        datetime.now(),
                    )
                )

    cur.executemany(
        """
        INSERT INTO public.student_unit_mastery
            (so_school_id, student_code, subject_id, unit_id, semester_index,
             raw_mastery, n_items, n_correct, coverage, lm_weight, exam_weight,
             adjusted_mastery, confidence, evidence_source, integrity_status,
             evidence_detail, detected_at, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (so_school_id, student_code, subject_id, unit_id, semester_index) DO UPDATE
          SET raw_mastery = EXCLUDED.raw_mastery,
              n_items = EXCLUDED.n_items,
              n_correct = EXCLUDED.n_correct,
              coverage = EXCLUDED.coverage,
              lm_weight = EXCLUDED.lm_weight,
              exam_weight = EXCLUDED.exam_weight,
              adjusted_mastery = EXCLUDED.adjusted_mastery,
              confidence = EXCLUDED.confidence,
              evidence_source = EXCLUDED.evidence_source,
              integrity_status = EXCLUDED.integrity_status,
              evidence_detail = EXCLUDED.evidence_detail,
              updated_at = EXCLUDED.updated_at
        """,
        mastery_rows,
    )
    print(f"  → Đã tính và lưu {len(mastery_rows)} bản ghi student_unit_mastery.")


def gd6_summary(cur, students: list[dict], profiles: list[dict]) -> None:
    """GĐ 6 — In bảng tổng kết đối chiếu."""
    print("\n" + "=" * 95)
    print("📊 BẢNG TỔNG KẾT MOCK TOÁN 6 — LỖ HỔNG KIẾN THỨC & EWS")
    print("=" * 95)
    print(f"{'Mã HS':<10} | {'Profile':<14} | {'GK':<5} | {'LMS Assign':<10} | {'LMS Responses':<14} | {'Lỗ Hổng (Mastery < 0.6)'}")
    print("-" * 95)

    for st, prof in zip(students[:14], profiles[:14], strict=False):
        sc = st["student_code"]
        cur.execute("SELECT COUNT(*) FROM s360.fact_so_assignment_grade WHERE student_code = %s", (sc,))
        n_grades = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM public.lms_question_response WHERE student_code = %s AND is_best_attempt = true", (sc,))
        n_resp = cur.fetchone()[0]
        cur.execute("""
            SELECT cu.name, m.adjusted_mastery, m.confidence, m.integrity_status
            FROM public.student_unit_mastery m
            JOIN public.curriculum_units cu ON m.unit_id = cu.id
            WHERE m.student_code = %s AND m.adjusted_mastery < 0.6
            LIMIT 3
        """, (sc,))
        gaps = cur.fetchall()
        gap_str = ", ".join(f"{g[0][:15]} ({g[1]:.2f}-{g[3]})" for g in gaps) or "None (All Mastered)"
        print(f"{sc:<10} | {prof['name']:<14} | {prof['gk']:<5.1f} | {n_grades:<10} | {n_resp:<14} | {gap_str}")
    print("=" * 95 + "\n")


def main():
    templates = load_question_templates()

    with psycopg.connect(DB_URL) as conn:
        with conn.cursor() as cur:
            students = discover_students(cur)
            profiles = [profile_for(i) for i in range(len(students))]

            # Tìm danh sách bài con theo chương
            cur.execute(
                """
                SELECT parent_id, id FROM public.curriculum_units
                WHERE subject_id = %s AND grade_number = 6 AND parent_id IS NOT NULL
                ORDER BY parent_id, id
                """,
                (SUBJECT_ID,),
            )
            lessons_by_chapter: dict[int, list[int]] = {}
            for p_id, u_id in cur.fetchall():
                lessons_by_chapter.setdefault(p_id, []).append(u_id)

            print(f"[INFO] Bắt đầu seed mock Toán 6 cho {len(students)} học sinh...\n")

            gd0_cleanup(cur)
            gd1_exam_papers(cur, lessons_by_chapter)
            gd2_gradebooks(cur, students, profiles)
            assignments, questions = build_assignments_and_bank(cur, templates, lessons_by_chapter)
            gd4_responses_and_grades(cur, students, profiles, assignments, questions)
            gd5_mastery(cur, students, profiles, lessons_by_chapter)
            conn.commit()

            gd6_summary(cur, students, profiles)

    print("🎉 SEED TOÁN 6 (EWS + KNOWLEDGE GAPS) HOÀN TẤT THÀNH CÔNG!")


if __name__ == "__main__":
    main()
