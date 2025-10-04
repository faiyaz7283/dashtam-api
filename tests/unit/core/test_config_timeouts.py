"""Tests for HTTP timeout configuration in Settings.

This module tests that HTTP timeout settings are properly configured
and that the get_http_timeout() method returns correct httpx.Timeout objects.
"""

import httpx

from src.core.config import Settings


class TestHttpTimeoutConfiguration:
    """Tests for HTTP timeout configuration and helper methods."""

    def test_default_timeout_values(self):
        """Test that default timeout values are set correctly."""
        settings = Settings()

        assert settings.HTTP_TIMEOUT_TOTAL == 30.0
        assert settings.HTTP_TIMEOUT_CONNECT == 10.0
        assert settings.HTTP_TIMEOUT_READ == 30.0
        assert settings.HTTP_TIMEOUT_POOL == 5.0

    def test_get_http_timeout_returns_httpx_timeout(self):
        """Test that get_http_timeout() returns a valid httpx.Timeout object."""
        settings = Settings()
        timeout = settings.get_http_timeout()

        assert isinstance(timeout, httpx.Timeout)
        assert timeout.connect == 10.0
        assert timeout.read == 30.0
        assert timeout.pool == 5.0
        # write timeout defaults to read timeout
        assert timeout.write == 30.0

    def test_custom_timeout_values(self, monkeypatch):
        """Test that custom timeout values can be configured via environment."""
        monkeypatch.setenv("HTTP_TIMEOUT_TOTAL", "60.0")
        monkeypatch.setenv("HTTP_TIMEOUT_CONNECT", "15.0")
        monkeypatch.setenv("HTTP_TIMEOUT_READ", "45.0")
        monkeypatch.setenv("HTTP_TIMEOUT_POOL", "10.0")

        settings = Settings()

        assert settings.HTTP_TIMEOUT_TOTAL == 60.0
        assert settings.HTTP_TIMEOUT_CONNECT == 15.0
        assert settings.HTTP_TIMEOUT_READ == 45.0
        assert settings.HTTP_TIMEOUT_POOL == 10.0

    def test_get_http_timeout_with_custom_values(self, monkeypatch):
        """Test that get_http_timeout() uses custom timeout values."""
        monkeypatch.setenv("HTTP_TIMEOUT_TOTAL", "60.0")
        monkeypatch.setenv("HTTP_TIMEOUT_CONNECT", "15.0")
        monkeypatch.setenv("HTTP_TIMEOUT_READ", "45.0")

        settings = Settings()
        timeout = settings.get_http_timeout()

        assert timeout.connect == 15.0
        assert timeout.read == 45.0

    def test_timeout_prevents_indefinite_hang(self):
        """Test that timeout configuration prevents indefinite hangs."""
        settings = Settings()
        timeout = settings.get_http_timeout()

        # All timeout values should be non-None (preventing indefinite waits)
        assert timeout.connect is not None
        assert timeout.read is not None
        assert timeout.write is not None
        assert timeout.pool is not None

        # All timeout values should be positive
        assert timeout.connect > 0
        assert timeout.read > 0
        assert timeout.write > 0
        assert timeout.pool > 0
