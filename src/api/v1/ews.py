"""
src/api/v1/ews.py — FastAPI Router cho Early Warning System (EWS) Dashboard APIs
"""

import logging
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.api.deps import CurrentUser, get_db
from src.core.security.sql_validator import get_user_assignment_constraints
from src.schemas.ews import (
    EwsClassOption,
    EwsLevelCount,
    EwsMeta,
    EwsOverview,
    EwsPagedResult,
    EwsPredictionRow,
    EwsRawAttendanceItem,
    EwsRawBehaviorItem,
    EwsRawDetail,
    EwsRawLmsItem,
    EwsRawScore,
    EwsWeekOption,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ews", tags=["Early Warning System"])


def _ews_rbac_filter(db: Session, user) -> tuple[str, dict]:
    """Trả (where_sql, params) giới hạn dữ liệu EWS theo phân quyền user.

    Luôn giới hạn theo ``so_school_id`` của user (chống rò rỉ giữa trường).
    Nếu user không full-access (ADMIN/PRINCIPAL), thêm giới hạn theo khối/lớp/môn
    từ ``teacher_assignments`` — cùng logic với chatbot (get_user_assignment_constraints).

    Query gọi helper phải có alias ``hcs`` = s360.dim_homeroom_class_student
    và ``rp`` = s360.fact_student_subject_risk_predictions.
    """
    constraints = get_user_assignment_constraints(user.id, user.role)
    params: dict = {"school_id": user.so_school_id}
    clauses = ["hcs.so_school_id = :school_id"]

    if not constraints.get("is_full_access", False):
        grade_ids = constraints.get("grade_ids") or []
        class_ids = constraints.get("homeroom_class_ids") or []
        pairs = constraints.get("subject_class_pairs") or []
        scope: list[str] = []

        if grade_ids:
            ph = ", ".join(f":g{i}" for i in range(len(grade_ids)))
            scope.append(f"hcs.grade_id IN ({ph})")
            for i, g in enumerate(grade_ids):
                params[f"g{i}"] = int(g)
        if class_ids:
            ph = ", ".join(f":c{i}" for i in range(len(class_ids)))
            scope.append(f"hcs.homeroom_class_id IN ({ph})")
            for i, c in enumerate(class_ids):
                params[f"c{i}"] = int(c)
        if pairs:
            pair_clauses = []
            for i, (c, s) in enumerate(pairs):
                pair_clauses.append(f"(hcs.homeroom_class_id = :pc{i} AND rp.subject_id = :ps{i})")
                params[f"pc{i}"] = int(c)
                params[f"ps{i}"] = int(s)
            scope.append("(" + " OR ".join(pair_clauses) + ")")

        if scope:
            clauses.append("(" + " OR ".join(scope) + ")")
        else:
            # Không có quyền lớp/khối/môn nào -> không thấy dữ liệu EWS.
            clauses.append("1 = 0")

    return " AND ".join(clauses), params


@router.get("/meta", response_model=EwsMeta)
def get_ews_meta(
    school_year_id: int | None = Query(None, description="Năm học (mặc định: mốc mới nhất)"),
    semester_index: int | None = Query(None, description="Học kỳ (mặc định: mốc mới nhất)"),
    evaluated_at_week: int | None = Query(None, description="Tuần đánh giá (mặc định: mốc mới nhất)"),
    current_user: CurrentUser = None,
    db: Session = Depends(get_db),
):
    """
    Endpoint 1: Lấy danh sách các mốc (school_year_id, semester_index, evaluated_at_week) có sẵn dữ liệu dự báo.
    Kèm dropdown danh sách môn học, khối lớp, lớp học.
    Truyền school_year_id/semester_index/evaluated_at_week để lấy danh sách đúng theo mốc đang chọn
    (mặc định: mốc mới nhất).
    """
    # 1. Lấy danh sách mốc tuần
    weeks_sql = text("""
        SELECT rp.school_year_id, COALESCE(sy.fullname, CAST(rp.school_year_id AS VARCHAR)) AS school_year_name,
               rp.semester_index, rp.evaluated_at_week
        FROM s360.fact_student_subject_risk_predictions rp
        LEFT JOIN s360.dim_school_year sy ON rp.school_year_id = sy.id
        GROUP BY rp.school_year_id, sy.fullname, rp.semester_index, rp.evaluated_at_week
        ORDER BY rp.school_year_id DESC, rp.semester_index DESC, rp.evaluated_at_week DESC;
    """)
    weeks_rows = db.execute(weeks_sql).fetchall()
    weeks = [
        EwsWeekOption(
            school_year_id=row.school_year_id,
            semester_index=row.semester_index,
            evaluated_at_week=row.evaluated_at_week,
            school_year_name=row.school_year_name,
        )
        for row in weeks_rows
    ]

    # Mốc mục tiêu = tham số truyền vào (nếu có), ngược lại lấy mốc mới nhất
    target_sy = school_year_id or (weeks[0].school_year_id if weeks else 2025)
    target_sem = semester_index or (weeks[0].semester_index if weeks else 1)
    target_wk = evaluated_at_week or (weeks[0].evaluated_at_week if weeks else 8)

    rbac_where, rbac_params = _ews_rbac_filter(db, current_user)
    base_params = {"sy": target_sy, "sem": target_sem, "wk": target_wk, **rbac_params}

    # 2. Lấy danh sách Môn học có trong kết quả EWS
    subjects_sql = text(f"""
        SELECT DISTINCT sub.id, sub.name, sub.code, sub.subject_category
        FROM s360.fact_student_subject_risk_predictions rp
        JOIN s360.dim_subject sub ON rp.subject_id = sub.id
        JOIN s360.dim_homeroom_class_student hcs
             ON rp.student_code = hcs.student_code AND rp.school_year_id = hcs.school_year_id
        WHERE rp.school_year_id = :sy AND rp.semester_index = :sem AND rp.evaluated_at_week = :wk
          AND {rbac_where}
        ORDER BY sub.name;
    """)
    subjects_rows = db.execute(subjects_sql, base_params).fetchall()
    subjects = [
        {"id": row.id, "name": row.name, "code": row.code, "subject_category": row.subject_category}
        for row in subjects_rows
    ]

    # 3. Lấy danh sách Khối lớp
    grades_sql = text(f"""
        SELECT DISTINCT hcs.grade_id, hcs.grade_name
        FROM s360.fact_student_subject_risk_predictions rp
        JOIN s360.dim_homeroom_class_student hcs ON rp.student_code = hcs.student_code AND rp.school_year_id = hcs.school_year_id
        WHERE rp.school_year_id = :sy AND rp.semester_index = :sem AND rp.evaluated_at_week = :wk
          AND {rbac_where}
        ORDER BY hcs.grade_id;
    """)
    grades_rows = db.execute(grades_sql, base_params).fetchall()
    grades = [{"grade_id": row.grade_id, "grade_name": row.grade_name} for row in grades_rows]

    # 4. Lấy danh sách Tên Lớp KÈM khối chủ quản (liên kết bộ lọc Khối → Lớp)
    classes_sql = text(f"""
        SELECT DISTINCT hcs.grade_id, hcs.grade_name, hcs.class_name
        FROM s360.fact_student_subject_risk_predictions rp
        JOIN s360.dim_homeroom_class_student hcs ON rp.student_code = hcs.student_code AND rp.school_year_id = hcs.school_year_id
        WHERE rp.school_year_id = :sy AND rp.semester_index = :sem AND rp.evaluated_at_week = :wk
          AND {rbac_where}
        ORDER BY hcs.grade_id, hcs.class_name;
    """)
    classes_rows = db.execute(classes_sql, base_params).fetchall()
    classes = [
        EwsClassOption(grade_id=row.grade_id, grade_name=row.grade_name, class_name=row.class_name)
        for row in classes_rows
        if row.class_name
    ]

    return EwsMeta(
        weeks=weeks,
        subjects=subjects,
        grades=grades,
        classes=classes,
    )


@router.get("/overview", response_model=EwsOverview)
def get_ews_overview(
    school_year_id: int = Query(2025, description="Năm học (VD: 2025)"),
    semester_index: int = Query(1, description="Học kỳ (1 hoặc 2)"),
    evaluated_at_week: int = Query(8, description="Tuần đánh giá"),
    current_user: CurrentUser = None,
    db: Session = Depends(get_db),
):
    """
    Endpoint 2: Lấy dữ liệu KPI tổng quan phân hệ EWS (Tổng số dự báo, số lượng theo 4 mức, top môn rủi ro).
    """
    rbac_where, rbac_params = _ews_rbac_filter(db, current_user)
    base_params = {"sy": school_year_id, "sem": semester_index, "wk": evaluated_at_week, **rbac_params}

    summary_sql = text(f"""
        SELECT
            COUNT(*) AS total_predictions,
            COUNT(DISTINCT rp.student_code) AS total_students,
            COUNT(*) FILTER (WHERE rp.risk_level IN ('HIGH', 'CRITICAL')) AS at_risk_count,
            ROUND(AVG(rp.risk_score)::numeric, 2) AS avg_risk_score,
            COUNT(*) FILTER (WHERE rp.risk_level = 'LOW') AS low_cnt,
            COUNT(*) FILTER (WHERE rp.risk_level = 'MODERATE') AS moderate_cnt,
            COUNT(*) FILTER (WHERE rp.risk_level = 'HIGH') AS high_cnt,
            COUNT(*) FILTER (WHERE rp.risk_level = 'CRITICAL') AS critical_cnt
        FROM s360.fact_student_subject_risk_predictions rp
        JOIN s360.dim_homeroom_class_student hcs
             ON rp.student_code = hcs.student_code AND rp.school_year_id = hcs.school_year_id
        WHERE rp.school_year_id = :sy
          AND rp.semester_index = :sem
          AND rp.evaluated_at_week = :wk
          AND {rbac_where};
    """)
    row = db.execute(summary_sql, base_params).fetchone()

    if not row or row.total_predictions == 0:
        return EwsOverview(
            school_year_id=school_year_id,
            semester_index=semester_index,
            evaluated_at_week=evaluated_at_week,
            total_predictions=0,
            total_students=0,
            at_risk_count=0,
            avg_risk_score=0.0,
            levels=[
                EwsLevelCount(level="LOW", count=0),
                EwsLevelCount(level="MODERATE", count=0),
                EwsLevelCount(level="HIGH", count=0),
                EwsLevelCount(level="CRITICAL", count=0),
            ],
            top_risk_subjects=[],
        )

    # Top 10 môn học nguy cơ nhất
    top_sub_sql = text(f"""
        SELECT sub.name AS subject_name, COUNT(*) AS cnt, ROUND(AVG(rp.risk_score)::numeric, 2) AS avg_risk
        FROM s360.fact_student_subject_risk_predictions rp
        JOIN s360.dim_subject sub ON rp.subject_id = sub.id
        JOIN s360.dim_homeroom_class_student hcs
             ON rp.student_code = hcs.student_code AND rp.school_year_id = hcs.school_year_id
        WHERE rp.school_year_id = :sy
          AND rp.semester_index = :sem
          AND rp.evaluated_at_week = :wk
          AND {rbac_where}
        GROUP BY sub.name
        ORDER BY avg_risk DESC LIMIT 10;
    """)
    top_sub_rows = db.execute(top_sub_sql, base_params).fetchall()
    top_risk_subjects = [
        {"subject_name": r.subject_name, "cnt": r.cnt, "avg_risk": float(r.avg_risk) if r.avg_risk else 0.0}
        for r in top_sub_rows
    ]

    return EwsOverview(
        school_year_id=school_year_id,
        semester_index=semester_index,
        evaluated_at_week=evaluated_at_week,
        total_predictions=row.total_predictions,
        total_students=row.total_students,
        at_risk_count=row.at_risk_count,
        avg_risk_score=float(row.avg_risk_score) if row.avg_risk_score else 0.0,
        levels=[
            EwsLevelCount(level="LOW", count=row.low_cnt),
            EwsLevelCount(level="MODERATE", count=row.moderate_cnt),
            EwsLevelCount(level="HIGH", count=row.high_cnt),
            EwsLevelCount(level="CRITICAL", count=row.critical_cnt),
        ],
        top_risk_subjects=top_risk_subjects,
    )


@router.get("/predictions", response_model=EwsPagedResult)
def get_ews_predictions(
    school_year_id: int = Query(2025, description="Năm học"),
    semester_index: int = Query(1, description="Học kỳ"),
    evaluated_at_week: int = Query(8, description="Tuần đánh giá"),
    model_version: str = Query("v1_single", description="v1_single | v2_ensemble"),
    risk_level: str | None = Query(None, description="LOW | MODERATE | HIGH | CRITICAL"),
    subject_id: int | None = Query(None, description="ID môn học"),
    grade_id: int | None = Query(None, description="ID khối lớp"),
    class_name: str | None = Query(None, description="Tên lớp"),
    q: str | None = Query(None, description="Tìm kiếm theo mã/tên học sinh hoặc tên môn học (ILIKE)"),
    min_risk_score: float | None = Query(None, description="Lọc risk_score tối thiểu"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: CurrentUser = None,
    db: Session = Depends(get_db),
):
    """
    Endpoint 3: Lấy danh sách bản ghi dự báo rủi ro chi tiết (có phân trang Server-side + filters).
    Tự động tính mảng cờ rủi ro `risk_factors` (SLOPE_DOWN, LAST_SCORE_LOW, ABSENTEEISM).
    """
    where_clauses = [
        "rp.school_year_id = :sy",
        "rp.semester_index = :sem",
        "rp.evaluated_at_week = :wk",
        "rp.model_version = :model_version",
    ]
    params: dict = {
        "sy": school_year_id, "sem": semester_index, "wk": evaluated_at_week,
        "model_version": model_version,
    }

    rbac_where, rbac_params = _ews_rbac_filter(db, current_user)
    params.update(rbac_params)
    where_clauses.append(rbac_where)

    if risk_level:
        where_clauses.append("rp.risk_level = :risk_level")
        params["risk_level"] = risk_level
    if subject_id is not None:
        where_clauses.append("rp.subject_id = :subject_id")
        params["subject_id"] = subject_id
    if grade_id is not None:
        where_clauses.append("hcs.grade_id = :grade_id")
        params["grade_id"] = grade_id
    if class_name:
        where_clauses.append("hcs.class_name = :class_name")
        params["class_name"] = class_name
    if q and q.strip():
        where_clauses.append("(rp.student_code ILIKE :q OR hcs.student_name ILIKE :q OR sub.name ILIKE :q)")
        params["q"] = f"%{q.strip()}%"
    if min_risk_score is not None:
        where_clauses.append("rp.risk_score >= :min_risk_score")
        params["min_risk_score"] = min_risk_score

    base_where = "WHERE " + " AND ".join(where_clauses)

    count_sql = text(f"""
        WITH hcs AS (
            SELECT DISTINCT ON (student_code)
                student_code, student_name, class_name, grade_id, grade_name,
                so_school_id, homeroom_class_id
            FROM s360.dim_homeroom_class_student
            WHERE school_year_id = :sy
            ORDER BY student_code, is_active DESC, homeroom_class_id
        )
        SELECT COUNT(*) AS total_cnt
        FROM s360.fact_student_subject_risk_predictions rp
        LEFT JOIN hcs ON rp.student_code = hcs.student_code
        LEFT JOIN s360.dim_subject sub ON rp.subject_id = sub.id
        {base_where};
    """)

    total_row = db.execute(count_sql, params).fetchone()
    total_cnt = total_row.total_cnt if total_row else 0

    if total_cnt == 0:
        return EwsPagedResult(items=[], total=0, limit=limit, offset=offset)

    query_sql = text(f"""
        WITH hcs AS (
            SELECT DISTINCT ON (student_code)
                student_code, student_name, class_name, grade_id, grade_name,
                so_school_id, homeroom_class_id
            FROM s360.dim_homeroom_class_student
            WHERE school_year_id = :sy
            ORDER BY student_code, is_active DESC, homeroom_class_id
        )
        SELECT rp.student_code, hcs.student_name, hcs.class_name, hcs.grade_name, hcs.grade_id AS grade_level,
               rp.subject_id, sub.name AS subject_name, sub.code AS subject_code,
               sub.subject_category,
               rp.evaluated_at_week, rp.model_version, rp.risk_score, rp.risk_level, rp.risk_probability,
               rp.evaluated_at_date, rp.cutoff_date, rp.join_date,
               rp.score_risk, rp.lms_risk, rp.attendance_risk, rp.behavior_risk,
               rp.weight_score, rp.weight_lms, rp.weight_attendance, rp.weight_behavior,
               -- Temporal
               rp.weighted_early_avg, rp.weighted_late_avg, rp.score_slope, rp.score_volatility,
               rp.max_drop, rp.last_score, rp.max_coefficient_so_far, rp.high_weight_score_count,
               rp.last_high_weight_score,
               -- LMS
               rp.lms_avg_score, rp.lms_recent_drop, rp.lms_submission_rate,
               rp.lms_recent_submission_rate, rp.lms_gradebook_gap,
               -- Attendance
               rp.daily_absence_rate, rp.unexcused_absent_rate, rp.excused_absent_days,
               rp.total_late_count,
               -- Behavior
               rp.total_demerit_points, rp.repeat_offense_count, rp.severe_sanction_count,
               ARRAY_REMOVE(ARRAY[
                   CASE WHEN rp.score_slope IS NOT NULL AND rp.score_slope < -0.5 THEN 'SLOPE_DOWN' END,
                   CASE WHEN rp.last_score IS NOT NULL AND rp.last_score < 5.0 THEN 'LAST_SCORE_LOW' END,
                   CASE WHEN rp.daily_absence_rate IS NOT NULL AND rp.daily_absence_rate > 0.1 THEN 'ABSENTEEISM' END
               ], NULL) AS risk_factors
        FROM s360.fact_student_subject_risk_predictions rp
        LEFT JOIN hcs ON rp.student_code = hcs.student_code
        LEFT JOIN s360.dim_subject sub ON rp.subject_id = sub.id
        {base_where}
        ORDER BY rp.risk_score DESC
        LIMIT :limit OFFSET :offset;
    """)

    exec_params = {**params, "limit": limit, "offset": offset}
    rows = db.execute(query_sql, exec_params).fetchall()

    def _flt(v):
        return float(v) if v is not None else None

    def _int(v):
        return int(v) if v is not None else None

    items = []
    for r in rows:
        factors = list(r.risk_factors) if r.risk_factors else []
        items.append(
            EwsPredictionRow(
                student_code=r.student_code,
                student_name=r.student_name or r.student_code,
                class_name=r.class_name,
                grade_name=r.grade_name,
                grade_level=_int(r.grade_level),
                subject_id=r.subject_id,
                subject_name=r.subject_name,
                subject_code=r.subject_code,
                subject_category=r.subject_category,
                evaluated_at_week=r.evaluated_at_week,
                risk_score=_flt(r.risk_score) or 0.0,
                risk_level=r.risk_level,
                risk_probability=_flt(r.risk_probability),
                risk_factors=factors,
                evaluated_at_date=r.evaluated_at_date,
                cutoff_date=r.cutoff_date,
                join_date=r.join_date,
                model_version=r.model_version or "v1_single",
                score_risk=_flt(r.score_risk),
                lms_risk=_flt(r.lms_risk),
                attendance_risk=_flt(r.attendance_risk),
                behavior_risk=_flt(r.behavior_risk),
                weight_score=_flt(r.weight_score),
                weight_lms=_flt(r.weight_lms),
                weight_attendance=_flt(r.weight_attendance),
                weight_behavior=_flt(r.weight_behavior),
                # Temporal
                weighted_early_avg=_flt(r.weighted_early_avg),
                weighted_late_avg=_flt(r.weighted_late_avg),
                score_slope=_flt(r.score_slope),
                score_volatility=_flt(r.score_volatility),
                max_drop=_flt(r.max_drop),
                last_score=_flt(r.last_score),
                max_coefficient_so_far=_flt(r.max_coefficient_so_far),
                high_weight_score_count=_int(r.high_weight_score_count),
                last_high_weight_score=_flt(r.last_high_weight_score),
                # LMS
                lms_avg_score=_flt(r.lms_avg_score),
                lms_recent_drop=_flt(r.lms_recent_drop),
                lms_submission_rate=_flt(r.lms_submission_rate),
                lms_recent_submission_rate=_flt(r.lms_recent_submission_rate),
                lms_gradebook_gap=_flt(r.lms_gradebook_gap),
                # Attendance
                daily_absence_rate=_flt(r.daily_absence_rate),
                unexcused_absent_rate=_flt(r.unexcused_absent_rate),
                excused_absent_days=_int(r.excused_absent_days),
                total_late_count=_int(r.total_late_count),
                # Behavior
                total_demerit_points=_int(r.total_demerit_points),
                repeat_offense_count=_int(r.repeat_offense_count),
                severe_sanction_count=_int(r.severe_sanction_count),
            )
        )

    return EwsPagedResult(
        items=items,
        total=total_cnt,
        limit=limit,
        offset=offset,
    )


@router.get("/raw", response_model=EwsRawDetail)
def get_ews_raw(
    student_code: str = Query(..., description="Mã học sinh cần đối chiếu"),
    subject_id: int = Query(..., description="ID môn học đang được cảnh báo"),
    school_year_id: int = Query(2025, description="Năm học (VD: 2025)"),
    semester_index: int = Query(1, description="Học kỳ (1 hoặc 2)"),
    evaluated_at_week: int = Query(8, description="Tuần đánh giá (dùng khi không truyền cutoff_date)"),
    cutoff_date: str | None = Query(None, description="Ngày cutoff dạng YYYY-MM-DD (ưu tiên hơn evaluated_at_week)"),
    current_user: CurrentUser = None,
    db: Session = Depends(get_db),
):
    """
    Endpoint 5: Dữ liệu GỐC (raw) để đối chiếu dự báo EWS của cặp (học sinh - môn):
      - scores    : điểm số đã khoá (QUOC_TE + BO_GD) trước cutoff
      - lms       : bài tập LMS do trong cửa sổ hiện diện [join_date, cutoff] + trạng thái nộp
      - attendance: điểm danh hằng ngày (30 ngày gần nhất trước cutoff)
      - behavior  : nhật ký kỷ luật / hành vi
    """
    # 0. Resolve ngày cutoff & ngày nhập học (khớp feature_extractor.extract_live_features)
    base_start = date(school_year_id, 9, 5) if semester_index == 1 else date(school_year_id + 1, 1, 20)
    if cutoff_date:
        cutoff = datetime.strptime(cutoff_date, "%Y-%m-%d").date()
    else:
        cutoff = base_start + timedelta(weeks=evaluated_at_week)

    # 1. Context học sinh (so_school_id, grade_id, homeroom_class_id, join_date)
    sg_sql = text("""
        SELECT DISTINCT ON (student_code)
            student_code, so_school_id, grade_id, homeroom_class_id, join_date
        FROM s360.dim_homeroom_class_student
        WHERE student_code = :sc AND school_year_id = :sy
        ORDER BY student_code, is_active DESC, homeroom_class_id
    """)
    sg = db.execute(sg_sql, {"sc": student_code, "sy": school_year_id}).fetchone()
    if sg is None:
        raise HTTPException(
            status_code=404, detail=f"Không tìm thấy học sinh {student_code} trong năm học {school_year_id}"
        )
    so_school_id = sg.so_school_id
    grade_id = sg.grade_id
    homeroom_class_id = sg.homeroom_class_id
    join_date = sg.join_date or base_start

    # 1b. Kiểm tra phân quyền: học sinh này có nằm trong phạm vi user không?
    constraints = get_user_assignment_constraints(current_user.id, current_user.role)
    if not constraints.get("is_full_access", False):
        grade_ids = constraints.get("grade_ids") or []
        class_ids = constraints.get("homeroom_class_ids") or []
        pairs = constraints.get("subject_class_pairs") or []
        allowed = grade_id in grade_ids or homeroom_class_id in class_ids or (homeroom_class_id, subject_id) in pairs
        if not allowed:
            raise HTTPException(
                status_code=403,
                detail="Bạn không có quyền truy cập dữ liệu EWS của học sinh này (ngoài phạm vi phân quyền).",
            )

    base_params = {"sc": student_code, "sid": subject_id, "sy": school_year_id, "sem": semester_index, "cutoff": cutoff}

    # 2. Điểm số đã khoá (QUOC_TE: fact_gradebooks + dim_exam; BO_GD: fact_gradebooks_moet + dim_exam_moet)
    scores_sql = text("""
        WITH sc AS (
            SELECT
                de.exam_name,
                de.exam_code,
                de.coefficient,
                fg.final_grade,
                fg.max_grade,
                fg.created_at::date AS created_at,
                'QUOC_TE' AS source
            FROM s360.fact_gradebooks fg
            JOIN s360.dim_exam de ON fg.so_exam_id = de.id
            WHERE fg.student_code = :sc
              AND fg.subject_id = :sid
              AND fg.school_year_id = :sy
              AND fg.semester_index = :sem
              AND fg.is_locked = 1
              AND fg.created_at <= CAST(:cutoff AS TIMESTAMPTZ)
            UNION ALL
            SELECT
                dem.gradebook_type_items_fullname AS exam_name,
                dem.gradebook_type_items_code AS exam_code,
                dem.coefficient,
                fgm.final_grade,
                dem.max_grade,
                fgm.created_at::date AS created_at,
                'BO_GD' AS source
            FROM s360.fact_gradebooks_moet fgm
            JOIN s360.dim_exam_moet dem ON fgm.gradebook_type_item_id = dem.gradebook_type_item_id
            WHERE fgm.student_code = :sc
              AND fgm.subject_id = :sid
              AND fgm.school_year_id = :sy
              AND fgm.semester_index = :sem
              AND fgm.is_locked = 1
              AND fgm.created_at <= CAST(:cutoff AS TIMESTAMPTZ)
        )
        SELECT * FROM sc ORDER BY created_at, exam_name
    """)
    score_rows = db.execute(scores_sql, base_params).fetchall()
    scores = [
        EwsRawScore(
            exam_name=r.exam_name,
            exam_code=r.exam_code,
            coefficient=r.coefficient,
            final_grade=r.final_grade,
            max_grade=r.max_grade,
            created_at=r.created_at,
            source=r.source,
        )
        for r in score_rows
    ]

    # 3. Bài tập LMS trong cửa sổ hiện diện [join_date, cutoff] + trạng thái nộp
    lms_sql = text("""
        SELECT
            dsa.code,
            dsa.fullname,
            dsa.max_grade,
            dsa.due_date,
            fag.final_grade,
            (fag.id IS NOT NULL) AS submitted
        FROM s360.dim_so_assignment dsa
        LEFT JOIN s360.fact_so_assignment_grade fag
            ON fag.assignment_id = dsa.assignment_id
           AND fag.student_code = :sc
        WHERE dsa.subject_id = :sid
          AND dsa.semester_index = :sem
          AND dsa.so_school_id = :school_id
          AND dsa.grade_id = :gid
          AND dsa.due_date <= CAST(:cutoff AS DATE)
          AND dsa.due_date >= CAST(:jdate AS DATE)
        ORDER BY dsa.due_date, dsa.assignment_id
    """)
    lms_params = {**base_params, "school_id": so_school_id, "gid": grade_id, "jdate": join_date}
    lms_rows = db.execute(lms_sql, lms_params).fetchall()
    lms = [
        EwsRawLmsItem(
            code=r.code,
            fullname=r.fullname,
            max_grade=r.max_grade,
            due_date=r.due_date,
            submitted=bool(r.submitted),
            final_grade=r.final_grade,
        )
        for r in lms_rows
    ]
    lms_expected = len(lms)
    lms_submitted = sum(1 for it in lms if it.submitted)

    # 4. Điểm danh hằng ngày (30 ngày gần nhất trước cutoff)
    att_sql = text("""
        SELECT _date, total_periods, absent_periods,
               absent_no_permission, absent_with_permission
        FROM s360.fact_so_daily_attendance
        WHERE student_code = :sc AND school_year_id = :sy
          AND _date <= CAST(:cutoff AS DATE)
        ORDER BY _date DESC
        LIMIT 30
    """)
    att_rows = db.execute(att_sql, {"sc": student_code, "sy": school_year_id, "cutoff": cutoff}).fetchall()
    attendance = []
    for r in att_rows:
        if (r.absent_periods or 0) == 0:
            status = "CÓ MẶT"
        elif (r.absent_no_permission or 0) > 0:
            status = "VẮNG KHÔNG PHÉP"
        elif (r.absent_with_permission or 0) > 0:
            status = "NGHỈ CÓ PHÉP"
        else:
            status = "VẮNG"
        attendance.append(
            EwsRawAttendanceItem(
                date=r._date,
                total_periods=r.total_periods or 0,
                absent_periods=r.absent_periods or 0,
                absent_no_permission=r.absent_no_permission or 0,
                absent_with_permission=r.absent_with_permission or 0,
                status=status,
            )
        )

    # 5. Nhật ký kỷ luật / hành vi
    beh_sql = text("""
        SELECT comment_date, behavior_fullname, behavior_point, sanction_name
        FROM s360.fact_behavior_logs
        WHERE student_code = :sc AND school_year_id = :sy
          AND comment_date <= CAST(:cutoff AS DATE)
        ORDER BY comment_date DESC
        LIMIT 100
    """)
    beh_rows = db.execute(beh_sql, {"sc": student_code, "sy": school_year_id, "cutoff": cutoff}).fetchall()
    behavior = [
        EwsRawBehaviorItem(
            comment_date=r.comment_date,
            behavior_fullname=r.behavior_fullname,
            behavior_point=r.behavior_point,
            sanction_name=r.sanction_name,
        )
        for r in beh_rows
    ]

    return EwsRawDetail(
        student_code=student_code,
        subject_id=subject_id,
        school_year_id=school_year_id,
        semester_index=semester_index,
        cutoff_date=cutoff,
        join_date=join_date,
        scores=scores,
        lms=lms,
        lms_expected=lms_expected,
        lms_submitted=lms_submitted,
        attendance=attendance,
        behavior=behavior,
    )


@router.get("/filters")
def get_ews_filters(
    school_year_id: int = Query(2025),
    semester_index: int = Query(1),
    evaluated_at_week: int = Query(8),
    current_user: CurrentUser = None,
    db: Session = Depends(get_db),
):
    """
    Endpoint 4: Lấy danh sách distinct subjects, grades, classes theo bộ lọc mốc tuần hiện tại.
    """
    rbac_where, rbac_params = _ews_rbac_filter(db, current_user)
    base_params = {"sy": school_year_id, "sem": semester_index, "wk": evaluated_at_week, **rbac_params}

    subjects_sql = text(f"""
        SELECT DISTINCT sub.id, sub.name, sub.code, sub.subject_category
        FROM s360.fact_student_subject_risk_predictions rp
        JOIN s360.dim_subject sub ON rp.subject_id = sub.id
        JOIN s360.dim_homeroom_class_student hcs
             ON rp.student_code = hcs.student_code AND rp.school_year_id = hcs.school_year_id
        WHERE rp.school_year_id = :sy AND rp.semester_index = :sem AND rp.evaluated_at_week = :wk
          AND {rbac_where}
        ORDER BY sub.name;
    """)
    s_rows = db.execute(subjects_sql, base_params).fetchall()

    grades_sql = text(f"""
        SELECT DISTINCT hcs.grade_id, hcs.grade_name
        FROM s360.fact_student_subject_risk_predictions rp
        JOIN s360.dim_homeroom_class_student hcs ON rp.student_code = hcs.student_code AND rp.school_year_id = hcs.school_year_id
        WHERE rp.school_year_id = :sy AND rp.semester_index = :sem AND rp.evaluated_at_week = :wk
          AND {rbac_where}
        ORDER BY hcs.grade_id;
    """)
    g_rows = db.execute(grades_sql, base_params).fetchall()

    classes_sql = text(f"""
        SELECT DISTINCT hcs.class_name
        FROM s360.fact_student_subject_risk_predictions rp
        JOIN s360.dim_homeroom_class_student hcs ON rp.student_code = hcs.student_code AND rp.school_year_id = hcs.school_year_id
        WHERE rp.school_year_id = :sy AND rp.semester_index = :sem AND rp.evaluated_at_week = :wk
          AND {rbac_where}
        ORDER BY hcs.class_name;
    """)
    c_rows = db.execute(classes_sql, base_params).fetchall()

    return {
        "subjects": [
            {"id": r.id, "name": r.name, "code": r.code, "subject_category": r.subject_category} for r in s_rows
        ],
        "grades": [{"grade_id": r.grade_id, "grade_name": r.grade_name} for r in g_rows],
        "classes": [r.class_name for r in c_rows if r.class_name],
    }
