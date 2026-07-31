# -*- coding: utf-8 -*-
"""
MASTER MOCK DATA GENERATOR FOR TTS_SRA (37 SYSTEM TABLES)
==========================================================
Implementation of Theory-Aligned & Distribution-Controllable Persona Generation (TAD-PG)
combined with Multi-Matrix Realism (G1-G9 Score Profiles & 22 Behavior Criteria).

Coverage:
- 2 Schools: School 1 (Vinschool Central Park), School 2 (Vinschool Golden River)
- 27 Homeroom Classes (Grades 6 to 11)
- 1,023 Fixed Students + 5 Benchmark Edge Cases
- 23 Subjects & 8 Grade Scales
- 37+ Total Database Tables (12 public schema + 25+ s360 schema)
- Synchronized Metadata Indexing for Hybrid Search Entity Linker
- Full School Year: ~185 school days | ~2,800 assignments | 4 exams/subject
"""

import sys
import os

# Ensure project root is on sys.path for direct script execution
if __name__ == "__main__" and __package__ is None:
    _root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    if _root not in sys.path:
        sys.path.insert(0, _root)

import random
import argparse
import numpy as np
import math
from datetime import datetime, timedelta, date
from sqlalchemy import text
from src.db.session import SessionLocal
from src.services.metadata_indexer import sync_school_metadata
from src.core.security import hash_password

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

# Set random seeds for deterministic reproducibility
np.random.seed(42)
random.seed(42)

DEFAULT_HASHED_PASSWORD = hash_password("password123")

# Batch insert chunk size for performance
BATCH_SIZE = 10000

# Mốc thời gian thực tế của từng bài thi trong năm học 2025-2026.
# Dùng cho created_at của fact_gradebooks / fact_gradebooks_moet để:
#   - EWS temporal features (week_float = (created_at - start_date)/7) đúng ý nghĩa;
#   - filter `created_at <= cutoff` + `is_locked = 1` hoạt động đúng nghiệp vụ
#     (bài thi đã diễn ra và đã được giáo viên khóa trước thời điểm dự báo).
#   exam 1 = Mid-term HK1 (2025-10-10 < cutoff week 8 HK1 = 2025-10-20)
#   exam 2 = Final HK1    (2025-12-20)
#   exam 3 = Mid-term HK2 (2026-03-10)
#   exam 4 = Final HK2    (2026-05-20)
EXAM_CREATED_AT = {
    1: datetime(2025, 10, 10, 8, 0, 0),
    2: datetime(2025, 12, 20, 8, 0, 0),
    3: datetime(2026, 3, 10, 8, 0, 0),
    4: datetime(2026, 5, 20, 8, 0, 0),
}

# --- PHÂN PHỐI HỌ VÀ TÊN VIỆT NAM (Thống kê dân cư thực tế) ---
FAMILY_PROBABILITIES = {
    "Nguyễn": 31.5, "Trần": 10.9, "Lê": 8.9, "Phạm": 5.9,
    "Hoàng": 2.6, "Huỳnh": 2.5, "Võ": 2.5, "Vũ": 2.4,
    "Phan": 2.8, "Trương": 2.2, "Bùi": 2.1, "Đặng": 1.9,
    "Đỗ": 1.9, "Ngô": 1.7, "Hồ": 1.5, "Dương": 1.4,
    "Đinh": 1.0, "Đoàn": 0.94, "Lâm": 0.92, "Mai": 0.86,
    "Trịnh": 0.82, "Đào": 0.76, "Cao": 0.75, "Lý": 0.74,
    "Hà": 0.66, "Lưu": 0.65, "Lương": 0.65, "Thái": 0.45,
    "Châu": 0.45, "Tạ": 0.38, "Phùng": 0.36, "Tô": 0.36
}

MALE_MIDDLE_PROBABILITIES = {
    "Văn": 50.0, "Minh": 12.0, "Đức": 10.0, "Quốc": 8.0,
    "Hữu": 6.0, "Ngọc": 4.0, "Anh": 3.0, "Thành": 3.0,
    "Hoàng": 2.0, "Gia": 1.5, "Khánh": 0.5
}

FEMALE_MIDDLE_PROBABILITIES = {
    "Thị": 45.0, "Thanh": 15.0, "Ngọc": 12.0, "Thảo": 8.0,
    "Minh": 6.0, "Quỳnh": 4.0, "Phương": 4.0, "Thu": 3.0,
    "Trúc": 1.5, "Khánh": 1.0, "Như": 0.5
}

MALE_GIVEN_PROBABILITIES = {
    "Huy": 4.9, "Khang": 4.2, "Bảo": 4.1, "Minh": 3.0,
    "Anh": 2.7, "Bình": 2.5, "Cường": 2.2, "Duy": 2.1,
    "Đạt": 2.0, "Gia": 1.8, "Hải": 1.7, "Hùng": 1.6,
    "Khánh": 1.5, "Lâm": 1.4, "Nam": 1.3, "Phúc": 1.2,
    "Quân": 1.1, "Sơn": 1.0, "Tùng": 0.9, "Tuấn": 0.8,
    "Phong": 0.5
}

FEMALE_GIVEN_PROBABILITIES = {
    "Anh": 7.91, "Vy": 5.0, "Linh": 4.5, "Phương": 4.0,
    "Quỳnh": 3.8, "Thảo": 3.5, "Trang": 3.2, "Mai": 3.0,
    "Ngọc": 2.8, "Hương": 2.5, "Bình": 2.0, "Chi": 1.8,
    "Diệp": 1.5, "Dung": 1.2, "Giang": 1.0, "Hà": 0.9,
    "Hoa": 0.8, "Khanh": 0.7, "Oanh": 0.6, "Yến": 0.5,
    "Lan": 0.4
}

class AdvancedVietnameseNameGenerator:
    """Sinh họ tên học sinh theo phân phối thống kê dân cư thực tế Việt Nam."""
    def __init__(self):
        self.families = list(FAMILY_PROBABILITIES.keys())
        self.family_weights = list(FAMILY_PROBABILITIES.values())
        self.male_middles = list(MALE_MIDDLE_PROBABILITIES.keys())
        self.male_middle_weights = list(MALE_MIDDLE_PROBABILITIES.values())
        self.female_middles = list(FEMALE_MIDDLE_PROBABILITIES.keys())
        self.female_middle_weights = list(FEMALE_MIDDLE_PROBABILITIES.values())
        self.male_givens = list(MALE_GIVEN_PROBABILITIES.keys())
        self.male_given_weights = list(MALE_GIVEN_PROBABILITIES.values())
        self.female_givens = list(FEMALE_GIVEN_PROBABILITIES.keys())
        self.female_given_weights = list(FEMALE_GIVEN_PROBABILITIES.values())

    def generate(self, gender=None):
        if gender is None:
            gender = random.choice(["MALE", "FEMALE"])
        else:
            gender = gender.upper()
        family = random.choices(self.families, weights=self.family_weights, k=1)[0]
        if gender == "MALE":
            middle = random.choices(self.male_middles, weights=self.male_middle_weights, k=1)[0]
            given = random.choices(self.male_givens, weights=self.male_given_weights, k=1)[0]
        else:
            middle = random.choices(self.female_middles, weights=self.female_middle_weights, k=1)[0]
            given = random.choices(self.female_givens, weights=self.female_given_weights, k=1)[0]
        return f"{family} {middle} {given}", gender

name_generator = AdvancedVietnameseNameGenerator()


# =====================================================================
# SUB-FUNCTIONS FOR PHASED EXECUTION
# =====================================================================

def _batch_insert(session, sql, rows, batch_size=BATCH_SIZE):
    """Helper: thực hiện batch insert với chunk size."""
    if not rows:
        return
    for i in range(0, len(rows), batch_size):
        chunk = rows[i:i + batch_size]
        session.execute(text(sql), chunk)
    session.commit()


# ---------------------------------------------------------------------------
# Phase 0: Truncate all 37 tables
# ---------------------------------------------------------------------------
def phase_truncate(session):
    """Xoá toàn bộ dữ liệu cũ trong 37 bảng."""
    print("\n🧹 [1/8] Truncating all existing data across 37 tables...")
    truncate_tables = [
        "public.ai_observability_snapshots", "public.ai_messages", "public.ai_session_attachments",
        "public.ai_sessions", "public.classroom_recordings", "public.report_schedules",
        "public.audit_logs", "public.exam_competencies", "public.curriculum_units",
        "public.exam_papers", "public.refresh_tokens", "public.users",
        "s360.metadata_index", "s360.fact_course_attendences", "s360.fact_so_class_attendance_statistics",
        "s360.fact_so_homeroom_class_late_attendances", "s360.fact_so_homeroom_class_attendances",
        "s360.fact_so_daily_attendance", "s360.fact_absent_logs", "s360.fact_behavior_logs",
        "s360.fact_course_enrolls", "s360.fact_so_evaluate_process_subjects",
        "s360.fact_overall_academic_records", "s360.fact_subject_academic_records",
        "s360.fact_so_assignment_grade", "s360.fact_gradebooks_moet", "s360.fact_gradebooks",
        "s360.dim_course", "s360.dim_behavior", "s360.dim_grade_scale_detail",
        "s360.dim_so_assignment", "s360.dim_exam_moet", "s360.dim_exam",
        "s360.dim_subject", "s360.dim_homeroom_class_student", "s360.dim_homeroom_class",
        "s360.dim_school_year"
    ]
    for table in truncate_tables:
        try:
            session.execute(text(f"TRUNCATE TABLE {table} CASCADE;"))
        except Exception as te:
            session.rollback()
    session.commit()
    print("   ✅ Cleaned all 37 tables successfully.")


# ---------------------------------------------------------------------------
# Phase 1: Seed core application users
# ---------------------------------------------------------------------------
def phase_users(session):
    """Seed public.users với tài khoản mẫu."""
    print("\n👥 [2/8] Seeding System Users (public.users)...")
    users_sql = """
    INSERT INTO public.users (so_school_id, email, hashed_password, full_name, role, is_active)
    VALUES 
    (1, 'principal_cp@vinschool.edu.vn', :hpwd, 'Nguyễn Văn Minh', 'PRINCIPAL', true),
    (2, 'principal_gr@vinschool.edu.vn', :hpwd, 'Trần Thị Thu Hương', 'PRINCIPAL', true),
    (1, 'grade_head_7_cp@vinschool.edu.vn', :hpwd, 'Lê Hoàng Nam', 'SUBJECT_TEACHER', true),
    (1, 'teacher_7a1_cp@vinschool.edu.vn', :hpwd, 'Phạm Thị Lan', 'SUBJECT_TEACHER', true),
    (1, 'teacher_7a2_cp@vinschool.edu.vn', :hpwd, 'Vũ Đức Thành', 'SUBJECT_TEACHER', true)
    ON CONFLICT (email) DO NOTHING;
    """
    session.execute(text(users_sql), {"hpwd": DEFAULT_HASHED_PASSWORD})
    session.commit()
    print("   ✅ Installed Core System Users.")


