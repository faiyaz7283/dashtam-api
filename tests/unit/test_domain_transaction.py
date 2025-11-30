"""Unit tests for Transaction domain model.

Tests cover:
- TransactionType enum (5 values + helpers)
- TransactionSubtype enum (24 values + helpers)
- AssetType enum (9 values)
- TransactionStatus enum (4 values + helpers)
- Transaction entity (creation, query methods, immutability)

Coverage target: 100%
"""

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from src.domain.entities.transaction import Transaction
from src.domain.enums.asset_type import AssetType
from src.domain.enums.transaction_status import TransactionStatus
from src.domain.enums.transaction_subtype import TransactionSubtype
from src.domain.enums.transaction_type import TransactionType
from src.domain.value_objects.money import Money


# ==============================================================================
# TransactionType Enum Tests
# ==============================================================================


class TestTransactionType:
    """Test TransactionType enum."""

    def test_all_values_exist(self):
        """Verify all 5 transaction types exist."""
        assert TransactionType.TRADE == "trade"
        assert TransactionType.TRANSFER == "transfer"
        assert TransactionType.INCOME == "income"
        assert TransactionType.FEE == "fee"
        assert TransactionType.OTHER == "other"

    def test_enum_count(self):
        """Verify exactly 5 transaction types."""
        assert len(TransactionType) == 5

    def test_security_related_returns_trade_and_income(self):
        """security_related() should return TRADE and INCOME."""
        security_types = TransactionType.security_related()

        assert len(security_types) == 2
        assert TransactionType.TRADE in security_types
        assert TransactionType.INCOME in security_types

    def test_security_related_excludes_others(self):
        """security_related() should exclude TRANSFER, FEE, OTHER."""
        security_types = TransactionType.security_related()

        assert TransactionType.TRANSFER not in security_types
        assert TransactionType.FEE not in security_types
        assert TransactionType.OTHER not in security_types

    def test_string_representation(self):
        """Enum values should be lowercase strings."""
        for tx_type in TransactionType:
            assert isinstance(tx_type.value, str)
            assert tx_type.value == tx_type.value.lower()


# ==============================================================================
# TransactionSubtype Enum Tests
# ==============================================================================


