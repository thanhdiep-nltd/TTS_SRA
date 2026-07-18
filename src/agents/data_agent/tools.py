import json
from types import SimpleNamespace

from langchain_core.tools import tool
from sqlalchemy import select

from src.agents.context import current_user_id, current_user_role, current_user_school_id
from src.agents.helpers import score_breakdown, subject_average_and_rank
from src.db.session import SessionLocal
from src.models import enums, tables
from src.services.rbac import accessible_score_filter


@tool
def get_student_info(name_or_id: str) -> str:
    """Tìm kiếm thông tin cá nhân của học sinh trong trường dựa trên Họ tên hoặc Mã học sinh.

    Args:
        name_or_id: Họ tên học sinh (ví dụ: 'Ngô Ngọc Hoa') hoặc Mã học sinh (ví dụ: '2502151184').

    Returns:
        Một chuỗi JSON chứa danh sách các học sinh khớp thông tin.
    """
    school_id = current_user_school_id.get()
    if not school_id:
        return "Lỗi: Không xác định được trường của người dùng. Vui lòng đăng nhập."

    query = name_or_id.strip()
    with SessionLocal() as session:
        stmt = select(tables.Student).where(tables.Student.school_id == school_id, tables.Student.is_active.is_(True))
        if query.isdigit():
            stmt = stmt.where(tables.Student.student_code == query)
        else:
            stmt = stmt.where(tables.Student.full_name.ilike(f"%{query}%"))

        students = session.scalars(stmt).all()
        if not students:
            return f"Không tìm thấy học sinh nào khớp với thông tin '{name_or_id}' tại trường của bạn."

        results = []
        for s in students:
            # Get latest enrollment to find their current class
            enroll_stmt = (
                select(tables.Enrollment, tables.Class, tables.AcademicYear)
                .join(tables.Class, tables.Enrollment.class_id == tables.Class.id)
                .join(tables.AcademicYear, tables.Enrollment.academic_year_id == tables.AcademicYear.id)
                .where(tables.Enrollment.student_id == s.id)
                .order_by(tables.AcademicYear.name.desc())
                .limit(1)
            )
            enroll_info = session.execute(enroll_stmt).first()

            class_name = "Chưa xếp lớp"
            year_name = "Năm học trống"
            cohort = "Không rõ"
            if enroll_info:
                enroll, cl, ay = enroll_info
                class_name = cl.name
                year_name = ay.name
                try:
                    # Cohort calculation based on class name (e.g. 8A1 -> grade 8)
                    grade_num = int("".join(filter(str.isdigit, class_name)))
                    start_year = int(year_name.split("-")[0])
                    base_grade = 6 if grade_num <= 9 else 10
                    cohort = start_year - (grade_num - base_grade)
                except Exception:
                    cohort = "Không rõ"

            results.append(
                {
                    "Mã học sinh": s.student_code,
                    "Họ và Tên": s.full_name,
                    "Ngày sinh": s.date_of_birth.strftime("%Y-%m-%d") if s.date_of_birth else "",
                    "Lớp (HK gần nhất)": class_name,
                    "Niên khóa (Năm vào trường)": cohort,
                }
            )

        return json.dumps(results, ensure_ascii=False, indent=2)


@tool
def get_student_grades(student_id: str, year: int = None, semester: int = None, subject: str = None) -> str:
    """Tra cứu điểm số chi tiết của một học sinh theo Mã học sinh và các bộ lọc tùy chọn.

    Args:
        student_id: Mã học sinh (10 chữ số, ví dụ: '2502151184').
        year: Năm học bắt đầu (ví dụ: 2023).
        semester: Học kỳ (tùy chọn, chỉ nhận giá trị 1 hoặc 2).
        subject: Tên môn học (tùy chọn: 'Toán học', 'Ngữ văn', 'Khoa học tự nhiên').

    Returns:
        Chuỗi JSON chứa danh sách điểm số chi tiết của học sinh.
    """
    school_id = current_user_school_id.get()
    if not school_id:
        return "Lỗi: Không xác định được trường của người dùng."

    student_id = student_id.strip()
    with SessionLocal() as session:
        # Scope check: student must be in the same school
        student = session.scalar(
            select(tables.Student).where(
                tables.Student.student_code == student_id, tables.Student.school_id == school_id
            )
        )
        if not student:
            return f"Không tìm thấy học sinh có mã '{student_id}' trong hệ thống của trường."

        stmt = (
            select(tables.Score, tables.Subject, tables.Semester, tables.AcademicYear, tables.Class)
            .join(tables.Subject, tables.Score.subject_id == tables.Subject.id)
            .join(tables.Semester, tables.Score.semester_id == tables.Semester.id)
            .join(tables.AcademicYear, tables.Semester.academic_year_id == tables.AcademicYear.id)
            .join(tables.Class, tables.Score.class_id == tables.Class.id)
            .where(tables.Score.student_id == student.id, tables.Score.status == enums.ScoreStatus.APPROVED)
        )

        user_role = current_user_role.get()
        user_id = current_user_id.get()
        if user_role not in ("PRINCIPAL", "ADMIN") and user_id:
            user = SimpleNamespace(id=user_id, school_id=school_id, role=user_role)
            rbac_filter = accessible_score_filter(session, user)
            stmt = stmt.where(rbac_filter)

        if year is not None:
            year_str = f"{year}-{year + 1}" if isinstance(year, int) else str(year)
            stmt = stmt.where(tables.AcademicYear.name == year_str)
        if semester is not None:
            stmt = stmt.where(tables.Semester.number == int(semester))
        if subject is not None:
            stmt = stmt.where(tables.Subject.name.ilike(f"%{subject.strip()}%"))

        scores = session.execute(stmt).all()
        if not scores:
            return f"Không tìm thấy dữ liệu điểm cho Mã học sinh '{student_id}' với bộ lọc đã cho."

        # Gom RAW Score theo (năm học, lớp, học kỳ, môn) để tính ĐTB đúng công thức chính thức
        # (bao gồm điểm Miệng, không yêu cầu phải đủ mọi đầu điểm).
        grouped: dict[tuple, dict] = {}
        for score, sub, sem, ay, cl in scores:
            key = (ay.name, cl.name, sem.number, sub.name)
            if key not in grouped:
                grouped[key] = {"meta": (ay.name, cl.name, sem.number, sub.name), "scores": []}
            grouped[key]["scores"].append(score)

        output_rows = []
        for val in grouped.values():
            ay_name, cl_name, sem_num, sub_name = val["meta"]
            dtb, rank = subject_average_and_rank(val["scores"])
            breakdown = score_breakdown(val["scores"])
            output_rows.append(
                {
                    "Năm học": ay_name,
                    "Lớp": cl_name,
                    "Học kỳ": sem_num,
                    "Môn": sub_name,
                    **{f"Điểm {label}": value for label, value in breakdown.items()},
                    "ĐTB môn học kỳ": dtb if dtb is not None else "",
                    "Học lực": rank if rank is not None else "",
                }
            )

        return json.dumps(output_rows, ensure_ascii=False, indent=2)


