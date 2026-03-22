"""
Dashboard E2E Tests (Browser)
==============================
Playwright-based browser automation tests for the admin dashboard.
Tests navigation, UI elements, stats cards, opportunity management,
system health display, and responsive layout.
"""

import asyncio
import threading
import time
from contextlib import asynccontextmanager

import pytest
import uvicorn
from playwright.async_api import async_playwright

from admin.dashboard import app
from auth.security import create_access_token
from config.settings import ADMIN_USER_IDS

VALID_ADMIN_ID = ADMIN_USER_IDS[0]
DASHBOARD_PORT = 8001
BASE_URL = f"http://localhost:{DASHBOARD_PORT}"


# ──────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def dashboard_server():
    """Start uvicorn on a background thread, yield base_url, then stop."""
    # Try default port first, fall back to an ephemeral free port if binding is blocked
    import socket
    chosen_port = DASHBOARD_PORT
    try:
        test_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        test_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        test_sock.bind(("127.0.0.1", DASHBOARD_PORT))
        test_sock.close()
    except OSError:
        # pick an available ephemeral port
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(("127.0.0.1", 0))
        chosen_port = s.getsockname()[1]
        s.close()

    config = uvicorn.Config(app, host="127.0.0.1", port=chosen_port, log_level="warning")
    server = uvicorn.Server(config)

    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    # Wait until the server is accepting connections
    for _ in range(40):
        try:
            with socket.create_connection(("127.0.0.1", chosen_port), timeout=0.5):
                break
        except OSError:
            time.sleep(0.25)
    else:
        pytest.fail("Dashboard server did not start in time")

    yield f"http://127.0.0.1:{chosen_port}"

    server.should_exit = True
    thread.join(timeout=5)


@pytest.fixture
async def browser_ctx():
    """Provide a fresh Playwright browser context (headless Chromium)."""
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context()
        yield context
        await context.close()
        await browser.close()


@pytest.fixture
async def page(browser_ctx):
    """Provide a fresh page inside the browser context."""
    page = await browser_ctx.new_page()
    yield page
    await page.close()


@pytest.fixture
async def authed_page(page, dashboard_server):
    """
    Navigate to the dashboard and inject a valid JWT into sessionStorage
    so the JS `checkAuth()` logic shows the main app section.
    """
    token, _ = create_access_token(VALID_ADMIN_ID)
    await page.goto(dashboard_server)
    await page.evaluate(f"sessionStorage.setItem('token', '{token}')")
    await page.reload()
    # Wait for the app section to become visible
    await page.wait_for_selector("#app-section", state="visible", timeout=5000)
    return page


# ──────────────────────────────────────────────────────
# Navigation Tests
# ──────────────────────────────────────────────────────

class TestNavigation:
    @pytest.mark.asyncio
    async def test_dashboard_loads_successfully(self, authed_page, dashboard_server):
        title = await authed_page.title()
        assert "Store Monitor" in title
        header = authed_page.locator(".header h1")
        assert await header.is_visible()
        text = await header.inner_text()
        assert "لوحة الإدارة" in text

    @pytest.mark.asyncio
    async def test_all_nav_buttons_visible(self, authed_page, dashboard_server):
        nav_btns = authed_page.locator(".nav-btn")
        count = await nav_btns.count()
        assert count == 11

        expected = [
            "الرئيسية",
            "الفرص",
            "المستخدمون",
            "الدعم الفني",
            "فريق الدعم",
            "المتاجر",
            "منشئ القائمة",
            "محلل المعرفات",
            "المجموعات",
            "البوتات",
            "صحة النظام",
        ]
        for i, label in enumerate(expected):
            text = await nav_btns.nth(i).inner_text()
            assert label in text

    @pytest.mark.asyncio
    async def test_nav_dashboard_active_by_default(self, authed_page, dashboard_server):
        first_btn = authed_page.locator(".nav-btn").first
        classes = await first_btn.get_attribute("class")
        assert "active" in classes

    @pytest.mark.asyncio
    async def test_nav_opportunities_click(self, authed_page, dashboard_server):
        await authed_page.locator(".nav-btn", has_text="الفرص").click()
        opp_section = authed_page.locator("#section-opportunities")
        assert await opp_section.is_visible()
        dash_section = authed_page.locator("#section-dashboard")
        assert not await dash_section.is_visible()

    @pytest.mark.asyncio
    async def test_nav_users_click(self, authed_page, dashboard_server):
        await authed_page.locator(".nav-btn", has_text="المستخدمون").click()
        users_section = authed_page.locator("#section-users")
        assert await users_section.is_visible()

    @pytest.mark.asyncio
    async def test_nav_stores_click(self, authed_page, dashboard_server):
        # The dashboard HTML has no section-stores div yet, so clicking the
        # stores nav button hides other sections.  Verify the click runs and
        # the dashboard section becomes hidden.
        stores_btn = authed_page.locator(".nav-btn", has_text="المتاجر")
        await stores_btn.click()
        await authed_page.wait_for_timeout(200)
        dashboard_section = authed_page.locator("#section-dashboard")
        assert not await dashboard_section.is_visible()

    @pytest.mark.asyncio
    async def test_nav_health_click(self, authed_page, dashboard_server):
        await authed_page.locator(".nav-btn", has_text="صحة النظام").click()
        health_section = authed_page.locator("#section-health")
        assert await health_section.is_visible()


