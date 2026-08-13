"""Logic truy vấn dữ liệu báo cáo từ schema s360 (score_focused_schema.sql).

Tách riêng khỏi tools.py để tránh file quá lớn. Chứa các hàm resolve tham số
và tổng hợp dữ liệu báo cáo từ các bảng s360.
"""

import re

from sqlalchemy import and_, func, select

from src.models.s360_tables import (
    DimHomeroomClass,
    DimHomeroomClassStudent,
    DimSchoolYear,
    DimSubject,
    FactGradebooks,
    FactOverallAcademicRecords,
)
from src.services.s360_stats import _at_risk_classes_s360, _average_gpa_s360


def is_valid_int(val) -> bool:
    """Kiểm tra xem giá trị có phải integer hợp lệ không."""
    if val is None or val == "" or val == "null" or val == "None":
        return False
    try:
        int(str(val))
        return True
    except (ValueError, TypeError):
        return False


def resolve_parameters(db, school_id, class_id_str, semester_id_str, subject_id_str, school_year_id_str=None):
    """Resolve text hoặc ID sang BIGINT/INTEGER ID trong schema s360.

    Returns:
        tuple (resolved_class_id, resolved_school_year_id, resolved_semester_index, resolved_subject_id)
    """
    resolved_class_id = None
    resolved_school_year_id = None
    resolved_semester_index = None
    resolved_subject_id = None

    # 1. Resolve School Year (dim_school_year)
    ay = None
    if is_valid_int(school_year_id_str):
        ay = db.get(DimSchoolYear, int(str(school_year_id_str)))
    elif school_year_id_str:
        year_match_range = re.search(r"(\d{4}-\d{4})", str(school_year_id_str))
        year_match_single = re.search(r"\b(\d{4})\b", str(school_year_id_str))
        if year_match_range:
            year_name = year_match_range.group(1)
            ay = db.execute(
                select(DimSchoolYear).where(
                    DimSchoolYear.fullname.contains(year_name) | DimSchoolYear.code.contains(year_name)
                )
            ).scalars().first()
        elif year_match_single:
            year_val = year_match_single.group(1)
            ay = db.execute(
                select(DimSchoolYear).where(
                    DimSchoolYear.fullname.contains(year_val) | DimSchoolYear.code.contains(year_val)
                )
            ).scalars().first()

    if not ay:
        ay = db.execute(select(DimSchoolYear).where(DimSchoolYear.is_current == 1)).scalars().first()
    if not ay:
        ay = db.execute(select(DimSchoolYear)).scalars().first()
    if ay:
        resolved_school_year_id = ay.id

    # 2. Resolve Semester Index (1/2)
    if semester_id_str:
        sem_str_clean = str(semester_id_str).lower().strip()
        if is_valid_int(semester_id_str):
            resolved_semester_index = int(str(semester_id_str))
            if resolved_semester_index not in (1, 2):
                resolved_semester_index = 1
        elif "2" in sem_str_clean or "ii" in sem_str_clean or "hai" in sem_str_clean:
            if "1" in sem_str_clean or "i" in sem_str_clean or "một" in sem_str_clean:
                resolved_semester_index = 1
            else:
                resolved_semester_index = 2
        elif "1" in sem_str_clean or "i" in sem_str_clean or "một" in sem_str_clean:
            resolved_semester_index = 1
        else:
            resolved_semester_index = 1
    else:
        resolved_semester_index = 1

    # 3. Resolve Class ID (dim_homeroom_class)
    if class_id_str:
        if is_valid_int(class_id_str):
            class_row = db.execute(
                select(DimHomeroomClass).where(
                    DimHomeroomClass.id == int(str(class_id_str)),
                    DimHomeroomClass.so_school_id == school_id,
                )
            ).scalars().first()
            if class_row:
                resolved_class_id = class_row.id
        else:
            search_term = str(class_id_str).strip()
            stmt = select(DimHomeroomClass).where(
                DimHomeroomClass.so_school_id == school_id,
                DimHomeroomClass.is_active == 1,
            )
            if resolved_school_year_id:
                stmt = stmt.where(DimHomeroomClass.school_year_id == resolved_school_year_id)
            class_row = db.execute(
                stmt.where(
                    (func.lower(DimHomeroomClass.code) == search_term.lower())
                    | (func.lower(DimHomeroomClass.fullname).contains(search_term.lower()))
                )
            ).scalars().first()
            if not class_row:
                class_row = db.execute(
                    stmt.where(DimHomeroomClass.code.contains(search_term))
                ).scalars().first()
            if class_row:
                resolved_class_id = class_row.id

    # 4. Resolve Subject ID (dim_subject)
    if subject_id_str:
        if is_valid_int(subject_id_str):
            sub_row = db.get(DimSubject, int(str(subject_id_str)))
            if sub_row:
                resolved_subject_id = sub_row.id
        else:
            search_term = str(subject_id_str).strip().lower()
            sub_row = db.execute(
                select(DimSubject).where(func.lower(DimSubject.name) == search_term)
            ).scalars().first()
            if not sub_row:
                sub_row = db.execute(
                    select(DimSubject).where(func.lower(DimSubject.code) == search_term)
                ).scalars().first()
            if not sub_row:
                all_subs = db.execute(select(DimSubject)).scalars().all()
                matched = [
                    s
                    for s in all_subs
                    if search_term in (s.name or "").lower() or search_term in (s.code or "").lower()
                ]
                if matched:
                    matched.sort(key=lambda x: len(x.name or ""))
                    sub_row = matched[0]
            if sub_row:
                resolved_subject_id = sub_row.id

    return resolved_class_id, resolved_school_year_id, resolved_semester_index, resolved_subject_id


