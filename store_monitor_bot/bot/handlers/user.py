"""
معالجات البوت الرئيسية (Handlers)
=====================================
كل handler مسؤول عن معالجة رسالة أو زر محدد
منظم حسب الوظيفة

هذا الملف يحتوي على:
- شاشة البداية /start
- إضافة منتج
- قائمة المنتجات
- تفاصيل المنتج
- إعداد التنبيهات
"""

import logging
import json
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

# SQLAlchemy is an optional runtime dependency in some developer environments.
# Wrap top-level imports to avoid breaking module import if SQLAlchemy is
# not installed (tests or static inspections). Individual functions that
# need DB access will import SQLAlchemy locally.
try:
    from sqlalchemy import select, update
except Exception:
    select = None
    update = None

from bot.keyboards.main import (
    main_menu_keyboard, product_found_keyboard, alerts_setup_keyboard,
    product_list_keyboard, product_detail_keyboard, sort_products_keyboard,
    back_home_keyboard, confirm_delete_keyboard
)

logger = logging.getLogger(__name__)

CURRENCY_SYMBOLS: dict[str, str] = {
    'EGP': 'ج.م',
    'SAR': 'ر.س',
    'AED': 'د.إ',
    'USD': '$',
    'GBP': '£',
    'EUR': '€',
    'CAD': 'CA$',
    'AUD': 'A$',
    'JPY': '¥',
    'INR': '₹',
    'BRL': 'R$',
    'MXN': 'MX$',
    'TRY': '₺',
    'PLN': 'zł',
    'SEK': 'kr',
    'SGD': 'S$',
}


def format_price(price: float, currency: str) -> str:
    symbol = CURRENCY_SYMBOLS.get(currency, currency)
    return f'{price:,.2f} {symbol}'


# Router الخاص بهذا الملف
router = Router()


async def format_product_message(
    product_data: dict
) -> str:
    lines = ['✅ *تم التعرف على المنتج!*\n']

    name = product_data.get('name', '')
    if name:
        lines.append(f'📦 *{name[:120]}*\n')

    price = product_data.get('price')
    orig = product_data.get('original_price')
    discount = product_data.get('discount_percent')
    currency = product_data.get('currency', '')
    symbol = product_data.get('symbol', currency)

    if price:
        lines.append(f'💰 *السعر الحالي:* {price:,.2f} {symbol}')

    if orig and price and float(orig) > float(price):
        lines.append(f'🏷 *السعر قبل:* ~~{orig:,.2f} {symbol}~~')

    if discount:
        lines.append(f'💥 *الخصم:* {float(discount):.0f}%')

    coupon = product_data.get('coupon')
    if coupon:
        lines.append(f'🎟 *كوبون:* {coupon[:100]}')

    in_stock = product_data.get('in_stock')
    stock_text = product_data.get('stock_text', '')

    if in_stock is False:
        lines.append('❌ *المخزون:* غير متوفر')
    elif stock_text and any(
        w in stock_text.lower()
        for w in ['only', 'left', 'متبقي', 'أخير']
    ):
        lines.append(f'⚠️ *المخزون:* {stock_text}')
    else:
        lines.append('✅ *المخزون:* متوفر')

    rating = product_data.get('rating')
    reviews = product_data.get('review_count')

    if rating:
        stars = '⭐' * min(5, round(float(rating)))
        lines.append(f'{stars} *التقييم:* {rating}/5')

    if reviews:
        lines.append(f'💬 *التقييمات:* {int(reviews):,}')

    brand = product_data.get('brand')
    if brand:
        lines.append(f'🏷 *البراند:* {brand}')

    delivery = product_data.get('delivery_info')
    if delivery:
        lines.append(f'🚚 *التوصيل:* {delivery}')

    store = product_data.get('store', '')
    if store:
        lines.append(f'\n🏪 *المتجر:* {store}')

    lines.append('\n*هل تريد بدء مراقبة هذا المنتج؟*')
    return '\n'.join(lines)


async def _read_bot_setting(session, key: str, default_value):
    from db.models import BotSetting

    try:
        row = (await session.execute(select(BotSetting).where(BotSetting.key == key))).scalar_one_or_none()
    except Exception:
        return default_value

    if not row or not hasattr(row, "value"):
        return default_value

    value_type = row.value_type.value if hasattr(row.value_type, "value") else str(row.value_type)
    if value_type == "boolean":
        return str(row.value).strip().lower() in {"1", "true", "yes", "on"}
    if value_type == "integer":
        try:
            return int(row.value)
        except Exception:
            return default_value
    if value_type == "float":
        try:
            return float(row.value)
        except Exception:
            return default_value
    if value_type == "json":
        try:
            return json.loads(row.value)
        except Exception:
            return default_value
    return row.value


