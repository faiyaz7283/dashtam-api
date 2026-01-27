"""Unit tests for portfolio domain events.

Tests cover:
- Event creation with all required fields
- Immutability (frozen dataclass)
- event_id auto-generation
- occurred_at timestamp auto-generation
- Decimal field handling
- Each of 3 portfolio events

Architecture:
- Unit tests for domain events (no dependencies)
- Validates OPERATIONAL events (not 3-state workflow)
- Tests: AccountBalanceUpdated, AccountHoldingsUpdated, PortfolioNetWorthRecalculated

Reference:
    - Implementation Plan: Issue #257, Phase 9.2
"""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

import pytest

from src.domain.events.base_event import DomainEvent
from src.domain.events.portfolio_events import (
    AccountBalanceUpdated,
    AccountHoldingsUpdated,
    PortfolioNetWorthRecalculated,
)


@pytest.mark.unit
class TestAccountBalanceUpdatedEvent:
    """Test AccountBalanceUpdated event."""

    def test_creation_with_all_fields(self):
        """Test event creation with all required fields."""
        # Arrange
        user_id = UUID("12345678-1234-5678-1234-567812345678")
        account_id = UUID("87654321-4321-8765-4321-876543218765")

        # Act
        event = AccountBalanceUpdated(
            user_id=user_id,
            account_id=account_id,
            previous_balance=Decimal("1000.00"),
            new_balance=Decimal("1500.50"),
            delta=Decimal("500.50"),
            currency="USD",
        )

        # Assert
        assert event.user_id == user_id
        assert event.account_id == account_id
        assert event.previous_balance == Decimal("1000.00")
        assert event.new_balance == Decimal("1500.50")
        assert event.delta == Decimal("500.50")
        assert event.currency == "USD"

    def test_event_id_auto_generated(self):
        """Test event_id is auto-generated when not provided."""
        # Act
        event = AccountBalanceUpdated(
            user_id=UUID("12345678-1234-5678-1234-567812345678"),
            account_id=UUID("87654321-4321-8765-4321-876543218765"),
            previous_balance=Decimal("0"),
            new_balance=Decimal("100"),
            delta=Decimal("100"),
            currency="USD",
        )

        # Assert
        assert event.event_id is not None
        assert isinstance(event.event_id, UUID)

    def test_occurred_at_auto_generated(self):
        """Test occurred_at timestamp is auto-generated in UTC."""
        # Arrange
        before = datetime.now(UTC)

        # Act
        event = AccountBalanceUpdated(
            user_id=UUID("12345678-1234-5678-1234-567812345678"),
            account_id=UUID("87654321-4321-8765-4321-876543218765"),
            previous_balance=Decimal("0"),
            new_balance=Decimal("100"),
            delta=Decimal("100"),
            currency="USD",
        )

        after = datetime.now(UTC)

        # Assert
        assert event.occurred_at is not None
        assert isinstance(event.occurred_at, datetime)
        assert event.occurred_at.tzinfo == UTC
        assert before <= event.occurred_at <= after

    def test_event_is_immutable(self):
        """Test event is immutable (frozen dataclass)."""
        # Arrange
        event = AccountBalanceUpdated(
            user_id=UUID("12345678-1234-5678-1234-567812345678"),
            account_id=UUID("87654321-4321-8765-4321-876543218765"),
            previous_balance=Decimal("0"),
            new_balance=Decimal("100"),
            delta=Decimal("100"),
            currency="USD",
        )

        # Act & Assert
        with pytest.raises(AttributeError):
            event.new_balance = Decimal("200")  # type: ignore[misc]

    def test_inherits_from_domain_event(self):
        """Test event inherits from DomainEvent."""
        # Act
        event = AccountBalanceUpdated(
            user_id=UUID("12345678-1234-5678-1234-567812345678"),
            account_id=UUID("87654321-4321-8765-4321-876543218765"),
            previous_balance=Decimal("0"),
            new_balance=Decimal("100"),
            delta=Decimal("100"),
            currency="USD",
        )

        # Assert
        assert isinstance(event, DomainEvent)

    def test_negative_delta_for_decrease(self):
        """Test delta can be negative for balance decrease."""
        # Act
        event = AccountBalanceUpdated(
            user_id=UUID("12345678-1234-5678-1234-567812345678"),
            account_id=UUID("87654321-4321-8765-4321-876543218765"),
            previous_balance=Decimal("1000.00"),
            new_balance=Decimal("800.00"),
            delta=Decimal("-200.00"),
            currency="USD",
        )

        # Assert
        assert event.delta == Decimal("-200.00")
        assert event.new_balance < event.previous_balance


