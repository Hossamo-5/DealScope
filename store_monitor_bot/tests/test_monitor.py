"""
Tests for Monitoring Engine and Opportunity Scorer
==================================================
Tests core/monitor.py functionality
"""

import pytest
from unittest.mock import AsyncMock, patch
from datetime import datetime, timedelta, timezone

from core.monitor import OpportunityScorer, MonitoringEngine
from db.models import MonitoringStatus


class _SessionCtx:
    def __init__(self, session):
        self._session = session

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, exc_type, exc, tb):
        return False


def _session_factory(session):
    return lambda: _SessionCtx(session)


class TestOpportunityScorerCalculateScore:
    """Test OpportunityScorer.calculate_score method."""

    def test_calculate_score_perfect_conditions(self):
        """Test calculate_score: 50% discount + 5-star rating + 1000 reviews + in-stock + lowest price = ~100."""
        scorer = OpportunityScorer()

        product_data = {
            "rating": 5.0,
            "review_count": 1000,
            "in_stock": True,
            "lowest_price": 80.0  # Same as new price, so lowest price ever
        }

        score = scorer.calculate_score(product_data, old_price=100.0, new_price=50.0)

        # 50% discount = 40 points
        # 5-star rating = 20 points
        # 1000 reviews = 15 points
        # In stock = 10 points
        # Lowest price ever = 15 points
        # Total should be close to 100
        assert score >= 95  # Allow some floating point tolerance

    def test_calculate_score_zero_discount(self):
        """Test calculate_score: 0% discount returns 0 discount points."""
        scorer = OpportunityScorer()

        product_data = {
            "rating": 5.0,
            "review_count": 1000,
            "in_stock": True,
            "lowest_price": 100.0
        }

        score = scorer.calculate_score(product_data, old_price=100.0, new_price=100.0)

        # 0% discount = 0 points from discount
        # Other factors should still contribute
        assert score > 0  # But not the full discount points
        assert score <= 60  # Should be less than or equal to max without discount

    def test_calculate_score_no_rating(self):
        """Test calculate_score with missing rating."""
        scorer = OpportunityScorer()

        product_data = {
            "rating": None,
            "review_count": 100,
            "in_stock": True,
            "lowest_price": 50.0
        }

        score = scorer.calculate_score(product_data, old_price=100.0, new_price=50.0)

        # Should still get discount and other points, but no rating points
        assert score > 40  # Discount points
        assert score < 85  # Less than with rating

    def test_calculate_score_out_of_stock(self):
        """Test calculate_score with out-of-stock product."""
        scorer = OpportunityScorer()

        product_data = {
            "rating": 4.0,
            "review_count": 500,
            "in_stock": False,
            "lowest_price": 50.0
        }

        score = scorer.calculate_score(product_data, old_price=100.0, new_price=50.0)

        # Should not get stock availability points
        assert score < 90  # Less than with stock


class TestOpportunityScorerGetScoreLabel:
    """Test OpportunityScorer.get_score_label method."""

    def test_get_score_label_excellent(self):
        """Test get_score_label: score 95 → '🔥 ممتاز'."""
        scorer = OpportunityScorer()

        assert scorer.get_score_label(95) == "🔥 ممتاز"
        assert scorer.get_score_label(90) == "🔥 ممتاز"
        assert scorer.get_score_label(100) == "🔥 ممتاز"

    def test_get_score_label_good(self):
        """Test get_score_label: score 75 → '✅ جيد'."""
        scorer = OpportunityScorer()

        assert scorer.get_score_label(75) == "✅ جيد"
        assert scorer.get_score_label(80) == "✅ جيد"
        assert scorer.get_score_label(89) == "✅ جيد"

    def test_get_score_label_normal(self):
        """Test get_score_label: score 50 → 'ℹ️ عادي'."""
        scorer = OpportunityScorer()

        assert scorer.get_score_label(50) == "ℹ️ عادي"
        assert scorer.get_score_label(0) == "ℹ️ عادي"
        assert scorer.get_score_label(69) == "ℹ️ عادي"


