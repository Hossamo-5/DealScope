"""
الموصل العام (Generic Connector)
==================================
يعمل مع أي موقع Shopify أو WooCommerce أو مواقع عامة
يحاول استخراج البيانات بطرق متعددة

وأيضاً: مدير الموصلات (Connector Manager)
يختار الموصل المناسب لكل رابط تلقائياً
"""

import re
import logging
from typing import Optional, Dict
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


def detect_currency_from_url(url: str) -> str:
    """
    استخراج رمز العملة من الدومين أو مسار الرابط.
    يُستخدم كـ fallback عندما لا يحدد الموقع العملة صراحةً.
    """
    url_lower = url.lower()
    # ordered from most specific to least specific
    patterns = [
        ('.eg/',     'EGP'),
        ('.eg?',     'EGP'),
        ('egypt',    'EGP'),
        ('-eg-',     'EGP'),
        ('.sa/',     'SAR'),
        ('.sa?',     'SAR'),
        ('saudi',    'SAR'),
        ('-sa-',     'SAR'),
        ('.ae/',     'AED'),
        ('.ae?',     'AED'),
        ('dubai',    'AED'),
        ('uae',      'AED'),
        ('-ae-',     'AED'),
        ('.co.uk',   'GBP'),
        ('.co.jp',   'JPY'),
        ('.com.au',  'AUD'),
        ('.com.br',  'BRL'),
        ('.com.mx',  'MXN'),
        ('.de/',     'EUR'),
        ('.fr/',     'EUR'),
        ('.it/',     'EUR'),
        ('.es/',     'EUR'),
        ('.nl/',     'EUR'),
        ('.ca/',     'CAD'),
        ('.in/',     'INR'),
    ]
    for pattern, currency in patterns:
        if pattern in url_lower:
            return currency
    return 'USD'


# ======================================================
# موصل Shopify
# ======================================================

class ShopifyConnector:
    """
    موصل للمتاجر المبنية على Shopify
    يستخدم Shopify JSON API المتاح على كل متجر Shopify
    مثال: https://store.com/products/product-name.json
    """

    @staticmethod
    def can_handle(url: str) -> bool:
        """
        التحقق هل الموقع مبني على Shopify
        معظم متاجر Shopify تحتوي على /products/ في الرابط
        أو ترجع header x-shopify-stage
        """
        return "/products/" in url and not "amazon" in url.lower()

    async def scrape(self, url: str) -> Optional[Dict]:
        """
        استخراج بيانات منتج Shopify
        يستخدم JSON endpoint مباشرة بدون سكرابينج HTML
        أسرع وأكثر استقراراً من HTML scraping
        """
        import httpx

        try:
            # تحويل رابط المنتج إلى JSON endpoint
            # مثال: /products/iphone-case → /products/iphone-case.json
            json_url = url.split("?")[0].rstrip("/") + ".json"

            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(json_url)

                if response.status_code != 200:
                    return None

                data = response.json()
                product = data.get("product", {})

                if not product:
                    return None

                # استخراج بيانات الـ variant الأول (المنتج الرئيسي)
                variants = product.get("variants", [])
                first_variant = variants[0] if variants else {}

                price = None
                if first_variant.get("price"):
                    try:
                        price = float(first_variant["price"])
                    except (ValueError, TypeError):
                        pass

                in_stock = first_variant.get("available", True)

                # الصورة الأولى للمنتج
                images = product.get("images", [])
                image_url = images[0].get("src") if images else None

                return {
                    "name": product.get("title"),
                    "price": price,
                    "currency": detect_currency_from_url(url),
                    "in_stock": in_stock,
                    "image_url": image_url,
                    "rating": None,
                    "review_count": None,
                    "store": urlparse(url).netloc,
                }

        except Exception as e:
            logger.error(f"Shopify scraping failed for {url}: {e}")
            return None


# ======================================================
# موصل WooCommerce
# ======================================================

