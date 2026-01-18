"""Unit tests for SSE Event Handler.

Tests cover:
- SSEEventHandler initialization
- handle() with domain events that have SSE mappings
- handle() with domain events without mappings (no-op)
- _transform_event() domain-to-SSE transformation
- Exception handling (fail-open behavior)
- has_mapping_for() and get_mapped_event_types() helpers

Architecture:
    - Unit tests with mocked publisher and manually injected mappings
    - Tests the event handler logic independent of actual domain events
"""

import logging
from dataclasses import dataclass
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest
from uuid_extensions import uuid7

from src.domain.events.base_event import DomainEvent
from src.domain.events.sse_event import SSEEvent, SSEEventType
from src.domain.events.sse_registry import DomainToSSEMapping
from src.infrastructure.sse.sse_event_handler import SSEEventHandler


# =============================================================================
# Test Fixtures and Helpers
# =============================================================================


@dataclass(frozen=True, kw_only=True)
class MockDomainEvent(DomainEvent):
    """Mock domain event for testing."""

    user_id: UUID
    account_count: int = 5
    provider_slug: str = "schwab"


@dataclass(frozen=True, kw_only=True)
class UnmappedDomainEvent(DomainEvent):
    """Domain event without SSE mapping."""

    user_id: UUID


def create_mock_mapping() -> DomainToSSEMapping:
    """Create a mock domain-to-SSE mapping for testing."""

    def extract_payload(e: DomainEvent) -> dict[str, Any]:
        """Extract payload from MockDomainEvent."""
        event = cast(MockDomainEvent, e)
        return {
            "account_count": event.account_count,
            "provider": event.provider_slug,
        }

    def extract_user_id(e: DomainEvent) -> UUID:
        """Extract user_id from MockDomainEvent."""
        event = cast(MockDomainEvent, e)
        return event.user_id

    return DomainToSSEMapping(
        domain_event_class=MockDomainEvent,
        sse_event_type=SSEEventType.SYNC_ACCOUNTS_COMPLETED,
        payload_extractor=extract_payload,
        user_id_extractor=extract_user_id,
    )


@pytest.fixture
def mock_publisher():
    """Create a mock SSE publisher."""
    publisher = MagicMock()
    publisher.publish = AsyncMock()
    return publisher


@pytest.fixture
def handler_with_mapping(mock_publisher):
    """Create handler with injected mock mapping."""
    handler = SSEEventHandler(publisher=mock_publisher)
    # Manually inject a mapping for testing
    mapping = create_mock_mapping()
    handler._mapping = {MockDomainEvent: mapping}
    return handler


@pytest.fixture
def handler_empty_mapping(mock_publisher):
    """Create handler with empty mapping for testing.

    Note: SSEEventHandler loads mappings from registry on init.
    We explicitly clear it to test empty-mapping behavior.
    """
    handler = SSEEventHandler(publisher=mock_publisher)
    handler._mapping = {}  # Clear to test empty-mapping behavior
    return handler


# =============================================================================
# Initialization Tests
# =============================================================================


@pytest.mark.unit
class TestSSEEventHandlerInit:
    """Test SSEEventHandler initialization."""

    def test_init_with_publisher(self, mock_publisher):
        """Test handler initializes with publisher."""
        handler = SSEEventHandler(publisher=mock_publisher)

        assert handler._publisher is mock_publisher
        assert handler._logger is not None

    def test_init_with_custom_logger(self, mock_publisher):
        """Test handler accepts custom logger."""
        custom_logger = logging.getLogger("test.custom")
        handler = SSEEventHandler(publisher=mock_publisher, logger=custom_logger)

        assert handler._logger is custom_logger

    def test_init_loads_mapping_from_registry(self, mock_publisher):
        """Test handler loads mapping from registry on init."""
        handler = SSEEventHandler(publisher=mock_publisher)

        # Currently empty, but should be a dict
        assert isinstance(handler._mapping, dict)


# =============================================================================
# Handle Method Tests - With Mapping
# =============================================================================


@pytest.mark.unit
class TestHandleWithMapping:
    """Test handle() method when domain event has SSE mapping."""

    @pytest.mark.asyncio
    async def test_handle_transforms_and_publishes(
        self, handler_with_mapping, mock_publisher
    ):
        """Test handle() transforms domain event and publishes SSE event."""
        user_id = uuid7()
        domain_event = MockDomainEvent(user_id=user_id, account_count=10)

        await handler_with_mapping.handle(domain_event)

        # Verify publish was called
        mock_publisher.publish.assert_called_once()

        # Verify SSE event was correct
        published_event = mock_publisher.publish.call_args[0][0]
        assert isinstance(published_event, SSEEvent)
        assert published_event.event_type == SSEEventType.SYNC_ACCOUNTS_COMPLETED
        assert published_event.user_id == user_id
        assert published_event.data["account_count"] == 10
        assert published_event.data["provider"] == "schwab"

    @pytest.mark.asyncio
    async def test_handle_extracts_user_id_correctly(
        self, handler_with_mapping, mock_publisher
    ):
        """Test handle() extracts user_id using mapping extractor."""
        user_id = uuid7()
        domain_event = MockDomainEvent(user_id=user_id)

        await handler_with_mapping.handle(domain_event)

        published_event = mock_publisher.publish.call_args[0][0]
        assert published_event.user_id == user_id

    @pytest.mark.asyncio
    async def test_handle_extracts_payload_correctly(
        self, handler_with_mapping, mock_publisher
    ):
        """Test handle() extracts payload using mapping extractor."""
        domain_event = MockDomainEvent(
            user_id=uuid7(),
            account_count=42,
            provider_slug="alpaca",
        )

        await handler_with_mapping.handle(domain_event)

        published_event = mock_publisher.publish.call_args[0][0]
        assert published_event.data == {"account_count": 42, "provider": "alpaca"}


