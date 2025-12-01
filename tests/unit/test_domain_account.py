"""Unit tests for Account domain entity.

Tests cover:
- Entity creation with all fields
- Query methods (is_investment_account, needs_sync, etc.)
- Update methods with Result types
- Validation and error handling

Architecture:
- Unit tests for domain entity (no dependencies)
- Tests pure business logic and validation
- Validates entity invariants and business rules
- All update methods return Result types (ROP)
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID
from uuid_extensions import uuid7

import pytest

from src.core.result import Failure, Success
from src.domain.entities.account import Account
from src.domain.enums.account_type import AccountType
from src.domain.errors.account_error import AccountError
from src.domain.value_objects.money import Money


# =============================================================================
# Test Fixtures and Helpers
# =============================================================================


def create_account(
    account_id: UUID | None = None,
    connection_id: UUID | None = None,
    provider_account_id: str = "SCHWAB-12345",
    account_number_masked: str = "****1234",
    name: str = "Individual Brokerage",
    account_type: AccountType = AccountType.BROKERAGE,
    balance: Money | None = None,
    available_balance: Money | None = None,
    currency: str = "USD",
    is_active: bool = True,
    last_synced_at: datetime | None = None,
    provider_metadata: dict | None = None,
) -> Account:
    """Helper to create Account entities for testing."""
    if balance is None:
        balance = Money(Decimal("10000.00"), currency)
    return Account(
        id=account_id or uuid7(),
        connection_id=connection_id or uuid7(),
        provider_account_id=provider_account_id,
        account_number_masked=account_number_masked,
        name=name,
        account_type=account_type,
        balance=balance,
        available_balance=available_balance,
        currency=currency,
        is_active=is_active,
        last_synced_at=last_synced_at,
        provider_metadata=provider_metadata,
    )


# =============================================================================
# AccountType Enum Tests
# =============================================================================


@pytest.mark.unit
class TestAccountTypeEnum:
    """Test AccountType enum helper methods."""

    def test_values_returns_all_types(self):
        """Test values() returns all account type strings."""
        values = AccountType.values()
        assert len(values) == 15
        assert "brokerage" in values
        assert "checking" in values
        assert "credit_card" in values

    def test_is_valid_for_valid_types(self):
        """Test is_valid returns True for valid types."""
        assert AccountType.is_valid("brokerage") is True
        assert AccountType.is_valid("checking") is True
        assert AccountType.is_valid("401k") is True

    def test_is_valid_false_for_invalid_types(self):
        """Test is_valid returns False for invalid types."""
        assert AccountType.is_valid("invalid") is False
        assert AccountType.is_valid("BROKERAGE") is False  # Case sensitive
        assert AccountType.is_valid("") is False

    def test_investment_types_returns_correct_list(self):
        """Test investment_types returns investment accounts."""
        inv_types = AccountType.investment_types()
        assert len(inv_types) == 6
        assert AccountType.BROKERAGE in inv_types
        assert AccountType.IRA in inv_types
        assert AccountType.ROTH_IRA in inv_types
        assert AccountType.RETIREMENT_401K in inv_types
        assert AccountType.RETIREMENT_403B in inv_types
        assert AccountType.HSA in inv_types
        assert AccountType.CHECKING not in inv_types

    def test_bank_types_returns_correct_list(self):
        """Test bank_types returns banking accounts."""
        bank_types = AccountType.bank_types()
        assert len(bank_types) == 4
        assert AccountType.CHECKING in bank_types
        assert AccountType.SAVINGS in bank_types
        assert AccountType.MONEY_MARKET in bank_types
        assert AccountType.CD in bank_types
        assert AccountType.BROKERAGE not in bank_types

    def test_retirement_types_returns_correct_list(self):
        """Test retirement_types returns retirement accounts."""
        ret_types = AccountType.retirement_types()
        assert len(ret_types) == 5
        assert AccountType.IRA in ret_types
        assert AccountType.ROTH_IRA in ret_types
        assert AccountType.RETIREMENT_401K in ret_types
        assert AccountType.RETIREMENT_403B in ret_types
        assert AccountType.HSA in ret_types
        assert AccountType.BROKERAGE not in ret_types

    def test_credit_types_returns_correct_list(self):
        """Test credit_types returns credit accounts."""
        credit_types = AccountType.credit_types()
        assert len(credit_types) == 4
        assert AccountType.CREDIT_CARD in credit_types
        assert AccountType.LINE_OF_CREDIT in credit_types
        assert AccountType.LOAN in credit_types
        assert AccountType.MORTGAGE in credit_types
        assert AccountType.CHECKING not in credit_types

    def test_instance_is_investment(self):
        """Test is_investment instance method."""
        assert AccountType.BROKERAGE.is_investment() is True
        assert AccountType.CHECKING.is_investment() is False

    def test_instance_is_bank(self):
        """Test is_bank instance method."""
        assert AccountType.CHECKING.is_bank() is True
        assert AccountType.BROKERAGE.is_bank() is False

    def test_instance_is_retirement(self):
        """Test is_retirement instance method."""
        assert AccountType.IRA.is_retirement() is True
        assert AccountType.BROKERAGE.is_retirement() is False

    def test_instance_is_credit(self):
        """Test is_credit instance method."""
        assert AccountType.CREDIT_CARD.is_credit() is True
        assert AccountType.CHECKING.is_credit() is False

    def test_category_property(self):
        """Test category property returns correct category."""
        assert AccountType.BROKERAGE.category == "investment"
        assert AccountType.CHECKING.category == "banking"
        assert AccountType.CREDIT_CARD.category == "credit"
        assert AccountType.OTHER.category == "other"


# =============================================================================
# Account Creation Tests
# =============================================================================


@pytest.mark.unit
class TestAccountCreation:
    """Test Account entity creation."""

    def test_account_created_with_required_fields(self):
        """Test account can be created with all required fields."""
        account_id = uuid7()
        connection_id = uuid7()
        balance = Money(Decimal("10000.00"), "USD")

        account = Account(
            id=account_id,
            connection_id=connection_id,
            provider_account_id="SCHWAB-12345",
            account_number_masked="****1234",
            name="Individual Brokerage",
            account_type=AccountType.BROKERAGE,
            balance=balance,
            currency="USD",
        )

        assert account.id == account_id
        assert account.connection_id == connection_id
        assert account.provider_account_id == "SCHWAB-12345"
        assert account.account_number_masked == "****1234"
        assert account.name == "Individual Brokerage"
        assert account.account_type == AccountType.BROKERAGE
        assert account.balance == balance
        assert account.currency == "USD"
        assert account.is_active is True
        assert account.available_balance is None
        assert account.last_synced_at is None
        assert account.provider_metadata is None
        assert account.created_at is not None
        assert account.updated_at is not None

    def test_account_created_with_available_balance(self):
        """Test account can be created with available balance."""
        balance = Money(Decimal("10000.00"), "USD")
        available = Money(Decimal("9500.00"), "USD")

        account = create_account(balance=balance, available_balance=available)

        assert account.balance == balance
        assert account.available_balance == available

    def test_account_normalizes_currency_to_uppercase(self):
        """Test currency is normalized to uppercase."""
        account = create_account(currency="usd")
        assert account.currency == "USD"

    def test_account_raises_error_for_empty_provider_account_id(self):
        """Test creation fails with empty provider_account_id."""
        with pytest.raises(ValueError) as exc_info:
            create_account(provider_account_id="")
        assert AccountError.INVALID_PROVIDER_ACCOUNT_ID in str(exc_info.value)

    def test_account_raises_error_for_whitespace_provider_account_id(self):
        """Test creation fails with whitespace provider_account_id."""
        with pytest.raises(ValueError) as exc_info:
            create_account(provider_account_id="   ")
        assert AccountError.INVALID_PROVIDER_ACCOUNT_ID in str(exc_info.value)

    def test_account_raises_error_for_empty_account_number(self):
        """Test creation fails with empty account_number_masked."""
        with pytest.raises(ValueError) as exc_info:
            create_account(account_number_masked="")
        assert AccountError.INVALID_ACCOUNT_NUMBER in str(exc_info.value)

    def test_account_raises_error_for_empty_name(self):
        """Test creation fails with empty name."""
        with pytest.raises(ValueError) as exc_info:
            create_account(name="")
        assert AccountError.INVALID_ACCOUNT_NAME in str(exc_info.value)

    def test_account_raises_error_for_balance_currency_mismatch(self):
        """Test creation fails if balance currency doesn't match account currency."""
        balance = Money(Decimal("10000.00"), "EUR")
        with pytest.raises(ValueError) as exc_info:
            create_account(balance=balance, currency="USD")
        assert "Balance currency" in str(exc_info.value)

    def test_account_raises_error_for_available_balance_currency_mismatch(self):
        """Test creation fails if available_balance currency doesn't match."""
        balance = Money(Decimal("10000.00"), "USD")
        available = Money(Decimal("9000.00"), "EUR")
        with pytest.raises(ValueError) as exc_info:
            create_account(
                balance=balance,
                available_balance=available,
                currency="USD",
            )
        assert "Available balance currency" in str(exc_info.value)