async def show_onboarding_step_1(message: Message):  # pragma: no cover
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    builder = InlineKeyboardBuilder()
    builder.button(text="التالي: كيف أبدأ؟ ←", callback_data="onboarding:step2")
    builder.adjust(1)

    first_name = message.from_user.first_name or "صديقنا"
    await message.answer(
        f"👋 أهلاً بك {first_name}!\n\n"
        "أنا بوت مراقبة الأسعار والعروض 🛍\n\n"
        "يمكنني مساعدتك في:\n"
        "📉 تتبع انخفاض الأسعار\n"
        "📦 مراقبة توفر المنتجات\n"
        "🔥 اكتشاف أفضل العروض\n"
        "🏪 مراقبة متاجر كاملة",
        reply_markup=builder.as_markup(),
    )


async def _set_user_onboarded(session, telegram_id: int):  # pragma: no cover
    from db.models import User

    await session.execute(
        update(User)
        .where(User.telegram_id == telegram_id)
        .values(is_onboarded=True)
    )
    await session.commit()


def _onboarding_step_2_text() -> str:  # pragma: no cover
    return (
        "🛒 كيف تراقب منتجاً؟\n\n"
        "1️⃣ اضغط \"➕ إضافة منتج\"\n"
        "2️⃣ انسخ رابط المنتج من المتجر\n"
        "3️⃣ أرسل الرابط للبوت\n"
        "4️⃣ اختر نوع التنبيه المناسب\n\n"
        "✅ روابط مدعومة:\n"
        "• Amazon (amazon.sa / .com / .ae)\n"
        "• متاجر Shopify\n"
        "• متاجر WooCommerce\n"
        "• معظم المتاجر الإلكترونية\n\n"
        "💡 مثال:\n"
        "https://amazon.sa/dp/B08L5TNJHG"
    )


def _onboarding_step_3_text() -> str:  # pragma: no cover
    return (
        "🔔 أنواع التنبيهات\n\n"
        "📉 انخفاض السعر\n"
        "عندما ينخفض سعر المنتج\n\n"
        "💥 خصم كبير فقط (10%+)\n"
        "عندما يصل الخصم لـ 10% أو أكثر\n\n"
        "🟢 عودة للمخزون\n"
        "عندما يعود المنتج بعد نفاده\n\n"
        "🎯 سعر مستهدف\n"
        "عندما يصل لسعر تحدده أنت\n\n"
        "⚙️ يمكن تغيير التنبيهات في أي وقت\n"
        "من قائمة \"منتجاتي\""
    )


def _onboarding_step_4_text() -> str:  # pragma: no cover
    return (
        "💳 خطط الاشتراك\n\n"
        "🆓 مجاني — ابدأ مجاناً!\n"
        "• 3 منتجات\n"
        "• تحديث كل 60 دقيقة\n\n"
        "⭐ أساسي — 10 ريال/شهر\n"
        "• 50 منتج + مراقبة الفئات\n"
        "• تحديث كل 30 دقيقة\n\n"
        "💎 احترافي — 49 ريال/شهر\n"
        "• 300 منتج + مراقبة المتاجر\n"
        "• تحديث كل 15 دقيقة\n\n"
        "ابدأ مجاناً الآن! يمكنك الترقية\n"
        "في أي وقت من قائمة \"الاشتراك\""
    )


# ======================================================
# 📋 حالات FSM (Finite State Machine)
# للتعامل مع المحادثات متعددة الخطوات
# ======================================================

class AddProductStates(StatesGroup):
    """حالات إضافة منتج جديد"""
    waiting_for_url = State()        # انتظار رابط المنتج
    waiting_for_target_price = State()  # انتظار السعر المستهدف


class AddCategoryStates(StatesGroup):
    """حالات إضافة فئة"""
    waiting_for_url = State()


class AddStoreStates(StatesGroup):
    """حالات إضافة طلب متجر"""
    waiting_for_url = State()


class SetTargetPriceStates(StatesGroup):
    """حالات تحديد سعر مستهدف"""
    waiting_for_price = State()


# ======================================================
# 🏠 شاشة البداية
# ======================================================

@router.message(CommandStart())
async def cmd_start(message: Message, session, state: FSMContext):
    """
    معالج أمر /start
    ينشئ المستخدم في قاعدة البيانات ويعرض القائمة الرئيسية
    """
    # مسح أي حالة FSM سابقة
    await state.clear()

    # إنشاء أو تحديث بيانات المستخدم
    from db.crud import get_or_create_user
    user = await get_or_create_user(
        session,
        telegram_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
        last_name=message.from_user.last_name
    )

    maintenance_mode = await _read_bot_setting(session, "bot.maintenance_mode", False)
    maintenance_message = await _read_bot_setting(
        session,
        "bot.maintenance_message",
        "🔧 البوت قيد الصيانة حالياً، نعود قريباً.",
    )

    if maintenance_mode:
        await message.answer(str(maintenance_message))
        return

    is_new_user = bool(getattr(user, "_is_new_user", False))
    if not is_new_user and not bool(getattr(user, "is_onboarded", False)):
        await _set_user_onboarded(session, message.from_user.id)

    if is_new_user:
        await show_onboarding_step_1(message)
        return

    welcome_template = await _read_bot_setting(
        session,
        "bot.welcome_message",
        "👋 أهلاً بك في بوت مراقبة الأسعار والعروض!",
    )
    plan_attr = getattr(user, "plan", "free")
    plan_value = plan_attr.value if hasattr(plan_attr, "value") else str(plan_attr)
    welcome_message = (
        str(welcome_template)
        .replace("{first_name}", message.from_user.first_name or "صديقنا")
        .replace("{plan}", plan_value)
        + "\n\n"
        f"يمكنك عبر هذا البوت:\n"
        f"📉 متابعة انخفاض الأسعار\n"
        f"📦 متابعة المخزون\n"
        f"📂 مراقبة الفئات\n"
        f"🏪 مراقبة المتاجر\n"
        f"🔥 اكتشاف أفضل العروض\n\n"
        f"🎧 تواصل مع فريق الدعم مباشرة\n\n"
        f"اختر من الأزرار التالية للبدء:"
    )

    await message.answer(welcome_message, reply_markup=main_menu_keyboard())


