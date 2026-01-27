"""Unit tests for SSE Portfolio Notifications Mappings (Issue #257).

Tests cover:
- All 3 domain-to-SSE mappings for portfolio events
- Payload extraction for each event type
- User ID extraction
- Decimal-to-string conversion for monetary values
- Mapping registry integration

Reference:
    - src/domain/events/sse_registry.py
    - src/domain/events/portfolio_events.py
    - GitHub Issue #257
"""

from decimal import Decimal
from typing import cast
from unittest.mock import MagicMock
from uuid import UUID

import pytest
from uuid_extensions import uuid7

from src.domain.events.portfolio_events import (
    AccountBalanceUpdated,
    AccountHoldingsUpdated,
    PortfolioNetWorthRecalculated,
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
def account_id() -> UUID:
    """Provide a test account ID."""
    return cast(UUID, uuid7())


# =============================================================================
# Registry Tests
# =============================================================================


@pytest.mark.unit
class TestPortfolioMappingsRegistry:
    """Test that portfolio mappings are properly registered."""

    def test_all_portfolio_events_have_mappings(self):
        """Verify all 3 portfolio domain events have SSE mappings."""
        mapping = get_domain_event_to_sse_mapping()

        assert AccountBalanceUpdated in mapping
        assert AccountHoldingsUpdated in mapping
        assert PortfolioNetWorthRecalculated in mapping

    def test_registry_statistics_include_portfolio_mappings(self):
        """Verify registry statistics reflect portfolio mappings."""
        stats = get_registry_statistics()

        # Should have at least 24 mappings (9 data sync + 3 provider + 4 import + 5 security + 3 portfolio)
        total_mappings = cast(int, stats["total_mappings"])
        assert total_mappings >= 24

    def test_mapping_list_contains_portfolio_entries(self):
        """Verify DOMAIN_TO_SSE_MAPPING has portfolio entries."""
        portfolio_types = {
            SSEEventType.PORTFOLIO_BALANCE_UPDATED,
            SSEEventType.PORTFOLIO_HOLDINGS_UPDATED,
            SSEEventType.PORTFOLIO_NETWORTH_UPDATED,
        }

        mapped_types = {m.sse_event_type for m in DOMAIN_TO_SSE_MAPPING}
        assert portfolio_types.issubset(mapped_types)


# =============================================================================
# AccountBalanceUpdated Mapping Tests
# =============================================================================


@pytest.mark.unit
class TestAccountBalanceUpdatedMapping:
    """Test AccountBalanceUpdated domain-to-SSE mapping."""

    def test_mapping_to_correct_sse_event_type(self):
        """Test AccountBalanceUpdated maps to PORTFOLIO_BALANCE_UPDATED."""
        mapping = get_domain_event_to_sse_mapping()
        m = mapping[AccountBalanceUpdated]

        assert m.sse_event_type == SSEEventType.PORTFOLIO_BALANCE_UPDATED

    def test_payload_extraction(self, user_id, account_id):
        """Test payload is correctly extracted from AccountBalanceUpdated."""
        mapping = get_domain_event_to_sse_mapping()
        m = mapping[AccountBalanceUpdated]

        event = AccountBalanceUpdated(
            user_id=user_id,
            account_id=account_id,
            previous_balance=Decimal("1000.00"),
            new_balance=Decimal("1250.50"),
            delta=Decimal("250.50"),
            currency="USD",
        )
        payload = m.payload_extractor(event)

        assert payload == {
            "account_id": str(account_id),
            "previous_balance": "1000.00",
            "new_balance": "1250.50",
            "delta": "250.50",
            "currency": "USD",
        }

    def test_payload_extraction_with_negative_delta(self, user_id, account_id):
        """Test payload extraction when balance decreases."""
        mapping = get_domain_event_to_sse_mapping()
        m = mapping[AccountBalanceUpdated]

        event = AccountBalanceUpdated(
            user_id=user_id,
            account_id=account_id,
            previous_balance=Decimal("5000.00"),
            new_balance=Decimal("4500.75"),
            delta=Decimal("-499.25"),
            currency="EUR",
        )
        payload = m.payload_extractor(event)

        assert payload == {
            "account_id": str(account_id),
            "previous_balance": "5000.00",
            "new_balance": "4500.75",
            "delta": "-499.25",
            "currency": "EUR",
        }

    def test_payload_extraction_with_zero_delta(self, user_id, account_id):
        """Test payload extraction when balance is unchanged (edge case)."""
        mapping = get_domain_event_to_sse_mapping()
        m = mapping[AccountBalanceUpdated]

        event = AccountBalanceUpdated(
            user_id=user_id,
            account_id=account_id,
            previous_balance=Decimal("1000.00"),
            new_balance=Decimal("1000.00"),
            delta=Decimal("0"),
            currency="GBP",
        )
        payload = m.payload_extractor(event)

        assert payload == {
            "account_id": str(account_id),
            "previous_balance": "1000.00",
            "new_balance": "1000.00",
            "delta": "0",
            "currency": "GBP",
        }

    def test_user_id_extraction(self, user_id, account_id):
        """Test user_id is correctly extracted from AccountBalanceUpdated."""
        mapping = get_domain_event_to_sse_mapping()
        m = mapping[AccountBalanceUpdated]

        event = AccountBalanceUpdated(
            user_id=user_id,
            account_id=account_id,
            previous_balance=Decimal("0"),
            new_balance=Decimal("100"),
            delta=Decimal("100"),
            currency="USD",
        )

        assert m.user_id_extractor(event) == user_id


# =============================================================================
# AccountHoldingsUpdated Mapping Tests
# =============================================================================


@pytest.mark.unit
class TestAccountHoldingsUpdatedMapping:
    """Test AccountHoldingsUpdated domain-to-SSE mapping."""

    def test_mapping_to_correct_sse_event_type(self):
        """Test AccountHoldingsUpdated maps to PORTFOLIO_HOLDINGS_UPDATED."""
        mapping = get_domain_event_to_sse_mapping()
        m = mapping[AccountHoldingsUpdated]

        assert m.sse_event_type == SSEEventType.PORTFOLIO_HOLDINGS_UPDATED

    def test_payload_extraction(self, user_id, account_id):
        """Test payload is correctly extracted from AccountHoldingsUpdated."""
        mapping = get_domain_event_to_sse_mapping()
        m = mapping[AccountHoldingsUpdated]

        event = AccountHoldingsUpdated(
            user_id=user_id,
            account_id=account_id,
            holdings_count=15,
            created_count=3,
            updated_count=10,
            deactivated_count=2,
        )
        payload = m.payload_extractor(event)

        assert payload == {
            "account_id": str(account_id),
            "holdings_count": 15,
            "created_count": 3,
            "updated_count": 10,
            "deactivated_count": 2,
        }

    def test_payload_extraction_with_all_zeros(self, user_id, account_id):
        """Test payload extraction when no holdings changed (edge case)."""
        mapping = get_domain_event_to_sse_mapping()
        m = mapping[AccountHoldingsUpdated]

        event = AccountHoldingsUpdated(
            user_id=user_id,
            account_id=account_id,
            holdings_count=0,
            created_count=0,
            updated_count=0,
            deactivated_count=0,
        )
        payload = m.payload_extractor(event)

        assert payload == {
            "account_id": str(account_id),
            "holdings_count": 0,
            "created_count": 0,
            "updated_count": 0,
            "deactivated_count": 0,
        }

    def test_payload_extraction_only_deactivations(self, user_id, account_id):
        """Test payload extraction when only holdings are deactivated."""
        mapping = get_domain_event_to_sse_mapping()
        m = mapping[AccountHoldingsUpdated]

        event = AccountHoldingsUpdated(
            user_id=user_id,
            account_id=account_id,
            holdings_count=5,
            created_count=0,
            updated_count=0,
            deactivated_count=3,
        )
        payload = m.payload_extractor(event)

        assert payload == {
            "account_id": str(account_id),
            "holdings_count": 5,
            "created_count": 0,
            "updated_count": 0,
            "deactivated_count": 3,
        }

    def test_user_id_extraction(self, user_id, account_id):
        """Test user_id is correctly extracted from AccountHoldingsUpdated."""
        mapping = get_domain_event_to_sse_mapping()
        m = mapping[AccountHoldingsUpdated]

        event = AccountHoldingsUpdated(
            user_id=user_id,
            account_id=account_id,
            holdings_count=10,
            created_count=0,
            updated_count=0,
            deactivated_count=0,
        )

        assert m.user_id_extractor(event) == user_id


# =============================================================================
# PortfolioNetWorthRecalculated Mapping Tests
# =============================================================================


@pytest.mark.unit
class TestPortfolioNetWorthRecalculatedMapping:
    """Test PortfolioNetWorthRecalculated domain-to-SSE mapping."""

    def test_mapping_to_correct_sse_event_type(self):
        """Test PortfolioNetWorthRecalculated maps to PORTFOLIO_NETWORTH_UPDATED."""
        mapping = get_domain_event_to_sse_mapping()
        m = mapping[PortfolioNetWorthRecalculated]

        assert m.sse_event_type == SSEEventType.PORTFOLIO_NETWORTH_UPDATED

    def test_payload_extraction(self, user_id):
        """Test payload is correctly extracted from PortfolioNetWorthRecalculated."""
        mapping = get_domain_event_to_sse_mapping()
        m = mapping[PortfolioNetWorthRecalculated]

        event = PortfolioNetWorthRecalculated(
            user_id=user_id,
            previous_net_worth=Decimal("50000.00"),
            new_net_worth=Decimal("52500.75"),
            delta=Decimal("2500.75"),
            currency="USD",
            account_count=5,
        )
        payload = m.payload_extractor(event)

        assert payload == {
            "previous_net_worth": "50000.00",
            "new_net_worth": "52500.75",
            "delta": "2500.75",
            "currency": "USD",
            "account_count": 5,
        }

    def test_payload_extraction_with_negative_delta(self, user_id):
        """Test payload extraction when net worth decreases."""
        mapping = get_domain_event_to_sse_mapping()
        m = mapping[PortfolioNetWorthRecalculated]

        event = PortfolioNetWorthRecalculated(
            user_id=user_id,
            previous_net_worth=Decimal("100000.00"),
            new_net_worth=Decimal("95000.00"),
            delta=Decimal("-5000.00"),
            currency="EUR",
            account_count=3,
        )
        payload = m.payload_extractor(event)

        assert payload == {
            "previous_net_worth": "100000.00",
            "new_net_worth": "95000.00",
            "delta": "-5000.00",
            "currency": "EUR",
            "account_count": 3,
        }

    def test_payload_extraction_with_single_account(self, user_id):
        """Test payload extraction with single account."""
        mapping = get_domain_event_to_sse_mapping()
        m = mapping[PortfolioNetWorthRecalculated]

        event = PortfolioNetWorthRecalculated(
            user_id=user_id,
            previous_net_worth=Decimal("0"),
            new_net_worth=Decimal("10000.00"),
            delta=Decimal("10000.00"),
            currency="USD",
            account_count=1,
        )
        payload = m.payload_extractor(event)

        assert payload == {
            "previous_net_worth": "0",
            "new_net_worth": "10000.00",
            "delta": "10000.00",
            "currency": "USD",
            "account_count": 1,
        }

    def test_payload_extraction_with_large_values(self, user_id):
        """Test payload extraction with large monetary values."""
        mapping = get_domain_event_to_sse_mapping()
        m = mapping[PortfolioNetWorthRecalculated]

        event = PortfolioNetWorthRecalculated(
            user_id=user_id,
            previous_net_worth=Decimal("999999999.99"),
            new_net_worth=Decimal("1000000000.00"),
            delta=Decimal("0.01"),
            currency="USD",
            account_count=100,
        )
        payload = m.payload_extractor(event)

        assert payload == {
            "previous_net_worth": "999999999.99",
            "new_net_worth": "1000000000.00",
            "delta": "0.01",
            "currency": "USD",
            "account_count": 100,
        }

    def test_user_id_extraction(self, user_id):
        """Test user_id is correctly extracted from PortfolioNetWorthRecalculated."""
        mapping = get_domain_event_to_sse_mapping()
        m = mapping[PortfolioNetWorthRecalculated]

        event = PortfolioNetWorthRecalculated(
            user_id=user_id,
            previous_net_worth=Decimal("0"),
            new_net_worth=Decimal("0"),
            delta=Decimal("0"),
            currency="USD",
            account_count=0,
        )

        assert m.user_id_extractor(event) == user_id


# =============================================================================
# SSE Event Handler Integration Tests
# =============================================================================


@pytest.mark.unit
class TestSSEEventHandlerIntegration:
    """Test that portfolio mappings work with SSEEventHandler."""

    def test_handler_has_mapping_for_all_portfolio_events(self):
        """Verify SSEEventHandler can find mappings for portfolio events."""
        from src.infrastructure.sse.sse_event_handler import SSEEventHandler

        mock_publisher = MagicMock()
        handler = SSEEventHandler(publisher=mock_publisher)

        # All portfolio events should have mappings
        assert handler.has_mapping_for(AccountBalanceUpdated)
        assert handler.has_mapping_for(AccountHoldingsUpdated)
        assert handler.has_mapping_for(PortfolioNetWorthRecalculated)

    def test_handler_returns_portfolio_events_in_mapped_types(self):
        """Verify SSEEventHandler returns portfolio events in mapped types."""
        from src.infrastructure.sse.sse_event_handler import SSEEventHandler

        mock_publisher = MagicMock()
        handler = SSEEventHandler(publisher=mock_publisher)

        mapped_types = handler.get_mapped_event_types()

        # Should include all portfolio events
        assert AccountBalanceUpdated in mapped_types
        assert AccountHoldingsUpdated in mapped_types
        assert PortfolioNetWorthRecalculated in mapped_types