# =============================================================================
# Query Method Tests
# =============================================================================


@pytest.mark.unit
class TestAccountQueryMethods:
    """Test Account query methods."""

    def test_is_investment_account_true(self):
        """Test is_investment_account returns True for investment types."""
        account = create_account(account_type=AccountType.BROKERAGE)
        assert account.is_investment_account() is True

        account = create_account(account_type=AccountType.IRA)
        assert account.is_investment_account() is True

    def test_is_investment_account_false(self):
        """Test is_investment_account returns False for non-investment types."""
        account = create_account(account_type=AccountType.CHECKING)
        assert account.is_investment_account() is False

    def test_is_bank_account_true(self):
        """Test is_bank_account returns True for banking types."""
        account = create_account(account_type=AccountType.CHECKING)
        assert account.is_bank_account() is True

        account = create_account(account_type=AccountType.SAVINGS)
        assert account.is_bank_account() is True

    def test_is_bank_account_false(self):
        """Test is_bank_account returns False for non-banking types."""
        account = create_account(account_type=AccountType.BROKERAGE)
        assert account.is_bank_account() is False

    def test_is_retirement_account_true(self):
        """Test is_retirement_account returns True for retirement types."""
        account = create_account(account_type=AccountType.IRA)
        assert account.is_retirement_account() is True

    def test_is_retirement_account_false(self):
        """Test is_retirement_account returns False for non-retirement types."""
        account = create_account(account_type=AccountType.BROKERAGE)
        assert account.is_retirement_account() is False

    def test_is_credit_account_true(self):
        """Test is_credit_account returns True for credit types."""
        account = create_account(account_type=AccountType.CREDIT_CARD)
        assert account.is_credit_account() is True

    def test_is_credit_account_false(self):
        """Test is_credit_account returns False for non-credit types."""
        account = create_account(account_type=AccountType.CHECKING)
        assert account.is_credit_account() is False

    def test_has_available_balance_true(self):
        """Test has_available_balance returns True when balances differ."""
        balance = Money(Decimal("1000.00"), "USD")
        available = Money(Decimal("900.00"), "USD")
        account = create_account(balance=balance, available_balance=available)
        assert account.has_available_balance() is True

    def test_has_available_balance_false_when_none(self):
        """Test has_available_balance returns False when None."""
        account = create_account(available_balance=None)
        assert account.has_available_balance() is False

    def test_has_available_balance_false_when_equal(self):
        """Test has_available_balance returns False when balances equal."""
        balance = Money(Decimal("1000.00"), "USD")
        account = create_account(balance=balance, available_balance=balance)
        assert account.has_available_balance() is False

    def test_needs_sync_true_when_never_synced(self):
        """Test needs_sync returns True when never synced."""
        account = create_account(last_synced_at=None)
        assert account.needs_sync(timedelta(hours=1)) is True

    def test_needs_sync_true_when_threshold_exceeded(self):
        """Test needs_sync returns True when threshold exceeded."""
        old_sync = datetime.now(UTC) - timedelta(hours=2)
        account = create_account(last_synced_at=old_sync)
        assert account.needs_sync(timedelta(hours=1)) is True

    def test_needs_sync_false_when_recently_synced(self):
        """Test needs_sync returns False when recently synced."""
        recent_sync = datetime.now(UTC) - timedelta(minutes=30)
        account = create_account(last_synced_at=recent_sync)
        assert account.needs_sync(timedelta(hours=1)) is False

    def test_get_display_name(self):
        """Test get_display_name returns formatted string."""
        account = create_account(
            name="Individual Brokerage",
            account_number_masked="****5678",
        )
        assert account.get_display_name() == "Individual Brokerage (****5678)"


