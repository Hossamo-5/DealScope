"""
Tests for Amazon connector
==========================
Tests AmazonConnector scraping functionality
"""

import pytest
from unittest.mock import AsyncMock, patch
from bs4 import BeautifulSoup

from core.connectors.amazon import AmazonConnector


class TestAmazonConnectorCanHandle:
    """Test can_handle method."""

    def test_can_handle_amazon_com(self):
        """Test can_handle: true for amazon.com."""
        connector = AmazonConnector()
        assert connector.can_handle("https://www.amazon.com/dp/B08L5TNJHG") == True

    def test_can_handle_amazon_sa(self):
        """Test can_handle: true for amazon.sa."""
        connector = AmazonConnector()
        assert connector.can_handle("https://www.amazon.sa/dp/B08L5TNJHG") == True

    def test_can_handle_amazon_ae(self):
        """Test can_handle: true for amazon.ae."""
        connector = AmazonConnector()
        assert connector.can_handle("https://www.amazon.ae/dp/B08L5TNJHG") == True

    def test_can_handle_amazon_co_uk(self):
        """Test can_handle: true for amazon.co.uk."""
        connector = AmazonConnector()
        assert connector.can_handle("https://www.amazon.co.uk/dp/B08L5TNJHG") == True

    def test_can_handle_amazon_eg(self):
        """Test can_handle: true for amazon.eg."""
        connector = AmazonConnector()
        assert connector.can_handle("https://www.amazon.eg/dp/B0F27WF3XL") == True

    def test_can_handle_non_amazon(self):
        """Test can_handle: false for non-amazon URLs."""
        connector = AmazonConnector()
        assert connector.can_handle("https://www.shopify.com/product/123") == False
        assert connector.can_handle("https://www.ebay.com/item/123") == False
        assert connector.can_handle("https://www.example.com") == False


class TestAmazonConnectorExtractAsin:
    """Test extract_asin method."""

    def test_extract_asin_from_dp(self):
        """Test extract_asin: extracts from /dp/ pattern."""
        connector = AmazonConnector()
        asin = connector.extract_asin("https://www.amazon.com/dp/B08L5TNJHG")
        assert asin == "B08L5TNJHG"

    def test_extract_asin_from_product(self):
        """Test extract_asin: extracts from /product/ pattern."""
        connector = AmazonConnector()
        asin = connector.extract_asin("https://www.amazon.com/product/B08L5TNJHG")
        assert asin == "B08L5TNJHG"

    def test_extract_asin_from_asin_param(self):
        """Test extract_asin: extracts from ASIN= pattern."""
        connector = AmazonConnector()
        asin = connector.extract_asin("https://www.amazon.com/dp/product?ASIN=B08L5TNJHG")
        assert asin == "B08L5TNJHG"

    def test_extract_asin_no_match(self):
        """Test extract_asin: returns None when no ASIN found."""
        connector = AmazonConnector()
        asin = connector.extract_asin("https://www.amazon.com/no-asin-here")
        assert asin is None


class TestExtractPrice:
    """Test _extract_price static helper."""

    def test_simple_number(self):
        assert AmazonConnector._extract_price("299.99") == 299.99

    def test_dollar_sign(self):
        assert AmazonConnector._extract_price("$1,299.00") == 1299.00

    def test_egp(self):
        assert AmazonConnector._extract_price("EGP 4,500") == 4500.0

    def test_arabic_numerals(self):
        assert AmazonConnector._extract_price("٤٥٠٠") == 4500.0

    def test_empty(self):
        assert AmazonConnector._extract_price("") is None

    def test_none(self):
        assert AmazonConnector._extract_price(None) is None

    def test_no_digits(self):
        assert AmazonConnector._extract_price("no price") is None