# ---------------------------------------------------------------------------
# Phase 2: Seed base dimensions
# ---------------------------------------------------------------------------
def phase_dimensions(session):
    """Seed tất cả dimension tables: school year, grade scales, subjects, classes,
    exams, assignments (~2,800), behavior catalog (22 criteria), courses.
    Trả về (classes_data, all_assignments) cho các phase sau."""
    print("\n🏫 [3/8] Seeding Base Dimensions (School Year, Classes, Subjects, Scales)...")

    # 3.1 School Year
    session.execute(text("""
        INSERT INTO s360.dim_school_year (id, code, fullname, start_date, end_date)
        VALUES (2025, '2025-2026', 'Năm học 2025 - 2026', '2025-09-05', '2026-05-31')
        ON CONFLICT (id) DO NOTHING;
    """))

    # 3.2 Grade Scale Details (8 Matrix Rows)
    scale_rows = [
        (1, 'SCALE_10', 9.0, 10.0, 90.0, 100.0, 95.0, 'A+', 'Xuất sắc', 4.0, 6, 'DAT'),
        (2, 'SCALE_10', 8.0, 8.9, 80.0, 89.0, 85.0, 'A', 'Giỏi', 3.5, 5, 'DAT'),
        (3, 'SCALE_10', 7.0, 7.9, 70.0, 79.0, 75.0, 'B+', 'Khá giỏi', 3.0, 4, 'DAT'),
        (4, 'SCALE_10', 6.5, 6.9, 65.0, 69.0, 67.0, 'B', 'Khá', 2.5, 3, 'DAT'),
        (5, 'SCALE_10', 5.5, 6.4, 55.0, 64.0, 60.0, 'C+', 'Trung bình khá', 2.0, 2, 'DAT'),
        (6, 'SCALE_10', 5.0, 5.4, 50.0, 54.0, 52.0, 'C', 'Trung bình', 1.5, 2, 'DAT'),
        (7, 'SCALE_10', 3.5, 4.9, 35.0, 49.0, 42.0, 'D', 'Yếu', 1.0, 1, 'CHUA_DAT'),
        (8, 'SCALE_10', 0.0, 3.4, 0.0, 34.0, 17.0, 'F', 'Kém', 0.0, 0, 'CHUA_DAT'),
    ]
    for sr in scale_rows:
        session.execute(text("""
            INSERT INTO s360.dim_grade_scale_detail 
            (id, scale_name, min_score_range, max_score_range, min_percent, max_percent, representative_percent, grade_letter, grade_label, gpa_scale_4, scale_6_value, pass_fail_status)
            VALUES (:id, :sname, :min_s, :max_s, :min_p, :max_p, :rep_p, :gletter, :glabel, :gpa4, :s6, CAST(:pf AS public.pass_fail_enum))
            ON CONFLICT (id) DO NOTHING;
        """), {
            "id": sr[0], "sname": sr[1], "min_s": sr[2], "max_s": sr[3],
            "min_p": sr[4], "max_p": sr[5], "rep_p": sr[6], "gletter": sr[7],
            "glabel": sr[8], "gpa4": sr[9], "s6": sr[10], "pf": sr[11]
        })

    # 3.3 Subjects (23 Canonical Standard Subjects)
    # (id, code, name, name_en, subject_type, assessment_type, default_scale_name, coeff, category_flag, subject_category)
    subjects_info = [
        (106, 'TOAN_6',   'Toán học Khối 6',            'Mathematics Grade 6',  'CORE',      'SCORED', 'SCALE_10',  2, 'MOET',     'MATH_SCIENCE'),
        (107, 'TOAN_7',   'Toán học Khối 7',            'Mathematics Grade 7',  'CORE',      'SCORED', 'SCALE_10',  2, 'MOET',     'MATH_SCIENCE'),
        (108, 'TOAN_8',   'Toán học Khối 8',            'Mathematics Grade 8',  'CORE',      'SCORED', 'SCALE_10',  2, 'MOET',     'MATH_SCIENCE'),
        (109, 'TOAN_9',   'Toán học Khối 9',            'Mathematics Grade 9',  'CORE',      'SCORED', 'SCALE_10',  2, 'MOET',     'MATH_SCIENCE'),
        (110, 'TOAN_10',  'Toán học Khối 10',           'Mathematics Grade 10', 'CORE',      'SCORED', 'SCALE_10',  2, 'MOET',     'MATH_SCIENCE'),
        (111, 'TOAN_11',  'Toán học Khối 11',           'Mathematics Grade 11', 'CORE',      'SCORED', 'SCALE_10',  2, 'MOET',     'MATH_SCIENCE'),
        (2,   'VAN',      'Ngữ văn',                    'Vietnamese Literature','CORE',      'SCORED', 'SCALE_10',  2, 'MOET',     'HUMANITIES'),
        (3,   'ANH',      'Tiếng Anh',                  'English MOET',         'CORE',      'SCORED', 'SCALE_10',  2, 'MOET',     'HUMANITIES'),
        (4,   'LY',       'Vật lý',                     'Physics',              'CORE',      'SCORED', 'SCALE_10',  1, 'MOET',     'MATH_SCIENCE'),
        (5,   'HOA',      'Hóa học',                    'Chemistry',            'CORE',      'SCORED', 'SCALE_10',  1, 'MOET',     'MATH_SCIENCE'),
        (6,   'SINH',     'Sinh học',                   'Biology',              'CORE',      'SCORED', 'SCALE_10',  1, 'MOET',     'MATH_SCIENCE'),
        (7,   'KHTN',     'Khoa học tự nhiên',          'Natural Sciences',     'CORE',      'SCORED', 'SCALE_10',  1, 'MOET',     'MATH_SCIENCE'),
        (8,   'LS_DL',    'Lịch sử và Địa lý',          'History & Geography',  'CORE',      'SCORED', 'SCALE_10',  1, 'MOET',     'HUMANITIES'),
        (9,   'CAM_ENG',  'Tiếng Anh Cambridge (ESL)',  'Cambridge ESL',        'CAMBRIDGE', 'SCORED', 'LETTER_AF', 2, 'NON_MOET', 'HUMANITIES'),
        (10,  'CAM_MATH', 'Toán Tiếng Anh Cambridge',   'Cambridge Math',       'CAMBRIDGE', 'SCORED', 'LETTER_AF', 2, 'NON_MOET', 'MATH_SCIENCE'),
        (11,  'IB_MATH',  'Toán Quốc tế IB',            'IB Mathematics',       'IB',        'SCORED', 'SCALE_6',   2, 'NON_MOET', 'MATH_SCIENCE'),
        (12,  'IB_SCI',   'Khoa học Quốc tế IB',        'IB Science',           'IB',        'SCORED', 'SCALE_6',   1, 'NON_MOET', 'MATH_SCIENCE'),
        (13,  'TIN',      'Tin học & Lập trình',        'Computer Science',     'ELECTIVE',  'SCORED', 'SCALE_100', 0.5, 'NON_MOET', 'TECHNOLOGY'),
        (14,  'ROBOTICS', 'STEM & Robotics',            'STEM Robotics',        'ELECTIVE',  'SCORED', 'SCALE_100', 0.5, 'NON_MOET', 'TECHNOLOGY'),
        (15,  'GPA_HONOR','Môn Chuyên Honor Course',    'Honor Course',         'HONOR',     'SCORED', 'SCALE_4',   2, 'NON_MOET', 'MATH_SCIENCE'),
        (16,  'THE_DUC',  'Giáo dục thể chất',          'Physical Education',   'CORE',      'REMARK', 'PASS_FAIL', 0.5, 'REMARK',   'ARTS_PE'),
        (17,  'MY_THUAT', 'Mỹ thuật',                   'Fine Arts',            'CORE',      'REMARK', 'PASS_FAIL', 0.5, 'REMARK',   'ARTS_PE'),
        (18,  'AM_NHAC',  'Âm nhạc',                    'Music',                'CORE',      'REMARK', 'PASS_FAIL', 0.5, 'REMARK',   'ARTS_PE')
    ]
    for sub in subjects_info:
        session.execute(text("""
            INSERT INTO s360.dim_subject (id, code, name, subject_category, assessment_type, default_scale_name)
            VALUES (:id, :code, :name, :cat, :atype, :scale)
            ON CONFLICT (id) DO UPDATE SET
                code = EXCLUDED.code, name = EXCLUDED.name,
                subject_category = EXCLUDED.subject_category,
                assessment_type = EXCLUDED.assessment_type,
                default_scale_name = EXCLUDED.default_scale_name;
        """), {
            "id": sub[0], "code": sub[1], "name": sub[2],
            "cat": sub[9], "atype": sub[5], "scale": sub[6]
        })

    # 3.4 Homeroom Classes (27 Classes across 2 Schools)
    classes_data = []
    c_id = 1
    for school_id in [1, 2]:
        for g_id in [6, 7, 8, 9, 10, 11]:
            num_classes = 3 if g_id == 7 else 2
            for c_num in range(1, num_classes + 1):
                c_code = f"CLASS_{school_id}_{g_id}A{c_num}"
                c_name = f"{g_id}A{c_num}"
                classes_data.append((c_id, school_id, 2025, g_id, c_code, c_name))
                c_id += 1

    for cl in classes_data:
        session.execute(text("""
            INSERT INTO s360.dim_homeroom_class (id, so_school_id, school_year_id, grade_id, code, fullname)
            VALUES (:id, :sid, :syid, :gid, :code, :name)
            ON CONFLICT (id) DO NOTHING;
        """), {"id": cl[0], "sid": cl[1], "syid": cl[2], "gid": cl[3], "code": cl[4], "name": cl[5]})

    # 3.5 Exams Catalog (dim_exam & dim_exam_moet)
    exams = [
        (1, 2025, 5, 7, "EXAM_MID_S1", "Kiểm tra Giữa Học kỳ 1", 1.0, 1),
        (2, 2025, 5, 7, "EXAM_FINAL_S1", "Kiểm tra Cuối Học kỳ 1", 2.0, 1),
        (3, 2025, 5, 7, "EXAM_MID_S2", "Kiểm tra Giữa Học kỳ 2", 1.0, 2),
        (4, 2025, 5, 7, "EXAM_FINAL_S2", "Kiểm tra Cuối Học kỳ 2", 2.0, 2),
    ]
    for ex in exams:
        session.execute(text("""
            INSERT INTO s360.dim_exam (id, school_year_id, subject_id, grade_id, exam_code, exam_name, coefficient, moet_semester_index)
            VALUES (:id, :syid, :subid, :gid, :code, :ename, :coeff, :sem)
            ON CONFLICT (id) DO NOTHING;
        """), {"id": ex[0], "syid": ex[1], "subid": ex[2], "gid": ex[3], "code": ex[4], "ename": ex[5], "coeff": ex[6], "sem": ex[7]})

        session.execute(text("""
            INSERT INTO s360.dim_exam_moet (gradebook_type_item_id, gradebook_type_items_code, gradebook_type_items_fullname, coefficient, moet_semester_index)
            VALUES (:id, :code, :ename, :coeff, :sem)
            ON CONFLICT (gradebook_type_item_id) DO NOTHING;
        """), {"id": ex[0], "code": ex[4], "ename": ex[5], "coeff": ex[6], "sem": ex[7]})

    # 3.6 LMS Assignment Catalog — MỞ RỘNG: tuần 1-18 HK1, tuần 1-17 HK2
    CORE_SUBJECTS_BY_GRADE = {
        6: [106, 2, 3, 7, 8],
        7: [107, 2, 3, 7, 8],
        8: [108, 2, 3, 7, 8],
        9: [109, 2, 3, 7, 8],
        10: [110, 2, 3, 4, 5, 6],
        11: [111, 2, 3, 4, 5, 6],
    }
    SEMESTER_STARTS = {1: date(2025, 9, 5), 2: date(2026, 1, 20)}

    all_assignments = []
    assign_id = 1
    print("   Generating dynamic assignment catalog (~2,800 assignments)...")
    for school_id in [1, 2]:
        for grade_id in range(6, 12):
            sub_ids = CORE_SUBJECTS_BY_GRADE.get(grade_id, [])
            for sem_idx in [1, 2]:
                sem_start = SEMESTER_STARTS[sem_idx]
                # HK1: 18 weeks (Sep 5 → Jan 5), HK2: 17 weeks (Jan 20 → May 18)
                num_assignments = 18 if sem_idx == 1 else 17
                for week_off in range(num_assignments):
                    week_num = week_off + 1  # weeks 1-18 or 1-17
                    assigned_date = sem_start + timedelta(weeks=week_off)
                    due_date = assigned_date + timedelta(days=7)
                    for sub_id in sub_ids:
                        code = f"ASS_S{school_id}_G{grade_id}_SUB{sub_id}_SEM{sem_idx}_W{week_num:02d}"
                        fullname = f"Bài tập Tuần {week_num} - HK{sem_idx} - Môn {sub_id} - Khối {grade_id}"
                        all_assignments.append({
                            "assignment_id": assign_id, "so_school_id": school_id,
                            "grade_id": grade_id, "semester_index": sem_idx,
                            "subject_id": sub_id, "code": code, "fullname": fullname,
                            "max_grade": 10.0, "date_assigned": assigned_date, "due_date": due_date,
                        })
                        assign_id += 1

    print(f"   Generated {len(all_assignments)} assignments across all grades/subjects/semesters.")
    # Batch insert assignments
    assign_sql = """
        INSERT INTO s360.dim_so_assignment
        (assignment_id, so_school_id, grade_id, semester_index, subject_id, code, fullname, max_grade, date_assigned, due_date)
        VALUES (:assignment_id, :so_school_id, :grade_id, :semester_index, :subject_id, :code, :fullname, :max_grade, :date_assigned, :due_date)
        ON CONFLICT (assignment_id) DO NOTHING;
    """
    _batch_insert(session, assign_sql, all_assignments)

    # 3.7 Behavior Catalog (22 Criteria in dim_behavior)
    behaviors_data = [
        (1, "BEH_LATE_MORNING", "Đi học muộn đầu giờ sáng (sau 7h30)", "NEP_SONG", "Nếp sống & Chuyên cần", -2.0, 1, 3, -5.0),
        (2, "BEH_ABSENT_FULLDAY_NO_PERM", "Nghỉ học cả ngày không xin phép", "NEP_SONG", "Nếp sống & Chuyên cần", -5.0, 1, 2, -8.0),
        (3, "BEH_ABSENT_FULLDAY_WITH_PERM", "Nghỉ học cả ngày có đơn xin phép / ốm", "NEP_SONG", "Nếp sống & Chuyên cần", 0.0, 0, 0, 0.0),
        (4, "BEH_ABSENT_PERIOD_NO_PERM", "Vắng mặt / Bỏ tiết học môn phần không lý do", "NEP_SONG", "Nếp sống & Chuyên cần", -3.0, 1, 2, -5.0),
        (5, "BEH_LATE_PERIOD", "Vào lớp muộn sau chuông báo tiết học", "NEP_SONG", "Nếp sống & Chuyên cần", -1.0, 0, 0, 0.0),
        (6, "BEH_LEAVE_EARLY", "Tự ý về sớm trước giờ tan học", "NEP_SONG", "Nếp sống & Chuyên cần", -4.0, 1, 2, -6.0),
        (7, "BEH_UNIFORM_WRONG", "Mặc sai đồng phục quy định của trường", "TRANG_PHUC", "Trang phục & Tác phong", -1.0, 0, 0, 0.0),
        (8, "BEH_NO_STUDENT_CARD", "Không đeo thẻ học sinh", "TRANG_PHUC", "Trang phục & Tác phong", -1.0, 0, 0, 0.0),
        (9, "BEH_HAIRCUT_VIOLATION", "Đầu tóc, trang điểm vi phạm nội quy", "TRANG_PHUC", "Trang phục & Tác phong", -2.0, 0, 0, 0.0),
        (10, "BEH_HOMEWORK_MISSING", "Không làm bài tập về nhà", "HOC_TAP", "Nề nếp Học tập", -2.0, 1, 3, -4.0),
        (11, "BEH_NO_EQUIPMENT", "Thiếu sách vở / dụng cụ học tập", "HOC_TAP", "Nề nếp Học tập", -1.0, 0, 0, 0.0),
        (12, "BEH_CELLPHONE_CLASS", "Sử dụng điện thoại riêng trong giờ học", "HOC_TAP", "Nề nếp Học tập", -3.0, 1, 2, -5.0),
        (13, "BEH_TALKING_IN_CLASS", "Mất trật tự, làm việc riêng trong giờ", "HOC_TAP", "Nề nếp Học tập", -1.0, 0, 0, 0.0),
        (14, "BEH_CHEATING_TEST", "Gian lận trong khi làm bài kiểm tra", "HOC_TAP", "Nề nếp Học tập", -10.0, 0, 0, 0.0),
        (15, "BEH_BAD_LANGUAGE", "Nói tục, chửi thề trong khuôn viên trường", "KY_LUAT", "Kỷ luật & Giao tiếp", -3.0, 0, 0, 0.0),
        (16, "BEH_LITTERING", "Xả rác bừa bãi không đúng nơi quy định", "KY_LUAT", "Kỷ luật & Giao tiếp", -2.0, 0, 0, 0.0),
        (17, "BEH_DISRESPECT_TEACHER", "Cãi lời / Vô lễ với thầy cô giáo", "KY_LUAT", "Kỷ luật & Giao tiếp", -10.0, 0, 0, 0.0),
        (18, "BEH_FIGHTING", "Gây nổ đố / Đánh nhau trong trường", "KY_LUAT", "Kỷ luật & Giao tiếp", -15.0, 0, 0, 0.0),
        (19, "BEH_GOOD_DEED", "Nhặt được của rơi trả lại người mất", "KHEN_THUONG", "Khen thưởng & Việc tốt", 5.0, 0, 0, 0.0),
        (20, "BEH_HELP_PEER", "Tích cực phụ đạo / Giúp đỡ bạn học tiến bộ", "KHEN_THUONG", "Khen thưởng & Việc tốt", 3.0, 0, 0, 0.0),
        (21, "BEH_SCHOOL_EVENT_VOLUNTEER", "Hỗ trợ tích cực sự kiện truyền thông của trường", "KHEN_THUONG", "Khen thưởng & Việc tốt", 4.0, 0, 0, 0.0),
        (22, "BEH_CLEAN_CLASSROOM", "Chủ động vệ sinh giữ gìn lớp học sạch đẹp", "KHEN_THUONG", "Khen thưởng & Việc tốt", 2.0, 0, 0, 0.0),
    ]
    for b in behaviors_data:
        session.execute(text("""
            INSERT INTO s360.dim_behavior 
            (id, code, name, group_code, group_name, point, is_duplicate_behavior, count_duplicate_behavior, point_duplicate_behavior)
            VALUES (:id, :code, :name, :gcode, :gname, :point, :is_dup, :cnt_dup, :pt_dup)
            ON CONFLICT (id) DO NOTHING;
        """), {"id": b[0], "code": b[1], "name": b[2], "gcode": b[3], "gname": b[4], "point": b[5], "is_dup": b[6], "cnt_dup": b[7], "pt_dup": b[8]})

    # 3.8 Elective Courses Catalog (dim_course)
    courses_data = [
        (101, 1, 2025, 7, 2, 14, "CRS_MATH_ADV_7A1", "Lớp Học Phần Toán Nâng Cao 7A1", "ELECTIVE", 35),
        (102, 1, 2025, 7, 3, 14, "CRS_ENG_CAMB_7A1", "Lớp Tiếng Anh Cambridge 7A1", "ELECTIVE", 35),
        (103, 1, 2025, 7, 4, 14, "CRS_STEM_ROBOTICS_7A1", "Lớp STEM & Robotics Khối 7", "ELECTIVE", 35),
        (104, 1, 2025, 7, 5, 15, "CRS_LIT_ADV_7A2", "Lớp Chuyên Ngữ Văn Khối 7", "ELECTIVE", 35),
    ]
    for c in courses_data:
        session.execute(text("""
            INSERT INTO s360.dim_course (id, so_school_id, school_year_id, grade_id, subject_id, homeroom_class_id, code, name, type, max_student)
            VALUES (:id, :sid, :syid, :gid, :subid, :cid, :code, :name, :type, :max_s)
            ON CONFLICT (id) DO NOTHING;
        """), {"id": c[0], "sid": c[1], "syid": c[2], "gid": c[3], "subid": c[4], "cid": c[5], "code": c[6], "name": c[7], "type": c[8], "max_s": c[9]})

    session.commit()
    print("   ✅ Base dimensions initialized successfully.")
    return classes_data, all_assignments


