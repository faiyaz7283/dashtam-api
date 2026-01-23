"""Unit tests for SSE event types and serialization.

Tests cover:
- SSEEvent dataclass creation and immutability
- to_sse_format() wire format serialization
- to_dict() / from_dict() round-trip
- SSEEventType enum completeness
- SSEEventCategory mapping
- get_category_for_event_type() lookup

Architecture:
    - Unit tests for domain layer (no dependencies)
    - Tests immutability and serialization
    - Validates event type to category mapping completeness
"""

import json
from datetime import UTC, datetime
from uuid import UUID

import pytest
from uuid_extensions import uuid7

from src.domain.events.sse_event import (
    SSEEvent,
    SSEEventCategory,
    SSEEventType,
    _EVENT_TYPE_TO_CATEGORY,
    get_category_for_event_type,
)


# =============================================================================
# Test Fixtures and Helpers
# =============================================================================


def create_sse_event(
    event_type: SSEEventType = SSEEventType.SYNC_ACCOUNTS_COMPLETED,
    user_id: UUID | None = None,
    data: dict[str, object] | None = None,
    event_id: UUID | None = None,
) -> SSEEvent:
    """Helper to create SSEEvent instances for testing."""
    return SSEEvent(
        event_type=event_type,
        user_id=user_id or uuid7(),
        data=data or {"test_key": "test_value"},
        event_id=event_id or uuid7(),
    )


# =============================================================================
# SSEEventCategory Tests
# =============================================================================


@pytest.mark.unit
class TestSSEEventCategory:
    """Test SSEEventCategory enum."""

    def test_all_categories_defined(self):
        """Test all expected categories are defined."""
        expected = {
            "data_sync",
            "provider",
            "ai",
            "import",
            "portfolio",
            "security",
        }
        actual = {cat.value for cat in SSEEventCategory}
        assert actual == expected

    def test_categories_are_lowercase_snake_case(self):
        """Test category values follow lowercase snake_case convention."""
        for category in SSEEventCategory:
            assert category.value == category.value.lower()
            assert category.value.isidentifier() or "_" in category.value


# =============================================================================
# SSEEventType Tests
# =============================================================================


@pytest.mark.unit
class TestSSEEventType:
    """Test SSEEventType enum."""

    def test_event_types_use_dot_notation(self):
        """Test all event types use dot notation (e.g., sync.accounts.started)."""
        for event_type in SSEEventType:
            assert "." in event_type.value, f"{event_type.name} should use dot notation"

    def test_data_sync_events(self):
        """Test data sync event types are defined."""
        sync_events = [
            SSEEventType.SYNC_ACCOUNTS_STARTED,
            SSEEventType.SYNC_ACCOUNTS_COMPLETED,
            SSEEventType.SYNC_ACCOUNTS_FAILED,
            SSEEventType.SYNC_TRANSACTIONS_STARTED,
            SSEEventType.SYNC_TRANSACTIONS_COMPLETED,
            SSEEventType.SYNC_TRANSACTIONS_FAILED,
            SSEEventType.SYNC_HOLDINGS_STARTED,
            SSEEventType.SYNC_HOLDINGS_COMPLETED,
            SSEEventType.SYNC_HOLDINGS_FAILED,
        ]
        for event in sync_events:
            assert event.value.startswith("sync.")

    def test_provider_events(self):
        """Test provider event types are defined."""
        provider_events = [
            SSEEventType.PROVIDER_TOKEN_EXPIRING,
            SSEEventType.PROVIDER_TOKEN_REFRESHED,
            SSEEventType.PROVIDER_TOKEN_FAILED,
            SSEEventType.PROVIDER_DISCONNECTED,
        ]
        for event in provider_events:
            assert event.value.startswith("provider.")

    def test_ai_events(self):
        """Test AI event types are defined."""
        ai_events = [
            SSEEventType.AI_RESPONSE_CHUNK,
            SSEEventType.AI_TOOL_EXECUTING,
            SSEEventType.AI_RESPONSE_COMPLETE,
        ]
        for event in ai_events:
            assert event.value.startswith("ai.")

    def test_import_events(self):
        """Test import event types are defined."""
        import_events = [
            SSEEventType.IMPORT_STARTED,
            SSEEventType.IMPORT_PROGRESS,
            SSEEventType.IMPORT_COMPLETED,
            SSEEventType.IMPORT_FAILED,
        ]
        for event in import_events:
            assert event.value.startswith("import.")

    def test_portfolio_events(self):
        """Test portfolio event types are defined."""
        portfolio_events = [
            SSEEventType.PORTFOLIO_BALANCE_UPDATED,
            SSEEventType.PORTFOLIO_HOLDINGS_UPDATED,
        ]
        for event in portfolio_events:
            assert event.value.startswith("portfolio.")

    def test_security_events(self):
        """Test security event types are defined."""
        security_events = [
            SSEEventType.SECURITY_SESSION_NEW,
            SSEEventType.SECURITY_SESSION_SUSPICIOUS,
            SSEEventType.SECURITY_SESSION_EXPIRING,
            SSEEventType.SECURITY_SESSION_REVOKED,
            SSEEventType.SECURITY_PASSWORD_CHANGED,
            SSEEventType.SECURITY_LOGIN_FAILED,
        ]
        for event in security_events:
            assert event.value.startswith("security.")


