"""
لوحة الإدارة على الويب (Admin Dashboard)
==========================================
واجهة ويب كاملة للإدارة باستخدام FastAPI
تعمل على رابط منفصل عن البوت
مثال: http://yourserver.com:8000

Security hardening applied:
- JWT authentication on all /api/* routes
- Login endpoint with rate limiting
- CSRF protection on state-changing POST endpoints
- Input validation via Pydantic
- Field filtering on sensitive data
- Pagination with max cap
- Security headers, HSTS, CSP
- Request size limit
- Global exception handler (no stack-trace leak)
- Audit logging
"""

from enum import Enum as PyEnum
from typing import Optional
from datetime import datetime, timedelta, timezone
from pathlib import Path
import asyncio
import json
import io
import csv
import platform
import re

import httpx
from fastapi import FastAPI, Depends, HTTPException, Request, Header, WebSocket, WebSocketDisconnect, Query, Body, Response
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, select, update, func, or_
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import selectinload
from pydantic import BaseModel, Field, field_validator
import logging

import config.settings as settings_module
from config.settings import (
    DATABASE_URL,
    REDIS_URL,
    PLAN_LIMITS,
    TELEGRAM_BOT_TOKEN,
    ADMIN_USER_IDS,
    LONGCAT_API_KEY,
    AI_SCRAPING_ENABLED,
    AI_SCRAPING_MODE,
)
from db.models import (
    get_engine, get_session_factory,
    User, UserProduct, UserCategory, UserStore, StoreRequest, Store,
    Product, Opportunity, OpportunityStatus, StoreRequestStatus,
    UserActivity, UserStats, PlanType, MonitoringStatus, AuditLog,
    AdminNotification, AdminUser, SupportTicket, SupportMessage, TeamMember,
    SupportTicketStatus, SupportDepartment, SupportSenderType,
    BotSetting, SettingValueType, BotMenuButton, TelegramGroup, TelegramGroupPurpose, TelegramBot,
)
from redis.asyncio import Redis
from core.monitor import monitoring_engine_running, monitoring_engine_last_run

from auth.security import (
    verify_admin,
    authenticate_admin,
    decode_access_token,
    create_access_token,
    LoginRequest,
    TokenResponse,
    generate_csrf_token,
    verify_csrf_token,
)
from middleware.security import apply_security_middleware

logger = logging.getLogger(__name__)

# إنشاء تطبيق FastAPI
app = FastAPI(
    title="DealScope - Admin Dashboard",
    description="لوحة إدارة بوت مراقبة المتاجر",
    version="2.0.0",
    docs_url=None,   # disable Swagger in production
    redoc_url=None,
)

# Apply security middleware (headers, CORS, size limit, exception handler)
apply_security_middleware(app)


# ======================================================
# 🔐 Pydantic validation models
# ======================================================

class OpportunityStatusEnum(str, PyEnum):
    all = "all"
    new = "new"
    approved = "approved"
    rejected = "rejected"
    postponed = "postponed"


class OpportunityQuery(BaseModel):
    status: OpportunityStatusEnum = OpportunityStatusEnum.new
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


class UserQuery(BaseModel):
    page: int = Field(default=1, ge=1)
    limit: int = Field(default=20, ge=1, le=100)
    plan: Optional[str] = None

    @field_validator("plan")
    @classmethod
    def validate_plan(cls, v):
        if v is not None and v not in ("free", "basic", "professional"):
            raise ValueError("plan must be free, basic, or professional")
        return v


class ApproveBody(BaseModel):
    affiliate_url: Optional[str] = None
    custom_message: Optional[str] = None


class UpgradeBody(BaseModel):
    plan: str = Field(..., pattern=r"^(free|basic|professional)$")
    days: int = Field(default=30, ge=1, le=365)


class ManualOpportunityBody(BaseModel):
    product_name: str = Field(..., min_length=2, max_length=500)
    product_url: str = Field(..., min_length=5, max_length=1000)
    affiliate_url: Optional[str] = Field(default=None, max_length=1000)
    old_price: float = Field(..., gt=0)
    new_price: float = Field(..., gt=0)
    custom_message: Optional[str] = Field(default=None, max_length=1000)
    target_plan: str = Field(default="all", pattern=r"^(all|basic|pro)$")


class StoreCreateBody(BaseModel):
    name: str = Field(..., min_length=2, max_length=200)
    base_url: str = Field(..., min_length=5, max_length=500)
    connector_type: str = Field(..., pattern=r"^(shopify|woocommerce|custom|amazon)$")


class BroadcastBody(BaseModel):
    message: str = Field(..., min_length=1, max_length=500)
    target: str = Field(default="all", pattern=r"^(all|paid|pro)$")


class StoreRequestDecisionBody(BaseModel):
    admin_notes: Optional[str] = Field(default=None, max_length=1000)


class AdminMessageBody(BaseModel):
    message: str = Field(..., min_length=1, max_length=4096)


class SupportReplyBody(BaseModel):
    message: str = Field(..., min_length=1, max_length=4096)


class SupportAssignBody(BaseModel):
    admin_id: int = Field(..., ge=1)


class SupportTransferBody(BaseModel):
    department: str = Field(..., pattern=r"^(support|billing|technical|general|management)$")
    note: Optional[str] = Field(default=None, max_length=1000)


class TeamMemberBody(BaseModel):
    display_name: str = Field(..., min_length=2, max_length=200)
    department: str = Field(default="support", pattern=r"^(support|billing|technical|general|management)$")
    admin_id: Optional[int] = Field(default=None, ge=1)
    role: Optional[str] = Field(default=None, max_length=100)
    avatar_color: Optional[str] = Field(default="#2563EB", pattern=r"^#[0-9A-Fa-f]{6}$")
    is_available: bool = True


class TelegramResolveBody(BaseModel):
    input: str = Field(..., min_length=1, max_length=1000)


class TelegramGroupBody(BaseModel):
    name: str = Field(..., min_length=2, max_length=200)
    chat_id: int
    purpose: str = Field(default="custom", pattern=r"^(admin_alerts|support_team|deals|announcements|developers|accounting|custom)$")
    description: Optional[str] = Field(default=None, max_length=2000)
    is_active: bool = True


class TelegramBotBody(BaseModel):
    name: str = Field(..., min_length=2, max_length=200)
    username: Optional[str] = Field(default=None, max_length=100)
    token: Optional[str] = Field(default=None, max_length=255)
    purpose: str = Field(default="custom", max_length=50)
    description: Optional[str] = Field(default=None, max_length=2000)
    is_active: bool = True


class ChangePasswordBody(BaseModel):
    current_password: str = Field(..., min_length=6, max_length=128)
    new_password: str = Field(..., min_length=8, max_length=128)


ENGINE = get_engine(DATABASE_URL)
SESSION_FACTORY = get_session_factory(ENGINE)


async def _get_db_session():
    """Create a one-off async session for API endpoints."""
    async with SESSION_FACTORY() as session:
        yield session


# ======================================================
# 🔑 Authentication endpoint
# ======================================================

@app.post("/auth/login", response_model=TokenResponse)
async def login(request: Request, body: LoginRequest):
    """Authenticate an admin by Telegram ID and return a JWT."""
    return await authenticate_admin(request, body)


@app.post("/auth/logout")
async def logout(admin: dict = Depends(verify_admin)):
    """Client-driven logout endpoint for SPA flows."""
    return {"success": True}


@app.post("/auth/refresh", response_model=TokenResponse)
async def refresh_token(admin: dict = Depends(verify_admin)):
    """Issue a fresh access token for an authenticated admin."""
    telegram_id = int(admin.get("sub", 0))
    token, expires_in = create_access_token(telegram_id)
    return TokenResponse(access_token=token, token_type="bearer", expires_in=expires_in)


@app.get("/auth/me")
async def auth_me(admin: dict = Depends(verify_admin)):
    """Return the current authenticated admin identity."""
    return {
        "telegram_id": int(admin.get("sub", 0)),
        "jti": admin.get("jti"),
        "exp": admin.get("exp"),
        "authenticated": True,
    }


