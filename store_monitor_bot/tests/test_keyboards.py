"""
Tests for Bot Keyboards
=======================
Tests bot/keyboards/main.py functionality
"""

import pytest
from aiogram.types import InlineKeyboardMarkup, ReplyKeyboardMarkup

from bot.keyboards.main import (
    main_menu_keyboard, product_found_keyboard, alerts_setup_keyboard,
    product_list_keyboard, product_detail_keyboard, subscription_keyboard,
    category_added_keyboard, category_alerts_keyboard, deals_list_keyboard,
    deal_detail_keyboard, settings_keyboard, back_home_keyboard,
    confirm_delete_keyboard, sort_products_keyboard
)
from db.models import UserProduct, Product, PlanType, MonitoringStatus, AlertType


class TestMainMenuKeyboard:
    """Test main_menu_keyboard function."""

    def test_main_menu_keyboard_returns_reply_keyboard(self):
        """Test main_menu_keyboard returns ReplyKeyboardMarkup."""
        keyboard = main_menu_keyboard()

        assert isinstance(keyboard, ReplyKeyboardMarkup)
        assert keyboard.resize_keyboard == True
        assert keyboard.one_time_keyboard == False

    def test_main_menu_keyboard_has_buttons(self):
        """Test main_menu_keyboard has expected buttons."""
        keyboard = main_menu_keyboard()

        # Check that keyboard has buttons (implementation detail)
        assert hasattr(keyboard, 'keyboard')
        assert len(keyboard.keyboard) > 0


class TestProductFoundKeyboard:
    """Test product_found_keyboard function."""

    def test_product_found_keyboard_returns_inline_keyboard(self):
        """Test product_found_keyboard returns InlineKeyboardMarkup."""
        keyboard = product_found_keyboard()

        assert isinstance(keyboard, InlineKeyboardMarkup)

    def test_product_found_keyboard_has_buttons(self):
        """Test product_found_keyboard has expected buttons."""
        keyboard = product_found_keyboard()

        assert hasattr(keyboard, 'inline_keyboard')
        assert len(keyboard.inline_keyboard) > 0


class TestAlertsSetupKeyboard:
    """Test alerts_setup_keyboard function."""

    def test_alerts_setup_keyboard_returns_inline_keyboard(self):
        """Test alerts_setup_keyboard returns InlineKeyboardMarkup."""
        keyboard = alerts_setup_keyboard(1)

        assert isinstance(keyboard, InlineKeyboardMarkup)

    def test_alerts_setup_keyboard_checked_alerts_have_prefix(self):
        """Test alerts_setup_keyboard: checked alerts have '✅ ' prefix."""
        current_alerts = ["price_drop", "back_in_stock"]

        keyboard = alerts_setup_keyboard(1, current_alerts)

        # Find the price_drop button
        price_drop_button = None
        for row in keyboard.inline_keyboard:
            for button in row:
                if "انخفاض السعر" in button.text:
                    price_drop_button = button
                    break

        assert price_drop_button is not None
        assert price_drop_button.text.startswith("✅ ")

    def test_alerts_setup_keyboard_unchecked_alerts_no_prefix(self):
        """Test alerts_setup_keyboard: unchecked alerts have no prefix."""
        current_alerts = ["price_drop"]  # Only price_drop checked

        keyboard = alerts_setup_keyboard(1, current_alerts)

        # Find a button that's not checked
        target_button = None
        for row in keyboard.inline_keyboard:
            for button in row:
                if "توفر المخزون" in button.text and not button.text.startswith("✅ "):
                    target_button = button
                    break

        assert target_button is not None


class TestProductListKeyboard:
    """Test product_list_keyboard function."""

    def test_product_list_keyboard_returns_inline_keyboard(self):
        """Test product_list_keyboard returns InlineKeyboardMarkup."""
        products = []
        keyboard = product_list_keyboard(products)

        assert isinstance(keyboard, InlineKeyboardMarkup)

    def test_product_list_keyboard_with_products(self):
        """Test product_list_keyboard displays products correctly."""
        # Create mock user products
        product = Product(
            id=1, name="Test Product", current_price=99.99,
            url="https://test.com"
        )
        user_product = UserProduct(
            id=1, user_id=1, product_id=1,
            status=MonitoringStatus.ACTIVE
        )
        user_product.product = product

        products = [user_product]
        keyboard = product_list_keyboard(products)

        assert len(keyboard.inline_keyboard) > 0

        # Check first button (product)
        first_button = keyboard.inline_keyboard[0][0]
        assert "Test Product" in first_button.text
        assert "100" in first_button.text  # Rounded price in UI
        assert "▶️" in first_button.text  # Active status

    def test_product_list_keyboard_paused_products_show_pause_icon(self):
        """Test product_list_keyboard: paused products show '⏸' icon."""
        product = Product(
            id=1, name="Paused Product", current_price=50.0,
            url="https://test.com"
        )
        user_product = UserProduct(
            id=1, user_id=1, product_id=1,
            status=MonitoringStatus.PAUSED  # Paused
        )
        user_product.product = product

        products = [user_product]
        keyboard = product_list_keyboard(products)

        first_button = keyboard.inline_keyboard[0][0]
        assert "⏸" in first_button.text  # Paused icon


