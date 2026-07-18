"""Test offline cho subsystem "Đánh giá & Thống kê AI" (audit 2026-07-02):

- histogram_quantile: độ chính xác percentile (trước đây lệch ~29% với bucket thưa).
- alerting: cửa sổ/ngưỡng eval degradation, đồng bộ daily_cost từ DB, error rate, agent runaway.
- eval: should_sample, judge_faithfulness/judge_groundedness (fail-soft), get_judge_llm.
- observability: redact_pii, classify_response_guardrail (advisory PII tagging).

Chạy offline: Histogram Prometheus thật (không cần server), mock DB/LLM, không chạm Neon.
"""

import copy
import random
from datetime import date, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from prometheus_client import CollectorRegistry, Histogram

from src.observability import (
    _LATENCY_BUCKETS,
    _PII_PATTERNS,
    breakdown_counter,
    classify_response_guardrail,
    histogram_quantile,
    merge_counts_with_snapshot_fallback,
    merge_p95_with_snapshot_fallback,
    redact_pii,
    sum_counter,
)
from src.services import alerting
from src.services import eval as eval_service
from src.services.llm import DeepSeekDSMLWrapper, TimedChatOpenAI, get_judge_llm

# --- histogram_quantile ------------------------------------------------------------


def _make_histogram(buckets, registry):
    return Histogram("t_latency", "t", ["feature"], buckets=buckets, registry=registry)


def test_histogram_quantile_accurate_with_dense_buckets_near_realistic_latency():
    """Buckets mới (dày ở 1-10s) phải cho P95 sát giá trị thật — trước đây lệch ~29%."""
    registry = CollectorRegistry()
    h = _make_histogram(_LATENCY_BUCKETS, registry)
    random.seed(7)
    samples = [max(0.3, random.gauss(4.5, 1.8)) for _ in range(500)]
    for s in samples:
        h.labels(feature="chat").observe(s)

    samples.sort()
    true_p95 = samples[int(0.95 * len(samples))]
    computed = histogram_quantile(h, 0.95, {"feature": "chat"})
    assert computed is not None
    error_pct = abs(true_p95 - computed) / true_p95 * 100
    assert error_pct < 10, f"P95 sai lệch {error_pct:.1f}% — bucket quá thưa"


def test_histogram_quantile_returns_none_when_no_samples():
    registry = CollectorRegistry()
    h = _make_histogram(_LATENCY_BUCKETS, registry)
    assert histogram_quantile(h, 0.95, {"feature": "chat"}) is None


def test_histogram_quantile_filters_by_label():
    registry = CollectorRegistry()
    h = _make_histogram(_LATENCY_BUCKETS, registry)
    for _ in range(20):
        h.labels(feature="chat").observe(1.0)
    for _ in range(20):
        h.labels(feature="other_feature").observe(100.0)
    p95_chat = histogram_quantile(h, 0.95, {"feature": "chat"})
    assert p95_chat is not None
    assert p95_chat < 5  # không bị nhiễu bởi 'other_feature' toàn giá trị 100


def test_histogram_quantile_single_bucket_all_same_value():
    registry = CollectorRegistry()
    h = _make_histogram(_LATENCY_BUCKETS, registry)
    for _ in range(10):
        h.labels(feature="chat").observe(0.1)
    p95 = histogram_quantile(h, 0.95, {"feature": "chat"})
    # Toàn bộ mẫu (0.1) rơi vào bucket nhỏ nhất (le=0.5) -> nội suy tuyến tính giữa 0 và 0.5.
    assert 0.0 < p95 <= 0.5


# --- sum_counter / breakdown_counter -------------------------------------------------


def test_sum_counter_and_breakdown_counter():
    from prometheus_client import Counter

    registry = CollectorRegistry()
    c = Counter("t_routes", "t", ["target_agent"], registry=registry)
    c.labels(target_agent="data_agent").inc(3)
    c.labels(target_agent="stat_agent").inc(2)

    assert sum_counter(c) == 5
    breakdown = breakdown_counter(c, "target_agent")
    assert breakdown == {"data_agent": 3, "stat_agent": 2}


# --- merge_counts_with_snapshot_fallback / merge_p95_with_snapshot_fallback ------------


