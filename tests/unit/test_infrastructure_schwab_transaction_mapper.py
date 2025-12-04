"""Unit tests for SchwabTransactionMapper.

Tests cover:
- Transaction type mapping (TRADE, DIVIDEND, TRANSFER, FEE, etc.)
- Subtype mapping (BUY, SELL, DIVIDEND, INTEREST, DEPOSIT, etc.)
- Asset type mapping (EQUITY, OPTION, ETF, etc.)
- Date parsing (tradeDate, transactionDate, settlementDate)
- Amount parsing (Decimal precision, negative values)
- Security details extraction (symbol, quantity, price, commission)
- Missing/invalid data handling

Architecture:
- Pure unit tests (no HTTP, no mocking needed)
- Tests mapper in isolation with raw dict input
- Verifies ProviderTransactionData output
"""

from datetime import date
from decimal import Decimal

import pytest

from src.domain.protocols.provider_protocol import ProviderTransactionData
from src.infrastructure.providers.schwab.mappers.transaction_mapper import (
    SCHWAB_TRANSACTION_TYPE_MAP,
    SchwabTransactionMapper,
)


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def mapper() -> SchwabTransactionMapper:
    """Create SchwabTransactionMapper instance."""
    return SchwabTransactionMapper()


def _build_schwab_transaction(
    *,
    activity_id: str = "123456789",
    txn_type: str = "TRADE",
    subtype: str | None = "BUY",
    net_amount: float = -1000.00,
    trade_date: str = "2024-11-28",
    settlement_date: str | None = "2024-11-30",
    description: str = "Test transaction",
    status: str = "EXECUTED",
    symbol: str | None = "AAPL",
    asset_type: str | None = "EQUITY",
    quantity: float | None = 10.0,
    price: float | None = 100.00,
    commission: float | None = 0.00,
) -> dict:
    """Build a Schwab transaction JSON structure for testing."""
    data: dict = {
        "activityId": activity_id,
        "type": txn_type,
        "netAmount": net_amount,
        "tradeDate": trade_date,
        "description": description,
        "status": status,
    }

    if subtype:
        data["transactionSubType"] = subtype

    if settlement_date:
        data["settlementDate"] = settlement_date

    # Add transaction item with instrument details
    if symbol or quantity or price:
        instrument = {}
        if symbol:
            instrument["symbol"] = symbol
            instrument["description"] = f"{symbol} Stock"
        if asset_type:
            instrument["assetType"] = asset_type

        txn_item: dict = {"instrument": instrument}
        if quantity:
            txn_item["amount"] = quantity
        if price:
            txn_item["price"] = price

        data["transactionItem"] = txn_item

    if commission is not None:
        data["totalCommission"] = commission

    return data


# =============================================================================
# Test: Transaction Type Mapping
# =============================================================================


