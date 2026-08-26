"""src/api/v1/pass_fail_forecast.py — API dự đoán pass/fail đề cuối kỳ (M4).

GV upload đề cuối kỳ (đã map unit qua exam_competencies, cấp bài) → dự đoán bao
nhiêu học sinh trượt/pass dựa năng lực LMS cấp bài (student_unit_mastery.raw_mastery)
+ trọng số unit của đề + độ khó CDI.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.api.deps import CurrentUser, get_db
from src.schemas.pass_fail_forecast import PassFailForecastResult, StudentForecastRow
from src.services.pass_fail_forecast import (
    ExamUnit,
    StudentAbility,
    compute_weak_units,
    forecast_exam,
    resolve_abilities,
    summarize,
)

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

    lesson_ids = [u.unit_id for u in units]

    # Map bài → chương (để fallback TB chương) — 1 query batch.
    parent_rows = db.execute(
        text(
            """
            SELECT id, parent_id FROM public.curriculum_units
            WHERE id = ANY(:ids) AND parent_id IS NOT NULL
            """
        ),
        {"ids": lesson_ids},
    ).fetchall()
    lesson_to_chapter = {int(r.id): int(r.parent_id) for r in parent_rows}

    # Năng lực LMS cấp bài — 1 query batch cho toàn bộ học sinh (không N+1), kèm tenant.
    school_cond_sum = "AND sum.so_school_id = :school_id" if school_id else ""
    sum_params: dict = {"sid": subject_id, "sem": semester_index}
    if school_id:
        sum_params["school_id"] = school_id
    sum_rows = db.execute(
        text(
            f"""
            SELECT sum.student_code, sum.unit_id, sum.raw_mastery, sum.integrity_status, sum.evidence_detail
            FROM public.student_unit_mastery sum
            WHERE sum.subject_id = :sid AND sum.semester_index = :sem
              AND sum.raw_mastery IS NOT NULL
              {school_cond_sum}
            """
        ),
        sum_params,
    ).fetchall()

    raw_by_student: dict[str, dict[int, float]] = {}
    student_discrepancy: dict[str, dict] = {}
    lesson_id_set = set(lesson_ids)

    for r in sum_rows:
        sc = str(r.student_code)
        uid = int(r.unit_id)
        if uid in lesson_id_set:
            raw_by_student.setdefault(sc, {})[uid] = float(r.raw_mastery)

        if sc not in student_discrepancy:
            ev = r.evidence_detail if isinstance(r.evidence_detail, dict) else {}
            if isinstance(ev, str):
                try:
                    ev = json.loads(ev)
                except Exception:
                    ev = {}
            exam_m = ev.get("exam_mastery") if isinstance(ev, dict) else None
            student_discrepancy[sc] = {
                "exam_score": round(float(exam_m) * 10, 1) if exam_m is not None else None,
                "statuses": set(),
                "raw_scores": [],
            }
        student_discrepancy[sc]["raw_scores"].append(float(r.raw_mastery) * 10)
        if r.integrity_status:
            student_discrepancy[sc]["statuses"].add(r.integrity_status)

    lms_students = set(raw_by_student)

    # Roster = distinct (LMS ∪ fact_gradebooks khoá); giữ HS không-LMS hiện diện → INSUFFICIENT.
    school_cond_fg = "AND fg.so_school_id = :school_id" if school_id else ""
    fg_params: dict = {"sid": subject_id, "sy": school_year_id, "sem": semester_index}
    if school_id:
        fg_params["school_id"] = school_id
    roster = db.execute(
        text(
            f"""
            SELECT DISTINCT ON (fg.student_code) fg.student_code
            FROM s360.fact_gradebooks fg
            WHERE fg.subject_id = :sid AND fg.school_year_id = :sy
              AND fg.semester_index = :sem AND fg.is_locked = 1
              {school_cond_fg}
            ORDER BY fg.student_code
            """
        ),
        fg_params,
    ).fetchall()
    roster_codes = sorted(lms_students | {r.student_code for r in roster})
    if not roster_codes:
        return PassFailForecastResult(exam_paper_id=exam_paper_id, cdi=cdi, total=0, pass_count=0, fail_count=0)

    students: list[StudentAbility] = []
    for code in roster_codes:
        raw = raw_by_student.get(code, {})
        abilities = resolve_abilities(raw, lesson_ids, lesson_to_chapter)
        # abilities=None → toàn bộ bài = None (HS không LMS) → predict trả None → INSUFFICIENT.
        students.append(
            StudentAbility(
                student_code=code,
                ability={u.unit_id: (abilities.get(u.unit_id) if abilities else None) for u in units},
            )
        )

    forecasts = forecast_exam(students, units, cdi)
    summary = summarize(forecasts)

    # Batch tra tên HS và lớp — 1 query từ dim_homeroom_class_student.
    code_to_info: dict[str, dict] = {}
    if roster_codes:
        info_rows = db.execute(
            text(
                """
                SELECT DISTINCT ON (dhcs.student_code)
                       dhcs.student_code,
                       COALESCE(dhcs.student_name, st.full_name, dhcs.student_code) AS student_name,
                       dhcs.class_name
                FROM s360.dim_homeroom_class_student dhcs
                LEFT JOIN public.students st ON dhcs.student_code = st.student_code
                WHERE dhcs.student_code = ANY(:codes)
                ORDER BY dhcs.student_code, dhcs.id DESC
                """
            ),
            {"codes": roster_codes},
        ).fetchall()
        code_to_info = {
            r.student_code: {
                "student_name": r.student_name,
                "class_name": r.class_name,
            }
            for r in info_rows
        }

    # Batch tra tên unit — 1 query.
    unit_name_rows = db.execute(
        text("SELECT id, name FROM public.curriculum_units WHERE id = ANY(:ids)"),
        {"ids": lesson_ids},
    ).fetchall()
    unit_names: dict[int, str] = {int(r.id): str(r.name) for r in unit_name_rows if r.name}

    students_by_code = {s.student_code: s for s in students}
    student_rows = []
    for f in forecasts:
        st_obj = students_by_code.get(f.student_code)
        ab_dict = (
            {u_id: (round(ab, 2) if ab is not None else None) for u_id, ab in st_obj.ability.items()}
            if st_obj and st_obj.ability
            else {}
        )

        disc_data = student_discrepancy.get(f.student_code, {})
        ex_score = disc_data.get("exam_score")
        raw_list = disc_data.get("raw_scores", [])
        lms_sc = round(sum(raw_list) / len(raw_list), 1) if raw_list else None
        statuses = disc_data.get("statuses", set())

        integ_status = "OK"
        disc_warn = None

        if ex_score is not None and lms_sc is not None:
            diff = lms_sc - ex_score
            if diff <= -3.0:
                integ_status = "LOW_ENGAGEMENT"
                disc_warn = f"Chênh lệch cao: Điểm thi {ex_score}đ vs LMS {lms_sc}đ (Ít luyện tập LMS). Dự báo có thể thấp hơn phong độ thi thật."
            elif diff >= 3.0:
                integ_status = "LMS_EXCEEDS_EXAM"
                disc_warn = f"Chênh lệch cao: Điểm LMS {lms_sc}đ vs Điểm thi {ex_score}đ (LMS vượt trội). Dự báo có thể cao hơn phong độ thi thật."
        elif ex_score is None:
            integ_status = "LMS_ONLY"

        student_rows.append(
            StudentForecastRow(
                student_code=f.student_code,
                student_name=code_to_info.get(f.student_code, {}).get("student_name"),
                class_name=code_to_info.get(f.student_code, {}).get("class_name"),
                predicted_score=f.predicted_score,
                verdict=f.verdict,
                weak_units=compute_weak_units(
                    st_obj or students[0],
                    units,
                    unit_names,
                ),
                unit_abilities=ab_dict,
                integrity_status=integ_status,
                exam_score=ex_score,
                lms_score=lms_sc,
                discrepancy_warning=disc_warn,
            )
        )

    return PassFailForecastResult(
        exam_paper_id=exam_paper_id,
        cdi=cdi,
        total=summary["total"],
        pass_count=summary["pass"],
        fail_count=summary["fail"],
        borderline_count=summary["borderline"],
        insufficient_count=summary["insufficient"],
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

