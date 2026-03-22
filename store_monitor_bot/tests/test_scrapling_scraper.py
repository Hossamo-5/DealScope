"""Unit tests for Scrapling-based scraper (no live network)."""

import pytest

from core.connectors.scrapling_scraper import (
    ScraplingProductScraper,
    extract_number,
    get_domain_info,
    get_scraper,
)


def test_extract_number_basic():
    assert extract_number("EGP 1,299.50") == 1299.5
    assert extract_number("٤٥٠٠") == 4500.0
    assert extract_number("") is None


def test_get_domain_info_amazon_eg():
    d = get_domain_info("https://www.amazon.eg/dp/B0TEST")
    assert d["currency"] == "EGP"
    assert d["store"].startswith("Amazon")


def test_get_scraper_singleton():
    assert get_scraper() is get_scraper()


@pytest.mark.asyncio
async def test_scrape_short_circuits_on_complete_http(monkeypatch):
    scraper = ScraplingProductScraper()

    async def fake_http(url: str):
        return {
            "name": "Test Product",
            "price": 10.0,
            "currency": "USD",
            "symbol": "$",
            "store": "Online Store",
            "in_stock": True,
        }

    monkeypatch.setattr(scraper, "_try_http", fake_http)
    calls = {"stealth": 0, "dynamic": 0}

    async def no_stealth(url: str):
        calls["stealth"] += 1
        return None

    async def no_dynamic(url: str):
        calls["dynamic"] += 1
        return None

    monkeypatch.setattr(scraper, "_try_stealth", no_stealth)
    monkeypatch.setattr(scraper, "_try_dynamic", no_dynamic)

    r = await scraper.scrape("https://example.com/p/1")
    assert r["name"] == "Test Product"
    assert r["price"] == 10.0
    assert calls["stealth"] == 0
    assert calls["dynamic"] == 0


@pytest.mark.asyncio
async def test_scrape_falls_back_to_stealth(monkeypatch):
    scraper = ScraplingProductScraper()

    async def bad_http(url: str):
        return None

    async def stealth_ok(url: str):
        return {
            "name": "Stealth Name",
            "price": 5.0,
            "currency": "SAR",
            "symbol": "ر.س",
            "store": "S",
            "in_stock": True,
        }

    monkeypatch.setattr(scraper, "_try_http", bad_http)
    monkeypatch.setattr(scraper, "_try_stealth", stealth_ok)
    monkeypatch.setattr(scraper, "_try_dynamic", lambda url: None)

    r = await scraper.scrape("https://example.com/x")
    assert r["name"] == "Stealth Name"
    assert r["price"] == 5.0


def test_parse_page_rejects_access_denied():
    scraper = ScraplingProductScraper()
    from scrapling.engines.toolbelt.custom import Response

    html = "<html><head><title>Access Denied</title></head><body></body></html>"
    resp = Response(
        url="https://example.com/p",
        content=html,
        status=200,
        reason="OK",
        cookies={},
        headers={},
        request_headers={},
    )
    assert scraper._parse_page(resp, "https://example.com/p") is None


def test_parse_page_extracts_amazon_like_html():
    scraper = ScraplingProductScraper()
    from scrapling.engines.toolbelt.custom import Response

    html = """<html><body>
    <span id="productTitle">Widget Pro</span>
    <span class="a-price"><span class="a-offscreen">EGP 100.50</span></span>
    </body></html>"""
    resp = Response(
        url="https://www.amazon.eg/dp/B0TEST",
        content=html,
        status=200,
        reason="OK",
        cookies={},
        headers={},
        request_headers={},
    )
    out = scraper._parse_page(resp, "https://www.amazon.eg/dp/B0TEST")
    assert out is not None
    assert out["name"] == "Widget Pro"
    assert out["price"] == 100.5
    assert out["currency"] == "EGP"
