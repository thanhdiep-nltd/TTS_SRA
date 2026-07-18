import os
import re
import uuid
from typing import Literal

import docx
from docx.oxml import parse_xml
from docx.oxml.ns import nsdecls
from docx.shared import Cm, Pt, RGBColor
from langchain_core.tools import tool
from sqlalchemy import and_, func, select

from src.agents.context import current_user_school_id
from src.api.v1.analytics import _at_risk_classes, _average_gpa
from src.db.session import SessionLocal
from src.models.tables import (
    Class,
    Enrollment,
    Grade,
    School,
    Score,
    Semester,
    Student,
    StudentTermReport,
    Subject,
    TeacherAssignment,
)
from src.schemas.analytics import ReportExportRequest

# We can import the actual export logic or recreate a lightweight version of it.
# To ensure perfect consistency, we will read from reports.py or call it.
# However, to avoid circular imports, we can implement a clean report compiler helper here.


def is_valid_uuid(val) -> bool:
    if not val:
        return False
    try:
        uuid.UUID(str(val))
        return True
    except (ValueError, TypeError):
        return False


def resolve_uuid_parameters(db, school_id, class_id_str, semester_id_str, subject_id_str=None):
    import re

    from src.models.tables import AcademicYear as DBAcademicYear

    resolved_class_id = None
    resolved_semester_id = None
    resolved_subject_id = None

    # 1. Nếu semester_id_str là UUID hợp lệ, truy vấn trực tiếp bảng Semester
    ay = None
    if semester_id_str and is_valid_uuid(semester_id_str):
        sem_row = (
            db.execute(
                select(Semester)
                .join(DBAcademicYear, Semester.academic_year_id == DBAcademicYear.id)
                .where(DBAcademicYear.school_id == school_id, Semester.id == uuid.UUID(str(semester_id_str)))
            )
            .scalars()
            .first()
        )
        if sem_row:
            resolved_semester_id = str(sem_row.id)
            # Lấy Academic Year trực tiếp thuộc về Semester này
            ay = db.get(DBAcademicYear, sem_row.academic_year_id)

    # 2. Nếu semester_id_str là Văn bản (Tên học kỳ)
    elif semester_id_str:
        # A. Cố gắng tìm niên khóa thông qua Regex (hỗ trợ cả dạng khoảng và năm đơn lẻ)
        year_match_range = re.search(r"(\d{4}-\d{4})", str(semester_id_str))
        year_match_single = re.search(r"\b(\d{4})\b", str(semester_id_str))

        if year_match_range:
            year_name = year_match_range.group(1)
            ay = (
                db.execute(
                    select(DBAcademicYear).where(
                        DBAcademicYear.school_id == school_id, DBAcademicYear.name == year_name
                    )
                )
                .scalars()
                .first()
            )
        elif year_match_single:
            # Nếu chỉ nói năm đơn lẻ, ví dụ: 2025 -> tìm niên khóa chứa chuỗi '2025' (ví dụ: 2025-2026)
            year_val = year_match_single.group(1)
            ay = (
                db.execute(
                    select(DBAcademicYear).where(
                        DBAcademicYear.school_id == school_id, DBAcademicYear.name.like(f"%{year_val}%")
                    )
                )
                .scalars()
                .first()
            )

        # B. Xác định số học kỳ từ chuỗi
        sem_num = None
        sem_str_clean = str(semester_id_str).lower().strip()
        if "1" in sem_str_clean or "i" in sem_str_clean or "một" in sem_str_clean:
            if "2" in sem_str_clean or "ii" in sem_str_clean or "hai" in sem_str_clean:
                sem_num = 2
            else:
                sem_num = 1
        elif "2" in sem_str_clean or "ii" in sem_str_clean or "hai" in sem_str_clean:
            sem_num = 2

        # C. Nếu tìm thấy ay từ chuỗi niên khóa, tìm Semester tương ứng
        if ay and sem_num is not None:
            sem_row = (
                db.execute(select(Semester).where(Semester.academic_year_id == ay.id, Semester.number == sem_num))
                .scalars()
                .first()
            )
            if sem_row:
                resolved_semester_id = str(sem_row.id)

    # 3. Nếu chưa tìm thấy Academic Year (ay), fallback theo thứ tự hiện tại -> mới nhất
    if not ay:
        ay = (
            db.execute(
                select(DBAcademicYear).where(DBAcademicYear.school_id == school_id, DBAcademicYear.is_current.is_(True))
            )
            .scalars()
            .first()
        )
    if not ay:
        ay = (
            db.execute(
                select(DBAcademicYear)
                .where(DBAcademicYear.school_id == school_id)
                .order_by(DBAcademicYear.start_date.desc())
            )
            .scalars()
            .first()
        )

    # Nếu có semester_id_str là chuỗi văn bản (ví dụ chỉ nói "HK1" không kèm năm),
    # và ta chưa tìm được resolved_semester_id nhưng đã có ay mặc định ở trên:
    if semester_id_str and not resolved_semester_id and not is_valid_uuid(semester_id_str):
        sem_num = None
        sem_str_clean = str(semester_id_str).lower().strip()
        if "1" in sem_str_clean or "i" in sem_str_clean or "một" in sem_str_clean:
            if "2" in sem_str_clean or "ii" in sem_str_clean or "hai" in sem_str_clean:
                sem_num = 2
            else:
                sem_num = 1
        elif "2" in sem_str_clean or "ii" in sem_str_clean or "hai" in sem_str_clean:
            sem_num = 2

        if ay and sem_num is not None:
            sem_row = (
                db.execute(select(Semester).where(Semester.academic_year_id == ay.id, Semester.number == sem_num))
                .scalars()
                .first()
            )
            if sem_row:
                resolved_semester_id = str(sem_row.id)

    # Resolve Class ID using resolved Academic Year scope
    if class_id_str:
        if is_valid_uuid(class_id_str):
            class_row = (
                db.execute(
                    select(Class)
                    .join(Grade, Class.grade_id == Grade.id)
                    .where(Grade.school_id == school_id, Class.id == uuid.UUID(str(class_id_str)))
                )
                .scalars()
                .first()
            )
            if class_row:
                resolved_class_id = str(class_row.id)
        else:
            # Query class filtering by grade, school_id, and academic_year_id
            stmt = (
                select(Class)
                .join(Grade, Class.grade_id == Grade.id)
                .where(Grade.school_id == school_id, func.lower(Class.name) == str(class_id_str).lower().strip())
            )
            if ay:
                stmt = stmt.where(Class.academic_year_id == ay.id)

            class_row = db.execute(stmt).scalars().first()
            if class_row:
                resolved_class_id = str(class_row.id)
            else:
                stmt_like = (
                    select(Class)
                    .join(Grade, Class.grade_id == Grade.id)
                    .where(Grade.school_id == school_id, Class.name.ilike(f"%{str(class_id_str).strip()}%"))
                )
                if ay:
                    stmt_like = stmt_like.where(Class.academic_year_id == ay.id)

                class_row_like = db.execute(stmt_like).scalars().first()
                if class_row_like:
                    resolved_class_id = str(class_row_like.id)

    # Resolve Subject ID
    if subject_id_str:
        if is_valid_uuid(subject_id_str):
            sub_row = (
                db.execute(
                    select(Subject).where(Subject.school_id == school_id, Subject.id == uuid.UUID(str(subject_id_str)))
                )
                .scalars()
                .first()
            )
            if sub_row:
                resolved_subject_id = str(sub_row.id)
        else:
            # 1. Exact match by name (case-insensitive)
            sub_row = (
                db.execute(
                    select(Subject).where(
                        Subject.school_id == school_id, func.lower(Subject.name) == str(subject_id_str).lower().strip()
                    )
                )
                .scalars()
                .first()
            )
            if sub_row:
                resolved_subject_id = str(sub_row.id)
            else:
                # 2. Exact match by code (case-insensitive)
                sub_row_code = (
                    db.execute(
                        select(Subject).where(
                            Subject.school_id == school_id,
                            func.lower(Subject.code) == str(subject_id_str).lower().strip(),
                        )
                    )
                    .scalars()
                    .first()
                )
                if sub_row_code:
                    resolved_subject_id = str(sub_row_code.id)
                else:
                    # 3. Partial match (case-insensitive, searching keyword in name or code)
                    stmt = select(Subject).where(Subject.school_id == school_id)
                    all_school_subs = db.execute(stmt).scalars().all()
                    
                    search_term = str(subject_id_str).lower().strip()
                    matched_subs = []
                    for sub in all_school_subs:
                        s_name = sub.name.lower()
                        s_code = sub.code.lower()
                        if search_term in s_name or search_term in s_code:
                            matched_subs.append(sub)
                    
                    if matched_subs:
                        # Prioritize exact/closer matches by sorting by name length (e.g. "Vật lý" vs "Lịch sử và Địa lý" when searching for "Lý")
                        matched_subs.sort(key=lambda s: len(s.name))
                        resolved_subject_id = str(matched_subs[0].id)

    return resolved_class_id, resolved_semester_id, resolved_subject_id