# =============================================================================
# Update Method Tests (Result Types)
# =============================================================================


@pytest.mark.unit
class TestAccountUpdateMethods:
    """Test Account update methods with Result types."""

    def test_update_balance_success(self):
        """Test update_balance succeeds with matching currency."""
        account = create_account()
        new_balance = Money(Decimal("15000.00"), "USD")
        new_available = Money(Decimal("14000.00"), "USD")

        result = account.update_balance(new_balance, new_available)

        assert isinstance(result, Success)
        assert account.balance == new_balance
        assert account.available_balance == new_available

    def test_update_balance_updates_timestamp(self):
        """Test update_balance updates updated_at timestamp."""
        account = create_account()
        original_updated = account.updated_at
        new_balance = Money(Decimal("15000.00"), "USD")

        account.update_balance(new_balance)

        assert account.updated_at > original_updated

    def test_update_balance_fails_currency_mismatch(self):
        """Test update_balance fails with currency mismatch."""
        account = create_account(currency="USD")
        new_balance = Money(Decimal("15000.00"), "EUR")

        result = account.update_balance(new_balance)

        assert isinstance(result, Failure)
        assert "currency" in result.error.lower()

    def test_update_balance_fails_available_currency_mismatch(self):
        """Test update_balance fails with available balance currency mismatch."""
        account = create_account(currency="USD")
        new_balance = Money(Decimal("15000.00"), "USD")
        new_available = Money(Decimal("14000.00"), "EUR")

        result = account.update_balance(new_balance, new_available)

        assert isinstance(result, Failure)
        assert "Available balance currency" in result.error

    def test_update_from_provider_success_name(self):
        """Test update_from_provider updates name."""
        account = create_account(name="Old Name")

        result = account.update_from_provider(name="New Name")

        assert isinstance(result, Success)
        assert account.name == "New Name"

    def test_update_from_provider_success_is_active(self):
        """Test update_from_provider updates is_active."""
        account = create_account(is_active=True)

        result = account.update_from_provider(is_active=False)

        assert isinstance(result, Success)
        assert account.is_active is False

    def test_update_from_provider_success_metadata(self):
        """Test update_from_provider updates metadata."""
        account = create_account()
        metadata = {"key": "value"}

        result = account.update_from_provider(provider_metadata=metadata)

        assert isinstance(result, Success)
        assert account.provider_metadata == metadata

    def test_update_from_provider_fails_empty_name(self):
        """Test update_from_provider fails with empty name."""
        account = create_account()

        result = account.update_from_provider(name="")

        assert isinstance(result, Failure)
        assert AccountError.INVALID_ACCOUNT_NAME in result.error

    def test_update_from_provider_fails_whitespace_name(self):
        """Test update_from_provider fails with whitespace name."""
        account = create_account()

        result = account.update_from_provider(name="   ")

        assert isinstance(result, Failure)
        assert AccountError.INVALID_ACCOUNT_NAME in result.error

    def test_update_from_provider_ignores_none_values(self):
        """Test update_from_provider ignores None values."""
        account = create_account(name="Original", is_active=True)

        result = account.update_from_provider(name=None, is_active=None)

        assert isinstance(result, Success)
        assert account.name == "Original"
        assert account.is_active is True

    def test_mark_synced_updates_timestamps(self):
        """Test mark_synced updates both timestamps."""
        account = create_account(last_synced_at=None)
        original_updated = account.updated_at

        result = account.mark_synced()

        assert isinstance(result, Success)
        assert account.last_synced_at is not None
        assert account.updated_at > original_updated
        assert account.last_synced_at == account.updated_at

    def test_deactivate_sets_inactive(self):
        """Test deactivate sets is_active to False."""
        account = create_account(is_active=True)

        result = account.deactivate()

        assert isinstance(result, Success)
        assert account.is_active is False

    def test_activate_sets_active(self):
        """Test activate sets is_active to True."""
        account = create_account(is_active=False)

        result = account.activate()

        assert isinstance(result, Success)
        assert account.is_active is True


# =============================================================================
# Edge Case Tests
# =============================================================================


@pytest.mark.unit
class TestAccountEdgeCases:
    """Test Account edge cases."""

    def test_account_with_negative_balance(self):
        """Test account can have negative balance (e.g., credit card)."""
        balance = Money(Decimal("-500.00"), "USD")
        account = create_account(
            account_type=AccountType.CREDIT_CARD,
            balance=balance,
        )
        assert account.balance.amount == Decimal("-500.00")

    def test_account_with_zero_balance(self):
        """Test account can have zero balance."""
        balance = Money(Decimal("0.00"), "USD")
        account = create_account(balance=balance)
        assert account.balance.is_zero() is True

    def test_account_with_provider_metadata(self):
        """Test account stores provider metadata."""
        metadata = {
            "account_id": "schwab-internal-123",
            "margin_enabled": True,
            "day_trades_remaining": 3,
        }
        account = create_account(provider_metadata=metadata)
        assert account.provider_metadata == metadata
        assert account.provider_metadata["margin_enabled"] is True

    def test_account_uuid_fields_are_proper_uuids(self):
        """Test id and connection_id are proper UUIDs."""
        account = create_account()
        assert isinstance(account.id, UUID)
        assert isinstance(account.connection_id, UUID)
