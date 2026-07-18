"""Client gửi tin cảnh báo qua Discord Webhook.

Thay Zalo (OAuth quá phức tạp: access_token ngắn hạn, refresh_token rotate) và Telegram
(bị chặn ở VN). Discord webhook không cần OAuth — chỉ cần 1 URL tĩnh tạo sẵn trong
Server Settings → Integrations → Webhooks, dùng được vĩnh viễn cho tới khi bị xoá.
"""

import httpx

from src.config import get_settings
from src.observability import logger


def send_message(text: str) -> bool:
    """Gửi tin nhắn tới Discord webhook. Fail-soft: trả False nếu chưa cấu hình hoặc lỗi mạng."""
    settings = get_settings()
    if not settings.discord_webhook_url:
        logger.info("discord_alert_skipped_no_config", message=text)
        return False

    try:
        resp = httpx.post(settings.discord_webhook_url, json={"content": text}, timeout=10)
        resp.raise_for_status()
        return True
    except httpx.HTTPError as exc:
        logger.warning("discord_send_failed", error=str(exc))
        return False