class TestTransactionTypeMapping:
    """Test Schwab transaction type to Dashtam type mapping."""

    def test_trade_maps_to_trade(self, mapper: SchwabTransactionMapper):
        """TRADE transaction type maps to trade."""
        result = mapper._map_transaction_type("TRADE")
        assert result == "trade"

    def test_receive_and_deliver_maps_to_trade(self, mapper: SchwabTransactionMapper):
        """RECEIVE_AND_DELIVER maps to trade (in-kind transfer)."""
        result = mapper._map_transaction_type("RECEIVE_AND_DELIVER")
        assert result == "trade"

    def test_dividend_or_interest_maps_to_income(self, mapper: SchwabTransactionMapper):
        """DIVIDEND_OR_INTEREST maps to income."""
        result = mapper._map_transaction_type("DIVIDEND_OR_INTEREST")
        assert result == "income"

    def test_dividend_maps_to_income(self, mapper: SchwabTransactionMapper):
        """DIVIDEND maps to income."""
        result = mapper._map_transaction_type("DIVIDEND")
        assert result == "income"

    def test_interest_maps_to_income(self, mapper: SchwabTransactionMapper):
        """INTEREST maps to income."""
        result = mapper._map_transaction_type("INTEREST")
        assert result == "income"

    def test_capital_gains_maps_to_income(self, mapper: SchwabTransactionMapper):
        """CAPITAL_GAINS maps to income."""
        result = mapper._map_transaction_type("CAPITAL_GAINS")
        assert result == "income"

    def test_electronic_fund_maps_to_transfer(self, mapper: SchwabTransactionMapper):
        """ELECTRONIC_FUND maps to transfer."""
        result = mapper._map_transaction_type("ELECTRONIC_FUND")
        assert result == "transfer"

    def test_ach_receipt_maps_to_transfer(self, mapper: SchwabTransactionMapper):
        """ACH_RECEIPT maps to transfer."""
        result = mapper._map_transaction_type("ACH_RECEIPT")
        assert result == "transfer"

    def test_wire_in_maps_to_transfer(self, mapper: SchwabTransactionMapper):
        """WIRE_IN maps to transfer."""
        result = mapper._map_transaction_type("WIRE_IN")
        assert result == "transfer"

    def test_journal_maps_to_transfer(self, mapper: SchwabTransactionMapper):
        """JOURNAL maps to transfer."""
        result = mapper._map_transaction_type("JOURNAL")
        assert result == "transfer"

    def test_service_fee_maps_to_fee(self, mapper: SchwabTransactionMapper):
        """SERVICE_FEE maps to fee."""
        result = mapper._map_transaction_type("SERVICE_FEE")
        assert result == "fee"

    def test_margin_interest_maps_to_fee(self, mapper: SchwabTransactionMapper):
        """MARGIN_INTEREST maps to fee."""
        result = mapper._map_transaction_type("MARGIN_INTEREST")
        assert result == "fee"

    def test_adjustment_maps_to_other(self, mapper: SchwabTransactionMapper):
        """ADJUSTMENT maps to other."""
        result = mapper._map_transaction_type("ADJUSTMENT")
        assert result == "other"

    def test_unknown_type_maps_to_other(self, mapper: SchwabTransactionMapper):
        """Unknown types default to other."""
        result = mapper._map_transaction_type("UNKNOWN_TYPE")
        assert result == "other"

    def test_type_mapping_is_case_insensitive(self, mapper: SchwabTransactionMapper):
        """Type mapping should be case-insensitive."""
        assert mapper._map_transaction_type("trade") == "trade"
        assert mapper._map_transaction_type("TRADE") == "trade"
        assert mapper._map_transaction_type("Trade") == "trade"

    def test_all_mapped_types_are_valid(self):
        """Verify all mapped types in SCHWAB_TRANSACTION_TYPE_MAP are valid."""
        valid_types = {"trade", "income", "transfer", "fee", "other"}
        for schwab_type, dashtam_type in SCHWAB_TRANSACTION_TYPE_MAP.items():
            assert dashtam_type in valid_types


# =============================================================================
# Test: Trade Subtype Mapping
# =============================================================================


class TestTradeSubtypeMapping:
    """Test Schwab trade subtype mapping."""

    def test_buy_maps_to_buy(self, mapper: SchwabTransactionMapper):
        """BUY subtype maps to buy."""
        result = mapper._map_subtype("TRADE", "BUY", {})
        assert result == "buy"

    def test_sell_maps_to_sell(self, mapper: SchwabTransactionMapper):
        """SELL subtype maps to sell."""
        result = mapper._map_subtype("TRADE", "SELL", {})
        assert result == "sell"

    def test_buy_to_open_maps_to_buy(self, mapper: SchwabTransactionMapper):
        """BUY_TO_OPEN maps to buy."""
        result = mapper._map_subtype("TRADE", "BUY_TO_OPEN", {})
        assert result == "buy"

    def test_sell_to_close_maps_to_sell(self, mapper: SchwabTransactionMapper):
        """SELL_TO_CLOSE maps to sell."""
        result = mapper._map_subtype("TRADE", "SELL_TO_CLOSE", {})
        assert result == "sell"

    def test_sell_short_maps_to_short_sell(self, mapper: SchwabTransactionMapper):
        """SELL_SHORT maps to short_sell."""
        result = mapper._map_subtype("TRADE", "SELL_SHORT", {})
        assert result == "short_sell"

    def test_buy_to_cover_maps_to_buy_to_cover(self, mapper: SchwabTransactionMapper):
        """BUY_TO_COVER maps to buy_to_cover."""
        result = mapper._map_subtype("TRADE", "BUY_TO_COVER", {})
        assert result == "buy_to_cover"

    def test_exercise_maps_to_exercise(self, mapper: SchwabTransactionMapper):
        """EXERCISE maps to exercise."""
        result = mapper._map_subtype("TRADE", "EXERCISE", {})
        assert result == "exercise"

    def test_assignment_maps_to_assignment(self, mapper: SchwabTransactionMapper):
        """ASSIGNMENT maps to assignment."""
        result = mapper._map_subtype("TRADE", "ASSIGNMENT", {})
        assert result == "assignment"

    def test_expiration_maps_to_expiration(self, mapper: SchwabTransactionMapper):
        """EXPIRATION maps to expiration."""
        result = mapper._map_subtype("TRADE", "EXPIRATION", {})
        assert result == "expiration"

    def test_trade_without_subtype_infers_from_amount(
        self, mapper: SchwabTransactionMapper
    ):
        """Trade without subtype infers buy/sell from amount."""
        # Negative amount (cash out) → buy
        result = mapper._map_subtype("TRADE", None, {"netAmount": -1000})
        assert result == "buy"

        # Positive amount (cash in) → sell
        result = mapper._map_subtype("TRADE", None, {"netAmount": 1000})
        assert result == "sell"