class TestAmazonConnectorParseHtml:
    """Test _parse_amazon_html method."""

    def test_parse_full_product(self):
        """Test _parse_amazon_html: extracts ALL fields from rich HTML."""
        html = """
        <html>
        <body>
            <span id="productTitle">Test Product Name</span>
            <span class="a-price-whole">299</span>
            <span class="a-price-fraction">99</span>
            <span class="a-price a-text-price"><span class="a-offscreen">$399.99</span></span>
            <span class="savingsPercentage">-25%</span>
            <div id="availability">
                <span>In Stock</span>
            </div>
            <span id="acrPopover" title="4.5 out of 5 stars"></span>
            <span class="a-icon-alt">4.5 out of 5 stars</span>
            <span id="acrCustomerReviewText">1,234 reviews</span>
            <img id="landingImage" src="https://example.com/image.jpg"
                 data-old-hires="https://example.com/image-hires.jpg">
            <a id="bylineInfo">Brand: TestBrand</a>
        </body>
        </html>
        """
        soup = BeautifulSoup(html, "html.parser")
        connector = AmazonConnector()

        result = connector._parse_amazon_html(soup, "https://www.amazon.com/dp/B08TEST123")

        assert result["name"] == "Test Product Name"
        assert result["price"] == 299.99
        assert result["original_price"] == 399.99
        assert result["discount_percent"] == 25.0
        assert result["currency"] == "USD"
        assert result["in_stock"] == True
        assert result["rating"] == 4.5
        assert result["review_count"] == 1234
        assert result["image_url"] == "https://example.com/image-hires.jpg"
        assert result["brand"] == "TestBrand"
        assert result["store"].startswith("Amazon")
        assert result["asin"] == "B08TEST123"

    def test_parse_basic_product(self):
        """Test _parse_amazon_html: extracts data from HTML with basic price."""
        html = """
        <html>
        <body>
            <span id="productTitle">Test Product Name</span>
            <span class="a-price-whole">299</span>
            <span class="a-price-fraction">99</span>
            <div id="availability">
                <span>In Stock</span>
            </div>
            <span class="a-icon-alt">4.5 out of 5 stars</span>
            <span id="acrCustomerReviewText">1,234 reviews</span>
            <img id="landingImage" src="https://example.com/image.jpg">
        </body>
        </html>
        """
        soup = BeautifulSoup(html, "html.parser")
        connector = AmazonConnector()

        result = connector._parse_amazon_html(soup, "https://www.amazon.com/dp/B08TEST123")

        assert result["name"] == "Test Product Name"
        assert result["price"] == 299.99
        assert result["currency"] == "USD"
        assert result["in_stock"] == True
        assert result["rating"] == 4.5
        assert result["review_count"] == 1234
        assert result["image_url"] == "https://example.com/image.jpg"
        assert result["store"].startswith("Amazon")
        assert result["asin"] == "B08TEST123"

    def test_parse_price_with_commas(self):
        """Test price parsing: handles commas."""
        html = """
        <span id="productTitle">Comma Product</span>
        <span class="a-price-whole">1,299</span>
        <span class="a-price-fraction">99</span>
        """
        soup = BeautifulSoup(html, "html.parser")
        connector = AmazonConnector()

        result = connector._parse_amazon_html(soup, "https://www.amazon.com/dp/B08TEST123")

        assert result["price"] == 1299.99

    def test_parse_out_of_stock(self):
        """Test stock detection: out-of-stock HTML patterns."""
        html = """
        <div id="availability">
            <span>Currently unavailable</span>
        </div>
        """
        soup = BeautifulSoup(html, "html.parser")
        connector = AmazonConnector()

        result = connector._parse_amazon_html(soup, "https://www.amazon.com/dp/B08TEST123")

        assert result["in_stock"] == False

    def test_parse_arabic_out_of_stock(self):
        """Test stock detection: Arabic 'غير متوفر'."""
        html = """
        <div id="availability">
            <span>غير متوفر حالياً</span>
        </div>
        """
        soup = BeautifulSoup(html, "html.parser")
        connector = AmazonConnector()

        result = connector._parse_amazon_html(soup, "https://www.amazon.eg/dp/B08TEST123")

        assert result["in_stock"] == False
        assert result["currency"] == "EGP"

    def test_parse_missing_price(self):
        """Test price parsing: handles missing prices."""
        html = """
        <span id="productTitle">Product Without Price</span>
        """
        soup = BeautifulSoup(html, "html.parser")
        connector = AmazonConnector()

        result = connector._parse_amazon_html(soup, "https://www.amazon.com/dp/B08TEST123")

        assert result.get("price") is None

    def test_parse_currency_detection_sa(self):
        """Test currency detection: sa = SAR."""
        connector = AmazonConnector()
        soup = BeautifulSoup("<html></html>", "html.parser")

        result = connector._parse_amazon_html(soup, "https://www.amazon.sa/dp/B08TEST123")

        assert result["currency"] == "SAR"

    def test_parse_currency_detection_ae(self):
        """Test currency detection: ae = AED."""
        connector = AmazonConnector()
        soup = BeautifulSoup("<html></html>", "html.parser")

        result = connector._parse_amazon_html(soup, "https://www.amazon.ae/dp/B08TEST123")

        assert result["currency"] == "AED"

    def test_parse_currency_detection_co_uk(self):
        """Test currency detection: co.uk = GBP."""
        connector = AmazonConnector()
        soup = BeautifulSoup("<html></html>", "html.parser")

        result = connector._parse_amazon_html(soup, "https://www.amazon.co.uk/dp/B08TEST123")

        assert result["currency"] == "GBP"

    def test_parse_currency_detection_eg(self):
        """Test currency detection: eg = EGP."""
        connector = AmazonConnector()
        soup = BeautifulSoup("<html></html>", "html.parser")

        result = connector._parse_amazon_html(soup, "https://www.amazon.eg/dp/B08TEST123")

        assert result["currency"] == "EGP"

    def test_parse_alternative_price_selectors(self):
        """Test alternative price selectors."""
        html = """
        <span id="priceblock_ourprice">$199.99</span>
        """
        soup = BeautifulSoup(html, "html.parser")
        connector = AmazonConnector()

        result = connector._parse_amazon_html(soup, "https://www.amazon.com/dp/B08TEST123")

        assert result["price"] == 199.99

    def test_parse_deal_price(self):
        """Test deal price selector."""
        html = """
        <span id="priceblock_dealprice">$149.99</span>
        """
        soup = BeautifulSoup(html, "html.parser")
        connector = AmazonConnector()

        result = connector._parse_amazon_html(soup, "https://www.amazon.com/dp/B08TEST123")

        assert result["price"] == 149.99

    def test_parse_offscreen_price(self):
        """Test .a-price .a-offscreen selector (modern Amazon layout)."""
        html = """
        <span id="productTitle">Offscreen Price Product</span>
        <span class="a-price">
            <span class="a-offscreen">EGP 4,500.00</span>
        </span>
        """
        soup = BeautifulSoup(html, "html.parser")
        connector = AmazonConnector()

        result = connector._parse_amazon_html(soup, "https://www.amazon.eg/dp/B08TEST123")

        assert result["price"] == 4500.0
        assert result["currency"] == "EGP"

    def test_parse_discount_calculated(self):
        """Test discount is calculated from price and original_price."""
        html = """
        <span id="productTitle">Discount Product</span>
        <span class="a-price-whole">750</span>
        <span class="a-price-fraction">00</span>
        <span class="a-price a-text-price"><span class="a-offscreen">$1000.00</span></span>
        """
        soup = BeautifulSoup(html, "html.parser")
        connector = AmazonConnector()

        result = connector._parse_amazon_html(soup, "https://www.amazon.com/dp/B08TEST123")

        assert result["price"] == 750.0
        assert result["original_price"] == 1000.0
        assert result["discount_percent"] == 25.0

    def test_parse_brand(self):
        """Test brand extraction."""
        html = """
        <span id="productTitle">Brand Product</span>
        <a id="bylineInfo">Visit the Samsung Store</a>
        """
        soup = BeautifulSoup(html, "html.parser")
        connector = AmazonConnector()

        result = connector._parse_amazon_html(soup, "https://www.amazon.com/dp/B08TEST123")

        assert result["brand"] == "Samsung Store"

    def test_parse_coupon(self):
        """Test coupon extraction."""
        html = """
        <span id="productTitle">Coupon Product</span>
        <span id="couponBadge">Apply 10% coupon</span>
        """
        soup = BeautifulSoup(html, "html.parser")
        connector = AmazonConnector()

        result = connector._parse_amazon_html(soup, "https://www.amazon.com/dp/B08TEST123")

        assert result["coupon"] == "Apply 10% coupon"

    def test_parse_image_hires_preferred(self):
        """Test image extraction prefers data-old-hires over src."""
        html = """
        <span id="productTitle">Image Product</span>
        <img id="landingImage"
             src="https://example.com/thumb.jpg"
             data-old-hires="https://example.com/hires.jpg">
        """
        soup = BeautifulSoup(html, "html.parser")
        connector = AmazonConnector()

        result = connector._parse_amazon_html(soup, "https://www.amazon.com/dp/B08TEST123")

        assert result["image_url"] == "https://example.com/hires.jpg"

    def test_parse_stock_text_preserved(self):
        """Test stock_text is preserved in result."""
        html = """
        <div id="availability">
            <span>Only 3 left in stock</span>
        </div>
        """
        soup = BeautifulSoup(html, "html.parser")
        connector = AmazonConnector()

        result = connector._parse_amazon_html(soup, "https://www.amazon.com/dp/B08TEST123")

        assert result["in_stock"] == True
        assert "3 left" in result["stock_text"]

    def test_parse_raw_html_string(self):
        """Test _parse_amazon_html can accept a raw HTML string."""
        html = """
        <span id="productTitle">Raw HTML Product</span>
        <span class="a-price-whole">100</span>
        <span class="a-price-fraction">00</span>
        """
        connector = AmazonConnector()

        result = connector._parse_amazon_html(html, "https://www.amazon.com/dp/B08TEST123")

        assert result["name"] == "Raw HTML Product"
        assert result["price"] == 100.0