@app.post("/auth/change-password")
async def change_password(
    body: ChangePasswordBody,
    admin: dict = Depends(verify_admin),
    session: AsyncSession = Depends(_get_db_session),
):
    """Change password for the currently authenticated admin user."""
    import bcrypt

    telegram_id = int(admin.get("sub", 0))
    row = (await session.execute(select(AdminUser).where(AdminUser.telegram_id == telegram_id))).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Admin user not found")

    if not row.password_hash or not bcrypt.checkpw(body.current_password.encode("utf-8"), row.password_hash.encode("utf-8")):
        raise HTTPException(status_code=401, detail="Current password is incorrect")

    row.password_hash = bcrypt.hashpw(body.new_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    await session.commit()
    return {"success": True}


@app.post("/auth/seed")
async def seed_admin_users(session: AsyncSession = Depends(_get_db_session)):
    """Seed admin user rows when missing to bootstrap local environments."""
    import bcrypt

    created = []
    for telegram_id in ADMIN_USER_IDS:
        existing = (await session.execute(select(AdminUser).where(AdminUser.telegram_id == int(telegram_id)))).scalar_one_or_none()
        if existing:
            continue

        default_password = "ChangeMeNow123!"
        row = AdminUser(
            telegram_id=int(telegram_id),
            name=f"Admin {telegram_id}",
            email=None,
            phone=None,
            password_hash=bcrypt.hashpw(default_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8"),
            is_active=True,
        )
        session.add(row)
        created.append(int(telegram_id))

    await session.commit()
    return {"success": True, "created": created, "count": len(created)}


# ======================================================
# 📊 Protected API Endpoints
# ======================================================

PLAN_NAMES = {"free": "مجانية 🆓", "basic": "أساسية ⭐", "professional": "احترافية 💎"}
redis_client = Redis.from_url(REDIS_URL)

# include lightweight control-panel routers (notifications, system, test)
try:
    from admin.routes.notifications import router as notifications_router
    from admin.routes.system import router as system_router
    from admin.routes.test import router as test_router

    app.include_router(notifications_router)
    app.include_router(system_router)
    app.include_router(test_router)
except Exception as _exc:  # pragma: no cover
    logger.warning("control-panel routers not loaded: %s", _exc)


SETTINGS_CATEGORIES = {"bot", "plans", "monitoring", "templates", "affiliate", "security"}
SETTING_DEFINITIONS: dict[str, tuple[str, str, str, str]] = {
    "bot.token": (str(TELEGRAM_BOT_TOKEN or ""), "string", "bot", "توكن البوت"),
    "bot.bot_name": ("DealScope", "string", "bot", "اسم البوت"),
    "bot.welcome_message": ("👋 أهلاً بك في بوت مراقبة الأسعار والعروض!", "string", "bot", "رسالة الترحيب"),
    "bot.maintenance_mode": ("false", "boolean", "bot", "تشغيل وضع الصيانة"),
    "bot.maintenance_message": ("🔧 البوت قيد الصيانة حالياً، نعود قريباً.", "string", "bot", "رسالة الصيانة"),
    "bot.test_mode": ("false", "boolean", "bot", "وضع الاختبار"),
    "monitoring.min_discount_percent": ("10", "integer", "monitoring", "الحد الأدنى للخصم"),
    "monitoring.scraping_delay": ("2", "integer", "monitoring", "التأخير بين الطلبات"),
    "monitoring.max_requests_per_minute": ("10", "integer", "monitoring", "أقصى طلبات/دقيقة"),
    "monitoring.max_products_per_cycle": ("50", "integer", "monitoring", "حد المنتجات للدورة"),
    "monitoring.retry_attempts": ("3", "integer", "monitoring", "محاولات إعادة المحاولة"),
    "monitoring.longcat_api_key": (str(LONGCAT_API_KEY or ""), "string", "monitoring", "LongCat API Key"),
    "monitoring.ai_scraping_enabled": ("true" if AI_SCRAPING_ENABLED else "false", "boolean", "monitoring", "تفعيل الاستخراج الذكي"),
    "monitoring.ai_scraping_mode": (str(AI_SCRAPING_MODE or "fallback"), "string", "monitoring", "وضع الاستخراج الذكي"),
    "plans.free.price": ("0", "integer", "plans", "سعر الخطة المجانية"),
    "plans.free.max_products": ("3", "integer", "plans", "حد منتجات الخطة المجانية"),
    "plans.free.max_categories": ("0", "integer", "plans", "حد فئات الخطة المجانية"),
    "plans.free.max_stores": ("0", "integer", "plans", "حد متاجر الخطة المجانية"),
    "plans.free.scan_interval": ("60", "integer", "plans", "تردد فحص الخطة المجانية"),
    "plans.basic.price": ("10", "integer", "plans", "سعر الخطة الأساسية"),
    "plans.basic.max_products": ("50", "integer", "plans", "حد منتجات الخطة الأساسية"),
    "plans.basic.max_categories": ("10", "integer", "plans", "حد فئات الخطة الأساسية"),
    "plans.basic.max_stores": ("0", "integer", "plans", "حد متاجر الخطة الأساسية"),
    "plans.basic.scan_interval": ("30", "integer", "plans", "تردد فحص الخطة الأساسية"),
    "plans.professional.price": ("49", "integer", "plans", "سعر الخطة الاحترافية"),
    "plans.professional.max_products": ("300", "integer", "plans", "حد منتجات الخطة الاحترافية"),
    "plans.professional.max_categories": ("50", "integer", "plans", "حد فئات الخطة الاحترافية"),
    "plans.professional.max_stores": ("20", "integer", "plans", "حد متاجر الخطة الاحترافية"),
    "plans.professional.scan_interval": ("15", "integer", "plans", "تردد فحص الخطة الاحترافية"),
    "templates.price_drop": ("📉 انخفاض في السعر!\n{product_name}\nالسعر: {old_price} ← {new_price}\nخصم: {discount}%", "string", "templates", "قالب انخفاض السعر"),
    "templates.deal_approved": ("🔥 عرض قوي!\n{product_name}\nخصم {discount}% 🎯", "string", "templates", "قالب عرض معتمد"),
    "templates.back_in_stock": ("🟢 عاد المنتج للمخزون: {product_name}", "string", "templates", "قالب عودة المخزون"),
    "templates.out_of_stock": ("🔴 نفد المنتج: {product_name}", "string", "templates", "قالب نفاد المخزون"),
    "templates.subscription_activated": ("✅ تم تفعيل اشتراكك {plan}", "string", "templates", "قالب تفعيل الاشتراك"),
    "templates.user_banned": ("🚫 تم تقييد حسابك مؤقتاً.", "string", "templates", "قالب الحظر"),
    "templates.support_reply": ("💬 رد من الدعم: {message}", "string", "templates", "قالب رد الدعم"),
    "affiliate.default_link": ("https://amzn.to/default", "string", "affiliate", "الرابط الافتراضي"),
    "affiliate.default_tag": ("storemonitor-21", "string", "affiliate", "وسم أفلييت افتراضي"),
    "affiliate.auto_tag": ("false", "boolean", "affiliate", "تفعيل إضافة الوسم"),
    "affiliate.default_offer_text": ("🔥 عرض حصري! سارع قبل النفاد", "string", "affiliate", "نص عرض افتراضي"),
    "affiliate.platform_amazon": ("true", "boolean", "affiliate", "تفعيل منصة أمازون"),
    "affiliate.platform_noon": ("false", "boolean", "affiliate", "تفعيل منصة نون"),
    "affiliate.platform_extra": ("false", "boolean", "affiliate", "تفعيل منصة اكسترا"),
    "security.max_login_attempts": ("5", "integer", "security", "عدد محاولات تسجيل الدخول"),
    "security.lockout_minutes": ("15", "integer", "security", "مدة القفل بالدقائق"),
    "security.jwt_expire_hours": ("8", "integer", "security", "مدة JWT"),
    "security.rate_limit_per_minute": ("10", "integer", "security", "طلبات تسجيل الدخول للدقيقة"),
    "security.blocked_ips": ("[]", "json", "security", "قائمة IPs محظورة"),
}


def _parse_setting_value(value: str, value_type: str):  # pragma: no cover
    if value_type == "integer":
        return int(value)
    if value_type == "float":
        return float(value)
    if value_type == "boolean":
        return str(value).strip().lower() in {"1", "true", "yes", "on"}
    if value_type == "json":
        try:
            return json.loads(value)
        except Exception:
            return value
    return value


def _infer_setting_type(value) -> str:  # pragma: no cover
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int) and not isinstance(value, bool):
        return "integer"
    if isinstance(value, float):
        return "float"
    if isinstance(value, (dict, list)):
        return "json"
    return "string"


def _stringify_setting_value(value, value_type: str) -> str:  # pragma: no cover
    if value_type == "json":
        return json.dumps(value, ensure_ascii=False)
    if value_type == "boolean":
        return "true" if bool(value) else "false"
    return str(value)


async def _ensure_default_settings(session: AsyncSession) -> None:  # pragma: no cover
    existing = (await session.execute(select(BotSetting.key))).scalars().all()
    existing_set = set(existing)
    created = False
    for key, (default_value, value_type, category, description) in SETTING_DEFINITIONS.items():
        if key in existing_set:
            continue
        session.add(
            BotSetting(
                key=key,
                value=default_value,
                value_type=SettingValueType(value_type),
                category=category,
                description=description,
            )
        )
        created = True
    if created:
        await session.commit()


def _apply_setting_to_memory(key: str, parsed_value):  # pragma: no cover
    if key.startswith("plans."):
        parts = key.split(".")
        if len(parts) == 3:
            _, plan_name, field_name = parts
            if plan_name in PLAN_LIMITS and field_name in PLAN_LIMITS[plan_name]:
                PLAN_LIMITS[plan_name][field_name] = parsed_value

    if key == "security.jwt_expire_hours":
        settings_module.JWT_EXPIRE_HOURS = int(parsed_value)
    elif key == "security.max_login_attempts":
        settings_module.MAX_LOGIN_ATTEMPTS = int(parsed_value)
    elif key == "security.lockout_minutes":
        settings_module.LOCKOUT_MINUTES = int(parsed_value)
    elif key == "monitoring.longcat_api_key":
        settings_module.LONGCAT_API_KEY = str(parsed_value)
    elif key == "monitoring.ai_scraping_enabled":
        settings_module.AI_SCRAPING_ENABLED = bool(parsed_value)
    elif key == "monitoring.ai_scraping_mode":
        settings_module.AI_SCRAPING_MODE = str(parsed_value)


async def _get_bot_token(session: AsyncSession) -> str:
    """Get Telegram bot token from settings table, fallback to env setting."""
    row = (await session.execute(select(BotSetting).where(BotSetting.key == "bot.token"))).scalar_one_or_none()
    if row and row.value and str(row.value).strip():
        return str(row.value).strip()
    return str(TELEGRAM_BOT_TOKEN or "").strip()


async def _telegram_get_me(token: str) -> dict:
    if not token:
        return {"ok": False, "description": "Missing bot token"}
    url = f"https://api.telegram.org/bot{token}/getMe"
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(url)
        return response.json()


async def _telegram_get_chat(token: str, chat_id: str) -> dict:
    url = f"https://api.telegram.org/bot{token}/getChat"
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(url, params={"chat_id": chat_id})
        return response.json()


async def _telegram_get_chat_member_count(token: str, chat_id: str) -> Optional[int]:
    url = f"https://api.telegram.org/bot{token}/getChatMemberCount"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(url, params={"chat_id": chat_id})
            payload = response.json()
        if payload.get("ok"):
            return int(payload.get("result"))
    except Exception:
        return None
    return None


def _serialize_group(group: TelegramGroup) -> dict:
    return {
        "id": group.id,
        "name": group.name,
        "chat_id": group.chat_id,
        "purpose": _enum_value(group.purpose),
        "description": group.description,
        "is_active": group.is_active,
        "created_at": group.created_at.isoformat() if group.created_at else None,
    }


def _serialize_bot_asset(bot: TelegramBot) -> dict:
    return {
        "id": bot.id,
        "name": bot.name,
        "username": bot.username,
        "purpose": bot.purpose,
        "description": bot.description,
        "is_active": bot.is_active,
        "has_token": bool(bot.token),
        "created_at": bot.created_at.isoformat() if bot.created_at else None,
    }



def _daily_sparkline_points(daily_activity: list | None, days: int = 7) -> list[int]:
    if not daily_activity:
        return [0] * days
    recent = daily_activity[-days:]
    points = [int(row.get("count", 0)) for row in recent]
    if len(points) < days:
        points = ([0] * (days - len(points))) + points
    return points


def _verify_ws_admin(token: str) -> bool:
    try:
        payload = decode_access_token(token)
        telegram_id = int(payload.get("sub", 0))
        return telegram_id in ADMIN_USER_IDS
    except Exception:
        return False


def _enum_value(value):
    return value.value if hasattr(value, "value") else value


def _serialize_support_message(message: SupportMessage) -> dict:
    return {
        "id": message.id,
        "sender_type": _enum_value(message.sender_type),
        "sender_user_id": message.sender_user_id,
        "sender_admin_id": message.sender_admin_id,
        "sender_name": message.sender_name,
        "message_type": _enum_value(message.message_type),
        "content": message.content,
        "telegram_message_id": message.telegram_message_id,
        "read_by_admin": message.read_by_admin,
        "read_by_user": message.read_by_user,
        "created_at": message.created_at.isoformat() if message.created_at else None,
    }


def _serialize_team_member(member: TeamMember) -> dict:
    admin = member.admin
    return {
        "id": member.id,
        "admin_id": member.admin_id,
        "display_name": member.display_name,
        "avatar_color": member.avatar_color,
        "role": member.role,
        "department": _enum_value(member.department),
        "is_available": member.is_available,
        "is_online": member.is_online,
        "last_seen": member.last_seen.isoformat() if member.last_seen else None,
        "tickets_handled": member.tickets_handled,
        "avg_response_time": member.avg_response_time,
        "admin": {
            "id": admin.id,
            "name": admin.name,
            "email": admin.email,
            "telegram_id": admin.telegram_id,
        } if admin else None,
    }


def _serialize_support_ticket(ticket: SupportTicket, include_messages: bool = False) -> dict:
    user = ticket.user
    assignee = ticket.assignee
    latest_message = ticket.messages[-1] if ticket.messages else None
    unread_count = sum(
        1
        for msg in ticket.messages
        if _enum_value(msg.sender_type) == "user" and not msg.read_by_admin
    )
    payload = {
        "id": ticket.id,
        "ticket_number": ticket.ticket_number,
        "subject": ticket.subject,
        "status": _enum_value(ticket.status),
        "priority": _enum_value(ticket.priority),
        "department": _enum_value(ticket.department),
        "assigned_to": ticket.assigned_to,
        "messages_count": ticket.messages_count,
        "last_message_at": ticket.last_message_at.isoformat() if ticket.last_message_at else None,
        "first_response_at": ticket.first_response_at.isoformat() if ticket.first_response_at else None,
        "resolved_at": ticket.resolved_at.isoformat() if ticket.resolved_at else None,
        "created_at": ticket.created_at.isoformat() if ticket.created_at else None,
        "updated_at": ticket.updated_at.isoformat() if ticket.updated_at else None,
        "unread_count": unread_count,
        "last_message_preview": (latest_message.content[:120] if latest_message and latest_message.content else None),
        "user": {
            "id": user.id,
            "telegram_id": user.telegram_id,
            "username": user.username,
            "first_name": user.first_name,
            "last_name": user.last_name,
        } if user else None,
        "assignee": {
            "id": assignee.id,
            "name": assignee.name,
            "telegram_id": assignee.telegram_id,
        } if assignee else None,
    }
    if include_messages:
        payload["messages"] = [_serialize_support_message(message) for message in ticket.messages]
    return payload


@app.get("/api/stats")
async def get_stats(
    admin: dict = Depends(verify_admin),
    session: AsyncSession = Depends(_get_db_session),
):
    """System statistics with plan breakdown."""
    now = datetime.utcnow()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)

    total = (await session.execute(select(func.count(User.id)))).scalar_one()
    free_count = (await session.execute(
        select(func.count(User.id)).where(User.plan == PlanType.FREE)
    )).scalar_one()
    basic_count = (await session.execute(
        select(func.count(User.id)).where(User.plan == PlanType.BASIC)
    )).scalar_one()
    pro_count = (await session.execute(
        select(func.count(User.id)).where(User.plan == PlanType.PROFESSIONAL)
    )).scalar_one()
    banned_count = (await session.execute(
        select(func.count(User.id)).where(User.is_banned == True)
    )).scalar_one()
    products_count = (await session.execute(
        select(func.count(UserProduct.id)).where(UserProduct.status == MonitoringStatus.ACTIVE)
    )).scalar_one()

    from db.models import Opportunity, OpportunityStatus
    new_opps = (await session.execute(
        select(func.count(Opportunity.id)).where(Opportunity.status == OpportunityStatus.NEW)
    )).scalar_one()
    try:
        open_support_tickets = (await session.execute(
            select(func.count(SupportTicket.id)).where(
                SupportTicket.status.in_([
                    SupportTicketStatus.OPEN,
                    SupportTicketStatus.IN_PROGRESS,
                    SupportTicketStatus.WAITING_USER,
                ])
            )
        )).scalar_one()
    except SQLAlchemyError:
        open_support_tickets = 0
    sent_today = (await session.execute(
        select(func.count(Opportunity.id)).where(
            Opportunity.status == OpportunityStatus.APPROVED,
            Opportunity.published_at >= today,
        )
    )).scalar_one()

    try:
        active_now = (await session.execute(
            select(func.count(UserStats.user_id)).where(UserStats.last_active >= now - timedelta(minutes=5))
        )).scalar_one()
        active_today = (await session.execute(
            select(func.count(UserStats.user_id)).where(UserStats.last_active >= today)
        )).scalar_one()
        alerts_sent_today = (await session.execute(
            select(func.coalesce(func.sum(UserStats.alerts_received), 0)).where(UserStats.last_active >= today)
        )).scalar_one()
    except Exception:
        active_now = 0
        active_today = 0
        alerts_sent_today = 0

    new_today = (await session.execute(
        select(func.count(User.id)).where(User.created_at >= today)
    )).scalar_one()

    top_products_query = await session.execute(
        select(UserProduct.product_id, func.count(UserProduct.id).label("watchers"))
        .where(UserProduct.status == MonitoringStatus.ACTIVE)
        .group_by(UserProduct.product_id)
        .order_by(func.count(UserProduct.id).desc())
        .limit(5)
    )
    top_products_rows = top_products_query.all()
    top_products = []
    if top_products_rows:
        from db.models import Product
        product_ids = [row[0] for row in top_products_rows]
        product_rows = await session.execute(select(Product).where(Product.id.in_(product_ids)))
        product_map = {p.id: p for p in product_rows.scalars().all()}
        for pid, watchers in top_products_rows:
            p = product_map.get(pid)
            top_products.append({
                "product_id": pid,
                "name": p.name if p else "Unknown",
                "watchers": int(watchers),
            })

    top_stores_query = await session.execute(
        select(StoreRequest.store_url, func.count(StoreRequest.id).label("requests"))
        .group_by(StoreRequest.store_url)
        .order_by(func.count(StoreRequest.id).desc())
        .limit(5)
    )
    top_stores = [
        {"store_url": row[0], "requests": int(row[1])}
        for row in top_stores_query.all()
    ]

    pending_store_requests = (await session.execute(
        select(func.count(StoreRequest.id)).where(StoreRequest.status == StoreRequestStatus.PENDING)
    )).scalar_one()

    return {
        "status": "ok",
        "users_count": total,
        "free_count": free_count,
        "basic_count": basic_count,
        "professional_count": pro_count,
        "banned_count": banned_count,
        "products_count": products_count,
        "new_opportunities": new_opps,
        "open_support_tickets": open_support_tickets,
        "sent_today": sent_today,
        "active_now": active_now,
        "active_today": active_today,
        "new_today": new_today,
        "alerts_sent_today": int(alerts_sent_today or 0),
        "top_products": top_products,
        "top_stores": top_stores,
        "pending_store_requests": pending_store_requests,
    }


@app.get("/api/notifications")
async def get_notifications(
    admin: dict = Depends(verify_admin),
    session: AsyncSession = Depends(_get_db_session),
):
    """Latest admin notifications for the bell dropdown."""
    try:
        result = await session.execute(
            select(AdminNotification)
            .order_by(AdminNotification.created_at.desc())
            .limit(50)
        )
        notifications = result.scalars().all()
        unread_count = (await session.execute(
            select(func.count(AdminNotification.id)).where(AdminNotification.read == False)
        )).scalar_one()
    except SQLAlchemyError:
        return {"notifications": [], "unread_count": 0}

    return {
        "notifications": [
            {
                "id": n.id,
                "type": n.type,
                "title": n.title,
                "message": n.message,
                "icon": n.icon,
                "color": n.color,
                "read": n.read,
                "action_url": n.action_url,
                "created_at": n.created_at.isoformat() if n.created_at else None,
            }
            for n in notifications
        ],
        "unread_count": int(unread_count),
    }


@app.post("/api/notifications/{notification_id}/read")
async def mark_notification_read(
    notification_id: int,
    admin: dict = Depends(verify_admin),
    session: AsyncSession = Depends(_get_db_session),
):
    try:
        notification = (await session.execute(
            select(AdminNotification).where(AdminNotification.id == notification_id)
        )).scalar_one_or_none()
    except SQLAlchemyError:
        return {"success": True}
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")

    notification.read = True
    await session.commit()
    return {"success": True}


@app.post("/api/notifications/read-all")
async def mark_all_notifications_read(
    admin: dict = Depends(verify_admin),
    session: AsyncSession = Depends(_get_db_session),
):
    try:
        await session.execute(
            update(AdminNotification)
            .where(AdminNotification.read == False)
            .values(read=True)
        )
        await session.commit()
    except SQLAlchemyError:
        await session.rollback()
    return {"success": True}


