from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import and_, case, func, select, text
from sqlalchemy.orm import Session

from src.api.deps import CurrentUser, get_db
from src.models.enums import ScoreCategory, ScoreStatus
from src.models.tables import AcademicYear, Class, Grade, Score, Semester, Student, Subject
from src.schemas.analytics import (
    AcademicDivergenceRow,
    DashboardOverview,
    GpaTrendPoint,
    GradeDistributionRow,
    GradeInflationRow,
    GradeTrendPoint,
    LearningMomentumRow,
    SemesterOption,
    StudentArchetypeRow,
    SubjectOption,
)
from src.services import rbac, scoring

router = APIRouter(prefix="/analytics", tags=["Analytics"])

_FINAL = ScoreCategory.FINAL
_APPROVED = ScoreStatus.APPROVED

_BUCKET = case(
    (Score.value >= 8, "gioi"),
    (Score.value >= 6.5, "kha"),
    (Score.value >= 5, "trung_binh"),
    else_="yeu",
)


def _average_gpa(db: Session, scope) -> float | None:
    stmt = select(func.avg(Score.value)).where(Score.status == _APPROVED, Score.score_category == _FINAL)
    if scope is not None:
        stmt = stmt.where(scope)
    val = db.scalar(stmt)
    return round(float(val), 2) if val is not None else None


def _gpa_trend(db: Session, scope) -> list[GpaTrendPoint]:
    stmt = select(Score.score_category, Score.column_index, func.avg(Score.value)).where(Score.status == _APPROVED)
    if scope is not None:
        stmt = stmt.where(scope)
    averages = {
        (cat, idx): avg for cat, idx, avg in db.execute(stmt.group_by(Score.score_category, Score.column_index)).all()
    }
    return [
        GpaTrendPoint(name=scoring.column_label(cat, idx), gpa=round(float(averages[(cat, idx)]), 2))
        for cat, idx in scoring.SCORE_COLUMNS
        if (cat, idx) in averages
    ]


def _grade_distribution(db: Session, scope) -> list[GradeDistributionRow]:
    stmt = (
        select(Grade.name, _BUCKET.label("bucket"), func.count())
        .select_from(Score)
        .join(Class, Class.id == Score.class_id)
        .join(Grade, Grade.id == Class.grade_id)
        .where(Score.status == _APPROVED, Score.score_category == _FINAL)
    )
    if scope is not None:
        stmt = stmt.where(scope)
    rows: dict[str, GradeDistributionRow] = {}
    for grade_name, bucket, count in db.execute(stmt.group_by(Grade.name, _BUCKET)).all():
        row = rows.setdefault(grade_name, GradeDistributionRow(name=grade_name, gioi=0, kha=0, trung_binh=0, yeu=0))
        setattr(row, bucket, count)
    return list(rows.values())


def _at_risk_classes(db: Session, scope) -> int:
    sub = select(Score.class_id).where(Score.status == _APPROVED, Score.score_category == _FINAL)
    if scope is not None:
        sub = sub.where(scope)
    sub = sub.group_by(Score.class_id).having(func.avg(Score.value) < 5.0)
    return db.scalar(select(func.count()).select_from(sub.subquery("at_risk"))) or 0


def _grade_trend(db: Session, scope) -> tuple[list[GradeTrendPoint], list[str]]:
    """Điểm TB của từng khối qua các đầu điểm (Miệng→Cuối kỳ) — học lực theo thời gian."""
    stmt = (
        select(Grade.name, Score.score_category, Score.column_index, func.avg(Score.value))
        .select_from(Score)
        .join(Class, Class.id == Score.class_id)
        .join(Grade, Grade.id == Class.grade_id)
        .where(Score.status == _APPROVED)
    )
    if scope is not None:
        stmt = stmt.where(scope)
    by_col: dict[tuple, dict[str, float]] = {}
    grade_names: set[str] = set()
    for grade_name, cat, idx, avg in db.execute(
        stmt.group_by(Grade.name, Score.score_category, Score.column_index)
    ).all():
        by_col.setdefault((cat, idx), {})[grade_name] = round(float(avg), 2)
        grade_names.add(grade_name)
    points = [
        GradeTrendPoint(name=scoring.column_label(cat, idx), values=by_col[(cat, idx)])
        for cat, idx in scoring.SCORE_COLUMNS
        if (cat, idx) in by_col
    ]
    return points, sorted(grade_names)