class TestTransactionSubtype:
    """Test TransactionSubtype enum."""

    def test_all_trade_subtypes_exist(self):
        """Verify all 7 TRADE subtypes exist."""
        assert TransactionSubtype.BUY == "buy"
        assert TransactionSubtype.SELL == "sell"
        assert TransactionSubtype.SHORT_SELL == "short_sell"
        assert TransactionSubtype.BUY_TO_COVER == "buy_to_cover"
        assert TransactionSubtype.EXERCISE == "exercise"
        assert TransactionSubtype.ASSIGNMENT == "assignment"
        assert TransactionSubtype.EXPIRATION == "expiration"

    def test_all_transfer_subtypes_exist(self):
        """Verify all 7 TRANSFER subtypes exist."""
        assert TransactionSubtype.DEPOSIT == "deposit"
        assert TransactionSubtype.WITHDRAWAL == "withdrawal"
        assert TransactionSubtype.WIRE_IN == "wire_in"
        assert TransactionSubtype.WIRE_OUT == "wire_out"
        assert TransactionSubtype.TRANSFER_IN == "transfer_in"
        assert TransactionSubtype.TRANSFER_OUT == "transfer_out"
        assert TransactionSubtype.INTERNAL == "internal"

    def test_all_income_subtypes_exist(self):
        """Verify all 4 INCOME subtypes exist."""
        assert TransactionSubtype.DIVIDEND == "dividend"
        assert TransactionSubtype.INTEREST == "interest"
        assert TransactionSubtype.CAPITAL_GAIN == "capital_gain"
        assert TransactionSubtype.DISTRIBUTION == "distribution"

    def test_all_fee_subtypes_exist(self):
        """Verify all 4 FEE subtypes exist."""
        assert TransactionSubtype.COMMISSION == "commission"
        assert TransactionSubtype.ACCOUNT_FEE == "account_fee"
        assert TransactionSubtype.MARGIN_INTEREST == "margin_interest"
        assert TransactionSubtype.OTHER_FEE == "other_fee"

    def test_all_other_subtypes_exist(self):
        """Verify all 3 OTHER subtypes exist."""
        assert TransactionSubtype.ADJUSTMENT == "adjustment"
        assert TransactionSubtype.JOURNAL == "journal"
        assert TransactionSubtype.UNKNOWN == "unknown"

    def test_enum_count(self):
        """Verify exactly 25 transaction subtypes."""
        assert len(TransactionSubtype) == 25

    def test_trade_subtypes_helper(self):
        """trade_subtypes() should return all 7 TRADE subtypes."""
        trade_subtypes = TransactionSubtype.trade_subtypes()

        assert len(trade_subtypes) == 7
        assert TransactionSubtype.BUY in trade_subtypes
        assert TransactionSubtype.SELL in trade_subtypes
        assert TransactionSubtype.SHORT_SELL in trade_subtypes
        assert TransactionSubtype.BUY_TO_COVER in trade_subtypes
        assert TransactionSubtype.EXERCISE in trade_subtypes
        assert TransactionSubtype.ASSIGNMENT in trade_subtypes
        assert TransactionSubtype.EXPIRATION in trade_subtypes

    def test_transfer_subtypes_helper(self):
        """transfer_subtypes() should return all 7 TRANSFER subtypes."""
        transfer_subtypes = TransactionSubtype.transfer_subtypes()

        assert len(transfer_subtypes) == 7
        assert TransactionSubtype.DEPOSIT in transfer_subtypes
        assert TransactionSubtype.WITHDRAWAL in transfer_subtypes
        assert TransactionSubtype.WIRE_IN in transfer_subtypes
        assert TransactionSubtype.WIRE_OUT in transfer_subtypes
        assert TransactionSubtype.TRANSFER_IN in transfer_subtypes
        assert TransactionSubtype.TRANSFER_OUT in transfer_subtypes
        assert TransactionSubtype.INTERNAL in transfer_subtypes

    def test_income_subtypes_helper(self):
        """income_subtypes() should return all 4 INCOME subtypes."""
        income_subtypes = TransactionSubtype.income_subtypes()

        assert len(income_subtypes) == 4
        assert TransactionSubtype.DIVIDEND in income_subtypes
        assert TransactionSubtype.INTEREST in income_subtypes
        assert TransactionSubtype.CAPITAL_GAIN in income_subtypes
        assert TransactionSubtype.DISTRIBUTION in income_subtypes

    def test_fee_subtypes_helper(self):
        """fee_subtypes() should return all 4 FEE subtypes."""
        fee_subtypes = TransactionSubtype.fee_subtypes()

        assert len(fee_subtypes) == 4
        assert TransactionSubtype.COMMISSION in fee_subtypes
        assert TransactionSubtype.ACCOUNT_FEE in fee_subtypes
        assert TransactionSubtype.MARGIN_INTEREST in fee_subtypes
        assert TransactionSubtype.OTHER_FEE in fee_subtypes


# ==============================================================================
# AssetType Enum Tests
# ==============================================================================


class TestAssetType:
    """Test AssetType enum."""

    def test_all_values_exist(self):
        """Verify all 9 asset types exist."""
        assert AssetType.EQUITY == "equity"
        assert AssetType.ETF == "etf"
        assert AssetType.OPTION == "option"
        assert AssetType.MUTUAL_FUND == "mutual_fund"
        assert AssetType.FIXED_INCOME == "fixed_income"
        assert AssetType.FUTURES == "futures"
        assert AssetType.CRYPTOCURRENCY == "cryptocurrency"
        assert AssetType.CASH_EQUIVALENT == "cash_equivalent"
        assert AssetType.OTHER == "other"

    def test_enum_count(self):
        """Verify exactly 9 asset types."""
        assert len(AssetType) == 9

    def test_string_representation(self):
        """Enum values should be lowercase strings."""
        for asset_type in AssetType:
            assert isinstance(asset_type.value, str)
            assert asset_type.value == asset_type.value.lower()