# =============================================================================
# Category Mapping Tests
# =============================================================================


@pytest.mark.unit
class TestCategoryMapping:
    """Test event type to category mapping."""

    def test_all_event_types_have_category_mapping(self):
        """CRITICAL: Every SSEEventType must have a category mapping."""
        missing = []
        for event_type in SSEEventType:
            if event_type not in _EVENT_TYPE_TO_CATEGORY:
                missing.append(event_type.name)

        assert not missing, (
            f"SSEEventTypes missing category mapping:\n"
            f"{chr(10).join(f'  - {m}' for m in missing)}\n\n"
            f"Fix: Add mapping to _EVENT_TYPE_TO_CATEGORY in sse_event.py"
        )

    def test_get_category_for_event_type_returns_correct_category(self):
        """Test get_category_for_event_type returns expected categories."""
        # Data sync events → DATA_SYNC
        assert (
            get_category_for_event_type(SSEEventType.SYNC_ACCOUNTS_STARTED)
            == SSEEventCategory.DATA_SYNC
        )
        assert (
            get_category_for_event_type(SSEEventType.SYNC_TRANSACTIONS_COMPLETED)
            == SSEEventCategory.DATA_SYNC
        )

        # Provider events → PROVIDER
        assert (
            get_category_for_event_type(SSEEventType.PROVIDER_TOKEN_EXPIRING)
            == SSEEventCategory.PROVIDER
        )

        # AI events → AI
        assert (
            get_category_for_event_type(SSEEventType.AI_RESPONSE_CHUNK)
            == SSEEventCategory.AI
        )

        # Import events → IMPORT
        assert (
            get_category_for_event_type(SSEEventType.IMPORT_PROGRESS)
            == SSEEventCategory.IMPORT
        )

        # Portfolio events → PORTFOLIO
        assert (
            get_category_for_event_type(SSEEventType.PORTFOLIO_BALANCE_UPDATED)
            == SSEEventCategory.PORTFOLIO
        )

        # Security events → SECURITY
        assert (
            get_category_for_event_type(SSEEventType.SECURITY_SESSION_NEW)
            == SSEEventCategory.SECURITY
        )


# =============================================================================
# SSEEvent Creation Tests
# =============================================================================


@pytest.mark.unit
class TestSSEEventCreation:
    """Test SSEEvent dataclass creation."""

    def test_event_created_with_required_fields(self):
        """Test SSEEvent can be created with required fields."""
        user_id = uuid7()
        event = SSEEvent(
            event_type=SSEEventType.SYNC_ACCOUNTS_COMPLETED,
            user_id=user_id,
            data={"count": 5},
        )
        assert event.event_type == SSEEventType.SYNC_ACCOUNTS_COMPLETED
        assert event.user_id == user_id
        assert event.data == {"count": 5}

    def test_event_generates_uuid7_event_id_by_default(self):
        """Test event_id is auto-generated as UUID v7."""
        event = create_sse_event()
        assert isinstance(event.event_id, UUID)
        # UUID v7 starts with version nibble 7
        assert (event.event_id.int >> 76) & 0xF == 7

    def test_event_generates_utc_timestamp_by_default(self):
        """Test occurred_at is auto-generated as UTC datetime."""
        before = datetime.now(UTC)
        event = create_sse_event()
        after = datetime.now(UTC)

        assert before <= event.occurred_at <= after
        assert event.occurred_at.tzinfo is not None

    def test_event_is_immutable(self):
        """Test SSEEvent is frozen (immutable)."""
        event = create_sse_event()
        with pytest.raises(AttributeError):
            event.event_type = SSEEventType.AI_RESPONSE_CHUNK  # type: ignore

    def test_event_category_property(self):
        """Test category property returns correct category."""
        event = create_sse_event(event_type=SSEEventType.PROVIDER_DISCONNECTED)
        assert event.category == SSEEventCategory.PROVIDER


# =============================================================================
# SSE Wire Format Tests
# =============================================================================


