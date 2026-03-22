from datetime import datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import async_sessionmaker

import admin.dashboard as dashboard
from auth.security import create_access_token
from config.settings import ADMIN_USER_IDS
from db.crud import create_admin_notification
from db.models import AdminNotification, PlanType, StoreRequest, StoreRequestStatus, User


VALID_ADMIN_ID = ADMIN_USER_IDS[0]


def _auth_headers() -> dict:
    token, _ = create_access_token(VALID_ADMIN_ID)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def api_client(engine, monkeypatch):
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(dashboard, "SESSION_FACTORY", session_factory)

    transport = ASGITransport(app=dashboard.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, session_factory


@pytest.mark.asyncio
async def test_create_admin_notification_persists_and_publishes(async_session, monkeypatch):
    calls = {"channel": None, "payload": None, "closed": False}

    class _Redis:
        async def publish(self, channel, payload):
            calls["channel"] = channel
            calls["payload"] = payload

        async def close(self):
            calls["closed"] = True

    monkeypatch.setattr("db.crud.Redis.from_url", lambda *_: _Redis())

    notif = await create_admin_notification(
        async_session,
        type="new_user",
        title="مستخدم جديد",
        message="@test انضم",
        icon="👤",
        color="green",
        action_url="/users",
    )

    assert notif is not None
    row = (await async_session.execute(select(AdminNotification).where(AdminNotification.id == notif.id))).scalar_one_or_none()
    assert row is not None
    assert calls["channel"] == "admin:notifications"
    assert calls["payload"] is not None
    assert calls["closed"] is True


@pytest.mark.asyncio
async def test_create_admin_notification_returns_none_on_db_error(async_session, monkeypatch):
    async def _raise_commit():
        raise SQLAlchemyError("boom")

    monkeypatch.setattr(async_session, "commit", _raise_commit)

    notif = await create_admin_notification(
        async_session,
        type="new_user",
        title="x",
        message="y",
    )
    assert notif is None


@pytest.mark.asyncio
async def test_get_notifications_returns_unread_count(api_client):
    client, session_factory = api_client

    async with session_factory() as session:
        session.add_all([
            AdminNotification(
                type="new_user",
                title="old",
                message="m1",
                icon="👤",
                color="green",
                read=True,
                created_at=datetime.utcnow() - timedelta(hours=2),
            ),
            AdminNotification(
                type="store_request",
                title="new",
                message="m2",
                icon="🏪",
                color="orange",
                read=False,
                created_at=datetime.utcnow() - timedelta(minutes=5),
            ),
        ])
        await session.commit()

    response = await client.get("/api/notifications", headers=_auth_headers())
    assert response.status_code == 200
    data = response.json()
    assert data["unread_count"] == 1
    assert len(data["notifications"]) == 2
    assert data["notifications"][0]["title"] == "new"


@pytest.mark.asyncio
async def test_mark_single_notification_as_read(api_client):
    client, session_factory = api_client

    async with session_factory() as session:
        item = AdminNotification(
            type="new_opportunity",
            title="n",
            message="m",
            read=False,
        )
        session.add(item)
        await session.commit()
        await session.refresh(item)
        notif_id = item.id

    response = await client.post(f"/api/notifications/{notif_id}/read", headers=_auth_headers())
    assert response.status_code == 200

    async with session_factory() as session:
        updated = (await session.execute(select(AdminNotification).where(AdminNotification.id == notif_id))).scalar_one()
        assert updated.read is True


@pytest.mark.asyncio
async def test_mark_notification_read_not_found(api_client):
    client, _ = api_client

    response = await client.post("/api/notifications/9999/read", headers=_auth_headers())
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_mark_all_notifications_read(api_client):
    client, session_factory = api_client

    async with session_factory() as session:
        session.add_all([
            AdminNotification(type="a", title="1", message="m1", read=False),
            AdminNotification(type="b", title="2", message="m2", read=False),
        ])
        await session.commit()

    response = await client.post("/api/notifications/read-all", headers=_auth_headers())
    assert response.status_code == 200

    async with session_factory() as session:
        rows = (await session.execute(select(AdminNotification))).scalars().all()
        assert rows
        assert all(r.read for r in rows)


@pytest.mark.asyncio
async def test_get_notifications_returns_empty_on_sqlalchemy_error(api_client):
    client, _ = api_client

    class _BrokenSession:
        async def execute(self, *_args, **_kwargs):
            raise SQLAlchemyError("broken")

        async def commit(self):
            return None

        async def rollback(self):
            return None

    async def _broken_dep():
        yield _BrokenSession()

    dashboard.app.dependency_overrides[dashboard._get_db_session] = _broken_dep
    try:
        response = await client.get("/api/notifications", headers=_auth_headers())
    finally:
        dashboard.app.dependency_overrides.pop(dashboard._get_db_session, None)

    assert response.status_code == 200
    assert response.json() == {"notifications": [], "unread_count": 0}


@pytest.mark.asyncio
async def test_mark_all_notifications_read_handles_sqlalchemy_error(api_client):
    client, _ = api_client

    class _BrokenSession:
        async def execute(self, *_args, **_kwargs):
            raise SQLAlchemyError("broken")

        async def commit(self):
            return None

        async def rollback(self):
            return None

    async def _broken_dep():
        yield _BrokenSession()

    dashboard.app.dependency_overrides[dashboard._get_db_session] = _broken_dep
    try:
        response = await client.post("/api/notifications/read-all", headers=_auth_headers())
    finally:
        dashboard.app.dependency_overrides.pop(dashboard._get_db_session, None)

    assert response.status_code == 200
    assert response.json()["success"] is True


@pytest.mark.asyncio
async def test_upgrade_user_endpoint_success(api_client, monkeypatch):
    client, session_factory = api_client
    auth_headers = _auth_headers()

    async with session_factory() as session:
        user = User(telegram_id=777001, username="upgrade_me", plan=PlanType.FREE)
        session.add(user)
        await session.commit()

    async def _fake_notify(*_args, **_kwargs):
        return None

    monkeypatch.setattr(dashboard, "_notify_user_via_telegram", _fake_notify)
    monkeypatch.setattr(dashboard, "_log_admin_action", lambda **_kwargs: None)

    csrf = (await client.get("/api/csrf-token", headers=auth_headers)).json()["csrf_token"]
    response = await client.post(
        "/api/users/777001/upgrade",
        json={"plan": "basic", "days": 30},
        headers={**auth_headers, "x-csrf-token": csrf},
    )
    assert response.status_code == 200
    assert response.json()["success"] is True


@pytest.mark.asyncio
async def test_toggle_ban_endpoint_success(api_client, monkeypatch):
    client, session_factory = api_client
    auth_headers = _auth_headers()

    async with session_factory() as session:
        user = User(telegram_id=777002, username="ban_me", plan=PlanType.FREE, is_banned=False)
        session.add(user)
        await session.commit()

    async def _fake_notify(*_args, **_kwargs):
        return None

    monkeypatch.setattr(dashboard, "_notify_user_via_telegram", _fake_notify)
    monkeypatch.setattr(dashboard, "_log_admin_action", lambda **_kwargs: None)

    csrf = (await client.get("/api/csrf-token", headers=auth_headers)).json()["csrf_token"]
    response = await client.post(
        "/api/users/777002/ban",
        headers={**auth_headers, "x-csrf-token": csrf},
    )
    assert response.status_code == 200
    assert response.json()["user"]["is_banned"] is True


@pytest.mark.asyncio
async def test_unban_endpoint_success(api_client, monkeypatch):
    client, session_factory = api_client
    auth_headers = _auth_headers()

    async with session_factory() as session:
        user = User(telegram_id=777005, username="unban_me", plan=PlanType.FREE, is_banned=True)
        session.add(user)
        await session.commit()

    async def _fake_notify(*_args, **_kwargs):
        return None

    monkeypatch.setattr(dashboard, "_notify_user_via_telegram", _fake_notify)
    monkeypatch.setattr(dashboard, "_log_admin_action", lambda **_kwargs: None)

    csrf = (await client.get("/api/csrf-token", headers=auth_headers)).json()["csrf_token"]
    response = await client.post(
        "/api/users/777005/unban",
        headers={**auth_headers, "x-csrf-token": csrf},
    )
    assert response.status_code == 200
    assert response.json()["user"]["is_banned"] is False


@pytest.mark.asyncio
async def test_send_message_to_user_endpoint_success(api_client, monkeypatch):
    client, session_factory = api_client
    auth_headers = _auth_headers()

    async with session_factory() as session:
        user = User(telegram_id=777006, username="message_me", plan=PlanType.FREE)
        session.add(user)
        await session.commit()

    async def _fake_notify(*_args, **_kwargs):
        return None

    monkeypatch.setattr(dashboard, "_notify_user_via_telegram", _fake_notify)
    monkeypatch.setattr(dashboard, "_log_admin_action", lambda **_kwargs: None)

    csrf = (await client.get("/api/csrf-token", headers=auth_headers)).json()["csrf_token"]
    response = await client.post(
        "/api/users/777006/send-message",
        json={"message": "hello from admin"},
        headers={**auth_headers, "x-csrf-token": csrf},
    )
    assert response.status_code == 200
    assert response.json()["success"] is True


@pytest.mark.asyncio
async def test_store_requests_approve_and_reject(api_client, monkeypatch):
    client, session_factory = api_client
    auth_headers = _auth_headers()

    async with session_factory() as session:
        user = User(telegram_id=777003, username="req_user", plan=PlanType.FREE)
        session.add(user)
        await session.flush()

        req1 = StoreRequest(user_id=user.id, store_url="https://example-store.com", status=StoreRequestStatus.PENDING)
        req2 = StoreRequest(user_id=user.id, store_url="https://example-store-2.com", status=StoreRequestStatus.PENDING)
        session.add_all([req1, req2])
        await session.commit()
        await session.refresh(req1)
        await session.refresh(req2)

    monkeypatch.setattr(dashboard, "_log_admin_action", lambda **_kwargs: None)
    csrf = (await client.get("/api/csrf-token", headers=auth_headers)).json()["csrf_token"]

    approve_res = await client.post(
        f"/api/store-requests/{req1.id}/approve",
        json={"admin_notes": "ok"},
        headers={**auth_headers, "x-csrf-token": csrf},
    )
    reject_res = await client.post(
        f"/api/store-requests/{req2.id}/reject",
        json={"admin_notes": "no"},
        headers={**auth_headers, "x-csrf-token": csrf},
    )

    assert approve_res.status_code == 200
    assert reject_res.status_code == 200


@pytest.mark.asyncio
async def test_broadcast_endpoint_success(api_client, monkeypatch):
    client, _ = api_client
    auth_headers = _auth_headers()

    async def _fake_resolve(*_args, **_kwargs):
        return [object(), object()]

    monkeypatch.setattr(dashboard, "_resolve_target_users", _fake_resolve)

    async def _fake_send(_users, _text):
        return 2, 0

    monkeypatch.setattr(dashboard, "_send_text_to_users", _fake_send)
    monkeypatch.setattr(dashboard, "_log_admin_action", lambda **_kwargs: None)

    csrf = (await client.get("/api/csrf-token", headers=auth_headers)).json()["csrf_token"]
    response = await client.post(
        "/api/broadcast",
        json={"message": "hello", "target": "all"},
        headers={**auth_headers, "x-csrf-token": csrf},
    )
    assert response.status_code == 200
    assert response.json()["sent"] == 2


@pytest.mark.asyncio
async def test_manual_opportunity_publish_success(api_client, monkeypatch):
    client, _ = api_client
    auth_headers = _auth_headers()

    async def _fake_resolve(*_args, **_kwargs):
        return [object()]

    monkeypatch.setattr(dashboard, "_resolve_target_users", _fake_resolve)

    async def _fake_send(_users, _text):
        return 1, 0

    monkeypatch.setattr(dashboard, "_send_text_to_users", _fake_send)
    monkeypatch.setattr(dashboard, "_log_admin_action", lambda **_kwargs: None)

    csrf = (await client.get("/api/csrf-token", headers=auth_headers)).json()["csrf_token"]
    response = await client.post(
        "/api/opportunities/manual",
        json={
            "product_name": "Test Product",
            "product_url": "https://example.com/p/1",
            "affiliate_url": "https://aff.example.com/p/1",
            "old_price": 100.0,
            "new_price": 70.0,
            "custom_message": "deal",
            "target_plan": "all",
        },
        headers={**auth_headers, "x-csrf-token": csrf},
    )
    assert response.status_code == 200
    assert response.json()["sent_count"] == 1
