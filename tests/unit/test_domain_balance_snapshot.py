"""Unit tests for BalanceSnapshot entity and SnapshotSource enum.

Tests:
    - SnapshotSource enum values and query methods
    - BalanceSnapshot entity creation and validation
    - BalanceSnapshot query methods
    - Currency consistency validation
    - Analytics calculations (percentage, change)
"""

import pytest
from datetime import UTC, datetime
from decimal import Decimal

from uuid_extensions import uuid7

from src.domain.entities.balance_snapshot import BalanceSnapshot
from src.domain.enums.snapshot_source import SnapshotSource
from src.domain.errors.balance_snapshot_error import BalanceSnapshotError
from src.domain.value_objects.money import Money


# =============================================================================
# SnapshotSource Enum Tests
# =============================================================================


class TestSnapshotSourceEnum:
    """Test SnapshotSource enum values and methods."""

    def test_snapshot_source_values(self) -> None:
        """Test all SnapshotSource enum values exist."""
        assert SnapshotSource.ACCOUNT_SYNC.value == "account_sync"
        assert SnapshotSource.HOLDINGS_SYNC.value == "holdings_sync"
        assert SnapshotSource.MANUAL_SYNC.value == "manual_sync"
        assert SnapshotSource.SCHEDULED_SYNC.value == "scheduled_sync"
        assert SnapshotSource.INITIAL_CONNECTION.value == "initial_connection"

    def test_is_automated_account_sync(self) -> None:
        """Test ACCOUNT_SYNC is automated."""
        assert SnapshotSource.ACCOUNT_SYNC.is_automated() is True
        assert SnapshotSource.ACCOUNT_SYNC.is_user_initiated() is False

    def test_is_automated_holdings_sync(self) -> None:
        """Test HOLDINGS_SYNC is automated."""
        assert SnapshotSource.HOLDINGS_SYNC.is_automated() is True
        assert SnapshotSource.HOLDINGS_SYNC.is_user_initiated() is False

    def test_is_automated_scheduled_sync(self) -> None:
        """Test SCHEDULED_SYNC is automated."""
        assert SnapshotSource.SCHEDULED_SYNC.is_automated() is True
        assert SnapshotSource.SCHEDULED_SYNC.is_user_initiated() is False

    def test_is_user_initiated_manual_sync(self) -> None:
        """Test MANUAL_SYNC is user initiated."""
        assert SnapshotSource.MANUAL_SYNC.is_user_initiated() is True
        assert SnapshotSource.MANUAL_SYNC.is_automated() is False

    def test_is_user_initiated_initial_connection(self) -> None:
        """Test INITIAL_CONNECTION is user initiated."""
        assert SnapshotSource.INITIAL_CONNECTION.is_user_initiated() is True
        assert SnapshotSource.INITIAL_CONNECTION.is_automated() is False


# =============================================================================
# BalanceSnapshot Entity Tests - Creation
# =============================================================================