class TestProductDetailKeyboard:
    """Test product_detail_keyboard function."""

    def test_product_detail_keyboard_returns_inline_keyboard(self):
        """Test product_detail_keyboard returns InlineKeyboardMarkup."""
        keyboard = product_detail_keyboard(1)

        assert isinstance(keyboard, InlineKeyboardMarkup)

    def test_product_detail_keyboard_active_product(self):
        """Test product_detail_keyboard for active product."""
        keyboard = product_detail_keyboard(1, is_paused=False)

        # Should have "⏸ إيقاف المراقبة" button
        pause_button_found = False
        for row in keyboard.inline_keyboard:
            for button in row:
                if "إيقاف المراقبة" in button.text:
                    pause_button_found = True
                    break

        assert pause_button_found

    def test_product_detail_keyboard_paused_product(self):
        """Test product_detail_keyboard for paused product."""
        keyboard = product_detail_keyboard(1, is_paused=True)

        # Should have "▶️ استئناف المراقبة" button
        resume_button_found = False
        for row in keyboard.inline_keyboard:
            for button in row:
                if "استئناف المراقبة" in button.text:
                    resume_button_found = True
                    break

        assert resume_button_found


class TestSubscriptionKeyboard:
    """Test subscription_keyboard function."""

    def test_subscription_keyboard_returns_inline_keyboard(self):
        """Test subscription_keyboard returns InlineKeyboardMarkup."""
        keyboard = subscription_keyboard(PlanType.FREE.value)

        assert isinstance(keyboard, InlineKeyboardMarkup)

    def test_subscription_keyboard_current_plan_has_prefix(self):
        """Test subscription_keyboard: current plan shows '✅ ' prefix."""
        keyboard = subscription_keyboard(PlanType.BASIC.value)

        # Find the basic plan button
        basic_button = None
        for row in keyboard.inline_keyboard:
            for button in row:
                if "الاشتراك الأساسي" in button.text:
                    basic_button = button
                    break

        assert basic_button is not None
        assert basic_button.text.startswith("✅ ")

    def test_subscription_keyboard_other_plans_no_prefix(self):
        """Test subscription_keyboard: other plans have no prefix."""
        keyboard = subscription_keyboard(PlanType.BASIC.value)

        # Find the free plan button (not current)
        free_button = None
        for row in keyboard.inline_keyboard:
            for button in row:
                if "الخطة المجانية" in button.text and not button.text.startswith("✅ "):
                    free_button = button
                    break

        assert free_button is not None


class TestCategoryKeyboard:
    """Test category-related keyboards."""

    def test_category_added_keyboard_returns_inline_keyboard(self):
        """Test category_added_keyboard returns InlineKeyboardMarkup."""
        keyboard = category_added_keyboard(1)

        assert isinstance(keyboard, InlineKeyboardMarkup)

    def test_category_alerts_keyboard_returns_inline_keyboard(self):
        """Test category_alerts_keyboard returns InlineKeyboardMarkup."""
        keyboard = category_alerts_keyboard(1)

        assert isinstance(keyboard, InlineKeyboardMarkup)


class TestDealsKeyboard:
    """Test deals-related keyboards."""

    def test_deals_list_keyboard_returns_inline_keyboard(self):
        """Test deals_list_keyboard returns InlineKeyboardMarkup."""
        opportunities = []
        keyboard = deals_list_keyboard(opportunities)

        assert isinstance(keyboard, InlineKeyboardMarkup)

    def test_deals_list_keyboard_with_opportunities(self):
        """Test deals_list_keyboard displays opportunities correctly."""
        # Mock opportunity
        class MockOpportunity:
            def __init__(self):
                self.id = 1
                self.product = MockProduct()
                self.discount_percent = 25.0

        class MockProduct:
            def __init__(self):
                self.name = "Deal Product"

        opportunities = [MockOpportunity()]
        keyboard = deals_list_keyboard(opportunities)

        assert len(keyboard.inline_keyboard) > 0

        # Check first button
        first_button = keyboard.inline_keyboard[0][0]
        assert "Deal Product" in first_button.text
        assert "25" in first_button.text  # Discount

    def test_deal_detail_keyboard_returns_inline_keyboard(self):
        """Test deal_detail_keyboard returns InlineKeyboardMarkup."""
        keyboard = deal_detail_keyboard(1, 1)

        assert isinstance(keyboard, InlineKeyboardMarkup)


class TestSettingsKeyboard:
    """Test settings keyboard."""

    def test_settings_keyboard_returns_inline_keyboard(self):
        """Test settings_keyboard returns InlineKeyboardMarkup."""
        keyboard = settings_keyboard()

        assert isinstance(keyboard, InlineKeyboardMarkup)


class TestGeneralKeyboards:
    """Test general utility keyboards."""

    def test_back_home_keyboard_returns_inline_keyboard(self):
        """Test back_home_keyboard returns InlineKeyboardMarkup."""
        keyboard = back_home_keyboard()

        assert isinstance(keyboard, InlineKeyboardMarkup)

    def test_confirm_delete_keyboard_returns_inline_keyboard(self):
        """Test confirm_delete_keyboard returns InlineKeyboardMarkup."""
        keyboard = confirm_delete_keyboard("product", 1)

        assert isinstance(keyboard, InlineKeyboardMarkup)


class TestSortProductsKeyboard:
    """Test sort_products_keyboard function."""

    def test_sort_products_keyboard_returns_inline_keyboard(self):
        """Test sort_products_keyboard returns InlineKeyboardMarkup."""
        keyboard = sort_products_keyboard()

        assert isinstance(keyboard, InlineKeyboardMarkup)

    def test_sort_products_keyboard_has_buttons(self):
        """Test sort_products_keyboard has expected sort options."""
        keyboard = sort_products_keyboard()

        button_texts = []
        for row in keyboard.inline_keyboard:
            for button in row:
                button_texts.append(button.text)

        assert "💰 حسب السعر" in button_texts
        assert "🕐 آخر تحديث" in button_texts
        assert "📦 حسب المخزون" in button_texts
        assert "🔤 حسب الاسم" in button_texts
        assert "🔙 رجوع" in button_texts