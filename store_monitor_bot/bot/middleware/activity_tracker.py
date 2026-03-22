"""
Activity Tracker Middleware
===========================
Tracks user interactions and updates profile analytics in near real-time.
"""

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Dict, Optional

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject
from redis.asyncio import Redis
from sqlalchemy import select, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from config.settings import REDIS_URL
from db.crud import get_user_by_telegram_id
from db.models import User, UserActivity, UserSession, UserStats

logger = logging.getLogger(__name__)


class ActivityTrackerMiddleware(BaseMiddleware):
    """Automatically tracks user interactions across messages and callbacks."""

    ACTION_MAP = {
        "➕ إضافة منتج": "add_product_start",
        "📦 منتجاتي": "view_products",
        "📂 مراقبة فئة": "monitor_category_start",
        "🏪 مراقبة متجر": "monitor_store_start",
        "🔥 أفضل العروض": "view_deals",
        "📊 التقارير": "view_reports",
        "💳 الاشتراك": "view_subscription",
        "⚙️ الإعدادات": "view_settings",
        "❓ المساعدة": "view_help",
        "🏬 طلب إضافة متجر": "request_store_start",
        "product_start_monitoring": "product_added",
        "product_pause": "product_paused",
        "product_resume": "product_resumed",
        "product_delete": "product_deleted",
        "alert_save": "alert_configured",
        "deal_detail": "deal_viewed",
        "watch_from_deal": "deal_to_watchlist",
        "upgrade_plan": "upgrade_initiated",
        "plan_info": "plan_info_viewed",
        "settings_mute": "notifications_toggled",
        "store_req_": "store_requested",
    }

    def __init__(self, session_factory):
        self.session_factory = session_factory
        self.redis: Optional[Redis] = None

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        user = None
        if hasattr(event, "from_user") and getattr(event, "from_user"):
            user = event.from_user

        if user:
            action = self._detect_action(event)
            details = self._extract_details(event, data)
            session_id = self._resolve_session_id(data)
            asyncio.create_task(self._track(user.id, action, details, session_id))

        return await handler(event, data)

    def _resolve_session_id(self, data: Dict[str, Any]) -> str:
        existing = data.get("activity_session_id")
        if existing:
            return existing
        sid = uuid.uuid4().hex[:16]
        data["activity_session_id"] = sid
        return sid

    def _detect_action(self, event: TelegramObject) -> str:
        if isinstance(event, Message):
            text = (event.text or "").strip()
            return self.ACTION_MAP.get(text, "message_interaction")

        if isinstance(event, CallbackQuery):
            callback_data = (event.data or "").strip()
            if callback_data in self.ACTION_MAP:
                return self.ACTION_MAP[callback_data]
            for key, value in self.ACTION_MAP.items():
                if key.endswith("_") and callback_data.startswith(key):
                    return value
            return "callback_interaction"

        return "unknown_interaction"

    def _extract_details(self, event: TelegramObject, data: Dict[str, Any]) -> dict:
        details: dict[str, Any] = {
            "event_type": type(event).__name__,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        if isinstance(event, Message):
            details["text"] = event.text
            details["chat_id"] = event.chat.id if event.chat else None
        elif isinstance(event, CallbackQuery):
            details["callback_data"] = event.data
            details["chat_id"] = event.message.chat.id if event.message and event.message.chat else None

        # Persist lightweight runtime hints if available
        if "connector_manager" in data:
            details["has_connector"] = True

        return details

    async def _track(
        self,
        telegram_id: int,
        action: str,
        details: dict,
        session_id: str,
    ) -> None:
        try:
            async with self.session_factory() as session:
                user = await get_user_by_telegram_id(session, telegram_id)
                if not user:
                    return

                activity = UserActivity(
                    user_id=user.id,
                    action=action,
                    details=details,
                    session_id=session_id,
                    created_at=datetime.utcnow(),
                )
                session.add(activity)

                await self._upsert_session(session, user.id, session_id)
                await self._upsert_stats(session, user.id, action)

                await session.execute(
                    update(User)
                    .where(User.id == user.id)
                    .values(updated_at=datetime.utcnow())
                )

                await session.commit()

                await self._publish_activity(user, action, details)
        except SQLAlchemyError as exc:
            logger.debug("Activity tracking DB error: %s", exc)
        except Exception as exc:  # noqa: BLE001
            logger.debug("Activity tracking error: %s", exc)

    async def _upsert_session(self, session: AsyncSession, user_id: int, session_id: str) -> None:
        existing = (
            await session.execute(
                select(UserSession).where(UserSession.session_id == session_id)
            )
        ).scalar_one_or_none()

        if existing:
            await session.execute(
                update(UserSession)
                .where(UserSession.id == existing.id)
                .values(
                    last_active=datetime.utcnow(),
                    actions_count=UserSession.actions_count + 1,
                )
            )
            return

        session.add(
            UserSession(
                user_id=user_id,
                session_id=session_id,
                started_at=datetime.utcnow(),
                last_active=datetime.utcnow(),
                actions_count=1,
            )
        )

    async def _upsert_stats(self, session: AsyncSession, user_id: int, action: str) -> None:
        field_map = {
            "product_added": "products_added",
            "product_deleted": "products_deleted",
            "deal_viewed": "deals_viewed",
            "deal_to_watchlist": "deals_clicked",
            "store_requested": "store_requests_sent",
            "view_reports": "reports_viewed",
            "monitor_category_start": "categories_added",
            "price_alert_received": "alerts_received",
        }

        stats = (
            await session.execute(
                select(UserStats).where(UserStats.user_id == user_id)
            )
        ).scalar_one_or_none()

        if not stats:
            stats = UserStats(user_id=user_id, total_actions=0, daily_activity=[])
            session.add(stats)
            await session.flush()

        values: dict[str, Any] = {
            "total_actions": UserStats.total_actions + 1,
            "last_active": datetime.utcnow(),
        }

        field = field_map.get(action)
        if field:
            values[field] = UserStats.__table__.c[field] + 1

        await session.execute(
            update(UserStats)
            .where(UserStats.user_id == user_id)
            .values(**values)
        )

        # Update daily sparkline source (rolling 30 days)
        refreshed = (
            await session.execute(
                select(UserStats).where(UserStats.user_id == user_id)
            )
        ).scalar_one()

        today = datetime.utcnow().date().isoformat()
        daily = list(refreshed.daily_activity or [])
        updated = False
        for row in daily:
            if row.get("date") == today:
                row["count"] = int(row.get("count", 0)) + 1
                updated = True
                break
        if not updated:
            daily.append({"date": today, "count": 1})

        daily = daily[-30:]
        await session.execute(
            update(UserStats)
            .where(UserStats.user_id == user_id)
            .values(daily_activity=daily)
        )

    async def _publish_activity(self, user: User, action: str, details: dict) -> None:
        if self.redis is None:
            self.redis = Redis.from_url(REDIS_URL)

        payload = {
            "type": "user_action",
            "timestamp": datetime.utcnow().isoformat(),
            "user": {
                "id": user.telegram_id,
                "username": user.username,
                "name": user.first_name,
                "plan": user.plan.value if hasattr(user.plan, "value") else user.plan,
            },
            "action": action,
            "details": details,
        }
        await self.redis.publish("bot:activity", json.dumps(payload, ensure_ascii=False))
