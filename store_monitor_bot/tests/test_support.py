from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import select
import admin.dashboard as dashboard
import bot.handlers.admin as admin_handlers
import bot.handlers.user2 as user2_handlers
import db.crud as crud
from auth.security import create_access_token
from config.settings import ADMIN_USER_IDS
from db.crud import add_ticket_message, create_support_ticket
from db.models import AdminUser, PlanType, SupportSenderType, SupportTicket, SupportTicketStatus, TeamMember, User


VALID_ADMIN_ID = ADMIN_USER_IDS[0]


def _auth_headers() -> dict:
    token, _ = create_access_token(VALID_ADMIN_ID)
    return {"Authorization": f"Bearer {token}"}


def _auth_bundle() -> tuple[str, dict]:
    token, _ = create_access_token(VALID_ADMIN_ID)
    return token, {"Authorization": f"Bearer {token}"}


async def _seed_support_context(session_factory, *, user_tid: int, username: str, admin_name: str = "Support Admin"):
    async with session_factory() as session:
        user = User(telegram_id=user_tid, username=username, first_name=username.title())
        admin_user = AdminUser(telegram_id=VALID_ADMIN_ID, password_hash="hash", name=admin_name)
        session.add_all([user, admin_user])
        await session.commit()
        await session.refresh(user)
        await session.refresh(admin_user)

        ticket = await create_support_ticket(
            session,
            user=user,
            content="رسالة دعم أولى",
            sender_name=user.first_name,
        )
        return user.id, admin_user.id, ticket.id


@pytest.mark.asyncio
async def test_ticket_creation(async_session, monkeypatch):
    user = User(telegram_id=1001, username="ticket_user", first_name="Ticket")
    async_session.add(user)
    await async_session.commit()
    await async_session.refresh(user)

    monkeypatch.setattr("db.crud.Redis.from_url", lambda *_: SimpleNamespace(publish=AsyncMock(), close=AsyncMock()))

    ticket = await create_support_ticket(
        async_session,
        user=user,
        content="مرحبا لدي مشكلة في الاشتراك",
        subject="مشكلة اشتراك",
        sender_name="Ticket",
    )

    saved = (await async_session.execute(
        select(SupportTicket).where(SupportTicket.id == ticket.id)
    )).scalar_one()

    assert saved.ticket_number.startswith("TKT-")
    assert saved.messages_count == 1
    assert saved.status == SupportTicketStatus.OPEN


@pytest.mark.asyncio
async def test_ticket_reply(async_session, monkeypatch):
    user = User(telegram_id=1002, username="reply_user", first_name="Reply")
    async_session.add(user)
    await async_session.commit()
    await async_session.refresh(user)

    monkeypatch.setattr("db.crud.Redis.from_url", lambda *_: SimpleNamespace(publish=AsyncMock(), close=AsyncMock()))
    ticket = await create_support_ticket(
        async_session,
        user=user,
        content="أول رسالة",
        sender_name="Reply",
    )

    reply = await add_ticket_message(
        async_session,
        ticket=ticket,
        sender_type=SupportSenderType.USER,
        content="هذه متابعة من المستخدم",
        sender_user_id=user.id,
        sender_name="Reply",
    )

    await async_session.refresh(ticket)
    assert reply.content == "هذه متابعة من المستخدم"
    assert ticket.messages_count == 2
    assert ticket.status in (SupportTicketStatus.OPEN, SupportTicketStatus.IN_PROGRESS)


@pytest.mark.asyncio
async def test_support_crud_helpers(async_session, monkeypatch):
    user = User(telegram_id=1010, username="crud_user", first_name="Crud")
    admin_user = AdminUser(telegram_id=5000, password_hash="hash", name="Crud Admin")
    async_session.add_all([user, admin_user])
    await async_session.commit()
    await async_session.refresh(user)
    await async_session.refresh(admin_user)

    monkeypatch.setattr("db.crud.Redis.from_url", lambda *_: SimpleNamespace(publish=AsyncMock(), close=AsyncMock()))

    ticket = await crud.create_support_ticket(
        async_session,
        user=user,
        content="أحتاج مساعدة",
        sender_name="Crud",
    )
    await crud.add_ticket_message(
        async_session,
        ticket=ticket,
        sender_type=SupportSenderType.ADMIN,
        content="تم الاستلام",
        sender_admin_id=admin_user.id,
        sender_name="Crud Admin",
    )

    generated = await crud.generate_ticket_number(async_session)
    open_tickets = await crud.get_user_open_tickets(async_session, user.id)
    all_tickets = await crud.get_user_tickets(async_session, user.id)
    loaded_ticket = await crud.get_ticket_by_id(async_session, ticket.id)

    assert generated.endswith("0002")
    assert len(open_tickets) == 1
    assert len(all_tickets) == 1
    assert loaded_ticket is not None
    assert loaded_ticket.messages
    assert loaded_ticket.status == SupportTicketStatus.WAITING_USER


