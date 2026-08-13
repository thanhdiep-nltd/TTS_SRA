# -*- coding: utf-8 -*-
"""
Tests cho tính năng "nâng rủi ro do LLM" (LLM risk escalation) trong EWS.

Bao gồm:
- `_llm_risk_escalated`: hàm thuần xác định LLM có nâng mức rủi ro so với CatBoost.
- `_risk_level_rank_case`: sinh biểu thức SQL CASE cho bộ lọc.
- `EwsPredictionRow.llm_risk_escalated`: schema chấp nhận trường mới.

Chạy offline, không chạm DB thật (theo triết lý test mock của dự án).
"""

from src.api.v1.ews import _llm_risk_escalated, _risk_level_rank_case
from src.schemas.ews import EwsPredictionRow


# ============================================================================
# _llm_risk_escalated — hàm thuần
# ============================================================================


class TestLlmRiskEscalated:
    def test_moderate_to_high_is_escalated(self):
        """MODERATE → HIGH là nâng rủi ro (ví dụ chính người dùng nêu)."""
        assert _llm_risk_escalated("MODERATE", "HIGH") is True

    def test_high_to_critical_is_escalated(self):
        assert _llm_risk_escalated("HIGH", "CRITICAL") is True

    def test_same_level_not_escalated(self):
        assert _llm_risk_escalated("HIGH", "HIGH") is False

    def test_downgrade_not_escalated(self):
        assert _llm_risk_escalated("HIGH", "MODERATE") is False

    def test_missing_llm_level_returns_none(self):
        assert _llm_risk_escalated("MODERATE", None) is None

    def test_missing_llm_level_empty_string_returns_none(self):
        assert _llm_risk_escalated("MODERATE", "") is None

    def test_unknown_levels_return_none(self):
        assert _llm_risk_escalated("WEIRD", "HIGH") is None
        assert _llm_risk_escalated("MODERATE", "WEIRD") is None

    def test_none_base_with_valid_llm_returns_none(self):
        assert _llm_risk_escalated(None, "HIGH") is None

    def test_case_insensitive(self):
        assert _llm_risk_escalated("moderate", "high") is True
        assert _llm_risk_escalated("MODERATE", "high") is True

    def test_multi_step_escalation(self):
        """LOW → HIGH (nhảy 2 bậc) vẫn là nâng."""
        assert _llm_risk_escalated("LOW", "HIGH") is True
        assert _llm_risk_escalated("LOW", "CRITICAL") is True


# ============================================================================
# _risk_level_rank_case — sinh SQL CASE cho bộ lọc
# ============================================================================


class TestRiskLevelRankCase:
    def test_produces_rank_case_for_column(self):
        sql = _risk_level_rank_case("rp.risk_level")
        assert "CASE rp.risk_level" in sql
        assert "WHEN 'LOW' THEN 0" in sql
        assert "WHEN 'MODERATE' THEN 1" in sql
        assert "WHEN 'HIGH' THEN 2" in sql
        assert "WHEN 'CRITICAL' THEN 3" in sql
        assert "ELSE -1" in sql
        assert "END" in sql

    def test_matches_rank_constant(self):
        """SQL CASE phải khớp RISK_LEVEL_RANK trong schema."""
        from src.schemas.ews import RISK_LEVEL_RANK

        sql = _risk_level_rank_case("rp.risk_level")
        for level, rank in RISK_LEVEL_RANK.items():
            assert f"WHEN '{level}' THEN {rank}" in sql


# ============================================================================
# EwsPredictionRow — schema chấp nhận trường mới
# ============================================================================


class TestEwsPredictionRowLlmEscalation:
    def test_default_is_none(self):
        row = EwsPredictionRow(
            student_code="HS001",
            subject_id=106,
            evaluated_at_week=8,
            risk_score=60.0,
            risk_level="HIGH",
        )
        assert row.llm_risk_escalated is None

    def test_accepts_true(self):
        row = EwsPredictionRow(
            student_code="HS001",
            subject_id=106,
            evaluated_at_week=8,
            risk_score=60.0,
            risk_level="MODERATE",
            llm_risk_level="HIGH",
            llm_risk_escalated=True,
        )
        assert row.llm_risk_escalated is True
        assert row.llm_risk_level == "HIGH"

    def test_round_trip_via_model_dump(self):
        row = EwsPredictionRow(
            student_code="HS001",
            subject_id=106,
            evaluated_at_week=8,
            risk_score=60.0,
            risk_level="MODERATE",
            llm_risk_level="HIGH",
            llm_risk_escalated=True,
        )
        dumped = row.model_dump()
        assert dumped["llm_risk_escalated"] is True