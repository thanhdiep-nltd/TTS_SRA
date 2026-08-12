# -*- coding: utf-8 -*-
"""
Tests cho LLM-based Forecasting (src/ews/llm_forecasting.py).

Dùng monkeypatch để mock `get_llm()` (tránh gọi API thật) theo plan Testing:
- `_parse_llm_response`: parse JSON + markdown fence + lỗi
- `_should_trigger`: trigger condition đúng (HIGH/CRITICAL, biến cố/bệnh ONGOING)
- `_normalize_llm_result`: chuẩn hoá score/level/actions
- `forecast_student_risk`: gọi LLM + lưu đúng cột llm_* (mock session)
"""

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from src.ews.llm_forecasting import (
    _build_llm_prompt,
    _json_safe,
    _normalize_llm_result,
    _parse_llm_response,
    _should_trigger,
    forecast_student_risk,
)


# ============================================================================
# _parse_llm_response
# ============================================================================


class TestParseLlmResponse:
    def test_parse_plain_json(self):
        raw = '{"llm_risk_score": 72.5, "llm_risk_level": "HIGH", "llm_recommended_actions": ["a", "b"]}'
        data = _parse_llm_response(raw)
        assert data["llm_risk_score"] == 72.5
        assert data["llm_risk_level"] == "HIGH"
        assert data["llm_recommended_actions"] == ["a", "b"]

    def test_parse_markdown_fence(self):
        raw = '```json\n{"llm_risk_score": 55, "llm_risk_level": "MODERATE"}\n```'
        data = _parse_llm_response(raw)
        assert data["llm_risk_score"] == 55
        assert data["llm_risk_level"] == "MODERATE"

    def test_parse_with_surrounding_text(self):
        raw = 'Đây là phân tích:\n{"llm_risk_score": 80, "llm_risk_level": "CRITICAL"}\nHy vọng hữu ích.'
        data = _parse_llm_response(raw)
        assert data["llm_risk_score"] == 80
        assert data["llm_risk_level"] == "CRITICAL"

    def test_invalid_json_raises(self):
        with pytest.raises(ValueError):
            _parse_llm_response("not json at all")

    def test_empty_raises(self):
        with pytest.raises(ValueError):
            _parse_llm_response("")


# ============================================================================
# _should_trigger
# ============================================================================


class TestShouldTrigger:
    def test_high_risk_triggers(self):
        # Tạm thời bỏ HIGH để test (chỉ giữ CRITICAL) → HIGH không trigger nếu không có biến cố/bệnh
        assert _should_trigger("HIGH", [], []) is False

    def test_critical_triggers(self):
        assert _should_trigger("CRITICAL", [], []) is True

    def test_low_no_event_no_trigger(self):
        assert _should_trigger("LOW", [], []) is False

    def test_ongoing_life_event_triggers(self):
        life_events = [{"status": "ONGOING"}]
        assert _should_trigger("LOW", life_events, []) is True

    def test_resolved_life_event_no_trigger(self):
        life_events = [{"status": "RESOLVED"}]
        assert _should_trigger("LOW", life_events, []) is False

    def test_chronic_ongoing_medical_triggers(self):
        medical = [{"status": "ONGOING", "is_chronic": True, "severity": "LOW"}]
        assert _should_trigger("LOW", [], medical) is True

    def test_ongoing_high_severity_medical_triggers(self):
        medical = [{"status": "ONGOING", "is_chronic": False, "severity": "HIGH"}]
        assert _should_trigger("LOW", [], medical) is True

    def test_ongoing_low_severity_nonchronic_no_trigger(self):
        medical = [{"status": "ONGOING", "is_chronic": False, "severity": "LOW"}]
        assert _should_trigger("LOW", [], medical) is False


# ============================================================================
# _normalize_llm_result
# ============================================================================


class TestNormalizeLlmResult:
    def test_valid_result(self):
        data = {
            "llm_risk_score": 70.0,
            "llm_risk_level": "HIGH",
            "llm_narrative_summary": "abc",
            "llm_forecast_trend": "def",
            "llm_recommended_actions": ["x", "y"],
        }
        out = _normalize_llm_result(data, cb_score=60.0)
        assert out["llm_risk_score"] == 70.0
        assert out["llm_risk_level"] == "HIGH"
        assert out["llm_narrative_summary"] == "abc"
        assert out["llm_forecast_trend"] == "def"
        assert json.loads(out["llm_recommended_actions"]) == ["x", "y"]
        assert isinstance(out["llm_evaluated_at"], datetime)

    def test_score_clamped_0_100(self):
        out = _normalize_llm_result({"llm_risk_score": 150}, cb_score=60)
        assert out["llm_risk_score"] == 100.0
        out2 = _normalize_llm_result({"llm_risk_score": -10}, cb_score=60)
        assert out2["llm_risk_score"] == 0.0

    def test_invalid_level_inferred_from_score(self):
        out = _normalize_llm_result({"llm_risk_score": 90, "llm_risk_level": "weird"}, cb_score=60)
        assert out["llm_risk_level"] == "CRITICAL"

    def test_actions_not_list_becomes_empty(self):
        out = _normalize_llm_result({"llm_recommended_actions": "not-a-list"}, cb_score=60)
        assert json.loads(out["llm_recommended_actions"]) == []


