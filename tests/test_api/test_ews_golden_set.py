"""Tests cho Golden Set API (src/api/v1/ews.py) — cơ chế Static JSON Cache.

Chạy offline, không cần model .cbm / catboost / DB:
  - File cache src/ews/golden_set_data.json phải parse đúng schema EwsGoldenSetResult.
  - Loader _load_golden_set_json() trả đúng shape.
  - Khi file cache thiếu -> HTTPException 503 (không 500 mơ hồ).
"""

import json
from pathlib import Path

import pytest
from fastapi import HTTPException

from src.api.v1 import ews as ews_module
from src.schemas.ews import EwsGoldenSetResult

CACHE_PATH = Path(__file__).resolve().parents[2] / "src" / "ews" / "golden_set_data.json"


def test_cache_file_matches_schema():
    """File cache commit trong git phải parse đúng EwsGoldenSetResult (chặn file hỏng/stale)."""
    assert CACHE_PATH.exists(), "Thiếu src/ews/golden_set_data.json — chạy scripts/precompute_golden_set.py"
    with open(CACHE_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    result = EwsGoldenSetResult.model_validate(data)
    assert result.total == len(result.cases) == 8
    assert result.passed == 7
    assert result.accuracy == pytest.approx(0.875)
    # Metadata (non-breaking) nên có khi sinh bằng script mới.
    assert result.model_version == "v2_ensemble"
    assert result.generated_at is not None


def test_loader_returns_expected_shape():
    """_load_golden_set_json() trả dict đúng shape {total, passed, accuracy, cases}."""
    data = ews_module._load_golden_set_json()
    assert set(data) >= {"total", "passed", "accuracy", "cases"}
    assert data["total"] == 8
    assert len(data["cases"]) == 8
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
