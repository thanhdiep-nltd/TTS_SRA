# -*- coding: utf-8 -*-
"""
src/ews/feature_extractor.py — Trích xuất 24 Features cho EWS từ DB s360

Nguồn dữ liệu:
  - Context & Anchor (3 features): subject_id, subject_category, grade_level
    (+ metadata dự báo: evaluated_at_week, semester_index)
  - 9 Temporal: s360.fact_gradebooks UNION s360.fact_gradebooks_moet
  - 5 LMS: s360.fact_so_assignment_grade JOIN s360.dim_so_assignment
  - 4 Attendance: s360.fact_so_daily_attendance LEFT JOIN fact_absent_logs & late_attendances
  - 3 Behavior: s360.fact_behavior_logs
"""

import logging
from datetime import date, datetime, timedelta
from typing import Optional, Union

import pandas as pd
import numpy as np
from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# Danh sách 22 Features chuẩn cho CatBoost Model
EWS_FEATURE_COLS = [
    # Categorical + Context (3)
    "subject_id",
    "subject_category",
    "grade_level",
    # Temporal Scores (9)
    "weighted_early_avg",
    "weighted_late_avg",
    "score_slope",
    "score_volatility",
    "max_drop",
    "last_score",
    "max_coefficient_so_far",
    "high_weight_score_count",
    "last_high_weight_score",
    # LMS (5)
    "lms_avg_score",
    "lms_recent_drop",
    "lms_submission_rate",
    "lms_recent_submission_rate",
    "lms_gradebook_gap",
    # Attendance (4)
    "daily_absence_rate",
    "unexcused_absent_rate",
    "excused_absent_days",
    "total_late_count",
    # Behavior (3)
    "total_demerit_points",
    "repeat_offense_count",
    "severe_sanction_count",
]

# Categorical (context) vs Numeric feature columns — dùng để ép kiểu phía serve
CATEGORICAL_FEATURE_COLS = ["subject_id", "subject_category", "grade_level"]
NUMERIC_FEATURE_COLS = [c for c in EWS_FEATURE_COLS if c not in CATEGORICAL_FEATURE_COLS]


