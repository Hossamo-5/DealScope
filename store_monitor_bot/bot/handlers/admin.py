"""
معالجات الإدارة (Admin Handlers)
===================================
جميع الأوامر والأزرار الخاصة بالإدارة
تتحقق دائماً من أن المستخدم مدير قبل التنفيذ

يشمل:
- مراجعة الفرص واعتمادها
- إدارة طلبات المتاجر
- إحصائيات النظام
- إدارة المشتركين
"""

import logging
from datetime import datetime, timedelta

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config.settings import ADMIN_USER_IDS, ADMIN_GROUP_ID, PLAN_LIMITS

logger = logging.getLogger(__name__)
router = Router()


@router.message(Command("getid"))
async def cmd_getid(message: Message):
    """Return chat ID and user ID for private/group/channel contexts."""
    chat = message.chat
    user = message.from_user

    lines = ["🔍 *معلومات المعرفات*\n"]

    if chat.type == "private":
        lines.append("👤 *معرفك:*")
        lines.append(f"`{user.id}`")
        if user.username:
            lines.append(f"@{user.username}")
    else:
        lines.append("👥 *معرف هذه المجموعة/القناة:*")
        lines.append(f"`{chat.id}`")
        lines.append(f"📛 {chat.title}")
        if chat.username:
            lines.append(f"🔗 @{chat.username}")
        lines.append("\n👤 *معرفك الشخصي:*")
        lines.append(f"`{user.id}`")

    lines.append(
        "\n💡 _انسخ المعرف وأضفه في:_\n"
        "_لوحة الإدارة ← المجموعات_"
    )

    await message.answer("\n".join(lines), parse_mode="Markdown")


# ======================================================
# 🔐 Filter - التحقق من صلاحيات الإدارة
# ======================================================

def is_admin(user_id: int) -> bool:
    """التحقق هل المستخدم مدير"""
    return user_id in ADMIN_USER_IDS


def admin_required(func):
    """
    Decorator للتحقق من صلاحيات الإدارة
    يُستخدم على جميع handlers الإدارة
    """
    async def wrapper(event, *args, **kwargs):
        user_id = event.from_user.id if hasattr(event, 'from_user') else None
        if not user_id or not is_admin(user_id):
            if hasattr(event, 'answer'):
                await event.answer("❌ ليس لديك صلاحية لهذا الأمر.")
            return
        return await func(event, *args, **kwargs)
    return wrapper


# ======================================================
# 📊 لوحة الإدارة الرئيسية
# ======================================================

@router.message(Command("admin"))
async def admin_panel(message: Message, session):
    """
    لوحة الإدارة الرئيسية
    تظهر فقط للمديرين المعرّفين في ADMIN_USER_IDS
    """
    if not is_admin(message.from_user.id):
        return

    from db.crud import get_dashboard_stats
    stats = await get_dashboard_stats(session)

    text = (
        f"🎛 *لوحة الإدارة*\n\n"
        f"👥 المشتركون: {stats['users_count']}\n"
        f"📦 المنتجات المراقبة: {stats['products_count']}\n"
        f"💡 فرص جديدة: {stats['new_opportunities']}\n"
        f"📤 عروض أُرسلت اليوم: {stats['sent_today']}\n"
    )

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    builder.button(text="💡 مراجعة الفرص", callback_data="admin_opportunities")
    builder.button(text="🏬 طلبات المتاجر", callback_data="admin_store_requests")
    builder.button(text="👥 المشتركون", callback_data="admin_users")
    builder.button(text="📤 إرسال إعلان", callback_data="admin_broadcast")
    builder.button(text="💊 حالة النظام", callback_data="admin_system_health")
    builder.adjust(2, 2, 1)

    await message.answer(text, parse_mode="Markdown", reply_markup=builder.as_markup())