@router.callback_query(F.data == "onboarding:step1")
async def onboarding_step_1_callback(callback: CallbackQuery):  # pragma: no cover
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    builder = InlineKeyboardBuilder()
    builder.button(text="التالي: كيف أبدأ؟ ←", callback_data="onboarding:step2")
    builder.adjust(1)

    first_name = callback.from_user.first_name or "صديقنا"
    await callback.message.edit_text(
        f"👋 أهلاً بك {first_name}!\n\n"
        "أنا بوت مراقبة الأسعار والعروض 🛍\n\n"
        "يمكنني مساعدتك في:\n"
        "📉 تتبع انخفاض الأسعار\n"
        "📦 مراقبة توفر المنتجات\n"
        "🔥 اكتشاف أفضل العروض\n"
        "🏪 مراقبة متاجر كاملة",
        reply_markup=builder.as_markup(),
    )
    await callback.answer()


@router.callback_query(F.data == "onboarding:step2")
async def onboarding_step_2_callback(callback: CallbackQuery):  # pragma: no cover
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    builder = InlineKeyboardBuilder()
    builder.button(text="← السابق", callback_data="onboarding:step1")
    builder.button(text="التالي: التنبيهات →", callback_data="onboarding:step3")
    builder.adjust(2)

    await callback.message.edit_text(_onboarding_step_2_text(), reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(F.data == "onboarding:step3")
async def onboarding_step_3_callback(callback: CallbackQuery):  # pragma: no cover
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    builder = InlineKeyboardBuilder()
    builder.button(text="← السابق", callback_data="onboarding:step2")
    builder.button(text="التالي: الخطط →", callback_data="onboarding:step4")
    builder.adjust(2)

    await callback.message.edit_text(_onboarding_step_3_text(), reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(F.data == "onboarding:step4")
async def onboarding_step_4_callback(callback: CallbackQuery):  # pragma: no cover
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    builder = InlineKeyboardBuilder()
    builder.button(text="← السابق", callback_data="onboarding:step3")
    builder.button(text="🚀 ابدأ الاستخدام الآن!", callback_data="onboarding:start")
    builder.adjust(1)

    await callback.message.edit_text(_onboarding_step_4_text(), reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(F.data == "onboarding:start")
async def onboarding_start_callback(callback: CallbackQuery, session):  # pragma: no cover
    await _set_user_onboarded(session, callback.from_user.id)
    await callback.message.answer("🏠 القائمة الرئيسية:", reply_markup=main_menu_keyboard())
    await callback.message.answer("💡 ابدأ بضغط ➕ إضافة منتج")
    await callback.answer("تم تفعيل حسابك بنجاح ✅", show_alert=False)


@router.callback_query(F.data == "go_home")
async def go_home(callback: CallbackQuery, state: FSMContext):
    """العودة للقائمة الرئيسية من أي مكان"""
    await state.clear()
    await callback.message.answer(
        "🏠 القائمة الرئيسية:",
        reply_markup=main_menu_keyboard()
    )
    await callback.answer()


# ======================================================
# ➕ إضافة منتج
# ======================================================

@router.message(F.text == "➕ إضافة منتج")
async def add_product_start(message: Message, state: FSMContext):
    """
    بدء عملية إضافة منتج
    يطلب من المستخدم إرسال الرابط
    """
    await state.set_state(AddProductStates.waiting_for_url)
    await message.answer(
        "🔗 أرسل رابط المنتج الذي تريد مراقبته:\n\n"
        "مثال: https://www.amazon.sa/dp/B08L5TNJHG\n\n"
        "💡 يمكنك إرسال روابط من أمازون، شوبيفاي، ووكومرس، وغيرها."
    )


@router.callback_query(F.data == "add_product")
async def add_product_start_callback(callback: CallbackQuery, state: FSMContext):
    """بدء إضافة منتج من أزرار inline/menu builder."""
    await state.set_state(AddProductStates.waiting_for_url)
    await callback.message.answer(
        "🔗 أرسل رابط المنتج الذي تريد مراقبته:\n\n"
        "مثال: https://www.amazon.sa/dp/B08L5TNJHG\n\n"
        "💡 يمكنك إرسال روابط من أمازون، شوبيفاي، ووكومرس، وغيرها."
    )
    await callback.answer()


@router.message(AddProductStates.waiting_for_url)
async def process_product_url(message: Message, state: FSMContext,
                               session, connector_manager):
    """
    معالجة الرابط المُرسل من المستخدم
    1. التحقق من صحة الرابط
    2. السكرابينج لجلب بيانات المنتج
    3. عرض بيانات المنتج وأزرار التأكيد
    """
    url = message.text.strip()

    # التحقق من أن الرسالة تبدأ بـ http
    if not url.startswith(("http://", "https://")):
        await message.answer(
            "❌ الرابط غير صالح. تأكد أن الرابط يبدأ بـ https://\n\n"
            "أرسل الرابط مرة أخرى:"
        )
        return

    # إخبار المستخدم أننا نجلب البيانات
    loading_msg = await message.answer("⏳ جاري فحص المنتج...")

    # جلب بيانات المستخدم
    from db.crud import get_user_by_telegram_id, can_user_add_product
    user = await get_user_by_telegram_id(session, message.from_user.id)

    # التحقق من حد الخطة
    if not await can_user_add_product(session, user):
        from config.settings import PLAN_LIMITS
        limit = PLAN_LIMITS[user.plan]["max_products"]
        await loading_msg.edit_text(
            f"❌ وصلت للحد الأقصى!\n\n"
            f"خطتك الحالية ({user.plan}) تسمح بـ {limit} منتج فقط.\n"
            f"قم بترقية اشتراكك للإضافة أكثر.",
            reply_markup=back_home_keyboard()
        )
        await state.clear()
        return

    try:
        # السكرابينج
        product_data = await connector_manager.scrape(url)

        if not product_data:
            await loading_msg.edit_text(
                "❌ لم نتمكن من جلب بيانات المنتج.\n\n"
                "تأكد من:\n"
                "• صحة الرابط\n"
                "• أن الموقع مدعوم\n"
                "• أن الرابط يؤدي لصفحة منتج\n\n"
                "أرسل الرابط مرة أخرى أو اضغط /start للبدء من جديد:"
            )
            return

        # حفظ الرابط وبيانات المنتج في الـ state لاستخدامها لاحقاً
        await state.update_data(
            product_url=url,
            product_data=product_data
        )

        product_info = await format_product_message(product_data)

        await loading_msg.edit_text(
            product_info,
            parse_mode="Markdown",
            reply_markup=product_found_keyboard()
        )

    except Exception as e:
        logger.error(f"Error scraping product: {e}")
        await loading_msg.edit_text(
            "❌ حدث خطأ أثناء جلب البيانات. حاول مرة أخرى لاحقاً.",
            reply_markup=back_home_keyboard()
        )
        await state.clear()


@router.callback_query(F.data == "product_start_monitoring")
async def start_product_monitoring(callback: CallbackQuery, state: FSMContext, session):
    """
    بدء مراقبة المنتج بعد تأكيد المستخدم
    1. حفظ المنتج في قاعدة البيانات
    2. ربطه بالمستخدم
    3. إظهار رسالة نجاح
    """
    data = await state.get_data()
    url = data.get("product_url")
    product_data = data.get("product_data")

    if not url or not product_data:
        await callback.answer("❌ حدث خطأ. ابدأ من جديد.", show_alert=True)
        await state.clear()
        return

    from db.crud import (
        get_user_by_telegram_id, get_product_by_url,
        create_product, add_product_to_user
    )

    user = await get_user_by_telegram_id(session, callback.from_user.id)

    # التحقق هل المنتج موجود أصلاً في قاعدة البيانات
    product = await get_product_by_url(session, url)

    if not product:
        # إنشاء المنتج لأول مرة
        product = await create_product(
            session,
            url=url,
            name=product_data.get("name"),
            price=product_data.get("price"),
            currency=product_data.get("currency", "USD"),
            in_stock=product_data.get("in_stock"),
            image_url=product_data.get("image_url"),
            rating=product_data.get("rating"),
            review_count=product_data.get("review_count")
        )

    # ربط المنتج بالمستخدم
    user_product = await add_product_to_user(
        session, user.id, product.id,
        alert_types=["price_drop"]  # تنبيه افتراضي
    )

    await state.clear()

    await callback.message.edit_text(
        f"✅ *تمت الإضافة بنجاح!*\n\n"
        f"📦 *{product.name or 'المنتج'}*\n"
        f"سيتم إشعارك عند تغير السعر أو المخزون.\n\n"
        f"💡 يمكنك تخصيص التنبيهات من 'منتجاتي'",
        parse_mode="Markdown",
        reply_markup=product_found_keyboard(user_product.id)
    )
    await callback.answer()


@router.callback_query(F.data == "product_cancel")
async def cancel_product_add(callback: CallbackQuery, state: FSMContext):
    """إلغاء عملية إضافة منتج"""
    await state.clear()
    await callback.message.edit_text(
        "تم الإلغاء.",
        reply_markup=back_home_keyboard()
    )
    await callback.answer()


# ======================================================
# 📦 قائمة المنتجات
# ======================================================

@router.message(F.text == "📦 منتجاتي")
async def my_products(message: Message, session):
    """عرض قائمة المنتجات التي يراقبها المستخدم"""
    from db.crud import get_user_by_telegram_id, get_user_products
    user = await get_user_by_telegram_id(session, message.from_user.id)
    user_products = await get_user_products(session, user.id)

    if not user_products:
        await message.answer(
            "📦 *منتجاتك المراقبة*\n\n"
            "لا توجد منتجات بعد!\n"
            "اضغط 'إضافة منتج' لبدء المراقبة.",
            parse_mode="Markdown",
            reply_markup=back_home_keyboard()
        )
        return

    text = f"📦 *منتجاتك المراقبة* ({len(user_products)} منتج)\n\n"

    for i, up in enumerate(user_products, 1):
        p = up.product
        price_text = f"{p.current_price:.0f}" if p.current_price else "—"
        stock_icon = "✅" if p.in_stock else "❌"
        status_icon = "▶️" if up.status.value == "active" else "⏸"

        text += f"{i}. {status_icon} {(p.name or 'منتج')[:40]}\n"
        text += f"    💰 {price_text} | {stock_icon}\n\n"

    await message.answer(
        text,
        parse_mode="Markdown",
        reply_markup=product_list_keyboard(user_products)
    )


@router.callback_query(F.data == "my_products")
async def my_products_callback(callback: CallbackQuery, session):
    """نفس العرض لكن من callback (للعودة من الصفحات الفرعية)"""
    from db.crud import get_user_by_telegram_id, get_user_products
    user = await get_user_by_telegram_id(session, callback.from_user.id)
    user_products = await get_user_products(session, user.id)

    if not user_products:
        await callback.message.edit_text(
            "لا توجد منتجات بعد!",
            reply_markup=back_home_keyboard()
        )
        await callback.answer()
        return

    text = f"📦 *منتجاتك المراقبة* ({len(user_products)} منتج)"

    await callback.message.edit_text(
        text,
        parse_mode="Markdown",
        reply_markup=product_list_keyboard(user_products)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("product_detail:"))
async def product_detail(callback: CallbackQuery, session):
    """عرض تفاصيل منتج محدد"""
    user_product_id = int(callback.data.split(":")[1])

    from sqlalchemy import select
    from db.models import UserProduct, Product
    from sqlalchemy.orm import selectinload

    result = await session.execute(
        select(UserProduct)
        .options(selectinload(UserProduct.product))
        .where(UserProduct.id == user_product_id)
    )
    user_product = result.scalar_one_or_none()

    if not user_product:
        await callback.answer("❌ المنتج غير موجود", show_alert=True)
        return

    p = user_product.product

    currency = p.currency or ""
    price_text = format_price(p.current_price, currency) if p.current_price else "غير متوفر"
    lowest_text = format_price(p.lowest_price, currency) if p.lowest_price else "—"
    highest_text = format_price(p.highest_price, currency) if p.highest_price else "—"
    stock_text = "متوفر ✅" if p.in_stock else "غير متوفر ❌"

    from datetime import datetime

    last_updated = "لم يُفحص بعد"
    if p.last_scraped:
        diff = (datetime.utcnow() - p.last_scraped).seconds // 60
        if diff < 60:
            last_updated = f"قبل {diff} دقيقة"
        else:
            last_updated = f"قبل {diff // 60} ساعة"

    text = (
        f"📦 *{p.name or 'المنتج'}*\n\n"
        f"💰 *السعر الحالي:* {price_text}\n"
        f"📉 *أقل سعر:* {lowest_text}\n"
        f"📈 *أعلى سعر:* {highest_text}\n"
        f"🏪 *المخزون:* {stock_text}\n"
        f"⏰ *آخر تحديث:* {last_updated}\n\n"
        f"🔗 {p.url[:50]}..."
    )

    is_paused = user_product.status.value == "paused"

    await callback.message.edit_text(
        text,
        parse_mode="Markdown",
        reply_markup=product_detail_keyboard(user_product_id, is_paused)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("product_pause:"))
async def pause_product(callback: CallbackQuery, session):
    """إيقاف مراقبة منتج مؤقتاً"""
    user_product_id = int(callback.data.split(":")[1])

    from db.crud import toggle_monitoring
    await toggle_monitoring(session, user_product_id, pause=True)

    await callback.answer("⏸ تم إيقاف المراقبة", show_alert=False)
    # إعادة تحميل الصفحة
    await product_detail(callback, session)


@router.callback_query(F.data.startswith("product_resume:"))
async def resume_product(callback: CallbackQuery, session):
    """استئناف مراقبة منتج"""
    user_product_id = int(callback.data.split(":")[1])

    from db.crud import toggle_monitoring
    await toggle_monitoring(session, user_product_id, pause=False)

    await callback.answer("▶️ تم استئناف المراقبة", show_alert=False)
    await product_detail(callback, session)


@router.callback_query(F.data.startswith("product_delete:"))
async def delete_product_confirm(callback: CallbackQuery):
    """طلب تأكيد حذف المنتج"""
    user_product_id = int(callback.data.split(":")[1])

    await callback.message.edit_text(
        "⚠️ هل أنت متأكد من حذف هذا المنتج من قائمة المراقبة؟\n\n"
        "لن تستقبل تنبيهات عنه بعد الحذف.",
        reply_markup=confirm_delete_keyboard("product", user_product_id)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("confirm_delete:product:"))
async def delete_product_execute(callback: CallbackQuery, session):
    """تنفيذ حذف المنتج"""
    user_product_id = int(callback.data.split(":")[2])

    from db.crud import delete_user_product
    await delete_user_product(session, user_product_id)

    await callback.message.edit_text(
        "✅ تم حذف المنتج من قائمة المراقبة.",
        reply_markup=back_home_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "cancel_delete")
async def cancel_delete(callback: CallbackQuery):
    """إلغاء الحذف"""
    await callback.message.edit_text(
        "تم الإلغاء.",
        reply_markup=back_home_keyboard()
    )
    await callback.answer()


# ======================================================
# 📈 سجل السعر والمخزون
# ======================================================

@router.callback_query(F.data.startswith("price_history:"))
async def show_price_history(callback: CallbackQuery, session):
    """عرض تاريخ تغيرات السعر"""
    user_product_id = int(callback.data.split(":")[1])

    from sqlalchemy import select
    from db.models import UserProduct, Product, PriceHistory
    from sqlalchemy.orm import selectinload

    # جلب المنتج
    result = await session.execute(
        select(UserProduct)
        .options(selectinload(UserProduct.product))
        .where(UserProduct.id == user_product_id)
    )
    user_product = result.scalar_one_or_none()

    if not user_product:
        await callback.answer("❌ المنتج غير موجود", show_alert=True)
        return

    # جلب آخر 10 سجلات للسعر
    history_result = await session.execute(
        select(PriceHistory)
        .where(PriceHistory.product_id == user_product.product_id)
        .order_by(PriceHistory.recorded_at.desc())
        .limit(10)
    )
    history = history_result.scalars().all()

    text = f"📈 *سجل السعر*\n📦 {user_product.product.name or 'المنتج'}\n\n"

    if not history:
        text += "لا توجد بيانات تاريخية بعد."
    else:
        from datetime import datetime
        for record in history:
            date_str = record.recorded_at.strftime("%d/%m %H:%M")
            text += f"• {date_str}: *{format_price(record.price, record.currency)}*\n"

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    builder.button(text="🔄 تحديث", callback_data=f"price_history:{user_product_id}")
    builder.button(text="🔙 رجوع", callback_data=f"product_detail:{user_product_id}")
    builder.adjust(2)

    await callback.message.edit_text(
        text,
        parse_mode="Markdown",
        reply_markup=builder.as_markup()
    )
    await callback.answer()


# ======================================================
# 🔔 إعداد التنبيهات
# ======================================================

@router.callback_query(F.data == "product_setup_alerts")
async def product_setup_alerts(callback: CallbackQuery, state: FSMContext):
    """فتح شاشة إعداد التنبيهات بعد إضافة المنتج مباشرةً (بدون product_id بعد)"""
    data = await state.get_data()
    # نحاول الحصول على user_product_id من state إن وجد
    user_product_id = data.get("user_product_id")
    if user_product_id:
        await callback.message.edit_text(
            "🔔 *إعداد التنبيهات*\n\nاختر نوع التنبيهات التي تريدها:",
            parse_mode="Markdown",
            reply_markup=alerts_setup_keyboard(user_product_id, [])
        )
    else:
        await callback.answer("✅ تم الحفظ. يمكنك تعديل التنبيهات من 'منتجاتي'", show_alert=True)
    await callback.answer()


@router.callback_query(F.data.startswith("product_alerts:"))
async def product_alerts_setup(callback: CallbackQuery, session):
    """فتح شاشة إعداد التنبيهات من صفحة تفاصيل المنتج"""
    user_product_id = int(callback.data.split(":")[1])

    from sqlalchemy import select
    from db.models import UserProduct

    result = await session.execute(
        select(UserProduct).where(UserProduct.id == user_product_id)
    )
    user_product = result.scalar_one_or_none()

    if not user_product:
        await callback.answer("❌ المنتج غير موجود", show_alert=True)
        return

    current_alerts = user_product.alert_types or []
    await callback.message.edit_text(
        "🔔 *إعداد التنبيهات*\n\nاختر نوع التنبيهات التي تريدها:",
        parse_mode="Markdown",
        reply_markup=alerts_setup_keyboard(user_product_id, current_alerts)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("alert_toggle:"))
async def alert_toggle(callback: CallbackQuery, session):
    """تفعيل/تعطيل نوع تنبيه معين"""
    parts = callback.data.split(":")
    # format: alert_toggle:{key}:{product_id}
    if len(parts) < 3:
        await callback.answer("❌ بيانات غير صحيحة", show_alert=True)
        return

    key = parts[1]
    user_product_id = int(parts[2])

    from sqlalchemy import select
    from db.models import UserProduct

    result = await session.execute(
        select(UserProduct).where(UserProduct.id == user_product_id)
    )
    user_product = result.scalar_one_or_none()

    if not user_product:
        await callback.answer("❌ المنتج غير موجود", show_alert=True)
        return

    current_alerts = list(user_product.alert_types or [])
    if key in current_alerts:
        current_alerts.remove(key)
        await callback.answer(f"🔕 تم إلغاء: {key}")
    else:
        current_alerts.append(key)
        await callback.answer(f"🔔 تم تفعيل: {key}")

    # حفظ مؤقت في قاعدة البيانات مباشرة
    user_product.alert_types = current_alerts
    await session.commit()

    await callback.message.edit_reply_markup(
        reply_markup=alerts_setup_keyboard(user_product_id, current_alerts)
    )


@router.callback_query(F.data.startswith("alert_save:"))
async def alert_save(callback: CallbackQuery, session):
    """حفظ إعدادات التنبيهات"""
    user_product_id = int(callback.data.split(":")[1])

    from sqlalchemy import select
    from db.models import UserProduct

    result = await session.execute(
        select(UserProduct).where(UserProduct.id == user_product_id)
    )
    user_product = result.scalar_one_or_none()

    if not user_product:
        await callback.answer("❌ المنتج غير موجود", show_alert=True)
        return

    alerts = user_product.alert_types or []
    await callback.message.edit_text(
        f"✅ *تم حفظ إعدادات التنبيهات!*\n\n"
        f"التنبيهات المفعّلة: {len(alerts)}\n"
        + ("\n".join(f"• {a}" for a in alerts) if alerts else "• لا توجد تنبيهات مفعّلة"),
        parse_mode="Markdown",
        reply_markup=product_detail_keyboard(user_product_id)
    )
    await callback.answer("✅ تم الحفظ")


# ======================================================
# 🔄 تحديث المنتجات
# ======================================================

@router.callback_query(F.data.startswith("product_refresh:"))
async def product_refresh(callback: CallbackQuery, session):
    """تحديث بيانات منتج معين الآن"""
    user_product_id = int(callback.data.split(":")[1])

    await callback.answer("⏳ جاري التحديث...", show_alert=False)
    # إعادة عرض التفاصيل (الفحص الفعلي يتم في الخلفية)
    await product_detail(callback, session)


@router.callback_query(F.data == "refresh_all_products")
async def refresh_all_products(callback: CallbackQuery, session):
    """تحديث جميع المنتجات"""
    await callback.answer("⏳ سيتم تحديث منتجاتك في أقرب وقت", show_alert=False)
    await my_products_callback(callback, session)


# ======================================================
# 📦 سجل المخزون
# ======================================================

@router.callback_query(F.data.startswith("stock_history:"))
async def show_stock_history(callback: CallbackQuery, session):
    """عرض تاريخ تغيرات المخزون"""
    user_product_id = int(callback.data.split(":")[1])

    from sqlalchemy import select
    from db.models import UserProduct, StockHistory
    from sqlalchemy.orm import selectinload

    result = await session.execute(
        select(UserProduct)
        .options(selectinload(UserProduct.product))
        .where(UserProduct.id == user_product_id)
    )
    user_product = result.scalar_one_or_none()

    if not user_product:
        await callback.answer("❌ المنتج غير موجود", show_alert=True)
        return

    history_result = await session.execute(
        select(StockHistory)
        .where(StockHistory.product_id == user_product.product_id)
        .order_by(StockHistory.recorded_at.desc())
        .limit(10)
    )
    history = history_result.scalars().all()

    text = f"📦 *سجل المخزون*\n📦 {user_product.product.name or 'المنتج'}\n\n"

    if not history:
        text += "لا توجد بيانات تاريخية بعد."
    else:
        for record in history:
            date_str = record.recorded_at.strftime("%d/%m %H:%M")
            status = "متوفر ✅" if record.in_stock else "غير متوفر ❌"
            qty = f" ({record.stock_quantity})" if record.stock_quantity else ""
            text += f"• {date_str}: {status}{qty}\n"

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    builder.button(text="🔄 تحديث", callback_data=f"stock_history:{user_product_id}")
    builder.button(text="🔙 رجوع", callback_data=f"product_detail:{user_product_id}")
    builder.adjust(2)

    await callback.message.edit_text(
        text,
        parse_mode="Markdown",
        reply_markup=builder.as_markup()
    )
    await callback.answer()


# ======================================================
# 🔀 فرز المنتجات
# ======================================================

@router.callback_query(F.data == "sort_products")
async def sort_products_menu(callback: CallbackQuery):
    """عرض خيارات الفرز"""
    await callback.message.edit_text(
        "🔀 *فرز المنتجات*\n\nاختر طريقة الفرز:",
        parse_mode="Markdown",
        reply_markup=sort_products_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data.startswith("sort:"))
async def sort_products_apply(callback: CallbackQuery, session):
    """تطبيق الفرز على قائمة المنتجات"""
    sort_key = callback.data.split(":")[1]  # price | updated | stock | name

    from db.crud import get_user_by_telegram_id, get_user_products
    user = await get_user_by_telegram_id(session, callback.from_user.id)
    user_products = await get_user_products(session, user.id)

    sort_labels = {
        "price": "💰 حسب السعر",
        "updated": "🕐 آخر تحديث",
        "stock": "📦 حسب المخزون",
        "name": "🔤 حسب الاسم",
    }

    if sort_key == "price":
        user_products.sort(key=lambda up: up.product.current_price or 0)
    elif sort_key == "updated":
        user_products.sort(
            key=lambda up: up.product.last_scraped or __import__("datetime").datetime.min,
            reverse=True
        )
    elif sort_key == "stock":
        user_products.sort(key=lambda up: up.product.in_stock or False, reverse=True)
    elif sort_key == "name":
        user_products.sort(key=lambda up: (up.product.name or "").lower())

    label = sort_labels.get(sort_key, sort_key)
    text = f"📦 *منتجاتك* (مرتبة: {label})\n\n"

    for i, up in enumerate(user_products, 1):
        p = up.product
        price_text = f"{p.current_price:.0f}" if p.current_price else "—"
        stock_icon = "✅" if p.in_stock else "❌"
        status_icon = "▶️" if up.status.value == "active" else "⏸"
        text += f"{i}. {status_icon} {(p.name or 'منتج')[:40]}\n"
        text += f"    💰 {price_text} | {stock_icon}\n\n"

    await callback.message.edit_text(
        text,
        parse_mode="Markdown",
        reply_markup=product_list_keyboard(user_products)
    )
    await callback.answer(f"✅ {label}")


# ------------------------------------------------------------------
# Catch-all debugging handler (must be last)
# Logs unhandled messages and nudges users to use the main menu
# ------------------------------------------------------------------
@router.message()
async def catch_all_messages(message: Message, session, state: FSMContext):
    """
    Catch all unhandled messages to help debugging missing handlers.
    Also route common main-menu text to their handlers (mismatch-proof).
    """
    if not message.text:
        return

    text = message.text.strip()
    logger.info(
        "UNHANDLED message from %s: '%s'",
        getattr(message.from_user, "id", "?"),
        (text[:200] if text else "[no text]")
    )

    # Route by Arabic keyword (mismatch-proof)
    try:
        if 'الدعم الفني' in text or 'دعم' in text:
            from bot.handlers.user2 import support_menu
            await support_menu(message, session, state)
            return
        if 'أفضل العروض' in text or 'عروض' in text:
            from bot.handlers.user2 import best_deals
            await best_deals(message, session)
            return
        if 'التقارير' in text:
            from bot.handlers.user2 import reports
            await reports(message, session)
            return
        if 'الاشتراك' in text or 'اشتراك' in text:
            from bot.handlers.user2 import subscription_page
            await subscription_page(message, session)
            return
        if 'الإعدادات' in text or 'إعدادات' in text:
            from bot.handlers.user2 import settings_page
            await settings_page(message, session)
            return
        if 'المساعدة' in text or 'مساعدة' in text:
            from bot.handlers.user2 import help_page
            await help_page(message, session)
            return
        if 'مراقبة فئة' in text or 'فئة' in text:
            from bot.handlers.user2 import monitor_category_start
            await monitor_category_start(message, state)
            return
        if 'مراقبة متجر' in text or 'متجر' in text:
            from bot.handlers.user2 import monitor_store_start
            await monitor_store_start(message, session, state)
            return
        if 'طلب إضافة متجر' in text:
            from bot.handlers.user2 import request_store_start
            await request_store_start(message, state)
            return
    except Exception as e:
        logger.exception('Error routing from catch_all: %s', e)

    # If it looks like a main-menu button press that we don't have a
    # handler for, offer the main menu to the user and log a warning.
    menu_keywords = [
        "إضافة", "منتجاتي", "عروض", "تقارير",
        "اشتراك", "إعدادات", "مساعدة", "دعم",
        "متجر", "فئة", "➕", "📦", "🔔", "🏪"
    ]

    if any(kw in text for kw in menu_keywords):
        logger.warning("POSSIBLE UNREGISTERED BUTTON: '%s'", text[:200])
        from bot.keyboards.main import main_menu_keyboard
        try:
            await message.answer(
                "اضغط على أحد الأزرار في القائمة:",
                reply_markup=main_menu_keyboard()
            )
        except Exception:
            # avoid raising from the catch-all
            pass