@pytest.mark.asyncio
async def test_support_ticket_listing_and_team_helpers(async_session, monkeypatch):
    user = User(telegram_id=1011, username="list_user", first_name="List")
    admin_user = AdminUser(telegram_id=5001, password_hash="hash", name="List Admin")
    async_session.add_all([user, admin_user])
    await async_session.commit()
    await async_session.refresh(user)
    await async_session.refresh(admin_user)

    monkeypatch.setattr("db.crud.Redis.from_url", lambda *_: SimpleNamespace(publish=AsyncMock(), close=AsyncMock()))

    ticket = await crud.create_support_ticket(
        async_session,
        user=user,
        content="تحويل للفواتير",
        department="billing",
        sender_name="List",
    )
    team_member = TeamMember(admin_id=admin_user.id, display_name="List Admin", department="billing")
    async_session.add(team_member)
    await async_session.commit()

    tickets, total = await crud.list_support_tickets(
        async_session,
        status="open",
        department="billing",
        page=1,
        per_page=10,
    )
    team = await crud.get_support_team(async_session)

    assert total == 1
    assert tickets[0].id == ticket.id
    assert team[0].display_name == "List Admin"


@pytest.mark.asyncio
async def test_support_related_admin_crud_helpers(async_session):
    active_user = User(telegram_id=1012, username="active_user", first_name="Active", plan=PlanType.FREE)
    banned_user = User(telegram_id=1013, username="banned_user", first_name="Banned", is_banned=True)
    admin_user = AdminUser(telegram_id=6001, password_hash="hash", name="Lookup Admin")
    async_session.add_all([active_user, banned_user, admin_user])
    await async_session.commit()
    await async_session.refresh(active_user)

    await crud.update_user_plan(async_session, active_user.id, PlanType.BASIC)
    looked_up_admin = await crud.get_admin_by_telegram_id(async_session, 6001)
    active_users = await crud.get_all_users(async_session)

    await async_session.refresh(active_user)
    assert active_user.plan == PlanType.BASIC
    assert looked_up_admin is not None
    assert looked_up_admin.name == "Lookup Admin"
    assert [user.telegram_id for user in active_users] == [1012]


@pytest.mark.asyncio
async def test_ticket_assignment(api_client, monkeypatch):
    client, session_factory = api_client
    publish_mock = AsyncMock()
    monkeypatch.setattr(dashboard.redis_client, "publish", publish_mock)
    monkeypatch.setattr(dashboard, "_notify_user_via_telegram", AsyncMock())

    _, admin_user_id, ticket_id = await _seed_support_context(
        session_factory,
        user_tid=1003,
        username="assign_user",
    )

    async with session_factory() as session:
        member = TeamMember(admin_id=admin_user_id, display_name="Support Admin")
        session.add(member)
        await session.commit()

    _token, headers = _auth_bundle()
    csrf = await client.get("/api/csrf-token", headers=headers)
    response = await client.post(
        f"/api/support/tickets/{ticket_id}/assign",
        json={"admin_id": admin_user_id},
        headers={**headers, "X-CSRF-Token": csrf.json()["csrf_token"]},
    )

    assert response.status_code == 200
    assert response.json()["ticket"]["assigned_to"] == admin_user_id


