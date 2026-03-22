from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

import bot.handlers.user as user_handlers
import db.crud as crud


@pytest.fixture
def message():
    msg = SimpleNamespace()
    msg.text = ""
    msg.from_user = SimpleNamespace(id=123, username="u", first_name="First", last_name="Last")
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
async def test_cmd_start_creates_new_user(monkeypatch, message):
    monkeypatch.setattr(crud, "get_or_create_user", AsyncMock(return_value=SimpleNamespace(id=1)))
    state = AsyncMock()

    await user_handlers.cmd_start(message, AsyncMock(), state)

    message.answer.assert_awaited_once()
    assert "أهلاً" in message.answer.call_args.args[0]
    assert message.answer.call_args.kwargs["reply_markup"] is not None


@pytest.mark.asyncio
async def test_cmd_start_clears_state(monkeypatch, message):
    monkeypatch.setattr(crud, "get_or_create_user", AsyncMock(return_value=SimpleNamespace(id=1)))
    state = AsyncMock()

    await user_handlers.cmd_start(message, AsyncMock(), state)
    state.clear.assert_awaited_once()


@pytest.mark.asyncio
async def test_add_product_start_sets_state(message):
    state = AsyncMock()
    await user_handlers.add_product_start(message, state)
    state.set_state.assert_awaited_once_with(user_handlers.AddProductStates.waiting_for_url)


@pytest.mark.asyncio
async def test_process_product_url_invalid_url(message):
    message.text = "not a url"
    state = AsyncMock()

    await user_handlers.process_product_url(message, state, AsyncMock(), AsyncMock())

    assert "❌" in message.answer.call_args.args[0]
    state.clear.assert_not_called()


@pytest.mark.asyncio
async def test_process_product_url_plan_limit_reached(monkeypatch, message):
    message.text = "https://x.com/p"
    loading = SimpleNamespace(edit_text=AsyncMock())
    message.answer = AsyncMock(return_value=loading)
    user = SimpleNamespace(plan="free")
    monkeypatch.setattr(crud, "get_user_by_telegram_id", AsyncMock(return_value=user))
    monkeypatch.setattr(crud, "can_user_add_product", AsyncMock(return_value=False))

    state = AsyncMock()
    await user_handlers.process_product_url(message, state, AsyncMock(), AsyncMock())

    assert "وصلت للحد الأقصى" in loading.edit_text.call_args.args[0]
    state.clear.assert_awaited_once()


@pytest.mark.asyncio
async def test_process_product_url_scraping_fails(monkeypatch, message):
    message.text = "https://x.com/p"
    loading = SimpleNamespace(edit_text=AsyncMock())
    message.answer = AsyncMock(return_value=loading)
    user = SimpleNamespace(plan="basic")
    connector_manager = SimpleNamespace(scrape=AsyncMock(return_value=None))

    monkeypatch.setattr(crud, "get_user_by_telegram_id", AsyncMock(return_value=user))
    monkeypatch.setattr(crud, "can_user_add_product", AsyncMock(return_value=True))

    await user_handlers.process_product_url(message, AsyncMock(), AsyncMock(), connector_manager)

    assert "لم نتمكن من جلب" in loading.edit_text.call_args.args[0]


@pytest.mark.asyncio
async def test_process_product_url_success(monkeypatch, message):
    message.text = "https://x.com/p"
    loading = SimpleNamespace(edit_text=AsyncMock())
    message.answer = AsyncMock(return_value=loading)
    user = SimpleNamespace(plan="basic")
    connector_manager = SimpleNamespace(
        scrape=AsyncMock(
            return_value={
                "name": "Name",
                "price": 100,
                "currency": "USD",
                "in_stock": True,
                "rating": 4.8,
                "store": "Store",
            }
        )
    )

    monkeypatch.setattr(crud, "get_user_by_telegram_id", AsyncMock(return_value=user))
    monkeypatch.setattr(crud, "can_user_add_product", AsyncMock(return_value=True))

    state = AsyncMock()
    await user_handlers.process_product_url(message, state, AsyncMock(), connector_manager)

    assert "Name" in loading.edit_text.call_args.args[0]
    assert loading.edit_text.call_args.kwargs["reply_markup"] is not None


@pytest.mark.asyncio
async def test_start_product_monitoring_saves_to_db(monkeypatch, callback):
    session = AsyncMock()
    state = AsyncMock()
    state.get_data.return_value = {
        "product_url": "https://x.com/p",
        "product_data": {"name": "Item", "price": 20, "currency": "USD"},
    }
    monkeypatch.setattr(crud, "get_user_by_telegram_id", AsyncMock(return_value=SimpleNamespace(id=5)))
    monkeypatch.setattr(crud, "get_product_by_url", AsyncMock(return_value=None))
    create_mock = AsyncMock(return_value=SimpleNamespace(id=8, name="Item"))
    add_mock = AsyncMock(return_value=SimpleNamespace(id=50))
    monkeypatch.setattr(crud, "create_product", create_mock)
    monkeypatch.setattr(crud, "add_product_to_user", add_mock)

    await user_handlers.start_product_monitoring(callback, state, session)

    create_mock.assert_awaited_once()
    add_mock.assert_awaited_once_with(session, 5, 8, alert_types=["price_drop"])