# ---------------------------------------------------------------------------
# Phase 3: Seed students with controllable TAD-PG persona distributions
# ---------------------------------------------------------------------------
def phase_students(session, classes_data):
    """Generate 1,023 students with TAD-PG persona weights, G1-G9 profiles,
    latent variables (c_math, c_lang, eff), and 5 special fixed-code students."""
    print("\n👨‍🎓 [4/8] Generating 1,023 Students (TAD-PG Persona Engine)...")

    PERSONA_WEIGHTS = {"High_Achiever": 15, "STEM_Focus": 15, "Humanities_Focus": 15,
                       "Diligent_Average": 45, "Academic_At_Risk": 10}
    personas_list = list(PERSONA_WEIGHTS.keys())
    persona_weights = list(PERSONA_WEIGHTS.values())

    PROFILE_GROUPS = ["G1", "G2", "G3", "G4", "G5", "G6", "G7", "G8", "G9"]
    PROFILE_WEIGHTS = {"G1": 10, "G2": 20, "G3": 12, "G4": 15, "G5": 8,
                       "G6": 10, "G7": 12, "G8": 8, "G9": 5}
    profile_list = list(PROFILE_WEIGHTS.keys())
    profile_weights = list(PROFILE_WEIGHTS.values())

    student_meta_map = {}
    sid_idx = 1
    fixed_codes = ["HS125071000", "HS125071001", "HS125071002", "HS225071000", "HS225061568"]

    print("   Generating students with persona profiles...")
    for class_row in classes_data:
        c_id, school_id, syid, grade_id, c_code, c_name = class_row
        num_students = random.randint(35, 42)

        for _ in range(num_students):
            student_code = f"HS{school_id}{grade_id}{sid_idx:04d}"
            if student_code in fixed_codes:
                sid_idx += 1
                continue

            gender = random.choice(["MALE", "FEMALE"])
            sname, _ = name_generator.generate(gender)
            persona = random.choices(personas_list, weights=persona_weights, k=1)[0]
            profile = random.choices(profile_list, weights=profile_weights, k=1)[0]

            c_math = round(float(np.random.uniform(-1.5, 1.5)), 4)
            c_lang = round(float(np.random.uniform(-1.5, 1.5)), 4)
            eff = round(float(np.random.uniform(-2.0, 2.0)), 4)

            session.execute(text("""
                INSERT INTO s360.dim_homeroom_class_student
                (id, so_student_id, student_code, student_name, homeroom_class_id, class_code, class_name,
                 so_school_id, school_year_id, school_name, grade_id, grade_name, moet_code)
                VALUES (:idx, :idx, :scode, :sname, :cid, :ccode, :cname, :sid, :syid, :sname_sch, :gid, :gname, :mcode)
                ON CONFLICT (id) DO NOTHING;
            """), {
                "idx": sid_idx, "scode": student_code, "sname": sname,
                "cid": c_id, "ccode": c_code, "cname": c_name,
                "sid": school_id, "syid": syid,
                "sname_sch": "Vinschool Central Park" if school_id == 1 else "Vinschool Golden River",
                "gid": grade_id, "gname": f"Khối {grade_id}", "mcode": f"MOET_{student_code}"
            })

            student_meta_map[student_code] = {
                "school_id": school_id, "school_year_id": syid,
                "grade_id": grade_id, "homeroom_class_id": c_id,
                "student_name": sname, "persona": persona, "profile": profile,
                "c_math": c_math, "c_lang": c_lang, "eff": eff,
            }
            sid_idx += 1

    # 5 special students with fixed codes
    special_students = [
        ("HS125071000", "Nguyễn Văn Hoàng", "High_Achiever", "G1", 1.2, 1.2, 1.8),
        ("HS125071001", "Trần Phương Linh", "STEM_Focus", "G3", 1.5, -0.2, 1.5),
        ("HS125071002", "Lê Minh Khang", "Diligent_Average", "G2", 0.5, 0.5, 1.2),
        ("HS225071000", "Phạm Hoàng Anh", "Humanities_Focus", "G4", -0.8, 1.2, 0.5),
        ("HS225061568", "Vũ Đức Thành", "Academic_At_Risk", "G7", -1.2, -1.0, -1.5),
    ]
    for scode, sname, persona, profile, c_math, c_lang, eff in special_students:
        school_id = 1 if scode[2] == '1' else 2
        grade_id = int(scode[4:6])
        matching_class = next((cl for cl in classes_data
                               if cl[1] == school_id and cl[3] == grade_id), None)
        if not matching_class:
            continue
        c_id, _, syid, gid, c_code, c_name = matching_class

        session.execute(text("""
            INSERT INTO s360.dim_homeroom_class_student
            (id, so_student_id, student_code, student_name, homeroom_class_id, class_code, class_name,
             so_school_id, school_year_id, school_name, grade_id, grade_name, moet_code)
            VALUES (:idx, :idx, :scode, :sname, :cid, :ccode, :cname, :sid, :syid, :sname_sch, :gid, :gname, :mcode)
            ON CONFLICT (id) DO NOTHING;
        """), {
            "idx": 100000 + hash(scode) % 9999, "scode": scode, "sname": sname,
            "cid": c_id, "ccode": c_code, "cname": c_name,
            "sid": school_id, "syid": syid,
            "sname_sch": "Vinschool Central Park" if school_id == 1 else "Vinschool Golden River",
            "gid": gid, "gname": f"Khối {gid}", "mcode": f"MOET_{scode}"
        })

        student_meta_map[scode] = {
            "school_id": school_id, "school_year_id": 2025,
            "grade_id": gid, "homeroom_class_id": c_id,
            "student_name": sname, "persona": persona, "profile": profile,
            "c_math": c_math, "c_lang": c_lang, "eff": eff,
        }

    session.commit()
    print(f"   ✅ Seeded {len(student_meta_map)} students across 27 homeroom classes.")
    return student_meta_map