# ==============================================================================
# TransactionStatus Enum Tests
# ==============================================================================


class TestTransactionStatus:
    """Test TransactionStatus enum."""

    def test_all_values_exist(self):
        """Verify all 4 transaction statuses exist."""
        assert TransactionStatus.PENDING == "pending"
        assert TransactionStatus.SETTLED == "settled"
        assert TransactionStatus.FAILED == "failed"
        assert TransactionStatus.CANCELLED == "cancelled"

    def test_enum_count(self):
        """Verify exactly 4 transaction statuses."""
        assert len(TransactionStatus) == 4

    def test_terminal_states_returns_three(self):
        """terminal_states() should return SETTLED, FAILED, CANCELLED."""
        terminal = TransactionStatus.terminal_states()

        assert len(terminal) == 3
        assert TransactionStatus.SETTLED in terminal
        assert TransactionStatus.FAILED in terminal
        assert TransactionStatus.CANCELLED in terminal

    def test_terminal_states_excludes_pending(self):
        """terminal_states() should exclude PENDING."""
        terminal = TransactionStatus.terminal_states()

        assert TransactionStatus.PENDING not in terminal

    def test_active_states_returns_pending_only(self):
        """active_states() should return only PENDING."""
        active = TransactionStatus.active_states()

        assert len(active) == 1
        assert TransactionStatus.PENDING in active

    def test_active_states_excludes_terminals(self):
        """active_states() should exclude terminal states."""
        active = TransactionStatus.active_states()

        assert TransactionStatus.SETTLED not in active
        assert TransactionStatus.FAILED not in active
        assert TransactionStatus.CANCELLED not in active


# ==============================================================================
# Transaction Entity Tests
# ==============================================================================


