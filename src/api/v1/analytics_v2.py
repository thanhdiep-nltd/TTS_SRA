"""Dashboard v2 — endpoints BI cho 4 tab (Executive / Drill-down / Trend / Cảnh báo).

Tất cả lọc theo `school_id` của user (BGH xem toàn trường, đồng bộ các endpoint EDM
hiện có). Tham số `semester_id` tùy chọn — mặc định học kỳ đang hiện hành của trường.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from src.api.deps import CurrentUser, get_db
from src.models.tables import AcademicYear, Semester
from src.schemas.analytics_v2 import (
    ClassRankRow,
    ExecutiveKpi,
    ExecutiveSummary,
    LevelDistributionRow,
    RiskMatrixCell,
    RiskStudent,
    ScatterPoint,
    SubjectMatrix,
    TalentStudent,
    WarningData,
    YearGpaRow,
    YoYResponse,
)

router = APIRouter(prefix="/analytics/v2", tags=["Analytics v2"])

# ĐTB từng môn (SCORED) của mỗi HS trong 1 học kỳ → ĐTB chung (GPA) của HS.
# Công thức tính inline (thay vì gọi hàm calc_subject_average() theo hàng) để PostgreSQL gộp
# thành 1 lượt quét tổng hợp duy nhất — gọi hàm scalar theo từng (student, subject) cho toàn
# trường (hàng nghìn lượt) chậm hơn nhiều so với 1 aggregate SQL set-based.
_STUDENT_GPA_CTE = """
student_subj AS (
    SELECT s.student_id, s.class_id, s.subject_id,
           ROUND(
               SUM(CASE s.score_category
                   WHEN 'ORAL' THEN s.value WHEN 'REGULAR' THEN s.value
                   WHEN 'MIDTERM' THEN 2 * s.value WHEN 'FINAL' THEN 3 * s.value END)
               / NULLIF(SUM(CASE s.score_category
                   WHEN 'ORAL' THEN 1 WHEN 'REGULAR' THEN 1
                   WHEN 'MIDTERM' THEN 2 WHEN 'FINAL' THEN 3 END), 0)
           , 2) AS subj_avg
    FROM scores s
    JOIN classes c ON s.class_id = c.id
    JOIN grades g ON c.grade_id = g.id
    JOIN subjects sub ON s.subject_id = sub.id
    WHERE g.school_id = :school_id AND s.semester_id = :semester_id
      AND s.status = 'APPROVED' AND sub.assessment_type = 'SCORED'
    GROUP BY s.student_id, s.class_id, s.subject_id
),
student_gpa AS (
    SELECT student_id, class_id, ROUND(AVG(subj_avg)::numeric, 2) AS gpa
    FROM student_subj WHERE subj_avg IS NOT NULL
    GROUP BY student_id, class_id
)
"""


def _resolve_semester(db: Session, user: CurrentUser, semester_id: UUID | None) -> tuple[UUID, str, str]:
    """Chốt học kỳ + nhãn (mặc định học kỳ hiện hành của trường)."""
    stmt = (
        select(Semester.id, Semester.name, AcademicYear.name)
        .join(AcademicYear, Semester.academic_year_id == AcademicYear.id)
        .where(AcademicYear.school_id == user.school_id)
    )
    stmt = stmt.where(Semester.id == semester_id) if semester_id else stmt.where(Semester.is_current.is_(True))
    row = db.execute(stmt.order_by(AcademicYear.name.desc(), Semester.number.desc())).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy học kỳ phù hợp.")
    return row[0], row[1], row[2]


def _params(user: CurrentUser, semester_id: UUID) -> dict:
    return {"school_id": user.school_id, "semester_id": semester_id}


# ============================================================
# TAB 1 — EXECUTIVE OVERVIEW
# ============================================================
_KPI_SQL = f"""
WITH {_STUDENT_GPA_CTE}
SELECT COUNT(*) AS total_graded,
       ROUND(AVG(gpa)::numeric, 2) AS avg_gpa,
       SUM(CASE WHEN gpa >= 8 THEN 1 ELSE 0 END) AS gioi,
       SUM(CASE WHEN gpa >= 6.5 AND gpa < 8 THEN 1 ELSE 0 END) AS kha,
       SUM(CASE WHEN gpa >= 5 AND gpa < 6.5 THEN 1 ELSE 0 END) AS trung_binh,
       SUM(CASE WHEN gpa < 5 THEN 1 ELSE 0 END) AS yeu