class WooCommerceConnector:
    """
    موصل للمتاجر المبنية على WooCommerce (WordPress)
    يحاول استخدام WooCommerce REST API
    """

    @staticmethod
    def can_handle(url: str) -> bool:
        """
        WooCommerce عادةً يستخدم /product/ في الرابط
        """
        return "/product/" in url.lower() and not "amazon" in url.lower()

    async def scrape(self, url: str) -> Optional[Dict]:
        """
        استخراج بيانات منتج WooCommerce
        يستخدم HTML scraping مع Open Graph meta tags
        """
        import httpx
        from bs4 import BeautifulSoup

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        }

        try:
            async with httpx.AsyncClient(headers=headers, timeout=15) as client:
                response = await client.get(url, follow_redirects=True)

                if response.status_code != 200:
                    return None

                soup = BeautifulSoup(response.text, "html.parser")
                return self._parse_woo_html(soup, url)

        except Exception as e:
            logger.error(f"WooCommerce scraping failed: {e}")
            return None

    def _parse_woo_html(self, soup, url: str) -> Optional[Dict]:
        """تحليل HTML صفحة WooCommerce"""
        # اسم المنتج
        name_el = (
            soup.find("h1", {"class": "product_title"}) or
            soup.find("h1", {"class": "entry-title"})
        )
        name = name_el.get_text(strip=True) if name_el else None

        # السعر - WooCommerce يضع السعر في .price
        price = None
        price_el = soup.find("p", {"class": "price"})
        if price_el:
            # الحصول على السعر الحالي (ins = inserted = سعر جديد)
            ins_el = price_el.find("ins")
            price_text = ins_el.get_text() if ins_el else price_el.get_text()
            price_numbers = re.findall(r"[\d.,]+", price_text)
            if price_numbers:
                try:
                    price = float(price_numbers[0].replace(",", ""))
                except ValueError:
                    pass

        # حالة المخزون
        in_stock = True
        stock_el = soup.find("p", {"class": "stock"})
        if stock_el:
            stock_text = stock_el.get_text(strip=True).lower()
            in_stock = "out-of-stock" not in stock_el.get("class", [])

        # الصورة الرئيسية
        image_url = None
        img_el = soup.find("figure", {"class": "woocommerce-product-gallery__image"})
        if img_el:
            img = img_el.find("img")
            if img:
                image_url = img.get("src")

        # Open Graph كبديل للبيانات
        if not name:
            og_name = soup.find("meta", {"property": "og:title"})
            if og_name:
                name = og_name.get("content")

        if not image_url:
            og_img = soup.find("meta", {"property": "og:image"})
            if og_img:
                image_url = og_img.get("content")

        return {
            "name": name,
            "price": price,
            "currency": detect_currency_from_url(url),
            "in_stock": in_stock,
            "image_url": image_url,
            "rating": None,
            "review_count": None,
            "store": urlparse(url).netloc,
        }


# ======================================================
# الموصل العام (Fallback لأي موقع)
# ======================================================

class GenericConnector:
    """
    موصل عام يعمل مع أي موقع
    يستخدم Open Graph meta tags والـ JSON-LD structured data
    """

    @staticmethod
    def can_handle(url: str) -> bool:
        """يقبل أي رابط كـ fallback"""
        return True

    async def scrape(self, url: str) -> Optional[Dict]:
        """
        استخراج بيانات أي منتج من أي موقع
        يعتمد على Schema.org وOpen Graph meta tags
        """
        import httpx
        from bs4 import BeautifulSoup
        import json as json_lib

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        }

        try:
            async with httpx.AsyncClient(headers=headers, timeout=15, follow_redirects=True) as client:
                response = await client.get(url)
                if response.status_code != 200:
                    return None

                soup = BeautifulSoup(response.text, "html.parser")

                # محاولة 1: Schema.org JSON-LD
                data = self._extract_json_ld(soup)
                if data:
                    return data

                # محاولة 2: Open Graph meta tags
                data = self._extract_open_graph(soup, url)
                if data:
                    return data

                return None

        except Exception as e:
            logger.error(f"Generic scraping failed for {url}: {e}")
            return None

    def _extract_json_ld(self, soup) -> Optional[Dict]:
        """
        استخراج بيانات Schema.org JSON-LD
        معظم المتاجر الحديثة تضيف هذه البيانات للـ SEO
        """
        import json as json_lib

        scripts = soup.find_all("script", {"type": "application/ld+json"})
        for script in scripts:
            try:
                data = json_lib.loads(script.string)
                # قد يكون array أو object
                if isinstance(data, list):
                    data = next((d for d in data if d.get("@type") == "Product"), None)

                if data and data.get("@type") == "Product":
                    offers = data.get("offers", {})
                    if isinstance(offers, list):
                        offers = offers[0]

                    price = None
                    if offers.get("price"):
                        try:
                            price = float(str(offers["price"]).replace(",", ""))
                        except (ValueError, TypeError):
                            pass

                    in_stock = True
                    availability = offers.get("availability", "")
                    in_stock = "InStock" in availability or "InStoreOnly" in availability

                    return {
                        "name": data.get("name"),
                        "price": price,
                        "currency": offers.get("priceCurrency", "USD"),
                        "in_stock": in_stock,
                        "image_url": (
                            data.get("image")[0] if isinstance(data.get("image"), list)
                            else data.get("image")
                        ),
                        "rating": (
                            data.get("aggregateRating", {}).get("ratingValue")
                            if data.get("aggregateRating") else None
                        ),
                        "review_count": (
                            data.get("aggregateRating", {}).get("reviewCount")
                            if data.get("aggregateRating") else None
                        ),
                        "store": None,
                    }
            except Exception:
                continue
        return None

    def _extract_open_graph(self, soup, url: str) -> Optional[Dict]:
        """استخراج Open Graph meta tags كبديل"""
        def og(prop):
            el = soup.find("meta", {"property": f"og:{prop}"})
            return el.get("content") if el else None

        name = og("title") or soup.title.get_text() if soup.title else None

        return {
            "name": name,
            "price": None,
            "currency": detect_currency_from_url(url),
            "in_stock": None,
            "image_url": og("image"),
            "rating": None,
            "review_count": None,
            "store": urlparse(url).netloc,
        }