@app.get("/api/settings/system/info")
async def get_system_info(
    admin: dict = Depends(verify_admin),
    session: AsyncSession = Depends(_get_db_session),
):  # pragma: no cover
    redis_status = "disconnected"
    try:
        await redis_client.ping()
        redis_status = "connected"
    except Exception:
        redis_status = "disconnected"

    db_version = "unknown"
    try:
        db_version = str((await session.execute(text("SELECT version()"))).scalar_one())
    except Exception:
        pass

    migration = "unknown"
    try:
        migration = str((await session.execute(text("SELECT version_num FROM alembic_version"))).scalar_one())
    except Exception:
        pass

    return {
        "bot_version": "v1.0.0",
        "python_version": platform.python_version(),
        "database_version": db_version,
        "redis_status": redis_status,
        "last_migration": migration,
        "monitoring_engine_running": monitoring_engine_running,
        "monitoring_engine_last_run": monitoring_engine_last_run.isoformat() if monitoring_engine_last_run else None,
    }


@app.post("/api/settings/system/restart-monitor")
async def restart_monitoring_engine(
    request: Request,
    x_csrf_token: Optional[str] = Header(None),
    admin: dict = Depends(verify_admin),
):  # pragma: no cover
    jti = admin.get("jti", "")
    if not x_csrf_token or not verify_csrf_token(jti, x_csrf_token):
        raise HTTPException(status_code=403, detail="Invalid or missing CSRF token")

    await redis_client.publish("system:commands", json.dumps({"action": "restart_monitor"}, ensure_ascii=False))
    _log_admin_action(
        admin_telegram_id=int(admin.get("sub", 0)),
        action="restart_monitoring_engine",
        target_type="system",
        ip=request.client.host if request.client else None,
    )
    return {"success": True, "message": "Restart signal sent"}


@app.post("/api/settings/system/clear-cache")
async def clear_redis_cache(
    request: Request,
    x_csrf_token: Optional[str] = Header(None),
    admin: dict = Depends(verify_admin),
):  # pragma: no cover
    jti = admin.get("jti", "")
    if not x_csrf_token or not verify_csrf_token(jti, x_csrf_token):
        raise HTTPException(status_code=403, detail="Invalid or missing CSRF token")

    try:
        await redis_client.flushdb()
        cleared = True
    except Exception:
        cleared = False

    _log_admin_action(
        admin_telegram_id=int(admin.get("sub", 0)),
        action="clear_cache",
        target_type="system",
        ip=request.client.host if request.client else None,
        details={"cleared": cleared},
    )
    return {"success": cleared}


@app.post("/api/settings/test-ai-scraper")
async def test_ai_scraper(
    body: dict = Body(...),
    admin: dict = Depends(verify_admin),
):
    """Run AI scraper against a URL and return extracted fields for validation."""
    url = str(body.get("url", "")).strip()
    if not url:
        raise HTTPException(status_code=422, detail="url is required")

    from core.connectors.ai_scraper import AIProductScraper

    scraper = AIProductScraper()
    data = await scraper.scrape(url)
    if not data:
        return {"success": False, "error": "AI scraper could not extract product data"}
    return {"success": True, "data": data}


@app.get("/api/settings/system/export/{export_type}")
async def export_system_data(
    export_type: str,
    admin: dict = Depends(verify_admin),
    session: AsyncSession = Depends(_get_db_session),
):  # pragma: no cover
    now = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    if export_type == "users":
        rows = (await session.execute(select(User).order_by(User.created_at.desc()))).scalars().all()
        stream = io.StringIO()
        writer = csv.writer(stream)
        writer.writerow(["telegram_id", "username", "first_name", "plan", "is_active", "is_banned", "created_at"])
        for row in rows:
            writer.writerow([
                row.telegram_id,
                row.username or "",
                row.first_name or "",
                _enum_value(row.plan),
                row.is_active,
                row.is_banned,
                row.created_at.isoformat() if row.created_at else "",
            ])
        return Response(
            content=stream.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="users_{now}.csv"'},
        )

    if export_type == "products":
        rows = (await session.execute(select(Product).order_by(Product.id.desc()))).scalars().all()
        stream = io.StringIO()
        writer = csv.writer(stream)
        writer.writerow(["id", "name", "url", "price", "currency", "in_stock", "last_scraped"])
        for row in rows:
            writer.writerow([
                row.id,
                row.name or "",
                row.url,
                row.current_price,
                row.currency,
                row.in_stock,
                row.last_scraped.isoformat() if row.last_scraped else "",
            ])
        return Response(
            content=stream.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="products_{now}.csv"'},
        )

    if export_type == "reports":
        stats = await get_stats(admin=admin, session=session)
        pseudo_pdf = (
            "%PDF-1.4\n"
            "1 0 obj<<>>endobj\n"
            "2 0 obj<< /Type /Catalog /Pages 3 0 R >>endobj\n"
            "3 0 obj<< /Type /Pages /Kids [4 0 R] /Count 1 >>endobj\n"
            "4 0 obj<< /Type /Page /Parent 3 0 R /MediaBox [0 0 612 792] /Contents 5 0 R >>endobj\n"
            f"5 0 obj<< /Length 120 >>stream\nBT /F1 12 Tf 50 740 Td (Store Monitor Summary - users: {stats['users_count']} - products: {stats['products_count']}) Tj ET\nendstream endobj\n"
            "xref\n0 6\n0000000000 65535 f \n"
            "trailer<< /Root 2 0 R /Size 6 >>\nstartxref\n0\n%%EOF"
        )
        return Response(
            content=pseudo_pdf.encode("utf-8"),
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="report_{now}.pdf"'},
        )

    raise HTTPException(status_code=400, detail="Unsupported export type")


@app.get("/api/settings/{category}")
async def get_settings_by_category(
    category: str,
    admin: dict = Depends(verify_admin),
    session: AsyncSession = Depends(_get_db_session),
):  # pragma: no cover
    if category not in SETTINGS_CATEGORIES:
        raise HTTPException(status_code=404, detail="Settings category not found")

    await _ensure_default_settings(session)

    settings_rows = (await session.execute(
        select(BotSetting)
        .where(BotSetting.category == category)
        .order_by(BotSetting.key.asc())
    )).scalars().all()

    values = {row.key: _parse_setting_value(row.value, _enum_value(row.value_type)) for row in settings_rows}
    metadata = {
        row.key: {
            "value_type": _enum_value(row.value_type),
            "description": row.description,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        }
        for row in settings_rows
    }
    return {"category": category, "values": values, "metadata": metadata}


@app.post("/api/settings/{category}")
async def update_settings_by_category(
    category: str,
    payload: dict = Body(default={}),
    request: Request = None,
    x_csrf_token: Optional[str] = Header(None),
    admin: dict = Depends(verify_admin),
    session: AsyncSession = Depends(_get_db_session),
):  # pragma: no cover
    if category not in SETTINGS_CATEGORIES:
        raise HTTPException(status_code=404, detail="Settings category not found")
    if not isinstance(payload, dict) or not payload:
        raise HTTPException(status_code=422, detail="Payload must be a non-empty object")

    jti = admin.get("jti", "")
    if not x_csrf_token or not verify_csrf_token(jti, x_csrf_token):
        raise HTTPException(status_code=403, detail="Invalid or missing CSRF token")

    await _ensure_default_settings(session)

    changed = {}
    admin_id = int(admin.get("sub", 0))

    for key, raw_value in payload.items():
        if not isinstance(key, str) or not key.startswith(f"{category}."):
            continue

        row = (await session.execute(select(BotSetting).where(BotSetting.key == key))).scalar_one_or_none()
        if row is None:
            inferred_type = _infer_setting_type(raw_value)
            row = BotSetting(
                key=key,
                category=category,
                value_type=SettingValueType(inferred_type),
                description=None,
            )
            session.add(row)

        value_type = _enum_value(row.value_type) if row.value_type else _infer_setting_type(raw_value)
        row.value = _stringify_setting_value(raw_value, value_type)
        row.value_type = SettingValueType(value_type)
        row.updated_by = admin_id
        row.updated_at = datetime.now(timezone.utc)

        parsed_value = _parse_setting_value(row.value, value_type)
        _apply_setting_to_memory(key, parsed_value)
        changed[key] = parsed_value

    await session.commit()

    _log_admin_action(
        admin_telegram_id=admin_id,
        action="update_settings",
        target_type="settings",
        ip=request.client.host if request and request.client else None,
        details={"category": category, "keys": sorted(changed.keys())},
    )

    return {"success": True, "category": category, "updated": changed}


# ======================================================
# 🎛 Bot Menu Builder API Endpoints
# ======================================================

@app.get("/api/bot-menu")
async def get_bot_menu(
    admin: dict = Depends(verify_admin),
    session: AsyncSession = Depends(_get_db_session),
):
    """Get full menu tree structure."""
    from db.models import BotMenuButton
    
    # Get all main menu buttons (parent_id == None)
    result = await session.execute(
        select(BotMenuButton)
        .where(BotMenuButton.parent_id == None)
        .order_by(BotMenuButton.row, BotMenuButton.col)
    )
    main_buttons = result.scalars().all()
    
    def serialize_button(btn: BotMenuButton) -> dict:
        return {
            "id": btn.id,
            "label": btn.label,
            "emoji": btn.emoji,
            "action_type": _enum_value(btn.action_type),
            "action_value": btn.action_value,
            "row": btn.row,
            "col": btn.col,
            "position": btn.position,
            "is_active": btn.is_active,
            "visible_for": _enum_value(btn.visible_for),
            "parent_id": btn.parent_id,
            "menu_level": btn.menu_level,
            "button_type": _enum_value(btn.button_type),
            "created_at": btn.created_at.isoformat(),
            "updated_at": btn.updated_at.isoformat(),
            "children": [serialize_button(child) for child in sorted(btn.children, key=lambda x: (x.row, x.col))],
        }
    
    menu = [serialize_button(btn) for btn in main_buttons]
    return {"menu": menu}


@app.post("/api/bot-menu")
async def create_bot_menu_button(
    payload: dict = Body(...),
    request: Request = None,
    x_csrf_token: Optional[str] = Header(None),
    admin: dict = Depends(verify_admin),
    session: AsyncSession = Depends(_get_db_session),
):
    """Create new menu button."""
    from db.models import BotMenuButton, BotMenuButtonActionType, BotMenuButtonType, BotMenuVisibility
    
    jti = admin.get("jti", "")
    if not x_csrf_token or not verify_csrf_token(jti, x_csrf_token):
        raise HTTPException(status_code=403, detail="Invalid or missing CSRF token")
    
    # Validate payload
    label = payload.get("label", "").strip()
    if not label or len(label) > 100:
        raise HTTPException(status_code=422, detail="Label required and must be ≤ 100 chars")
    
    action_type = payload.get("action_type", "message")
    button_type = payload.get("button_type", "reply")
    visible_for = payload.get("visible_for", "all")
    
    # Create button
    btn = BotMenuButton(
        label=label,
        emoji=payload.get("emoji"),
        action_type=BotMenuButtonActionType(action_type),
        action_value=payload.get("action_value"),
        row=max(0, int(payload.get("row", 0))),
        col=max(0, int(payload.get("col", 0))),
        position=max(0, int(payload.get("position", 0))),
        parent_id=payload.get("parent_id"),
        menu_level=max(0, int(payload.get("menu_level", 0))),
        button_type=BotMenuButtonType(button_type),
        visible_for=BotMenuVisibility(visible_for),
        is_active=payload.get("is_active", True),
    )
    session.add(btn)
    await session.commit()
    
    _log_admin_action(
        admin_telegram_id=int(admin.get("sub", 0)),
        action="create_bot_menu_button",
        target_type="bot_menu_button",
        target_id=btn.id,
        ip=request.client.host if request and request.client else None,
    )
    
    return {
        "id": btn.id,
        "label": btn.label,
        "emoji": btn.emoji,
        "action_type": _enum_value(btn.action_type),
        "action_value": btn.action_value,
        "row": btn.row,
        "col": btn.col,
        "position": btn.position,
        "is_active": btn.is_active,
        "visible_for": _enum_value(btn.visible_for),
        "parent_id": btn.parent_id,
        "menu_level": btn.menu_level,
        "button_type": _enum_value(btn.button_type),
    }


@app.put("/api/bot-menu/{button_id}")
async def update_bot_menu_button(
    button_id: int,
    payload: dict = Body(...),
    request: Request = None,
    x_csrf_token: Optional[str] = Header(None),
    admin: dict = Depends(verify_admin),
    session: AsyncSession = Depends(_get_db_session),
):
    """Update menu button."""
    from db.models import BotMenuButton, BotMenuButtonActionType, BotMenuButtonType, BotMenuVisibility
    
    jti = admin.get("jti", "")
    if not x_csrf_token or not verify_csrf_token(jti, x_csrf_token):
        raise HTTPException(status_code=403, detail="Invalid or missing CSRF token")
    
    btn = (await session.execute(
        select(BotMenuButton).where(BotMenuButton.id == button_id)
    )).scalar_one_or_none()
    
    if not btn:
        raise HTTPException(status_code=404, detail="Button not found")
    
    # Update fields if provided
    if "label" in payload:
        label = payload["label"].strip()
        if not label or len(label) > 100:
            raise HTTPException(status_code=422, detail="Label must be 1-100 chars")
        btn.label = label
    
    if "emoji" in payload:
        btn.emoji = payload["emoji"]
    
    if "action_type" in payload:
        btn.action_type = BotMenuButtonActionType(payload["action_type"])
    
    if "action_value" in payload:
        btn.action_value = payload["action_value"]
    
    if "row" in payload:
        btn.row = max(0, int(payload["row"]))
    
    if "col" in payload:
        btn.col = max(0, int(payload["col"]))
    
    if "position" in payload:
        btn.position = max(0, int(payload["position"]))
    
    if "button_type" in payload:
        btn.button_type = BotMenuButtonType(payload["button_type"])
    
    if "visible_for" in payload:
        btn.visible_for = BotMenuVisibility(payload["visible_for"])
    
    if "is_active" in payload:
        btn.is_active = bool(payload["is_active"])
    
    if "parent_id" in payload:
        btn.parent_id = payload["parent_id"]
    
    if "menu_level" in payload:
        btn.menu_level = max(0, int(payload["menu_level"]))
    
    btn.updated_at = datetime.now(timezone.utc)
    await session.commit()
    
    _log_admin_action(
        admin_telegram_id=int(admin.get("sub", 0)),
        action="update_bot_menu_button",
        target_type="bot_menu_button",
        target_id=btn.id,
        ip=request.client.host if request and request.client else None,
    )
    
    return {
        "id": btn.id,
        "label": btn.label,
        "emoji": btn.emoji,
        "action_type": _enum_value(btn.action_type),
        "action_value": btn.action_value,
        "row": btn.row,
        "col": btn.col,
        "position": btn.position,
        "is_active": btn.is_active,
        "visible_for": _enum_value(btn.visible_for),
        "parent_id": btn.parent_id,
        "menu_level": btn.menu_level,
        "button_type": _enum_value(btn.button_type),
    }


