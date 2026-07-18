import json
from contextvars import ContextVar
from uuid import UUID

from langchain_core.tools import tool
from sqlalchemy import select

from src.db.session import SessionLocal
from src.models import enums, tables

# Context variables for thread/task-safe propagation of user environment
current_user_school_id: ContextVar[UUID | None] = ContextVar("current_user_school_id", default=None)
current_user_role: ContextVar[str | None] = ContextVar("current_user_role", default=None)


def _get_subject_average(item):
    """Helper to calculate subject average score in Python using PL/pgSQL logic:
    (sum(TX) + 2*GK + 3*CK) / (count(TX) + 5)
    """
    tx_vals = [item[t] for t in ["TX1", "TX2", "TX3", "TX4"] if item[t] is not None]
    gk_val = item["GK"]
    ck_val = item["CK"]
    if tx_vals and gk_val is not None and ck_val is not None:
        avg = (sum(tx_vals) + 2 * gk_val + 3 * ck_val) / (len(tx_vals) + 5)
        return round(avg, 2)
    return None


def _get_rank_label(avg):
    """Helper to map average score to GDPT 2018 ranks"""
    if avg is None:
        return ""
    if avg >= 8.0:
        return "Tốt"
    elif avg >= 6.5:
        return "Khá"
    elif avg >= 5.0:
        return "Đạt"
    else:
        return "Chưa đạt"