# =============================================================================
# Test: Income Subtype Mapping
# =============================================================================


class TestIncomeSubtypeMapping:
    """Test income transaction subtype mapping."""

    def test_dividend_type_maps_to_dividend(self, mapper: SchwabTransactionMapper):
        """DIVIDEND type maps to dividend subtype."""
        result = mapper._map_subtype("DIVIDEND", None, {})
        assert result == "dividend"

    def test_dividend_or_interest_maps_to_interest(
        self, mapper: SchwabTransactionMapper
    ):
        """DIVIDEND_OR_INTEREST contains 'INTEREST', maps to interest."""
        # Note: The implementation checks if 'INTEREST' is in the type string
        # So DIVIDEND_OR_INTEREST maps to interest, not dividend
        result = mapper._map_subtype("DIVIDEND_OR_INTEREST", None, {})
        assert result == "interest"

    def test_interest_type_maps_to_interest(self, mapper: SchwabTransactionMapper):
        """INTEREST type maps to interest subtype."""
        result = mapper._map_subtype("INTEREST", None, {})
        assert result == "interest"

    def test_capital_gains_maps_to_capital_gain(self, mapper: SchwabTransactionMapper):
        """CAPITAL_GAINS maps to capital_gain subtype."""
        result = mapper._map_subtype("CAPITAL_GAINS", None, {})
        assert result == "capital_gain"

    def test_interest_subtype_overrides(self, mapper: SchwabTransactionMapper):
        """Interest in subtype overrides default dividend."""
        result = mapper._map_subtype("DIVIDEND_OR_INTEREST", "INTEREST", {})
        assert result == "interest"


# =============================================================================
# Test: Transfer Subtype Mapping
# =============================================================================


class TestTransferSubtypeMapping:
    """Test transfer transaction subtype mapping."""

    def test_ach_receipt_maps_to_deposit(self, mapper: SchwabTransactionMapper):
        """ACH_RECEIPT maps to deposit."""
        result = mapper._map_subtype("ACH_RECEIPT", None, {})
        assert result == "deposit"

    def test_ach_disbursement_maps_to_withdrawal(self, mapper: SchwabTransactionMapper):
        """ACH_DISBURSEMENT maps to withdrawal."""
        result = mapper._map_subtype("ACH_DISBURSEMENT", None, {})
        assert result == "withdrawal"

    def test_wire_in_maps_to_deposit(self, mapper: SchwabTransactionMapper):
        """WIRE_IN maps to deposit (it contains 'IN')."""
        result = mapper._map_subtype("WIRE_IN", None, {})
        assert result == "deposit"

    def test_wire_out_maps_to_withdrawal(self, mapper: SchwabTransactionMapper):
        """WIRE_OUT maps to withdrawal (it contains 'OUT')."""
        result = mapper._map_subtype("WIRE_OUT", None, {})
        assert result == "withdrawal"

    def test_journal_infers_from_amount(self, mapper: SchwabTransactionMapper):
        """JOURNAL infers direction from amount."""
        # Positive amount → deposit
        result = mapper._map_subtype("JOURNAL", None, {"netAmount": 1000})
        assert result == "deposit"

        # Negative amount → withdrawal
        result = mapper._map_subtype("JOURNAL", None, {"netAmount": -1000})
        assert result == "withdrawal"


# =============================================================================
# Test: Fee Subtype Mapping
# =============================================================================


