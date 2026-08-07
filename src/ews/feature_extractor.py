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
-- LƯU Ý HIỆU NĂNG: PostgreSQL 12+ mặc định INLINE mọi CTE. Nếu để mặc định, CTE
-- lms_features (nặng: quét fact_so_assignment_grade) bị nhúng thành subquery trong
-- "LEFT JOIN lms_features lf ON tf.student_code=lf.student_code AND ..." → planner
-- chọn Nested Loop và TÍNH LẠI lms_features cho TỪNG (student, subject) (loops=7158,
-- ~86s → vượt statement_timeout=60s). Vì vậy dùng AS MATERIALIZED để mỗi CTE chính
-- được tính ĐÚNG 1 LẦN rồi join bằng hash join (dữ liệu nhỏ: vài chục nghìn dòng).
WITH student_grades AS MATERIALIZED (
    -- Lấy grade_id + so_school_id + join_date từ dim_homeroom_class_student
    -- (cần so_school_id để giới hạn mẫu số tỷ lệ nộp bài LMS theo đúng trường của học sinh;
    --  join_date dùng cho cửa sổ hiện diện [join_date, cutoff] phân loại 3 bucket LMS — M2)
    SELECT DISTINCT ON (student_code)
        student_code,
        grade_id AS grade_level,
        so_school_id,
        COALESCE(join_date, CAST(:semester_start AS DATE)) AS join_date,
        join_date AS join_date_raw
    FROM s360.dim_homeroom_class_student
    WHERE school_year_id = :school_year_id
      AND (CAST(:so_school_id AS INTEGER) IS NULL OR so_school_id = CAST(:so_school_id AS INTEGER))
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
all_scores AS MATERIALIZED (
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

    -- FIX DOUBLE-COUNT: 2 bảng KHÔNG phải mirror mà được TÁCH theo loại môn:
    --   • fact_gradebooks      = môn chuẩn QUỐC TẾ (9-15: CAM/IB/Tin/STEM/Honor)
    --   • fact_gradebooks_moet = môn chuẩn QUỐC GIA/Bộ GD (1-8, 106-111) — GỒM CẢ môn
    --     PASS_FAIL (16-18: Thể dục, Mỹ thuật, Âm nhạc; final_grade=NULL, nhận xét ở comment)
    -- Mỗi môn chỉ nằm ở ĐÚNG 1 bảng → giữa 2 bảng KHÔNG có dòng trùng lặp, nên UNION
    -- (thay vì UNION ALL) chỉ là phòng thủ (defensive dedupe) — nếu sau này có dữ liệu
    -- seed chưa tách bảng thì điểm vẫn không bị đếm 2 lần (tránh early/late avg, slope,
    -- volatility bị bóp méo). Data agents truy vấn fact_gradebooks trực tiếp (môn quốc tế)
    -- vẫn hoạt động bình thường.
    UNION

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
score_series AS MATERIALIZED (
    SELECT
        s.*,
        EXTRACT(EPOCH FROM (s.created_at - sy.start_date)) / 86400 / 7 AS week_float
    FROM all_scores s
    JOIN s360.dim_school_year sy ON s.school_year_id = sy.id
    WHERE s.created_at <= CAST(:cutoff_date AS TIMESTAMPTZ)
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
temporal_features AS MATERIALIZED (
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

        (ARRAY_AGG(ss.final_grade ORDER BY ss.created_at DESC) FILTER (WHERE ss.coefficient >= 2.0))[1] AS last_high_weight_score

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
lms_features AS MATERIALIZED (
    -- M2 — PHÂN LOẠI 3 BUCKET LMS thay vì impute 5.0/0.0 mù:
    --   • NỘP            : submitted > 0                  → avg thực, rate = submitted/expected
    --   • BỎ KHÔNG LÀM   : submitted = 0 AND expected > 0 → rate = 0.0 (phạt rủi ro), avg = NULL
    --   • CHUYỂN TRƯỜNG  : submitted = 0 AND expected = 0 → rate = NULL (không phạt), avg = NULL
    --   Với  expected (đáng lẽ nộp) = số bài do trong cửa sổ hiện diện [join_date, cutoff].
    -- Để có hàng cho học sinh KHÔNG nộp (không có dòng nào trong fact_so_assignment_grade),
    -- population được xây bằng JOIN từ student_grades × assignments (không còn inner join từ
    -- fact_so_assignment_grade như cũ → học sinh bỏ bài / chuyển trường vẫn xuất hiện).
    -- BUG >100% (đã sửa trước đó) vẫn được giữ: tử/mẫu số cùng giới hạn
    -- due_date<=cutoff + semester_index + (so_school_id, grade_id) của học sinh.
    WITH pop AS MATERIALIZED (
        -- Population: mọi (student × subject) có bài tập do trong học kỳ này
        SELECT
            sg.student_code,
            dsa.subject_id,
            sg.join_date_raw
        FROM student_grades sg
        JOIN (
            SELECT DISTINCT so_school_id, grade_id, semester_index, subject_id
            FROM s360.dim_so_assignment
            WHERE semester_index = :semester_index
              AND due_date <= CAST(:cutoff_date AS DATE)
        ) dsa
            ON dsa.so_school_id = sg.so_school_id
           AND dsa.grade_id = sg.grade_level
    ),
    exp AS MATERIALIZED (
        -- ĐÁNG LẼ NỘP: số bài do trong cửa sổ hiện diện [join_date, cutoff]
        SELECT
            sg.student_code,
            dsa.subject_id,
            COUNT(*) AS lms_expected,
            COUNT(*) FILTER (WHERE dsa.due_date >= (CAST(:cutoff_date AS DATE) - 28)) AS lms_recent_expected
        FROM student_grades sg
        JOIN s360.dim_so_assignment dsa
            ON dsa.so_school_id = sg.so_school_id
           AND dsa.grade_id = sg.grade_level
           AND dsa.semester_index = :semester_index
        WHERE dsa.due_date <= CAST(:cutoff_date AS DATE)
          AND dsa.due_date >= sg.join_date
        GROUP BY sg.student_code, dsa.subject_id
    ),
    sub AS MATERIALIZED (
        -- THỰC NỘP: số bài HS có dòng chấm điểm trong cửa sổ hiện diện
        SELECT
            fag.student_code,
            dsa.subject_id,
            COUNT(fag.id) AS lms_submitted,
            ROUND(AVG(fag.final_grade), 2) AS lms_avg_score,
            ROUND(AVG(CASE WHEN dsa.due_date >= (CAST(:cutoff_date AS DATE) - 28)
                           THEN fag.final_grade END), 2) AS lms_recent_avg,
            COUNT(CASE WHEN dsa.due_date >= (CAST(:cutoff_date AS DATE) - 28)
                       THEN fag.id END) AS lms_recent_submitted
        FROM s360.fact_so_assignment_grade fag
        JOIN s360.dim_so_assignment dsa ON fag.assignment_id = dsa.assignment_id
        JOIN student_grades sg ON fag.student_code = sg.student_code
        WHERE (fag.is_locked = 1 OR fag.final_grade IS NOT NULL)
          AND dsa.due_date <= CAST(:cutoff_date AS DATE)
          AND dsa.due_date >= sg.join_date
          AND dsa.semester_index = :semester_index
          AND dsa.so_school_id = sg.so_school_id
          AND dsa.grade_id = sg.grade_level
        GROUP BY fag.student_code, dsa.subject_id
    )
    SELECT
        pop.student_code,
        pop.subject_id,
        -- M2 — ĐTB LMS theo 3 bucket (đồng bộ với generator train):
        --   • NỘP            : submitted > 0                  → avg thực
        --   • BỎ KHÔNG LÀM   : submitted = 0 AND expected > 0 → 0.0 (có trách nhiệm, phạt rủi ro)
        --   • CHUYỂN TRƯỜNG  : submitted = 0 AND expected = 0 → NULL (không phạt)
        CASE
            WHEN COALESCE(sub.lms_submitted, 0) > 0 THEN sub.lms_avg_score
            WHEN COALESCE(exp.lms_expected, 0) > 0 THEN 0.0
            ELSE NULL
        END AS lms_avg_score,
        CASE
            WHEN COALESCE(sub.lms_recent_submitted, 0) > 0 THEN sub.lms_recent_avg
            WHEN COALESCE(exp.lms_recent_expected, 0) > 0 THEN 0.0
            ELSE NULL
        END AS lms_recent_avg,
        CASE
            WHEN COALESCE(sub.lms_submitted, 0) > 0
                THEN ROUND(COALESCE(sub.lms_submitted, 0) * 1.0 / NULLIF(exp.lms_expected, 0), 4)
            WHEN COALESCE(exp.lms_expected, 0) > 0 THEN 0.0
            ELSE NULL
        END AS lms_submission_rate,
        CASE
            WHEN COALESCE(sub.lms_recent_submitted, 0) > 0
                THEN ROUND(COALESCE(sub.lms_recent_submitted, 0) * 1.0 / NULLIF(exp.lms_recent_expected, 0), 4)
            WHEN COALESCE(exp.lms_recent_expected, 0) > 0 THEN 0.0
            ELSE NULL
        END AS lms_recent_submission_rate,
        pop.join_date_raw AS join_date
    FROM pop
    LEFT JOIN exp ON pop.student_code = exp.student_code AND pop.subject_id = exp.subject_id
    LEFT JOIN sub ON pop.student_code = sub.student_code AND pop.subject_id = sub.subject_id
),
attendance_features AS MATERIALIZED (
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
        WHERE absent_date <= CAST(:cutoff_date AS DATE) AND is_approved = 1
        GROUP BY student_code
    ) fal ON fda.student_code = fal.student_code
    LEFT JOIN (
        SELECT student_code, COUNT(*) AS late_count
        FROM s360.fact_so_homeroom_class_late_attendances
        WHERE attendance_date <= CAST(:cutoff_date AS DATE) AND is_late = 1
        GROUP BY student_code
    ) fla ON fda.student_code = fla.student_code
    WHERE fda._date <= CAST(:cutoff_date AS DATE) AND fda.school_year_id = :school_year_id
    GROUP BY fda.student_code, fal.excused_days, fla.late_count
),
behavior_features AS MATERIALIZED (
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
            WHERE comment_date <= CAST(:cutoff_date AS DATE) AND behavior_point < 0
            GROUP BY student_code, behavior_id
            HAVING COUNT(*) > 1
        ) t
        GROUP BY student_code
    ) rep ON fbl.student_code = rep.student_code
    WHERE fbl.comment_date <= CAST(:cutoff_date AS DATE) AND fbl.school_year_id = :school_year_id
    GROUP BY fbl.student_code, rep.repeat_count
)
SELECT
    tf.student_code,
    sg.so_school_id,
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
    lf.join_date,
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
LEFT JOIN behavior_features bf ON tf.student_code = bf.student_code
-- GUARD DỮ LIỆU MỒ CÔI: học sinh có điểm (temporal_features) nhưng KHÔNG có bản ghi
-- homeroom/khối/trường trong dim_homeroom_class_student → sg.so_school_id = NULL.
-- Không thể gán trường nào để persist/tenant isolation → loại bỏ (tránh lỗi astype(int) trên NaN).
WHERE sg.so_school_id IS NOT NULL;
"""


def extract_live_features(
    session: Session,
    school_year_id: int,
    semester_index: int,
    evaluated_at_week: int,
    cutoff_date: Optional[Union[date, str]] = None,
    so_school_id: Optional[int] = None,
) -> pd.DataFrame:
    """
    Trích xuất DataFrame 24 Features (X) cho tất cả cặp (student_code, subject_id) tại mốc tuần.

    Args:
        session: SQLAlchemy Session / Connection
        school_year_id: ID năm học (vd: 2025)
        semester_index: Học kỳ (1 hoặc 2)
        evaluated_at_week: Tuần học đang đánh giá (vd: 8)
        cutoff_date: Ngày cutoff (date hoặc 'YYYY-MM-DD'). Nếu None, tự động tính từ tuần.
        so_school_id: Nếu cho, chỉ trích xuất học sinh của trường này (BGH control panel).
            None = toàn bộ trường (hành vi cũ).

    Returns:
        pd.DataFrame chứa 24 features + student_code
    """
    base_start = date(school_year_id, 9, 5) if semester_index == 1 else date(school_year_id + 1, 1, 20)
    if cutoff_date is None:
        cutoff_date = base_start + timedelta(weeks=evaluated_at_week)
    elif isinstance(cutoff_date, str):
        cutoff_date = datetime.strptime(cutoff_date, "%Y-%m-%d").date()

    logger.info(f"Extracting live EWS features (SchoolYear={school_year_id}, Sem={semester_index}, Week={evaluated_at_week}, Cutoff={cutoff_date})...")

    params = {
        "school_year_id": school_year_id,
        "semester_index": semester_index,
        "cutoff_date": cutoff_date,
        "semester_start": base_start,
        "so_school_id": so_school_id,
    }

    # Engine chung (src/db/session.py) set statement_timeout=3000ms cho MỌI kết nối. Query
    # extract EWS xử lý toàn trường trên nhiều fact table lớn (fact_so_assignment_grade ~133k,
    # fact_so_daily_attendance ~190k, fact_gradebooks(+moet) ~91k, fact_behavior_logs ~14k) nên
    # cần thời gian thực thi đáng kể — đo thực tế ~78.8s (trước MATERIALIZED) và vẫn >60s sau khi
    # đã MATERIALIZED toàn bộ CTE chính + ANALYZE stats mới. Dùng SET LOCAL (chỉ hiệu lực trong
    # transaction hiện tại) để nâng timeout riêng cho query này lên 300s; sau commit/rollback sẽ
    # trở về 3s, KHÔNG ảnh hưởng phần còn lại của hệ thống.
    session.execute(text("SET LOCAL statement_timeout = 300000"))

    # ROOT CAUSE timeout (2026-08): dù MATERIALIZED + ANALYZE, query vẫn >300s vì planner MISESTIMATE
    # row count trầm trọng → chọn kế hoạch Nested Loop bệnh lý:
    #   - lms_features: outer Hash Join (197 assignment × 1009 HS) est rows~5 nhưng THỰC TẾ ~198k cặp,
    #     kéo theo Index Scan fact_so_assignment_grade rows~59 chạy cho TỪNG cặp → ~198k × index scan.
    #   - temporal_features: Nested Loop quanh CTE Scan score_series (est 1 row, thực tế ~80k) → re-sort lặp.
    # Fix: buộc planner chỉ dùng Hash/Merge join (enable_nestloop=off) — tất cả fact table <200k rows
    # nên hash join luôn tối ưu. Đã xác nhận bằng diag_plan.py: plan NLOFF hết Nested Loop, lms inner
    # thành Hash Join rows~11721 (khớp thực tế). SET LOCAL → chỉ hiệu lực transaction này.
    session.execute(text("SET LOCAL enable_nestloop = off"))

    result = session.execute(text(SQL_EXTRACT_FEATURES), params)
    rows = result.fetchall()
    cols = result.keys()

    df = pd.DataFrame(rows, columns=cols)
    if df.empty:
        logger.warning(f"No records returned for EWS feature extraction at week {evaluated_at_week}")
        return pd.DataFrame(columns=["student_code", "evaluated_at_week", "semester_index", "join_date"] + EWS_FEATURE_COLS)

    logger.info(f"Retrieved {len(df):,} raw feature rows from s360 DB")

    # Ép kiểu toàn bộ cột numeric → float64 NGAY SAU khi lấy dữ liệu. psycopg trả Decimal cho cột
    # numeric → DataFrame bị object dtype; trộn float (AVG/LMS) với Decimal (final_grade, last_score)
    # gây TypeError khi trừ. Loại trừ các cột categorical/context & key (được ép str ở bước 4-5).
    # Đặt ở ĐẦU để mọi phép tính derived features (lms_recent_drop, lms_gradebook_gap...) chạy float64.
    _NON_NUMERIC_COLS = {
        "student_code", "subject_id", "subject_category",
        "grade_level", "semester_index", "evaluated_at_week", "join_date",
        "so_school_id",
    }
    for _c in df.columns:
        if _c not in _NON_NUMERIC_COLS:
            df[_c] = pd.to_numeric(df[_c], errors="coerce").astype("float64")

    # =========================================================================
    # DERIVED FEATURES & NULL IMPUTATION
    # =========================================================================

    # 1. LMS Derived Features
    # M2: KHÔNG impute 5.0 cho lms_avg_score nữa — giữ NULL cho học sinh không có điểm LMS thật.
    # CatBoost xử lý NaN native (nhánh riêng); model phải retrain với data chứa NULL (xem M2-C1).
    lms_recent_avg_clean = df["lms_recent_avg"].fillna(df["lms_avg_score"])
    df["lms_recent_drop"] = df["lms_avg_score"] - lms_recent_avg_clean

    last_score_clean = df["last_score"].fillna(5.0)
    df["lms_gradebook_gap"] = df["lms_avg_score"] - last_score_clean

    # 2. LMS Submission rates — KHÔNG fillna(0.0): SQL đã trả 0.0 cho BỎ KHÔNG LÀM và NULL cho
    #    CHUYỂN TRƯỜNG (không phạt). Giữ NULL để CatBoost học đúng 3 bucket.

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

    # 3b. SMART TEMPORAL IMPUTATION (đồng bộ với training generator — tránh train/serve skew)
    # Training generator (compute_features_at_checkpoint) đã impute:
    #   • weighted_late_avg = weighted_early_avg khi chưa có điểm nửa sau kỳ (giả định phong độ duy trì)
    #   • score_slope = 0.0 khi chưa đủ 2 đầu điểm (chưa có xu hướng)
    # Nhưng serve-side trước đây để NULL → CatBoost coi nhánh NaN là "chưa hoàn thành/rủi ro",
    # gây False Alarm: học sinh ĐTB 8.5 vẫn bị score_risk ~66%. Impute cùng quy tắc để khớp training.
    if "weighted_late_avg" in df.columns and "weighted_early_avg" in df.columns:
        # Đánh dấu những dòng bị impute (chưa có điểm nửa sau kỳ thật) để UI hiển thị "—"
        # thay vì giá trị giả định (tránh gây hiểu lầm). Giá trị impute vẫn dùng cho model.
        df["weighted_late_avg_imputed"] = df["weighted_late_avg"].isna() & df["weighted_early_avg"].notna()
        df["weighted_late_avg"] = df["weighted_late_avg"].fillna(df["weighted_early_avg"])
    else:
        df["weighted_late_avg_imputed"] = False
    if "score_slope" in df.columns:
        df["score_slope"] = df["score_slope"].fillna(0.0)

    # 3c. FIX TRAIN/SERVE SKEW — last_high_weight_score (Phương án C):
    # Khi học sinh KHÔNG có bài hệ số lớn (high_weight_score_count=0), serve-side SQL trả NULL
    # (ARRAY_AGG FILTER trả NULL khi không có phần tử).
    # → GIỮ NULL THẬT (KHÔNG impute) — đồng bộ với training generator (compute_features_at_checkpoint
    #   đã sửa thành NaN). CatBoost xử lý NaN native (nhánh riêng), model học "không có bài hệ số lớn"
    #   là một trạng thái riêng, KHÔNG phạt như rủi ro cao.
    # (Trước đây impute = weighted_early_avg gây hiểu lầm: feature vẫn xuất hiện trong Top 5 SHAP
    #   với giá trị giả định dù thực tế NULL.)

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

    # Reorder columns chuẩn: student_code, evaluated_at_week, semester_index, join_date + 24 features
    # + weighted_late_avg_imputed (cờ đánh dấu giá trị ĐTB Nửa Sau Kỳ bị impute — chỉ để persist/UI,
    # KHÔNG phải feature của model).
    final_cols = ["student_code", "so_school_id", "evaluated_at_week", "semester_index", "join_date"] + EWS_FEATURE_COLS + ["weighted_late_avg_imputed"]
    df = df[final_cols].copy()
    df["weighted_late_avg_imputed"] = df["weighted_late_avg_imputed"].astype(bool)
    # so_school_id giữ nguyên kiểu int (không phải feature của model, chỉ để persist/tenant isolation).
    # Học sinh mồ côi (có điểm nhưng thiếu bản ghi trường/khối) đã bị loại ở SQL (WHERE sg.so_school_id
    # IS NOT NULL) nên cột này không còn NULL → ép int an toàn.
    df["so_school_id"] = df["so_school_id"].astype(int)

    logger.info(f"Feature extraction complete: {df.shape[0]:,} rows, {len(EWS_FEATURE_COLS)} features")
    return df
