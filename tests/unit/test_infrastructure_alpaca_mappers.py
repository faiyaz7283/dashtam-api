"""Unit tests for Alpaca mappers.

Tests for:
- AlpacaAccountMapper: JSON → ProviderAccountData
- AlpacaHoldingMapper: JSON → ProviderHoldingData
- AlpacaTransactionMapper: JSON → ProviderTransactionData

These mappers contain Alpaca-specific knowledge and are critical
for accurate data transformation.
"""

from datetime import date
from decimal import Decimal

import pytest

from src.infrastructure.providers.alpaca.mappers.account_mapper import (
    AlpacaAccountMapper,
)
from src.infrastructure.providers.alpaca.mappers.holding_mapper import (
    AlpacaHoldingMapper,
)
from src.infrastructure.providers.alpaca.mappers.transaction_mapper import (
    AlpacaTransactionMapper,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def account_mapper() -> AlpacaAccountMapper:
    """Create AlpacaAccountMapper instance."""
    return AlpacaAccountMapper()


@pytest.fixture
def holding_mapper() -> AlpacaHoldingMapper:
    """Create AlpacaHoldingMapper instance."""
    return AlpacaHoldingMapper()


@pytest.fixture
def transaction_mapper() -> AlpacaTransactionMapper:
    """Create AlpacaTransactionMapper instance."""
    return AlpacaTransactionMapper()


# =============================================================================
# Account Mapper Tests
# =============================================================================


@pytest.mark.unit
class TestAlpacaAccountMapper:
    """Tests for AlpacaAccountMapper."""

    def test_map_account_valid_data(self, account_mapper: AlpacaAccountMapper):
        """Map valid Alpaca account JSON to ProviderAccountData."""
        data = {
            "account_number": "PA3CRCJ7QUIR",
            "status": "ACTIVE",
            "currency": "USD",
            "equity": "150000.50",
            "buying_power": "300000.00",
            "cash": "50000.00",
        }

        result = account_mapper.map_account(data)

        assert result is not None
        assert result.provider_account_id == "PA3CRCJ7QUIR"
        assert result.account_number_masked == "****QUIR"
        assert result.balance == Decimal("150000.50")
        assert result.available_balance == Decimal("300000.00")
        assert result.currency == "USD"
        assert result.is_active is True
        assert "Paper" in result.name  # PA prefix = Paper account

    def test_map_account_live_account(self, account_mapper: AlpacaAccountMapper):
        """Map live account (non-PA prefix) correctly."""
        data = {
            "account_number": "123456789ABC",
            "status": "ACTIVE",
            "equity": "100000",
        }

        result = account_mapper.map_account(data)

        assert result is not None
        assert "Live" in result.name  # Non-PA prefix = Live account

    def test_map_account_inactive_status(self, account_mapper: AlpacaAccountMapper):
        """Map inactive account status correctly."""
        data = {
            "account_number": "PA123",
            "status": "INACTIVE",
            "equity": "0",
        }

        result = account_mapper.map_account(data)

        assert result is not None
        assert result.is_active is False

    def test_map_account_missing_account_number(
        self, account_mapper: AlpacaAccountMapper
    ):
        """Return None when account_number is missing."""
        data = {
            "status": "ACTIVE",
            "equity": "100000",
        }

        result = account_mapper.map_account(data)

        assert result is None

    def test_map_account_empty_account_number(
        self, account_mapper: AlpacaAccountMapper
    ):
        """Return None when account_number is empty string."""
        data = {
            "account_number": "",
            "status": "ACTIVE",
            "equity": "100000",
        }

        result = account_mapper.map_account(data)

        assert result is None

    def test_map_account_handles_missing_optional_fields(
        self, account_mapper: AlpacaAccountMapper
    ):
        """Handle missing optional fields gracefully."""
        data = {
            "account_number": "PA123",
        }

        result = account_mapper.map_account(data)

        assert result is not None
        assert result.balance == Decimal("0")
        assert result.currency == "USD"

    def test_map_account_invalid_decimal_values(
        self, account_mapper: AlpacaAccountMapper
    ):
        """Handle invalid decimal values gracefully."""
        data = {
            "account_number": "PA123",
            "equity": "not_a_number",
            "buying_power": None,
        }

        result = account_mapper.map_account(data)

        assert result is not None
        assert result.balance == Decimal("0")

    def test_map_account_preserves_raw_data(self, account_mapper: AlpacaAccountMapper):
        """Preserve raw JSON data in result."""
        data = {
            "account_number": "PA123",
            "equity": "100000",
            "extra_field": "extra_value",
        }

        result = account_mapper.map_account(data)

        assert result is not None
        assert result.raw_data == data

    def test_map_account_short_account_number(
        self, account_mapper: AlpacaAccountMapper
    ):
        """Handle short account numbers (less than 4 chars) in masking."""
        data = {
            "account_number": "PA1",
            "equity": "100",
        }

        result = account_mapper.map_account(data)

        assert result is not None
        assert result.account_number_masked == "****PA1"

    def test_map_account_uses_cash_when_no_buying_power(
        self, account_mapper: AlpacaAccountMapper
    ):
        """Use cash as available_balance when buying_power is missing."""
        data = {
            "account_number": "PA123",
            "equity": "100000",
            "cash": "25000.50",
        }

        result = account_mapper.map_account(data)

        assert result is not None
        assert result.available_balance == Decimal("25000.50")

    def test_map_account_exception_handling(self, account_mapper: AlpacaAccountMapper):
        """Return None when mapping raises exception (catches TypeError, etc.)."""
        # Pass None as dict to trigger AttributeError on .get()
        # This tests the try/except block in map_account
        result = account_mapper.map_account(None)  # type: ignore

        # Should return None due to exception handling, not crash
        assert result is None


# =============================================================================
# Holding Mapper Tests
# =============================================================================


@pytest.mark.unit
class TestAlpacaHoldingMapper:
    """Tests for AlpacaHoldingMapper."""

    def test_map_holding_valid_data(self, holding_mapper: AlpacaHoldingMapper):
        """Map valid Alpaca position JSON to ProviderHoldingData."""
        data = {
            "asset_id": "b0b6dd9d-8b9b-48a9-ba46-b9d54906e415",
            "symbol": "AAPL",
            "asset_class": "us_equity",
            "qty": "100",
            "avg_entry_price": "150.25",
            "market_value": "15500.00",
            "cost_basis": "15025.00",
            "current_price": "155.00",
            "side": "long",
        }

        result = holding_mapper.map_holding(data)

        assert result is not None
        assert result.provider_holding_id == "b0b6dd9d-8b9b-48a9-ba46-b9d54906e415"
        assert result.symbol == "AAPL"
        assert result.quantity == Decimal("100")
        assert result.cost_basis == Decimal("15025.00")
        assert result.market_value == Decimal("15500.00")
        assert result.current_price == Decimal("155.00")
        assert result.asset_type == "equity"

    def test_map_holding_short_position(self, holding_mapper: AlpacaHoldingMapper):
        """Map short position with negative quantity."""
        data = {
            "asset_id": "abc123",
            "symbol": "TSLA",
            "qty": "50",
            "side": "short",
            "cost_basis": "10000",
            "market_value": "9000",
        }

        result = holding_mapper.map_holding(data)

        assert result is not None
        assert result.quantity == Decimal("-50")  # Negative for short

    def test_map_holding_crypto_asset(self, holding_mapper: AlpacaHoldingMapper):
        """Map cryptocurrency holding with correct asset type."""
        data = {
            "asset_id": "crypto123",
            "symbol": "BTC/USD",
            "asset_class": "crypto",
            "qty": "0.5",
            "cost_basis": "25000",
            "market_value": "30000",
        }

        result = holding_mapper.map_holding(data)

        assert result is not None
        assert result.asset_type == "cryptocurrency"

    def test_map_holding_zero_quantity_skipped(
        self, holding_mapper: AlpacaHoldingMapper
    ):
        """Skip positions with zero quantity."""
        data = {
            "asset_id": "abc123",
            "symbol": "AAPL",
            "qty": "0",
            "cost_basis": "0",
            "market_value": "0",
        }

        result = holding_mapper.map_holding(data)

        assert result is None

    def test_map_holding_missing_symbol(self, holding_mapper: AlpacaHoldingMapper):
        """Return None when symbol is missing."""
        data = {
            "asset_id": "abc123",
            "qty": "100",
        }

        result = holding_mapper.map_holding(data)

        assert result is None

    def test_map_holding_unknown_asset_class(self, holding_mapper: AlpacaHoldingMapper):
        """Map unknown asset class to 'other'."""
        data = {
            "asset_id": "abc123",
            "symbol": "UNKNOWN",
            "asset_class": "future_asset_type",
            "qty": "10",
            "cost_basis": "1000",
            "market_value": "1100",
        }

        result = holding_mapper.map_holding(data)

        assert result is not None
        assert result.asset_type == "other"

    def test_map_holdings_list(self, holding_mapper: AlpacaHoldingMapper):
        """Map list of positions, skipping invalid ones."""
        data_list = [
            {
                "asset_id": "1",
                "symbol": "AAPL",
                "qty": "100",
                "cost_basis": "15000",
                "market_value": "16000",
            },
            {"asset_id": "2", "symbol": "", "qty": "50"},  # Invalid - no symbol
            {
                "asset_id": "3",
                "symbol": "GOOGL",
                "qty": "10",
                "cost_basis": "28000",
                "market_value": "29000",
            },
        ]

        results = holding_mapper.map_holdings(data_list)

        assert len(results) == 2
        assert results[0].symbol == "AAPL"
        assert results[1].symbol == "GOOGL"

    def test_map_holding_fallback_asset_id(self, holding_mapper: AlpacaHoldingMapper):
        """Use symbol as asset_id fallback when asset_id is missing."""
        data = {
            "symbol": "MSFT",
            "qty": "25",
            "cost_basis": "10000",
            "market_value": "11000",
        }

        result = holding_mapper.map_holding(data)

        assert result is not None
        assert result.provider_holding_id == "alpaca_MSFT"

    def test_map_holding_empty_asset_class(self, holding_mapper: AlpacaHoldingMapper):
        """Handle empty asset class string."""
        data = {
            "asset_id": "abc123",
            "symbol": "TEST",
            "asset_class": "",
            "qty": "10",
            "cost_basis": "1000",
            "market_value": "1100",
        }

        result = holding_mapper.map_holding(data)

        assert result is not None
        assert result.asset_type == "other"

    def test_map_holding_invalid_decimal_value(
        self, holding_mapper: AlpacaHoldingMapper
    ):
        """Handle invalid decimal values in holding data."""
        data = {
            "asset_id": "abc123",
            "symbol": "AAPL",
            "qty": "100",
            "cost_basis": "not_a_number",  # Invalid decimal
            "market_value": "invalid",  # Invalid decimal
        }

        result = holding_mapper.map_holding(data)

        assert result is not None
        assert result.cost_basis == Decimal("0")
        assert result.market_value == Decimal("0")

    def test_map_holding_invalid_optional_decimal(
        self, holding_mapper: AlpacaHoldingMapper
    ):
        """Handle invalid optional decimal values (returns None)."""
        data = {
            "asset_id": "abc123",
            "symbol": "AAPL",
            "qty": "100",
            "cost_basis": "15000",
            "market_value": "16000",
            "avg_entry_price": "not_a_number",  # Invalid optional
            "current_price": "also_invalid",  # Invalid optional
        }

        result = holding_mapper.map_holding(data)

        assert result is not None
        assert result.average_price is None
        assert result.current_price is None

    def test_map_holding_exception_handling(self, holding_mapper: AlpacaHoldingMapper):
        """Return None when mapping raises exception."""
        # Pass None as dict to trigger AttributeError on .get()
        # This tests the try/except block in map_holding
        result = holding_mapper.map_holding(None)  # type: ignore

        # Should return None due to exception handling
        assert result is None

    def test_map_holding_none_quantity(self, holding_mapper: AlpacaHoldingMapper):
        """Handle None quantity value."""
        data = {
            "asset_id": "abc123",
            "symbol": "AAPL",
            "qty": None,
            "cost_basis": "15000",
            "market_value": "16000",
        }

        result = holding_mapper.map_holding(data)

        # Zero quantity should be skipped
        assert result is None


# =============================================================================
# Transaction Mapper Tests
# =============================================================================


@pytest.mark.unit
class TestAlpacaTransactionMapper:
    """Tests for AlpacaTransactionMapper."""

    def test_map_trade_fill(self, transaction_mapper: AlpacaTransactionMapper):
        """Map trade fill activity to ProviderTransactionData."""
        data = {
            "id": "20210301000000000::8c51c51d-2ccb-4a7c-9bc1-f31b0a7b0ae9",
            "activity_type": "FILL",
            "transaction_time": "2021-03-01T09:30:00Z",
            "symbol": "AAPL",
            "side": "buy",
            "qty": "100",
            "price": "150.25",
        }

        result = transaction_mapper.map_transaction(data)

        assert result is not None
        assert result.provider_transaction_id == data["id"]
        assert result.transaction_type == "trade"
        assert result.subtype == "buy"
        assert result.symbol == "AAPL"
        assert result.quantity == Decimal("100")
        assert result.unit_price == Decimal("150.25")
        assert result.amount < 0  # Buy = negative (cash outflow)
        assert result.transaction_date == date(2021, 3, 1)

    def test_map_trade_sell(self, transaction_mapper: AlpacaTransactionMapper):
        """Map sell trade with positive amount."""
        data = {
            "id": "sell123",
            "activity_type": "FILL",
            "transaction_time": "2021-03-01T10:00:00Z",
            "symbol": "AAPL",
            "side": "sell",
            "qty": "50",
            "price": "160.00",
        }

        result = transaction_mapper.map_transaction(data)

        assert result is not None
        assert result.subtype == "sell"
        assert result.amount > 0  # Sell = positive (cash inflow)
        assert result.amount == Decimal("8000")  # 50 * 160

    def test_map_dividend_activity(self, transaction_mapper: AlpacaTransactionMapper):
        """Map dividend activity to ProviderTransactionData."""
        data = {
            "id": "div123",
            "activity_type": "DIV",
            "date": "2021-06-15",
            "net_amount": "125.50",
            "symbol": "AAPL",
        }

        result = transaction_mapper.map_transaction(data)

        assert result is not None
        assert result.transaction_type == "income"
        assert result.subtype == "dividend"
        assert result.amount == Decimal("125.50")
        assert result.transaction_date == date(2021, 6, 15)

    def test_map_journal_cash_transfer(
        self, transaction_mapper: AlpacaTransactionMapper
    ):
        """Map journal cash transfer activity."""
        data = {
            "id": "jnl123",
            "activity_type": "JNLC",
            "date": "2021-10-25",
            "net_amount": "100000.00",
            "status": "executed",
        }

        result = transaction_mapper.map_transaction(data)

        assert result is not None
        assert result.transaction_type == "transfer"
        assert result.subtype == "journal_cash"
        assert result.amount == Decimal("100000.00")

    def test_map_interest_activity(self, transaction_mapper: AlpacaTransactionMapper):
        """Map interest activity to ProviderTransactionData."""
        data = {
            "id": "int123",
            "activity_type": "INT",
            "date": "2021-12-31",
            "net_amount": "15.75",
        }

        result = transaction_mapper.map_transaction(data)

        assert result is not None
        assert result.transaction_type == "income"
        assert result.subtype == "interest"

    def test_map_transaction_missing_id(
        self, transaction_mapper: AlpacaTransactionMapper
    ):
        """Return None when transaction ID is missing."""
        data = {
            "activity_type": "FILL",
            "transaction_time": "2021-03-01T09:30:00Z",
        }

        result = transaction_mapper.map_transaction(data)

        assert result is None

    def test_map_transaction_missing_date(
        self, transaction_mapper: AlpacaTransactionMapper
    ):
        """Return None when date cannot be parsed."""
        data = {
            "id": "txn123",
            "activity_type": "DIV",
            # No date fields
        }

        result = transaction_mapper.map_transaction(data)

        assert result is None

    def test_map_transaction_unknown_activity_type(
        self, transaction_mapper: AlpacaTransactionMapper
    ):
        """Map unknown activity type to 'other'."""
        data = {
            "id": "txn123",
            "activity_type": "FUTURE_TYPE",
            "date": "2021-12-01",
            "net_amount": "50.00",
        }

        result = transaction_mapper.map_transaction(data)

        assert result is not None
        assert result.transaction_type == "other"

    def test_map_transactions_list(self, transaction_mapper: AlpacaTransactionMapper):
        """Map list of activities, skipping invalid ones."""
        data_list = [
            {
                "id": "1",
                "activity_type": "DIV",
                "date": "2021-06-15",
                "net_amount": "100",
            },
            {"activity_type": "DIV", "date": "2021-06-16"},  # Invalid - no ID
            {
                "id": "3",
                "activity_type": "INT",
                "date": "2021-06-17",
                "net_amount": "25",
            },
        ]

        results = transaction_mapper.map_transactions(data_list)

        assert len(results) == 2
        assert results[0].provider_transaction_id == "1"
        assert results[1].provider_transaction_id == "3"

    def test_map_trade_short_sell(self, transaction_mapper: AlpacaTransactionMapper):
        """Map short sell trade correctly."""
        data = {
            "id": "short123",
            "activity_type": "FILL",
            "transaction_time": "2021-03-01T10:00:00Z",
            "symbol": "TSLA",
            "side": "sell_short",
            "qty": "20",
            "price": "700.00",
        }

        result = transaction_mapper.map_transaction(data)

        assert result is not None
        assert result.subtype == "short_sell"
        assert result.amount > 0  # Short sell = cash inflow

    def test_map_transaction_preserves_raw_data(
        self, transaction_mapper: AlpacaTransactionMapper
    ):
        """Preserve raw JSON data in result."""
        data = {
            "id": "txn123",
            "activity_type": "DIV",
            "date": "2021-06-15",
            "net_amount": "100",
            "extra_field": "extra_value",
        }

        result = transaction_mapper.map_transaction(data)

        assert result is not None
        assert result.raw_data == data

    def test_map_trade_commission_is_zero(
        self, transaction_mapper: AlpacaTransactionMapper
    ):
        """Alpaca is commission-free, verify commission is zero."""
        data = {
            "id": "trade123",
            "activity_type": "FILL",
            "transaction_time": "2021-03-01T09:30:00Z",
            "symbol": "AAPL",
            "side": "buy",
            "qty": "10",
            "price": "100.00",
        }

        result = transaction_mapper.map_transaction(data)

        assert result is not None
        assert result.commission == Decimal("0")

    def test_map_transaction_empty_activity_type(
        self, transaction_mapper: AlpacaTransactionMapper
    ):
        """Handle empty activity type string."""
        data = {
            "id": "txn123",
            "activity_type": "",
            "date": "2021-06-15",
            "net_amount": "100",
        }

        result = transaction_mapper.map_transaction(data)

        assert result is not None
        assert result.transaction_type == "other"

    def test_map_transaction_empty_side(
        self, transaction_mapper: AlpacaTransactionMapper
    ):
        """Handle empty trade side string."""
        data = {
            "id": "trade123",
            "activity_type": "FILL",
            "transaction_time": "2021-03-01T09:30:00Z",
            "symbol": "AAPL",
            "side": "",  # Empty side
            "qty": "10",
            "price": "100.00",
        }

        result = transaction_mapper.map_transaction(data)

        assert result is not None
        assert result.subtype is None  # Empty side returns None

    def test_map_transaction_invalid_decimal(
        self, transaction_mapper: AlpacaTransactionMapper
    ):
        """Handle invalid decimal in transaction amount."""
        data = {
            "id": "txn123",
            "activity_type": "DIV",
            "date": "2021-06-15",
            "net_amount": "not_a_number",
        }

        result = transaction_mapper.map_transaction(data)

        assert result is not None
        assert result.amount == Decimal("0")

    def test_map_transaction_created_at_fallback(
        self, transaction_mapper: AlpacaTransactionMapper
    ):
        """Parse date from created_at field as fallback."""
        data = {
            "id": "txn123",
            "activity_type": "DIV",
            "created_at": "2021-06-15T12:00:00Z",  # Use created_at as fallback
            "net_amount": "100",
        }

        result = transaction_mapper.map_transaction(data)

        assert result is not None
        assert result.transaction_date == date(2021, 6, 15)

    def test_map_transaction_invalid_date_format(
        self, transaction_mapper: AlpacaTransactionMapper
    ):
        """Handle invalid date format returns None."""
        data = {
            "id": "txn123",
            "activity_type": "DIV",
            "date": "not-a-date",
            "net_amount": "100",
        }

        result = transaction_mapper.map_transaction(data)

        assert result is None  # Invalid date, no fallback

    def test_map_transaction_invalid_transaction_time(
        self, transaction_mapper: AlpacaTransactionMapper
    ):
        """Handle invalid transaction_time format falls through to date field."""
        data = {
            "id": "trade123",
            "activity_type": "FILL",
            "transaction_time": "invalid-timestamp",
            "date": "2021-03-01",  # Falls through to date field
            "symbol": "AAPL",
            "side": "buy",
            "qty": "10",
            "price": "100.00",
        }

        result = transaction_mapper.map_transaction(data)

        assert result is not None
        assert result.transaction_date == date(2021, 3, 1)

    def test_map_transaction_buy_to_cover(
        self, transaction_mapper: AlpacaTransactionMapper
    ):
        """Map buy_to_cover trade as negative amount."""
        data = {
            "id": "cover123",
            "activity_type": "FILL",
            "transaction_time": "2021-03-01T10:00:00Z",
            "symbol": "TSLA",
            "side": "buy_to_cover",
            "qty": "20",
            "price": "650.00",
        }

        result = transaction_mapper.map_transaction(data)

        assert result is not None
        assert result.subtype == "buy_to_cover"
        assert result.amount < 0  # Buy to cover = cash outflow

    def test_map_transaction_generates_description(
        self, transaction_mapper: AlpacaTransactionMapper
    ):
        """Generate description when none provided."""
        data = {
            "id": "jnl123",
            "activity_type": "JNLC",
            "date": "2021-10-25",
            "net_amount": "5000.00",
            # No description field
        }

        result = transaction_mapper.map_transaction(data)

        assert result is not None
        assert "Journal entry (cash)" in result.description

    def test_map_transaction_generates_negative_description(
        self, transaction_mapper: AlpacaTransactionMapper
    ):
        """Generate description for negative amount."""
        data = {
            "id": "wire123",
            "activity_type": "WIRE",
            "date": "2021-10-25",
            "net_amount": "-1000.00",
            # No description field
        }

        result = transaction_mapper.map_transaction(data)

        assert result is not None
        assert "Wire transfer" in result.description
        assert "-$" in result.description

    def test_map_transaction_exception_handling(
        self, transaction_mapper: AlpacaTransactionMapper
    ):
        """Return None when mapping raises exception."""
        # Pass None as dict to trigger AttributeError on .get()
        # This tests the try/except block in map_transaction
        result = transaction_mapper.map_transaction(None)  # type: ignore

        # Should return None due to exception handling
        assert result is None

    def test_map_transaction_journal_stock(
        self, transaction_mapper: AlpacaTransactionMapper
    ):
        """Map journal stock transfer activity."""
        data = {
            "id": "jnls123",
            "activity_type": "JNLS",
            "date": "2021-10-25",
            "net_amount": "0",  # Stock transfers have no cash amount
        }

        result = transaction_mapper.map_transaction(data)

        assert result is not None
        assert result.transaction_type == "transfer"
        assert result.subtype == "journal_stock"

    def test_map_transaction_invalid_created_at_fallback(
        self, transaction_mapper: AlpacaTransactionMapper
    ):
        """Invalid created_at date falls through, returns None."""
        data = {
            "id": "txn123",
            "activity_type": "DIV",
            "created_at": "invalid-date",  # Invalid created_at
            "net_amount": "100",
        }

        result = transaction_mapper.map_transaction(data)

        # No valid date found, returns None
        assert result is None

    def test_map_transaction_none_net_amount(
        self, transaction_mapper: AlpacaTransactionMapper
    ):
        """Handle None net_amount value."""
        data = {
            "id": "txn123",
            "activity_type": "DIV",
            "date": "2021-06-15",
            "net_amount": None,  # Explicit None
        }

        result = transaction_mapper.map_transaction(data)

        assert result is not None
        assert result.amount == Decimal("0")
