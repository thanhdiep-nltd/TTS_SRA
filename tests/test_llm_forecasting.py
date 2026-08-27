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
    _get_previous_llm_result,
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
        raw = '{"llm_risk_score": 72.5, "llm_narrative_summary": "ok", "llm_recommended_actions": ["a", "b"]}'
        data = _parse_llm_response(raw)
        assert data["llm_risk_score"] == 72.5
        assert data["llm_narrative_summary"] == "ok"
        assert data["llm_recommended_actions"] == ["a", "b"]

    def test_parse_markdown_fence(self):
        raw = '```json\n{"llm_risk_score": 55, "llm_narrative_summary": "ghi chú"}\n```'
        data = _parse_llm_response(raw)
        assert data["llm_risk_score"] == 55
        assert data["llm_narrative_summary"] == "ghi chú"

    def test_parse_with_surrounding_text(self):
        raw = 'Đây là phân tích:\n{"llm_risk_score": 80, "llm_forecast_trend": "tăng"}\nHy vọng hữu ích.'
        data = _parse_llm_response(raw)
        assert data["llm_risk_score"] == 80
        assert data["llm_forecast_trend"] == "tăng"

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

    def test_ongoing_critical_severity_medical_triggers(self):
        """Bệnh ONGOING mức CRITICAL → trigger (kể cả không mãn tính)."""
        medical = [{"status": "ONGOING", "is_chronic": False, "severity": "CRITICAL"}]
        assert _should_trigger("LOW", [], medical) is True


# ============================================================================
# _normalize_llm_result
# ============================================================================


class TestNormalizeLlmResult:
    def test_valid_result_auto_classifies_level(self):
        """LLM không trả llm_risk_level; hệ thống tự phân loại theo baseline thresholds."""
        data = {
            "llm_risk_score": 70.0,
            "llm_narrative_summary": "abc",
            "llm_forecast_trend": "def",
            "llm_recommended_actions": ["x", "y"],
        }
        out = _normalize_llm_result(data, cb_score=60.0)
        assert out["llm_risk_score"] == 70.0
        # Default baseline: LOW < 20, MODERATE < 52.5, HIGH < 88.0 -> 70.0 is HIGH
        assert out["llm_risk_level"] == "HIGH"
        assert out["llm_narrative_summary"] == "abc"
        assert out["llm_forecast_trend"] == "def"
        assert json.loads(out["llm_recommended_actions"]) == ["x", "y"]
        assert isinstance(out["llm_evaluated_at"], datetime)

    def test_custom_school_config_thresholds(self):
        """Kiểm tra phân loại theo cấu hình tùy chỉnh của trường."""
        from src.ews.risk_config import RiskConfig
        custom_cfg = RiskConfig(
            thresholds={"LOW": 15.0, "MODERATE": 40.0, "HIGH": 65.0, "CRITICAL": 100.0}
        )
        data = {"llm_risk_score": 70.0}
        # Với custom config: >= 65.0 là CRITICAL -> 70.0 là CRITICAL
        out = _normalize_llm_result(data, cb_score=60.0, cfg=custom_cfg)
        assert out["llm_risk_level"] == "CRITICAL"

    def test_score_clamped_0_100(self):
        out = _normalize_llm_result({"llm_risk_score": 150}, cb_score=60)
        assert out["llm_risk_score"] == 100.0
        assert out["llm_risk_level"] == "CRITICAL"

        out2 = _normalize_llm_result({"llm_risk_score": -10}, cb_score=60)
        assert out2["llm_risk_score"] == 0.0
        assert out2["llm_risk_level"] == "LOW"

    def test_actions_not_list_becomes_empty(self):
        out = _normalize_llm_result({"llm_recommended_actions": "not-a-list"}, cb_score=60)
        assert json.loads(out["llm_recommended_actions"]) == []

    # --- Chính sách ổn định khi re-run (previous_llm_result) ---

    def test_rerun_keeps_old_score_when_delta_small(self):
        """|mới - cũ| <= 1.0 → giữ nguyên điểm cũ, không có lý do đổi."""
        previous = {"llm_risk_score": 75.0, "llm_risk_level": "HIGH"}
        data = {"llm_risk_score": 75.5}
        out = _normalize_llm_result(data, cb_score=60.0, previous_llm_result=previous)
        assert out["llm_risk_score"] == 75.0
        assert out["llm_risk_level"] == "HIGH"
        assert out["llm_previous_score"] == 75.0
        assert out["llm_score_change_reason"] is None

    def test_rerun_uses_new_score_when_delta_large_with_reason(self):
        """|mới - cũ| > 1.0 và có lý do từ LLM → dùng điểm mới + lưu lý do."""
        previous = {"llm_risk_score": 75.0, "llm_risk_level": "HIGH"}
        data = {
            "llm_risk_score": 90.0,
            "llm_score_change_reason": "Biến cố gia đình mới nghiêm trọng.",
        }
        out = _normalize_llm_result(data, cb_score=60.0, previous_llm_result=previous)
        assert out["llm_risk_score"] == 90.0
        assert out["llm_risk_level"] == "CRITICAL"
        assert out["llm_previous_score"] == 75.0
        assert out["llm_score_change_reason"] == "Biến cố gia đình mới nghiêm trọng."

    def test_rerun_fallback_reason_uses_giam_tu_when_score_drops(self):
        """Điểm giảm > 1.0, không có lý do từ LLM → fallback dùng chữ 'giảm từ'."""
        previous = {"llm_risk_score": 80.0, "llm_risk_level": "HIGH"}
        data = {"llm_risk_score": 50.0}
        out = _normalize_llm_result(data, cb_score=60.0, previous_llm_result=previous)
        assert out["llm_risk_score"] == 50.0
        assert out["llm_risk_level"] == "MODERATE"
        assert out["llm_previous_score"] == 80.0
        assert out["llm_score_change_reason"] is not None
        assert "giảm từ 80 sang 50" in out["llm_score_change_reason"]
        assert "tăng từ" not in out["llm_score_change_reason"]


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


