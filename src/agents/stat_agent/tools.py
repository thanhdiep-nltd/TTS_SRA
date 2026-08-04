import json
from types import SimpleNamespace
from uuid import UUID

from langchain_core.tools import tool
from sqlalchemy import select

from src.agents.context import current_user_id, current_user_role, current_user_school_id
from src.agents.helpers import _score_type_str, subject_average_and_rank
from src.db.session import SessionLocal
from src.models import enums, tables
from src.schemas.exam_generation import RecommendBlueprintRequest
from src.services import blueprint_recommendation, exam_validity, rbac
from src.services.rbac import accessible_score_filter


def _rbac_denied_or(empty_message: str, session, user_role, user_id, school_id) -> str:
    """Khi RBAC active (user không PRINCIPAL/ADMIN) và kết quả rỗng → trả ACCESS_DENIED kèm phạm vi quyền;
    ngược lại (full access) → trả về empty_message như cũ."""
    if user_role not in ("PRINCIPAL", "ADMIN") and user_id:
        user = SimpleNamespace(id=user_id, school_id=school_id, role=user_role)
        scope = rbac.scope_summary_for_user(session, user)
        return rbac.rbac_denied_message(scope)
    return empty_message


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

        user_role = current_user_role.get()
        user_id = current_user_id.get()
        if user_role not in ("PRINCIPAL", "ADMIN") and user_id:
            user = SimpleNamespace(id=user_id, school_id=school_id, role=user_role)
            rbac_filter = accessible_score_filter(session, user)
            stmt = stmt.where(rbac_filter)
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

        try:
            scores = session.execute(stmt).all()
        except Exception as exc:
            # OLTP (bảng scores/classes/grades) có thể không được cung cấp trong môi trường
            # DWH-only -> trả thông báo rõ ràng thay vì exception tràn ra ngoài khiến agent
            # hiểu nhầm thành "từ chối phân quyền".
            if "does not exist" in str(exc) or "undefined_table" in str(exc):
                return (
                    "Hệ thống chưa cấu hình dữ liệu bảng điểm vận hành (OLTP scores) nên chưa "
                    "tính được thống kê. Vui lòng dùng công cụ tra cứu điểm của Data Service "
                    "(get_class_grades / get_student_grades) để xem điểm chi tiết trong phạm vi phân quyền."
                )
            raise
        if not scores:
            return _rbac_denied_or(
                "Không tìm thấy dữ liệu phù hợp để tính toán thống kê.",
                session,
                user_role,
                user_id,
                school_id,
            )

        grouped: dict[tuple, list] = {}
        for score, sub, cl, gr in scores:
            s_key = (score.student_id, sub.name)
            grouped.setdefault(s_key, []).append(score)

        dtb_scores = []
        ranks = {"Giỏi": 0, "Khá": 0, "Trung bình": 0, "Yếu": 0, "Kém": 0}
        for item in grouped.values():
            dtb, rank = subject_average_and_rank(item)
            if dtb is not None:
                dtb_scores.append(dtb)
                ranks[rank] += 1

        if not dtb_scores:
            return "Không tìm thấy đủ dữ liệu điểm để tính điểm trung bình học kỳ."

        total_count = len(dtb_scores)
        avg_score = round(sum(dtb_scores) / total_count, 2)
        max_score = max(dtb_scores)
        min_score = min(dtb_scores)

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

        user_role = current_user_role.get()
        user_id = current_user_id.get()
        if user_role not in ("PRINCIPAL", "ADMIN") and user_id:
            user = SimpleNamespace(id=user_id, school_id=school_id, role=user_role)
            rbac_filter = accessible_score_filter(session, user)
            stmt = stmt.where(rbac_filter)
        if class_name is not None:
            stmt = stmt.where(tables.Class.name == class_name.strip().upper())
        if grade_level is not None:
            stmt = stmt.where(tables.Grade.grade_number == int(grade_level))
        if subject is not None:
            stmt = stmt.where(tables.Subject.name.ilike(f"%{subject.strip()}%"))

        scores = session.execute(stmt).all()
        if not scores:
            return _rbac_denied_or(
                "Không tìm thấy dữ liệu điểm phù hợp.",
                session,
                user_role,
                user_id,
                school_id,
            )

        student_data: dict = {}
        for score, student, sub, cl, gr in scores:
            s_key = (student.student_code, student.full_name, cl.name)
            student_data.setdefault(s_key, {}).setdefault(sub.name, []).append(score)

        leaderboard = []
        for s_key, subjects in student_data.items():
            code, name, cl_name = s_key
            subject_avgs = []
            for item in subjects.values():
                dtb, _rank = subject_average_and_rank(item)
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

        user_role = current_user_role.get()
        user_id = current_user_id.get()
        if user_role not in ("PRINCIPAL", "ADMIN") and user_id:
            user = SimpleNamespace(id=user_id, school_id=school_id, role=user_role)
            rbac_filter = accessible_score_filter(session, user)
            stmt = stmt.where(rbac_filter)
        if class_name is not None:
            stmt = stmt.where(tables.Class.name == class_name.strip().upper())
        if grade_level is not None:
            stmt = stmt.where(tables.Grade.grade_number == int(grade_level))
        if subject is not None:
            stmt = stmt.where(tables.Subject.name.ilike(f"%{subject.strip()}%"))

        scores = session.execute(stmt).all()
        if not scores:
            return _rbac_denied_or(
                "Không tìm thấy dữ liệu điểm phù hợp.",
                session,
                user_role,
                user_id,
                school_id,
            )

        student_data: dict = {}
        for score, student, sub, cl, gr in scores:
            s_key = (student.student_code, student.full_name, cl.name)
            student_data.setdefault(s_key, {}).setdefault(sub.name, []).append(score)

        leaderboard = []
        for s_key, subjects in student_data.items():
            code, name, cl_name = s_key
            subject_avgs = []
            for item in subjects.values():
                dtb, _rank = subject_average_and_rank(item)
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

        user_role = current_user_role.get()
        user_id = current_user_id.get()
        if user_role not in ("PRINCIPAL", "ADMIN") and user_id:
            user = SimpleNamespace(id=user_id, school_id=school_id, role=user_role)
            rbac_filter = accessible_score_filter(session, user)
            stmt = stmt.where(rbac_filter)
        scores = session.execute(stmt).all()
        if not scores:
            return _rbac_denied_or(
                f"Không tìm thấy dữ liệu điểm cho môn '{subject}' khối {grade_level} năm {year_str} học kỳ {semester}.",
                session,
                user_role,
                user_id,
                school_id,
            )

        class_student_data: dict = {}
        for score, sub, cl, gr in scores:
            class_student_data.setdefault(cl.name, {}).setdefault(score.student_id, []).append(score)

        comparison = []
        for c_name, students in class_student_data.items():
            dtb_list = []
            for item in students.values():
                dtb, _rank = subject_average_and_rank(item)
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
            return _rbac_denied_or(
                f"Không tìm thấy dữ liệu điểm cho học sinh '{student_id}'.",
                session,
                user_role,
                user_id,
                school_id,
            )

        history_data: dict = {}
        for score, sub, sem, ay, cl in scores:
            key = (ay.name, sem.number, cl.name)
            history_data.setdefault(key, {}).setdefault(sub.name, []).append(score)

        history = []
        for key, subjects in history_data.items():
            ay_name, sem_num, cl_name = key
            subject_avgs = []
            for item in subjects.values():
                dtb, _rank = subject_average_and_rank(item)
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

        user_role = current_user_role.get()
        user_id = current_user_id.get()
        if user_role not in ("PRINCIPAL", "ADMIN") and user_id:
            # Kiểm tra xem GV có được phân công tại lớp này không (HOMEROOM, SUBJECT_TEACHER hoặc GRADE_HEAD)
            has_access = False
            ta_stmt = select(tables.TeacherAssignment).where(
                tables.TeacherAssignment.user_id == user_id, tables.TeacherAssignment.is_active.is_(True)
            )
            assignments = session.scalars(ta_stmt).all()
            for ta in assignments:
                if ta.role_context == enums.RoleContext.GRADE_HEAD and ta.grade_id == clazz.grade_id:
                    has_access = True
                    break
                elif ta.class_id == clazz.id:
                    has_access = True
                    break
            if not has_access:
                user = SimpleNamespace(id=user_id, school_id=school_id, role=user_role)
                return rbac.rbac_denied_message(rbac.scope_summary_for_user(session, user))

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
            return _rbac_denied_or(
                "Không có dữ liệu điểm.",
                session,
                user_role,
                user_id,
                school_id,
            )

        # Group by student_id -> subject_name -> danh sách Score
        student_subj_scores: dict = {}
        for score, sub in scores:
            student_subj_scores.setdefault(score.student_id, {}).setdefault(sub.name, []).append(score)

        # For each student, compute averages for each subject
        target_subject_clean = subject.strip().lower()
        delta_g_list = []

        for s_id, subjects_dict in student_subj_scores.items():
            # Calc average for each subject
            subject_avgs = {}
            for sub_name, item in subjects_dict.items():
                avg, _rank = subject_average_and_rank(item)
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
    user_role = current_user_role.get()
    if not school_id:
        return "Lỗi: Không xác định được trường của người dùng."

    if user_role not in ("PRINCIPAL", "ADMIN"):
        return rbac.rbac_denied_message("báo cáo Lạm phát điểm GDI (chỉ dành cho Ban Giám Hiệu)")

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
                comment = (
                    "Lệch pha dương lớn. Lớp có hiện tượng lạm phát điểm số thường xuyên (chấm lỏng tay) "
                    "so với điểm thi tập trung."
                )
            elif gdi_avg <= -1.0:
                comment = "Lệch pha âm lớn. Tiêu chuẩn chấm thường xuyên nghiêm ngặt hơn hoặc đề thi cuối kỳ quá dễ."
            else:
                comment = "Chỉ số ổn định. Đánh giá thường xuyên phản ánh đúng kết quả thi tập trung."

            report.append(
                {
                    "Lớp": c_name,
                    "Chỉ số lạm phát điểm (GDI_Class)": gdi_avg,
                    "Nhận xét": comment,
                }
            )

        report.sort(key=lambda x: x["Chỉ số lạm phát điểm (GDI_Class)"], reverse=True)
        return json.dumps(report, ensure_ascii=False, indent=2)


