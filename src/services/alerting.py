"""Smart Alerting nhẹ (Giai đoạn 4): bắn cảnh báo qua Discord Webhook, KHÔNG qua Alertmanager.

Dùng Discord webhook thay Telegram (bị chặn ở VN) và Zalo (OAuth quá phức tạp cho MVP) —
xem src/services/discord_client.py.

Các kịch bản theo docs/observability_design.md §4.1 (+ mở rộng), đo trực tiếp trong process
(không cần Prometheus query API vì backend chạy 1 instance):
1. Budget Warning: chi phí LLM trong ngày vượt 80% `daily_llm_budget_usd`.
2. Quality Degradation: điểm Faithfulness (RAG) hoặc Groundedness (data/stat/sql/report_agent)
   trung bình `_EVAL_WINDOW_SECONDS` qua < 0.80.
3. Agent Runaway: 1 session Supervisor định tuyến quá N bước mà chưa FINISH.
4. Error Rate High: tỷ lệ request lỗi 15 phút qua > 20%.

Mỗi loại cảnh báo có debounce 15 phút để tránh spam khi ngưỡng bị vượt liên tục.
"""

import time
from datetime import UTC, date, datetime

from src.services.discord_client import send_message

_DEBOUNCE_SECONDS = 900  # 15 phút
_ALERT_HISTORY_MAX = 50  # ring buffer — đủ cho UI hiển thị, không phình bộ nhớ vô hạn

# Cửa sổ + số mẫu tối thiểu cho eval degradation. Với eval_sample_rate mặc định 5% và traffic
# thấp (trường học, không phải SaaS đại trà), cửa sổ 15 phút + tối thiểu 3 mẫu gần như không
# bao giờ đạt được (cần ~60 lượt chat/15 phút) -> cảnh báo hallucination bị "ngủ đông" quanh
# năm. Nới ra 2 giờ + tối thiểu 2 mẫu để có cơ hội thực tế tích lũy đủ mẫu mà vẫn đủ nhạy.
_EVAL_WINDOW_SECONDS = 7200  # 2 giờ
_EVAL_MIN_SAMPLES = 2
_EVAL_RETENTION_SECONDS = _EVAL_WINDOW_SECONDS + 1800  # giữ dư 30 phút để không cắt mẫu sát biên

_state = {
    "day": date.today(),
    "daily_cost": 0.0,
    "daily_cost_seeded_day": None,  # ngày đã đồng bộ daily_cost từ DB (xem `_seed_daily_cost_if_needed`)
    "eval_scores": {},  # dict[str, list[tuple[float, float]]] = metric_name -> [(timestamp, score), ...]
    "request_results": [],  # list[tuple[float, bool]] = (timestamp, success) — cửa sổ trượt cho error rate
    "last_alert": {},  # alert_key -> timestamp lần bắn gần nhất
    "alert_history": [],  # list[dict] = {type, message, sent_at} — mới nhất ở cuối
}

# Ngưỡng cảnh báo "suy thoái chất lượng" cho từng metric eval (avg _EVAL_WINDOW_SECONDS < threshold)
_EVAL_DEGRADATION_THRESHOLDS = {
    "faithfulness": 0.80,
    "groundedness": 0.80,
}
_EVAL_DEGRADATION_LABEL = {
    "faithfulness": "Faithfulness (knowledge_agent/RAG)",
    "groundedness": "Groundedness (data_agent/stat_agent/sql_agent/report_agent)",
}


def _should_alert(alert_key: str) -> bool:
    """Debounce 15 phút: chỉ cho bắn lại cùng 1 loại cảnh báo sau khi đã im lặng đủ lâu."""
    now = time.time()
    last = _state["last_alert"].get(alert_key, 0.0)
    if now - last < _DEBOUNCE_SECONDS:
        return False
    _state["last_alert"][alert_key] = now
    return True


