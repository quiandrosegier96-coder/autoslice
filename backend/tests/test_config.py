"""
Tests for application configuration validation.
"""

import pytest


def test_get_jwt_secret_returns_configured_value(monkeypatch):
    """get_jwt_secret() must return the value when JWT_SECRET_KEY is set."""
    from app.config import settings, get_jwt_secret

    monkeypatch.setattr(settings, "jwt_secret_key", "my-test-secret-value")
    assert get_jwt_secret() == "my-test-secret-value"


def test_get_jwt_secret_raises_when_missing(monkeypatch):
    """get_jwt_secret() must raise RuntimeError with a clear message when secret is absent."""
    from app.config import settings, get_jwt_secret

    monkeypatch.setattr(settings, "jwt_secret_key", None)
    with pytest.raises(RuntimeError, match="JWT_SECRET_KEY"):
        get_jwt_secret()


def test_get_jwt_secret_raises_on_empty_string(monkeypatch):
    """get_jwt_secret() must reject an empty string, not just None."""
    from app.config import settings, get_jwt_secret

    monkeypatch.setattr(settings, "jwt_secret_key", "")
    with pytest.raises(RuntimeError, match="JWT_SECRET_KEY"):
        get_jwt_secret()


def test_allowed_origins_accepts_json_text():
    """ALLOWED_ORIGINS may arrive from Docker/Coolify as JSON text."""
    from app.config import Settings

    settings = Settings(
        jwt_secret_key="test-secret",
        allowed_origins='["http://localhost:3000"]',
        coolify_fqdn="autoslice.be",
    )

    assert settings.cors_origins == [
        "http://localhost:3000",
        "https://autoslice.be",
    ]


def test_allowed_origins_accepts_comma_text():
    """ALLOWED_ORIGINS may also be configured as a comma-separated value."""
    from app.config import Settings

    settings = Settings(
        jwt_secret_key="test-secret",
        allowed_origins="http://localhost:3000,https://admin.autoslice.be",
        coolify_fqdn="https://autoslice.be",
    )

    assert settings.cors_origins == [
        "http://localhost:3000",
        "https://admin.autoslice.be",
        "https://autoslice.be",
    ]
