"""
عمليات قاعدة البيانات (CRUD Operations)
==========================================
جميع الدوال للتعامل مع قاعدة البيانات
Create, Read, Update, Delete
"""

from datetime import datetime, timedelta, timezone
import json
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, func
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import selectinload
from redis.asyncio import Redis
import logging

from db.models import (
    User, Product, UserProduct, UserCategory, UserStore,
    Store, PriceHistory, StockHistory, Opportunity, StoreRequest,
    AdminNotification, AdminUser, SupportTicket, SupportMessage, TeamMember,
    PlanType, MonitoringStatus, OpportunityStatus,
    SupportTicketStatus, SupportTicketPriority, SupportDepartment,
    SupportSenderType, SupportMessageType
)
from config.settings import PLAN_LIMITS, REDIS_URL


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


async def create_admin_notification(
    session: AsyncSession,
    *,
    type: str,
    title: str,
    message: str,
    icon: str = "🔔",
    color: str = "blue",
    action_url: Optional[str] = None,
) -> Optional[AdminNotification]:
    """Persist an admin notification and publish it to Redis for real-time consumers."""
    notification = AdminNotification(
        type=type,
        title=title,
        message=message,
        icon=icon,
        color=color,
        read=False,
        action_url=action_url,
    )
    session.add(notification)
    try:
        await session.commit()
        await session.refresh(notification)
    except SQLAlchemyError:
        logging.getLogger(__name__).exception('Failed to commit admin notification')
        await session.rollback()
        return None

    payload = {
        "id": notification.id,
        "type": notification.type,
        "title": notification.title,
        "message": notification.message,
        "icon": notification.icon,
        "color": notification.color,
        "read": notification.read,
        "action_url": notification.action_url,
        "created_at": notification.created_at.isoformat() if notification.created_at else None,
    }

    redis = None
    try:
        redis = Redis.from_url(REDIS_URL)
        await redis.publish("admin:notifications", json.dumps(payload, ensure_ascii=False))
    except Exception:
        logging.getLogger(__name__).exception('Failed to publish admin notification to Redis')
        # Notification persistence should not fail if Redis is down.
        pass
    finally:
        if redis:
            await redis.close()

    return notification


# ======================================================
# 👤 عمليات المستخدمين
# ======================================================

