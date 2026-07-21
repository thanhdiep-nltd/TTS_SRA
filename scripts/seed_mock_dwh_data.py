import os
import sys
import random
from pathlib import Path
from datetime import datetime, date, timedelta
from dotenv import load_dotenv

if sys.platform.startswith("win"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Load .env
env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

db_url = os.getenv("DATABASE_URL")
if not db_url:
    print("[ERROR] DATABASE_URL is not set in .env")
    sys.exit(1)

print(f"[INFO] Seeding Mock DWH Data on: {db_url[:40]}...")

import psycopg
from bcrypt import hashpw, gensalt

def get_hashed_password(plain: str) -> str:
    return hashpw(plain.encode('utf-8'), gensalt()).decode('utf-8')

# --- HỌ TÊN VIỆT NAM THỰC TẾ ---
FAMILY_NAMES = ["Nguyễn", "Trần", "Lê", "Phạm", "Hoàng", "Huỳnh", "Vũ", "Võ", "Phan", "Trương", "Bùi", "Đặng", "Đỗ", "Ngô"]
MALE_MIDDLES = ["Văn", "Minh", "Đức", "Quốc", "Hữu", "Ngọc", "Anh", "Thành", "Gia", "Khánh"]
FEMALE_MIDDLES = ["Thị", "Thanh", "Ngọc", "Thảo", "Minh", "Quỳnh", "Phương", "Thu", "Trúc", "Như"]
MALE_GIVENS = ["Huy", "Khang", "Bảo", "Minh", "Anh", "Bình", "Cường", "Duy", "Đạt", "Gia", "Hải", "Hùng", "Nam", "Phúc", "Quân", "Sơn", "Tùng", "Tuấn"]
FEMALE_GIVENS = ["Anh", "Vy", "Linh", "Phương", "Quỳnh", "Thảo", "Trang", "Mai", "Ngọc", "Hương", "Chi", "Diệp", "Dung", "Giang", "Hà", "Yến"]

random.seed(42)

def generate_vietnamese_name():
    is_male = random.choice([True, False])
    family = random.choice(FAMILY_NAMES)
    if is_male:
        middle = random.choice(MALE_MIDDLES)
        given = random.choice(MALE_GIVENS)
        gender_str = "Nam"
    else:
        middle = random.choice(FEMALE_MIDDLES)
        given = random.choice(FEMALE_GIVENS)
        gender_str = "Nữ"
    return f"{family} {middle} {given}", gender_str

SO_SCHOOL_ID = 101
TENANT_ID = 1

def seed():
    conn = psycopg.connect(db_url, autocommit=True)
    cur = conn.cursor()

    print("[INFO] 1. Truncating target mock tables...")
    tables_to_truncate = [
        "public.users",
        "s360.dim_grade_scale_detail",
        "s360.dim_school_year",
        "s360.dim_subject",
        "s360.dim_so_school_mapping_subject",
        "s360.dim_homeroom_class",
        "s360.dim_homeroom_class_student",
        "s360.dim_course",
        "s360.dim_exam",
        "s360.dim_exam_moet",
        "s360.dim_behavior",
        "s360.dim_so_assignment",
        "s360.dim_so_evaluate_progress",
        "s360.dim_extracurricular_activity",
        "s360.fact_gradebooks_moet",
        "s360.fact_gradebooks",
        "s360.fact_subject_academic_records",
        "s360.fact_overall_academic_records",
        "s360.fact_so_subject_mastery",
        "s360.fact_so_daily_attendance",
        "s360.fact_absent_logs",
        "s360.fact_course_attendences",
        "s360.fact_so_class_attendance_statistics",
        "s360.fact_so_homeroom_class_attendances",
        "s360.fact_so_homeroom_class_late_attendances",
        "s360.fact_so_absent_extract_late",
        "s360.fact_behavior_logs",
        "s360.fact_so_evaluate_process_subjects",
        "s360.fact_so_evaluate_process_subject_criterion",
        "s360.fact_so_assignment_grade",
        "t360.dim_t360_homeroom_class_teacher",
        '"default".stg_so_exam_moet_path',
        '"default".stg_so_strand_path',
        '"default".stg_so_students'
    ]

    for tbl in tables_to_truncate:
        try:
            cur.execute(f"TRUNCATE TABLE {tbl} CASCADE;")
        except Exception as e:
            print(f"  [WARN] Truncate {tbl}: {e}")

    hashed_pw = get_hashed_password("password123")

    # 1. Seed Users (Public - BGH & Giáo viên)
    print("[INFO] 2. Seeding Users (Public - Admin, Principal, Teachers)...")
    users_data = [
        (SO_SCHOOL_ID, TENANT_ID, "admin@vinschool.edu.vn", hashed_pw, "Quản Trị Viên", "ADMIN", "ALL", "ADM001"),
        (SO_SCHOOL_ID, TENANT_ID, "principal@vinschool.edu.vn", hashed_pw, "Nguyễn Minh Triết", "PRINCIPAL", "ALL", "HT001"),
        (SO_SCHOOL_ID, TENANT_ID, "teacher.math@vinschool.edu.vn", hashed_pw, "Trần Đức Lương", "HOMEROOM_TEACHER_SECONDARY", "SECONDARY", "GV001"),
        (SO_SCHOOL_ID, TENANT_ID, "teacher.literature@vinschool.edu.vn", hashed_pw, "Phạm Thanh Vân", "SUBJECT_TEACHER", "SECONDARY", "GV002"),
        (SO_SCHOOL_ID, TENANT_ID, "teacher.english@vinschool.edu.vn", hashed_pw, "Lê Hoàng Nam", "SUBJECT_TEACHER", "SECONDARY", "GV003"),
        (SO_SCHOOL_ID, TENANT_ID, "teacher.physics@vinschool.edu.vn", hashed_pw, "Đặng Thu Thảo", "SUBJECT_TEACHER", "HIGH", "GV004"),
        (SO_SCHOOL_ID, TENANT_ID, "teacher.chemistry@vinschool.edu.vn", hashed_pw, "Vũ Văn Minh", "SUBJECT_TEACHER", "HIGH", "GV005"),
    ]
    for u in users_data:
        cur.execute("""
            INSERT INTO public.users (so_school_id, tenant_id, email, hashed_password, full_name, role, school_level, teacher_code, is_active)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, TRUE);
        """, u)

    # 2. Seed School Years (s360.dim_school_year)
    print("[INFO] 3. Seeding School Years (s360.dim_school_year)...")
    cur.execute("""
        INSERT INTO s360.dim_school_year (id, code, fullname, is_current)
        VALUES (2025, '2025-2026', 'Năm học 2025-2026', 1), (2024, '2024-2025', 'Năm học 2024-2025', 0);
    """)

    # 3. Seed Universal Percentage Bridge Scale (s360.dim_grade_scale_detail)
    print("[INFO] 4. Seeding Grade Scale Detail Universal Bridge (s360.dim_grade_scale_detail)...")
    grade_scales = [
        (1, SO_SCHOOL_ID, "MOET_THANG_10", 10.0, 9.0, 10.0, 90.0, 100.0, 95.0, "Giỏi"),
        (2, SO_SCHOOL_ID, "MOET_THANG_10", 10.0, 7.0, 8.9, 70.0, 89.0, 80.0, "Khá"),
        (3, SO_SCHOOL_ID, "MOET_THANG_10", 10.0, 5.0, 6.9, 50.0, 69.0, 60.0, "TB"),
        (4, SO_SCHOOL_ID, "MOET_THANG_10", 10.0, 0.0, 4.9, 0.0, 49.0, 25.0, "Yếu"),
        (5, SO_SCHOOL_ID, "CAMBRIDGE_LETTER", 6.0, 5.0, 6.0, 85.0, 100.0, 92.5, "A"),
        (6, SO_SCHOOL_ID, "CAMBRIDGE_LETTER", 6.0, 4.0, 4.9, 70.0, 84.9, 77.5, "B"),
        (7, SO_SCHOOL_ID, "CAMBRIDGE_LETTER", 6.0, 3.0, 3.9, 55.0, 69.9, 62.5, "C"),
        (8, SO_SCHOOL_ID, "CAMBRIDGE_LETTER", 6.0, 0.0, 2.9, 0.0, 54.9, 27.5, "F"),
    ]
    for gs in grade_scales:
        cur.execute("""
            INSERT INTO s360.dim_grade_scale_detail 
            (id, so_school_id, scale_name, max_score, min_score_range, max_score_range, min_percent, max_percent, representative_percent, grade_letter)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
        """, gs)

    # 4. Seed Homeroom Classes (s360.dim_homeroom_class)
    print("[INFO] 5. Seeding Homeroom Classes (s360.dim_homeroom_class)...")
    classes_info = [
        (601, SO_SCHOOL_ID, 2025, 6, "6A1", "Lớp 6A1"),
        (702, SO_SCHOOL_ID, 2025, 7, "7A2", "Lớp 7A2"),
        (1001, SO_SCHOOL_ID, 2025, 10, "10B1", "Lớp 10B1"),
        (1102, SO_SCHOOL_ID, 2025, 11, "11C2", "Lớp 11C2"),
    ]
    for cl in classes_info:
        cur.execute("""
            INSERT INTO s360.dim_homeroom_class (id, so_school_id, school_year_id, grade_id, code, fullname)
            VALUES (%s, %s, %s, %s, %s, %s);
        """, cl)

    # 5. Seed Students (DWH - s360.dim_homeroom_class_student)
    print("[INFO] 6. Seeding 30 Students in DWH (s360.dim_homeroom_class_student)...")
    students_list = []
    student_id_counter = 1001
    pk_id_counter = 1
    for cl_id, cl_code in [(601, "6A1"), (702, "7A2"), (1001, "10B1"), (1102, "11C2")]:
        count_in_class = 8 if cl_id in [601, 1001] else 7
        for i in range(count_in_class):
            st_name, st_gender = generate_vietnamese_name()
            st_code = f"HS{student_id_counter}"
            students_list.append({
                "so_student_id": student_id_counter,
                "so_school_id": SO_SCHOOL_ID,
                "tenant_id": TENANT_ID,
                "homeroom_class_id": cl_id,
                "student_code": st_code,
                "student_fullname": st_name,
                "student_gender": st_gender,
                # Năng lực giả lập: 60% Giỏi/Khá, 25% Cảnh báo, 15% Rủi ro Cao
                "risk_category": "HIGH_RISK" if i >= 5 else ("WARNING" if i >= 3 else "SAFE")
            })
            cur.execute("""
                INSERT INTO s360.dim_homeroom_class_student (id, tenant_id, so_student_id, student_code, homeroom_class_id, class_code, class_name, so_school_id, school_year_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 2025);
            """, (pk_id_counter, TENANT_ID, student_id_counter, st_code, cl_id, cl_code, f"Lớp {cl_code}", SO_SCHOOL_ID))
            student_id_counter += 1
            pk_id_counter += 1

    # 6. Seed Subjects & Mapping (s360.dim_subject & dim_so_school_mapping_subject)
    print("[INFO] 7. Seeding Subjects (s360.dim_subject & dim_so_school_mapping_subject)...")
    subjects = [
        (1, "TOAN", "Toán học"),
        (2, "VAN", "Ngữ văn"),
        (3, "ANH", "Tiếng Anh"),
        (4, "LY", "Vật lý"),
        (5, "HOA", "Hóa học"),
    ]
    for sub in subjects:
        cur.execute("""
            INSERT INTO s360.dim_subject (id, code, name, is_active)
            VALUES (%s, %s, %s, 1);
        """, sub)
        cur.execute("""
            INSERT INTO s360.dim_so_school_mapping_subject (so_school_id, subject_id, subject_name, school_year_id)
            VALUES (%s, %s, %s, 2025);
        """, (SO_SCHOOL_ID, sub[0], sub[2]))

    # 7. Seed Exam Types (dim_exam & dim_exam_moet)
    print("[INFO] 8. Seeding Exams (s360.dim_exam & dim_exam_moet)...")
    exams = [
        (1, "Miệng 1", "TX1", 1.0),
        (2, "Thường xuyên 1", "TX2", 1.0),
        (3, "Thường xuyên 2", "TX3", 1.0),
        (4, "Kiểm tra Giữa kỳ HK1", "GK", 2.0),
        (5, "Thi Cuối kỳ HK1", "CK", 3.0),
    ]
    for ex in exams:
        cur.execute("""
            INSERT INTO s360.dim_exam (id, so_exam_id, exam_name, coefficient)
            VALUES (%s, %s, %s, %s);
        """, (ex[0], ex[0], ex[1], ex[3]))
        cur.execute("""
            INSERT INTO s360.dim_exam_moet (gradebook_type_item_id, tenant_id, gradebook_type_items_code, gradebook_type_items_fullname, coefficient)
            VALUES (%s, %s, %s, %s, %s);
        """, (ex[0], TENANT_ID, ex[2], ex[1], ex[3]))

    # 8. Seed Gradebooks (fact_gradebooks_moet & fact_gradebooks) with Risk Scenarios
    print("[INFO] 9. Seeding Gradebook Scores with 3 Risk Scenarios (fact_gradebooks_moet & fact_gradebooks)...")
    fact_id_counter = 1
    for st in students_list:
        st_code = st["student_code"]
        st_id = st["so_student_id"]
        risk = st["risk_category"]
        
        for sub in subjects:
            sub_id = sub[0]
            for ex in exams:
                ex_id = ex[0]
                
                # Tính điểm theo Kịch bản Rủi ro
                if risk == "SAFE":
                    score = round(random.uniform(7.5, 10.0), 1)
                elif risk == "WARNING":
                    score = round(random.uniform(5.0, 6.4), 1)
                else: # HIGH_RISK
                    if ex[2] in ["GK", "CK"]:
                        score = round(random.uniform(2.5, 4.8), 1) # Bị rủi ro trượt môn ở thi HK
                    else:
                        score = round(random.uniform(4.0, 5.5), 1)
                
                # Seed into MOET Gradebook (Gieo đầy đủ 100% thông tin phẳng DWH)
                now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                cl_id = st["homeroom_class_id"]
                grade_id = 6 if cl_id == 601 else (7 if cl_id == 702 else (10 if cl_id == 1001 else 11))
                cur.execute("""
                    INSERT INTO s360.fact_gradebooks_moet 
                    (id, tenant_id, so_school_id, school_code, school_name, grade_id, grade_code, grade_name, 
                     subject_id, school_year_id, semester_index, semester_stages, so_user_id, student_code, 
                     homeroom_class_id, gradebook_type_item_id, final_grade, is_semester_locked, is_locked, is_deleted, created_at, source_system)
                    VALUES (%s, %s, %s, 'VINSCHOOL', 'Trường Vinschool', %s, %s, %s, %s, 2025, 1, 1, %s, %s, %s, %s, %s, 0, 0, 0, %s, 'SCHOOL_ONLINE_DWH');
                """, (fact_id_counter, TENANT_ID, SO_SCHOOL_ID, grade_id, f"KHOI_{grade_id}", f"Khối {grade_id}", sub_id, st_id, st_code, cl_id, ex_id, score, now_str))

                # Seed into LMS Gradebook (Gieo đầy đủ 100% thông tin phẳng DWH)
                cur.execute("""
                    INSERT INTO s360.fact_gradebooks 
                    (id, so_school_id, school_year_id, semester_index, semester_stages, student_code, subject_id, 
                     homeroom_class_id, so_exam_id, final_grade, max_grade, is_locked, grade_id, created_at, source_system)
                    VALUES (%s, %s, 2025, 1, 1, %s, %s, %s, %s, %s, 10.0, 0, %s, %s, 'SCHOOL_ONLINE_LMS');
                """, (fact_id_counter, SO_SCHOOL_ID, st_code, sub_id, cl_id, ex_id, score, grade_id, now_str))
                fact_id_counter += 1

    # 9. Seed Attendance & Absence Logs (fact_so_daily_attendance & fact_absent_logs)
    print("[INFO] 10. Seeding Daily Attendance & Absence Logs...")
    today = date.today()
    absent_id_counter = 1
    for st in students_list:
        st_code = st["student_code"]
        risk = st["risk_category"]
        
        # Nếu là học sinh HIGH_RISK -> tạo 3-4 ngày nghỉ KHÔNG PHÉP liên tiếp
        if risk == "HIGH_RISK":
            for day_offset in range(1, 5):
                absent_date = today - timedelta(days=day_offset)
                try:
                    cur.execute("""
                        INSERT INTO s360.fact_so_daily_attendance (_date, student_code, school_id, any_absence_flag, absent_no_permission)
                        VALUES (%s, %s, %s, 1, 1);
                    """, (absent_date, st_code, SO_SCHOOL_ID))
                    cur.execute("""
                        INSERT INTO s360.fact_absent_logs (id, so_school_id, student_code, absent_date, reason_norm)
                        VALUES (%s, %s, %s, %s, 'Nghỉ học không xin phép');
                    """, (absent_id_counter, SO_SCHOOL_ID, st_code, absent_date))
                    absent_id_counter += 1
                except Exception as e:
                    print(f"  [ERROR] Attendance Insert: {e}")
        else:
            try:
                cur.execute("""
                    INSERT INTO s360.fact_so_daily_attendance (_date, student_code, school_id, any_absence_flag, absent_no_permission)
                    VALUES (%s, %s, %s, 0, 0);
                """, (today, st_code, SO_SCHOOL_ID))
            except Exception as e:
                print(f"  [ERROR] Attendance Safe Insert: {e}")

    # 10. Seed Behavior Logs (dim_behavior & fact_behavior_logs)
    print("[INFO] 11. Seeding Behavior Criteria & Logs (s360.dim_behavior & fact_behavior_logs)...")
    try:
        cur.execute("""
            INSERT INTO s360.dim_behavior (id, code, name, point)
            VALUES (1, 'BEH01', 'Đóng góp bài giảng xuất sắc', 5.0), 
                   (2, 'BEH02', 'Đi học muộn', -2.0), 
                   (3, 'BEH03', 'Không làm bài tập về nhà', -3.0);
        """)
    except Exception as e:
        print(f"  [ERROR] dim_behavior insert: {e}")

    behavior_log_counter = 1
    for st in students_list:
        st_code = st["student_code"]
        risk = st["risk_category"]
        try:
            if risk == "HIGH_RISK":
                cur.execute("""
                    INSERT INTO s360.fact_behavior_logs (id, so_school_id, student_code, behavior_id, comment_date, behavior_comment)
                    VALUES (%s, %s, %s, 3, %s, 'Vi phạm không làm bài tập 3 lần');
                """, (behavior_log_counter, SO_SCHOOL_ID, st_code, today))
            else:
                cur.execute("""
                    INSERT INTO s360.fact_behavior_logs (id, so_school_id, student_code, behavior_id, comment_date, behavior_comment)
                    VALUES (%s, %s, %s, 1, %s, 'Tuyên dương phát biểu xây dựng bài');
                """, (behavior_log_counter, SO_SCHOOL_ID, st_code, today))
            behavior_log_counter += 1
        except Exception as e:
            print(f"  [ERROR] behavior_logs insert: {e}")

    conn.commit()
    cur.close()
    conn.close()
    print("[SUCCESS] All 37 Target Mock Tables Seeded Successfully!")

if __name__ == "__main__":
    seed()