@tool
def get_evaluation_momentum(class_name: str, year: int, semester: int, subject: str) -> str:
    """Tính toán chỉ số Động lượng học tập (Momentum Index) của học sinh trong một lớp học sau kỳ thi giữa kỳ.

    Đo lường mức độ tiến bộ ở giai đoạn sau giữa kỳ (TX3, TX4) so với trước giữa kỳ (TX1, TX2),
    chuẩn hóa theo điểm giữa kỳ (GK).
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

        user_role = current_user_role.get()
        user_id = current_user_id.get()
        if user_role not in ("PRINCIPAL", "ADMIN") and user_id:
            # Kiểm tra xem GV có được phân công tại lớp này không
            has_access = False
            ta_stmt = select(tables.TeacherAssignment).where(
                tables.TeacherAssignment.user_id == user_id, tables.TeacherAssignment.is_active.is_(True)
            )
            assignments = session.scalars(ta_stmt).all()
            for ta in assignments:
                if ta.role_context == enums.RoleContext.GRADE_HEAD and ta.grade_id == clazz.grade_id:
                    has_access = True
                    break
                elif ta.class_id == clazz.id:
                    has_access = True
                    break
            if not has_access:
                user = SimpleNamespace(id=user_id, school_id=school_id, role=user_role)
                return rbac.rbac_denied_message(rbac.scope_summary_for_user(session, user))

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
            return _rbac_denied_or(
                "Không tìm thấy dữ liệu điểm.",
                session,
                user_role,
                user_id,
                school_id,
            )

        # Group by student -> components
        students_data = {}
        student_names = {}
        for score, student in scores:
            student_names[student.id] = student.full_name
            s_id = student.id
            if s_id not in students_data:
                students_data[s_id] = {
                    "TX1": None,
                    "TX2": None,
                    "TX3": None,
                    "TX4": None,
                    "GK": None,
                }
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


@tool
def get_exam_validity_report(subject: str, grade_level: int, year: int, semester: int) -> str:
    """Đối chiếu độ khó NỘI DUNG đề (Bloom/chuẩn CT) vs độ khó THỰC NGHIỆM (điểm) để
    đánh giá điểm có phản ánh đúng thực lực + phát hiện bất thường (lạm phát điểm, nghi
    lộ đề, lỗ hổng dạy-học). Dùng cho câu hỏi về tính TIN CẬY của điểm, độ khó đề thi,
    hoặc nghi vấn bê bối điểm số. Chỉ áp dụng cho đề Giữa kỳ/Cuối kỳ (GK/CK).

    Args:
        subject: Tên môn học (ví dụ: 'Toán học').
        grade_level: Khối học (6, 7, 8, 9, 10, 11, 12).
        year: Năm học bắt đầu (ví dụ: 2023).
        semester: Học kỳ (1 hoặc 2).
    """
    school_id = current_user_school_id.get()
    user_role = current_user_role.get()
    if not school_id:
        return "Lỗi: Không xác định được trường của người dùng."

    if user_role not in ("PRINCIPAL", "ADMIN"):
        return rbac.rbac_denied_message("báo cáo Độ tin cậy đề thi (chỉ dành cho Ban Giám Hiệu)")

    # Phân giải năm học linh hoạt (hỗ trợ cả int ví dụ: 2025, hoặc str ví dụ: "2025", "2025-2026")
    if isinstance(year, int):
        year_str = f"{year}-{year + 1}"
    else:
        year_val = str(year).strip()
        if len(year_val) == 4 and year_val.isdigit():
            y_int = int(year_val)
            year_str = f"{y_int}-{y_int + 1}"
        else:
            year_str = year_val

    with SessionLocal() as session:
        subj = session.scalar(
            select(tables.Subject).where(
                tables.Subject.school_id == school_id,
                tables.Subject.name.ilike(f"%{subject.strip()}%"),
            )
        )
        if not subj:
            return f"Không tìm thấy môn học '{subject}'."

        grade = session.scalar(
            select(tables.Grade).where(
                tables.Grade.school_id == school_id, tables.Grade.grade_number == int(grade_level)
            )
        )
        if not grade:
            return f"Không tìm thấy khối '{grade_level}'."

        sem = session.scalar(
            select(tables.Semester)
            .join(tables.AcademicYear, tables.Semester.academic_year_id == tables.AcademicYear.id)
            .where(
                tables.AcademicYear.school_id == school_id,
                tables.AcademicYear.name == year_str,
                tables.Semester.number == int(semester),
            )
        )
        if not sem:
            return "Học kỳ không hợp lệ."

        report = {}
        for cat in (enums.ScoreCategory.MIDTERM, enums.ScoreCategory.FINAL):
            rows = exam_validity.compute_validity(
                db=session,
                school_id=school_id,
                semester_id=sem.id,
                subject_id=subj.id,
                score_category=cat,
                grade_id=grade.id,
            )
            if rows:
                report[cat.value] = [row.model_dump(mode="json") for row in rows]

        if not report:
            return (
                "Không tìm thấy dữ liệu tam giác hóa (cần có đề đã map vào cột điểm GK/CK "
                "và đã nhập exam_competencies để có CDI)."
            )
        return json.dumps(report, ensure_ascii=False, indent=2)


_SCORE_CATEGORY_BY_LABEL = {"giữa kỳ": enums.ScoreCategory.MIDTERM, "cuối kỳ": enums.ScoreCategory.FINAL}
_EXAM_FORMAT_BY_LABEL = {
    "trắc nghiệm": enums.ExamFormat.MCQ_ONLY,
    "tự luận": enums.ExamFormat.ESSAY_ONLY,
    "kết hợp": enums.ExamFormat.MIXED,
    "mix": enums.ExamFormat.MIXED,
}


def _match_units(units: list, focus_units: list[str]) -> tuple[list, list[str]]:
    """Khớp tên chương LLM đưa vào (có thể không chính xác 100%) với curriculum_units thật
    bằng substring không phân biệt hoa/thường — trả (đơn vị khớp được, tên không khớp)."""
    matched, not_found = [], []
    for name in focus_units:
        unit = next((u for u in units if name.strip().lower() in u.name.lower()), None)
        (matched if unit else not_found).append(unit if unit else name)
    return matched, not_found


@tool
def draft_exam_blueprint(
    subject: str,
    grade_level: int,
    year: int,
    semester: int,
    score_category: str,
    focus_units: list[str],
    total_questions: int = 20,
    exam_format: str = "kết hợp",
    total_points: float = 10.0,
) -> str:
    """Gợi ý MA TRẬN đề kiểm tra Giữa kỳ/Cuối kỳ dựa trên năng lực thực tế của khối (TEVI),
    lỗi sai học sinh hay gặp, và kho câu hỏi hiện có — CHỈ đề xuất cấu hình (số câu, mức độ,
    điểm mỗi chương), TUYỆT ĐỐI KHÔNG tự sinh hay hiển thị câu hỏi thật, không lưu gì vào hệ
    thống. Người ra đề vẫn phải vào trang "Tạo đề thi" để xem/chỉnh và tự lưu ma trận.

    Args:
        subject: Tên môn học (ví dụ: 'Toán học').
        grade_level: Khối học (6, 7, 8, 9, 10, 11, 12).
        year: Năm học bắt đầu (ví dụ: 2023).
        semester: Học kỳ (1 hoặc 2).
        score_category: Loại đề — 'Giữa kỳ' hoặc 'Cuối kỳ' (chỉ hỗ trợ đề chính thức).
        focus_units: Danh sách tên chương/chủ đề đã dạy (ví dụ: ['Phân thức đại số', 'Hàm số']).
        total_questions: Tổng số câu của đề (mặc định 20).
        exam_format: Loại đề — 'trắc nghiệm' (100% TN), 'tự luận' (100% TL), hoặc 'kết hợp'
            (mix, mặc định 70% điểm TN / 30% điểm TL).
        total_points: Tổng điểm đề (mặc định 10).
    """
    raw_school_id, raw_user_id = current_user_school_id.get(), current_user_id.get()
    if not raw_school_id or not raw_user_id:
        return "Lỗi: Không xác định được người dùng/trường."
    # ContextVar được set từ school_context (state LangGraph) dưới dạng STR (str(user.school_id)
    # ở chat.py), không phải UUID như type hint khai báo -> chuẩn hóa để so sánh Python-level
    # (vd _validate_grade_in_school) không lệch kiểu str/UUID.
    school_id, user_id = UUID(str(raw_school_id)), UUID(str(raw_user_id))

    cat = _SCORE_CATEGORY_BY_LABEL.get(score_category.strip().lower())
    if cat is None:
        return "Lỗi: score_category phải là 'Giữa kỳ' hoặc 'Cuối kỳ'."

    fmt = _EXAM_FORMAT_BY_LABEL.get(exam_format.strip().lower())
    if fmt is None:
        return "Lỗi: exam_format phải là 'trắc nghiệm', 'tự luận', hoặc 'kết hợp'."

    year_str = f"{year}-{year + 1}" if isinstance(year, int) else str(year)

    with SessionLocal() as session:
        user = session.get(tables.User, user_id)
        subj = session.scalar(
            select(tables.Subject).where(
                tables.Subject.school_id == school_id, tables.Subject.name.ilike(f"%{subject.strip()}%")
            )
        )
        if user is None or not subj:
            return f"Không tìm thấy môn học '{subject}' hoặc người dùng."
        if not rbac.can_manage_question_bank(session, user, subj.id):
            return "Lỗi bảo mật: Bạn không phụ trách môn này nên không thể gợi ý ma trận đề."

        grade = session.scalar(
            select(tables.Grade).where(
                tables.Grade.school_id == school_id, tables.Grade.grade_number == int(grade_level)
            )
        )
        if not grade:
            return f"Không tìm thấy khối '{grade_level}'."

        sem = session.scalar(
            select(tables.Semester)
            .join(tables.AcademicYear, tables.Semester.academic_year_id == tables.AcademicYear.id)
            .where(
                tables.AcademicYear.school_id == school_id,
                tables.AcademicYear.name == year_str,
                tables.Semester.number == int(semester),
            )
        )
        if not sem:
            return "Học kỳ không hợp lệ."

        units = list(
            session.scalars(
                select(tables.CurriculumUnit).where(
                    tables.CurriculumUnit.subject_id == subj.id,
                    tables.CurriculumUnit.grade_number == int(grade_level),
                )
            ).all()
        )
        matched, not_found = _match_units(units, focus_units)
        if not matched:
            return (
                f"Không khớp được chương nào trong danh sách chương trình ({[u.name for u in units]}) — "
                "kiểm tra lại tên chương, hoặc môn/khối này chưa có chuẩn chương trình trong hệ thống."
            )

        req = RecommendBlueprintRequest(
            subject_id=subj.id,
            grade_number=int(grade_level),
            grade_id=grade.id,
            semester_id=sem.id,
            score_category=cat,
            unit_ids=[u.id for u in matched],
            total_points=float(total_points),
            exam_format=fmt,
            total_questions=int(total_questions),
        )
        try:
            draft = blueprint_recommendation.recommend(session, school_id, req)
        except blueprint_recommendation.RecommendationInputError as exc:
            return f"Không gợi ý được: {exc}"

        result = draft.model_dump(mode="json")
        if not_found:
            result["chuong_khong_khop"] = not_found
        result["luu_y"] = (
            "Đây CHỈ là gợi ý ma trận — vào trang 'Tạo đề thi' trong hệ thống để xem/chỉnh và tự "
            "lưu; hệ thống KHÔNG tự tạo đề thi thật từ đây."
        )
        return json.dumps(result, ensure_ascii=False, indent=2)