# ---------------------------------------------------------------------------
# Phase 4: Seed academic scores (gradebooks, assignment grades, records)
#           Includes MID-TERM + FINAL exam scores for both semesters
# ---------------------------------------------------------------------------
def phase_academic(session, student_meta_map, all_assignments):
    """Seed fact_gradebooks (mid-term + final), fact_so_assignment_grade,
    fact_subject_academic_records, fact_overall_academic_records, etc."""
    print("\n📝 [5/8] Generating Academic Scores & Full Exam Records (Mid-term + Final)...")

    gradebook_id = 1
    record_id = 1
    GRADE_MATH_MAP = {6: 106, 7: 107, 8: 108, 9: 109, 10: 110, 11: 111}

    # Prepare batch containers
    gradebook_batch = []
    gradebook_moet_batch = []
    assign_grade_batch = []
    course_enroll_batch = []
    subject_academic_batch = []
    overall_academic_batch = []
    eval_process_batch = []

    for scode, meta in student_meta_map.items():
        sid, syid, gid, cid = meta["school_id"], meta["school_year_id"], meta["grade_id"], meta["homeroom_class_id"]
        c_math, c_lang, eff = meta["c_math"], meta["c_lang"], meta["eff"]
        prof = meta["profile"]
        persona = meta["persona"]

        b_math = np.clip(6.5 + 1.5 * c_math + 0.5 * eff, 0.0, 10.0)
        b_lang = np.clip(6.5 + 1.5 * c_lang + 0.5 * eff, 0.0, 10.0)

        if prof == "G1":
            exam_m, exam_e = np.clip(b_math + 1.0, 8.0, 10.0), np.clip(b_lang + 1.0, 8.0, 10.0)
            lms_score = np.random.uniform(8.5, 10.0)
        elif prof == "G5":
            exam_m, exam_e = np.clip(b_math + 1.2, 7.5, 9.8), np.clip(b_lang + 1.0, 7.0, 9.5)
            lms_score = np.random.uniform(0.0, 3.0)
        elif prof == "G6":
            exam_m, exam_e = np.random.uniform(2.0, 4.0), np.random.uniform(2.5, 4.2)
            lms_score = np.random.uniform(9.0, 10.0)
        elif prof == "G3":
            exam_m, exam_e = 8.5, 8.2
            lms_score = 8.5
        elif prof == "G4":
            exam_m, exam_e = np.random.uniform(3.8, 5.2), np.random.uniform(4.0, 5.5)
            lms_score = np.random.uniform(4.5, 6.0)
        elif prof == "G7":
            exam_m, exam_e = 3.0, 3.2
            lms_score = 4.0
        elif prof == "G8":
            exam_m, exam_e = np.random.uniform(1.5, 3.2), np.random.uniform(1.8, 3.4)
            lms_score = np.random.uniform(1.0, 3.0)
        elif prof == "G9":
            exam_m, exam_e = 0.0, 0.0
            lms_score = 0.0
        else:
            exam_m, exam_e = np.clip(b_math, 5.5, 7.8), np.clip(b_lang, 5.5, 7.8)
            lms_score = np.random.uniform(6.0, 7.5)

        exam_math_eng = np.clip(0.7 * exam_m + 0.3 * exam_e + np.random.normal(0, 0.15), 0.0, 10.0)

        s_math = round(float(exam_m), 1)
        s_eng = round(float(exam_e), 1)
        s_lit = round(float(b_lang), 1)
        s_math_eng = round(float(exam_math_eng), 1)
        s_cam_eng = round(float(np.clip(b_lang + 0.3 * eff + np.random.normal(0, 0.2), 0.0, 10.0)), 1)
        s_khtn = round(float(np.clip(0.6 * b_math + 0.4 * b_lang + np.random.normal(0, 0.2), 0.0, 10.0)), 1)
        s_lsdl = round(float(np.clip(0.8 * b_lang + 0.2 * eff + np.random.normal(0, 0.2), 0.0, 10.0)), 1)
        s_tin = round(float(np.clip(0.7 * b_math + 0.3 * eff + np.random.normal(0, 0.2), 0.0, 10.0)), 1)
        s_stem = round(float(np.clip(0.8 * b_math + 0.2 * eff + np.random.normal(0, 0.2), 0.0, 10.0)), 1)
        s_ly = round(float(np.clip(0.8 * b_math + 0.2 * eff + np.random.normal(0, 0.2), 0.0, 10.0)), 1)
        s_hoa = round(float(np.clip(0.75 * b_math + 0.25 * eff + np.random.normal(0, 0.2), 0.0, 10.0)), 1)
        s_sinh = round(float(np.clip(0.5 * b_math + 0.5 * b_lang + np.random.normal(0, 0.2), 0.0, 10.0)), 1)
        s_honor = round(float(np.clip(0.85 * b_math + 0.15 * eff + np.random.normal(0, 0.2), 0.0, 10.0)), 1)

        math_sub_id = GRADE_MATH_MAP.get(gid, 107)

        if gid in [6, 7, 8, 9]:
            student_scored_subjects = [
                (math_sub_id, s_math), (2, s_lit), (3, s_eng),
                (7, s_khtn), (8, s_lsdl)
            ]
        else:
            student_scored_subjects = [
                (math_sub_id, s_math), (2, s_lit), (3, s_eng),
                (4, s_ly), (5, s_hoa), (6, s_sinh)
            ]

        is_benchmark_student = scode in ["HS125071000", "HS125071001", "HS125071002", "HS225071000", "HS225061568"]

        p_cambridge = 0.85 if persona in ["High_Achiever", "STEM_Focus", "Humanities_Focus"] else 0.35
        if is_benchmark_student or random.random() < p_cambridge:
            student_scored_subjects.append((9, s_cam_eng))
            student_scored_subjects.append((10, s_math_eng))

        p_ib = 0.30 if persona == "High_Achiever" else 0.10
        if random.random() < p_ib:
            student_scored_subjects.append((11, s_math_eng))
            student_scored_subjects.append((12, s_khtn))

        p_tech = 0.70 if persona == "STEM_Focus" else 0.40
        if random.random() < p_tech:
            sub_tech = 14 if (persona == "STEM_Focus" and random.random() < 0.6) else 13
            student_scored_subjects.append((sub_tech, s_tin if sub_tech == 13 else s_stem))

        if persona == "High_Achiever" and random.random() < 0.4:
            student_scored_subjects.append((15, s_honor))

        student_remark_subjects = [16, 17, 18]

        # --- Gradebook: Mid-term + Final cho cả 2 học kỳ ---
        for sub_id, score_val in student_scored_subjects:
            for exam_id, sem_idx, type_item_id in [
                (1, 1, 1),   # Mid-term HK1
                (2, 1, 2),   # Final HK1
                (3, 2, 3),   # Mid-term HK2
                (4, 2, 4),   # Final HK2
            ]:
                if exam_id in (2, 4):  # Final exams: nhích điểm ±10% so với mid-term
                    final_score = round(float(np.clip(score_val + random.uniform(-0.5, 0.5), 0.0, 10.0)), 1)
                else:
                    final_score = score_val

                pf_status = 'DAT' if final_score >= 5.0 else 'CHUA_DAT'

                gradebook_batch.append({
                    "id": gradebook_id, "sid": sid, "syid": syid,
                    "sem": sem_idx, "scode": scode, "cid": cid,
                    "subid": sub_id, "eid": exam_id,
                    "score": final_score, "pf": pf_status,
                    "is_locked": 1, "created_at": EXAM_CREATED_AT[exam_id]
                })

                gradebook_moet_batch.append({
                    "id": gradebook_id, "sid": sid, "syid": syid,
                    "sem": sem_idx, "gid": gid, "cid": cid, "scode": scode,
                    "subid": sub_id, "type_item_id": type_item_id,
                    "score": final_score,
                    "is_locked": 1, "created_at": EXAM_CREATED_AT[exam_id]
                })

                gradebook_id += 1

            # Course enrolls for elective/advanced subjects
            if sub_id in [9, 10, 11, 12, 13, 14, 15]:
                course_enroll_batch.append({
                    "id": gradebook_id - 4,  # re-use first id of this subject's block
                    "sid": sid, "scode": scode,
                    "subid": sub_id, "gid": gid
                })

        # --- Remark subjects (Physical Ed, Fine Arts, Music) ---
        remark_comments = {
            16: ("Hoàn thành xuất sắc các chỉ số rèn luyện thể lực và tinh thần đồng đội.",
                 "Cần tăng cường rèn luyện sức bền."),
            17: ("Sáng tạo tốt, có năng khiếu mỹ thuật và cảm thụ màu sắc hài hòa.",
                 "Cần chú ý hoàn thành đúng hạn các bài vẽ."),
            18: ("Cảm thụ âm nhạc tốt, thuộc lời và thể hiện chuẩn xác các bài hát.",
                 "Cần tự tin hơn khi hát trước tập thể.")
        }

        for sub_id in student_remark_subjects:
            for sem_idx in [1, 2]:
                pf_status = 'DAT' if (eff > -1.0 or prof != "Academic_At_Risk") else 'CHUA_DAT'
                exam_id_rem = 1 if sem_idx == 1 else 3

                gradebook_batch.append({
                    "id": gradebook_id, "sid": sid, "syid": syid,
                    "sem": sem_idx, "scode": scode, "cid": cid,
                    "subid": sub_id, "eid": exam_id_rem,
                    "score": None, "pf": pf_status,
                    "is_locked": 1, "created_at": EXAM_CREATED_AT[exam_id_rem]
                })

                cmt_text = remark_comments[sub_id][0] if pf_status == 'DAT' else remark_comments[sub_id][1]
                eval_process_batch.append({
                    "id": gradebook_id, "eid": gradebook_id,
                    "subid": sub_id, "scode": scode, "syid": syid,
                    "sem": sem_idx,
                    "fgl": pf_status,
                    "slevel": "ĐẠT" if pf_status == 'DAT' else "CHƯA ĐẠT",
                    "comment": cmt_text, "tname": "Giáo viên Bộ Môn"
                })
                gradebook_id += 1

        # --- Assignment grades (fact_so_assignment_grade) ---
        student_enrolled_subject_ids = {sub_id for sub_id, _ in student_scored_subjects}
        for assign in all_assignments:
            if (assign["so_school_id"] == sid and
                assign["grade_id"] == gid and
                assign["subject_id"] in student_enrolled_subject_ids):

                week_off = (assign["date_assigned"] - date(2025, 9, 5)).days // 7

                if prof == "G7":
                    score = np.clip(5.0 - 0.25 * week_off + random.uniform(-0.5, 0.5), 0.0, 10.0)
                elif prof == "G3":
                    score = np.clip(3.0 + 0.35 * week_off + random.uniform(-0.5, 0.5), 0.0, 10.0)
                elif prof == "G6":
                    score = np.random.uniform(9.0, 10.0)
                elif prof == "G5":
                    score = np.random.uniform(0.0, 3.0)
                elif prof == "G9":
                    score = 0.0
                else:
                    score = np.clip(lms_score + random.uniform(-1.0, 1.0), 1.0, 10.0)

                assign_grade_batch.append({
                    "id": gradebook_id, "sid": sid,
                    "aid": assign["assignment_id"], "scode": scode,
                    "fg": round(float(score), 1)
                })
                gradebook_id += 1

        # --- Subject academic records ---
        for sub_id, score_val in student_scored_subjects[:3]:
            subject_academic_batch.append({
                "id": record_id, "oid": record_id,
                "subid": sub_id, "scode": scode,
                "fg": score_val, "s1fg": score_val
            })
            record_id += 1

        # --- Overall academic record ---
        all_scores = [sc for _, sc in student_scored_subjects]
        gpa = round(float(np.mean(all_scores)), 1)
        conduct_val = "TOT" if eff > 0.5 else ("KHA" if eff > 0.0 else "TRUNG_BINH")
        capacity_val = "Giỏi" if gpa >= 8.0 else ("Khá" if gpa >= 6.5 else ("Trung bình" if gpa >= 5.0 else "Yếu"))

        overall_academic_batch.append({
            "id": record_id, "sid": sid, "syid": syid, "gid": gid,
            "cid": cid, "st_id": record_id, "scode": scode,
            "fg": gpa, "s1fg": gpa,
            "cond": conduct_val, "s1cond": conduct_val,
            "lcap": capacity_val, "s1lcap": capacity_val
        })
        record_id += 1

    # === BATCH INSERTS ===
    print(f"   Batch inserting {len(gradebook_batch)} gradebook records...")
    _batch_insert(session, """
        INSERT INTO s360.fact_gradebooks
        (id, so_school_id, school_year_id, semester_index, student_code, homeroom_class_id, subject_id, so_exam_id, final_grade, pass_fail_status, is_locked, created_at)
        VALUES (:id, :sid, :syid, :sem, :scode, :cid, :subid, :eid, :score, CAST(:pf AS public.pass_fail_enum), :is_locked, :created_at)
        ON CONFLICT (id) DO NOTHING;
    """, gradebook_batch)

    print(f"   Batch inserting {len(gradebook_moet_batch)} gradebook_moet records...")
    _batch_insert(session, """
        INSERT INTO s360.fact_gradebooks_moet
        (id, so_school_id, school_year_id, semester_index, grade_id, homeroom_class_id, student_code, subject_id, gradebook_type_item_id, final_grade, is_locked, created_at)
        VALUES (:id, :sid, :syid, :sem, :gid, :cid, :scode, :subid, :type_item_id, :score, :is_locked, :created_at)
        ON CONFLICT (id) DO NOTHING;
    """, gradebook_moet_batch)

    print(f"   Batch inserting {len(assign_grade_batch)} assignment grades...")
    _batch_insert(session, """
        INSERT INTO s360.fact_so_assignment_grade
        (id, so_school_id, assignment_id, student_code, final_grade)
        VALUES (:id, :sid, :aid, :scode, :fg)
        ON CONFLICT (id) DO NOTHING;
    """, assign_grade_batch)

    if course_enroll_batch:
        _batch_insert(session, """
            INSERT INTO s360.fact_course_enrolls
            (id, so_school_id, student_code, subject_id, grade_id, is_moved_out, is_student)
            VALUES (:id, :sid, :scode, :subid, :gid, 0, 1)
            ON CONFLICT (id) DO NOTHING;
        """, course_enroll_batch)

    _batch_insert(session, """
        INSERT INTO s360.fact_subject_academic_records
        (id, overall_record_id, subject_id, student_code, final_grade, s1_final_grade)
        VALUES (:id, :oid, :subid, :scode, :fg, :s1fg)
        ON CONFLICT (id) DO NOTHING;
    """, subject_academic_batch)

    _batch_insert(session, """
        INSERT INTO s360.fact_overall_academic_records
        (id, so_school_id, school_year_id, grade_id, homeroom_class_id, student_id, student_code, final_grade, s1_final_grade, conduct, s1_conduct, learning_capacity, s1_learning_capacity)
        VALUES (:id, :sid, :syid, :gid, :cid, :st_id, :scode, :fg, :s1fg, CAST(:cond AS public.conduct_enum), CAST(:s1cond AS public.conduct_enum), :lcap, :s1lcap)
        ON CONFLICT (id) DO NOTHING;
    """, overall_academic_batch)

    if eval_process_batch:
        _batch_insert(session, """
            INSERT INTO s360.fact_so_evaluate_process_subjects
            (id, evaluate_progress_id, subject_id, student_code, school_year_id, semester_index, final_grade_level, student_level, comment, teacher_fullname)
            VALUES (:id, :eid, :subid, :scode, :syid, :sem, :fgl, :slevel, :comment, :tname)
            ON CONFLICT (id) DO NOTHING;
        """, eval_process_batch)

    session.commit()
    print("   ✅ Seeded gradebooks (mid-term + final) and academic records with batch inserts.")


