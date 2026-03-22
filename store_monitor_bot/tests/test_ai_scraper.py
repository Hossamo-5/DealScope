"""Tests for AI-powered universal scraper and AI fallback behavior."""

import pytest

from core.connectors.ai_scraper import AIProductScraper
from core.connectors.generic import ConnectorManager


class TestAIProductScraper:
    def test_clean_html_removes_scripts(self):
        scraper = AIProductScraper()
        html = """
        <html>
          <head><script>alert('x')</script><style>.a{}</style></head>
          <body>
            <nav>menu</nav>
            <h1>Product Title</h1>
            <div>Price 199 SAR</div>
            <footer>copyright</footer>
          </body>
        </html>
        """
        cleaned = scraper._clean_html(html)
        assert "alert" not in cleaned
        assert "menu" not in cleaned
        assert "copyright" not in cleaned
        assert "Product Title" in cleaned

    def test_parse_ai_response_valid_json(self):
        scraper = AIProductScraper()
        parsed = scraper._parse_ai_response('{"name":"Phone","price":100}')
        assert parsed == {"name": "Phone", "price": 100}

    def test_parse_ai_response_with_markdown(self):
        scraper = AIProductScraper()
        parsed = scraper._parse_ai_response('```json\n{"name":"Phone","price":100}\n```')
        assert parsed == {"name": "Phone", "price": 100}

    def test_parse_ai_response_invalid_json(self):
        scraper = AIProductScraper()
        assert scraper._parse_ai_response("this is not json") is None

    def test_validate_result_price_conversion(self):
        scraper = AIProductScraper()
        out = scraper._validate_result({"price": "10,999.99"}, "https://example.com")
        assert out["price"] == 10999.99

    def test_validate_result_discount_calculation(self):
        scraper = AIProductScraper()
        out = scraper._validate_result({"price": 800, "original_price": 1000}, "https://example.com")
        assert out["discount_percent"] == 20.0

    @pytest.mark.parametrize(
        "url,expected",
        [
            ("https://shop.example.eg/product/1", "EGP"),
            ("https://amazon.sa/dp/B08", "SAR"),
        ],
    )
    def test_validate_result_currency_from_url(self, url, expected):
        scraper = AIProductScraper()
        out = scraper._validate_result({"price": 10}, url)
        assert out["currency"] == expected


class TestConnectorManagerAIHelpers:
    def test_is_complete_with_all_fields(self):
        manager = ConnectorManager()
        assert manager._is_complete({"name": "Phone", "price": 12.0}) is True

    def test_is_complete_missing_price(self):
        manager = ConnectorManager()
        assert manager._is_complete({"name": "Phone"}) is False

    def test_merge_results_traditional_wins(self):
        manager = ConnectorManager()
        merged = manager._merge_results({"price": 100, "name": "A"}, {"price": 200, "name": "B", "rating": 4.5})
        assert merged["price"] == 100
        assert merged["name"] == "A"

    def test_merge_results_ai_fills_gaps(self):
        manager = ConnectorManager()
        merged = manager._merge_results({"name": "A", "rating": None}, {"name": "B", "rating": 4.5})
        assert merged["name"] == "A"
        assert merged["rating"] == 4.5


@pytest.mark.asyncio
async def test_connector_manager_uses_ai_fallback(monkeypatch):
    manager = ConnectorManager()
    manager.ai_mode = "fallback"

    class DummyTraditional:
        @staticmethod
        def can_handle(_url):
            return True

        async def scrape(self, _url):
            return {"name": "Phone"}  # incomplete (no price)

    class DummyAI:
        async def scrape(self, _url):
            return {"name": "AI Phone", "price": 100.0, "rating": 4.4}

    manager.traditional_connectors = [DummyTraditional()]
    manager.connectors = manager.traditional_connectors
    manager.ai_scraper = DummyAI()

    # Avoid SSRF validator dependency in this isolated unit test.
    monkeypatch.setattr("utils.url_validator.validate_scrape_url", lambda _url: True)

    result = await manager.scrape("https://store.example/product/1")
    assert result is not None
    assert result["name"] == "Phone"  # traditional wins when present
    assert result["price"] == 100.0  # AI fills missing critical field
    assert result["rating"] == 4.4