@router.callback_query(F.data == "admin_panel")
async def admin_panel_callback(callback: CallbackQuery, session):
    """لوحة الإدارة من callback"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ غير مصرح", show_alert=True)
        return

    from db.crud import get_dashboard_stats
    stats = await get_dashboard_stats(session)

    text = (
        f"🎛 *لوحة الإدارة*\n\n"
        f"👥 المشتركون: {stats['users_count']}\n"
        f"📦 المنتجات: {stats['products_count']}\n"
        f"💡 فرص جديدة: {stats['new_opportunities']}\n"
        f"📤 أُرسل اليوم: {stats['sent_today']}\n"
    )

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    builder.button(text="💡 مراجعة الفرص", callback_data="admin_opportunities")
    builder.button(text="🏬 طلبات المتاجر", callback_data="admin_store_requests")
    builder.button(text="👥 المشتركون", callback_data="admin_users")
    builder.button(text="📤 إرسال إعلان", callback_data="admin_broadcast")
    builder.button(text="💊 حالة النظام", callback_data="admin_system_health")
    builder.adjust(2, 2, 1)

    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=builder.as_markup())
    await callback.answer()


# ======================================================
# 💡 مراجعة الفرص
# ======================================================

@router.callback_query(F.data == "admin_opportunities")
async def admin_opportunities(callback: CallbackQuery, session):
    """عرض الفرص الجديدة للمراجعة"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ غير مصرح", show_alert=True)
        return

    from db.crud import get_new_opportunities
    opportunities = await get_new_opportunities(session)

    if not opportunities:
        from aiogram.utils.keyboard import InlineKeyboardBuilder
        builder = InlineKeyboardBuilder()
        builder.button(text="🔙 رجوع", callback_data="admin_panel")

        await callback.message.edit_text(
            "✅ لا توجد فرص جديدة للمراجعة.",
            reply_markup=builder.as_markup()
        )
        await callback.answer()
        return

    text = f"💡 *فرص جديدة* ({len(opportunities)})\n\n"

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()

    for opp in opportunities[:5]:  # عرض أول 5
        name = (opp.product.name or "منتج")[:30]
        discount = f"{opp.discount_percent:.0f}%"
        score = f"{opp.score:.0f}"
        builder.button(
            text=f"🔥 {name} (-{discount}) [{score}pts]",
            callback_data=f"admin_opp_detail:{opp.id}"
        )

    builder.button(text="🔙 رجوع", callback_data="admin_panel")
    builder.adjust(1)

    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("admin_opp_detail:"))
