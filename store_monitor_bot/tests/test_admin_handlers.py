from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

import bot.handlers.admin as admin_handlers
import db.crud as crud


@pytest.fixture
def mock_message():
    msg = MagicMock()
    msg.from_user = SimpleNamespace(id=admin_handlers.ADMIN_USER_IDS[0])
    msg.answer = AsyncMock()
    msg.bot = SimpleNamespace(send_message=AsyncMock())
    return msg


@pytest.fixture
def mock_callback():
    cb = MagicMock()
    cb.from_user = SimpleNamespace(id=admin_handlers.ADMIN_USER_IDS[0])
    cb.data = ""
    cb.answer = AsyncMock()
    cb.bot = SimpleNamespace(send_message=AsyncMock())
    cb.message = SimpleNamespace(edit_text=AsyncMock(), answer=AsyncMock())
    return cb


@pytest.fixture
def mock_session():
    return AsyncMock()


@pytest.mark.asyncio
async def test_is_admin_returns_true_for_admin_id():
    assert admin_handlers.is_admin(admin_handlers.ADMIN_USER_IDS[0]) is True


@pytest.mark.asyncio
async def test_is_admin_returns_false_for_random_id():
    assert admin_handlers.is_admin(999999999) is False


@pytest.mark.asyncio
async def test_admin_panel_blocked_for_non_admin(mock_message, mock_session):
    mock_message.from_user.id = 1
    await admin_handlers.admin_panel(mock_message, mock_session)
    mock_message.answer.assert_not_called()


@pytest.mark.asyncio
async def test_admin_panel_shows_stats_for_admin(monkeypatch, mock_message, mock_session):
    monkeypatch.setattr(
        crud,
        "get_dashboard_stats",
        AsyncMock(
            return_value={
                "users_count": 5,
                "products_count": 10,
                "new_opportunities": 2,
                "sent_today": 1,
            }
        ),
    )

    await admin_handlers.admin_panel(mock_message, mock_session)
    mock_message.answer.assert_called_once()
    assert "لوحة الإدارة" in mock_message.answer.call_args.args[0]


@pytest.mark.asyncio
async def test_admin_opportunities_empty(monkeypatch, mock_callback, mock_session):
    mock_callback.data = "admin_opportunities"
    monkeypatch.setattr(crud, "get_new_opportunities", AsyncMock(return_value=[]))

    await admin_handlers.admin_opportunities(mock_callback, mock_session)
    assert "لا توجد فرص" in mock_callback.message.edit_text.call_args.args[0]


@pytest.mark.asyncio
async def test_admin_opportunities_shows_list(monkeypatch, mock_callback, mock_session):
    mock_callback.data = "admin_opportunities"
    opportunity = SimpleNamespace(
        id=10,
        score=88,
        discount_percent=25,
        product=SimpleNamespace(name="Sample Product")
    )
    monkeypatch.setattr(crud, "get_new_opportunities", AsyncMock(return_value=[opportunity]))

    await admin_handlers.admin_opportunities(mock_callback, mock_session)
    mock_callback.message.edit_text.assert_called_once()
    assert "فرص جديدة" in mock_callback.message.edit_text.call_args.args[0]


@pytest.mark.asyncio
async def test_approve_opportunity_updates_status(monkeypatch, mock_callback, mock_session):
    mock_callback.data = "opp_approve:7"
    state = AsyncMock()
    state.get_data.return_value = {}

    approved = SimpleNamespace(
        id=7,
        discount_percent=30,
        product=SimpleNamespace(name="Deal Product"),
    )

    approve_mock = AsyncMock(return_value=approved)
    send_mock = AsyncMock()
    monkeypatch.setattr(crud, "approve_opportunity", approve_mock)
    monkeypatch.setattr(admin_handlers, "send_deal_to_subscribers", send_mock)

    await admin_handlers.approve_opportunity(mock_callback, state, mock_session)

    approve_mock.assert_awaited_once_with(mock_session, 7, None, None)


@pytest.mark.asyncio
async def test_reject_opportunity_updates_db(mock_callback, mock_session):
    mock_callback.data = "opp_reject:9"

    await admin_handlers.reject_opportunity(mock_callback, mock_session)

    mock_session.execute.assert_awaited_once()
    mock_session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_approve_store_request_notifies_user(mock_callback, mock_session):
    mock_callback.data = "store_req_approve:12"

    req = SimpleNamespace(user_id=22, store_url="https://example.com")
    user = SimpleNamespace(telegram_id=333)

    first = MagicMock()
    first.scalar_one_or_none.return_value = req
    second = MagicMock()
    second.scalar_one_or_none.return_value = user
    mock_session.execute = AsyncMock(side_effect=[None, first, second])

    await admin_handlers.approve_store_request(mock_callback, mock_session)

    mock_callback.bot.send_message.assert_awaited_once_with(
        333,
        "✅ تم اعتماد طلبك!\n\nتم إضافة المتجر: https://example.com",
    )


@pytest.mark.asyncio
async def test_broadcast_sends_to_all_users(monkeypatch, mock_message, mock_session):
    users = [
        SimpleNamespace(telegram_id=101),
        SimpleNamespace(telegram_id=102),
        SimpleNamespace(telegram_id=103),
    ]
    monkeypatch.setattr(crud, "get_all_users", AsyncMock(return_value=users))

    status_msg = SimpleNamespace(edit_text=AsyncMock())
    mock_message.text = "Hello users"
    mock_message.answer = AsyncMock(return_value=status_msg)
    state = AsyncMock()

    await admin_handlers.execute_broadcast(mock_message, state, mock_session)

    assert mock_message.bot.send_message.await_count == 3


