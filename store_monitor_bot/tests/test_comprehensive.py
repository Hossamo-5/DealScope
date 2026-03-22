"""Comprehensive logic tests for cross-feature coverage."""

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from admin.dashboard import app

client = TestClient(app)


class TestDashboardAPI:
    def test_health_endpoint_structure(self):
        r = client.get('/api/health')
        assert r.status_code in [200, 401]
        if r.status_code == 200:
            data = r.json()
            assert 'status' in data
            assert 'components' in data
            assert 'database' in data['components']
            assert 'redis' in data['components']

    def test_all_api_endpoints_require_auth(self):
        endpoints = [
            ('GET', '/api/stats'),
            ('GET', '/api/users'),
            ('GET', '/api/opportunities'),
            ('GET', '/api/notifications'),
            ('GET', '/api/support/tickets'),
            ('GET', '/api/settings/bot'),
            ('GET', '/api/bot-menu'),
            ('GET', '/api/groups'),
            ('POST', '/api/telegram/resolve'),
            ('POST', '/api/broadcast'),
        ]
        for method, path in endpoints:
            r = getattr(client, method.lower())(path)
            assert r.status_code in [401, 403], (
                f'{method} {path} returned {r.status_code} without auth'
            )

    def test_dashboard_serves_vue_html(self):
        r = client.get('/')
        assert r.status_code == 200

    def test_login_missing_password_returns_422(self):
        r = client.post('/auth/login', json={'email': 'test@test.com'})
        assert r.status_code in [401, 422]

    def test_login_no_identifier_returns_error(self):
        r = client.post('/auth/login', json={'password': 'pass123'})
        assert r.status_code in [401, 422]

    def test_login_wrong_credentials_returns_401(self):
        r = client.post('/auth/login', json={
            'email': 'nonexistent@test.com',
            'password': 'wrongpassword',
        })
        assert r.status_code == 401


class TestScraperLogic:
    def test_amazon_connector_handles_amazon_urls(self):
        from core.connectors.amazon import AmazonConnector

        valid_urls = [
            'https://www.amazon.sa/dp/B123',
            'https://www.amazon.com/dp/B123',
            'https://www.amazon.ae/dp/B123',
            'https://www.amazon.co.uk/dp/B123',
        ]
        for url in valid_urls:
            assert AmazonConnector.can_handle(url)

    def test_amazon_connector_rejects_non_amazon(self):
        from core.connectors.amazon import AmazonConnector

        invalid_urls = [
            'https://www.noon.com/product',
            'https://www.extra.com/product',
            'https://shop.myshopify.com/products/item',
        ]
        for url in invalid_urls:
            assert not AmazonConnector.can_handle(url)

    def test_amazon_asin_extraction(self):
        from core.connectors.amazon import AmazonConnector

        test_cases = [
            ('https://amazon.sa/dp/B08L5TNJHG', 'B08L5TNJHG'),
            ('https://amazon.com/product/B08L5TNJHG', 'B08L5TNJHG'),
            ('https://amazon.com?ASIN=B08L5TNJHG', 'B08L5TNJHG'),
        ]
        for url, expected_asin in test_cases:
            result = AmazonConnector.extract_asin(url)
            assert result == expected_asin

    def test_shopify_connector_handles_shopify(self):
        from core.connectors.generic import ShopifyConnector

        assert ShopifyConnector.can_handle('https://store.myshopify.com/products/item')
        assert not ShopifyConnector.can_handle('https://amazon.com/dp/B123')

    def test_ai_scraper_clean_html(self):
        from core.connectors.ai_scraper import AIProductScraper

        scraper = AIProductScraper()
        dirty_html = '''
        <html>
        <head><script>alert("test")</script></head>
        <body>
          <nav>Navigation menu here</nav>
          <div class="product-price">EGP 999</div>
          <div class="product-name">Test Product</div>
          <footer>Footer content</footer>
          <script>var x = 1;</script>
        </body>
        </html>
        '''

        cleaned = scraper._clean_html(dirty_html)
        assert 'alert' not in cleaned
        assert 'Navigation' not in cleaned
        assert 'Footer' not in cleaned
        assert 'EGP 999' in cleaned
        assert 'Test Product' in cleaned

    def test_ai_scraper_validate_price_conversion(self):
        from core.connectors.ai_scraper import AIProductScraper

        scraper = AIProductScraper()
        result = scraper._validate_result(
            {'price': '10,999.99', 'currency': 'EGP', 'in_stock': True},
            'https://noon.com/egypt-en/test/p/Z123/',
        )
        assert result['price'] == 10999.99