class TestBalanceSnapshotCreation:
    """Test BalanceSnapshot entity creation and initialization."""

    def test_create_minimal_snapshot(self) -> None:
        """Test creating snapshot with required fields only."""
        snapshot_id = uuid7()
        account_id = uuid7()
        balance = Money(Decimal("10000.00"), "USD")

        snapshot = BalanceSnapshot(
            id=snapshot_id,
            account_id=account_id,
            balance=balance,
            currency="USD",
            source=SnapshotSource.ACCOUNT_SYNC,
        )

        assert snapshot.id == snapshot_id
        assert snapshot.account_id == account_id
        assert snapshot.balance == balance
        assert snapshot.currency == "USD"
        assert snapshot.source == SnapshotSource.ACCOUNT_SYNC
        assert snapshot.available_balance is None
        assert snapshot.holdings_value is None
        assert snapshot.cash_value is None
        assert snapshot.provider_metadata is None

    def test_create_full_snapshot(self) -> None:
        """Test creating snapshot with all fields."""
        snapshot_id = uuid7()
        account_id = uuid7()
        balance = Money(Decimal("10000.00"), "USD")
        available = Money(Decimal("9500.00"), "USD")
        holdings = Money(Decimal("8500.00"), "USD")
        cash = Money(Decimal("1500.00"), "USD")
        captured = datetime.now(UTC)
        metadata = {"raw_balance": "10000.00"}

        snapshot = BalanceSnapshot(
            id=snapshot_id,
            account_id=account_id,
            balance=balance,
            available_balance=available,
            holdings_value=holdings,
            cash_value=cash,
            currency="USD",
            source=SnapshotSource.MANUAL_SYNC,
            provider_metadata=metadata,
            captured_at=captured,
        )

        assert snapshot.balance == balance
        assert snapshot.available_balance == available
        assert snapshot.holdings_value == holdings
        assert snapshot.cash_value == cash
        assert snapshot.source == SnapshotSource.MANUAL_SYNC
        assert snapshot.provider_metadata == metadata
        assert snapshot.captured_at == captured

    def test_currency_normalized_to_uppercase(self) -> None:
        """Test that lowercase currency is normalized."""
        snapshot = BalanceSnapshot(
            id=uuid7(),
            account_id=uuid7(),
            balance=Money(Decimal("1000.00"), "USD"),
            currency="usd",
            source=SnapshotSource.ACCOUNT_SYNC,
        )

        assert snapshot.currency == "USD"

    def test_default_timestamps(self) -> None:
        """Test default timestamp generation."""
        before = datetime.now(UTC)

        snapshot = BalanceSnapshot(
            id=uuid7(),
            account_id=uuid7(),
            balance=Money(Decimal("1000.00"), "USD"),
            currency="USD",
            source=SnapshotSource.ACCOUNT_SYNC,
        )

        after = datetime.now(UTC)

        assert before <= snapshot.captured_at <= after
        assert before <= snapshot.created_at <= after


# =============================================================================
# BalanceSnapshot Validation Tests
# =============================================================================


class TestBalanceSnapshotValidation:
    """Test BalanceSnapshot validation rules."""

    def test_invalid_currency_empty(self) -> None:
        """Test that empty currency raises ValueError."""
        with pytest.raises(ValueError, match=BalanceSnapshotError.INVALID_CURRENCY):
            BalanceSnapshot(
                id=uuid7(),
                account_id=uuid7(),
                balance=Money(Decimal("1000.00"), "USD"),
                currency="",
                source=SnapshotSource.ACCOUNT_SYNC,
            )

    def test_invalid_currency_wrong_length(self) -> None:
        """Test that non-3-letter currency raises ValueError."""
        with pytest.raises(ValueError, match=BalanceSnapshotError.INVALID_CURRENCY):
            BalanceSnapshot(
                id=uuid7(),
                account_id=uuid7(),
                balance=Money(Decimal("1000.00"), "USD"),
                currency="US",
                source=SnapshotSource.ACCOUNT_SYNC,
            )

    def test_balance_currency_mismatch(self) -> None:
        """Test that balance currency must match snapshot currency."""
        with pytest.raises(ValueError, match="Balance currency.*must match"):
            BalanceSnapshot(
                id=uuid7(),
                account_id=uuid7(),
                balance=Money(Decimal("1000.00"), "EUR"),
                currency="USD",
                source=SnapshotSource.ACCOUNT_SYNC,
            )

    def test_available_balance_currency_mismatch(self) -> None:
        """Test that available_balance currency must match."""
        with pytest.raises(ValueError, match="Available balance currency.*must match"):
            BalanceSnapshot(
                id=uuid7(),
                account_id=uuid7(),
                balance=Money(Decimal("1000.00"), "USD"),
                available_balance=Money(Decimal("900.00"), "EUR"),
                currency="USD",
                source=SnapshotSource.ACCOUNT_SYNC,
            )

    def test_holdings_value_currency_mismatch(self) -> None:
        """Test that holdings_value currency must match."""
        with pytest.raises(ValueError, match="Holdings value currency.*must match"):
            BalanceSnapshot(
                id=uuid7(),
                account_id=uuid7(),
                balance=Money(Decimal("1000.00"), "USD"),
                holdings_value=Money(Decimal("800.00"), "GBP"),
                currency="USD",
                source=SnapshotSource.ACCOUNT_SYNC,
            )

    def test_cash_value_currency_mismatch(self) -> None:
        """Test that cash_value currency must match."""
        with pytest.raises(ValueError, match="Cash value currency.*must match"):
            BalanceSnapshot(
                id=uuid7(),
                account_id=uuid7(),
                balance=Money(Decimal("1000.00"), "USD"),
                cash_value=Money(Decimal("200.00"), "JPY"),
                currency="USD",
                source=SnapshotSource.ACCOUNT_SYNC,
            )

    def test_all_optional_currencies_must_match(self) -> None:
        """Test all Money fields must have matching currency."""
        # This should work - all currencies match
        snapshot = BalanceSnapshot(
            id=uuid7(),
            account_id=uuid7(),
            balance=Money(Decimal("10000.00"), "EUR"),
            available_balance=Money(Decimal("9500.00"), "EUR"),
            holdings_value=Money(Decimal("8000.00"), "EUR"),
            cash_value=Money(Decimal("2000.00"), "EUR"),
            currency="EUR",
            source=SnapshotSource.ACCOUNT_SYNC,
        )

        assert snapshot.currency == "EUR"
        assert snapshot.balance.currency == "EUR"


