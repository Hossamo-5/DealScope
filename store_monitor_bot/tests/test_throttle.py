"""
Tests for bot throttle middleware.
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock
from bot.middleware.throttle import ThrottleMiddleware


@pytest.fixture
def throttle():
    return ThrottleMiddleware(rate_limit=3, window_seconds=10)


def _make_message(user_id: int):
    msg = MagicMock(spec=[])  # Empty spec — no auto-attributes
    msg.from_user = MagicMock()
    msg.from_user.id = user_id
    return msg


def _make_callback(user_id: int):
    cb = MagicMock(spec=[])
    cb.from_user = MagicMock()
    cb.from_user.id = user_id
    cb.answer = AsyncMock()
    return cb


@pytest.mark.asyncio
async def test_allows_under_limit(throttle):
    handler = AsyncMock(return_value="ok")
    msg = _make_message(111)

    result = await throttle(handler, msg, {})
    assert result == "ok"
    handler.assert_called_once()


@pytest.mark.asyncio
async def test_blocks_over_limit(throttle):
    handler = AsyncMock(return_value="ok")
    msg = _make_message(222)

    # 3 allowed
    for _ in range(3):
        await throttle(handler, msg, {})

    # 4th should be blocked
    result = await throttle(handler, msg, {})
    assert result is None
    assert handler.call_count == 3


@pytest.mark.asyncio
async def test_different_users_independent(throttle):
    handler = AsyncMock(return_value="ok")
    msg1 = _make_message(333)
    msg2 = _make_message(444)

    for _ in range(3):
        await throttle(handler, msg1, {})

    # User 444 should still be allowed
    result = await throttle(handler, msg2, {})
    assert result == "ok"


@pytest.mark.asyncio
async def test_callback_query_throttled_shows_message(throttle):
    handler = AsyncMock(return_value="ok")
    cb = _make_callback(555)

    for _ in range(3):
        await throttle(handler, cb, {})

    # 4th triggers throttle answer
    await throttle(handler, cb, {})
    cb.answer.assert_called_once()