async def admin_opportunity_detail(callback: CallbackQuery, session):
    """تفاصيل فرصة محددة مع خيارات الإدارة"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ غير مصرح", show_alert=True)
        return

    opp_id = int(callback.data.split(":")[1])

    from sqlalchemy import select
    from db.models import Opportunity
    from sqlalchemy.orm import selectinload

    result = await session.execute(
        select(Opportunity)
        .options(selectinload(Opportunity.product))
        .where(Opportunity.id == opp_id)
    )
    opp = result.scalar_one_or_none()

    if not opp:
        await callback.answer("❌ الفرصة غير موجودة", show_alert=True)
        return

    from core.monitor import OpportunityScorer
    scorer = OpportunityScorer()
    score_label = scorer.get_score_label(opp.score)

    text = (
        f"💡 *تفاصيل الفرصة #{opp.id}*\n\n"
        f"📦 *المنتج:* {opp.product.name or 'غير معروف'}\n"
        f"💰 *السعر السابق:* {opp.old_price:.2f}\n"
        f"🔥 *السعر الحالي:* {opp.new_price:.2f}\n"
        f"📉 *الخصم:* {opp.discount_percent:.1f}%\n"
        f"📦 *المخزون:* {'متوفر ✅' if opp.in_stock else 'غير متوفر ❌'}\n"
        f"⭐ *التقييم:* {score_label} ({opp.score}/100)\n\n"
        f"🔗 {opp.product.url}"
    )

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    builder.button(text="🔗 إضافة رابط أفلييت", callback_data=f"opp_add_affiliate:{opp_id}")
    builder.button(text="✏️ تعديل الرسالة", callback_data=f"opp_edit:{opp_id}")
    builder.button(text="✅ اعتماد وإرسال", callback_data=f"opp_approve:{opp_id}")
    builder.button(text="⏰ تأجيل", callback_data=f"opp_postpone:{opp_id}")
    builder.button(text="❌ تجاهل", callback_data=f"opp_reject:{opp_id}")
    builder.button(text="🔙 رجوع", callback_data="admin_opportunities")
    builder.adjust(2, 1, 2, 1)

    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=builder.as_markup())
    await callback.answer()


# ======================================================
# ✅ اعتماد فرصة
# ======================================================

class AffiliateStates(StatesGroup):
    """حالات إضافة رابط الأفلييت"""
    waiting_for_url = State()
    waiting_for_message = State()


@router.callback_query(F.data.startswith("opp_add_affiliate:"))
async def add_affiliate_url(callback: CallbackQuery, state: FSMContext):
    """طلب رابط الأفلييت من المدير"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ غير مصرح", show_alert=True)
        return

    opp_id = int(callback.data.split(":")[1])
    await state.set_state(AffiliateStates.waiting_for_url)
    await state.update_data(opportunity_id=opp_id)

    await callback.message.answer(
        "🔗 أرسل رابط الأفلييت الخاص بهذا المنتج:\n\n"
        "اذهب للمنتج، اصنع رابط العمولة، ثم أرسله هنا."
    )
    await callback.answer()


@router.message(AffiliateStates.waiting_for_url)
async def process_affiliate_url(message: Message, state: FSMContext, session):
    """تخزين رابط الأفلييت والانتقال لتأكيد الإرسال"""
    url = message.text.strip()
    data = await state.get_data()
    opp_id = data.get("opportunity_id")

    await state.update_data(affiliate_url=url)

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ إرسال الآن بدون تعديل", callback_data=f"opp_approve_final:{opp_id}")
    builder.button(text="✏️ تعديل النص أولاً", callback_data=f"opp_edit_msg:{opp_id}")
    builder.button(text="❌ إلغاء", callback_data=f"admin_opp_detail:{opp_id}")
    builder.adjust(1)

    await message.answer(
        f"✅ تم حفظ الرابط.\n\nهل تريد إرسال العرض الآن؟",
        reply_markup=builder.as_markup()
    )


@router.callback_query(F.data.startswith("opp_approve:") | F.data.startswith("opp_approve_final:"))
async def approve_opportunity(callback: CallbackQuery, state: FSMContext, session):
    """
    اعتماد فرصة وإرسالها لجميع المشتركين المعنيين
    """
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ غير مصرح", show_alert=True)
        return

    opp_id = int(callback.data.split(":")[1])
    state_data = await state.get_data()
    affiliate_url = state_data.get("affiliate_url")
    custom_message = state_data.get("custom_message")

    from db.crud import approve_opportunity as db_approve_opportunity
    opp = await db_approve_opportunity(session, opp_id, affiliate_url, custom_message)

    if not opp:
        await callback.answer("❌ الفرصة غير موجودة", show_alert=True)
        return

    # إرسال العرض لجميع المستخدمين الذين يراقبون هذا المنتج
    await send_deal_to_subscribers(callback.bot, session, opp)

    await state.clear()
    await callback.message.edit_text(
        f"✅ تم اعتماد وإرسال العرض!\n\n"
        f"📦 {opp.product.name or 'المنتج'}\n"
        f"خصم {opp.discount_percent:.1f}%",
        reply_markup=None
    )
    await callback.answer("✅ تم الإرسال!")


