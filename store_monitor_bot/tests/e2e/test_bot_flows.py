"""
Bot User Flow Simulation Tests
================================
End-to-end Telegram user journey tests using the real handlers
with mocked Telegram API and an in-memory SQLite database.
Each flow test simulates multi-step conversations.
"""

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from aiogram.types import (
    Message, CallbackQuery, User as TgUser, Chat,
    Update,
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage

from db.models import (
    Base, User, Product, UserProduct, StoreRequest,
    PlanType, MonitoringStatus, OpportunityStatus, Opportunity,
)
from db.crud import (
    get_or_create_user,
    get_user_by_telegram_id,
    create_product,
    add_product_to_user,
    get_user_products,
    count_user_products,
    can_user_add_product,
    create_opportunity,
    approve_opportunity,
)
from config.settings import ADMIN_USER_IDS, ADMIN_GROUP_ID


# ──────────────────────────────────────────────────────
# Test-scoped DB fixture
# ──────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def db():
    """In-memory SQLite engine + session for each test."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    SessionLocal = async_sessionmaker(engine, expire_on_commit=False)
    async with SessionLocal() as session:
        yield session
        await session.rollback()

    await engine.dispose()


# ──────────────────────────────────────────────────────
# Helpers to create fake Telegram objects
# ──────────────────────────────────────────────────────

def _make_tg_user(user_id: int = 111222333, first_name: str = "TestUser",
                   username: str = "testuser"):
    return TgUser(id=user_id, is_bot=False, first_name=first_name, username=username)


def _make_message(text: str, user_id: int = 111222333, **kw) -> Message:
    tg_user = _make_tg_user(user_id, **{k: v for k, v in kw.items() if k in ("first_name", "username")})
    chat = Chat(id=user_id, type="private")
    msg = MagicMock(spec=Message)
    msg.text = text
    msg.from_user = tg_user
    msg.chat = chat
    msg.answer = AsyncMock()
    msg.reply = AsyncMock()
    return msg


def _make_callback(data: str, user_id: int = 111222333) -> CallbackQuery:
    tg_user = _make_tg_user(user_id)
    chat = Chat(id=user_id, type="private")
    msg = MagicMock(spec=Message)
    msg.edit_text = AsyncMock()
    msg.answer = AsyncMock()
    msg.chat = chat

    cb = MagicMock(spec=CallbackQuery)
    cb.data = data
    cb.from_user = tg_user
    cb.message = msg
    cb.answer = AsyncMock()
    return cb


@pytest_asyncio.fixture
async def fsm_state():
    storage = MemoryStorage()
    # key = (chat_id, user_id)
    return FSMContext(
        storage=storage,
        key=MagicMock(chat_id=111222333, user_id=111222333, bot_id=1),
    )


@pytest_asyncio.fixture
async def connector_mock():
    cm = AsyncMock()
    cm.scrape = AsyncMock(return_value={
        "name": "Test Product - iPhone 15",
        "price": 3999.0,
        "currency": "SAR",
        "in_stock": True,
        "image_url": "https://example.com/img.jpg",
        "rating": 4.5,
        "review_count": 1200,
        "store": "amazon.sa",
    })
    cm.detect_store_type = MagicMock(return_value="amazon")
    return cm


@pytest_asyncio.fixture
async def bot_mock():
    bot = AsyncMock()
    bot.send_message = AsyncMock()
    return bot


# ──────────────────────────────────────────────────────
# FLOW 1: Complete Product Monitoring Setup
# ──────────────────────────────────────────────────────

class TestFlowAddProductComplete:
    @pytest.mark.asyncio
    async def test_step1_start_command(self, db):
        """User sends /start → welcome message + main menu keyboard."""
        from bot.handlers.user import cmd_start

        msg = _make_message("/start")
        storage = MemoryStorage()
        state = FSMContext(
            storage=storage,
            key=MagicMock(chat_id=111222333, user_id=111222333, bot_id=1),
        )

        await cmd_start(msg, session=db, state=state)

        msg.answer.assert_called_once()
        call_args = msg.answer.call_args
        text = call_args[0][0]
        assert "أهلاً بك" in text
        assert call_args[1].get("reply_markup") is not None

    @pytest.mark.asyncio
    async def test_step2_add_product_prompt(self, db, fsm_state):
        """User taps '➕ إضافة منتج' → prompt for URL."""
        from bot.handlers.user import add_product_start

        msg = _make_message("➕ إضافة منتج")
        await add_product_start(msg, state=fsm_state)

        msg.answer.assert_called_once()
        text = msg.answer.call_args[0][0]
        assert "رابط المنتج" in text

    @pytest.mark.asyncio
    async def test_step3_invalid_url_error(self, db, fsm_state):
        """User sends invalid URL → error, state kept."""
        from bot.handlers.user import process_product_url, AddProductStates

        await fsm_state.set_state(AddProductStates.waiting_for_url)

        msg = _make_message("not-a-url")
        await process_product_url(msg, state=fsm_state, session=db,
                                   connector_manager=AsyncMock())

        msg.answer.assert_called_once()
        text = msg.answer.call_args[0][0]
        assert "غير صالح" in text

        # State should still be waiting
        current = await fsm_state.get_state()
        assert current == AddProductStates.waiting_for_url

    @pytest.mark.asyncio
    async def test_step4_valid_url_shows_product(self, db, fsm_state, connector_mock):
        """User sends valid URL → product info displayed."""
        from bot.handlers.user import process_product_url, AddProductStates

        # Create user in DB first
        await get_or_create_user(db, telegram_id=111222333, username="testuser",
                                  first_name="TestUser")
        await fsm_state.set_state(AddProductStates.waiting_for_url)

        msg = _make_message("https://amazon.com/dp/B123456789")
        # loading_msg = msg.answer return value
        loading_msg = AsyncMock()
        loading_msg.edit_text = AsyncMock()
        msg.answer = AsyncMock(return_value=loading_msg)

        await process_product_url(msg, state=fsm_state, session=db,
                                   connector_manager=connector_mock)

        connector_mock.scrape.assert_called_once_with("https://amazon.com/dp/B123456789")
        loading_msg.edit_text.assert_called_once()
        text = loading_msg.edit_text.call_args[0][0]
        assert "تم التعرف" in text
        assert "iPhone" in text

    @pytest.mark.asyncio
    async def test_step5_start_monitoring_saves_product(self, db, fsm_state, connector_mock):
        """User clicks '✅ بدء المراقبة' → product saved in DB."""
        from bot.handlers.user import start_product_monitoring

        user = await get_or_create_user(db, telegram_id=111222333)

        # Simulate state data from previous step
        await fsm_state.update_data(
            product_url="https://amazon.com/dp/B123456789",
            product_data={
                "name": "Test Product - iPhone 15",
                "price": 3999.0,
                "currency": "SAR",
                "in_stock": True,
                "rating": 4.5,
                "review_count": 1200,
            },
        )

        cb = _make_callback("product_start_monitoring")
        await start_product_monitoring(cb, state=fsm_state, session=db)

        # Product should be in DB
        user_products = await get_user_products(db, user.id)
        assert len(user_products) == 1
        assert user_products[0].product.name == "Test Product - iPhone 15"
        assert user_products[0].product.current_price == 3999.0

        cb.message.edit_text.assert_called_once()
        text = cb.message.edit_text.call_args[0][0]
        assert "تمت الإضافة" in text

    @pytest.mark.asyncio
    async def test_step6_my_products_shows_product(self, db):
        """User taps '📦 منتجاتي' → product appears in list."""
        from bot.handlers.user import my_products

        user = await get_or_create_user(db, telegram_id=111222333)
        product = await create_product(db, url="https://amazon.com/dp/B1",
                                        name="iPhone 15", price=3999.0)
        await add_product_to_user(db, user.id, product.id)

        msg = _make_message("📦 منتجاتي")
        await my_products(msg, session=db)

        msg.answer.assert_called_once()
        text = msg.answer.call_args[0][0]
        assert "iPhone 15" in text
        assert "1 منتج" in text


# ──────────────────────────────────────────────────────
# FLOW 2: Product Alert Configuration
# ──────────────────────────────────────────────────────

class TestFlowConfigureAlerts:
    @pytest.mark.asyncio
    async def test_product_detail_shows_alert_button(self, db):
        """Clicking product → detail page with alert setup button."""
        from bot.handlers.user import product_detail

        user = await get_or_create_user(db, telegram_id=111222333)
        product = await create_product(db, url="https://amazon.com/dp/B2",
                                        name="Galaxy S24", price=2999.0,
                                        in_stock=True)
        up = await add_product_to_user(db, user.id, product.id)

        cb = _make_callback(f"product_detail:{up.id}")
        await product_detail(cb, session=db)

        cb.message.edit_text.assert_called_once()
        text = cb.message.edit_text.call_args[0][0]
        assert "Galaxy S24" in text
        assert "2,999" in text

        # Keyboard should have alert setup button
        keyboard = cb.message.edit_text.call_args[1].get("reply_markup")
        assert keyboard is not None


# ──────────────────────────────────────────────────────
# FLOW 3: Subscription Journey
# ──────────────────────────────────────────────────────

class TestFlowSubscriptionJourney:
    @pytest.mark.asyncio
    async def test_step1_subscription_shows_current_plan(self, db):
        """User taps '💳 الاشتراك' → current plan shown."""
        from bot.handlers.user2 import subscription_page

        await get_or_create_user(db, telegram_id=111222333)

        msg = _make_message("💳 الاشتراك")
        await subscription_page(msg, session=db)

        msg.answer.assert_called_once()
        text = msg.answer.call_args[0][0]
        assert "مجانية" in text  # free plan

    @pytest.mark.asyncio
    async def test_step2_plan_info_shows_details(self, db):
        """Click on a plan → details displayed."""
        from bot.handlers.user2 import plan_info

        cb = _make_callback("plan_info:basic")
        await plan_info(cb)

        cb.message.edit_text.assert_called_once()
        text = cb.message.edit_text.call_args[0][0]
        assert "الأساسي" in text
        assert "50" in text  # 50 products
        assert "30" in text  # 30 min interval

    @pytest.mark.asyncio
    async def test_step3_compare_plans_table(self, db):
        """Click '📊 مقارنة الخطط' → comparison table."""
        from bot.handlers.user2 import compare_plans

        cb = _make_callback("compare_plans")
        await compare_plans(cb)

        cb.message.edit_text.assert_called_once()
        text = cb.message.edit_text.call_args[0][0]
        assert "مقارنة" in text
        assert "مجاني" in text
        assert "أساسي" in text
        assert "احترافي" in text

    @pytest.mark.asyncio
    async def test_step4_upgrade_shows_contact(self, db):
        """Click '⬆️ ترقية' → upgrade message."""
        from bot.handlers.user2 import upgrade_plan

        cb = _make_callback("upgrade:basic")
        await upgrade_plan(cb)

        cb.message.edit_text.assert_called_once()
        text = cb.message.edit_text.call_args[0][0]
        assert "ترقية" in text


# ──────────────────────────────────────────────────────
# FLOW 4: Free Plan Restriction Enforcement
# ──────────────────────────────────────────────────────

class TestFlowPlanLimitsEnforced:
    @pytest.mark.asyncio
    async def test_free_plan_limit_blocks_add(self, db, fsm_state, connector_mock):
        """User at max product limit gets blocked from adding more."""
        from bot.handlers.user import process_product_url, AddProductStates

        user = await get_or_create_user(db, telegram_id=111222333)

        # Add 3 products (free plan limit)
        for i in range(3):
            p = await create_product(db, url=f"https://example.com/p{i}",
                                      name=f"Product {i}", price=100.0)
            await add_product_to_user(db, user.id, p.id)

        assert not await can_user_add_product(db, user)

        # Try adding a 4th
        await fsm_state.set_state(AddProductStates.waiting_for_url)
        msg = _make_message("https://amazon.com/dp/B999999")
        loading_msg = AsyncMock()
        loading_msg.edit_text = AsyncMock()
        msg.answer = AsyncMock(return_value=loading_msg)

        await process_product_url(msg, state=fsm_state, session=db,
                                   connector_manager=connector_mock)

        loading_msg.edit_text.assert_called_once()
        text = loading_msg.edit_text.call_args[0][0]
        assert "وصلت للحد الأقصى" in text

        # Product should NOT have been saved
        count = await count_user_products(db, user.id)
        assert count == 3


# ──────────────────────────────────────────────────────
# FLOW 5: Store Request Flow
# ──────────────────────────────────────────────────────

class TestFlowRequestStore:
    @pytest.mark.asyncio
    async def test_step1_request_store_prompt(self, db, fsm_state):
        """User taps '🏬 طلب إضافة متجر' → prompt for URL."""
        from bot.handlers.user2 import request_store_start

        msg = _make_message("🏬 طلب إضافة متجر")
        await request_store_start(msg, state=fsm_state)

        msg.answer.assert_called_once()
        text = msg.answer.call_args[0][0]
        assert "رابط المتجر" in text

    @pytest.mark.asyncio
    async def test_step2_submit_store_url(self, db, fsm_state):
        """User sends store URL → request saved in DB."""
        from bot.handlers.user2 import process_store_request, RequestStoreStates

        user = await get_or_create_user(db, telegram_id=111222333)
        await fsm_state.set_state(RequestStoreStates.waiting_for_url)

        msg = _make_message("https://www.noon.com")
        # Mock bot.send_message for admin notification
        with patch("bot.handlers.user2.router") as _:
            await process_store_request(msg, state=fsm_state, session=db)

        msg.answer.assert_called()

        # StoreRequest should be in DB
        from sqlalchemy import select
        result = await db.execute(select(StoreRequest))
        requests = result.scalars().all()
        assert len(requests) == 1
        assert requests[0].store_url == "https://www.noon.com"

    @pytest.mark.asyncio
    async def test_invalid_store_url_rejected(self, db, fsm_state):
        """Non-URL store request should be rejected."""
        from bot.handlers.user2 import process_store_request, RequestStoreStates

        await fsm_state.set_state(RequestStoreStates.waiting_for_url)
        msg = _make_message("not a url")
        await process_store_request(msg, state=fsm_state, session=db)

        msg.answer.assert_called_once()
        text = msg.answer.call_args[0][0]
        assert "غير صالح" in text


# ──────────────────────────────────────────────────────
# FLOW 6: Admin Opportunity Approval (DB layer)
# ──────────────────────────────────────────────────────

class TestFlowAdminApproveOpportunity:
    @pytest.mark.asyncio
    async def test_opportunity_lifecycle(self, db):
        """Create opportunity → approve → verify status change."""
        product = await create_product(
            db, url="https://amazon.com/dp/OPP1",
            name="Deal Product", price=500.0,
        )

        opp = await create_opportunity(
            db, product_id=product.id,
            old_price=1000.0, new_price=500.0,
            score=85.0,
        )
        assert opp.status == OpportunityStatus.NEW
        assert opp.discount_percent == 50.0

        approved = await approve_opportunity(
            db, opp.id,
            affiliate_url="https://affiliate.example.com/link",
            custom_message="عرض حصري!",
        )
        assert approved.status == OpportunityStatus.APPROVED
        assert approved.affiliate_url == "https://affiliate.example.com/link"

    @pytest.mark.asyncio
    async def test_opportunity_scoring(self, db):
        """Test that the scorer produces expected labels."""
        from core.monitor import OpportunityScorer

        scorer = OpportunityScorer()

        # Excellent score: huge discount, high rating, many reviews, in stock, lowest price
        score = scorer.calculate_score(
            {"rating": 4.8, "review_count": 2000, "in_stock": True, "lowest_price": 500},
            old_price=1000.0, new_price=500.0,
        )
        label = scorer.get_score_label(score)
        assert score >= 90
        assert "ممتاز" in label

        # Low score: small discount, no rating
        score2 = scorer.calculate_score(
            {"rating": None, "review_count": 0, "in_stock": False},
            old_price=100.0, new_price=90.0,
        )
        assert score2 < 70


# ──────────────────────────────────────────────────────
# FLOW 7: Settings & Mute Toggle
# ──────────────────────────────────────────────────────

class TestFlowSettingsMute:
    @pytest.mark.asyncio
    async def test_step1_settings_page(self, db):
        """User taps '⚙️ الإعدادات' → settings displayed."""
        from bot.handlers.user2 import settings_page

        await get_or_create_user(db, telegram_id=111222333, first_name="Ali")

        msg = _make_message("⚙️ الإعدادات")
        await settings_page(msg, session=db)

        msg.answer.assert_called_once()
        text = msg.answer.call_args[0][0]
        assert "إعدادات" in text
        assert "مفعلة" in text  # muted=False by default

    @pytest.mark.asyncio
    async def test_step2_toggle_mute_on(self, db):
        """Click '🔕 كتم التنبيهات' → muted=True in DB."""
        from bot.handlers.user2 import toggle_mute

        user = await get_or_create_user(db, telegram_id=111222333)
        assert user.muted is False

        cb = _make_callback("settings_mute")
        await toggle_mute(cb, session=db)

        # Refresh from DB
        updated = await get_user_by_telegram_id(db, 111222333)
        assert updated.muted is True

    @pytest.mark.asyncio
    async def test_step3_toggle_mute_off(self, db):
        """Click again → muted=False."""
        from bot.handlers.user2 import toggle_mute
        from sqlalchemy import update as sa_update

        user = await get_or_create_user(db, telegram_id=111222333)
        # Pre-set muted=True
        await db.execute(sa_update(User).where(User.id == user.id).values(muted=True))
        await db.commit()

        cb = _make_callback("settings_mute")
        await toggle_mute(cb, session=db)

        updated = await get_user_by_telegram_id(db, 111222333)
        assert updated.muted is False


# ──────────────────────────────────────────────────────
# FLOW: Best Deals Display
# ──────────────────────────────────────────────────────

class TestFlowBestDeals:
    @pytest.mark.asyncio
    async def test_no_deals_shows_empty(self, db):
        """Best deals with no approved opportunities → empty message."""
        from bot.handlers.user2 import best_deals

        msg = _make_message("🔥 أفضل العروض")
        await best_deals(msg, session=db)

        msg.answer.assert_called_once()
        text = msg.answer.call_args[0][0]
        assert "أفضل العروض" in text

    @pytest.mark.asyncio
    async def test_deals_displayed_when_available(self, db):
        """Approved opportunities show up in best deals."""
        from bot.handlers.user2 import best_deals

        product = await create_product(db, url="https://amazon.com/dp/DEAL1",
                                        name="Super Deal Product", price=500.0,
                                        in_stock=True)
        opp = await create_opportunity(db, product_id=product.id,
                                        old_price=1000.0, new_price=500.0,
                                        score=85.0)
        await approve_opportunity(db, opp.id)

        msg = _make_message("🔥 أفضل العروض")
        await best_deals(msg, session=db)

        msg.answer.assert_called_once()
        text = msg.answer.call_args[0][0]
        assert "Super Deal" in text
        assert "50%" in text


# ──────────────────────────────────────────────────────
# FLOW: Reports
# ──────────────────────────────────────────────────────

class TestFlowReports:
    @pytest.mark.asyncio
    async def test_reports_page(self, db):
        """User taps '📊 التقارير' → report displayed."""
        from bot.handlers.user2 import reports

        await get_or_create_user(db, telegram_id=111222333)

        msg = _make_message("📊 التقارير")
        await reports(msg, session=db)

        msg.answer.assert_called_once()
        text = msg.answer.call_args[0][0]
        assert "تقرير" in text
        assert "تحت المراقبة" in text


# ──────────────────────────────────────────────────────
# FLOW: Category monitoring (plan check)
# ──────────────────────────────────────────────────────

class TestFlowCategoryMonitoring:
    @pytest.mark.asyncio
    async def test_free_user_blocked_from_categories(self, db, fsm_state):
        """Free plan user cannot monitor categories."""
        from bot.handlers.user2 import process_category_url, AddCategoryStates

        await get_or_create_user(db, telegram_id=111222333)
        await fsm_state.set_state(AddCategoryStates.waiting_for_url)

        msg = _make_message("https://amazon.sa/s?rh=n:12345")
        await process_category_url(msg, state=fsm_state, session=db)

        msg.answer.assert_called_once()
        text = msg.answer.call_args[0][0]
        assert "غير متاح" in text or "ترقية" in text