class TestFeeSubtypeMapping:
    """Test fee transaction subtype mapping."""

    def test_margin_interest_maps_to_margin_interest(
        self, mapper: SchwabTransactionMapper
    ):
        """MARGIN_INTEREST maps to margin_interest."""
        result = mapper._map_subtype("MARGIN_INTEREST", None, {})
        assert result == "margin_interest"

    def test_service_fee_maps_to_account_fee(self, mapper: SchwabTransactionMapper):
        """SERVICE_FEE maps to account_fee."""
        result = mapper._map_subtype("SERVICE_FEE", None, {})
        assert result == "account_fee"

    def test_adr_fee_maps_to_account_fee(self, mapper: SchwabTransactionMapper):
        """ADR_FEE maps to account_fee."""
        result = mapper._map_subtype("ADR_FEE", None, {})
        assert result == "account_fee"


# =============================================================================
# Test: Asset Type Mapping
# =============================================================================


class TestAssetTypeMapping:
    """Test Schwab asset type to Dashtam asset type mapping."""

    def test_equity_maps_to_equity(self, mapper: SchwabTransactionMapper):
        """EQUITY maps to equity."""
        result = mapper._map_asset_type("EQUITY")
        assert result == "equity"

    def test_stock_maps_to_equity(self, mapper: SchwabTransactionMapper):
        """STOCK maps to equity."""
        result = mapper._map_asset_type("STOCK")
        assert result == "equity"

    def test_etf_maps_to_etf(self, mapper: SchwabTransactionMapper):
        """ETF maps to etf."""
        result = mapper._map_asset_type("ETF")
        assert result == "etf"

    def test_option_maps_to_option(self, mapper: SchwabTransactionMapper):
        """OPTION maps to option."""
        result = mapper._map_asset_type("OPTION")
        assert result == "option"

    def test_mutual_fund_maps_to_mutual_fund(self, mapper: SchwabTransactionMapper):
        """MUTUAL_FUND maps to mutual_fund."""
        result = mapper._map_asset_type("MUTUAL_FUND")
        assert result == "mutual_fund"

    def test_fixed_income_maps_to_fixed_income(self, mapper: SchwabTransactionMapper):
        """FIXED_INCOME maps to fixed_income."""
        result = mapper._map_asset_type("FIXED_INCOME")
        assert result == "fixed_income"

    def test_futures_maps_to_futures(self, mapper: SchwabTransactionMapper):
        """FUTURES maps to futures."""
        result = mapper._map_asset_type("FUTURES")
        assert result == "futures"

    def test_none_returns_none(self, mapper: SchwabTransactionMapper):
        """None asset type returns None."""
        result = mapper._map_asset_type(None)
        assert result is None

    def test_unknown_maps_to_other(self, mapper: SchwabTransactionMapper):
        """Unknown asset types map to other."""
        result = mapper._map_asset_type("UNKNOWN_ASSET")
        assert result == "other"


# =============================================================================
# Test: Date Parsing
# =============================================================================


class TestDateParsing:
    """Test date parsing from Schwab data."""

    def test_parse_trade_date(self, mapper: SchwabTransactionMapper):
        """Parse tradeDate field."""
        data = {"tradeDate": "2024-11-28"}
        result = mapper._parse_date(data)
        assert result == date(2024, 11, 28)

    def test_parse_transaction_date(self, mapper: SchwabTransactionMapper):
        """Parse transactionDate field when tradeDate missing."""
        data = {"transactionDate": "2024-11-28"}
        result = mapper._parse_date(data)
        assert result == date(2024, 11, 28)

    def test_parse_datetime_format(self, mapper: SchwabTransactionMapper):
        """Parse ISO datetime format (uses first 10 chars)."""
        data = {"tradeDate": "2024-11-28T14:30:00.000Z"}
        result = mapper._parse_date(data)
        assert result == date(2024, 11, 28)

    def test_parse_settlement_date(self, mapper: SchwabTransactionMapper):
        """Parse settlementDate field."""
        data = {"settlementDate": "2024-11-30"}
        result = mapper._parse_settlement_date(data)
        assert result == date(2024, 11, 30)

    def test_missing_date_returns_none(self, mapper: SchwabTransactionMapper):
        """Missing date fields return None."""
        result = mapper._parse_date({})
        assert result is None

    def test_invalid_date_returns_none(self, mapper: SchwabTransactionMapper):
        """Invalid date format returns None."""
        data = {"tradeDate": "not-a-date"}
        result = mapper._parse_date(data)
        assert result is None


# =============================================================================
# Test: Decimal Parsing
# =============================================================================