class TestMonitoringEngineNotifyUsers:
    """Test MonitoringEngine._notify_users method."""

    @pytest.mark.asyncio
    async def test_notify_users_price_drop_alert(self, async_session, mock_bot):
        """Test _notify_users: sends alert when price_drop alert is set and price decreased."""
        from db.models import User, Product, UserProduct, AlertType

        # Create test data
        user = User(telegram_id=123456, muted=False, is_active=True, is_banned=False)
        product = Product(
            id=1, url="https://test.com", name="Test Product",
            current_price=80.0
        )
        user_product = UserProduct(
            id=1, user_id=user.id, product_id=product.id,
            alert_types=[AlertType.PRICE_DROP.value]
        )

        async_session.add(user)
        async_session.add(product)
        await async_session.commit()
        user_product.user_id = user.id
        user_product.product_id = product.id
        async_session.add(user_product)
        await async_session.commit()

        # Create monitoring engine
        engine = MonitoringEngine(_session_factory(async_session), mock_bot, None)
        scorer = OpportunityScorer()
        engine.scorer = scorer

        # Test price drop notification
        await engine._notify_users(
            async_session, product.id,
            old_price=100.0, new_price=80.0,  # Price dropped
            old_stock=True, new_stock=True
        )

        # Should have sent a message
        mock_bot.send_message.assert_called_once()
        call_args = mock_bot.send_message.call_args
        assert user.telegram_id in call_args[0]
        assert "انخفاض في السعر" in call_args[0][1]
        assert "80.00" in call_args[0][1]

    @pytest.mark.asyncio
    async def test_notify_users_muted_user(self, async_session, mock_bot):
        """Test _notify_users: does NOT send when muted=True."""
        from db.models import User, Product, UserProduct, AlertType

        # Create muted user
        user = User(telegram_id=123456, muted=True, is_active=True, is_banned=False)
        product = Product(
            id=1, url="https://test.com", name="Test Product",
            current_price=80.0
        )
        user_product = UserProduct(
            id=1, user_id=user.id, product_id=product.id,
            alert_types=[AlertType.PRICE_DROP.value]
        )

        async_session.add(user)
        async_session.add(product)
        await async_session.commit()
        user_product.user_id = user.id
        user_product.product_id = product.id
        async_session.add(user_product)
        await async_session.commit()

        engine = MonitoringEngine(_session_factory(async_session), mock_bot, None)

        await engine._notify_users(
            async_session, product.id,
            old_price=100.0, new_price=80.0,
            old_stock=True, new_stock=True
        )

        # Should NOT have sent a message
        mock_bot.send_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_notify_users_back_in_stock(self, async_session, mock_bot):
        """Test _notify_users: sends back_in_stock alert only when stock changes False→True."""
        from db.models import User, Product, UserProduct, AlertType

        user = User(telegram_id=123456, muted=False, is_active=True, is_banned=False)
        product = Product(
            id=1, url="https://test.com", name="Test Product"
        )
        user_product = UserProduct(
            id=1, user_id=user.id, product_id=product.id,
            alert_types=[AlertType.BACK_IN_STOCK.value]
        )

        async_session.add(user)
        async_session.add(product)
        await async_session.commit()
        user_product.user_id = user.id
        user_product.product_id = product.id
        async_session.add(user_product)
        await async_session.commit()

        engine = MonitoringEngine(_session_factory(async_session), mock_bot, None)

        # Test stock change from False to True
        await engine._notify_users(
            async_session, product.id,
            old_price=100.0, new_price=100.0,
            old_stock=False, new_stock=True  # Stock back in
        )

        # Should have sent back in stock message
        mock_bot.send_message.assert_called_once()
        call_args = mock_bot.send_message.call_args
        assert "عاد للمخزون" in call_args[0][1]

    @pytest.mark.asyncio
    async def test_notify_users_no_back_in_stock_on_same_status(self, async_session, mock_bot):
        """Test _notify_users: does not send back_in_stock when stock doesn't change."""
        from db.models import User, Product, UserProduct, AlertType

        user = User(telegram_id=123456, muted=False, is_active=True, is_banned=False)
        product = Product(
            id=1, url="https://test.com", name="Test Product"
        )
        user_product = UserProduct(
            id=1, user_id=user.id, product_id=product.id,
            alert_types=[AlertType.BACK_IN_STOCK.value]
        )

        async_session.add(user)
        async_session.add(product)
        await async_session.commit()
        user_product.user_id = user.id
        user_product.product_id = product.id
        async_session.add(user_product)
        await async_session.commit()

        engine = MonitoringEngine(_session_factory(async_session), mock_bot, None)

        # Test no stock change (True to True)
        await engine._notify_users(
            async_session, product.id,
            old_price=100.0, new_price=100.0,
            old_stock=True, new_stock=True  # No change
        )

        # Should NOT have sent a message
        mock_bot.send_message.assert_not_called()


