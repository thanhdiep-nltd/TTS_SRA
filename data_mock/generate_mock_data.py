import sys
import os
import random
from datetime import datetime, date, timedelta
from uuid import uuid4

sys.path.append("f:\\PROJECT_VINUNI\\BUILD_COHORT\\C2-App-051")

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from src.config import get_settings
from src.db.session import get_sqlalchemy_url
from src.models import enums, tables
from src.core.security import hash_password

# Set seed for reproducibility
random.seed(42)

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

def truncate_db(engine):
    """Xóa dữ liệu cũ theo đúng thứ tự để không bị lỗi khóa ngoại."""
    print("Clearing old data in correct FK order...")
    tables_to_clear = [
        "audit_logs",
        "ai_messages",
        "ai_sessions",
        "report_schedules",
        "scores",
        "exam_competencies",
        "exam_papers",
        "curriculum_units",
        "enrollments",
        "students",
        "teacher_assignments",
        "classes",
        "grades",
        "semesters",
        "academic_years",
        "subjects",
        "refresh_tokens",
        "users",
        "schools"
    ]
    with engine.begin() as conn:
        for t in tables_to_clear:
            try:
                conn.execute(text(f'TRUNCATE TABLE "{t}" CASCADE;'))
                print(f"  Truncated {t}")
            except Exception as e:
                print(f"  Error or table not exists '{t}': {str(e)}")