class TestDecimalParsing:
    """Test amount parsing to Decimal."""

    def test_parse_positive_amount(self, mapper: SchwabTransactionMapper):
        """Parse positive amount."""
        result = mapper._parse_decimal(1000.50)
        assert result == Decimal("1000.5")

    def test_parse_negative_amount(self, mapper: SchwabTransactionMapper):
        """Parse negative amount."""
        result = mapper._parse_decimal(-500.25)
        assert result == Decimal("-500.25")

    def test_parse_zero(self, mapper: SchwabTransactionMapper):
        """Parse zero amount."""
        result = mapper._parse_decimal(0)
        assert result == Decimal("0")

    def test_parse_none_returns_zero(self, mapper: SchwabTransactionMapper):
        """None returns Decimal(0)."""
        result = mapper._parse_decimal(None)
        assert result == Decimal("0")

    def test_parse_string_amount(self, mapper: SchwabTransactionMapper):
        """Parse string amount."""
        result = mapper._parse_decimal("1234.56")
        assert result == Decimal("1234.56")


# =============================================================================
# Test: Full Transaction Mapping
# =============================================================================


class TestFullTransactionMapping:
    """Test complete transaction mapping from Schwab JSON."""

    def test_map_trade_transaction(self, mapper: SchwabTransactionMapper):
        """Map complete trade transaction."""
        data = _build_schwab_transaction(
            activity_id="999888777",
            txn_type="TRADE",
            subtype="BUY",
            net_amount=-1050.00,
            trade_date="2024-11-28",
            settlement_date="2024-11-30",
            description="Bought 10 shares of AAPL",
            symbol="AAPL",
            asset_type="EQUITY",
            quantity=10.0,
            price=105.00,
            commission=5.00,  # Non-zero commission to test
        )

        result = mapper.map_transaction(data)

        assert result is not None
        assert isinstance(result, ProviderTransactionData)
        assert result.provider_transaction_id == "999888777"
        assert result.transaction_type == "trade"
        assert result.subtype == "buy"
        assert result.amount == Decimal("-1050")
        assert result.currency == "USD"
        assert result.description == "Bought 10 shares of AAPL"
        assert result.transaction_date == date(2024, 11, 28)
        assert result.settlement_date == date(2024, 11, 30)
        assert result.symbol == "AAPL"
        assert result.asset_type == "equity"
        assert result.quantity == Decimal("10")
        assert result.unit_price == Decimal("105")
        assert result.commission == Decimal("5")  # Commission is set
        assert result.raw_data == data

    def test_map_dividend_transaction(self, mapper: SchwabTransactionMapper):
        """Map dividend transaction using pure DIVIDEND type."""
        # Use DIVIDEND type (not DIVIDEND_OR_INTEREST) for dividend mapping
        data = {
            "activityId": "111222333",
            "type": "DIVIDEND",
            "netAmount": 25.50,
            "tradeDate": "2024-11-15",
            "description": "AAPL Dividend",
            "status": "EXECUTED",
        }

        result = mapper.map_transaction(data)

        assert result is not None
        assert result.transaction_type == "income"
        assert result.subtype == "dividend"
        assert result.amount == Decimal("25.5")

    def test_map_transfer_transaction(self, mapper: SchwabTransactionMapper):
        """Map transfer transaction."""
        data = {
            "activityId": "444555666",
            "type": "ACH_RECEIPT",
            "netAmount": 5000.00,
            "transactionDate": "2024-11-01",
            "description": "ACH Deposit",
            "status": "EXECUTED",
        }

        result = mapper.map_transaction(data)

        assert result is not None
        assert result.transaction_type == "transfer"
        assert result.subtype == "deposit"
        assert result.amount == Decimal("5000")

    def test_map_fee_transaction(self, mapper: SchwabTransactionMapper):
        """Map fee transaction."""
        data = {
            "activityId": "777888999",
            "type": "MARGIN_INTEREST",
            "netAmount": -15.75,
            "transactionDate": "2024-11-30",
            "description": "Margin Interest Charge",
            "status": "EXECUTED",
        }

        result = mapper.map_transaction(data)

        assert result is not None
        assert result.transaction_type == "fee"
        assert result.subtype == "margin_interest"
        assert result.amount == Decimal("-15.75")

    def test_map_transaction_missing_id(self, mapper: SchwabTransactionMapper):
        """Transaction without ID returns None."""
        data = {
            "type": "TRADE",
            "netAmount": -1000,
            "tradeDate": "2024-11-28",
        }

        result = mapper.map_transaction(data)
        assert result is None

    def test_map_transaction_missing_date(self, mapper: SchwabTransactionMapper):
        """Transaction without date returns None."""
        data = {
            "activityId": "123",
            "type": "TRADE",
            "netAmount": -1000,
        }

        result = mapper.map_transaction(data)
        assert result is None

    def test_map_transaction_uses_transaction_id(self, mapper: SchwabTransactionMapper):
        """Uses transactionId when activityId is missing."""
        data = {
            "transactionId": "txn_12345",
            "type": "TRADE",
            "netAmount": -1000,
            "tradeDate": "2024-11-28",
        }

        result = mapper.map_transaction(data)

        assert result is not None
        assert result.provider_transaction_id == "txn_12345"