def _score_type_str(score) -> str:
    # Trích xuất giá trị string từ enum score_category
    cat = score.score_category.value if hasattr(score.score_category, "value") else str(score.score_category)
    idx = score.column_index
    if cat == "REGULAR":
        return f"TX{idx}"
    elif cat == "MIDTERM":
        return "GK"
    elif cat == "FINAL":
        return "CK"
    elif cat == "ORAL":
        return f"ORAL{idx}"
    return "UNKNOWN"


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

        # Group components by semester subject
        grouped = {}
        for score, sub, sem, ay, cl in scores:
            key = (ay.name, cl.name, sem.number, sub.name)
            if key not in grouped:
                grouped[key] = {
                    "Năm học": ay.name,
                    "Lớp": cl.name,
                    "Học kỳ": sem.number,
                    "Môn": sub.name,
                    "TX1": None,
                    "TX2": None,
                    "TX3": None,
                    "TX4": None,
                    "GK": None,
                    "CK": None,
                }
            s_type = _score_type_str(score)
            if s_type in grouped[key]:
                grouped[key][s_type] = float(score.value)

        output_rows = []
        for key, val in grouped.items():
            dtb = _get_subject_average(val)
            rank = _get_rank_label(dtb)
            output_rows.append(
                {
                    "Năm học": val["Năm học"],
                    "Lớp": val["Lớp"],
                    "Học kỳ": val["Học kỳ"],
                    "Môn": val["Môn"],
                    "Điểm Tx1": val["TX1"] if val["TX1"] is not None else "",
                    "Điểm Tx2": val["TX2"] if val["TX2"] is not None else "",
                    "Điểm Tx3": val["TX3"] if val["TX3"] is not None else "",
                    "Điểm Tx4": val["TX4"] if val["TX4"] is not None else "",
                    "Điểm Giữa kỳ": val["GK"] if val["GK"] is not None else "",
                    "Điểm Cuối kỳ": val["CK"] if val["CK"] is not None else "",
                    "ĐTB môn học kỳ": dtb if dtb is not None else "",
                    "Học lực": rank,
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
        if subject is not None:
            stmt = stmt.where(tables.Subject.name.ilike(f"%{subject.strip()}%"))

        scores = session.execute(stmt).all()
        if not scores:
            return f"Không tìm thấy dữ liệu điểm cho lớp '{class_name}' môn '{subject}' trong học kỳ {semester}."

        student_data = {}
        student_names = {}
        for score, student, sub in scores:
            student_names[student.id] = (student.student_code, student.full_name)
            s_key = student.id
            if s_key not in student_data:
                student_data[s_key] = {}
            if sub.name not in student_data[s_key]:
                student_data[s_key][sub.name] = {
                    "TX1": None,
                    "TX2": None,
                    "TX3": None,
                    "TX4": None,
                    "GK": None,
                    "CK": None,
                }
            s_type = _score_type_str(score)
            if s_type in student_data[s_key][sub.name]:
                student_data[s_key][sub.name][s_type] = float(score.value)

        results = []
        for s_id, subjects_dict in student_data.items():
            code, name = student_names[s_id]
            for sub_name, item in subjects_dict.items():
                dtb = _get_subject_average(item)
                rank = _get_rank_label(dtb)
                results.append(
                    {
                        "Mã học sinh": code,
                        "Họ và Tên": name,
                        "Môn": sub_name,
                        "ĐTB môn học kỳ": dtb if dtb is not None else "",
                        "Học lực": rank,
                    }
                )

        return json.dumps(results, ensure_ascii=False, indent=2)


@tool
def calculate_grade_statistics(
    class_name: str = None, grade_level: int = None, year: int = None, semester: int = None, subject: str = None
) -> str:
    """Tính toán thống kê học tập (Điểm trung bình, Điểm cao nhất, Điểm thấp nhất, Phân loại học lực) của một lớp hoặc toàn khối.

    Args:
        class_name: Tên lớp học (tùy chọn, ví dụ: '6A1').
        grade_level: Khối lớp (tùy chọn: 6, 7, 8, 9, 10, 11, 12).
        year: Năm học bắt đầu (ví dụ: 2023).
        semester: Học kỳ (tùy chọn, 1 hoặc 2).
        subject: Tên môn học (tùy chọn: 'Toán học', 'Ngữ văn').

    Returns:
        Chuỗi JSON chứa báo cáo thống kê chi tiết.
    """
    school_id = current_user_school_id.get()
    if not school_id:
        return "Lỗi: Không xác định được trường của người dùng."

    year_str = f"{year}-{year + 1}" if isinstance(year, int) else str(year)

    with SessionLocal() as session:
        stmt = (
            select(tables.Score, tables.Subject, tables.Class, tables.Grade)
            .join(tables.Subject, tables.Score.subject_id == tables.Subject.id)
            .join(tables.Class, tables.Score.class_id == tables.Class.id)
            .join(tables.Grade, tables.Class.grade_id == tables.Grade.id)
            .join(tables.Semester, tables.Score.semester_id == tables.Semester.id)
            .join(tables.AcademicYear, tables.Semester.academic_year_id == tables.AcademicYear.id)
            .where(tables.Grade.school_id == school_id, tables.Score.status == enums.ScoreStatus.APPROVED)
        )
        if year is not None:
            stmt = stmt.where(tables.AcademicYear.name == year_str)
        if semester is not None:
            stmt = stmt.where(tables.Semester.number == int(semester))
        if class_name is not None:
            stmt = stmt.where(tables.Class.name == class_name.strip().upper())
        if grade_level is not None:
            stmt = stmt.where(tables.Grade.grade_number == int(grade_level))
        if subject is not None:
            stmt = stmt.where(tables.Subject.name.ilike(f"%{subject.strip()}%"))

        scores = session.execute(stmt).all()
        if not scores:
            return "Không tìm thấy dữ liệu phù hợp để tính toán thống kê."

        grouped = {}
        for score, sub, cl, gr in scores:
            s_key = (score.student_id, sub.name)
            if s_key not in grouped:
                grouped[s_key] = {"TX1": None, "TX2": None, "TX3": None, "TX4": None, "GK": None, "CK": None}
            s_type = _score_type_str(score)
            if s_type in grouped[s_key]:
                grouped[s_key][s_type] = float(score.value)

        dtb_scores = []
        for s_key, item in grouped.items():
            dtb = _get_subject_average(item)
            if dtb is not None:
                dtb_scores.append(dtb)

        if not dtb_scores:
            return "Không tìm thấy đủ dữ liệu điểm để tính điểm trung bình học kỳ."

        total_count = len(dtb_scores)
        avg_score = round(sum(dtb_scores) / total_count, 2)
        max_score = max(dtb_scores)
        min_score = min(dtb_scores)

        ranks = {"Tốt": 0, "Khá": 0, "Đạt": 0, "Chưa đạt": 0}
        for s in dtb_scores:
            ranks[_get_rank_label(s)] += 1

        stats = {
            "Bộ lọc áp dụng": {
                "Lớp": class_name,
                "Khối": grade_level,
                "Năm học": year_str if year else None,
                "Học kỳ": semester,
                "Môn học": subject,
            },
            "Tổng số bản ghi điểm học sinh": total_count,
            "Điểm trung bình (ĐTB)": avg_score,
            "Điểm cao nhất": max_score,
            "Điểm thấp nhất": min_score,
            "Phân phối học lực": ranks,
        }

        return json.dumps(stats, ensure_ascii=False, indent=2)


@tool
def find_top_students(
    year: int, semester: int, class_name: str = None, grade_level: int = None, subject: str = None, limit: int = 5
) -> str:
    """Tìm danh sách những học sinh có điểm số cao nhất (Thủ khoa, top học sinh giỏi) theo lớp hoặc khối.

    Args:
        year: Năm học bắt đầu (ví dụ: 2023).
        semester: Học kỳ (1 hoặc 2).
        class_name: Tên lớp học (tùy chọn, ví dụ: '6A1').
        grade_level: Khối lớp (tùy chọn: 6, 7, 8, 9, 10, 11, 12).
        subject: Môn học cụ thể (tùy chọn, ví dụ: 'Toán học').
        limit: Số lượng học sinh tối đa muốn hiển thị (mặc định là 5).

    Returns:
        Chuỗi JSON chứa danh sách học sinh xuất sắc nhất và điểm trung bình tương ứng.
    """
    school_id = current_user_school_id.get()
    if not school_id:
        return "Lỗi: Không xác định được trường của người dùng."

    year_str = f"{year}-{year + 1}" if isinstance(year, int) else str(year)

    with SessionLocal() as session:
        stmt = (
            select(tables.Score, tables.Student, tables.Subject, tables.Class, tables.Grade)
            .join(tables.Student, tables.Score.student_id == tables.Student.id)
            .join(tables.Subject, tables.Score.subject_id == tables.Subject.id)
            .join(tables.Class, tables.Score.class_id == tables.Class.id)
            .join(tables.Grade, tables.Class.grade_id == tables.Grade.id)
            .join(tables.Semester, tables.Score.semester_id == tables.Semester.id)
            .join(tables.AcademicYear, tables.Semester.academic_year_id == tables.AcademicYear.id)
            .where(
                tables.Grade.school_id == school_id,
                tables.Score.status == enums.ScoreStatus.APPROVED,
                tables.AcademicYear.name == year_str,
                tables.Semester.number == int(semester),
            )
        )
        if class_name is not None:
            stmt = stmt.where(tables.Class.name == class_name.strip().upper())
        if grade_level is not None:
            stmt = stmt.where(tables.Grade.grade_number == int(grade_level))
        if subject is not None:
            stmt = stmt.where(tables.Subject.name.ilike(f"%{subject.strip()}%"))

        scores = session.execute(stmt).all()
        if not scores:
            return "Không tìm thấy dữ liệu điểm phù hợp."

        student_data = {}
        for score, student, sub, cl, gr in scores:
            s_key = (student.student_code, student.full_name, cl.name)
            if s_key not in student_data:
                student_data[s_key] = {}
            sub_key = sub.name
            if sub_key not in student_data[s_key]:
                student_data[s_key][sub_key] = {
                    "TX1": None,
                    "TX2": None,
                    "TX3": None,
                    "TX4": None,
                    "GK": None,
                    "CK": None,
                }
            s_type = _score_type_str(score)
            if s_type in student_data[s_key][sub_key]:
                student_data[s_key][sub_key][s_type] = float(score.value)

        leaderboard = []
        for s_key, subjects in student_data.items():
            code, name, cl_name = s_key
            subject_avgs = []
            for sub_name, item in subjects.items():
                dtb = _get_subject_average(item)
                if dtb is not None:
                    subject_avgs.append(dtb)

            if subject_avgs:
                gpa = round(sum(subject_avgs) / len(subject_avgs), 2)
                leaderboard.append(
                    {
                        "Mã học sinh": code,
                        "Họ và Tên": name,
                        "Lớp": cl_name,
                        "Điểm trung bình (GPA)": gpa,
                        "Số môn tính điểm": len(subject_avgs),
                    }
                )

        leaderboard.sort(key=lambda x: x["Điểm trung bình (GPA)"], reverse=True)
        return json.dumps(leaderboard[:limit], ensure_ascii=False, indent=2)


@tool
def find_struggling_students(
    year: int, semester: int, class_name: str = None, grade_level: int = None, subject: str = None, limit: int = 5
) -> str:
    """Tìm danh sách những học sinh có kết quả học tập thấp nhất (học sinh yếu, kém) để kịp thời hỗ trợ.

    Args:
        year: Năm học bắt đầu (ví dụ: 2023).
        semester: Học kỳ (1 hoặc 2).
        class_name: Tên lớp học (tùy chọn, ví dụ: '6A1').
        grade_level: Khối lớp (tùy chọn: 6, 7, 8, 9, 10, 11, 12).
        subject: Môn học cụ thể (tùy chọn: 'Toán học', 'Ngữ văn').
        limit: Số lượng học sinh tối đa muốn hiển thị (mặc định là 5).

    Returns:
        Chuỗi JSON chứa danh sách học sinh yếu nhất.
    """
    school_id = current_user_school_id.get()
    if not school_id:
        return "Lỗi: Không xác định được trường của người dùng."

    year_str = f"{year}-{year + 1}" if isinstance(year, int) else str(year)

    with SessionLocal() as session:
        stmt = (
            select(tables.Score, tables.Student, tables.Subject, tables.Class, tables.Grade)
            .join(tables.Student, tables.Score.student_id == tables.Student.id)
            .join(tables.Subject, tables.Score.subject_id == tables.Subject.id)
            .join(tables.Class, tables.Score.class_id == tables.Class.id)
            .join(tables.Grade, tables.Class.grade_id == tables.Grade.id)
            .join(tables.Semester, tables.Score.semester_id == tables.Semester.id)
            .join(tables.AcademicYear, tables.Semester.academic_year_id == tables.AcademicYear.id)
            .where(
                tables.Grade.school_id == school_id,
                tables.Score.status == enums.ScoreStatus.APPROVED,
                tables.AcademicYear.name == year_str,
                tables.Semester.number == int(semester),
            )
        )
        if class_name is not None:
            stmt = stmt.where(tables.Class.name == class_name.strip().upper())
        if grade_level is not None:
            stmt = stmt.where(tables.Grade.grade_number == int(grade_level))
        if subject is not None:
            stmt = stmt.where(tables.Subject.name.ilike(f"%{subject.strip()}%"))

        scores = session.execute(stmt).all()
        if not scores:
            return "Không tìm thấy dữ liệu điểm phù hợp."

        student_data = {}
        for score, student, sub, cl, gr in scores:
            s_key = (student.student_code, student.full_name, cl.name)
            if s_key not in student_data:
                student_data[s_key] = {}
            sub_key = sub.name
            if sub_key not in student_data[s_key]:
                student_data[s_key][sub_key] = {
                    "TX1": None,
                    "TX2": None,
                    "TX3": None,
                    "TX4": None,
                    "GK": None,
                    "CK": None,
                }
            s_type = _score_type_str(score)
            if s_type in student_data[s_key][sub_key]:
                student_data[s_key][sub_key][s_type] = float(score.value)

        leaderboard = []
        for s_key, subjects in student_data.items():
            code, name, cl_name = s_key
            subject_avgs = []
            for sub_name, item in subjects.items():
                dtb = _get_subject_average(item)
                if dtb is not None:
                    subject_avgs.append(dtb)

            if subject_avgs:
                gpa = round(sum(subject_avgs) / len(subject_avgs), 2)
                leaderboard.append(
                    {
                        "Mã học sinh": code,
                        "Họ và Tên": name,
                        "Lớp": cl_name,
                        "Điểm trung bình (GPA)": gpa,
                        "Số môn tính điểm": len(subject_avgs),
                    }
                )

        # Sort ascending for struggling students
        leaderboard.sort(key=lambda x: x["Điểm trung bình (GPA)"])
        return json.dumps(leaderboard[:limit], ensure_ascii=False, indent=2)


@tool
def compare_classes(year: int, semester: int, subject: str, grade_level: int) -> str:
    """So sánh điểm trung bình giữa tất cả các lớp trong một khối lớp cụ thể của một môn học.

    Args:
        year: Năm học (ví dụ: 2023).
        semester: Học kỳ (1 hoặc 2).
        subject: Tên môn học (ví dụ: 'Toán học', 'Ngữ văn').
        grade_level: Khối lớp muốn so sánh (6, 7, 8, 9, 10, 11, 12).

    Returns:
        Chuỗi JSON chứa danh sách xếp hạng các lớp và điểm trung bình của từng lớp.
    """
    school_id = current_user_school_id.get()
    if not school_id:
        return "Lỗi: Không xác định được trường của người dùng."

    year_str = f"{year}-{year + 1}" if isinstance(year, int) else str(year)

    with SessionLocal() as session:
        stmt = (
            select(tables.Score, tables.Subject, tables.Class, tables.Grade)
            .join(tables.Subject, tables.Score.subject_id == tables.Subject.id)
            .join(tables.Class, tables.Score.class_id == tables.Class.id)
            .join(tables.Grade, tables.Class.grade_id == tables.Grade.id)
            .join(tables.Semester, tables.Score.semester_id == tables.Semester.id)
            .join(tables.AcademicYear, tables.Semester.academic_year_id == tables.AcademicYear.id)
            .where(
                tables.Grade.school_id == school_id,
                tables.Score.status == enums.ScoreStatus.APPROVED,
                tables.AcademicYear.name == year_str,
                tables.Semester.number == int(semester),
                tables.Grade.grade_number == int(grade_level),
                tables.Subject.name.ilike(f"%{subject.strip()}%"),
            )
        )
        scores = session.execute(stmt).all()
        if not scores:
            return (
                f"Không tìm thấy dữ liệu điểm cho môn '{subject}' khối {grade_level} năm {year_str} học kỳ {semester}."
            )

        class_student_data = {}
        for score, sub, cl, gr in scores:
            c_name = cl.name
            if c_name not in class_student_data:
                class_student_data[c_name] = {}
            s_key = score.student_id
            if s_key not in class_student_data[c_name]:
                class_student_data[c_name][s_key] = {
                    "TX1": None,
                    "TX2": None,
                    "TX3": None,
                    "TX4": None,
                    "GK": None,
                    "CK": None,
                }
            s_type = _score_type_str(score)
            if s_type in class_student_data[c_name][s_key]:
                class_student_data[c_name][s_key][s_type] = float(score.value)

        comparison = []
        for c_name, students in class_student_data.items():
            dtb_list = []
            for s_id, item in students.items():
                dtb = _get_subject_average(item)
                if dtb is not None:
                    dtb_list.append(dtb)

            if dtb_list:
                class_avg = round(sum(dtb_list) / len(dtb_list), 2)
                comparison.append({"Lớp": c_name, "Điểm trung bình lớp": class_avg, "Sĩ số môn học": len(dtb_list)})

        comparison.sort(key=lambda x: x["Điểm trung bình lớp"], reverse=True)
        return json.dumps(comparison, ensure_ascii=False, indent=2)


@tool
def get_student_academic_trend(student_id: str, subject: str = None) -> str:
    """Phân tích xu hướng học tập (tăng tiến, sa sút hay ổn định) của một học sinh qua các kỳ học.

    Args:
        student_id: Mã học sinh (10 chữ số, ví dụ: '2502151184').
        subject: Tên môn học cụ thể muốn theo dõi xu hướng. Nếu không điền sẽ tính trung bình tất cả các môn.

    Returns:
        Chuỗi JSON chứa lịch sử điểm số theo thứ tự thời gian và phân tích nhận xét xu hướng.
    """
    school_id = current_user_school_id.get()
    if not school_id:
        return "Lỗi: Không xác định được trường của người dùng."

    student_id = student_id.strip()
    with SessionLocal() as session:
        student = session.scalar(
            select(tables.Student).where(
                tables.Student.student_code == student_id, tables.Student.school_id == school_id
            )
        )
        if not student:
            return f"Không tìm thấy học sinh '{student_id}' trong hệ thống."

        stmt = (
            select(tables.Score, tables.Subject, tables.Semester, tables.AcademicYear, tables.Class)
            .join(tables.Subject, tables.Score.subject_id == tables.Subject.id)
            .join(tables.Semester, tables.Score.semester_id == tables.Semester.id)
            .join(tables.AcademicYear, tables.Semester.academic_year_id == tables.AcademicYear.id)
            .join(tables.Class, tables.Score.class_id == tables.Class.id)
            .where(tables.Score.student_id == student.id, tables.Score.status == enums.ScoreStatus.APPROVED)
        )
        if subject is not None:
            stmt = stmt.where(tables.Subject.name.ilike(f"%{subject.strip()}%"))

        scores = session.execute(stmt).all()
        if not scores:
            return f"Không tìm thấy dữ liệu điểm cho học sinh '{student_id}'."

        history_data = {}
        for score, sub, sem, ay, cl in scores:
            key = (ay.name, sem.number, cl.name)
            if key not in history_data:
                history_data[key] = {}
            sub_key = sub.name
            if sub_key not in history_data[key]:
                history_data[key][sub_key] = {
                    "TX1": None,
                    "TX2": None,
                    "TX3": None,
                    "TX4": None,
                    "GK": None,
                    "CK": None,
                }
            s_type = _score_type_str(score)
            if s_type in history_data[key][sub_key]:
                history_data[key][sub_key][s_type] = float(score.value)

        history = []
        for key, subjects in history_data.items():
            ay_name, sem_num, cl_name = key
            subject_avgs = []
            for sub_name, item in subjects.items():
                dtb = _get_subject_average(item)
                if dtb is not None:
                    subject_avgs.append(dtb)

            if subject_avgs:
                gpa = round(sum(subject_avgs) / len(subject_avgs), 2)
                history.append({"Năm học": ay_name, "Học kỳ": sem_num, "Lớp": cl_name, "GPA": gpa})

        history.sort(key=lambda x: (x["Năm học"], x["Học kỳ"]))

        if len(history) < 2:
            trend_label = "Chưa đủ dữ liệu để phân tích xu hướng (cần ít nhất 2 kỳ học)."
            diff = 0.0
        else:
            first_gpa = history[0]["GPA"]
            last_gpa = history[-1]["GPA"]
            diff = round(last_gpa - first_gpa, 2)

            if diff >= 1.0:
                trend_label = "Tăng tiến vượt bậc (Học lực cải thiện rõ rệt qua các năm)"
            elif diff >= 0.2:
                trend_label = "Có tiến bộ (Điểm số có chiều hướng tăng nhẹ)"
            elif diff <= -1.0:
                trend_label = "Sa sút nghiêm trọng (Học lực giảm mạnh qua các năm)"
            elif diff <= -0.2:
                trend_label = "Có chiều hướng đi xuống (Cần chú ý hỗ trợ thêm)"
            else:
                trend_label = "Ổn định (Điểm số duy trì đều đặn)"

        report = {
            "Mã học sinh": student_id,
            "Họ và Tên": student.full_name,
            "Môn học theo dõi": subject if subject else "Trung bình tất cả các môn",
            "Lịch sử học tập": history,
            "Xu hướng phân tích": {"Chênh lệch điểm số (Kỳ cuối - Kỳ đầu)": diff, "Nhận xét chung": trend_label},
        }
        return json.dumps(report, ensure_ascii=False, indent=2)


@tool
def get_academic_divergence_metrics(class_name: str, year: int, semester: int, subject: str) -> str:
    """Tính toán chỉ số Dị biệt Học thuật Tập thể (Delta G) của một lớp học cho một môn học cụ thể.
    Chỉ số này so sánh điểm trung bình môn học mục tiêu với điểm trung bình các môn khác (GPAO) của cùng học sinh.
    Delta G âm có nghĩa học sinh học môn này kém hơn năng lực chung ở các môn khác (giáo viên chấm khó hoặc đề quá khó).
    Delta G dương có nghĩa học sinh học môn này tốt nổi trội so với năng lực chung.

    Args:
        class_name: Tên lớp học (ví dụ: '6A1', '10A2').
        year: Năm học bắt đầu (ví dụ: 2023).
        semester: Học kỳ (1 hoặc 2).
        subject: Tên môn học mục tiêu (ví dụ: 'Toán học', 'Vật lý').
    """
    school_id = current_user_school_id.get()
    if not school_id:
        return "Lỗi: Không xác định được trường của người dùng."

    class_name = class_name.strip().upper()
    year_str = f"{year}-{year + 1}" if isinstance(year, int) else str(year)

    with SessionLocal() as session:
        # Resolve class
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
            return f"Không tìm thấy lớp '{class_name}'."

        sem = session.scalar(
            select(tables.Semester).where(
                tables.Semester.academic_year_id == clazz.academic_year_id, tables.Semester.number == int(semester)
            )
        )
        if not sem:
            return "Học kỳ không hợp lệ."

        # Fetch all approved scores for students in this class
        stmt = (
            select(tables.Score, tables.Subject)
            .join(tables.Subject, tables.Score.subject_id == tables.Subject.id)
            .where(
                tables.Score.class_id == clazz.id,
                tables.Score.semester_id == sem.id,
                tables.Score.status == enums.ScoreStatus.APPROVED,
            )
        )
        scores = session.execute(stmt).all()
        if not scores:
            return "Không có dữ liệu điểm."

        # Group by student_id -> subject_name -> components dict
        student_subj_scores = {}
        for score, sub in scores:
            s_id = score.student_id
            if s_id not in student_subj_scores:
                student_subj_scores[s_id] = {}
            sub_name = sub.name
            if sub_name not in student_subj_scores[s_id]:
                student_subj_scores[s_id][sub_name] = {
                    "TX1": None,
                    "TX2": None,
                    "TX3": None,
                    "TX4": None,
                    "GK": None,
                    "CK": None,
                }
            s_type = _score_type_str(score)
            if s_type in student_subj_scores[s_id][sub_name]:
                student_subj_scores[s_id][sub_name][s_type] = float(score.value)

        # For each student, compute averages for each subject
        target_subject_clean = subject.strip().lower()
        delta_g_list = []

        for s_id, subjects_dict in student_subj_scores.items():
            # Calc average for each subject
            subject_avgs = {}
            for sub_name, item in subjects_dict.items():
                avg = _get_subject_average(item)
                if avg is not None:
                    subject_avgs[sub_name] = avg

            # Find target subject average
            target_avg = None
            other_avgs = []
            for sub_name, avg in subject_avgs.items():
                if sub_name.lower() == target_subject_clean:
                    target_avg = avg
                else:
                    other_avgs.append(avg)

            if target_avg is not None and other_avgs:
                gpao = sum(other_avgs) / len(other_avgs)
                delta_g = target_avg - gpao
                delta_g_list.append(delta_g)

        if not delta_g_list:
            return f"Không đủ dữ liệu điểm để so sánh Dị biệt học thuật Delta G môn '{subject}' cho lớp '{class_name}'."

        avg_delta_g = round(sum(delta_g_list) / len(delta_g_list), 2)

        # Interpret
        if avg_delta_g <= -1.0:
            analysis = "Dị biệt âm lớn. Lớp có điểm môn này thấp hơn hẳn mặt bằng chung các môn khác. Khả năng cao do giáo viên chấm quá khắt khe hoặc đề thi quá khó."
        elif avg_delta_g <= -0.3:
            analysis = "Dị biệt âm nhẹ. Kết quả môn này hơi tụt so với năng lực trung bình."
        elif avg_delta_g >= 1.0:
            analysis = (
                "Dị biệt dương lớn. Học sinh lớp này học môn này nổi trội hoặc tiêu chuẩn chấm điểm lớp học nới lỏng."
            )
        else:
            analysis = "Dị biệt không đáng kể. Điểm môn học này tương đồng với năng lực học tập các môn khác của lớp."

        result = {
            "Lớp": class_name,
            "Môn học": subject,
            "Số học sinh tham gia phân tích": len(delta_g_list),
            "Chỉ số Dị biệt Tập thể (Delta G_Class)": avg_delta_g,
            "Phân tích chuyên môn": analysis,
        }
        return json.dumps(result, ensure_ascii=False, indent=2)


@tool
def get_grade_inflation_report(year: int, semester: int, grade_level: int, subject: str) -> str:
    """Báo cáo chỉ số Lệch pha tiêu chuẩn & Lạm phát điểm (GDI) của tất cả các lớp trong một khối học.
    So sánh điểm đánh giá thường xuyên (TX_mean) và điểm thi cuối kỳ (CK) sau khi chuẩn hóa Z-score theo khối.
    GDI lớp lớn hơn +1.0 cho thấy hiện tượng lỏng tay khi chấm điểm thường xuyên so với thi cuối kỳ tập trung.

    Args:
        year: Năm học bắt đầu (ví dụ: 2023).
        semester: Học kỳ (1 hoặc 2).
        grade_level: Khối học (6, 7, 8, 9, 10, 11, 12).
        subject: Tên môn học (ví dụ: 'Toán học').
    """
    school_id = current_user_school_id.get()
    if not school_id:
        return "Lỗi: Không xác định được trường của người dùng."

    year_str = f"{year}-{year + 1}" if isinstance(year, int) else str(year)

    with SessionLocal() as session:
        # Get all scores for this grade, semester, year, subject
        stmt = (
            select(tables.Score, tables.Student, tables.Class)
            .join(tables.Student, tables.Score.student_id == tables.Student.id)
            .join(tables.Class, tables.Score.class_id == tables.Class.id)
            .join(tables.Grade, tables.Class.grade_id == tables.Grade.id)
            .join(tables.Subject, tables.Score.subject_id == tables.Subject.id)
            .join(tables.Semester, tables.Score.semester_id == tables.Semester.id)
            .join(tables.AcademicYear, tables.Semester.academic_year_id == tables.AcademicYear.id)
            .where(
                tables.Grade.school_id == school_id,
                tables.Grade.grade_number == int(grade_level),
                tables.AcademicYear.name == year_str,
                tables.Semester.number == int(semester),
                tables.Subject.name.ilike(f"%{subject.strip()}%"),
                tables.Score.status == enums.ScoreStatus.APPROVED,
            )
        )
        scores = session.execute(stmt).all()
        if not scores:
            return "Không tìm thấy dữ liệu phù hợp."

        # Group by student -> class_name -> components
        # student_id -> (class_name) -> TX1-4 and CK
        students_grades = {}
        for score, student, cl in scores:
            s_key = student.id
            if s_key not in students_grades:
                students_grades[s_key] = {
                    "class": cl.name,
                    "TX1": None,
                    "TX2": None,
                    "TX3": None,
                    "TX4": None,
                    "CK": None,
                }
            s_type = _score_type_str(score)
            if s_type in students_grades[s_key]:
                students_grades[s_key][s_type] = float(score.value)

        # Calculate TX_mean and CK for each student
        tx_list = []
        ck_list = []
        processed_students = []
        for s_id, item in students_grades.items():
            tx_vals = [item[t] for t in ["TX1", "TX2", "TX3", "TX4"] if item[t] is not None]
            ck_val = item["CK"]
            if tx_vals and ck_val is not None:
                tx_mean = sum(tx_vals) / len(tx_vals)
                tx_list.append(tx_mean)
                ck_list.append(ck_val)
                processed_students.append({"id": s_id, "class": item["class"], "tx_mean": tx_mean, "ck": ck_val})

        if len(processed_students) < 5:
            return "Không đủ số lượng học sinh trong khối để tính toán Z-score (tối thiểu cần 5 học sinh)."

        # Grade-level statistics
        avg_tx = sum(tx_list) / len(tx_list)
        avg_ck = sum(ck_list) / len(ck_list)

        def stddev(lst, avg):
            variance = sum((x - avg) ** 2 for x in lst) / max(len(lst) - 1, 1)
            return variance**0.5

        std_tx = stddev(tx_list, avg_tx)
        std_ck = stddev(ck_list, avg_ck)

        if std_tx == 0:
            std_tx = 1.0
        if std_ck == 0:
            std_ck = 1.0

        # Calculate GDI for each student and average by class
        class_gdi = {}
        for s in processed_students:
            z_tx = (s["tx_mean"] - avg_tx) / std_tx
            z_ck = (s["ck"] - avg_ck) / std_ck
            gdi = z_tx - z_ck

            c_name = s["class"]
            if c_name not in class_gdi:
                class_gdi[c_name] = []
            class_gdi[c_name].append(gdi)

        report = []
        for c_name, gdi_vals in class_gdi.items():
            gdi_avg = round(sum(gdi_vals) / len(gdi_vals), 2)

            if gdi_avg >= 1.0:
                comment = "Lệch pha dương lớn. Lớp có hiện tượng lạm phát điểm số thường xuyên (chấm lỏng tay) so với điểm thi tập trung."
            elif gdi_avg <= -1.0:
                comment = "Lệch pha âm lớn. Tiêu chuẩn chấm thường xuyên nghiêm ngặt hơn hoặc đề thi cuối kỳ quá dễ."
            else:
                comment = "Chỉ số ổn định. Đánh giá thường xuyên phản ánh đúng kết quả thi tập trung."

            report.append({"Lớp": c_name, "Chỉ số lạm phát điểm (GDI_Class)": gdi_avg, "Nhận xét": comment})

        report.sort(key=lambda x: x["Chỉ số lạm phát điểm (GDI_Class)"], reverse=True)
        return json.dumps(report, ensure_ascii=False, indent=2)


@tool
def get_evaluation_momentum(class_name: str, year: int, semester: int, subject: str) -> str:
    """Tính toán chỉ số Động lượng học tập (Momentum Index) của học sinh trong một lớp học sau kỳ thi giữa kỳ.
    Đo lường mức độ tiến bộ ở giai đoạn sau giữa kỳ (TX3, TX4) so với trước giữa kỳ (TX1, TX2), chuẩn hóa theo điểm giữa kỳ (GK).
    Học sinh có động lượng dương cao thể hiện nỗ lực tự điều chỉnh tốt sau kỳ thi giữa kỳ.

    Args:
        class_name: Tên lớp học (ví dụ: '6A1', '10A2').
        year: Năm học bắt đầu (ví dụ: 2023).
        semester: Học kỳ (1 hoặc 2).
        subject: Tên môn học (ví dụ: 'Toán học').
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
            return f"Không tìm thấy lớp '{class_name}'."

        sem = session.scalar(
            select(tables.Semester).where(
                tables.Semester.academic_year_id == clazz.academic_year_id, tables.Semester.number == int(semester)
            )
        )
        if not sem:
            return "Học kỳ không hợp lệ."

        stmt = (
            select(tables.Score, tables.Student)
            .join(tables.Student, tables.Score.student_id == tables.Student.id)
            .join(tables.Subject, tables.Score.subject_id == tables.Subject.id)
            .where(
                tables.Score.class_id == clazz.id,
                tables.Score.semester_id == sem.id,
                tables.Subject.name.ilike(f"%{subject.strip()}%"),
                tables.Score.status == enums.ScoreStatus.APPROVED,
            )
        )
        scores = session.execute(stmt).all()
        if not scores:
            return "Không tìm thấy dữ liệu điểm."

        # Group by student -> components
        students_data = {}
        student_names = {}
        for score, student in scores:
            student_names[student.id] = student.full_name
            s_id = student.id
            if s_id not in students_data:
                students_data[s_id] = {"TX1": None, "TX2": None, "TX3": None, "TX4": None, "GK": None}
            s_type = _score_type_str(score)
            if s_type in students_data[s_id]:
                students_data[s_id][s_type] = float(score.value)

        results = []
        for s_id, item in students_data.items():
            tx_early = [item[t] for t in ["TX1", "TX2"] if item[t] is not None]
            tx_late = [item[t] for t in ["TX3", "TX4"] if item[t] is not None]
            gk = item["GK"]

            if tx_early and tx_late and gk is not None and gk > 0:
                mean_early = sum(tx_early) / len(tx_early)
                mean_late = sum(tx_late) / len(tx_late)
                # Momentum = (mean_late - mean_early) / gk
                momentum = round((mean_late - mean_early) / gk, 3)
                results.append(
                    {
                        "Học sinh": student_names[s_id],
                        "Điểm trước GK (TX1-2)": round(mean_early, 2),
                        "Điểm giữa kỳ (GK)": gk,
                        "Điểm sau GK (TX3-4)": round(mean_late, 2),
                        "Động lượng học tập (M)": momentum,
                    }
                )

        if not results:
            return "Không đủ dữ liệu điểm để tính toán động lượng."

        # Sort by momentum to see who improved the most or got discouraged
        results.sort(key=lambda x: x["Động lượng học tập (M)"], reverse=True)

        top_improvers = results[:3]
        most_declined = results[-3:]
        most_declined.reverse()

        summary = {
            "Lớp": class_name,
            "Môn học": subject,
            "Học sinh tiến bộ nhiều nhất (Động lượng dương cao nhất)": top_improvers,
            "Học sinh sa sút sau giữa kỳ (Động lượng âm thấp nhất)": most_declined,
        }
        return json.dumps(summary, ensure_ascii=False, indent=2)
