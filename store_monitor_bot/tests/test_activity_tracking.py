from datetime import datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

import admin.dashboard as dashboard
from auth.security import create_access_token
from bot.middleware.activity_tracker import ActivityTrackerMiddleware
from config.settings import ADMIN_USER_IDS
from db.models import User, UserActivity, UserStats, PlanType


@pytest.mark.asyncio
async def test_activity_recorded_on_product_add(async_session):
    user = User(telegram_id=1111, username="u1", first_name="User", plan=PlanType.FREE)
    async_session.add(user)
    await async_session.commit()

    session_factory = async_sessionmaker(async_session.bind, expire_on_commit=False)
    middleware = ActivityTrackerMiddleware(session_factory)

    await middleware._track(1111, "product_added", {"product_url": "https://example.com/p"}, "sess-a")

    activity = (await async_session.execute(select(UserActivity).where(UserActivity.user_id == user.id))).scalar_one_or_none()
    stats = (await async_session.execute(select(UserStats).where(UserStats.user_id == user.id))).scalar_one_or_none()

    assert activity is not None
    assert activity.action == "product_added"
    assert stats is not None
    assert stats.products_added >= 1


@pytest.mark.asyncio
async def test_activity_recorded_on_deal_view(async_session):
    user = User(telegram_id=2222, username="u2", first_name="User", plan=PlanType.FREE)
    async_session.add(user)
    await async_session.commit()

    session_factory = async_sessionmaker(async_session.bind, expire_on_commit=False)
    middleware = ActivityTrackerMiddleware(session_factory)

    await middleware._track(2222, "deal_viewed", {"deal": "x"}, "sess-b")

    activity = (await async_session.execute(select(UserActivity).where(UserActivity.user_id == user.id))).scalar_one_or_none()
    stats = (await async_session.execute(select(UserStats).where(UserStats.user_id == user.id))).scalar_one_or_none()

    assert activity is not None
    assert activity.action == "deal_viewed"
    assert stats is not None
    assert stats.deals_viewed >= 1


@pytest.mark.asyncio
async def test_user_stats_update_correctly(async_session):
    user = User(telegram_id=3333, username="u3", first_name="User", plan=PlanType.FREE)
    async_session.add(user)
    await async_session.commit()

    session_factory = async_sessionmaker(async_session.bind, expire_on_commit=False)
    middleware = ActivityTrackerMiddleware(session_factory)

    await middleware._track(3333, "product_added", {}, "sess-c")
    await middleware._track(3333, "deal_viewed", {}, "sess-c")
    await middleware._track(3333, "store_requested", {}, "sess-c")

    stats = (await async_session.execute(select(UserStats).where(UserStats.user_id == user.id))).scalar_one()
    assert stats.total_actions >= 3
    assert stats.products_added >= 1
    assert stats.deals_viewed >= 1
    assert stats.store_requests_sent >= 1


@pytest.mark.asyncio
async def test_user_profile_api_returns_full_data(async_session):
    user = User(telegram_id=4444, username="u4", first_name="User", plan=PlanType.PROFESSIONAL)
    async_session.add(user)
    await async_session.commit()

    async_session.add(UserStats(user_id=user.id, total_actions=5, products_added=2, daily_activity=[{"date": "2026-03-17", "count": 5}]))
    async_session.add(UserActivity(user_id=user.id, action="product_added", details={"product": "Phone"}))
    await async_session.commit()

    async def _override_session():
        yield async_session

    dashboard.app.dependency_overrides[dashboard._get_db_session] = _override_session

    token, _ = create_access_token(ADMIN_USER_IDS[0])
    headers = {"Authorization": f"Bearer {token}"}

    transport = ASGITransport(app=dashboard.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(f"/api/users/{user.telegram_id}/profile", headers=headers)

    dashboard.app.dependency_overrides.pop(dashboard._get_db_session, None)

    assert response.status_code == 200
    payload = response.json()
    assert "user" in payload
    assert "stats" in payload
    assert "products" in payload
    assert "recent_activities" in payload


def test_live_feed_websocket_receives_events(monkeypatch):
    class _PubSub:
        def __init__(self):
            self._sent = False

        async def subscribe(self, *_):
            return None

        async def unsubscribe(self, *_):
            return None

        async def close(self):
            return None

        async def get_message(self, **_):
            if self._sent:
                raise RuntimeError("stop")
            self._sent = True
            return {
                "type": "message",
                "data": b'{"type":"user_action","action":"product_added"}',
            }

    class _Redis:
        def pubsub(self):
            return _PubSub()

    monkeypatch.setattr(dashboard, "redis_client", _Redis())
    monkeypatch.setattr(dashboard, "_verify_ws_admin", lambda _token: True)

    from fastapi.testclient import TestClient

    client = TestClient(dashboard.app, raise_server_exceptions=False)
    with client.websocket_connect("/ws/activity?token=test-token") as ws:
        data = ws.receive_json()
        assert data["type"] == "user_action"
        assert data["action"] == "product_added"


@pytest.mark.asyncio
async def test_daily_activity_sparkline_data(async_session):
    user = User(telegram_id=5555, username="u5", first_name="User", plan=PlanType.FREE)
    async_session.add(user)
    await async_session.commit()

    start = datetime.utcnow() - timedelta(days=6)
    daily = []
    for i in range(7):
        daily.append({"date": (start + timedelta(days=i)).date().isoformat(), "count": i + 1})

    async_session.add(UserStats(user_id=user.id, total_actions=28, daily_activity=daily))
    await async_session.commit()

    stats = (await async_session.execute(select(UserStats).where(UserStats.user_id == user.id))).scalar_one()
    assert len(stats.daily_activity) == 7
    assert stats.daily_activity[-1]["count"] == 7