# =============================================================================
# Test: Batch Transaction Mapping
# =============================================================================


class TestBatchTransactionMapping:
    """Test mapping multiple transactions."""

    def test_map_multiple_transactions(self, mapper: SchwabTransactionMapper):
        """Map list of transactions."""
        data_list = [
            _build_schwab_transaction(activity_id="111", txn_type="TRADE"),
            _build_schwab_transaction(activity_id="222", txn_type="DIVIDEND"),
            _build_schwab_transaction(activity_id="333", txn_type="ACH_RECEIPT"),
        ]

        results = mapper.map_transactions(data_list)

        assert len(results) == 3
        assert results[0].provider_transaction_id == "111"
        assert results[1].provider_transaction_id == "222"
        assert results[2].provider_transaction_id == "333"

    def test_map_transactions_skips_invalid(self, mapper: SchwabTransactionMapper):
        """Invalid transactions are skipped."""
        data_list = [
            _build_schwab_transaction(activity_id="111"),
            {"type": "TRADE"},  # Missing ID
            _build_schwab_transaction(activity_id="333"),
        ]

        results = mapper.map_transactions(data_list)

        assert len(results) == 2
        assert results[0].provider_transaction_id == "111"
        assert results[1].provider_transaction_id == "333"

    def test_map_empty_list(self, mapper: SchwabTransactionMapper):
        """Empty list returns empty list."""
        results = mapper.map_transactions([])
        assert results == []


# =============================================================================
# Test: Edge Cases and Error Handling
# =============================================================================


class TestEdgeCasesAndErrorHandling:
    """Test edge cases and error handling."""

    def test_map_transaction_with_none_data(self, mapper: SchwabTransactionMapper):
        """Mapping None data doesn't crash."""
        result = mapper.map_transaction(None)  # type: ignore
        assert result is None

    def test_map_transaction_with_non_dict(self, mapper: SchwabTransactionMapper):
        """Mapping non-dict data doesn't crash."""
        result = mapper.map_transaction("not a dict")  # type: ignore
        assert result is None

    def test_map_transaction_with_empty_transaction_item(
        self, mapper: SchwabTransactionMapper
    ):
        """Transaction with empty transactionItem works."""
        data = {
            "activityId": "123",
            "type": "TRADE",
            "netAmount": -1000,
            "tradeDate": "2024-11-28",
            "transactionItem": {},
        }

        result = mapper.map_transaction(data)

        assert result is not None
        assert result.symbol is None
        assert result.quantity is None

    def test_map_transaction_preserves_raw_data(self, mapper: SchwabTransactionMapper):
        """Raw Schwab data is preserved."""
        data = _build_schwab_transaction()

        result = mapper.map_transaction(data)

        assert result is not None
        assert result.raw_data == data

    def test_generated_description_when_missing(self, mapper: SchwabTransactionMapper):
        """Description is generated when missing."""
        data = {
            "activityId": "123",
            "type": "TRADE",
            "transactionSubType": "BUY",
            "netAmount": -1000,
            "tradeDate": "2024-11-28",
            "transactionItem": {
                "instrument": {"symbol": "AAPL"},
            },
        }

        result = mapper.map_transaction(data)

        assert result is not None
        assert "Buy" in result.description
        assert "AAPL" in result.description

    def test_large_transaction_amount(self, mapper: SchwabTransactionMapper):
        """Large amounts are handled correctly."""
        data = _build_schwab_transaction(net_amount=-9999999.99)

        result = mapper.map_transaction(data)

        assert result is not None
        assert result.amount == Decimal("-9999999.99")
