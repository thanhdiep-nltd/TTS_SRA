# -*- coding: utf-8 -*-
"""
src/ews/golden_set.py — Golden Set kiểm tra độ chính xác EWS v2_ensemble.

Mỗi case = 1 bộ 24 features + kỳ vọng risk_level (ground truth).
Chạy qua pipeline thật (load_ensemble -> run_ensemble_inference) rồi so sánh.

Dùng chung cho:
  - scripts/ews_golden_set.py (CLI)
  - API GET /ews/golden-set (dashboard demo)
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.ews.inference_service import load_ensemble, run_ensemble_inference

# ============================================================================
# ĐỊNH NGHĨA CASE
# ============================================================================

# Feature mẫu cho từng "mức" của mỗi yếu tố
SCORE_GOOD = dict(weighted_early_avg=9.0, weighted_late_avg=9.0, score_slope=0.1,
                  score_volatility=0.2, max_drop=0.3, last_score=9.0,
                  max_coefficient_so_far=1.0, high_weight_score_count=0, last_high_weight_score=0.0)
SCORE_BAD = dict(weighted_early_avg=3.0, weighted_late_avg=2.5, score_slope=-0.5,
                 score_volatility=1.5, max_drop=3.0, last_score=2.5,
                 max_coefficient_so_far=0.5, high_weight_score_count=3, last_high_weight_score=2.0)
SCORE_MID = dict(weighted_early_avg=6.0, weighted_late_avg=5.5, score_slope=-0.1,
                 score_volatility=0.8, max_drop=1.2, last_score=5.5,
                 max_coefficient_so_far=0.8, high_weight_score_count=1, last_high_weight_score=5.0)

LMS_GOOD = dict(lms_avg_score=9.0, lms_recent_drop=0.0, lms_submission_rate=1.0,
                lms_recent_submission_rate=1.0, lms_gradebook_gap=0.0)
LMS_BAD = dict(lms_avg_score=4.0, lms_recent_drop=2.0, lms_submission_rate=0.3,
               lms_recent_submission_rate=0.2, lms_gradebook_gap=1.5)

ATT_GOOD = dict(daily_absence_rate=0.0, unexcused_absent_rate=0.0,
                excused_absent_days=0, total_late_count=0)
ATT_BAD = dict(daily_absence_rate=0.8, unexcused_absent_rate=0.7,
               excused_absent_days=10, total_late_count=5)

BEH_GOOD = dict(total_demerit_points=0, repeat_offense_count=0, severe_sanction_count=0)
BEH_BAD = dict(total_demerit_points=15, repeat_offense_count=5, severe_sanction_count=2)

# Context (categorical) — dùng chung
CTX = dict(subject_id="TOAN", subject_category="MATH_SCIENCE", grade_level="G10")

# Danh sách case: (id, mô tả, feature dict, kỳ vọng)
CASES = [
    ("GS-01", "Học giỏi + chăm chỉ", {**CTX, **SCORE_GOOD, **LMS_GOOD, **ATT_GOOD, **BEH_GOOD}, "LOW"),
    ("GS-02", "Học giỏi + NGHỈ NHIỀU", {**CTX, **SCORE_GOOD, **LMS_GOOD, **ATT_BAD, **BEH_GOOD}, "HIGH"),
    ("GS-03", "Học giỏi + hành vi xấu", {**CTX, **SCORE_GOOD, **LMS_GOOD, **ATT_GOOD, **BEH_BAD}, "HIGH"),
    ("GS-04", "Học kém + chăm chỉ", {**CTX, **SCORE_BAD, **LMS_GOOD, **ATT_GOOD, **BEH_GOOD}, "HIGH"),
    ("GS-05", "Học kém + nghỉ nhiều + hành vi xấu", {**CTX, **SCORE_BAD, **LMS_GOOD, **ATT_BAD, **BEH_BAD}, "CRITICAL"),
    ("GS-06", "Học trung bình + bỏ bài LMS", {**CTX, **SCORE_MID, **LMS_BAD, **ATT_GOOD, **BEH_GOOD}, "MODERATE"),
    ("GS-07", "Học giỏi + mọi thứ tốt (đối chứng)", {**CTX, **SCORE_GOOD, **LMS_GOOD, **ATT_GOOD, **BEH_GOOD}, "LOW"),
    # GS-08: học sinh mới — toàn bộ feature NaN -> mọi yếu tố bị loại -> MODERATE (trung tính)
    ("GS-08", "Học sinh mới (ít dữ liệu)", {**CTX, **{k: np.nan for k in SCORE_GOOD},
                                            **{k: np.nan for k in LMS_GOOD},
                                            **{k: np.nan for k in ATT_GOOD},
                                            **{k: np.nan for k in BEH_GOOD}}, "MODERATE"),
]


def run_golden_set() -> dict:
    """Chạy golden set, trả về dict kết quả (cases + accuracy) cho API/CLI."""
    rows = []
    for cid, desc, feats, _exp in CASES:
        rows.append({"student_code": cid, "evaluated_at_week": 8, **feats})
    X = pd.DataFrame(rows)

    models = load_ensemble()
    result = run_ensemble_inference(models, X, return_shap=False)

    cases = []
    n_pass = 0
    for i, (cid, desc, feats, expected) in enumerate(CASES):
        pred = result.iloc[i]["risk_level"]
        ok = pred == expected
        n_pass += int(ok)
        cases.append({
            "id": cid,
            "description": desc,
            "predicted": pred,
            "expected": expected,
            "passed": ok,
            "risk_score": round(float(result.iloc[i]["risk_score"]), 2),
            "score_risk": _fmt(result.iloc[i]["score_risk"]),
            "lms_risk": _fmt(result.iloc[i]["lms_risk"]),
            "attendance_risk": _fmt(result.iloc[i]["attendance_risk"]),
            "behavior_risk": _fmt(result.iloc[i]["behavior_risk"]),
            "weight_attendance": _fmt(result.iloc[i]["weight_attendance"], 3),
            "weight_behavior": _fmt(result.iloc[i]["weight_behavior"], 3),
            # Bộ 24 thông số đầu vào (đã sanitize NaN -> None) để UI hiển thị chi tiết.
            "features": {k: _fmt_feature(v) for k, v in feats.items()},
        })

    total = len(CASES)
    return {
        "total": total,
        "passed": n_pass,
        # accuracy là HỆ SỐ 0..1 (vd 0.875) để khớp logic frontend (nhân 100 để hiện %).
        "accuracy": round(n_pass / total, 4),
        "cases": cases,
    }


def _fmt(v, ndigits: int = 1) -> float | None:
    # pd.isna chặn cả None lẫn np.nan — tránh float('nan') lọt vào JSON gây lỗi 500.
    if v is None or pd.isna(v):
        return None
    return round(float(v), ndigits)


def _fmt_feature(v) -> float | str | None:
    """Sanitize 1 feature đầu vào: giữ string (categorical), làm tròn số, NaN -> None."""
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    if isinstance(v, str):
        return v
    try:
        return round(float(v), 3)
    except (TypeError, ValueError):
        return str(v)
