"""Unit tests for SSE container factories.

Tests cover:
- get_sse_publisher() singleton behavior
- get_sse_subscriber() factory behavior
- Container wiring with mocked Redis

Architecture:
    - Unit tests with mocked Redis and settings
    - Tests factory behavior, not Redis functionality
"""

from unittest.mock import MagicMock, patch

import pytest

from src.core.container.sse import get_sse_publisher, get_sse_subscriber


# =============================================================================
# Publisher Factory Tests
# =============================================================================


@pytest.mark.unit
class TestGetSSEPublisher:
    """Test get_sse_publisher() factory."""

    def test_returns_publisher_protocol(self):
        """Test get_sse_publisher returns SSEPublisherProtocol implementation."""
        # Clear LRU cache for clean test
        get_sse_publisher.cache_clear()

        with patch("src.core.config.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                redis_url="redis://localhost:6379",
                sse_enable_retention=False,
            )

            publisher = get_sse_publisher()

            # Should have publish method (protocol compliance)
            assert hasattr(publisher, "publish")
            assert callable(publisher.publish)

        # Clean up
        get_sse_publisher.cache_clear()

    def test_publisher_is_singleton(self):
        """Test get_sse_publisher returns same instance (cached)."""
        get_sse_publisher.cache_clear()

        with patch("src.core.config.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                redis_url="redis://localhost:6379",
                sse_enable_retention=False,
            )

            publisher1 = get_sse_publisher()
            publisher2 = get_sse_publisher()

            # Should be same instance
            assert publisher1 is publisher2

        get_sse_publisher.cache_clear()

    def test_publisher_uses_settings(self):
        """Test publisher uses settings for configuration."""
        get_sse_publisher.cache_clear()

        with patch("src.core.config.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                redis_url="redis://testhost:6379",
                sse_enable_retention=True,
            )

            publisher = get_sse_publisher()

            # Verify settings were accessed
            mock_settings.assert_called()

            # Publisher should be configured with retention enabled
            # Access implementation detail for testing
            assert getattr(publisher, "_enable_retention", None) is True

        get_sse_publisher.cache_clear()


# =============================================================================
# Subscriber Factory Tests
# =============================================================================


@pytest.mark.unit
class TestGetSSESubscriber:
    """Test get_sse_subscriber() factory."""

    def test_returns_subscriber(self):
        """Test get_sse_subscriber returns RedisSSESubscriber."""
        with patch("src.core.config.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                redis_url="redis://localhost:6379",
                sse_enable_retention=False,
            )

            subscriber = get_sse_subscriber()

            # Should have subscribe method
            assert hasattr(subscriber, "subscribe")
            assert callable(subscriber.subscribe)

    def test_subscriber_is_not_singleton(self):
        """Test get_sse_subscriber returns new instance each call."""
        with patch("src.core.config.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                redis_url="redis://localhost:6379",
                sse_enable_retention=False,
            )

            subscriber1 = get_sse_subscriber()
            subscriber2 = get_sse_subscriber()

            # Should be different instances
            assert subscriber1 is not subscriber2

    def test_subscriber_uses_settings(self):
        """Test subscriber uses settings for configuration."""
        with patch("src.core.config.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                redis_url="redis://testhost:6380",
                sse_enable_retention=True,
            )

            subscriber = get_sse_subscriber()

            # Verify settings were accessed
            mock_settings.assert_called()

            # Subscriber should be configured with retention enabled
            assert subscriber._enable_retention is True
