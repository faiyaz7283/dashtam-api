"""Unit tests for SSE Provider Health Mappings (Issue #157).

Tests cover:
- All 3 domain-to-SSE mappings for provider events
- Payload extraction for each event type
- User ID extraction
- Mapping registry integration

Note:
    The provider.token.expiring event is NOT covered here as it requires
    a background job (not triggered by domain events). That will be
    implemented in a separate issue once background job architecture
    is established.

Reference:
    - src/domain/events/sse_registry.py
    - GitHub Issue #157
"""

from typing import cast
from unittest.mock import MagicMock
from uuid import UUID

import pytest
from uuid_extensions import uuid7

from src.domain.events.provider_events import (
    ProviderDisconnectionSucceeded,
    ProviderTokenRefreshFailed,
    ProviderTokenRefreshSucceeded,
)
from src.domain.events.sse_event import SSEEventType
from src.domain.events.sse_registry import (
    DOMAIN_TO_SSE_MAPPING,
    get_domain_event_to_sse_mapping,
    get_registry_statistics,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def user_id() -> UUID:
    """Provide a test user ID."""
    return cast(UUID, uuid7())


@pytest.fixture
def connection_id() -> UUID:
    """Provide a test connection ID."""
    return cast(UUID, uuid7())


@pytest.fixture
def provider_id() -> UUID:
    """Provide a test provider ID."""
    return cast(UUID, uuid7())


# =============================================================================
# Registry Tests
# =============================================================================


@pytest.mark.unit
class TestProviderMappingsRegistry:
    """Test that provider mappings are properly registered."""

    def test_all_provider_events_have_mappings(self):
        """Verify all 3 provider domain events have SSE mappings."""
        mapping = get_domain_event_to_sse_mapping()

        # Provider token refresh events
        assert ProviderTokenRefreshSucceeded in mapping
        assert ProviderTokenRefreshFailed in mapping

        # Provider disconnection event
        assert ProviderDisconnectionSucceeded in mapping

    def test_registry_statistics_include_provider_mappings(self):
        """Verify registry statistics reflect provider mappings."""
        stats = get_registry_statistics()

        # Should have at least 12 mappings (9 data sync + 3 provider)
        total_mappings = cast(int, stats["total_mappings"])
        assert total_mappings >= 12

    def test_mapping_list_contains_provider_entries(self):
        """Verify DOMAIN_TO_SSE_MAPPING has provider entries."""
        provider_types = {
            SSEEventType.PROVIDER_TOKEN_REFRESHED,
            SSEEventType.PROVIDER_TOKEN_FAILED,
            SSEEventType.PROVIDER_DISCONNECTED,
        }

        mapped_types = {m.sse_event_type for m in DOMAIN_TO_SSE_MAPPING}
        assert provider_types.issubset(mapped_types)


# =============================================================================
# Token Refresh Succeeded Mapping Tests
# =============================================================================


@pytest.mark.unit
class TestTokenRefreshSucceededMapping:
    """Test ProviderTokenRefreshSucceeded domain-to-SSE mapping."""

    def test_mapping_to_correct_sse_event_type(self):
        """Test ProviderTokenRefreshSucceeded maps to PROVIDER_TOKEN_REFRESHED."""
        mapping = get_domain_event_to_sse_mapping()
        m = mapping[ProviderTokenRefreshSucceeded]

        assert m.sse_event_type == SSEEventType.PROVIDER_TOKEN_REFRESHED

    def test_payload_extraction(self, user_id, connection_id, provider_id):
        """Test payload is correctly extracted from ProviderTokenRefreshSucceeded."""
        mapping = get_domain_event_to_sse_mapping()
        m = mapping[ProviderTokenRefreshSucceeded]

        event = ProviderTokenRefreshSucceeded(
            user_id=user_id,
            connection_id=connection_id,
            provider_id=provider_id,
            provider_slug="schwab",
        )
        payload = m.payload_extractor(event)

        assert payload == {
            "connection_id": str(connection_id),
            "provider_slug": "schwab",
        }

    def test_user_id_extraction(self, user_id, connection_id, provider_id):
        """Test user_id is correctly extracted from ProviderTokenRefreshSucceeded."""
        mapping = get_domain_event_to_sse_mapping()
        m = mapping[ProviderTokenRefreshSucceeded]

        event = ProviderTokenRefreshSucceeded(
            user_id=user_id,
            connection_id=connection_id,
            provider_id=provider_id,
            provider_slug="schwab",
        )

        assert m.user_id_extractor(event) == user_id


# =============================================================================
# Token Refresh Failed Mapping Tests
# =============================================================================


@pytest.mark.unit
class TestTokenRefreshFailedMapping:
    """Test ProviderTokenRefreshFailed domain-to-SSE mapping."""

    def test_mapping_to_correct_sse_event_type(self):
        """Test ProviderTokenRefreshFailed maps to PROVIDER_TOKEN_FAILED."""
        mapping = get_domain_event_to_sse_mapping()
        m = mapping[ProviderTokenRefreshFailed]

        assert m.sse_event_type == SSEEventType.PROVIDER_TOKEN_FAILED

    def test_payload_extraction_with_needs_reauth_true(
        self, user_id, connection_id, provider_id
    ):
        """Test payload extraction when user action is needed."""
        mapping = get_domain_event_to_sse_mapping()
        m = mapping[ProviderTokenRefreshFailed]

        event = ProviderTokenRefreshFailed(
            user_id=user_id,
            connection_id=connection_id,
            provider_id=provider_id,
            provider_slug="schwab",
            reason="refresh_token_expired",
            needs_user_action=True,
        )
        payload = m.payload_extractor(event)

        assert payload == {
            "connection_id": str(connection_id),
            "provider_slug": "schwab",
            "needs_reauth": True,
        }

    def test_payload_extraction_with_needs_reauth_false(
        self, user_id, connection_id, provider_id
    ):
        """Test payload extraction when user action is not needed."""
        mapping = get_domain_event_to_sse_mapping()
        m = mapping[ProviderTokenRefreshFailed]

        event = ProviderTokenRefreshFailed(
            user_id=user_id,
            connection_id=connection_id,
            provider_id=provider_id,
            provider_slug="alpaca",
            reason="network_error",
            needs_user_action=False,
        )
        payload = m.payload_extractor(event)

        assert payload == {
            "connection_id": str(connection_id),
            "provider_slug": "alpaca",
            "needs_reauth": False,
        }

    def test_user_id_extraction(self, user_id, connection_id, provider_id):
        """Test user_id is correctly extracted from ProviderTokenRefreshFailed."""
        mapping = get_domain_event_to_sse_mapping()
        m = mapping[ProviderTokenRefreshFailed]

        event = ProviderTokenRefreshFailed(
            user_id=user_id,
            connection_id=connection_id,
            provider_id=provider_id,
            provider_slug="schwab",
            reason="test",
            needs_user_action=False,
        )

        assert m.user_id_extractor(event) == user_id


# =============================================================================
# Provider Disconnection Succeeded Mapping Tests
# =============================================================================


@pytest.mark.unit
class TestProviderDisconnectionSucceededMapping:
    """Test ProviderDisconnectionSucceeded domain-to-SSE mapping."""

    def test_mapping_to_correct_sse_event_type(self):
        """Test ProviderDisconnectionSucceeded maps to PROVIDER_DISCONNECTED."""
        mapping = get_domain_event_to_sse_mapping()
        m = mapping[ProviderDisconnectionSucceeded]

        assert m.sse_event_type == SSEEventType.PROVIDER_DISCONNECTED

    def test_payload_extraction(self, user_id, connection_id, provider_id):
        """Test payload is correctly extracted from ProviderDisconnectionSucceeded."""
        mapping = get_domain_event_to_sse_mapping()
        m = mapping[ProviderDisconnectionSucceeded]

        event = ProviderDisconnectionSucceeded(
            user_id=user_id,
            connection_id=connection_id,
            provider_id=provider_id,
            provider_slug="schwab",
        )
        payload = m.payload_extractor(event)

        assert payload == {
            "connection_id": str(connection_id),
            "provider_slug": "schwab",
        }

    def test_user_id_extraction(self, user_id, connection_id, provider_id):
        """Test user_id is correctly extracted from ProviderDisconnectionSucceeded."""
        mapping = get_domain_event_to_sse_mapping()
        m = mapping[ProviderDisconnectionSucceeded]

        event = ProviderDisconnectionSucceeded(
            user_id=user_id,
            connection_id=connection_id,
            provider_id=provider_id,
            provider_slug="schwab",
        )

        assert m.user_id_extractor(event) == user_id


# =============================================================================
# SSE Event Handler Integration Tests
# =============================================================================


@pytest.mark.unit
class TestSSEEventHandlerIntegration:
    """Test that provider mappings work with SSEEventHandler."""

    def test_handler_has_mapping_for_all_provider_events(self):
        """Verify SSEEventHandler can find mappings for provider events."""
        from src.infrastructure.sse.sse_event_handler import SSEEventHandler

        mock_publisher = MagicMock()
        handler = SSEEventHandler(publisher=mock_publisher)

        # All provider events should have mappings
        assert handler.has_mapping_for(ProviderTokenRefreshSucceeded)
        assert handler.has_mapping_for(ProviderTokenRefreshFailed)
        assert handler.has_mapping_for(ProviderDisconnectionSucceeded)

    def test_handler_returns_provider_events_in_mapped_types(self):
        """Verify SSEEventHandler returns provider events in mapped types."""
        from src.infrastructure.sse.sse_event_handler import SSEEventHandler

        mock_publisher = MagicMock()
        handler = SSEEventHandler(publisher=mock_publisher)

        mapped_types = handler.get_mapped_event_types()

        # Should include all provider events
        assert ProviderTokenRefreshSucceeded in mapped_types
        assert ProviderTokenRefreshFailed in mapped_types
        assert ProviderDisconnectionSucceeded in mapped_types
