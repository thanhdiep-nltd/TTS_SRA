#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
train_catboost_ews.py — Huấn luyện & Triển khai mô hình CatBoost EWS Risk Prediction

Mô tả:
    Pipeline đầy đủ: Load data → Preprocess → Optuna Tuning → CatBoost Training
    → Evaluation (F1, Precision/Recall, Confusion Matrix) → SHAP Explanation → Export.

Plan: plans/gbdt/plan_catboost_ews_model.md (v2.0 Revised)
Data: data_mock/mock_train_data/train_risk_dataset.csv

Output:
    - src/models/gbdt/saved/catboost_ews_model.cbm
    - src/models/gbdt/saved/catboost_evaluation_report.json
    - src/models/gbdt/saved/shap_feature_importance.json
"""

import json
import warnings
import logging
from pathlib import Path
from typing import Tuple, Dict, Optional

import numpy as np
import pandas as pd

from sklearn.model_selection import GroupShuffleSplit
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    precision_recall_fscore_support,
    confusion_matrix,
)

import catboost as cb
import optuna
import shap

warnings.filterwarnings("ignore", category=FutureWarning)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# =============================================================================
# CẤU HÌNH
# =============================================================================

DATA_PATH = Path("data_mock/mock_train_data/train_risk_dataset.csv")
SAVED_DIR = Path("src/models/gbdt/saved")
MODEL_PATH = SAVED_DIR / "catboost_ews_model.cbm"
METRICS_PATH = SAVED_DIR / "catboost_evaluation_report.json"
SHAP_PATH = SAVED_DIR / "shap_feature_importance.json"

RANDOM_SEED = 42
N_TRIALS = 10
EARLY_STOPPING_ROUNDS = 50

# --- Danh sách 24 Feature Columns (bỏ lms_bucket — PIVOT M2) ---
FEATURE_COLS = [
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

CAT_FEATURES = ["subject_id", "subject_category", "grade_level"]
TARGET_COL = "actual_risk_level"
GROUP_COL = "student_code"

RISK_LEVEL_MAP: Dict[str, int] = {
    "LOW": 0,
    "MODERATE": 1,
    "HIGH": 2,
    "CRITICAL": 3,
}
RISK_LEVEL_NAMES = ["LOW", "MODERATE", "HIGH", "CRITICAL"]

# Trọng số risk_score: P(LOW)=0.00 → risk=0, P(CRITICAL)=1.00 → risk=100
RISK_SCORE_WEIGHTS = np.array([0.00, 0.35, 0.70, 1.00], dtype=np.float64)

# Optuna search space
DEPTH_CHOICES = [4, 5, 6, 7, 8]


# =============================================================================
# HÀM TIỆN ÍCH
# =============================================================================

def ensure_saved_dir():
    """Tạo thư mục saved nếu chưa tồn tại."""
    SAVED_DIR.mkdir(parents=True, exist_ok=True)


def load_data(path: Path = DATA_PATH) -> pd.DataFrame:
    """Đọc CSV và validation cơ bản."""
    logger.info(f"Loading data from {path}...")
    df = pd.read_csv(path)

    # Kiểm tra các cột bắt buộc
    required = FEATURE_COLS + [TARGET_COL, GROUP_COL]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    logger.info(f"Loaded {len(df):,} rows, {len(df.columns)} columns")
    logger.info(f"Target distribution:\n{df[TARGET_COL].value_counts(normalize=True).to_string()}")
    return df


def preprocess_data(df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Series, pd.Series]:
    """
    Tách X (features), y (target), groups (student_code).
    Mã hóa target thành ordinal 0/1/2/3.
    """
    X = df[FEATURE_COLS].copy()
    y = df[TARGET_COL].map(RISK_LEVEL_MAP)
    groups = df[GROUP_COL]

    # Kiểm tra mapping
    if y.isna().any():
        unknown = df.loc[y.isna(), TARGET_COL].unique()
        raise ValueError(f"Unknown risk levels in target: {unknown}")

    # Ép kiểu string cho categorical features
    for col in CAT_FEATURES:
        if col in X.columns:
            X[col] = X[col].astype(str)

    logger.info(f"X shape: {X.shape}, y classes: {np.bincount(y)}")
    return X, y, groups


def group_train_val_test_split(
    X: pd.DataFrame, y: pd.Series, groups: pd.Series,
    train_size: float = 0.7, val_size: float = 0.15,
    random_state: int = RANDOM_SEED,
) -> Tuple:
    """
    GroupShuffleSplit 2 lần:
      Lần 1: Train 70% vs Temp 30%
      Lần 2: Temp → Val 50% vs Test 50%  (= 15% val + 15% test)
    """
    # Lần 1: train vs temp
    gss1 = GroupShuffleSplit(n_splits=1, train_size=train_size, random_state=random_state)
    train_idx, temp_idx = next(gss1.split(X, y, groups))

    X_train = X.iloc[train_idx]
    y_train = y.iloc[train_idx]

    X_temp = X.iloc[temp_idx]
    y_temp = y.iloc[temp_idx]
    groups_temp = groups.iloc[temp_idx]

    # Lần 2: val vs test (50/50 của temp → 15% val + 15% test)
    val_ratio = val_size / (1.0 - train_size)  # 0.15 / 0.30 = 0.5
    gss2 = GroupShuffleSplit(n_splits=1, train_size=val_ratio, random_state=random_state)
    val_idx_rel, test_idx_rel = next(gss2.split(X_temp, y_temp, groups_temp))

    X_val = X_temp.iloc[val_idx_rel]
    y_val = y_temp.iloc[val_idx_rel]
    X_test = X_temp.iloc[test_idx_rel]
    y_test = y_temp.iloc[test_idx_rel]

    logger.info(f"Split: Train {len(X_train):,} | Val {len(X_val):,} | Test {len(X_test):,}")
    logger.info(f"Train classes: {dict(zip(*np.unique(y_train, return_counts=True)))}")
    logger.info(f"Val classes:   {dict(zip(*np.unique(y_val, return_counts=True)))}")
    logger.info(f"Test classes:  {dict(zip(*np.unique(y_test, return_counts=True)))}")

    return X_train, X_val, X_test, y_train, y_val, y_test


def compute_risk_score(probs: np.ndarray) -> np.ndarray:
    """
    Tính risk_score [0, 100] từ probability matrix (N, 4).

    Công thức:
        risk_score = (0.00*P(LOW) + 0.35*P(MOD) + 0.70*P(HIGH) + 1.00*P(CRIT)) * 100
    """
    raw = probs @ RISK_SCORE_WEIGHTS  # (N,)
    return np.round(raw * 100.0, 2)


# =============================================================================
# OPTUNA HYPERPARAMETER TUNING
# =============================================================================

def objective(trial: optuna.Trial, X_train, y_train, X_val, y_val) -> float:
    """Objective function cho Optuna — maximize F1-Macro trên validation set."""
    params = {
        "loss_function": "MultiClass",
        "eval_metric": "MultiClass",
        "iterations": 1000,
        "depth": trial.suggest_int("depth", 4, 8),
        "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.1, log=True),
        "l2_leaf_reg": trial.suggest_float("l2_leaf_reg", 1.0, 10.0),
        "subsample": trial.suggest_float("subsample", 0.6, 1.0),
        "bootstrap_type": "Bernoulli",
        "random_seed": RANDOM_SEED,
        "auto_class_weights": "Balanced",
        "verbose": False,
        "od_type": "Iter",
        "od_wait": EARLY_STOPPING_ROUNDS,
    }

    model = cb.CatBoostClassifier(**params)
    model.fit(
        X_train, y_train,
        eval_set=(X_val, y_val),
        cat_features=CAT_FEATURES,
        early_stopping_rounds=EARLY_STOPPING_ROUNDS,
        verbose=False,
    )

    y_pred = model.predict(X_val)
    f1 = f1_score(y_val, y_pred, average="macro")
    return f1


def run_optuna_tuning(
    X_train, y_train, X_val, y_val,
    n_trials: int = N_TRIALS,
) -> Dict:
    """Chạy Optuna tìm params tối ưu."""
    logger.info(f"Starting Optuna tuning with {n_trials} trials...")
    study = optuna.create_study(
        direction="maximize",
        sampler=optuna.samplers.TPESampler(seed=RANDOM_SEED),
    )
    study.optimize(
        lambda trial: objective(trial, X_train, y_train, X_val, y_val),
        n_trials=n_trials,
        show_progress_bar=True,
    )

    logger.info(f"Best trial: #{study.best_trial.number}")
    logger.info(f"Best F1-Macro (val): {study.best_trial.value:.4f}")
    logger.info(f"Best params: {study.best_trial.params}")

    return study.best_trial.params


# =============================================================================
# TRAINING
# =============================================================================

def train_final_model(
    X_train, y_train, X_val, y_val,
    best_params: Dict,
) -> cb.CatBoostClassifier:
    """Train mô hình cuối cùng với best params từ Optuna."""
    logger.info("Training final model with best params...")

    final_params = {
        "loss_function": "MultiClass",
        "eval_metric": "MultiClass",
        "iterations": 1000,
        "random_seed": RANDOM_SEED,
        "auto_class_weights": "Balanced",
        "verbose": 100,
        "od_type": "Iter",
        "od_wait": EARLY_STOPPING_ROUNDS,
        "bootstrap_type": "Bernoulli",
        **best_params,
    }

    model = cb.CatBoostClassifier(**final_params)
    model.fit(
        X_train, y_train,
        eval_set=(X_val, y_val),
        cat_features=CAT_FEATURES,
        early_stopping_rounds=EARLY_STOPPING_ROUNDS,
        verbose=100,
    )

    best_iter = model.get_best_iteration()
    logger.info(f"Best iteration: {best_iter}")

    return model


# =============================================================================
# EVALUATION
# =============================================================================

def evaluate_model(
    model: cb.CatBoostClassifier,
    X_test: pd.DataFrame,
    y_test: pd.Series,
) -> Dict:
    """Đánh giá mô hình trên test set."""
    logger.info("Evaluating model on test set...")

    y_pred = model.predict(X_test)
    y_proba = model.predict_proba(X_test)  # (N, 4)

    # Metrics
    acc = accuracy_score(y_test, y_pred)
    f1_macro = f1_score(y_test, y_pred, average="macro")
    f1_weighted = f1_score(y_test, y_pred, average="weighted")

    # Per-class metrics
    precision, recall, f1_per, support = precision_recall_fscore_support(
        y_test, y_pred, labels=[0, 1, 2, 3]
    )

    # Confusion matrix
    cm = confusion_matrix(y_test, y_pred, labels=[0, 1, 2, 3])

    # Risk score
    risk_scores = compute_risk_score(y_proba)

    report = {
        "accuracy": round(float(acc), 4),
        "f1_macro": round(float(f1_macro), 4),
        "f1_weighted": round(float(f1_weighted), 4),
        "per_class": {},
        "confusion_matrix": cm.tolist(),
        "risk_score_stats": {
            "min": float(risk_scores.min()),
            "max": float(risk_scores.max()),
            "mean": float(risk_scores.mean()),
            "median": float(np.median(risk_scores)),
            "std": float(risk_scores.std()),
        },
    }

    for i, cls_name in enumerate(RISK_LEVEL_NAMES):
        report["per_class"][cls_name] = {
            "precision": round(float(precision[i]), 4),
            "recall": round(float(recall[i]), 4),
            "f1_score": round(float(f1_per[i]), 4),
            "support": int(support[i]),
        }

    logger.info(f"Accuracy: {acc:.4f}")
    logger.info(f"F1-Macro: {f1_macro:.4f} | F1-Weighted: {f1_weighted:.4f}")
    logger.info(f"Risk score range: [{risk_scores.min():.1f}, {risk_scores.max():.1f}]")
    logger.info(f"Confusion Matrix:\n{cm}")

    return report


# =============================================================================
# SHAP EXPLANATION
# =============================================================================

def compute_shap_explanations(
    model: cb.CatBoostClassifier,
    X_test: pd.DataFrame,
    y_test: pd.Series,
    n_samples: int = 500,
) -> Dict:
    """
    Tính SHAP values trên test set (subset n_samples).
    Export: feature importance tổng thể + top 3 features per class.
    """
    logger.info(f"Computing SHAP explanations on {n_samples} samples...")

    # Lấy subset nếu test set quá lớn
    if len(X_test) > n_samples:
        rng = np.random.default_rng(RANDOM_SEED)
        idx = rng.choice(len(X_test), n_samples, replace=False)
        X_subset = X_test.iloc[idx]
        y_subset = y_test.iloc[idx]
    else:
        X_subset = X_test
        y_subset = y_test

    explainer = shap.TreeExplainer(model)
    raw_shap = explainer.shap_values(X_subset)

    # ------------------------------------------------------------------
    # Xử lý các định dạng output khác nhau của SHAP theo version
    # ------------------------------------------------------------------
    n_classes = len(RISK_LEVEL_NAMES)
    feature_names = X_subset.columns.tolist()

    if isinstance(raw_shap, list):
        # SHAP < 0.45: list of (N, F) arrays, one per class
        shap_by_class = raw_shap
        # mean |SHAP| tổng thể: average across classes
        mean_abs_shap = np.mean(
            [np.abs(sv).mean(axis=0) for sv in shap_by_class], axis=0
        )
    elif raw_shap.ndim == 3 and raw_shap.shape[2] == n_classes:
        # SHAP >= 0.45: 3D array (N, F, C) — chuyển về list (C, N, F)
        shap_by_class = [raw_shap[:, :, i] for i in range(n_classes)]
        mean_abs_shap = np.abs(raw_shap).mean(axis=(0, 2))  # (F,)
    elif raw_shap.ndim == 3 and raw_shap.shape[1] == n_classes:
        # Alternate 3D: (N, C, F)
        shap_by_class = [raw_shap[:, i, :] for i in range(n_classes)]
        mean_abs_shap = np.abs(raw_shap).mean(axis=(0, 1))  # (F,)
    else:
        # Binary case — should not happen for 4-class
        shap_by_class = [raw_shap]
        mean_abs_shap = np.abs(raw_shap).mean(axis=0)

    # DataFrame feature importance tổng thể
    importance_df = pd.DataFrame({
        "feature": feature_names,
        "mean_abs_shap": mean_abs_shap,
    }).sort_values("mean_abs_shap", ascending=False)

    top3_overall = importance_df.head(3).to_dict("records")

    # Top 3 features per risk class
    top3_per_class = {}
    for cls_idx, cls_name in enumerate(RISK_LEVEL_NAMES):
        if cls_idx < len(shap_by_class):
            cls_shap = np.abs(shap_by_class[cls_idx]).mean(axis=0)
            cls_df = pd.DataFrame({"feature": feature_names, "mean_abs_shap": cls_shap})
            cls_df = cls_df.sort_values("mean_abs_shap", ascending=False)
            top3_per_class[cls_name] = cls_df.head(3).to_dict("records")

    result = {
        "method": "shap.TreeExplainer",
        "n_samples_used": len(X_subset),
        "top3_overall": top3_overall,
        "top3_per_class": top3_per_class,
        "feature_importance": importance_df.to_dict("records"),
    }

    logger.info(f"SHAP Top 3 features overall: {[t['feature'] for t in top3_overall]}")
    return result


# =============================================================================
# EXPORT
# =============================================================================

def export_results(
    model: cb.CatBoostClassifier,
    metrics: Dict,
    shap_result: Dict,
):
    """Export model + metrics + SHAP ra thư mục saved."""
    ensure_saved_dir()

    # Model
    logger.info(f"Saving model to {MODEL_PATH}...")
    model.save_model(str(MODEL_PATH))

    # Metrics
    logger.info(f"Saving metrics to {METRICS_PATH}...")
    with open(METRICS_PATH, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2, ensure_ascii=False)

    # SHAP
    logger.info(f"Saving SHAP to {SHAP_PATH}...")
    with open(SHAP_PATH, "w", encoding="utf-8") as f:
        json.dump(shap_result, f, indent=2, ensure_ascii=False)

    logger.info("All artifacts exported successfully!")


# =============================================================================
# MAIN PIPELINE
# =============================================================================

def run_pipeline(
    data_path: Path = DATA_PATH,
    n_trials: int = N_TRIALS,
    skip_tuning: bool = False,
    default_params: Optional[Dict] = None,
) -> Dict:
    """
    Pipeline chính:
    1. Load & Preprocess
    2. GroupShuffleSplit
    3. Optuna Tuning (optional)
    4. Train final model
    5. Evaluate
    6. SHAP Explanation
    7. Export
    """
    logger.info("=" * 60)
    logger.info("CatBoost EWS Training Pipeline — v2.0 Revised")
    logger.info("=" * 60)

    # Step 1-2: Load, preprocess, split
    df = load_data(data_path)
    X, y, groups = preprocess_data(df)
    X_train, X_val, X_test, y_train, y_val, y_test = group_train_val_test_split(X, y, groups)

    # Step 3: Hyperparameter tuning (Optuna)
    if skip_tuning and default_params is not None:
        logger.info("Skipping Optuna tuning, using default params...")
        best_params = default_params
    else:
        best_params = run_optuna_tuning(X_train, y_train, X_val, y_val, n_trials=n_trials)

    # Step 4: Train final model
    model = train_final_model(X_train, y_train, X_val, y_val, best_params)

    # Step 5: Evaluate
    metrics = evaluate_model(model, X_test, y_test)

    # Step 6: SHAP
    shap_result = compute_shap_explanations(model, X_test, y_test)

    # Step 7: Export
    export_results(model, metrics, shap_result)

    summary = {
        "status": "success",
        "model_path": str(MODEL_PATH),
        "metrics": metrics,
        "best_params": best_params,
        "shap_top_features": shap_result.get("top3_overall", []),
    }

    logger.info("=" * 60)
    logger.info("Pipeline completed successfully!")
    logger.info("=" * 60)

    return summary


# =============================================================================
# CLI
# =============================================================================

def main():
    import argparse

    global RANDOM_SEED

    parser = argparse.ArgumentParser(description="CatBoost EWS Training Pipeline v2.0")
    parser.add_argument("--data", type=str, default=str(DATA_PATH),
                        help=f"Path to training CSV (default: {DATA_PATH})")
    parser.add_argument("--trials", type=int, default=N_TRIALS,
                        help=f"Number of Optuna trials (default: {N_TRIALS})")
    parser.add_argument("--skip-tuning", action="store_true",
                        help="Skip Optuna tuning, use default params")
    parser.add_argument("--seed", type=int, default=RANDOM_SEED,
                        help=f"Random seed (default: {RANDOM_SEED})")
    args = parser.parse_args()

    RANDOM_SEED = args.seed

    default_params = {
        "depth": 6,
        "learning_rate": 0.05,
        "l2_leaf_reg": 3.0,
        "subsample": 0.8,
        "bootstrap_type": "Bernoulli",
    } if args.skip_tuning else None

    result = run_pipeline(
        data_path=Path(args.data),
        n_trials=args.trials,
        skip_tuning=args.skip_tuning,
        default_params=default_params,
    )

    print(f"\n[DONE] Pipeline complete! Model: {result['model_path']}")
    print(f"       F1-Macro: {result['metrics']['f1_macro']:.4f}")
    print(f"       F1-Weighted: {result['metrics']['f1_weighted']:.4f}")


if __name__ == "__main__":
    main()