@pytest.mark.asyncio
async def test_ticket_resolve(api_client, monkeypatch):
    client, session_factory = api_client
    publish_mock = AsyncMock()
    monkeypatch.setattr(dashboard.redis_client, "publish", publish_mock)
    notify_mock = AsyncMock()
    monkeypatch.setattr(dashboard, "_notify_user_via_telegram", notify_mock)

    _, _admin_user_id, ticket_id = await _seed_support_context(
        session_factory,
        user_tid=1004,
        username="resolve_user",
        admin_name="Resolver",
    )

    _token, headers = _auth_bundle()
    csrf = await client.get("/api/csrf-token", headers=headers)
    response = await client.post(
        f"/api/support/tickets/{ticket_id}/resolve",
        headers={**headers, "X-CSRF-Token": csrf.json()["csrf_token"]},
    )

    assert response.status_code == 200
    assert response.json()["ticket"]["status"] == "resolved"
    notify_mock.assert_awaited()


@pytest.mark.asyncio
async def test_support_ticket_list_and_detail(api_client, monkeypatch):
    client, session_factory = api_client
    monkeypatch.setattr(dashboard.redis_client, "publish", AsyncMock())
    _, _admin_user_id, ticket_id = await _seed_support_context(
        session_factory,
        user_tid=1005,
        username="list_user",
    )

    list_response = await client.get("/api/support/tickets", headers=_auth_headers())
    detail_response = await client.get(f"/api/support/tickets/{ticket_id}", headers=_auth_headers())

    assert list_response.status_code == 200
    assert list_response.json()["tickets"]
    assert detail_response.status_code == 200
    assert detail_response.json()["id"] == ticket_id
    assert isinstance(detail_response.json()["messages"], list)


@pytest.mark.asyncio
async def test_support_ticket_reply_endpoint(api_client, monkeypatch):
    client, session_factory = api_client
    monkeypatch.setattr(dashboard.redis_client, "publish", AsyncMock())
    notify_mock = AsyncMock()
    monkeypatch.setattr(dashboard, "_notify_user_via_telegram", notify_mock)
    _, _admin_user_id, ticket_id = await _seed_support_context(
        session_factory,
        user_tid=1006,
        username="reply_endpoint_user",
    )

    _token, headers = _auth_bundle()
    csrf = await client.get("/api/csrf-token", headers=headers)
    response = await client.post(
        f"/api/support/tickets/{ticket_id}/reply",
        json={"message": "هذا رد من لوحة الإدارة"},
        headers={**headers, "X-CSRF-Token": csrf.json()["csrf_token"]},
    )

    assert response.status_code == 200
    assert response.json()["ticket"]["status"] == "waiting_user"
    notify_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_support_ticket_transfer_and_close(api_client, monkeypatch):
    client, session_factory = api_client
    monkeypatch.setattr(dashboard.redis_client, "publish", AsyncMock())
    _, _admin_user_id, ticket_id = await _seed_support_context(
        session_factory,
        user_tid=1007,
        username="transfer_user",
    )

    _token, headers = _auth_bundle()
    csrf = await client.get("/api/csrf-token", headers=headers)
    transfer_response = await client.post(
        f"/api/support/tickets/{ticket_id}/transfer",
        json={"department": "billing", "note": "تحويل للفواتير"},
        headers={**headers, "X-CSRF-Token": csrf.json()["csrf_token"]},
    )
    close_response = await client.post(
        f"/api/support/tickets/{ticket_id}/close",
        headers={**headers, "X-CSRF-Token": csrf.json()["csrf_token"]},
    )

    assert transfer_response.status_code == 200
    assert transfer_response.json()["ticket"]["department"] == "billing"
    assert close_response.status_code == 200
    assert close_response.json()["ticket"]["status"] == "closed"


