"""
Security Middleware
===================
HSTS, security headers, CORS lockdown, request-size limit, global exception handler.
"""

import logging
import os

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)

# Max request body size (1 MB)
MAX_BODY_SIZE = 1 * 1024 * 1024  # 1 048 576 bytes

# Allowed CORS origin — override via env var in production
ADMIN_CORS_ORIGIN = os.getenv("ADMIN_CORS_ORIGIN", "")


# ── Security-headers middleware ────────────────────────

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Inject OWASP-recommended response headers on every response."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; img-src 'self' data:;"
        )
        response.headers["Strict-Transport-Security"] = (
            "max-age=63072000; includeSubDomains; preload"
        )
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=()"
        )
        return response


# ── Request-size limiter middleware ────────────────────

class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """Reject requests whose Content-Length exceeds MAX_BODY_SIZE."""

    async def dispatch(self, request: Request, call_next):
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > MAX_BODY_SIZE:
            return JSONResponse(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                content={"detail": "Request body too large (max 1 MB)"},
            )
        return await call_next(request)


# ── Global exception handler ──────────────────────────

async def global_exception_handler(request: Request, exc: Exception):
    """Never leak stack traces to the client."""
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"},
    )


# ── Wire everything onto the app ──────────────────────

def apply_security_middleware(app: FastAPI) -> None:
    """Call once after app creation to register all middleware & handlers."""

    # CORS — restrict to a single admin origin (or block entirely)
    allowed_origins = [ADMIN_CORS_ORIGIN] if ADMIN_CORS_ORIGIN else []
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["Authorization", "Content-Type", "X-CSRF-Token"],
    )

    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RequestSizeLimitMiddleware)

    # Global 500 handler — suppress stack traces
    app.add_exception_handler(Exception, global_exception_handler)
