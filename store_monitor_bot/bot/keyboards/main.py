"""
لوحات المفاتيح (Keyboards)
============================
جميع أزرار البوت منظمة هنا
Inline keyboards = أزرار تحت الرسالة
Reply keyboards = أزرار في لوحة الكيبورد
"""

from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup, ReplyKeyboardMarkup


# ======================================================
# 🏠 القائمة الرئيسية
# ======================================================

def _default_main_menu() -> ReplyKeyboardMarkup:
    """Default hardcoded main menu (fallback if DB is empty)."""
    builder = ReplyKeyboardBuilder()
    builder.button(text="➕ إضافة منتج")
    builder.button(text="📦 منتجاتي")
    builder.button(text="📂 مراقبة فئة")
    builder.button(text="🏪 مراقبة متجر")
    builder.button(text="🔥 أفضل العروض")
    builder.button(text="📊 التقارير")
    builder.button(text="💳 الاشتراك")
    builder.button(text="⚙️ الإعدادات")
    builder.button(text="❓ المساعدة")
    builder.button(text="🏬 طلب إضافة متجر")
    builder.button(text="🎧 الدعم الفني")
    builder.adjust(2, 2, 2, 2, 2, 1)
    return builder.as_markup(
        resize_keyboard=True,
        one_time_keyboard=False
    )


def main_menu_keyboard() -> ReplyKeyboardMarkup:
    from aiogram.utils.keyboard import ReplyKeyboardBuilder

    builder = ReplyKeyboardBuilder()
    
    builder.button(text="➕ إضافة منتج")
    builder.button(text="📦 منتجاتي")
    builder.button(text="📂 مراقبة فئة")
    builder.button(text="🏪 مراقبة متجر")
    builder.button(text="🔥 أفضل العروض")
    builder.button(text="📊 التقارير")
    builder.button(text="💳 الاشتراك")
    builder.button(text="⚙️ الإعدادات")
    builder.button(text="❓ المساعدة")
    builder.button(text="🏬 طلب إضافة متجر")
    builder.button(text="🎧 الدعم الفني")
    
    builder.adjust(2, 2, 2, 2, 2, 1)
    
    return builder.as_markup(
        resize_keyboard=True,
        one_time_keyboard=False
    )





# ======================================================
# ➕ إضافة منتج
# ======================================================

def product_found_keyboard(user_product_id: int = None) -> InlineKeyboardMarkup:
    """
    الأزرار التي تظهر بعد العثور على المنتج ومعالجته
    """
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ بدء المراقبة", callback_data="product_start_monitoring")
    builder.button(text="🔔 إعداد التنبيهات", callback_data="product_setup_alerts")
    builder.button(text="❌ إلغاء", callback_data="product_cancel")
    builder.button(text="🏠 رجوع للرئيسية", callback_data="go_home")
    builder.adjust(1, 1, 2)
    return builder.as_markup()


def alerts_setup_keyboard(product_id: int, current_alerts: list = None) -> InlineKeyboardMarkup:
    """
    إعداد التنبيهات لمنتج محدد
    يعرض خيارات التنبيه مع علامة ✅ على المفعّل منها
    """
    if current_alerts is None:
        current_alerts = []

    builder = InlineKeyboardBuilder()

    alert_options = [
        ("price_drop", "📉 انخفاض السعر"),
        ("any_price_change", "🔄 أي تغير في السعر"),
        ("back_in_stock", "🟢 توفر المخزون"),
        ("out_of_stock", "🔴 نفاد المخزون"),
        ("big_discount", "💥 خصم كبير فقط"),
        ("target_price", "🎯 الوصول لسعر محدد"),
    ]

    for key, label in alert_options:
        # إضافة ✅ إذا كان التنبيه مفعّلاً
        prefix = "✅ " if key in current_alerts else ""
        builder.button(
            text=f"{prefix}{label}",
            callback_data=f"alert_toggle:{key}:{product_id}"
        )

    builder.button(text="💾 حفظ الإعدادات", callback_data=f"alert_save:{product_id}")
    builder.button(text="🔙 رجوع", callback_data=f"product_detail:{product_id}")
    builder.adjust(1)
    return builder.as_markup()


# ======================================================
# 📦 قائمة المنتجات
# ======================================================