# ---------------------------------------------------------------------------
# Phase 5: Seed attendance, behavior, late logs, absent logs
# ---------------------------------------------------------------------------
def _get_weekdays(start_dt, end_dt):
    """Tính danh sách các ngày trong tuần (T2-T6) từ start đến end INCLUSIVE."""
    days = (end_dt - start_dt).days
    return [start_dt + timedelta(days=i) for i in range(days + 1)
            if (start_dt + timedelta(days=i)).weekday() < 5]


def phase_attendance_behavior(session, student_meta_map):
    """Seed fact_so_daily_attendance (~185 school days), homeroom class attendances,
    behavior logs (tăng volume), late attendance logs, absent logs.
    Trả về all_school_dates cho benchmark phase."""
    print("\n📋 [6/8] Seeding Daily Attendance, Tardiness & Behavior Logs (Full 185-day school year)...")

    hk1_start = datetime(2025, 9, 5)
    hk1_end = datetime(2026, 1, 15)
    hk2_start = datetime(2026, 1, 20)
    hk2_end = datetime(2026, 5, 31)

    school_dates_hk1 = _get_weekdays(hk1_start, hk1_end)
    school_dates_hk2 = _get_weekdays(hk2_start, hk2_end)
    all_school_dates = school_dates_hk1 + school_dates_hk2
    total_school_days = len(all_school_dates)
    total_weeks = total_school_days // 5
    print(f"   School days: {len(school_dates_hk1)} HK1 + {len(school_dates_hk2)} HK2 = {total_school_days} total")

    # 5A. Seed fact_so_daily_attendance (BATCH INSERT)
    daily_att_batch = []
    school_name_map = {1: "Vinschool Central Park", 2: "Vinschool Golden River"}

    for scode, meta in student_meta_map.items():
        sid, syid, gid, cid = meta["school_id"], meta["school_year_id"], meta["grade_id"], meta["homeroom_class_id"]
        persona = meta["persona"]
        eff = meta["eff"]

        for day in all_school_dates:
            absent_prob = 1.0 / (1.0 + math.exp(1.0 * eff + 3.5))
            if persona == "Academic_At_Risk":
                absent_prob = max(absent_prob, 0.25)
            elif persona == "High_Achiever":
                absent_prob = min(absent_prob, 0.03)

            is_absent = random.random() < absent_prob
            total_p = 5

            if is_absent:
                absent_p = random.choices([2, 3, 4, 5], weights=[0.2, 0.4, 0.3, 0.1])[0]
                if persona == "Academic_At_Risk":
                    no_perm = random.choices([0, absent_p], weights=[0.3, 0.7])[0]
                elif persona == "High_Achiever":
                    no_perm = 0
                else:
                    no_perm = random.choices([0, absent_p], weights=[0.7, 0.3])[0]
                with_perm = max(0, absent_p - no_perm)
            else:
                absent_p = 0
                no_perm = 0
                with_perm = 0

            any_abs = 1 if absent_p > 0 else 0
            full_abs = 1 if absent_p >= total_p else 0
            week_start = day - timedelta(days=day.weekday())
            month_start = day.replace(day=1)

            daily_att_batch.append({
                "_date": day.date(), "ws": week_start.date(), "ms": month_start,
                "syid": syid, "sid": sid,
                "scode": scode, "cid": cid,
                "gid": gid, "tp": total_p, "ap": absent_p,
                "anp": no_perm, "awp": with_perm,
                "aaf": any_abs, "faf": full_abs
            })

    print(f"   Batch inserting {len(daily_att_batch)} daily attendance records...")
    _batch_insert(session, """
        INSERT INTO s360.fact_so_daily_attendance
        (_date, week_start, month_start, school_year_id, school_id,
         student_code, homeroom_class_id,
         grade_id, total_periods, absent_periods,
         absent_no_permission, absent_with_permission,
         any_absence_flag, full_subject_absence_flag)
        VALUES (:_date, :ws, :ms, :syid, :sid,
                :scode, :cid,
                :gid, :tp, :ap, :anp, :awp,
                :aaf, :faf);
    """, daily_att_batch)

    # 5B. Homeroom Class Attendances (BATCH INSERT)
    homeroom_att_batch = []
    for scode, meta in student_meta_map.items():
        sid, syid, gid, cid = meta["school_id"], meta["school_year_id"], meta["grade_id"], meta["homeroom_class_id"]
        persona = meta["persona"]
        eff = meta["eff"]
        absent_prob = 1.0 / (1.0 + math.exp(1.0 * eff + 3.5))
        if persona == "Academic_At_Risk":
            absent_prob = max(absent_prob, 0.20)
        elif persona == "High_Achiever":
            absent_prob = min(absent_prob, 0.02)

        for day in all_school_dates:
            status = 2 if random.random() < absent_prob else 1
            homeroom_att_batch.append({
                "sid": sid, "syid": syid, "cid": cid,
                "adate": day.date(), "scode": scode, "status": status
            })

    print(f"   Batch inserting {len(homeroom_att_batch)} homeroom attendance records...")
    _batch_insert(session, """
        INSERT INTO s360.fact_so_homeroom_class_attendances
        (so_school_id, school_year_id, homeroom_class_id, attendance_date, student_code, status)
        VALUES (:sid, :syid, :cid, :adate, :scode, :status);
    """, homeroom_att_batch)

    # 5C. Behavior Logs — TĂNG VOLUME (BATCH INSERT)
    beh_log_batch = []
    print("   Seeding behavior logs with temporal distribution (increased volume)...")
    for scode, meta in student_meta_map.items():
        sid, syid, gid, cid = meta["school_id"], meta["school_year_id"], meta["grade_id"], meta["homeroom_class_id"]
        persona = meta["persona"]
        eff = meta["eff"]

        if persona == "Academic_At_Risk":
            num_violations = random.randint(20, 50)
        elif persona in ["STEM_Focus", "Humanities_Focus", "Diligent_Average"]:
            num_violations = random.randint(8, 18)
        else:
            num_violations = random.randint(2, 5)

        for _ in range(num_violations):
            week_idx = random.choices(
                range(total_weeks),
                weights=[0.03 + (w / total_weeks) * 0.10 for w in range(total_weeks)]
            )[0]
            day_in_week = random.randint(0, 4)
            pick_idx = min(week_idx * 5 + day_in_week, total_school_days - 1)
            log_date = all_school_dates[pick_idx]

            if persona == "Academic_At_Risk":
                if week_idx < 6:
                    points_pool = [-1, -2, -3]
                    pt_weights = [0.5, 0.3, 0.2]
                elif week_idx < 12:
                    points_pool = [-2, -3, -5]
                    pt_weights = [0.3, 0.4, 0.3]
                else:
                    points_pool = [-3, -5, -10]
                    pt_weights = [0.3, 0.4, 0.3]
                b_point = random.choices(points_pool, weights=pt_weights)[0]
                b_id, b_code, b_name = random.choice([
                    (1, "BEH_LATE_MORNING", "Đi học muộn đầu giờ sáng (sau 7h30)"),
                    (2, "BEH_ABSENT_FULLDAY_NO_PERM", "Nghỉ học cả ngày không xin phép"),
                    (12, "BEH_CELLPHONE_CLASS", "Sử dụng điện thoại riêng trong giờ học"),
                    (10, "BEH_HOMEWORK_MISSING", "Không làm bài tập về nhà"),
                ])
            else:
                b_id, b_code, b_name, b_point = random.choice([
                    (7, "BEH_UNIFORM_WRONG", "Mặc sai đồng phục quy định của trường", -1.0),
                    (8, "BEH_NO_STUDENT_CARD", "Không đeo thẻ học sinh", -1.0),
                    (19, "BEH_GOOD_DEED", "Nhặt được của rơi trả lại người mất", 5.0),
                    (20, "BEH_HELP_PEER", "Tích cực phụ đạo / Giúp đỡ bạn học tiến bộ", 3.0),
                ])

            beh_log_batch.append({
                "sid": sid, "syid": syid, "scode": scode,
                "bid": b_id, "bcode": b_code, "bname": b_name,
                "bpt": b_point,
                "bcmt": f"Ghi nhận nếp sống ngày {log_date.strftime('%d/%m/%Y')}",
                "cdate": log_date.date()
            })

    print(f"   Batch inserting {len(beh_log_batch)} behavior logs...")
    _batch_insert(session, """
        INSERT INTO s360.fact_behavior_logs
        (so_school_id, school_year_id, student_code, behavior_id, behavior_code, behavior_fullname, behavior_point, behavior_comment, comment_date)
        VALUES (:sid, :syid, :scode, :bid, :bcode, :bname, :bpt, :bcmt, :cdate);
    """, beh_log_batch)

    # 5D. Late Attendance Logs — TĂNG VOLUME (BATCH INSERT)
    late_log_batch = []
    print("   Seeding late attendance logs (increased volume)...")
    for scode, meta in student_meta_map.items():
        sid, syid, gid, cid = meta["school_id"], meta["school_year_id"], meta["grade_id"], meta["homeroom_class_id"]
        persona = meta["persona"]
        eff = meta["eff"]
        sname = meta["student_name"]

        if persona == "Academic_At_Risk":
            num_lates = random.randint(15, 30)
        elif persona in ["STEM_Focus", "Humanities_Focus", "Diligent_Average"]:
            num_lates = random.randint(5, 12)
        else:
            num_lates = random.randint(1, 4)

        for _ in range(num_lates):
            week_idx = random.choices(
                range(total_weeks),
                weights=[0.02 + (w / total_weeks) * 0.12 for w in range(total_weeks)]
            )[0]
            day_in_week = random.randint(0, 4)
            pick_idx = min(week_idx * 5 + day_in_week, total_school_days - 1)
            late_date = all_school_dates[pick_idx]

            minutes_late = random.randint(5, 40)
            if persona == "Academic_At_Risk":
                minutes_late = random.randint(10, 60)

            late_log_batch.append({
                "sid": sid, "syid": syid, "gid": gid, "cid": cid,
                "adate": late_date.date(), "scode": scode, "sname": sname,
                "atime": datetime.combine(late_date.date(), datetime.min.time()) + timedelta(hours=7, minutes=30 + minutes_late),
                "tlate": minutes_late
            })

    print(f"   Batch inserting {len(late_log_batch)} late attendance records...")
    _batch_insert(session, """
        INSERT INTO s360.fact_so_homeroom_class_late_attendances
        (so_school_id, school_year_id, grade_id, homeroom_class_id, attendance_date, student_code, user_fullname, attendance_time, is_late, status_name, time_late)
        VALUES (:sid, :syid, :gid, :cid, :adate, :scode, :sname, :atime, 1, 'DI_MUON', :tlate);
    """, late_log_batch)

    # 5E. Absent Logs — TĂNG VOLUME (BATCH INSERT)
    abs_log_batch = []
    print("   Seeding absent logs (increased volume)...")
    for scode, meta in student_meta_map.items():
        sid, syid, gid, cid = meta["school_id"], meta["school_year_id"], meta["grade_id"], meta["homeroom_class_id"]
        persona = meta["persona"]
        eff = meta["eff"]

        if persona == "Academic_At_Risk":
            num_absents = random.randint(15, 40)
        elif persona in ["STEM_Focus", "Humanities_Focus", "Diligent_Average"]:
            num_absents = random.randint(5, 15)
        else:
            num_absents = random.randint(1, 5)

        for _ in range(num_absents):
            abs_date = random.choice(all_school_dates)
            is_excused = random.random() < 0.7 if persona != "Academic_At_Risk" else random.random() < 0.2
            reason_cat = "CO_PHEP" if is_excused else "KHONG_PHEP"
            reason_txt = "Nghỉ ốm có đơn xin phép phụ huynh" if is_excused else "Nghỉ học không lý do"

            abs_log_batch.append({
                "sid": sid, "syid": syid, "cid": cid, "scode": scode,
                "reason": reason_txt, "rcat": reason_cat, "adate": abs_date.date(),
                "app": 1 if is_excused else 0
            })

    print(f"   Batch inserting {len(abs_log_batch)} absence logs...")
    _batch_insert(session, """
        INSERT INTO s360.fact_absent_logs
        (so_school_id, school_year_id, homeroom_class_id, student_code, reason, reason_category, from_date, to_date, is_approved, absent_date)
        VALUES (:sid, :syid, :cid, :scode, :reason, :rcat, :adate, :adate, :app, :adate);
    """, abs_log_batch)

    session.commit()
    print(f"   ✅ Daily attendance: {len(daily_att_batch)} records across {total_school_days} school days.")
    print(f"   ✅ Homeroom attendances: {len(homeroom_att_batch)} records.")
    print(f"   ✅ Behavior logs: {len(beh_log_batch)} records.")
    print(f"   ✅ Late logs: {len(late_log_batch)} records.")
    print(f"   ✅ Absent logs: {len(abs_log_batch)} records.")
    return all_school_dates


