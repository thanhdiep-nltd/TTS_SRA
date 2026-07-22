import random
import os
import sys
from datetime import date, datetime, timezone, timedelta
from typing import List, Dict, Tuple, Optional

# Ensure UTF-8 output on Windows terminal
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import create_engine, text
from src.core.security import hash_password

# Set deterministic seed for reproducible mock generation
random.seed(42)
DEFAULT_HASHED_PASSWORD = hash_password("password123")


class VietnameseNameGenerator:
    """Sinh họ tên học sinh và giáo viên chuẩn Việt Nam"""
    FAMILY_NAMES = [
        "Nguyễn", "Trần", "Lê", "Phạm", "Hoàng", "Huỳnh", "Vũ", "Võ", "Đặng",
        "Bùi", "Đỗ", "Hồ", "Ngô", "Dương", "Lý"
    ]
    MIDDLE_NAMES_MALE = ["Văn", "Hữu", "Đức", "Minh", "Quang", "Đình", "Xuân", "Thành", "Gia", "Bảo"]
    MIDDLE_NAMES_FEMALE = ["Thị", "Ngọc", "Thu", "Thanh", "Phương", "Khanh", "Hồng", "Khánh", "Bích", "Mai"]
    FIRST_NAMES_MALE = [
        "An", "Bình", "Cường", "Dũng", "Đạt", "Hải", "Hiếu", "Hùng", "Huy", "Khang",
        "Khoa", "Lâm", "Long", "Minh", "Nam", "Nghĩa", "Phúc", "Quân", "Sơn", "Tài",
        "Tâm", "Thắng", "Thành", "Thiện", "Thịnh", "Trung", "Tuấn", "Tùng", "Vinh", "Vũ"
    ]
    FIRST_NAMES_FEMALE = [
        "Anh", "Châu", "Chi", "Dương", "Hà", "Hằng", "Hạnh", "Hoa", "Hương", "Linh",
        "Mai", "Nga", "Ngân", "Nhi", "Nhung", "Oanh", "Phương", "Quyên", "Quỳnh", "Trang",
        "Trinh", "Trúc", "Tú", "Vân", "Vy", "Yến"
    ]

    @classmethod
    def generate(cls, gender: str = None) -> Tuple[str, str]:
        if gender is None:
            gender = random.choice(["MALE", "FEMALE"])
        family = random.choice(cls.FAMILY_NAMES)
        if gender == "MALE":
            middle = random.choice(cls.MIDDLE_NAMES_MALE)
            first = random.choice(cls.FIRST_NAMES_MALE)
        else:
            middle = random.choice(cls.MIDDLE_NAMES_FEMALE)
            first = random.choice(cls.FIRST_NAMES_FEMALE)
        return f"{family} {middle} {first}", gender

def convert_score_to_all_scales(score_10: Optional[float]) -> dict:
    if score_10 is None:
        return {"gpa4": None, "letter": None, "label": "Chưa có điểm", "scale6": None, "percent": None, "pass_fail": "CHUA_DAT"}
    val = round(score_10, 1)
    percent = round(val * 10.0, 2)
    if val >= 9.0:
        return {"gpa4": 4.0, "letter": "A+", "label": "Xuất sắc", "scale6": "6", "percent": percent, "pass_fail": "DAT"}
    elif val >= 8.5:
        return {"gpa4": 3.75, "letter": "A", "label": "Giỏi xuất sắc", "scale6": "6", "percent": percent, "pass_fail": "DAT"}
    elif val >= 8.0:
        return {"gpa4": 3.5, "letter": "B+", "label": "Giỏi", "scale6": "5", "percent": percent, "pass_fail": "DAT"}
    elif val >= 7.0:
        return {"gpa4": 3.0, "letter": "B", "label": "Khá", "scale6": "4", "percent": percent, "pass_fail": "DAT"}
    elif val >= 6.5:
        return {"gpa4": 2.5, "letter": "C+", "label": "Trung bình khá", "scale6": "3", "percent": percent, "pass_fail": "DAT"}
    elif val >= 5.0:
        return {"gpa4": 2.0, "letter": "C", "label": "Trung bình", "scale6": "3", "percent": percent, "pass_fail": "DAT"}
    elif val >= 4.0:
        return {"gpa4": 1.0, "letter": "D", "label": "Yếu", "scale6": "2", "percent": percent, "pass_fail": "CHUA_DAT"}
    else:
        return {"gpa4": 0.0, "letter": "F", "label": "Kém", "scale6": "1", "percent": percent, "pass_fail": "CHUA_DAT"}

def generate_teacher_comment(final_grade: Optional[float], group_code: str) -> str:
    if group_code == "G9" or final_grade is None:
        return "Vắng thi / Thiếu dữ liệu điểm số, cần làm rõ lý do vắng mặt."
    elif group_code == "G7":
        return "Sụt giảm điểm số đột ngột từ giữa kỳ, học sinh cần được gặp tham vấn học đường."
    elif group_code == "G6":
        return "Điểm bài tập trực tuyến cao nhưng kết quả thi trên trường thấp, có dấu hiệu học vẹt hoặc tâm lý thi cử."
    elif group_code == "G5":
        return "Điểm thi trên trường tốt nhưng thường xuyên bỏ bài tập LMS, cần tăng cường ý thức tự học."
    elif group_code == "G8" or final_grade < 4.0:
        return "Kết quả yếu kém toàn diện, thuộc diện báo động đỏ cần phụ đạo gấp."
    elif final_grade >= 8.5:
        return "Thành tích học tập xuất sắc, tư duy tốt và hoàn thành xuất sắc các yêu cầu."
    elif final_grade >= 7.0:
        return "Nắm vững kiến thức môn học, kết quả học tập khá giỏi."
    elif final_grade >= 5.0:
        return "Đạt yêu cầu tối thiểu của môn học, cần rèn luyện cẩn thận hơn."
    else:
        return "Lực học còn bấp bênh sát ngưỡng trượt, cần hỗ trợ thêm từ giáo viên bộ môn."