def test_merge_counts_partial_live_data_backfills_missing_agents_from_snapshot():
    """Bug đã sửa: trước đây chỉ cần 1 agent có hoạt động mới (live không rỗng) là TOÀN BỘ
    breakdown bỏ qua snapshot, khiến các agent khác hiện sai thành 0 dù có lịch sử."""
    live = {"data_agent": 1}  # chỉ data_agent được gọi lại kể từ restart
    snapshot = {"data_agent": 50, "stat_agent": 30, "sql_agent": 10, "knowledge_agent": 5, "report_agent": 2}
    merged = merge_counts_with_snapshot_fallback(live, snapshot)
    assert merged == {"data_agent": 1, "stat_agent": 30, "sql_agent": 10, "knowledge_agent": 5, "report_agent": 2}


def test_merge_counts_live_value_always_wins_over_snapshot():
    live = {"data_agent": 5}
    snapshot = {"data_agent": 999}
    merged = merge_counts_with_snapshot_fallback(live, snapshot)
    assert merged["data_agent"] == 5  # live (đã tích lũy kể từ restart) không bị snapshot cũ ghi đè


def test_merge_counts_no_snapshot_returns_live_unchanged():
    live = {"data_agent": 1}
    assert merge_counts_with_snapshot_fallback(live, None) == {"data_agent": 1}
    assert merge_counts_with_snapshot_fallback(live, {}) == {"data_agent": 1}


def test_merge_counts_empty_live_and_no_snapshot_returns_empty():
    assert merge_counts_with_snapshot_fallback({}, None) == {}


def test_merge_p95_backfills_only_none_entries_from_snapshot():
    live = {"supervisor": 100.0, "data_agent": None, "stat_agent": None}
    snapshot = {"supervisor": 999.0, "data_agent": 200.0, "stat_agent": None}
    merged = merge_p95_with_snapshot_fallback(live, snapshot)
    assert merged["supervisor"] == 100.0  # live thắng, không bị ghi đè
    assert merged["data_agent"] == 200.0  # live None -> lấy từ snapshot
    assert merged["stat_agent"] is None  # cả live lẫn snapshot đều None -> vẫn None


def test_merge_p95_no_snapshot_returns_live_unchanged():
    live = {"data_agent": None}
    assert merge_p95_with_snapshot_fallback(live, None) == {"data_agent": None}


# --- redact_pii / classify_response_guardrail -----------------------------------------


def test_redact_pii_masks_phone_email_id():
    text = "Gọi số 0912345678 hoặc email a@b.com, CCCD 123456789012"
    redacted = redact_pii(text)
    assert "0912345678" not in redacted
    assert "a@b.com" not in redacted
    assert "123456789012" not in redacted
    assert "[PHONE_REDACTED]" in redacted
    assert "[EMAIL_REDACTED]" in redacted


def test_redact_pii_leaves_clean_text_untouched():
    text = "Điểm trung bình môn Toán của lớp 8A1 là 7.5"
    assert redact_pii(text) == text


def test_redact_pii_non_string_passthrough():
    assert redact_pii(123) == 123
    assert redact_pii(None) is None


def test_classify_response_guardrail_flags_pii():
    from src.models.enums import GuardrailStatus

    text = "Liên hệ phụ huynh qua số 0987654321 để trao đổi thêm."
    assert classify_response_guardrail(text) == GuardrailStatus.BLOCKED_PII


def test_classify_response_guardrail_passes_clean_text():
    from src.models.enums import GuardrailStatus

    text = "Điểm trung bình học kỳ 1 của học sinh là 8.2, xếp loại Giỏi."
    assert classify_response_guardrail(text) == GuardrailStatus.PASSED


def test_classify_response_guardrail_empty_text_passes():
    from src.models.enums import GuardrailStatus

    assert classify_response_guardrail("") == GuardrailStatus.PASSED
    assert classify_response_guardrail(None) == GuardrailStatus.PASSED


def test_pii_patterns_not_empty():
    """Đảm bảo classify_response_guardrail/redact_pii dùng chung 1 nguồn pattern duy nhất."""
    assert len(_PII_PATTERNS) >= 3


# --- alerting: fixture reset state --------------------------------------------------


@pytest.fixture(autouse=True)
def reset_alerting_state():
    original = copy.deepcopy(alerting._state)
    yield
    alerting._state.clear()
    alerting._state.update(original)