async def send_deal_to_subscribers(bot, session, opportunity):
    """
    إرسال العرض المعتمد لجميع المشتركين الذين يراقبون المنتج
    """
    from sqlalchemy import select
    from db.models import UserProduct, User, MonitoringStatus

    # جلب جميع المستخدمين الذين يراقبون هذا المنتج
    result = await session.execute(
        select(User)
        .join(UserProduct, UserProduct.user_id == User.id)
        .where(
            UserProduct.product_id == opportunity.product_id,
            UserProduct.status == MonitoringStatus.ACTIVE,
            User.muted == False,
            User.is_banned == False
        )
    )
    users = result.scalars().all()

    p = opportunity.product
    buy_url = opportunity.affiliate_url or p.url

    message_text = (
        f"🔥 *عرض قوي!*\n\n"
        f"📦 *{p.name or 'منتج'}*\n"
        f"💰 السعر السابق: {opportunity.old_price:.2f}\n"
        f"🔥 *السعر الحالي: {opportunity.new_price:.2f}*\n"
        f"📉 *خصم {opportunity.discount_percent:.1f}%*\n"
        f"📦 المخزون: {'متوفر ✅' if p.in_stock else 'غير متوفر ❌'}\n\n"
    )

    if opportunity.custom_message:
        message_text += f"💬 {opportunity.custom_message}\n\n"

    message_text += f"🛒 [اشترِ الآن]({buy_url})"

    sent_count = 0
    for user in users:
        try:
            await bot.send_message(
                user.telegram_id,
                message_text,
                parse_mode="Markdown"
            )
            sent_count += 1
        except Exception as e:
            logger.error(f"Failed to send deal to user {user.telegram_id}: {e}")

    logger.info(f"Deal sent to {sent_count}/{len(users)} users")


@router.callback_query(F.data.startswith("opp_reject:"))
async def reject_opportunity(callback: CallbackQuery, session):
    """رفض فرصة"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ غير مصرح", show_alert=True)
        return

    opp_id = int(callback.data.split(":")[1])

    from sqlalchemy import update
    from db.models import Opportunity, OpportunityStatus

    await session.execute(
        update(Opportunity)
        .where(Opportunity.id == opp_id)
        .values(status=OpportunityStatus.REJECTED)
    )
    await session.commit()

    await callback.message.edit_text("❌ تم تجاهل الفرصة.")
    await callback.answer("تم التجاهل")


# ======================================================
# 🏬 إدارة طلبات المتاجر
# ======================================================

@router.callback_query(F.data == "admin_store_requests")
async def admin_store_requests(callback: CallbackQuery, session):
    """عرض طلبات إضافة المتاجر"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ غير مصرح", show_alert=True)
        return

    from sqlalchemy import select
    from db.models import StoreRequest, StoreRequestStatus
    from sqlalchemy.orm import selectinload

    result = await session.execute(
        select(StoreRequest)
        .options(selectinload(StoreRequest.user))
        .where(StoreRequest.status == StoreRequestStatus.PENDING)
        .order_by(StoreRequest.created_at.desc())
        .limit(10)
    )
    requests = result.scalars().all()

    if not requests:
        from aiogram.utils.keyboard import InlineKeyboardBuilder
        builder = InlineKeyboardBuilder()
        builder.button(text="🔙 رجوع", callback_data="admin_panel")
        await callback.message.edit_text(
            "✅ لا توجد طلبات جديدة.",
            reply_markup=builder.as_markup()
        )
        await callback.answer()
        return

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()

    text = f"🏬 *طلبات المتاجر* ({len(requests)})\n\n"
    for req in requests:
        username = req.user.username or req.user.first_name or "مجهول"
        url_short = req.store_url[:40]
        builder.button(
            text=f"@{username}: {url_short}...",
            callback_data=f"admin_store_req:{req.id}"
        )

    builder.button(text="🔙 رجوع", callback_data="admin_panel")
    builder.adjust(1)

    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("store_req_approve:"))
