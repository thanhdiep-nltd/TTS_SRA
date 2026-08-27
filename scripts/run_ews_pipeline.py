#!/usr/bin/env python3
"""
CLI Entry Point — EWS Inference Pipeline.

Usage:
    python scripts/run_ews_pipeline.py --school-year 2025 --semester 1 --week 8
    python scripts/run_ews_pipeline.py --school-year 2025 --semester 2 --week 26 --skip-shap

Args:
    --school-year   Năm học (VD: 2025)
    --semester      Học kỳ (1 hoặc 2)
    --week          Tuần đánh giá
                    HK1: [8, 11, 14, 16]
                    HK2: [23, 26, 29, 32, 34]
    --cutoff-date   (optional) Ngày cutoff, mặc định tính từ week
    --skip-shap     (optional) Bỏ qua SHAP để tăng tốc

Examples:
    # Chạy cho HK1 tuần 8 (có SHAP)
    python scripts/run_ews_pipeline.py --school-year 2025 --semester 1 --week 8

    # Chạy cho HK2 tuần 26 (bỏ qua SHAP — nhanh hơn)
    python scripts/run_ews_pipeline.py --school-year 2025 --semester 2 --week 26 --skip-shap

Tham khảo: plans/integration/plan_ews_model_integration.md
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date, timedelta
from pathlib import Path

# Đảm bảo root project nằm trong sys.path
_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from src.db.session import SessionLocal
from src.ews.pipeline_runner import run_pipeline

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


# ============================================================================
# HELPER: Tính cutoff_date từ week
# ============================================================================

# Ngày bắt đầu năm học mặc định (có thể override bằng --cutoff-date)
DEFAULT_SCHOOL_START = {
    1: date(2025, 9, 1),   # HK1: đầu tháng 9
    2: date(2026, 1, 15),  # HK2: giữa tháng 1
}


def estimate_cutoff_date(semester: int, week: int) -> date:
    """
    Ước tính cutoff_date từ semester và week.

    Công thức: start_date + (week - 1) * 7 ngày
    """
    start = DEFAULT_SCHOOL_START[semester]
    return start + timedelta(weeks=week - 1)


# ============================================================================
# VALIDATION
# ============================================================================

VALID_WEEKS = {
    1: {8, 11, 14, 16},
    2: {23, 26, 29, 32, 34},
}


def validate_semester(semester: int) -> None:
    if semester not in (1, 2):
        raise ValueError(f"semester must be 1 or 2, got {semester}")


def validate_week(semester: int, week: int) -> None:
    valid = VALID_WEEKS.get(semester, set())
    if week not in valid:
        logger.warning(
            "Week %d is not a standard checkpoint for semester %d. "
            "Standard checkpoints: %s",
            week, semester, sorted(valid),
        )


# ============================================================================
# MAIN
# ============================================================================


def main() -> None:
    parser = argparse.ArgumentParser(
        description="EWS Inference Pipeline — Extract Features → Inference → Persist",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--school-year", type=int, required=True,
        help="Năm học (VD: 2025)",
    )
    parser.add_argument(
        "--semester", type=int, required=True, choices=[1, 2],
        help="Học kỳ (1 hoặc 2)",
    )
    parser.add_argument(
        "--week", type=int, required=True,
        help="Tuần đánh giá (HK1: 5,8,11,14,16; HK2: 23,26,29,32,34)",
    )
    parser.add_argument(
        "--cutoff-date", type=str, default=None,
        help="Ngày cutoff (YYYY-MM-DD). Mặc định: tính từ week",
    )
    parser.add_argument(
        "--skip-shap", action="store_true", default=False,
        help="Bỏ qua SHAP TreeExplainer để tăng tốc",
    )
    parser.add_argument(
        "--model-version", type=str, default="v1_single",
        choices=["v1_single", "v2_ensemble"],
        help="Phiên bản model: v1_single (model đơn) hoặc v2_ensemble (factor-ensemble)",
    )
    parser.add_argument(
        "--so-school-id", type=int, default=None,
        help="Mã trường (VD: 1 cho Trường 1). Nếu không truyền, mặc định chạy toàn bộ các trường",
    )
    parser.add_argument(
        "--enable-llm", action="store_true", default=False,
        help="Kích hoạt LLM-based Forecasting cho nhóm học sinh thuộc điều kiện trigger",
    )
    parser.add_argument(
        "--dry-run-llm", action="store_true", default=False,
        help="Chỉ kiểm tra và in số bản ghi đủ điều kiện trigger LLM, KHÔNG gọi LLM API thật",
    )

    args = parser.parse_args()

    # Validate
    validate_semester(args.semester)
    validate_week(args.semester, args.week)

    # Xác định cutoff_date
    if args.cutoff_date:
        cutoff_date = date.fromisoformat(args.cutoff_date)
    else:
        cutoff_date = estimate_cutoff_date(args.semester, args.week)
    logger.info("Using cutoff_date: %s", cutoff_date)

    # Run pipeline
    session = SessionLocal()
    try:
        result = run_pipeline(
            session=session,
            school_year_id=args.school_year,
            semester_index=args.semester,
            evaluated_at_week=args.week,
            cutoff_date=cutoff_date,
            skip_shap=args.skip_shap,
            model_version=args.model_version,
            so_school_id=args.so_school_id,
            enable_llm=args.enable_llm,
            dry_run_llm=args.dry_run_llm,
        )
        logger.info("✅ Pipeline completed successfully: %d predictions", len(result))
    except Exception:
        logger.exception("❌ Pipeline failed")
        sys.exit(1)
    finally:
        session.close()


if __name__ == "__main__":
    main()