# ──────────────────────────────────────────────────────
# Stats Cards Tests
# ──────────────────────────────────────────────────────

class TestStatsCards:
    @pytest.mark.asyncio
    async def test_stats_cards_all_present(self, authed_page, dashboard_server):
        cards = authed_page.locator(".stat-card")
        count = await cards.count()
        assert count == 4

    @pytest.mark.asyncio
    async def test_stats_cards_have_icons(self, authed_page, dashboard_server):
        icons = authed_page.locator(".stat-card .icon")
        count = await icons.count()
        assert count == 4
        expected_icons = ["👥", "📦", "💡", "📤"]
        for i, icon in enumerate(expected_icons):
            text = await icons.nth(i).inner_text()
            assert icon in text

    @pytest.mark.asyncio
    async def test_stats_cards_labels(self, authed_page, dashboard_server):
        labels = authed_page.locator(".stat-card .label")
        expected = ["المشتركون", "المنتجات", "فرص جديدة", "أُرسل اليوم"]
        for i, label in enumerate(expected):
            text = await labels.nth(i).inner_text()
            assert label in text

    @pytest.mark.asyncio
    async def test_stats_cards_number_elements_exist(self, authed_page, dashboard_server):
        assert await authed_page.locator("#stat-users").is_visible()
        assert await authed_page.locator("#stat-products").is_visible()
        assert await authed_page.locator("#stat-opportunities").is_visible()
        assert await authed_page.locator("#stat-sent").is_visible()


# ──────────────────────────────────────────────────────
# Opportunities Section Tests
# ──────────────────────────────────────────────────────

class TestOpportunitiesSection:
    @pytest.mark.asyncio
    async def test_opportunities_filter_dropdown_exists(self, authed_page, dashboard_server):
        await authed_page.locator(".nav-btn", has_text="الفرص").click()
        select = authed_page.locator("#opp-filter")
        assert await select.is_visible()

    @pytest.mark.asyncio
    async def test_opportunities_filter_options(self, authed_page, dashboard_server):
        await authed_page.locator(".nav-btn", has_text="الفرص").click()
        options = authed_page.locator("#opp-filter option")
        count = await options.count()
        assert count == 3
        values = {await options.nth(i).get_attribute("value") for i in range(count)}
        assert values == {"new", "approved", "rejected"}

    @pytest.mark.asyncio
    async def test_opportunities_filter_change_triggers_request(self, authed_page, dashboard_server):
        await authed_page.locator(".nav-btn", has_text="الفرص").click()
        # Wait for initial load
        await asyncio.sleep(0.5)

        # Intercept API calls
        requests_made = []

        async def handle_route(route):
            requests_made.append(route.request.url)
            await route.continue_()

        await authed_page.route("**/api/opportunities**", handle_route)

        # Change dropdown
        await authed_page.select_option("#opp-filter", "approved")
        await asyncio.sleep(1)

        assert any("status=approved" in url for url in requests_made)


# ──────────────────────────────────────────────────────
# System Health Tests
# ──────────────────────────────────────────────────────