# ---------------------------------------------------------------------------
# Phase 6: Aggregate attendance statistics
# ---------------------------------------------------------------------------
def phase_aggregated_attendance(session, student_meta_map):
    """Aggregate từ fact_so_daily_attendance vào fact_so_class_attendance_statistics (per-student, per-date)."""
    print("\n📊 [7/8] Aggregating Class Attendance Statistics from daily data...")

    # Query all daily attendance records
    rows = session.execute(text("""
        SELECT student_code, _date, homeroom_class_id, grade_id, school_id,
               school_year_id, total_periods, absent_periods
        FROM s360.fact_so_daily_attendance
        ORDER BY student_code, _date
    """)).fetchall()

    stats_batch = []
    for r in rows:
        total_lessons = r.total_periods or 0
        absent = r.absent_periods or 0
        attended = max(0, total_lessons - absent)
        stats_batch.append({
            "student_code": r.student_code,
            "date": r._date,
            "total_lesson": total_lessons,
            "lesson_attend": attended,
            "lesson_not_attend": absent,
            "homeroom_class_id": r.homeroom_class_id,
            "grade_id": r.grade_id,
            "so_school_id": r.school_id,
            "school_year_id": r.school_year_id,
        })

    if stats_batch:
        _batch_insert(session, """
            INSERT INTO s360.fact_so_class_attendance_statistics
            (student_code, date, total_lesson, lesson_attend, lesson_not_attend,
             homeroom_class_id, grade_id, so_school_id, school_year_id)
            VALUES (:student_code, :date, :total_lesson, :lesson_attend, :lesson_not_attend,
                    :homeroom_class_id, :grade_id, :so_school_id, :school_year_id)
            ON CONFLICT (id) DO NOTHING;
        """, stats_batch)

    session.commit()
    print(f"   ✅ Aggregated attendance statistics for {len(stats_batch)} student-days across {len(set(r.homeroom_class_id for r in rows))} classes.")


