"""
Bot Throttle Middleware
=======================
Per-user rate limiting for Telegram bot handlers.
Prevents spam and abuse of scrape-triggering commands.
"""

import time
import logging
from collections import defaultdict
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery

logger = logging.getLogger(__name__)

# Default: max 5 actions per 30-second window per user
DEFAULT_RATE_LIMIT = 5
DEFAULT_WINDOW_SECONDS = 30


class ThrottleMiddleware(BaseMiddleware):
    """
    Simple per-user rate limiter.
    Silently drops requests that exceed the threshold.
    """

    def __init__(
        self,
        rate_limit: int = DEFAULT_RATE_LIMIT,
        window_seconds: int = DEFAULT_WINDOW_SECONDS,
    ):
        self.rate_limit = rate_limit
        self.window_seconds = window_seconds
        self._user_timestamps: dict[int, list[float]] = defaultdict(list)

    def _is_throttled(self, user_id: int) -> bool:
        now = time.monotonic()
        timestamps = self._user_timestamps[user_id]
        # Prune old entries
        self._user_timestamps[user_id] = [
            t for t in timestamps if now - t < self.window_seconds
        ]
        if len(self._user_timestamps[user_id]) >= self.rate_limit:
            return True
        self._user_timestamps[user_id].append(now)
        return False

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        user_id: int | None = None
        if hasattr(event, "from_user") and event.from_user:
            user_id = event.from_user.id

        if user_id is not None and self._is_throttled(user_id):
            logger.warning("Throttled user %s", user_id)
            # Silently drop — do not call the handler
            if isinstance(event, CallbackQuery) or hasattr(event, "answer"):
                try:
                    await event.answer("⏳ الرجاء الانتظار قليلاً...", show_alert=False)
                except Exception:
                    pass
            return None

        return await handler(event, data)