@pytest.mark.asyncio
async def test_support_team_create_update_and_stats(api_client, monkeypatch):
    client, session_factory = api_client
    monkeypatch.setattr(dashboard.redis_client, "publish", AsyncMock())
    _, admin_user_id, ticket_id = await _seed_support_context(
        session_factory,
        user_tid=1008,
        username="team_user",
    )

    _token, headers = _auth_bundle()
    csrf = await client.get("/api/csrf-token", headers=headers)
    create_response = await client.post(
        "/api/support/team",
        json={
            "display_name": "Sara Ahmed",
            "department": "billing",
            "admin_id": admin_user_id,
            "role": "فريق الحسابات",
            "avatar_color": "#10B981",
            "is_available": True,
        },
        headers={**headers, "X-CSRF-Token": csrf.json()["csrf_token"]},
    )

    member_id = create_response.json()["member"]["id"]
    update_response = await client.put(
        f"/api/support/team/{member_id}",
        json={
            "display_name": "Sara Updated",
            "department": "support",
            "admin_id": admin_user_id,
            "role": "خدمة العملاء",
            "avatar_color": "#2563EB",
            "is_available": False,
        },
        headers={**headers, "X-CSRF-Token": csrf.json()["csrf_token"]},
    )
    list_response = await client.get("/api/support/team", headers=_auth_headers())
    stats_response = await client.get("/api/support/stats", headers=_auth_headers())

    assert create_response.status_code == 200
    assert update_response.status_code == 200
    assert list_response.status_code == 200
    assert stats_response.status_code == 200
    assert stats_response.json()["tickets_today"] >= 1


@pytest.mark.asyncio
async def test_support_menu_callback_clears_state(monkeypatch, support_callback):
    state = AsyncMock()
    monkeypatch.setattr(
        "db.crud.get_user_by_telegram_id",
        AsyncMock(return_value=SimpleNamespace(id=8, telegram_id=2001)),
    )
    monkeypatch.setattr("db.crud.get_user_open_tickets", AsyncMock(return_value=[]))

    await user2_handlers.support_menu_callback(support_callback, AsyncMock(), state)

    state.clear.assert_awaited_once()
    support_callback.message.edit_text.assert_awaited_once()


@pytest.mark.asyncio
async def test_new_ticket_department_sets_state(support_callback):
    state = AsyncMock()
    support_callback.data = "support_new"

    await user2_handlers.new_ticket_department(support_callback, state)

    state.set_state.assert_awaited_once_with(user2_handlers.SupportTicketStates.choosing_department)
    support_callback.message.edit_text.assert_awaited_once()


@pytest.mark.asyncio
async def test_new_ticket_write_sets_department(support_callback):
    state = AsyncMock()
    support_callback.data = "dept:billing"

    await user2_handlers.new_ticket_write(support_callback, state)

    state.update_data.assert_awaited_once_with(department="billing")
    state.set_state.assert_awaited_once_with(user2_handlers.SupportTicketStates.writing_message)


@pytest.mark.asyncio
async def test_open_ticket_conversation_sets_reply_state(monkeypatch, support_callback):
    state = AsyncMock()
    support_callback.data = "support_ticket:13"
    ticket = SimpleNamespace(
        id=13,
        user=SimpleNamespace(telegram_id=2001),
        ticket_number="TKT-2026-0013",
        status="open",
        messages=[
            SimpleNamespace(sender_type=SimpleNamespace(value="user"), sender_name="User", content="hello"),
            SimpleNamespace(sender_type=SimpleNamespace(value="admin"), sender_name="Admin", content="reply"),
        ],
    )
    monkeypatch.setattr("db.crud.get_ticket_by_id", AsyncMock(return_value=ticket))

    await user2_handlers.open_ticket_conversation(support_callback, state, AsyncMock())

    state.set_state.assert_awaited_once_with(user2_handlers.SupportTicketStates.replying_to_ticket)
    support_callback.message.edit_text.assert_awaited_once()


@pytest.mark.asyncio
async def test_handle_user_reply_to_ticket_handler(monkeypatch, support_message):
    state = AsyncMock()
    state.get_data = AsyncMock(return_value={"ticket_id": 22})
    ticket = SimpleNamespace(id=22, user_id=5)
    user = SimpleNamespace(id=5, first_name="Support", username="support_user")

    monkeypatch.setattr("db.crud.get_ticket_by_id", AsyncMock(return_value=ticket))
    monkeypatch.setattr("db.crud.get_user_by_telegram_id", AsyncMock(return_value=user))
    monkeypatch.setattr("db.crud.add_ticket_message", AsyncMock())
    monkeypatch.setattr(user2_handlers, "_publish_support_event", AsyncMock())

    await user2_handlers.handle_user_reply_to_ticket(support_message, state, AsyncMock())

    user2_handlers._publish_support_event.assert_awaited_once()
    support_message.answer.assert_awaited_once()


