"""
نماذج قاعدة البيانات (Database Models)
========================================
هنا تعريف جميع جداول قاعدة البيانات باستخدام SQLAlchemy
كل class = جدول في PostgreSQL
"""

import enum
from datetime import datetime, timezone
from sqlalchemy import (
    Column, Integer, BigInteger, String, Float, Boolean,
    DateTime, Text, Enum, ForeignKey, JSON, Index, create_engine
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

# Base class لجميع النماذج
Base = declarative_base()


def utcnow() -> datetime:
    """Return an aware UTC timestamp for timezone-safe defaults."""
    return datetime.now(timezone.utc)


# ======================================================
# 📋 Enums - تعريف القيم الثابتة للحقول
# ======================================================

class PlanType(str, enum.Enum):
    """أنواع خطط الاشتراك"""
    FREE = "free"
    BASIC = "basic"
    PROFESSIONAL = "professional"


class AlertType(str, enum.Enum):
    """أنواع التنبيهات المتاحة"""
    PRICE_DROP = "price_drop"           # انخفاض السعر
    ANY_PRICE_CHANGE = "any_price_change"  # أي تغير في السعر
    BACK_IN_STOCK = "back_in_stock"     # عودة للمخزون
    OUT_OF_STOCK = "out_of_stock"       # نفاد المخزون
    BIG_DISCOUNT = "big_discount"       # خصم كبير فقط
    TARGET_PRICE = "target_price"       # وصول لسعر محدد


class MonitoringStatus(str, enum.Enum):
    """حالة مراقبة المنتج"""
    ACTIVE = "active"       # نشطة
    PAUSED = "paused"       # موقوفة مؤقتاً
    DELETED = "deleted"     # محذوفة


class OpportunityStatus(str, enum.Enum):
    """حالة الفرصة في لوحة الإدارة"""
    NEW = "new"             # جديدة - لم تُراجع
    APPROVED = "approved"   # معتمدة وأُرسلت
    REJECTED = "rejected"   # مرفوضة
    POSTPONED = "postponed" # مؤجلة


class StoreRequestStatus(str, enum.Enum):
    """حالة طلب إضافة متجر"""
    PENDING = "pending"       # قيد المراجعة
    APPROVED = "approved"     # معتمد
    REJECTED = "rejected"     # مرفوض
    IN_REVIEW = "in_review"   # تحت المراجعة


class SupportTicketStatus(str, enum.Enum):
    """Support ticket lifecycle state."""
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    WAITING_USER = "waiting_user"
    RESOLVED = "resolved"
    CLOSED = "closed"


class SupportTicketPriority(str, enum.Enum):
    """Support ticket priority level."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class SupportDepartment(str, enum.Enum):
    """Departments that handle support requests."""
    SUPPORT = "support"
    BILLING = "billing"
    TECHNICAL = "technical"
    GENERAL = "general"
    MANAGEMENT = "management"


class SupportSenderType(str, enum.Enum):
    """Origin of a support message."""
    USER = "user"
    ADMIN = "admin"
    SYSTEM = "system"
    BOT = "bot"


class SupportMessageType(str, enum.Enum):
    """Support message content type."""
    TEXT = "text"
    IMAGE = "image"
    FILE = "file"
    VOICE = "voice"
    SYSTEM = "system"


class SettingValueType(str, enum.Enum):
    """Supported storage types for dynamic bot settings."""
    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    JSON = "json"


class BotMenuButtonActionType(str, enum.Enum):
    """Types of actions when a menu button is pressed"""
    MENU = "menu"              # Go to sub-menu
    MESSAGE = "message"        # Send a text message
    URL = "url"                # Open a URL
    COMMAND = "command"        # Run a bot command
    HANDLER = "handler"        # Call existing handler function
    SUPPORT = "support"        # Open support ticket
    SUBSCRIBE = "subscribe"    # Open subscription page


class BotMenuButtonType(str, enum.Enum):
    """Button rendering type"""
    REPLY = "reply"            # Reply keyboard button at bottom
    INLINE = "inline"          # Inline button under message


class BotMenuVisibility(str, enum.Enum):
    """Who can see this button"""
    ALL = "all"                # All users
    FREE = "free"              # Free plan only
    BASIC = "basic"            # Basic plan only
    PROFESSIONAL = "professional"  # Professional plan only
    ADMIN = "admin"            # Admin only


class TelegramGroupPurpose(str, enum.Enum):
    """Configured purpose for a Telegram group/channel."""
    ADMIN_ALERTS = "admin_alerts"
    SUPPORT_TEAM = "support_team"
    DEALS = "deals"
    ANNOUNCEMENTS = "announcements"
    DEVELOPERS = "developers"
    ACCOUNTING = "accounting"
    CUSTOM = "custom"


# ======================================================
# 👤 جدول المستخدمين
# ======================================================

class User(Base):
    """
    جدول المستخدمين
    يخزن جميع معلومات مستخدمي البوت
    """
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # معرف تيليغرام الفريد للمستخدم
    telegram_id = Column(BigInteger, unique=True, nullable=False, index=True)

    # اسم المستخدم في تيليغرام (بدون @)
    username = Column(String(100), nullable=True)

    # الاسم الأول والأخير
    first_name = Column(String(100), nullable=True)
    last_name = Column(String(100), nullable=True)

    # خطة الاشتراك الحالية
    plan = Column(Enum(PlanType), default=PlanType.FREE, nullable=False)

    # تاريخ انتهاء الاشتراك (null = مجاني أو لا ينتهي)
    plan_expires_at = Column(DateTime, nullable=True)

    # اللغة المفضلة
    language = Column(String(10), default="ar")

    # العملة المفضلة للعرض
    currency = Column(String(10), default="SAR")

    # كتم التنبيهات (True = لا ترسل إشعارات)
    muted = Column(Boolean, default=False)

    # حالة الحساب
    is_active = Column(Boolean, default=True)
    is_banned = Column(Boolean, default=False)
    is_onboarded = Column(Boolean, default=False, nullable=False)

    # تاريخ التسجيل
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # العلاقات مع الجداول الأخرى
    monitored_products = relationship("UserProduct", back_populates="user")
    monitored_categories = relationship("UserCategory", back_populates="user")
    monitored_stores = relationship("UserStore", back_populates="user")
    store_requests = relationship("StoreRequest", back_populates="user")
    activities = relationship("UserActivity", back_populates="user")
    sessions = relationship("UserSession", back_populates="user")
    stats = relationship("UserStats", back_populates="user", uselist=False)
    tickets = relationship("SupportTicket", back_populates="user")


# ======================================================
# 🏪 جدول المتاجر المدعومة
# ======================================================

class Store(Base):
    """
    جدول المتاجر المدعومة في النظام
    كل متجر له موصل (connector) مستقل للسكرابينج
    """
    __tablename__ = "stores"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # اسم المتجر
    name = Column(String(200), nullable=False)

    # الرابط الأساسي للمتجر
    base_url = Column(String(500), nullable=False, unique=True)

    # نوع الموصل المستخدم (amazon, shopify, woocommerce, custom)
    connector_type = Column(String(50), nullable=False)

    # هل المتجر مفعل ويعمل؟
    is_active = Column(Boolean, default=True)

    # نسبة نجاح السكرابينج (0-100)
    success_rate = Column(Float, default=100.0)

    # آخر خطأ حدث
    last_error = Column(Text, nullable=True)

    # آخر وقت تحديث
    last_checked = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    # العلاقة بالمنتجات
    products = relationship("Product", back_populates="store")


# ======================================================
# 📦 جدول المنتجات
# ======================================================

class Product(Base):
    """
    جدول المنتجات
    يخزن معلومات كل منتج يتم مراقبته في النظام
    """
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # رابط المنتج الأصلي
    url = Column(Text, nullable=False, unique=True, index=True)

    # معرف المتجر
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=True)

    # اسم المنتج
    name = Column(String(500), nullable=True)

    # السعر الحالي
    current_price = Column(Float, nullable=True)

    # العملة
    currency = Column(String(10), default="USD")

    # السعر الأصلي قبل الخصم (إن وجد)
    original_price = Column(Float, nullable=True)

    # حالة المخزون (True = متوفر)
    in_stock = Column(Boolean, nullable=True)

    # رابط الصورة
    image_url = Column(Text, nullable=True)

    # تقييم المنتج
    rating = Column(Float, nullable=True)

    # عدد المراجعات
    review_count = Column(Integer, nullable=True)

    # أقل سعر تاريخي
    lowest_price = Column(Float, nullable=True)

    # أعلى سعر تاريخي
    highest_price = Column(Float, nullable=True)

    # آخر وقت تحديث البيانات
    last_scraped = Column(DateTime, nullable=True)

    # بيانات إضافية (JSON مرن)
    extra_data = Column(JSON, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    # العلاقات
    store = relationship("Store", back_populates="products")
    user_products = relationship("UserProduct", back_populates="product")
    price_history = relationship("PriceHistory", back_populates="product")
    stock_history = relationship("StockHistory", back_populates="product")
    opportunities = relationship("Opportunity", back_populates="product")


# ======================================================
# 🔗 جدول ربط المستخدم بالمنتجات (many-to-many)
# ======================================================

class UserProduct(Base):
    """
    جدول ربط المستخدمين بالمنتجات التي يراقبونها
    كل مستخدم يمكنه مراقبة منتجات متعددة بإعدادات مختلفة
    """
    __tablename__ = "user_products"

    id = Column(Integer, primary_key=True, autoincrement=True)

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)

    # حالة المراقبة
    status = Column(Enum(MonitoringStatus), default=MonitoringStatus.ACTIVE)

    # أنواع التنبيهات المفعلة (مخزنة كـ JSON array)
    alert_types = Column(JSON, default=list)

    # السعر المستهدف (لنوع تنبيه target_price)
    target_price = Column(Float, nullable=True)

    # آخر إشعار تم إرساله
    last_notified_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    # العلاقات
    user = relationship("User", back_populates="monitored_products")
    product = relationship("Product", back_populates="user_products")


# ======================================================
# 📂 جدول الفئات المراقبة
# ======================================================

class UserCategory(Base):
    """
    فئات يراقبها المستخدمون
    مثل: قسم الهواتف في أمازون
    """
    __tablename__ = "user_categories"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # رابط الفئة
    url = Column(Text, nullable=False)

    # اسم الفئة
    name = Column(String(300), nullable=True)

    # إعدادات التنبيه
    alert_types = Column(JSON, default=list)
    status = Column(Enum(MonitoringStatus), default=MonitoringStatus.ACTIVE)

    last_checked = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="monitored_categories")


# ======================================================
# 🏬 جدول المتاجر التي يراقبها المستخدمون
# ======================================================

class UserStore(Base):
    """
    متاجر كاملة يراقبها المستخدمون
    """
    __tablename__ = "user_stores"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=False)

    alert_types = Column(JSON, default=list)
    status = Column(Enum(MonitoringStatus), default=MonitoringStatus.ACTIVE)

    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="monitored_stores")


# ======================================================
# 📈 سجل تاريخ الأسعار
# ======================================================

class PriceHistory(Base):
    """
    يخزن جميع تغيرات الأسعار لكل منتج
    يُستخدم لرسم الرسم البياني وحساب أقل/أعلى سعر
    """
    __tablename__ = "price_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False, index=True)

    # السعر في هذه اللحظة
    price = Column(Float, nullable=False)
    currency = Column(String(10), default="USD")

    # وقت التسجيل
    recorded_at = Column(DateTime, default=datetime.utcnow)

    product = relationship("Product", back_populates="price_history")


# ======================================================
# 📦 سجل تاريخ المخزون
# ======================================================

class StockHistory(Base):
    """
    يخزن جميع تغيرات حالة المخزون لكل منتج
    """
    __tablename__ = "stock_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False, index=True)

    # حالة المخزون في هذه اللحظة
    in_stock = Column(Boolean, nullable=False)
    recorded_at = Column(DateTime, default=datetime.utcnow)

    product = relationship("Product", back_populates="stock_history")


# ======================================================
# 💡 جدول الفرص (للإدارة)
# ======================================================

class Opportunity(Base):
    """
    الفرص التي اكتشفها النظام تلقائياً
    تُعرض على الإدارة لمراجعتها وإضافة رابط أفلييت
    """
    __tablename__ = "opportunities"

    id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)

    # السعر قبل وبعد التغير
    old_price = Column(Float, nullable=False)
    new_price = Column(Float, nullable=False)

    # نسبة الخصم المحسوبة
    discount_percent = Column(Float, nullable=False)

    # حالة المخزون
    in_stock = Column(Boolean, default=True)

    # نقاط تقييم الفرصة (0-100)
    score = Column(Float, default=0)

    # حالة الفرصة
    status = Column(Enum(OpportunityStatus), default=OpportunityStatus.NEW)

    # رابط الأفلييت (يضيفه المدير يدوياً)
    affiliate_url = Column(Text, nullable=True)

    # نص العرض المعدّل من الإدارة
    custom_message = Column(Text, nullable=True)

    # وقت اكتشاف الفرصة
    discovered_at = Column(DateTime, default=datetime.utcnow)

    # وقت الإرسال للمشتركين
    published_at = Column(DateTime, nullable=True)

    product = relationship("Product", back_populates="opportunities")


# ======================================================
# 📨 جدول طلبات إضافة متاجر
# ======================================================

class StoreRequest(Base):
    """
    طلبات المستخدمين لإضافة متاجر جديدة
    تُراجع من الإدارة وتُعتمد أو تُرفض
    """
    __tablename__ = "store_requests"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # رابط المتجر المطلوب
    store_url = Column(Text, nullable=False)

    # حالة الطلب
    status = Column(Enum(StoreRequestStatus), default=StoreRequestStatus.PENDING)

    # ملاحظات الإدارة
    admin_notes = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="store_requests")


# ======================================================
# 🔔 جدول إشعارات الإدارة
# ======================================================

class AdminNotification(Base):
    """Notifications consumed by the admin dashboard bell."""
    __tablename__ = "admin_notifications"

    id = Column(Integer, primary_key=True, autoincrement=True)
    type = Column(String(50), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    message = Column(Text, nullable=False)
    icon = Column(String(10), default="🔔")
    color = Column(String(20), default="blue")
    read = Column(Boolean, default=False, index=True)
    action_url = Column(String(200), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, index=True)


# ======================================================
# 👮 جدول مدراء لوحة التحكم
# ======================================================

class AdminUser(Base):
    """Admin identity used for dashboard authentication."""
    __tablename__ = "admin_users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), nullable=True)
    email = Column(String(255), unique=True, nullable=True, index=True)
    phone = Column(String(30), unique=True, nullable=True, index=True)
    telegram_id = Column(BigInteger, unique=True, nullable=True, index=True)
    password_hash = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    failed_attempts = Column(Integer, default=0, nullable=False)
    locked_until = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    assigned_tickets = relationship("SupportTicket", back_populates="assignee", foreign_keys="SupportTicket.assigned_to")
    support_messages = relationship("SupportMessage", back_populates="sender_admin", foreign_keys="SupportMessage.sender_admin_id")
    team_member = relationship("TeamMember", back_populates="admin", uselist=False)


# ======================================================
# � جدول سجل التدقيق (Audit Log)
# ======================================================

class AuditLog(Base):
    """
    Audit trail for admin actions (approvals, rejections, broadcasts, logins).
    """
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    admin_telegram_id = Column(BigInteger, nullable=False, index=True)
    action = Column(String(100), nullable=False, index=True)
    target_type = Column(String(50), nullable=True)
    target_id = Column(Integer, nullable=True)
    details = Column(JSON, nullable=True)
    ip_address = Column(String(45), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


# ======================================================
# 📈 جدول نشاط المستخدمين التفصيلي
# ======================================================

class UserActivity(Base):
    """
    Every single user action tracked here.
    Inserted automatically by middleware.
    """
    __tablename__ = "user_activities"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    action = Column(String(100), nullable=False, index=True)
    details = Column(JSON, nullable=True)
    session_id = Column(String(50), nullable=True)
    ip_address = Column(String(45), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, index=True)

    user = relationship("User", back_populates="activities")

    __table_args__ = (
        Index("ix_user_activities_user_created", "user_id", "created_at"),
        Index("ix_user_activities_action_created", "action", "created_at"),
    )


# ======================================================
# 🕒 جدول جلسات المستخدمين
# ======================================================

class UserSession(Base):
    """Tracks user conversation sessions in Telegram."""
    __tablename__ = "user_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    session_id = Column(String(50), unique=True, nullable=False)
    started_at = Column(DateTime(timezone=True), default=utcnow)
    last_active = Column(DateTime(timezone=True), default=utcnow)
    ended_at = Column(DateTime, nullable=True)
    actions_count = Column(Integer, default=0)

    user = relationship("User", back_populates="sessions")


# ======================================================
# 🎧 نظام الدعم الفني
# ======================================================

class SupportTicket(Base):
    """Support conversation initiated by a Telegram user."""
    __tablename__ = "support_tickets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticket_number = Column(String(20), unique=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    subject = Column(String(300), nullable=True)
    status = Column(Enum(SupportTicketStatus), default=SupportTicketStatus.OPEN, nullable=False, index=True)
    priority = Column(Enum(SupportTicketPriority), default=SupportTicketPriority.NORMAL, nullable=False)
    department = Column(Enum(SupportDepartment), default=SupportDepartment.GENERAL, nullable=False)
    assigned_to = Column(Integer, ForeignKey("admin_users.id"), nullable=True)
    messages_count = Column(Integer, default=0, nullable=False)
    last_message_at = Column(DateTime(timezone=True), nullable=True)
    first_response_at = Column(DateTime(timezone=True), nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False, index=True)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    user = relationship("User", back_populates="tickets")
    messages = relationship("SupportMessage", back_populates="ticket", order_by="SupportMessage.created_at")
    assignee = relationship("AdminUser", back_populates="assigned_tickets", foreign_keys=[assigned_to])

    __table_args__ = (
        Index("ix_support_tickets_user_status_created", "user_id", "status", "created_at"),
    )


class SupportMessage(Base):
    """Individual message within a support ticket."""
    __tablename__ = "support_messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticket_id = Column(Integer, ForeignKey("support_tickets.id"), nullable=False, index=True)
    sender_type = Column(Enum(SupportSenderType), nullable=False)
    sender_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    sender_admin_id = Column(Integer, ForeignKey("admin_users.id"), nullable=True)
    sender_name = Column(String(200), nullable=True)
    message_type = Column(Enum(SupportMessageType), default=SupportMessageType.TEXT, nullable=False)
    content = Column(Text, nullable=False)
    telegram_message_id = Column(Integer, nullable=True)
    read_by_admin = Column(Boolean, default=False, nullable=False)
    read_by_user = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False, index=True)

    ticket = relationship("SupportTicket", back_populates="messages")
    sender_user = relationship("User", foreign_keys=[sender_user_id])
    sender_admin = relationship("AdminUser", back_populates="support_messages", foreign_keys=[sender_admin_id])

    __table_args__ = (
        Index("ix_support_messages_ticket_created", "ticket_id", "created_at"),
    )


class TeamMember(Base):
    """Team members available for support ticket assignment."""
    __tablename__ = "team_members"

    id = Column(Integer, primary_key=True, autoincrement=True)
    admin_id = Column(Integer, ForeignKey("admin_users.id"), unique=True, nullable=True)
    display_name = Column(String(200), nullable=False)
    avatar_color = Column(String(7), default="#2563EB", nullable=False)
    role = Column(String(100), nullable=True)
    department = Column(Enum(SupportDepartment), default=SupportDepartment.SUPPORT, nullable=False)
    is_available = Column(Boolean, default=True, nullable=False)
    is_online = Column(Boolean, default=False, nullable=False)
    last_seen = Column(DateTime(timezone=True), nullable=True)
    tickets_handled = Column(Integer, default=0, nullable=False)
    avg_response_time = Column(Integer, default=0, nullable=False)

    admin = relationship("AdminUser", back_populates="team_member")


class BotSetting(Base):
    """Key-value storage for mutable runtime settings."""
    __tablename__ = "bot_settings"

    key = Column(String(100), primary_key=True)
    value = Column(Text, nullable=False)
    value_type = Column(Enum(SettingValueType), default=SettingValueType.STRING, nullable=False)
    category = Column(String(50), nullable=False, index=True)
    description = Column(Text, nullable=True)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    updated_by = Column(Integer, ForeignKey("admin_users.id"), nullable=True)


# ======================================================
# 🎛 جدول أزرار قائمة البوت المخصصة
# ======================================================

class BotMenuButton(Base):
    """
    Custom buttons for the bot main menu
    Admin controls these from the dashboard
    Allows creating/editing menu structure without code
    """
    __tablename__ = "bot_menu_buttons"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Button display
    label = Column(String(100), nullable=False)
    # Example: "🔥 العروض اليومية"

    emoji = Column(String(10), nullable=True)
    # Emoji stored separately for easy emoji picker

    # What happens when the button is pressed
    action_type = Column(
        Enum(BotMenuButtonActionType),
        nullable=False,
        default=BotMenuButtonActionType.MESSAGE
    )

    # Action payload (value depends on action_type)
    action_value = Column(Text, nullable=True)
    # menu → sub_menu_id
    # message → text to send
    # url → https://...
    # command → /start
    # handler → "add_product" | "my_products" etc
    # support → ticket type
    # subscribe → subscription page ref

    # Position in menu
    position = Column(Integer, default=0)
    row = Column(Integer, default=0)
    # row 0 = first row, row 1 = second row, etc

    col = Column(Integer, default=0)
    # col 0 = right, col 1 = left (RTL layout)

    # Visibility rules
    is_active = Column(Boolean, default=True, index=True)
    visible_for = Column(
        Enum(BotMenuVisibility),
        default=BotMenuVisibility.ALL
    )
    # Show button only for specific plan

    # Menu hierarchy (for sub-menus)
    parent_id = Column(
        Integer,
        ForeignKey("bot_menu_buttons.id"),
        nullable=True
    )
    # None = main menu button
    # Not None = sub-menu button

    menu_level = Column(Integer, default=0)
    # 0 = main menu
    # 1 = sub-menu level 1
    # 2 = sub-menu level 2

    # Rendering style
    button_type = Column(
        Enum(BotMenuButtonType),
        default=BotMenuButtonType.REPLY
    )
    # reply = keyboard button at bottom
    # inline = button under message

    created_at = Column(
        DateTime(timezone=True),
        default=utcnow,
        index=True
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow
    )

    # Self-referential relationship for hierarchy
    children = relationship(
        "BotMenuButton",
        backref="parent",
        remote_side=[id],
        foreign_keys=[parent_id]
    )

    # Indexes for common queries
    __table_args__ = (
        Index("ix_bot_menu_active_row_col", "is_active", "row", "col"),
        Index("ix_bot_menu_parent", "parent_id", "is_active"),
    )


class TelegramGroup(Base):
    """Saved Telegram groups/channels used by dashboard workflows."""
    __tablename__ = "telegram_groups"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), nullable=False)
    chat_id = Column(BigInteger, nullable=False, unique=True, index=True)
    purpose = Column(Enum(TelegramGroupPurpose), default=TelegramGroupPurpose.CUSTOM, nullable=False)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    __table_args__ = (
        Index("ix_telegram_groups_purpose_active", "purpose", "is_active"),
    )


class TelegramBot(Base):
    """Saved Telegram bot assets configured from the admin dashboard."""
    __tablename__ = "telegram_bots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), nullable=False)
    username = Column(String(100), nullable=True, unique=True, index=True)
    token = Column(String(255), nullable=True)
    purpose = Column(String(50), nullable=False, default="custom")
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    __table_args__ = (
        Index("ix_telegram_bots_purpose_active", "purpose", "is_active"),
    )


# ======================================================
# 📊 جدول إحصائيات المستخدمين المجمعة
# ======================================================

class UserStats(Base):
    """Denormalized counters for fast dashboard queries."""
    __tablename__ = "user_stats"

    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    total_actions = Column(Integer, default=0)
    products_added = Column(Integer, default=0)
    products_deleted = Column(Integer, default=0)
    alerts_received = Column(Integer, default=0)
    deals_viewed = Column(Integer, default=0)
    deals_clicked = Column(Integer, default=0)
    store_requests_sent = Column(Integer, default=0)
    categories_added = Column(Integer, default=0)
    reports_viewed = Column(Integer, default=0)
    last_active = Column(DateTime, nullable=True)
    streak_days = Column(Integer, default=0)
    daily_activity = Column(JSON, default=list)

    user = relationship("User", back_populates="stats")


# ======================================================
# �🔧 إعداد الاتصال بقاعدة البيانات
# ======================================================

def get_engine(database_url: str):
    """
    إنشاء محرك قاعدة البيانات
    استبدل DATABASE_URL في ملف .env بعنوان قاعدة البيانات الخاصة بك
    """
    if database_url.startswith("sqlite:///"):
        # استخدام aiosqlite لـ SQLite
        return create_async_engine(database_url.replace("sqlite:///", "sqlite+aiosqlite:///"), echo=False)
    else:
        # تحويل URL من sync إلى async لـ PostgreSQL
        async_url = database_url.replace("postgresql://", "postgresql+asyncpg://")
        return create_async_engine(async_url, echo=False)


async def create_tables(engine):
    """
    إنشاء جميع الجداول في قاعدة البيانات
    استدعِ هذه الدالة عند تشغيل البوت لأول مرة
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


def get_session_factory(engine):
    """
    إنشاء مصنع للجلسات
    استخدم هذا في كل مكان تحتاج فيه للتعامل مع قاعدة البيانات
    """
    return sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
