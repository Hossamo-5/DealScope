"""
API Integration Tests
=====================
Full request/response cycle tests using httpx AsyncClient
against the real FastAPI app (no browser required).
Tests endpoint structure, validation, auth, pagination, and health.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from admin.dashboard import app
import admin.dashboard as dashboard
from auth.security import create_access_token
from config.settings import ADMIN_USER_IDS

VALID_ADMIN_ID = ADMIN_USER_IDS[0]


# ──────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────

def _auth_headers() -> dict:
    token, _ = create_access_token(VALID_ADMIN_ID)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def api_client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


# ──────────────────────────────────────────────────────
# Root / HTML Tests
# ──────────────────────────────────────────────────────

class TestRootEndpoint:
    @pytest.mark.asyncio
    async def test_get_root_returns_html(self, api_client):
        response = await api_client.get("/")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert "Store Monitor" in response.text

    @pytest.mark.asyncio
    async def test_root_contains_rtl_direction(self, api_client):
        response = await api_client.get("/")
        assert 'dir="rtl"' in response.text

    @pytest.mark.asyncio
    async def test_root_contains_login_section(self, api_client):
        response = await api_client.get("/")
        assert "login-section" in response.text


# ──────────────────────────────────────────────────────
# Stats Endpoint Tests
# ──────────────────────────────────────────────────────

class TestStatsEndpoint:
    @pytest.mark.asyncio
    async def test_stats_endpoint_structure(self, api_client):
        response = await api_client.get("/api/stats", headers=_auth_headers())
        assert response.status_code == 200
        data = response.json()
        assert "status" in data

    @pytest.mark.asyncio
    async def test_stats_endpoint_unauthenticated(self, api_client):
        response = await api_client.get("/api/stats")
        assert response.status_code == 401


# ──────────────────────────────────────────────────────
# Opportunities Endpoint Tests
# ──────────────────────────────────────────────────────

class TestOpportunitiesEndpoint:
    @pytest.mark.asyncio
    async def test_opportunities_endpoint_default(self, api_client):
        response = await api_client.get("/api/opportunities", headers=_auth_headers())
        assert response.status_code == 200
        data = response.json()
        assert "opportunities" in data
        assert isinstance(data["opportunities"], list)
        assert "total" in data

    @pytest.mark.asyncio
    async def test_opportunities_status_new(self, api_client):
        response = await api_client.get(
            "/api/opportunities?status=new", headers=_auth_headers()
        )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_opportunities_status_approved(self, api_client):
        response = await api_client.get(
            "/api/opportunities?status=approved", headers=_auth_headers()
        )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_opportunities_status_rejected(self, api_client):
        response = await api_client.get(
            "/api/opportunities?status=rejected", headers=_auth_headers()
        )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_opportunities_with_limit(self, api_client):
        response = await api_client.get(
            "/api/opportunities?limit=5", headers=_auth_headers()
        )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_opportunities_invalid_status_422(self, api_client):
        response = await api_client.get(
            "/api/opportunities?status=INVALID", headers=_auth_headers()
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_opportunities_limit_out_of_range(self, api_client):
        response = await api_client.get(
            "/api/opportunities?limit=999", headers=_auth_headers()
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_opportunities_negative_offset(self, api_client):
        response = await api_client.get(
            "/api/opportunities?offset=-1", headers=_auth_headers()
        )
        assert response.status_code == 422


# ──────────────────────────────────────────────────────
# Users Endpoint Tests
# ──────────────────────────────────────────────────────

class TestUsersEndpoint:
    @pytest.mark.asyncio
    async def test_users_endpoint_structure(self, api_client):
        response = await api_client.get("/api/users", headers=_auth_headers())
        assert response.status_code == 200
        data = response.json()
        assert "users" in data
        assert "total" in data
        assert "page" in data

    @pytest.mark.asyncio
    async def test_users_pagination(self, api_client):
        response = await api_client.get(
            "/api/users?page=1&limit=10", headers=_auth_headers()
        )
        assert response.status_code == 200
        assert response.json()["page"] == 1

    @pytest.mark.asyncio
    async def test_users_page_2(self, api_client):
        response = await api_client.get(
            "/api/users?page=2", headers=_auth_headers()
        )
        assert response.status_code == 200
        assert response.json()["page"] == 2

    @pytest.mark.asyncio
    async def test_users_invalid_plan_filter(self, api_client):
        response = await api_client.get(
            "/api/users?plan=platinum", headers=_auth_headers()
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_users_valid_plan_filter(self, api_client):
        response = await api_client.get(
            "/api/users?plan=free", headers=_auth_headers()
        )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_users_page_zero_invalid(self, api_client):
        response = await api_client.get(
            "/api/users?page=0", headers=_auth_headers()
        )
        assert response.status_code == 422


# ──────────────────────────────────────────────────────
# Stores Endpoint Tests
# ──────────────────────────────────────────────────────

class TestStoresEndpoint:
    @pytest.mark.asyncio
    async def test_stores_endpoint(self, api_client):
        response = await api_client.get("/api/stores", headers=_auth_headers())
        assert response.status_code == 200
        assert "stores" in response.json()


# ──────────────────────────────────────────────────────
# Health Endpoint Tests
# ──────────────────────────────────────────────────────

class TestHealthEndpoint:
    @pytest.mark.asyncio
    async def test_health_endpoint_structure(self, api_client, monkeypatch):
        # Stub external dependencies so the health endpoint succeeds
        class _ConnCtx:
            async def __aenter__(self):
                return self
            async def __aexit__(self, *a):
                return False
            async def execute(self, _):
                return None

        class _Engine:
            def connect(self):
                return _ConnCtx()

        class _Redis:
            async def ping(self):
                return True
            async def close(self):
                return None

        monkeypatch.setattr(dashboard, "get_engine", lambda *_: _Engine())
        monkeypatch.setattr(dashboard.Redis, "from_url", lambda *_: _Redis())
        monkeypatch.setattr(dashboard, "monitoring_engine_running", True)
        monkeypatch.setattr(
            dashboard,
            "monitoring_engine_last_run",
            datetime.now(timezone.utc),
        )

        response = await api_client.get("/api/health", headers=_auth_headers())
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "timestamp" in data
        assert "components" in data
        comps = data["components"]
        assert "database" in comps
        assert "redis" in comps
        assert "scraper" in comps

    @pytest.mark.asyncio
    async def test_health_timestamp_is_valid_iso(self, api_client, monkeypatch):
        class _ConnCtx:
            async def __aenter__(self):
                return self
            async def __aexit__(self, *a):
                return False
            async def execute(self, _):
                return None

        class _Engine:
            def connect(self):
                return _ConnCtx()

        monkeypatch.setattr(dashboard, "get_engine", lambda *_: _Engine())
        monkeypatch.setattr(dashboard.Redis, "from_url", lambda *_: AsyncMock())
        monkeypatch.setattr(dashboard, "monitoring_engine_running", True)
        monkeypatch.setattr(
            dashboard,
            "monitoring_engine_last_run",
            datetime.now(timezone.utc),
        )

        response = await api_client.get("/api/health", headers=_auth_headers())
        ts = response.json()["timestamp"]
        # Must parse without error
        datetime.fromisoformat(ts)


# ──────────────────────────────────────────────────────
# 404 and Edge Cases
# ──────────────────────────────────────────────────────

class TestEdgeCases:
    @pytest.mark.asyncio
    async def test_invalid_endpoint_returns_404(self, api_client):
        response = await api_client.get(
            "/api/nonexistent", headers=_auth_headers()
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_response_time_under_500ms(self, api_client, monkeypatch):
        class _ConnCtx:
            async def __aenter__(self):
                return self
            async def __aexit__(self, *a):
                return False
            async def execute(self, _):
                return None

        class _Engine:
            def connect(self):
                return _ConnCtx()

        monkeypatch.setattr(dashboard, "get_engine", lambda *_: _Engine())
        monkeypatch.setattr(dashboard.Redis, "from_url", lambda *_: AsyncMock())

        import time as _time
        start = _time.perf_counter()
        response = await api_client.get("/api/health", headers=_auth_headers())
        elapsed_ms = (_time.perf_counter() - start) * 1000
        assert response.status_code == 200
        assert elapsed_ms < 500, f"Response took {elapsed_ms:.0f}ms, expected <500ms"
