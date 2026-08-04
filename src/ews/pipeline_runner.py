#!/usr/bin/env python3
"""
Pipeline Runner — Điều phối toàn bộ EWS Inference Pipeline.

Các hàm:
    run_pipeline() : Extract Features → Inference → Persist

Tham khảo: plans/integration/plan_ews_model_integration.md Section II.4
"""

from __future__ import annotations

import logging
from datetime import date, datetime

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.ews.feature_extractor import extract_live_features
from src.ews.inference_service import (
    compute_v1_group_contributions,
    load_ensemble,
    load_model,
    run_ensemble_inference,
    run_inference,
)

logger = logging.getLogger(__name__)

# ============================================================================
# UPSERT SQL
# ============================================================================

UPSERT_SQL = """
INSERT INTO s360.fact_student_subject_risk_predictions (
    student_code, so_school_id, subject_id, school_year_id, semester_index,
    evaluated_at_week, model_version, join_date, evaluated_at_date, cutoff_date,
    weighted_early_avg, weighted_late_avg, weighted_late_avg_imputed, score_slope,
    score_volatility, max_drop, last_score,
    max_coefficient_so_far, high_weight_score_count, last_high_weight_score,
    lms_avg_score, lms_recent_drop, lms_submission_rate,
    lms_recent_submission_rate, lms_gradebook_gap,
    daily_absence_rate, unexcused_absent_rate,
    excused_absent_days, total_late_count,
    total_demerit_points, repeat_offense_count, severe_sanction_count,
    score_risk, lms_risk, attendance_risk, behavior_risk,
    weight_score, weight_lms, weight_attendance, weight_behavior,
    risk_score, risk_level, risk_probability
)
VALUES (
    :student_code, :so_school_id, :subject_id, :school_year_id, :semester_index,
    :evaluated_at_week, :model_version, :join_date, CURRENT_DATE, :cutoff_date,
    :weighted_early_avg, :weighted_late_avg, :weighted_late_avg_imputed, :score_slope,
    :score_volatility, :max_drop, :last_score,
    :max_coefficient_so_far, :high_weight_score_count, :last_high_weight_score,
    :lms_avg_score, :lms_recent_drop, :lms_submission_rate,
    :lms_recent_submission_rate, :lms_gradebook_gap,
    :daily_absence_rate, :unexcused_absent_rate,
    :excused_absent_days, :total_late_count,
    :total_demerit_points, :repeat_offense_count, :severe_sanction_count,
    :score_risk, :lms_risk, :attendance_risk, :behavior_risk,
    :weight_score, :weight_lms, :weight_attendance, :weight_behavior,
    :risk_score, :risk_level, :risk_probability
)
ON CONFLICT (so_school_id, student_code, subject_id, school_year_id, semester_index, evaluated_at_week, model_version)
DO UPDATE SET
    so_school_id = EXCLUDED.so_school_id,
    join_date = EXCLUDED.join_date,
    evaluated_at_date = CURRENT_DATE,
    cutoff_date = EXCLUDED.cutoff_date,
    weighted_early_avg = EXCLUDED.weighted_early_avg,
    weighted_late_avg = EXCLUDED.weighted_late_avg,
    weighted_late_avg_imputed = EXCLUDED.weighted_late_avg_imputed,
    score_slope = EXCLUDED.score_slope,
    score_volatility = EXCLUDED.score_volatility,
    max_drop = EXCLUDED.max_drop,
    last_score = EXCLUDED.last_score,
    max_coefficient_so_far = EXCLUDED.max_coefficient_so_far,
    high_weight_score_count = EXCLUDED.high_weight_score_count,
    last_high_weight_score = EXCLUDED.last_high_weight_score,
    lms_avg_score = EXCLUDED.lms_avg_score,
    lms_recent_drop = EXCLUDED.lms_recent_drop,
    lms_submission_rate = EXCLUDED.lms_submission_rate,
    lms_recent_submission_rate = EXCLUDED.lms_recent_submission_rate,
    lms_gradebook_gap = EXCLUDED.lms_gradebook_gap,
    daily_absence_rate = EXCLUDED.daily_absence_rate,
    unexcused_absent_rate = EXCLUDED.unexcused_absent_rate,
    excused_absent_days = EXCLUDED.excused_absent_days,
    total_late_count = EXCLUDED.total_late_count,
    total_demerit_points = EXCLUDED.total_demerit_points,
    repeat_offense_count = EXCLUDED.repeat_offense_count,
    severe_sanction_count = EXCLUDED.severe_sanction_count,
    score_risk = EXCLUDED.score_risk,
    lms_risk = EXCLUDED.lms_risk,
    attendance_risk = EXCLUDED.attendance_risk,
    behavior_risk = EXCLUDED.behavior_risk,
    weight_score = EXCLUDED.weight_score,
    weight_lms = EXCLUDED.weight_lms,
    weight_attendance = EXCLUDED.weight_attendance,
    weight_behavior = EXCLUDED.weight_behavior,
    risk_score = EXCLUDED.risk_score,
    risk_level = EXCLUDED.risk_level,
    risk_probability = EXCLUDED.risk_probability;
"""