FROM student_gpa;
"""

_CONDUCT_SQL = """
SELECT COUNT(*) AS total,
       SUM(CASE WHEN conduct IN ('TOT', 'KHA') THEN 1 ELSE 0 END) AS good
FROM student_term_reports tr
JOIN classes c ON tr.class_id = c.id
JOIN grades g ON c.grade_id = g.id
WHERE g.school_id = :school_id AND tr.semester_id = :semester_id;
"""

_LEVEL_SQL = f"""
WITH {_STUDENT_GPA_CTE}
SELECT g.school_level AS level,
       SUM(CASE WHEN sg.gpa >= 8 THEN 1 ELSE 0 END) AS gioi,
       SUM(CASE WHEN sg.gpa >= 6.5 AND sg.gpa < 8 THEN 1 ELSE 0 END) AS kha,
       SUM(CASE WHEN sg.gpa >= 5 AND sg.gpa < 6.5 THEN 1 ELSE 0 END) AS trung_binh,
       SUM(CASE WHEN sg.gpa < 5 THEN 1 ELSE 0 END) AS yeu
FROM student_gpa sg
JOIN classes c ON sg.class_id = c.id
JOIN grades g ON c.grade_id = g.id
GROUP BY g.school_level;
"""

_CLASS_RANK_SQL = f"""
WITH {_STUDENT_GPA_CTE}
SELECT c.name AS class_name, g.name AS grade_name,
       ROUND(AVG(sg.gpa)::numeric, 2) AS gpa, COUNT(*) AS student_count
FROM student_gpa sg
JOIN classes c ON sg.class_id = c.id
JOIN grades g ON c.grade_id = g.id
GROUP BY c.name, g.name
ORDER BY gpa DESC;
"""

_LEVEL_LABELS = {"PRIMARY": "Tiểu học", "SECONDARY": "THCS", "HIGH": "THPT", "ALL": "Toàn cấp"}


def _build_kpi(db: Session, params: dict) -> ExecutiveKpi:
    r = db.execute(text(_KPI_SQL), params).first()
    c = db.execute(text(_CONDUCT_SQL), params).first()
    conduct_ratio = round(c.good / c.total, 3) if c and c.total else None
    return ExecutiveKpi(
        avg_gpa=float(r.avg_gpa) if r.avg_gpa is not None else None,
        total_graded=int(r.total_graded or 0),
        gioi=int(r.gioi or 0),
        kha=int(r.kha or 0),
        trung_binh=int(r.trung_binh or 0),
        yeu=int(r.yeu or 0),
        at_risk_count=int(r.yeu or 0),
        conduct_good_ratio=conduct_ratio,
        attendance_available=False,
        promotion_available=False,
    )


@router.get("/executive", response_model=ExecutiveSummary)
def executive(user: CurrentUser, semester_id: UUID | None = None, db: Session = Depends(get_db)):
    """KPI tổng quan + cơ cấu học lực theo cấp + xếp hạng lớp (Tab Executive)."""
    sem_id, sem_name, year = _resolve_semester(db, user, semester_id)
    params = _params(user, sem_id)
    levels = [
        LevelDistributionRow(
            level=_LEVEL_LABELS.get(r.level, r.level),
            gioi=int(r.gioi or 0),
            kha=int(r.kha or 0),
            trung_binh=int(r.trung_binh or 0),
            yeu=int(r.yeu or 0),
        )
        for r in db.execute(text(_LEVEL_SQL), params).all()
    ]
    ranking = [
        ClassRankRow(
            class_name=r.class_name,
            grade_name=r.grade_name,
            gpa=float(r.gpa or 0),
            student_count=int(r.student_count or 0),
        )
        for r in db.execute(text(_CLASS_RANK_SQL), params).all()
    ]
    return ExecutiveSummary(
        semester_name=sem_name,
        academic_year=year,
        kpi=_build_kpi(db, params),
        level_distribution=levels,
        class_ranking=ranking,
    )


# ============================================================
# TAB 2 — ACADEMIC DRILL-DOWN
# ============================================================
_SUBJECT_AVG_SQL = """
WITH student_subject_avg AS (
    SELECT s.student_id, s.class_id, s.subject_id, g.name AS grade_name, c.name AS class_name, sub.name AS subject_name,
           ROUND(
               SUM(CASE s.score_category
                   WHEN 'ORAL' THEN s.value WHEN 'REGULAR' THEN s.value
                   WHEN 'MIDTERM' THEN 2 * s.value WHEN 'FINAL' THEN 3 * s.value END)
               / NULLIF(SUM(CASE s.score_category
                   WHEN 'ORAL' THEN 1 WHEN 'REGULAR' THEN 1
                   WHEN 'MIDTERM' THEN 2 WHEN 'FINAL' THEN 3 END), 0)
           , 2) AS subj_avg
    FROM scores s
    JOIN classes c ON s.class_id = c.id
    JOIN grades g ON c.grade_id = g.id
    JOIN subjects sub ON s.subject_id = sub.id
    WHERE g.school_id = :school_id AND s.semester_id = :semester_id
      AND s.status = 'APPROVED' AND sub.assessment_type = 'SCORED'
    GROUP BY s.student_id, s.class_id, s.subject_id, g.name, c.name, sub.name
)
SELECT grade_name, class_name, subject_name,
       ROUND(AVG(subj_avg)::numeric, 2) AS avg_score