class TestAmazonConnectorScrape:
    """Test scrape method with mocked HTTP requests."""

    @pytest.mark.asyncio
    @patch('httpx.AsyncClient')
    async def test_scrape_successful(self, mock_client_class):
        """Test successful scraping with mocked httpx."""
        mock_client = AsyncMock()
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.text = """
        <html>
        <body>
            <span id="productTitle">Mock Product</span>
            <span class="a-price-whole">199</span>
            <span class="a-price-fraction">99</span>
            <div id="availability"><span>In Stock</span></div>
        </body>
        </html>
        """
        mock_client.get.return_value = mock_response
        mock_client_class.return_value.__aenter__.return_value = mock_client
        mock_client_class.return_value.__aexit__.return_value = None

        connector = AmazonConnector()
        result = await connector.scrape("https://www.amazon.com/dp/B08TEST123")

        assert result is not None
        assert result["name"] == "Mock Product"
        assert result["price"] == 199.99
        assert result["in_stock"] == True

    @pytest.mark.asyncio
    @patch('core.connectors.amazon.AmazonConnector._scrape_with_playwright')
    @patch('httpx.AsyncClient')
    async def test_scrape_http_error(self, mock_client_class, mock_playwright):
        """Test scraping with HTTP error."""
        mock_client = AsyncMock()
        mock_response = AsyncMock()
        mock_response.status_code = 404
        mock_client.get.return_value = mock_response
        mock_client_class.return_value.__aenter__.return_value = mock_client
        mock_client_class.return_value.__aexit__.return_value = None
        mock_playwright.return_value = None

        connector = AmazonConnector()
        result = await connector.scrape("https://www.amazon.com/dp/B08TEST123")

        assert result is None

    @pytest.mark.asyncio
    @patch('core.connectors.amazon.AmazonConnector._scrape_with_playwright')
    @patch('core.connectors.amazon.AmazonConnector._scrape_with_requests')
    @patch('httpx.AsyncClient')
    async def test_scrape_fallback_to_playwright(self, mock_client_class, mock_requests, mock_playwright):
        """Test scraping falls back to Playwright when HTTP fails."""
        mock_client = AsyncMock()
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.text = ""
        mock_client.get.return_value = mock_response
        mock_client_class.return_value.__aenter__.return_value = mock_client
        mock_client_class.return_value.__aexit__.return_value = None

        # Force request-path failure so fallback is exercised
        mock_requests.return_value = None
        # Mock Playwright to succeed
        mock_playwright.return_value = {"name": "Playwright Product", "price": 100.0}

        connector = AmazonConnector()
        result = await connector.scrape("https://www.amazon.com/dp/B08TEST123")

        assert result is not None
        assert result["name"] == "Playwright Product"
        mock_playwright.assert_called_once()

    @pytest.mark.asyncio
    @patch('core.connectors.amazon.AmazonConnector._scrape_with_playwright')
    @patch('httpx.AsyncClient')
    async def test_scrape_merge_http_and_playwright(self, mock_client_class, mock_playwright):
        """Test that Playwright results are merged with HTTP results."""
        # HTTP returns name but no price
        mock_client = AsyncMock()
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.text = """
        <span id="productTitle">HTTP Product</span>
        <img id="landingImage" src="https://example.com/img.jpg">
        """
        mock_client.get.return_value = mock_response
        mock_client_class.return_value.__aenter__.return_value = mock_client
        mock_client_class.return_value.__aexit__.return_value = None

        # Playwright returns price but no image
        mock_playwright.return_value = {
            "name": "PW Product",
            "price": 500.0,
            "currency": "EGP",
        }

        connector = AmazonConnector()
        result = await connector.scrape("https://www.amazon.eg/dp/B08TEST123")

        assert result is not None
        assert result["price"] == 500.0
        # image_url should be filled from HTTP data
        assert result.get("image_url") == "https://example.com/img.jpg"