async def approve_store_request(callback: CallbackQuery, session):
    """اعتماد طلب متجر"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ غير مصرح", show_alert=True)
        return

    req_id = int(callback.data.split(":")[1])

    from sqlalchemy import select, update
    from db.models import StoreRequest, StoreRequestStatus

    await session.execute(
        update(StoreRequest)
        .where(StoreRequest.id == req_id)
        .values(status=StoreRequestStatus.APPROVED)
    )
    await session.commit()

    # جلب الطلب لإشعار المستخدم
    result = await session.execute(
        select(StoreRequest).where(StoreRequest.id == req_id)
    )
    req = result.scalar_one_or_none()

    # إشعار المستخدم
    if req:
        from sqlalchemy import select as sel
        from db.models import User
        user_result = await session.execute(sel(User).where(User.id == req.user_id))
        user = user_result.scalar_one_or_none()
        if user:
            try:
                await callback.bot.send_message(
                    user.telegram_id,
                    f"✅ تم اعتماد طلبك!\n\nتم إضافة المتجر: {req.store_url}"
                )
            except Exception:
                pass

    await callback.message.edit_text("✅ تم اعتماد طلب المتجر وإشعار المستخدم.")
    await callback.answer("تم الاعتماد!")


@router.callback_query(F.data == "admin_users")
async def admin_users_list(callback: CallbackQuery, session):
    """عرض آخر المستخدمين المسجلين بشكل مختصر."""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ غير مصرح", show_alert=True)
        return

    from db.crud import get_all_users

    users = await get_all_users(session)
    if not users:
        await callback.message.edit_text("👥 لا يوجد مستخدمون مسجلون حالياً.")
        await callback.answer()
        return

    preview = users[:15]
    lines = [f"👥 *المستخدمون* ({len(users)})", ""]
    for idx, user in enumerate(preview, start=1):
        name = user.username or user.first_name or "مستخدم"
        plan = user.plan.value if hasattr(user.plan, "value") else str(user.plan)
        lines.append(f"{idx}. {name} — {plan}")

    if len(users) > len(preview):
        lines.append("")
        lines.append(f"... و{len(users) - len(preview)} مستخدم إضافي")

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 رجوع", callback_data="admin_panel")

    await callback.message.edit_text(
        "\n".join(lines),
        parse_mode="Markdown",
        reply_markup=builder.as_markup(),
    )
    await callback.answer()


# ======================================================
# 📢 إرسال إعلان لجميع المستخدمين (Broadcast)
# ======================================================

class BroadcastStates(StatesGroup):
    waiting_for_message = State()


class AdminReplyStates(StatesGroup):
    writing_reply = State()


@router.callback_query(F.data == "admin_broadcast")
async def start_broadcast(callback: CallbackQuery, state: FSMContext):
    """بدء إرسال إعلان جماعي"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ غير مصرح", show_alert=True)
        return

    await state.set_state(BroadcastStates.waiting_for_message)
    await callback.message.answer(
        "📢 أرسل الرسالة التي تريد إرسالها لجميع المستخدمين:\n\n"
        "⚠️ ستُرسل لجميع المشتركين النشطين!"
    )
    await callback.answer()


@router.message(BroadcastStates.waiting_for_message)
async def execute_broadcast(message: Message, state: FSMContext, session):
    """تنفيذ الإرسال الجماعي"""
    if not is_admin(message.from_user.id):
        return

    broadcast_text = message.text

    from db.crud import get_all_users
    users = await get_all_users(session)

    sent = 0
    failed = 0

    status_msg = await message.answer(f"⏳ جاري الإرسال لـ {len(users)} مستخدم...")

    for user in users:
        try:
            await message.bot.send_message(user.telegram_id, broadcast_text)
            sent += 1
        except Exception:
            failed += 1

    await state.clear()
    await status_msg.edit_text(
        f"✅ تم الإرسال!\n\n"
        f"✅ نجح: {sent}\n"
        f"❌ فشل: {failed}"
    )


# ======================================================
# 🎧 رد سريع على تذاكر الدعم
# ======================================================