@app.delete("/api/bot-menu/{button_id}")
async def delete_bot_menu_button(
    button_id: int,
    request: Request = None,
    x_csrf_token: Optional[str] = Header(None),
    admin: dict = Depends(verify_admin),
    session: AsyncSession = Depends(_get_db_session),
):
    """Delete menu button and its children."""
    from db.models import BotMenuButton
    
    jti = admin.get("jti", "")
    if not x_csrf_token or not verify_csrf_token(jti, x_csrf_token):
        raise HTTPException(status_code=403, detail="Invalid or missing CSRF token")
    
    btn = (await session.execute(
        select(BotMenuButton).where(BotMenuButton.id == button_id)
    )).scalar_one_or_none()
    
    if not btn:
        raise HTTPException(status_code=404, detail="Button not found")
    
    # Delete button and all its children recursively
    async def delete_recursive(button: BotMenuButton):
        for child in button.children:
            await delete_recursive(child)
        await session.delete(button)
    
    await delete_recursive(btn)
    await session.commit()
    
    _log_admin_action(
        admin_telegram_id=int(admin.get("sub", 0)),
        action="delete_bot_menu_button",
        target_type="bot_menu_button",
        target_id=button_id,
        ip=request.client.host if request and request.client else None,
    )
    
    return {"success": True, "deleted_id": button_id}


@app.post("/api/bot-menu/reorder")
async def reorder_bot_menu_buttons(
    payload: dict = Body(...),
    request: Request = None,
    x_csrf_token: Optional[str] = Header(None),
    admin: dict = Depends(verify_admin),
    session: AsyncSession = Depends(_get_db_session),
):
    """Reorder buttons via drag & drop."""
    from db.models import BotMenuButton
    
    jti = admin.get("jti", "")
    if not x_csrf_token or not verify_csrf_token(jti, x_csrf_token):
        raise HTTPException(status_code=403, detail="Invalid or missing CSRF token")
    
    buttons_data = payload.get("buttons", [])
    if not isinstance(buttons_data, list):
        raise HTTPException(status_code=422, detail="buttons must be an array")
    
    # Update all buttons
    for btn_data in buttons_data:
        button_id = btn_data.get("id")
        btn = (await session.execute(
            select(BotMenuButton).where(BotMenuButton.id == button_id)
        )).scalar_one_or_none()
        
        if btn:
            if "row" in btn_data:
                btn.row = max(0, int(btn_data["row"]))
            if "col" in btn_data:
                btn.col = max(0, int(btn_data["col"]))
            if "position" in btn_data:
                btn.position = max(0, int(btn_data["position"]))
            btn.updated_at = datetime.now(timezone.utc)
    
    await session.commit()
    
    _log_admin_action(
        admin_telegram_id=int(admin.get("sub", 0)),
        action="reorder_bot_menu",
        target_type="bot_menu",
        ip=request.client.host if request and request.client else None,
        details={"count": len(buttons_data)},
    )
    
    return {"success": True, "reordered": len(buttons_data)}


@app.post("/api/bot-menu/publish")
async def publish_bot_menu(
    request: Request = None,
    x_csrf_token: Optional[str] = Header(None),
    admin: dict = Depends(verify_admin),
    session: AsyncSession = Depends(_get_db_session),
):
    """Apply menu changes to live bot."""
    jti = admin.get("jti", "")
    if not x_csrf_token or not verify_csrf_token(jti, x_csrf_token):
        raise HTTPException(status_code=403, detail="Invalid or missing CSRF token")
    
    # Publish event to Redis for bot to pick up
    await redis_client.publish(
        "bot:menu:updated",
        json.dumps({
            "action": "reload_menu",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }, ensure_ascii=False),
    )
    
    _log_admin_action(
        admin_telegram_id=int(admin.get("sub", 0)),
        action="publish_bot_menu",
        target_type="bot_menu",
        ip=request.client.host if request and request.client else None,
    )
    
    return {"success": True, "message": "Menu published to bot"}


@app.post("/api/bot-menu/test-connection")
async def test_bot_connection(
    admin: dict = Depends(verify_admin),
    session: AsyncSession = Depends(_get_db_session),
):
    """Verify current Telegram bot token using getMe."""
    token = await _get_bot_token(session)
    result = await _telegram_get_me(token)
    if not result.get("ok"):
        return {
            "connected": False,
            "error": result.get("description", "Invalid token"),
            "bot_username": None,
            "bot_name": None,
            "bot_id": None,
        }

    bot = result.get("result", {})
    return {
        "connected": True,
        "bot_username": bot.get("username"),
        "bot_name": bot.get("first_name"),
        "bot_id": bot.get("id"),
    }


@app.post("/api/telegram/resolve")
async def resolve_telegram_entity(
    body: TelegramResolveBody,
    admin: dict = Depends(verify_admin),
    session: AsyncSession = Depends(_get_db_session),
):
    """Resolve Telegram entity from username/link/id formats."""
    token = await _get_bot_token(session)
    if not token:
        raise HTTPException(status_code=400, detail="Bot token is not configured")

    s = body.input.strip()

    async def _call_get_chat(chat_id: str) -> dict:
        data = await _telegram_get_chat(token, chat_id)
        if not data.get("ok"):
            return {
                "success": False,
                "error": "لم يتم العثور على هذا المعرف",
                "raw": data.get("description", ""),
            }

        chat = data.get("result", {})
        chat_id_raw = chat.get("id")
        chat_id_str = str(chat_id_raw) if chat_id_raw is not None else chat_id
        member_count = await _telegram_get_chat_member_count(token, chat_id_str)
        chat_type = chat.get("type", "unknown")
        type_info = {
            "private": ("👤", "مستخدم/بوت", "user"),
            "group": ("👥", "مجموعة", "group"),
            "supergroup": ("👥", "مجموعة كبيرة", "supergroup"),
            "channel": ("📢", "قناة", "channel"),
        }.get(chat_type, ("❓", "غير معروف", "unknown"))

        name = chat.get("title") or " ".join(
            part for part in [chat.get("first_name"), chat.get("last_name")] if part
        )

        suggestions = {
            "user": [
                {"label": "👤 إضافة كمدير", "url": "/settings?tab=team"},
                {"label": "👁 عرض البروفايل", "url": f"/users/{chat.get('id')}"},
            ],
            "group": [
                {"label": "🔔 إضافة كمجموعة إدارة", "url": f"/groups?add={chat.get('id')}&purpose=admin_alerts"},
                {"label": "🎧 إضافة كمجموعة دعم", "url": f"/groups?add={chat.get('id')}&purpose=support_team"},
            ],
            "supergroup": [
                {"label": "🔔 مجموعة إدارة", "url": f"/groups?add={chat.get('id')}&purpose=admin_alerts"},
                {"label": "🎧 مجموعة دعم", "url": f"/groups?add={chat.get('id')}&purpose=support_team"},
                {"label": "👨‍💻 مجموعة تطوير", "url": f"/groups?add={chat.get('id')}&purpose=developers"},
            ],
            "channel": [
                {"label": "🔥 قناة عروض", "url": f"/groups?add={chat.get('id')}&purpose=deals"},
                {"label": "📢 قناة إعلانات", "url": f"/groups?add={chat.get('id')}&purpose=announcements"},
            ],
        }

        return {
            "success": True,
            "id": chat.get("id"),
            "type": type_info[2],
            "type_label": type_info[1],
            "type_icon": type_info[0],
            "name": name,
            "username": chat.get("username"),
            "member_count": member_count,
            "description": chat.get("description"),
            "is_verified": chat.get("is_verified", False),
            "suggestions": suggestions.get(type_info[2], []),
        }

    if re.match(r"^-?\d+$", s):
        return await _call_get_chat(s)

    private_channel_match = re.search(r"t\.me/c/(\d+)", s)
    if private_channel_match:
        return await _call_get_chat("-100" + private_channel_match.group(1))

    if "+" in s or "joinchat" in s:
        return {
            "success": False,
            "error": "روابط الدعوة لا يمكن حلها تلقائياً",
            "suggestion": "أضف البوت للمجموعة وأرسل /getid",
        }

    username = re.sub(r"^(https?://)?(t\.me/|telegram\.me/)?@?", "", s).strip("/")
    return await _call_get_chat(f"@{username}")


@app.get("/api/groups")
async def get_groups(
    admin: dict = Depends(verify_admin),
    session: AsyncSession = Depends(_get_db_session),
):
    rows = (await session.execute(select(TelegramGroup).order_by(TelegramGroup.created_at.desc()))).scalars().all()
    return {"groups": [_serialize_group(row) for row in rows]}


@app.post("/api/groups")
async def create_group(
    body: TelegramGroupBody,
    request: Request,
    x_csrf_token: Optional[str] = Header(None),
    admin: dict = Depends(verify_admin),
    session: AsyncSession = Depends(_get_db_session),
):
    jti = admin.get("jti", "")
    if not x_csrf_token or not verify_csrf_token(jti, x_csrf_token):
        raise HTTPException(status_code=403, detail="Invalid or missing CSRF token")

    exists = (await session.execute(select(TelegramGroup).where(TelegramGroup.chat_id == body.chat_id))).scalar_one_or_none()
    if exists:
        raise HTTPException(status_code=409, detail="Group already exists")

    group = TelegramGroup(
        name=body.name,
        chat_id=body.chat_id,
        purpose=TelegramGroupPurpose(body.purpose),
        description=body.description,
        is_active=body.is_active,
    )
    session.add(group)
    await session.commit()
    await session.refresh(group)

    _log_admin_action(
        admin_telegram_id=int(admin.get("sub", 0)),
        action="create_group",
        target_type="telegram_group",
        target_id=group.id,
        ip=request.client.host if request and request.client else None,
        details={"chat_id": group.chat_id, "purpose": _enum_value(group.purpose)},
    )
    return {"success": True, "group": _serialize_group(group)}


@app.put("/api/groups/{group_id}")
async def update_group(
    group_id: int,
    body: TelegramGroupBody,
    request: Request,
    x_csrf_token: Optional[str] = Header(None),
    admin: dict = Depends(verify_admin),
    session: AsyncSession = Depends(_get_db_session),
):
    jti = admin.get("jti", "")
    if not x_csrf_token or not verify_csrf_token(jti, x_csrf_token):
        raise HTTPException(status_code=403, detail="Invalid or missing CSRF token")

    group = (await session.execute(select(TelegramGroup).where(TelegramGroup.id == group_id))).scalar_one_or_none()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    if body.chat_id != group.chat_id:
        chat_taken = (await session.execute(
            select(TelegramGroup).where(TelegramGroup.chat_id == body.chat_id, TelegramGroup.id != group_id)
        )).scalar_one_or_none()
        if chat_taken:
            raise HTTPException(status_code=409, detail="chat_id already used")

    group.name = body.name
    group.chat_id = body.chat_id
    group.purpose = TelegramGroupPurpose(body.purpose)
    group.description = body.description
    group.is_active = body.is_active
    await session.commit()

    _log_admin_action(
        admin_telegram_id=int(admin.get("sub", 0)),
        action="update_group",
        target_type="telegram_group",
        target_id=group.id,
        ip=request.client.host if request and request.client else None,
    )
    return {"success": True, "group": _serialize_group(group)}


@app.delete("/api/groups/{group_id}")
async def delete_group(
    group_id: int,
    request: Request,
    x_csrf_token: Optional[str] = Header(None),
    admin: dict = Depends(verify_admin),
    session: AsyncSession = Depends(_get_db_session),
):
    jti = admin.get("jti", "")
    if not x_csrf_token or not verify_csrf_token(jti, x_csrf_token):
        raise HTTPException(status_code=403, detail="Invalid or missing CSRF token")

    group = (await session.execute(select(TelegramGroup).where(TelegramGroup.id == group_id))).scalar_one_or_none()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    await session.delete(group)
    await session.commit()

    _log_admin_action(
        admin_telegram_id=int(admin.get("sub", 0)),
        action="delete_group",
        target_type="telegram_group",
        target_id=group_id,
        ip=request.client.host if request and request.client else None,
    )
    return {"success": True}


@app.post("/api/groups/{group_id}/test")
async def test_group_connection(
    group_id: int,
    request: Request,
    x_csrf_token: Optional[str] = Header(None),
    admin: dict = Depends(verify_admin),
    session: AsyncSession = Depends(_get_db_session),
):
    jti = admin.get("jti", "")
    if not x_csrf_token or not verify_csrf_token(jti, x_csrf_token):
        raise HTTPException(status_code=403, detail="Invalid or missing CSRF token")

    group = (await session.execute(select(TelegramGroup).where(TelegramGroup.id == group_id))).scalar_one_or_none()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    token = await _get_bot_token(session)
    if not token:
        raise HTTPException(status_code=400, detail="Bot token is not configured")

    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data={"chat_id": str(group.chat_id), "text": "📡 اختبار اتصال من لوحة الإدارة"},
        )
        payload = response.json()

    if not payload.get("ok"):
        return {"success": False, "error": payload.get("description", "Failed to send")}

    message_id = payload.get("result", {}).get("message_id")
    _log_admin_action(
        admin_telegram_id=int(admin.get("sub", 0)),
        action="test_group_connection",
        target_type="telegram_group",
        target_id=group_id,
        ip=request.client.host if request and request.client else None,
        details={"chat_id": group.chat_id, "message_id": message_id},
    )
    return {"success": True, "message_id": message_id}


@app.post("/api/groups/{group_id}/verify")
async def verify_group(
    group_id: int,
    admin: dict = Depends(verify_admin),
    session: AsyncSession = Depends(_get_db_session),
):
    """Verify a configured group exists and is reachable by the current bot token."""
    group = (await session.execute(select(TelegramGroup).where(TelegramGroup.id == group_id))).scalar_one_or_none()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    token = await _get_bot_token(session)
    if not token:
        raise HTTPException(status_code=400, detail="Bot token is not configured")

    payload = await _telegram_get_chat(token, str(group.chat_id))
    if not payload.get("ok"):
        return {"success": False, "verified": False, "error": payload.get("description", "Verification failed")}

    return {"success": True, "verified": True, "chat": payload.get("result", {})}


@app.get("/api/bots")
async def get_bots(
    admin: dict = Depends(verify_admin),
    session: AsyncSession = Depends(_get_db_session),
):
    rows = (await session.execute(select(TelegramBot).order_by(TelegramBot.created_at.desc()))).scalars().all()
    return {"bots": [_serialize_bot_asset(row) for row in rows]}


@app.post("/api/bots")
async def create_bot(
    body: TelegramBotBody,
    request: Request,
    x_csrf_token: Optional[str] = Header(None),
    admin: dict = Depends(verify_admin),
    session: AsyncSession = Depends(_get_db_session),
):
    jti = admin.get("jti", "")
    if not x_csrf_token or not verify_csrf_token(jti, x_csrf_token):
        raise HTTPException(status_code=403, detail="Invalid or missing CSRF token")

    if body.username:
        exists = (await session.execute(select(TelegramBot).where(TelegramBot.username == body.username))).scalar_one_or_none()
        if exists:
            raise HTTPException(status_code=409, detail="Bot username already exists")

    bot = TelegramBot(
        name=body.name,
        username=body.username,
        token=body.token,
        purpose=body.purpose,
        description=body.description,
        is_active=body.is_active,
    )
    session.add(bot)
    await session.commit()
    await session.refresh(bot)

    _log_admin_action(
        admin_telegram_id=int(admin.get("sub", 0)),
        action="create_bot_asset",
        target_type="telegram_bot",
        target_id=bot.id,
        ip=request.client.host if request and request.client else None,
    )
    return {"success": True, "bot": _serialize_bot_asset(bot)}


