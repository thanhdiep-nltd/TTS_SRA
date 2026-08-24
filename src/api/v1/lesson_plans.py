# -*- coding: utf-8 -*-
"""API endpoints for Kế hoạch bài dạy (Giáo án) & Lesson Plans."""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.api.deps import get_current_user, get_db
from src.models.tables import User
from src.schemas.lesson_plan import (
    CourseSummary,
    CourseTreeItem,
    GradeOption,
    LessonPlanBrief,
    LessonPlanDetail,
    LessonTargetItem,
    SubjectOption,
    UnitTreeItem,
)

router = APIRouter(prefix="/lesson-plans", tags=["Lesson Plans & Giáo Án"])


@router.get("/subjects", response_model=dict)
def get_subjects_and_grades(
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """Lấy danh sách các Khối và Môn học kèm trạng thái đã có giáo án hay chưa."""
    # 1. Danh sách Khối
    grades_sql = text("""
        SELECT DISTINCT grade_id 
        FROM s360.cm_course 
        WHERE is_deleted = FALSE AND grade_id IS NOT NULL
    """)
    active_grades = {r[0] for r in db.execute(grades_sql).fetchall()}
    
    all_grades = [
        GradeOption(id=g, name=f"Khối {g}", has_lesson_plans=(g in active_grades or g == 6))
        for g in [6, 7, 8, 9, 10, 11, 12]
    ]

    # 2. Danh sách Môn học từ s360.dim_subject
    subj_sql = text("""
        SELECT s.id, s.code, s.name,
               EXISTS(SELECT 1 FROM s360.cm_course c WHERE c.subject_id = s.id AND c.is_deleted = FALSE) as has_plans
        FROM s360.dim_subject s
        WHERE s.is_active = 1
        ORDER BY s.id
    """)
    rows = db.execute(subj_sql).fetchall()

    subjects = [
        SubjectOption(
            id=r[0],
            code=r[1],
            name=r[2],
            has_lesson_plans=bool(r[3]),
        )
        for r in rows
    ]

    return {
        "grades": all_grades,
        "subjects": subjects,
    }


@router.get("/courses", response_model=List[CourseSummary])
def get_courses(
    subject_id: Optional[int] = Query(None, description="Subject ID (106 = Toán 6)"),
    grade_id: Optional[int] = Query(None, description="Grade ID (6 = Khối 6)"),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """Lấy danh sách các khóa học / học kỳ theo môn học và khối."""
    conditions = ["c.is_deleted = FALSE"]
    params = {}

    if subject_id:
        conditions.append("c.subject_id = :subject_id")
        params["subject_id"] = subject_id
    if grade_id:
        conditions.append("c.grade_id = :grade_id")
        params["grade_id"] = grade_id

    where_clause = " AND ".join(conditions)

    sql = text(f"""
        SELECT 
            c.id,
            c.code,
            c.name,
            c.period,
            c.description,
            COUNT(DISTINCT u.id) as unit_count,
            COUNT(DISTINCT l.id) as lesson_count
        FROM s360.cm_course c
        LEFT JOIN s360.cm_unit u ON u.course_id = c.id AND u.is_deleted = FALSE
        LEFT JOIN s360.cm_lesson l ON l.unit_id = u.id AND l.is_deleted = FALSE
        WHERE {where_clause}
        GROUP BY c.id, c.code, c.name, c.period, c.description
        ORDER BY c.order_number, c.id
    """)
    rows = db.execute(sql, params).fetchall()

    return [
        CourseSummary(
            id=r[0],
            code=r[1],
            name=r[2],
            period=float(r[3] or 0),
            description=r[4],
            unit_count=r[5],
            lesson_count=r[6],
        )
        for r in rows
    ]


@router.get("/tree", response_model=Optional[CourseTreeItem])
def get_course_tree(
    course_id: Optional[int] = Query(None, description="Course ID (1000 = HK1, 1001 = HK2)"),
    subject_id: Optional[int] = Query(None, description="Subject ID"),
    grade_id: Optional[int] = Query(None, description="Grade ID"),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """Lấy toàn bộ cây phân cấp Chương & Bài học kèm tóm tắt giáo án cho một khóa học."""
    # Nếu không truyền course_id, lấy course đầu tiên phù hợp với subject_id / grade_id
    if not course_id:
        conditions = ["is_deleted = FALSE"]
        params = {}
        if subject_id:
            conditions.append("subject_id = :subject_id")
            params["subject_id"] = subject_id
        if grade_id:
            conditions.append("grade_id = :grade_id")
            params["grade_id"] = grade_id

        where_clause = " AND ".join(conditions)
        c_row = db.execute(
            text(f"SELECT id FROM s360.cm_course WHERE {where_clause} ORDER BY order_number, id LIMIT 1"),
            params,
        ).fetchone()
        if not c_row:
            return None
        course_id = c_row[0]

    # 1. Lấy thông tin Course
    course_row = db.execute(
        text("SELECT id, code, name, period, description FROM s360.cm_course WHERE id = :course_id"),
        {"course_id": course_id},
    ).fetchone()
    if not course_row:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy course_id = {course_id}")

    # 2. Lấy danh sách Chương (cm_unit)
    units_rows = db.execute(
        text("""
            SELECT id, code, name, order_number, period 
            FROM s360.cm_unit 
            WHERE course_id = :course_id AND is_deleted = FALSE
            ORDER BY order_number, id
        """),
        {"course_id": course_id},
    ).fetchall()

    # 3. Lấy toàn bộ Bài học (cm_lesson) kèm thông tin giáo án & mục tiêu (1 row duy nhất cho mỗi lesson)
    lessons_rows = db.execute(
        text("""
            SELECT 
                l.id,
                l.code,
                l.name,
                l.period,
                l.order_number,
                l.unit_id,
                (
                    SELECT cu.id FROM public.curriculum_units cu 
                    WHERE LOWER(TRIM(cu.name)) = LOWER(TRIM(l.name)) 
                       OR LOWER(TRIM(l.name)) LIKE '%' || LOWER(TRIM(cu.name)) || '%'
                    ORDER BY LENGTH(cu.name) DESC LIMIT 1
                ) as curriculum_unit_id,
                (
                    SELECT cu.name FROM public.curriculum_units cu 
                    WHERE LOWER(TRIM(cu.name)) = LOWER(TRIM(l.name)) 
                       OR LOWER(TRIM(l.name)) LIKE '%' || LOWER(TRIM(cu.name)) || '%'
                    ORDER BY LENGTH(cu.name) DESC LIMIT 1
                ) as curriculum_unit_name,
                LENGTH(COALESCE(lp.content_own, '')) as content_len,
                (SELECT COUNT(*) FROM s360.cm_lessontarget lt WHERE lt.lesson_id = l.id AND lt.is_deleted = FALSE) as target_count
            FROM s360.cm_lesson l
            JOIN s360.cm_unit u ON l.unit_id = u.id
            LEFT JOIN s360.cm_lessonplan lp ON lp.lesson_id = l.id AND lp.is_deleted = FALSE
            WHERE u.course_id = :course_id AND l.is_deleted = FALSE
            ORDER BY l.unit_id, l.order_number, l.id
        """),
        {"course_id": course_id},
    ).fetchall()

    # Nhóm bài học theo unit_id
    lessons_by_unit = {}
    for r in lessons_rows:
        brief = LessonPlanBrief(
            id=r[0],
            code=r[1],
            name=r[2],
            period=float(r[3] or 0),
            order_number=r[4],
            unit_id=r[5],
            curriculum_unit_id=r[6],
            curriculum_unit_name=r[7],
            has_plan=r[8] > 0,
            target_count=r[9] or 0,
            content_length=r[8],
        )
        lessons_by_unit.setdefault(r[5], []).append(brief)

    units = [
        UnitTreeItem(
            id=u[0],
            code=u[1],
            name=u[2],
            order_number=u[3],
            period=float(u[4] or 0),
            lessons=lessons_by_unit.get(u[0], []),
        )
        for u in units_rows
    ]

    return CourseTreeItem(
        id=course_row[0],
        code=course_row[1],
        name=course_row[2],
        period=float(course_row[3] or 0),
        description=course_row[4],
        units=units,
    )


@router.get("/{lesson_id}", response_model=LessonPlanDetail)
def get_lesson_plan_detail(
    lesson_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """Lấy nội dung chi tiết của một Giáo án bài dạy (gồm markdown text, mục tiêu, SGK)."""
    # 1. Lấy thông tin bài học & giáo án
    sql = text("""
        SELECT 
            l.id as lesson_id,
            l.name as lesson_name,
            l.code as lesson_code,
            l.period as lesson_period,
            l.order_number as lesson_order,
            u.id as unit_id,
            u.name as unit_name,
            u.code as unit_code,
            c.id as course_id,
            c.name as course_name,
            c.code as course_code,
            lp.id as plan_id,
            lp.name as plan_name,
            lp.content_own as content_own,
            lp.description as plan_desc
        FROM s360.cm_lesson l
        JOIN s360.cm_unit u ON l.unit_id = u.id
        JOIN s360.cm_course c ON u.course_id = c.id
        LEFT JOIN s360.cm_lessonplan lp ON lp.lesson_id = l.id AND lp.is_deleted = FALSE
        WHERE l.id = :lesson_id
    """)
    row = db.execute(sql, {"lesson_id": lesson_id}).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy bài học có ID = {lesson_id}")

    # 2. Tìm mỏ neo SGK tương ứng trong curriculum_units
    lesson_name = row[1]
    cu_sql = text("""
        SELECT id, name, summary, keywords 
        FROM public.curriculum_units 
        WHERE (
            LOWER(TRIM(name)) = LOWER(TRIM(:name)) OR
            LOWER(TRIM(:name)) LIKE '%' || LOWER(TRIM(name)) || '%' OR
            LOWER(TRIM(name)) LIKE '%' || LOWER(TRIM(:name)) || '%'
        )
        ORDER BY LENGTH(name) DESC
        LIMIT 1
    """)
    cu_row = db.execute(cu_sql, {"name": lesson_name}).fetchone()

    curriculum_unit_id = cu_row[0] if cu_row else None
    curriculum_unit_name = cu_row[1] if cu_row else None
    curriculum_summary = cu_row[2] if cu_row else None
    curriculum_keywords = cu_row[3] if cu_row and cu_row[3] else []

    # 3. Lấy danh sách mục tiêu (cm_lessontarget)
    tgt_sql = text("""
        SELECT id, code, name, description, order_number
        FROM s360.cm_lessontarget
        WHERE lesson_id = :lesson_id AND is_deleted = FALSE
        ORDER BY order_number, id
    """)
    tgt_rows = db.execute(tgt_sql, {"lesson_id": lesson_id}).fetchall()
    targets = [
        LessonTargetItem(
            id=t[0],
            code=t[1],
            name=t[2],
            description=t[3],
            order_number=t[4],
        )
        for t in tgt_rows
    ]

    # 4. Đếm số câu hỏi LMS liên quan trong lms_question_bank
    lms_q_count = 0
    if curriculum_unit_id:
        count_sql = text("""
            SELECT COUNT(*) 
            FROM public.lms_question_bank 
            WHERE unit_id = :unit_id OR lesson_id = :unit_id
        """)
        lms_q_count = db.execute(count_sql, {"unit_id": curriculum_unit_id}).scalar() or 0

    return LessonPlanDetail(
        lesson_id=row[0],
        lesson_name=row[1],
        lesson_code=row[2],
        period=float(row[3] or 0),
        order_number=row[4],
        unit_id=row[5],
        unit_name=row[6],
        unit_code=row[7],
        course_id=row[8],
        course_name=row[9],
        course_code=row[10],
        curriculum_unit_id=curriculum_unit_id,
        curriculum_unit_name=curriculum_unit_name,
        curriculum_summary=curriculum_summary,
        curriculum_keywords=curriculum_keywords,
        plan_id=row[11],
        plan_name=row[12],
        content_own=row[13],
        description=row[14],
        targets=targets,
        related_lms_questions_count=lms_q_count,
    )


@router.get("/by-curriculum/{unit_id}", response_model=LessonPlanDetail)
def get_lesson_plan_by_curriculum(
    unit_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """Tìm và lấy chi tiết Giáo án dựa trên curriculum_units.id (Dùng cho Deep-link từ Knowledge Gaps)."""
    # 1. Lấy tên từ curriculum_units
    cu_row = db.execute(
        text("SELECT name FROM public.curriculum_units WHERE id = :unit_id"),
        {"unit_id": unit_id},
    ).fetchone()
    if not cu_row:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy curriculum_unit có ID = {unit_id}")
    
    cu_name = cu_row[0]

    # 2. Tìm cm_lesson có tên tương ứng
    l_row = db.execute(
        text("""
            SELECT id FROM s360.cm_lesson 
            WHERE LOWER(TRIM(name)) = LOWER(TRIM(:name)) 
               OR LOWER(TRIM(:name)) LIKE '%' || LOWER(TRIM(name)) || '%'
               OR LOWER(TRIM(name)) LIKE '%' || LOWER(TRIM(:name)) || '%'
            ORDER BY LENGTH(name) DESC
            LIMIT 1
        """),
        {"name": cu_name},
    ).fetchone()

    if not l_row:
        # Fallback: tìm theo ID nếu trùng
        l_row = db.execute(
            text("SELECT id FROM s360.cm_lesson WHERE id = :unit_id"),
            {"unit_id": unit_id},
        ).fetchone()

    if not l_row:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy giáo án tương ứng cho bài học '{cu_name}'")

    return get_lesson_plan_detail(lesson_id=l_row[0], db=db, _user=_user)
