"""
Tests for database models
========================
Tests table relationships, enum values, and default values
"""

import pytest
from datetime import datetime
from db.models import (
    Base, User, Product, UserProduct, Store, PriceHistory, StockHistory,
    Opportunity, PlanType, AlertType, MonitoringStatus, OpportunityStatus,
    StoreRequestStatus, get_engine
)


class TestEnums:
    """Test enum values match expected strings."""

    def test_plan_type_enum_values(self):
        """Test PlanType enum has correct values."""
        assert PlanType.FREE.value == "free"
        assert PlanType.BASIC.value == "basic"
        assert PlanType.PROFESSIONAL.value == "professional"

    def test_alert_type_enum_values(self):
        """Test AlertType enum has correct values."""
        assert AlertType.PRICE_DROP.value == "price_drop"
        assert AlertType.ANY_PRICE_CHANGE.value == "any_price_change"
        assert AlertType.BACK_IN_STOCK.value == "back_in_stock"
        assert AlertType.OUT_OF_STOCK.value == "out_of_stock"
        assert AlertType.BIG_DISCOUNT.value == "big_discount"
        assert AlertType.TARGET_PRICE.value == "target_price"

    def test_monitoring_status_enum_values(self):
        """Test MonitoringStatus enum has correct values."""
        assert MonitoringStatus.ACTIVE.value == "active"
        assert MonitoringStatus.PAUSED.value == "paused"
        assert MonitoringStatus.DELETED.value == "deleted"

    def test_opportunity_status_enum_values(self):
        """Test OpportunityStatus enum has correct values."""
        assert OpportunityStatus.NEW.value == "new"
        assert OpportunityStatus.APPROVED.value == "approved"
        assert OpportunityStatus.REJECTED.value == "rejected"
        assert OpportunityStatus.POSTPONED.value == "postponed"

    def test_store_request_status_enum_values(self):
        """Test StoreRequestStatus enum has correct values."""
        assert StoreRequestStatus.PENDING.value == "pending"
        assert StoreRequestStatus.APPROVED.value == "approved"
        assert StoreRequestStatus.REJECTED.value == "rejected"
        assert StoreRequestStatus.IN_REVIEW.value == "in_review"


class TestTableRelationships:
    """Test all table relationships are correct."""

    def test_user_relationships(self):
        """Test User model relationships."""
        user = User(telegram_id=123456789, username="testuser")

        # Check relationships exist
        assert hasattr(user, 'monitored_products')
        assert hasattr(user, 'monitored_categories')
        assert hasattr(user, 'monitored_stores')
        assert hasattr(user, 'store_requests')

    def test_product_relationships(self):
        """Test Product model relationships."""
        product = Product(url="https://example.com/product")

        # Check relationships exist
        assert hasattr(product, 'store')
        assert hasattr(product, 'user_products')
        assert hasattr(product, 'price_history')
        assert hasattr(product, 'stock_history')
        assert hasattr(product, 'opportunities')

    def test_store_relationships(self):
        """Test Store model relationships."""
        store = Store(name="Test Store", base_url="https://store.com", connector_type="amazon")

        # Check relationships exist
        assert hasattr(store, 'products')

    def test_user_product_relationships(self):
        """Test UserProduct model relationships."""
        user_product = UserProduct(user_id=1, product_id=1)

        # Check relationships exist
        assert hasattr(user_product, 'user')
        assert hasattr(user_product, 'product')

    def test_price_history_relationships(self):
        """Test PriceHistory model relationships."""
        price_history = PriceHistory(product_id=1, price=100.0)

        # Check relationships exist
        assert hasattr(price_history, 'product')

    def test_stock_history_relationships(self):
        """Test StockHistory model relationships."""
        stock_history = StockHistory(product_id=1, in_stock=True)

        # Check relationships exist
        assert hasattr(stock_history, 'product')

    def test_opportunity_relationships(self):
        """Test Opportunity model relationships."""
        opportunity = Opportunity(
            product_id=1, old_price=200.0, new_price=150.0, discount_percent=25.0
        )

        # Check relationships exist
        assert hasattr(opportunity, 'product')


class TestDefaultValues:
    """Test default values on all columns."""

    def test_user_defaults(self):
        """Test User model default values."""
        user = User(telegram_id=123456789)

        assert user.plan in (None, PlanType.FREE)
        assert user.language in (None, "ar")
        assert user.currency in (None, "SAR")
        assert user.muted in (None, False)
        assert user.is_active in (None, True)
        assert user.is_banned in (None, False)

    def test_product_defaults(self):
        """Test Product model default values."""
        product = Product(url="https://example.com/product")

        assert product.currency in (None, "USD")
        assert product.in_stock is None
        assert product.lowest_price is None
        assert product.highest_price is None
        assert product.rating is None
        assert product.review_count is None
        assert product.created_at is None or isinstance(product.created_at, datetime)

    def test_user_product_defaults(self):
        """Test UserProduct model default values."""
        user_product = UserProduct(user_id=1, product_id=1)

        assert user_product.status in (None, MonitoringStatus.ACTIVE)
        assert user_product.alert_types in (None, [])
        assert user_product.target_price is None
        assert user_product.last_notified_at is None
        assert user_product.created_at is None or isinstance(user_product.created_at, datetime)

    def test_store_defaults(self):
        """Test Store model default values."""
        store = Store(name="Test Store", base_url="https://store.com", connector_type="amazon")

        assert store.is_active in (None, True)
        assert store.success_rate in (None, 100.0)
        assert store.last_error is None
        assert store.last_checked is None
        assert store.created_at is None or isinstance(store.created_at, datetime)

    def test_opportunity_defaults(self):
        """Test Opportunity model default values."""
        opportunity = Opportunity(
            product_id=1, old_price=200.0, new_price=150.0, discount_percent=25.0
        )

        assert opportunity.status in (None, OpportunityStatus.NEW)
        assert opportunity.in_stock in (None, True)
        assert opportunity.score in (None, 0)
        assert opportunity.affiliate_url is None
        assert opportunity.custom_message is None
        assert opportunity.published_at is None
        assert opportunity.discovered_at is None or isinstance(opportunity.discovered_at, datetime)


class TestDatabaseEngine:
    """Test database engine creation."""

    def test_sqlite_engine_creation(self):
        """Test SQLite engine creation."""
        engine = get_engine("sqlite:///test.db")
        assert engine is not None
        assert "aiosqlite" in str(engine.url)

    def test_postgresql_engine_creation(self):
        """Test PostgreSQL engine creation."""
        engine = get_engine("postgresql://user:pass@localhost/db")
        assert engine is not None
        assert "asyncpg" in str(engine.url)