SQL_EXTRACT_FEATURES = """
WITH student_grades AS (
    -- Lấy grade_id từ dim_homeroom_class_student
    SELECT DISTINCT ON (student_code)
        student_code,
        grade_id AS grade_level
    FROM s360.dim_homeroom_class_student
    WHERE school_year_id = :school_year_id
),
subject_info AS (
    -- Lấy thông tin subject & subject_category
    SELECT
        id AS subject_id,
        COALESCE(subject_category,
            CASE
                WHEN code LIKE 'TOAN%' OR code LIKE '%MATH%' OR code IN ('LY', 'HOA', 'SINH', 'KHTN', 'IB_SCI') THEN 'MATH_SCIENCE'
                WHEN code LIKE '%ENG%' OR code IN ('VAN', 'ANH', 'LS_DL', 'CAM_ENG') THEN 'HUMANITIES'
                WHEN code IN ('TIN', 'ROBOTICS') THEN 'TECHNOLOGY'
                ELSE 'ARTS_PE'
            END
        ) AS subject_category
    FROM s360.dim_subject
),
all_scores AS (
    -- NGUỒN 1: fact_gradebooks (Cambridge/IB/Honor)
    -- YÊU CẦU NGHIỆP VỤ: KHÔNG cảnh báo EWS cho môn đánh giá Đạt/Không đạt (PASS_FAIL/REMARK,
    -- vd Thể dục, Mỹ thuật, Âm nhạc — final_grade=NULL nên temporal scores toàn NaN, CatBoost
    -- đẩy risk sai lên CRITICAL). Chỉ lấy môn tính điểm thang số (assessment_type='SCORED').
    SELECT
        fg.student_code,
        fg.subject_id,
        fg.semester_index,
        fg.final_grade,
        de.coefficient,
        fg.created_at,
        fg.school_year_id
    FROM s360.fact_gradebooks fg
    JOIN s360.dim_exam de ON fg.so_exam_id = de.id
    JOIN s360.dim_subject ds ON fg.subject_id = ds.id
    WHERE fg.is_locked = 1
        AND fg.school_year_id = :school_year_id
        AND COALESCE(ds.assessment_type, 'SCORED') = 'SCORED'

    UNION ALL

    -- NGUỒN 1b: fact_gradebooks_moet (Bộ GD)
    SELECT
        fgm.student_code,
        fgm.subject_id,
        fgm.semester_index,
        fgm.final_grade,
        dem.coefficient,
        fgm.created_at,
        fgm.school_year_id
    FROM s360.fact_gradebooks_moet fgm
    JOIN s360.dim_exam_moet dem ON fgm.gradebook_type_item_id = dem.gradebook_type_item_id
    JOIN s360.dim_subject dsm ON fgm.subject_id = dsm.id
    WHERE fgm.is_locked = 1
        AND fgm.school_year_id = :school_year_id
        AND COALESCE(dsm.assessment_type, 'SCORED') = 'SCORED'
),
score_series AS (
    SELECT
        s.*,
        EXTRACT(EPOCH FROM (s.created_at - sy.start_date)) / 86400 / 7 AS week_float
    FROM all_scores s
    JOIN s360.dim_school_year sy ON s.school_year_id = sy.id
    WHERE s.created_at <= :cutoff_date
        AND s.semester_index = :semester_index
        AND sy.start_date IS NOT NULL
),
medians AS (
    SELECT
        student_code,
        subject_id,
        semester_index,
        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY week_float) AS median_week
    FROM score_series
    GROUP BY student_code, subject_id, semester_index
),
diffs AS (
    SELECT
        student_code,
        subject_id,
        semester_index,
        LAG(final_grade) OVER (
            PARTITION BY student_code, subject_id, semester_index
            ORDER BY created_at
        ) - final_grade AS drop_amount
    FROM score_series
),
max_drops AS (
    SELECT
        student_code,
        subject_id,
        semester_index,
        MAX(drop_amount) AS max_drop
    FROM diffs
    WHERE drop_amount > 0
    GROUP BY student_code, subject_id, semester_index
),
temporal_features AS (
    SELECT
        ss.student_code,
        ss.subject_id,
        ss.semester_index,

        ROUND(
            SUM(CASE WHEN ss.week_float <= m.median_week
                     THEN ss.final_grade * ss.coefficient END)
            / NULLIF(SUM(CASE WHEN ss.week_float <= m.median_week
                              THEN ss.coefficient END), 0)
        , 2) AS weighted_early_avg,

        ROUND(
            SUM(CASE WHEN ss.week_float > m.median_week
                     THEN ss.final_grade * ss.coefficient END)
            / NULLIF(SUM(CASE WHEN ss.week_float > m.median_week
                              THEN ss.coefficient END), 0)
        , 2) AS weighted_late_avg,

        ROUND(
            (COVAR_POP(ss.week_float, ss.final_grade)
            / NULLIF(VAR_POP(ss.week_float), 0))::numeric
        , 4) AS score_slope,

        ROUND(STDDEV_POP(ss.final_grade), 4) AS score_volatility,

        COALESCE(md.max_drop, 0) AS max_drop,

        (ARRAY_AGG(ss.final_grade ORDER BY ss.created_at DESC))[1] AS last_score,

        MAX(ss.coefficient) AS max_coefficient_so_far,

        COUNT(CASE WHEN ss.coefficient >= 2.0 THEN 1 END) AS high_weight_score_count,

        (ARRAY_AGG(ss.final_grade ORDER BY CASE WHEN ss.coefficient >= 2.0 THEN ss.created_at END DESC NULLS LAST))[1] AS last_high_weight_score

    FROM score_series ss
    JOIN medians m
        ON ss.student_code = m.student_code
        AND ss.subject_id = m.subject_id
        AND ss.semester_index = m.semester_index
    LEFT JOIN max_drops md
        ON ss.student_code = md.student_code
        AND ss.subject_id = md.subject_id
        AND ss.semester_index = md.semester_index
    GROUP BY ss.student_code, ss.subject_id, ss.semester_index, m.median_week, md.max_drop
),
lms_features AS (
    SELECT
        fag.student_code,
        dsa.subject_id,
        ROUND(AVG(fag.final_grade), 2) AS lms_avg_score,
        ROUND(AVG(CASE WHEN dsa.due_date >= (:cutoff_date - INTERVAL '28 days')
                       THEN fag.final_grade END), 2) AS lms_recent_avg,
        COUNT(fag.id) * 1.0 / NULLIF(total.total_assigned, 0) AS lms_submission_rate,
        COUNT(CASE WHEN dsa.due_date >= (:cutoff_date - INTERVAL '28 days')
                   THEN fag.id END) * 1.0
            / NULLIF(total_recent.recent_assigned, 0) AS lms_recent_submission_rate

    FROM s360.fact_so_assignment_grade fag
    JOIN s360.dim_so_assignment dsa ON fag.assignment_id = dsa.assignment_id
    LEFT JOIN (
        SELECT subject_id, COUNT(*) AS total_assigned
        FROM s360.dim_so_assignment
        WHERE due_date <= :cutoff_date
        GROUP BY subject_id
    ) total ON dsa.subject_id = total.subject_id
    LEFT JOIN (
        SELECT subject_id, COUNT(*) AS recent_assigned
        FROM s360.dim_so_assignment
        WHERE due_date BETWEEN (:cutoff_date - INTERVAL '28 days') AND :cutoff_date
        GROUP BY subject_id
    ) total_recent ON dsa.subject_id = total_recent.subject_id
    WHERE fag.is_locked = 1
    GROUP BY fag.student_code, dsa.subject_id,
             total.total_assigned, total_recent.recent_assigned
),
attendance_features AS (
    SELECT
        fda.student_code,
        ROUND(SUM(fda.absent_periods) * 1.0 / NULLIF(SUM(fda.total_periods), 0), 4) AS daily_absence_rate,
        ROUND(SUM(fda.absent_no_permission) * 1.0 / NULLIF(SUM(fda.total_periods), 0), 4) AS unexcused_absent_rate,
        COALESCE(fal.excused_days, 0) AS excused_absent_days,
        COALESCE(fla.late_count, 0) AS total_late_count
    FROM s360.fact_so_daily_attendance fda
    LEFT JOIN (
        SELECT student_code, COUNT(DISTINCT absent_date) AS excused_days
        FROM s360.fact_absent_logs
        WHERE absent_date <= :cutoff_date AND is_approved = 1
        GROUP BY student_code
    ) fal ON fda.student_code = fal.student_code
    LEFT JOIN (
        SELECT student_code, COUNT(*) AS late_count
        FROM s360.fact_so_homeroom_class_late_attendances
        WHERE attendance_date <= :cutoff_date AND is_late = 1
        GROUP BY student_code
    ) fla ON fda.student_code = fla.student_code
    WHERE fda._date <= :cutoff_date AND fda.school_year_id = :school_year_id
    GROUP BY fda.student_code, fal.excused_days, fla.late_count
),
behavior_features AS (
    SELECT
        fbl.student_code,
        ROUND(SUM(CASE WHEN fbl.behavior_point < 0 THEN ABS(fbl.behavior_point) ELSE 0 END)::numeric, 2) AS total_demerit_points,
        COALESCE(rep.repeat_count, 0) AS repeat_offense_count,
        COUNT(CASE WHEN fbl.sanction_code IS NOT NULL THEN 1 END) AS severe_sanction_count
    FROM s360.fact_behavior_logs fbl
    LEFT JOIN (
        SELECT student_code, SUM(cnt - 1) AS repeat_count
        FROM (
            SELECT student_code, behavior_id, COUNT(*) AS cnt
            FROM s360.fact_behavior_logs
            WHERE comment_date <= :cutoff_date AND behavior_point < 0
            GROUP BY student_code, behavior_id
            HAVING COUNT(*) > 1
        ) t
        GROUP BY student_code
    ) rep ON fbl.student_code = rep.student_code
    WHERE fbl.comment_date <= :cutoff_date AND fbl.school_year_id = :school_year_id
    GROUP BY fbl.student_code, rep.repeat_count
)
SELECT
    tf.student_code,
    tf.subject_id,
    COALESCE(si.subject_category, 'MATH_SCIENCE') AS subject_category,
    COALESCE(sg.grade_level, 7) AS grade_level,
    tf.semester_index,
    tf.weighted_early_avg,
    tf.weighted_late_avg,
    tf.score_slope,
    tf.score_volatility,
    tf.max_drop,
    tf.last_score,
    tf.max_coefficient_so_far,
    tf.high_weight_score_count,
    tf.last_high_weight_score,
    lf.lms_avg_score,
    lf.lms_recent_avg,
    lf.lms_submission_rate,
    lf.lms_recent_submission_rate,
    af.daily_absence_rate,
    af.unexcused_absent_rate,
    af.excused_absent_days,
    af.total_late_count,
    bf.total_demerit_points,
    bf.repeat_offense_count,
    bf.severe_sanction_count
FROM temporal_features tf
LEFT JOIN subject_info si ON tf.subject_id = si.subject_id
LEFT JOIN student_grades sg ON tf.student_code = sg.student_code
LEFT JOIN lms_features lf ON tf.student_code = lf.student_code AND tf.subject_id = lf.subject_id
LEFT JOIN attendance_features af ON tf.student_code = af.student_code
LEFT JOIN behavior_features bf ON tf.student_code = bf.student_code;
"""


