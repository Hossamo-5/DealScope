"""
Tests for audit-related security fixes.
"""
import pytest
from auth.security import _validate_secret_key


class TestSecretKeyValidation:
    """P0-B3: Default SECRET_KEY rejection tests."""

    def test_rejects_known_default_placeholder(self, monkeypatch):
        import auth.security as sec
        monkeypatch.setattr(sec, "SECRET_KEY", "CHANGE_THIS_TO_A_RANDOM_SECRET_KEY_IN_PRODUCTION")
        with pytest.raises(RuntimeError, match="default placeholder"):
            _validate_secret_key()

    def test_rejects_lowercase_variant(self, monkeypatch):
        import auth.security as sec
        monkeypatch.setattr(sec, "SECRET_KEY", "change_this_to_a_very_long_random_secret_key_in_production")
        with pytest.raises(RuntimeError, match="default placeholder"):
            _validate_secret_key()

    def test_rejects_short_key(self, monkeypatch):
        import auth.security as sec
        monkeypatch.setattr(sec, "SECRET_KEY", "tooshort")
        with pytest.raises(RuntimeError, match="at least"):
            _validate_secret_key()

    def test_accepts_strong_random_key(self, monkeypatch):
        import auth.security as sec
        monkeypatch.setattr(sec, "SECRET_KEY", "a" * 64)
        # Should not raise
        _validate_secret_key()