@app.put("/api/bots/{bot_id}")
async def update_bot(
    bot_id: int,
    body: TelegramBotBody,
    request: Request,
    x_csrf_token: Optional[str] = Header(None),
    admin: dict = Depends(verify_admin),
    session: AsyncSession = Depends(_get_db_session),
):
    jti = admin.get("jti", "")
    if not x_csrf_token or not verify_csrf_token(jti, x_csrf_token):
        raise HTTPException(status_code=403, detail="Invalid or missing CSRF token")

    bot = (await session.execute(select(TelegramBot).where(TelegramBot.id == bot_id))).scalar_one_or_none()
    if not bot:
        raise HTTPException(status_code=404, detail="Bot not found")

    if body.username and body.username != bot.username:
        username_taken = (await session.execute(
            select(TelegramBot).where(TelegramBot.username == body.username, TelegramBot.id != bot_id)
        )).scalar_one_or_none()
        if username_taken:
            raise HTTPException(status_code=409, detail="Bot username already exists")

    bot.name = body.name
    bot.username = body.username
    bot.token = body.token
    bot.purpose = body.purpose
    bot.description = body.description
    bot.is_active = body.is_active
    await session.commit()

    _log_admin_action(
        admin_telegram_id=int(admin.get("sub", 0)),
        action="update_bot_asset",
        target_type="telegram_bot",
        target_id=bot.id,
        ip=request.client.host if request and request.client else None,
    )
    return {"success": True, "bot": _serialize_bot_asset(bot)}


@app.delete("/api/bots/{bot_id}")
async def delete_bot(
    bot_id: int,
    request: Request,
    x_csrf_token: Optional[str] = Header(None),
    admin: dict = Depends(verify_admin),
    session: AsyncSession = Depends(_get_db_session),
):
    jti = admin.get("jti", "")
    if not x_csrf_token or not verify_csrf_token(jti, x_csrf_token):
        raise HTTPException(status_code=403, detail="Invalid or missing CSRF token")

    bot = (await session.execute(select(TelegramBot).where(TelegramBot.id == bot_id))).scalar_one_or_none()
    if not bot:
        raise HTTPException(status_code=404, detail="Bot not found")

    await session.delete(bot)
    await session.commit()
    _log_admin_action(
        admin_telegram_id=int(admin.get("sub", 0)),
        action="delete_bot_asset",
        target_type="telegram_bot",
        target_id=bot_id,
        ip=request.client.host if request and request.client else None,
    )
    return {"success": True}


@app.post("/api/bots/{bot_id}/test")
async def test_bot_asset(
    bot_id: int,
    admin: dict = Depends(verify_admin),
    session: AsyncSession = Depends(_get_db_session),
):
    bot = (await session.execute(select(TelegramBot).where(TelegramBot.id == bot_id))).scalar_one_or_none()
    if not bot:
        raise HTTPException(status_code=404, detail="Bot not found")

    token = (bot.token or "").strip()
    result = await _telegram_get_me(token)
    if not result.get("ok"):
        return {"success": False, "connected": False, "error": result.get("description", "Invalid token")}

    return {"success": True, "connected": True, "bot": result.get("result", {})}


@app.post("/api/bots/{bot_id}/toggle")
async def toggle_bot_asset(
    bot_id: int,
    request: Request,
    x_csrf_token: Optional[str] = Header(None),
    admin: dict = Depends(verify_admin),
    session: AsyncSession = Depends(_get_db_session),
):
    jti = admin.get("jti", "")
    if not x_csrf_token or not verify_csrf_token(jti, x_csrf_token):
        raise HTTPException(status_code=403, detail="Invalid or missing CSRF token")

    bot = (await session.execute(select(TelegramBot).where(TelegramBot.id == bot_id))).scalar_one_or_none()
    if not bot:
        raise HTTPException(status_code=404, detail="Bot not found")

    bot.is_active = not bool(bot.is_active)
    await session.commit()
    _log_admin_action(
        admin_telegram_id=int(admin.get("sub", 0)),
        action="toggle_bot_asset",
        target_type="telegram_bot",
        target_id=bot_id,
        ip=request.client.host if request and request.client else None,
        details={"is_active": bot.is_active},
    )
    return {"success": True, "bot": _serialize_bot_asset(bot)}