FROM student_subject_avg
GROUP BY grade_name, class_name, subject_name
ORDER BY grade_name, class_name, subject_name;
"""


def _avg(values: list[float]) -> float:
    return round(sum(values) / len(values), 2) if values else 0.0


@router.get("/subject-matrix", response_model=SubjectMatrix)
def subject_matrix(user: CurrentUser, semester_id: UUID | None = None, db: Session = Depends(get_db)):
    """Ma trận điểm môn × khối (clustered bar) + môn × lớp (heatmap) + xếp hạng môn."""
    sem_id, _, _ = _resolve_semester(db, user, semester_id)
    rows = db.execute(text(_SUBJECT_AVG_SQL), _params(user, sem_id)).all()
    grades = sorted({r.grade_name for r in rows})
    classes = sorted({r.class_name for r in rows})
    subjects = sorted({r.subject_name for r in rows})

    by_grade: dict[str, dict[str, list[float]]] = {s: {g: [] for g in grades} for s in subjects}
    by_class: dict[str, dict[str, float]] = {c: {} for c in classes}
    by_subject: dict[str, list[float]] = {s: [] for s in subjects}
    for r in rows:
        score = float(r.avg_score or 0)
        by_grade[r.subject_name][r.grade_name].append(score)
        by_class[r.class_name][r.subject_name] = score
        by_subject[r.subject_name].append(score)

    grade_cells = [{"subject": s, **{g: _avg(by_grade[s][g]) for g in grades}} for s in subjects]
    heatmap_cells = [{"class_name": c, **by_class[c]} for c in classes]
    subject_ranking = sorted(
        (ClassRankRow(class_name=s, grade_name="", gpa=_avg(by_subject[s]), student_count=0) for s in subjects),
        key=lambda x: x.gpa,
        reverse=True,
    )
    return SubjectMatrix(
        grades=grades,
        classes=classes,
        subjects=subjects,
        grade_cells=grade_cells,
        heatmap_cells=heatmap_cells,
        subject_ranking=subject_ranking,
    )


# ============================================================
# TAB 4 — EARLY WARNING SYSTEM
# ============================================================
# ĐTB quá trình (Miệng+TX+GK) và điểm cuối kỳ của mỗi HS-môn → suy ra risk.
_STUDENT_DETAIL_SQL = f"""
WITH {_STUDENT_GPA_CTE},
process AS (
    SELECT s.student_id,
           AVG(CASE WHEN s.score_category IN ('ORAL','REGULAR','MIDTERM') THEN s.value END) AS process_gpa,
           AVG(CASE WHEN s.score_category = 'FINAL' THEN s.value END) AS final_score
    FROM scores s
    JOIN classes c ON s.class_id = c.id
    JOIN grades g ON c.grade_id = g.id
    WHERE g.school_id = :school_id AND s.semester_id = :semester_id AND s.status = 'APPROVED'
    GROUP BY s.student_id
),
subj_extreme AS (
    SELECT student_id,
           (ARRAY_AGG(subj_name ORDER BY subj_avg ASC))[1] AS weakest_subject,
           MIN(subj_avg) AS weakest_score,
           (ARRAY_AGG(subj_name ORDER BY subj_avg DESC))[1] AS best_subject,
           MAX(subj_avg) AS best_score
    FROM (
        SELECT ss.student_id, sub.name AS subj_name, ss.subj_avg
        FROM student_subj ss JOIN subjects sub ON ss.subject_id = sub.id
        WHERE ss.subj_avg IS NOT NULL
    ) t GROUP BY student_id
)
SELECT st.student_code, st.full_name, cl.name AS class_name, sg.gpa,
       tr.conduct::text AS conduct,
       p.process_gpa, p.final_score,
       se.weakest_subject, se.weakest_score, se.best_subject, se.best_score
