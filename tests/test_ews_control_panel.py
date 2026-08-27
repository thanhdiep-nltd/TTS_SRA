# -*- coding: utf-8 -*-
"""Tests cho EWS Control Panel (BGH): ews_config_service + job_worker.

Chạy offline, không chạm DB thật — dùng mock session / mock run_pipeline.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from src.ews import ews_config_service
from src.ews.ews_config_service import (
    EwsConfigValidationError,
    build_effective_config,
    get_effective_config,
    validate_override,
)
from src.ews.risk_config import load_risk_config
from src.models.tables import EwsWeightOverride


# ============================================================================
# validate_override
# ============================================================================


def test_validate_weights_sum_must_be_one():
    with pytest.raises(EwsConfigValidationError):
        validate_override({"weight_score": 0.5, "weight_lms": 0.2, "weight_attendance": 0.1, "weight_behavior": 0.1})


def test_validate_weights_sum_ok():
    # Không raise
    validate_override({"weight_score": 0.5, "weight_lms": 0.2, "weight_attendance": 0.15, "weight_behavior": 0.15})


def test_validate_thresholds_must_increase():
    with pytest.raises(EwsConfigValidationError):
        validate_override({"threshold_low": 20.0, "threshold_moderate": 10.0})


def test_validate_thresholds_ok():
    validate_override({"threshold_low": 20.0, "threshold_moderate": 52.5, "threshold_high": 88.0, "threshold_critical": 100.0})


# ============================================================================
# build_effective_config / get_effective_config
# ============================================================================


def _override(**kw) -> EwsWeightOverride:
    ov = EwsWeightOverride(so_school_id=1)
    for k, v in kw.items():
        setattr(ov, k, v)
    return ov


def test_build_effective_config_no_override_returns_base():
    base = load_risk_config()
    assert build_effective_config(base, None) is base


def test_build_effective_config_merges_override():
    base = load_risk_config()
    ov = _override(weight_score=0.7, weight_lms=0.1, weight_attendance=0.1, weight_behavior=0.1)
    cfg = build_effective_config(base, ov)
    assert cfg.weights["score"] == 0.7
    assert cfg.weights["lms"] == 0.1
    # Các field không override giữ nguyên baseline
    assert cfg.dynamic.weight_floor == base.dynamic.weight_floor
    assert cfg.thresholds == base.thresholds
    # Không đụng baseline gốc
    assert base.weights["score"] != 0.7


def test_get_effective_config_per_school(monkeypatch):
    """Trường A có override, trường B không -> config khác nhau đúng (tenant isolation)."""
    base = load_risk_config()

    def fake_query(model):
        q = MagicMock()
        q.filter.return_value = q
        q.first.return_value = None
        return q

    db = MagicMock()
    db.query.side_effect = fake_query

    # Trường B: không override
    monkeypatch.setattr(ews_config_service, "get_override", lambda db_, sid: None)
    cfg_b = get_effective_config(db, 999)
    assert cfg_b.weights == base.weights

    # Trường A: có override
    ov = _override(weight_score=0.6, weight_lms=0.2, weight_attendance=0.1, weight_behavior=0.1)
    monkeypatch.setattr(ews_config_service, "get_override", lambda db_, sid: ov)
    cfg_a = get_effective_config(db, 1)
    assert cfg_a.weights["score"] == 0.6
    assert cfg_a.weights["lms"] == 0.2


# ============================================================================
# job_worker — process_next_ews_job (mock run_pipeline)
# ============================================================================


def _make_job(**kw) -> SimpleNamespace:
    defaults = dict(
        id=1, so_school_id=1, requested_by=99, school_year_id=2025,
        semester_index=1, evaluated_at_week=8, cutoff_date=None,
        model_version="v2_ensemble", status="pending", progress=0,
        rows_processed=None, error_message=None, started_at=None, finished_at=None,
    )
    defaults.update(kw)
    return SimpleNamespace(**defaults)


def test_process_next_ews_job_completes(monkeypatch):
    """Job pending -> chạy run_pipeline (mock) -> completed + rows_processed."""
    job = _make_job()
    db = MagicMock()
    # Mỗi lần db.query(model) trả về query mock riêng:
    #   - stuck: .all() -> [] ; active: .first() -> None ; next: .first() -> job
    def fake_query(model):
        q = MagicMock()
        q.filter.return_value.all.return_value = []
        q.filter.return_value.first.side_effect = [None, job]  # active -> None
        q.filter.return_value.order_by.return_value.first.return_value = job  # next -> job
        return q
    db.query.side_effect = fake_query
    db.get.return_value = SimpleNamespace(id=99)

    monkeypatch.setattr("src.db.session.SessionLocal", lambda: db)
    monkeypatch.setattr("src.ews.job_worker.get_effective_config", lambda db_, sid: load_risk_config())
    result = MagicMock()
    result.__len__.return_value = 42
    monkeypatch.setattr("src.ews.job_worker.run_pipeline", lambda **kw: result)
    # Tránh đệ quy vô hạn: patch attribute module, giữ tham chiếu hàm gốc để gọi
    from src.ews import job_worker as jw
    orig = jw.process_next_ews_job
    monkeypatch.setattr(jw, "process_next_ews_job", lambda: None)
    orig()

    assert job.status == "completed"
    assert job.progress == 100
    assert job.rows_processed == 42


def test_process_next_ews_job_fails(monkeypatch):
    """run_pipeline raise -> job failed + error_message."""
    job = _make_job()
    db = MagicMock()
    def fake_query(model):
        q = MagicMock()
        q.filter.return_value.all.return_value = []
        q.filter.return_value.first.side_effect = [None, job]
        q.filter.return_value.order_by.return_value.first.return_value = job
        return q
    db.query.side_effect = fake_query
    db.get.return_value = SimpleNamespace(id=99)

    monkeypatch.setattr("src.db.session.SessionLocal", lambda: db)
    monkeypatch.setattr("src.ews.job_worker.get_effective_config", lambda db_, sid: load_risk_config())
    monkeypatch.setattr(
        "src.ews.job_worker.run_pipeline",
        lambda **kw: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    from src.ews import job_worker as jw
    orig = jw.process_next_ews_job
    monkeypatch.setattr(jw, "process_next_ews_job", lambda: None)
    orig()

    assert job.status == "failed"
    assert "boom" in job.error_message