# Các cột bắt buộc phải có trong DataFrame trước khi persist (khớp với UPSERT_SQL).
# Nguồn: feature_extractor sinh 24 features; inference_service giữ chúng trong result.
UPSERT_REQUIRED_COLS = [
    "student_code", "so_school_id", "subject_id", "school_year_id", "semester_index",
    "evaluated_at_week", "model_version", "join_date", "cutoff_date",
    "weighted_early_avg", "weighted_late_avg", "weighted_late_avg_imputed", "score_slope",
    "score_volatility", "max_drop", "last_score",
    "max_coefficient_so_far", "high_weight_score_count", "last_high_weight_score",
    "lms_avg_score", "lms_recent_drop", "lms_submission_rate",
    "lms_recent_submission_rate", "lms_gradebook_gap",
    "daily_absence_rate", "unexcused_absent_rate",
    "excused_absent_days", "total_late_count",
    "total_demerit_points", "repeat_offense_count", "severe_sanction_count",
    "score_risk", "lms_risk", "attendance_risk", "behavior_risk",
    "weight_score", "weight_lms", "weight_attendance", "weight_behavior",
    "risk_score", "risk_level", "risk_probability",
]


# ============================================================================
# PUBLIC FUNCTIONS
# ============================================================================


def persist_predictions(session: Session, df: pd.DataFrame) -> None:
    """Batch UPSERT results into fact_student_subject_risk_predictions."""
    missing = [c for c in UPSERT_REQUIRED_COLS if c not in df.columns]
    if missing:
        raise ValueError(
            "Cannot persist predictions: missing required columns in result "
            f"DataFrame: {missing}"
        )
    # Lọc đúng các cột cần thiết (bỏ subject_category/grade_level/shap_drivers nếu có)
    rows = df[UPSERT_REQUIRED_COLS].to_dict("records")
    session.execute(text(UPSERT_SQL), rows)
    session.commit()
    logger.info("Persisted %d predictions to DB", len(rows))


def run_pipeline(
    session: Session,
    school_year_id: int,
    semester_index: int,
    evaluated_at_week: int,
    cutoff_date: date,
    skip_shap: bool = False,
    model_version: str = "v1_single",
) -> pd.DataFrame:
    """
    Pipeline tích hợp EWS hoàn chỉnh.

    Args:
        session: SQLAlchemy session (kết nối DB s360)
        school_year_id: Năm học (VD: 2025)
        semester_index: Học kỳ (1 hoặc 2)
        evaluated_at_week: Tuần đánh giá (VD: 8)
        cutoff_date: Ngày cutoff để lấy dữ liệu
        skip_shap: Nếu True, bỏ qua SHAP TreeExplainer để tăng tốc
        model_version: 'v1_single' (model đơn) hoặc 'v2_ensemble' (factor-ensemble)

    Returns:
        DataFrame kết quả đã persist vào DB
    """
    start_time = datetime.now()
    logger.info("=" * 60)
    logger.info("EWS Pipeline started: school_year=%d, semester=%d, week=%d, cutoff=%s, model=%s",
                school_year_id, semester_index, evaluated_at_week, cutoff_date, model_version)
    logger.info("=" * 60)

    # Step 1: Extract features
    logger.info("[Step 1/3] Extracting features...")
    X = extract_live_features(
        session=session,
        school_year_id=school_year_id,
        semester_index=semester_index,
        evaluated_at_week=evaluated_at_week,
        cutoff_date=cutoff_date,
    )
    logger.info("[Step 1/3] Done: %d rows x %d cols", len(X), len(X.columns))

    # Step 2: Load model & inference (theo model_version)
    logger.info("[Step 2/3] Running inference (model=%s, skip_shap=%s)...", model_version, skip_shap)
    if model_version == "v2_ensemble":
        models = load_ensemble()
        result = run_ensemble_inference(models, X, return_shap=False)
    else:
        model = load_model()
        result = run_inference(model, X, return_shap=not skip_shap)
        # v1 là model đơn: không có sub-score riêng từng yếu tố → None.
        # weight_* = mức đóng góp (%) HỌC ĐƯỢC từ model (SHAP theo nhóm), chung mọi học sinh.
        contrib = compute_v1_group_contributions()
        for col in ("score_risk", "lms_risk", "attendance_risk", "behavior_risk"):
            result[col] = None
        result["weight_score"] = contrib["score"]
        result["weight_lms"] = contrib["lms"]
        result["weight_attendance"] = contrib["attendance"]
        result["weight_behavior"] = contrib["behavior"]
    logger.info("[Step 2/3] Done: %d predictions", len(result))

    # Step 3: Persist to DB
    logger.info("[Step 3/3] Persisting to DB...")
    # Thêm school_year_id, semester_index, cutoff_date, model_version vào result trước khi persist
    result["school_year_id"] = school_year_id
    result["semester_index"] = semester_index
    result["cutoff_date"] = cutoff_date
    result["model_version"] = model_version
    persist_predictions(session, result)

    elapsed = (datetime.now() - start_time).total_seconds()
    logger.info("=" * 60)
    logger.info("Pipeline complete: %d predictions in %.2f seconds",
                len(result), elapsed)
    if skip_shap:
        logger.info("  (SHAP skipped — use --no-skip-shap to enable)")
    logger.info("=" * 60)

    return result
