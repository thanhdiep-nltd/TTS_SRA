# -*- coding: utf-8 -*-
"""Unit tests cho danh sách tuần checkpoint hợp lệ của EWS (get_ews_valid_weeks, predict validation)."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from scripts import run_ews_pipeline
from src.api.v1 import ews as ews_module
from src.schemas.ews import EwsPredictRequest


def test_valid_weeks_does_not_contain_week_5():
    """Kiểm tra _VALID_WEEKS trong api ews và script pipeline không chứa tuần 5 cho HK1."""
    assert 5 not in ews_module._VALID_WEEKS[1]
    assert ews_module._VALID_WEEKS[1] == [8, 11, 14, 16]
    assert 5 not in run_ews_pipeline.VALID_WEEKS[1]
    assert run_ews_pipeline.VALID_WEEKS[1] == {8, 11, 14, 16}


def test_get_ews_valid_weeks_endpoint():
    """Kiểm tra endpoint get_ews_valid_weeks trả về semester_1 không có tuần 5."""
    user = SimpleNamespace(id=1, role="ADMIN", so_school_id=1)
    res = ews_module.get_ews_valid_weeks(current_user=user)
    assert res.semester_1 == [8, 11, 14, 16]
    assert 5 not in res.semester_1
    assert res.semester_2 == [23, 26, 29, 32, 34]


def test_trigger_ews_predict_rejects_week_5():
    """Kiểm tra gọi predict với tuần 5 ở HK1 bị reject 422."""
    user = SimpleNamespace(id=1, role="ADMIN", so_school_id=1)
    db = MagicMock()
    bg = MagicMock()
    req = EwsPredictRequest(
        school_year_id=2025,
        semester_index=1,
        evaluated_at_week=5,
        model_version="v2_ensemble",
    )
    with pytest.raises(HTTPException) as exc_info:
        ews_module.trigger_ews_predict(
            payload=req,
            background_tasks=bg,
            current_user=user,
            db=db,
        )
    assert exc_info.value.status_code == 422
    assert "không phải checkpoint chuẩn" in exc_info.value.detail
