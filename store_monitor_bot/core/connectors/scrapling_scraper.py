"""
Universal product scraping via Scrapling (HTTP + stealth + dynamic browsers).
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any, Dict, Optional

from scrapling.fetchers import DynamicFetcher, Fetcher, StealthyFetcher

logger = logging.getLogger(__name__)

DOMAIN_INFO = {
    "amazon.eg": ("EGP", "ج.م", "Amazon مصر"),
    "amazon.sa": ("SAR", "ر.س", "Amazon السعودية"),
    "amazon.com.sa": ("SAR", "ر.س", "Amazon السعودية"),
    "amazon.ae": ("AED", "د.إ", "Amazon الإمارات"),
    "amazon.co.uk": ("GBP", "£", "Amazon UK"),
    "amazon.de": ("EUR", "€", "Amazon Germany"),
    "amazon.fr": ("EUR", "€", "Amazon France"),
    "amazon.com": ("USD", "$", "Amazon USA"),
    "noon.com/egypt": ("EGP", "ج.م", "Noon مصر"),
    "noon.com/saudi": ("SAR", "ر.س", "Noon السعودية"),
    "noon.com/uae": ("AED", "د.إ", "Noon الإمارات"),
    "jumia.com.eg": ("EGP", "ج.م", "Jumia مصر"),
    "extra.com": ("SAR", "ر.س", "Extra"),
    "jarir.com": ("SAR", "ر.س", "Jarir"),
    "sharafdg.com": ("AED", "د.إ", "Sharaf DG"),
    "carrefour": ("EGP", "ج.م", "Carrefour"),
}


def get_domain_info(url: str) -> Dict[str, str]:
    url_lower = url.lower()
    for pattern, (currency, symbol, store) in DOMAIN_INFO.items():
        if pattern in url_lower:
            return {"currency": currency, "symbol": symbol, "store": store}
    if ".eg" in url_lower or "egypt" in url_lower:
        return {"currency": "EGP", "symbol": "ج.م", "store": "متجر مصري"}
    if ".sa" in url_lower or "saudi" in url_lower:
        return {"currency": "SAR", "symbol": "ر.س", "store": "متجر سعودي"}
    if ".ae" in url_lower or "uae" in url_lower:
        return {"currency": "AED", "symbol": "د.إ", "store": "متجر إماراتي"}
    return {"currency": "USD", "symbol": "$", "store": "Online Store"}


def extract_number(text: str) -> Optional[float]:
    if not text:
        return None
    text = str(text).translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789"))
    nums = re.findall(r"[\d,]+\.?\d*", text)
    for n in nums:
        try:
            val = float(n.replace(",", ""))
            if 0.1 < val < 10_000_000:
                return val
        except ValueError:
            continue
    return None


def _css_first(page: Any, selector: str) -> Any:
    try:
        found = page.css(selector)
        return found.first
    except Exception:
        return None


def _elem_text(el: Any) -> str:
    if el is None:
        return ""
    try:
        return str(el.get_all_text(strip=True))
    except Exception:
        try:
            return str(el.text)
        except Exception:
            return ""


def _attr(el: Any, name: str) -> str:
    if el is None:
        return ""
    try:
        return str(el.attrib.get(name, "") or "")
    except Exception:
        return ""


class ScraplingProductScraper:
    """Universal product scraper using Scrapling fetchers."""

    PRICE_SELECTORS = [
        ".a-price .a-offscreen",
        "#priceblock_ourprice",
        "#priceblock_dealprice",
        ".priceToPay .a-offscreen",
        "#apex_offerDisplay_desktop .a-offscreen",
        '[class*="priceNow"]',
        '[class*="price-now"]',
        '[data-qa="price-now"]',
        '[itemprop="price"]',
        '[class*="sale-price"]',
        '[class*="current-price"]',
        '[class*="product-price"]',
        ".price",
        "#price",
    ]

    ORIGINAL_PRICE_SELECTORS = [
        ".a-text-price .a-offscreen",
        ".a-price.a-text-price .a-offscreen",
        '[class*="originalPrice"]',
        '[class*="priceWas"]',
        '[class*="old-price"]',
        ".a-text-strike",
        '[class*="strike"]',
    ]

    NAME_SELECTORS = [
        "#productTitle",
        'h1[class*="title"]',
        'h1[class*="name"]',
        "h1.product-title",
        '[itemprop="name"]',
        "h1",
    ]

    RATING_SELECTORS = [
        "#acrPopover",
        '[data-hook="average-star-rating"]',
        '[class*="rating-value"]',
        '[itemprop="ratingValue"]',
    ]

    async def scrape(self, url: str) -> Optional[Dict]:
        result = await self._try_http(url)
        if result and result.get("name") and result.get("price") is not None:
            return result

        logger.info("HTTP incomplete, trying Stealth for %s", url)
        result = await self._try_stealth(url)
        if result and result.get("name"):
            return result

        logger.info("Trying Dynamic browser for %s", url)
        return await self._try_dynamic(url)

    async def _try_http(self, url: str) -> Optional[Dict]:
        def _fetch():
            try:
                return Fetcher.get(
                    url,
                    stealthy_headers=True,
                    follow_redirects=True,
                    verify=True,
                    timeout=25,
                )
            except Exception:
                return Fetcher.get(
                    url,
                    stealthy_headers=True,
                    follow_redirects=True,
                    verify=False,
                    timeout=25,
                )

        try:
            page = await asyncio.to_thread(_fetch)
            return self._parse_page(page, url)
        except Exception as e:
            logger.warning("HTTP failed: %s", e)
            return None

    async def _try_stealth(self, url: str) -> Optional[Dict]:
        try:
            page = await asyncio.to_thread(
                StealthyFetcher.fetch,
                url,
                headless=True,
                network_idle=True,
                disable_resources=True,
                timeout=45_000,
            )
            return self._parse_page(page, url)
        except Exception as e:
            logger.warning("Stealth failed: %s", e)
            return None

    async def _try_dynamic(self, url: str) -> Optional[Dict]:
        try:
            page = await asyncio.to_thread(
                DynamicFetcher.fetch,
                url,
                headless=True,
                network_idle=True,
                disable_resources=True,
                timeout=60_000,
            )
            return self._parse_page(page, url)
        except Exception as e:
            logger.error("Dynamic failed: %s", e)
            return None

    def _parse_page(self, page: Any, url: str) -> Optional[Dict]:
        result: Dict[str, Any] = {}
        domain = get_domain_info(url)
        result.update(domain)

        for script in page.find_all("script", type="application/ld+json"):
            raw = _elem_text(script).strip()
            if not raw:
                continue
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue

            if isinstance(data, list):
                data = next((d for d in data if isinstance(d, dict) and d.get("@type") == "Product"), {})
            if not isinstance(data, dict):
                continue
            if data.get("@graph"):
                inner = next(
                    (d for d in data["@graph"] if isinstance(d, dict) and d.get("@type") == "Product"),
                    {},
                )
                data = inner if inner else data
            if data.get("@type") != "Product":
                continue

            if data.get("name") and not result.get("name"):
                result["name"] = data["name"]

            offers = data.get("offers", {})
            if isinstance(offers, list):
                offers = offers[0] if offers else {}
            if isinstance(offers, dict):
                if offers.get("price"):
                    p = extract_number(str(offers["price"]))
                    if p:
                        result["price"] = p
                if offers.get("priceCurrency"):
                    result["currency"] = offers["priceCurrency"]
                avail = str(offers.get("availability", ""))
                if "InStock" in avail:
                    result["in_stock"] = True
                elif "OutOfStock" in avail:
                    result["in_stock"] = False

            rating = data.get("aggregateRating") or {}
            if isinstance(rating, dict):
                if rating.get("ratingValue"):
                    try:
                        result["rating"] = float(rating["ratingValue"])
                    except (ValueError, TypeError):
                        pass
                if rating.get("reviewCount"):
                    try:
                        result["review_count"] = int(rating["reviewCount"])
                    except (ValueError, TypeError):
                        pass

            brand = data.get("brand", {})
            if isinstance(brand, dict):
                brand = brand.get("name")
            if brand:
                result["brand"] = brand

            img = data.get("image")
            if isinstance(img, list):
                img = img[0]
            if isinstance(img, dict):
                img = img.get("url")
            if isinstance(img, str) and img.startswith("http"):
                result["image_url"] = img

            if result.get("name"):
                break

        if not result.get("name"):
            for sel in self.NAME_SELECTORS:
                el = _css_first(page, sel)
                name = _elem_text(el)
                if name and len(name) > 3:
                    result["name"] = name[:300]
                    break

        if result.get("price") is None:
            for sel in self.PRICE_SELECTORS:
                el = _css_first(page, sel)
                if not el:
                    continue
                p = extract_number(_elem_text(el)) or extract_number(_attr(el, "content"))
                if p:
                    result["price"] = p
                    break

        if not result.get("original_price"):
            for sel in self.ORIGINAL_PRICE_SELECTORS:
                el = _css_first(page, sel)
                if not el:
                    continue
                p = extract_number(_elem_text(el))
                if p and p > (result.get("price") or 0):
                    result["original_price"] = p
                    break

        if not result.get("rating"):
            for sel in self.RATING_SELECTORS:
                el = _css_first(page, sel)
                if not el:
                    continue
                text = _attr(el, "title") or _elem_text(el)
                m = re.search(r"([\d.]+)\s*(?:out of|من|/)\s*5", text)
                if m:
                    result["rating"] = float(m.group(1))
                    break

        if not result.get("review_count"):
            for sel in (
                "#acrCustomerReviewText",
                '[data-hook="total-review-count"]',
                '[class*="review-count"]',
            ):
                el = _css_first(page, sel)
                if not el:
                    continue
                text = _elem_text(el).replace(",", "")
                m = re.search(r"(\d+)", text)
                if m:
                    result["review_count"] = int(m.group(1))
                    break

        if result.get("in_stock") is None:
            for sel in ("#availability span", '[class*="availability"]', '[class*="stock"]'):
                el = _css_first(page, sel)
                if not el:
                    continue
                text = _elem_text(el).lower()
                if not text:
                    continue
                out_words = ("out of stock", "unavailable", "غير متوفر", "نفد", "sold out")
                result["in_stock"] = not any(w in text for w in out_words)
                result["stock_text"] = _elem_text(el)
                break

        if result.get("in_stock") is None:
            result["in_stock"] = True

        price = result.get("price")
        orig = result.get("original_price")
        if price and orig and orig > price:
            result["discount_percent"] = round((orig - price) / orig * 100, 1)

        if not result.get("image_url"):
            for sel in ("#landingImage", "#imgBlkFront", '[class*="product-image"] img'):
                el = _css_first(page, sel)
                if not el:
                    continue
                img = (
                    _attr(el, "data-old-hires")
                    or _attr(el, "data-src")
                    or _attr(el, "src")
                )
                if img and img.startswith("http"):
                    result["image_url"] = img
                    break

        name = result.get("name") or ""
        if not name or name.lower() in ("access denied", "robot check", "sorry! we couldn't find that page"):
            return None
        return result


_scraper: Optional[ScraplingProductScraper] = None


def get_scraper() -> ScraplingProductScraper:
    global _scraper
    if _scraper is None:
        _scraper = ScraplingProductScraper()
    return _scraper