def compute_report_data(db, school_id, report_type, grade_level, class_id=None, semester_id=None, subject_id=None, school_year_id=None):
    """Tổng hợp dữ liệu báo cáo từ schema s360."""
    resolved_class_id, resolved_school_year_id, resolved_semester_index, resolved_subject_id = resolve_parameters(
        db, school_id, class_id, semester_id, subject_id, school_year_id
    )
    class_id = resolved_class_id or class_id
    school_year_id = resolved_school_year_id or school_year_id
    semester_index = resolved_semester_index or 1
    subject_id = resolved_subject_id or subject_id

    year_name = "2025-2026"
    ay = db.get(DimSchoolYear, school_year_id) if school_year_id else None
    if ay:
        year_name = ay.fullname or year_name

    sem_name = f"Học Kỳ {semester_index}"

    selected_grade_name = "Toàn trường"
    if grade_level != "all":
        selected_grade_name = f"Khối {grade_level}"

    selected_class_name = ""
    if class_id and is_valid_int(class_id):
        cls_row = db.get(DimHomeroomClass, int(str(class_id)))
        if cls_row:
            selected_class_name = f" - Lớp {cls_row.fullname or cls_row.code}"

    # Filters for score-based stats
    filters = []
    if school_year_id:
        filters.append(FactGradebooks.school_year_id == school_year_id)
    filters.append(FactGradebooks.semester_index == semester_index)
    if class_id and is_valid_int(class_id):
        filters.append(FactGradebooks.homeroom_class_id == int(str(class_id)))
    elif grade_level != "all":
        try:
            grade_num = int(grade_level)
            class_ids_subq = select(DimHomeroomClass.id).where(
                DimHomeroomClass.so_school_id == school_id, DimHomeroomClass.grade_id == grade_num
            )
            filters.append(FactGradebooks.homeroom_class_id.in_(class_ids_subq))
        except ValueError:
            pass
    final_scope = and_(*filters) if filters else None

    gpa = _average_gpa_s360(db, final_scope)
    at_risk = _at_risk_classes_s360(db, final_scope)

    # Total students
    total_students = 0
    if school_year_id:
        stmt_students_count = select(func.count(DimHomeroomClassStudent.id.distinct())).where(
            DimHomeroomClassStudent.so_school_id == school_id,
            DimHomeroomClassStudent.school_year_id == school_year_id,
            DimHomeroomClassStudent.is_active == 1,
        )
        if class_id and is_valid_int(class_id):
            stmt_students_count = stmt_students_count.where(
                DimHomeroomClassStudent.homeroom_class_id == int(str(class_id))
            )
        elif grade_level != "all":
            try:
                grade_num = int(grade_level)
                stmt_students_count = stmt_students_count.where(
                    DimHomeroomClassStudent.homeroom_class_id.in_(
                        select(DimHomeroomClass.id).where(
                            DimHomeroomClass.so_school_id == school_id, DimHomeroomClass.grade_id == grade_num
                        )
                    )
                )
            except ValueError:
                pass
        total_students = db.scalar(stmt_students_count) or 0

    # Total classes
    total_classes = 0
    if school_year_id:
        stmt_classes_count = select(func.count()).select_from(DimHomeroomClass).where(
            DimHomeroomClass.so_school_id == school_id,
            DimHomeroomClass.school_year_id == school_year_id,
            DimHomeroomClass.is_active == 1,
        )
        if class_id and is_valid_int(class_id):
            stmt_classes_count = stmt_classes_count.where(DimHomeroomClass.id == int(str(class_id)))
        elif grade_level != "all":
            try:
                grade_num = int(grade_level)
                stmt_classes_count = stmt_classes_count.where(DimHomeroomClass.grade_id == grade_num)
            except ValueError:
                pass
        total_classes = db.scalar(stmt_classes_count) or 0

    # Subject averages
    subject_averages = []
    if school_year_id:
        stmt_sub_avg = (
            select(DimSubject.name, func.avg(FactGradebooks.final_grade))
            .select_from(FactGradebooks)
            .join(DimSubject, FactGradebooks.subject_id == DimSubject.id)
            .where(
                FactGradebooks.so_school_id == school_id,
                FactGradebooks.school_year_id == school_year_id,
                FactGradebooks.semester_index == semester_index,
                FactGradebooks.final_grade.isnot(None),
            )
        )
        if class_id and is_valid_int(class_id):
            stmt_sub_avg = stmt_sub_avg.where(FactGradebooks.homeroom_class_id == int(str(class_id)))
        elif grade_level != "all":
            try:
                grade_num = int(grade_level)
                stmt_sub_avg = stmt_sub_avg.where(
                    FactGradebooks.homeroom_class_id.in_(
                        select(DimHomeroomClass.id).where(
                            DimHomeroomClass.so_school_id == school_id, DimHomeroomClass.grade_id == grade_num
                        )
                    )
                )
            except ValueError:
                pass
        for s_name, val in db.execute(stmt_sub_avg.group_by(DimSubject.name)).all():
            if val is not None:
                subject_averages.append({"Môn học": s_name, "ĐTB": round(float(val), 2)})

    # Conduct stats
    conduct_stats = {"TOT": 0, "KHA": 0, "TRUNG_BINH": 0, "YEU": 0}
    if school_year_id:
        stmt_conduct = (
            select(FactOverallAcademicRecords.conduct, func.count(FactOverallAcademicRecords.id))
            .where(
                FactOverallAcademicRecords.so_school_id == school_id,
                FactOverallAcademicRecords.school_year_id == school_year_id,
            )
        )
        if class_id and is_valid_int(class_id):
            stmt_conduct = stmt_conduct.where(FactOverallAcademicRecords.homeroom_class_id == int(str(class_id)))
        elif grade_level != "all":
            try:
                grade_num = int(grade_level)
                stmt_conduct = stmt_conduct.where(
                    FactOverallAcademicRecords.homeroom_class_id.in_(
                        select(DimHomeroomClass.id).where(
                            DimHomeroomClass.so_school_id == school_id, DimHomeroomClass.grade_id == grade_num
                        )
                    )
                )
            except ValueError:
                pass
        for c_enum, count in db.execute(stmt_conduct.group_by(FactOverallAcademicRecords.conduct)).all():
            if c_enum:
                c_key = str(c_enum).split(".")[-1]  # handle enum value
                if c_key in conduct_stats:
                    conduct_stats[c_key] = count

    return {
        "semester_id": f"{school_year_id}-{semester_index}",
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
    }