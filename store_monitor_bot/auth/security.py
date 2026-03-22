"""
JWT Authentication & Authorization Module
==========================================
Handles admin login, token creation/validation, and CSRF protection.
"""

import hashlib
import hmac
import logging
import secrets
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
import math
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from config.settings import ADMIN_USER_IDS, SECRET_KEY, DATABASE_URL
from db.models import AdminUser, get_engine, get_session_factory

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 8
MIN_SECRET_KEY_LENGTH = 32

# ── Rate-limit state (per-process; use Redis for multi-worker) ─
_login_attempts: dict[str, list[float]] = defaultdict(list)
RATE_LIMIT_WINDOW = 60  # seconds
RATE_LIMIT_MAX = 5       # attempts per window
ACCOUNT_LOCK_MINUTES = 15

ENGINE = get_engine(DATABASE_URL)
SESSION_FACTORY = get_session_factory(ENGINE)


# ── Pydantic schemas ──────────────────────────────────
class LoginRequest(BaseModel):
    telegram_id: Optional[int] = Field(default=None, description="Admin Telegram user ID")
    email: Optional[str] = Field(default=None)
    phone: Optional[str] = Field(default=None)
    password: Optional[str] = Field(default=None)

    @model_validator(mode="after")
    def validate_identifier(self):
        if self.telegram_id is None and not self.email and not self.phone:
            raise ValueError("A login identifier is required")
        return self


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


# ── Helpers ────────────────────────────────────────────

def _validate_secret_key() -> None:
    """Raise on startup if SECRET_KEY is weak."""
    if len(SECRET_KEY) < MIN_SECRET_KEY_LENGTH:
        raise RuntimeError(
            f"SECRET_KEY must be at least {MIN_SECRET_KEY_LENGTH} characters. "
            "Set a strong random value in your .env file."
        )
    _known_defaults = {
        "CHANGE_THIS_TO_A_RANDOM_SECRET_KEY_IN_PRODUCTION",
        "change_this_to_a_very_long_random_secret_key_in_production",
    }
    if SECRET_KEY.strip() in _known_defaults:
        raise RuntimeError(
            "SECRET_KEY is still set to the default placeholder. "
            "Generate a strong random value with: python -c \"import secrets; print(secrets.token_urlsafe(64))\""
        )


def _is_rate_limited(client_ip: str) -> bool:
    """Return True if the IP exceeded the login attempt threshold."""
    now = time.monotonic()
    window = _login_attempts[client_ip]
    # Prune old entries
    _login_attempts[client_ip] = [t for t in window if now - t < RATE_LIMIT_WINDOW]
    return len(_login_attempts[client_ip]) >= RATE_LIMIT_MAX


def _record_attempt(client_ip: str) -> None:
    _login_attempts[client_ip].append(time.monotonic())


def create_access_token(telegram_id: int) -> tuple[str, int]:
    """Create a signed JWT for an authenticated admin."""
    expire = datetime.now(timezone.utc) + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    expires_in = int(ACCESS_TOKEN_EXPIRE_HOURS * 3600)
    payload = {
        "sub": str(telegram_id),
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "jti": secrets.token_hex(16),
    }
    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    return token, expires_in


def decode_access_token(token: str) -> dict:
    """Decode and validate a JWT.  Raises JWTError on failure."""
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])


# ── CSRF ───────────────────────────────────────────────

def generate_csrf_token(session_id: str) -> str:
    """HMAC-based CSRF token tied to the caller session/JWT jti."""
    return hmac.new(
        SECRET_KEY.encode(), session_id.encode(), hashlib.sha256
    ).hexdigest()


def verify_csrf_token(session_id: str, token: str) -> bool:
    expected = generate_csrf_token(session_id)
    return hmac.compare_digest(expected, token)


# ── FastAPI dependencies ───────────────────────────────

_bearer_scheme = HTTPBearer(auto_error=False)


