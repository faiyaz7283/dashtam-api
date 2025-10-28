"""Unit tests for device fingerprinting.

Tests fingerprint generation, user agent parsing, and device info formatting.
"""

import pytest
from unittest.mock import Mock

from src.core.fingerprinting import (
    generate_device_fingerprint,
    parse_user_agent,
    format_device_info,
)


class TestGenerateDeviceFingerprint:
    """Test device fingerprint generation."""

    @pytest.fixture
    def mock_request_chrome_macos(self):
        """Create mock Request with Chrome on macOS headers."""
        request = Mock()
        request.headers = {
            "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "accept-language": "en-US,en;q=0.9",
            "x-screen-resolution": "1920x1080",
            "x-timezone-offset": "-300",
        }
        request.headers.get = lambda key, default="": request.headers.get(key, default)
        return request

    @pytest.fixture
    def mock_request_firefox_windows(self):
        """Create mock Request with Firefox on Windows headers."""
        request = Mock()
        request.headers = {
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0",
            "accept-language": "en-GB,en;q=0.8",
        }
        request.headers.get = lambda key, default="": request.headers.get(key, default)
        return request

    def test_generate_fingerprint_chrome_macos(self, mock_request_chrome_macos):
        """Test fingerprint generation for Chrome on macOS."""
        fingerprint = generate_device_fingerprint(mock_request_chrome_macos)
        
        # Fingerprint should be SHA256 hash (64 hex characters)
        assert len(fingerprint) == 64
        assert all(c in "0123456789abcdef" for c in fingerprint)

    def test_generate_fingerprint_firefox_windows(self, mock_request_firefox_windows):
        """Test fingerprint generation for Firefox on Windows."""
        fingerprint = generate_device_fingerprint(mock_request_firefox_windows)
        
        # Fingerprint should be SHA256 hash
        assert len(fingerprint) == 64
        assert all(c in "0123456789abcdef" for c in fingerprint)

    def test_generate_fingerprint_empty_headers(self):
        """Test fingerprint generation with empty headers."""
        request = Mock()
        request.headers = {}
        request.headers.get = lambda key, default="": default
        
        fingerprint = generate_device_fingerprint(request)
        
        # Should still generate fingerprint (hash of empty components)
        assert len(fingerprint) == 64

    def test_fingerprint_consistency(self, mock_request_chrome_macos):
        """Test same headers produce same fingerprint."""
        fingerprint1 = generate_device_fingerprint(mock_request_chrome_macos)
        fingerprint2 = generate_device_fingerprint(mock_request_chrome_macos)
        
        assert fingerprint1 == fingerprint2

    def test_different_headers_produce_different_fingerprints(
        self, mock_request_chrome_macos, mock_request_firefox_windows
    ):
        """Test different headers produce different fingerprints."""
        fingerprint1 = generate_device_fingerprint(mock_request_chrome_macos)
        fingerprint2 = generate_device_fingerprint(mock_request_firefox_windows)
        
        assert fingerprint1 != fingerprint2


class TestParseUserAgent:
    """Test user agent string parsing."""

    def test_parse_user_agent_chrome(self):
        """Test parsing Chrome user agent."""
        ua = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        parsed = parse_user_agent(ua)
        
        assert parsed["browser"] == "Chrome"
        assert parsed["os"] == "macOS"
        assert parsed["device_type"] == "desktop"

    def test_parse_user_agent_safari(self):
        """Test parsing Safari user agent."""
        ua = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15"
        parsed = parse_user_agent(ua)
        
        assert parsed["browser"] == "Safari"
        assert parsed["os"] == "macOS"
        assert parsed["device_type"] == "desktop"

    def test_parse_user_agent_firefox(self):
        """Test parsing Firefox user agent."""
        ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0"
        parsed = parse_user_agent(ua)
        
        assert parsed["browser"] == "Firefox"
        assert parsed["os"] == "Windows"
        assert parsed["device_type"] == "desktop"

    def test_parse_user_agent_edge(self):
        """Test parsing Edge user agent."""
        ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0"
        parsed = parse_user_agent(ua)
        
        assert parsed["browser"] == "Edge"
        assert parsed["os"] == "Windows"
        assert parsed["device_type"] == "desktop"

    def test_parse_user_agent_mobile_iphone(self):
        """Test parsing iPhone user agent."""
        ua = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
        parsed = parse_user_agent(ua)
        
        assert parsed["browser"] == "Safari"
        assert parsed["os"] == "iOS"
        assert parsed["device_type"] == "mobile"

    def test_parse_user_agent_mobile_android(self):
        """Test parsing Android user agent."""
        ua = "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.6099.144 Mobile Safari/537.36"
        parsed = parse_user_agent(ua)
        
        assert parsed["browser"] == "Chrome"
        assert parsed["os"] == "Android"
        assert parsed["device_type"] == "mobile"

    def test_parse_user_agent_tablet_ipad(self):
        """Test parsing iPad user agent."""
        ua = "Mozilla/5.0 (iPad; CPU OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
        parsed = parse_user_agent(ua)
        
        assert parsed["os"] == "iOS"
        assert parsed["device_type"] == "tablet"

    def test_parse_user_agent_unknown(self):
        """Test parsing unknown user agent."""
        ua = "CustomBot/1.0"
        parsed = parse_user_agent(ua)
        
        assert parsed["browser"] == "Unknown Browser"
        assert parsed["os"] == "Unknown OS"
        assert parsed["device_type"] == "desktop"  # Default


class TestFormatDeviceInfo:
    """Test device info formatting."""

    def test_format_device_info_chrome_macos(self):
        """Test formatting Chrome on macOS."""
        ua = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        formatted = format_device_info(ua)
        
        assert formatted == "Chrome on macOS"

    def test_format_device_info_firefox_windows(self):
        """Test formatting Firefox on Windows."""
        ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0"
        formatted = format_device_info(ua)
        
        assert formatted == "Firefox on Windows"

    def test_format_device_info_safari_ios(self):
        """Test formatting Safari on iOS."""
        ua = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
        formatted = format_device_info(ua)
        
        assert formatted == "Safari on iOS"

    def test_format_device_info_empty_string(self):
        """Test formatting empty user agent."""
        formatted = format_device_info("")
        
        assert formatted == "Unknown Device"

    def test_format_device_info_unknown(self):
        """Test formatting unknown user agent."""
        formatted = format_device_info("CustomBot/1.0")
        
        assert formatted == "Unknown Browser on Unknown OS"
