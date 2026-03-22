"""
محرك المراقبة (Monitoring Engine)
=====================================
القلب الحقيقي للنظام
مسؤول عن:
- جدولة الفحص الدوري لجميع المنتجات
- اكتشاف التغيرات في الأسعار والمخزون
- حساب نقاط الفرص (Opportunity Score)
- إرسال الفرص للإدارة عبر تيليغرام
- إرسال التنبيهات للمستخدمين
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict

from config.settings import (
    SCAN_INTERVALS, MIN_DISCOUNT_PERCENT, SCORE_WEIGHTS,
    SCORE_LEVELS, SCRAPING_DELAY_SECONDS, MAX_RETRY_ATTEMPTS
)

logger = logging.getLogger(__name__)

# حالة محرك المراقبة (للداشبورد)
monitoring_engine_running = False
monitoring_engine_last_run: Optional[datetime] = None


# ======================================================
# 📊 حاسب نقاط الفرص (Opportunity Scorer)
# ======================================================

class OpportunityScorer:
    """
    يحسب نقاط الفرصة (0-100) لكل منتج
    كلما زادت النقاط، كلما كانت الفرصة أفضل
    يساعد الإدارة على تحديد الأولويات بسرعة
    """

    def calculate_score(self, product_data: dict, old_price: float,
                         new_price: float) -> float:
        """
        حساب نقاط الفرصة الإجمالية

        product_data: بيانات المنتج من السكرابينج
        old_price: السعر قبل التغير
        new_price: السعر الجديد
        """
        score = 0.0

        # 1. نقاط نسبة الخصم (الأهم - 40 نقطة)
        if old_price > 0:
            discount_pct = ((old_price - new_price) / old_price) * 100
            # معادلة: خصم 50% = 40 نقطة كاملة، خصم 25% = 20 نقطة
            discount_score = min(discount_pct * 0.8, 40)
            score += discount_score

        # 2. نقاط تقييم المنتج (20 نقطة)
        rating = product_data.get("rating")
        if rating:
            # تقييم 5 = 20 نقطة، تقييم 4 = 16 نقطة
            rating_score = (float(rating) / 5.0) * 20
            score += rating_score

        # 3. نقاط عدد المراجعات (15 نقطة)
        review_count = product_data.get("review_count", 0) or 0
        if review_count > 0:
            # 1000+ مراجعة = 15 نقطة كاملة
            review_score = min((review_count / 1000) * 15, 15)
            score += review_score

        # 4. نقاط توافر المخزون (10 نقاط)
        if product_data.get("in_stock"):
            score += 10

        # 5. نقاط تاريخ السعر - هل هو أقل سعر تاريخي؟ (15 نقطة)
        lowest_price = product_data.get("lowest_price")
        if lowest_price and new_price <= lowest_price:
            score += 15  # أقل سعر تاريخي = نقاط كاملة
        elif lowest_price and new_price <= lowest_price * 1.05:
            score += 7  # قريب جداً من الأقل التاريخي

        return round(min(score, 100), 1)

    def get_score_label(self, score: float) -> str:
        """
        تحويل النقاط إلى تصنيف نصي
        يُستخدم في رسائل الإدارة
        """
        if score >= SCORE_LEVELS["excellent"]:
            return "🔥 ممتاز"
        elif score >= SCORE_LEVELS["good"]:
            return "✅ جيد"
        else:
            return "ℹ️ عادي"


# ======================================================
# 🔍 محرك المراقبة الرئيسي
# ======================================================

class MonitoringEngine:
    """
    محرك المراقبة الرئيسي
    يدير دورة الفحص الكاملة لجميع المنتجات
    """

    def __init__(self, session_factory, bot, connector_manager):
        """
        session_factory: مصنع جلسات قاعدة البيانات
        bot: كائن بوت تيليغرام لإرسال الرسائل
        connector_manager: مدير الموصلات للسكرابينج
        """
        self.session_factory = session_factory
        self.bot = bot
        self.connector = connector_manager
        self.scorer = OpportunityScorer()

        # تتبع الروابط الفريدة لمنع فحص نفس الرابط مرتين
        # مثال: 100 مستخدم يراقبون نفس المنتج = فحص واحد فقط
        self._currently_scanning = set()

    async def start(self):
        """
        بدء حلقة المراقبة اللانهائية
        تعمل في الخلفية طوال وقت تشغيل البوت
        """
        global monitoring_engine_running, monitoring_engine_last_run
        monitoring_engine_running = True

        logger.info("🚀 بدء محرك المراقبة...")

        while True:
            monitoring_engine_last_run = datetime.utcnow()
            try:
                await self.run_scan_cycle()
            except Exception as e:
                logger.error(f"خطأ في دورة الفحص: {e}")

            # انتظار دقيقة بين كل دورة وأخرى
            await asyncio.sleep(60)

    async def run_scan_cycle(self):
        """
        دورة فحص كاملة:
        1. جلب المنتجات التي حان وقت فحصها
        2. تجميع الروابط الفريدة (لمنع التكرار)
        3. فحص كل رابط مرة واحدة
        4. معالجة التغيرات وإرسال التنبيهات
        """
        async with self.session_factory() as session:
            from db.crud import get_all_users
            from sqlalchemy import select
            from db.models import UserProduct, Product, User, MonitoringStatus

            # جلب المنتجات التي حان وقت فحصها
            products_to_scan = await self._get_products_due_for_scan(session)

            if not products_to_scan:
                return

            logger.info(f"📊 {len(products_to_scan)} منتج للفحص")

            # Concurrent scanning with semaphore to limit parallelism
            semaphore = asyncio.Semaphore(10)

            async def _scan_with_limit(product):
                if product.id in self._currently_scanning:
                    return
                self._currently_scanning.add(product.id)
                try:
                    async with semaphore:
                        await self._scan_product(session, product)
                        await asyncio.sleep(SCRAPING_DELAY_SECONDS)
                finally:
                    self._currently_scanning.discard(product.id)

            await asyncio.gather(
                *[_scan_with_limit(p) for p in products_to_scan],
                return_exceptions=True,
            )

    async def _get_products_due_for_scan(self, session) -> list:
        """
        جلب المنتجات التي حان وقت فحصها
        يراعي مستوى الاشتراك لكل مستخدم
        """
        from sqlalchemy import select, and_
        from db.models import Product, UserProduct, User, MonitoringStatus

        # المنتجات التي لم تُفحص منذ 30 دقيقة على الأقل
        # (الفترة الأقصر لتغطية جميع مستويات الاشتراكات)
        cutoff_time = datetime.utcnow() - timedelta(minutes=30)

        result = await session.execute(
            select(Product)
            .join(UserProduct, UserProduct.product_id == Product.id)
            .where(
                UserProduct.status == MonitoringStatus.ACTIVE,
                (Product.last_scraped == None) |
                (Product.last_scraped < cutoff_time)
            )
            .distinct()
            .limit(50)  # حد أقصى 50 منتج لكل دورة لمنع الضغط
        )
        return result.scalars().all()

    async def _scan_product(self, session, product) -> bool:
        """
        فحص منتج واحد وتحديث بياناته
        ترجع True إذا وُجد تغيير مهم
        """
        # Enqueue scraping job to worker queue (Celery).
        # Worker will perform the actual scraping and DB updates.
        try:
            # Import lazily to avoid circular imports at module load
            from worker.tasks import scrape_product

            # Pass current product values so worker can compute diffs
            current_price = float(product.current_price) if product.current_price is not None else None
            current_stock = bool(product.in_stock) if product.in_stock is not None else None

            # Enqueue the celery task (async-safe call; .delay is non-blocking)
            scrape_product.delay(product.id, product.url, current_price, current_stock)
            logger.info("Enqueued scrape job for product %s", product.id)
            return True
        except Exception as e:
            logger.error("Failed to enqueue scrape job for %s: %s", product.id, e)
            return False

    async def _create_and_notify_opportunity(self, session, product,
                                               old_price: float, new_price: float,
                                               score: float):
        """
        إنشاء فرصة وإرسال إشعار للإدارة عبر تيليغرام
        الإدارة تستلم الرسالة وتقرر الاعتماد أو الرفض
        """
        from db.crud import create_opportunity, create_admin_notification
        from config.settings import ADMIN_GROUP_ID

        opportunity = await create_opportunity(
            session, product.id, old_price, new_price, score,
            in_stock=product.in_stock
        )

        discount_pct = ((old_price - new_price) / old_price) * 100
        await create_admin_notification(
            session,
            type="new_opportunity",
            title="فرصة جديدة 💡",
            message=f"{product.name or 'منتج'} انخفض {discount_pct:.0f}%",
            icon="💡",
            color="blue",
            action_url="/opportunities",
        )

        score_label = self.scorer.get_score_label(score)

        # صياغة رسالة الإدارة
        message = (
            f"💡 *فرصة جديدة*\n\n"
            f"📦 *المنتج:* {product.name or 'غير معروف'}\n"
            f"🏪 *المتجر:* {product.url[:50]}...\n"
            f"💰 *السعر السابق:* {old_price:.2f}\n"
            f"🔥 *السعر الحالي:* {new_price:.2f}\n"
            f"📉 *الخصم:* {discount_pct:.1f}%\n"
            f"📦 *المخزون:* {'متوفر ✅' if product.in_stock else 'غير متوفر ❌'}\n"
            f"⭐ *التقييم:* {score_label} ({score}/100)\n"
            f"🔗 {product.url}"
        )

        from aiogram.utils.keyboard import InlineKeyboardBuilder
        builder = InlineKeyboardBuilder()
        builder.button(text="✅ اعتماد وإرسال", callback_data=f"opp_approve:{opportunity.id}")
        builder.button(text="✏️ تعديل الرسالة", callback_data=f"opp_edit:{opportunity.id}")
        builder.button(text="⏰ تأجيل", callback_data=f"opp_postpone:{opportunity.id}")
        builder.button(text="❌ تجاهل", callback_data=f"opp_reject:{opportunity.id}")
        builder.adjust(2)

        try:
            await self.bot.send_message(
                ADMIN_GROUP_ID,
                message,
                parse_mode="Markdown",
                reply_markup=builder.as_markup()
            )
        except Exception as e:
            logger.error(f"فشل إرسال إشعار الإدارة: {e}")

    async def _notify_users(self, session, product_id: int,
                             old_price: float, new_price: float,
                             old_stock: bool, new_stock: bool):
        """
        إرسال تنبيهات للمستخدمين الذين يراقبون هذا المنتج
        بناءً على إعدادات التنبيه الخاصة بكل مستخدم
        """
        from sqlalchemy import select
        from db.models import UserProduct, User, MonitoringStatus

        # جلب جميع المستخدمين الذين يراقبون هذا المنتج
        result = await session.execute(
            select(UserProduct)
            .join(User, User.id == UserProduct.user_id)
            .where(
                UserProduct.product_id == product_id,
                UserProduct.status == MonitoringStatus.ACTIVE,
                User.muted == False,
                User.is_banned == False
            )
        )
        user_products = result.scalars().all()

        for user_product in user_products:
            should_notify = False
            message_text = None

            alert_types = user_product.alert_types or []

            # فحص انخفاض السعر
            if (old_price and new_price and new_price < old_price and
                    ("price_drop" in alert_types or "any_price_change" in alert_types)):
                discount = ((old_price - new_price) / old_price) * 100

                # تحقق من خصم كبير فقط
                if "big_discount" in alert_types and discount < 20:
                    pass  # لا ترسل إذا الخصم أقل من 20%
                else:
                    should_notify = True
                    message_text = (
                        f"📉 *انخفاض في السعر!*\n\n"
                        f"السعر السابق: {old_price:.2f}\n"
                        f"السعر الجديد: *{new_price:.2f}*\n"
                        f"الخصم: *{discount:.1f}%*"
                    )

            # فحص الوصول للسعر المستهدف
            elif (new_price and user_product.target_price and
                  new_price <= user_product.target_price and
                  "target_price" in alert_types):
                should_notify = True
                message_text = (
                    f"🎯 *وصل المنتج للسعر المستهدف!*\n\n"
                    f"السعر الحالي: *{new_price:.2f}*\n"
                    f"السعر المستهدف: {user_product.target_price:.2f}"
                )

            # فحص عودة المخزون
            elif (old_stock == False and new_stock == True and
                  "back_in_stock" in alert_types):
                should_notify = True
                message_text = "🟢 *المنتج عاد للمخزون!*"

            # فحص نفاد المخزون
            elif (old_stock == True and new_stock == False and
                  "out_of_stock" in alert_types):
                should_notify = True
                message_text = "🔴 *نفد المخزون!*"

            if should_notify and message_text:
                await self._send_user_alert(session, user_product, message_text)

    async def _send_user_alert(self, session, user_product, message_text: str):
        """
        إرسال تنبيه لمستخدم محدد
        """
        from sqlalchemy import select
        from db.models import User, Product

        # جلب بيانات المستخدم والمنتج
        user_result = await session.execute(
            select(User).where(User.id == user_product.user_id)
        )
        user = user_result.scalar_one_or_none()

        product_result = await session.execute(
            select(Product).where(Product.id == user_product.product_id)
        )
        product = product_result.scalar_one_or_none()

        if not user or not product:
            return

        full_message = (
            f"{message_text}\n\n"
            f"📦 *{product.name or 'المنتج'}*\n"
            f"🔗 {product.url}"
        )

        try:
            await self.bot.send_message(
                user.telegram_id,
                full_message,
                parse_mode="Markdown"
            )
            # تحديث وقت آخر إشعار
            from sqlalchemy import update
            await session.execute(
                update(type(user_product))
                .where(type(user_product).id == user_product.id)
                .values(last_notified_at=datetime.utcnow())
            )
            await session.commit()

        except Exception as e:
            logger.error(f"فشل إرسال تنبيه للمستخدم {user.telegram_id}: {e}")