def main():
    if sys.platform.startswith('win'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')

    db_url = get_sqlalchemy_url()
    print("Connecting to:", db_url)
    engine = create_engine(db_url)
    Session = sessionmaker(bind=engine)
    session = Session()

    # 1. Truncate Database
    truncate_db(engine)

    # 2. Sinh Schools
    print("\nCreating Schools...")
    school_c2 = tables.School(
        id=uuid4(),
        name="Trường THCS Nguyễn Du",
        code="THCS-ND",
        address="102 Nguyễn Du, Quận 1, TP. Hồ Chí Minh",
        phone="02838291045"
    )
    school_c3 = tables.School(
        id=uuid4(),
        name="Trường THPT Chu Văn An",
        code="THPT-CVA",
        address="10 Thụy Khuê, Quận Tây Hồ, Hà Nội",
        phone="02438233131"
    )
    session.add_all([school_c2, school_c3])
    session.commit()
    print(f"  THCS Nguyễn Du ID: {school_c2.id}")
    print(f"  THPT Chu Văn An ID: {school_c3.id}")

    # 3. Sinh Năm học (3 năm) & Học kỳ (2 học kỳ/năm)
    print("\nCreating Academic Years & Semesters...")
    years_data = [
        {"name": "2023-2024", "start": date(2023, 9, 1), "end": date(2024, 5, 31), "is_current": False},
        {"name": "2024-2025", "start": date(2024, 9, 1), "end": date(2025, 5, 31), "is_current": False},
        {"name": "2025-2026", "start": date(2025, 9, 1), "end": date(2026, 5, 31), "is_current": True}
    ]

    acad_years = {}
    semesters = {}

    for sch_id in [school_c2.id, school_c3.id]:
        acad_years[sch_id] = {}
        semesters[sch_id] = {}
        for y in years_data:
            ay = tables.AcademicYear(
                id=uuid4(),
                school_id=sch_id,
                name=y["name"],
                start_date=y["start"],
                end_date=y["end"],
                is_current=y["is_current"]
            )
            session.add(ay)
            acad_years[sch_id][y["name"]] = ay

            # HK1
            hk1 = tables.Semester(
                id=uuid4(),
                academic_year_id=ay.id,
                name="HK1",
                number=1,
                start_date=y["start"],
                end_date=y["start"] + timedelta(days=135),
                is_current=False
            )
            # HK2
            hk2 = tables.Semester(
                id=uuid4(),
                academic_year_id=ay.id,
                name="HK2",
                number=2,
                start_date=y["start"] + timedelta(days=136),
                end_date=y["end"],
                is_current=y["is_current"]
            )
            session.add_all([hk1, hk2])
            semesters[sch_id][(y["name"], 1)] = hk1
            semesters[sch_id][(y["name"], 2)] = hk2

    session.commit()
    print("  Created Academic Years and Semesters for 3 years.")

    # 4. Sinh Khối lớp (Grades)
    print("\nCreating Grades...")
    # Cấp 2: Khối 6, 7, 8, 9
    grades_c2 = {}
    for g_num in [6, 7, 8, 9]:
        g = tables.Grade(
            id=uuid4(),
            school_id=school_c2.id,
            name=f"Khối {g_num}",
            grade_number=g_num,
            school_level=enums.SchoolLevel.SECONDARY
        )
        session.add(g)
        grades_c2[g_num] = g

    # Cấp 3: Khối 10, 11, 12
    grades_c3 = {}
    for g_num in [10, 11, 12]:
        g = tables.Grade(
            id=uuid4(),
            school_id=school_c3.id,
            name=f"Khối {g_num}",
            grade_number=g_num,
            school_level=enums.SchoolLevel.HIGH
        )
        session.add(g)
        grades_c3[g_num] = g

    session.commit()
    print("  Created Grades 6-9 for THCS and 10-12 for THPT.")

    # 5. Sinh Lớp học (Classes) cho 3 năm học
    print("\nCreating Classes...")
    classes_by_year_c2 = {}
    classes_by_year_c3 = {}

    for y_name in ["2023-2024", "2024-2025", "2025-2026"]:
        classes_by_year_c2[y_name] = {}
        classes_by_year_c3[y_name] = {}
        
        # Cấp 2: 4 lớp/khối -> e.g. 6A1, 6A2, 6A3, 6A4
        for g_num, g in grades_c2.items():
            classes_by_year_c2[y_name][g_num] = []
            for idx in [1, 2, 3, 4]:
                c = tables.Class(
                    id=uuid4(),
                    grade_id=g.id,
                    name=f"{g_num}A{idx}",
                    academic_year_id=acad_years[school_c2.id][y_name].id,
                    student_count=0
                )
                session.add(c)
                classes_by_year_c2[y_name][g_num].append(c)

        # Cấp 3: 4 lớp/khối -> e.g. 10A1 (Tự Nhiên), 10A2 (Xã Hội), 10A3 (Song Hành), 10A4 (Song Hành)
        for g_num, g in grades_c3.items():
            classes_by_year_c3[y_name][g_num] = []
            for idx in [1, 2, 3, 4]:
                c = tables.Class(
                    id=uuid4(),
                    grade_id=g.id,
                    name=f"{g_num}A{idx}",
                    academic_year_id=acad_years[school_c3.id][y_name].id,
                    student_count=0
                )
                session.add(c)
                classes_by_year_c3[y_name][g_num].append(c)

    session.commit()
    print("  Created Classes for each year.")

    # 6. Sinh Môn học (Subjects) theo chương trình GDPT 2018
    print("\nCreating Subjects (GDPT 2018)...")
    
    # Cấp 2: Các môn học bắt buộc và môn học phân hóa chính thức (8 môn chính khóa)
    c2_subjects_info = [
        ("Toán học", "TOAN"),
        ("Ngữ văn", "VAN"),
        ("Tiếng Anh", "ANH"),
        ("Giáo dục công dân", "GDCD"),
        ("Khoa học tự nhiên", "KHTN"),
        ("Lịch sử và Địa lý", "LS_DL"),
        ("Tin học", "TIN"),
        ("Công nghệ", "CN")
    ]
    subjects_c2 = {}
    for name, code in c2_subjects_info:
        sub = tables.Subject(
            id=uuid4(),
            school_id=school_c2.id,
            name=name,
            code=code,
            applicable_level=enums.SchoolLevel.SECONDARY,
            is_active=True
        )
        session.add(sub)
        subjects_c2[code] = sub

    # Cấp 3: Đầy đủ các môn học chính khóa của cấp THPT
    c3_subjects_info = [
        ("Toán học", "TOAN"),
        ("Ngữ văn", "VAN"),
        ("Tiếng Anh", "ANH"),
        ("Lịch sử", "SU"),
        ("Địa lý", "DIA"),
        ("Vật lý", "LY"),
        ("Hóa học", "HOA"),
        ("Sinh học", "SINH"),
        ("Giáo dục kinh tế và pháp luật", "GDKT_PL"),
        ("Tin học", "TIN"),
        ("Công nghệ", "CN")
    ]
    subjects_c3 = {}
    for name, code in c3_subjects_info:
        sub = tables.Subject(
            id=uuid4(),
            school_id=school_c3.id,
            name=name,
            code=code,
            applicable_level=enums.SchoolLevel.HIGH,
            is_active=True
        )
        session.add(sub)
        subjects_c3[code] = sub

    session.commit()
    print("  Created Subjects for THCS and THPT.")

    # 7. Sinh Users (BGH & Giáo viên)
    print("\nCreating Users (BGH & Teachers)...")
    hashed_pw = hash_password("password123")
    
    # BGH THCS
    principal_c2 = tables.User(
        id=uuid4(),
        school_id=school_c2.id,
        email="principal.c2@nguyendu.edu.vn",
        hashed_password=hashed_pw,
        full_name="Nguyễn Minh Triết",
        role=enums.UserRole.PRINCIPAL,
        school_level=enums.SchoolLevel.SECONDARY,
        is_active=True
    )
    # BGH THPT
    principal_c3 = tables.User(
        id=uuid4(),
        school_id=school_c3.id,
        email="principal.c3@chuvanan.edu.vn",
        hashed_password=hashed_pw,
        full_name="Trần Đức Lương",
        role=enums.UserRole.PRINCIPAL,
        school_level=enums.SchoolLevel.HIGH,
        is_active=True
    )
    session.add_all([principal_c2, principal_c3])

    # Sinh Giáo viên cho Cấp 2 (20 GV sử dụng name_generator có trọng số)
    teachers_c2 = []
    for i in range(1, 21):
        name, gender = name_generator.generate()
        teacher = tables.User(
            id=uuid4(),
            school_id=school_c2.id,
            email=f"teacher.c2.{i}@nguyendu.edu.vn",
            hashed_password=hashed_pw,
            full_name=name,
            role=enums.UserRole.SUBJECT_TEACHER,
            school_level=enums.SchoolLevel.SECONDARY,
            is_active=True
        )
        session.add(teacher)
        teachers_c2.append(teacher)

    # Sinh Giáo viên cho Cấp 3 (25 GV sử dụng name_generator có trọng số)
    teachers_c3 = []
    for i in range(1, 26):
        name, gender = name_generator.generate()
        teacher = tables.User(
            id=uuid4(),
            school_id=school_c3.id,
            email=f"teacher.c3.{i}@chuvanan.edu.vn",
            hashed_password=hashed_pw,
            full_name=name,
            role=enums.UserRole.SUBJECT_TEACHER,
            school_level=enums.SchoolLevel.HIGH,
            is_active=True
        )
        session.add(teacher)
        teachers_c3.append(teacher)

    session.commit()
    print(f"  Created 1 Principal + {len(teachers_c2)} Teachers for THCS.")
    print(f"  Created 1 Principal + {len(teachers_c3)} Teachers for THPT.")

    # 8. Thiết lập Phân công giảng dạy (Teacher Assignments) cho 3 năm
    print("\nCreating Teacher Assignments...")
    
    # Cấp 2:
    # 8 lớp mỗi năm. Đối với mỗi lớp trong năm học:
    # - Chọn 1 GVCN trong pool làm HOMEROOM_SECONDARY
    # - Các môn học chính khóa của Cấp 2: Toán, Văn, Anh, GDCD, KHTN, LS_DL, Tin học, Công nghệ.
    for y_name in ["2023-2024", "2024-2025", "2025-2026"]:
        ay_id = acad_years[school_c2.id][y_name].id
        random.shuffle(teachers_c2)
        
        c2_classes_in_year = []
        for g_num in [6, 7, 8, 9]:
            c2_classes_in_year.extend(classes_by_year_c2[y_name][g_num])
            
        for idx, cl in enumerate(c2_classes_in_year):
            # Homeroom
            hr_teacher = teachers_c2[idx % len(teachers_c2)]
            ta_hr = tables.TeacherAssignment(
                id=uuid4(),
                user_id=hr_teacher.id,
                academic_year_id=ay_id,
                role_context=enums.RoleContext.HOMEROOM_SECONDARY,
                class_id=cl.id
            )
            session.add(ta_hr)
            
            # Subject teachers
            for code, sub in subjects_c2.items():
                sub_teacher_idx = (idx + ord(code[0])) % len(teachers_c2)
                sub_teacher = teachers_c2[sub_teacher_idx]
                
                ta_sub = tables.TeacherAssignment(
                    id=uuid4(),
                    user_id=sub_teacher.id,
                    academic_year_id=ay_id,
                    role_context=enums.RoleContext.SUBJECT_TEACHER,
                    class_id=cl.id,
                    subject_id=sub.id
                )
                session.add(ta_sub)

    # Cấp 3:
    # Thiết lập phân ban học tập lựa chọn (Custom môn học theo lớp học)
    # Lớp A1: Tự nhiên -> Toán, Văn, Anh, Sử, Lý, Hóa, Sinh, Tin học, Công nghệ.
    # Lớp A2: Xã hội -> Toán, Văn, Anh, Sử, Địa, GDKT_PL, Công nghệ, Tin học.
    # Lớp A3: Song hành -> Toán, Văn, Anh, Sử, Lý, Hóa, Địa, Tin học, Công nghệ.
    for y_name in ["2023-2024", "2024-2025", "2025-2026"]:
        ay_id = acad_years[school_c3.id][y_name].id
        random.shuffle(teachers_c3)
        
        c3_classes_in_year = []
        for g_num in [10, 11, 12]:
            c3_classes_in_year.extend(classes_by_year_c3[y_name][g_num])
            
        for idx, cl in enumerate(c3_classes_in_year):
            # Homeroom
            hr_teacher = teachers_c3[idx % len(teachers_c3)]
            ta_hr = tables.TeacherAssignment(
                id=uuid4(),
                user_id=hr_teacher.id,
                academic_year_id=ay_id,
                role_context=enums.RoleContext.HOMEROOM_SECONDARY,
                class_id=cl.id
            )
            session.add(ta_hr)
            
            # Phân tách môn học theo ban (Custom lớp tự chọn)
            suffix = cl.name[-1]
            if suffix == "1": # Ban Tự nhiên
                active_codes = ["TOAN", "VAN", "ANH", "SU", "LY", "HOA", "SINH", "TIN", "CN"]
            elif suffix == "2": # Ban Xã hội
                active_codes = ["TOAN", "VAN", "ANH", "SU", "DIA", "GDKT_PL", "CN", "TIN"]
            else: # Ban Song hành (Tổng hòa)
                active_codes = ["TOAN", "VAN", "ANH", "SU", "LY", "HOA", "DIA", "TIN", "CN"]
                
            for code in active_codes:
                sub = subjects_c3[code]
                sub_teacher_idx = (idx + ord(code[0])) % len(teachers_c3)
                sub_teacher = teachers_c3[sub_teacher_idx]
                
                ta_sub = tables.TeacherAssignment(
                    id=uuid4(),
                    user_id=sub_teacher.id,
                    academic_year_id=ay_id,
                    role_context=enums.RoleContext.SUBJECT_TEACHER,
                    class_id=cl.id,
                    subject_id=sub.id
                )
                session.add(ta_sub)

    session.commit()
    print("  Created Teacher Assignments for all years and classes (with partition).")

    # 9. Sinh Học sinh (Students) & Enrollments qua 3 năm
    # Đảm bảo tính liên tục của lịch sử lớp học và Sĩ số lớp dao động ngẫu nhiên (35 - 45 học sinh/lớp)
    print("\nCreating Students & Enrollments (Tracking cohorts & dynamic class sizes)...")
    
    student_cohorts_c2 = {}
    student_cohorts_c3 = {}
    active_enrollments = []
    existing_student_codes = set()

    def enroll_students_for_class(sch_id, cl, y_name, cohort_dict):
        objs = []
        # Tự động tính năm sinh thực tế dựa theo lớp và năm học
        cl_grade = int(cl.name[:-2]) if cl.name[:-2].isdigit() else 6
        birth_year = int(y_name[:4]) - (cl_grade + 5)
        
        # SĨ SỐ LỚP DAO ĐỘNG NGẪU NHIÊN: 35 đến 45 học sinh
        num_students = random.randint(35, 45)
        
        students_to_add = []
        student_data = []
        
        for s_idx in range(num_students):
            name, gender = name_generator.generate()
            sch_code = "ND" if sch_id == school_c2.id else "CVA"
            code_prefix = y_name[2:4]
            
            while True:
                student_code = f"{code_prefix}{sch_code}{random.randint(10000, 99999)}"
                code_key = (sch_id, student_code)
                if code_key not in existing_student_codes:
                    existing_student_codes.add(code_key)
                    break
            
            st = tables.Student(
                id=uuid4(),
                school_id=sch_id,
                student_code=student_code,
                full_name=name,
                date_of_birth=date(birth_year, random.randint(1, 12), random.randint(1, 28)),
                gender=gender,
                is_active=True
            )
            students_to_add.append(st)
            
            # Gieo năng lực cốt lõi cho học sinh với độ lệch rộng hơn [3.0 -> 9.5] để có học sinh giỏi thực sự và học sinh yếu thực sự
            r = random.random()
            if r < 0.15: # Nhóm xuất sắc
                ability = random.uniform(8.0, 9.5)
            elif r < 0.50: # Nhóm khá
                ability = random.uniform(6.5, 8.0)
            elif r < 0.85: # Nhóm trung bình
                ability = random.uniform(5.0, 6.5)
            else: # Nhóm yếu/kém
                ability = random.uniform(3.0, 5.0)
            
            # Phân chia cụm năng lực ẩn cho học sinh
            archetype = random.choices(
                ["consistent", "procrastinator", "high_effort", "high_risk", "others"],
                weights=[15, 20, 20, 10, 35],
                k=1
            )[0]

            # Điều chỉnh năng lực cốt lõi để khớp với archetype mong muốn
            if archetype == "consistent":
                ability = max(8.0, ability)
            elif archetype == "high_risk":
                ability = min(4.8, ability)

            ability = round(ability, 2)

            student_data.append({
                "st": st,
                "ability": ability,
                "archetype": archetype,
                "affinities": {
                    "TOAN": random.uniform(-0.8, 0.8),
                    "VAN": random.uniform(-0.8, 0.8),
                    "ANH": random.uniform(-0.8, 0.8),
                    "LY": random.uniform(-0.8, 0.8),
                    "HOA": random.uniform(-0.8, 0.8),
                    "SINH": random.uniform(-0.8, 0.8),
                    "SU": random.uniform(-0.8, 0.8),
                    "DIA": random.uniform(-0.8, 0.8),
                    "KHTN": random.uniform(-0.8, 0.8),
                    "LS_DL": random.uniform(-0.8, 0.8),
                    "GDCD": random.uniform(-0.8, 0.8),
                    "GDKT_PL": random.uniform(-0.8, 0.8),
                    "TIN": random.uniform(-0.8, 0.8),
                    "CN": random.uniform(-0.8, 0.8),
                },
                "trend_type": random.choice(["NONE"] * 18 + ["DECREASE", "INCREASE"])
            })
            
        session.add_all(students_to_add)
        session.flush()
        
        enrollments_to_add = []
        for item in student_data:
            st = item["st"]
            cohort_dict[st.id] = {
                "ability": item["ability"],
                "archetype": item["archetype"],
                "affinities": item["affinities"],
                "trend_type": item["trend_type"]
            }
            
            en = tables.Enrollment(
                id=uuid4(),
                student_id=st.id,
                class_id=cl.id,
                academic_year_id=acad_years[sch_id][y_name].id,
                enrolled_at=acad_years[sch_id][y_name].start_date,
                is_active=True
            )
            enrollments_to_add.append(en)
            active_enrollments.append((st.id, cl.id, y_name, sch_id))
            cl.student_count = (cl.student_count or 0) + 1
            objs.append(st.id)

        session.add_all(enrollments_to_add)
        session.flush()
        return objs

    # Năm 2023-2024: tạo mới toàn bộ học sinh các lớp
    print("  Creating students for Year 1 (2023-2024)...")
    
    # THCS 2023-2024
    c2_student_mapping = {}
    for g_num in [6, 7, 8, 9]:
        for cl in classes_by_year_c2["2023-2024"][g_num]:
            c2_student_mapping[cl.id] = enroll_students_for_class(school_c2.id, cl, "2023-2024", student_cohorts_c2)

    # THPT 2023-2024
    c3_student_mapping = {}
    for g_num in [10, 11, 12]:
        for cl in classes_by_year_c3["2023-2024"][g_num]:
            c3_student_mapping[cl.id] = enroll_students_for_class(school_c3.id, cl, "2023-2024", student_cohorts_c3)

    session.commit()

    # Năm 2024-2025: Lên lớp!
    print("  Promoting students for Year 2 (2024-2025)...")
    
    # THCS Lên lớp: 6 -> 7, 7 -> 8, 8 -> 9. Khối 9 tốt nghiệp. Khối 6 tạo mới.
    for cl_next in classes_by_year_c2["2024-2025"][7]:
        cl_prev = next(c for c in classes_by_year_c2["2023-2024"][6] if c.name[-1] == cl_next.name[-1])
        st_ids = c2_student_mapping[cl_prev.id]
        for st_id in st_ids:
            en = tables.Enrollment(id=uuid4(), student_id=st_id, class_id=cl_next.id, academic_year_id=acad_years[school_c2.id]["2024-2025"].id, enrolled_at=acad_years[school_c2.id]["2024-2025"].start_date)
            session.add(en)
            active_enrollments.append((st_id, cl_next.id, "2024-2025", school_c2.id))
            cl_next.student_count = (cl_next.student_count or 0) + 1
            
    for cl_next in classes_by_year_c2["2024-2025"][8]:
        cl_prev = next(c for c in classes_by_year_c2["2023-2024"][7] if c.name[-1] == cl_next.name[-1])
        st_ids = c2_student_mapping[cl_prev.id]
        for st_id in st_ids:
            en = tables.Enrollment(id=uuid4(), student_id=st_id, class_id=cl_next.id, academic_year_id=acad_years[school_c2.id]["2024-2025"].id, enrolled_at=acad_years[school_c2.id]["2024-2025"].start_date)
            session.add(en)
            active_enrollments.append((st_id, cl_next.id, "2024-2025", school_c2.id))
            cl_next.student_count = (cl_next.student_count or 0) + 1
            
    for cl_next in classes_by_year_c2["2024-2025"][9]:
        cl_prev = next(c for c in classes_by_year_c2["2023-2024"][8] if c.name[-1] == cl_next.name[-1])
        st_ids = c2_student_mapping[cl_prev.id]
        for st_id in st_ids:
            en = tables.Enrollment(id=uuid4(), student_id=st_id, class_id=cl_next.id, academic_year_id=acad_years[school_c2.id]["2024-2025"].id, enrolled_at=acad_years[school_c2.id]["2024-2025"].start_date)
            session.add(en)
            active_enrollments.append((st_id, cl_next.id, "2024-2025", school_c2.id))
            cl_next.student_count = (cl_next.student_count or 0) + 1
            
    # Tạo mới học sinh Khối 6 năm 2024-2025
    c2_student_mapping_2024 = {}
    for cl in classes_by_year_c2["2024-2025"][6]:
        c2_student_mapping_2024[cl.id] = enroll_students_for_class(school_c2.id, cl, "2024-2025", student_cohorts_c2)

    # THPT Lên lớp 2024-2025: 10 -> 11, 11 -> 12. Khối 12 tốt nghiệp. Khối 10 tạo mới.
    for cl_next in classes_by_year_c3["2024-2025"][11]:
        cl_prev = next(c for c in classes_by_year_c3["2023-2024"][10] if c.name[-1] == cl_next.name[-1])
        st_ids = c3_student_mapping[cl_prev.id]
        for st_id in st_ids:
            en = tables.Enrollment(id=uuid4(), student_id=st_id, class_id=cl_next.id, academic_year_id=acad_years[school_c3.id]["2024-2025"].id, enrolled_at=acad_years[school_c3.id]["2024-2025"].start_date)
            session.add(en)
            active_enrollments.append((st_id, cl_next.id, "2024-2025", school_c3.id))
            cl_next.student_count = (cl_next.student_count or 0) + 1
            
    for cl_next in classes_by_year_c3["2024-2025"][12]:
        cl_prev = next(c for c in classes_by_year_c3["2023-2024"][11] if c.name[-1] == cl_next.name[-1])
        st_ids = c3_student_mapping[cl_prev.id]
        for st_id in st_ids:
            en = tables.Enrollment(id=uuid4(), student_id=st_id, class_id=cl_next.id, academic_year_id=acad_years[school_c3.id]["2024-2025"].id, enrolled_at=acad_years[school_c3.id]["2024-2025"].start_date)
            session.add(en)
            active_enrollments.append((st_id, cl_next.id, "2024-2025", school_c3.id))
            cl_next.student_count = (cl_next.student_count or 0) + 1
            
    # Tạo mới học sinh Khối 10 năm 2024-2025
    c3_student_mapping_2024 = {}
    for cl in classes_by_year_c3["2024-2025"][10]:
        c3_student_mapping_2024[cl.id] = enroll_students_for_class(school_c3.id, cl, "2024-2025", student_cohorts_c3)

    session.commit()

    # Năm 2025-2026: Lên lớp tiếp!
    print("  Promoting students for Year 3 (2025-2026)...")
    
    # THCS Lên lớp 2025-2026:
    for cl_next in classes_by_year_c2["2025-2026"][7]:
        cl_prev = next(c for c in classes_by_year_c2["2024-2025"][6] if c.name[-1] == cl_next.name[-1])
        st_ids = c2_student_mapping_2024[cl_prev.id]
        for st_id in st_ids:
            en = tables.Enrollment(id=uuid4(), student_id=st_id, class_id=cl_next.id, academic_year_id=acad_years[school_c2.id]["2025-2026"].id, enrolled_at=acad_years[school_c2.id]["2025-2026"].start_date)
            session.add(en)
            active_enrollments.append((st_id, cl_next.id, "2025-2026", school_c2.id))
            cl_next.student_count = (cl_next.student_count or 0) + 1
            
    for cl_next in classes_by_year_c2["2025-2026"][8]:
        cl_prev = next(c for c in classes_by_year_c2["2024-2025"][7] if c.name[-1] == cl_next.name[-1])
        st_ids = [st_id for st_id, class_id, y, sch in active_enrollments if class_id == cl_prev.id and y == "2024-2025"]
        for st_id in st_ids:
            en = tables.Enrollment(id=uuid4(), student_id=st_id, class_id=cl_next.id, academic_year_id=acad_years[school_c2.id]["2025-2026"].id, enrolled_at=acad_years[school_c2.id]["2025-2026"].start_date)
            session.add(en)
            active_enrollments.append((st_id, cl_next.id, "2025-2026", school_c2.id))
            cl_next.student_count = (cl_next.student_count or 0) + 1
            
    for cl_next in classes_by_year_c2["2025-2026"][9]:
        cl_prev = next(c for c in classes_by_year_c2["2024-2025"][8] if c.name[-1] == cl_next.name[-1])
        st_ids = [st_id for st_id, class_id, y, sch in active_enrollments if class_id == cl_prev.id and y == "2024-2025"]
        for st_id in st_ids:
            en = tables.Enrollment(id=uuid4(), student_id=st_id, class_id=cl_next.id, academic_year_id=acad_years[school_c2.id]["2025-2026"].id, enrolled_at=acad_years[school_c2.id]["2025-2026"].start_date)
            session.add(en)
            active_enrollments.append((st_id, cl_next.id, "2025-2026", school_c2.id))
            cl_next.student_count = (cl_next.student_count or 0) + 1
            
    # Tạo mới Khối 6 năm 2025-2026
    for cl in classes_by_year_c2["2025-2026"][6]:
        enroll_students_for_class(school_c2.id, cl, "2025-2026", student_cohorts_c2)

    # THPT Lên lớp 2025-2026:
    for cl_next in classes_by_year_c3["2025-2026"][11]:
        cl_prev = next(c for c in classes_by_year_c3["2024-2025"][10] if c.name[-1] == cl_next.name[-1])
        st_ids = c3_student_mapping_2024[cl_prev.id]
        for st_id in st_ids:
            en = tables.Enrollment(id=uuid4(), student_id=st_id, class_id=cl_next.id, academic_year_id=acad_years[school_c3.id]["2025-2026"].id, enrolled_at=acad_years[school_c3.id]["2025-2026"].start_date)
            session.add(en)
            active_enrollments.append((st_id, cl_next.id, "2025-2026", school_c3.id))
            cl_next.student_count = (cl_next.student_count or 0) + 1
            
    for cl_next in classes_by_year_c3["2025-2026"][12]:
        cl_prev = next(c for c in classes_by_year_c3["2024-2025"][11] if c.name[-1] == cl_next.name[-1])
        st_ids = [st_id for st_id, class_id, y, sch in active_enrollments if class_id == cl_prev.id and y == "2024-2025"]
        for st_id in st_ids:
            en = tables.Enrollment(id=uuid4(), student_id=st_id, class_id=cl_next.id, academic_year_id=acad_years[school_c3.id]["2025-2026"].id, enrolled_at=acad_years[school_c3.id]["2025-2026"].start_date)
            session.add(en)
            active_enrollments.append((st_id, cl_next.id, "2025-2026", school_c3.id))
            cl_next.student_count = (cl_next.student_count or 0) + 1
            
    # Tạo mới Khối 10 năm 2025-2026
    for cl in classes_by_year_c3["2025-2026"][10]:
        enroll_students_for_class(school_c3.id, cl, "2025-2026", student_cohorts_c3)

    session.commit()
    print("  Finished enrolling students. Total enrollment records:", len(active_enrollments))

    # 10. Sinh điểm số (Scores) cho 3 năm
    print("\nGenerating Scores...")
    # Lấy phân công GV
    all_ta = session.query(tables.TeacherAssignment).all()
    assignment_map = {}
    for ta in all_ta:
        if ta.role_context == enums.RoleContext.SUBJECT_TEACHER:
            assignment_map[(ta.class_id, ta.subject_id, ta.academic_year_id)] = ta.user_id

    scores_to_add = []
    total_scores_count = 0
    
    # Định nghĩa các cột điểm của V2 học kỳ
    score_columns = []
    for idx in range(1, 4):
        score_columns.append((enums.ScoreCategory.ORAL, idx))
    for idx in range(1, 5):
        score_columns.append((enums.ScoreCategory.REGULAR, idx))
    for idx in range(1, 3):
        score_columns.append((enums.ScoreCategory.MIDTERM, idx))
    score_columns.append((enums.ScoreCategory.FINAL, 1))

    # Sinh hệ số độ khó ngẫu nhiên cho đề thi (mỗi môn, học kỳ, năm học, khối) để kiểm thử Z-score
    difficulty_map = {}
    
    for idx, (st_id, cl_id, y_name, sch_id) in enumerate(active_enrollments):
        ay_id = acad_years[sch_id][y_name].id
        cohort_dict = student_cohorts_c2 if sch_id == school_c2.id else student_cohorts_c3
        
        student_profile = cohort_dict[st_id]
        ability_base = student_profile["ability"]
        affinities = student_profile["affinities"]
        trend_type = student_profile["trend_type"]
        
        sch_subjects = subjects_c2 if sch_id == school_c2.id else subjects_c3
        
        # Lấy thông tin lớp
        class_obj = session.get(tables.Class, cl_id)
        grade_id = class_obj.grade_id
        
        for code, sub in sch_subjects.items():
            if (cl_id, sub.id, ay_id) not in assignment_map:
                continue
                
            teacher_id = assignment_map[(cl_id, sub.id, ay_id)]
            sub_ability = ability_base + affinities.get(code, 0.0)
            
            # ĐỘ LỆCH PHỔ ĐIỂM ĐẶC THÙ MÔN HỌC:
            # - Môn Ngữ văn (VAN): Phổ điểm hẹp, kéo về mức trung bình khá (6.0 - 7.2)
            if code == "VAN":
                sub_ability = 6.2 + (sub_ability - 6.5) * 0.4
                sub_ability = max(5.0, min(8.8, sub_ability))
                std_dev_base = 0.35
            else:
                std_dev_base = 0.7

            # --- ÁP DỤNG PROFILE DỊ BIỆT HỌC THUẬT LỚP HỌC (Delta G) ---
            # Lớp 7A1 và 12A1 học rất tốt Tiếng Anh nhưng rất tệ môn Toán học
            if class_obj.name in ["7A1", "12A1"]:
                if code == "TOAN":
                    sub_ability -= 2.0
                elif code == "ANH":
                    sub_ability += 2.0
            
            for sem_num in [1, 2]:
                sem_obj = semesters[sch_id][(y_name, sem_num)]
                sem_id = sem_obj.id
                
                # Khởi tạo độ khó đề thi ngẫu nhiên cho nhóm (môn, học kỳ, khối)
                diff_key = (sub.id, sem_id, grade_id)
                if diff_key not in difficulty_map:
                    difficulty_map[diff_key] = random.uniform(-1.2, 1.0)
                diff_bias = difficulty_map[diff_key]
                
                adjusted_ability = sub_ability + diff_bias
                if sem_num == 2:
                    if trend_type == "DECREASE":
                        adjusted_ability -= 1.8
                    elif trend_type == "INCREASE":
                        adjusted_ability += 1.5

                # --- ÁP DỤNG PROFILE LỚP HỌC YẾU/CAN THIỆP (At-Risk) ---
                if class_obj.name in ["9A2", "12A2"]:
                    adjusted_ability -= 2.2
                
                sem_start = sem_obj.start_date
                
                for category, column_index in score_columns:
                    # HIỆN TƯỢNG THIẾU ĐIỂM: Gieo 0.6% tỷ lệ điểm bị khuyết (NULL)
                    if random.random() < 0.006:
                        continue
                        
                    is_regular = category in (enums.ScoreCategory.ORAL, enums.ScoreCategory.REGULAR)
                    std_dev = std_dev_base if is_regular else (std_dev_base * 0.6)
                    val = random.normalvariate(adjusted_ability, std_dev)
                    
                    is_early = category == enums.ScoreCategory.ORAL or (category == enums.ScoreCategory.REGULAR and column_index in (1, 2)) or (category == enums.ScoreCategory.MIDTERM and column_index == 1)

                    # --- ÁP DỤNG PROFILE LẠM PHÁT ĐIỂM (GDI) ---
                    if class_obj.name in ["8A1", "10A1"]:
                        if is_regular:
                            val = max(8.5, min(9.8, adjusted_ability + 2.0 + random.normalvariate(0, 0.4)))
                        else:
                            val = max(3.5, min(5.5, adjusted_ability - 2.0 + random.normalvariate(0, 0.5)))

                    # --- ÁP DỤNG PROFILE ĐỘNG LƯỢNG ÂM (Sa sút sau giữa kỳ) ---
                    elif class_obj.name in ["8A2", "10A2"]:
                        if is_early:
                            val = max(7.5, min(9.5, adjusted_ability + 1.5 + random.normalvariate(0, 0.4)))
                        else:
                            val = max(3.0, min(5.2, adjusted_ability - 2.0 + random.normalvariate(0, 0.5)))

                    # --- ÁP DỤNG PROFILE ĐỘNG LƯỢNG DƯƠNG (Tiến bộ sau giữa kỳ) ---
                    elif class_obj.name in ["9A1", "11A1"]:
                        if is_early:
                            val = max(3.0, min(5.8, adjusted_ability - 1.5 + random.normalvariate(0, 0.5)))
                        else:
                            val = max(7.5, min(9.8, adjusted_ability + 1.8 + random.normalvariate(0, 0.4)))

                    # --- ÁP DỤNG PROFILE NĂNG LỰC ẨN HỌC SINH (Student Archetype) ---
                    else:
                        archetype = student_profile.get("archetype", "others")
                        if archetype == "consistent":
                            val = max(8.0, min(10.0, adjusted_ability + random.normalvariate(0, 0.3)))
                        elif archetype == "procrastinator":
                            if is_regular:
                                val = min(6.2, max(3.5, adjusted_ability - 2.0 + random.normalvariate(0, 0.4)))
                            else:
                                val = max(7.8, min(9.8, adjusted_ability + 1.5 + random.normalvariate(0, 0.4)))
                        elif archetype == "high_effort":
                            if is_regular:
                                val = max(7.6, min(9.8, adjusted_ability + 1.5 + random.normalvariate(0, 0.4)))
                            else:
                                val = min(5.2, max(2.5, adjusted_ability - 2.0 + random.normalvariate(0, 0.4)))
                        elif archetype == "high_risk":
                            if category == enums.ScoreCategory.FINAL or (category == enums.ScoreCategory.REGULAR and column_index in (3, 4)) or (category == enums.ScoreCategory.MIDTERM and column_index == 2):
                                val = min(4.8, max(1.0, adjusted_ability - 1.5 + random.normalvariate(0, 0.4)))
                            else:
                                val = min(4.8, max(1.0, adjusted_ability - 0.8 + random.normalvariate(0, 0.5)))
                    
                    val = max(0.0, min(10.0, val))
                    val = round(val, 1)
                    
                    # RẢI NGÀY NHẬP ĐIỂM THỰC TẾ (Scattered Timestamps):
                    if category == enums.ScoreCategory.ORAL:
                        if column_index == 1:
                            days_offset = random.randint(10, 35)
                        elif column_index == 2:
                            days_offset = random.randint(40, 75)
                        else:
                            days_offset = random.randint(80, 115)
                    elif category == enums.ScoreCategory.REGULAR:
                        if column_index == 1:
                            days_offset = random.randint(15, 30)
                        elif column_index == 2:
                            days_offset = random.randint(35, 55)
                        elif column_index == 3:
                            days_offset = random.randint(65, 85)
                        else:
                            days_offset = random.randint(90, 110)
                    elif category == enums.ScoreCategory.MIDTERM:
                        if column_index == 1:
                            days_offset = random.randint(50, 70)
                        else:
                            days_offset = random.randint(75, 95)
                    else: # FINAL
                        days_offset = random.randint(110, 130)
                        
                    score_date = datetime.combine(sem_start + timedelta(days=days_offset), datetime.min.time())
                    score_date = score_date + timedelta(hours=random.randint(7, 17), minutes=random.randint(0, 59))
                    
                    status = enums.ScoreStatus.APPROVED
                    if random.random() < 0.01:
                        status = enums.ScoreStatus.DRAFT
                    
                    approved_by_val = None if status == enums.ScoreStatus.DRAFT else (principal_c2.id if sch_id == school_c2.id else principal_c3.id)
                    approved_at_val = None if status == enums.ScoreStatus.DRAFT else score_date + timedelta(days=random.randint(1, 3))

                    scores_to_add.append({
                        "id": uuid4(),
                        "student_id": st_id,
                        "subject_id": sub.id,
                        "class_id": cl_id,
                        "semester_id": sem_id,
                        "score_category": category,
                        "column_index": column_index,
                        "value": val,
                        "status": status,
                        "entered_by": teacher_id,
                        "approved_by": approved_by_val,
                        "approved_at": approved_at_val,
                        "created_at": score_date,
                        "updated_at": score_date
                    })
                    total_scores_count += 1
                    
        if len(scores_to_add) >= 5000:
            session.bulk_insert_mappings(tables.Score, scores_to_add)
            session.commit()
            print(f"  Inserted {total_scores_count} scores...")
            scores_to_add = []

    if scores_to_add:
        session.bulk_insert_mappings(tables.Score, scores_to_add)
        session.commit()
        
    print(f"  Finished generating scores. Total scores added: {total_scores_count}")

    # 11. Làm mới Materialized View
    print("\nRefreshing Materialized View `mv_exam_difficulty`...")
    try:
        session.execute(text("REFRESH MATERIALIZED VIEW mv_exam_difficulty;"))
        session.commit()
        print("  Materialized view refreshed successfully.")
    except Exception as e:
        print("  Error refreshing materialized view:", str(e))

    session.close()
    print("\n================ MOCK DATA GENERATION COMPLETE ================ \n")

if __name__ == "__main__":
    main()
