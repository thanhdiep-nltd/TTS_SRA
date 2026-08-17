"""src/api/v1/pass_fail_forecast.py — API dự đoán pass/fail đề cuối kỳ (M4).

GV upload đề cuối kỳ (đã map unit qua exam_competencies) → dự đoán bao nhiêu học
sinh trượt/pass dựa năng lực từng unit (từ fact_gradebooks) + độ khó CDI.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.api.deps import CurrentUser, get_db
from src.schemas.pass_fail_forecast import PassFailForecastResult, StudentForecastRow
from src.services.pass_fail_forecast import ExamUnit, StudentAbility, forecast_exam, summarize

router = APIRouter(prefix="/pass-fail-forecast", tags=["Pass/Fail Forecast"])


def _resolve_school_year(db: Session, school_year_id: int | None) -> int:
    """Lấy năm học hiện hành nếu không truyền."""
    if school_year_id and school_year_id > 0:
        return school_year_id
    row = db.execute(text("SELECT id FROM s360.dim_school_year WHERE is_current = 1 LIMIT 1")).fetchone()
    return int(row.id) if row and row.id is not None else 2025


def _load_exam_units(db: Session, exam_paper_id: int) -> list[ExamUnit]:
    """Load trọng số unit của đề (từ exam_competencies)."""
    rows = db.execute(
        text("SELECT unit_id, weight FROM public.exam_competencies WHERE exam_paper_id = :eid"),
        {"eid": exam_paper_id},
    ).fetchall()
    return [ExamUnit(unit_id=r.unit_id, weight=float(r.weight) if r.weight is not None else 0.0) for r in rows]


def _load_cdi(db: Session, exam_paper_id: int) -> float | None:
    """Load CDI của đề (NULL nếu chưa phân tích nội dung)."""
    row = db.execute(
        text("SELECT content_difficulty FROM public.exam_papers WHERE id = :eid"),
        {"eid": exam_paper_id},
    ).fetchone()
    return float(row.content_difficulty) if row and row.content_difficulty is not None else None


def _calculate_forecast(
    db: Session,
    exam_paper_id: int,
    subject_id: int,
    school_year_id: int,
    semester_index: int,
    school_id: int | None = None,
) -> PassFailForecastResult:
    units = _load_exam_units(db, exam_paper_id)
    cdi = _load_cdi(db, exam_paper_id)

    if not units:
        return PassFailForecastResult(exam_paper_id=exam_paper_id, cdi=cdi, total=0, pass_count=0, fail_count=0)

    # Năng lực từng unit của mọi học sinh (từ fact_gradebooks đã khoá) kèm Tenant isolation.
    school_cond = "AND fg.so_school_id = :school_id" if school_id else ""
    params = {"sid": subject_id, "sy": school_year_id, "sem": semester_index}
    if school_id:
        params["school_id"] = school_id

    rows = db.execute(
        text(f"""
            SELECT fg.student_code, fg.final_grade, fg.max_grade
            FROM s360.fact_gradebooks fg
            WHERE fg.subject_id = :sid
              AND fg.school_year_id = :sy AND fg.semester_index = :sem
              AND fg.is_locked = 1
              {school_cond}
        """),
        params,
    ).fetchall()

    if not rows:
        return PassFailForecastResult(exam_paper_id=exam_paper_id, cdi=cdi, total=0, pass_count=0, fail_count=0)

    students: list[StudentAbility] = []
    for r in rows:
        grade = float(r.final_grade) if r.final_grade is not None else 0.0
        ability = {u.unit_id: grade for u in units}
        students.append(StudentAbility(student_code=r.student_code, ability=ability))

    forecasts = forecast_exam(students, units, cdi)
    summary = summarize(forecasts)

    student_rows = [
        StudentForecastRow(
            student_code=f.student_code,
            predicted_score=f.predicted_score,
            verdict=f.verdict,
        )
        for f in forecasts
    ]

    return PassFailForecastResult(
        exam_paper_id=exam_paper_id,
        cdi=cdi,
        total=summary["total"],
        pass_count=summary["pass"],
        fail_count=summary["fail"],
        borderline_count=summary["borderline"],
        fail_rate=summary["fail_rate"],
        students=student_rows,
    )


@router.get("/by-subject", response_model=PassFailForecastResult)
def forecast_by_subject(
    subject_id: int = Query(..., description="ID môn học"),
    grade_id: int | None = Query(None, description="Khối lớp (tùy chọn)"),
    school_year_id: int | None = Query(None, description="Năm học"),
    semester_index: int = Query(1, description="Học kỳ"),
    current_user: CurrentUser = None,
    db: Session = Depends(get_db),
):
    """Tìm đề cuối kỳ mới nhất của môn rồi dự đoán pass/fail."""
    sy_id = _resolve_school_year(db, school_year_id)
    school_id = getattr(current_user, "so_school_id", None)

    school_cond = "AND (ep.school_id IS NULL OR ep.school_id = :school_id)" if school_id else ""
    params = {"sid": subject_id, "sem": semester_index}
    if school_id:
        params["school_id"] = school_id

    exam_row = db.execute(
        text(f"""
            SELECT ep.id
            FROM public.exam_papers ep
            WHERE ep.subject_id = :sid
              AND ep.semester_id = :sem
              {school_cond}
            ORDER BY CASE ep.score_category WHEN 'FINAL' THEN 0 WHEN 'MIDTERM' THEN 1 ELSE 2 END, ep.created_at DESC
            LIMIT 1
        """),
        params,
    ).fetchone()

    if not exam_row:
        return PassFailForecastResult(exam_paper_id=0, total=0, pass_count=0, fail_count=0)

    return _calculate_forecast(db, int(exam_row.id), subject_id, sy_id, semester_index, school_id)


@router.get("/{exam_paper_id}", response_model=PassFailForecastResult)
def forecast_pass_fail(
    exam_paper_id: int,
    subject_id: int = Query(..., description="ID môn học (s360.dim_subject.id)"),
    school_year_id: int | None = Query(None, description="Năm học"),
    semester_index: int = Query(1),
    current_user: CurrentUser = None,
    db: Session = Depends(get_db),
):
    """Dự đoán pass/fail cho 1 đề cuối kỳ đã map unit."""
    sy_id = _resolve_school_year(db, school_year_id)
    school_id = getattr(current_user, "so_school_id", None)
    return _calculate_forecast(db, exam_paper_id, subject_id, sy_id, semester_index, school_id)