@pytest.mark.asyncio
async def test_start_product_monitoring_existing_product(monkeypatch, callback):
    session = AsyncMock()
    state = AsyncMock()
    state.get_data.return_value = {
        "product_url": "https://x.com/p",
        "product_data": {"name": "Item", "price": 20, "currency": "USD"},
    }
    monkeypatch.setattr(crud, "get_user_by_telegram_id", AsyncMock(return_value=SimpleNamespace(id=5)))
    monkeypatch.setattr(crud, "get_product_by_url", AsyncMock(return_value=SimpleNamespace(id=8, name="Item")))
    create_mock = AsyncMock()
    add_mock = AsyncMock(return_value=SimpleNamespace(id=50))
    monkeypatch.setattr(crud, "create_product", create_mock)
    monkeypatch.setattr(crud, "add_product_to_user", add_mock)

    await user_handlers.start_product_monitoring(callback, state, session)

    create_mock.assert_not_called()
    add_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_product_detail_shows_correct_info(callback):
    callback.data = "product_detail:77"
    product = SimpleNamespace(
        name="P",
        current_price=30,
        lowest_price=20,
        highest_price=50,
        in_stock=True,
        currency="USD",
        last_scraped=None,
        url="https://x.com/prod",
    )
    user_product = SimpleNamespace(product=product, status=SimpleNamespace(value="active"))

    result = SimpleNamespace(
        scalar_one_or_none=MagicMock(return_value=user_product)
    )
    session = AsyncMock()
    session.execute = AsyncMock(return_value=result)

    await user_handlers.product_detail(callback, session)

    text = callback.message.edit_text.call_args.args[0]
    assert "السعر الحالي" in text
    assert "المخزون" in text
    assert "https://x.com/prod" in text


@pytest.mark.asyncio
async def test_pause_product_updates_status(monkeypatch, callback):
    callback.data = "product_pause:55"
    toggle_mock = AsyncMock()
    monkeypatch.setattr(crud, "toggle_monitoring", toggle_mock)
    monkeypatch.setattr(user_handlers, "product_detail", AsyncMock())

    session = AsyncMock()
    await user_handlers.pause_product(callback, session)

    toggle_mock.assert_awaited_once_with(session, 55, pause=True)


@pytest.mark.asyncio
async def test_delete_product_shows_confirmation(callback):
    callback.data = "product_delete:9"

    await user_handlers.delete_product_confirm(callback)

    assert callback.message.edit_text.call_args.kwargs["reply_markup"] is not None


@pytest.mark.asyncio
async def test_price_history_shows_records(callback):
    callback.data = "price_history:11"
    up = SimpleNamespace(product=SimpleNamespace(name="P"), product_id=1)
    h1 = SimpleNamespace(recorded_at=datetime.now(timezone.utc), price=10.5, currency="USD")
    h2 = SimpleNamespace(recorded_at=datetime.now(timezone.utc), price=11.5, currency="USD")
    h3 = SimpleNamespace(recorded_at=datetime.now(timezone.utc), price=12.5, currency="USD")

    first = SimpleNamespace(
        scalar_one_or_none=MagicMock(return_value=up)
    )
    second = SimpleNamespace(
        scalars=MagicMock(return_value=SimpleNamespace(all=MagicMock(return_value=[h1, h2, h3])))
    )

    session = AsyncMock()
    session.execute = AsyncMock(side_effect=[first, second])

    await user_handlers.show_price_history(callback, session)

    text = callback.message.edit_text.call_args.args[0]
    assert "10.50" in text
    assert "11.50" in text
    assert "12.50" in text


@pytest.mark.asyncio
async def test_go_home_clears_state(callback):
    state = AsyncMock()
    await user_handlers.go_home(callback, state)
    state.clear.assert_awaited_once()


@pytest.mark.asyncio
async def test_my_products_empty(monkeypatch, message):
    monkeypatch.setattr(crud, "get_user_by_telegram_id", AsyncMock(return_value=SimpleNamespace(id=1)))
    monkeypatch.setattr(crud, "get_user_products", AsyncMock(return_value=[]))

    await user_handlers.my_products(message, AsyncMock())
    assert "لا توجد منتجات" in message.answer.call_args.args[0]


@pytest.mark.asyncio
async def test_my_products_callback_empty(monkeypatch, callback):
    monkeypatch.setattr(crud, "get_user_by_telegram_id", AsyncMock(return_value=SimpleNamespace(id=1)))
    monkeypatch.setattr(crud, "get_user_products", AsyncMock(return_value=[]))

    await user_handlers.my_products_callback(callback, AsyncMock())
    assert "لا توجد منتجات" in callback.message.edit_text.call_args.args[0]


@pytest.mark.asyncio
async def test_resume_product_updates_status(monkeypatch, callback):
    callback.data = "product_resume:55"
    toggle_mock = AsyncMock()
    monkeypatch.setattr(crud, "toggle_monitoring", toggle_mock)
    monkeypatch.setattr(user_handlers, "product_detail", AsyncMock())

    session = AsyncMock()
    await user_handlers.resume_product(callback, session)
    toggle_mock.assert_awaited_once_with(session, 55, pause=False)


@pytest.mark.asyncio
async def test_cancel_product_add(callback):
    state = AsyncMock()
    await user_handlers.cancel_product_add(callback, state)
    state.clear.assert_awaited_once()


@pytest.mark.asyncio
async def test_delete_product_execute(monkeypatch, callback):
    callback.data = "confirm_delete:product:21"
    delete_mock = AsyncMock()
    monkeypatch.setattr(crud, "delete_user_product", delete_mock)

    await user_handlers.delete_product_execute(callback, AsyncMock())
    delete_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_cancel_delete(callback):
    await user_handlers.cancel_delete(callback)
    assert "تم الإلغاء" in callback.message.edit_text.call_args.args[0]


@pytest.mark.asyncio
async def test_price_history_missing_product(callback):
    callback.data = "price_history:11"
    first = SimpleNamespace(scalar_one_or_none=MagicMock(return_value=None))
    session = AsyncMock()
    session.execute = AsyncMock(return_value=first)

    await user_handlers.show_price_history(callback, session)
    callback.answer.assert_awaited_with("❌ المنتج غير موجود", show_alert=True)