FROM student_gpa sg
JOIN students st ON sg.student_id = st.id
JOIN classes cl ON sg.class_id = cl.id
LEFT JOIN process p ON p.student_id = sg.student_id
LEFT JOIN subj_extreme se ON se.student_id = sg.student_id
LEFT JOIN student_term_reports tr
       ON tr.student_id = sg.student_id AND tr.class_id = sg.class_id AND tr.semester_id = :semester_id;
"""


def _risk_level(gpa: float, conduct: str | None) -> str:
    """Phân loại nguy cơ theo ĐTB + hạnh kiểm (rule engine rút gọn)."""
    if gpa < 3.5 or conduct == "YEU":
        return "Critical"
    if gpa < 5.0 or conduct == "TRUNG_BINH":
        return "High"
    if gpa < 6.5:
        return "Medium"
    return "Low"


def _to_risk(r) -> RiskStudent:
    return RiskStudent(
        student_code=r.student_code,
        full_name=r.full_name,
        class_name=r.class_name,
        gpa=float(r.gpa),
        conduct=r.conduct,
        weakest_subject=r.weakest_subject,
        weakest_score=round(float(r.weakest_score), 2) if r.weakest_score is not None else None,
        risk_level=_risk_level(float(r.gpa), r.conduct),
    )


@router.get("/warnings", response_model=WarningData)
def warnings(user: CurrentUser, semester_id: UUID | None = None, db: Session = Depends(get_db)):
    """Học sinh nguy cơ + tài năng + ma trận rủi ro + scatter quá trình/cuối kỳ (Tab Cảnh báo)."""
    sem_id, _, _ = _resolve_semester(db, user, semester_id)
    rows = db.execute(text(_STUDENT_DETAIL_SQL), _params(user, sem_id)).all()

    risks = sorted((_to_risk(r) for r in rows if float(r.gpa) < 6.5), key=lambda x: x.gpa)[:40]
    talents = sorted(
        (
            TalentStudent(
                student_code=r.student_code,
                full_name=r.full_name,
                class_name=r.class_name,
                gpa=float(r.gpa),
                best_subject=r.best_subject,
                best_score=round(float(r.best_score), 2) if r.best_score is not None else None,
            )
            for r in rows
            if float(r.gpa) >= 8.0
        ),
        key=lambda x: x.gpa,
        reverse=True,
    )[:40]

    matrix_counts = {"Low": 0, "Medium": 0, "High": 0, "Critical": 0}
    scatter: list[ScatterPoint] = []
    for r in rows:
        level = _risk_level(float(r.gpa), r.conduct)
        matrix_counts[level] += 1
        if r.process_gpa is not None and r.final_score is not None:
            scatter.append(
                ScatterPoint(
                    process_gpa=round(float(r.process_gpa), 2),
                    final_score=round(float(r.final_score), 2),
                    class_name=r.class_name,
                    risk_level=level,
                )
            )
    matrix = [RiskMatrixCell(level=k, count=v) for k, v in matrix_counts.items()]
    return WarningData(risk_students=risks, talent_students=talents, risk_matrix=matrix, scatter=scatter)


# ============================================================
# TAB 3 — YEAR OVER YEAR
# ============================================================
_YOY_SQL = """
WITH final_avg AS (
    SELECT ay.name AS academic_year, s.student_id, AVG(s.value) AS gpa
    FROM scores s
    JOIN semesters sem ON s.semester_id = sem.id
    JOIN academic_years ay ON sem.academic_year_id = ay.id
    JOIN classes c ON s.class_id = c.id
    JOIN grades g ON c.grade_id = g.id
    WHERE g.school_id = :school_id AND s.status = 'APPROVED' AND s.score_category = 'FINAL'
    GROUP BY ay.name, s.student_id
)
SELECT academic_year, ROUND(AVG(gpa)::numeric, 2) AS avg_gpa, COUNT(*) AS student_count
FROM final_avg GROUP BY academic_year ORDER BY academic_year;
"""


@router.get("/yoy", response_model=YoYResponse)
def year_over_year(user: CurrentUser, db: Session = Depends(get_db)):
    """So sánh ĐTB cuối kỳ trung bình giữa các năm học (Tab Trend)."""
    rows = db.execute(text(_YOY_SQL), {"school_id": user.school_id}).all()
    years = [
        YearGpaRow(
            academic_year=r.academic_year,
            avg_gpa=float(r.avg_gpa) if r.avg_gpa is not None else None,
            student_count=int(r.student_count or 0),
        )
        for r in rows
    ]
    return YoYResponse(years=years)