# ======================================================
# 🎯 مدير الموصلات - Scrapling + AI + fallback تقليدي
# ======================================================

class ConnectorManager:
    """
    Scrapling أولاً (HTTP / Stealth / Dynamic)، ثم تعبئة الفجوات بالذكاء الاصطناعي،
    ثم الموصلات التقليدية عند الفشل.
    """

    def __init__(self):
        from core.connectors.scrapling_scraper import get_scraper
        from core.connectors.amazon import AmazonConnector
        from config.settings import LONGCAT_API_KEY, AI_SCRAPING_ENABLED

        self.scraper = get_scraper()
        self.amazon = AmazonConnector()
        self.connectors = [
            self.amazon,
            ShopifyConnector(),
            WooCommerceConnector(),
            GenericConnector(),
        ]
        self.traditional_connectors = self.connectors
        self.ai_scraper = None
        self.ai_mode = "fallback"
        self.ai_enabled = (
            AI_SCRAPING_ENABLED
            and bool(LONGCAT_API_KEY)
            and LONGCAT_API_KEY != "PUT_YOUR_LONGCAT_API_KEY_HERE"
        )

    async def scrape(self, url: str) -> Optional[Dict]:
        from utils.url_validator import validate_scrape_url

        if not validate_scrape_url(url):
            logger.warning("URL rejected by SSRF validator: %s", url)
            return None

        if self.ai_scraper and self.ai_mode in {"fallback", "primary"}:
            if self.ai_mode == "primary":
                ai_result = await self.ai_scraper.scrape(url)
                if ai_result and self._is_complete(ai_result):
                    return ai_result
                logger.info("AI incomplete, trying traditional connectors")
                traditional = await self._traditional_scrape(url)
                if ai_result and traditional:
                    return self._merge_results(traditional, ai_result)
                return traditional or ai_result

            traditional = await self._traditional_scrape(url)
            if traditional and self._is_complete(traditional):
                return traditional
            ai_result = await self.ai_scraper.scrape(url)
            if ai_result:
                return self._merge_results(traditional or {}, ai_result)
            return traditional

        if not any(c.can_handle(url) for c in self.connectors):
            return None

        result = await self.scraper.scrape(url)

        if not result or not self._is_complete(result):
            fb = await self._traditional_scrape(url)
            if fb:
                result = self._merge_results(result or {}, fb)

        if self.ai_enabled:
            from core.connectors.ai_scraper import AIProductScraper
            if result:
                missing = [
                    f for f in ("price", "rating", "brand")
                    if result.get(f) in (None, "")
                ]
                if missing:
                    ai_result = await AIProductScraper().scrape(url)
                    if ai_result:
                        result = self._merge_results(result, ai_result)
            else:
                result = await AIProductScraper().scrape(url)

        return result

    def can_handle(self, url: str) -> bool:
        return True

    async def _traditional_scrape(self, url: str) -> Optional[Dict]:
        for connector in self.traditional_connectors:
            if connector.can_handle(url):
                res = await connector.scrape(url)
                if res:
                    return res
        return None

    def _is_complete(self, result: Dict) -> bool:
        if not result:
            return False
        return bool(result.get("name")) and result.get("price") is not None

    def _merge_results(self, traditional: Dict, ai: Dict) -> Dict:
        merged = dict(ai)
        for key, value in traditional.items():
            if value is not None:
                merged[key] = value
        return merged

    @staticmethod
    def detect_store_type(url: str) -> str:
        from core.connectors.amazon import AmazonConnector
        if AmazonConnector.can_handle(url):
            return "amazon"
        if "/products/" in url:
            return "shopify"
        if "/product/" in url.lower():
            return "woocommerce"
        return "custom"
