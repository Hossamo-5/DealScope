"""
معالجات المستخدم - الجزء الثاني
==================================
يحتوي على:
- أفضل العروض
- التقارير
- الاشتراكات
- الإعدادات
- المساعدة
- مراقبة الفئات والمتاجر
- طلب إضافة متجر
"""

import logging
import json
from datetime import datetime, timezone

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from redis.asyncio import Redis

from bot.keyboards.main import (
    main_menu_keyboard, deals_list_keyboard, deal_detail_keyboard,
    subscription_keyboard, compare_plans_keyboard, settings_keyboard,
    category_added_keyboard, category_alerts_keyboard, back_home_keyboard
)
from config.settings import ADMIN_GROUP_ID, DASHBOARD_PORT, REDIS_URL

logger = logging.getLogger(__name__)
router = Router()


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _support_status_icon(status) -> str:
    status_value = status.value if hasattr(status, "value") else status
    return {
        "open": "🔵",
        "in_progress": "🟡",
        "waiting_user": "🟠",
        "resolved": "🟢",
        "closed": "⚪",
    }.get(status_value, "⚪")


async def _publish_support_event(channel: str, payload: dict) -> None:
    redis = None
    log = logging.getLogger(__name__)
    try:
        log.info('Publishing support event to %s: %s', channel, payload)
        redis = Redis.from_url(REDIS_URL)
        result = await redis.publish(channel, json.dumps(payload, ensure_ascii=False))
        log.info('Published support event to %s (result=%s)', channel, result)
    except Exception as exc:
        log.exception('Failed to publish support event to %s: %s', channel, exc)
    finally:
        if redis:
            try:
                await redis.close()
            except Exception:
                pass


async def _notify_support_team(bot, session, ticket, user, first_message: str) -> None:
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from db.crud import create_admin_notification

    dept_names = {
        "support": "خدمة العملاء",
        "billing": "الفواتير",
        "technical": "الدعم التقني",
        "general": "عام",
    }
    username = user.username or user.first_name or str(user.telegram_id)
    text = (
        f"🎧 *تذكرة دعم جديدة*\n\n"
        f"🔢 الرقم: `{ticket.ticket_number}`\n"
        f"👤 المستخدم: @{username}\n"
        f"📋 القسم: {dept_names.get(ticket.department.value if hasattr(ticket.department, 'value') else ticket.department, 'عام')}\n\n"
        f"💬 الرسالة:\n{first_message[:200]}"
    )

    builder = InlineKeyboardBuilder()
    builder.button(text="📨 فتح المحادثة", url=f"http://localhost:{DASHBOARD_PORT}/support/{ticket.id}")
    builder.button(text="⚡ رد سريع", callback_data=f"quick_reply:{ticket.id}")
    builder.adjust(2)

    try:
        await bot.send_message(
            ADMIN_GROUP_ID,
            text,
            parse_mode="Markdown",
            reply_markup=builder.as_markup(),
        )
    except Exception as exc:
        logger.warning("Failed to notify admin group for support ticket %s: %s", ticket.id, exc)

    await create_admin_notification(
        session,
        type="new_support_ticket",
        title="تذكرة دعم جديدة 🎧",
        message=f"@{username}: {first_message[:80]}",
        icon="🎧",
        color="purple",
        action_url=f"/support/{ticket.id}",
    )

    await _publish_support_event(
        "support:messages",
        {
            "type": "new_ticket",
            "ticket_id": ticket.id,
            "ticket_number": ticket.ticket_number,
            "user": username,
            "message": first_message[:100],
            "timestamp": utcnow().isoformat(),
        },
    )


def _support_menu_text(open_tickets) -> str:
    return (
        "🎧 *الدعم الفني*\n\n"
        f"التذاكر المفتوحة: {len(open_tickets)}\n\n"
        "كيف يمكننا مساعدتك؟"
    )


async def _send_support_menu(target, session, telegram_user_id: int, edit: bool = False):
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from db.crud import get_user_by_telegram_id, get_user_open_tickets

    user = await get_user_by_telegram_id(session, telegram_user_id)
    if not user:
        return

    open_tickets = await get_user_open_tickets(session, user.id)
    builder = InlineKeyboardBuilder()
    builder.button(text="🆕 فتح تذكرة دعم جديدة", callback_data="support_new")

    for ticket in open_tickets[:3]:
        builder.button(
            text=f"{_support_status_icon(ticket.status)} {ticket.ticket_number}",
            callback_data=f"support_ticket:{ticket.id}",
        )

    builder.button(text="🏠 رجوع للرئيسية", callback_data="go_home")
    builder.adjust(1)

    if edit:
        await target.edit_text(
            _support_menu_text(open_tickets),
            parse_mode="Markdown",
            reply_markup=builder.as_markup(),
        )
    else:
        await target.answer(
            _support_menu_text(open_tickets),
            parse_mode="Markdown",
            reply_markup=builder.as_markup(),
        )


class SupportTicketStates(StatesGroup):
    choosing_department = State()
    writing_message = State()
    replying_to_ticket = State()


# ======================================================
# 🎧 الدعم الفني
# ======================================================

@router.message(F.text == "🎧 الدعم الفني")
async def support_menu(message: Message, session, state: FSMContext = None):
    """Show the support entry menu and recent open tickets."""
    # Always clear any active FSM state so this button always responds,
    # even if the user was in the middle of another flow.
    if state is not None:
        await state.clear()
    import logging
    logging.getLogger(__name__).info(
        f'🎧 SUPPORT MENU CALLED by {getattr(message.from_user, "id", None)}'
    )
    await _send_support_menu(message, session, message.from_user.id)