def product_list_keyboard(products: list) -> InlineKeyboardMarkup:
    """
    قائمة المنتجات التي يراقبها المستخدم
    كل منتج زر مستقل
    """
    builder = InlineKeyboardBuilder()

    for user_product in products:
        product = user_product.product
        name = (product.name or "منتج")[:30]  # اقتصار الاسم لـ 30 حرف
        price = f" - {product.current_price:.0f}" if product.current_price else ""
        status_icon = "▶️" if user_product.status.value == "active" else "⏸"

        builder.button(
            text=f"{status_icon} {name}{price}",
            callback_data=f"product_detail:{user_product.id}"
        )

    builder.button(text="➕ إضافة منتج", callback_data="add_product")
    builder.button(text="🔄 تحديث الكل", callback_data="refresh_all_products")
    builder.button(text="🔀 فرز المنتجات", callback_data="sort_products")
    builder.button(text="🏠 رجوع للرئيسية", callback_data="go_home")
    builder.adjust(1)
    return builder.as_markup()


def product_detail_keyboard(user_product_id: int, is_paused: bool = False) -> InlineKeyboardMarkup:
    """
    أزرار صفحة تفاصيل المنتج
    """
    builder = InlineKeyboardBuilder()

    builder.button(text="🔄 تحديث الآن", callback_data=f"product_refresh:{user_product_id}")
    builder.button(text="🔔 إعداد التنبيهات", callback_data=f"product_alerts:{user_product_id}")
    builder.button(text="📈 سجل السعر", callback_data=f"price_history:{user_product_id}")
    builder.button(text="📦 سجل المخزون", callback_data=f"stock_history:{user_product_id}")

    # زر الإيقاف/الاستئناف حسب الحالة
    if is_paused:
        builder.button(text="▶️ استئناف المراقبة", callback_data=f"product_resume:{user_product_id}")
    else:
        builder.button(text="⏸ إيقاف المراقبة", callback_data=f"product_pause:{user_product_id}")

    builder.button(text="🗑 حذف المنتج", callback_data=f"product_delete:{user_product_id}")
    builder.button(text="🔙 رجوع", callback_data="my_products")
    builder.adjust(2, 2, 2, 1)
    return builder.as_markup()


def sort_products_keyboard() -> InlineKeyboardMarkup:
    """خيارات فرز المنتجات"""
    builder = InlineKeyboardBuilder()
    builder.button(text="💰 حسب السعر", callback_data="sort:price")
    builder.button(text="🕐 آخر تحديث", callback_data="sort:updated")
    builder.button(text="📦 حسب المخزون", callback_data="sort:stock")
    builder.button(text="🔤 حسب الاسم", callback_data="sort:name")
    builder.button(text="🔙 رجوع", callback_data="my_products")
    builder.adjust(2, 2, 1)
    return builder.as_markup()


# ======================================================
# 📂 الفئات والمتاجر
# ======================================================

def category_added_keyboard(category_id: int) -> InlineKeyboardMarkup:
    """أزرار بعد إضافة فئة"""
    builder = InlineKeyboardBuilder()
    builder.button(text="🔔 إعداد تنبيهات الفئة", callback_data=f"cat_alerts:{category_id}")
    builder.button(text="👁 عرض الفئة", callback_data=f"cat_view:{category_id}")
    builder.button(text="🗑 حذف الفئة", callback_data=f"cat_delete:{category_id}")
    builder.button(text="🏠 رجوع للرئيسية", callback_data="go_home")
    builder.adjust(1)
    return builder.as_markup()


def category_alerts_keyboard(category_id: int) -> InlineKeyboardMarkup:
    """إعداد تنبيهات الفئة"""
    builder = InlineKeyboardBuilder()
    builder.button(text="🆕 منتجات جديدة", callback_data=f"catal:new_products:{category_id}")
    builder.button(text="🏷 تخفيضات فقط", callback_data=f"catal:discounts:{category_id}")
    builder.button(text="💥 خصومات كبيرة فقط", callback_data=f"catal:big_discounts:{category_id}")
    builder.button(text="🟢 منتجات عادت للمخزون", callback_data=f"catal:back_stock:{category_id}")
    builder.button(text="💾 حفظ", callback_data=f"catal_save:{category_id}")
    builder.button(text="🔙 رجوع", callback_data=f"cat_view:{category_id}")
    builder.adjust(1)
    return builder.as_markup()


# ======================================================
# 🔥 أفضل العروض
# ======================================================