async def verify_admin(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
) -> dict:
    """
    Dependency that protects API routes.
    Returns the decoded JWT payload on success, raises 401 otherwise.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = decode_access_token(credentials.credentials)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    telegram_id = int(payload.get("sub", 0))
    if telegram_id not in ADMIN_USER_IDS and not await _is_admin_user_telegram(telegram_id):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not an authorized admin",
        )

    return payload


# ── Login logic (called from dashboard router) ─────────

async def authenticate_admin(request: Request, body: LoginRequest, session: Optional[AsyncSession] = None) -> TokenResponse:
    """Validate credentials and return a JWT, enforcing rate limits."""
    client_ip = request.client.host if request.client else "unknown"

    # Rate-limit check
    if _is_rate_limited(client_ip):
        logger.warning("Rate-limited login attempt from %s", client_ip)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts. Try again later.",
        )

    _record_attempt(client_ip)

    managed_session = session is None
    if managed_session:
        session_ctx = SESSION_FACTORY()
        session = await session_ctx.__aenter__()

    try:
        # Legacy fallback: allow known static admins to login with telegram_id only.
        if body.telegram_id and body.telegram_id in ADMIN_USER_IDS and not body.password:
            token, expires_in = create_access_token(body.telegram_id)
            logger.info("Admin login successful (legacy): telegram_id=%s", body.telegram_id)
            return TokenResponse(access_token=token, token_type="bearer", expires_in=expires_in)

        admin_user = await _find_admin_user(session, body)
        if not admin_user:
            if body.telegram_id is not None:
                detail = "لا يوجد حساب مرتبط بهذا المعرف"
            else:
                detail = "معرف تيليغرام أو كلمة المرور غير صحيحة"
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)

        now = datetime.utcnow()
        if admin_user.locked_until and admin_user.locked_until > now:
            minutes = max(1, math.ceil((admin_user.locked_until - now).total_seconds() / 60))
            raise HTTPException(
                status_code=status.HTTP_423_LOCKED,
                detail=f"الحساب مقفل، حاول بعد {minutes} دقيقة",
            )

        if not body.password:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="معرف تيليغرام أو كلمة المرور غير صحيحة",
            )

        if not _verify_password(body.password, admin_user.password_hash):
            admin_user.failed_attempts = int(admin_user.failed_attempts or 0) + 1
            if admin_user.failed_attempts >= RATE_LIMIT_MAX:
                admin_user.locked_until = now + timedelta(minutes=ACCOUNT_LOCK_MINUTES)
                await session.commit()
                raise HTTPException(
                    status_code=status.HTTP_423_LOCKED,
                    detail=f"الحساب مقفل، حاول بعد {ACCOUNT_LOCK_MINUTES} دقيقة",
                )
            await session.commit()
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="معرف تيليغرام أو كلمة المرور غير صحيحة",
            )

        if not admin_user.telegram_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="لا يوجد حساب مرتبط بهذا المعرف",
            )

        admin_user.failed_attempts = 0
        admin_user.locked_until = None
        await session.commit()

        token, expires_in = create_access_token(int(admin_user.telegram_id))
        logger.info("Admin login successful: telegram_id=%s", admin_user.telegram_id)
    finally:
        if managed_session:
            await session_ctx.__aexit__(None, None, None)

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=expires_in,
    )


async def _find_admin_user(session: AsyncSession, body: LoginRequest) -> Optional[AdminUser]:
    try:
        if body.telegram_id is not None:
            result = await session.execute(
                select(AdminUser).where(AdminUser.telegram_id == body.telegram_id, AdminUser.is_active == True)
            )
            return result.scalar_one_or_none()
        if body.email:
            result = await session.execute(
                select(AdminUser).where(AdminUser.email == body.email, AdminUser.is_active == True)
            )
            return result.scalar_one_or_none()
        if body.phone:
            result = await session.execute(
                select(AdminUser).where(AdminUser.phone == body.phone, AdminUser.is_active == True)
            )
            return result.scalar_one_or_none()
        return None
    except SQLAlchemyError:
        return None


async def _is_admin_user_telegram(telegram_id: int) -> bool:
    try:
        async with SESSION_FACTORY() as session:
            result = await session.execute(
                select(AdminUser.id).where(AdminUser.telegram_id == telegram_id, AdminUser.is_active == True)
            )
            return result.scalar_one_or_none() is not None
    except SQLAlchemyError:
        return False


def _verify_password(password: str, password_hash: str) -> bool:
    try:
        import bcrypt

        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except Exception:
        return False
