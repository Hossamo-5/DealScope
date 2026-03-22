import asyncio
import logging
import threading
import json
from aiogram import Bot, Dispatcher, BaseMiddleware
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import TelegramObject
from typing import Callable, Dict, Any, Awaitable
from redis.asyncio import Redis as AsyncRedis

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def run_dashboard_in_thread(bot_instance, sf, host, port):
    """
    Run FastAPI/uvicorn dashboard in a SEPARATE THREAD with its own
    event loop. This avoids asyncio signal-handler conflicts with aiogram.
    """
    import uvicorn
    from admin.dashboard import app as dashboard_app

    dashboard_app.state.bot = bot_instance
    dashboard_app.state.session_factory = sf

    config = uvicorn.Config(
        dashboard_app,
        host=host,
        port=port,
        log_level="warning",
        loop="asyncio",
    )
    server = uvicorn.Server(config)

    # Each thread needs its own event loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(server.serve())
    except Exception as e:
        logger.error(f"Dashboard thread error: {e}")
    finally:
        loop.close()


async def main():
    from config.settings import (
        TELEGRAM_BOT_TOKEN, DATABASE_URL, REDIS_URL,
        ADMIN_GROUP_ID, DASHBOARD_HOST, DASHBOARD_PORT,
    )

    # ── Validate token ────────────────────────
    if TELEGRAM_BOT_TOKEN in ["PUT_YOUR_BOT_TOKEN_HERE", "", None]:
        logger.error("❌ TELEGRAM_BOT_TOKEN not set in .env!")
        return

    logger.info("🚀 Starting DealScope...")

    # ── Create Bot ────────────────────────────
    bot = Bot(token=TELEGRAM_BOT_TOKEN)

    # Register bot in registry for dashboard use
    from utils.bot_registry import set_bot
    set_bot(bot)

    # Clear any existing webhooks before polling
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("✅ Webhooks cleared")
    except Exception as e:
        logger.warning(f"Webhook clear: {e}")

    await asyncio.sleep(2)

    # ── FSM Storage ───────────────────────────
    try:
        from aiogram.fsm.storage.redis import RedisStorage
        storage = RedisStorage.from_url(REDIS_URL)
        logger.info("✅ Redis storage connected")
    except Exception as e:
        logger.warning(f"⚠️ Redis unavailable ({e}), using MemoryStorage")
        storage = MemoryStorage()

    dp = Dispatcher(storage=storage)

    # ── Database ──────────────────────────────
    from db.models import get_engine, create_tables, get_session_factory
    engine = get_engine(DATABASE_URL)
    await create_tables(engine)
    session_factory = get_session_factory(engine)
    logger.info("✅ Database ready")

    # ── Connectors ────────────────────────────
    from core.connectors.generic import ConnectorManager
    connector_manager = ConnectorManager()

    # ── START DASHBOARD IN SEPARATE THREAD ────
    display_host = "localhost" if str(DASHBOARD_HOST) in ("0.0.0.0", "::") else DASHBOARD_HOST
    dashboard_thread = threading.Thread(
        target=run_dashboard_in_thread,
        args=(bot, session_factory, DASHBOARD_HOST, DASHBOARD_PORT),
        daemon=True,
        name="dashboard-thread",
    )
    dashboard_thread.start()
    logger.info(f"✅ Dashboard started → http://{display_host}:{DASHBOARD_PORT}")

    # Give dashboard a moment to bind
    await asyncio.sleep(2)

    # ── Middleware ────────────────────────────

    class DatabaseMiddleware(BaseMiddleware):
        def __init__(self, sf, cm):
            self.session_factory = sf
            self.connector_manager = cm

        async def __call__(
            self,
            handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
            event: TelegramObject,
            data: Dict[str, Any],
        ) -> Any:
            async with self.session_factory() as session:
                data["session"] = session
                data["connector_manager"] = self.connector_manager
                return await handler(event, data)

    class ExceptionMiddleware(BaseMiddleware):
        async def __call__(self, handler, event, data):
            try:
                return await handler(event, data)
            except Exception as exc:
                logger.error("Handler error: %s", exc, exc_info=True)
                try:
                    if hasattr(event, "message") and event.message is not None:
                        await event.message.answer("❌ حدث خطأ مؤقت. حاول مرة أخرى.")
                    elif hasattr(event, "answer"):
                        await event.answer("❌ حدث خطأ مؤقت. حاول مرة أخرى.")
                except Exception:
                    pass

    dp.message.middleware(ExceptionMiddleware())
    dp.callback_query.middleware(ExceptionMiddleware())

    # Activity tracker
    try:
        from bot.middleware.activity_tracker import ActivityTrackerMiddleware
        activity_mw = ActivityTrackerMiddleware(session_factory)
        dp.message.middleware(activity_mw)
        dp.callback_query.middleware(activity_mw)
        logger.info("✅ Activity tracker registered")
    except Exception as e:
        logger.warning(f"⚠️ Activity tracker skipped: {e}")

    # Throttle
    try:
        from bot.middleware.throttle import ThrottleMiddleware
        throttle_mw = ThrottleMiddleware()
        dp.message.middleware(throttle_mw)
        logger.info("✅ Throttle middleware registered")
    except Exception as e:
        logger.warning(f"⚠️ Throttle skipped: {e}")

    # DB middleware LAST
    db_mw = DatabaseMiddleware(session_factory, connector_manager)
    dp.message.middleware(db_mw)
    dp.callback_query.middleware(db_mw)

    # ── Register Routers ──────────────────────
    from bot.handlers.admin import router as admin_router
    from bot.handlers.user import router as user_router
    from bot.handlers.user2 import router as user2_router

    dp.include_router(admin_router)   # Admin FIRST
    dp.include_router(user_router)
    dp.include_router(user2_router)
    logger.info("✅ All handlers registered")

    # ── Monitoring Engine ─────────────────────
    from core.monitor import MonitoringEngine
    monitoring = MonitoringEngine(session_factory, bot, connector_manager)
    monitoring_task = asyncio.create_task(monitoring.start())
    logger.info("✅ Monitoring engine started")

    # ── Redis pubsub (admin notifications & user alerts) ──
    async def _redis_pubsub_listener():
        try:
            redis = AsyncRedis.from_url(REDIS_URL)
            pubsub = redis.pubsub()
            await pubsub.subscribe("admin:notifications", "user:alerts")
            logger.info("Subscribed to Redis notification channels")
            async for message in pubsub.listen():
                try:
                    if not message or message.get("type") != "message":
                        continue
                    channel = message.get("channel")
                    data = message.get("data")
                    if isinstance(channel, bytes):
                        channel = channel.decode()
                    if isinstance(data, (bytes, bytearray)):
                        data = data.decode()
                    payload = json.loads(data)

                    if channel == "admin:notifications":
                        text = f"{payload.get('title', '')}\n\n{payload.get('message', '')}"
                        try:
                            await bot.send_message(ADMIN_GROUP_ID, text)
                        except Exception:
                            logger.exception("Failed to send admin notification")

                    elif channel == "user:alerts":
                        telegram_id = payload.get("telegram_id")
                        message_text = payload.get("message")
                        if telegram_id and message_text:
                            try:
                                await bot.send_message(telegram_id, message_text, parse_mode="Markdown")
                            except Exception:
                                logger.exception("Failed to send user alert to %s", telegram_id)
                except Exception:
                    logger.exception("Error processing pubsub message")
        except Exception:
            logger.exception("Redis pubsub listener failed to start")

    try:
        asyncio.create_task(_redis_pubsub_listener())
    except Exception:
        logger.exception("Failed to start Redis pubsub listener task")

    # ── Start Bot ─────────────────────────────
    logger.info("=" * 50)
    logger.info("🤖 Bot is RUNNING!")
    logger.info(f"📊 Dashboard: http://{display_host}:{DASHBOARD_PORT}")
    logger.info("Press Ctrl+C to stop")
    logger.info("=" * 50)

    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    except asyncio.CancelledError:
        logger.info("⏹ Stopping bot...")
    except Exception as e:
        if "Conflict" in str(e):
            logger.error(
                "\n❌ CONFLICT: Another bot instance is running!\n"
                "Run start_bot.bat to stop all instances and restart.\n"
            )
        else:
            logger.error(f"Bot error: {e}")
    finally:
        logger.info("Shutting down...")
        monitoring_task.cancel()
        try:
            await bot.session.close()
        except Exception:
            pass
        await engine.dispose()
        logger.info("✅ Shutdown complete")


if __name__ == "__main__":
    asyncio.run(main())