@router.get("/overview", response_model=DashboardOverview)
def overview(user: CurrentUser, semester_id: UUID | None = None, db: Session = Depends(get_db)):
    """Số liệu tổng quan cho dashboard (đã áp scope RLS theo vai trò và trường).

    `semester_id` lọc điểm theo đúng học kỳ đang chọn trên dashboard; nếu bỏ trống, giữ hành vi
    cũ (gộp mọi học kỳ) để tương thích ngược với client chưa gửi tham số.
    """
    rls_scope = rbac.accessible_score_filter(db, user)
    sem_scope = Score.semester_id == semester_id if semester_id else None
    if rls_scope is not None and sem_scope is not None:
        scope = and_(rls_scope, sem_scope)
    else:
        scope = rls_scope if rls_scope is not None else sem_scope
    grade_trend, grade_names = _grade_trend(db, scope)

    # Lọc học sinh theo trường của user
    total_students_stmt = (
        select(func.count())
        .select_from(Student)
        .where(Student.is_active.is_(True), Student.school_id == user.school_id)
    )
    total_students = db.scalar(total_students_stmt) or 0

    # Lọc lớp học theo trường của user (join qua Grade)
    total_classes_stmt = (
        select(func.count())
        .select_from(Class)
        .join(Grade, Class.grade_id == Grade.id)
        .where(Grade.school_id == user.school_id)
    )
    total_classes = db.scalar(total_classes_stmt) or 0
    return DashboardOverview(
        total_students=total_students,
        total_classes=total_classes,
        average_gpa=_average_gpa(db, scope),
        at_risk_classes=_at_risk_classes(db, scope),
        grade_distribution=_grade_distribution(db, scope),
        gpa_trend=_gpa_trend(db, scope),
        grade_names=grade_names,
        grade_trend=grade_trend,
    )


@router.get("/semesters", response_model=list[SemesterOption])
def list_semesters(user: CurrentUser, db: Session = Depends(get_db)):
    """Lấy danh sách các học kỳ của trường user để làm bộ lọc."""
    stmt = (
        select(Semester.id, Semester.name, AcademicYear.name.label("academic_year"), Semester.is_current)
        .join(AcademicYear, Semester.academic_year_id == AcademicYear.id)
        .where(AcademicYear.school_id == user.school_id)
        .order_by(AcademicYear.name.desc(), Semester.number.desc())
    )
    return [
        SemesterOption(id=row.id, name=row.name, academic_year=row.academic_year, is_current=row.is_current)
        for row in db.execute(stmt).all()
    ]


@router.get("/subjects", response_model=list[SubjectOption])
def list_subjects(user: CurrentUser, db: Session = Depends(get_db)):
    """Lấy danh sách các môn học của trường user để làm bộ lọc."""
    stmt = (
        select(Subject.id, Subject.name, Subject.code)
        .where(Subject.school_id == user.school_id, Subject.is_active.is_(True))
        .order_by(Subject.name)
    )
    return [SubjectOption(id=row.id, name=row.name, code=row.code) for row in db.execute(stmt).all()]


