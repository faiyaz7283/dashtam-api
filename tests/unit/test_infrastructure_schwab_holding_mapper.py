"""Unit tests for SchwabHoldingMapper.

Tests the mapping of Schwab position JSON responses to ProviderHoldingData.
"""

from decimal import Decimal
from typing import Any

import pytest

from src.domain.protocols.provider_protocol import ProviderHoldingData
from src.infrastructure.providers.schwab.mappers.holding_mapper import (
    SCHWAB_ASSET_TYPE_MAP,
    SchwabHoldingMapper,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mapper() -> SchwabHoldingMapper:
    """Create a SchwabHoldingMapper instance."""
    return SchwabHoldingMapper()


@pytest.fixture
def valid_equity_position() -> dict[str, Any]:
    """Create a valid equity position from Schwab."""
    return {
        "longQuantity": 100.0,
        "shortQuantity": 0.0,
        "averagePrice": 150.25,
        "marketValue": 15500.00,
        "currentDayCost": 15025.00,
        "instrument": {
            "assetType": "EQUITY",
            "cusip": "037833100",
            "symbol": "AAPL",
            "description": "APPLE INC",
            "netChange": 1.25,
        },
    }


@pytest.fixture
def valid_etf_position() -> dict[str, Any]:
    """Create a valid ETF position from Schwab."""
    return {
        "longQuantity": 50.0,
        "shortQuantity": 0.0,
        "averagePrice": 450.00,
        "marketValue": 23000.00,
        "instrument": {
            "assetType": "ETF",
            "cusip": "78462F103",
            "symbol": "SPY",
            "description": "SPDR S&P 500 ETF TRUST",
        },
    }


@pytest.fixture
def valid_option_position() -> dict[str, Any]:
    """Create a valid option position from Schwab."""
    return {
        "longQuantity": 5.0,
        "shortQuantity": 0.0,
        "averagePrice": 3.50,
        "marketValue": 1750.00,
        "instrument": {
            "assetType": "OPTION",
            "cusip": "",
            "symbol": "AAPL_012624C195",
            "description": "AAPL Jan 26 2024 195 Call",
            "underlyingSymbol": "AAPL",
        },
    }


@pytest.fixture
def short_position() -> dict[str, Any]:
    """Create a short position from Schwab."""
    return {
        "longQuantity": 0.0,
        "shortQuantity": 50.0,
        "averagePrice": 200.00,
        "marketValue": -10000.00,
        "instrument": {
            "assetType": "EQUITY",
            "cusip": "88160R101",
            "symbol": "TSLA",
            "description": "TESLA INC",
        },
    }


@pytest.fixture
def account_with_positions() -> dict[str, Any]:
    """Create a full account response with positions."""
    return {
        "securitiesAccount": {
            "type": "INDIVIDUAL",
            "accountNumber": "12345678",
            "positions": [
                {
                    "longQuantity": 100.0,
                    "averagePrice": 150.25,
                    "marketValue": 15500.00,
                    "instrument": {
                        "assetType": "EQUITY",
                        "cusip": "037833100",
                        "symbol": "AAPL",
                        "description": "APPLE INC",
                    },
                },
                {
                    "longQuantity": 50.0,
                    "averagePrice": 450.00,
                    "marketValue": 23000.00,
                    "instrument": {
                        "assetType": "ETF",
                        "cusip": "78462F103",
                        "symbol": "SPY",
                        "description": "SPDR S&P 500 ETF TRUST",
                    },
                },
            ],
        }
    }


# =============================================================================
# Test: map_holding - Valid Data
# =============================================================================


class TestMapHoldingValidData:
    """Tests for map_holding with valid position data."""

    def test_maps_equity_position(
        self, mapper: SchwabHoldingMapper, valid_equity_position: dict[str, Any]
    ) -> None:
        """Test mapping a valid equity position."""
        result = mapper.map_holding(valid_equity_position)

        assert result is not None
        assert isinstance(result, ProviderHoldingData)
        assert result.symbol == "AAPL"
        assert result.security_name == "APPLE INC"
        assert result.asset_type == "equity"
        assert result.quantity == Decimal("100")
        assert result.average_price == Decimal("150.25")
        assert result.market_value == Decimal("15500")
        assert result.currency == "USD"
        assert result.provider_holding_id == "schwab_037833100_AAPL"

    def test_maps_etf_position(
        self, mapper: SchwabHoldingMapper, valid_etf_position: dict[str, Any]
    ) -> None:
        """Test mapping a valid ETF position."""
        result = mapper.map_holding(valid_etf_position)

        assert result is not None
        assert result.symbol == "SPY"
        assert result.asset_type == "etf"
        assert result.quantity == Decimal("50")
        assert result.market_value == Decimal("23000")

    def test_maps_option_position(
        self, mapper: SchwabHoldingMapper, valid_option_position: dict[str, Any]
    ) -> None:
        """Test mapping a valid option position."""
        result = mapper.map_holding(valid_option_position)

        assert result is not None
        assert result.symbol == "AAPL_012624C195"
        assert result.asset_type == "option"
        assert result.quantity == Decimal("5")
        # Options without CUSIP use asset_type in ID
        assert result.provider_holding_id == "schwab_option_AAPL_012624C195"

    def test_maps_short_position(
        self, mapper: SchwabHoldingMapper, short_position: dict[str, Any]
    ) -> None:
        """Test mapping a short position (negative quantity)."""
        result = mapper.map_holding(short_position)

        assert result is not None
        assert result.symbol == "TSLA"
        assert result.quantity == Decimal("-50")  # Negative for short
        assert result.market_value == Decimal("-10000")

    def test_calculates_cost_basis_from_average_price(
        self, mapper: SchwabHoldingMapper, valid_equity_position: dict[str, Any]
    ) -> None:
        """Test cost basis calculation from average price * quantity."""
        result = mapper.map_holding(valid_equity_position)

        assert result is not None
        # 100 shares * $150.25 = $15,025
        assert result.cost_basis == Decimal("15025.00")

    def test_preserves_raw_data(
        self, mapper: SchwabHoldingMapper, valid_equity_position: dict[str, Any]
    ) -> None:
        """Test that raw data is preserved in result."""
        result = mapper.map_holding(valid_equity_position)

        assert result is not None
        assert result.raw_data == valid_equity_position


# =============================================================================
# Test: map_holding - Edge Cases
# =============================================================================


class TestMapHoldingEdgeCases:
    """Tests for map_holding edge cases."""

    def test_returns_none_for_missing_instrument(
        self, mapper: SchwabHoldingMapper
    ) -> None:
        """Test that missing instrument returns None."""
        data = {
            "longQuantity": 100.0,
            "averagePrice": 150.25,
            "marketValue": 15500.00,
        }
        result = mapper.map_holding(data)
        assert result is None

    def test_returns_none_for_empty_instrument(
        self, mapper: SchwabHoldingMapper
    ) -> None:
        """Test that empty instrument returns None."""
        data = {
            "longQuantity": 100.0,
            "averagePrice": 150.25,
            "marketValue": 15500.00,
            "instrument": {},
        }
        result = mapper.map_holding(data)
        assert result is None

    def test_returns_none_for_missing_symbol(self, mapper: SchwabHoldingMapper) -> None:
        """Test that missing symbol returns None."""
        data = {
            "longQuantity": 100.0,
            "averagePrice": 150.25,
            "marketValue": 15500.00,
            "instrument": {
                "assetType": "EQUITY",
                "cusip": "037833100",
            },
        }
        result = mapper.map_holding(data)
        assert result is None

    def test_returns_none_for_zero_quantity(self, mapper: SchwabHoldingMapper) -> None:
        """Test that zero quantity position returns None."""
        data = {
            "longQuantity": 0.0,
            "shortQuantity": 0.0,
            "averagePrice": 150.25,
            "marketValue": 0.0,
            "instrument": {
                "assetType": "EQUITY",
                "cusip": "037833100",
                "symbol": "AAPL",
            },
        }
        result = mapper.map_holding(data)
        assert result is None

    def test_handles_missing_average_price(self, mapper: SchwabHoldingMapper) -> None:
        """Test handling of missing average price (uses currentDayCost)."""
        data = {
            "longQuantity": 100.0,
            "marketValue": 15500.00,
            "currentDayCost": 15000.00,
            "instrument": {
                "assetType": "EQUITY",
                "cusip": "037833100",
                "symbol": "AAPL",
                "description": "APPLE INC",
            },
        }
        result = mapper.map_holding(data)

        assert result is not None
        assert result.average_price is None
        assert result.cost_basis == Decimal("15000")

    def test_handles_missing_description_uses_symbol(
        self, mapper: SchwabHoldingMapper
    ) -> None:
        """Test that missing description falls back to symbol."""
        data = {
            "longQuantity": 100.0,
            "averagePrice": 150.25,
            "marketValue": 15500.00,
            "instrument": {
                "assetType": "EQUITY",
                "cusip": "037833100",
                "symbol": "AAPL",
            },
        }
        result = mapper.map_holding(data)

        assert result is not None
        assert result.security_name == "AAPL"

    def test_handles_invalid_decimal_values(self, mapper: SchwabHoldingMapper) -> None:
        """Test handling of invalid decimal values."""
        data = {
            "longQuantity": "not_a_number",
            "averagePrice": 150.25,
            "marketValue": 15500.00,
            "instrument": {
                "assetType": "EQUITY",
                "cusip": "037833100",
                "symbol": "AAPL",
                "description": "APPLE INC",
            },
        }
        # Should return None due to zero quantity after parsing error
        result = mapper.map_holding(data)
        assert result is None


# =============================================================================
# Test: map_holdings - List Processing
# =============================================================================


class TestMapHoldings:
    """Tests for map_holdings (list processing)."""

    def test_maps_multiple_positions(
        self,
        mapper: SchwabHoldingMapper,
        valid_equity_position: dict[str, Any],
        valid_etf_position: dict[str, Any],
    ) -> None:
        """Test mapping multiple positions."""
        positions = [valid_equity_position, valid_etf_position]
        results = mapper.map_holdings(positions)

        assert len(results) == 2
        symbols = {r.symbol for r in results}
        assert symbols == {"AAPL", "SPY"}

    def test_skips_invalid_positions(
        self,
        mapper: SchwabHoldingMapper,
        valid_equity_position: dict[str, Any],
    ) -> None:
        """Test that invalid positions are skipped."""
        positions = [
            valid_equity_position,
            {"invalid": "data"},
            {"longQuantity": 0, "instrument": {"symbol": "ZERO"}},
        ]
        results = mapper.map_holdings(positions)

        assert len(results) == 1
        assert results[0].symbol == "AAPL"

    def test_handles_empty_list(self, mapper: SchwabHoldingMapper) -> None:
        """Test handling of empty position list."""
        results = mapper.map_holdings([])
        assert results == []


# =============================================================================
# Test: map_holdings_from_account
# =============================================================================


class TestMapHoldingsFromAccount:
    """Tests for map_holdings_from_account."""

    def test_extracts_positions_from_account(
        self, mapper: SchwabHoldingMapper, account_with_positions: dict[str, Any]
    ) -> None:
        """Test extracting positions from full account response."""
        results = mapper.map_holdings_from_account(account_with_positions)

        assert len(results) == 2
        symbols = {r.symbol for r in results}
        assert symbols == {"AAPL", "SPY"}

    def test_handles_account_without_positions(
        self, mapper: SchwabHoldingMapper
    ) -> None:
        """Test handling account with no positions."""
        account_data = {
            "securitiesAccount": {
                "type": "INDIVIDUAL",
                "accountNumber": "12345678",
            }
        }
        results = mapper.map_holdings_from_account(account_data)
        assert results == []

    def test_handles_empty_positions_list(self, mapper: SchwabHoldingMapper) -> None:
        """Test handling account with empty positions list."""
        account_data = {
            "securitiesAccount": {
                "type": "INDIVIDUAL",
                "accountNumber": "12345678",
                "positions": [],
            }
        }
        results = mapper.map_holdings_from_account(account_data)
        assert results == []

    def test_handles_missing_securities_account(
        self, mapper: SchwabHoldingMapper
    ) -> None:
        """Test handling response without securitiesAccount."""
        results = mapper.map_holdings_from_account({})
        assert results == []


# =============================================================================
# Test: Asset Type Mapping
# =============================================================================


class TestAssetTypeMapping:
    """Tests for asset type mapping."""

    @pytest.mark.parametrize(
        "schwab_type,expected",
        [
            ("EQUITY", "equity"),
            ("STOCK", "equity"),
            ("ETF", "etf"),
            ("MUTUAL_FUND", "mutual_fund"),
            ("OPTION", "option"),
            ("FIXED_INCOME", "fixed_income"),
            ("BOND", "fixed_income"),
            ("CASH_EQUIVALENT", "cash_equivalent"),
            ("MONEY_MARKET", "cash_equivalent"),
            ("FUTURES", "futures"),
            ("CRYPTO", "cryptocurrency"),
        ],
    )
    def test_maps_known_asset_types(
        self, mapper: SchwabHoldingMapper, schwab_type: str, expected: str
    ) -> None:
        """Test mapping of known Schwab asset types."""
        result = mapper._map_asset_type(schwab_type)
        assert result == expected

    def test_maps_unknown_type_to_other(self, mapper: SchwabHoldingMapper) -> None:
        """Test that unknown asset type maps to 'other'."""
        result = mapper._map_asset_type("UNKNOWN_TYPE")
        assert result == "other"

    def test_handles_empty_asset_type(self, mapper: SchwabHoldingMapper) -> None:
        """Test handling of empty asset type."""
        result = mapper._map_asset_type("")
        assert result == "other"

    def test_normalizes_case(self, mapper: SchwabHoldingMapper) -> None:
        """Test that asset type comparison is case-insensitive."""
        assert mapper._map_asset_type("equity") == "equity"
        assert mapper._map_asset_type("Equity") == "equity"
        assert mapper._map_asset_type("EQUITY") == "equity"


# =============================================================================
# Test: Position ID Generation
# =============================================================================


class TestPositionIdGeneration:
    """Tests for position ID generation."""

    def test_uses_cusip_when_available(self, mapper: SchwabHoldingMapper) -> None:
        """Test that CUSIP is used in position ID when available."""
        result = mapper._generate_position_id("AAPL", "037833100", "equity")
        assert result == "schwab_037833100_AAPL"

    def test_uses_asset_type_without_cusip(self, mapper: SchwabHoldingMapper) -> None:
        """Test fallback to asset_type when CUSIP not available."""
        result = mapper._generate_position_id("AAPL_012624C195", "", "option")
        assert result == "schwab_option_AAPL_012624C195"


# =============================================================================
# Test: Decimal Parsing
# =============================================================================


class TestDecimalParsing:
    """Tests for decimal parsing methods."""

    def test_parses_float(self, mapper: SchwabHoldingMapper) -> None:
        """Test parsing float to Decimal."""
        result = mapper._parse_decimal(150.25)
        assert result == Decimal("150.25")

    def test_parses_int(self, mapper: SchwabHoldingMapper) -> None:
        """Test parsing int to Decimal."""
        result = mapper._parse_decimal(100)
        assert result == Decimal("100")

    def test_parses_string(self, mapper: SchwabHoldingMapper) -> None:
        """Test parsing string to Decimal."""
        result = mapper._parse_decimal("150.25")
        assert result == Decimal("150.25")

    def test_returns_zero_for_none(self, mapper: SchwabHoldingMapper) -> None:
        """Test that None returns Decimal('0')."""
        result = mapper._parse_decimal(None)
        assert result == Decimal("0")

    def test_optional_returns_none_for_none(self, mapper: SchwabHoldingMapper) -> None:
        """Test that _parse_decimal_optional returns None for None."""
        result = mapper._parse_decimal_optional(None)
        assert result is None

    def test_optional_parses_valid_value(self, mapper: SchwabHoldingMapper) -> None:
        """Test that _parse_decimal_optional parses valid values."""
        result = mapper._parse_decimal_optional(150.25)
        assert result == Decimal("150.25")


# =============================================================================
# Test: Asset Type Map Completeness
# =============================================================================


class TestAssetTypeMapCompleteness:
    """Tests for asset type map coverage."""

    def test_map_has_expected_entries(self) -> None:
        """Test that asset type map has expected entries."""
        expected_schwab_types = {
            "EQUITY",
            "STOCK",
            "ETF",
            "MUTUAL_FUND",
            "OPTION",
            "FIXED_INCOME",
            "BOND",
            "CASH_EQUIVALENT",
            "MONEY_MARKET",
            "CURRENCY",
            "FUTURES",
            "CRYPTO",
        }
        actual_types = set(SCHWAB_ASSET_TYPE_MAP.keys())

        # Check that all expected types are present
        missing = expected_schwab_types - actual_types
        assert not missing, f"Missing asset types: {missing}"
