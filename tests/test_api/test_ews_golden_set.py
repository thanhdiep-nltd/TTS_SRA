"""Tests cho Golden Set API (src/api/v1/ews.py) — cơ chế Static JSON Cache.

Chạy offline, không cần model .cbm / catboost / DB:
  - File cache src/ews/golden_set_data.json phải parse đúng schema EwsGoldenSetResult.
  - Loader _load_golden_set_json() trả đúng shape.
  - Khi file cache thiếu -> HTTPException 503 (không 500 mơ hồ).
"""

import json
from pathlib import Path

import pandas as pd
import pytest
from fastapi import HTTPException

from src.api.v1 import ews as ews_module
from src.ews import golden_set
from src.schemas.ews import EwsGoldenSetResult

CACHE_PATH = Path(__file__).resolve().parents[2] / "src" / "ews" / "golden_set_data.json"


def test_cache_file_matches_schema():
    """File cache commit trong git phải parse đúng EwsGoldenSetResult (chặn file hỏng/stale)."""
    assert CACHE_PATH.exists(), "Thiếu src/ews/golden_set_data.json — chạy scripts/precompute_golden_set.py"
    with open(CACHE_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    result = EwsGoldenSetResult.model_validate(data)
    assert result.total == len(result.cases) == 16
    assert result.passed == 15
    assert result.accuracy == pytest.approx(0.9375)
    # Metadata (non-breaking) nên có khi sinh bằng script mới.
    assert result.model_version == "v2_ensemble"
    assert result.generated_at is not None


def test_loader_returns_expected_shape():
    """_load_golden_set_json() trả dict đúng shape {total, passed, accuracy, cases}."""
    data = ews_module._load_golden_set_json()
    assert set(data) >= {"total", "passed", "accuracy", "cases"}
    assert data["total"] == 16
    assert len(data["cases"]) == 16
    # Mỗi case phải có đủ các trường bắt buộc của EwsGoldenSetCase.
    for c in data["cases"]:
        assert {"id", "description", "predicted", "expected", "passed", "risk_score"} <= set(c)
        assert "features" in c


def test_loader_503_when_file_missing(monkeypatch):
    """Khi file cache thiếu -> HTTPException 503 kèm hướng dẫn tái sinh (không 500)."""
    missing = CACHE_PATH.parent / "golden_set_data_missing.json"
    monkeypatch.setattr(ews_module, "_GOLDEN_SET_CACHE_PATH", missing)
    with pytest.raises(HTTPException) as exc:
        ews_module._load_golden_set_json()
    assert exc.value.status_code == 503
    assert "precompute_golden_set" in exc.value.detail


def _fake_result_df() -> pd.DataFrame:
    """Fake DataFrame đủ cột mà run_golden_set đọc; risk_level trùng expected -> all pass."""
    expected_levels = [c[3] for c in golden_set.CASES]
    n = len(expected_levels)
    return pd.DataFrame({
        "risk_level": expected_levels,
        "risk_score": [50.0] * n,
        "score_risk": [10.0] * n,
        "lms_risk": [10.0] * n,
        "attendance_risk": [10.0] * n,
        "behavior_risk": [10.0] * n,
        "weight_attendance": [0.25] * n,
        "weight_behavior": [0.25] * n,
    })


def test_run_golden_set_school_id_none_uses_baseline(monkeypatch):
    """school_id=None -> KHÔNG mở DB, truyền cfg=None (baseline YAML thuần)."""
    captured = {}
    monkeypatch.setattr(golden_set, "load_ensemble", lambda: {})
    monkeypatch.setattr(golden_set, "run_ensemble_inference",
                        lambda models, X, return_shap, cfg: (captured.update(cfg=cfg) or _fake_result_df()))
    res = golden_set.run_golden_set(school_id=None)
    assert captured["cfg"] is None
    assert res["total"] == 16
    assert res["passed"] == 16  # fake trả risk_level = expected


def test_run_golden_set_with_school_id_passes_merged_cfg(monkeypatch):
    """school_id != None -> mở SessionLocal, gọi get_effective_config và truyền cfg đã merge."""
    captured = {}

    class _FakeDB:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    def fake_effective(db, school_id):
        captured["school_id"] = school_id
        captured["session_opened"] = isinstance(db, _FakeDB)
        return {"merged": True}  # cfg giả — chỉ để verify được truyền qua

    monkeypatch.setattr(golden_set, "load_ensemble", lambda: {})
    monkeypatch.setattr("src.db.session.SessionLocal", lambda: _FakeDB())
    monkeypatch.setattr("src.ews.ews_config_service.get_effective_config", fake_effective)
    monkeypatch.setattr(golden_set, "run_ensemble_inference",
                        lambda models, X, return_shap, cfg: (captured.update(cfg=cfg) or _fake_result_df()))

    res = golden_set.run_golden_set(school_id=7)

    assert captured["school_id"] == 7
    assert captured["session_opened"] is True
    assert captured["cfg"] == {"merged": True}
    assert res["total"] == 16
    assert res["passed"] == 16