def compute_report_data(db, school_id, report_type, grade_level, class_id=None, semester_id=None, subject_id=None):
    # Resolve dynamic names or text to UUIDs
    resolved_class_id, resolved_semester_id, resolved_subject_id = resolve_uuid_parameters(
        db, school_id, class_id, semester_id, subject_id
    )
    class_id = resolved_class_id or class_id
    semester_id = resolved_semester_id or semester_id
    subject_id = resolved_subject_id or subject_id

    # Resolve semester
    sem = None
    if semester_id and is_valid_uuid(semester_id):
        sem = db.get(Semester, uuid.UUID(str(semester_id)))
    if not sem:
        sem = db.execute(select(Semester).where(Semester.is_current.is_(True))).scalars().first()
        if not sem:
            sem = db.execute(select(Semester)).scalars().first()

    semester_id = sem.id if sem else None
    sem_name = sem.name if sem else "Học Kỳ 2"
    academic_year_id = sem.academic_year_id if sem else None

    # Resolve academic year name
    year_name = "2025-2026"
    if academic_year_id:
        from src.models.tables import AcademicYear as DBAcademicYear

        ay = db.get(DBAcademicYear, academic_year_id)
        if ay:
            year_name = ay.name

    selected_grade_name = "Toàn trường"
    if grade_level != "all":
        selected_grade_name = f"Khối {grade_level}"

    selected_class_name = ""
    if class_id and is_valid_uuid(class_id):
        cls_row = db.get(Class, uuid.UUID(str(class_id)) if isinstance(class_id, str) else class_id)
        if cls_row:
            selected_class_name = f" - Lớp {cls_row.name}"

    # Filters
    filters = []
    if semester_id:
        if is_valid_uuid(semester_id):
            filters.append(Score.semester_id == semester_id)
        else:
            raise ValueError(f"Không tìm thấy học kỳ '{semester_id}' trong cơ sở dữ liệu.")
    if class_id:
        if is_valid_uuid(class_id):
            filters.append(Score.class_id == class_id)
        else:
            raise ValueError(f"Không tìm thấy lớp học '{class_id}' trong cơ sở dữ liệu.")
    elif grade_level != "all":
        try:
            grade_num = int(grade_level)
            filters.append(
                Score.class_id.in_(
                    select(Class.id).join(Grade).where(Grade.grade_number == grade_num, Grade.school_id == school_id)
                )
            )
        except ValueError:
            pass
    final_scope = and_(*filters) if filters else None

    # Stats
    gpa = _average_gpa(db, final_scope)
    at_risk = _at_risk_classes(db, final_scope)

    if academic_year_id:
        if class_id is None and grade_level == "all":
            total_students_stmt = (
                select(func.count(Student.id.distinct()))
                .select_from(Student)
                .where(Student.is_active.is_(True), Student.school_id == school_id)
            )
        else:
            total_students_stmt = (
                select(func.count(Student.id.distinct()))
                .select_from(Student)
                .join(Enrollment, Student.id == Enrollment.student_id)
                .where(
                    Student.is_active.is_(True),
                    Student.school_id == school_id,
                    Enrollment.academic_year_id == academic_year_id,
                )
            )
            if class_id:
                total_students_stmt = total_students_stmt.where(Enrollment.class_id == class_id)
            elif grade_level != "all":
                try:
                    grade_num = int(grade_level)
                    total_students_stmt = (
                        total_students_stmt.join(Class, Enrollment.class_id == Class.id)
                        .join(Grade, Class.grade_id == Grade.id)
                        .where(Grade.grade_number == grade_num)
                    )
                except ValueError:
                    pass
        total_students = db.scalar(total_students_stmt) or 0

        total_classes_stmt = (
            select(func.count())
            .select_from(Class)
            .join(Grade, Class.grade_id == Grade.id)
            .where(Grade.school_id == school_id, Class.academic_year_id == academic_year_id)
        )
        if class_id:
            total_classes_stmt = total_classes_stmt.where(Class.id == class_id)
        elif grade_level != "all":
            try:
                grade_num = int(grade_level)
                total_classes_stmt = total_classes_stmt.where(Grade.grade_number == grade_num)
            except ValueError:
                pass
        total_classes = db.scalar(total_classes_stmt) or 0
    else:
        total_students_stmt = (
            select(func.count(Student.id.distinct()))
            .select_from(Student)
            .where(Student.is_active.is_(True), Student.school_id == school_id)
        )
        if class_id or grade_level != "all":
            total_students_stmt = total_students_stmt.join(Enrollment, Student.id == Enrollment.student_id)
            if class_id:
                total_students_stmt = total_students_stmt.where(Enrollment.class_id == class_id)
            elif grade_level != "all":
                try:
                    grade_num = int(grade_level)
                    total_students_stmt = (
                        total_students_stmt.join(Class, Enrollment.class_id == Class.id)
                        .join(Grade, Class.grade_id == Grade.id)
                        .where(Grade.grade_number == grade_num)
                    )
                except ValueError:
                    pass
        total_students = db.scalar(total_students_stmt) or 0

        total_classes_stmt = (
            select(func.count())
            .select_from(Class)
            .join(Grade, Class.grade_id == Grade.id)
            .where(Grade.school_id == school_id)
        )
        if class_id:
            total_classes_stmt = total_classes_stmt.where(Class.id == class_id)
        elif grade_level != "all":
            try:
                grade_num = int(grade_level)
                total_classes_stmt = total_classes_stmt.where(Grade.grade_number == grade_num)
            except ValueError:
                pass
        total_classes = db.scalar(total_classes_stmt) or 0

    # Subject Averages
    subject_averages = []
    if semester_id:
        stmt_sub_avg = (
            select(Subject.name, func.avg(Score.value))
            .select_from(Score)
            .join(Subject, Score.subject_id == Subject.id)
            .join(Class, Score.class_id == Class.id)
            .join(Grade, Class.grade_id == Grade.id)
            .where(
                Grade.school_id == school_id,
                Score.semester_id == semester_id,
                Score.status == "APPROVED",
                Score.score_category == "FINAL",
            )
        )
        if class_id:
            stmt_sub_avg = stmt_sub_avg.where(Score.class_id == class_id)
        elif grade_level != "all":
            try:
                grade_num = int(grade_level)
                stmt_sub_avg = stmt_sub_avg.where(Grade.grade_number == grade_num)
            except ValueError:
                pass
        for s_name, val in db.execute(stmt_sub_avg.group_by(Subject.name)).all():
            if val is not None:
                subject_averages.append({"Môn học": s_name, "ĐTB": round(float(val), 2)})

    # Conduct
    conduct_stats = {"TOT": 0, "KHA": 0, "TRUNG_BINH": 0, "YEU": 0}
    if semester_id:
        stmt_conduct = (
            select(StudentTermReport.conduct, func.count(StudentTermReport.id))
            .join(Class, StudentTermReport.class_id == Class.id)
            .join(Grade, Class.grade_id == Grade.id)
            .where(Grade.school_id == school_id, StudentTermReport.semester_id == semester_id)
        )
        if class_id:
            stmt_conduct = stmt_conduct.where(StudentTermReport.class_id == class_id)
        elif grade_level != "all":
            try:
                grade_num = int(grade_level)
                stmt_conduct = stmt_conduct.where(Grade.grade_number == grade_num)
            except ValueError:
                pass
        for c_enum, count in db.execute(stmt_conduct.group_by(StudentTermReport.conduct)).all():
            if c_enum:
                conduct_stats[c_enum.name] = count

    # Staff
    active_teachers_count = 0
    homeroom_count = 0
    subject_teacher_count = 0
    if academic_year_id:
        active_teachers_count = (
            db.scalar(
                select(func.count(TeacherAssignment.user_id.distinct())).where(
                    TeacherAssignment.academic_year_id == academic_year_id, TeacherAssignment.is_active.is_(True)
                )
            )
            or 0
        )
        homeroom_count = (
            db.scalar(
                select(func.count(TeacherAssignment.id)).where(
                    TeacherAssignment.academic_year_id == academic_year_id,
                    TeacherAssignment.role_context.in_(["HOMEROOM_PRIMARY", "HOMEROOM_SECONDARY"]),
                    TeacherAssignment.is_active.is_(True),
                )
            )
            or 0
        )
        subject_teacher_count = (
            db.scalar(
                select(func.count(TeacherAssignment.id)).where(
                    TeacherAssignment.academic_year_id == academic_year_id,
                    TeacherAssignment.role_context == "SUBJECT_TEACHER",
                    TeacherAssignment.is_active.is_(True),
                )
            )
            or 0
        )

    return {
        "semester_id": semester_id,
        "sem_name": sem_name,
        "year_name": year_name,
        "selected_grade_name": selected_grade_name,
        "selected_class_name": selected_class_name,
        "total_students": total_students,
        "total_classes": total_classes,
        "gpa": gpa,
        "at_risk": at_risk,
        "subject_averages": subject_averages,
        "conduct_stats": conduct_stats,
        "active_teachers_count": active_teachers_count,
        "homeroom_count": homeroom_count,
        "subject_teacher_count": subject_teacher_count,
    }