@router.get("/academic-divergence", response_model=list[AcademicDivergenceRow])
def academic_divergence(subject_id: UUID, semester_id: UUID, user: CurrentUser, db: Session = Depends(get_db)):
    """Tính toán chỉ số dị biệt học thuật tập thể (Delta G) của từng lớp trong trường của user."""
    sql = """
    WITH student_subject_averages AS (
        SELECT s.student_id,
               s.class_id,
               s.subject_id,
               ROUND(
                   SUM(CASE s.score_category
                       WHEN 'ORAL' THEN s.value WHEN 'REGULAR' THEN s.value
                       WHEN 'MIDTERM' THEN 2 * s.value WHEN 'FINAL' THEN 3 * s.value END)
                   / NULLIF(SUM(CASE s.score_category
                       WHEN 'ORAL' THEN 1 WHEN 'REGULAR' THEN 1
                       WHEN 'MIDTERM' THEN 2 WHEN 'FINAL' THEN 3 END), 0)
               , 2) AS avg_score
        FROM scores s
        JOIN classes c ON s.class_id = c.id
        JOIN grades g ON c.grade_id = g.id
        JOIN subjects sub ON s.subject_id = sub.id
        WHERE g.school_id = :school_id
          AND s.semester_id = :semester_id
          AND s.status = 'APPROVED'
          AND sub.assessment_type = 'SCORED'
        GROUP BY s.student_id, s.class_id, s.subject_id
    ),
    student_gpao AS (
        SELECT a.student_id,
               a.class_id,
               a.subject_id,
               a.avg_score AS target_avg,
               (
                   SELECT AVG(b.avg_score)
                   FROM student_subject_averages b
                   WHERE b.student_id = a.student_id
                     AND b.subject_id != a.subject_id
               ) AS gpao
        FROM student_subject_averages a
        WHERE a.subject_id = :target_subject_id
    )
    SELECT c.name AS class_name,
           ROUND(AVG(target_avg)::numeric, 2) AS avg_subject_score,
           ROUND(AVG(gpao)::numeric, 2) AS avg_gpao,
           ROUND(AVG(target_avg - gpao)::numeric, 2) AS delta_g
    FROM student_gpao sg
    JOIN classes c ON sg.class_id = c.id
    GROUP BY c.name
    ORDER BY c.name;
    """
    rows = db.execute(
        text(sql), {"school_id": user.school_id, "semester_id": semester_id, "target_subject_id": subject_id}
    ).all()
    return [
        AcademicDivergenceRow(
            class_name=r.class_name,
            avg_subject_score=float(r.avg_subject_score or 0),
            avg_gpao=float(r.avg_gpao or 0),
            delta_g=float(r.delta_g or 0),
        )
        for r in rows
    ]


@router.get("/grade-inflation", response_model=list[GradeInflationRow])
def grade_inflation(subject_id: UUID, semester_id: UUID, user: CurrentUser, db: Session = Depends(get_db)):
    """Tính toán chỉ số lạm phát điểm (GDI) của từng lớp trong trường của user."""
    sql = """
    WITH student_subject_grades AS (
        SELECT s.student_id,
               s.subject_id,
               s.semester_id,
               s.class_id,
               c.grade_id,
               AVG(CASE WHEN s.score_category = 'REGULAR' THEN s.value END) AS tx_mean,
               MAX(CASE WHEN s.score_category = 'FINAL' THEN s.value END) AS ck_score
        FROM scores s
        JOIN classes c ON s.class_id = c.id
        JOIN grades g ON c.grade_id = g.id
        WHERE g.school_id = :school_id
          AND s.semester_id = :semester_id
          AND s.subject_id = :subject_id
          AND s.status = 'APPROVED'
        GROUP BY s.student_id, s.subject_id, s.semester_id, s.class_id, c.grade_id
    ),
    grade_stats AS (
        SELECT grade_id,
               AVG(tx_mean) AS mean_tx,
               COALESCE(STDDEV_SAMP(tx_mean), 1.0) AS std_tx,
               AVG(ck_score) AS mean_ck,
               COALESCE(STDDEV_SAMP(ck_score), 1.0) AS std_ck
        FROM student_subject_grades
        GROUP BY grade_id
    ),
    z_scores AS (
        SELECT sg.class_id,
               CASE WHEN gs.std_tx > 0 THEN (sg.tx_mean - gs.mean_tx) / gs.std_tx ELSE 0 END AS z_tx,
               CASE WHEN gs.std_ck > 0 THEN (sg.ck_score - gs.mean_ck) / gs.std_ck ELSE 0 END AS z_ck
        FROM student_subject_grades sg
        JOIN grade_stats gs ON sg.grade_id = gs.grade_id
    )
    SELECT c.name AS class_name,
           ROUND(AVG(z_tx - z_ck)::numeric, 2) AS gdi
    FROM z_scores zs
    JOIN classes c ON zs.class_id = c.id
    GROUP BY c.name
    ORDER BY c.name;
    """
    rows = db.execute(
        text(sql), {"school_id": user.school_id, "semester_id": semester_id, "subject_id": subject_id}
    ).all()
    return [GradeInflationRow(class_name=r.class_name, gdi=float(r.gdi or 0)) for r in rows]


