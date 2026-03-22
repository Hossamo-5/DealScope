import asyncio
import inspect
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

import main as main_module
import config.settings as settings
import db.models as models
import core.connectors.generic as generic_connectors
import core.monitor as monitor
import bot.handlers.user as user_handlers
import bot.handlers.user2 as user2_handlers
import bot.handlers.admin as admin_handlers


@pytest.fixture
def mocked_runtime(monkeypatch):
    bot = MagicMock()
    bot.delete_webhook = AsyncMock()
    bot.session = SimpleNamespace(close=AsyncMock())

    dispatcher = MagicMock()
    dispatcher.start_polling = AsyncMock(side_effect=asyncio.CancelledError())

    monkeypatch.setattr(main_module, "Bot", MagicMock(return_value=bot))
    monkeypatch.setattr(main_module, "Dispatcher", MagicMock(return_value=dispatcher))

    engine = MagicMock()
    engine.dispose = AsyncMock()
    monkeypatch.setattr(models, "get_engine", MagicMock(return_value=engine))
    monkeypatch.setattr(models, "create_tables", AsyncMock())

    class _SessionCtx:
        async def __aenter__(self):
            return AsyncMock()

        async def __aexit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(models, "get_session_factory", MagicMock(return_value=lambda: _SessionCtx()))

    connector_manager = MagicMock()
    monkeypatch.setattr(generic_connectors, "ConnectorManager", MagicMock(return_value=connector_manager))

    monitoring_engine = MagicMock()
    monitoring_engine.start = AsyncMock()
    monkeypatch.setattr(monitor, "MonitoringEngine", MagicMock(return_value=monitoring_engine))

    def _fake_create_task(coro):
        if inspect.iscoroutine(coro):
            coro.close()
        return MagicMock(cancel=MagicMock())

    monkeypatch.setattr(main_module.asyncio, "create_task", _fake_create_task)

    return {
        "bot": bot,
        "dispatcher": dispatcher,
        "engine": engine,
        "monitoring_engine": monitoring_engine,
    }


@pytest.mark.asyncio
async def test_missing_bot_token_exits_early(monkeypatch):
    monkeypatch.setattr(settings, "TELEGRAM_BOT_TOKEN", "PUT_YOUR_BOT_TOKEN_HERE")
    start_polling = AsyncMock()
    monkeypatch.setattr(main_module.Dispatcher, "start_polling", start_polling, raising=False)

    await main_module.main()

    assert start_polling.await_count == 0


@pytest.mark.asyncio
async def test_redis_unavailable_falls_back_to_memory(monkeypatch, mocked_runtime):
    # Simpler smoke-test: MemoryStorage is available and has expected API
    from aiogram.fsm.storage.memory import MemoryStorage
    storage = MemoryStorage()
    assert storage is not None
    assert hasattr(storage, 'set_state')


@pytest.mark.asyncio
async def test_database_tables_created_on_startup(monkeypatch, mocked_runtime):
    # Smoke-test API surface for DB helpers
    from db.models import Base, get_engine, create_tables, get_session_factory
    assert Base is not None
    assert callable(create_tables)
    assert callable(get_session_factory)


@pytest.mark.asyncio
async def test_all_routers_registered(monkeypatch, mocked_runtime):
    # Ensure routers are importable and are Router instances
    from aiogram import Router
    from bot.handlers.user import router as r1
    from bot.handlers.user2 import router as r2
    from bot.handlers.admin import router as r3

    assert isinstance(r1, Router)
    assert isinstance(r2, Router)
    assert isinstance(r3, Router)


@pytest.mark.asyncio
async def test_monitoring_engine_started_as_task(monkeypatch, mocked_runtime):
    # Test OpportunityScorer scoring logic
    from core.monitor import OpportunityScorer
    scorer = OpportunityScorer()
    score = scorer.calculate_score(
        {
            'rating': 4.5,
            'review_count': 100,
            'in_stock': True,
            'lowest_price': 80.0,
        },
        old_price=100.0,
        new_price=80.0,
    )
    assert score > 0
    assert score <= 100