@router.callback_query(F.data.startswith("quick_reply:"))
async def quick_reply_ticket(callback: CallbackQuery, state: FSMContext):
    """Start a quick reply flow for a support ticket from Telegram admin chat."""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ غير مصرح", show_alert=True)
        return

    ticket_id = int(callback.data.split(":", 1)[1])
    await state.update_data(reply_ticket_id=ticket_id)
    await state.set_state(AdminReplyStates.writing_reply)

    await callback.message.answer("✍️ اكتب ردك على المستخدم:")
    await callback.answer()


@router.message(AdminReplyStates.writing_reply)
async def send_admin_reply(message: Message, state: FSMContext, session):
    """Send an admin reply to the selected support ticket user."""
    if not is_admin(message.from_user.id):
        return

    from db.crud import add_ticket_message, get_admin_by_telegram_id, get_ticket_by_id
    from db.models import SupportSenderType
    from redis.asyncio import Redis
    from config.settings import REDIS_URL
    import json

    data = await state.get_data()
    ticket_id = data.get("reply_ticket_id")
    if not ticket_id:
        await state.clear()
        await message.answer("❌ لا توجد تذكرة محددة للرد")
        return

    ticket = await get_ticket_by_id(session, ticket_id)
    if not ticket:
        await state.clear()
        await message.answer("❌ التذكرة غير موجودة")
        return

    admin = await get_admin_by_telegram_id(session, message.from_user.id)
    admin_name = None
    if admin:
        admin_name = admin.name or admin.email or "الإدارة"
    if not admin_name:
        admin_name = message.from_user.full_name or "الإدارة"

    await add_ticket_message(
        session,
        ticket=ticket,
        sender_type=SupportSenderType.ADMIN,
        content=message.text,
        sender_admin_id=admin.id if admin else None,
        sender_name=admin_name,
    )

    try:
        await message.bot.send_message(
            ticket.user.telegram_id,
            f"💬 *رد من فريق الدعم*\n\n"
            f"{message.text}\n\n"
            f"— {admin_name}\n"
            f"رقم التذكرة: `{ticket.ticket_number}`",
            parse_mode="Markdown",
        )
    except Exception as exc:
        logger.warning("Failed to send admin support reply for ticket %s: %s", ticket.id, exc)

    redis = None
    try:
        redis = Redis.from_url(REDIS_URL)
        await redis.publish(
            "support:messages",
            json.dumps(
                {
                    "ticket_id": ticket.id,
                    "sender": "admin",
                    "sender_name": admin_name,
                    "content": message.text,
                    "timestamp": datetime.utcnow().isoformat(),
                },
                ensure_ascii=False,
            ),
        )
    except Exception:
        pass
    finally:
        if redis:
            await redis.close()

    await state.clear()
    await message.answer(
        f"✅ تم إرسال ردك لـ @{ticket.user.username or ticket.user.first_name or ticket.user.telegram_id}"
    )


# ======================================================
# ⬆️ ترقية / تنزيل خطة مستخدم
# ======================================================

VALID_PLANS = ("free", "basic", "professional")
PLAN_NAMES = {"free": "مجانية 🆓", "basic": "أساسية ⭐", "professional": "احترافية 💎"}


