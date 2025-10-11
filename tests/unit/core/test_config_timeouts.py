"""Tests for HTTP timeout configuration in Settings.

This module tests that HTTP timeout settings are properly configured
and that the get_http_timeout() method returns correct httpx.Timeout objects.
"""

import httpx

from src.core.config import Settings


class TestHttpTimeoutConfiguration:
    """Tests for HTTP timeout configuration and helper methods.

    Validates P1 requirement: HTTP connection timeouts prevent indefinite hangs.
    Tests configurable timeouts for all provider API calls.
    """

    def test_default_timeout_values(self):
        """Test default HTTP timeout values.

        Verifies that:
        - HTTP_TIMEOUT_TOTAL defaults to 30.0 seconds
        - HTTP_TIMEOUT_CONNECT defaults to 10.0 seconds
        - HTTP_TIMEOUT_READ defaults to 30.0 seconds
        - HTTP_TIMEOUT_POOL defaults to 5.0 seconds

        Note:
            P1 requirement: prevents indefinite hangs on provider API calls.
        """
        settings = Settings()

        assert settings.HTTP_TIMEOUT_TOTAL == 30.0
        assert settings.HTTP_TIMEOUT_CONNECT == 10.0
        assert settings.HTTP_TIMEOUT_READ == 30.0
        assert settings.HTTP_TIMEOUT_POOL == 5.0

    def test_get_http_timeout_returns_httpx_timeout(self):
        """Test get_http_timeout() returns configured httpx.Timeout object.

        Verifies that:
        - Returns httpx.Timeout instance
        - connect timeout set to 10.0 seconds
        - read timeout set to 30.0 seconds
        - pool timeout set to 5.0 seconds
        - write timeout defaults to read timeout (30.0)

        Note:
            Used for all httpx HTTP client requests to providers.
        """
        settings = Settings()
        timeout = settings.get_http_timeout()

        assert isinstance(timeout, httpx.Timeout)
        assert timeout.connect == 10.0
        assert timeout.read == 30.0
        assert timeout.pool == 5.0
        # write timeout defaults to read timeout
        assert timeout.write == 30.0

    def test_custom_timeout_values(self, monkeypatch):
        """Test custom timeout values via environment variables.

        Verifies that:
        - HTTP_TIMEOUT_TOTAL env var overrides default (60.0)
        - HTTP_TIMEOUT_CONNECT env var overrides default (15.0)
        - HTTP_TIMEOUT_READ env var overrides default (45.0)
        - HTTP_TIMEOUT_POOL env var overrides default (10.0)
        - Environment configuration works correctly

        Args:
            monkeypatch: Pytest fixture for environment variables
        """
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
        """Test get_http_timeout() respects custom environment values.

        Verifies that:
        - httpx.Timeout created with custom values
        - connect timeout uses custom 15.0 seconds
        - read timeout uses custom 45.0 seconds
        - Environment overrides applied correctly

        Args:
            monkeypatch: Pytest fixture for environment variables
        """
        monkeypatch.setenv("HTTP_TIMEOUT_TOTAL", "60.0")
        monkeypatch.setenv("HTTP_TIMEOUT_CONNECT", "15.0")
        monkeypatch.setenv("HTTP_TIMEOUT_READ", "45.0")

        settings = Settings()
        timeout = settings.get_http_timeout()

        assert timeout.connect == 15.0
        assert timeout.read == 45.0

    def test_timeout_prevents_indefinite_hang(self):
        """Test timeout configuration prevents indefinite hangs (P1 requirement).

        Verifies that:
        - All timeout values are non-None (no indefinite waits)
        - connect, read, write, pool all configured
        - All timeout values are positive numbers
        - Critical safety check for production

        Note:
            P1 CRITICAL: Prevents hanging requests that never time out.
        """
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