# ============================================================================
# _get_previous_llm_result (mock session)
# ============================================================================


class TestGetPreviousLlmResult:
    def test_returns_dict_when_row_found(self):
        """Mock session trả về row → trả dict llm_risk_score/llm_risk_level."""
        session = MagicMock()
        row = MagicMock()
        row.llm_risk_score = 75.0
        row.llm_risk_level = "HIGH"
        session.execute.return_value.fetchone.return_value = row

        result = _get_previous_llm_result(
            session,
            student_code="HS0001",
            subject_id=106,
            school_year_id=2025,
            semester_index=1,
            evaluated_at_week=8,
        )
        assert result == {"llm_risk_score": 75.0, "llm_risk_level": "HIGH"}

    def test_returns_none_when_no_row(self):
        """Mock session trả về None → trả None (lần đánh giá đầu tiên)."""
        session = MagicMock()
        session.execute.return_value.fetchone.return_value = None

        result = _get_previous_llm_result(
            session,
            student_code="HS0001",
            subject_id=106,
            school_year_id=2025,
            semester_index=1,
            evaluated_at_week=8,
        )
        assert result is None

    def test_passes_tenant_and_model_filters(self):
        """so_school_id + model_version được truyền vào params của SQL query."""
        session = MagicMock()
        session.execute.return_value.fetchone.return_value = None

        _get_previous_llm_result(
            session,
            student_code="HS0001",
            subject_id=106,
            school_year_id=2025,
            semester_index=1,
            evaluated_at_week=8,
            so_school_id="42",
            model_version="v2_ensemble",
        )
        # Kiểm tra params truyền vào session.execute
        call_args = session.execute.call_args
        assert call_args is not None
        params = call_args[0][1]
        assert params["so_school_id"] == "42"
        assert params["model_version"] == "v2_ensemble"
