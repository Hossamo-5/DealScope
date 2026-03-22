"""
AI-Powered Universal Product Scraper
=====================================
Uses LongCat AI to understand any product page and extract structured data.
"""

import json
import logging
import re
from typing import Dict, Optional

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class AIProductScraper:
    """Intelligent product scraper using LongCat AI."""

    def __init__(self):
        from config.settings import LONGCAT_API_KEY, LONGCAT_BASE_URL, LONGCAT_MODEL

        self.api_key = LONGCAT_API_KEY
        self.base_url = LONGCAT_BASE_URL
        self.model = LONGCAT_MODEL
        self.system_prompt = """You are a product data extraction specialist.
Your job is to extract product information from e-commerce webpage HTML.

You MUST respond with ONLY a valid JSON object, nothing else.
No explanation, no markdown, no code blocks. Just pure JSON.

Extract these fields (use null if not found):
{
  "name": "Full product name",
  "price": 99.99,
  "original_price": 149.99,
  "currency": "EGP",
  "discount_percent": 33,
  "in_stock": true,
  "stock_quantity": null,
  "stock_text": "Only 2 left in stock",
  "rating": 4.5,
  "review_count": 1250,
  "brand": "Samsung",
  "category": "Electronics",
  "image_url": "https://...",
  "description": "Brief product description",
  "store": "Noon",
  "delivery_info": "Get it by tomorrow",
  "color": null,
  "size": null,
  "model_number": null,
  "sku": null,
  "barcode": null
}

Rules:
- price and original_price must be numbers only (no currency symbols)
- discount_percent must be a number (e.g., 15 for 15%)
- in_stock must be boolean
- rating must be a number between 0-5
- review_count must be an integer
- currency must be the 3-letter ISO code (EGP, SAR, AED, USD, GBP, etc.)
- If a field cannot be determined, use null
- For Arabic pages, still return field names in English but values in original language"""

    async def scrape(self, url: str) -> Optional[Dict]:
        """Fetch, clean, and extract data with AI."""
        html = await self._fetch_page(url)
        if not html:
            logger.error("AI Scraper: Failed to fetch %s", url)
            return None

        cleaned_text = self._clean_html(html)
        result = await self._extract_with_ai(url, cleaned_text)
        if not result:
            return None

        return self._validate_result(result, url)

    async def _fetch_page(self, url: str) -> Optional[str]:
        """Fetch page HTML. Prefer httpx (HTTP/1.1) then Playwright as fallback.

        This avoids Playwright HTTP/2 protocol errors on some hosts.
        """
        import httpx

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,*/*",
            "Accept-Language": "ar,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
        }

        # Try 1: httpx with HTTP/1.1 (avoid HTTP2)
        try:
            async with httpx.AsyncClient(
                headers=headers,
                timeout=20,
                follow_redirects=True,
                http2=False,
            ) as client:
                response = await client.get(url)
                if response.status_code == 200 and len(response.text) > 3000:
                    logger.info("HTTP fetch success: %s chars", len(response.text))
                    return response.text
                else:
                    logger.warning("HTTP returned %s", response.status_code)
        except Exception as e:
            logger.warning(f"HTTP/1.1 fetch failed: {e}")

        # Try 2: httpx with Googlebot UA
        try:
            simple_headers = {
                "User-Agent": (
                    "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"
                )
            }
            async with httpx.AsyncClient(headers=simple_headers, timeout=15, follow_redirects=True) as client:
                response = await client.get(url)
                if response.status_code == 200 and len(response.text) > 2000:
                    logger.info("HTTP fetch (Googlebot UA) success: %s", response.status_code)
                    return response.text
        except Exception as e:
            logger.warning(f"Googlebot UA failed: {e}")

        # Try 3: Playwright as last resort (if installed)
        try:
            from playwright.async_api import async_playwright
            import asyncio

            logger.info("Trying Playwright...")
            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=True,
                    args=[
                        '--no-sandbox',
                        '--disable-blink-features=AutomationControlled',
                        '--disable-http2',
                    ],
                )
                context = await browser.new_context(user_agent=headers["User-Agent"], ignore_https_errors=True)
                page = await context.new_page()
                try:
                    await page.goto(url, wait_until="domcontentloaded", timeout=25000)
                    await asyncio.sleep(2)
                    html = await page.content()
                    await browser.close()
                    if len(html) > 3000:
                        logger.info("Playwright fetch success")
                        return html
                except Exception as pe:
                    logger.warning(f"Playwright page error: {pe}")
                    await browser.close()

        except ImportError:
            logger.warning("Playwright not installed")
        except Exception as e:
            logger.error(f"Playwright failed: {e}")

        logger.error(f"All fetch methods failed for {url}")
        return None

    def _clean_html(self, html: str) -> str:
        """Clean HTML to reduce noise and token usage."""
        soup = BeautifulSoup(html, "html.parser")

        noise_tags = [
            "script",
            "style",
            "noscript",
            "iframe",
            "nav",
            "footer",
            "header",
            "aside",
        ]
        noise_classes = [
            "nav",
            "footer",
            "header",
            "sidebar",
            "advertisement",
            "ad-",
            "cookie",
            "popup",
            "modal",
            "overlay",
            "menu",
            "breadcrumb",
            "related",
            "recommend",
            "social",
            "share",
            "comment",
        ]

        for tag in noise_tags:
            for element in soup.find_all(tag):
                element.decompose()

        for element in soup.find_all(
            class_=lambda c: c and any(n in " ".join(c).lower() for n in noise_classes)
        ):
            element.decompose()

        product_keywords = [
            "product",
            "price",
            "cart",
            "buy",
            "rating",
            "review",
            "stock",
            "detail",
            "description",
            "specification",
            "feature",
            "brand",
            "model",
            "delivery",
            "shipping",
        ]

        product_section = None
        for keyword in product_keywords:
            found = soup.find(id=lambda x: x and keyword in x.lower()) or soup.find(
                class_=lambda x: x and keyword in " ".join(x).lower() if x else False
            )
            if found:
                product_section = found
                break

        target = product_section or soup.find("body") or soup
        text = target.get_text(separator="\n", strip=True)
        lines = [line.strip() for line in text.splitlines() if line.strip() and len(line.strip()) > 2]
        compact = "\n".join(lines)
        if len(compact) > 8000:
            return compact[:8000] + "\n...[content truncated]"
        return compact

    async def _extract_with_ai(self, url: str, cleaned_text: str) -> Optional[Dict]:
        """Call LongCat OpenAI-compatible endpoint."""
        if not self.api_key or self.api_key == "PUT_YOUR_LONGCAT_API_KEY_HERE":
            logger.warning("LongCat API key not set, skipping AI extraction")
            return None

        user_prompt = (
            "Extract product information from this webpage.\n\n"
            f"URL: {url}\n\n"
            f"Page content:\n{cleaned_text}\n\n"
            "Return ONLY the JSON object with product data."
        )

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    f"{self.base_url}/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self.model,
                        "messages": [
                            {"role": "system", "content": self.system_prompt},
                            {"role": "user", "content": user_prompt},
                        ],
                        "max_tokens": 1000,
                        "temperature": 0.1,
                    },
                )

            if response.status_code != 200:
                logger.error("LongCat API error: %s - %s", response.status_code, response.text[:200])
                return None

            payload = response.json()
            content = payload.get("choices", [{}])[0].get("message", {}).get("content", "")
            return self._parse_ai_response(content)
        except Exception as exc:
            logger.error("LongCat API call failed: %s", exc)
            return None

    def _parse_ai_response(self, content: str) -> Optional[Dict]:
        """Parse JSON from raw model output."""
        if not content:
            return None

        cleaned = content.strip()
        if "```json" in cleaned:
            cleaned = cleaned.split("```json", 1)[1].split("```", 1)[0].strip()
        elif "```" in cleaned:
            cleaned = cleaned.split("```", 1)[1].split("```", 1)[0].strip()

        try:
            parsed = json.loads(cleaned)
            return parsed if isinstance(parsed, dict) else None
        except json.JSONDecodeError:
            pass

        match = re.search(r"\{[\s\S]*\}", cleaned)
        if match:
            try:
                parsed = json.loads(match.group(0))
                return parsed if isinstance(parsed, dict) else None
            except json.JSONDecodeError:
                return None
        return None

    def _validate_result(self, result: Dict, url: str) -> Dict:
        """Normalize model output to expected types and defaults."""
        for field in ["price", "original_price"]:
            value = result.get(field)
            if value is None:
                continue
            try:
                result[field] = float(str(value).replace(",", "").replace(" ", ""))
            except (ValueError, TypeError):
                result[field] = None

        discount = result.get("discount_percent")
        if discount is not None:
            try:
                result["discount_percent"] = float(str(discount).replace("%", ""))
            except (ValueError, TypeError):
                result["discount_percent"] = None

        if (
            result.get("discount_percent") is None
            and result.get("price") is not None
            and result.get("original_price") is not None
            and result["original_price"] > result["price"]
        ):
            result["discount_percent"] = round(
                (result["original_price"] - result["price"]) / result["original_price"] * 100,
                1,
            )

        in_stock = result.get("in_stock")
        if isinstance(in_stock, str):
            result["in_stock"] = in_stock.lower() in ["true", "yes", "1", "available", "in stock", "متوفر"]
        elif in_stock is None:
            result["in_stock"] = True

        rating = result.get("rating")
        if rating is not None:
            try:
                rating_value = float(rating)
                if rating_value > 5:
                    rating_value = rating_value / 2
                result["rating"] = round(min(5.0, max(0.0, rating_value)), 1)
            except (ValueError, TypeError):
                result["rating"] = None

        review_count = result.get("review_count")
        if review_count is not None:
            try:
                result["review_count"] = int(str(review_count).replace(",", "").replace(".", ""))
            except (ValueError, TypeError):
                result["review_count"] = None

        # Always re-derive currency from URL when AI didn't detect one,
        # or when it defaulted to USD for a non-US domain.
        detected = self._detect_currency_from_url(url)
        if not result.get("currency") or (
            result.get("currency") == "USD" and detected != "USD"
        ):
            result["currency"] = detected

        return result

    def _detect_currency_from_url(self, url: str) -> str:
        """Detect currency code from URL domain and path patterns."""
        url_lower = url.lower()
        # ordered from most specific to least specific
        currency_patterns = [
            ('amazon.eg',      'EGP'),
            ('amazon.sa',      'SAR'),
            ('amazon.ae',      'AED'),
            ('amazon.com.sa',  'SAR'),
            ('noon.com/egypt', 'EGP'),
            ('noon.com/saudi', 'SAR'),
            ('noon.com/uae',   'AED'),
            ('amazon.co.uk',   'GBP'),
            ('amazon.co.jp',   'JPY'),
            ('amazon.in',      'INR'),
            ('amazon.ca',      'CAD'),
            ('amazon.com.au',  'AUD'),
            ('amazon.de',      'EUR'),
            ('amazon.fr',      'EUR'),
            ('.eg/',            'EGP'),
            ('.eg?',            'EGP'),
            ('egypt',          'EGP'),
            ('-eg-',           'EGP'),
            ('saudi',          'SAR'),
            ('-sa-',           'SAR'),
            ('dubai',          'AED'),
            ('-ae-',           'AED'),
            ('uae',            'AED'),
        ]
        for pattern, currency in currency_patterns:
            if pattern in url_lower:
                return currency
        return 'USD'