class TestTransactionCreation:
    """Test Transaction entity creation."""

    def test_create_minimal_transaction(self):
        """Create transaction with only required fields."""
        transaction_id = uuid4()
        account_id = uuid4()
        now = datetime.now(UTC)

        transaction = Transaction(
            id=transaction_id,
            account_id=account_id,
            provider_transaction_id="provider-12345",
            transaction_type=TransactionType.TRANSFER,
            subtype=TransactionSubtype.DEPOSIT,
            status=TransactionStatus.SETTLED,
            amount=Money(amount=Decimal("100.00"), currency="USD"),
            description="Test deposit",
            transaction_date=date(2025, 11, 30),
            created_at=now,
            updated_at=now,
        )

        assert transaction.id == transaction_id
        assert transaction.account_id == account_id
        assert transaction.provider_transaction_id == "provider-12345"
        assert transaction.transaction_type == TransactionType.TRANSFER
        assert transaction.subtype == TransactionSubtype.DEPOSIT
        assert transaction.status == TransactionStatus.SETTLED
        assert transaction.amount.amount == Decimal("100.00")
        assert transaction.amount.currency == "USD"
        assert transaction.description == "Test deposit"
        assert transaction.transaction_date == date(2025, 11, 30)

    def test_create_trade_transaction_with_security_details(self):
        """Create trade transaction with all security fields."""
        transaction = Transaction(
            id=uuid4(),
            account_id=uuid4(),
            provider_transaction_id="trade-123",
            transaction_type=TransactionType.TRADE,
            subtype=TransactionSubtype.BUY,
            status=TransactionStatus.SETTLED,
            amount=Money(amount=Decimal("-1050.00"), currency="USD"),
            description="Bought 10 shares of AAPL",
            asset_type=AssetType.EQUITY,
            symbol="AAPL",
            security_name="Apple Inc.",
            quantity=Decimal("10"),
            unit_price=Money(amount=Decimal("105.00"), currency="USD"),
            commission=Money(amount=Decimal("0.00"), currency="USD"),
            transaction_date=date(2025, 11, 28),
            settlement_date=date(2025, 11, 30),
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        assert transaction.transaction_type == TransactionType.TRADE
        assert transaction.subtype == TransactionSubtype.BUY
        assert transaction.asset_type == AssetType.EQUITY
        assert transaction.symbol == "AAPL"
        assert transaction.security_name == "Apple Inc."
        assert transaction.quantity == Decimal("10")
        assert transaction.unit_price.amount == Decimal("105.00")
        assert transaction.commission.amount == Decimal("0.00")
        assert transaction.settlement_date == date(2025, 11, 30)

    def test_create_transaction_with_provider_metadata(self):
        """Create transaction with provider metadata dict."""
        metadata = {
            "activityId": 123456789,
            "type": "TRADE",
            "status": "EXECUTED",
            "subAccount": "MARGIN",
        }

        transaction = Transaction(
            id=uuid4(),
            account_id=uuid4(),
            provider_transaction_id="schwab-123",
            transaction_type=TransactionType.TRADE,
            subtype=TransactionSubtype.SELL,
            status=TransactionStatus.SETTLED,
            amount=Money(amount=Decimal("1000.00"), currency="USD"),
            description="Sold shares",
            transaction_date=date(2025, 11, 30),
            provider_metadata=metadata,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        assert transaction.provider_metadata == metadata
        assert transaction.provider_metadata["activityId"] == 123456789


class TestTransactionQueryMethods:
    """Test Transaction entity query methods."""

    def test_is_trade_returns_true_for_trade_type(self):
        """is_trade() should return True for TRADE type."""
        transaction = Transaction(
            id=uuid4(),
            account_id=uuid4(),
            provider_transaction_id="test-1",
            transaction_type=TransactionType.TRADE,
            subtype=TransactionSubtype.BUY,
            status=TransactionStatus.SETTLED,
            amount=Money(amount=Decimal("-100.00"), currency="USD"),
            description="Test",
            transaction_date=date(2025, 11, 30),
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        assert transaction.is_trade() is True

    def test_is_trade_returns_false_for_non_trade_types(self):
        """is_trade() should return False for non-TRADE types."""
        transaction = Transaction(
            id=uuid4(),
            account_id=uuid4(),
            provider_transaction_id="test-1",
            transaction_type=TransactionType.TRANSFER,
            subtype=TransactionSubtype.DEPOSIT,
            status=TransactionStatus.SETTLED,
            amount=Money(amount=Decimal("100.00"), currency="USD"),
            description="Test",
            transaction_date=date(2025, 11, 30),
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        assert transaction.is_trade() is False

    def test_is_transfer_returns_true_for_transfer_type(self):
        """is_transfer() should return True for TRANSFER type."""
        transaction = Transaction(
            id=uuid4(),
            account_id=uuid4(),
            provider_transaction_id="test-1",
            transaction_type=TransactionType.TRANSFER,
            subtype=TransactionSubtype.WITHDRAWAL,
            status=TransactionStatus.SETTLED,
            amount=Money(amount=Decimal("-50.00"), currency="USD"),
            description="Test",
            transaction_date=date(2025, 11, 30),
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        assert transaction.is_transfer() is True

    def test_is_income_returns_true_for_income_type(self):
        """is_income() should return True for INCOME type."""
        transaction = Transaction(
            id=uuid4(),
            account_id=uuid4(),
            provider_transaction_id="test-1",
            transaction_type=TransactionType.INCOME,
            subtype=TransactionSubtype.DIVIDEND,
            status=TransactionStatus.SETTLED,
            amount=Money(amount=Decimal("25.50"), currency="USD"),
            description="Test",
            transaction_date=date(2025, 11, 30),
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        assert transaction.is_income() is True

    def test_is_fee_returns_true_for_fee_type(self):
        """is_fee() should return True for FEE type."""
        transaction = Transaction(
            id=uuid4(),
            account_id=uuid4(),
            provider_transaction_id="test-1",
            transaction_type=TransactionType.FEE,
            subtype=TransactionSubtype.ACCOUNT_FEE,
            status=TransactionStatus.SETTLED,
            amount=Money(amount=Decimal("-5.00"), currency="USD"),
            description="Test",
            transaction_date=date(2025, 11, 30),
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        assert transaction.is_fee() is True

    def test_is_debit_returns_true_for_negative_amount(self):
        """is_debit() should return True for negative amounts."""
        transaction = Transaction(
            id=uuid4(),
            account_id=uuid4(),
            provider_transaction_id="test-1",
            transaction_type=TransactionType.TRANSFER,
            subtype=TransactionSubtype.WITHDRAWAL,
            status=TransactionStatus.SETTLED,
            amount=Money(amount=Decimal("-100.00"), currency="USD"),
            description="Test",
            transaction_date=date(2025, 11, 30),
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        assert transaction.is_debit() is True

    def test_is_debit_returns_false_for_positive_amount(self):
        """is_debit() should return False for positive amounts."""
        transaction = Transaction(
            id=uuid4(),
            account_id=uuid4(),
            provider_transaction_id="test-1",
            transaction_type=TransactionType.TRANSFER,
            subtype=TransactionSubtype.DEPOSIT,
            status=TransactionStatus.SETTLED,
            amount=Money(amount=Decimal("100.00"), currency="USD"),
            description="Test",
            transaction_date=date(2025, 11, 30),
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        assert transaction.is_debit() is False

    def test_is_credit_returns_true_for_positive_amount(self):
        """is_credit() should return True for positive amounts."""
        transaction = Transaction(
            id=uuid4(),
            account_id=uuid4(),
            provider_transaction_id="test-1",
            transaction_type=TransactionType.TRANSFER,
            subtype=TransactionSubtype.DEPOSIT,
            status=TransactionStatus.SETTLED,
            amount=Money(amount=Decimal("100.00"), currency="USD"),
            description="Test",
            transaction_date=date(2025, 11, 30),
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        assert transaction.is_credit() is True

    def test_is_credit_returns_false_for_negative_amount(self):
        """is_credit() should return False for negative amounts."""
        transaction = Transaction(
            id=uuid4(),
            account_id=uuid4(),
            provider_transaction_id="test-1",
            transaction_type=TransactionType.TRANSFER,
            subtype=TransactionSubtype.WITHDRAWAL,
            status=TransactionStatus.SETTLED,
            amount=Money(amount=Decimal("-100.00"), currency="USD"),
            description="Test",
            transaction_date=date(2025, 11, 30),
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        assert transaction.is_credit() is False

    def test_is_settled_returns_true_for_settled_status(self):
        """is_settled() should return True for SETTLED status."""
        transaction = Transaction(
            id=uuid4(),
            account_id=uuid4(),
            provider_transaction_id="test-1",
            transaction_type=TransactionType.TRADE,
            subtype=TransactionSubtype.BUY,
            status=TransactionStatus.SETTLED,
            amount=Money(amount=Decimal("-100.00"), currency="USD"),
            description="Test",
            transaction_date=date(2025, 11, 30),
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        assert transaction.is_settled() is True

    def test_is_settled_returns_false_for_non_settled_statuses(self):
        """is_settled() should return False for non-SETTLED statuses."""
        for status in [
            TransactionStatus.PENDING,
            TransactionStatus.FAILED,
            TransactionStatus.CANCELLED,
        ]:
            transaction = Transaction(
                id=uuid4(),
                account_id=uuid4(),
                provider_transaction_id="test-1",
                transaction_type=TransactionType.TRADE,
                subtype=TransactionSubtype.BUY,
                status=status,
                amount=Money(amount=Decimal("-100.00"), currency="USD"),
                description="Test",
                transaction_date=date(2025, 11, 30),
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )

            assert transaction.is_settled() is False

    def test_has_security_details_returns_true_when_all_present(self):
        """has_security_details() should return True when symbol, quantity, unit_price all present."""
        transaction = Transaction(
            id=uuid4(),
            account_id=uuid4(),
            provider_transaction_id="test-1",
            transaction_type=TransactionType.TRADE,
            subtype=TransactionSubtype.BUY,
            status=TransactionStatus.SETTLED,
            amount=Money(amount=Decimal("-1000.00"), currency="USD"),
            description="Test",
            symbol="AAPL",
            quantity=Decimal("10"),
            unit_price=Money(amount=Decimal("100.00"), currency="USD"),
            transaction_date=date(2025, 11, 30),
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        assert transaction.has_security_details() is True

    def test_has_security_details_returns_false_when_symbol_missing(self):
        """has_security_details() should return False when symbol is None."""
        transaction = Transaction(
            id=uuid4(),
            account_id=uuid4(),
            provider_transaction_id="test-1",
            transaction_type=TransactionType.TRADE,
            subtype=TransactionSubtype.BUY,
            status=TransactionStatus.SETTLED,
            amount=Money(amount=Decimal("-1000.00"), currency="USD"),
            description="Test",
            symbol=None,  # Missing
            quantity=Decimal("10"),
            unit_price=Money(amount=Decimal("100.00"), currency="USD"),
            transaction_date=date(2025, 11, 30),
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        assert transaction.has_security_details() is False

    def test_has_security_details_returns_false_when_quantity_missing(self):
        """has_security_details() should return False when quantity is None."""
        transaction = Transaction(
            id=uuid4(),
            account_id=uuid4(),
            provider_transaction_id="test-1",
            transaction_type=TransactionType.TRADE,
            subtype=TransactionSubtype.BUY,
            status=TransactionStatus.SETTLED,
            amount=Money(amount=Decimal("-1000.00"), currency="USD"),
            description="Test",
            symbol="AAPL",
            quantity=None,  # Missing
            unit_price=Money(amount=Decimal("100.00"), currency="USD"),
            transaction_date=date(2025, 11, 30),
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        assert transaction.has_security_details() is False

    def test_has_security_details_returns_false_when_unit_price_missing(self):
        """has_security_details() should return False when unit_price is None."""
        transaction = Transaction(
            id=uuid4(),
            account_id=uuid4(),
            provider_transaction_id="test-1",
            transaction_type=TransactionType.TRADE,
            subtype=TransactionSubtype.BUY,
            status=TransactionStatus.SETTLED,
            amount=Money(amount=Decimal("-1000.00"), currency="USD"),
            description="Test",
            symbol="AAPL",
            quantity=Decimal("10"),
            unit_price=None,  # Missing
            transaction_date=date(2025, 11, 30),
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        assert transaction.has_security_details() is False


class TestTransactionImmutability:
    """Test Transaction entity immutability."""

    def test_transaction_is_frozen(self):
        """Transaction should be immutable (frozen dataclass)."""
        transaction = Transaction(
            id=uuid4(),
            account_id=uuid4(),
            provider_transaction_id="test-1",
            transaction_type=TransactionType.TRANSFER,
            subtype=TransactionSubtype.DEPOSIT,
            status=TransactionStatus.SETTLED,
            amount=Money(amount=Decimal("100.00"), currency="USD"),
            description="Test",
            transaction_date=date(2025, 11, 30),
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        # Attempt to modify should raise FrozenInstanceError
        with pytest.raises(Exception):  # FrozenInstanceError from dataclasses
            transaction.status = TransactionStatus.CANCELLED

    def test_transaction_has_no_update_methods(self):
        """Transaction should not have any update methods."""
        transaction = Transaction(
            id=uuid4(),
            account_id=uuid4(),
            provider_transaction_id="test-1",
            transaction_type=TransactionType.TRANSFER,
            subtype=TransactionSubtype.DEPOSIT,
            status=TransactionStatus.SETTLED,
            amount=Money(amount=Decimal("100.00"), currency="USD"),
            description="Test",
            transaction_date=date(2025, 11, 30),
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        # Verify no update methods exist
        assert not hasattr(transaction, "update")
        assert not hasattr(transaction, "update_status")
        assert not hasattr(transaction, "update_amount")
