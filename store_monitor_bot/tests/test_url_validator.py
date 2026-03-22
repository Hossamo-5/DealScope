"""
Tests for URL validator (SSRF protection).
"""
import pytest
from utils.url_validator import validate_scrape_url


class TestValidateScrapeUrl:
    """P0-B1: SSRF protection tests."""

    def test_valid_https_url(self):
        assert validate_scrape_url("https://www.amazon.com/dp/B08N5WRWNW") is True

    def test_valid_http_url(self):
        assert validate_scrape_url("http://www.example.com/product/123") is True

    def test_rejects_ftp_scheme(self):
        assert validate_scrape_url("ftp://example.com/file") is False

    def test_rejects_file_scheme(self):
        assert validate_scrape_url("file:///etc/passwd") is False

    def test_rejects_no_scheme(self):
        assert validate_scrape_url("www.example.com") is False

    def test_rejects_empty_string(self):
        assert validate_scrape_url("") is False

    def test_rejects_cloud_metadata_ip(self):
        assert validate_scrape_url("http://169.254.169.254/latest/meta-data/") is False

    def test_rejects_cloud_metadata_host(self):
        assert validate_scrape_url("http://metadata.google.internal/computeMetadata/v1/") is False

    def test_rejects_localhost(self):
        assert validate_scrape_url("http://127.0.0.1/admin") is False

    def test_rejects_localhost_name(self):
        assert validate_scrape_url("http://localhost/admin") is False

    def test_rejects_private_10_range(self):
        assert validate_scrape_url("http://10.0.0.1/secret") is False

    def test_rejects_private_192_range(self):
        assert validate_scrape_url("http://192.168.1.1/") is False

    def test_rejects_private_172_range(self):
        assert validate_scrape_url("http://172.16.0.1/") is False

    def test_rejects_no_hostname(self):
        assert validate_scrape_url("http://") is False

    def test_rejects_javascript_scheme(self):
        assert validate_scrape_url("javascript:alert(1)") is False

    def test_accepts_real_ecommerce(self):
        assert validate_scrape_url("https://www.noon.com/product/12345") is True

    def test_rejects_alibaba_metadata(self):
        assert validate_scrape_url("http://100.100.100.200/latest/meta-data") is False
