"""
Tests for Generic connector and Connector Manager
================================================
Tests GenericConnector, ShopifyConnector, WooCommerceConnector, and ConnectorManager
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from bs4 import BeautifulSoup

from core.connectors.generic import (
    ShopifyConnector, WooCommerceConnector, GenericConnector, ConnectorManager
)


class TestShopifyConnector:
    """Test ShopifyConnector functionality."""

    def test_can_handle_shopify_products(self):
        """Test ShopifyConnector.can_handle(): detects /products/ URLs."""
        connector = ShopifyConnector()
        assert connector.can_handle("https://store.com/products/iphone-case") == True
        assert connector.can_handle("https://store.com/products/iphone-case?variant=123") == True

    def test_can_handle_non_shopify(self):
        """Test ShopifyConnector.can_handle(): false for non-shopify URLs."""
        connector = ShopifyConnector()
        assert connector.can_handle("https://amazon.com/dp/B08TEST") == False
        assert connector.can_handle("https://store.com/product/123") == False

    @pytest.mark.asyncio
    @patch('httpx.AsyncClient')
    async def test_scrape_successful(self, mock_client_class):
        """Test successful Shopify scraping."""
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "product": {
                "title": "Test Shopify Product",
                "variants": [{
                    "price": "99.99",
                    "available": True
                }],
                "images": [{"src": "https://example.com/image.jpg"}]
            }
        }
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client_class.return_value.__aenter__.return_value = mock_client
        mock_client_class.return_value.__aexit__.return_value = None

        connector = ShopifyConnector()
        result = await connector.scrape("https://store.com/products/test-product")

        assert result is not None
        assert result["name"] == "Test Shopify Product"
        assert result["price"] == 99.99
        assert result["in_stock"] == True
        assert result["image_url"] == "https://example.com/image.jpg"


class TestWooCommerceConnector:
    """Test WooCommerceConnector functionality."""

    def test_can_handle_woocommerce_products(self):
        """Test WooCommerceConnector.can_handle(): detects /product/ URLs."""
        connector = WooCommerceConnector()
        assert connector.can_handle("https://store.com/product/iphone-case") == True
        assert connector.can_handle("https://store.com/product/iphone-case/") == True

    def test_can_handle_non_woocommerce(self):
        """Test WooCommerceConnector.can_handle(): false for non-woocommerce URLs."""
        connector = WooCommerceConnector()
        assert connector.can_handle("https://amazon.com/dp/B08TEST") == False
        assert connector.can_handle("https://store.com/products/123") == False

    @pytest.mark.asyncio
    @patch('httpx.AsyncClient')
    async def test_scrape_successful(self, mock_client_class):
        """Test successful WooCommerce scraping."""
        html = """
        <html>
        <body>
            <h1 class="product_title">Woo Product</h1>
            <p class="price"><ins><span>$79.99</span></ins></p>
            <p class="stock in-stock">In stock</p>
            <figure class="woocommerce-product-gallery__image">
                <img src="https://example.com/woo-image.jpg">
            </figure>
        </body>
        </html>
        """

        mock_client = AsyncMock()
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.text = html
        mock_client.get.return_value = mock_response
        mock_client_class.return_value.__aenter__.return_value = mock_client
        mock_client_class.return_value.__aexit__.return_value = None

        connector = WooCommerceConnector()
        result = await connector.scrape("https://store.com/product/test-product")

        assert result is not None
        assert result["name"] == "Woo Product"
        assert result["price"] == 79.99
        assert result["in_stock"] == True
        assert result["image_url"] == "https://example.com/woo-image.jpg"


class TestGenericConnector:
    """Test GenericConnector functionality."""

    def test_can_handle_any_url(self):
        """Test GenericConnector.can_handle(): accepts any URL."""
        connector = GenericConnector()
        assert connector.can_handle("https://any-site.com/product/123") == True
        assert connector.can_handle("https://example.com") == True

    def test_extract_json_ld_product(self):
        """Test GenericConnector._extract_json_ld(): valid Schema.org Product JSON."""
        html = """
        <html>
        <script type="application/ld+json">
        {
            "@type": "Product",
            "name": "JSON-LD Product",
            "offers": {
                "price": "149.99",
                "priceCurrency": "EUR",
                "availability": "InStock"
            },
            "aggregateRating": {
                "ratingValue": 4.2,
                "reviewCount": 89
            },
            "image": "https://example.com/json-image.jpg"
        }
        </script>
        </html>
        """
        soup = BeautifulSoup(html, "html.parser")
        connector = GenericConnector()

        result = connector._extract_json_ld(soup)

        assert result is not None
        assert result["name"] == "JSON-LD Product"
        assert result["price"] == 149.99
        assert result["currency"] == "EUR"
        assert result["in_stock"] == True
        assert result["rating"] == 4.2
        assert result["review_count"] == 89
        assert result["image_url"] == "https://example.com/json-image.jpg"

    def test_extract_open_graph(self):
        """Test GenericConnector._extract_open_graph()."""
        html = """
        <html>
        <head><title>OG Product</title></head>
        <head>
            <meta property="og:title" content="OG Product">
            <meta property="og:image" content="https://example.com/og-image.jpg">
        </head>
        </html>
        """
        soup = BeautifulSoup(html, "html.parser")
        connector = GenericConnector()

        result = connector._extract_open_graph(soup, "https://example.com")

        assert result is not None
        assert result["name"] == "OG Product"
        assert result["image_url"] == "https://example.com/og-image.jpg"
        assert result["store"] == "example.com"


class TestConnectorManager:
    """Test ConnectorManager functionality."""

    def test_detect_store_type_amazon(self):
        """Test ConnectorManager.detect_store_type(): returns 'amazon' for Amazon URLs."""
        store_type = ConnectorManager.detect_store_type("https://www.amazon.com/dp/B08TEST")
        assert store_type == "amazon"

    def test_detect_store_type_shopify(self):
        """Test ConnectorManager.detect_store_type(): returns 'shopify' for Shopify URLs."""
        store_type = ConnectorManager.detect_store_type("https://store.com/products/item")
        assert store_type == "shopify"

    def test_detect_store_type_woocommerce(self):
        """Test ConnectorManager.detect_store_type(): returns 'woocommerce' for WooCommerce URLs."""
        store_type = ConnectorManager.detect_store_type("https://store.com/product/item")
        assert store_type == "woocommerce"

    def test_detect_store_type_custom(self):
        """Test ConnectorManager.detect_store_type(): returns 'custom' for other URLs."""
        store_type = ConnectorManager.detect_store_type("https://unknown.com/item/123")
        assert store_type == "custom"

    @pytest.mark.asyncio
    async def test_scrape_falls_through_connectors(self):
        """Test ConnectorManager.scrape(): falls through connectors correctly."""
        manager = ConnectorManager()

        # Mock connectors to fail in order
        manager.connectors[0].can_handle = MagicMock(return_value=False)  # Amazon
        manager.connectors[1].can_handle = MagicMock(return_value=True)   # Shopify
        manager.connectors[1].scrape = AsyncMock(return_value={"name": "Shopify Product"})

        result = await manager.scrape("https://store.com/products/test")

        assert result is not None
        assert result["name"] == "Shopify Product"
        manager.connectors[1].scrape.assert_called_once()

    @pytest.mark.asyncio
    async def test_scrape_all_fail(self):
        """Test ConnectorManager.scrape(): returns None when all connectors fail."""
        manager = ConnectorManager()

        # Mock all connectors to fail
        for connector in manager.connectors:
            connector.can_handle = MagicMock(return_value=False)

        result = await manager.scrape("https://unknown.com/product")

        assert result is None