def truncate_db(conn):
    tables_to_clear = [
        "public.ai_messages", "public.ai_sessions", "public.classroom_recordings",
        "public.report_schedules", "public.audit_logs", "public.exam_competencies",
        "public.curriculum_units", "public.exam_papers", "public.refresh_tokens", "public.users",
        "s360.fact_course_enrolls", "s360.fact_so_evaluate_process_subjects",
        "s360.fact_overall_academic_records", "s360.fact_subject_academic_records",
        "s360.fact_so_assignment_grade", "s360.fact_gradebooks_moet",
        "s360.fact_gradebooks", "s360.dim_grade_scale_detail",
        "s360.dim_so_assignment", "s360.dim_exam_moet",
        "s360.dim_exam", "s360.dim_subject", "s360.dim_homeroom_class_student",
        "s360.dim_homeroom_class", "s360.dim_school_year"
    ]
    print("Truncating old mock data...")
    for t in tables_to_clear:
        try:
            conn.execute(text(f"TRUNCATE TABLE {t} RESTART IDENTITY CASCADE;"))
            print(f"  Truncated {t}")
        except Exception:
            pass

def assign_score_profile_group() -> str:
    """Gán 1 trong 9 nhóm mẫu điểm (G1-G9) theo tỷ lệ xác suất chính xác"""
    r = random.random()
    if r < 0.60:
        return "G1"  # 60% Giỏi / Ổn định
    elif r < 0.75:
        return "G2"  # 15% Trung bình / Ổn định
    elif r < 0.78:
        return "G3"  # 3% Tiến bộ vượt bậc
    elif r < 0.83:
        return "G4"  # 5% Sát ngưỡng trượt / Bấp bênh
    elif r < 0.88:
        return "G5"  # 5% Bỏ bài LMS nhưng thi đạt
    elif r < 0.93:
        return "G6"  # 5% LMS cao nhưng Thi thấp
    elif r < 0.97:
        return "G7"  # 4% Sụt giảm điểm đột ngột
    elif r < 0.97 + 0.02:
        return "G8"  # 2% Yếu kém toàn diện (trong tổng 5% cho G8)
    else:
        return "G9"  # 1% Trắng điểm (trong tổng 3% cho G9)

