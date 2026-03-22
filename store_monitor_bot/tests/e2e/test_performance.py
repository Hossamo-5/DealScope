"""
Performance Tests
==================
Benchmarks for dashboard response times, API throughput,
opportunity scoring, and connector selection speed.
"""

import asyncio
import time

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock

from httpx import ASGITransport, AsyncClient

from admin.dashboard import app
import admin.dashboard as dashboard
from auth.security import create_access_token
from config.settings import ADMIN_USER_IDS
from core.monitor import OpportunityScorer
from core.connectors.generic import ConnectorManager

VALID_ADMIN_ID = ADMIN_USER_IDS[0]


def _auth_headers() -> dict:
    token, _ = create_access_token(VALID_ADMIN_ID)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def api_client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


# ──────────────────────────────────────────────────────
# Dashboard Load Time
# ──────────────────────────────────────────────────────

class TestDashboardPerformance:
    @pytest.mark.asyncio
    async def test_dashboard_loads_under_1_second(self, api_client):
        start = time.perf_counter()
        response = await api_client.get("/")
        elapsed_ms = (time.perf_counter() - start) * 1000

        assert response.status_code == 200
        assert elapsed_ms < 1000, f"Dashboard load took {elapsed_ms:.0f}ms, expected <1000ms"

    @pytest.mark.asyncio
    async def test_dashboard_html_size_reasonable(self, api_client):
        response = await api_client.get("/")
        # The dashboard is a single HTML page; should be <500KB
        assert len(response.content) < 500 * 1024


# ──────────────────────────────────────────────────────
# API Endpoint Response Times
# ──────────────────────────────────────────────────────

class TestAPIResponseTimes:
    @pytest.mark.asyncio
    async def test_api_endpoints_response_times(self, api_client, monkeypatch):
        """All API endpoints should respond in under 200ms."""
        # Stub health dependencies
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

        endpoints = [
            "/api/stats",
            "/api/opportunities",
            "/api/users",
            "/api/stores",
            "/api/health",
        ]

        headers = _auth_headers()
        report = []

        for endpoint in endpoints:
            start = time.perf_counter()
            response = await api_client.get(endpoint, headers=headers)
            elapsed_ms = (time.perf_counter() - start) * 1000

            report.append((endpoint, elapsed_ms, response.status_code))
            assert response.status_code == 200, f"{endpoint} returned {response.status_code}"
            assert elapsed_ms < 200, f"{endpoint} took {elapsed_ms:.0f}ms, expected <200ms"

    @pytest.mark.asyncio
    async def test_root_response_under_200ms(self, api_client):
        start = time.perf_counter()
        response = await api_client.get("/")
        elapsed_ms = (time.perf_counter() - start) * 1000

        assert response.status_code == 200
        assert elapsed_ms < 200, f"/ took {elapsed_ms:.0f}ms"


# ──────────────────────────────────────────────────────
# Concurrent API Requests
# ──────────────────────────────────────────────────────

class TestConcurrentRequests:
    @pytest.mark.asyncio
    async def test_concurrent_api_requests(self, api_client, monkeypatch):
        """Send 20 simultaneous requests to /api/stats — all should return 200."""
        headers = _auth_headers()

        async def single_request():
            start = time.perf_counter()
            response = await api_client.get("/api/stats", headers=headers)
            elapsed_ms = (time.perf_counter() - start) * 1000
            return response.status_code, elapsed_ms

        results = await asyncio.gather(*[single_request() for _ in range(20)])

        for status, elapsed_ms in results:
            assert status == 200
            assert elapsed_ms < 1000, f"Request took {elapsed_ms:.0f}ms, expected <1000ms"

    @pytest.mark.asyncio
    async def test_concurrent_root_requests(self, api_client):
        """20 parallel root requests should all succeed."""
        async def fetch():
            return await api_client.get("/")

        results = await asyncio.gather(*[fetch() for _ in range(20)])
        assert all(r.status_code == 200 for r in results)


# ──────────────────────────────────────────────────────
# Opportunity Scorer Performance
# ──────────────────────────────────────────────────────

class TestScorerPerformance:
    def test_opportunity_scorer_performance(self):
        """Run calculate_score() 10,000 times — should complete in <1s."""
        scorer = OpportunityScorer()
        product_data = {
            "rating": 4.5,
            "review_count": 500,
            "in_stock": True,
            "lowest_price": 80.0,
        }

        start = time.perf_counter()
        for _ in range(10_000):
            scorer.calculate_score(product_data, old_price=100.0, new_price=70.0)
        elapsed = time.perf_counter() - start

        assert elapsed < 1.0, f"10k scores took {elapsed:.2f}s, expected <1s"

    def test_scorer_consistency(self):
        """Same inputs always produce the same score."""
        scorer = OpportunityScorer()
        data = {"rating": 4.0, "review_count": 100, "in_stock": True, "lowest_price": 50.0}
        scores = {scorer.calculate_score(data, 100.0, 50.0) for _ in range(100)}
        assert len(scores) == 1

    def test_get_score_label_performance(self):
        scorer = OpportunityScorer()
        start = time.perf_counter()
        for i in range(10_000):
            scorer.get_score_label(float(i % 100))
        elapsed = time.perf_counter() - start
        assert elapsed < 1.0


# ──────────────────────────────────────────────────────
# Connector Manager Selection Speed
# ──────────────────────────────────────────────────────

class TestConnectorManagerPerformance:
    def test_detect_store_type_performance(self):
        """Call detect_store_type() 1,000 times — should complete in <100ms."""
        urls = [
            "https://www.amazon.sa/dp/B08L5TNJHG",
            "https://mystore.com/products/fancy-widget",
            "https://shop.example.com/product/12345",
            "https://www.noon.com/deals/phone",
            "https://www.extra.com/cameras",
        ]

        start = time.perf_counter()
        for i in range(1_000):
            ConnectorManager.detect_store_type(urls[i % len(urls)])
        elapsed_ms = (time.perf_counter() - start) * 1000

        assert elapsed_ms < 100, f"1k detections took {elapsed_ms:.0f}ms, expected <100ms"

    def test_detect_store_type_correctness(self):
        """Verify correct store type detection."""
        assert ConnectorManager.detect_store_type("https://amazon.sa/dp/B123") == "amazon"
        assert ConnectorManager.detect_store_type("https://store.com/products/item") == "shopify"
        assert ConnectorManager.detect_store_type("https://shop.com/product/item") == "woocommerce"
        assert ConnectorManager.detect_store_type("https://www.noon.com/deals") == "custom"


# ──────────────────────────────────────────────────────
# Auth Token Creation Performance
# ──────────────────────────────────────────────────────

class TestAuthPerformance:
    def test_jwt_creation_speed(self):
        """Create 1000 JWT tokens in <1s."""
        start = time.perf_counter()
        for _ in range(1_000):
            create_access_token(VALID_ADMIN_ID)
        elapsed = time.perf_counter() - start
        assert elapsed < 1.0, f"1k tokens took {elapsed:.2f}s"
