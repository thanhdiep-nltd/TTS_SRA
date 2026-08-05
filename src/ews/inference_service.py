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

from src.ews.risk_config import RiskConfig

logger = logging.getLogger(__name__)

# ============================================================================
# CONSTANTS
# ============================================================================

# Đường dẫn TUYỆT ĐỐI dựa trên vị trí file này (không phụ thuộc CWD của process).
# Trước đây dùng đường dẫn tương đối "src/models/gbdt/saved/..." — nếu server chạy
# với working directory khác project root (vd. uvicorn --reload từ nơi khác) thì
# load_ensemble() sẽ FileNotFoundError -> API /ews/golden-set trả 500.
_SRC_DIR = Path(__file__).resolve().parent.parent  # .../src
_SAVED_DIR = _SRC_DIR / "models" / "gbdt" / "saved"

MODEL_PATH = _SAVED_DIR / "catboost_ews_model.cbm"
SHAP_PATH = _SAVED_DIR / "shap_feature_importance.json"
CAT_FEATURES = ["subject_id", "subject_category", "grade_level"]  # same as training

# Nhóm feature theo 4 yếu tố quyết định (khớp FEATURE_COLS trong training).
# Dùng để tính mức đóng góp (%) của từng nhóm vào quyết định của model v1_single
# từ SHAP feature importance (mean |SHAP|) — giá trị học được sau khi train.
FACTOR_GROUP_FEATURES: dict[str, list[str]] = {
    "score": [
        "weighted_early_avg", "weighted_late_avg", "score_slope",
        "score_volatility", "max_drop", "last_score",
        "max_coefficient_so_far", "high_weight_score_count", "last_high_weight_score",
    ],
    "lms": [
        "lms_avg_score", "lms_recent_drop", "lms_submission_rate",
        "lms_recent_submission_rate", "lms_gradebook_gap",
    ],
    "attendance": [
        "daily_absence_rate", "unexcused_absent_rate",
        "excused_absent_days", "total_late_count",
    ],
    "behavior": [
        "total_demerit_points", "repeat_offense_count", "severe_sanction_count",
    ],
}

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


def compute_v1_group_contributions(
    shap_path: Path = SHAP_PATH,
) -> dict[str, float]:
    """
    Tính mức đóng góp (%) của từng nhóm yếu tố vào quyết định của model v1_single.

    Đọc SHAP feature importance (mean |SHAP|) đã lưu sau khi train, cộng dồn theo
    nhóm (score/lms/attendance/behavior) rồi chuẩn hoá về tổng = 1.0.

    Đây là giá trị HỌC ĐƯỢC từ model (không phải trọng số cấu hình) — chung cho
    mọi học sinh vì v1 là model đơn.

    Returns:
        {"score": 0.746, "lms": 0.112, "attendance": 0.075, "behavior": 0.066}
    """
    if not shap_path.exists():
        logger.warning("SHAP file not found (%s) — fallback to default weights", shap_path)
        return {"score": 0.65, "lms": 0.15, "attendance": 0.10, "behavior": 0.10}

    with open(shap_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # feature -> mean_abs_shap
    imp = {row["feature"]: row["mean_abs_shap"] for row in data.get("feature_importance", [])}

    group_sum: dict[str, float] = {}
    for group, feats in FACTOR_GROUP_FEATURES.items():
        group_sum[group] = sum(imp.get(f, 0.0) for f in feats)

    total = sum(group_sum.values())
    if total <= 0:
        logger.warning("SHAP group total <= 0 — fallback to default weights")
        return {"score": 0.65, "lms": 0.15, "attendance": 0.10, "behavior": 0.10}

    contrib = {g: s / total for g, s in group_sum.items()}
    logger.info("v1 group contributions (learned from SHAP): %s",
                {g: round(v, 4) for g, v in contrib.items()})
    return contrib


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
    # join_date & so_school_id là metadata (chỉ để persist/hiển thị/tenant isolation, KHÔNG đưa vào model)
    meta_cols = ["student_code", "evaluated_at_week", "semester_index", "join_date", "so_school_id"]
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
    ) + (["so_school_id"] if "so_school_id" in X.columns else []) + feature_cols
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


# ============================================================================
# FACTOR-ENSEMBLE (v2) — 4 sub-model + dynamic weighting
# ============================================================================

# Nhóm feature cho từng sub-model (khớp train_catboost_ews_ensemble.py)
ENSEMBLE_FACTOR_GROUPS = {
    "score": [
        "weighted_early_avg", "weighted_late_avg", "score_slope", "score_volatility",
        "max_drop", "last_score", "max_coefficient_so_far",
        "high_weight_score_count", "last_high_weight_score",
    ],
    "lms": [
        "lms_avg_score", "lms_recent_drop", "lms_submission_rate",
        "lms_recent_submission_rate", "lms_gradebook_gap",
    ],
    "attendance": [
        "daily_absence_rate", "unexcused_absent_rate", "excused_absent_days", "total_late_count",
    ],
    "behavior": [
        "total_demerit_points", "repeat_offense_count", "severe_sanction_count",
    ],
}