@router.get("/momentum", response_model=list[LearningMomentumRow])
def learning_momentum(subject_id: UUID, semester_id: UUID, user: CurrentUser, db: Session = Depends(get_db)):
    """Phân phối động lượng học tập (Momentum) sau kỳ thi giữa kỳ của các lớp trong trường."""
    sql = """
    WITH student_momentum AS (
        SELECT s.student_id,
               s.class_id,
               (
                   COALESCE(AVG(CASE WHEN s.score_category = 'REGULAR' AND s.column_index IN (3, 4) THEN s.value END), 0) -
                   COALESCE(AVG(CASE WHEN s.score_category = 'REGULAR' AND s.column_index IN (1, 2) THEN s.value END), 0)
               ) / NULLIF(MAX(CASE WHEN s.score_category = 'MIDTERM' THEN s.value END), 0) AS momentum
        FROM scores s
        JOIN classes c ON s.class_id = c.id
        JOIN grades g ON c.grade_id = g.id
        WHERE g.school_id = :school_id
          AND s.semester_id = :semester_id
          AND s.subject_id = :subject_id
          AND s.status = 'APPROVED'
        GROUP BY s.student_id, s.class_id
    )
    SELECT c.name AS class_name,
           SUM(CASE WHEN momentum > 0.05 THEN 1 ELSE 0 END) AS positive_count,
           SUM(CASE WHEN momentum BETWEEN -0.05 AND 0.05 THEN 1 ELSE 0 END) AS stable_count,
           SUM(CASE WHEN momentum < -0.05 THEN 1 ELSE 0 END) AS negative_count
    FROM student_momentum sm
    JOIN classes c ON sm.class_id = c.id
    GROUP BY c.name
    ORDER BY c.name;
    """
    rows = db.execute(
        text(sql), {"school_id": user.school_id, "semester_id": semester_id, "subject_id": subject_id}
    ).all()
    return [
        LearningMomentumRow(
            class_name=r.class_name,
            positive_count=int(r.positive_count or 0),
            stable_count=int(r.stable_count or 0),
            negative_count=int(r.negative_count or 0),
        )
        for r in rows
    ]


@router.get("/student-archetypes", response_model=list[StudentArchetypeRow])
def student_archetypes(semester_id: UUID, user: CurrentUser, db: Session = Depends(get_db)):
    """Phân bổ 4 nhóm năng lực học tập ẩn (Rule-based) của các lớp trong trường."""
    sql = """
    WITH student_semester_stats AS (
        SELECT s.student_id,
               s.class_id,
               AVG(CASE WHEN s.score_category = 'REGULAR' THEN s.value END) AS tx_mean,
               MAX(CASE WHEN s.score_category = 'FINAL' THEN s.value END) AS ck_score
        FROM scores s
        JOIN classes c ON s.class_id = c.id
        JOIN grades g ON c.grade_id = g.id
        WHERE g.school_id = :school_id
          AND s.semester_id = :semester_id
          AND s.status = 'APPROVED'
        GROUP BY s.student_id, s.class_id
    ),
    student_classifications AS (
        SELECT student_id,
               class_id,
               CASE
                   WHEN tx_mean >= 8.0 AND ck_score >= 8.0 THEN 'consistent'
                   WHEN tx_mean < 6.5 AND ck_score >= 7.5 THEN 'procrastinator'
                   WHEN tx_mean >= 7.5 AND ck_score < 5.5 THEN 'high_effort'
                   WHEN tx_mean < 5.0 AND ck_score < 5.0 THEN 'high_risk'
                   ELSE 'others'
               END AS archetype
         FROM student_semester_stats
    )
    SELECT c.name AS class_name,
           SUM(CASE WHEN archetype = 'consistent' THEN 1 ELSE 0 END) AS consistent,
           SUM(CASE WHEN archetype = 'procrastinator' THEN 1 ELSE 0 END) AS procrastinator,
           SUM(CASE WHEN archetype = 'high_effort' THEN 1 ELSE 0 END) AS high_effort,
           SUM(CASE WHEN archetype = 'high_risk' THEN 1 ELSE 0 END) AS high_risk,
           SUM(CASE WHEN archetype = 'others' THEN 1 ELSE 0 END) AS others
    FROM student_classifications sc
    JOIN classes c ON sc.class_id = c.id
    GROUP BY c.name
    ORDER BY c.name;
    """
    rows = db.execute(text(sql), {"school_id": user.school_id, "semester_id": semester_id}).all()
    return [
        StudentArchetypeRow(
            class_name=r.class_name,
            consistent=int(r.consistent or 0),
            procrastinator=int(r.procrastinator or 0),
            high_effort=int(r.high_effort or 0),
            high_risk=int(r.high_risk or 0),
            others=int(r.others or 0),
        )
        for r in rows
    ]
