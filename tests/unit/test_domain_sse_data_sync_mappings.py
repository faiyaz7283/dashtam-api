"""Unit tests for SSE Data Sync Mappings (Issue #156).

Tests cover:
- All 9 domain-to-SSE mappings for data sync events
- Payload extraction for each event type
- User ID extraction
- Mapping registry integration

Reference:
    - src/domain/events/sse_registry.py
    - GitHub Issue #156
"""

from typing import cast
from uuid import UUID

import pytest
from uuid_extensions import uuid7

from src.domain.events.data_events import (
    AccountSyncAttempted,
    AccountSyncFailed,
    AccountSyncSucceeded,
    HoldingsSyncAttempted,
    HoldingsSyncFailed,
    HoldingsSyncSucceeded,
    TransactionSyncAttempted,
    TransactionSyncFailed,
    TransactionSyncSucceeded,
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
def account_id() -> UUID:
    """Provide a test account ID."""
    return cast(UUID, uuid7())


# =============================================================================
# Registry Tests
# =============================================================================


@pytest.mark.unit
class TestDataSyncMappingsRegistry:
    """Test that data sync mappings are properly registered."""

    def test_all_data_sync_events_have_mappings(self):
        """Verify all 9 data sync domain events have SSE mappings."""
        mapping = get_domain_event_to_sse_mapping()

        # Account sync events
        assert AccountSyncAttempted in mapping
        assert AccountSyncSucceeded in mapping
        assert AccountSyncFailed in mapping

        # Transaction sync events
        assert TransactionSyncAttempted in mapping
        assert TransactionSyncSucceeded in mapping
        assert TransactionSyncFailed in mapping

        # Holdings sync events
        assert HoldingsSyncAttempted in mapping
        assert HoldingsSyncSucceeded in mapping
        assert HoldingsSyncFailed in mapping

    def test_registry_statistics_show_nine_mappings(self):
        """Verify registry statistics reflect 9 data sync mappings."""
        stats = get_registry_statistics()

        # Should have at least 9 mappings (may have more in future)
        total_mappings = cast(int, stats["total_mappings"])
        assert total_mappings >= 9

    def test_mapping_list_contains_nine_data_sync_entries(self):
        """Verify DOMAIN_TO_SSE_MAPPING has 9 entries."""
        # Count data sync mappings by checking SSE event types
        data_sync_types = {
            SSEEventType.SYNC_ACCOUNTS_STARTED,
            SSEEventType.SYNC_ACCOUNTS_COMPLETED,
            SSEEventType.SYNC_ACCOUNTS_FAILED,
            SSEEventType.SYNC_TRANSACTIONS_STARTED,
            SSEEventType.SYNC_TRANSACTIONS_COMPLETED,
            SSEEventType.SYNC_TRANSACTIONS_FAILED,
            SSEEventType.SYNC_HOLDINGS_STARTED,
            SSEEventType.SYNC_HOLDINGS_COMPLETED,
            SSEEventType.SYNC_HOLDINGS_FAILED,
        }

        mapped_types = {m.sse_event_type for m in DOMAIN_TO_SSE_MAPPING}
        assert data_sync_types.issubset(mapped_types)


# =============================================================================
# Account Sync Mapping Tests
# =============================================================================


@pytest.mark.unit
class TestAccountSyncMappings:
    """Test Account Sync domain-to-SSE mappings."""

    def test_account_sync_attempted_mapping(self, user_id, connection_id):
        """Test AccountSyncAttempted maps to SYNC_ACCOUNTS_STARTED."""
        mapping = get_domain_event_to_sse_mapping()
        m = mapping[AccountSyncAttempted]

        assert m.sse_event_type == SSEEventType.SYNC_ACCOUNTS_STARTED

        # Test payload extraction
        event = AccountSyncAttempted(connection_id=connection_id, user_id=user_id)
        payload = m.payload_extractor(event)

        assert payload == {"connection_id": str(connection_id)}

    def test_account_sync_succeeded_mapping(self, user_id, connection_id):
        """Test AccountSyncSucceeded maps to SYNC_ACCOUNTS_COMPLETED."""
        mapping = get_domain_event_to_sse_mapping()
        m = mapping[AccountSyncSucceeded]

        assert m.sse_event_type == SSEEventType.SYNC_ACCOUNTS_COMPLETED

        # Test payload extraction
        event = AccountSyncSucceeded(
            connection_id=connection_id,
            user_id=user_id,
            account_count=5,
        )
        payload = m.payload_extractor(event)

        assert payload == {
            "connection_id": str(connection_id),
            "account_count": 5,
        }

    def test_account_sync_failed_mapping(self, user_id, connection_id):
        """Test AccountSyncFailed maps to SYNC_ACCOUNTS_FAILED."""
        mapping = get_domain_event_to_sse_mapping()
        m = mapping[AccountSyncFailed]

        assert m.sse_event_type == SSEEventType.SYNC_ACCOUNTS_FAILED

        # Test payload extraction
        event = AccountSyncFailed(
            connection_id=connection_id,
            user_id=user_id,
            reason="provider_error",
        )
        payload = m.payload_extractor(event)

        assert payload == {
            "connection_id": str(connection_id),
            "error": "provider_error",
        }

    def test_account_sync_attempted_user_id_extraction(self, user_id, connection_id):
        """Test user_id is correctly extracted from AccountSyncAttempted."""
        mapping = get_domain_event_to_sse_mapping()
        m = mapping[AccountSyncAttempted]
        event = AccountSyncAttempted(connection_id=connection_id, user_id=user_id)
        assert m.user_id_extractor(event) == user_id

    def test_account_sync_succeeded_user_id_extraction(self, user_id, connection_id):
        """Test user_id is correctly extracted from AccountSyncSucceeded."""
        mapping = get_domain_event_to_sse_mapping()
        m = mapping[AccountSyncSucceeded]
        event = AccountSyncSucceeded(
            connection_id=connection_id, user_id=user_id, account_count=1
        )
        assert m.user_id_extractor(event) == user_id

    def test_account_sync_failed_user_id_extraction(self, user_id, connection_id):
        """Test user_id is correctly extracted from AccountSyncFailed."""
        mapping = get_domain_event_to_sse_mapping()
        m = mapping[AccountSyncFailed]
        event = AccountSyncFailed(
            connection_id=connection_id, user_id=user_id, reason="test"
        )
        assert m.user_id_extractor(event) == user_id


# =============================================================================
# Transaction Sync Mapping Tests
# =============================================================================


@pytest.mark.unit
class TestTransactionSyncMappings:
    """Test Transaction Sync domain-to-SSE mappings."""

    def test_transaction_sync_attempted_mapping(
        self, user_id, connection_id, account_id
    ):
        """Test TransactionSyncAttempted maps to SYNC_TRANSACTIONS_STARTED."""
        mapping = get_domain_event_to_sse_mapping()
        m = mapping[TransactionSyncAttempted]

        assert m.sse_event_type == SSEEventType.SYNC_TRANSACTIONS_STARTED

        # Test with account_id
        event = TransactionSyncAttempted(
            connection_id=connection_id,
            user_id=user_id,
            account_id=account_id,
        )
        payload = m.payload_extractor(event)

        assert payload == {
            "connection_id": str(connection_id),
            "account_id": str(account_id),
        }

    def test_transaction_sync_attempted_without_account_id(
        self, user_id, connection_id
    ):
        """Test TransactionSyncAttempted with None account_id."""
        mapping = get_domain_event_to_sse_mapping()
        m = mapping[TransactionSyncAttempted]

        # Test without account_id (None)
        event = TransactionSyncAttempted(
            connection_id=connection_id,
            user_id=user_id,
            account_id=None,
        )
        payload = m.payload_extractor(event)

        assert payload == {
            "connection_id": str(connection_id),
            "account_id": None,
        }

    def test_transaction_sync_succeeded_mapping(
        self, user_id, connection_id, account_id
    ):
        """Test TransactionSyncSucceeded maps to SYNC_TRANSACTIONS_COMPLETED."""
        mapping = get_domain_event_to_sse_mapping()
        m = mapping[TransactionSyncSucceeded]

        assert m.sse_event_type == SSEEventType.SYNC_TRANSACTIONS_COMPLETED

        event = TransactionSyncSucceeded(
            connection_id=connection_id,
            user_id=user_id,
            account_id=account_id,
            transaction_count=42,
        )
        payload = m.payload_extractor(event)

        assert payload == {
            "connection_id": str(connection_id),
            "account_id": str(account_id),
            "transaction_count": 42,
        }

    def test_transaction_sync_failed_mapping(self, user_id, connection_id, account_id):
        """Test TransactionSyncFailed maps to SYNC_TRANSACTIONS_FAILED."""
        mapping = get_domain_event_to_sse_mapping()
        m = mapping[TransactionSyncFailed]

        assert m.sse_event_type == SSEEventType.SYNC_TRANSACTIONS_FAILED

        event = TransactionSyncFailed(
            connection_id=connection_id,
            user_id=user_id,
            account_id=account_id,
            reason="date_range_invalid",
        )
        payload = m.payload_extractor(event)

        assert payload == {
            "connection_id": str(connection_id),
            "account_id": str(account_id),
            "error": "date_range_invalid",
        }

    def test_transaction_sync_user_id_extraction(self, user_id, connection_id):
        """Test user_id is correctly extracted from Transaction Sync events."""
        mapping = get_domain_event_to_sse_mapping()

        event = TransactionSyncAttempted(
            connection_id=connection_id,
            user_id=user_id,
            account_id=None,
        )

        extracted = mapping[TransactionSyncAttempted].user_id_extractor(event)
        assert extracted == user_id


# =============================================================================
# Holdings Sync Mapping Tests
# =============================================================================


@pytest.mark.unit
class TestHoldingsSyncMappings:
    """Test Holdings Sync domain-to-SSE mappings."""

    def test_holdings_sync_attempted_mapping(self, user_id, account_id):
        """Test HoldingsSyncAttempted maps to SYNC_HOLDINGS_STARTED."""
        mapping = get_domain_event_to_sse_mapping()
        m = mapping[HoldingsSyncAttempted]

        assert m.sse_event_type == SSEEventType.SYNC_HOLDINGS_STARTED

        event = HoldingsSyncAttempted(account_id=account_id, user_id=user_id)
        payload = m.payload_extractor(event)

        assert payload == {"account_id": str(account_id)}

    def test_holdings_sync_succeeded_mapping(self, user_id, account_id):
        """Test HoldingsSyncSucceeded maps to SYNC_HOLDINGS_COMPLETED."""
        mapping = get_domain_event_to_sse_mapping()
        m = mapping[HoldingsSyncSucceeded]

        assert m.sse_event_type == SSEEventType.SYNC_HOLDINGS_COMPLETED

        event = HoldingsSyncSucceeded(
            account_id=account_id,
            user_id=user_id,
            holding_count=15,
        )
        payload = m.payload_extractor(event)

        assert payload == {
            "account_id": str(account_id),
            "holding_count": 15,
        }

    def test_holdings_sync_failed_mapping(self, user_id, account_id):
        """Test HoldingsSyncFailed maps to SYNC_HOLDINGS_FAILED."""
        mapping = get_domain_event_to_sse_mapping()
        m = mapping[HoldingsSyncFailed]

        assert m.sse_event_type == SSEEventType.SYNC_HOLDINGS_FAILED

        event = HoldingsSyncFailed(
            account_id=account_id,
            user_id=user_id,
            reason="holdings_not_supported",
        )
        payload = m.payload_extractor(event)

        assert payload == {
            "account_id": str(account_id),
            "error": "holdings_not_supported",
        }

    def test_holdings_sync_attempted_user_id_extraction(self, user_id, account_id):
        """Test user_id is correctly extracted from HoldingsSyncAttempted."""
        mapping = get_domain_event_to_sse_mapping()
        m = mapping[HoldingsSyncAttempted]
        event = HoldingsSyncAttempted(account_id=account_id, user_id=user_id)
        assert m.user_id_extractor(event) == user_id

    def test_holdings_sync_succeeded_user_id_extraction(self, user_id, account_id):
        """Test user_id is correctly extracted from HoldingsSyncSucceeded."""
        mapping = get_domain_event_to_sse_mapping()
        m = mapping[HoldingsSyncSucceeded]
        event = HoldingsSyncSucceeded(
            account_id=account_id, user_id=user_id, holding_count=1
        )
        assert m.user_id_extractor(event) == user_id

    def test_holdings_sync_failed_user_id_extraction(self, user_id, account_id):
        """Test user_id is correctly extracted from HoldingsSyncFailed."""
        mapping = get_domain_event_to_sse_mapping()
        m = mapping[HoldingsSyncFailed]
        event = HoldingsSyncFailed(
            account_id=account_id, user_id=user_id, reason="test"
        )
        assert m.user_id_extractor(event) == user_id


# =============================================================================
# SSE Event Handler Integration Tests
# =============================================================================


@pytest.mark.unit
class TestSSEEventHandlerIntegration:
    """Test that mappings work with SSEEventHandler."""

    def test_handler_has_mapping_for_all_data_sync_events(self):
        """Verify SSEEventHandler can find mappings for data sync events."""
        from unittest.mock import MagicMock

        from src.infrastructure.sse.sse_event_handler import SSEEventHandler

        mock_publisher = MagicMock()
        handler = SSEEventHandler(publisher=mock_publisher)

        # All data sync events should have mappings
        assert handler.has_mapping_for(AccountSyncAttempted)
        assert handler.has_mapping_for(AccountSyncSucceeded)
        assert handler.has_mapping_for(AccountSyncFailed)
        assert handler.has_mapping_for(TransactionSyncAttempted)
        assert handler.has_mapping_for(TransactionSyncSucceeded)
        assert handler.has_mapping_for(TransactionSyncFailed)
        assert handler.has_mapping_for(HoldingsSyncAttempted)
        assert handler.has_mapping_for(HoldingsSyncSucceeded)
        assert handler.has_mapping_for(HoldingsSyncFailed)

    def test_handler_returns_correct_mapped_event_types(self):
        """Verify SSEEventHandler returns data sync events in mapped types."""
        from unittest.mock import MagicMock

        from src.infrastructure.sse.sse_event_handler import SSEEventHandler

        mock_publisher = MagicMock()
        handler = SSEEventHandler(publisher=mock_publisher)

        mapped_types = handler.get_mapped_event_types()

        # Should include all data sync events
        assert AccountSyncAttempted in mapped_types
        assert HoldingsSyncSucceeded in mapped_types
        assert TransactionSyncFailed in mapped_types