@router.callback_query(F.data == "support_menu")
async def support_menu_callback(callback: CallbackQuery, session, state: FSMContext):
    """Open the support menu from inline navigation."""
    await state.clear()
    await _send_support_menu(callback.message, session, callback.from_user.id, edit=True)
    await callback.answer()


@router.callback_query(F.data == "support_new")
async def new_ticket_department(callback: CallbackQuery, state: FSMContext):
    """Choose department for a new support ticket."""
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    await state.set_state(SupportTicketStates.choosing_department)

    builder = InlineKeyboardBuilder()
    builder.button(text="💬 خدمة العملاء العامة", callback_data="dept:support")
    builder.button(text="💰 الفواتير والاشتراكات", callback_data="dept:billing")
    builder.button(text="🔧 مشاكل تقنية", callback_data="dept:technical")
    builder.button(text="🔙 رجوع", callback_data="support_menu")
    builder.adjust(1)

    await callback.message.edit_text(
        "📋 اختر نوع الدعم المطلوب:",
        reply_markup=builder.as_markup(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("dept:"))
async def new_ticket_write(callback: CallbackQuery, state: FSMContext):
    """Ask the user for the first support message."""
    department = callback.data.split(":", 1)[1]
    await state.update_data(department=department)
    await state.set_state(SupportTicketStates.writing_message)

    await callback.message.edit_text(
        "✍️ اكتب رسالتك وسنرد عليك في أقرب وقت:\n\n"
        "_يمكنك إرسال نص في هذه المرحلة وسيتم توسيع المرفقات لاحقاً_",
        parse_mode="Markdown",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("support_ticket:"))
async def open_ticket_conversation(callback: CallbackQuery, state: FSMContext, session):
    """Open a ticket summary and switch the user into reply mode for that ticket."""
    from db.crud import get_ticket_by_id

    ticket_id = int(callback.data.split(":", 1)[1])
    ticket = await get_ticket_by_id(session, ticket_id)
    if not ticket or ticket.user.telegram_id != callback.from_user.id:
        await callback.answer("❌ التذكرة غير موجودة", show_alert=True)
        return

    await state.set_state(SupportTicketStates.replying_to_ticket)
    await state.update_data(ticket_id=ticket.id)

    last_messages = ticket.messages[-3:]
    transcript = "\n\n".join(
        f"{('👤' if msg.sender_type.value == 'user' else '🎧')} {msg.sender_name or 'الدعم'}:\n{msg.content[:180]}"
        for msg in last_messages
    ) or "لا توجد رسائل بعد"

    await callback.message.edit_text(
        f"🎫 *{ticket.ticket_number}*\n"
        f"الحالة: {_support_status_icon(ticket.status)}\n\n"
        f"{transcript}\n\n"
        "✍️ أرسل الآن رسالتك التالية وسنضيفها للتذكرة.",
        parse_mode="Markdown",
        reply_markup=back_home_keyboard(),
    )
    await callback.answer()


@router.message(SupportTicketStates.writing_message)
async def create_ticket_from_message(message: Message, state: FSMContext, session):
    """Create a support ticket from the user's first message."""
    from db.crud import create_support_ticket, get_user_by_telegram_id
    from db.models import SupportDepartment, SupportMessageType

    # Accept text, photo, document, or voice
    if message.text:
        content = message.text
        msg_type = SupportMessageType.TEXT
    elif message.photo:
        content = f"[صورة] {message.caption or 'بدون تعليق'}"
        msg_type = SupportMessageType.IMAGE
    elif message.document:
        content = f"[ملف] {message.document.file_name or 'ملف مرفق'}"
        msg_type = SupportMessageType.FILE
    elif message.voice or message.audio:
        content = "[رسالة صوتية]"
        msg_type = SupportMessageType.VOICE
    else:
        await message.answer("❌ الرجاء إرسال رسالة نصية أو صورة أو ملف.")
        return

    state_data = await state.get_data()
    department = state_data.get("department", SupportDepartment.GENERAL.value)
    user = await get_user_by_telegram_id(session, message.from_user.id)
    if not user:
        await state.clear()
        await message.answer("❌ حدث خطأ. أرسل /start وحاول مرة أخرى.")
        return

    dept_names = {
        "support": "خدمة العملاء",
        "billing": "الفواتير",
        "technical": "الدعم التقني",
        "general": "عام",
        "management": "الإدارة",
    }

    try:
        ticket = await create_support_ticket(
            session,
            user=user,
            content=content,
            subject=content[:100],
            department=department,
            message_type=msg_type,
            telegram_message_id=message.message_id,
            sender_name=user.first_name or user.username,
        )
    except Exception as exc:
        logger.error("Failed to create support ticket: %s", exc, exc_info=True)
        await state.clear()
        await message.answer(
            "❌ حدث خطأ أثناء إنشاء التذكرة.\nحاول مرة أخرى أو تواصل معنا مباشرة."
        )
        return

    await state.clear()
    await state.set_state(SupportTicketStates.replying_to_ticket)
    await state.update_data(ticket_id=ticket.id)

    await message.answer(
        f"✅ *تم استلام طلبك بنجاح!*\n\n"
        f"🎫 رقم تذكرتك: `{ticket.ticket_number}`\n"
        f"📋 القسم: {dept_names.get(department, department)}\n"
        f"📊 الحالة: 🔵 مفتوحة\n\n"
        "سنرد عليك في أقرب وقت ممكن.\n"
        "_يمكنك الرد هنا مباشرة لإضافة تفاصيل للتذكرة_",
        parse_mode="Markdown",
        reply_markup=back_home_keyboard(),
    )

    await _notify_support_team(message.bot, session, ticket, user, content)


@router.message(SupportTicketStates.replying_to_ticket)
async def handle_user_reply_to_ticket(message: Message, state: FSMContext, session):
    """Append a reply to the currently selected support ticket."""
    from db.crud import add_ticket_message, get_ticket_by_id, get_user_by_telegram_id
    from db.models import SupportSenderType

    if not message.text:
        await message.answer("❌ حالياً يمكن إرسال رسائل نصية فقط داخل التذكرة.")
        return

    state_data = await state.get_data()
    ticket_id = state_data.get("ticket_id")
    if not ticket_id:
        await state.clear()
        return

    ticket = await get_ticket_by_id(session, ticket_id)
    user = await get_user_by_telegram_id(session, message.from_user.id)
    if not ticket or not user or ticket.user_id != user.id:
        await state.clear()
        await message.answer("❌ لم نتمكن من العثور على التذكرة المطلوبة.")
        return

    await add_ticket_message(
        session,
        ticket=ticket,
        sender_type=SupportSenderType.USER,
        content=message.text,
        sender_user_id=user.id,
        sender_name=user.first_name or user.username,
        telegram_message_id=message.message_id,
    )

    await _publish_support_event(
        "support:messages",
        {
            "ticket_id": ticket.id,
            "sender": "user",
            "content": message.text,
            "timestamp": utcnow().isoformat(),
        },
    )

    await message.answer(
        "📨 تم استلام رسالتك، سنرد عليك قريباً.",
        reply_markup=back_home_keyboard(),
    )


# ======================================================
# 🔥 أفضل العروض
# ======================================================

@router.message(F.text == "🔥 أفضل العروض")
async def best_deals(message: Message, session):
    """
    عرض أفضل العروض المعتمدة من الإدارة
    مرتبة حسب نسبة الخصم
    """
    from sqlalchemy import select
    from db.models import Opportunity, OpportunityStatus
    from sqlalchemy.orm import selectinload

    result = await session.execute(
        select(Opportunity)
        .options(selectinload(Opportunity.product))
        .where(
            Opportunity.status == OpportunityStatus.APPROVED,
            Opportunity.product.has()  # التأكد من وجود المنتج
        )
        .order_by(Opportunity.discount_percent.desc())
        .limit(10)
    )
    opportunities = result.scalars().all()

    if not opportunities:
        await message.answer(
            "🔥 *أفضل العروض*\n\n"
            "لا توجد عروض متاحة حالياً.\n"
            "تابعنا للحصول على أفضل الفرص!",
            parse_mode="Markdown",
            reply_markup=back_home_keyboard()
        )
        return

    text = f"🔥 *أفضل عروض اليوم* ({len(opportunities)} عرض)\n\n"

    for i, opp in enumerate(opportunities, 1):
        name = (opp.product.name or "منتج")[:40]
        text += (
            f"{i}. *{name}*\n"
            f"   خصم {opp.discount_percent:.0f}% | "
            f"السعر: {opp.new_price:.0f}\n\n"
        )

    await message.answer(
        text,
        parse_mode="Markdown",
        reply_markup=deals_list_keyboard(opportunities)
    )


@router.callback_query(F.data == "best_deals")
async def best_deals_callback(callback: CallbackQuery, session):
    """نفس صفحة العروض من callback"""
    from sqlalchemy import select
    from db.models import Opportunity, OpportunityStatus
    from sqlalchemy.orm import selectinload

    result = await session.execute(
        select(Opportunity)
        .options(selectinload(Opportunity.product))
        .where(Opportunity.status == OpportunityStatus.APPROVED)
        .order_by(Opportunity.discount_percent.desc())
        .limit(10)
    )
    opportunities = result.scalars().all()

    await callback.message.edit_text(
        "🔥 *أفضل العروض*",
        parse_mode="Markdown",
        reply_markup=deals_list_keyboard(opportunities)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("deal_detail:"))
async def deal_detail(callback: CallbackQuery, session):
    """تفاصيل عرض واحد"""
    opportunity_id = int(callback.data.split(":")[1])

    from sqlalchemy import select
    from db.models import Opportunity
    from sqlalchemy.orm import selectinload

    result = await session.execute(
        select(Opportunity)
        .options(selectinload(Opportunity.product))
        .where(Opportunity.id == opportunity_id)
    )
    opp = result.scalar_one_or_none()

    if not opp:
        await callback.answer("❌ العرض غير موجود", show_alert=True)
        return

    p = opp.product
    stock_text = "متوفر ✅" if p.in_stock else "غير متوفر ❌"

    text = (
        f"🔥 *عرض قوي!*\n\n"
        f"📦 *المنتج:* {p.name or 'غير معروف'}\n"
        f"💰 *السعر السابق:* {opp.old_price:.2f}\n"
        f"🔥 *السعر الحالي:* *{opp.new_price:.2f}*\n"
        f"📉 *الخصم:* {opp.discount_percent:.1f}%\n"
        f"📦 *المخزون:* {stock_text}\n"
    )

    if opp.custom_message:
        text += f"\n💬 {opp.custom_message}"

    await callback.message.edit_text(
        text,
        parse_mode="Markdown",
        reply_markup=deal_detail_keyboard(opportunity_id, p.id, opp.affiliate_url)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("watch_from_deal:"))
async def watch_product_from_deal(callback: CallbackQuery, session):
    """إضافة منتج للمراقبة من صفحة العروض"""
    product_id = int(callback.data.split(":")[1])

    from db.crud import get_user_by_telegram_id, add_product_to_user, can_user_add_product
    user = await get_user_by_telegram_id(session, callback.from_user.id)

    if not await can_user_add_product(session, user):
        await callback.answer(
            "❌ وصلت للحد الأقصى! قم بترقية الاشتراك.",
            show_alert=True
        )
        return

    await add_product_to_user(session, user.id, product_id)
    await callback.answer("✅ تم إضافة المنتج للمراقبة!", show_alert=True)


# ======================================================
# 📊 التقارير
# ======================================================

@router.message(F.text == "📊 التقارير")
async def reports(message: Message, session):
    """عرض التقارير اليومية"""
    from datetime import datetime, timedelta
    from sqlalchemy import select, func
    from db.models import PriceHistory, Product, UserProduct, MonitoringStatus, Opportunity, OpportunityStatus
    from db.crud import get_user_by_telegram_id

    user = await get_user_by_telegram_id(session, message.from_user.id)

    today = datetime.utcnow().replace(hour=0, minute=0, second=0)

    # حساب المنتجات التي انخفضت أسعارها اليوم من منتجات المستخدم
    user_products = await session.execute(
        select(UserProduct.product_id)
        .where(
            UserProduct.user_id == user.id,
            UserProduct.status == MonitoringStatus.ACTIVE
        )
    )
    product_ids = [row[0] for row in user_products.all()]

    # منتجات انخفضت اليوم
    price_drops_result = await session.execute(
        select(func.count(PriceHistory.id))
        .join(Product, Product.id == PriceHistory.product_id)
        .where(
            PriceHistory.product_id.in_(product_ids),
            PriceHistory.recorded_at >= today
        )
    )
    price_changes = price_drops_result.scalar_one()

    # العروض القوية اليوم
    deals_today_result = await session.execute(
        select(func.count(Opportunity.id))
        .where(
            Opportunity.status == OpportunityStatus.APPROVED,
            Opportunity.published_at >= today
        )
    )
    deals_today = deals_today_result.scalar_one()

    text = (
        f"📊 *تقرير اليوم*\n\n"
        f"🔄 {price_changes} تغيير في الأسعار\n"
        f"🔥 {deals_today} عروض قوية\n"
        f"📦 {len(product_ids)} منتج تحت المراقبة"
    )

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    builder.button(text="📅 تقرير يومي", callback_data="report:daily")
    builder.button(text="📅 تقرير أسبوعي", callback_data="report:weekly")
    builder.button(text="📅 تقرير شهري", callback_data="report:monthly")
    builder.button(text="🏠 رجوع للرئيسية", callback_data="go_home")
    builder.adjust(3, 1)

    await message.answer(text, parse_mode="Markdown", reply_markup=builder.as_markup())


# ======================================================
# 📂 مراقبة الفئات
# ======================================================

class AddCategoryStates(StatesGroup):
    waiting_for_url = State()


@router.message(F.text == "📂 مراقبة فئة")
async def monitor_category_start(message: Message, state: FSMContext):
    """بدء إضافة فئة للمراقبة"""
    await state.set_state(AddCategoryStates.waiting_for_url)
    await message.answer(
        "📂 أرسل رابط الفئة التي تريد مراقبتها\n\n"
        "سيتم تنبيهك عند:\n"
        "🆕 ظهور منتجات جديدة\n"
        "🏷 وجود تخفيضات\n"
        "🔄 تغيرات مهمة في الفئة\n\n"
        "مثال: https://www.amazon.sa/s?rh=n:12345"
    )


@router.message(AddCategoryStates.waiting_for_url)
async def process_category_url(message: Message, state: FSMContext, session):
    """معالجة رابط الفئة"""
    url = message.text.strip()

    if not url.startswith(("http://", "https://")):
        await message.answer("❌ الرابط غير صالح. أرسله مرة أخرى:")
        return

    from db.crud import get_user_by_telegram_id, add_category_to_user
    user = await get_user_by_telegram_id(session, message.from_user.id)

    # التحقق من خطة المستخدم (الفئات غير متاحة في الخطة المجانية)
    from config.settings import PLAN_LIMITS
    if PLAN_LIMITS[user.plan]["max_categories"] == 0:
        await message.answer(
            "❌ مراقبة الفئات غير متاحة في الخطة المجانية.\n"
            "قم بترقية اشتراكك للوصول لهذه الميزة.",
            reply_markup=back_home_keyboard()
        )
        await state.clear()
        return

    category = await add_category_to_user(session, user.id, url)
    await state.clear()

    await message.answer(
        f"✅ *تم إضافة الفئة للمراقبة!*\n\n"
        f"🔗 {url[:60]}...",
        parse_mode="Markdown",
        reply_markup=category_added_keyboard(category.id)
    )


# ======================================================
# 🏪 مراقبة متجر
# ======================================================

class AddStoreMonitorStates(StatesGroup):
    waiting_for_url = State()


@router.message(F.text == "🏪 مراقبة متجر")
async def monitor_store_start(message: Message, state: FSMContext, session):
    """بدء مراقبة متجر كامل"""
    from db.crud import get_user_by_telegram_id
    from config.settings import PLAN_LIMITS

    user = await get_user_by_telegram_id(session, message.from_user.id)

    if PLAN_LIMITS[user.plan]["max_stores"] == 0:
        await message.answer(
            "❌ مراقبة المتاجر متاحة في الاشتراك الاحترافي فقط.\n"
            "قم بالترقية للوصول لهذه الميزة.",
            reply_markup=back_home_keyboard()
        )
        return

    await state.set_state(AddStoreMonitorStates.waiting_for_url)
    await message.answer(
        "🏪 أرسل رابط المتجر الذي تريد مراقبته:\n\n"
        "مثال: https://www.extra.com"
    )


# ======================================================
# 💳 الاشتراكات
# ======================================================

@router.message(F.text == "💳 الاشتراك")
async def subscription_page(message: Message, session):
    """صفحة الاشتراكات"""
    from db.crud import get_user_by_telegram_id
    from config.settings import PLAN_LIMITS

    user = await get_user_by_telegram_id(session, message.from_user.id)
    plan = user.plan

    plan_names = {
        "free": "🆓 مجانية",
        "basic": "⭐ أساسية",
        "professional": "💎 احترافية"
    }

    limits = PLAN_LIMITS[plan]

    text = (
        f"💳 *خطتك الحالية: {plan_names.get(plan, plan)}*\n\n"
        f"📦 المنتجات: {limits['max_products']}\n"
        f"📂 الفئات: {limits['max_categories'] or 'غير متاح'}\n"
        f"🏪 المتاجر: {limits['max_stores'] or 'غير متاح'}\n"
        f"⏱ فحص كل: {limits['scan_interval']} دقيقة\n"
    )

    await message.answer(text, parse_mode="Markdown", reply_markup=subscription_keyboard(plan))


@router.callback_query(F.data == "subscription")
async def subscription_callback(callback: CallbackQuery, session):
    """صفحة الاشتراكات من callback"""
    from db.crud import get_user_by_telegram_id
    user = await get_user_by_telegram_id(session, callback.from_user.id)

    await callback.message.edit_text(
        "💳 *الاشتراكات*",
        parse_mode="Markdown",
        reply_markup=subscription_keyboard(user.plan)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("plan_info:"))
async def plan_info(callback: CallbackQuery):
    """عرض تفاصيل خطة محددة"""
    plan = callback.data.split(":")[1]

    from config.settings import PLAN_LIMITS
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    limits = PLAN_LIMITS.get(plan, {})

    plan_details = {
        "free": (
            "🆓 *الخطة المجانية*\n\n"
            f"• {limits['max_products']} منتجات\n"
            "• تحديث كل 60 دقيقة\n"
            "• تنبيهات أساسية\n"
            "• السعر: مجاني ✨"
        ),
        "basic": (
            "⭐ *الاشتراك الأساسي*\n\n"
            f"• حتى {limits['max_products']} منتج\n"
            "• مراقبة الفئات ✅\n"
            f"• تحديث كل {limits['scan_interval']} دقيقة\n"
            "• تقارير كاملة ✅\n"
            "• طلب إضافة متجر ✅\n"
            "• السعر: 10 ريال/شهر 💰"
        ),
        "professional": (
            "💎 *الاشتراك الاحترافي*\n\n"
            f"• حتى {limits['max_products']} منتج\n"
            "• مراقبة المتاجر الكاملة ✅\n"
            f"• تحديث كل {limits['scan_interval']} دقيقة\n"
            "• أولوية أعلى ✅\n"
            "• تنبيهات متقدمة ✅\n"
            "• تقارير وتحليلات ✅\n"
            "• السعر: 49 ريال/شهر 💰"
        )
    }

    builder = InlineKeyboardBuilder()
    if plan != "free":
        builder.button(text="⬆️ ترقية لهذه الخطة", callback_data=f"upgrade:{plan}")
    builder.button(text="🔙 رجوع", callback_data="subscription")
    builder.adjust(1)

    await callback.message.edit_text(
        plan_details.get(plan, "خطة غير معروفة"),
        parse_mode="Markdown",
        reply_markup=builder.as_markup()
    )
    await callback.answer()


@router.callback_query(F.data == "compare_plans")
async def compare_plans(callback: CallbackQuery):
    """مقارنة الخطط"""
    text = (
        "📊 *مقارنة الخطط*\n\n"
        "```\n"
        "الميزة        | مجاني | أساسي | احترافي\n"
        "المنتجات      |   3   |  50   |   300\n"
        "الفئات        |  ❌   |  10   |    50\n"
        "المتاجر       |  ❌   |  ❌   |    20\n"
        "الفحص (دقيقة) |  60   |  30   |    15\n"
        "التقارير      |  ❌   |  ✅   |    ✅\n"
        "```\n"
    )

    await callback.message.edit_text(
        text,
        parse_mode="Markdown",
        reply_markup=compare_plans_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data.startswith("upgrade:") | (F.data == "upgrade_plan"))
async def upgrade_plan(callback: CallbackQuery):
    """
    صفحة الترقية
    """
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    builder.button(text="💬 تواصل مع الدعم", url="https://t.me/UncleNull")
    builder.button(text="🔙 رجوع", callback_data="go_home")
    builder.adjust(1)

    await callback.message.edit_text(
        "💳 *ترقية الاشتراك*\n\n"
        "لترقية اشتراكك، تواصل معنا على تيليغرام:\n"
        "👤 @UncleNull\n\n"
        "أو اضغط الزر أدناه:",
        parse_mode="Markdown",
        reply_markup=builder.as_markup()
    )
    await callback.answer()


# ======================================================
# ⚙️ الإعدادات
# ======================================================

@router.message(F.text == "⚙️ الإعدادات")
async def settings_page(message: Message, session):
    """صفحة الإعدادات"""
    from db.crud import get_user_by_telegram_id
    user = await get_user_by_telegram_id(session, message.from_user.id)

    plan_names = {"free": "مجانية", "basic": "أساسية", "professional": "احترافية"}

    text = (
        f"⚙️ *إعدادات الحساب*\n\n"
        f"👤 الاسم: {user.first_name or 'غير محدد'}\n"
        f"🔗 المعرف: @{user.username or 'غير محدد'}\n"
        f"💳 الخطة: {plan_names.get(user.plan, user.plan)}\n"
        f"🔕 التنبيهات: {'مكتومة ⏸' if user.muted else 'مفعلة ✅'}"
    )

    await message.answer(text, parse_mode="Markdown", reply_markup=settings_keyboard())


@router.callback_query(F.data == "settings_mute")
async def toggle_mute(callback: CallbackQuery, session):
    """تفعيل/إلغاء كتم التنبيهات"""
    from db.crud import get_user_by_telegram_id
    from sqlalchemy import update
    from db.models import User

    user = await get_user_by_telegram_id(session, callback.from_user.id)
    new_mute = not user.muted

    await session.execute(
        update(User)
        .where(User.id == user.id)
        .values(muted=new_mute)
    )
    await session.commit()

    status = "مكتومة ⏸" if new_mute else "مفعلة ✅"
    await callback.answer(f"التنبيهات {status}", show_alert=True)


# ======================================================
# ❓ المساعدة
# ======================================================

@router.message(F.text == "❓ المساعدة")
async def help_page(message: Message, session):  # pragma: no cover
    """Interactive help center with multiple guided sections."""
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from db.crud import get_user_by_telegram_id

    _ = await get_user_by_telegram_id(session, message.from_user.id)

    text = (
        "❓ *مركز المساعدة والدليل*\n\n"
        "اختر الموضوع الذي تريد معرفته:"
    )

    builder = InlineKeyboardBuilder()
    builder.button(text="🚀 البدء السريع", callback_data="help:quickstart")
    builder.button(text="➕ إضافة منتج", callback_data="help:add_product")
    builder.button(text="🔔 التنبيهات", callback_data="help:alerts")
    builder.button(text="💳 الاشتراكات", callback_data="help:plans")
    builder.button(text="📂 مراقبة الفئات", callback_data="help:categories")
    builder.button(text="🏪 مراقبة المتاجر", callback_data="help:stores")
    builder.button(text="❓ الأسئلة الشائعة", callback_data="help:faq")
    builder.button(text="🎧 تواصل مع الدعم", callback_data="support_new")
    builder.button(text="🔄 إعادة عرض الشرح", callback_data="help:restart_onboarding")
    builder.button(text="🏠 رجوع للرئيسية", callback_data="go_home")
    builder.adjust(2, 2, 2, 2, 1, 1)

    await message.answer(text, parse_mode="Markdown", reply_markup=builder.as_markup())


@router.callback_query(F.data == "help:main")
async def help_main(callback: CallbackQuery, session):  # pragma: no cover
    await help_page(callback.message, session)
    await callback.answer()


@router.callback_query(F.data == "help:quickstart")
async def help_quickstart(callback: CallbackQuery):  # pragma: no cover
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    text = (
        "🚀 *البدء السريع — 3 خطوات*\n\n"
        "*الخطوة 1: أضف منتجاً*\n"
        "اضغط ➕ إضافة منتج\n"
        "ثم أرسل رابط المنتج من أي متجر\n\n"
        "*الخطوة 2: اختر التنبيه*\n"
        "اختر متى تريد التنبيه:\n"
        "• عند انخفاض السعر 📉\n"
        "• عند توفر المنتج 🟢\n"
        "• عند خصم معين 💥\n\n"
        "*الخطوة 3: انتظر التنبيهات*\n"
        "سيراقب البوت المنتج تلقائياً\n"
        "وسيرسل لك إشعاراً فور حدوث تغيير! 🎯\n\n"
        "⏱ *مدة الفحص:*\n"
        "الخطة المجانية: كل 60 دقيقة\n"
        "الأساسية: كل 30 دقيقة\n"
        "الاحترافية: كل 15 دقيقة"
    )

    builder = InlineKeyboardBuilder()
    builder.button(text="➕ جرّب إضافة منتج الآن", callback_data="help:go_add_product")
    builder.button(text="🔙 رجوع للمساعدة", callback_data="help:main")
    builder.adjust(1)
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(F.data == "help:go_add_product")
async def help_go_add_product(callback: CallbackQuery, state: FSMContext):  # pragma: no cover
    from bot.handlers.user import AddProductStates

    await state.set_state(AddProductStates.waiting_for_url)
    await callback.message.answer(
        "🔗 أرسل رابط المنتج الذي تريد مراقبته:\n\n"
        "مثال: https://www.amazon.sa/dp/B08L5TNJHG"
    )
    await callback.answer()


@router.callback_query(F.data == "help:add_product")
async def help_add_product(callback: CallbackQuery):  # pragma: no cover
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    text = (
        "➕ *كيف تضيف منتجاً؟*\n\n"
        "*روابط مقبولة ✅*\n"
        "• https://amazon.sa/dp/B08...\n"
        "• https://amazon.com/dp/B08...\n"
        "• https://store.myshopify.com/products/...\n"
        "• معظم متاجر WooCommerce\n\n"
        "*روابط غير مقبولة ❌*\n"
        "• روابط بدون http/https\n"
        "• روابط صفحات البحث\n"
        "• روابط الفئات (استخدم 'مراقبة فئة')\n\n"
        "*💡 نصيحة:*\n"
        "احذف أي شيء بعد علامة ? في الرابط\n\n"
        "*مثال:*\n"
        "✅ https://amazon.sa/dp/B08L5TNJHG"
    )

    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 رجوع", callback_data="help:main")
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(F.data == "help:alerts")
async def help_alerts(callback: CallbackQuery):  # pragma: no cover
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    text = (
        "🔔 *أنواع التنبيهات*\n\n"
        "📉 *انخفاض السعر*\n"
        "يرسل تنبيهاً عند أي انخفاض في السعر\n\n"
        "💥 *خصم كبير فقط*\n"
        "يرسل فقط عند خصم 10% أو أكثر\n\n"
        "🟢 *عودة للمخزون*\n"
        "يرسل عندما يعود منتج نافد\n\n"
        "🔴 *نفاد المخزون*\n"
        "يرسل عندما ينفد المنتج\n\n"
        "🎯 *سعر مستهدف*\n"
        "تحدد سعراً معيناً وتستقبل تنبيهاً\n"
        "عندما يصل المنتج لهذا السعر أو أقل\n\n"
        "🔄 *أي تغيير في السعر*\n"
        "ارتفاع أو انخفاض — تنبيه في كل مرة"
    )

    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 رجوع", callback_data="help:main")
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(F.data == "help:faq")
async def help_faq(callback: CallbackQuery):  # pragma: no cover
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    text = (
        "❓ *الأسئلة الشائعة*\n\n"
        "*س: لماذا لم يصلني تنبيه رغم انخفاض السعر؟*\n"
        "ج: تحقق من إعداد التنبيه وحالة المراقبة والكتم.\n\n"
        "*س: كم مرة يفحص البوت المنتج؟*\n"
        "ج: مجاني كل 60 دقيقة، أساسي كل 30، احترافي كل 15.\n\n"
        "*س: المتجر الذي أريده غير مدعوم؟*\n"
        "ج: استخدم زر '🏬 طلب إضافة متجر'.\n\n"
        "*س: كيف أوقف التنبيهات مؤقتاً؟*\n"
        "ج: منتجاتي ← اختر المنتج ← ⏸ إيقاف.\n\n"
        "*س: كيف أرى تاريخ السعر؟*\n"
        "ج: منتجاتي ← المنتج ← 📈 سجل السعر."
    )

    builder = InlineKeyboardBuilder()
    builder.button(text="🎧 سؤالك غير موجود؟ تواصل معنا", callback_data="support_new")
    builder.button(text="🔙 رجوع", callback_data="help:main")
    builder.adjust(1)
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(F.data == "help:supported")
async def help_supported_sites(callback: CallbackQuery):
    """المواقع المدعومة"""
    text = (
        "🌐 *المواقع المدعومة حالياً:*\n\n"
        "🛒 Amazon (جميع الدول)\n"
        "🛍 Shopify stores\n"
        "🏪 WooCommerce stores\n"
        "🌐 معظم المتاجر العامة\n\n"
        "💡 إذا لم يعمل موقعك، اطلب إضافته من\n"
        "'طلب إضافة متجر' في القائمة الرئيسية"
    )
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 رجوع", callback_data="help:main")
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(F.data == "help:categories")
async def help_categories(callback: CallbackQuery):  # pragma: no cover
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    text = (
        "📂 *مراقبة الفئات*\n\n"
        "راقب قسماً كاملاً من المتجر، وليس منتجاً واحداً فقط.\n"
        "ستتلقى تنبيهات عند ظهور منتجات جديدة أو عروض قوية.\n\n"
        "متاحة في الخطط المدفوعة."
    )
    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 رجوع", callback_data="help:main")
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(F.data == "help:stores")
async def help_stores(callback: CallbackQuery):  # pragma: no cover
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    text = (
        "🏪 *مراقبة المتاجر*\n\n"
        "هذه الميزة تراقب متجراً كاملاً لاكتشاف التخفيضات الجديدة تلقائياً.\n"
        "متاحة في الخطة الاحترافية فقط."
    )
    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 رجوع", callback_data="help:main")
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(F.data == "help:plans")
async def help_plans(callback: CallbackQuery, session):  # pragma: no cover
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from db.crud import get_user_by_telegram_id

    user = await get_user_by_telegram_id(session, callback.from_user.id)
    current = user.plan.value if hasattr(user.plan, "value") else str(user.plan)
    plan_icon = {"free": "🆓", "basic": "⭐", "professional": "💎"}.get(current, "🆓")
    plan_name = {"free": "مجانية", "basic": "أساسية", "professional": "احترافية"}.get(current, current)

    text = (
        f"💳 *خطط الاشتراك*\n\n"
        f"خطتك الحالية: {plan_icon} {plan_name}\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "🆓 *مجانية — 0 ريال*\n"
        "• 3 منتجات فقط\n"
        "• فحص كل 60 دقيقة\n"
        "• تنبيهات أساسية\n\n"
        "⭐ *أساسية — 10 ريال/شهر*\n"
        "• 50 منتج\n"
        "• مراقبة الفئات\n"
        "• فحص كل 30 دقيقة\n\n"
        "💎 *احترافية — 49 ريال/شهر*\n"
        "• 300 منتج\n"
        "• مراقبة المتاجر الكاملة\n"
        "• فحص كل 15 دقيقة\n"
        "━━━━━━━━━━━━━━━━━━━━"
    )

    builder = InlineKeyboardBuilder()
    if current == "free":
        builder.button(text="⬆️ ترقية الاشتراك", callback_data="upgrade_plan")
    builder.button(text="🔙 رجوع", callback_data="help:main")
    builder.adjust(1)

    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(F.data == "help:restart_onboarding")
async def restart_onboarding(callback: CallbackQuery):  # pragma: no cover
    from bot.handlers.user import onboarding_step_1_callback

    await callback.message.edit_text("🔄 سنعيد عرض شرح البوت من البداية...")
    callback.data = "onboarding:step1"
    await onboarding_step_1_callback(callback)


# ======================================================
# 🏬 طلب إضافة متجر
# ======================================================

class RequestStoreStates(StatesGroup):
    waiting_for_url = State()


@router.message(F.text == "🏬 طلب إضافة متجر")
async def request_store_start(message: Message, state: FSMContext):
    """بدء طلب إضافة متجر جديد"""
    await state.set_state(RequestStoreStates.waiting_for_url)
    await message.answer(
        "🏬 إذا كان المتجر غير مدعوم حالياً، أرسل رابطه وسنراجعه.\n\n"
        "أرسل رابط المتجر الرئيسي:\n"
        "مثال: https://www.noon.com"
    )


@router.message(RequestStoreStates.waiting_for_url)
async def process_store_request(message: Message, state: FSMContext, session):
    """معالجة طلب إضافة متجر"""
    url = message.text.strip()

    if not url.startswith(("http://", "https://")):
        await message.answer("❌ الرابط غير صالح. أرسله مرة أخرى:")
        return

    from db.crud import get_user_by_telegram_id, create_admin_notification
    from db.models import StoreRequest
    from config.settings import ADMIN_GROUP_ID

    user = await get_user_by_telegram_id(session, message.from_user.id)

    # حفظ الطلب في قاعدة البيانات
    request = StoreRequest(user_id=user.id, store_url=url)
    session.add(request)
    await session.commit()
    await session.refresh(request)

    display_name = user.username or user.first_name or user.telegram_id
    await create_admin_notification(
        session,
        type="store_request",
        title="طلب متجر جديد 🏪",
        message=f"@{display_name} طلب إضافة {url}",
        icon="🏪",
        color="orange",
        action_url="/store-requests",
    )

    await state.clear()

    # إرسال الطلب للإدارة
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ اعتماد المتجر", callback_data=f"store_req_approve:{request.id}")
    builder.button(text="🔍 تحت المراجعة", callback_data=f"store_req_review:{request.id}")
    builder.button(text="❌ رفض الطلب", callback_data=f"store_req_reject:{request.id}")
    builder.adjust(2, 1)

    admin_msg = (
        f"🏬 *طلب متجر جديد*\n\n"
        f"👤 المستخدم: @{user.username or user.first_name}\n"
        f"🔗 الرابط: {url}"
    )

    try:
        await message.bot.send_message(
            ADMIN_GROUP_ID,
            admin_msg,
            parse_mode="Markdown",
            reply_markup=builder.as_markup()
        )
    except Exception as e:
        logger.error(f"Failed to send store request to admin: {e}")

    await message.answer(
        "✅ *تم إرسال طلبك للإدارة!*\n\n"
        "سيتم إشعارك عند دعم المتجر.",
        parse_mode="Markdown",
        reply_markup=back_home_keyboard()
    )


# ======================================================
# 🎛 Dynamic Menu Button Handler
# ======================================================

async def execute_handler(handler_name: str, message: Message, session, state: FSMContext):  # pragma: no cover
    """
    Maps handler name to actual function and executes it.
    Called when user presses a dynamic menu button.
    """
    from bot.handlers.user import (
        add_product_start, my_products
    )
    
    handler_map = {
        "add_product": add_product_start,
        "my_products": my_products,
        "best_deals": best_deals,
        "reports": reports,
        "monitor_category": monitor_category_start,
        "monitor_store": monitor_store_start,
        "subscription": subscription_page,
        "settings": settings_page,
        "help": help_page,
        "request_store": request_store_start,
    }
    
    handler = handler_map.get(handler_name)
    if handler:
        try:
            await handler(message, session)
        except Exception as e:
            logger.error(f"Error executing handler {handler_name}: {e}")
            await message.answer(
                "❌ حدث خطأ. يرجى المحاولةلاحقاً.",
                reply_markup=back_home_keyboard()
            )


@router.message()
async def handle_dynamic_button(message: Message, state: FSMContext, session):  # pragma: no cover
    """
    Catch-all handler for dynamic menu button presses.
    Looks up button label in DB and executes its action.
    """
    from sqlalchemy import select
    from db.models import BotMenuButton
    
    text = (message.text or "").strip()
    if not text:
        return
    
    try:
        # Look up button by label in database
        result = await session.execute(
            select(BotMenuButton)
            .where(
                BotMenuButton.label == text,
                BotMenuButton.is_active == True
            )
        )
        button = result.scalar_one_or_none()
        
        if not button:
            # Not a menu button, ignore and let other handlers take it
            return
        
        # Execute action based on type
        if button.action_type == "handler":
            # Call existing handler function
            await execute_handler(button.action_value, message, session, state)
        
        elif button.action_type == "message":
            # Send a simple text message
            await message.answer(button.action_value)
        
        elif button.action_type == "url":
            # Send text with link button
            from aiogram.utils.keyboard import InlineKeyboardBuilder
            builder = InlineKeyboardBuilder()
            builder.button(text="🔗 فتح الرابط", url=button.action_value)
            await message.answer(
                "اضغط الزر للفتح:",
                reply_markup=builder.as_markup()
            )
        
        elif button.action_type == "support":
            # Open support menu
            await _send_support_menu(message, session, message.from_user.id)
        
        elif button.action_type == "subscribe":
            # Show subscription page
            await subscription_page(message, session)
        
        elif button.action_type == "menu":
            # Show sub-menu (future implementation)
            await message.answer("📋 هذه قائمة فرعية قادمة قريباً")
        
        elif button.action_type == "command":
            # This would simulate a command - not typically used for buttons
            await message.answer("⚙️ أمر محجوز للاستخدام الداخلي")
        
    except Exception as e:
        logger.error(f"Error handling dynamic button '{text}': {e}")
        # Silently fail - don't interrupt user experience
        pass