def run_mock_generation(db_url: str = None):
    if not db_url:
        from src.db.session import get_sqlalchemy_url
        db_url = get_sqlalchemy_url()

    print(f"Connecting to database: {db_url.split('@')[-1] if '@' in db_url else db_url}")
    engine = create_engine(db_url, connect_args={"connect_timeout": 30})

    name_gen = VietnameseNameGenerator()

    # 1. Dimension Tables Data
    scales_data = [
        {"id": 1, "name": 'SCALE_ALL_EXCELLENT', "min_s": 9.00, "max_s": 10.00, "min_p": 90.00, "max_p": 100.00, "rep_p": 95.00, "letter": 'A+', "label": 'Xuất sắc', "gpa4": 4.00, "s6": 6, "pf": 'DAT'},
        {"id": 2, "name": 'SCALE_ALL_GOOD_HIGH',  "min_s": 8.50, "max_s":  8.99, "min_p": 85.00, "max_p":  89.99, "rep_p": 87.50, "letter": 'A',  "label": 'Giỏi xuất sắc', "gpa4": 3.75, "s6": 6, "pf": 'DAT'},
        {"id": 3, "name": 'SCALE_ALL_GOOD',       "min_s": 8.00, "max_s":  8.49, "min_p": 80.00, "max_p":  84.99, "rep_p": 82.50, "letter": 'B+', "label": 'Giỏi',         "gpa4": 3.50, "s6": 5, "pf": 'DAT'},
        {"id": 4, "name": 'SCALE_ALL_ABOVE_AVG',  "min_s": 7.00, "max_s":  7.99, "min_p": 70.00, "max_p":  79.99, "rep_p": 75.00, "letter": 'B',  "label": 'Khá',         "gpa4": 3.00, "s6": 4, "pf": 'DAT'},
        {"id": 5, "name": 'SCALE_ALL_AVERAGE',    "min_s": 6.50, "max_s":  6.99, "min_p": 65.00, "max_p":  69.99, "rep_p": 67.50, "letter": 'C+', "label": 'Trung bình khá',"gpa4": 2.50, "s6": 3, "pf": 'DAT'},
        {"id": 6, "name": 'SCALE_ALL_BELOW_AVG',  "min_s": 5.00, "max_s":  6.49, "min_p": 50.00, "max_p":  64.99, "rep_p": 57.50, "letter": 'C',  "label": 'Trung bình',  "gpa4": 2.00, "s6": 3, "pf": 'DAT'},
        {"id": 7, "name": 'SCALE_ALL_POOR',       "min_s": 4.00, "max_s":  4.99, "min_p": 40.00, "max_p":  49.99, "rep_p": 45.00, "letter": 'D',  "label": 'Yếu',         "gpa4": 1.00, "s6": 2, "pf": 'CHUA_DAT'},
        {"id": 8, "name": 'SCALE_ALL_FAIL',       "min_s": 0.00, "max_s":  3.99, "min_p":  0.00, "max_p":  39.99, "rep_p": 20.00, "letter": 'F',  "label": 'Kém',         "gpa4": 0.00, "s6": 1, "pf": 'CHUA_DAT'}
    ]

    years_data = [
        {"id": 2025, "code": '2025_2026', "fn": 'Năm học 2025 - 2026', "st": date(2025, 9, 5), "en": date(2026, 5, 31), "cur": 1}
    ]

    # Danh mục 22 Môn Học Chuẩn Hóa (Tách môn Toán TOAN_7 -> TOAN_11, Chuẩn hóa subject_type cho IB và Honor)
    subjects_info = [
        # (ID, CODE, NAME, NAME_EN, SUBJECT_TYPE, ASSESSMENT_TYPE, DEFAULT_SCALE, FREQUENCY_PER_WEEK, CATEGORY)
        (107, 'TOAN_7',   'Toán học Khối 7',            'Mathematics Grade 7',  'CORE',      'SCORED', 'SCALE_10',  2, 'MOET'),
        (108, 'TOAN_8',   'Toán học Khối 8',            'Mathematics Grade 8',  'CORE',      'SCORED', 'SCALE_10',  2, 'MOET'),
        (109, 'TOAN_9',   'Toán học Khối 9',            'Mathematics Grade 9',  'CORE',      'SCORED', 'SCALE_10',  2, 'MOET'),
        (110, 'TOAN_10',  'Toán học Khối 10',           'Mathematics Grade 10', 'CORE',      'SCORED', 'SCALE_10',  2, 'MOET'),
        (111, 'TOAN_11',  'Toán học Khối 11',           'Mathematics Grade 11', 'CORE',      'SCORED', 'SCALE_10',  2, 'MOET'),
        (2,   'VAN',      'Ngữ văn',                    'Vietnamese Literature','CORE',      'SCORED', 'SCALE_10',  2, 'MOET'),
        (3,   'ANH',      'Tiếng Anh',                  'English MOET',         'CORE',      'SCORED', 'SCALE_10',  2, 'MOET'),
        (4,   'LY',       'Vật lý',                     'Physics',              'CORE',      'SCORED', 'SCALE_10',  1, 'MOET'),
        (5,   'HOA',      'Hóa học',                    'Chemistry',            'CORE',      'SCORED', 'SCALE_10',  1, 'MOET'),
        (6,   'SINH',     'Sinh học',                   'Biology',              'CORE',      'SCORED', 'SCALE_10',  1, 'MOET'),
        (7,   'KHTN',     'Khoa học tự nhiên',          'Natural Sciences',     'CORE',      'SCORED', 'SCALE_10',  1, 'MOET'),
        (8,   'LS_DL',    'Lịch sử và Địa lý',          'History & Geography',  'CORE',      'SCORED', 'SCALE_10',  1, 'MOET'),
        (9,   'CAM_ENG',  'Tiếng Anh Cambridge (ESL)',  'Cambridge ESL',        'CAMBRIDGE', 'SCORED', 'LETTER_AF', 2, 'NON_MOET'),
        (10,  'CAM_MATH', 'Toán Tiếng Anh Cambridge',   'Cambridge Math',       'CAMBRIDGE', 'SCORED', 'LETTER_AF', 2, 'NON_MOET'),
        (11,  'IB_MATH',  'Toán Quốc tế IB',            'IB Mathematics',       'IB',        'SCORED', 'SCALE_6',   2, 'NON_MOET'),
        (12,  'IB_SCI',   'Khoa học Quốc tế IB',        'IB Science',           'IB',        'SCORED', 'SCALE_6',   1, 'NON_MOET'),
        (13,  'TIN',      'Tin học & Lập trình',        'Computer Science',     'ELECTIVE',  'SCORED', 'SCALE_100', 0.5, 'NON_MOET'),
        (14,  'ROBOTICS', 'STEM & Robotics',            'STEM Robotics',        'ELECTIVE',  'SCORED', 'SCALE_100', 0.5, 'NON_MOET'),
        (15,  'GPA_HONOR','Môn Chuyên Honor Course',    'Honor Course',         'HONOR',     'SCORED', 'SCALE_4',   2, 'NON_MOET'),
        (16,  'THE_DUC',  'Giáo dục thể chất',          'Physical Education',   'CORE',      'REMARK', 'PASS_FAIL', 0.5, 'REMARK'),
        (17,  'MY_THUAT', 'Mỹ thuật',                   'Fine Arts',            'CORE',      'REMARK', 'PASS_FAIL', 0.5, 'REMARK'),
        (18,  'AM_NHAC',  'Âm nhạc',                    'Music',                'CORE',      'REMARK', 'PASS_FAIL', 0.5, 'REMARK')
    ]
    sub_data = [
        {"id": s[0], "code": s[1], "name": s[2], "name_en": s[3], "stype": s[4], "atype": s[5], "scale": s[6]}
        for s in subjects_info
    ]

    staff_accounts = [
        ('admin@vinschool.edu.vn', 'Quản Trị Viên Hệ Thống', 'ADMIN', 'ALL', 'GV_ADMIN_01', None),
        ('principal@vinschool.edu.vn', 'Nguyễn Tri Thức (Hiệu Trưởng)', 'PRINCIPAL', 'ALL', 'GV_BGH_01', None),
        ('vice_principal@vinschool.edu.vn', 'Lê Thanh Hải (Phó Hiệu Trưởng)', 'PRINCIPAL', 'ALL', 'GV_BGH_02', None),
        ('head_math@vinschool.edu.vn', 'Trần Văn Toán (Tổ Trưởng Toán)', 'SUBJECT_HEAD', 'ALL', 'GV_HEAD_MATH', 107),
        ('head_literature@vinschool.edu.vn', 'Phạm Thị Văn (Tổ Trưởng Ngữ Văn)', 'SUBJECT_HEAD', 'ALL', 'GV_HEAD_VAN', 2),
        ('head_english@vinschool.edu.vn', 'Hoàng Anh Tuấn (Tổ Trưởng Tiếng Anh)', 'SUBJECT_HEAD', 'ALL', 'GV_HEAD_ENG', 3),
        ('grade_head_c2@vinschool.edu.vn', 'Vũ Minh Đức (Khối Trưởng THCS)', 'HOMEROOM_TEACHER_SECONDARY', 'SECONDARY', 'GV_GRADE_C2', None),
        ('grade_head_c3@vinschool.edu.vn', 'Đặng Quốc Bảo (Khối Trưởng THPT)', 'HOMEROOM_TEACHER_SECONDARY', 'HIGH', 'GV_GRADE_C3', None),
        ('homeroom_7a1@vinschool.edu.vn', 'Nguyễn Thị Mai (GVCN Lớp 7A1 - THCS)', 'HOMEROOM_TEACHER_SECONDARY', 'SECONDARY', 'GV_HR_7A1', None),
        ('homeroom_10a1@vinschool.edu.vn', 'Trần Đức Anh (GVCN Lớp 10A1 - THPT)', 'HOMEROOM_TEACHER_SECONDARY', 'HIGH', 'GV_HR_10A1', None)
    ]
    users_data = [
        {"email": acc[0], "name": acc[1], "role": acc[2], "slevel": acc[3], "tcode": acc[4], "sid": acc[5]}
        for acc in staff_accounts
    ]
    for i in range(1, 21):
        name, gender = name_gen.generate()
        # Teacher subject assignment
        assigned_sid = 107 if i % 18 == 1 else ((i % 18) if (i % 18) != 0 else 18)
        users_data.append({"email": f"teacher_{i}@vinschool.edu.vn", "name": name, "role": "SUBJECT_TEACHER", "slevel": "ALL", "tcode": f"GV_SUB_{i:02d}", "sid": assigned_sid})

    class_id_counter = 1
    class_map = {}
    target_grades = [7, 8, 9, 10, 11]
    classes_data = []

    for y_id in [2025]:
        for grade_id in target_grades:
            for c_idx in [1, 2, 3]:
                code = f"{grade_id}A{c_idx}"
                fname = f"Lớp {code}"
                t_code = f"GV_SUB_{(class_id_counter % 20) + 1:02d}"
                classes_data.append({"id": class_id_counter, "yid": y_id, "gid": grade_id, "code": code, "fname": fname, "tcode": t_code})
                class_map[(y_id, code)] = class_id_counter
                class_id_counter += 1

    student_id_counter = 1000
    student_records = []
    student_users_data = []
    student_dim_data = []

    for y_id in [2025]:
        for grade_id in target_grades:
            slevel = "SECONDARY" if grade_id <= 9 else "HIGH"
            for c_idx in [1, 2, 3]:
                code = f"{grade_id}A{c_idx}"
                c_id = class_map[(y_id, code)]
                num_students = random.randint(35, 40)

                for s_idx in range(num_students):
                    name, gender = name_gen.generate()
                    scode = f"HS{y_id % 100}{grade_id:02d}{student_id_counter:04d}"
                    moet_c = f"MOET_{scode}"

                    student_users_data.append({"email": f"{scode.lower()}@student.vinschool.edu.vn", "name": name, "slevel": slevel, "scode": scode, "sid": student_id_counter})
                    student_dim_data.append({
                        "id": student_id_counter, "sid": student_id_counter, "scode": scode, "sname": name,
                        "cid": c_id, "ccode": code, "cname": f"Lớp {code}", "yid": y_id,
                        "gid": grade_id, "gname": f"Khối {grade_id}", "mcode": moet_c
                    })

                    student_records.append({
                        "id": student_id_counter,
                        "code": scode,
                        "name": name,
                        "year_id": y_id,
                        "class_id": c_id,
                        "class_code": code,
                        "grade_id": grade_id
                    })
                    student_id_counter += 1

    # 2. Setup Exam Metadata & LMS Assignment Definitions per Subject
    exam_id_counter = 1
    moet_item_counter = 1
    assignment_id_counter = 1
    
    exam_map = {}
    assignment_map = {}  # (grade_id, subject_id, sem, week_index, assignment_seq) -> assignment_id
    moet_map = {}        # (grade_id, subject_id, sem, item_code) -> moet_item_id

    dim_exam_data = []
    dim_moet_data = []
    dim_asg_data = []
    exam_papers_data = []

    start_semester_date = date(2025, 9, 8)  # Monday Week 1 HK1

    for y_id in [2025]:
        for grade_id in target_grades:
            for sub_info in subjects_info:
                sub_id, sub_code, sub_name, _, _, _, scale_name, freq_week, category = sub_info

                # Ensure math subject matches grade_id (TOAN_7 for Grade 7, TOAN_8 for Grade 8...)
                if sub_code.startswith("TOAN_") and sub_id != (100 + grade_id):
                    continue

                for sem in [1]:
                    # Create School Exams based on Category
                    if category == 'MOET':
                        # 4 MOET Exam Columns
                        moet_templates = [
                            ("MOET_ORAL_1", f"Kiểm tra miệng HK{sem}", 1.0, 2),
                            ("MOET_QUIZ_15M_1", f"Kiểm tra 15 phút Lần 1 HK{sem}", 1.0, 4),
                            ("MOET_QUIZ_15M_2", f"Kiểm tra 15 phút Lần 2 HK{sem}", 1.0, 8),
                            ("MOET_MIDTERM", f"Kiểm tra Giữa kỳ HK{sem}", 2.0, 10),
                        ]
                        for icode, iname, coeff, week_target in moet_templates:
                            dim_moet_data.append({
                                "id": moet_item_counter,
                                "tcode": "DG_TX" if "15M" in icode or "ORAL" in icode else "DG_DK",
                                "tfname": "Đánh giá thường xuyên" if "15M" in icode or "ORAL" in icode else "Đánh giá định kỳ",
                                "icode": icode,
                                "ifname": f"{iname} - Môn {sub_name} Khối {grade_id}",
                                "sem": sem,
                                "coeff": coeff
                            })
                            moet_map[(grade_id, sub_id, sem, icode)] = moet_item_counter
                            moet_item_counter += 1

                    elif category == 'NON_MOET':
                        # 4 Vinschool Internal Exam Columns in dim_exam
                        non_moet_templates = [
                            ("PC_1", f"Progress Check 1 HK{sem}", 1.0, 3),
                            ("PC_2", f"Progress Check 2 HK{sem}", 1.0, 7),
                            ("PROJECT", f"Dự án thực hành / Portfolio HK{sem}", 1.0, 9),
                            ("MIDTERM", f"Thi Giữa kỳ Vinschool HK{sem}", 2.0, 10),
                        ]
                        for ecode, ename, coeff, week_target in non_moet_templates:
                            dim_exam_data.append({
                                "id": exam_id_counter,
                                "so_id": exam_id_counter * 10,
                                "yid": y_id,
                                "sid": sub_id,
                                "gid": grade_id,
                                "ename": f"{ename} Khối {grade_id} - Môn {sub_name}",
                                "sem": sem,
                                "coeff": coeff
                            })
                            exam_map[(grade_id, sub_id, sem, ecode)] = exam_id_counter
                            exam_id_counter += 1

                    else:  # REMARK
                        # 2 Progress Check Remarks
                        remark_templates = [
                            ("REMARK_1", f"Đánh giá thể lực/năng khiếu Đợt 1 HK{sem}", 1.0, 5),
                            ("REMARK_2", f"Đánh giá thể lực/năng khiếu Đợt 2 HK{sem}", 1.0, 10),
                        ]
                        for ecode, ename, coeff, week_target in remark_templates:
                            dim_exam_data.append({
                                "id": exam_id_counter,
                                "so_id": exam_id_counter * 10,
                                "yid": y_id,
                                "sid": sub_id,
                                "gid": grade_id,
                                "ename": f"{ename} Khối {grade_id} - Môn {sub_name}",
                                "sem": sem,
                                "coeff": coeff
                            })
                            exam_map[(grade_id, sub_id, sem, ecode)] = exam_id_counter
                            exam_id_counter += 1

                    # Generate Weekly LMS Assignments
                    weeks = range(1, 11)  # Weeks 1 to 10
                    for w in weeks:
                        if freq_week == 2:
                            seqs = [1, 2]
                        elif freq_week == 1:
                            seqs = [1]
                        else:  # 0.5 (every 2 weeks)
                            seqs = [1] if w % 2 == 0 else []

                        for seq in seqs:
                            assign_date = start_semester_date + timedelta(weeks=w-1, days=(seq-1)*3)
                            due_d = assign_date + timedelta(days=6)
                            asg_name = f"Bài tập LMS Tuần {w} (Bài {seq}) Khối {grade_id} - Môn {sub_name}"

                            # Determine LMS-to-MOET/Vinschool mapping
                            mapped_moet_item_id = None
                            mapped_item_name = None

                            if category == 'MOET':
                                if w == 4 and seq == 1:
                                    mapped_moet_item_id = moet_map.get((grade_id, sub_id, sem, "MOET_QUIZ_15M_1"))
                                    mapped_item_name = "Kiểm tra 15 phút Lần 1 MOET"
                                elif w == 8 and seq == 1:
                                    mapped_moet_item_id = moet_map.get((grade_id, sub_id, sem, "MOET_QUIZ_15M_2"))
                                    mapped_item_name = "Kiểm tra 15 phút Lần 2 MOET"
                            elif category == 'NON_MOET':
                                if w == 7 and seq == 1:
                                    mapped_item_name = "Progress Check 2 Vinschool"

                            dim_asg_data.append({
                                "aid": assignment_id_counter,
                                "gid": grade_id,
                                "sem": sem,
                                "sid": sub_id,
                                "code": f"ASG_{sub_code}_K{grade_id}_W{w}_{seq}",
                                "fname": asg_name,
                                "asg_date": assign_date,
                                "due_date": due_d,
                                "moet_item_id": mapped_moet_item_id,
                                "moet_item_name": mapped_item_name
                            })
                            assignment_map[(grade_id, sub_id, sem, w, seq)] = assignment_id_counter
                            assignment_id_counter += 1

                    exam_papers_data.append({
                        "sid": sub_id, "sem": sem, "gid": grade_id,
                        "title": f"Đề thi Giữa kỳ HK1 Khối {grade_id} Môn {sub_name}", "uby": 1
                    })

    # 3. Fact Tables Generation with 9 Score Profiles (G1 -> G9)
    enroll_id_counter = 1
    fact_gb_counter = 1
    fact_moet_counter = 1
    fact_asg_counter = 1
    overall_record_counter = 1

    enrolls_data = []
    gradebooks_data = []
    gradebooks_moet_data = []
    asg_grade_data = []
    overall_records_data = []
    subject_academic_records_data = []

    for st in student_records:
        s_code = st["code"]
        g_id = st["grade_id"]
        c_id = st["class_id"]
        y_id = st["year_id"]

        math_sub_id = 100 + g_id  # Dynamic grade-specific Math subject ID (107..111)

        # Assign subjects based on Grade level
        if g_id in [7, 8]:
            core_subs = [math_sub_id, 2, 3, 7, 8, 16, 17, 18]
            electives_pool = [13, 14, 9, 10]
        elif g_id == 9:
            core_subs = [math_sub_id, 2, 3, 7, 8, 16, 17, 18]
            electives_pool = [13, 14, 15, 9, 10, 11, 12]
        else:
            core_subs = [math_sub_id, 2, 3, 4, 5, 6, 8, 16]
            electives_pool = [13, 14, 15, 9, 10, 11, 12]

        chosen_electives = random.sample(electives_pool, k=2)
        student_subjects = core_subs + chosen_electives

        for sub_id in student_subjects:
            is_moved = 1 if (random.random() < 0.02) else 0
            moved_date = date(2026, 1, 15) if is_moved else None
            enrolls_data.append({
                "id": enroll_id_counter, "scode": s_code, "sid": sub_id, "gid": g_id,
                "moved": is_moved, "moved_at": moved_date
            })
            enroll_id_counter += 1

        student_s1_subject_averages = []

        # Generate scores per enrolled subject according to 9 Score Profiles (G1-G9)
        for sub_id in student_subjects:
            sub_info = next(s for s in subjects_info if s[0] == sub_id)
            _, sub_code, sub_name, _, _, assessment_type, default_scale, freq_week, category = sub_info
            sem = 1

            # Assign 1 of 9 Score Profiles for this (student, subject) pair
            group_code = assign_score_profile_group()

            # Generate Raw 10-Point Scores for School Exam Columns (4 columns) & LMS Assignments (up to 20)
            def gen_score_by_profile(gcode: str, week_idx: int = 1, is_exam: bool = False, col_idx: int = 1) -> Optional[float]:
                if gcode == "G9":  # Trắng điểm / NULL
                    return None
                elif gcode == "G1":  # Giỏi / Ổn định
                    return round(max(8.0, min(10.0, random.normalvariate(9.0, 0.5))), 1)
                elif gcode == "G2":  # Trung bình / Ổn định
                    return round(max(5.0, min(7.5, random.normalvariate(6.5, 0.6))), 1)
                elif gcode == "G3":  # Tiến bộ vượt bậc
                    if is_exam:
                        target = 4.0 if col_idx <= 2 else 8.5
                    else:
                        target = 4.0 if week_idx <= 4 else 8.5
                    return round(max(2.5, min(9.8, random.normalvariate(target, 0.6))), 1)
                elif gcode == "G4":  # Sát ngưỡng trượt / Bấp bênh
                    return round(max(3.8, min(5.5, random.normalvariate(4.6, 0.5))), 1)
                elif gcode == "G5":  # Bỏ bài LMS nhưng Thi đạt
                    if not is_exam:
                        return None if random.random() < 0.7 else round(max(3.0, min(6.0, random.normalvariate(4.5, 0.8))), 1)
                    else:
                        return round(max(6.5, min(9.0, random.normalvariate(7.8, 0.6))), 1)
                elif gcode == "G6":  # LMS cao nhưng Thi thấp
                    if not is_exam:
                        return round(max(8.5, min(10.0, random.normalvariate(9.3, 0.4))), 1)
                    else:
                        return round(max(2.0, min(4.5, random.normalvariate(3.2, 0.6))), 1)
                elif gcode == "G7":  # Sụt giảm điểm đột ngột
                    if is_exam:
                        target = 8.2 if col_idx <= 2 else 3.2
                    else:
                        target = 8.2 if week_idx <= 5 else 3.2
                    return round(max(1.5, min(9.5, random.normalvariate(target, 0.6))), 1)
                elif gcode == "G8":  # Yếu kém toàn diện
                    if not is_exam and random.random() < 0.5:
                        return None
                    return round(max(0.0, min(4.0, random.normalvariate(2.2, 0.8))), 1)
                return 6.5

            # Generate School Exam Scores for 4 Columns
            col_scores_10 = []
            for col in range(1, 5):
                score = gen_score_by_profile(group_code, col_idx=col, is_exam=True)
                col_scores_10.append(score)

            oral_10, quiz1_10, quiz2_10, midterm_10 = col_scores_10

            # Process LMS Assignments & Synchronize mapped scores
            lms_assignments_for_sub = [a for a in dim_asg_data if a["sid"] == sub_id and a["gid"] == g_id]
            
            for asg in lms_assignments_for_sub:
                aid = asg["aid"]
                asg_date = asg["asg_date"]
                week_no = (asg_date - start_semester_date).days // 7 + 1

                # Check if this assignment is mapped to a School Exam Column
                if category == 'MOET' and asg["moet_item_id"] is not None:
                    if "15M_1" in asg.get("moet_item_name", ""):
                        asg_val_10 = quiz1_10
                    elif "15M_2" in asg.get("moet_item_name", ""):
                        asg_val_10 = quiz2_10
                    else:
                        asg_val_10 = gen_score_by_profile(group_code, week_idx=week_no, is_exam=False)
                elif category == 'NON_MOET' and asg.get("moet_item_name") == "Progress Check 2 Vinschool":
                    asg_val_10 = quiz2_10  # Synchronize to Progress Check 2
                else:
                    asg_val_10 = gen_score_by_profile(group_code, week_idx=week_no, is_exam=False)

                asg_comment = generate_teacher_comment(asg_val_10, group_code)
                asg_grade_data.append({
                    "id": fact_asg_counter,
                    "aid": aid,
                    "scode": s_code,
                    "fg": asg_val_10 if default_scale != 'SCALE_100' or asg_val_10 is None else round(asg_val_10 * 10.0, 1),
                    "comment": asg_comment
                })
                fact_asg_counter += 1

            # Seed School Exam Facts based on Category (MOET vs NON_MOET vs REMARK)
            if category == 'MOET':
                moet_items = [
                    ("MOET_ORAL_1", oral_10),
                    ("MOET_QUIZ_15M_1", quiz1_10),
                    ("MOET_QUIZ_15M_2", quiz2_10),
                    ("MOET_MIDTERM", midterm_10)
                ]
                valid_scores = [sc for _, sc in moet_items if sc is not None]
                if valid_scores and group_code != "G9":
                    sub_avg_10 = round((oral_10 + quiz1_10 + quiz2_10 + 2.0 * midterm_10) / 5.0, 1) if all(s is not None for s in [oral_10, quiz1_10, quiz2_10, midterm_10]) else round(sum(valid_scores)/len(valid_scores), 1)
                else:
                    sub_avg_10 = None

                for icode, sc_10 in moet_items:
                    mitem_id = moet_map[(g_id, sub_id, sem, icode)]
                    gradebooks_moet_data.append({
                        "id": fact_moet_counter, "yid": y_id, "sem": sem, "gid": g_id, "sid": sub_id,
                        "scode": s_code, "cid": c_id, "mitem": mitem_id, "fg": sc_10,
                        "comment": generate_teacher_comment(sc_10, group_code)
                    })
                    fact_moet_counter += 1

            elif category == 'NON_MOET':
                non_moet_items = [
                    ("PC_1", oral_10),
                    ("PC_2", quiz1_10),
                    ("PROJECT", quiz2_10),
                    ("MIDTERM", midterm_10)
                ]
                valid_scores = [sc for _, sc in non_moet_items if sc is not None]
                if valid_scores and group_code != "G9":
                    sub_avg_10 = round((oral_10 + quiz1_10 + quiz2_10 + 2.0 * midterm_10) / 5.0, 1) if all(s is not None for s in [oral_10, quiz1_10, quiz2_10, midterm_10]) else round(sum(valid_scores)/len(valid_scores), 1)
                else:
                    sub_avg_10 = None

                for ecode, sc_10 in non_moet_items:
                    eid = exam_map[(g_id, sub_id, sem, ecode)]
                    conv = convert_score_to_all_scales(sc_10)

                    # Scale-specific final_grade formatting
                    if default_scale == 'LETTER_AF':
                        fg_val = sc_10  # 10-point equivalent stored alongside letter
                    elif default_scale == 'SCALE_6':
                        fg_val = float(conv["scale6"]) if conv["scale6"] else None
                    elif default_scale == 'SCALE_4':
                        fg_val = conv["gpa4"]
                    elif default_scale == 'SCALE_100':
                        fg_val = round(sc_10 * 10.0, 1) if sc_10 is not None else None
                    else:
                        fg_val = sc_10

                    gradebooks_data.append({
                        "id": fact_gb_counter, "yid": y_id, "sem": sem, "scode": s_code,
                        "cid": c_id, "sid": sub_id, "eid": eid, "fg": fg_val,
                        "fp": conv["percent"], "fl": conv["letter"],
                        "pf": conv["pass_fail"], "scale": default_scale,
                        "max_g": 6.0 if default_scale == 'SCALE_6' else (4.0 if default_scale == 'SCALE_4' else (100.0 if default_scale == 'SCALE_100' else 10.0))
                    })
                    fact_gb_counter += 1

            else:  # REMARK
                sub_avg_10 = None
                remark_items = [("REMARK_1", quiz1_10), ("REMARK_2", midterm_10)]
                for ecode, sc_10 in remark_items:
                    eid = exam_map[(g_id, sub_id, sem, ecode)]
                    pf_status = "DAT" if (sc_10 is not None and sc_10 >= 5.0) else "CHUA_DAT"
                    gradebooks_data.append({
                        "id": fact_gb_counter, "yid": y_id, "sem": sem, "scode": s_code,
                        "cid": c_id, "sid": sub_id, "eid": eid, "fg": None,
                        "fp": None, "fl": None,
                        "pf": pf_status, "scale": 'PASS_FAIL', "max_g": 1.0
                    })
                    fact_gb_counter += 1

            # Store subject HK1 average in fact_subject_academic_records
            if sub_avg_10 is not None:
                student_s1_subject_averages.append(sub_avg_10)

            subject_academic_records_data.append({
                "id": overall_record_counter * 1000 + sub_id,
                "overall_id": overall_record_counter,
                "sid": sub_id,
                "scode": s_code,
                "s1_fg": sub_avg_10,
                "fg_summer": None
            })

        # Calculate Overall Student GPA for HK1
        if student_s1_subject_averages:
            avg_s1 = round(sum(student_s1_subject_averages) / len(student_s1_subject_averages), 1)
        else:
            avg_s1 = 3.0

        conduct = "TOT" if avg_s1 >= 7.0 else ("KHA" if avg_s1 >= 5.0 else "TRUNG_BINH")
        capacity = "Giỏi" if avg_s1 >= 8.0 else ("Khá" if avg_s1 >= 6.5 else ("Trung bình" if avg_s1 >= 5.0 else "Yếu"))

        overall_records_data.append({
            "id": overall_record_counter, "yid": y_id, "gid": g_id, "cid": c_id,
            "sid": st["id"], "scode": s_code, "fg": avg_s1, "s1fg": avg_s1, "s2fg": None,
            "conduct": conduct, "cap": capacity, "absent": random.randint(0, 4),
            "comment": f"Học sinh có sức học học kỳ 1 ở mức {capacity}, rèn luyện {conduct}."
        })
        overall_record_counter += 1

    # 4. Execute Atomic Bulk Insertion Into PostgreSQL
    with engine.begin() as conn:
        truncate_db(conn)

        print("[1/9] Seeding s360.dim_grade_scale_detail Matrix (8 Scales)...")
        conn.execute(text("""
            INSERT INTO s360.dim_grade_scale_detail 
            (id, scale_name, min_score_range, max_score_range, min_percent, max_percent, representative_percent, grade_letter, grade_label, gpa_scale_4, scale_6_value, pass_fail_status)
            VALUES (:id, :name, :min_s, :max_s, :min_p, :max_p, :rep_p, :letter, :label, :gpa4, :s6, CAST(:pf AS public.pass_fail_enum));
        """), scales_data)

        print("[2/9] Seeding s360.dim_school_year (Năm học 2025-2026)...")
        conn.execute(text("""
            INSERT INTO s360.dim_school_year (id, code, fullname, start_date, end_date, is_current)
            VALUES (:id, :code, :fn, :st, :en, :cur);
        """), years_data)

        print("[3/9] Seeding 22 Subjects (TOAN_7..11, 7 MOET Core, 7 Non-MOET, 3 Remark)...")
        conn.execute(text("""
            INSERT INTO s360.dim_subject (id, code, name, name_en, subject_type, assessment_type, default_scale_name)
            VALUES (:id, :code, :name, :name_en, :stype, CAST(:atype AS public.assessment_type_enum), :scale);
        """), sub_data)

        print("[4/9] Seeding public.users & Student Records...")
        conn.execute(text("""
            INSERT INTO public.users (so_school_id, email, hashed_password, full_name, role, school_level, teacher_code, subject_id)
            VALUES (1, :email, :hpwd, :name, CAST(:role AS public.user_role_enum), CAST(:slevel AS public.school_level_enum), :tcode, :sid);
        """), [{**u, "hpwd": DEFAULT_HASHED_PASSWORD} for u in users_data])

        conn.execute(text("""
            INSERT INTO s360.dim_homeroom_class (id, so_school_id, school_year_id, grade_id, code, fullname, teacher_code)
            VALUES (:id, 1, :yid, :gid, :code, :fname, :tcode);
        """), classes_data)

        conn.execute(text("""
            INSERT INTO public.users (so_school_id, email, hashed_password, full_name, role, school_level, student_code, so_student_id)
            VALUES (1, :email, :hpwd, :name, CAST('STUDENT' AS public.user_role_enum), CAST(:slevel AS public.school_level_enum), :scode, :sid);
        """), [{**u, "hpwd": DEFAULT_HASHED_PASSWORD} for u in student_users_data])


        conn.execute(text("""
            INSERT INTO s360.dim_homeroom_class_student 
            (id, so_student_id, student_code, student_name, homeroom_class_id, class_code, class_name, so_school_id, school_year_id, school_name, grade_id, grade_name, moet_code)
            VALUES (:id, :sid, :scode, :sname, :cid, :ccode, :cname, 1, :yid, 'Trường Vinschool', :gid, :gname, :mcode);
        """), student_dim_data)

        print("[5/9] Seeding Metadata for Exams & MOET items...")
        if dim_exam_data:
            conn.execute(text("""
                INSERT INTO s360.dim_exam (id, so_exam_id, school_year_id, subject_id, grade_id, exam_name, coefficient, moet_semester_index, max_grade)
                VALUES (:id, :so_id, :yid, :sid, :gid, :ename, :coeff, :sem, 10.0);
            """), dim_exam_data)

        conn.execute(text("""
            INSERT INTO s360.dim_exam_moet (gradebook_type_item_id, gradebook_types_code, gradebook_types_fullname, gradebook_type_items_code, gradebook_type_items_fullname, moet_semester_index, coefficient, max_grade)
            VALUES (:id, :tcode, :tfname, :icode, :ifname, :sem, :coeff, 10.0);
        """), dim_moet_data)

        print("[6/9] Seeding s360.dim_so_assignment with LMS-MOET mapping attributes...")
        conn.execute(text("""
            INSERT INTO s360.dim_so_assignment 
            (assignment_id, so_school_id, grade_id, semester_index, subject_id, code, fullname, max_grade, due_date, date_assigned)
            VALUES (:aid, 1, :gid, :sem, :sid, :code, :fname, 10.0, :due_date, :asg_date);
        """), dim_asg_data)

        admin_user_id = conn.execute(text("SELECT id FROM public.users WHERE role = 'ADMIN' LIMIT 1;")).scalar()
        if not admin_user_id:
            admin_user_id = conn.execute(text("SELECT id FROM public.users ORDER BY id ASC LIMIT 1;")).scalar() or 1

        for ep in exam_papers_data:
            ep["uby"] = admin_user_id

        conn.execute(text("""
            INSERT INTO public.exam_papers (so_school_id, subject_id, semester_id, grade_id, score_category, title, difficulty, uploaded_by)
            VALUES (1, :sid, :sem, :gid, CAST('MIDTERM' AS public.score_category_enum), :title, CAST('MEDIUM' AS public.difficulty_enum), :uby);
        """), exam_papers_data)

        print("[7/9] Seeding Fact Tables (Course Enrolls & LMS Assignment Grades)...")
        conn.execute(text("""
            INSERT INTO s360.fact_course_enrolls
            (id, so_school_id, student_code, subject_id, grade_id, is_moved_out, moved_out_at, is_student)
            VALUES (:id, 1, :scode, :sid, :gid, :moved, :moved_at, 1);
        """), enrolls_data)

        conn.execute(text("""
            INSERT INTO s360.fact_so_assignment_grade
            (id, so_school_id, assignment_id, student_code, final_grade, comment)
            VALUES (:id, 1, :aid, :scode, :fg, :comment);
        """), asg_grade_data)

        print("[8/9] Seeding Fact Tables (MOET Gradebooks & Vinschool Gradebooks)...")
        if gradebooks_moet_data:
            conn.execute(text("""
                INSERT INTO s360.fact_gradebooks_moet
                (id, so_school_id, school_year_id, semester_index, grade_id, subject_id, student_code, homeroom_class_id, gradebook_type_item_id, final_grade, comment)
                VALUES (:id, 1, :yid, :sem, :gid, :sid, :scode, :cid, :mitem, :fg, :comment);
            """), gradebooks_moet_data)

        if gradebooks_data:
            conn.execute(text("""
                INSERT INTO s360.fact_gradebooks 
                (id, so_school_id, school_year_id, semester_index, student_code, homeroom_class_id, subject_id, so_exam_id, final_grade, final_grade_percent, final_grade_letter, pass_fail_status, scale_name_used, max_grade)
                VALUES (:id, 1, :yid, :sem, :scode, :cid, :sid, :eid, :fg, :fp, :fl, CAST(:pf AS public.pass_fail_enum), :scale, :max_g);
            """), gradebooks_data)

        print("[9/9] Seeding Fact Tables (Subject Academic Records & Overall Academic Records)...")
        conn.execute(text("""
            INSERT INTO s360.fact_subject_academic_records
            (id, overall_record_id, subject_id, student_code, s1_final_grade, final_grade_after_summer)
            VALUES (:id, :overall_id, :sid, :scode, :s1_fg, :fg_summer);
        """), subject_academic_records_data)

        conn.execute(text("""
            INSERT INTO s360.fact_overall_academic_records
            (id, so_school_id, school_year_id, grade_id, homeroom_class_id, student_id, student_code, final_grade, s1_final_grade, s2_final_grade, conduct, learning_capacity, day_of_absent, homeroom_teacher_comment)
            VALUES (:id, 1, :yid, :gid, :cid, :sid, :scode, :fg, :s1fg, :s2fg, CAST(:conduct AS public.conduct_enum), :cap, :absent, :comment);
        """), overall_records_data)

    print("\n================ MOCK DATA GENERATION COMPLETE ==================")
    print(f" Successfully bulk seeded all tables on PostgreSQL in seconds!")
    print(f" Total Students: {len(student_records)}")
    print(f" Total Weekly LMS Assignments (dim_so_assignment): {len(dim_asg_data)}")
    print(f" Total LMS Student Assignment Grades (fact_so_assignment_grade): {len(asg_grade_data)}")
    print(f" Total MOET Fact Column Scores (fact_gradebooks_moet): {len(gradebooks_moet_data)}")
    print(f" Total Vinschool Gradebook Facts (fact_gradebooks): {len(gradebooks_data)}")
    print(f" Total Subject Academic Records (fact_subject_academic_records): {len(subject_academic_records_data)}")

if __name__ == "__main__":
    run_mock_generation()
