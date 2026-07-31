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
from src.ews.inference_service import load_model, run_inference

logger = logging.getLogger(__name__)

# ============================================================================
# UPSERT SQL
# ============================================================================

UPSERT_SQL = """
INSERT INTO s360.fact_student_subject_risk_predictions (
    student_code, subject_id, school_year_id, semester_index,
    evaluated_at_week, evaluated_at_date,
    weighted_early_avg, weighted_late_avg, score_slope,
    score_volatility, max_drop, last_score,
    max_coefficient_so_far, high_weight_score_count, last_high_weight_score,
    lms_avg_score, lms_recent_drop, lms_submission_rate,
    lms_recent_submission_rate, lms_gradebook_gap,
    daily_absence_rate, unexcused_absent_rate,
    excused_absent_days, total_late_count,
    total_demerit_points, repeat_offense_count, severe_sanction_count,
    risk_score, risk_level, risk_probability
)
VALUES (
    :student_code, :subject_id, :school_year_id, :semester_index,
    :evaluated_at_week, CURRENT_DATE,
    :weighted_early_avg, :weighted_late_avg, :score_slope,
    :score_volatility, :max_drop, :last_score,
    :max_coefficient_so_far, :high_weight_score_count, :last_high_weight_score,
    :lms_avg_score, :lms_recent_drop, :lms_submission_rate,
    :lms_recent_submission_rate, :lms_gradebook_gap,
    :daily_absence_rate, :unexcused_absent_rate,
    :excused_absent_days, :total_late_count,
    :total_demerit_points, :repeat_offense_count, :severe_sanction_count,
    :risk_score, :risk_level, :risk_probability
)
ON CONFLICT (student_code, subject_id, school_year_id, semester_index, evaluated_at_week)
DO UPDATE SET
    risk_score = EXCLUDED.risk_score,
    risk_level = EXCLUDED.risk_level,
    risk_probability = EXCLUDED.risk_probability,
    evaluated_at_date = CURRENT_DATE;
"""

# Các cột bắt buộc phải có trong DataFrame trước khi persist (khớp với UPSERT_SQL).
# Nguồn: feature_extractor sinh 24 features; inference_service giữ chúng trong result.
UPSERT_REQUIRED_COLS = [
    "student_code", "subject_id", "school_year_id", "semester_index",
    "evaluated_at_week",
    "weighted_early_avg", "weighted_late_avg", "score_slope",
    "score_volatility", "max_drop", "last_score",
    "max_coefficient_so_far", "high_weight_score_count", "last_high_weight_score",
    "lms_avg_score", "lms_recent_drop", "lms_submission_rate",
    "lms_recent_submission_rate", "lms_gradebook_gap",
    "daily_absence_rate", "unexcused_absent_rate",
    "excused_absent_days", "total_late_count",
    "total_demerit_points", "repeat_offense_count", "severe_sanction_count",
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

    Returns:
        DataFrame kết quả đã persist vào DB
    """
    start_time = datetime.now()
    logger.info("=" * 60)
    logger.info("EWS Pipeline started: school_year=%d, semester=%d, week=%d, cutoff=%s",
                school_year_id, semester_index, evaluated_at_week, cutoff_date)
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

    # Step 2: Load model & inference
    logger.info("[Step 2/3] Running inference (skip_shap=%s)...", skip_shap)
    model = load_model()
    result = run_inference(model, X, return_shap=not skip_shap)
    logger.info("[Step 2/3] Done: %d predictions", len(result))

    # Step 3: Persist to DB
    logger.info("[Step 3/3] Persisting to DB...")
    # Thêm school_year_id, semester_index vào result trước khi persist
    result["school_year_id"] = school_year_id
    result["semester_index"] = semester_index
    persist_predictions(session, result)

    elapsed = (datetime.now() - start_time).total_seconds()
    logger.info("=" * 60)
    logger.info("Pipeline complete: %d predictions in %.2f seconds",
                len(result), elapsed)
    if skip_shap:
        logger.info("  (SHAP skipped — use --no-skip-shap to enable)")
    logger.info("=" * 60)

    return result
