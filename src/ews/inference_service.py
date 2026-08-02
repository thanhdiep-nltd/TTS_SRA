#!/usr/bin/env python3
"""
Runtime Inference Service — Load model, predict, SHAP.

Các hàm:
    load_model()            : Load CatBoost model từ .cbm file
    compute_risk_score()    : [0.00, 100.00] từ probability matrix
    assign_risk_level()     : argmax → LOW/MODERATE/HIGH/CRITICAL
    compute_shap_drivers()  : Top 3 features theo |SHAP|
    run_inference()         : Pipeline inference hoàn chỉnh

Tham khảo: plans/integration/plan_ews_model_integration.md Section II.2
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import catboost as cb
import numpy as np
import pandas as pd
import shap

logger = logging.getLogger(__name__)

# ============================================================================
# CONSTANTS
# ============================================================================

MODEL_PATH = Path("src/models/gbdt/saved/catboost_ews_model.cbm")
CAT_FEATURES = ["subject_id", "subject_category", "grade_level"]  # same as training

# Trọng số risk score — giống training
RISK_SCORE_WEIGHTS = np.array([0.00, 0.35, 0.70, 1.00], dtype=np.float64)
RISK_LEVELS = ["LOW", "MODERATE", "HIGH", "CRITICAL"]

# SHAP: số lượng mẫu tối đa để tính SHAP (tránh O(n²))
SHAP_MAX_SAMPLES = 100


# ============================================================================
# PUBLIC FUNCTIONS
# ============================================================================


def load_model(path: Path = MODEL_PATH) -> cb.CatBoostClassifier:
    """Load CatBoost model từ .cbm file."""
    if not path.exists():
        raise FileNotFoundError(f"Model file not found: {path}")
    logger.info("Loading model from %s", path)
    model = cb.CatBoostClassifier()
    model.load_model(str(path))
    logger.info("Model loaded: iterations=%d", model.tree_count_)
    return model


def compute_risk_score(probs: np.ndarray) -> np.ndarray:
    """
    Tính risk_score [0, 100] từ probability matrix (N, 4).

    Công thức:
        risk_score = (0.00*P(LOW) + 0.35*P(MOD) + 0.70*P(HIGH) + 1.00*P(CRIT)) * 100

    Giải thích:
        LOW=0.00 → không rủi ro → score ~0
        MODERATE=0.35 → rủi ro nhẹ
        HIGH=0.70 → rủi ro cao
        CRITICAL=1.00 → rủi ro cực cao → score ~100
    """
    raw = probs @ RISK_SCORE_WEIGHTS  # (N,)
    return np.round(raw * 100.0, 2)


def assign_risk_level(probs: np.ndarray) -> np.ndarray:
    """argmax trên 4 classes → LOW/MODERATE/HIGH/CRITICAL."""
    return np.array([RISK_LEVELS[i] for i in probs.argmax(axis=1)])


def compute_shap_drivers(
    model: cb.CatBoostClassifier,
    X: pd.DataFrame,
    n_samples: int = SHAP_MAX_SAMPLES,
) -> list[list[dict[str, float | int | str]]]:
    """
    Tính SHAP TreeExplainer, trả về top 3 features có |SHAP| lớn nhất mỗi row.

    Args:
        model: CatBoost model đã load
        X: DataFrame features (cần có student_code, subject_id để trace)
        n_samples: Subsample nếu batch quá lớn (SHAP O(n²))

    Returns:
        list[list[dict]]: Mỗi phần tử là list top 3 drivers:
            [{"rank": 1, "feature": "...", "shap_value": ...}, ...]
    """
    # Subsample nếu batch quá lớn (SHAP O(n²) — chỉ tính trên mẫu con).
    # Giữ sample_idx để sau đó trải driver về đúng độ dài của X, tránh lỗi
    # "Length of values (100) does not match length of index (7151)" khi
    # run_inference gán result["shap_drivers"].
    sample_idx = None
    if len(X) > n_samples:
        rng = np.random.default_rng(42)
        sample_idx = rng.choice(len(X), n_samples, replace=False)
        X_shap = X.iloc[sample_idx].reset_index(drop=True)
        logger.info("SHAP subsample: %d → %d rows", len(X), n_samples)
    else:
        X_shap = X.copy()

    # Giữ lại metadata columns để trace
    # (subject_id giờ là FEATURE → KHÔNG loại khỏi X_features; semester_index/join_date là metadata → phải loại)
    meta_cols = ["student_code", "evaluated_at_week", "semester_index", "join_date"]
    meta_df = X_shap[meta_cols].copy()

    # Bỏ metadata columns trước khi tính SHAP
    feature_cols = [c for c in X_shap.columns if c not in meta_cols]
    X_features = X_shap[feature_cols]

    explainer = shap.TreeExplainer(model)
    shap_values = explainer.shap_values(X_features)

    # Xử lý SHAP output format
    n_classes = len(RISK_LEVELS)

    if isinstance(shap_values, list):
        shap_by_class = shap_values
    elif shap_values.ndim == 3 and shap_values.shape[2] == n_classes:
        shap_by_class = [shap_values[:, :, i] for i in range(n_classes)]
    else:
        shap_by_class = [shap_values]

    # Mean |SHAP| across classes
    mean_shap = np.mean([np.abs(sv) for sv in shap_by_class], axis=0)  # (N, F)

    # Top 3 features per row
    top3_idx = np.argsort(-mean_shap, axis=1)[:, :3]  # (N, 3)

    drivers: list[list[dict[str, float | int | str]]] = []
    for i in range(len(X_shap)):
        row_drivers: list[dict[str, float | int | str]] = []
        for rank, fidx in enumerate(top3_idx[i]):
            row_drivers.append({
                "rank": rank + 1,
                "feature": feature_cols[fidx],
                "shap_value": float(mean_shap[i, fidx]),
            })
        drivers.append(row_drivers)

    # Khôi phục đúng độ dài của X: dòng ngoài subsample → driver rỗng [].
    # Đảm bảo list trả về luôn có len == len(X) để gán được vào DataFrame kết quả.
    if sample_idx is not None:
        full_drivers: list[list[dict[str, float | int | str]]] = [[] for _ in range(len(X))]
        for pos, orig_idx in enumerate(sample_idx):
            full_drivers[int(orig_idx)] = drivers[pos]
        drivers = full_drivers

    logger.info("SHAP drivers computed: %d rows (subsample %d)", len(drivers), n_samples if sample_idx is not None else len(X))
    return drivers


def run_inference(
    model: cb.CatBoostClassifier,
    X: pd.DataFrame,
    return_shap: bool = True,
) -> pd.DataFrame:
    """
    Inference pipeline hoàn chỉnh.

    Input:
        model: CatBoost model đã load
        X: DataFrame 24 features (có student_code, evaluated_at_week, semester_index)
        return_shap: Nếu True, tính SHAP drivers

    Output:
        DataFrame với các cột:
        - student_code, evaluated_at_week, semester_index (metadata; pipeline thêm school_year_id)
        - 24 feature columns (subject_id, subject_category, grade_level + 21 numeric) — để persist đầy đủ
        - risk_score, risk_level, risk_probability
        - shap_drivers (JSON string, optional)
    """
    # Xác định feature columns — CHỈ loại metadata; KHÔNG loại subject_id (nó là feature của model)
    # join_date là metadata (chỉ để persist/hiển thị, KHÔNG đưa vào model)
    meta_cols = ["student_code", "evaluated_at_week", "semester_index", "join_date"]
    feature_cols = [c for c in X.columns if c not in meta_cols]

    # Step 1: Predict probabilities
    logger.info("Running predict_proba on %d rows...", len(X))
    y_proba = model.predict_proba(X[feature_cols])  # (N, 4)

    # Step 2: Tính risk_score
    risk_scores = compute_risk_score(y_proba)

    # Step 3: Gán risk_level
    risk_levels = assign_risk_level(y_proba)

    # Step 4: Lấy probability của predicted class
    max_probs = y_proba.max(axis=1)

    # Step 5: SHAP (optional, chậm)
    shap_drivers = None
    if return_shap:
        shap_drivers = compute_shap_drivers(model, X)

    # Gộp kết quả: metadata + toàn bộ feature cols (đủ bind params cho UPSERT) + risk outputs
    result_cols = ["student_code", "evaluated_at_week"] + (
        ["join_date"] if "join_date" in X.columns else []
    ) + feature_cols
    result = X[result_cols].copy()
    result["risk_score"] = risk_scores
    result["risk_level"] = risk_levels
    result["risk_probability"] = max_probs.round(4)
    if shap_drivers is not None:
        result["shap_drivers"] = [json.dumps(d, ensure_ascii=False) for d in shap_drivers]

    logger.info(
        "Inference complete: %d predictions, risk_score range [%.2f, %.2f]",
        len(result),
        result["risk_score"].min(),
        result["risk_score"].max(),
    )
    return result