@tool
def get_report_data_summary(
    report_type: Literal["academic_conduct", "subject_quality", "at_risk", "subject_report"],
    grade_level: str = "all",
    class_id: str = None,
    semester_id: str = None,
    subject_id: str = None,
) -> str:
    """Tra cứu và tổng hợp số liệu báo cáo thống kê phục vụ cho việc hiển thị bảng số liệu trực tiếp.

    Args:
        report_type: Loại báo cáo ('academic_conduct', 'subject_quality', 'at_risk', 'subject_report').
        grade_level: Khối lớp học ('all' hoặc số khối ví dụ: '7', '8', '10', '11', '12').
        class_id: ID hoặc Tên lớp học cụ thể (tùy chọn, ví dụ: '10A1', '8B').
        semester_id: ID hoặc Tên học kỳ/Số học kỳ (tùy chọn, ví dụ: 'Học kỳ 1', 'HK1', '1', 'Học kỳ 2', 'HK2', '2').
        subject_id: ID hoặc Tên/Mã môn học cụ thể (tùy chọn, ví dụ: 'Toán', 'Ngữ văn', 'Tiếng Anh').
    """
    school_id = current_user_school_id.get()
    if not school_id:
        return "Lỗi: Không xác định được trường học. Vui lòng đăng nhập."

    with SessionLocal() as db:
        # Fetch school name
        school = db.get(School, school_id)
        school_name = school.name if school else "Trường học"

        data = compute_report_data(db, school_id, report_type, grade_level, class_id, semester_id, subject_id)

        report_titles = {
            "academic_conduct": "BÁO CÁO TỔNG KẾT KẾT QUẢ HỌC TẬP VÀ RÈN LUYỆN",
            "subject_quality": "BÁO CÁO PHÂN TÍCH PHỔ ĐIỂM VÀ CHẤT LƯỢNG BỘ MÔN",
            "at_risk": "BÁO CÁO SÀNG LỌC VÀ THEO DÕI NHÓM HỌC SINH CẦN HỖ TRỢ SƯ PHẠM",
            "subject_report": "BÁO CÁO CHUYÊN SÂU MÔN HỌC",
        }
        title_text = report_titles.get(report_type, f"BÁO CÁO THỐNG KÊ {report_type.upper()}")

        summary = f"### {title_text} - {school_name.upper()}\n"
        summary += f"- **Phạm vi**: {data['selected_grade_name']}{data['selected_class_name']}\n"
        summary += f"- **Niên khóa**: {data['year_name']} / **Học kỳ**: {data['sem_name']}\n\n"

        summary += "| Chỉ số thống kê | Giá trị thực tế |\n"
        summary += "| --- | --- |\n"
        summary += f"| Sĩ số học sinh active | {data['total_students']} học sinh |\n"
        if not class_id:
            summary += f"| Tổng số lớp học hoạt động | {data['total_classes']} lớp học |\n"
        summary += f"| GPA trung bình | {data['gpa'] or 0.0} / 10 |\n"
        if not class_id:
            summary += f"| Số lớp cần can thiệp học thuật | {data['at_risk']} lớp |\n"

        if report_type == "subject_quality" and data["subject_averages"]:
            summary += "\n#### Điểm trung bình các môn học:\n"
            summary += "| Môn học | Điểm trung bình |\n"
            summary += "| --- | --- |\n"
            for item in data["subject_averages"]:
                summary += f"| {item['Môn học']} | {item['ĐTB']} |\n"

        elif report_type == "academic_conduct":
            summary += "\n#### Phân loại hạnh kiểm:\n"
            summary += "| Loại hạnh kiểm | Số học sinh |\n"
            summary += "| --- | --- |\n"
            summary += f"| Tốt | {data['conduct_stats']['TOT']} học sinh |\n"
            summary += f"| Khá | {data['conduct_stats']['KHA']} học sinh |\n"
            summary += f"| Đạt | {data['conduct_stats']['TRUNG_BINH']} học sinh |\n"
            summary += f"| Chưa đạt | {data['conduct_stats']['YEU']} học sinh |\n"

        elif report_type == "at_risk":
            summary += "\n#### Thống kê nhóm học sinh cần hỗ trợ sư phạm:\n"
            summary += f"- **Số lượng học sinh nguy cơ**: {data['at_risk']} lớp học cảnh báo có ĐTB < 5.0\n"

        elif report_type == "subject_report":
            summary += "\n#### Báo cáo chuyên sâu môn học:\n"
            summary += f"- Học sinh tham gia thi: {data['total_students']} học sinh\n"
            summary += f"- Điểm trung bình môn: {data['gpa'] or 0.0} / 10\n"

        return summary