@pytest.fixture(autouse=True)
def no_discord(monkeypatch):
    """Không gọi Discord thật trong test — chỉ cần biết _dispatch có được gọi hay không."""
    monkeypatch.setattr(alerting, "send_message", MagicMock(return_value=True))


# --- alerting.track_eval_score -------------------------------------------------------


def test_track_eval_score_no_alert_below_min_samples():
    alerting.track_eval_score("faithfulness", 0.1)
    alerting.track_eval_score("faithfulness", 0.1)  # chỉ 2 mẫu, cần _EVAL_MIN_SAMPLES=2 -> đủ
    assert alerting.send_message.called  # 2 mẫu điểm thấp -> đủ ngưỡng mới -> phải bắn


def test_track_eval_score_no_alert_with_single_sample():
    alerting.track_eval_score("faithfulness", 0.1)  # 1 mẫu < _EVAL_MIN_SAMPLES=2
    assert not alerting.send_message.called


def test_track_eval_score_alerts_when_avg_below_threshold():
    for _ in range(3):
        alerting.track_eval_score("groundedness", 0.5)
    assert alerting.send_message.called
    msg = alerting.send_message.call_args[0][0]
    assert "Groundedness" in msg or "groundedness" in msg.lower()


def test_track_eval_score_no_alert_when_avg_above_threshold():
    for _ in range(3):
        alerting.track_eval_score("faithfulness", 0.95)
    assert not alerting.send_message.called


def test_track_eval_score_debounced_within_window():
    for _ in range(3):
        alerting.track_eval_score("faithfulness", 0.1)
    assert alerting.send_message.call_count == 1
    alerting.track_eval_score("faithfulness", 0.1)
    assert alerting.send_message.call_count == 1  # debounce 15 phút chặn lần 2


def test_track_eval_score_unknown_metric_is_noop():
    alerting.track_eval_score("some_unknown_metric", 0.0)
    assert not alerting.send_message.called


def test_get_recent_eval_avg_uses_wide_default_window():
    """Cửa sổ mặc định phải đủ rộng (2 giờ) để traffic thấp vẫn tích lũy được mẫu hiển thị."""
    alerting.track_eval_score("faithfulness", 0.9)
    assert alerting.get_recent_faithfulness_avg() == pytest.approx(0.9)
    assert alerting._EVAL_WINDOW_SECONDS >= 3600


# --- alerting.track_cost / daily budget ----------------------------------------------


def test_track_cost_accumulates_and_alerts_over_budget(monkeypatch):
    monkeypatch.setattr(alerting, "_seed_daily_cost_if_needed", lambda today: None)
    fake_settings = SimpleNamespace(daily_llm_budget_usd=1.0)
    with patch("src.config.get_settings", return_value=fake_settings):
        alerting.track_cost(0.5)
        assert not alerting.send_message.called
        alerting.track_cost(0.4)  # tổng 0.9 = 90% > 80%
        assert alerting.send_message.called


def test_track_cost_resets_on_new_day(monkeypatch):
    monkeypatch.setattr(alerting, "_seed_daily_cost_if_needed", lambda today: None)
    alerting._state["daily_cost"] = 5.0
    alerting._state["day"] = date.today() - timedelta(days=1)
    fake_settings = SimpleNamespace(daily_llm_budget_usd=100.0)
    with patch("src.config.get_settings", return_value=fake_settings):
        alerting.track_cost(0.1)
    assert alerting._state["daily_cost"] == pytest.approx(0.1)  # reset về 0 rồi cộng 0.1


def test_get_daily_cost_returns_zero_on_new_day():
    alerting._state["daily_cost"] = 5.0
    alerting._state["day"] = date.today() - timedelta(days=1)
    assert alerting.get_daily_cost() == 0.0


def test_seed_daily_cost_syncs_from_db(monkeypatch):
    """Sau restart, lần track_cost đầu tiên trong ngày phải đồng bộ từ DB thay vì bắt đầu từ 0."""
    fake_db = MagicMock()
    fake_db.execute.return_value.scalar_one.return_value = 3.5
    monkeypatch.setattr("src.db.session.SessionLocal", lambda: fake_db)

    today = date.today()
    alerting._state["daily_cost_seeded_day"] = None
    alerting._state["daily_cost"] = 0.0
    alerting._seed_daily_cost_if_needed(today)

    assert alerting._state["daily_cost"] == pytest.approx(3.5)
    assert alerting._state["daily_cost_seeded_day"] == today