async def get_or_create_user(session: AsyncSession, telegram_id: int,
                              username: str = None, first_name: str = None,
                              last_name: str = None) -> User:
    """
    الحصول على مستخدم موجود أو إنشاء مستخدم جديد
    يُستدعى عند كل تفاعل مع البوت
    """
    result = await session.execute(
        select(User).where(User.telegram_id == telegram_id)
    )
    user = result.scalar_one_or_none()
    is_new_user = False

    if not user:
        # إنشاء مستخدم جديد بالخطة المجانية
        user = User(
            telegram_id=telegram_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
            plan=PlanType.FREE
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        is_new_user = True

        display_name = username or first_name or str(telegram_id)
        await create_admin_notification(
            session,
            type="new_user",
            title="مستخدم جديد 👤",
            message=f"@{display_name} انضم للمنصة",
            icon="👤",
            color="green",
            action_url="/users",
        )

    setattr(user, "_is_new_user", is_new_user)
    return user


async def get_user_by_telegram_id(session: AsyncSession, telegram_id: int) -> Optional[User]:
    """الحصول على مستخدم بواسطة معرف تيليغرام"""
    result = await session.execute(
        select(User).where(User.telegram_id == telegram_id)
    )
    return result.scalar_one_or_none()


async def get_admin_by_telegram_id(session: AsyncSession, telegram_id: int) -> Optional[AdminUser]:
    """Fetch an admin identity using the linked Telegram account."""
    result = await session.execute(
        select(AdminUser).where(AdminUser.telegram_id == telegram_id)
    )
    return result.scalar_one_or_none()


async def generate_ticket_number(session: AsyncSession, created_at: datetime | None = None) -> str:
    """Generate a unique ticket number in the TKT-YYYY-NNNN format."""
    current = created_at or utcnow()
    year = current.year
    prefix = f"TKT-{year}-"

    result = await session.execute(
        select(SupportTicket.ticket_number)
        .where(SupportTicket.ticket_number.like(f"{prefix}%"))
        .order_by(SupportTicket.ticket_number.desc())
        .limit(1)
    )
    last_number = result.scalar_one_or_none()

    if not last_number:
        return f"{prefix}0001"

    try:
        sequence = int(last_number.rsplit("-", 1)[1]) + 1
    except (IndexError, ValueError):
        sequence = 1
    return f"{prefix}{sequence:04d}"


async def create_support_ticket(
    session: AsyncSession,
    *,
    user: User,
    content: str,
    subject: Optional[str] = None,
    department: SupportDepartment | str = SupportDepartment.GENERAL,
    message_type: SupportMessageType | str = SupportMessageType.TEXT,
    telegram_message_id: Optional[int] = None,
    sender_name: Optional[str] = None,
) -> SupportTicket:
    """Create a support ticket and its first message in one transaction."""
    created_at = utcnow()
    ticket = SupportTicket(
        ticket_number=await generate_ticket_number(session, created_at),
        user_id=user.id,
        subject=(subject or content or "رسالة دعم")[:300],
        department=department,
        status=SupportTicketStatus.OPEN,
        priority=SupportTicketPriority.NORMAL,
        messages_count=1,
        last_message_at=created_at,
        created_at=created_at,
        updated_at=created_at,
    )
    session.add(ticket)
    await session.flush()

    first_message = SupportMessage(
        ticket_id=ticket.id,
        sender_type=SupportSenderType.USER,
        sender_user_id=user.id,
        sender_name=sender_name or user.first_name or user.username,
        message_type=message_type,
        content=content,
        telegram_message_id=telegram_message_id,
        read_by_admin=False,
        read_by_user=True,
        created_at=created_at,
    )
    session.add(first_message)
    await session.commit()
    await session.refresh(ticket)
    return ticket


async def get_user_open_tickets(session: AsyncSession, user_id: int) -> List[SupportTicket]:
    """Return active tickets for a user, newest first."""
    result = await session.execute(
        select(SupportTicket)
        .where(
            SupportTicket.user_id == user_id,
            SupportTicket.status.in_([
                SupportTicketStatus.OPEN,
                SupportTicketStatus.IN_PROGRESS,
                SupportTicketStatus.WAITING_USER,
            ]),
        )
        .order_by(SupportTicket.updated_at.desc())
    )
    return result.scalars().all()


async def get_user_tickets(session: AsyncSession, user_id: int) -> List[SupportTicket]:
    """Return all tickets for a user with messages preloaded."""
    result = await session.execute(
        select(SupportTicket)
        .options(selectinload(SupportTicket.messages))
        .where(SupportTicket.user_id == user_id)
        .order_by(SupportTicket.updated_at.desc())
    )
    return result.scalars().all()


async def get_ticket_by_id(session: AsyncSession, ticket_id: int) -> Optional[SupportTicket]:
    """Fetch a ticket with its user, assignee, and messages."""
    result = await session.execute(
        select(SupportTicket)
        .options(
            selectinload(SupportTicket.user),
            selectinload(SupportTicket.assignee),
            selectinload(SupportTicket.messages),
        )
        .where(SupportTicket.id == ticket_id)
    )
    return result.scalar_one_or_none()


async def add_ticket_message(
    session: AsyncSession,
    *,
    ticket: SupportTicket,
    sender_type: SupportSenderType | str,
    content: str,
    message_type: SupportMessageType | str = SupportMessageType.TEXT,
    sender_user_id: Optional[int] = None,
    sender_admin_id: Optional[int] = None,
    sender_name: Optional[str] = None,
    telegram_message_id: Optional[int] = None,
) -> SupportMessage:
    """Append a message to an existing ticket and update counters/state."""
    timestamp = utcnow()
    message = SupportMessage(
        ticket_id=ticket.id,
        sender_type=sender_type,
        sender_user_id=sender_user_id,
        sender_admin_id=sender_admin_id,
        sender_name=sender_name,
        message_type=message_type,
        content=content,
        telegram_message_id=telegram_message_id,
        read_by_admin=sender_type in (SupportSenderType.ADMIN, SupportSenderType.SYSTEM, SupportSenderType.BOT),
        read_by_user=sender_type == SupportSenderType.USER,
        created_at=timestamp,
    )
    session.add(message)

    ticket.messages_count = (ticket.messages_count or 0) + 1
    ticket.last_message_at = timestamp
    ticket.updated_at = timestamp
    if sender_type == SupportSenderType.USER and ticket.status == SupportTicketStatus.WAITING_USER:
        ticket.status = SupportTicketStatus.IN_PROGRESS
    if sender_type == SupportSenderType.ADMIN:
        ticket.status = SupportTicketStatus.WAITING_USER
        if not ticket.first_response_at:
            ticket.first_response_at = timestamp

    await session.commit()
    await session.refresh(message)
    return message


async def list_support_tickets(
    session: AsyncSession,
    *,
    status: Optional[SupportTicketStatus | str] = None,
    department: Optional[SupportDepartment | str] = None,
    page: int = 1,
    per_page: int = 20,
) -> tuple[List[SupportTicket], int]:
    """Paginated support ticket listing for the dashboard."""
    filters = []
    if status and status != "all":
        filters.append(SupportTicket.status == status)
    if department and department != "all":
        filters.append(SupportTicket.department == department)

    base_query = select(SupportTicket).options(
        selectinload(SupportTicket.user),
        selectinload(SupportTicket.assignee),
        selectinload(SupportTicket.messages),
    )
    count_query = select(func.count(SupportTicket.id))

    if filters:
        base_query = base_query.where(*filters)
        count_query = count_query.where(*filters)

    total = (await session.execute(count_query)).scalar_one()
    result = await session.execute(
        base_query
        .order_by(SupportTicket.updated_at.desc(), SupportTicket.created_at.desc())
        .offset(max(page - 1, 0) * per_page)
        .limit(per_page)
    )
    return result.scalars().unique().all(), int(total)


async def get_support_team(session: AsyncSession) -> List[TeamMember]:
    """Return support team members with linked admin identities."""
    result = await session.execute(
        select(TeamMember)
        .options(selectinload(TeamMember.admin))
        .order_by(TeamMember.is_available.desc(), TeamMember.display_name.asc())
    )
    return result.scalars().all()


async def update_user_plan(session: AsyncSession, user_id: int,
                            plan: PlanType, expires_at: datetime = None):
    """تحديث خطة اشتراك المستخدم"""
    await session.execute(
        update(User)
        .where(User.id == user_id)
        .values(plan=plan, plan_expires_at=expires_at)
    )
    await session.commit()


async def get_all_users(session: AsyncSession) -> List[User]:
    """الحصول على جميع المستخدمين النشطين (للإدارة)"""
    result = await session.execute(
        select(User).where(User.is_active == True, User.is_banned == False)
    )
    return result.scalars().all()


# ======================================================
# 📦 عمليات المنتجات
# ======================================================

async def get_product_by_url(session: AsyncSession, url: str) -> Optional[Product]:
    """البحث عن منتج برابطه"""
    result = await session.execute(
        select(Product).where(Product.url == url)
    )
    return result.scalar_one_or_none()


async def create_product(session: AsyncSession, url: str, name: str = None,
                          price: float = None, currency: str = "USD",
                          in_stock: bool = None, image_url: str = None,
                          rating: float = None, review_count: int = None,
                          store_id: int = None) -> Product:
    """
    إنشاء منتج جديد في قاعدة البيانات
    يُستدعى بعد أول عملية سكرابينج للمنتج
    """
    product = Product(
        url=url,
        name=name,
        current_price=price,
        currency=currency,
        in_stock=in_stock,
        image_url=image_url,
        rating=rating,
        review_count=review_count,
        store_id=store_id,
        lowest_price=price,
        highest_price=price,
        last_scraped=datetime.utcnow()
    )
    session.add(product)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        # URL already exists — return the existing product
        return await get_product_by_url(session, url)
    await session.refresh(product)
    return product


async def update_product_data(session: AsyncSession, product_id: int,
                               price: float = None, in_stock: bool = None,
                               name: str = None) -> Product:
    """
    تحديث بيانات المنتج بعد كل عملية سكرابينج
    يحدّث أيضاً سجلات التاريخ وأعلى/أقل سعر
    """
    result = await session.execute(
        select(Product).where(Product.id == product_id)
    )
    product = result.scalar_one_or_none()
    if not product:
        return None

    # تحديث البيانات الأساسية
    if price is not None:
        # تسجيل السعر في سجل التاريخ
        price_record = PriceHistory(product_id=product_id, price=price)
        session.add(price_record)

        # تحديث أقل/أعلى سعر
        if product.lowest_price is None or price < product.lowest_price:
            product.lowest_price = price
        if product.highest_price is None or price > product.highest_price:
            product.highest_price = price

        product.current_price = price

    if in_stock is not None:
        # تسجيل تغير المخزون
        if product.in_stock != in_stock:
            stock_record = StockHistory(product_id=product_id, in_stock=in_stock)
            session.add(stock_record)
        product.in_stock = in_stock

    if name:
        product.name = name

    product.last_scraped = datetime.utcnow()

    await session.commit()
    await session.refresh(product)
    return product


# ======================================================
# 🔗 عمليات ربط المستخدم بالمنتجات
# ======================================================

async def add_product_to_user(session: AsyncSession, user_id: int,
                               product_id: int, alert_types: list = None) -> UserProduct:
    """
    إضافة منتج لقائمة مراقبة المستخدم
    يتحقق من حد الخطة قبل الإضافة
    """
    if alert_types is None:
        alert_types = ["price_drop"]  # تنبيه افتراضي

    # التحقق من عدم وجود ارتباط سابق
    result = await session.execute(
        select(UserProduct).where(
            UserProduct.user_id == user_id,
            UserProduct.product_id == product_id,
            UserProduct.status != MonitoringStatus.DELETED
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        return existing

    user_product = UserProduct(
        user_id=user_id,
        product_id=product_id,
        alert_types=alert_types,
        status=MonitoringStatus.ACTIVE
    )
    session.add(user_product)
    await session.commit()
    await session.refresh(user_product)
    return user_product


async def get_user_products(session: AsyncSession, user_id: int) -> List[UserProduct]:
    """
    الحصول على جميع منتجات المستخدم مع بيانات المنتج
    """
    result = await session.execute(
        select(UserProduct)
        .options(selectinload(UserProduct.product))
        .where(
            UserProduct.user_id == user_id,
            UserProduct.status != MonitoringStatus.DELETED
        )
    )
    return result.scalars().all()


async def count_user_products(session: AsyncSession, user_id: int) -> int:
    """عدّ المنتجات النشطة للمستخدم"""
    result = await session.execute(
        select(func.count(UserProduct.id)).where(
            UserProduct.user_id == user_id,
            UserProduct.status == MonitoringStatus.ACTIVE
        )
    )
    return result.scalar_one()


async def can_user_add_product(session: AsyncSession, user: User) -> bool:
    """
    التحقق هل يمكن للمستخدم إضافة منتج جديد
    بناءً على حدود خطته
    """
    plan_limit = PLAN_LIMITS[user.plan]["max_products"]
    current_count = await count_user_products(session, user.id)
    return current_count < plan_limit


async def toggle_monitoring(session: AsyncSession, user_product_id: int,
                             pause: bool) -> UserProduct:
    """
    إيقاف أو استئناف مراقبة منتج
    pause=True يوقف المراقبة، pause=False يستأنفها
    """
    new_status = MonitoringStatus.PAUSED if pause else MonitoringStatus.ACTIVE
    await session.execute(
        update(UserProduct)
        .where(UserProduct.id == user_product_id)
        .values(status=new_status)
    )
    await session.commit()


async def delete_user_product(session: AsyncSession, user_product_id: int):
    """حذف منتج من قائمة المراقبة"""
    await session.execute(
        update(UserProduct)
        .where(UserProduct.id == user_product_id)
        .values(status=MonitoringStatus.DELETED)
    )
    await session.commit()


# ======================================================
# 📂 عمليات الفئات
# ======================================================

async def add_category_to_user(session: AsyncSession, user_id: int,
                                url: str, name: str = None,
                                alert_types: list = None) -> UserCategory:
    """إضافة فئة للمراقبة"""
    if alert_types is None:
        alert_types = ["new_products", "discounts"]

    category = UserCategory(
        user_id=user_id,
        url=url,
        name=name,
        alert_types=alert_types
    )
    session.add(category)
    await session.commit()
    await session.refresh(category)
    return category


async def get_user_categories(session: AsyncSession, user_id: int) -> List[UserCategory]:
    """الحصول على جميع فئات المستخدم"""
    result = await session.execute(
        select(UserCategory).where(
            UserCategory.user_id == user_id,
            UserCategory.status != MonitoringStatus.DELETED
        )
    )
    return result.scalars().all()


# ======================================================
# 💡 عمليات الفرص
# ======================================================

async def create_opportunity(session: AsyncSession, product_id: int,
                              old_price: float, new_price: float,
                              score: float, in_stock: bool = True) -> Opportunity:
    """
    إنشاء فرصة جديدة عند اكتشاف خصم مهم
    يُستدعى تلقائياً من محرك المراقبة
    """
    discount = ((old_price - new_price) / old_price) * 100

    opportunity = Opportunity(
        product_id=product_id,
        old_price=old_price,
        new_price=new_price,
        discount_percent=round(discount, 1),
        score=score,
        in_stock=in_stock,
        status=OpportunityStatus.NEW
    )
    session.add(opportunity)
    await session.commit()
    await session.refresh(opportunity)
    return opportunity


async def get_new_opportunities(session: AsyncSession) -> List[Opportunity]:
    """الحصول على الفرص الجديدة غير المراجعة (للإدارة)"""
    result = await session.execute(
        select(Opportunity)
        .options(selectinload(Opportunity.product))
        .where(Opportunity.status == OpportunityStatus.NEW)
        .order_by(Opportunity.score.desc())
    )
    return result.scalars().all()


async def approve_opportunity(session: AsyncSession, opportunity_id: int,
                               affiliate_url: str = None,
                               custom_message: str = None) -> Opportunity:
    """اعتماد فرصة وإضافة رابط الأفلييت"""
    await session.execute(
        update(Opportunity)
        .where(Opportunity.id == opportunity_id)
        .values(
            status=OpportunityStatus.APPROVED,
            affiliate_url=affiliate_url,
            custom_message=custom_message,
            published_at=datetime.utcnow()
        )
    )
    await session.commit()

    result = await session.execute(
        select(Opportunity)
        .options(selectinload(Opportunity.product))
        .where(Opportunity.id == opportunity_id)
    )
    return result.scalar_one_or_none()


# ======================================================
# 📊 إحصائيات للداشبورد
# ======================================================

async def get_dashboard_stats(session: AsyncSession) -> dict:
    """
    إحصائيات عامة للوحة الإدارة
    تُستدعى لعرض الأرقام في الصفحة الرئيسية للداشبورد
    """
    # عدد المستخدمين
    users_count = await session.execute(
        select(func.count(User.id)).where(User.is_active == True)
    )

    # عدد المنتجات المراقبة
    products_count = await session.execute(
        select(func.count(UserProduct.id))
        .where(UserProduct.status == MonitoringStatus.ACTIVE)
    )

    # عدد الفرص الجديدة
    new_opportunities = await session.execute(
        select(func.count(Opportunity.id))
        .where(Opportunity.status == OpportunityStatus.NEW)
    )

    # عدد العروض المرسلة اليوم
    today = datetime.utcnow().replace(hour=0, minute=0, second=0)
    sent_today = await session.execute(
        select(func.count(Opportunity.id))
        .where(
            Opportunity.status == OpportunityStatus.APPROVED,
            Opportunity.published_at >= today
        )
    )

    return {
        "users_count": users_count.scalar_one(),
        "products_count": products_count.scalar_one(),
        "new_opportunities": new_opportunities.scalar_one(),
        "sent_today": sent_today.scalar_one(),
    }
