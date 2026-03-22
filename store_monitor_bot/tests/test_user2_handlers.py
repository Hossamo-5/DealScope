from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

import bot.handlers.user2 as user2_handlers
import db.crud as crud


@pytest.fixture
def message():
    msg = SimpleNamespace()
    msg.text = ""
    msg.from_user = SimpleNamespace(id=123)
    msg.answer = AsyncMock()
    msg.bot = SimpleNamespace(send_message=AsyncMock())
    return msg


@pytest.fixture
def callback():
    cb = SimpleNamespace()
    cb.data = ""
    cb.from_user = SimpleNamespace(id=123)
    cb.answer = AsyncMock()
    cb.message = SimpleNamespace(edit_text=AsyncMock(), answer=AsyncMock())
    return cb


@pytest.mark.asyncio
async def test_best_deals_empty(message):
    result = SimpleNamespace(
        scalars=MagicMock(return_value=SimpleNamespace(all=MagicMock(return_value=[])))
    )
    session = AsyncMock()
    session.execute = AsyncMock(return_value=result)

    await user2_handlers.best_deals(message, session)
    assert "لا توجد عروض" in message.answer.call_args.args[0]


@pytest.mark.asyncio
async def test_best_deals_shows_list(message):
    opps = [
        SimpleNamespace(id=1, discount_percent=10, new_price=90, product=SimpleNamespace(name="A")),
        SimpleNamespace(id=2, discount_percent=20, new_price=80, product=SimpleNamespace(name="B")),
        SimpleNamespace(id=3, discount_percent=30, new_price=70, product=SimpleNamespace(name="C")),
    ]
    result = SimpleNamespace(
        scalars=MagicMock(return_value=SimpleNamespace(all=MagicMock(return_value=opps)))
    )
    session = AsyncMock()
    session.execute = AsyncMock(return_value=result)

    await user2_handlers.best_deals(message, session)
    text = message.answer.call_args.args[0]
    assert "خصم" in text


@pytest.mark.asyncio
async def test_deal_detail_shows_info(callback):
    callback.data = "deal_detail:7"
    opp = SimpleNamespace(
        old_price=100,
        new_price=75,
        discount_percent=25,
        custom_message="x",
        affiliate_url="https://buy",
        product=SimpleNamespace(id=2, name="P", in_stock=True),
    )
    result = SimpleNamespace(
        scalar_one_or_none=MagicMock(return_value=opp)
    )
    session = AsyncMock()
    session.execute = AsyncMock(return_value=result)

    await user2_handlers.deal_detail(callback, session)
    text = callback.message.edit_text.call_args.args[0]
    assert "100.00" in text
    assert "75.00" in text
    assert "25.0%" in text


@pytest.mark.asyncio
async def test_watch_product_from_deal_plan_limit(monkeypatch, callback):
    callback.data = "watch_from_deal:5"
    monkeypatch.setattr(crud, "get_user_by_telegram_id", AsyncMock(return_value=SimpleNamespace(id=9)))
    monkeypatch.setattr(crud, "can_user_add_product", AsyncMock(return_value=False))
    add_mock = AsyncMock()
    monkeypatch.setattr(crud, "add_product_to_user", add_mock)

    await user2_handlers.watch_product_from_deal(callback, AsyncMock())

    callback.answer.assert_awaited()
    assert "وصلت للحد الأقصى" in callback.answer.call_args.args[0]
    add_mock.assert_not_called()


@pytest.mark.asyncio
async def test_watch_product_adds_to_monitoring(monkeypatch, callback):
    callback.data = "watch_from_deal:5"
    monkeypatch.setattr(crud, "get_user_by_telegram_id", AsyncMock(return_value=SimpleNamespace(id=9)))
    monkeypatch.setattr(crud, "can_user_add_product", AsyncMock(return_value=True))
    add_mock = AsyncMock()
    monkeypatch.setattr(crud, "add_product_to_user", add_mock)

    session = AsyncMock()
    await user2_handlers.watch_product_from_deal(callback, session)

    add_mock.assert_awaited_once_with(session, 9, 5)


@pytest.mark.asyncio
async def test_reports_page_shows_counts(monkeypatch, message):
    monkeypatch.setattr(crud, "get_user_by_telegram_id", AsyncMock(return_value=SimpleNamespace(id=1)))

    user_products_result = SimpleNamespace(all=MagicMock(return_value=[(11,), (12,)]))
    price_changes_result = SimpleNamespace(scalar_one=MagicMock(return_value=3))
    deals_result = SimpleNamespace(scalar_one=MagicMock(return_value=2))

    session = AsyncMock()
    session.execute = AsyncMock(side_effect=[user_products_result, price_changes_result, deals_result])

    await user2_handlers.reports(message, session)

    text = message.answer.call_args.args[0]
    assert "منتج" in text
    assert "تغيير" in text
    assert "عروض" in text


