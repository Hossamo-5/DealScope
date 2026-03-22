"""
Security tests for admin/dashboard.py
=======================================
Tests: unauthenticated → 401, expired JWT → 401, invalid input → 422,
       rate limiting → 429, sensitive-field filtering, CSRF, audit log.
"""

import time
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from jose import jwt

import admin.dashboard as dashboard
from auth.security import (
    ALGORITHM,
    _login_attempts,
    create_access_token,
    generate_csrf_token,
)
from config.settings import ADMIN_USER_IDS, SECRET_KEY

client = TestClient(dashboard.app, raise_server_exceptions=False)

VALID_ADMIN_ID = ADMIN_USER_IDS[0]  # 123456789


# ── Helpers ────────────────────────────────────────────

def _auth_header(telegram_id: int = None, expired: bool = False) -> dict:
    """Build an Authorization header with a valid or expired JWT."""
    tid = telegram_id or VALID_ADMIN_ID
    if expired:
        payload = {
            "sub": str(tid),
            "exp": datetime.now(timezone.utc) - timedelta(hours=1),
            "iat": datetime.now(timezone.utc) - timedelta(hours=9),
            "jti": "test-jti",
        }
        token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    else:
        token, _ = create_access_token(tid)
    return {"Authorization": f"Bearer {token}"}


# ── 1. Unauthenticated requests → 401 ─────────────────

@pytest.mark.parametrize("path", [
    "/api/stats",
    "/api/opportunities",
    "/api/users",
    "/api/stores",
    "/api/health",
    "/api/csrf-token",
])
def test_unauthenticated_returns_401(path):
    response = client.get(path)
    assert response.status_code == 401


def test_unauthenticated_post_approve_returns_401():
    response = client.post(
        "/api/opportunities/1/approve",
        json={},
    )
    assert response.status_code == 401


# ── 2. Expired JWT → 401 ──────────────────────────────

@pytest.mark.parametrize("path", [
    "/api/stats",
    "/api/users",
    "/api/health",
])
def test_expired_jwt_returns_401(path):
    response = client.get(path, headers=_auth_header(expired=True))
    assert response.status_code == 401


# ── 3. Invalid input → 422 ────────────────────────────

def test_invalid_opportunity_status_returns_422():
    response = client.get(
        "/api/opportunities?status=INVALID_XYZ",
        headers=_auth_header(),
    )
    assert response.status_code == 422


def test_negative_page_returns_422():
    response = client.get("/api/users?page=-1", headers=_auth_header())
    assert response.status_code == 422


def test_limit_over_max_returns_422():
    response = client.get("/api/users?limit=500", headers=_auth_header())
    assert response.status_code == 422


def test_limit_zero_returns_422():
    response = client.get("/api/opportunities?limit=0", headers=_auth_header())
    assert response.status_code == 422


def test_invalid_plan_filter_returns_422():
    response = client.get("/api/users?plan=hacker", headers=_auth_header())
    assert response.status_code == 422


# ── 4. Rate limiting on login → 429 ───────────────────

def test_login_rate_limit_returns_429():
    # Clear any prior state
    _login_attempts.clear()

    # Exhaust the rate limit budget (5 attempts)
    for _ in range(5):
        client.post("/auth/login", json={"telegram_id": 999999})

    # 6th attempt should be rate-limited
    response = client.post("/auth/login", json={"telegram_id": 999999})
    assert response.status_code == 429

    # Cleanup
    _login_attempts.clear()


# ── 5. Sensitive-field filtering ───────────────────────

def test_users_response_excludes_telegram_id():
    """The /api/users response must not leak telegram_id."""
    response = client.get("/api/users", headers=_auth_header())
    assert response.status_code == 200
    data = response.json()
    for user in data.get("users", []):
        assert "telegram_id" not in user


# ── 6. Login flow ─────────────────────────────────────

def test_login_valid_admin_returns_token():
    _login_attempts.clear()
    response = client.post(
        "/auth/login",
        json={"telegram_id": VALID_ADMIN_ID},
    )
    assert response.status_code == 200
    body = response.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"
    assert body["expires_in"] > 0
    _login_attempts.clear()


def test_login_invalid_id_returns_401():
    _login_attempts.clear()
    response = client.post(
        "/auth/login",
        json={"telegram_id": 0},
    )
    assert response.status_code == 401
    _login_attempts.clear()


# ── 7. CSRF protection on approve ─────────────────────

def test_approve_without_csrf_returns_403():
    response = client.post(
        "/api/opportunities/1/approve",
        json={},
        headers=_auth_header(),
    )
    assert response.status_code == 403


def test_approve_with_valid_csrf_succeeds():
    token, _ = create_access_token(VALID_ADMIN_ID)
    # Decode to get jti
    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    csrf = generate_csrf_token(payload["jti"])

    response = client.post(
        "/api/opportunities/1/approve",
        json={},
        headers={
            "Authorization": f"Bearer {token}",
            "X-CSRF-Token": csrf,
        },
    )
    assert response.status_code == 200
    assert response.json()["status"] == "approved"


# ── 8. Security headers ───────────────────────────────

def test_security_headers_present():
    response = client.get("/")
    h = response.headers
    assert h.get("x-frame-options") == "DENY"
    assert h.get("x-content-type-options") == "nosniff"
    assert "strict-transport-security" in h
    assert "content-security-policy" in h


# ── 9. Dashboard home still works ─────────────────────

def test_dashboard_home_returns_html():
    response = client.get("/")
    assert response.status_code == 200
    assert "Store Monitor" in response.text
    assert "login-section" in response.text


# ── 10. Valid auth on protected routes returns 200 ────

@pytest.mark.parametrize("path", [
    "/api/stats",
    "/api/opportunities",
    "/api/users",
    "/api/stores",
])
def test_authenticated_routes_return_200(path):
    response = client.get(path, headers=_auth_header())
    assert response.status_code == 200


def test_health_authenticated(monkeypatch):
    class _ConnCtx:
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def execute(self, _): return None

    class _Engine:
        def connect(self): return _ConnCtx()

    class _Redis:
        async def ping(self): return True
        async def close(self): return None

    monkeypatch.setattr(dashboard, "get_engine", lambda *_: _Engine())
    monkeypatch.setattr(dashboard.Redis, "from_url", lambda *_: _Redis())
    monkeypatch.setattr(dashboard, "monitoring_engine_running", True)
    monkeypatch.setattr(
        dashboard, "monitoring_engine_last_run", datetime.now(timezone.utc)
    )

    response = client.get("/api/health", headers=_auth_header())
    assert response.status_code == 200
    data = response.json()
    assert data["components"]["database"] == "ok"


# ── 11. Non-admin telegram_id in JWT → 401 ────────────

def test_non_admin_jwt_returns_401():
    # Create a token for an ID NOT in ADMIN_USER_IDS
    payload = {
        "sub": "9999",
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        "iat": datetime.now(timezone.utc),
        "jti": "fake",
    }
    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    response = client.get(
        "/api/stats",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 401