@pytest.mark.asyncio
async def test_broadcast_blocked_for_non_admin(mock_message, mock_session):
    mock_message.from_user.id = 42
    state = AsyncMock()

    await admin_handlers.execute_broadcast(mock_message, state, mock_session)

    mock_message.bot.send_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_admin_panel_callback_shows_stats(monkeypatch, mock_callback, mock_session):
    monkeypatch.setattr(
        crud,
        "get_dashboard_stats",
        AsyncMock(
            return_value={
                "users_count": 10,
                "products_count": 20,
                "new_opportunities": 3,
                "sent_today": 4,
            }
        ),
    )

    await admin_handlers.admin_panel_callback(mock_callback, mock_session)
    assert "لوحة الإدارة" in mock_callback.message.edit_text.call_args.args[0]


@pytest.mark.asyncio
async def test_admin_opportunity_detail_not_found(mock_callback, mock_session):
    mock_callback.data = "admin_opp_detail:123"
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    mock_session.execute = AsyncMock(return_value=result)

    await admin_handlers.admin_opportunity_detail(mock_callback, mock_session)
    mock_callback.answer.assert_awaited_with("❌ الفرصة غير موجودة", show_alert=True)


@pytest.mark.asyncio
async def test_admin_opportunity_detail_shows_payload(monkeypatch, mock_callback, mock_session):
    mock_callback.data = "admin_opp_detail:6"
    opp = SimpleNamespace(
        id=6,
        product=SimpleNamespace(name="Product", url="https://p"),
        old_price=100.0,
        new_price=80.0,
        discount_percent=20.0,
        in_stock=True,
        score=95,
    )
    result = MagicMock()
    result.scalar_one_or_none.return_value = opp
    mock_session.execute = AsyncMock(return_value=result)

    class _Scorer:
        def get_score_label(self, _):
            return "excellent"

    monkeypatch.setattr("core.monitor.OpportunityScorer", _Scorer)

    await admin_handlers.admin_opportunity_detail(mock_callback, mock_session)
    text = mock_callback.message.edit_text.call_args.args[0]
    assert "تفاصيل الفرصة" in text


@pytest.mark.asyncio
async def test_add_affiliate_url_sets_state(mock_callback):
    mock_callback.data = "opp_add_affiliate:5"
    state = AsyncMock()

    await admin_handlers.add_affiliate_url(mock_callback, state)

    state.set_state.assert_awaited_once_with(admin_handlers.AffiliateStates.waiting_for_url)


@pytest.mark.asyncio
async def test_process_affiliate_url_updates_data(mock_message):
    mock_message.text = "https://aff"
    state = AsyncMock()
    state.get_data.return_value = {"opportunity_id": 6}

    await admin_handlers.process_affiliate_url(mock_message, state, AsyncMock())
    state.update_data.assert_awaited_once_with(affiliate_url="https://aff")


@pytest.mark.asyncio
async def test_send_deal_to_subscribers_handles_errors(mock_session):
    users = [SimpleNamespace(telegram_id=1), SimpleNamespace(telegram_id=2)]
    result = MagicMock()
    result.scalars.return_value.all.return_value = users
    mock_session.execute = AsyncMock(return_value=result)

    bot = SimpleNamespace(send_message=AsyncMock(side_effect=[None, Exception("x")]))
    opportunity = SimpleNamespace(
        product_id=10,
        affiliate_url=None,
        custom_message="msg",
        old_price=10.0,
        new_price=8.0,
        discount_percent=20.0,
        product=SimpleNamespace(name="N", url="https://u", in_stock=True),
    )

    await admin_handlers.send_deal_to_subscribers(bot, mock_session, opportunity)
    assert bot.send_message.await_count == 2


@pytest.mark.asyncio
async def test_admin_store_requests_empty(mock_callback, mock_session):
    mock_callback.data = "admin_store_requests"
    result = MagicMock()
    result.scalars.return_value.all.return_value = []
    mock_session.execute = AsyncMock(return_value=result)

    await admin_handlers.admin_store_requests(mock_callback, mock_session)
    assert "لا توجد طلبات" in mock_callback.message.edit_text.call_args.args[0]


@pytest.mark.asyncio
async def test_admin_store_requests_shows_list(mock_callback, mock_session):
    mock_callback.data = "admin_store_requests"
    req = SimpleNamespace(
        id=1,
        store_url="https://store.example/path",
        user=SimpleNamespace(username="tester", first_name="t"),
    )
    result = MagicMock()
    result.scalars.return_value.all.return_value = [req]
    mock_session.execute = AsyncMock(return_value=result)

    await admin_handlers.admin_store_requests(mock_callback, mock_session)
    assert "طلبات المتاجر" in mock_callback.message.edit_text.call_args.args[0]


@pytest.mark.asyncio
async def test_start_broadcast_admin(mock_callback):
    state = AsyncMock()
    await admin_handlers.start_broadcast(mock_callback, state)
    state.set_state.assert_awaited_once_with(admin_handlers.BroadcastStates.waiting_for_message)
