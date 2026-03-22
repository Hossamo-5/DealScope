"""
موصل أمازون (Amazon Connector)
================================
مسؤول عن استخراج بيانات المنتجات من موقع أمازون
يدعم Amazon.com و Amazon.sa و Amazon.ae وغيرها

⚠️ ملاحظة مهمة:
أمازون تغير HTML باستمرار. إذا توقف الـ scraping:
1. افحص الـ selectors في devtools
2. حدّث الـ CSS selectors أدناه
3. أو استخدم Amazon Product API (يحتاج مفتاح API)
"""

import re
import asyncio
import logging
from typing import Optional, Dict
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class AmazonConnector:
    """
    موصل أمازون
    يستخرج: الاسم، السعر، السعر الأصلي، الخصم، الكوبون،
    المخزون، التقييم، عدد المراجعات، الصورة، البراند
    """

    # أسماء الدومينات التي يدعمها هذا الموصل
    SUPPORTED_DOMAINS = [
        "amazon.com", "amazon.sa", "amazon.ae",
        "amazon.co.uk", "amazon.de", "amazon.fr",
        "amazon.com.au", "amazon.ca", "amazon.eg"
    ]

    # خريطة العملات حسب الدومين
    CURRENCY_MAP = {
        # دول عربية
        'amazon.eg':     ('EGP', 'مصر'),
        'amazon.sa':     ('SAR', 'السعودية'),
        'amazon.ae':     ('AED', 'الإمارات'),
        'amazon.com.sa': ('SAR', 'السعودية'),
        # دول أخرى
        'amazon.co.uk':  ('GBP', 'بريطانيا'),
        'amazon.co.jp':  ('JPY', 'اليابان'),
        'amazon.com.au': ('AUD', 'أستراليا'),
        'amazon.com.br': ('BRL', 'البرازيل'),
        'amazon.com.mx': ('MXN', 'المكسيك'),
        'amazon.com.tr': ('TRY', 'تركيا'),
        'amazon.de':     ('EUR', 'ألمانيا'),
        'amazon.fr':     ('EUR', 'فرنسا'),
        'amazon.it':     ('EUR', 'إيطاليا'),
        'amazon.es':     ('EUR', 'إسبانيا'),
        'amazon.nl':     ('EUR', 'هولندا'),
        'amazon.pl':     ('PLN', 'بولندا'),
        'amazon.se':     ('SEK', 'السويد'),
        'amazon.sg':     ('SGD', 'سنغافورة'),
        'amazon.ca':     ('CAD', 'كندا'),
        'amazon.in':     ('INR', 'الهند'),
        # الافتراضي أمريكا
        'amazon.com':    ('USD', 'أمريكا'),
    }

    @staticmethod
    def detect_currency(url: str) -> str:
        """
        استخراج العملة من دومين أمازون.
        amazon.eg → EGP | amazon.sa → SAR | amazon.ae → AED | amazon.com → USD
        """
        url_lower = url.lower()
        for domain, (currency, _country) in AmazonConnector.CURRENCY_MAP.items():
            if domain in url_lower:
                return currency
        return 'USD'

    @staticmethod
    def detect_store_name(url: str) -> str:
        """يرجع اسم المتجر المحلي (مثلاً: Amazon مصر)"""
        url_lower = url.lower()
        for domain, (_currency, country) in AmazonConnector.CURRENCY_MAP.items():
            if domain in url_lower:
                return f'Amazon {country}'
        return 'Amazon'

    def __init__(self, session=None):
        """
        session: aiohttp session أو httpx session
        يمكن تمرير session موجودة لإعادة الاستخدام وتوفير الاتصالات
        """
        self.session = session

    @staticmethod
    def can_handle(url: str) -> bool:
        """
        هل هذا الموصل يدعم هذا الرابط؟
        يُستدعى قبل بدء السكرابينج للتحقق من نوع الموقع
        """
        try:
            domain = urlparse(url).netloc.lower()
            return any(d in domain for d in AmazonConnector.SUPPORTED_DOMAINS)
        except Exception:
            return False

    @staticmethod
    def extract_asin(url: str) -> Optional[str]:
        """
        استخراج ASIN من رابط أمازون
        ASIN = معرف المنتج الفريد في أمازون
        مثال: https://www.amazon.com/dp/B08L5TNJHG → B08L5TNJHG
        """
        patterns = [
            r'/dp/([A-Z0-9]{10})',
            r'/product/([A-Z0-9]{10})',
            r'ASIN=([A-Z0-9]{10})',
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None

    # ------------------------------------------------------------------
    # Price extraction helper
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_price(text: str) -> Optional[float]:
        """Extract float price from any text format"""
        if not text:
            return None

        # Arabic numerals to English
        arabic = '٠١٢٣٤٥٦٧٨٩'
        english = '0123456789'
        trans = str.maketrans(arabic, english)
        text = text.translate(trans)

        # Remove currency symbols
        text = re.sub(
            r'(?:EGP|SAR|AED|USD|GBP|EUR|CAD|AUD|JPY|INR|BRL|MXN|TRY|PLN|SEK|SGD|ج\.م|ر\.س|د\.إ|\$|£|€)',
            '',
            text,
            flags=re.IGNORECASE,
        )

        # Find number with optional decimal
        # Handle formats: 1,299.00 or 1.299,00 or 1299
        numbers = re.findall(r'[\d,]+\.?\d*', text)

        for num_str in numbers:
            # Remove thousands separator
            clean = num_str.replace(',', '')
            try:
                val = float(clean)
                if val > 0:
                    return val
            except ValueError:
                continue

        return None

    # ------------------------------------------------------------------
    # Main scrape entry-point
    # ------------------------------------------------------------------

    async def scrape(self, url: str) -> Optional[Dict]:
        # Try HTTP first (fast)
        try:
            result = await self._scrape_http(url)

            # Check if we got price
            if result and result.get('price'):
                return result

            # Amazon Egypt/dynamic pages need Playwright
            logger.info("HTTP incomplete for %s, trying Playwright", url)
            playwright_result = await self._scrape_with_playwright(url)

            if playwright_result:
                # Merge: use playwright data, fill gaps with HTTP
                if result:
                    for key, val in result.items():
                        if val and not playwright_result.get(key):
                            playwright_result[key] = val
                return playwright_result

            return result

        except Exception as e:
            logger.error("Amazon scraping failed for %s: %s", url, e)
            return None

    # ------------------------------------------------------------------
    # HTTP scrape path
    # ------------------------------------------------------------------

    async def _scrape_http(self, url: str) -> Optional[Dict]:
        """Try HTTP scraping (fast but may miss JS content)"""
        import httpx

        headers = {
            'User-Agent': (
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/120.0.0.0 Safari/537.36'
            ),
            'Accept-Language': 'ar-EG,ar;q=0.9,en;q=0.8',
            'Accept': 'text/html,application/xhtml+xml',
        }

        try:
            async with httpx.AsyncClient(
                headers=headers,
                timeout=15,
                follow_redirects=True,
                http2=False
            ) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    return self._parse_amazon_html(resp.text, url)
        except Exception as e:
            logger.warning("HTTP scrape failed: %s", e)

        return None

    async def _scrape_with_requests(self, url: str) -> Optional[Dict]:
        """Backward-compatible alias for older callers/tests."""
        return await self._scrape_http(url)

    # ------------------------------------------------------------------
    # HTML parser – comprehensive selectors
    # ------------------------------------------------------------------

    def _parse_amazon_html(self, html: str, url: str) -> Optional[Dict]:
        from bs4 import BeautifulSoup

        if hasattr(html, "select_one"):
            soup = html
        else:
            soup = BeautifulSoup(html, 'html.parser')
        result = {}

        # ── NAME ──────────────────────────────────
        name_selectors = [
            '#productTitle',
            '#title span',
            'h1.product-title',
            'h1#title',
            'span#productTitle',
        ]
        for sel in name_selectors:
            el = soup.select_one(sel)
            if el and el.get_text(strip=True):
                result['name'] = el.get_text(strip=True)
                break

        # ── PRICE ─────────────────────────────────
        whole = soup.select_one('.a-price-whole')
        if whole:
            whole_text = whole.get_text(strip=True).replace(',', '').rstrip('.')
            fraction = soup.select_one('.a-price-fraction')
            frac_text = fraction.get_text(strip=True) if fraction else '00'
            try:
                result['price'] = float(f'{whole_text}.{frac_text}')
            except ValueError:
                pass

        # Amazon has many price formats - try all
        price_selectors = [
            # Main price
            '.a-price .a-offscreen',
            '#priceblock_ourprice',
            '#priceblock_dealprice',
            '#price_inside_buybox',
            '#apex_offerDisplay_desktop .a-price',
            '.priceToPay .a-offscreen',
            '.apexPriceToPay .a-offscreen',
            '#corePrice_feature_div .a-offscreen',
            '#corePriceDisplay_desktop_feature_div .a-offscreen',
            '.a-price[data-a-color="price"] .a-offscreen',
        ]

        if 'price' not in result:
            for sel in price_selectors:
                el = soup.select_one(sel)
                if el:
                    text = el.get_text(strip=True)
                    price = self._extract_price(text)
                    if price and price > 0:
                        result['price'] = price
                        break

        # If still no price, try JavaScript data
        if 'price' not in result:
            scripts = soup.find_all('script', type='text/javascript')
            for script in scripts:
                if script.string and 'priceAmount' in script.string:
                    m = re.search(
                        r'"priceAmount"\s*:\s*([\d.]+)',
                        script.string
                    )
                    if m:
                        result['price'] = float(m.group(1))
                        break

        # ── ORIGINAL PRICE (before discount) ──────
        original_selectors = [
            '.a-price.a-text-price .a-offscreen',
            '#priceblock_saleprice',
            '.priceBlockStrikePriceString',
            '.a-text-strike',
            '#listPrice',
            '.basisPrice .a-offscreen',
            '.a-text-price[data-a-strike] .a-offscreen',
        ]

        for sel in original_selectors:
            el = soup.select_one(sel)
            if el:
                text = el.get_text(strip=True)
                orig = self._extract_price(text)
                if orig and orig > result.get('price', 0):
                    result['original_price'] = orig
                    break

        # ── DISCOUNT ──────────────────────────────
        discount_selectors = [
            '.savingsPercentage',
            '#savingsPercentage',
            '.a-color-price.a-text-bold',
            '[id*="saving"] .a-color-price',
            '.reinventPriceAccordionT2',
        ]

        for sel in discount_selectors:
            el = soup.select_one(sel)
            if el:
                text = el.get_text(strip=True)
                m = re.search(r'(\d+)%', text)
                if m:
                    result['discount_percent'] = float(m.group(1))
                    break

        # Calculate discount if not found
        if ('discount_percent' not in result and
                result.get('price') and
                result.get('original_price')):
            orig = result['original_price']
            price = result['price']
            if orig > price:
                result['discount_percent'] = round(
                    (orig - price) / orig * 100, 1
                )

        # ── COUPON ────────────────────────────────
        coupon_selectors = [
            '#couponBadge',
            '.promoPriceBlockMessage',
            '[id*="coupon"]',
            '.a-box.a-color-alternate-background',
        ]
        for sel in coupon_selectors:
            el = soup.select_one(sel)
            if el:
                text = el.get_text(strip=True)
                if text and len(text) < 200:
                    result['coupon'] = text
                    break

        # ── RATING ────────────────────────────────
        rating_selectors = [
            '#acrPopover',
            '#averageCustomerReviews .a-icon-alt',
            'span[data-hook="rating-out-of-text"]',
            '.a-icon-star .a-icon-alt',
            'span.a-icon-alt',
            '#acrPopover span',
            'i.a-icon-star span',
        ]

        for sel in rating_selectors:
            el = soup.select_one(sel)
            if el:
                text = (el.get('title') or
                        el.get_text(strip=True))
                m = re.search(r'([\d.]+)\s*(?:out of|من|/)\s*5', text)
                if m:
                    result['rating'] = float(m.group(1))
                    break

        # Try title attribute
        if 'rating' not in result:
            el = soup.select_one('#acrPopover')
            if el and el.get('title'):
                m = re.search(r'([\d.]+)', el['title'])
                if m:
                    try:
                        result['rating'] = float(m.group(1))
                    except ValueError:
                        pass

        # ── REVIEW COUNT ──────────────────────────
        review_selectors = [
            '#acrCustomerReviewText',
            'span[data-hook="total-review-count"]',
            '#totalReviewCount',
            '#reviews-medley-footer .a-size-base',
        ]

        for sel in review_selectors:
            el = soup.select_one(sel)
            if el:
                text = el.get_text(strip=True)
                # Handle formats: "1,234 ratings" or "1234"
                text = text.replace(',', '').replace('.', '')
                m = re.search(r'(\d+)', text)
                if m:
                    result['review_count'] = int(m.group(1))
                    break

        # ── STOCK STATUS ──────────────────────────
        stock_selectors = [
            '#availability span',
            '#availability_feature_div span',
            '#outOfStock',
            '.qa-buybox-title',
        ]

        in_stock = True  # default
        stock_text = ''

        for sel in stock_selectors:
            el = soup.select_one(sel)
            if el:
                text = el.get_text(strip=True).lower()
                if text:
                    stock_text = el.get_text(strip=True)
                    out_keywords = [
                        'out of stock', 'unavailable',
                        'غير متوفر', 'غير متاح',
                        'not available'
                    ]
                    in_stock = not any(
                        kw in text for kw in out_keywords
                    )
                    break

        result['in_stock'] = in_stock
        result['stock_text'] = stock_text or (
            'متوفر' if in_stock else 'غير متوفر'
        )

        # ── IMAGE ─────────────────────────────────
        image_selectors = [
            '#landingImage',
            '#imgBlkFront',
            '#main-image',
            '.a-dynamic-image[data-old-hires]',
            '#imageBlock img',
            '#altImages img',
        ]

        for sel in image_selectors:
            el = soup.select_one(sel)
            if el:
                # Try high-res first
                img_url = (
                    el.get('data-old-hires') or
                    el.get('data-a-hires') or
                    el.get('data-src') or
                    el.get('src', '')
                )
                if img_url and img_url.startswith('http'):
                    result['image_url'] = img_url
                    break

        # Try to find image in JavaScript
        if 'image_url' not in result:
            scripts = soup.find_all('script')
            for script in scripts:
                if script.string and 'hiRes' in script.string:
                    m = re.search(
                        r'"hiRes"\s*:\s*"([^"]+)"',
                        script.string
                    )
                    if m:
                        result['image_url'] = m.group(1)
                        break

        # ── BRAND ─────────────────────────────────
        brand_selectors = [
            '#bylineInfo',
            '#brand',
            '.po-brand .po-break-word',
            'a#bylineInfo',
            'tr.po-brand td.po-break-word',
        ]

        for sel in brand_selectors:
            el = soup.select_one(sel)
            if el:
                text = el.get_text(strip=True)
                text = re.sub(
                    r'^(Visit the|Brand:|العلامة التجارية:)\s*',
                    '',
                    text,
                    flags=re.I
                ).strip()
                if text and len(text) < 100:
                    result['brand'] = text
                    break

        # ── CURRENCY ──────────────────────────────
        result['currency'] = self.detect_currency(url)
        result['store'] = self.detect_store_name(url)
        result['asin'] = self.extract_asin(url)

        return result

    # ------------------------------------------------------------------
    # Playwright scrape path (JS-heavy pages)
    # ------------------------------------------------------------------

    async def _scrape_with_playwright(self, url: str) -> Optional[Dict]:
        """
        السكرابينج باستخدام Playwright (متصفح كامل)
        يُستخدم فقط عند فشل الطريقة الأولى
        أبطأ لكن أقوى - يتجاوز JavaScript protection

        ⚠️ يحتاج تثبيت: pip install playwright && playwright install chromium
        """
        try:
            from playwright.async_api import async_playwright

            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)

                context = await browser.new_context(
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36"
                    ),
                    locale="ar-EG",
                )

                page = await context.new_page()
                await page.goto(url, wait_until="networkidle", timeout=30000)

                # Wait a bit for dynamic price elements to render
                await asyncio.sleep(2)

                html = await page.content()
                await browser.close()

                return self._parse_amazon_html(html, url)

        except Exception as e:
            logger.error("Playwright scraping failed: %s", e)
            return None
