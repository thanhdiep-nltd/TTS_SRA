"""Callback cảnh báo Slack (#data-alerts) khi task thất bại sau khi hết retry."""

_CONN_ID = "slack_alerts"


def slack_on_failure(context: dict) -> None:
    """on_failure_callback cho Airflow: bắn log lỗi task vào Slack.

    Nhấn mạnh các task gọi API ngoài (DeepSeek/OpenAI) khi timeout/HTTP 429.
    """
    from airflow.providers.slack.hooks.slack_webhook import SlackWebhookHook

    task_instance = context.get("task_instance")
    dag_id = getattr(task_instance, "dag_id", "?")
    task_id = getattr(task_instance, "task_id", "?")
    exception = context.get("exception")
    log_url = getattr(task_instance, "log_url", "")

    message = (
        f":red_circle: *Pipeline lỗi*\n"
        f"*DAG:* `{dag_id}`\n*Task:* `{task_id}`\n"
        f"*Lỗi:* {exception}\n<{log_url}|Xem log>"
    )
    # Không để lỗi gửi Slack (webhook sai/không cấu hình) làm hỏng callback.
    try:
        SlackWebhookHook(slack_webhook_conn_id=_CONN_ID).send(text=message)
    except Exception:  # noqa: BLE001 — cảnh báo chỉ là phụ trợ
        pass