def _dispatch(alert_type: str, message: str) -> None:
    """Ghi vào alert_history (để UI hiển thị) rồi gửi Discord. Ghi cả khi gửi lỗi/chưa cấu hình."""
    _state["alert_history"].append({"type": alert_type, "message": message, "sent_at": datetime.now(UTC).isoformat()})
    _state["alert_history"] = _state["alert_history"][-_ALERT_HISTORY_MAX:]
    send_message(message)


def get_recent_alerts(limit: int = 10) -> list[dict]:
    """Trả về tối đa `limit` cảnh báo gần nhất (mới nhất trước), cho UI 'Cảnh báo gần đây'."""
    return list(reversed(_state["alert_history"][-limit:]))


def _seed_daily_cost_if_needed(today: date) -> None:
    """Đồng bộ `_state["daily_cost"]` từ tổng cost thật trong DB — 1 lần/ngày/process.

    Bộ đếm in-process reset về 0 mỗi khi backend restart, trong khi DB vẫn giữ đúng tổng chi
    phí đã ghi nhận trong ngày -> nếu không đồng bộ, cảnh báo "vượt 80% ngân sách" có thể im
    lặng sau restart dù thực tế đã vượt từ trước (chi phí hiển thị trên dashboard vẫn đúng vì
    được tính thẳng từ DB, chỉ riêng NGƯỠNG CẢNH BÁO dựa vào bộ đếm in-process này là sai).
    """
    if _state.get("daily_cost_seeded_day") == today:
        return
    _state["daily_cost_seeded_day"] = today  # đánh dấu trước để tránh seed lặp nếu lỗi giữa chừng
    try:
        from datetime import time as time_cls

        from sqlalchemy import func, select

        from src.db.session import SessionLocal
        from src.models import enums
        from src.models.tables import AiMessage

        today_start = datetime.combine(today, time_cls.min, tzinfo=UTC)
        db = SessionLocal()
        try:
            total = db.execute(
                select(func.coalesce(func.sum(AiMessage.cost), 0)).where(
                    AiMessage.role == enums.AiSessionRole.assistant, AiMessage.created_at >= today_start
                )
            ).scalar_one()
            _state["daily_cost"] = max(_state["daily_cost"], float(total))
        finally:
            db.close()
    except Exception as exc:
        from src.observability import logger

        logger.warning("daily_cost_seed_failed", error=str(exc))


def track_cost(amount_usd: float) -> None:
    """Cộng dồn chi phí LLM trong ngày (reset khi qua ngày mới); bắn cảnh báo nếu vượt 80% ngân sách."""
    today = date.today()
    if _state["day"] != today:
        _state["day"] = today
        _state["daily_cost"] = 0.0
    _seed_daily_cost_if_needed(today)
    _state["daily_cost"] += amount_usd

    from src.config import get_settings

    budget = get_settings().daily_llm_budget_usd
    if _state["daily_cost"] >= 0.8 * budget and _should_alert("budget_warning"):
        pct = _state["daily_cost"] / budget * 100
        _dispatch(
            "budget_warning",
            f"⚠️ [CẢNH BÁO SỚM] Chi phí LLM hôm nay đã đạt {_state['daily_cost']:.4f} USD "
            f"({pct:.0f}% ngân sách ngày {budget} USD).",
        )