@tool
async def generate_report_download_link(
    report_type: Literal["academic_conduct", "subject_quality", "at_risk", "subject_report"],
    format: Literal["docx", "pdf", "html"],
    grade_level: str = "all",
    class_id: str = None,
    semester_id: str = None,
    subject_id: str = None,
    include_ai_insights: bool = True,
    include_tables: bool = True,
    include_signature: bool = True,
) -> str:
    """Tạo tệp báo cáo thống kê thực tế ở server và trả về link tải trực tiếp trong khung chat.

    IMPORTANT WARNING: Công cụ này sẽ tự động tạo đồng thời cả 3 định dạng file (.docx, .pdf, .html) và trả về đường link của cả 3 định dạng này trong cùng 1 lần gọi. 
    BẠN CHỈ ĐƯỢC PHÉP GỌI CÔNG CỤ NÀY ĐÚNG 1 LẦN DUY NHẤT CHO MỖI YÊU CẦU BÁO CÁO. Tuyệt đối KHÔNG gọi công cụ này nhiều lần trong vòng lặp hoặc gọi riêng rẽ cho từng định dạng.

    Args:
        report_type: Loại báo cáo ('academic_conduct', 'subject_quality', 'at_risk', 'subject_report').
        format: Định dạng tệp ('docx', 'pdf', 'html'). Bạn có thể chọn bất kỳ định dạng nào (ví dụ 'docx'), cả 3 định dạng đều sẽ được tạo ra tự động dưới cùng một UUID.
        grade_level: Khối lớp học ('all' hoặc số khối ví dụ: '7', '8', '10', '11', '12').
        class_id: ID hoặc Tên lớp học cụ thể (tùy chọn, ví dụ: '10A1', '8B').
        semester_id: ID hoặc Tên học kỳ/Số học kỳ (tùy chọn, ví dụ: 'Học kỳ 1', 'HK1', '1', 'Học kỳ 2', 'HK2', '2').
        subject_id: ID hoặc tên môn học cụ thể (tùy chọn).
        include_ai_insights: Bao gồm nhận xét phân tích từ AI.
        include_tables: Bao gồm bảng dữ liệu chi tiết.
        include_signature: Bao gồm khung chữ ký phê duyệt.
    """
    school_id = current_user_school_id.get()
    if not school_id:
        return "Lỗi: Không xác định được trường học. Vui lòng đăng nhập."

    file_uuid = str(uuid.uuid4())[:8]
    temp_dir = "temp"
    if not os.path.exists(temp_dir):
        os.makedirs(temp_dir)

    try:
        from src.api.v1.reports import export_analytics_report

        user_id = None
        with SessionLocal() as db:
            db.get(School, school_id)

            from src.models.tables import User as DBUser

            user_row = (
                db.execute(select(DBUser).where(DBUser.school_id == school_id, DBUser.is_active.is_(True)))
                .scalars()
                .first()
            )

            if not user_row:
                return "Lỗi: Không tìm thấy tài khoản người dùng hợp lệ để xuất báo cáo."

            user_id = user_row.id

            # Resolve dynamic names or text to UUIDs
            resolved_class_id, resolved_semester_id, resolved_subject_id = resolve_uuid_parameters(
                db, school_id, class_id, semester_id, subject_id
            )
            class_id = resolved_class_id or class_id
            semester_id = resolved_semester_id or semester_id
            subject_id = resolved_subject_id or subject_id

        formats_to_generate = ["docx", "html", "pdf"]
        generated_formats = []

        for fmt in formats_to_generate:
            try:
                with SessionLocal() as db:
                    from src.models.tables import User as DBUser
                    user = db.get(DBUser, user_id)
                    if not user:
                        continue

                    payload = ReportExportRequest(
                        report_type=report_type,
                        format=fmt,
                        grade_level=grade_level,
                        class_id=class_id,
                        semester_id=uuid.UUID(semester_id) if semester_id and is_valid_uuid(semester_id) else None,
                        subject_id=uuid.UUID(subject_id) if subject_id and is_valid_uuid(subject_id) else None,
                        include_charts=True,
                        include_tables=include_tables,
                        include_ai_insights=include_ai_insights,
                        include_signature=include_signature,
                    )

                    response = export_analytics_report(payload=payload, user=user, db=db)

                fmt_filepath = os.path.join(temp_dir, f"bao_cao_{report_type}_{file_uuid}.{fmt}")
                if hasattr(response, "body"):
                    with open(fmt_filepath, "wb") as f:
                        f.write(response.body)
                elif hasattr(response, "body_iterator"):
                    with open(fmt_filepath, "wb") as f:
                        async for chunk in response.body_iterator:
                            f.write(chunk)
                generated_formats.append(fmt)
            except Exception as e:
                # Log error for a specific format but allow others to succeed
                print(f"Error generating format {fmt}: {str(e)}")

        if not generated_formats:
            return "Lỗi: Không thể tạo bất kỳ định dạng báo cáo nào."

        from src.config import get_settings

        settings = get_settings()
        base_url = settings.backend_url.rstrip('/')

        links = []
        if "html" in generated_formats:
            download_url_html = f"{base_url}/api/v1/reports/download/bao_cao_{report_type}_{file_uuid}.html"
            links.append(f"[Xem Bản Xem Trước Báo Cáo]({download_url_html})")
        if "docx" in generated_formats:
            download_url_docx = f"{base_url}/api/v1/reports/download/bao_cao_{report_type}_{file_uuid}.docx"
            links.append(f"[Tải Báo Cáo Word (.docx)]({download_url_docx})")
        if "pdf" in generated_formats:
            download_url_pdf = f"{base_url}/api/v1/reports/download/bao_cao_{report_type}_{file_uuid}.pdf"
            links.append(f"[Tải Báo Cáo PDF (.pdf)]({download_url_pdf})")

        links_str = " | ".join(links)
        return f"Tệp báo cáo đã được tạo thành công!\n\n👉 {links_str}"

    except Exception as e:
        return f"Lỗi trong quá trình tạo tệp báo cáo: {str(e)}"


