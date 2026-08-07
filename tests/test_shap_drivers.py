# -*- coding: utf-8 -*-
"""Tests cho tính năng Top 5 SHAP Drivers (Signed SHAP) trong EWS."""

import json

import pytest

from src.api.v1.ews import _parse_shap
from src.schemas.ews import EwsPredictionRow


class TestParseShap:
    """Test helper _parse_shap (parse cột shap_drivers JSON string → list dict)."""

    def test_parses_valid_json_string(self):
        raw = json.dumps([
            {"rank": 1, "feature": "weighted_early_avg", "shap_value": 0.42, "value": 4.8},
            {"rank": 2, "feature": "lms_submission_rate", "shap_value": -0.25, "value": 0.32},
        ])
        parsed = _parse_shap(raw)
        assert isinstance(parsed, list)
        assert len(parsed) == 2
        assert parsed[0]["feature"] == "weighted_early_avg"
        assert parsed[0]["shap_value"] == 0.42
        # Signed SHAP: giữ dấu âm
        assert parsed[1]["shap_value"] == -0.25

    def test_returns_none_for_null(self):
        assert _parse_shap(None) is None

    def test_returns_none_for_empty_string(self):
        assert _parse_shap("") is None

    def test_returns_none_for_invalid_json(self):
        assert _parse_shap("not-json") is None

    def test_returns_none_for_non_list_json(self):
        assert _parse_shap('{"rank": 1}') is None

    def test_accepts_already_parsed_list(self):
        data = [{"rank": 1, "feature": "score_slope", "shap_value": 0.1}]
        assert _parse_shap(data) == data


class TestEwsPredictionRowShapDrivers:
    """Test schema EwsPredictionRow chấp nhận trường shap_drivers."""

    def test_shap_drivers_default_none(self):
        row = EwsPredictionRow(
            student_code="HS001",
            subject_id=1,
            evaluated_at_week=8,
            risk_score=60.0,
            risk_level="HIGH",
        )
        assert row.shap_drivers is None

    def test_shap_drivers_accepts_list(self):
        drivers = [
            {"rank": 1, "feature": "weighted_early_avg", "shap_value": 0.42, "value": 4.8},
            {"rank": 2, "feature": "lms_submission_rate", "shap_value": -0.25, "value": 0.32},
        ]
        row = EwsPredictionRow(
            student_code="HS001",
            subject_id=1,
            evaluated_at_week=8,
            risk_score=60.0,
            risk_level="HIGH",
            shap_drivers=drivers,
        )
        assert row.shap_drivers == drivers
        assert row.shap_drivers[1]["shap_value"] == -0.25  # Signed SHAP giữ dấu