def track_eval_score(metric_name: str, score: float) -> None:
    """Theo dõi điểm eval gần đây cho 1 metric (faithfulness hoặc groundedness); bắn cảnh báo nếu
    điểm trung bình `_EVAL_WINDOW_SECONDS` qua tụt dưới ngưỡng suy thoái của metric đó."""
    threshold = _EVAL_DEGRADATION_THRESHOLDS.get(metric_name)
    if threshold is None:
        return

    now = time.time()
    scores = _state["eval_scores"].setdefault(metric_name, [])
    scores.append((now, score))
    _state["eval_scores"][metric_name] = [(t, s) for t, s in scores if now - t <= _EVAL_RETENTION_SECONDS]

    recent = [s for t, s in _state["eval_scores"][metric_name] if now - t <= _EVAL_WINDOW_SECONDS]
    if len(recent) < _EVAL_MIN_SAMPLES:
        return  # cần tối thiểu vài mẫu mới đủ tin cậy để chấm "suy thoái"

    avg_score = sum(recent) / len(recent)
    if avg_score < threshold and _should_alert(f"{metric_name}_degradation"):
        label = _EVAL_DEGRADATION_LABEL.get(metric_name, metric_name)
        window_min = _EVAL_WINDOW_SECONDS // 60
        _dispatch(
            f"{metric_name}_degradation",
            f"🚨 [NGUY HIỂM] Điểm {label} trung bình {window_min} phút qua = {avg_score:.2f} (< {threshold}). "
            f"Agent có khả năng đang sinh thông tin bịa đặt/sai lệch với dữ liệu nguồn (hallucination).",
        )


def get_daily_cost() -> float:
    """Chi phí LLM cộng dồn trong ngày hiện tại (dùng cho snapshot job)."""
    today = date.today()
    if _state["day"] != today:
        return 0.0
    return _state["daily_cost"]


def get_recent_eval_avg(metric_name: str, window_seconds: int = _EVAL_WINDOW_SECONDS) -> float | None:
    """Điểm eval trung bình của 1 metric (faithfulness/groundedness) trong `window_seconds` gần nhất,
    None nếu chưa có mẫu."""
    now = time.time()
    scores = _state["eval_scores"].get(metric_name, [])
    recent = [s for t, s in scores if now - t <= window_seconds]
    if not recent:
        return None
    return sum(recent) / len(recent)


def get_recent_faithfulness_avg(window_seconds: int = _EVAL_WINDOW_SECONDS) -> float | None:
    """Điểm Faithfulness trung bình trong `window_seconds` gần nhất, None nếu chưa có mẫu."""
    return get_recent_eval_avg("faithfulness", window_seconds)


def track_request_result(success: bool) -> None:
    """Theo dõi tỷ lệ lỗi 15 phút gần nhất; bắn cảnh báo nếu error rate > 20% (cần tối thiểu 5 mẫu).

    Tách riêng với `agent_requests_total` (Prometheus) vì không có Prometheus server scrape
    để query qua PromQL — cửa sổ trượt in-process này đủ cho cảnh báo real-time, tương tự
    cơ chế của `track_eval_score`.
    """
    now = time.time()
    results = _state["request_results"]
    results.append((now, success))
    _state["request_results"] = [(t, s) for t, s in results if now - t <= 900]

    recent = [s for t, s in _state["request_results"] if now - t <= 900]
    if len(recent) < 5:
        return  # cần tối thiểu vài mẫu mới đủ tin cậy để chấm "tỷ lệ lỗi cao"

    error_rate = 1 - (sum(recent) / len(recent))
    if error_rate > 0.20 and _should_alert("error_rate_high"):
        _dispatch(
            "error_rate_high",
            f"🚨 [NGUY HIỂM] Tỷ lệ lỗi Agent 15 phút qua = {error_rate * 100:.0f}% "
            f"({len(recent)} request gần nhất). Có thể đang gặp sự cố LLM provider/DB/tool.",
        )


def check_agent_runaway(session_id: str, step_count: int, threshold: int = 10) -> None:
    """Bắn cảnh báo nếu 1 session Supervisor định tuyến quá `threshold` bước mà chưa FINISH."""
    if step_count > threshold and _should_alert(f"runaway_{session_id}"):
        _dispatch(
            "agent_runaway",
            f"🚨 [NGUY HIỂM] Session {session_id} đã vượt quá {threshold} bước Supervisor "
            f"mà chưa hoàn tất. Có thể agent đang kẹt vòng lặp vô tận (LangGraph recursion_limit "
            f"sẽ tự ngắt nếu vượt giới hạn cấu hình).",
        )
