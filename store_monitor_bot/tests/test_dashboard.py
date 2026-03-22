from datetime import datetime, timezone
from unittest.mock import MagicMock
from unittest.mock import AsyncMock
import pytest

from fastapi.testclient import TestClient

import admin.dashboard as dashboard
from auth.security import create_access_token
from config.settings import ADMIN_USER_IDS

client = TestClient(dashboard.app, raise_server_exceptions=False)

VALID_ADMIN_ID = ADMIN_USER_IDS[0]


def _auth():
    token, _ = create_access_token(VALID_ADMIN_ID)
    return {"Authorization": f"Bearer {token}"}


def test_dashboard_home_returns_200():
    response = client.get("/")
    assert response.status_code == 200
    assert "Store Monitor" in response.text


def test_api_stats_returns_ok():
    response = client.get("/api/stats", headers=_auth())
    assert response.status_code == 200
    assert "status" in response.json()


def test_api_opportunities_default_params():
    response = client.get("/api/opportunities", headers=_auth())
    assert response.status_code == 200
    data = response.json()
    assert "opportunities" in data
    assert "total" in data


def test_api_opportunities_with_status_filter():
    response = client.get("/api/opportunities?status=approved", headers=_auth())
    assert response.status_code == 200


def test_api_opportunities_invalid_status():
    response = client.get("/api/opportunities?status=invalid_xyz", headers=_auth())
    assert response.status_code == 422


def test_api_users_returns_paginated():
    response = client.get("/api/users", headers=_auth())
    assert response.status_code == 200
    data = response.json()
    assert "users" in data
    assert "total" in data
    assert "page" in data


def test_api_users_with_page_param():
    response = client.get("/api/users?page=2&limit=10", headers=_auth())
    assert response.status_code == 200
    assert response.json()["page"] == 2


def test_api_stores_returns_list():
    response = client.get("/api/stores", headers=_auth())
    assert response.status_code == 200
    assert "stores" in response.json()


def test_api_health_returns_components(monkeypatch):
    class _ConnCtx:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
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
    monkeypatch.setattr(dashboard, "monitoring_engine_last_run", datetime.now(timezone.utc))

    response = client.get("/api/health", headers=_auth())
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "timestamp" in data
    assert "components" in data


def test_api_health_has_all_components(monkeypatch):
    class _ConnCtx:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def execute(self, _):
            return None

    class _Engine:
        def connect(self):
            return _ConnCtx()

    mock_redis = AsyncMock()
    monkeypatch.setattr(dashboard, "get_engine", lambda *_: _Engine())
    monkeypatch.setattr(dashboard.Redis, "from_url", lambda *_: mock_redis)

    response = client.get("/api/health", headers=_auth())
    components = response.json()["components"]
    assert "database" in components
    assert "redis" in components
    assert "scraper" in components


@pytest.mark.asyncio
async def test_verify_admin_rejects_unauthenticated():
    """verify_admin is now a real JWT check — no token → 401."""
    response = client.get("/api/stats")
    assert response.status_code == 401


def test_api_health_degraded_paths(monkeypatch):
    def _raise_engine(*_):
        raise RuntimeError("db down")

    class _Redis:
        async def ping(self):
            raise RuntimeError("redis down")

        async def close(self):
            return None

    monkeypatch.setattr(dashboard, "get_engine", _raise_engine)
    monkeypatch.setattr(dashboard.Redis, "from_url", lambda *_: _Redis())
    monkeypatch.setattr(dashboard, "monitoring_engine_running", False)

    response = client.get("/api/health", headers=_auth())
    data = response.json()
    assert data["status"] == "degraded"
    assert data["components"]["scraper"] == "stopped"


def test_run_dashboard_calls_uvicorn(monkeypatch):
    run_mock = MagicMock()
    monkeypatch.setattr("uvicorn.run", run_mock)

    dashboard.run_dashboard(host="127.0.0.1", port=9001)

    run_mock.assert_called_once()