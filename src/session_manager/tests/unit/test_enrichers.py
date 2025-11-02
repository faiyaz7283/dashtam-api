"""Unit tests for session enrichers.

Tests stub enricher implementations (GeolocationEnricher and DeviceFingerprintEnricher).
"""

import pytest

from src.session_manager.enrichers.device_fingerprint import (
    DeviceFingerprintEnricher,
)
from src.session_manager.enrichers.geolocation import GeolocationEnricher
from src.session_manager.tests.fixtures.mock_models import MockSession


@pytest.mark.asyncio
class TestGeolocationEnricher:
    """Test GeolocationEnricher stub implementation."""

    async def test_init_default_fail_silently(self):
        """Test initialization with default fail_silently."""
        enricher = GeolocationEnricher()

        assert enricher.fail_silently is True

    async def test_init_custom_fail_silently(self):
        """Test initialization with custom fail_silently."""
        enricher = GeolocationEnricher(fail_silently=False)

        assert enricher.fail_silently is False

    async def test_enrich_returns_session_unchanged(self):
        """Test that stub enricher returns session unchanged."""
        enricher = GeolocationEnricher()
        session = MockSession(
            user_id="user-123",
            ip_address="192.168.1.100",
            location=None,
        )

        result = await enricher.enrich(session)

        # Stub does nothing - session unchanged
        assert result is session
        assert result.location is None

    async def test_enrich_does_not_overwrite_existing_location(self):
        """Test that stub doesn't overwrite existing location data."""
        enricher = GeolocationEnricher()
        session = MockSession(
            user_id="user-123",
            ip_address="192.168.1.100",
            location="San Francisco, USA",
        )

        result = await enricher.enrich(session)

        # Stub preserves existing data
        assert result.location == "San Francisco, USA"

    async def test_enrich_logs_debug_message(self, caplog):
        """Test that stub logs debug message."""
        import logging

        enricher = GeolocationEnricher()
        session = MockSession(user_id="user-123")

        with caplog.at_level(logging.DEBUG):
            await enricher.enrich(session)

        # Should log debug message about being a stub
        assert any("stub" in record.message.lower() for record in caplog.records)


@pytest.mark.asyncio
class TestDeviceFingerprintEnricher:
    """Test DeviceFingerprintEnricher stub implementation."""

    async def test_init_default_fail_silently(self):
        """Test initialization with default fail_silently."""
        enricher = DeviceFingerprintEnricher()

        assert enricher.fail_silently is True

    async def test_init_custom_fail_silently(self):
        """Test initialization with custom fail_silently."""
        enricher = DeviceFingerprintEnricher(fail_silently=False)

        assert enricher.fail_silently is False

    async def test_enrich_returns_session_unchanged(self):
        """Test that stub enricher returns session unchanged."""
        enricher = DeviceFingerprintEnricher()
        session = MockSession(
            user_id="user-123",
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
            device_info="Original Device Info",
        )

        result = await enricher.enrich(session)

        # Stub does nothing - session unchanged
        assert result is session
        assert result.device_info == "Original Device Info"

    async def test_enrich_does_not_overwrite_existing_device_info(self):
        """Test that stub doesn't overwrite existing device_info."""
        enricher = DeviceFingerprintEnricher()
        session = MockSession(
            user_id="user-123",
            user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X)",
            device_info="Chrome on macOS",
        )

        result = await enricher.enrich(session)

        # Stub preserves existing data
        assert result.device_info == "Chrome on macOS"

    async def test_enrich_logs_debug_message(self, caplog):
        """Test that stub logs debug message."""
        import logging

        enricher = DeviceFingerprintEnricher()
        session = MockSession(user_id="user-123")

        with caplog.at_level(logging.DEBUG):
            await enricher.enrich(session)

        # Should log debug message about being a stub
        assert any("stub" in record.message.lower() for record in caplog.records)


@pytest.mark.asyncio
class TestEnricherChaining:
    """Test that multiple enrichers can be chained together."""

    async def test_multiple_enrichers_can_be_chained(self):
        """Test applying multiple enrichers in sequence."""
        geo_enricher = GeolocationEnricher()
        device_enricher = DeviceFingerprintEnricher()

        session = MockSession(
            user_id="user-123",
            ip_address="192.168.1.100",
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
        )

        # Apply enrichers in sequence (like service would do)
        result = await geo_enricher.enrich(session)
        result = await device_enricher.enrich(result)

        # Both enrichers are stubs - session unchanged
        assert result is session

    async def test_enricher_order_does_not_matter_for_stubs(self):
        """Test that stub enrichers can be applied in any order."""
        geo_enricher = GeolocationEnricher()
        device_enricher = DeviceFingerprintEnricher()

        session = MockSession(user_id="user-123")

        # Apply in different order
        result1 = await geo_enricher.enrich(session)
        result1 = await device_enricher.enrich(result1)

        # Reset session
        session2 = MockSession(user_id="user-123")

        # Apply in reverse order
        result2 = await device_enricher.enrich(session2)
        result2 = await geo_enricher.enrich(result2)

        # Both stubs - order doesn't matter, both unchanged
        assert result1.user_id == result2.user_id