def render_markdown_to_docx(title: str, content_markdown: str) -> docx.Document:
    doc = docx.Document()

    # 1. Page Setup
    section = doc.sections[0]
    section.top_margin = Cm(2.0)
    section.bottom_margin = Cm(2.0)
    section.left_margin = Cm(3.0)
    section.right_margin = Cm(2.0)

    # 2. Style Setup
    style = doc.styles["Normal"]
    font = style.font
    font.name = "Times New Roman"
    font.size = Pt(12)
    font.color.rgb = RGBColor(0, 0, 0)

    # 3. Parse Markdown Body
    lines = content_markdown.split("\n")

    # 4. Parse Markdown Body helper

    def add_formatted_text(paragraph, text, is_bold_default=False):
        parts = re.split(r"(\*\*.*?\*\*|\*.*?\*|`.*?`)", text)
        for part in parts:
            if part.startswith("**") and part.endswith("**"):
                r = paragraph.add_run(part[2:-2])
                r.font.bold = True
                r.font.name = "Times New Roman"
            elif part.startswith("*") and part.endswith("*"):
                r = paragraph.add_run(part[1:-1])
                r.font.italic = True
                r.font.name = "Times New Roman"
            elif part.startswith("`") and part.endswith("`"):
                r = paragraph.add_run(part[1:-1])
                r.font.name = "Courier New"
                r.font.size = Pt(10.5)
            else:
                if part:
                    r = paragraph.add_run(part)
                    if is_bold_default:
                        r.font.bold = True
                    r.font.name = "Times New Roman"

    in_table = False
    table_rows = []

    def flush_table():
        nonlocal in_table, table_rows
        if not table_rows:
            return
        parsed_rows = []
        for r in table_rows:
            cols = [c.strip() for c in r.split("|")]
            if len(cols) >= 2:
                if cols[0] == "":
                    cols = cols[1:]
                if cols and cols[-1] == "":
                    cols = cols[:-1]
                if all(re.match(r"^\s*:-?-*:?\s*$", c) or re.match(r"^\s*-+\s*$", c) for c in cols):
                    continue
                parsed_rows.append(cols)

        if parsed_rows:
            num_cols = max(len(row) for row in parsed_rows)
            table = doc.add_table(rows=len(parsed_rows), cols=num_cols)
            table.style = "Table Grid"
            table.alignment = 1  # Center

            for r_idx, row_data in enumerate(parsed_rows):
                row = table.rows[r_idx]
                is_header = r_idx == 0
                for c_idx, val in enumerate(row_data):
                    if c_idx < len(row.cells):
                        cell = row.cells[c_idx]
                        cell.text = ""
                        p = cell.paragraphs[0]
                        p.paragraph_format.space_after = Pt(2)
                        p.paragraph_format.space_before = Pt(2)
                        if is_header:
                            p.alignment = 1  # Center
                            add_formatted_text(p, val, is_bold_default=True)
                            shading_elm = parse_xml(f'<w:shd {nsdecls("w")} w:fill="F2F2F2"/>')
                            cell._tc.get_or_add_tcPr().append(shading_elm)
                        else:
                            p.alignment = 0  # Left
                            add_formatted_text(p, val)

            doc.add_paragraph().paragraph_format.space_after = Pt(6)

        table_rows = []
        in_table = False

    idx = 0
    while idx < len(lines):
        line = lines[idx].strip()

        if line.startswith("|"):
            in_table = True
            table_rows.append(line)
            idx += 1
            continue
        elif in_table:
            flush_table()

        if not line:
            idx += 1
            continue

        # Check for center alignment tags (case-insensitive)
        is_center = False
        line_lower = line.lower()
        if (line_lower.startswith("<center>") and line_lower.endswith("</center>")) or (line_lower.startswith('<p align="center">') and line_lower.endswith('</p>')):
            is_center = True
            line = re.sub(r"^<center>", "", line, flags=re.IGNORECASE)
            line = re.sub(r"</center>$", "", line, flags=re.IGNORECASE)
            line = re.sub(r'^<p align="center">', "", line, flags=re.IGNORECASE)
            line = re.sub(r'</p>$', "", line, flags=re.IGNORECASE)
            line = line.strip()

        if line.startswith("# "):
            heading_text = line[2:].strip()
            p = doc.add_paragraph()
            if is_center:
                p.alignment = 1
            r = p.add_run(heading_text.upper())
            r.font.bold = True
            r.font.size = Pt(13)
            r.font.name = "Times New Roman"
            p.paragraph_format.space_before = Pt(12)
            p.paragraph_format.space_after = Pt(6)
            p.paragraph_format.keep_with_next = True

        elif line.startswith("## "):
            heading_text = line[3:].strip()
            p = doc.add_paragraph()
            if is_center:
                p.alignment = 1
            r = p.add_run(heading_text)
            r.font.bold = True
            r.font.size = Pt(13)
            r.font.name = "Times New Roman"
            p.paragraph_format.space_before = Pt(12)
            p.paragraph_format.space_after = Pt(6)
            p.paragraph_format.keep_with_next = True

        elif line.startswith("### "):
            heading_text = line[4:].strip()
            p = doc.add_paragraph()
            if is_center:
                p.alignment = 1
            r = p.add_run(heading_text)
            r.font.bold = True
            r.font.italic = True
            r.font.size = Pt(12)
            r.font.name = "Times New Roman"
            p.paragraph_format.space_before = Pt(6)
            p.paragraph_format.space_after = Pt(4)
            p.paragraph_format.keep_with_next = True

        elif re.match(r"^[-*+]\s+", line):
            bullet_text = re.sub(r"^[-*+]\s+", "", line).strip()
            p = doc.add_paragraph(style="List Bullet")
            if is_center:
                p.alignment = 1
            p.paragraph_format.space_after = Pt(4)
            p.paragraph_format.left_indent = Cm(0.75)
            add_formatted_text(p, bullet_text)

        elif re.match(r"^\d+\.\s+", line):
            match = re.match(r"^(\d+\.\s+)", line)
            num_prefix = match.group(1) if match else ""
            num_text = re.sub(r"^\d+\.\s+", "", line).strip()
            p = doc.add_paragraph()
            if is_center:
                p.alignment = 1
            p.paragraph_format.space_after = Pt(4)
            p.paragraph_format.left_indent = Cm(0.75)
            if num_prefix:
                run_num = p.add_run(num_prefix)
                run_num.font.name = "Times New Roman"
                run_num.font.size = Pt(12)
            add_formatted_text(p, num_text)

        else:
            p = doc.add_paragraph()
            if is_center:
                p.alignment = 1
            p.paragraph_format.space_after = Pt(6)
            p.paragraph_format.line_spacing = 1.15
            add_formatted_text(p, line)

        idx += 1

    if in_table:
        flush_table()

    return doc