# =============================================================================
# BalanceSnapshot Query Methods Tests
# =============================================================================


class TestBalanceSnapshotQueryMethods:
    """Test BalanceSnapshot query methods."""

    def test_has_value_breakdown_true(self) -> None:
        """Test has_value_breakdown returns True when both values present."""
        snapshot = BalanceSnapshot(
            id=uuid7(),
            account_id=uuid7(),
            balance=Money(Decimal("10000.00"), "USD"),
            holdings_value=Money(Decimal("8000.00"), "USD"),
            cash_value=Money(Decimal("2000.00"), "USD"),
            currency="USD",
            source=SnapshotSource.ACCOUNT_SYNC,
        )

        assert snapshot.has_value_breakdown() is True

    def test_has_value_breakdown_false_no_holdings(self) -> None:
        """Test has_value_breakdown returns False without holdings_value."""
        snapshot = BalanceSnapshot(
            id=uuid7(),
            account_id=uuid7(),
            balance=Money(Decimal("10000.00"), "USD"),
            cash_value=Money(Decimal("2000.00"), "USD"),
            currency="USD",
            source=SnapshotSource.ACCOUNT_SYNC,
        )

        assert snapshot.has_value_breakdown() is False

    def test_has_value_breakdown_false_no_cash(self) -> None:
        """Test has_value_breakdown returns False without cash_value."""
        snapshot = BalanceSnapshot(
            id=uuid7(),
            account_id=uuid7(),
            balance=Money(Decimal("10000.00"), "USD"),
            holdings_value=Money(Decimal("8000.00"), "USD"),
            currency="USD",
            source=SnapshotSource.ACCOUNT_SYNC,
        )

        assert snapshot.has_value_breakdown() is False

    def test_get_holdings_percentage(self) -> None:
        """Test holdings percentage calculation."""
        snapshot = BalanceSnapshot(
            id=uuid7(),
            account_id=uuid7(),
            balance=Money(Decimal("10000.00"), "USD"),
            holdings_value=Money(Decimal("8500.00"), "USD"),
            cash_value=Money(Decimal("1500.00"), "USD"),
            currency="USD",
            source=SnapshotSource.ACCOUNT_SYNC,
        )

        assert snapshot.get_holdings_percentage() == 85.0

    def test_get_cash_percentage(self) -> None:
        """Test cash percentage calculation."""
        snapshot = BalanceSnapshot(
            id=uuid7(),
            account_id=uuid7(),
            balance=Money(Decimal("10000.00"), "USD"),
            holdings_value=Money(Decimal("8500.00"), "USD"),
            cash_value=Money(Decimal("1500.00"), "USD"),
            currency="USD",
            source=SnapshotSource.ACCOUNT_SYNC,
        )

        assert snapshot.get_cash_percentage() == 15.0

    def test_get_holdings_percentage_no_breakdown(self) -> None:
        """Test holdings percentage returns None without breakdown."""
        snapshot = BalanceSnapshot(
            id=uuid7(),
            account_id=uuid7(),
            balance=Money(Decimal("10000.00"), "USD"),
            currency="USD",
            source=SnapshotSource.ACCOUNT_SYNC,
        )

        assert snapshot.get_holdings_percentage() is None

    def test_get_cash_percentage_no_breakdown(self) -> None:
        """Test cash percentage returns None without breakdown."""
        snapshot = BalanceSnapshot(
            id=uuid7(),
            account_id=uuid7(),
            balance=Money(Decimal("10000.00"), "USD"),
            currency="USD",
            source=SnapshotSource.ACCOUNT_SYNC,
        )

        assert snapshot.get_cash_percentage() is None

    def test_get_holdings_percentage_zero_balance(self) -> None:
        """Test holdings percentage returns None for zero balance."""
        snapshot = BalanceSnapshot(
            id=uuid7(),
            account_id=uuid7(),
            balance=Money(Decimal("0.00"), "USD"),
            holdings_value=Money(Decimal("0.00"), "USD"),
            cash_value=Money(Decimal("0.00"), "USD"),
            currency="USD",
            source=SnapshotSource.ACCOUNT_SYNC,
        )

        assert snapshot.get_holdings_percentage() is None

    def test_is_automated_capture(self) -> None:
        """Test is_automated_capture for automated sources."""
        snapshot = BalanceSnapshot(
            id=uuid7(),
            account_id=uuid7(),
            balance=Money(Decimal("10000.00"), "USD"),
            currency="USD",
            source=SnapshotSource.SCHEDULED_SYNC,
        )

        assert snapshot.is_automated_capture() is True
        assert snapshot.is_user_initiated_capture() is False

    def test_is_user_initiated_capture(self) -> None:
        """Test is_user_initiated_capture for user sources."""
        snapshot = BalanceSnapshot(
            id=uuid7(),
            account_id=uuid7(),
            balance=Money(Decimal("10000.00"), "USD"),
            currency="USD",
            source=SnapshotSource.MANUAL_SYNC,
        )

        assert snapshot.is_user_initiated_capture() is True
        assert snapshot.is_automated_capture() is False