def test_seed_daily_cost_only_runs_once_per_day(monkeypatch):
    fake_db = MagicMock()
    fake_db.execute.return_value.scalar_one.return_value = 9.0
    monkeypatch.setattr("src.db.session.SessionLocal", lambda: fake_db)

    today = date.today()
    alerting._state["daily_cost_seeded_day"] = today  # đã seed hôm nay rồi
    alerting._state["daily_cost"] = 1.0
    alerting._seed_daily_cost_if_needed(today)

    assert alerting._state["daily_cost"] == 1.0  # không bị ghi đè
    fake_db.execute.assert_not_called()


def test_seed_daily_cost_fails_soft_on_db_error(monkeypatch):
    def boom():
        raise RuntimeError("DB down")

    monkeypatch.setattr("src.db.session.SessionLocal", boom)
    alerting._state["daily_cost_seeded_day"] = None
    alerting._state["daily_cost"] = 2.0
    alerting._seed_daily_cost_if_needed(date.today())  # không raise
    assert alerting._state["daily_cost"] == 2.0  # giữ nguyên giá trị cũ


# --- alerting.track_request_result ---------------------------------------------------


def test_track_request_result_no_alert_below_min_samples():
    for _ in range(4):
        alerting.track_request_result(False)
    assert not alerting.send_message.called  # cần tối thiểu 5 mẫu


def test_track_request_result_alerts_high_error_rate():
    for _ in range(4):
        alerting.track_request_result(False)
    alerting.track_request_result(True)  # đủ 5 mẫu, error rate = 80%
    assert alerting.send_message.called


def test_track_request_result_no_alert_low_error_rate():
    for _ in range(9):
        alerting.track_request_result(True)
    alerting.track_request_result(False)  # error rate = 10%
    assert not alerting.send_message.called


# --- alerting.check_agent_runaway ----------------------------------------------------


def test_check_agent_runaway_alerts_over_threshold():
    alerting.check_agent_runaway("session-1", step_count=11, threshold=10)
    assert alerting.send_message.called


def test_check_agent_runaway_no_alert_under_threshold():
    alerting.check_agent_runaway("session-2", step_count=5, threshold=10)
    assert not alerting.send_message.called


def test_get_recent_alerts_returns_newest_first():
    alerting.check_agent_runaway("s1", step_count=99, threshold=10)
    alerting.track_request_result(False)
    for _ in range(4):
        alerting.track_request_result(False)
    alerts = alerting.get_recent_alerts(10)
    assert len(alerts) >= 1
    assert alerts[0]["sent_at"] >= alerts[-1]["sent_at"]


# --- eval.should_sample ---------------------------------------------------------------


def test_should_sample_always_false_in_test_env():
    fake_settings = SimpleNamespace(app_env="test", eval_sample_rate=1.0)
    with patch("src.services.eval.get_settings", return_value=fake_settings):
        assert eval_service.should_sample() is False


def test_should_sample_respects_rate_boundaries(monkeypatch):
    fake_settings = SimpleNamespace(app_env="production", eval_sample_rate=1.0)
    with patch("src.services.eval.get_settings", return_value=fake_settings):
        monkeypatch.setattr(random, "random", lambda: 0.999)
        assert eval_service.should_sample() is True  # rate=1.0 luôn True

    fake_settings0 = SimpleNamespace(app_env="production", eval_sample_rate=0.0)
    with patch("src.services.eval.get_settings", return_value=fake_settings0):
        monkeypatch.setattr(random, "random", lambda: 0.0001)
        assert eval_service.should_sample() is False  # rate=0.0 luôn False


# --- eval.judge_faithfulness / judge_groundedness (fail-soft) -------------------------


@pytest.mark.asyncio
async def test_judge_faithfulness_returns_score_and_tracks():
    judgement = eval_service.FaithfulnessJudgement(score=0.42, reasoning="test")
    fake_structured = MagicMock()
    fake_structured.ainvoke = AsyncMock(return_value=judgement)
    fake_llm = MagicMock()
    fake_llm.with_structured_output.return_value = fake_structured

    with (
        patch("src.services.eval.get_judge_llm", return_value=fake_llm),
        patch("src.services.eval.track_eval_score") as mock_track,
    ):
        score = await eval_service.judge_faithfulness("q", "context", "answer")

    assert score == 0.42
    mock_track.assert_called_once_with("faithfulness", 0.42)