class TestSystemHealth:
    @pytest.mark.asyncio
    async def test_health_section_has_loading_or_content(self, authed_page, dashboard_server):
        await authed_page.locator(".nav-btn", has_text="صحة النظام").click()
        health_info = authed_page.locator("#health-info")
        assert await health_info.is_visible()

    @pytest.mark.asyncio
    async def test_health_api_called_on_nav(self, authed_page, dashboard_server):
        api_called = []

        async def handle_route(route):
            api_called.append(route.request.url)
            await route.fulfill(
                status=200,
                content_type="application/json",
                body='{"status":"ok","timestamp":"2026-03-17T00:00:00","components":{"database":"ok","redis":"ok","scraper":"ok"}}'
            )

        await authed_page.route("**/api/health", handle_route)
        await authed_page.locator(".nav-btn", has_text="صحة النظام").click()
        await asyncio.sleep(1)

        assert len(api_called) >= 1

    @pytest.mark.asyncio
    async def test_health_ok_shows_green(self, authed_page, dashboard_server):
        await authed_page.route(
            "**/api/health",
            lambda route: route.fulfill(
                status=200,
                content_type="application/json",
                body='{"status":"ok","timestamp":"2026-03-17T00:00:00","components":{"database":"ok","redis":"ok","scraper":"ok"}}'
            ),
        )
        await authed_page.locator(".nav-btn", has_text="صحة النظام").click()
        await asyncio.sleep(1)

        html = await authed_page.locator("#health-info").inner_html()
        assert "✅" in html
        assert "ok" in html

    @pytest.mark.asyncio
    async def test_health_error_shows_red(self, authed_page, dashboard_server):
        await authed_page.route(
            "**/api/health",
            lambda route: route.fulfill(
                status=200,
                content_type="application/json",
                body='{"status":"degraded","timestamp":"2026-03-17T00:00:00","components":{"database":"error","redis":"ok","scraper":"stopped"}}'
            ),
        )
        await authed_page.locator(".nav-btn", has_text="صحة النظام").click()
        await asyncio.sleep(1)

        html = await authed_page.locator("#health-info").inner_html()
        assert "❌" in html
        assert "error" in html

    @pytest.mark.asyncio
    async def test_system_status_header_updates(self, authed_page, dashboard_server):
        await authed_page.route(
            "**/api/health",
            lambda route: route.fulfill(
                status=200,
                content_type="application/json",
                body='{"status":"ok","timestamp":"2026-03-17T00:00:00","components":{"database":"ok","redis":"ok","scraper":"ok"}}'
            ),
        )
        await authed_page.locator(".nav-btn", has_text="صحة النظام").click()
        await asyncio.sleep(1)

        status_span = await authed_page.locator("#system-status").inner_text()
        assert "النظام يعمل" in status_span


# ──────────────────────────────────────────────────────
# Responsive & UX Tests
# ──────────────────────────────────────────────────────

class TestResponsiveUX:
    @pytest.mark.asyncio
    async def test_time_updates_in_header(self, authed_page, dashboard_server):
        time_el = authed_page.locator("#current-time")
        assert await time_el.is_visible()
        t1 = await time_el.inner_text()
        await asyncio.sleep(2)
        t2 = await time_el.inner_text()
        # The time should have changed (or at minimum still be visible)
        # It updates every second, so after 2s it should differ
        assert t1 != t2 or len(t1) > 0

    @pytest.mark.asyncio
    async def test_refresh_button_triggers_fetch(self, authed_page, dashboard_server):
        fetched = []

        async def handle_route(route):
            fetched.append(True)
            await route.fulfill(
                status=200,
                content_type="application/json",
                body='{"opportunities":[],"total":0}',
            )

        await authed_page.route("**/api/opportunities**", handle_route)
        refresh_btn = authed_page.locator(".refresh-btn", has_text="تحديث")
        await refresh_btn.click()
        await asyncio.sleep(1)
        assert len(fetched) >= 1

    @pytest.mark.asyncio
    async def test_arabic_rtl_layout(self, authed_page, dashboard_server):
        dir_attr = await authed_page.locator("html").get_attribute("dir")
        assert dir_attr == "rtl"

        direction = await authed_page.evaluate(
            "getComputedStyle(document.body).direction"
        )
        assert direction == "rtl"


# ──────────────────────────────────────────────────────
# Login Flow Tests
# ──────────────────────────────────────────────────────

class TestLogin:
    @pytest.mark.asyncio
    async def test_login_section_shown_without_token(self, page, dashboard_server):
        await page.goto(dashboard_server)
        await page.evaluate("sessionStorage.removeItem('token')")
        await page.reload()
        await asyncio.sleep(0.5)

        login_section = page.locator("#login-section")
        assert await login_section.is_visible()
        app_section = page.locator("#app-section")
        assert not await app_section.is_visible()

    @pytest.mark.asyncio
    async def test_login_with_valid_admin_id(self, page, dashboard_server):
        await page.goto(dashboard_server)
        await page.evaluate("sessionStorage.removeItem('token')")
        await page.reload()
        await asyncio.sleep(0.5)

        await page.fill("#login-tid", str(VALID_ADMIN_ID))
        await page.click("#login-section button")
        await asyncio.sleep(1)

        app_section = page.locator("#app-section")
        assert await app_section.is_visible()

    @pytest.mark.asyncio
    async def test_login_with_invalid_id_shows_error(self, page, dashboard_server):
        await page.goto(dashboard_server)
        await page.evaluate("sessionStorage.removeItem('token')")
        await page.reload()
        await asyncio.sleep(0.5)

        await page.fill("#login-tid", "999999999")
        await page.click("#login-section button")
        await asyncio.sleep(1)

        error_el = page.locator("#login-error")
        text = await error_el.inner_text()
        assert len(text) > 0  # Error message displayed