# =============================================================================
# BalanceSnapshot Calculate Change Tests
# =============================================================================


class TestBalanceSnapshotCalculateChange:
    """Test BalanceSnapshot change calculation methods."""

    def test_calculate_change_positive(self) -> None:
        """Test calculating positive change between snapshots."""
        account_id = uuid7()

        previous = BalanceSnapshot(
            id=uuid7(),
            account_id=account_id,
            balance=Money(Decimal("10000.00"), "USD"),
            currency="USD",
            source=SnapshotSource.ACCOUNT_SYNC,
        )

        current = BalanceSnapshot(
            id=uuid7(),
            account_id=account_id,
            balance=Money(Decimal("10500.00"), "USD"),
            currency="USD",
            source=SnapshotSource.ACCOUNT_SYNC,
        )

        result = current.calculate_change_from(previous)

        assert result is not None
        change_amount, change_percent = result
        assert change_amount.amount == Decimal("500.00")
        assert change_percent == 5.0

    def test_calculate_change_negative(self) -> None:
        """Test calculating negative change between snapshots."""
        account_id = uuid7()

        previous = BalanceSnapshot(
            id=uuid7(),
            account_id=account_id,
            balance=Money(Decimal("10000.00"), "USD"),
            currency="USD",
            source=SnapshotSource.ACCOUNT_SYNC,
        )

        current = BalanceSnapshot(
            id=uuid7(),
            account_id=account_id,
            balance=Money(Decimal("9000.00"), "USD"),
            currency="USD",
            source=SnapshotSource.ACCOUNT_SYNC,
        )

        result = current.calculate_change_from(previous)

        assert result is not None
        change_amount, change_percent = result
        assert change_amount.amount == Decimal("-1000.00")
        assert change_percent == -10.0

    def test_calculate_change_no_change(self) -> None:
        """Test calculating zero change between snapshots."""
        account_id = uuid7()
        balance = Money(Decimal("10000.00"), "USD")

        previous = BalanceSnapshot(
            id=uuid7(),
            account_id=account_id,
            balance=balance,
            currency="USD",
            source=SnapshotSource.ACCOUNT_SYNC,
        )

        current = BalanceSnapshot(
            id=uuid7(),
            account_id=account_id,
            balance=Money(Decimal("10000.00"), "USD"),
            currency="USD",
            source=SnapshotSource.ACCOUNT_SYNC,
        )

        result = current.calculate_change_from(previous)

        assert result is not None
        change_amount, change_percent = result
        assert change_amount.amount == Decimal("0.00")
        assert change_percent == 0.0

    def test_calculate_change_currency_mismatch(self) -> None:
        """Test calculate_change_from returns None for different currencies."""
        previous = BalanceSnapshot(
            id=uuid7(),
            account_id=uuid7(),
            balance=Money(Decimal("10000.00"), "USD"),
            currency="USD",
            source=SnapshotSource.ACCOUNT_SYNC,
        )

        current = BalanceSnapshot(
            id=uuid7(),
            account_id=uuid7(),
            balance=Money(Decimal("9000.00"), "EUR"),
            currency="EUR",
            source=SnapshotSource.ACCOUNT_SYNC,
        )

        result = current.calculate_change_from(previous)

        assert result is None

    def test_calculate_change_from_zero_balance(self) -> None:
        """Test calculating change from zero balance."""
        account_id = uuid7()

        previous = BalanceSnapshot(
            id=uuid7(),
            account_id=account_id,
            balance=Money(Decimal("0.00"), "USD"),
            currency="USD",
            source=SnapshotSource.INITIAL_CONNECTION,
        )

        current = BalanceSnapshot(
            id=uuid7(),
            account_id=account_id,
            balance=Money(Decimal("10000.00"), "USD"),
            currency="USD",
            source=SnapshotSource.ACCOUNT_SYNC,
        )

        result = current.calculate_change_from(previous)

        assert result is not None
        change_amount, change_percent = result
        assert change_amount.amount == Decimal("10000.00")
        assert change_percent == float("inf")

    def test_calculate_change_both_zero(self) -> None:
        """Test calculating change when both are zero."""
        account_id = uuid7()

        previous = BalanceSnapshot(
            id=uuid7(),
            account_id=account_id,
            balance=Money(Decimal("0.00"), "USD"),
            currency="USD",
            source=SnapshotSource.INITIAL_CONNECTION,
        )

        current = BalanceSnapshot(
            id=uuid7(),
            account_id=account_id,
            balance=Money(Decimal("0.00"), "USD"),
            currency="USD",
            source=SnapshotSource.ACCOUNT_SYNC,
        )

        result = current.calculate_change_from(previous)

        assert result is not None
        change_amount, change_percent = result
        assert change_amount.amount == Decimal("0.00")
        assert change_percent == 0.0