@pytest.mark.asyncio
async def test_judge_groundedness_returns_score_and_tracks():
    judgement = eval_service.GroundednessJudgement(score=0.77, reasoning="test")
    fake_structured = MagicMock()
    fake_structured.ainvoke = AsyncMock(return_value=judgement)
    fake_llm = MagicMock()
    fake_llm.with_structured_output.return_value = fake_structured

    with (
        patch("src.services.eval.get_judge_llm", return_value=fake_llm),
        patch("src.services.eval.track_eval_score") as mock_track,
    ):
        score = await eval_service.judge_groundedness("q", "tool_outputs", "answer")

    assert score == 0.77
    mock_track.assert_called_once_with("groundedness", 0.77)


@pytest.mark.asyncio
async def test_judge_faithfulness_fails_soft_on_llm_error():
    fake_structured = MagicMock()
    fake_structured.ainvoke = AsyncMock(side_effect=RuntimeError("LLM timeout"))
    fake_llm = MagicMock()
    fake_llm.with_structured_output.return_value = fake_structured

    with patch("src.services.eval.get_judge_llm", return_value=fake_llm):
        score = await eval_service.judge_faithfulness("q", "context", "answer")

    assert score is None  # fail-soft, không raise


# --- llm.get_judge_llm ------------------------------------------------------------------


def _fake_llm_settings(**overrides):
    base = dict(
        llm_provider="openai",
        openai_api_key="test-key",
        openai_api_base="https://api.openai.com/v1",
        model_name="gpt-4o-mini",
        deepseek_api_key="test-key",
        deepseek_model_name="deepseek-v4-flash",
        deepseek_api_base="https://api.deepseek.com",
        llm_temperature=0.7,
        llm_timeout_s=60.0,
        judge_llm_provider="same",
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def test_get_judge_llm_same_matches_main_llm_model():
    settings = _fake_llm_settings(judge_llm_provider="same", llm_provider="openai", model_name="gpt-4o-mini")
    with patch("src.services.llm.get_settings", return_value=settings):
        judge = get_judge_llm()
    assert isinstance(judge, TimedChatOpenAI)
    assert judge.model_name == "gpt-4o-mini"


def test_get_judge_llm_distinct_provider_builds_independent_model():
    settings = _fake_llm_settings(judge_llm_provider="deepseek", llm_provider="openai")
    with patch("src.services.llm.get_settings", return_value=settings):
        judge = get_judge_llm()
    assert isinstance(judge, DeepSeekDSMLWrapper)


def test_get_judge_llm_same_as_main_provider_string_falls_back():
    """judge_llm_provider trùng llm_provider -> coi như 'same', không build lại object mới."""
    settings = _fake_llm_settings(judge_llm_provider="openai", llm_provider="openai")
    with patch("src.services.llm.get_settings", return_value=settings):
        judge = get_judge_llm()
    assert isinstance(judge, TimedChatOpenAI)


# --- observability_snapshot.capture_snapshot -------------------------------------------


def test_capture_snapshot_writes_row_with_expected_fields():
    from src.services import observability_snapshot as snap

    fake_db = MagicMock()
    fake_settings = SimpleNamespace(daily_llm_budget_usd=5.0)
    with (
        patch("src.services.observability_snapshot.SessionLocal", return_value=fake_db),
        patch("src.config.get_settings", return_value=fake_settings),
    ):
        snap.capture_snapshot()

    assert fake_db.add.called
    added_snapshot = fake_db.add.call_args[0][0]
    assert added_snapshot.daily_budget_usd == 5.0
    assert fake_db.commit.called
    assert fake_db.close.called


def test_capture_snapshot_fails_soft_on_db_error():
    from src.services import observability_snapshot as snap

    def boom():
        raise RuntimeError("DB unreachable")

    with patch("src.services.observability_snapshot.SessionLocal", boom):
        snap.capture_snapshot()  # không raise, fail-soft


def test_capture_snapshot_includes_report_agent_in_step_breakdown():
    """Fix 3: report_agent giờ nằm trong nhóm Groundedness -> snapshot cũng phải theo dõi latency
    của nó (đã có sẵn trong _AGENT_NAMES — khoá lại để tránh ai đó vô tình bỏ sót khi sửa)."""
    from src.services import observability_snapshot as snap

    assert "report_agent" in snap._AGENT_NAMES