@pytest.mark.unit
class TestSSEWireFormat:
    """Test to_sse_format() wire format serialization."""

    def test_to_sse_format_contains_event_id(self):
        """Test SSE format includes event ID."""
        event_id = uuid7()
        event = create_sse_event(event_id=event_id)
        formatted = event.to_sse_format()

        assert f"id: {event_id}" in formatted

    def test_to_sse_format_contains_event_type(self):
        """Test SSE format includes event type."""
        event = create_sse_event(event_type=SSEEventType.AI_RESPONSE_CHUNK)
        formatted = event.to_sse_format()

        assert "event: ai.response.chunk" in formatted

    def test_to_sse_format_contains_json_data(self):
        """Test SSE format includes JSON data."""
        event = create_sse_event(data={"key": "value", "count": 42})
        formatted = event.to_sse_format()

        # Extract the data line
        for line in formatted.split("\n"):
            if line.startswith("data: "):
                json_str = line[6:]  # Remove "data: " prefix
                parsed = json.loads(json_str)
                assert parsed == {"key": "value", "count": 42}
                return

        pytest.fail("data line not found in SSE format")

    def test_to_sse_format_ends_with_double_newline(self):
        """Test SSE message ends with double newline (per spec)."""
        event = create_sse_event()
        formatted = event.to_sse_format()

        assert formatted.endswith("\n\n")

    def test_to_sse_format_field_order(self):
        """Test SSE format field order: id, event, data."""
        event_id = uuid7()
        event = create_sse_event(
            event_id=event_id,
            event_type=SSEEventType.IMPORT_STARTED,
            data={"file": "test.qfx"},
        )
        formatted = event.to_sse_format()
        lines = formatted.strip().split("\n")

        assert lines[0].startswith("id:")
        assert lines[1].startswith("event:")
        assert lines[2].startswith("data:")

    def test_to_sse_format_handles_complex_data(self):
        """Test SSE format handles nested JSON data."""
        complex_data: dict[str, object] = {
            "nested": {"key": "value"},
            "list": [1, 2, 3],
            "unicode": "日本語",
            "null": None,
        }
        event = create_sse_event(data=complex_data)
        formatted = event.to_sse_format()

        # Extract and parse data
        for line in formatted.split("\n"):
            if line.startswith("data: "):
                parsed = json.loads(line[6:])
                assert parsed == complex_data
                return

        pytest.fail("data line not found")


# =============================================================================
# Dictionary Serialization Tests
# =============================================================================


@pytest.mark.unit
class TestDictionarySerialization:
    """Test to_dict() and from_dict() methods."""

    def test_to_dict_contains_all_fields(self):
        """Test to_dict includes all event fields."""
        event = create_sse_event()
        d = event.to_dict()

        assert "event_id" in d
        assert "event_type" in d
        assert "user_id" in d
        assert "data" in d
        assert "occurred_at" in d

    def test_to_dict_serializes_uuid_as_string(self):
        """Test UUIDs are serialized as strings."""
        event_id = uuid7()
        user_id = uuid7()
        event = create_sse_event(event_id=event_id, user_id=user_id)
        d = event.to_dict()

        assert d["event_id"] == str(event_id)
        assert d["user_id"] == str(user_id)

    def test_to_dict_serializes_event_type_as_string(self):
        """Test event_type is serialized as string value."""
        event = create_sse_event(event_type=SSEEventType.SECURITY_SESSION_NEW)
        d = event.to_dict()

        assert d["event_type"] == "security.session.new"

    def test_to_dict_serializes_datetime_as_iso(self):
        """Test occurred_at is serialized as ISO format."""
        event = create_sse_event()
        d = event.to_dict()

        # Should be parseable as ISO format
        parsed = datetime.fromisoformat(d["occurred_at"])
        assert parsed == event.occurred_at

    def test_from_dict_creates_equivalent_event(self):
        """Test from_dict creates equivalent SSEEvent."""
        original = create_sse_event()
        d = original.to_dict()
        restored = SSEEvent.from_dict(d)

        assert restored.event_id == original.event_id
        assert restored.event_type == original.event_type
        assert restored.user_id == original.user_id
        assert restored.data == original.data
        assert restored.occurred_at == original.occurred_at

    def test_round_trip_preserves_all_data(self):
        """Test to_dict/from_dict round-trip preserves all data."""
        original = SSEEvent(
            event_type=SSEEventType.PORTFOLIO_HOLDINGS_UPDATED,
            user_id=uuid7(),
            data={"account_id": "abc", "holdings_count": 15},
        )
        restored = SSEEvent.from_dict(original.to_dict())

        # Equal in all fields
        assert original.event_id == restored.event_id
        assert original.event_type == restored.event_type
        assert original.user_id == restored.user_id
        assert original.data == restored.data
        # Timestamps should be equal (may differ slightly due to precision)
        assert (
            abs((original.occurred_at - restored.occurred_at).total_seconds()) < 0.001
        )

    def test_from_dict_raises_on_invalid_event_type(self):
        """Test from_dict raises ValueError for invalid event type."""
        d = {
            "event_id": str(uuid7()),
            "event_type": "invalid.event.type",
            "user_id": str(uuid7()),
            "data": {},
            "occurred_at": datetime.now(UTC).isoformat(),
        }
        with pytest.raises(ValueError):
            SSEEvent.from_dict(d)

    def test_from_dict_raises_on_missing_field(self):
        """Test from_dict raises KeyError for missing required field."""
        d = {
            "event_id": str(uuid7()),
            # Missing event_type
            "user_id": str(uuid7()),
            "data": {},
            "occurred_at": datetime.now(UTC).isoformat(),
        }
        with pytest.raises(KeyError):
            SSEEvent.from_dict(d)