class TestMonitoringEngineScanCycle:
    """Test MonitoringEngine scan cycle functionality."""

    @pytest.mark.asyncio
    async def test_run_scan_cycle_no_products(self, async_session, mock_bot, mock_connector_manager):
        """Test run_scan_cycle with no products due for scan."""
        engine = MonitoringEngine(_session_factory(async_session), mock_bot, mock_connector_manager)

        # Should not crash with no products
        await engine.run_scan_cycle()

        # Should not call connector
        mock_connector_manager.scrape.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_products_due_for_scan(self, async_session, mock_bot, mock_connector_manager):
        """Test _get_products_due_for_scan method."""
        from db.models import Product, UserProduct, User

        # Create user and product
        user = User(telegram_id=999)
        product = Product(
            url="https://scan-test.com",
            last_scraped=datetime.now(timezone.utc) - timedelta(minutes=70)  # Old enough
        )
        user_product = UserProduct(
            user_id=user.id, product_id=product.id,
            status=MonitoringStatus.ACTIVE
        )

        async_session.add(user)
        async_session.add(product)
        await async_session.commit()
        user_product.user_id = user.id
        user_product.product_id = product.id
        async_session.add(user_product)
        await async_session.commit()

        engine = MonitoringEngine(_session_factory(async_session), mock_bot, mock_connector_manager)

        products = await engine._get_products_due_for_scan(async_session)

        assert len(products) == 1
        assert products[0].id == product.id

    @pytest.mark.asyncio
    async def test_scan_product_success(self, async_session, mock_bot, mock_connector_manager, monkeypatch):
        """Test _scan_product enqueues a Celery scrape job successfully."""
        from db.models import Product, UserProduct, User
        from unittest.mock import MagicMock

        # Create user and product
        user = User(telegram_id=888)
        product = Product(
            url="https://success-test.com",
            current_price=100.0,
            in_stock=True
        )
        user_product = UserProduct(
            user_id=user.id, product_id=product.id,
            status=MonitoringStatus.ACTIVE
        )

        async_session.add(user)
        async_session.add(product)
        await async_session.commit()
        user_product.user_id = user.id
        user_product.product_id = product.id
        async_session.add(user_product)
        await async_session.commit()

        # Mock the Celery task (new architecture: _scan_product enqueues, doesn't scrape directly)
        mock_task = MagicMock()
        mock_delay = MagicMock()
        mock_task.delay = mock_delay
        monkeypatch.setattr("worker.tasks.scrape_product", mock_task)

        engine = MonitoringEngine(_session_factory(async_session), mock_bot, mock_connector_manager)

        result = await engine._scan_product(async_session, product)

        assert result == True  # Should return True when enqueue succeeds
        # Celery task was enqueued with product id, url and current values
        mock_delay.assert_called_once_with(product.id, product.url, 100.0, True)

    @pytest.mark.asyncio
    async def test_scan_product_scraping_failure(self, async_session, mock_bot, mock_connector_manager, monkeypatch):
        """Test _scan_product returns False when Celery enqueue fails."""
        from db.models import Product
        from unittest.mock import MagicMock

        product = Product(url="https://fail-test.com")
        async_session.add(product)
        await async_session.commit()

        # Mock Celery task raising an exception (enqueue failure)
        mock_task = MagicMock()
        mock_task.delay.side_effect = Exception("Celery broker unavailable")
        monkeypatch.setattr("worker.tasks.scrape_product", mock_task)

        engine = MonitoringEngine(_session_factory(async_session), mock_bot, mock_connector_manager)

        result = await engine._scan_product(async_session, product)

        assert result == False  # Should return False when enqueue fails


class TestMonitoringEngineOpportunityCreation:
    """Test opportunity creation functionality."""

    @pytest.mark.asyncio
    async def test_create_and_notify_opportunity(self, async_session, mock_bot, mock_connector_manager):
        """Test _create_and_notify_opportunity method."""
        from db.models import Product
        from config.settings import ADMIN_GROUP_ID

        product = Product(
            url="https://opp-test.com",
            name="Opportunity Product",
            current_price=50.0,
            in_stock=True
        )
        async_session.add(product)
        await async_session.commit()

        engine = MonitoringEngine(_session_factory(async_session), mock_bot, mock_connector_manager)

        await engine._create_and_notify_opportunity(
            async_session, product, 100.0, 50.0, 85.0
        )

        # Should have sent message to admin
        mock_bot.send_message.assert_called_once()
        call_args = mock_bot.send_message.call_args
        assert ADMIN_GROUP_ID in call_args[0]
        assert "فرصة جديدة" in call_args[0][1]
        assert "50.00" in call_args[0][1]  # New price
        assert "85" in call_args[0][1]  # Score text includes the numeric score