# =============================================================================
# BalanceSnapshot Immutability Tests
# =============================================================================


class TestBalanceSnapshotImmutability:
    """Test BalanceSnapshot immutability (frozen dataclass)."""

    def test_cannot_modify_balance(self) -> None:
        """Test that balance cannot be modified after creation."""
        snapshot = BalanceSnapshot(
            id=uuid7(),
            account_id=uuid7(),
            balance=Money(Decimal("10000.00"), "USD"),
            currency="USD",
            source=SnapshotSource.ACCOUNT_SYNC,
        )

        with pytest.raises(AttributeError):
            snapshot.balance = Money(Decimal("20000.00"), "USD")  # type: ignore

    def test_cannot_modify_source(self) -> None:
        """Test that source cannot be modified after creation."""
        snapshot = BalanceSnapshot(
            id=uuid7(),
            account_id=uuid7(),
            balance=Money(Decimal("10000.00"), "USD"),
            currency="USD",
            source=SnapshotSource.ACCOUNT_SYNC,
        )

        with pytest.raises(AttributeError):
            snapshot.source = SnapshotSource.MANUAL_SYNC  # type: ignore

    def test_cannot_modify_account_id(self) -> None:
        """Test that account_id cannot be modified after creation."""
        snapshot = BalanceSnapshot(
            id=uuid7(),
            account_id=uuid7(),
            balance=Money(Decimal("10000.00"), "USD"),
            currency="USD",
            source=SnapshotSource.ACCOUNT_SYNC,
        )

        with pytest.raises(AttributeError):
            snapshot.account_id = uuid7()  # type: ignore


# =============================================================================
# BalanceSnapshotError Tests
# =============================================================================


class TestBalanceSnapshotError:
    """Test BalanceSnapshotError constants."""

    def test_validation_errors_exist(self) -> None:
        """Test validation error constants exist."""
        assert BalanceSnapshotError.INVALID_BALANCE
        assert BalanceSnapshotError.INVALID_CURRENCY
        assert BalanceSnapshotError.CURRENCY_MISMATCH

    def test_query_errors_exist(self) -> None:
        """Test query error constants exist."""
        assert BalanceSnapshotError.SNAPSHOT_NOT_FOUND
        assert BalanceSnapshotError.ACCOUNT_NOT_FOUND

    def test_time_range_errors_exist(self) -> None:
        """Test time range error constants exist."""
        assert BalanceSnapshotError.INVALID_DATE_RANGE
        assert BalanceSnapshotError.DATE_RANGE_TOO_LARGE