# ============================================================================
# _json_safe (Decimal/numpy → JSON-serializable)
# ============================================================================


class TestJsonSafe:
    def test_decimal_to_float(self):
        from decimal import Decimal
        assert _json_safe(Decimal("60.45")) == 60.45

    def test_int_and_float_pass_through(self):
        assert _json_safe(5) == 5
        assert _json_safe(5.5) == 5.5

    def test_bool_not_confused_with_int(self):
        assert _json_safe(True) is True

    def test_none_returns_none(self):
        assert _json_safe(None) is None

    def test_string_fallback(self):
        assert _json_safe("abc") == "abc"


class TestBuildLlmPromptWithDecimal:
    def test_prompt_builds_with_decimal_features(self):
        """Regression test: json.dumps không serialize được Decimal — prompt phải build được."""
        from decimal import Decimal

        features = {
            "risk_score": Decimal("75.5"),
            "risk_level": "HIGH",
            "weighted_early_avg": Decimal("6.5"),
            "weighted_late_avg": Decimal("5.2"),
            "score_slope": Decimal("-0.3"),
            "score_volatility": Decimal("1.2"),
            "max_drop": Decimal("2.5"),
            "last_score": Decimal("4.0"),
            "lms_avg_score": Decimal("7.0"),
            "lms_recent_drop": Decimal("0.5"),
            "lms_submission_rate": Decimal("0.6"),
            "daily_absence_rate": Decimal("0.1"),
            "unexcused_absent_rate": Decimal("0.05"),
            "total_demerit_points": Decimal("3"),
            "repeat_offense_count": Decimal("1"),
            "severe_sanction_count": Decimal("0"),
        }
        prompt = _build_llm_prompt(
            student_code="HS0001",
            subject_name="Toán",
            features=features,
            life_events=[{"status": "ONGOING", "time_quantity": 2, "time_unit": "MONTH"}],
            medical=[],
        )
        # Prompt phải chứa risk_score đã convert sang float
        assert '"risk_score": 75.5' in prompt
        assert "HIGH" in prompt


# ============================================================================
# forecast_student_risk (mock session + get_llm)
# ============================================================================


class TestForecastStudentRisk:
    def test_no_trigger_returns_none(self, monkeypatch):
        # Mock session trả về không có life_events/medical
        session = MagicMock()
        session.execute.return_value.fetchall.return_value = []

        monkeypatch.setattr(
            "src.ews.llm_forecasting.get_llm",
            lambda: (_ for _ in ()).throw(AssertionError("get_llm should not be called")),
        )

        features = {"risk_score": 30.0, "risk_level": "LOW"}
        result = forecast_student_risk(
            session=session,
            student_code="HS0001",
            subject_id=106,
            school_year_id=2025,
            semester_index=1,
            evaluated_at_week=8,
            subject_name="Toán",
            features=features,
        )
        assert result is None

    def test_trigger_calls_llm_and_persists(self, monkeypatch):
        # Mock get_llm() trả về JSON hợp lệ
        class FakeLLM:
            def invoke(self, prompt):
                msg = MagicMock()
                msg.content = json.dumps({
                    "llm_risk_score": 75.0,
                    "llm_risk_level": "HIGH",
                    "llm_narrative_summary": "Học sinh có biến cố gia đình ONGOING.",
                    "llm_forecast_trend": "Rủi ro có thể tăng.",
                    "llm_recommended_actions": ["Hỗ trợ tâm lý", "Trao đổi với phụ huynh"],
                })
                return msg

        monkeypatch.setattr("src.ews.llm_forecasting.get_llm", lambda: FakeLLM())

        # Mock session: trả về 1 biến cố ONGOING → trigger
        session = MagicMock()

        def fake_execute(sql, params=None):
            r = MagicMock()
            if "life_events" in str(sql):
                r.fetchall.return_value = [
                    MagicMock(
                        event_name="Bố mẹ ly hôn",
                        event_type="FAMILY_DIVORCE",
                        event_date=None,
                        severity="HIGH",
                        description="",
                        time_quantity=2,
                        time_unit="MONTH",
                        status="ONGOING",
                    )
                ]
            elif "medical_history" in str(sql):
                r.fetchall.return_value = []
            else:
                r.fetchall.return_value = []
            return r

        session.execute.side_effect = fake_execute

        features = {"risk_score": 40.0, "risk_level": "MODERATE"}
        result = forecast_student_risk(
            session=session,
            student_code="HS0001",
            subject_id=106,
            school_year_id=2025,
            semester_index=1,
            evaluated_at_week=8,
            subject_name="Toán",
            features=features,
        )
        assert result is not None
        assert result["llm_risk_score"] == 75.0
        assert result["llm_risk_level"] == "HIGH"
        # Đảm bảo _persist_llm_columns được gọi (session.execute UPDATE)
        assert session.commit.called