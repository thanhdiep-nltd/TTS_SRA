#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
train_catboost_ews_ensemble.py — Huấn luyện 4 sub-model EWS (factor-ensemble).

Mỗi sub-model học trên context chung (subject_id, subject_category, grade_level)
+ feature của riêng nhóm yếu tố đó, cùng target RIÊNG của yếu tố đó (từ component
0-10 trong CSV: score_component / lms_component / attendance_component / behavior_component),
map sang risk level bằng ngưỡng 6.5/5.0/3.5. KHÔNG dùng chung actual_risk_level (rủi ro
TỔNG) nữa — tránh baseline cao khiến học sinh sạch bị gắn cờ oan.

Nhóm yếu tố:
  - score      : 9 Temporal features
  - lms        : 5 LMS features
  - attendance : 4 Attendance features
  - behavior   : 3 Behavior features

Output (4 file .cbm, không đè model v1):
  - src/models/gbdt/saved/catboost_ews_score.cbm
  - src/models/gbdt/saved/catboost_ews_lms.cbm
  - src/models/gbdt/saved/catboost_ews_attendance.cbm
  - src/models/gbdt/saved/catboost_ews_behavior.cbm

Tham khảo: plans/ews/plan_factor_ensemble_ews.md
"""

import json
import logging
import warnings
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
import catboost as cb
from sklearn.model_selection import GroupShuffleSplit
from sklearn.metrics import accuracy_score, f1_score, precision_recall_fscore_support

warnings.filterwarnings("ignore", category=FutureWarning)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

DATA_PATH = Path("data_mock/mock_train_data/train_risk_dataset.csv")
SAVED_DIR = Path("src/models/gbdt/saved")

RANDOM_SEED = 42
EARLY_STOPPING_ROUNDS = 50

RISK_LEVEL_MAP: Dict[str, int] = {"LOW": 0, "MODERATE": 1, "HIGH": 2, "CRITICAL": 3}
RISK_SCORE_WEIGHTS = np.array([0.00, 0.35, 0.70, 1.00], dtype=np.float64)

CAT_FEATURES = ["subject_id", "subject_category", "grade_level"]

# Nhóm feature cho từng sub-model (ngoài context chung)
FACTOR_GROUPS: Dict[str, List[str]] = {
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

# Cột component (0-10) riêng từng yếu tố — dùng làm target RIÊNG cho từng sub-model.
# Trước đây cả 4 sub-model cùng dự đoán actual_risk_level (rủi ro TỔNG) nên bị baseline
# cao (học sinh sạch vẫn ra ~28-44). Dùng component riêng → học sinh sạch (component=10)
# tự nhiên ra LOW, không cần calibration hardcode.
FACTOR_COMPONENT_COL: Dict[str, str] = {
    "score": "score_component",
    "lms": "lms_component",
    "attendance": "attendance_component",
    "behavior": "behavior_component",
}

TARGET_COL = "actual_risk_level"
GROUP_COL = "student_code"


def component_to_risk_level(component: float) -> str:
    """Map component (0-10, cao = khỏe) sang risk level bằng cùng ngưỡng RISK_THRESHOLDS."""
    if component >= 6.5:
        return "LOW"
    if component >= 5.0:
        return "MODERATE"
    if component >= 3.5:
        return "HIGH"
    return "CRITICAL"


def ensure_saved_dir():
    SAVED_DIR.mkdir(parents=True, exist_ok=True)


def load_data(path: Path = DATA_PATH) -> pd.DataFrame:
    logger.info(f"Loading data from {path}...")
    df = pd.read_csv(path)
    all_feats = CAT_FEATURES + [c for grp in FACTOR_GROUPS.values() for c in grp]
    required = all_feats + [TARGET_COL, GROUP_COL]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")
    logger.info(f"Loaded {len(df):,} rows, {len(df.columns)} columns")
    return df


def preprocess(df: pd.DataFrame, factor: str) -> Tuple[pd.DataFrame, pd.Series, pd.Series]:
    feats = CAT_FEATURES + FACTOR_GROUPS[factor]
    X = df[feats].copy()
    # Target RIÊNG theo yếu tố: map component (0-10) của yếu tố đó sang risk level.
    # Không dùng actual_risk_level (rủi ro TỔNG) nữa → bỏ baseline cao.
    comp_col = FACTOR_COMPONENT_COL[factor]
    y = df[comp_col].apply(component_to_risk_level).map(RISK_LEVEL_MAP)
    groups = df[GROUP_COL]
    if y.isna().any():
        raise ValueError(f"Unknown risk levels from {comp_col}: {df.loc[y.isna(), comp_col].unique()}")
    for col in CAT_FEATURES:
        X[col] = X[col].astype(str)
    return X, y, groups


def group_split(X, y, groups, train_size=0.7, val_size=0.15, random_state=RANDOM_SEED):
    gss1 = GroupShuffleSplit(n_splits=1, train_size=train_size, random_state=random_state)
    train_idx, temp_idx = next(gss1.split(X, y, groups))
    X_train, y_train = X.iloc[train_idx], y.iloc[train_idx]
    X_temp, y_temp, groups_temp = X.iloc[temp_idx], y.iloc[temp_idx], groups.iloc[temp_idx]
    val_ratio = val_size / (1.0 - train_size)
    gss2 = GroupShuffleSplit(n_splits=1, train_size=val_ratio, random_state=random_state)
    val_idx, test_idx = next(gss2.split(X_temp, y_temp, groups_temp))
    return (
        X_train, X_temp.iloc[val_idx], X_temp.iloc[test_idx],
        y_train, y_temp.iloc[val_idx], y_temp.iloc[test_idx],
    )


def train_submodel(factor: str, X_train, y_train, X_val, y_val) -> cb.CatBoostClassifier:
    logger.info(f"Training sub-model [{factor}] ({len(FACTOR_GROUPS[factor])} features)...")
    params = {
        "loss_function": "MultiClass",
        "eval_metric": "MultiClass",
        "iterations": 1000,
        "depth": 6,
        "learning_rate": 0.05,
        "l2_leaf_reg": 3.0,
        "subsample": 0.8,
        "bootstrap_type": "Bernoulli",
        "random_seed": RANDOM_SEED,
        "auto_class_weights": "Balanced",
        "verbose": 100,
        "od_type": "Iter",
        "od_wait": EARLY_STOPPING_ROUNDS,
    }
    model = cb.CatBoostClassifier(**params)
    model.fit(
        X_train, y_train,
        eval_set=(X_val, y_val),
        cat_features=CAT_FEATURES,
        early_stopping_rounds=EARLY_STOPPING_ROUNDS,
        verbose=100,
    )
    logger.info(f"[{factor}] best_iter={model.get_best_iteration()}")
    return model


def evaluate_submodel(factor: str, model, X_test, y_test) -> Dict:
    y_pred = model.predict(X_test)
    acc = accuracy_score(y_test, y_pred)
    f1_macro = f1_score(y_test, y_pred, average="macro")
    precision, recall, f1_per, _ = precision_recall_fscore_support(
        y_test, y_pred, labels=[0, 1, 2, 3], zero_division=0
    )
    logger.info(
        f"[{factor}] acc={acc:.4f} f1_macro={f1_macro:.4f} "
        f"f1_per={np.round(f1_per, 3).tolist()}"
    )
    return {"factor": factor, "accuracy": round(acc, 4), "f1_macro": round(f1_macro, 4)}


def main():
    ensure_saved_dir()
    df = load_data()

    # Split chung 1 lần (dùng split của factor đầu tiên để nhất quán)
    factor0 = list(FACTOR_GROUPS.keys())[0]
    X0, y0, g0 = preprocess(df, factor0)
    X_train, X_val, X_test, y_train, y_val, y_test = group_split(X0, y0, g0)

    report = {}
    for factor in FACTOR_GROUPS:
        X, y, _ = preprocess(df, factor)
        # Dùng lại index split từ factor0 (cùng thứ tự dòng)
        model = train_submodel(factor, X.iloc[X_train.index], y.iloc[X_train.index],
                               X.iloc[X_val.index], y.iloc[X_val.index])
        path = SAVED_DIR / f"catboost_ews_{factor}.cbm"
        model.save_model(str(path))
        logger.info(f"Saved {path}")
        report[factor] = evaluate_submodel(factor, model, X.iloc[X_test.index], y.iloc[X_test.index])

    report_path = SAVED_DIR / "catboost_ews_ensemble_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    logger.info(f"Report saved: {report_path}")


if __name__ == "__main__":
    main()