def extract_live_features(
    session: Session,
    school_year_id: int,
    semester_index: int,
    evaluated_at_week: int,
    cutoff_date: Optional[Union[date, str]] = None,
) -> pd.DataFrame:
    """
    Trích xuất DataFrame 24 Features (X) cho tất cả cặp (student_code, subject_id) tại mốc tuần.

    Args:
        session: SQLAlchemy Session / Connection
        school_year_id: ID năm học (vd: 2025)
        semester_index: Học kỳ (1 hoặc 2)
        evaluated_at_week: Tuần học đang đánh giá (vd: 8)
        cutoff_date: Ngày cutoff (date hoặc 'YYYY-MM-DD'). Nếu None, tự động tính từ tuần.

    Returns:
        pd.DataFrame chứa 24 features + student_code
    """
    if cutoff_date is None:
        base_start = date(school_year_id, 9, 5) if semester_index == 1 else date(school_year_id + 1, 1, 20)
        cutoff_date = base_start + timedelta(weeks=evaluated_at_week)
    elif isinstance(cutoff_date, str):
        cutoff_date = datetime.strptime(cutoff_date, "%Y-%m-%d").date()

    logger.info(f"Extracting live EWS features (SchoolYear={school_year_id}, Sem={semester_index}, Week={evaluated_at_week}, Cutoff={cutoff_date})...")

    params = {
        "school_year_id": school_year_id,
        "semester_index": semester_index,
        "cutoff_date": cutoff_date,
    }

    # Engine chung (src/db/session.py) set statement_timeout=3000ms cho MỌI kết nối. Query
    # extract EWS nặng hơn — đo thực tế ~3.5s ở week 14 (cutoff trễ → scan nhiều dòng hơn) —
    # nên bị cancel giữa chừng (QueryCanceled). Dùng SET LOCAL (chỉ hiệu lực trong transaction
    # hiện tại) để nâng timeout riêng cho query này lên 60s; sau commit/rollback sẽ trở về 3s,
    # KHÔNG ảnh hưởng phần còn lại của hệ thống.
    session.execute(text("SET LOCAL statement_timeout = 60000"))

    result = session.execute(text(SQL_EXTRACT_FEATURES), params)
    rows = result.fetchall()
    cols = result.keys()

    df = pd.DataFrame(rows, columns=cols)
    if df.empty:
        logger.warning(f"No records returned for EWS feature extraction at week {evaluated_at_week}")
        return pd.DataFrame(columns=["student_code"] + EWS_FEATURE_COLS)

    logger.info(f"Retrieved {len(df):,} raw feature rows from s360 DB")

    # Ép kiểu toàn bộ cột numeric → float64 NGAY SAU khi lấy dữ liệu. psycopg trả Decimal cho cột
    # numeric → DataFrame bị object dtype; trộn float (AVG/LMS) với Decimal (final_grade, last_score)
    # gây TypeError khi trừ. Loại trừ các cột categorical/context & key (được ép str ở bước 4-5).
    # Đặt ở ĐẦU để mọi phép tính derived features (lms_recent_drop, lms_gradebook_gap...) chạy float64.
    _NON_NUMERIC_COLS = {
        "student_code", "subject_id", "subject_category",
        "grade_level", "semester_index", "evaluated_at_week",
    }
    for _c in df.columns:
        if _c not in _NON_NUMERIC_COLS:
            df[_c] = pd.to_numeric(df[_c], errors="coerce").astype("float64")

    # =========================================================================
    # DERIVED FEATURES & NULL IMPUTATION
    # =========================================================================

    # 1. LMS Derived Features
    df["lms_avg_score"] = df["lms_avg_score"].fillna(5.0)
    lms_recent_avg_clean = df["lms_recent_avg"].fillna(df["lms_avg_score"])
    df["lms_recent_drop"] = df["lms_avg_score"] - lms_recent_avg_clean

    last_score_clean = df["last_score"].fillna(5.0)
    df["lms_gradebook_gap"] = df["lms_avg_score"] - last_score_clean

    # 2. LMS Submission rates missing -> fill 0.0
    df["lms_submission_rate"] = df["lms_submission_rate"].fillna(0.0)
    df["lms_recent_submission_rate"] = df["lms_recent_submission_rate"].fillna(0.0)

    # 3. Attendance & Behavior missing -> fill 0
    attendance_behavior_cols = [
        "daily_absence_rate",
        "unexcused_absent_rate",
        "excused_absent_days",
        "total_late_count",
        "total_demerit_points",
        "repeat_offense_count",
        "severe_sanction_count",
    ]
    for c in attendance_behavior_cols:
        if c in df.columns:
            df[c] = df[c].fillna(0)

    # 4. Context columns
    df["evaluated_at_week"] = evaluated_at_week
    df["semester_index"] = semester_index
    # Ép grade_level → str để KHỚP training (train_catboost_ews.preprocess_data ép toàn bộ
    # CAT_FEATURES thành str). CatBoost hash "6" != 6 → nếu để int, grade_level bị coi là unseen category.
    df["grade_level"] = df["grade_level"].fillna(7).astype(int).astype(str)

    # 5. Ép kiểu Categorical cho subject_id & subject_category (BẮT BUỘC cho CatBoost)
    df["subject_id"] = df["subject_id"].astype(str)
    df["subject_category"] = df["subject_category"].astype(str)

    # (Bước ép kiểu numeric → float64 đã thực hiện ngay sau khi tạo df, trước các phép tính derived,
    #  nên mọi cột numeric & derived đều đã là float64 tại thời điểm này.)

    # Reorder columns chuẩn: student_code, evaluated_at_week, semester_index + 24 features
    final_cols = ["student_code", "evaluated_at_week", "semester_index"] + EWS_FEATURE_COLS
    df = df[final_cols].copy()

    logger.info(f"Feature extraction complete: {df.shape[0]:,} rows, {len(EWS_FEATURE_COLS)} features")
    return df