def render_markdown_to_html(title: str, content_markdown: str) -> str:
    import re

    lines = content_markdown.split("\n")

    html_body = []
    in_table = False
    table_rows = []

    def flush_table():
        nonlocal in_table, table_rows
        if not table_rows:
            return
        parsed_rows = []
        for r in table_rows:
            cols = [c.strip() for c in r.split("|")]
            if len(cols) >= 2:
                if cols[0] == "":
                    cols = cols[1:]
                if cols and cols[-1] == "":
                    cols = cols[:-1]
                if all(re.match(r"^\s*:-?-*:?\s*$", c) or re.match(r"^\s*-+\s*$", c) for c in cols):
                    continue
                parsed_rows.append(cols)

        if parsed_rows:
            html_body.append('<table class="report-table">')
            for r_idx, row_data in enumerate(parsed_rows):
                is_header = r_idx == 0
                html_body.append("<tr>")
                for val in row_data:
                    cell_tag = "th" if is_header else "td"
                    val_html = parse_inline_markdown(val)
                    html_body.append(f"<{cell_tag}>{val_html}</{cell_tag}>")
                html_body.append("</tr>")
            html_body.append("</table>")
        table_rows = []
        in_table = False

    def parse_inline_markdown(text):
        text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
        text = re.sub(r"\*([^*]+)\*", r"<em>\1</em>", text)
        text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
        return text

    in_list = False
    list_type = None

    def flush_list():
        nonlocal in_list, list_type
        if in_list:
            html_body.append(f"</{list_type}>")
            in_list = False
            list_type = None

    idx = 0
    while idx < len(lines):
        line = lines[idx].strip()

        if line.startswith("|"):
            flush_list()
            in_table = True
            table_rows.append(line)
            idx += 1
            continue
        elif in_table:
            flush_table()

        if not line:
            flush_list()
            idx += 1
            continue

        # Check for center alignment tags (case-insensitive)
        is_center = False
        line_lower = line.lower()
        if (line_lower.startswith("<center>") and line_lower.endswith("</center>")) or (line_lower.startswith('<p align="center">') and line_lower.endswith('</p>')):
            is_center = True
            line = re.sub(r"^<center>", "", line, flags=re.IGNORECASE)
            line = re.sub(r"</center>$", "", line, flags=re.IGNORECASE)
            line = re.sub(r'^<p align="center">', "", line, flags=re.IGNORECASE)
            line = re.sub(r'</p>$', "", line, flags=re.IGNORECASE)
            line = line.strip()

        tag_html = ""

        if line.startswith("# "):
            flush_list()
            tag_html = f"<h2>{parse_inline_markdown(line[2:].strip())}</h2>"
        elif line.startswith("## "):
            flush_list()
            tag_html = f"<h2>{parse_inline_markdown(line[3:].strip())}</h2>"
        elif line.startswith("### "):
            flush_list()
            tag_html = f"<h3>{parse_inline_markdown(line[4:].strip())}</h3>"
        elif re.match(r"^[-*+]\s+", line):
            bullet_text = re.sub(r"^[-*+]\s+", "", line).strip()
            if not in_list or list_type != "ul":
                flush_list()
                html_body.append("<ul>")
                in_list = True
                list_type = "ul"
            tag_html = f"<li>{parse_inline_markdown(bullet_text)}</li>"
        elif re.match(r"^\d+\.\s+", line):
            num_text = re.sub(r"^\d+\.\s+", "", line).strip()
            if not in_list or list_type != "ol":
                flush_list()
                html_body.append("<ol>")
                in_list = True
                list_type = "ol"
            tag_html = f"<li>{parse_inline_markdown(num_text)}</li>"
        else:
            flush_list()
            tag_html = f"<p>{parse_inline_markdown(line)}</p>"

        if is_center and tag_html:
            if tag_html.startswith("<p>"):
                tag_html = tag_html.replace("<p>", '<p style="text-align: center;">', 1)
            elif tag_html.startswith("<h2>"):
                tag_html = tag_html.replace("<h2>", '<h2 style="text-align: center; text-transform: uppercase;">', 1)
            elif tag_html.startswith("<h3>"):
                tag_html = tag_html.replace("<h3>", '<h3 style="text-align: center;">', 1)
            else:
                tag_html = f'<div style="text-align: center;">{tag_html}</div>'

        if tag_html:
            html_body.append(tag_html)

        idx += 1

    flush_table()
    flush_list()

    body_content = "\n".join(html_body)

    html_template = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
    body {{
        font-family: 'Times New Roman', Times, serif;
        font-size: 13pt;
        line-height: 1.3;
        color: #000000;
        margin: 0;
        padding: 2cm 2cm 2cm 3cm;
        background-color: #ffffff;
    }}
    .document-title {{
        text-align: center;
        font-size: 14pt;
        font-weight: bold;
        text-transform: uppercase;
        margin-bottom: 24px;
    }}
    p {{
        margin-top: 0;
        margin-bottom: 12px;
        text-align: justify;
    }}
    h2 {{
        font-size: 13pt;
        font-weight: bold;
        margin-top: 18px;
        margin-bottom: 8px;
        text-transform: uppercase;
    }}
    h3 {{
        font-size: 12pt;
        font-weight: bold;
        font-style: italic;
        margin-top: 12px;
        margin-bottom: 6px;
    }}
    .report-table {{
        width: 100%;
        border-collapse: collapse;
        margin-top: 12px;
        margin-bottom: 18px;
    }}
    .report-table th, .report-table td {{
        border: 1px solid #000000;
        padding: 6px 8px;
        font-size: 11pt;
    }}
    .report-table th {{
        background-color: #f2f2f2;
        font-weight: bold;
        text-align: center;
    }}
    .report-table td {{
        text-align: left;
    }}
    ul, ol {{
        margin-top: 0;
        margin-bottom: 12px;
        padding-left: 20px;
    }}
    li {{
        margin-bottom: 4px;
    }}
    code {{
        font-family: Consolas, Monaco, monospace;
        font-size: 10pt;
        background-color: #f4f4f4;
        padding: 2px 4px;
        border-radius: 3px;
    }}
