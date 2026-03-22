"""In-process registry for the active Telegram Bot instance."""

from __future__ import annotations

from typing import Any

_BOT_INSTANCE: Any = None


def set_bot(bot: Any) -> None:
    """Store the current bot instance for modules that need shared access."""
    global _BOT_INSTANCE
    _BOT_INSTANCE = bot


def get_bot() -> Any:
    """Return the previously stored bot instance, or None if not set."""
    return _BOT_INSTANCE