@pytest.mark.unit
class TestAccountHoldingsUpdatedEvent:
    """Test AccountHoldingsUpdated event."""

    def test_creation_with_all_fields(self):
        """Test event creation with all required fields."""
        # Arrange
        user_id = UUID("12345678-1234-5678-1234-567812345678")
        account_id = UUID("87654321-4321-8765-4321-876543218765")

        # Act
        event = AccountHoldingsUpdated(
            user_id=user_id,
            account_id=account_id,
            holdings_count=10,
            created_count=3,
            updated_count=5,
            deactivated_count=2,
        )

        # Assert
        assert event.user_id == user_id
        assert event.account_id == account_id
        assert event.holdings_count == 10
        assert event.created_count == 3
        assert event.updated_count == 5
        assert event.deactivated_count == 2

    def test_event_id_auto_generated(self):
        """Test event_id is auto-generated when not provided."""
        # Act
        event = AccountHoldingsUpdated(
            user_id=UUID("12345678-1234-5678-1234-567812345678"),
            account_id=UUID("87654321-4321-8765-4321-876543218765"),
            holdings_count=5,
            created_count=1,
            updated_count=2,
            deactivated_count=0,
        )

        # Assert
        assert event.event_id is not None
        assert isinstance(event.event_id, UUID)

    def test_event_is_immutable(self):
        """Test event is immutable (frozen dataclass)."""
        # Arrange
        event = AccountHoldingsUpdated(
            user_id=UUID("12345678-1234-5678-1234-567812345678"),
            account_id=UUID("87654321-4321-8765-4321-876543218765"),
            holdings_count=5,
            created_count=1,
            updated_count=2,
            deactivated_count=0,
        )

        # Act & Assert
        with pytest.raises(AttributeError):
            event.holdings_count = 10  # type: ignore[misc]

    def test_inherits_from_domain_event(self):
        """Test event inherits from DomainEvent."""
        # Act
        event = AccountHoldingsUpdated(
            user_id=UUID("12345678-1234-5678-1234-567812345678"),
            account_id=UUID("87654321-4321-8765-4321-876543218765"),
            holdings_count=5,
            created_count=1,
            updated_count=2,
            deactivated_count=0,
        )

        # Assert
        assert isinstance(event, DomainEvent)

    def test_zero_counts_valid(self):
        """Test all counts can be zero (no changes)."""
        # Act
        event = AccountHoldingsUpdated(
            user_id=UUID("12345678-1234-5678-1234-567812345678"),
            account_id=UUID("87654321-4321-8765-4321-876543218765"),
            holdings_count=0,
            created_count=0,
            updated_count=0,
            deactivated_count=0,
        )

        # Assert
        assert event.holdings_count == 0
        assert event.created_count == 0
        assert event.updated_count == 0
        assert event.deactivated_count == 0


@pytest.mark.unit
class TestPortfolioNetWorthRecalculatedEvent:
    """Test PortfolioNetWorthRecalculated event."""

    def test_creation_with_all_fields(self):
        """Test event creation with all required fields."""
        # Arrange
        user_id = UUID("12345678-1234-5678-1234-567812345678")

        # Act
        event = PortfolioNetWorthRecalculated(
            user_id=user_id,
            previous_net_worth=Decimal("10000.00"),
            new_net_worth=Decimal("12500.00"),
            delta=Decimal("2500.00"),
            currency="USD",
            account_count=5,
        )

        # Assert
        assert event.user_id == user_id
        assert event.previous_net_worth == Decimal("10000.00")
        assert event.new_net_worth == Decimal("12500.00")
        assert event.delta == Decimal("2500.00")
        assert event.currency == "USD"
        assert event.account_count == 5

    def test_event_id_auto_generated(self):
        """Test event_id is auto-generated when not provided."""
        # Act
        event = PortfolioNetWorthRecalculated(
            user_id=UUID("12345678-1234-5678-1234-567812345678"),
            previous_net_worth=Decimal("0"),
            new_net_worth=Decimal("1000"),
            delta=Decimal("1000"),
            currency="USD",
            account_count=1,
        )

        # Assert
        assert event.event_id is not None
        assert isinstance(event.event_id, UUID)

    def test_occurred_at_auto_generated(self):
        """Test occurred_at timestamp is auto-generated in UTC."""
        # Arrange
        before = datetime.now(UTC)

        # Act
        event = PortfolioNetWorthRecalculated(
            user_id=UUID("12345678-1234-5678-1234-567812345678"),
            previous_net_worth=Decimal("0"),
            new_net_worth=Decimal("1000"),
            delta=Decimal("1000"),
            currency="USD",
            account_count=1,
        )

        after = datetime.now(UTC)

        # Assert
        assert event.occurred_at is not None
        assert isinstance(event.occurred_at, datetime)
        assert event.occurred_at.tzinfo == UTC
        assert before <= event.occurred_at <= after

    def test_event_is_immutable(self):
        """Test event is immutable (frozen dataclass)."""
        # Arrange
        event = PortfolioNetWorthRecalculated(
            user_id=UUID("12345678-1234-5678-1234-567812345678"),
            previous_net_worth=Decimal("0"),
            new_net_worth=Decimal("1000"),
            delta=Decimal("1000"),
            currency="USD",
            account_count=1,
        )

        # Act & Assert
        with pytest.raises(AttributeError):
            event.new_net_worth = Decimal("2000")  # type: ignore[misc]

    def test_inherits_from_domain_event(self):
        """Test event inherits from DomainEvent."""
        # Act
        event = PortfolioNetWorthRecalculated(
            user_id=UUID("12345678-1234-5678-1234-567812345678"),
            previous_net_worth=Decimal("0"),
            new_net_worth=Decimal("1000"),
            delta=Decimal("1000"),
            currency="USD",
            account_count=1,
        )

        # Assert
        assert isinstance(event, DomainEvent)

    def test_negative_delta_for_decrease(self):
        """Test delta can be negative for net worth decrease."""
        # Act
        event = PortfolioNetWorthRecalculated(
            user_id=UUID("12345678-1234-5678-1234-567812345678"),
            previous_net_worth=Decimal("10000.00"),
            new_net_worth=Decimal("8000.00"),
            delta=Decimal("-2000.00"),
            currency="USD",
            account_count=3,
        )

        # Assert
        assert event.delta == Decimal("-2000.00")
        assert event.new_net_worth < event.previous_net_worth

    def test_zero_net_worth_valid(self):
        """Test net worth can be zero (no accounts or all zero balances)."""
        # Act
        event = PortfolioNetWorthRecalculated(
            user_id=UUID("12345678-1234-5678-1234-567812345678"),
            previous_net_worth=Decimal("1000.00"),
            new_net_worth=Decimal("0"),
            delta=Decimal("-1000.00"),
            currency="USD",
            account_count=0,
        )

        # Assert
        assert event.new_net_worth == Decimal("0")
        assert event.account_count == 0