class TestMonitoringEngine:
    def test_opportunity_scorer_high_score(self):
        from core.monitor import OpportunityScorer

        scorer = OpportunityScorer()
        score = scorer.calculate_score(
            {
                'rating': 5.0,
                'review_count': 1000,
                'in_stock': True,
                'lowest_price': 50.0,
            },
            old_price=100.0,
            new_price=50.0,
        )
        assert score >= 90

    def test_opportunity_scorer_max_100(self):
        from core.monitor import OpportunityScorer

        scorer = OpportunityScorer()
        score = scorer.calculate_score(
            {
                'rating': 5.0,
                'review_count': 999999,
                'in_stock': True,
                'lowest_price': 1.0,
            },
            old_price=10000.0,
            new_price=1.0,
        )
        assert score <= 100


class TestSettings:
    def test_plan_limits_structure(self):
        from config.settings import PLAN_LIMITS

        for plan in ['free', 'basic', 'professional']:
            assert plan in PLAN_LIMITS
            limits = PLAN_LIMITS[plan]
            assert 'max_products' in limits
            assert 'max_categories' in limits
            assert 'max_stores' in limits
            assert 'scan_interval' in limits

    def test_score_weights_sum_100(self):
        from config.settings import SCORE_WEIGHTS

        assert sum(SCORE_WEIGHTS.values()) == 100


class TestSecurity:
    def test_url_validator_blocks_private_ips(self):
        from utils.url_validator import URLValidator

        validator = URLValidator()
        private_urls = [
            'http://192.168.1.1/product',
            'http://10.0.0.1/shop',
            'http://localhost/api',
            'http://127.0.0.1/admin',
        ]
        for url in private_urls:
            result = validator.validate(url)
            assert not result['valid']

    def test_bot_registry_get_set(self):
        from utils.bot_registry import get_bot, set_bot

        mock_bot = MagicMock()
        set_bot(mock_bot)
        assert get_bot() == mock_bot


class TestDBCRUD:
    @pytest.mark.asyncio
    async def test_get_or_create_user_new(self, async_session):
        from db.crud import get_or_create_user

        user = await get_or_create_user(
            async_session,
            telegram_id=999999001,
            username='testuser_new',
            first_name='Test',
        )
        assert user is not None
        assert user.telegram_id == 999999001
        assert user.username == 'testuser_new'
        assert user.plan.value == 'free'


class TestBotFormatting:
    @pytest.mark.asyncio
    async def test_format_product_message_complete(self):
        from bot.handlers.user import format_product_message

        product_data = {
            'name': 'iPhone 17 Pro',
            'price': 3999.00,
            'original_price': 4999.00,
            'currency': 'SAR',
            'discount_percent': 20.0,
            'in_stock': True,
            'stock_text': 'Only 2 left in stock',
            'rating': 4.5,
            'review_count': 1250,
            'brand': 'Apple',
            'delivery_info': 'Get it tomorrow',
            'store': 'Amazon Saudi',
        }

        msg = await format_product_message(product_data)
        assert 'iPhone 17 Pro' in msg
        assert '20%' in msg
        assert 'Apple' in msg


class TestSupportSystem:
    def test_support_endpoints_require_auth(self):
        endpoints = [
            ('GET', '/api/support/tickets'),
            ('GET', '/api/support/team'),
            ('GET', '/api/support/stats'),
        ]
        for method, path in endpoints:
            r = getattr(client, method.lower())(path)
            assert r.status_code in [401, 403]


class TestTelegramResolver:
    def test_resolve_requires_auth(self):
        r = client.post('/api/telegram/resolve', json={'input': '@test'})
        assert r.status_code == 401


class TestMenuBuilder:
    def test_menu_endpoints_exist(self):
        for method, path in [('get', '/api/bot-menu'), ('post', '/api/bot-menu')]:
            r = getattr(client, method)(path)
            assert r.status_code != 404

    def test_menu_requires_auth(self):
        r = client.get('/api/bot-menu')
        assert r.status_code in [401, 403]
