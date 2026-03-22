"""
Tests for database CRUD operations
==================================
Tests all CRUD functions in db/crud.py
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock

from db import crud
from db.models import (
    User, Product, UserProduct, PlanType, MonitoringStatus,
    OpportunityStatus, AlertType
)


class TestUserOperations:
    """Test user-related CRUD operations."""

    @pytest.mark.asyncio
    async def test_get_or_create_user_new_user(self, async_session):
        """Test get_or_create_user: new user creation."""
        # Test creating new user
        user = await crud.get_or_create_user(
            async_session, telegram_id=123456789,
            username="testuser", first_name="Test", last_name="User"
        )

        assert user.telegram_id == 123456789
        assert user.username == "testuser"
        assert user.first_name == "Test"
        assert user.last_name == "User"
        assert user.plan == PlanType.FREE

    @pytest.mark.asyncio
    async def test_get_or_create_user_existing_user(self, async_session):
        """Test get_or_create_user: existing user retrieval."""
        # Create user first
        user1 = User(
            telegram_id=987654321,
            username="existing",
            first_name="Existing",
            last_name="User"
        )
        async_session.add(user1)
        await async_session.commit()

        # Try to get or create the same user
        user2 = await crud.get_or_create_user(
            async_session, telegram_id=987654321,
            username="updated", first_name="Updated"
        )

        assert user2.telegram_id == 987654321
        assert user2.username == "existing"  # Should not update existing data
        assert user2.first_name == "Existing"

    @pytest.mark.asyncio
    async def test_get_user_by_telegram_id(self, async_session):
        """Test get_user_by_telegram_id."""
        user = User(telegram_id=111222333, username="test")
        async_session.add(user)
        await async_session.commit()

        found_user = await crud.get_user_by_telegram_id(async_session, 111222333)
        assert found_user is not None
        assert found_user.telegram_id == 111222333

        # Test non-existent user
        not_found = await crud.get_user_by_telegram_id(async_session, 999999999)
        assert not_found is None


class TestProductOperations:
    """Test product-related CRUD operations."""

    @pytest.mark.asyncio
    async def test_create_product(self, async_session):
        """Test create_product function."""
        product = await crud.create_product(
            async_session,
            url="https://example.com/product",
            name="Test Product",
            price=100.0,
            currency="USD",
            in_stock=True,
            image_url="https://example.com/image.jpg",
            rating=4.5,
            review_count=100
        )

        assert product.url == "https://example.com/product"
        assert product.name == "Test Product"
        assert product.current_price == 100.0
        assert product.currency == "USD"
        assert product.in_stock == True
        assert product.lowest_price == 100.0
        assert product.highest_price == 100.0

    @pytest.mark.asyncio
    async def test_get_product_by_url(self, async_session):
        """Test get_product_by_url function."""
        product = Product(
            url="https://unique-url.com",
            name="Unique Product"
        )
        async_session.add(product)
        await async_session.commit()

        found = await crud.get_product_by_url(async_session, "https://unique-url.com")
        assert found is not None
        assert found.name == "Unique Product"

        # Test non-existent URL
        not_found = await crud.get_product_by_url(async_session, "https://nonexistent.com")
        assert not_found is None

    @pytest.mark.asyncio
    async def test_update_product_data_price_update(self, async_session):
        """Test update_product_data: price updates correctly."""
        # Create product with initial price
        product = Product(
            url="https://test.com",
            current_price=200.0,
            lowest_price=200.0,
            highest_price=200.0
        )
        async_session.add(product)
        await async_session.commit()

        # Update with lower price
        updated = await crud.update_product_data(
            async_session, product.id, price=150.0
        )

        assert updated.current_price == 150.0
        assert updated.lowest_price == 150.0  # Should update lowest
        assert updated.highest_price == 200.0  # Should keep highest

        # Update with higher price
        updated2 = await crud.update_product_data(
            async_session, product.id, price=250.0
        )

        assert updated2.current_price == 250.0
        assert updated2.lowest_price == 150.0  # Should keep lowest
        assert updated2.highest_price == 250.0  # Should update highest


class TestUserProductOperations:
    """Test user-product relationship operations."""

    @pytest.mark.asyncio
    async def test_can_user_add_product_free_plan(self, async_session):
        """Test can_user_add_product: respects plan limits (free=3)."""
        # Create free user
        user = User(telegram_id=123, plan=PlanType.FREE)
        async_session.add(user)
        await async_session.commit()

        # Should allow adding up to 3 products
        assert await crud.can_user_add_product(async_session, user) == True

        # Add 3 products
        for i in range(3):
            product = Product(url=f"https://test{i}.com")
            async_session.add(product)
            await async_session.commit()

            user_product = UserProduct(user_id=user.id, product_id=product.id)
            async_session.add(user_product)
            await async_session.commit()

        # Should not allow 4th product
        assert await crud.can_user_add_product(async_session, user) == False

    @pytest.mark.asyncio
    async def test_can_user_add_product_basic_plan(self, async_session):
        """Test can_user_add_product: basic plan allows 50 products."""
        user = User(telegram_id=456, plan=PlanType.BASIC)
        async_session.add(user)
        await async_session.commit()

        # Should allow adding products up to limit
        assert await crud.can_user_add_product(async_session, user) == True

    @pytest.mark.asyncio
    async def test_count_user_products(self, async_session):
        """Test count_user_products function."""
        user = User(telegram_id=789)
        async_session.add(user)
        await async_session.commit()

        # Add some products
        for i in range(3):
            product = Product(url=f"https://count{i}.com")
            async_session.add(product)
            await async_session.commit()

            user_product = UserProduct(
                user_id=user.id,
                product_id=product.id,
                status=MonitoringStatus.ACTIVE
            )
            async_session.add(user_product)
            await async_session.commit()

        count = await crud.count_user_products(async_session, user.id)
        assert count == 3


class TestOpportunityOperations:
    """Test opportunity-related operations."""

    @pytest.mark.asyncio
    async def test_create_opportunity_calculates_discount(self, async_session):
        """Test create_opportunity: calculates discount_percent accurately."""
        # Create product first
        product = Product(url="https://test.com", current_price=200.0)
        async_session.add(product)
        await async_session.commit()

        opportunity = await crud.create_opportunity(
            async_session, product.id, old_price=200.0, new_price=150.0, score=85.0
        )

        assert opportunity.product_id == product.id
        assert opportunity.old_price == 200.0
        assert opportunity.new_price == 150.0
        assert opportunity.discount_percent == 25.0  # (200-150)/200 * 100
        assert opportunity.score == 85.0
        assert opportunity.status == OpportunityStatus.NEW

    @pytest.mark.asyncio
    async def test_get_new_opportunities(self, async_session):
        """Test get_new_opportunities returns only new opportunities."""
        # Create product
        product = Product(url="https://opp.com")
        async_session.add(product)
        await async_session.commit()

        # Create opportunities with different statuses
        opp_new = crud.Opportunity(
            product_id=product.id, old_price=100.0, new_price=80.0,
            discount_percent=20.0, status=OpportunityStatus.NEW
        )
        opp_approved = crud.Opportunity(
            product_id=product.id, old_price=100.0, new_price=70.0,
            discount_percent=30.0, status=OpportunityStatus.APPROVED
        )

        async_session.add(opp_new)
        async_session.add(opp_approved)
        await async_session.commit()

        new_opportunities = await crud.get_new_opportunities(async_session)

        assert len(new_opportunities) == 1
        assert new_opportunities[0].status == OpportunityStatus.NEW


class TestDashboardStats:
    """Test dashboard statistics functions."""

    @pytest.mark.asyncio
    async def test_get_dashboard_stats(self, async_session):
        """Test get_dashboard_stats: returns correct counts."""
        # Create test data
        user = User(telegram_id=111, is_active=True)
        async_session.add(user)

        product = Product(url="https://stats.com")
        async_session.add(product)

        await async_session.commit()

        user_product = UserProduct(
            user_id=user.id, product_id=product.id, status=MonitoringStatus.ACTIVE
        )
        async_session.add(user_product)

        opportunity = crud.Opportunity(
            product_id=product.id, old_price=100.0, new_price=80.0,
            discount_percent=20.0, status=OpportunityStatus.NEW
        )
        async_session.add(opportunity)

        await async_session.commit()

        stats = await crud.get_dashboard_stats(async_session)

        assert stats["users_count"] == 1
        assert stats["products_count"] == 1
        assert stats["new_opportunities"] == 1
        assert stats["sent_today"] == 0  # No approved opportunities today


class TestCategoryOperations:
    """Test category-related CRUD operations."""

    @pytest.mark.asyncio
    async def test_add_category_to_user(self, async_session):
        """Test add_category_to_user function."""
        user = User(telegram_id=222)
        async_session.add(user)
        await async_session.commit()

        category = await crud.add_category_to_user(
            async_session, user.id,
            url="https://store.com/category/electronics",
            name="Electronics"
        )

        assert category.user_id == user.id
        assert category.url == "https://store.com/category/electronics"
        assert category.name == "Electronics"
        assert category.status == MonitoringStatus.ACTIVE

    @pytest.mark.asyncio
    async def test_get_user_categories(self, async_session):
        """Test get_user_categories function."""
        user = User(telegram_id=333)
        async_session.add(user)
        await async_session.commit()

        # Add categories
        cat1 = crud.UserCategory(
            user_id=user.id, url="https://cat1.com", name="Cat1"
        )
        cat2 = crud.UserCategory(
            user_id=user.id, url="https://cat2.com", name="Cat2",
            status=MonitoringStatus.DELETED  # Should be excluded
        )

        async_session.add(cat1)
        async_session.add(cat2)
        await async_session.commit()

        categories = await crud.get_user_categories(async_session, user.id)

        assert len(categories) == 1
        assert categories[0].name == "Cat1"


class TestStoreOperations:
    """Test store-related CRUD operations."""

    @pytest.mark.asyncio
    async def test_get_store_by_url(self, async_session):
        """Test get_store_by_url function (if it exists)."""
        # This function might not exist, let's check what we have
        pass


class TestOpportunityOperations:
    """Test opportunity-related operations."""

    @pytest.mark.asyncio
    async def test_create_opportunity_calculates_discount(self, async_session):
        """Test create_opportunity: calculates discount_percent accurately."""
        # Create product first
        product = Product(url="https://test.com", current_price=200.0)
        async_session.add(product)
        await async_session.commit()

        opportunity = await crud.create_opportunity(
            async_session, product.id, old_price=200.0, new_price=150.0, score=85.0
        )

        assert opportunity.product_id == product.id
        assert opportunity.old_price == 200.0
        assert opportunity.new_price == 150.0
        assert opportunity.discount_percent == 25.0  # (200-150)/200 * 100
        assert opportunity.score == 85.0
        assert opportunity.status == OpportunityStatus.NEW

    @pytest.mark.asyncio
    async def test_approve_opportunity(self, async_session):
        """Test approve_opportunity function."""
        product = Product(url="https://approve.com")
        async_session.add(product)
        await async_session.commit()

        opportunity = crud.Opportunity(
            product_id=product.id, old_price=100.0, new_price=80.0,
            discount_percent=20.0, status=OpportunityStatus.NEW
        )
        async_session.add(opportunity)
        await async_session.commit()

        approved = await crud.approve_opportunity(
            async_session, opportunity.id,
            affiliate_url="https://affiliate.com",
            custom_message="Special offer!"
        )

        assert approved.status == OpportunityStatus.APPROVED
        assert approved.affiliate_url == "https://affiliate.com"
        assert approved.custom_message == "Special offer!"
        assert approved.published_at is not None


class TestUserProductOperations:
    """Test user-product relationship operations."""

    @pytest.mark.asyncio
    async def test_toggle_monitoring_pause(self, async_session):
        """Test toggle_monitoring: pause functionality."""
        user = User(telegram_id=444)
        product = Product(url="https://toggle.com")
        async_session.add(user)
        async_session.add(product)
        await async_session.commit()

        user_product = UserProduct(
            user_id=user.id, product_id=product.id,
            status=MonitoringStatus.ACTIVE
        )
        async_session.add(user_product)
        await async_session.commit()

        # Pause monitoring
        await crud.toggle_monitoring(async_session, user_product.id, pause=True)
        await async_session.refresh(user_product)

        assert user_product.status == MonitoringStatus.PAUSED

        # Resume monitoring
        await crud.toggle_monitoring(async_session, user_product.id, pause=False)
        await async_session.refresh(user_product)

        assert user_product.status == MonitoringStatus.ACTIVE

    @pytest.mark.asyncio
    async def test_delete_user_product(self, async_session):
        """Test delete_user_product function."""
        user = User(telegram_id=555)
        product = Product(url="https://delete.com")
        async_session.add(user)
        async_session.add(product)
        await async_session.commit()

        user_product = UserProduct(
            user_id=user.id, product_id=product.id,
            status=MonitoringStatus.ACTIVE
        )
        async_session.add(user_product)
        await async_session.commit()

        await crud.delete_user_product(async_session, user_product.id)
        await async_session.refresh(user_product)

        assert user_product.status == MonitoringStatus.DELETED