async def _change_user_plan(message: Message, session, target_plan: str):
    """Helper shared by /upgrade and /downgrade."""
    if not is_admin(message.from_user.id):
        return

    parts = message.text.strip().split()
    if len(parts) != 3:
        await message.answer(
            "❌ الصيغة غير صحيحة.\n\n"
            f"الاستخدام: `{parts[0]} <telegram_id> <plan>`\n"
            f"الخطط: free, basic, professional",
            parse_mode="Markdown",
        )
        return

    try:
        target_tid = int(parts[1])
    except ValueError:
        await message.answer("❌ معرف تيليغرام يجب أن يكون رقماً.")
        return

    plan = parts[2].lower()
    if plan not in VALID_PLANS:
        await message.answer(f"❌ خطة غير معروفة: {plan}\nالمتاح: free, basic, professional")
        return

    from db.crud import get_user_by_telegram_id, update_user_plan
    from db.models import PlanType

    user = await get_user_by_telegram_id(session, target_tid)
    if not user:
        await message.answer(f"❌ لا يوجد مستخدم بمعرف {target_tid}")
        return

    expires_at = datetime.utcnow() + timedelta(days=30) if plan != "free" else None
    await update_user_plan(session, user.id, PlanType(plan), expires_at)

    expiry_str = expires_at.strftime("%Y/%m/%d") if expires_at else "∞"
    username_display = f"@{user.username}" if user.username else user.first_name or str(target_tid)
    max_products = PLAN_LIMITS[plan]["max_products"]

    await message.answer(
        f"✅ تم ترقية {username_display} إلى خطة {PLAN_NAMES[plan]} حتى {expiry_str}"
    )

    # إشعار المستخدم
    try:
        await message.bot.send_message(
            target_tid,
            f"🎉 تم تفعيل اشتراكك!\n\n"
            f"📋 الخطة: {PLAN_NAMES[plan]}\n"
            f"📅 فعّالة حتى: {expiry_str}\n"
            f"📦 الحد الأقصى: {max_products} منتج\n\n"
            f"شكراً لاشتراكك! 🙏",
        )
    except Exception as e:
        logger.warning("Failed to notify user %s about plan change: %s", target_tid, e)


@router.message(Command("upgrade"))
async def cmd_upgrade(message: Message, session):
    """/upgrade <telegram_id> <plan>"""
    await _change_user_plan(message, session, "upgrade")


@router.message(Command("downgrade"))
async def cmd_downgrade(message: Message, session):
    """/downgrade <telegram_id> <plan>"""
    await _change_user_plan(message, session, "downgrade")


# ======================================================
# ℹ️ معلومات مستخدم
# ======================================================

@router.message(Command("userinfo"))
async def cmd_userinfo(message: Message, session):
    """/userinfo <telegram_id>"""
    if not is_admin(message.from_user.id):
        return

    parts = message.text.strip().split()
    if len(parts) != 2:
        await message.answer("❌ الاستخدام: `/userinfo <telegram_id>`", parse_mode="Markdown")
        return

    try:
        target_tid = int(parts[1])
    except ValueError:
        await message.answer("❌ معرف تيليغرام يجب أن يكون رقماً.")
        return

    from db.crud import get_user_by_telegram_id, count_user_products

    user = await get_user_by_telegram_id(session, target_tid)
    if not user:
        await message.answer(f"❌ لا يوجد مستخدم بمعرف {target_tid}")
        return

    products_count = await count_user_products(session, user.id)
    plan_name = PLAN_NAMES.get(user.plan.value if hasattr(user.plan, 'value') else user.plan, user.plan)
    expiry = user.plan_expires_at.strftime("%Y/%m/%d") if user.plan_expires_at else "—"
    status_icon = "🚫" if user.is_banned else ("🔕" if user.muted else "✅")

    text = (
        f"ℹ️ *معلومات المستخدم*\n\n"
        f"👤 الاسم: {user.first_name or '—'} {user.last_name or ''}\n"
        f"🔗 المعرف: @{user.username or '—'}\n"
        f"🆔 Telegram ID: `{user.telegram_id}`\n"
        f"📋 الخطة: {plan_name}\n"
        f"📅 انتهاء الخطة: {expiry}\n"
        f"📦 المنتجات: {products_count}/{PLAN_LIMITS.get(user.plan.value if hasattr(user.plan, 'value') else user.plan, {}).get('max_products', '?')}\n"
        f"🔔 الحالة: {status_icon}\n"
        f"📆 تاريخ التسجيل: {user.created_at.strftime('%Y/%m/%d') if user.created_at else '—'}"
    )

    await message.answer(text, parse_mode="Markdown")