@pytest.mark.asyncio
async def test_monitor_category_free_plan_blocked(monkeypatch, message):
    message.text = "https://cat"
    monkeypatch.setattr(crud, "get_user_by_telegram_id", AsyncMock(return_value=SimpleNamespace(id=2, plan="free")))
    state = AsyncMock()

    await user2_handlers.process_category_url(message, state, AsyncMock())

    assert "غير متاحة في الخطة المجانية" in message.answer.call_args.args[0]
    state.clear.assert_awaited_once()


@pytest.mark.asyncio
async def test_monitor_category_success(monkeypatch, message):
    message.text = "https://cat"
    monkeypatch.setattr(crud, "get_user_by_telegram_id", AsyncMock(return_value=SimpleNamespace(id=2, plan="basic")))
    monkeypatch.setattr(crud, "add_category_to_user", AsyncMock(return_value=SimpleNamespace(id=4)))
    state = AsyncMock()

    await user2_handlers.process_category_url(message, state, AsyncMock())

    assert "تم إضافة الفئة" in message.answer.call_args.args[0]


@pytest.mark.asyncio
async def test_subscription_page_shows_current_plan(monkeypatch, message):
    monkeypatch.setattr(crud, "get_user_by_telegram_id", AsyncMock(return_value=SimpleNamespace(plan="professional")))

    await user2_handlers.subscription_page(message, AsyncMock())

    assert "احترافية" in message.answer.call_args.args[0]


@pytest.mark.asyncio
async def test_compare_plans_shows_table(callback):
    await user2_handlers.compare_plans(callback)
    assert "مجاني" in callback.message.edit_text.call_args.args[0]


@pytest.mark.asyncio
async def test_settings_shows_mute_status(monkeypatch, message):
    user = SimpleNamespace(first_name="N", username="u", plan="basic", muted=True)
    monkeypatch.setattr(crud, "get_user_by_telegram_id", AsyncMock(return_value=user))

    await user2_handlers.settings_page(message, AsyncMock())

    assert "مكتومة" in message.answer.call_args.args[0]


@pytest.mark.asyncio
async def test_toggle_mute_flips_value(monkeypatch, callback):
    user = SimpleNamespace(id=1, muted=False)
    monkeypatch.setattr(crud, "get_user_by_telegram_id", AsyncMock(return_value=user))

    session = AsyncMock()
    await user2_handlers.toggle_mute(callback, session)

    session.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_request_store_sets_state(message):
    state = AsyncMock()
    await user2_handlers.request_store_start(message, state)
    state.set_state.assert_awaited_once_with(user2_handlers.RequestStoreStates.waiting_for_url)


@pytest.mark.asyncio
async def test_process_store_request_saves_and_notifies_admin(monkeypatch, message):
    message.text = "https://new-store.com"
    user = SimpleNamespace(id=2, username="u", first_name="name")
    monkeypatch.setattr(crud, "get_user_by_telegram_id", AsyncMock(return_value=user))

    state = AsyncMock()
    session = AsyncMock()
    session.add = MagicMock()
    session.refresh = AsyncMock(side_effect=lambda obj: setattr(obj, "id", 99))

    await user2_handlers.process_store_request(message, state, session)

    message.bot.send_message.assert_awaited_once()


@pytest.mark.asyncio
async def test_best_deals_callback(callback):
    callback.data = "best_deals"
    result = SimpleNamespace(
        scalars=MagicMock(return_value=SimpleNamespace(all=MagicMock(return_value=[])))
    )
    session = AsyncMock()
    session.execute = AsyncMock(return_value=result)

    await user2_handlers.best_deals_callback(callback, session)
    assert "أفضل العروض" in callback.message.edit_text.call_args.args[0]


@pytest.mark.asyncio
async def test_subscription_callback(monkeypatch, callback):
    callback.data = "subscription"
    monkeypatch.setattr(crud, "get_user_by_telegram_id", AsyncMock(return_value=SimpleNamespace(plan="basic")))

    await user2_handlers.subscription_callback(callback, AsyncMock())
    assert "الاشتراكات" in callback.message.edit_text.call_args.args[0]


@pytest.mark.asyncio
async def test_plan_info_basic(callback):
    callback.data = "plan_info:basic"
    await user2_handlers.plan_info(callback)
    assert "الاشتراك الأساسي" in callback.message.edit_text.call_args.args[0]


@pytest.mark.asyncio
async def test_upgrade_plan(callback):
    callback.data = "upgrade:professional"
    await user2_handlers.upgrade_plan(callback)
    assert "ترقية الاشتراك" in callback.message.edit_text.call_args.args[0]


@pytest.mark.asyncio
async def test_monitor_store_free_blocked(monkeypatch, message):
    monkeypatch.setattr(crud, "get_user_by_telegram_id", AsyncMock(return_value=SimpleNamespace(plan="free")))
    await user2_handlers.monitor_store_start(message, AsyncMock(), AsyncMock())
    assert "الاشتراك الاحترافي" in message.answer.call_args.args[0]


@pytest.mark.asyncio
async def test_help_supported_sites(callback):
    await user2_handlers.help_supported_sites(callback)
    assert "المواقع المدعومة" in callback.message.edit_text.call_args.args[0]