# =============================================================================
# Handle Method Tests - Without Mapping
# =============================================================================


@pytest.mark.unit
class TestHandleWithoutMapping:
    """Test handle() method when domain event has no SSE mapping."""

    @pytest.mark.asyncio
    async def test_handle_no_mapping_returns_early(
        self, handler_empty_mapping, mock_publisher
    ):
        """Test handle() returns early when no mapping exists."""
        domain_event = UnmappedDomainEvent(user_id=uuid7())

        await handler_empty_mapping.handle(domain_event)

        # Publisher should NOT be called
        mock_publisher.publish.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_unmapped_event_no_error(
        self, handler_with_mapping, mock_publisher
    ):
        """Test handle() doesn't error on unmapped event types."""
        # Handler has mapping for MockDomainEvent, but not UnmappedDomainEvent
        domain_event = UnmappedDomainEvent(user_id=uuid7())

        # Should not raise
        await handler_with_mapping.handle(domain_event)

        mock_publisher.publish.assert_not_called()


# =============================================================================
# Error Handling Tests
# =============================================================================


@pytest.mark.unit
class TestHandleErrorHandling:
    """Test handle() error handling (fail-open behavior)."""

    @pytest.mark.asyncio
    async def test_handle_catches_publisher_exception(
        self, handler_with_mapping, mock_publisher
    ):
        """Test handle() catches publisher exceptions (fail-open)."""
        mock_publisher.publish.side_effect = Exception("Redis connection failed")
        domain_event = MockDomainEvent(user_id=uuid7())

        # Should NOT raise - fail-open behavior
        await handler_with_mapping.handle(domain_event)

    @pytest.mark.asyncio
    async def test_handle_logs_error_on_exception(
        self, handler_with_mapping, mock_publisher
    ):
        """Test handle() logs error when exception occurs."""
        mock_publisher.publish.side_effect = Exception("Test error")
        handler_with_mapping._logger = MagicMock()
        domain_event = MockDomainEvent(user_id=uuid7())

        await handler_with_mapping.handle(domain_event)

        # Verify error was logged
        handler_with_mapping._logger.error.assert_called_once()
        call_args = handler_with_mapping._logger.error.call_args
        assert "fail-open" in call_args[0][0].lower()

    @pytest.mark.asyncio
    async def test_handle_catches_extractor_exception(self, mock_publisher):
        """Test handle() catches exceptions from payload extractor."""

        def bad_extractor(event: Any) -> dict[str, Any]:
            raise ValueError("Extraction failed")

        mapping = DomainToSSEMapping(
            domain_event_class=MockDomainEvent,
            sse_event_type=SSEEventType.SYNC_ACCOUNTS_COMPLETED,
            payload_extractor=bad_extractor,
            user_id_extractor=lambda e: cast(MockDomainEvent, e).user_id,
        )
        handler = SSEEventHandler(publisher=mock_publisher)
        handler._mapping = {MockDomainEvent: mapping}

        domain_event = MockDomainEvent(user_id=uuid7())

        # Should NOT raise - fail-open
        await handler.handle(domain_event)

        # Publish should not be called due to extraction error
        mock_publisher.publish.assert_not_called()


# =============================================================================
# Helper Method Tests
# =============================================================================


@pytest.mark.unit
class TestHelperMethods:
    """Test helper methods."""

    def test_has_mapping_for_returns_true(self, handler_with_mapping):
        """Test has_mapping_for() returns True for mapped events."""
        assert handler_with_mapping.has_mapping_for(MockDomainEvent) is True

    def test_has_mapping_for_returns_false(self, handler_with_mapping):
        """Test has_mapping_for() returns False for unmapped events."""
        assert handler_with_mapping.has_mapping_for(UnmappedDomainEvent) is False

    def test_get_mapped_event_types(self, handler_with_mapping):
        """Test get_mapped_event_types() returns list of mapped types."""
        types = handler_with_mapping.get_mapped_event_types()

        assert isinstance(types, list)
        assert MockDomainEvent in types

    def test_get_mapped_event_types_empty(self, handler_empty_mapping):
        """Test get_mapped_event_types() returns empty list when no mappings."""
        types = handler_empty_mapping.get_mapped_event_types()

        assert types == []


# =============================================================================
# Transform Event Tests
# =============================================================================


@pytest.mark.unit
class TestTransformEvent:
    """Test _transform_event() method."""

    def test_transform_creates_sse_event(self, handler_with_mapping):
        """Test _transform_event creates valid SSEEvent."""
        user_id = uuid7()
        domain_event = MockDomainEvent(user_id=user_id, account_count=7)
        mapping = create_mock_mapping()

        sse_event = handler_with_mapping._transform_event(domain_event, mapping)

        assert isinstance(sse_event, SSEEvent)
        assert sse_event.event_type == SSEEventType.SYNC_ACCOUNTS_COMPLETED
        assert sse_event.user_id == user_id
        assert sse_event.data == {"account_count": 7, "provider": "schwab"}

    def test_transform_generates_event_id(self, handler_with_mapping):
        """Test _transform_event generates unique event_id."""
        domain_event = MockDomainEvent(user_id=uuid7())
        mapping = create_mock_mapping()

        sse_event = handler_with_mapping._transform_event(domain_event, mapping)

        assert sse_event.event_id is not None
        # UUID v7 check
        assert (sse_event.event_id.int >> 76) & 0xF == 7
