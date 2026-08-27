# -*- coding: utf-8 -*-
"""
src/ews/ews_config_service.py — Merge cấu hình trọng số EWS theo trường (BGH).

Vấn đề: `load_risk_config()` dùng `@lru_cache(maxsize=1)` cho baseline YAML toàn cục.
Nếu BGH trường A chỉnh trọng số, KHÔNG được đụng cache toàn cục (tránh lỗi tenant
isolation giữa các trường trong cùng process). Thay vào đó, mỗi lần cần config hiệu
lực cho một trường, ta lấy baseline (có cache) rồi merge override từ bảng
`ews_weight_overrides` (theo `so_school_id`) thành một `RiskConfig` MỚI.

Override chỉ ảnh hưởng `v2_ensemble` (factor-ensemble dùng `combine_risk_scores`).
"""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from src.ews.risk_config import (
    FACTOR_KEYS,
    RISK_LEVELS,
    DynamicConfig,
    RiskConfig,
    load_risk_config,
)
from src.models.tables import EwsWeightOverride

logger = logging.getLogger(__name__)

# Dải an toàn gợi ý cho từng nhóm chỉ số (dùng để cảnh báo trên UI, không chặn cứng).
SAFE_RANGES = {
    "alpha": (0.5, 3.0),
    "weight_floor": (0.0, 0.2),
    "worst_factor_beta": (0.0, 1.0),
}


class EwsConfigValidationError(ValueError):
    """Lỗi validate override trọng số EWS."""


def get_override(db: Session, school_id: int) -> EwsWeightOverride | None:
    """Lấy override của một trường (None nếu chưa có)."""
    return (
        db.query(EwsWeightOverride)
        .filter(EwsWeightOverride.so_school_id == school_id)
        .first()
    )


def _merge_weights(base: dict, ov: EwsWeightOverride) -> dict:
    weights = dict(base)
    mapping = {
        "score": ov.weight_score,
        "lms": ov.weight_lms,
        "attendance": ov.weight_attendance,
        "behavior": ov.weight_behavior,
    }
    for factor, val in mapping.items():
        if val is not None:
            weights[factor] = float(val)
    return weights


def _merge_alpha(base: dict, ov: EwsWeightOverride) -> dict:
    alpha = dict(base)
    mapping = {
        "score": ov.alpha_score,
        "lms": ov.alpha_lms,
        "attendance": ov.alpha_attendance,
        "behavior": ov.alpha_behavior,
    }
    for factor, val in mapping.items():
        if val is not None:
            alpha[factor] = float(val)
    return alpha


def _merge_thresholds(base: dict, ov: EwsWeightOverride) -> dict:
    thresholds = dict(base)
    mapping = {
        "LOW": ov.threshold_low,
        "MODERATE": ov.threshold_moderate,
        "HIGH": ov.threshold_high,
        "CRITICAL": ov.threshold_critical,
    }
    for level, val in mapping.items():
        if val is not None:
            thresholds[level] = float(val)
    return thresholds


def build_effective_config(
    base: RiskConfig, ov: EwsWeightOverride | None
) -> RiskConfig:
    """Merge baseline + override thành RiskConfig mới (không đụng cache toàn cục)."""
    if ov is None:
        return base

    weights = _merge_weights(base.weights, ov)
    alpha = _merge_alpha(base.dynamic.alpha, ov)
    weight_floor = (
        float(ov.weight_floor)
        if ov.weight_floor is not None
        else base.dynamic.weight_floor
    )
    worst_factor_beta = (
        float(ov.worst_factor_beta)
        if ov.worst_factor_beta is not None
        else base.dynamic.worst_factor_beta
    )
    thresholds = _merge_thresholds(base.thresholds, ov)

    dyn = DynamicConfig(
        enabled=base.dynamic.enabled,
        alpha=alpha,
        weight_floor=weight_floor,
        worst_factor_beta=worst_factor_beta,
    )
    return RiskConfig(
        weights=weights,
        dynamic=dyn,
        thresholds=thresholds,
        calibration=dict(base.calibration),
    )