# ---------------------------------------------------------------------------
# Phase 7: Add benchmark edge case students (5 specific EWS scenarios)
#           Full subject coverage × both semesters × all exam types
# ---------------------------------------------------------------------------
def phase_benchmark(session, all_assignments, all_school_dates):
    """Thêm 5 benchmark students với edge cases cho EWS evaluation.
    Mỗi student có điểm cho ALL core subjects, cả 2 học kỳ,
    gồm assignment scores + mid-term + final exam scores."""
    print("\n🧪 [7c/8] Adding Benchmark Edge Case Students (5 students × 5 subjects × 2 semesters)...")

    CORE_SUBJECTS_GRADE7 = [107, 2, 3, 7, 8]  # TOAN_7, VAN, ANH, KHTN, LS_DL

    def _gen_declining_scores(weeks, start_high=9.5, end_low=1.5):
        """Tạo dãy điểm giảm dần đều."""
        return {w: round(float(np.clip(start_high - (start_high - end_low) * (w - 1) / (weeks - 1), 0.0, 10.0)), 1)
                for w in range(1, weeks + 1)}

    def _gen_stable_scores(weeks, mean=7.0, spread=0.8):
        """Tạo dãy điểm ổn định quanh mean."""
        return {w: round(float(np.clip(mean + random.uniform(-spread, spread), 0.0, 10.0)), 1)
                for w in range(1, weeks + 1)}

    def _gen_high_lms_low_exam(weeks):
        """G6 profile: LMS cao (9-10), thi thấp."""
        return {w: round(float(np.random.uniform(9.0, 10.0)), 1) for w in range(1, weeks + 1)}

    hk1_weeks = 18
    hk2_weeks = 17

    benchmark_students = [
        {
            "scode": "HS000EDGE01",
            "sname": "Nguyễn Văn A_SUT",
            "scenario": "Điểm cao → sụt giảm đột ngột tuần 12 (G7 profile)",
            "school_id": 1, "school_year_id": 2025, "grade_id": 7, "homeroom_class_id": 3,
            "subjects": CORE_SUBJECTS_GRADE7,
            # Assignment scores decline sharply for all subjects
            "assignment_scores_hk1": {sub: _gen_declining_scores(hk1_weeks, 9.5, 1.5) for sub in CORE_SUBJECTS_GRADE7},
            "assignment_scores_hk2": {sub: _gen_stable_scores(hk2_weeks, 2.0, 0.5) for sub in CORE_SUBJECTS_GRADE7},
            "exam_scores": {
                # (mid_hk1, final_hk1, mid_hk2, final_hk2)
                107: (8.5, 3.0, 2.5, 1.5),
                2:   (7.5, 2.5, 2.0, 1.0),
                3:   (8.0, 3.5, 3.0, 2.0),
                7:   (7.0, 2.0, 1.5, 1.0),
                8:   (8.0, 3.0, 2.5, 1.5),
            },
            "war_rate": 2.0, "demerits": 1,
        },
        {
            "scode": "HS000EDGE02",
            "sname": "Trần Thị B_WAR",
            "scenario": "Vắng không phép liên tục (WAR=45%) nhưng điểm vẫn cao",
            "school_id": 1, "school_year_id": 2025, "grade_id": 7, "homeroom_class_id": 3,
            "subjects": CORE_SUBJECTS_GRADE7,
            "assignment_scores_hk1": {sub: _gen_stable_scores(hk1_weeks, 8.8, 0.5) for sub in CORE_SUBJECTS_GRADE7},
            "assignment_scores_hk2": {sub: _gen_stable_scores(hk2_weeks, 8.5, 0.6) for sub in CORE_SUBJECTS_GRADE7},
            "exam_scores": {
                107: (8.5, 8.0, 8.2, 7.8),
                2:   (8.8, 8.3, 8.5, 8.0),
                3:   (9.0, 8.5, 8.8, 8.2),
                7:   (8.2, 7.8, 8.0, 7.5),
                8:   (8.5, 8.0, 8.3, 7.8),
            },
            "war_rate": 45.0, "demerits": 3,
        },
        {
            "scode": "HS000EDGE03",
            "sname": "Lê Văn C_TARDY",
            "scenario": "Đi muộn 10-15 phút mỗi ngày (tích lũy nhiều demerits)",
            "school_id": 1, "school_year_id": 2025, "grade_id": 7, "homeroom_class_id": 3,
            "subjects": CORE_SUBJECTS_GRADE7,
            "assignment_scores_hk1": {sub: _gen_stable_scores(hk1_weeks, 6.6, 0.5) for sub in CORE_SUBJECTS_GRADE7},
            "assignment_scores_hk2": {sub: _gen_stable_scores(hk2_weeks, 6.4, 0.6) for sub in CORE_SUBJECTS_GRADE7},
            "exam_scores": {
                107: (6.5, 6.0, 6.2, 5.8),
                2:   (6.8, 6.3, 6.5, 6.0),
                3:   (6.2, 5.8, 6.0, 5.5),
                7:   (6.0, 5.5, 5.8, 5.2),
                8:   (7.0, 6.5, 6.8, 6.2),
            },
            "war_rate": 12.0, "demerits": 5,
        },
        {
            "scode": "HS000EDGE04",
            "sname": "Phạm Văn D_LMSGAP",
            "scenario": "LMS full điểm (9-10) nhưng thi thấp (2-4) — G6 profile",
            "school_id": 1, "school_year_id": 2025, "grade_id": 7, "homeroom_class_id": 3,
            "subjects": CORE_SUBJECTS_GRADE7,
            "assignment_scores_hk1": {sub: _gen_high_lms_low_exam(hk1_weeks) for sub in CORE_SUBJECTS_GRADE7},
            "assignment_scores_hk2": {sub: _gen_high_lms_low_exam(hk2_weeks) for sub in CORE_SUBJECTS_GRADE7},
            "exam_scores": {
                107: (3.0, 2.5, 3.5, 3.0),
                2:   (4.0, 3.5, 4.2, 3.8),
                3:   (2.5, 2.0, 3.0, 2.5),
                7:   (3.5, 3.0, 4.0, 3.5),
                8:   (3.0, 2.5, 3.5, 3.0),
            },
            "war_rate": 5.0, "demerits": 0,
        },
        {
            "scode": "HS000EDGE05",
            "sname": "Hoàng Văn E_GRADIENT",
            "scenario": "Điểm TB (6.5) nhưng đang giảm mạnh qua các tuần",
            "school_id": 1, "school_year_id": 2025, "grade_id": 7, "homeroom_class_id": 3,
            "subjects": CORE_SUBJECTS_GRADE7,
            "assignment_scores_hk1": {sub: _gen_declining_scores(hk1_weeks, 7.0, 2.0) for sub in CORE_SUBJECTS_GRADE7},
            "assignment_scores_hk2": {sub: _gen_declining_scores(hk2_weeks, 3.0, 0.5) for sub in CORE_SUBJECTS_GRADE7},
            "exam_scores": {
                107: (6.5, 3.5, 3.0, 2.0),
                2:   (6.0, 3.0, 2.5, 1.5),
                3:   (7.0, 4.0, 3.5, 2.5),
                7:   (5.5, 3.0, 2.5, 1.5),
                8:   (6.5, 3.5, 3.0, 2.0),
            },
            "war_rate": 8.0, "demerits": 2,
        },
    ]

    gid_counter = 1
    gradebook_batch = []
    gradebook_moet_batch = []
    assign_grade_batch = []
    daily_att_batch = []
    beh_log_batch = []
    subject_academic_batch = []
    overall_academic_batch = []
    total_school_days = len(all_school_dates)

    for i, bm in enumerate(benchmark_students, 1):
        scode = bm["scode"]
        sid = bm["school_id"]
        syid = bm["school_year_id"]
        gid_v = bm["grade_id"]
        cid = bm["homeroom_class_id"]
        sname = bm["sname"]
        subjects = bm["subjects"]

        # Insert into dim_homeroom_class_student
        session.execute(text("""
            INSERT INTO s360.dim_homeroom_class_student
            (id, so_student_id, student_code, student_name, homeroom_class_id, class_code, class_name,
             so_school_id, school_year_id, school_name, grade_id, grade_name, moet_code)
            VALUES (:idx, :idx, :scode, :sname, :cid, :ccode, :cname, :sid, :syid, :sname_sch, :gid, :gname, :mcode)
            ON CONFLICT (id) DO NOTHING;
        """), {
            "idx": 99990 + i, "scode": scode, "sname": sname, "cid": cid,
            "ccode": f"CLASS_{sid}_{gid_v}A1", "cname": f"Lớp {gid_v}A1",
            "sid": sid, "syid": syid,
            "sname_sch": "Vinschool Central Park",
            "gid": gid_v, "gname": f"Khối {gid_v}", "mcode": f"MOET_{scode}"
        })

        # === ASSIGNMENT SCORES (HK1 + HK2) ===
        for sem_idx in [1, 2]:
            scores_dict = bm["assignment_scores_hk1"] if sem_idx == 1 else bm["assignment_scores_hk2"]
            for sub_id in subjects:
                week_scores = scores_dict.get(sub_id, {})
                for week_num, score_val in week_scores.items():
                    # Find matching assignment
                    matching_assign = next(
                        (a for a in all_assignments
                         if a["so_school_id"] == sid and a["grade_id"] == gid_v
                         and a["subject_id"] == sub_id and a["semester_index"] == sem_idx
                         and (a["date_assigned"] - date(2025, 9, 5)).days // 7 + 1 == week_num),
                        None
                    )
                    if matching_assign:
                        assign_grade_batch.append({
                            "id": gid_counter, "sid": sid,
                            "aid": matching_assign["assignment_id"],
                            "scode": scode, "fg": score_val
                        })
                        gid_counter += 1

        # === GRADEBOOK: MID-TERM + FINAL (HK1 + HK2) ===
        exam_scores = bm["exam_scores"]
        for sub_id in subjects:
            sub_exams = exam_scores.get(sub_id, (5.0, 5.0, 5.0, 5.0))
            for exam_idx, (exam_id, sem_idx, type_item_id) in enumerate([
                (1, 1, 1), (2, 1, 2), (3, 2, 3), (4, 2, 4)
            ]):
                score_val = sub_exams[exam_idx]
                pf_status = 'DAT' if score_val >= 5.0 else 'CHUA_DAT'

                gradebook_batch.append({
                    "id": gid_counter, "sid": sid, "syid": syid,
                    "sem": sem_idx, "scode": scode, "cid": cid,
                    "subid": sub_id, "eid": exam_id,
                    "score": score_val, "pf": pf_status,
                    "is_locked": 1, "created_at": EXAM_CREATED_AT[exam_id]
                })
                gradebook_moet_batch.append({
                    "id": gid_counter, "sid": sid, "syid": syid,
                    "sem": sem_idx, "gid": gid_v, "cid": cid, "scode": scode,
                    "subid": sub_id, "type_item_id": type_item_id,
                    "score": score_val,
                    "is_locked": 1, "created_at": EXAM_CREATED_AT[exam_id]
                })
                gid_counter += 1

        # === DAILY ATTENDANCE (dựa trên war_rate) ===
        for day in all_school_dates:
            is_absent = random.random() < (bm["war_rate"] / 100.0)
            total_p = 5
            if is_absent:
                absent_p = random.randint(2, 5)
                no_perm = absent_p if bm["war_rate"] > 20 else 0
            else:
                absent_p = 0
                no_perm = 0
            with_perm = max(0, absent_p - no_perm)
            week_start = day - timedelta(days=day.weekday())

            daily_att_batch.append({
                "_date": day.date(), "ws": week_start.date(), "ms": day.replace(day=1),
                "syid": syid, "sid": sid, "scode": scode, "cid": cid,
                "gid_v": gid_v, "tp": total_p, "ap": absent_p,
                "anp": no_perm, "awp": with_perm,
                "aaf": 1 if absent_p > 0 else 0, "faf": 1 if absent_p >= total_p else 0
            })

        # === BEHAVIOR LOGS ===
        for _ in range(bm["demerits"]):
            log_date = random.choice(all_school_dates)
            b_id, b_code, b_name, b_point = random.choice([
                (1, "BEH_LATE_MORNING", "Đi học muộn đầu giờ sáng (sau 7h30)", -2.0),
                (10, "BEH_HOMEWORK_MISSING", "Không làm bài tập về nhà", -2.0),
                (12, "BEH_CELLPHONE_CLASS", "Sử dụng điện thoại riêng trong giờ học", -3.0),
            ])
            beh_log_batch.append({
                "sid": sid, "syid": syid, "scode": scode,
                "bid": b_id, "bcode": b_code, "bname": b_name, "bpt": b_point,
                "bcmt": f"Benchmark: {bm['scenario']}", "cdate": log_date.date()
            })

        # === SUBJECT ACADEMIC RECORDS ===
        for sub_id in subjects:
            avg_exam = sum(exam_scores.get(sub_id, (5.0, 5.0, 5.0, 5.0))) / 4.0
            subject_academic_batch.append({
                "id": gid_counter, "oid": gid_counter,
                "subid": sub_id, "scode": scode,
                "fg": round(avg_exam, 1), "s1fg": round(avg_exam, 1)
            })
            gid_counter += 1

        # === OVERALL ACADEMIC RECORD ===
        all_exam_vals = []
        for sub_id in subjects:
            all_exam_vals.extend(exam_scores.get(sub_id, (5.0, 5.0, 5.0, 5.0)))
        gpa_bm = round(float(np.mean(all_exam_vals)), 1)

        overall_academic_batch.append({
            "id": gid_counter, "sid": sid, "syid": syid, "gid": gid_v,
            "cid": cid, "st_id": gid_counter, "scode": scode,
            "fg": gpa_bm, "s1fg": gpa_bm,
            "cond": "KHA", "s1cond": "KHA",
            "lcap": "Khá" if gpa_bm >= 6.5 else ("Trung bình" if gpa_bm >= 5.0 else "Yếu"),
            "s1lcap": "Khá" if gpa_bm >= 6.5 else ("Trung bình" if gpa_bm >= 5.0 else "Yếu"),
        })
        gid_counter += 1

    # === BATCH INSERTS ===
    if assign_grade_batch:
        _batch_insert(session, """
            INSERT INTO s360.fact_so_assignment_grade
            (id, so_school_id, assignment_id, student_code, final_grade)
            VALUES (:id, :sid, :aid, :scode, :fg)
            ON CONFLICT (id) DO NOTHING;
        """, assign_grade_batch)

    if gradebook_batch:
        _batch_insert(session, """
            INSERT INTO s360.fact_gradebooks
            (id, so_school_id, school_year_id, semester_index, student_code, homeroom_class_id, subject_id, so_exam_id, final_grade, pass_fail_status, is_locked, created_at)
            VALUES (:id, :sid, :syid, :sem, :scode, :cid, :subid, :eid, :score, CAST(:pf AS public.pass_fail_enum), :is_locked, :created_at)
            ON CONFLICT (id) DO NOTHING;
        """, gradebook_batch)

    if gradebook_moet_batch:
        _batch_insert(session, """
            INSERT INTO s360.fact_gradebooks_moet
            (id, so_school_id, school_year_id, semester_index, grade_id, homeroom_class_id, student_code, subject_id, gradebook_type_item_id, final_grade, is_locked, created_at)
            VALUES (:id, :sid, :syid, :sem, :gid, :cid, :scode, :subid, :type_item_id, :score, :is_locked, :created_at)
            ON CONFLICT (id) DO NOTHING;
        """, gradebook_moet_batch)

    if daily_att_batch:
        _batch_insert(session, """
            INSERT INTO s360.fact_so_daily_attendance
            (_date, week_start, month_start, school_year_id, school_id,
             student_code, homeroom_class_id, grade_id,
             total_periods, absent_periods,
             absent_no_permission, absent_with_permission,
             any_absence_flag, full_subject_absence_flag)
            VALUES (:_date, :ws, :ms, :syid, :sid,
                    :scode, :cid, :gid_v,
                    :tp, :ap, :anp, :awp, :aaf, :faf);
        """, daily_att_batch)

    if beh_log_batch:
        _batch_insert(session, """
            INSERT INTO s360.fact_behavior_logs
            (so_school_id, school_year_id, student_code, behavior_id, behavior_code, behavior_fullname, behavior_point, behavior_comment, comment_date)
            VALUES (:sid, :syid, :scode, :bid, :bcode, :bname, :bpt, :bcmt, :cdate);
        """, beh_log_batch)

    if subject_academic_batch:
        _batch_insert(session, """
            INSERT INTO s360.fact_subject_academic_records
            (id, overall_record_id, subject_id, student_code, final_grade, s1_final_grade)
            VALUES (:id, :oid, :subid, :scode, :fg, :s1fg)
            ON CONFLICT (id) DO NOTHING;
        """, subject_academic_batch)

    if overall_academic_batch:
        _batch_insert(session, """
            INSERT INTO s360.fact_overall_academic_records
            (id, so_school_id, school_year_id, grade_id, homeroom_class_id, student_id, student_code, final_grade, s1_final_grade, conduct, s1_conduct, learning_capacity, s1_learning_capacity)
            VALUES (:id, :sid, :syid, :gid, :cid, :st_id, :scode, :fg, :s1fg, CAST(:cond AS public.conduct_enum), CAST(:s1cond AS public.conduct_enum), :lcap, :s1lcap)
            ON CONFLICT (id) DO NOTHING;
        """, overall_academic_batch)

    session.commit()
    print(f"   ✅ Added {len(benchmark_students)} benchmark edge case students with full subject coverage.")
    for bm in benchmark_students:
        print(f"      • {bm['scode']} ({bm['sname']}): {bm['scenario']}")


# ---------------------------------------------------------------------------
# Phase 8: Sync metadata indexer
# ---------------------------------------------------------------------------
def phase_metadata():
    """Đồng bộ metadata index cho hybrid search entity linker."""
    print("\n🔍 [8/8] Syncing Metadata Indexer for both Schools...")
    for school_id in [1, 2]:
        print(f"   Syncing metadata index for School {school_id}...")
        sync_school_metadata(so_school_id=school_id)


# =====================================================================
# MAIN GENERATOR — dispatches by phase
# =====================================================================
def generate_full_system_mock_data(phase="all"):
    """Điều phối việc generate mock data theo phase.

    Args:
        phase: Tên phase cần chạy, hoặc "all" để chạy tất cả.
               Các phase: truncate, users, dimensions, students, academic,
               attendance_behavior, aggregated_attendance,
               benchmark, metadata
    """
    print("🚀 STARTING MASTER MULTI-SCHOOL MOCK DATA GENERATION (37 TABLES)...")
    session = SessionLocal()

    try:
        if phase in ("all", "truncate"):
            phase_truncate(session)
            session.commit()

        if phase in ("all", "users"):
            phase_users(session)
            session.commit()

        if phase in ("all", "dimensions"):
            classes_data, all_assignments = phase_dimensions(session)
            session.commit()

        if phase in ("all", "students"):
            # classes_data cần từ dimensions phase
            if "classes_data" not in dir():
                classes_data = session.execute(text(
                    "SELECT id, so_school_id, school_year_id, grade_id, code, fullname FROM s360.dim_homeroom_class ORDER BY id"
                )).fetchall()
            student_meta_map = phase_students(session, classes_data)
            session.commit()

        if phase in ("all", "academic"):
            if "all_assignments" not in dir():
                assign_rows = session.execute(text(
                    "SELECT assignment_id, so_school_id, grade_id, semester_index, subject_id, code, fullname, max_grade, date_assigned, due_date FROM s360.dim_so_assignment ORDER BY assignment_id"
                )).fetchall()
                all_assignments = []
                for row in assign_rows:
                    all_assignments.append({
                        "assignment_id": row[0], "so_school_id": row[1],
                        "grade_id": row[2], "semester_index": row[3],
                        "subject_id": row[4], "code": row[5], "fullname": row[6],
                        "max_grade": row[7], "date_assigned": row[8], "due_date": row[9],
                    })
            if "student_meta_map" not in dir():
                student_meta_map = _build_student_meta_from_db(session)
            phase_academic(session, student_meta_map, all_assignments)
            session.commit()

        if phase in ("all", "attendance_behavior"):
            if "student_meta_map" not in dir():
                student_meta_map = _build_student_meta_from_db(session)
            all_school_dates = phase_attendance_behavior(session, student_meta_map)
            session.commit()

        if phase in ("all", "aggregated_attendance"):
            if "student_meta_map" not in dir():
                student_meta_map = _build_student_meta_from_db(session)
            phase_aggregated_attendance(session, student_meta_map)
            session.commit()

        if phase in ("all", "benchmark"):
            if "all_assignments" not in dir():
                assign_rows = session.execute(text(
                    "SELECT assignment_id, so_school_id, grade_id, semester_index, subject_id, code, fullname, max_grade, date_assigned, due_date FROM s360.dim_so_assignment ORDER BY assignment_id"
                )).fetchall()
                all_assignments = []
                for row in assign_rows:
                    all_assignments.append({
                        "assignment_id": row[0], "so_school_id": row[1],
                        "grade_id": row[2], "semester_index": row[3],
                        "subject_id": row[4], "code": row[5], "fullname": row[6],
                        "max_grade": row[7], "date_assigned": row[8], "due_date": row[9],
                    })
            if "all_school_dates" not in dir():
                all_school_dates = _get_all_school_dates()
            phase_benchmark(session, all_assignments, all_school_dates)
            session.commit()

        if phase in ("all", "metadata"):
            phase_metadata()

        if phase == "all":
            print("\n================ MASTER MOCK DATA GENERATION COMPLETE ================")
            print(" Successfully populated all 37 database tables across 2 Schools!")
            print(" Total Students: 1,023 + 5 benchmark | Total Classes: 27 | Total System Tables: 37")
            print(" School Days: ~185 (HK1 + HK2) | Assignments: ~2,800")
            print(" Exams per subject: 4 (Mid HK1, Final HK1, Mid HK2, Final HK2)")
            print(" Batch insert mode: ON (chunk size = 10,000)")

    except Exception as e:
        session.rollback()
        print(f"❌ Error during master data generation: {e}")
        raise e
    finally:
        session.close()


def _build_student_meta_from_db(session):
    """Build student_meta_map từ DB (dùng khi chạy standalone phase)."""
    rows = session.execute(text("""
        SELECT student_code, so_school_id, school_year_id, grade_id, homeroom_class_id, student_name
        FROM s360.dim_homeroom_class_student
    """)).fetchall()
    meta = {}
    for r in rows:
        meta[r[0]] = {
            "school_id": r[1], "school_year_id": r[2],
            "grade_id": r[3], "homeroom_class_id": r[4],
            "student_name": r[5],
            "persona": "Diligent_Average", "profile": "G2",
            "c_math": 0.0, "c_lang": 0.0, "eff": 0.0,
        }
    return meta


def _get_all_school_dates():
    """Tính danh sách school dates (dùng khi chạy standalone benchmark phase)."""
    hk1_start = datetime(2025, 9, 5)
    hk1_end = datetime(2026, 1, 15)
    hk2_start = datetime(2026, 1, 20)
    hk2_end = datetime(2026, 5, 31)
    dates = []
    for i in range((hk1_end - hk1_start).days + 1):
        d = hk1_start + timedelta(days=i)
        if d.weekday() < 5:
            dates.append(d)
    for i in range((hk2_end - hk2_start).days + 1):
        d = hk2_start + timedelta(days=i)
        if d.weekday() < 5:
            dates.append(d)
    return dates


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate mock data for TTS_SRA")
    parser.add_argument(
        "--phase",
        choices=["all", "truncate", "users", "dimensions", "students",
                 "academic", "attendance_behavior", "aggregated_attendance",
                 "benchmark", "metadata"],
        default="all",
        help="Phase to execute (default: all)"
    )
    args = parser.parse_args()
    generate_full_system_mock_data(phase=args.phase)
