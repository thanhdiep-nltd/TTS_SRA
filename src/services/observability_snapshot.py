"""Snapshot định kỳ cho trend chart "Tình trạng hệ thống AI" (Giai đoạn A).

Đọc trực tiếp Prometheus REGISTRY trong process (không cần Prometheus server riêng) +
alerting._state, ghi 1 row vào `ai_observability_snapshots` mỗi N phút. Mục đích: có lịch sử
xu hướng trong app mà không phụ thuộc Grafana (vốn chỉ giữ dữ liệu khi container còn sống).
"""

import asyncio

from src.db import SessionLocal
from src.models.tables import AiObservabilitySnapshot
from src.observability import (
    agent_latency_seconds,
    agent_requests_total,
    agent_routes_total,
    agent_step_seconds,
    agent_tokens_total,
    agent_ttft_seconds,
    breakdown_counter,
    histogram_quantile,
    logger,
    sum_counter,
    tool_calls_total,
)
from src.services.alerting import get_daily_cost, get_recent_eval_avg

_AGENT_NAMES = ["supervisor", "data_agent", "stat_agent", "sql_agent", "knowledge_agent", "report_agent"]


def capture_snapshot() -> None:
    """Tính toán + ghi 1 row snapshot. Fail-soft: lỗi chỉ log warning, không raise."""
    try:
        from src.config import get_settings

        settings = get_settings()

        p95_latency = histogram_quantile(agent_latency_seconds, 0.95, {"feature": "chat"})
        p95_ttft = histogram_quantile(agent_ttft_seconds, 0.95, {"feature": "chat"})

        success = sum_counter(tool_calls_total, {"status": "success"})
        error = sum_counter(tool_calls_total, {"status": "error"})
        total_tool_calls = success + error
        tool_success_rate = (success / total_tool_calls) if total_tool_calls > 0 else None

        agent_routes = {k: int(v) for k, v in breakdown_counter(agent_routes_total, "target_agent").items()}
        agent_step_p95_ms = {}
        for agent_name in _AGENT_NAMES:
            p95 = histogram_quantile(agent_step_seconds, 0.95, {"agent_name": agent_name})
            agent_step_p95_ms[agent_name] = round(p95 * 1000, 1) if p95 is not None else None

        snapshot = AiObservabilitySnapshot(
            daily_cost_usd=get_daily_cost(),
            daily_budget_usd=settings.daily_llm_budget_usd,
            latency_p95_ms=int(p95_latency * 1000) if p95_latency is not None else None,
            ttft_p95_ms=int(p95_ttft * 1000) if p95_ttft is not None else None,
            faithfulness_avg=get_recent_eval_avg("faithfulness"),
            groundedness_avg=get_recent_eval_avg("groundedness"),
            tool_success_rate=tool_success_rate,
            total_requests=int(sum_counter(agent_requests_total)),
            total_tokens_in=int(sum_counter(agent_tokens_total, {"direction": "input"})),
            total_tokens_out=int(sum_counter(agent_tokens_total, {"direction": "output"})),
            agent_routes=agent_routes,
            agent_step_p95_ms=agent_step_p95_ms,
        )
        db = SessionLocal()
        try:
            db.add(snapshot)
            db.commit()
            logger.info(
                "observability_snapshot_captured",
                latency_p95_ms=snapshot.latency_p95_ms,
                daily_cost_usd=float(snapshot.daily_cost_usd),
                tool_success_rate=tool_success_rate,
            )
        finally:
            db.close()
    except Exception as exc:
        logger.warning("observability_snapshot_failed", error=str(exc))


async def run_snapshot_loop(interval_seconds: int = 1800) -> None:
    """Loop nền: chụp snapshot ngay khi khởi động, sau đó lặp lại mỗi `interval_seconds`."""
    while True:
        capture_snapshot()
        try:
            await asyncio.sleep(interval_seconds)
        except asyncio.CancelledError:
            break