ENSEMBLE_MODEL_PATHS = {
    "score": _SAVED_DIR / "catboost_ews_score.cbm",
    "lms": _SAVED_DIR / "catboost_ews_lms.cbm",
    "attendance": _SAVED_DIR / "catboost_ews_attendance.cbm",
    "behavior": _SAVED_DIR / "catboost_ews_behavior.cbm",
}


def load_ensemble(paths: dict | None = None) -> dict:
    """Load 4 sub-model CatBoost (factor-ensemble)."""
    paths = paths or ENSEMBLE_MODEL_PATHS
    models = {}
    for factor, p in paths.items():
        if not p.exists():
            raise FileNotFoundError(f"Ensemble model not found: {p}")
        m = cb.CatBoostClassifier()
        m.load_model(str(p))
        models[factor] = m
        logger.info("Loaded ensemble model [%s]: iterations=%d", factor, m.tree_count_)
    return models


def run_ensemble_inference(
    models: dict,
    X: pd.DataFrame,
    return_shap: bool = False,
    cfg: RiskConfig | None = None,
) -> pd.DataFrame:
    """
    Inference factor-ensemble: mỗi sub-model xuất risk_score riêng, rồi kết hợp
    bằng trọng số động (risk_config.combine_risk_scores).

    Args:
        models: dict {factor: CatBoostClassifier}
        X: DataFrame features
        return_shap: giữ API cũ (ensemble không dùng SHAP)
        cfg: RiskConfig hiệu lực (mặc định load_risk_config()). Cho phép truyền
            config đã merge theo trường (BGH override) mà không đụng cache toàn cục.

    Output DataFrame gồm:
      - metadata + toàn bộ feature cols (đủ bind UPSERT)
      - score_risk, lms_risk, attendance_risk, behavior_risk (sub-score 0-100)
      - weight_score, weight_lms, weight_attendance, weight_behavior (trọng số động đã dùng)
      - risk_score (final), risk_level (final), risk_probability
    """
    from src.ews.risk_config import FACTOR_KEYS, combine_risk_scores, load_risk_config
    cfg = cfg or load_risk_config()

    meta_cols = ["student_code", "evaluated_at_week", "semester_index", "join_date"]
    feature_cols = [c for c in X.columns if c not in meta_cols]

    result = X[["student_code", "evaluated_at_week"] + (
        ["join_date"] if "join_date" in X.columns else []
    ) + feature_cols].copy()

    # Feature cols thực của từng nhóm (bỏ context) để xác định yếu tố "có dữ liệu"
    factor_feat_cols = {
        f: [c for c in ENSEMBLE_FACTOR_GROUPS[f] if c in X.columns]
        for f in FACTOR_KEYS
    }

    sub_scores = {}
    for factor in FACTOR_KEYS:
        cols = [c for c in CAT_FEATURES + factor_feat_cols[factor] if c in X.columns]
        y_proba = models[factor].predict_proba(X[cols])
        sub_scores[factor] = compute_risk_score(y_proba)  # (N,) 0-100

    # Kết hợp từng dòng; yếu tố toàn NaN (không có dữ liệu) bị LOẠI khỏi ensemble
    # (không coi "không có dữ liệu" như "không nộp bài / rủi ro cao").
    final_scores = []
    final_levels = []
    weight_cols = {f: [] for f in FACTOR_KEYS}
    risk_cols = {f: [] for f in FACTOR_KEYS}
    for i in range(len(X)):
        available = [
            f for f in FACTOR_KEYS
            if factor_feat_cols[f]
            and not X.iloc[i][factor_feat_cols[f]].isna().all()
        ]
        row = {f: float(sub_scores[f][i]) for f in FACTOR_KEYS}
        comb = combine_risk_scores(row, available=available, cfg=cfg)
        final_scores.append(comb["final_risk_score"])
        final_levels.append(comb["final_risk_level"])
        for f in FACTOR_KEYS:
            weight_cols[f].append(comb["weights"][f])
            # Lưu sub-score ĐÃ HIỆU CHỈNH baseline (khớp với final risk) để UI nhất quán
            calib = cfg.calibration.get(f, 0.0) * 100.0
            calibrated = max(0.0, float(sub_scores[f][i]) - calib)
            risk_cols[f].append(calibrated if f in available else None)

    result["risk_score"] = np.array(final_scores)
    result["risk_level"] = np.array(final_levels)
    for f in FACTOR_KEYS:
        result[f"weight_{f}"] = np.array(weight_cols[f])
        result[f"{f}_risk"] = np.array(risk_cols[f], dtype=object)

    # risk_probability: dùng max prob của sub-model score (xấp xỉ độ tin cậy)
    result["risk_probability"] = models["score"].predict_proba(
        X[[c for c in CAT_FEATURES + ENSEMBLE_FACTOR_GROUPS["score"] if c in X.columns]]
    ).max(axis=1).round(4)

    logger.info(
        "Ensemble inference complete: %d rows, final risk_score range [%.2f, %.2f]",
        len(result), result["risk_score"].min(), result["risk_score"].max(),
    )
    return result
