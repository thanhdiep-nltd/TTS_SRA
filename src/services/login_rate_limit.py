"""Rate-limit đăng nhập theo email (in-process, không cần Redis — backend chạy 1 instance,
xem services/alerting.py cho cùng kiểu state trong process).

Khóa tài khoản tạm thời sau `_MAX_ATTEMPTS` lần sai mật khẩu liên tiếp trong `_WINDOW_SECONDS`,
chống brute-force/dò mật khẩu. Reset ngay khi đăng nhập đúng.
"""

import time
from collections import defaultdict

_MAX_ATTEMPTS = 5
_WINDOW_SECONDS = 900  # 15 phút

_failed_attempts: dict[str, list[float]] = defaultdict(list)


def _recent_attempts(key: str) -> list[float]:
    now = time.time()
    attempts = [t for t in _failed_attempts.get(key, []) if now - t <= _WINDOW_SECONDS]
    _failed_attempts[key] = attempts
    return attempts


def is_locked(key: str) -> bool:
    """True nếu key (email) đã sai đủ `_MAX_ATTEMPTS` lần trong cửa sổ hiện tại."""
    return len(_recent_attempts(key)) >= _MAX_ATTEMPTS


def register_failure(key: str) -> None:
    """Ghi nhận 1 lần đăng nhập sai cho key."""
    attempts = _recent_attempts(key)
    attempts.append(time.time())
    _failed_attempts[key] = attempts


def reset(key: str) -> None:
    """Xóa lịch sử sai của key khi đăng nhập thành công."""
    _failed_attempts.pop(key, None)