</style>
</head>
<body>
    {body_content}
</body>
</html>
"""
    return html_template


@tool
async def generate_custom_report_docx(title: str, content_markdown: str) -> str:
    """Tạo tệp báo cáo tự do (.docx và .html) từ nội dung Markdown được định nghĩa bởi Agent và trả về liên kết tải xuống/xem trước.

    Args:
        title: Tiêu đề báo cáo (ví dụ: 'Báo cáo Học tập bổ sung lớp 10A1').
        content_markdown: Nội dung báo cáo định dạng Markdown (hỗ trợ các tiêu đề, danh sách, bảng biểu).
    """
    file_uuid = str(uuid.uuid4())[:8]
    filename_docx = f"bao_cao_tu_do_{file_uuid}.docx"
    filename_html = f"bao_cao_tu_do_{file_uuid}.html"
    temp_dir = "temp"
    if not os.path.exists(temp_dir):
        os.makedirs(temp_dir)
    file_path_docx = os.path.join(temp_dir, filename_docx)
    file_path_html = os.path.join(temp_dir, filename_html)

    try:
        # 1. Generate DOCX
        doc = render_markdown_to_docx(title, content_markdown)
        doc.save(file_path_docx)

        # 2. Generate HTML
        html_content = render_markdown_to_html(title, content_markdown)
        with open(file_path_html, "w", encoding="utf-8") as f:
            f.write(html_content)

        # 3. Generate PDF via Gotenberg to prevent download errors
        filename_pdf = f"bao_cao_tu_do_{file_uuid}.pdf"
        file_path_pdf = os.path.join(temp_dir, filename_pdf)

        gotenberg_url = "https://c2-app-051-gotenberg.up.railway.app/forms/libreoffice/convert"
        try:
            import requests
            with open(file_path_docx, "rb") as f_docx:
                files = {
                    "files": (
                        "report.docx",
                        f_docx.read(),
                        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    )
                }
            resp = requests.post(gotenberg_url, files=files, timeout=60)
            if resp.status_code == 200:
                with open(file_path_pdf, "wb") as f_pdf:
                    f_pdf.write(resp.content)
            else:
                print(f"Gotenberg convert failed: {resp.text}")
        except Exception as e:
            print(f"Failed to generate PDF for custom report: {str(e)}")

        from src.config import get_settings

        settings = get_settings()
        download_url = f"{settings.backend_url.rstrip('/')}/api/v1/reports/download/{filename_docx}"
        preview_url = f"{settings.backend_url.rstrip('/')}/api/v1/reports/download/{filename_html}"

        return f"Tệp báo cáo tự do đã được tạo thành công!\n\n👉 [Xem Bản Xem Trước Báo Cáo]({preview_url}) | [Tải Báo Cáo Word (.docx)]({download_url})"
    except Exception as e:
        return f"Lỗi trong quá trình tạo tệp báo cáo tự do: {str(e)}"