@pytest.mark.asyncio
async def test_quick_reply_ticket_sets_state():
    state = AsyncMock()
    callback = SimpleNamespace(
        data="quick_reply:44",
        from_user=SimpleNamespace(id=VALID_ADMIN_ID),
        message=SimpleNamespace(answer=AsyncMock()),
        answer=AsyncMock(),
    )

    await admin_handlers.quick_reply_ticket(callback, state)

    state.update_data.assert_awaited_once_with(reply_ticket_id=44)
    state.set_state.assert_awaited_once_with(admin_handlers.AdminReplyStates.writing_reply)


@pytest.fixture
def support_message():
    message = SimpleNamespace()
    message.text = "مرحبا لدي مشكلة"
    message.message_id = 55
    message.from_user = SimpleNamespace(id=2001, first_name="User", username="support_user", full_name="Support User")
    message.answer = AsyncMock()
    message.bot = SimpleNamespace(send_message=AsyncMock())
    return message


@pytest.fixture
def support_callback():
    callback = SimpleNamespace()
    callback.data = ""
    callback.from_user = SimpleNamespace(id=2001)
    callback.answer = AsyncMock()
    callback.message = SimpleNamespace(edit_text=AsyncMock(), answer=AsyncMock())
    return callback


@pytest.mark.asyncio
async def test_support_menu_shows_open_ticket(monkeypatch, support_message):
    monkeypatch.setattr(
        "db.crud.get_user_by_telegram_id",
        AsyncMock(return_value=SimpleNamespace(id=8, telegram_id=2001)),
    )
    monkeypatch.setattr(
        "db.crud.get_user_open_tickets",
        AsyncMock(return_value=[SimpleNamespace(id=3, ticket_number="TKT-2026-0003", status="open")]),
    )

    await user2_handlers.support_menu(support_message, AsyncMock())

    assert "الدعم الفني" in support_message.answer.call_args.args[0]
    assert "1" in support_message.answer.call_args.args[0]


@pytest.mark.asyncio
async def test_create_ticket_from_message_handler(monkeypatch, support_message):
    state = AsyncMock()
    state.get_data = AsyncMock(return_value={"department": "support"})
    ticket = SimpleNamespace(id=9, ticket_number="TKT-2026-0009")
    user = SimpleNamespace(id=4, first_name="User", username="support_user")

    monkeypatch.setattr("db.crud.get_user_by_telegram_id", AsyncMock(return_value=user))
    monkeypatch.setattr("db.crud.create_support_ticket", AsyncMock(return_value=ticket))
    monkeypatch.setattr(user2_handlers, "_notify_support_team", AsyncMock())

    await user2_handlers.create_ticket_from_message(support_message, state, AsyncMock())

    assert "تم استلام طلبك" in support_message.answer.call_args.args[0]
    user2_handlers._notify_support_team.assert_awaited_once()


@pytest.mark.asyncio
async def test_admin_quick_reply_handler(monkeypatch):
    state = AsyncMock()
    message = SimpleNamespace()
    message.text = "هذا رد من الإدارة"
    message.from_user = SimpleNamespace(id=VALID_ADMIN_ID, full_name="Admin User")
    message.answer = AsyncMock()
    message.bot = SimpleNamespace(send_message=AsyncMock())

    ticket = SimpleNamespace(
        id=12,
        ticket_number="TKT-2026-0012",
        user=SimpleNamespace(telegram_id=3001, username="ticket_owner", first_name="Owner"),
    )
    state.get_data = AsyncMock(return_value={"reply_ticket_id": 12})

    monkeypatch.setattr(admin_handlers, "is_admin", lambda *_: True)
    monkeypatch.setattr("db.crud.get_ticket_by_id", AsyncMock(return_value=ticket))
    monkeypatch.setattr("db.crud.get_admin_by_telegram_id", AsyncMock(return_value=SimpleNamespace(id=1, name="Admin User")))
    monkeypatch.setattr("db.crud.add_ticket_message", AsyncMock())
    monkeypatch.setattr("redis.asyncio.Redis.from_url", lambda *_: SimpleNamespace(publish=AsyncMock(), close=AsyncMock()))

    await admin_handlers.send_admin_reply(message, state, AsyncMock())

    message.bot.send_message.assert_awaited_once()
    state.clear.assert_awaited_once()