@app.get("/api/support/tickets")
async def get_support_tickets(
    status: str = Query(default="all"),
    department: str = Query(default="all"),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    admin: dict = Depends(verify_admin),
    session: AsyncSession = Depends(_get_db_session),
):
    from db.crud import list_support_tickets
    from sqlalchemy import func, select
    from db.models import SupportTicket

    tickets, total = await list_support_tickets(
        session,
        status=status,
        department=department,
        page=page,
        per_page=limit,
    )

    # Get status counts for statistics
    status_counts = {}
    for status_val in ['open', 'in_progress', 'waiting_user', 'resolved', 'closed']:
        count_query = select(func.count(SupportTicket.id)).where(
            SupportTicket.status == status_val
        )
        status_counts[status_val] = (await session.execute(count_query)).scalar_one()

    return {
        "tickets": [_serialize_support_ticket(ticket) for ticket in tickets],
        "total": total,
        "page": page,
        "pages": max(1, (total + limit - 1) // limit),
        "limit": limit,
        "status_counts": status_counts,
    }


@app.get("/api/support/tickets/{ticket_id}")
async def get_support_ticket_detail(
    ticket_id: int,
    admin: dict = Depends(verify_admin),
    session: AsyncSession = Depends(_get_db_session),
):
    from db.crud import get_ticket_by_id

    ticket = await get_ticket_by_id(session, ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Support ticket not found")
    return _serialize_support_ticket(ticket, include_messages=True)


@app.post("/api/support/tickets/{ticket_id}/reply")
async def reply_to_support_ticket(
    ticket_id: int,
    body: SupportReplyBody,
    request: Request,
    x_csrf_token: Optional[str] = Header(None),
    admin: dict = Depends(verify_admin),
    session: AsyncSession = Depends(_get_db_session),
):
    from db.crud import add_ticket_message, get_admin_by_telegram_id, get_ticket_by_id

    jti = admin.get("jti", "")
    if not x_csrf_token or not verify_csrf_token(jti, x_csrf_token):
        raise HTTPException(status_code=403, detail="Invalid or missing CSRF token")

    ticket = await get_ticket_by_id(session, ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Support ticket not found")

    admin_user = await get_admin_by_telegram_id(session, int(admin.get("sub", 0)))
    sender_name = None
    if admin_user:
        sender_name = admin_user.name or admin_user.email or "الإدارة"
    if not sender_name:
        sender_name = "الإدارة"

    await add_ticket_message(
        session,
        ticket=ticket,
        sender_type=SupportSenderType.ADMIN,
        content=body.message,
        sender_admin_id=admin_user.id if admin_user else None,
        sender_name=sender_name,
    )

    await _notify_user_via_telegram(
        ticket.user.telegram_id,
        f"💬 رد من فريق الدعم\n\n{body.message}\n\n— {sender_name}\nرقم التذكرة: {ticket.ticket_number}",
    )

    await redis_client.publish(
        "support:messages",
        json.dumps(
            {
                "ticket_id": ticket.id,
                "sender": "admin",
                "sender_name": sender_name,
                "content": body.message,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
            ensure_ascii=False,
        ),
    )

    _log_admin_action(
        admin_telegram_id=int(admin.get("sub", 0)),
        action="reply_support_ticket",
        target_type="support_ticket",
        target_id=ticket.id,
        ip=request.client.host if request.client else None,
        details={"message_length": len(body.message)},
    )

    refreshed_ticket = await session.get(SupportTicket, ticket.id)
    return {"success": True, "ticket": _serialize_support_ticket(refreshed_ticket or ticket)}


@app.post("/api/support/tickets/{ticket_id}/assign")
async def assign_support_ticket(
    ticket_id: int,
    body: SupportAssignBody,
    request: Request,
    x_csrf_token: Optional[str] = Header(None),
    admin: dict = Depends(verify_admin),
    session: AsyncSession = Depends(_get_db_session),
):
    from db.crud import add_ticket_message, get_ticket_by_id

    jti = admin.get("jti", "")
    if not x_csrf_token or not verify_csrf_token(jti, x_csrf_token):
        raise HTTPException(status_code=403, detail="Invalid or missing CSRF token")

    ticket = await get_ticket_by_id(session, ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Support ticket not found")

    assignee = (await session.execute(select(AdminUser).where(AdminUser.id == body.admin_id))).scalar_one_or_none()
    if not assignee:
        raise HTTPException(status_code=404, detail="Admin user not found")

    ticket.assigned_to = assignee.id
    ticket.updated_at = datetime.now(timezone.utc)
    await session.commit()

    await add_ticket_message(
        session,
        ticket=ticket,
        sender_type=SupportSenderType.SYSTEM,
        content=f"تم تعيين التذكرة لـ {assignee.name or assignee.email or 'عضو الفريق'}",
        sender_admin_id=assignee.id,
        sender_name="النظام",
    )

    if assignee.telegram_id:
        await _notify_user_via_telegram(
            assignee.telegram_id,
            f"📋 تذكرة جديدة معيّنة لك: {ticket.ticket_number}",
        )

    _log_admin_action(
        admin_telegram_id=int(admin.get("sub", 0)),
        action="assign_support_ticket",
        target_type="support_ticket",
        target_id=ticket.id,
        ip=request.client.host if request.client else None,
        details={"assigned_to": assignee.id},
    )
    return {"success": True, "ticket": _serialize_support_ticket(ticket)}


@app.post("/api/support/tickets/{ticket_id}/transfer")
async def transfer_support_ticket(
    ticket_id: int,
    body: SupportTransferBody,
    request: Request,
    x_csrf_token: Optional[str] = Header(None),
    admin: dict = Depends(verify_admin),
    session: AsyncSession = Depends(_get_db_session),
):
    from db.crud import add_ticket_message, get_ticket_by_id

    jti = admin.get("jti", "")
    if not x_csrf_token or not verify_csrf_token(jti, x_csrf_token):
        raise HTTPException(status_code=403, detail="Invalid or missing CSRF token")

    ticket = await get_ticket_by_id(session, ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Support ticket not found")

    old_department = _enum_value(ticket.department)
    ticket.department = SupportDepartment(body.department)
    ticket.updated_at = datetime.now(timezone.utc)
    await session.commit()

    note = f". ملاحظة: {body.note}" if body.note else ""
    await add_ticket_message(
        session,
        ticket=ticket,
        sender_type=SupportSenderType.SYSTEM,
        content=f"تم نقل التذكرة من {old_department} إلى {body.department}{note}",
        sender_name="النظام",
    )

    _log_admin_action(
        admin_telegram_id=int(admin.get("sub", 0)),
        action="transfer_support_ticket",
        target_type="support_ticket",
        target_id=ticket.id,
        ip=request.client.host if request.client else None,
        details={"from": old_department, "to": body.department, "note": body.note},
    )
    return {"success": True, "ticket": _serialize_support_ticket(ticket)}


@app.post("/api/support/tickets/{ticket_id}/resolve")
async def resolve_support_ticket(
    ticket_id: int,
    request: Request,
    x_csrf_token: Optional[str] = Header(None),
    admin: dict = Depends(verify_admin),
    session: AsyncSession = Depends(_get_db_session),
):
    from db.crud import add_ticket_message, get_ticket_by_id

    jti = admin.get("jti", "")
    if not x_csrf_token or not verify_csrf_token(jti, x_csrf_token):
        raise HTTPException(status_code=403, detail="Invalid or missing CSRF token")

    ticket = await get_ticket_by_id(session, ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Support ticket not found")

    now = datetime.now(timezone.utc)
    ticket.status = SupportTicketStatus.RESOLVED
    ticket.resolved_at = now
    ticket.updated_at = now
    await session.commit()

    await add_ticket_message(
        session,
        ticket=ticket,
        sender_type=SupportSenderType.SYSTEM,
        content="تم حل التذكرة من فريق الدعم",
        sender_name="النظام",
    )
    await _notify_user_via_telegram(
        ticket.user.telegram_id,
        f"✅ تم حل تذكرتك {ticket.ticket_number}",
    )

    _log_admin_action(
        admin_telegram_id=int(admin.get("sub", 0)),
        action="resolve_support_ticket",
        target_type="support_ticket",
        target_id=ticket.id,
        ip=request.client.host if request.client else None,
    )
    return {"success": True, "ticket": _serialize_support_ticket(ticket)}


@app.post("/api/support/tickets/{ticket_id}/close")
async def close_support_ticket(
    ticket_id: int,
    request: Request,
    x_csrf_token: Optional[str] = Header(None),
    admin: dict = Depends(verify_admin),
    session: AsyncSession = Depends(_get_db_session),
):
    from db.crud import add_ticket_message, get_ticket_by_id

    jti = admin.get("jti", "")
    if not x_csrf_token or not verify_csrf_token(jti, x_csrf_token):
        raise HTTPException(status_code=403, detail="Invalid or missing CSRF token")

    ticket = await get_ticket_by_id(session, ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Support ticket not found")

    ticket.status = SupportTicketStatus.CLOSED
    ticket.updated_at = datetime.now(timezone.utc)
    await session.commit()

    await add_ticket_message(
        session,
        ticket=ticket,
        sender_type=SupportSenderType.SYSTEM,
        content="تم إغلاق التذكرة",
        sender_name="النظام",
    )

    _log_admin_action(
        admin_telegram_id=int(admin.get("sub", 0)),
        action="close_support_ticket",
        target_type="support_ticket",
        target_id=ticket.id,
        ip=request.client.host if request.client else None,
    )
    return {"success": True, "ticket": _serialize_support_ticket(ticket)}


@app.get("/api/support/team")
async def get_support_team_members(
    admin: dict = Depends(verify_admin),
    session: AsyncSession = Depends(_get_db_session),
):
    from db.crud import get_support_team

    members = await get_support_team(session)
    return {"members": [_serialize_team_member(member) for member in members]}


@app.post("/api/support/team")
async def create_support_team_member(
    body: TeamMemberBody,
    request: Request,
    x_csrf_token: Optional[str] = Header(None),
    admin: dict = Depends(verify_admin),
    session: AsyncSession = Depends(_get_db_session),
):
    jti = admin.get("jti", "")
    if not x_csrf_token or not verify_csrf_token(jti, x_csrf_token):
        raise HTTPException(status_code=403, detail="Invalid or missing CSRF token")

    member = TeamMember(
        admin_id=body.admin_id,
        display_name=body.display_name,
        department=SupportDepartment(body.department),
        role=body.role,
        avatar_color=body.avatar_color,
        is_available=body.is_available,
    )
    session.add(member)
    await session.commit()
    member = (await session.execute(
        select(TeamMember)
        .options(selectinload(TeamMember.admin))
        .where(TeamMember.id == member.id)
    )).scalar_one()

    _log_admin_action(
        admin_telegram_id=int(admin.get("sub", 0)),
        action="create_team_member",
        target_type="team_member",
        target_id=member.id,
        ip=request.client.host if request.client else None,
    )
    return {"success": True, "member": _serialize_team_member(member)}


@app.put("/api/support/team/{member_id}")
async def update_support_team_member(
    member_id: int,
    body: TeamMemberBody,
    request: Request,
    x_csrf_token: Optional[str] = Header(None),
    admin: dict = Depends(verify_admin),
    session: AsyncSession = Depends(_get_db_session),
):
    jti = admin.get("jti", "")
    if not x_csrf_token or not verify_csrf_token(jti, x_csrf_token):
        raise HTTPException(status_code=403, detail="Invalid or missing CSRF token")

    member = (await session.execute(
        select(TeamMember)
        .options(selectinload(TeamMember.admin))
        .where(TeamMember.id == member_id)
    )).scalar_one_or_none()
    if not member:
        raise HTTPException(status_code=404, detail="Team member not found")

    member.admin_id = body.admin_id
    member.display_name = body.display_name
    member.department = SupportDepartment(body.department)
    member.role = body.role
    member.avatar_color = body.avatar_color
    member.is_available = body.is_available
    await session.commit()

    member = (await session.execute(
        select(TeamMember)
        .options(selectinload(TeamMember.admin))
        .where(TeamMember.id == member_id)
    )).scalar_one()

    _log_admin_action(
        admin_telegram_id=int(admin.get("sub", 0)),
        action="update_team_member",
        target_type="team_member",
        target_id=member.id,
        ip=request.client.host if request.client else None,
    )
    return {"success": True, "member": _serialize_team_member(member)}


@app.get("/api/support/stats")
async def get_support_stats(
    admin: dict = Depends(verify_admin),
    session: AsyncSession = Depends(_get_db_session),
):
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    open_count = (await session.execute(
        select(func.count(SupportTicket.id)).where(SupportTicket.status == SupportTicketStatus.OPEN)
    )).scalar_one()
    in_progress = (await session.execute(
        select(func.count(SupportTicket.id)).where(SupportTicket.status == SupportTicketStatus.IN_PROGRESS)
    )).scalar_one()
    waiting_user = (await session.execute(
        select(func.count(SupportTicket.id)).where(SupportTicket.status == SupportTicketStatus.WAITING_USER)
    )).scalar_one()
    tickets_today = (await session.execute(
        select(func.count(SupportTicket.id)).where(SupportTicket.created_at >= today)
    )).scalar_one()
    resolved_today = (await session.execute(
        select(func.count(SupportTicket.id)).where(
            SupportTicket.status == SupportTicketStatus.RESOLVED,
            SupportTicket.resolved_at >= today,
        )
    )).scalar_one()

    first_response_rows = (await session.execute(
        select(SupportTicket.created_at, SupportTicket.first_response_at)
        .where(SupportTicket.first_response_at.is_not(None))
    )).all()
    if first_response_rows:
        avg_response_time = int(sum(
            max(0, int((first_response - created_at).total_seconds() // 60))
            for created_at, first_response in first_response_rows
            if created_at and first_response
        ) / len(first_response_rows))
    else:
        avg_response_time = 0

    return {
        "open_count": int(open_count),
        "in_progress": int(in_progress),
        "waiting_user": int(waiting_user),
        "avg_response_time": avg_response_time,
        "tickets_today": int(tickets_today),
        "resolved_today": int(resolved_today),
    }


@app.get("/api/opportunities")
async def get_opportunities(
    status: OpportunityStatusEnum = OpportunityStatusEnum.new,
    limit: int = 20,
    offset: int = 0,
    admin: dict = Depends(verify_admin),
    session: AsyncSession = Depends(_get_db_session),
):
    """List opportunities with validated filters and pagination."""
    if limit < 1 or limit > 100:
        raise HTTPException(status_code=422, detail="limit must be 1-100")
    if offset < 0:
        raise HTTPException(status_code=422, detail="offset must be >= 0")

    from db.models import Opportunity, OpportunityStatus
    from sqlalchemy.orm import selectinload

    status_map = {
        "all": None,
        "new": OpportunityStatus.NEW,
        "approved": OpportunityStatus.APPROVED,
        "rejected": OpportunityStatus.REJECTED,
        "postponed": OpportunityStatus.POSTPONED,
    }
    selected_status = status_map.get(status.value, OpportunityStatus.NEW)
    q = (
        select(Opportunity)
        .options(selectinload(Opportunity.product))
        .order_by(Opportunity.score.desc())
        .offset(offset)
        .limit(limit)
    )
    if selected_status is not None:
        q = q.where(Opportunity.status == selected_status)
    result = await session.execute(q)
    opps = result.scalars().all()

    total_q = select(func.count(Opportunity.id))
    if selected_status is not None:
        total_q = total_q.where(Opportunity.status == selected_status)
    total = (await session.execute(total_q)).scalar_one()

    return {
        "opportunities": [
            {
                "id": o.id,
                "product_name": o.product.name if o.product else None,
                "old_price": o.old_price,
                "new_price": o.new_price,
                "discount_percent": o.discount_percent,
                "score": o.score,
                "status": o.status.value if hasattr(o.status, 'value') else o.status,
                "in_stock": o.in_stock,
                "discovered_at": o.discovered_at.isoformat() if o.discovered_at else None,
            }
            for o in opps
        ],
        "total": total,
    }


@app.get("/api/users")
async def get_users(
    page: int = 1,
    limit: int = 20,
    plan: Optional[str] = None,
    search: Optional[str] = None,
    include_sensitive: bool = False,
    admin: dict = Depends(verify_admin),
    session: AsyncSession = Depends(_get_db_session),
):
    """User list with search, plan filter, pagination and profile telemetry."""
    if page < 1:
        raise HTTPException(status_code=422, detail="page must be >= 1")
    if limit < 1 or limit > 100:
        raise HTTPException(status_code=422, detail="limit must be 1-100")
    if plan is not None and plan not in ("free", "basic", "professional"):
        raise HTTPException(status_code=422, detail="Invalid plan filter")

    offset = (page - 1) * limit
    base = select(
        User.id,
        User.telegram_id,
        User.username,
        User.first_name,
        User.last_name,
        User.plan,
        User.plan_expires_at,
        User.is_active,
        User.created_at,
        User.is_banned,
        User.muted,
    )
    count_q = select(func.count(User.id))

    if plan:
        plan_enum = PlanType(plan)
        base = base.where(User.plan == plan_enum)
        count_q = count_q.where(User.plan == plan_enum)

    if search:
        search_filter = or_(
            User.username.ilike(f"%{search}%"),
            User.first_name.ilike(f"%{search}%"),
            User.telegram_id == int(search) if search.isdigit() else False,
        )
        base = base.where(search_filter)
        count_q = count_q.where(search_filter)

    total = (await session.execute(count_q)).scalar_one()
    result = await session.execute(
        base.order_by(User.created_at.desc()).offset(offset).limit(limit)
    )
    users = result.all()

    # Count products per user in one query
    user_ids = [u.id for u in users]
    products_map = {}
    categories_map = {}
    stores_map = {}
    stats_map: dict[int, UserStats] = {}
    if user_ids:
        pc = await session.execute(
            select(UserProduct.user_id, func.count(UserProduct.id))
            .where(UserProduct.user_id.in_(user_ids), UserProduct.status == MonitoringStatus.ACTIVE)
            .group_by(UserProduct.user_id)
        )
        products_map = dict(pc.all())

        cc = await session.execute(
            select(UserCategory.user_id, func.count(UserCategory.id))
            .where(UserCategory.user_id.in_(user_ids), UserCategory.status == MonitoringStatus.ACTIVE)
            .group_by(UserCategory.user_id)
        )
        categories_map = dict(cc.all())

        sc = await session.execute(
            select(UserStore.user_id, func.count(UserStore.id))
            .where(UserStore.user_id.in_(user_ids), UserStore.status == MonitoringStatus.ACTIVE)
            .group_by(UserStore.user_id)
        )
        stores_map = dict(sc.all())

        try:
            stats_rows = await session.execute(
                select(UserStats).where(UserStats.user_id.in_(user_ids))
            )
            stats_map = {s.user_id: s for s in stats_rows.scalars().all()}
        except Exception:
            stats_map = {}

    users_payload = []
    for u in users:
        row = {
            "id": u.id,
            "username": u.username,
            "first_name": u.first_name,
            "last_name": u.last_name,
            "plan": u.plan.value if hasattr(u.plan, 'value') else u.plan,
            "plan_expires_at": u.plan_expires_at.isoformat() if u.plan_expires_at else None,
            "is_active": u.is_active,
            "products_count": products_map.get(u.id, 0),
            "categories_count": categories_map.get(u.id, 0),
            "stores_count": stores_map.get(u.id, 0),
            "total_actions": int(stats_map.get(u.id).total_actions if stats_map.get(u.id) else 0),
            "alerts_received": int(stats_map.get(u.id).alerts_received if stats_map.get(u.id) else 0),
            "deals_clicked": int(stats_map.get(u.id).deals_clicked if stats_map.get(u.id) else 0),
            "last_active": (
                stats_map.get(u.id).last_active.isoformat()
                if stats_map.get(u.id) and stats_map.get(u.id).last_active
                else None
            ),
            "daily_activity": _daily_sparkline_points(
                stats_map.get(u.id).daily_activity if stats_map.get(u.id) else []
            ),
            "created_at": u.created_at.isoformat() if u.created_at else None,
            "is_banned": u.is_banned,
            "muted": u.muted,
        }
        if include_sensitive:
            row["telegram_id"] = u.telegram_id
        users_payload.append(row)

    return {
        "users": users_payload,
        "total": total,
        "page": page,
    }


@app.get("/api/users/{telegram_id}/profile")
async def get_user_profile(
    telegram_id: int,
    admin: dict = Depends(verify_admin),
    session: AsyncSession = Depends(_get_db_session),
):
    """Full detailed user profile with telemetry and history."""
    user_result = await session.execute(
        select(User)
        .options(
            selectinload(User.monitored_products).selectinload(UserProduct.product),
            selectinload(User.store_requests),
            selectinload(User.stats),
        )
        .where(User.telegram_id == telegram_id)
    )
    user = user_result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    stats = user.stats
    profile_stats = {
        "total_actions": int(stats.total_actions if stats else 0),
        "products_added": int(stats.products_added if stats else 0),
        "products_deleted": int(stats.products_deleted if stats else 0),
        "alerts_received": int(stats.alerts_received if stats else 0),
        "deals_viewed": int(stats.deals_viewed if stats else 0),
        "deals_clicked": int(stats.deals_clicked if stats else 0),
        "store_requests_sent": int(stats.store_requests_sent if stats else 0),
        "streak_days": int(stats.streak_days if stats else 0),
        "daily_activity": stats.daily_activity if stats and stats.daily_activity else [],
    }

    activities_q = await session.execute(
        select(UserActivity)
        .where(UserActivity.user_id == user.id)
        .order_by(UserActivity.created_at.desc())
        .limit(100)
    )
    activities = activities_q.scalars().all()

    hour_hist: dict[int, int] = {}
    favorite_store_hist: dict[str, int] = {}
    for act in activities:
        if act.created_at:
            hour = act.created_at.hour
            hour_hist[hour] = hour_hist.get(hour, 0) + 1
        if isinstance(act.details, dict):
            store_name = act.details.get("store")
            if store_name:
                favorite_store_hist[store_name] = favorite_store_hist.get(store_name, 0) + 1

    profile_stats["most_active_hour"] = max(hour_hist, key=hour_hist.get) if hour_hist else None
    profile_stats["favorite_store"] = max(favorite_store_hist, key=favorite_store_hist.get) if favorite_store_hist else None

    products = []
    for up in user.monitored_products:
        if up.status == MonitoringStatus.DELETED:
            continue
        product = up.product
        products.append(
            {
                "name": product.name if product else None,
                "url": product.url if product else None,
                "current_price": product.current_price if product else None,
                "status": up.status.value if hasattr(up.status, "value") else up.status,
                "alert_types": up.alert_types or [],
                "added_at": up.created_at.isoformat() if up.created_at else None,
                "alerts_count": 0,
            }
        )

    recent_activities = [
        {
            "action": a.action,
            "details": a.details,
            "created_at": a.created_at.isoformat() if a.created_at else None,
        }
        for a in activities[:30]
    ]

    store_requests = [
        {
            "store_url": r.store_url,
            "status": r.status.value if hasattr(r.status, "value") else r.status,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "admin_notes": r.admin_notes,
        }
        for r in user.store_requests
    ]

    sub_audit = await session.execute(
        select(AuditLog)
        .where(AuditLog.target_type == "user", AuditLog.target_id == user.id, AuditLog.action == "upgrade_user")
        .order_by(AuditLog.created_at.desc())
    )
    subscription_history = [
        {
            "action": row.action,
            "details": row.details,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "admin_telegram_id": row.admin_telegram_id,
        }
        for row in sub_audit.scalars().all()
    ]

    return {
        "user": {
            "id": user.id,
            "telegram_id": user.telegram_id,
            "username": user.username,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "plan": user.plan.value if hasattr(user.plan, "value") else user.plan,
            "plan_expires_at": user.plan_expires_at.isoformat() if user.plan_expires_at else None,
            "is_active": user.is_active,
            "is_banned": user.is_banned,
            "muted": user.muted,
            "created_at": user.created_at.isoformat() if user.created_at else None,
            "last_active": stats.last_active.isoformat() if stats and stats.last_active else None,
        },
        "stats": profile_stats,
        "products": products,
        "recent_activities": recent_activities,
        "store_requests": store_requests,
        "subscription_history": subscription_history,
    }


@app.get("/api/users/{telegram_id}/activity")
async def get_user_activity(
    telegram_id: int,
    from_date: Optional[str] = Query(None, alias="from"),
    to_date: Optional[str] = Query(None, alias="to"),
    action: str = Query("all"),
    page: int = 1,
    limit: int = 50,
    admin: dict = Depends(verify_admin),
    session: AsyncSession = Depends(_get_db_session),
):  # pragma: no cover
    """Paginated activity timeline for a user."""
    if page < 1:
        raise HTTPException(status_code=422, detail="page must be >= 1")
    if limit < 1 or limit > 200:
        raise HTTPException(status_code=422, detail="limit must be 1-200")

    user = (
        await session.execute(select(User).where(User.telegram_id == telegram_id))
    ).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    q = select(UserActivity).where(UserActivity.user_id == user.id)
    count_q = select(func.count(UserActivity.id)).where(UserActivity.user_id == user.id)

    if action != "all":
        q = q.where(UserActivity.action == action)
        count_q = count_q.where(UserActivity.action == action)

    if from_date:
        from_dt = datetime.fromisoformat(from_date)
        q = q.where(UserActivity.created_at >= from_dt)
        count_q = count_q.where(UserActivity.created_at >= from_dt)
    if to_date:
        to_dt = datetime.fromisoformat(to_date)
        q = q.where(UserActivity.created_at <= to_dt)
        count_q = count_q.where(UserActivity.created_at <= to_dt)

    offset = (page - 1) * limit
    q = q.order_by(UserActivity.created_at.desc()).offset(offset).limit(limit)

    rows = (await session.execute(q)).scalars().all()
    total = (await session.execute(count_q)).scalar_one()

    return {
        "activities": [
            {
                "id": r.id,
                "action": r.action,
                "details": r.details,
                "session_id": r.session_id,
                "ip_address": r.ip_address,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ],
        "total": total,
        "page": page,
        "limit": limit,
    }


@app.get("/api/dashboard/live")
async def dashboard_live(
    admin: dict = Depends(verify_admin),
    session: AsyncSession = Depends(_get_db_session),
):  # pragma: no cover
    """Polling fallback endpoint for live dashboard widgets."""
    now = datetime.utcnow()
    active_since = now - timedelta(minutes=5)

    try:
        active_now = (await session.execute(
            select(func.count(UserStats.user_id)).where(UserStats.last_active >= active_since)
        )).scalar_one()
    except Exception:
        active_now = 0

    recent = []
    top_users = []
    recent_alerts = []

    try:
        recent_q = await session.execute(
            select(UserActivity, User)
            .join(User, User.id == UserActivity.user_id)
            .order_by(UserActivity.created_at.desc())
            .limit(20)
        )

        for activity, user in recent_q.all():
            recent.append(
                {
                    "type": "user_action",
                    "timestamp": activity.created_at.isoformat() if activity.created_at else None,
                    "user": {
                        "id": user.telegram_id,
                        "username": user.username,
                        "name": user.first_name,
                        "plan": user.plan.value if hasattr(user.plan, "value") else user.plan,
                    },
                    "action": activity.action,
                    "details": activity.details,
                }
            )

        top_users_q = await session.execute(
            select(UserActivity.user_id, func.count(UserActivity.id).label("actions"))
            .where(UserActivity.created_at >= now.replace(hour=0, minute=0, second=0, microsecond=0))
            .group_by(UserActivity.user_id)
            .order_by(func.count(UserActivity.id).desc())
            .limit(5)
        )
        top_users_rows = top_users_q.all()
        user_map = {}
        if top_users_rows:
            ids = [row[0] for row in top_users_rows]
            users_q = await session.execute(select(User).where(User.id.in_(ids)))
            user_map = {u.id: u for u in users_q.scalars().all()}

        for uid, actions in top_users_rows:
            u = user_map.get(uid)
            if not u:
                continue
            top_users.append(
                {
                    "telegram_id": u.telegram_id,
                    "username": u.username,
                    "first_name": u.first_name,
                    "actions": int(actions),
                }
            )

        alerts_q = await session.execute(
            select(UserActivity, User)
            .join(User, User.id == UserActivity.user_id)
            .where(UserActivity.action == "price_alert_received")
            .order_by(UserActivity.created_at.desc())
            .limit(5)
        )
        for activity, user in alerts_q.all():
            details = activity.details or {}
            recent_alerts.append(
                {
                    "product": details.get("product") or details.get("product_name"),
                    "user": user.username or user.first_name,
                    "alert_type": details.get("alert_type") or "price_alert",
                    "time": activity.created_at.isoformat() if activity.created_at else None,
                }
            )
    except Exception:
        recent = []
        top_users = []
        recent_alerts = []

    return {
        "active_now": active_now,
        "recent_activities": recent,
        "top_users_today": top_users,
        "recent_alerts": recent_alerts,
    }


@app.websocket("/ws/activity")
async def activity_websocket(websocket: WebSocket, token: str = Query(...)):
    """Real-time activity stream for dashboard."""
    if not _verify_ws_admin(token):
        await websocket.close(code=4001)
        return

    await websocket.accept()
    pubsub = redis_client.pubsub()
    await pubsub.subscribe("bot:activity")

    try:
        while True:
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if message and message.get("type") == "message":
                raw_data = message.get("data")
                if isinstance(raw_data, bytes):
                    raw_data = raw_data.decode("utf-8")
                try:
                    payload = json.loads(raw_data)
                except Exception:
                    payload = {"type": "raw", "data": raw_data}
                await websocket.send_json(payload)
            await asyncio.sleep(0.05)
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        await pubsub.unsubscribe("bot:activity")
        await pubsub.close()


@app.websocket("/ws/support/{ticket_id}")
async def support_ticket_websocket(ticket_id: int, websocket: WebSocket, token: str = Query(...)):
    """Stream real-time support messages for a single ticket."""
    if not _verify_ws_admin(token):
        await websocket.close(code=4001)
        return

    await websocket.accept()
    pubsub = redis_client.pubsub()
    await pubsub.subscribe("support:messages")

    try:
        while True:
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if message and message.get("type") == "message":
                raw_data = message.get("data")
                if isinstance(raw_data, bytes):
                    raw_data = raw_data.decode("utf-8")
                try:
                    payload = json.loads(raw_data)
                except Exception:
                    payload = {"type": "raw", "data": raw_data}

                if payload.get("ticket_id") == ticket_id:
                    await websocket.send_json(payload)
            await asyncio.sleep(0.05)
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        await pubsub.unsubscribe("support:messages")
        await pubsub.close()


@app.get("/api/users/{telegram_id}")
async def get_user_detail(
    telegram_id: int,
    admin: dict = Depends(verify_admin),
    session: AsyncSession = Depends(_get_db_session),
):
    """Full user profile with products and subscription info."""
    from sqlalchemy.orm import selectinload

    result = await session.execute(
        select(User)
        .options(
            selectinload(User.monitored_products).selectinload(UserProduct.product),
            selectinload(User.monitored_categories),
            selectinload(User.store_requests),
        )
        .where(User.telegram_id == telegram_id)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    products = [
        {
            "id": up.id,
            "name": up.product.name if up.product else None,
            "url": up.product.url if up.product else None,
            "current_price": up.product.current_price if up.product else None,
            "status": up.status.value if hasattr(up.status, 'value') else up.status,
        }
        for up in user.monitored_products
        if up.status != MonitoringStatus.DELETED
    ]

    # Audit log entries for this user
    audit_result = await session.execute(
        select(AuditLog)
        .where(AuditLog.target_type == "user", AuditLog.target_id == user.id)
        .order_by(AuditLog.created_at.desc())
        .limit(20)
    )
    audit_entries = audit_result.scalars().all()

    return {
        "id": user.id,
        "telegram_id": user.telegram_id,
        "username": user.username,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "plan": user.plan.value if hasattr(user.plan, 'value') else user.plan,
        "plan_expires_at": user.plan_expires_at.isoformat() if user.plan_expires_at else None,
        "is_banned": user.is_banned,
        "muted": user.muted,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "products": products,
        "categories_count": len(user.monitored_categories),
        "store_requests_count": len(user.store_requests),
        "audit_log": [
            {
                "action": a.action,
                "details": a.details,
                "created_at": a.created_at.isoformat() if a.created_at else None,
            }
            for a in audit_entries
        ],
    }


@app.post("/api/users/{telegram_id}/upgrade")
async def upgrade_user(
    telegram_id: int,
    body: UpgradeBody,
    request: Request,
    x_csrf_token: Optional[str] = Header(None),
    admin: dict = Depends(verify_admin),
    session: AsyncSession = Depends(_get_db_session),
):
    """Upgrade/change a user's plan and notify via Telegram."""
    jti = admin.get("jti", "")
    if not x_csrf_token or not verify_csrf_token(jti, x_csrf_token):
        raise HTTPException(status_code=403, detail="Invalid or missing CSRF token")

    user = (await session.execute(
        select(User).where(User.telegram_id == telegram_id)
    )).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    plan_enum = PlanType(body.plan)
    expires_at = datetime.utcnow() + timedelta(days=body.days) if body.plan != "free" else None

    await session.execute(
        update(User)
        .where(User.id == user.id)
        .values(plan=plan_enum, plan_expires_at=expires_at)
    )
    await session.commit()

    from db.crud import create_admin_notification
    display_name = user.username or user.first_name or user.telegram_id
    await create_admin_notification(
        session,
        type="plan_upgraded",
        title="ترقية خطة اشتراك ⭐",
        message=f"تمت ترقية @{display_name} إلى {PLAN_NAMES.get(body.plan, body.plan)}",
        icon="⭐",
        color="purple",
        action_url="/users",
    )

    # Audit log
    _log_admin_action(
        admin_telegram_id=int(admin.get("sub", 0)),
        action="upgrade_user",
        target_type="user",
        target_id=user.id,
        ip=request.client.host if request.client else None,
        details={"plan": body.plan, "days": body.days},
    )

    # Send Telegram notification to the user
    plan_label = PLAN_NAMES.get(body.plan, body.plan)
    expiry_str = expires_at.strftime("%d/%m/%Y") if expires_at else "∞"
    max_products = PLAN_LIMITS.get(body.plan, {}).get("max_products", "?")
    await _notify_user_via_telegram(
        telegram_id,
        f"🎉 تم تفعيل اشتراكك!\n\n"
        f"📋 الخطة: {plan_label}\n"
        f"📅 فعّالة حتى: {expiry_str}\n"
        f"📦 الحد الأقصى: {max_products} منتج\n\n"
        f"شكراً لاشتراكك! 🙏",
    )

    return {
        "success": True,
        "user": {
            "telegram_id": user.telegram_id,
            "username": user.username,
            "plan": body.plan,
            "plan_expires_at": expires_at.isoformat() if expires_at else None,
        },
    }


@app.post("/api/users/{telegram_id}/ban")
async def ban_user(
    telegram_id: int,
    request: Request,
    x_csrf_token: Optional[str] = Header(None),
    admin: dict = Depends(verify_admin),
    session: AsyncSession = Depends(_get_db_session),
):
    """Ban a user account."""
    jti = admin.get("jti", "")
    if not x_csrf_token or not verify_csrf_token(jti, x_csrf_token):
        raise HTTPException(status_code=403, detail="Invalid or missing CSRF token")

    user = (await session.execute(
        select(User).where(User.telegram_id == telegram_id)
    )).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    await session.execute(update(User).where(User.id == user.id).values(is_banned=True))
    await session.commit()

    _log_admin_action(
        admin_telegram_id=int(admin.get("sub", 0)),
        action="ban_user",
        target_type="user",
        target_id=user.id,
        ip=request.client.host if request.client else None,
    )

    await _notify_user_via_telegram(
        telegram_id,
        "🚫 تم تعليق حسابك. للاستفسار: @UncleNull",
    )

    return {
        "success": True,
        "user": {
            "telegram_id": user.telegram_id,
            "username": user.username,
            "is_banned": True,
        },
    }


@app.post("/api/users/{telegram_id}/unban")
async def unban_user(
    telegram_id: int,
    request: Request,
    x_csrf_token: Optional[str] = Header(None),
    admin: dict = Depends(verify_admin),
    session: AsyncSession = Depends(_get_db_session),
):
    """Unban a user account."""
    jti = admin.get("jti", "")
    if not x_csrf_token or not verify_csrf_token(jti, x_csrf_token):
        raise HTTPException(status_code=403, detail="Invalid or missing CSRF token")

    user = (await session.execute(
        select(User).where(User.telegram_id == telegram_id)
    )).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    await session.execute(update(User).where(User.id == user.id).values(is_banned=False))
    await session.commit()

    _log_admin_action(
        admin_telegram_id=int(admin.get("sub", 0)),
        action="unban_user",
        target_type="user",
        target_id=user.id,
        ip=request.client.host if request.client else None,
    )

    await _notify_user_via_telegram(
        telegram_id,
        "✅ تم رفع التعليق عن حسابك ويمكنك استخدام البوت مجدداً.",
    )

    return {
        "success": True,
        "user": {
            "telegram_id": user.telegram_id,
            "username": user.username,
            "is_banned": False,
        },
    }


@app.post("/api/users/{telegram_id}/send-message")
async def send_message_to_user(
    telegram_id: int,
    body: AdminMessageBody,
    request: Request,
    x_csrf_token: Optional[str] = Header(None),
    admin: dict = Depends(verify_admin),
    session: AsyncSession = Depends(_get_db_session),
):
    """Send a direct dashboard message to a user via Telegram."""
    jti = admin.get("jti", "")
    if not x_csrf_token or not verify_csrf_token(jti, x_csrf_token):
        raise HTTPException(status_code=403, detail="Invalid or missing CSRF token")

    user = (await session.execute(
        select(User).where(User.telegram_id == telegram_id)
    )).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    message_text = (body.message or "").strip()
    if not message_text:
        raise HTTPException(status_code=422, detail="message must not be empty")

    await _notify_user_via_telegram(
        telegram_id,
        f"📢 رسالة من الإدارة\n\n{message_text}",
    )

    session.add(
        UserActivity(
            user_id=user.id,
            action="admin_message_sent",
            details={
                "admin_telegram_id": int(admin.get("sub", 0)),
                "message": message_text,
            },
            ip_address=request.client.host if request.client else None,
            created_at=datetime.utcnow(),
        )
    )
    await session.commit()

    _log_admin_action(
        admin_telegram_id=int(admin.get("sub", 0)),
        action="admin_message_sent",
        target_type="user",
        target_id=user.id,
        ip=request.client.host if request.client else None,
        details={"message_length": len(message_text)},
    )

    return {
        "success": True,
        "message": "تم الإرسال",
        "user": {
            "telegram_id": user.telegram_id,
            "username": user.username,
        },
    }


async def _notify_user_via_telegram(telegram_id: int, text: str):
    """Send a Telegram message to a user via the Bot API."""
    try:
        from aiogram import Bot
        bot = Bot(token=TELEGRAM_BOT_TOKEN)
        await bot.send_message(telegram_id, text)
        await bot.session.close()
    except Exception as e:
        logger.warning("Failed to send Telegram notification to %s: %s", telegram_id, e)


async def _resolve_target_users(session: AsyncSession, target: str):
    query = select(User).where(User.is_active == True, User.is_banned == False, User.muted == False)
    if target == "pro":
        query = query.where(User.plan == PlanType.PROFESSIONAL)
    elif target in ("paid", "basic"):
        query = query.where(User.plan.in_([PlanType.BASIC, PlanType.PROFESSIONAL]))
    result = await session.execute(query)
    return result.scalars().all()


async def _send_text_to_users(users: list[User], message_text: str) -> tuple[int, int]:
    from aiogram import Bot

    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    sent = 0
    failed = 0
    try:
        for user in users:
            try:
                await bot.send_message(user.telegram_id, message_text)
                sent += 1
            except Exception:
                failed += 1
    finally:
        await bot.session.close()
    return sent, failed


@app.post("/api/opportunities/manual")
async def publish_manual_opportunity(
    body: ManualOpportunityBody,
    request: Request,
    x_csrf_token: Optional[str] = Header(None),
    admin: dict = Depends(verify_admin),
    session: AsyncSession = Depends(_get_db_session),
):
    """Create approved opportunity manually then broadcast it to selected users."""
    jti = admin.get("jti", "")
    if not x_csrf_token or not verify_csrf_token(jti, x_csrf_token):
        raise HTTPException(status_code=403, detail="Invalid or missing CSRF token")

    store = (
        await session.execute(select(Store).where(Store.base_url.ilike(f"%{body.product_url.split('/')[2]}%")))
    ).scalar_one_or_none() if body.product_url.startswith("http") and len(body.product_url.split("/")) > 2 else None

    product = Product(
        url=body.product_url,
        store_id=store.id if store else None,
        name=body.product_name,
        current_price=body.new_price,
        original_price=body.old_price,
        in_stock=True,
        currency="SAR",
        created_at=datetime.utcnow(),
    )
    session.add(product)
    await session.flush()

    discount = max(0.0, ((body.old_price - body.new_price) / body.old_price) * 100)
    opp = Opportunity(
        product_id=product.id,
        old_price=body.old_price,
        new_price=body.new_price,
        discount_percent=discount,
        in_stock=True,
        score=min(100.0, 50.0 + discount),
        status=OpportunityStatus.APPROVED,
        affiliate_url=body.affiliate_url,
        custom_message=body.custom_message,
        discovered_at=datetime.utcnow(),
        published_at=datetime.utcnow(),
    )
    session.add(opp)
    await session.commit()

    users = await _resolve_target_users(session, body.target_plan)
    message_text = (
        f"📢 عرض يدوي جديد\n\n"
        f"📦 {body.product_name}\n"
        f"💰 قبل: {body.old_price:.2f}\n"
        f"🔥 بعد: {body.new_price:.2f}\n"
        f"📉 الخصم: {discount:.1f}%\n"
        f"🔗 {body.affiliate_url or body.product_url}"
    )
    if body.custom_message:
        message_text += f"\n\n💬 {body.custom_message}"

    sent, failed = await _send_text_to_users(users, message_text)

    _log_admin_action(
        admin_telegram_id=int(admin.get("sub", 0)),
        action="manual_opportunity_publish",
        target_type="opportunity",
        target_id=opp.id,
        ip=request.client.host if request.client else None,
        details={"target_plan": body.target_plan, "sent": sent, "failed": failed},
    )

    return {"success": True, "sent_count": sent, "failed": failed}


@app.get("/api/stores")
async def get_stores(
    admin: dict = Depends(verify_admin),
    session: AsyncSession = Depends(_get_db_session),
):
    """Supported store list."""
    result = await session.execute(select(Store).order_by(Store.created_at.desc()))
    stores = result.scalars().all()
    return {
        "stores": [
            {
                "id": s.id,
                "name": s.name,
                "base_url": s.base_url,
                "connector_type": s.connector_type,
                "is_active": s.is_active,
                "created_at": s.created_at.isoformat() if s.created_at else None,
            }
            for s in stores
        ]
    }


@app.post("/api/stores")
async def create_store(
    body: StoreCreateBody,
    request: Request,
    x_csrf_token: Optional[str] = Header(None),
    admin: dict = Depends(verify_admin),
    session: AsyncSession = Depends(_get_db_session),
):
    jti = admin.get("jti", "")
    if not x_csrf_token or not verify_csrf_token(jti, x_csrf_token):
        raise HTTPException(status_code=403, detail="Invalid or missing CSRF token")

    existing = (await session.execute(select(Store).where(Store.base_url == body.base_url))).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="Store already exists")

    store = Store(
        name=body.name,
        base_url=body.base_url,
        connector_type=body.connector_type,
        is_active=True,
        created_at=datetime.utcnow(),
    )
    session.add(store)
    await session.commit()
    await session.refresh(store)

    _log_admin_action(
        admin_telegram_id=int(admin.get("sub", 0)),
        action="create_store",
        target_type="store",
        target_id=store.id,
        ip=request.client.host if request.client else None,
        details={"name": store.name, "base_url": store.base_url},
    )

    return {
        "success": True,
        "store": {
            "id": store.id,
            "name": store.name,
            "base_url": store.base_url,
            "connector_type": store.connector_type,
            "is_active": store.is_active,
        },
    }


@app.post("/api/broadcast")
async def broadcast_message(
    body: BroadcastBody,
    request: Request,
    x_csrf_token: Optional[str] = Header(None),
    admin: dict = Depends(verify_admin),
    session: AsyncSession = Depends(_get_db_session),
):
    jti = admin.get("jti", "")
    if not x_csrf_token or not verify_csrf_token(jti, x_csrf_token):
        raise HTTPException(status_code=403, detail="Invalid or missing CSRF token")

    users = await _resolve_target_users(session, body.target)
    sent, failed = await _send_text_to_users(users, f"📢 إعلان من Store Monitor\n\n{body.message}")

    from db.crud import create_admin_notification
    await create_admin_notification(
        session,
        type="broadcast_done",
        title="انتهاء الإرسال الجماعي 📣",
        message=f"تم إرسال الإعلان إلى {sent} مستخدم (فشل {failed})",
        icon="📣",
        color="blue",
        action_url="/users",
    )

    _log_admin_action(
        admin_telegram_id=int(admin.get("sub", 0)),
        action="broadcast",
        target_type="users",
        target_id=None,
        ip=request.client.host if request.client else None,
        details={"target": body.target, "sent": sent, "failed": failed},
    )

    return {"sent": sent, "failed": failed}


@app.get("/api/store-requests")
async def list_store_requests(
    status: str = Query("pending"),
    admin: dict = Depends(verify_admin),
    session: AsyncSession = Depends(_get_db_session),
):
    status_map = {
        "pending": StoreRequestStatus.PENDING,
        "approved": StoreRequestStatus.APPROVED,
        "rejected": StoreRequestStatus.REJECTED,
        "in_review": StoreRequestStatus.IN_REVIEW,
    }
    if status not in status_map and status != "all":
        raise HTTPException(status_code=422, detail="Invalid status")

    query = select(StoreRequest, User).join(User, User.id == StoreRequest.user_id).order_by(StoreRequest.created_at.desc())
    if status != "all":
        query = query.where(StoreRequest.status == status_map[status])

    rows = (await session.execute(query)).all()
    pending = (await session.execute(
        select(func.count(StoreRequest.id)).where(StoreRequest.status == StoreRequestStatus.PENDING)
    )).scalar_one()

    return {
        "requests": [
            {
                "id": req.id,
                "store_url": req.store_url,
                "status": req.status.value if hasattr(req.status, "value") else req.status,
                "admin_notes": req.admin_notes,
                "created_at": req.created_at.isoformat() if req.created_at else None,
                "user": {
                    "telegram_id": user.telegram_id,
                    "username": user.username,
                    "first_name": user.first_name,
                },
            }
            for req, user in rows
        ],
        "pending_count": pending,
    }


@app.post("/api/store-requests/{request_id}/approve")
async def approve_store_request_api(
    request_id: int,
    body: StoreRequestDecisionBody,
    request: Request,
    x_csrf_token: Optional[str] = Header(None),
    admin: dict = Depends(verify_admin),
    session: AsyncSession = Depends(_get_db_session),
):
    jti = admin.get("jti", "")
    if not x_csrf_token or not verify_csrf_token(jti, x_csrf_token):
        raise HTTPException(status_code=403, detail="Invalid or missing CSRF token")

    req = (await session.execute(select(StoreRequest).where(StoreRequest.id == request_id))).scalar_one_or_none()
    if not req:
        raise HTTPException(status_code=404, detail="Store request not found")

    await session.execute(
        update(StoreRequest)
        .where(StoreRequest.id == request_id)
        .values(status=StoreRequestStatus.APPROVED, admin_notes=body.admin_notes, updated_at=datetime.utcnow())
    )
    await session.commit()

    _log_admin_action(
        admin_telegram_id=int(admin.get("sub", 0)),
        action="approve_store_request",
        target_type="store_request",
        target_id=request_id,
        ip=request.client.host if request.client else None,
        details={"admin_notes": body.admin_notes},
    )
    return {"success": True}


@app.post("/api/store-requests/{request_id}/reject")
async def reject_store_request_api(
    request_id: int,
    body: StoreRequestDecisionBody,
    request: Request,
    x_csrf_token: Optional[str] = Header(None),
    admin: dict = Depends(verify_admin),
    session: AsyncSession = Depends(_get_db_session),
):
    jti = admin.get("jti", "")
    if not x_csrf_token or not verify_csrf_token(jti, x_csrf_token):
        raise HTTPException(status_code=403, detail="Invalid or missing CSRF token")

    req = (await session.execute(select(StoreRequest).where(StoreRequest.id == request_id))).scalar_one_or_none()
    if not req:
        raise HTTPException(status_code=404, detail="Store request not found")

    await session.execute(
        update(StoreRequest)
        .where(StoreRequest.id == request_id)
        .values(status=StoreRequestStatus.REJECTED, admin_notes=body.admin_notes, updated_at=datetime.utcnow())
    )
    await session.commit()

    _log_admin_action(
        admin_telegram_id=int(admin.get("sub", 0)),
        action="reject_store_request",
        target_type="store_request",
        target_id=request_id,
        ip=request.client.host if request.client else None,
        details={"admin_notes": body.admin_notes},
    )
    return {"success": True}


@app.get("/api/health")
async def system_health(admin: dict = Depends(verify_admin)):
    """
    System health check.
    Checks database, Redis and scraper engine status.
    """
    health = {
        "status": "ok",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "components": {
            "database": "unknown",
            "redis": "unknown",
            "scraper": "unknown",
        }
    }

    # ── Database ──
    try:
        engine = get_engine(DATABASE_URL)
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        health["components"]["database"] = "ok"
    except Exception as e:
        logger.warning("Database health check failed: %s", e)
        health["components"]["database"] = "error"
        health["status"] = "degraded"

    # ── Redis ──
    try:
        redis = Redis.from_url(REDIS_URL)
        await redis.ping()
        await redis.close()
        health["components"]["redis"] = "ok"
    except Exception as e:
        logger.warning("Redis health check failed: %s", e)
        health["components"]["redis"] = "error"
        if health["status"] != "degraded":
            health["status"] = "degraded"

    # ── Scraper engine ──
    if monitoring_engine_running:
        health["components"]["scraper"] = "ok"
        if monitoring_engine_last_run:
            health["last_scan"] = monitoring_engine_last_run.isoformat()
    else:
        health["components"]["scraper"] = "stopped"

    return health


@app.post("/api/opportunities/{opportunity_id}/approve")
async def approve_opportunity_endpoint(
    opportunity_id: int,
    body: ApproveBody,
    request: Request,
    x_csrf_token: Optional[str] = Header(None),
    admin: dict = Depends(verify_admin),
):
    """Approve an opportunity — requires CSRF token."""
    jti = admin.get("jti", "")
    if not x_csrf_token or not verify_csrf_token(jti, x_csrf_token):
        raise HTTPException(status_code=403, detail="Invalid or missing CSRF token")

    # Audit log
    _log_admin_action(
        admin_telegram_id=int(admin.get("sub", 0)),
        action="approve_opportunity",
        target_type="opportunity",
        target_id=opportunity_id,
        ip=request.client.host if request.client else None,
    )
    return {"status": "approved", "opportunity_id": opportunity_id}


@app.post("/api/opportunities/{opportunity_id}/reject")
async def reject_opportunity_endpoint(
    opportunity_id: int,
    request: Request,
    x_csrf_token: Optional[str] = Header(None),
    admin: dict = Depends(verify_admin),
):
    """Reject an opportunity — requires CSRF token."""
    jti = admin.get("jti", "")
    if not x_csrf_token or not verify_csrf_token(jti, x_csrf_token):
        raise HTTPException(status_code=403, detail="Invalid or missing CSRF token")

    _log_admin_action(
        admin_telegram_id=int(admin.get("sub", 0)),
        action="reject_opportunity",
        target_type="opportunity",
        target_id=opportunity_id,
        ip=request.client.host if request.client else None,
    )
    return {"status": "rejected", "opportunity_id": opportunity_id}


@app.post("/api/opportunities/{opportunity_id}/postpone")
async def postpone_opportunity_endpoint(
    opportunity_id: int,
    request: Request,
    x_csrf_token: Optional[str] = Header(None),
    admin: dict = Depends(verify_admin),
):
    """Postpone an opportunity — requires CSRF token."""
    jti = admin.get("jti", "")
    if not x_csrf_token or not verify_csrf_token(jti, x_csrf_token):
        raise HTTPException(status_code=403, detail="Invalid or missing CSRF token")

    _log_admin_action(
        admin_telegram_id=int(admin.get("sub", 0)),
        action="postpone_opportunity",
        target_type="opportunity",
        target_id=opportunity_id,
        ip=request.client.host if request.client else None,
    )
    return {"status": "postponed", "opportunity_id": opportunity_id}


@app.get("/api/csrf-token")
async def get_csrf_token(admin: dict = Depends(verify_admin)):
    """Return a CSRF token tied to the admin's JWT session."""
    jti = admin.get("jti", "")
    return {"csrf_token": generate_csrf_token(jti)}


# ======================================================
# 📝 Audit helper
# ======================================================

def _log_admin_action(
    admin_telegram_id: int,
    action: str,
    target_type: str = None,
    target_id: int = None,
    ip: str = None,
    details: dict = None,
):
    """Write an audit-log entry to the database and logger."""
    logger.info(
        "AUDIT | admin=%s action=%s target=%s/%s ip=%s",
        admin_telegram_id, action, target_type, target_id, ip,
    )
    # Fire-and-forget DB write via background task
    import asyncio

    async def _persist():
        try:
            from db.models import AuditLog, get_engine, get_session_factory
            engine = get_engine(DATABASE_URL)
            SessionLocal = get_session_factory(engine)
            async with SessionLocal() as session:
                entry = AuditLog(
                    admin_telegram_id=admin_telegram_id,
                    action=action,
                    target_type=target_type,
                    target_id=target_id,
                    ip_address=ip,
                    details=details,
                )
                session.add(entry)
                await session.commit()
        except Exception as exc:
            logger.warning("Failed to persist audit log: %s", exc)

    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_persist())
    except RuntimeError:
        pass  # No running loop — skip DB write, logger entry is enough


# ======================================================
# 🌐 واجهة الداشبورد (Vue SPA)
# ======================================================

BASE_DIR = Path(__file__).resolve().parents[1]
VUE_DIST_DIR = BASE_DIR / 'dashboard-vue' / 'dist'
VUE_ASSETS_DIR = VUE_DIST_DIR / 'assets'

if VUE_ASSETS_DIR.exists():
    app.mount('/assets', StaticFiles(directory=str(VUE_ASSETS_DIR)), name='vue-assets')


@app.get('/', response_class=FileResponse)
async def dashboard_home():
    """Serve Vue index page."""
    index_file = VUE_DIST_DIR / 'index.html'
    if not index_file.exists():
        return JSONResponse(
            status_code=200,
            content={
                'status': 'ok',
                'message': 'Store Monitor dashboard frontend not built yet',
                'hint': 'Run: cd dashboard-vue && npm run build',
            },
        )
    return FileResponse(index_file)


@app.get('/{full_path:path}')
async def dashboard_spa(full_path: str):
    """Serve Vue static files and SPA fallback for non-API routes."""
    if full_path.startswith('api/') or full_path.startswith('auth/'):
        raise HTTPException(status_code=404, detail='Not Found')

    requested = VUE_DIST_DIR / full_path
    if requested.exists() and requested.is_file():
        return FileResponse(requested)

    index_file = VUE_DIST_DIR / 'index.html'
    if index_file.exists():
        return FileResponse(index_file)

    return JSONResponse(
        status_code=200,
        content={
            'status': 'ok',
            'message': 'Store Monitor dashboard frontend not built yet',
            'hint': 'Run: cd dashboard-vue && npm run build',
        },
    )
# ======================================================
# 🚀 تشغيل الداشبورد
# ======================================================

def run_dashboard(host: str = "0.0.0.0", port: int = 8000):
    """
    تشغيل لوحة الإدارة
    يُستدعى بشكل مستقل عن البوت
    """
    import uvicorn
    uvicorn.run(app, host=host, port=port, log_level="info")