def get_effective_config(db: Session, school_id: int) -> RiskConfig:
    """Config hiệu lực cho một trường = baseline YAML + override (nếu có)."""
    base = load_risk_config()
    ov = get_override(db, school_id)
    cfg = build_effective_config(base, ov)
    if ov is not None:
        logger.info(
            "Effective EWS config for school %d: weights=%s alpha=%s floor=%.2f beta=%.2f thr=%s",
            school_id, cfg.weights, cfg.dynamic.alpha,
            cfg.dynamic.weight_floor, cfg.dynamic.worst_factor_beta, cfg.thresholds,
        )
    return cfg


def validate_override(payload: dict) -> None:
    """Validate override trước khi lưu. Raise EwsConfigValidationError nếu sai."""
    weights = {
        k: payload.get(f"weight_{k}")
        for k in FACTOR_KEYS
    }
    provided_weights = {k: v for k, v in weights.items() if v is not None}
    if provided_weights:
        total = sum(float(v) for v in provided_weights.values())
        if abs(total - 1.0) > 1e-6:
            raise EwsConfigValidationError(
                f"Tổng trọng số phải bằng 1.0, hiện tại {total:.4f}"
            )
        for k, v in provided_weights.items():
            if float(v) < 0:
                raise EwsConfigValidationError(
                    f"Trọng số {k} phải >= 0, nhận {v}"
                )

    thresholds = {
        "LOW": payload.get("threshold_low"),
        "MODERATE": payload.get("threshold_moderate"),
        "HIGH": payload.get("threshold_high"),
        "CRITICAL": payload.get("threshold_critical"),
    }
    provided_thr = [thresholds[lv] for lv in RISK_LEVELS if thresholds[lv] is not None]
    if len(provided_thr) >= 2:
        vals = [float(v) for v in provided_thr]
        if any(vals[i] >= vals[i + 1] for i in range(len(vals) - 1)):
            raise EwsConfigValidationError(
                "Các ngưỡng risk_level phải tăng dần (LOW < MODERATE < HIGH < CRITICAL)"
            )

    # Cảnh báo dải an toàn (không chặn cứng, chỉ ghi log — UI hiển thị cảnh báo).
    for factor in FACTOR_KEYS:
        a = payload.get(f"alpha_{factor}")
        if a is not None and not (SAFE_RANGES["alpha"][0] <= float(a) <= SAFE_RANGES["alpha"][1]):
            logger.warning("alpha_%s=%.2f ngoài dải an toàn %s", factor, float(a), SAFE_RANGES["alpha"])
    wf = payload.get("weight_floor")
    if wf is not None and not (SAFE_RANGES["weight_floor"][0] <= float(wf) <= SAFE_RANGES["weight_floor"][1]):
        logger.warning("weight_floor=%.2f ngoài dải an toàn %s", float(wf), SAFE_RANGES["weight_floor"])


def apply_override(
    db: Session, school_id: int, payload: dict, updated_by: int
) -> EwsWeightOverride:
    """Lưu (upsert) override cho một trường. Trả về bản ghi đã lưu."""
    validate_override(payload)

    ov = get_override(db, school_id)
    if ov is None:
        ov = EwsWeightOverride(so_school_id=school_id)
        db.add(ov)

    field_map = {
        "weight_score": "weight_score",
        "weight_lms": "weight_lms",
        "weight_attendance": "weight_attendance",
        "weight_behavior": "weight_behavior",
        "alpha_score": "alpha_score",
        "alpha_lms": "alpha_lms",
        "alpha_attendance": "alpha_attendance",
        "alpha_behavior": "alpha_behavior",
        "weight_floor": "weight_floor",
        "worst_factor_beta": "worst_factor_beta",
        "threshold_low": "threshold_low",
        "threshold_moderate": "threshold_moderate",
        "threshold_high": "threshold_high",
        "threshold_critical": "threshold_critical",
    }
    for key, col in field_map.items():
        if key in payload and payload[key] is not None:
            setattr(ov, col, float(payload[key]))

    ov.updated_by = updated_by
    db.commit()
    db.refresh(ov)
    logger.info("Applied EWS weight override for school %d by user %d", school_id, updated_by)
    return ov


def clear_override(db: Session, school_id: int) -> bool:
    """Xóa override của một trường (khôi phục baseline). Trả về True nếu có xóa."""
    ov = get_override(db, school_id)
    if ov is None:
        return False
    db.delete(ov)
    db.commit()
    logger.info("Cleared EWS weight override for school %d", school_id)
    return True