def deals_list_keyboard(opportunities: list) -> InlineKeyboardMarkup:
    """قائمة أفضل العروض"""
    builder = InlineKeyboardBuilder()

    for opp in opportunities[:10]:  # أقصى 10 عروض
        product_name = (opp.product.name or "عرض")[:25]
        discount = f"{opp.discount_percent:.0f}%"
        builder.button(
            text=f"🔥 {product_name} - خصم {discount}",
            callback_data=f"deal_detail:{opp.id}"
        )

    builder.button(text="🔄 تحديث", callback_data="refresh_deals")
    builder.button(text="🏠 رجوع للرئيسية", callback_data="go_home")
    builder.adjust(1)
    return builder.as_markup()


def deal_detail_keyboard(opportunity_id: int, product_id: int,
                          affiliate_url: str = None) -> InlineKeyboardMarkup:
    """تفاصيل عرض واحد"""
    builder = InlineKeyboardBuilder()

    buy_url = affiliate_url or "#"
    builder.button(text="🛒 شراء الآن", url=buy_url)
    builder.button(text="👁 راقب المنتج", callback_data=f"watch_from_deal:{product_id}")
    builder.button(text="🔙 رجوع", callback_data="best_deals")
    builder.adjust(2, 1)
    return builder.as_markup()


# ======================================================
# 💳 الاشتراكات
# ======================================================

def subscription_keyboard(current_plan: str) -> InlineKeyboardMarkup:
    """صفحة الاشتراكات"""
    builder = InlineKeyboardBuilder()

    plans = [
        ("free", "🆓 الخطة المجانية"),
        ("basic", "⭐ الاشتراك الأساسي - 10 ريال"),
        ("professional", "💎 الاشتراك الاحترافي - 49 ريال"),
    ]

    for plan_key, plan_name in plans:
        # إضافة ✅ للخطة الحالية
        prefix = "✅ " if plan_key == current_plan else ""
        builder.button(text=f"{prefix}{plan_name}", callback_data=f"plan_info:{plan_key}")

    if current_plan == "free":
        builder.button(text="⬆️ ترقية الآن", callback_data="upgrade_plan")

    builder.button(text="📊 مقارنة الخطط", callback_data="compare_plans")
    builder.button(text="🏠 رجوع للرئيسية", callback_data="go_home")
    builder.adjust(1)
    return builder.as_markup()


def compare_plans_keyboard() -> InlineKeyboardMarkup:
    """مقارنة الخطط"""
    builder = InlineKeyboardBuilder()
    builder.button(text="⬆️ ترقية الآن", callback_data="upgrade_plan")
    builder.button(text="🔙 رجوع", callback_data="subscription")
    builder.adjust(2)
    return builder.as_markup()


# ======================================================
# ⚙️ الإعدادات
# ======================================================

def settings_keyboard() -> InlineKeyboardMarkup:
    """صفحة الإعدادات"""
    builder = InlineKeyboardBuilder()
    builder.button(text="🌐 اللغة", callback_data="settings_language")
    builder.button(text="💱 العملة", callback_data="settings_currency")
    builder.button(text="⏱ تكرار الفحص", callback_data="settings_interval")
    builder.button(text="🔕 كتم التنبيهات", callback_data="settings_mute")
    builder.button(text="🔔 نوع التنبيهات الافتراضي", callback_data="settings_default_alerts")
    builder.button(text="👤 معلومات الحساب", callback_data="settings_account_info")
    builder.button(text="🏠 رجوع للرئيسية", callback_data="go_home")
    builder.adjust(2, 2, 1, 1, 1)
    return builder.as_markup()


# ======================================================
# 🏠 أزرار عامة
# ======================================================

def back_home_keyboard() -> InlineKeyboardMarkup:
    """زر رجوع للرئيسية فقط"""
    builder = InlineKeyboardBuilder()
    builder.button(text="🏠 رجوع للرئيسية", callback_data="go_home")
    return builder.as_markup()


def confirm_delete_keyboard(item_type: str, item_id: int) -> InlineKeyboardMarkup:
    """تأكيد الحذف"""
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ نعم، احذف", callback_data=f"confirm_delete:{item_type}:{item_id}")
    builder.button(text="❌ لا، إلغاء", callback_data=f"cancel_delete")
    builder.adjust(2)
    return builder.as_markup()