@tool
def get_class_grades(class_name: str, year: int, semester: int, subject: str = None) -> str:
    """Tra cứu danh sách điểm trung bình môn học kỳ của tất cả học sinh trong một lớp học cụ thể.

    Args:
        class_name: Tên lớp học (ví dụ: '6A1', '10A2').
        year: Năm học bắt đầu (ví dụ: 2023).
        semester: Học kỳ (1 hoặc 2).
        subject: Tên môn học (tùy chọn: 'Toán học', 'Ngữ văn').

    Returns:
        Chuỗi JSON chứa danh sách điểm số của lớp học.
    """
    school_id = current_user_school_id.get()
    if not school_id:
        return "Lỗi: Không xác định được trường của người dùng."

    class_name = class_name.strip().upper()
    year_str = f"{year}-{year + 1}" if isinstance(year, int) else str(year)

    with SessionLocal() as session:
        clazz = session.scalar(
            select(tables.Class)
            .join(tables.Grade, tables.Class.grade_id == tables.Grade.id)
            .join(tables.AcademicYear, tables.Class.academic_year_id == tables.AcademicYear.id)
            .where(
                tables.Class.name == class_name,
                tables.AcademicYear.name == year_str,
                tables.Grade.school_id == school_id,
            )
        )
        if not clazz:
            return f"Không tìm thấy lớp '{class_name}' trong năm học {year_str} của trường."

        sem = session.scalar(
            select(tables.Semester).where(
                tables.Semester.academic_year_id == clazz.academic_year_id, tables.Semester.number == int(semester)
            )
        )
        if not sem:
            return f"Không tìm thấy Học kỳ {semester} trong năm học {year_str}."

        stmt = (
            select(tables.Score, tables.Student, tables.Subject)
            .join(tables.Student, tables.Score.student_id == tables.Student.id)
            .join(tables.Subject, tables.Score.subject_id == tables.Subject.id)
            .where(
                tables.Score.class_id == clazz.id,
                tables.Score.semester_id == sem.id,
                tables.Score.status == enums.ScoreStatus.APPROVED,
            )
        )

        user_role = current_user_role.get()
        user_id = current_user_id.get()
        if user_role not in ("PRINCIPAL", "ADMIN") and user_id:
            user = SimpleNamespace(id=user_id, school_id=school_id, role=user_role)
            rbac_filter = accessible_score_filter(session, user)
            stmt = stmt.where(rbac_filter)
        if subject is not None:
            stmt = stmt.where(tables.Subject.name.ilike(f"%{subject.strip()}%"))

        scores = session.execute(stmt).all()
        if not scores:
            return f"Không tìm thấy dữ liệu điểm cho lớp '{class_name}' môn '{subject}' trong học kỳ {semester}."

        student_data: dict = {}
        student_names = {}
        for score, student, sub in scores:
            student_names[student.id] = (student.student_code, student.full_name)
            student_data.setdefault(student.id, {}).setdefault(sub.name, []).append(score)

        results = []
        for s_id, subjects_dict in student_data.items():
            code, name = student_names[s_id]
            for sub_name, score_list in subjects_dict.items():
                dtb, rank = subject_average_and_rank(score_list)
                results.append(
                    {
                        "Mã học sinh": code,
                        "Họ và Tên": name,
                        "Môn": sub_name,
                        "ĐTB môn học kỳ": dtb if dtb is not None else "",
                        "Học lực": rank if rank is not None else "",
                    }
                )

        return json.dumps(results, ensure_ascii=False, indent=2)
