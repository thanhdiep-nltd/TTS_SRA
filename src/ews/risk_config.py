# -*- coding: utf-8 -*-
"""
src/ews/risk_config.py — Load & validate cấu hình trọng số EWS (v2_ensemble).

Nguồn:
  - File YAML: src/ews/risk_weights.yaml (trọng số gốc + dynamic + ngưỡng risk_level).
  - Env override (đổi không cần retrain):
      EWS_WEIGHT_SCORE, EWS_WEIGHT_LMS, EWS_WEIGHT_ATTENDANCE, EWS_WEIGHT_BEHAVIOR
      EWS_ALPHA, EWS_WEIGHT_FLOOR, EWS_WORST_FACTOR_BETA

Cung cấp:
  - RiskConfig dataclass (weights, dynamic, thresholds).
  - load_risk_config() -> RiskConfig (có cache).
  - combine_risk_scores() -> final risk_score + risk_level từ 4 sub-score
    (Dynamic Softmax Attention + floor + Worst-Factor blend).
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import numpy as np
import yaml

logger = logging.getLogger(__name__)

CONFIG_PATH = Path(__file__).parent / "risk_weights.yaml"

# Thứ tự cố định của 4 yếu tố (khớp với cột lưu trữ & frontend).
FACTOR_KEYS = ["score", "lms", "attendance", "behavior"]

RISK_LEVELS = ["LOW", "MODERATE", "HIGH", "CRITICAL"]


@dataclass
class DynamicConfig:
    enabled: bool = True
    alpha: float = 2.5
    weight_floor: float = 0.05
    worst_factor_beta: float = 0.20


@dataclass
class RiskConfig:
    weights: dict = field(default_factory=dict)          # {factor: float} tổng = 1.0
    dynamic: DynamicConfig = field(default_factory=DynamicConfig)
    thresholds: dict = field(default_factory=dict)       # {level: float} ngưỡng trên [0,100]

    def base_weight_vector(self) -> np.ndarray:
        """Trọng số gốc theo FACTOR_KEYS."""
        return np.array([self.weights[k] for k in FACTOR_KEYS], dtype=np.float64)

    def threshold_vector(self) -> np.ndarray:
        """Ngưỡng theo RISK_LEVELS (tăng dần)."""
        return np.array([self.thresholds[lv] for lv in RISK_LEVELS], dtype=np.float64)


def _env_float(name: str, default: float) -> float:
    v = os.environ.get(name)
    if v is None or v.strip() == "":
        return default
    try:
        return float(v)
    except ValueError:
        logger.warning("Invalid env %s=%r, fallback %s", name, v, default)
        return default


def _load_raw() -> dict:
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(f"Risk config not found: {CONFIG_PATH}")
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _apply_env_overrides(raw: dict) -> dict:
    weights = dict(raw.get("weights", {}))
    for k in FACTOR_KEYS:
        env_name = f"EWS_WEIGHT_{k.upper()}"
        if os.environ.get(env_name):
            weights[k] = _env_float(env_name, weights.get(k, 0.0))

    dyn = dict(raw.get("dynamic", {}))
    dyn["alpha"] = _env_float("EWS_ALPHA", dyn.get("alpha", 2.5))
    dyn["weight_floor"] = _env_float("EWS_WEIGHT_FLOOR", dyn.get("weight_floor", 0.05))
    dyn["worst_factor_beta"] = _env_float("EWS_WORST_FACTOR_BETA", dyn.get("worst_factor_beta", 0.20))

    raw["weights"] = weights
    raw["dynamic"] = dyn
    return raw


def _validate(raw: dict) -> None:
    weights = raw.get("weights", {})
    missing = [k for k in FACTOR_KEYS if k not in weights]
    if missing:
        raise ValueError(f"Missing weights for factors: {missing}")
    total = sum(weights[k] for k in FACTOR_KEYS)
    if abs(total - 1.0) > 1e-6:
        raise ValueError(f"Sum of weights must be 1.0, got {total:.4f}")
    for k in FACTOR_KEYS:
        if weights[k] < 0:
            raise ValueError(f"Weight for {k} must be >= 0, got {weights[k]}")

    thresholds = raw.get("risk_level_thresholds", {})
    missing_t = [lv for lv in RISK_LEVELS if lv not in thresholds]
    if missing_t:
        raise ValueError(f"Missing risk_level_thresholds for: {missing_t}")
    vals = [thresholds[lv] for lv in RISK_LEVELS]
    if any(vals[i] >= vals[i + 1] for i in range(len(vals) - 1)):
        raise ValueError("risk_level_thresholds must be strictly increasing")


@lru_cache(maxsize=1)
def load_risk_config() -> RiskConfig:
    """Load (có cache) RiskConfig từ YAML + env override."""
    raw = _load_raw()
    raw = _apply_env_overrides(raw)
    _validate(raw)
    dyn = DynamicConfig(**raw.get("dynamic", {}))
    cfg = RiskConfig(
        weights=raw.get("weights", {}),
        dynamic=dyn,
        thresholds=raw.get("risk_level_thresholds", {}),
    )
    logger.info(
        "RiskConfig loaded: weights=%s alpha=%.2f floor=%.2f beta=%.2f",
        cfg.weights, dyn.alpha, dyn.weight_floor, dyn.worst_factor_beta,
    )
    return cfg


def _softmax_weights(base: np.ndarray, sub_scores: np.ndarray, alpha: float, floor: float) -> np.ndarray:
    """Dynamic Softmax Attention: w_k = base_k * e^(alpha*S_k) / sum(...), rồi áp sàn."""
    s = np.clip(sub_scores, 0.0, 1.0)
    logits = base * np.exp(alpha * s)
    w = logits / logits.sum()
    if floor > 0:
        n = len(w)
        w = np.maximum(w, floor)
        w = w / w.sum()  # chuẩn hóa lại về 1.0 sau khi áp sàn
    return w


def combine_risk_scores(
    sub_scores: dict,
    cfg: RiskConfig | None = None,
    available: list[str] | None = None,
) -> dict:
    """
    Kết hợp sub-score (0-100) thành final risk_score + risk_level.

    Args:
        sub_scores: {factor: float} với factor thuộc FACTOR_KEYS (thang 0-100).
        cfg: RiskConfig (mặc định load_risk_config()).
        available: danh sách yếu tố CÓ DỮ LIỆU (subset của FACTOR_KEYS).
            Yếu tố không có dữ liệu (toàn bộ feature NaN) bị LOẠI khỏi ensemble —
            không coi "không có dữ liệu" như "không nộp bài / rủi ro cao".
            Mặc định None = dùng cả 4 yếu tố.

    Returns:
        dict gồm:
          final_risk_score (0-100), final_risk_level,
          weights (dict trọng số động đã dùng, yếu tố bị loại = 0.0), alpha, beta.
    """
    cfg = cfg or load_risk_config()

    # Chỉ dùng các yếu tố có dữ liệu
    keys = [k for k in FACTOR_KEYS if k in (available or FACTOR_KEYS)]
    if not keys:
        # Không có yếu tố nào có dữ liệu → trả về mức trung tính (50) để không phạt
        return {
            "final_risk_score": 50.0,
            "final_risk_level": RISK_LEVELS[1],  # MODERATE
            "weights": {k: 0.0 for k in FACTOR_KEYS},
            "alpha": cfg.dynamic.alpha if cfg.dynamic.enabled else 0.0,
            "beta": 0.0,
        }

    # Trọng số gốc chuẩn hoá lại theo subset yếu tố có dữ liệu
    base = np.array([cfg.weights[k] for k in keys], dtype=np.float64)
    base = base / base.sum()
    s100 = np.array([sub_scores[k] for k in keys], dtype=np.float64)  # 0-100
    s01 = s100 / 100.0

    if cfg.dynamic.enabled:
        w = _softmax_weights(base, s01, cfg.dynamic.alpha, cfg.dynamic.weight_floor)
        softmax_avg = float((w * s100).sum())
        beta = cfg.dynamic.worst_factor_beta
        worst = float(s100.max())
        final_score = (1.0 - beta) * softmax_avg + beta * worst
    else:
        w = base
        beta = 0.0
        final_score = float((w * s100).sum())

    final_score = round(float(np.clip(final_score, 0.0, 100.0)), 2)

    # Suy risk_level từ ngưỡng trên final risk_score
    thr = cfg.threshold_vector()
    level = RISK_LEVELS[0]
    for i, t in enumerate(thr):
        if final_score < t:
            level = RISK_LEVELS[i]
            break
    else:
        level = RISK_LEVELS[-1]

    # weights đầy đủ 4 yếu tố; yếu tố bị loại = 0.0
    weights_full = {k: 0.0 for k in FACTOR_KEYS}
    for i, k in enumerate(keys):
        weights_full[k] = round(float(w[i]), 4)

    return {
        "final_risk_score": final_score,
        "final_risk_level": level,
        "weights": weights_full,
        "alpha": cfg.dynamic.alpha if cfg.dynamic.enabled else 0.0,
        "beta": beta,
    }
