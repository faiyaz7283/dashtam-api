"""Schwab holding (position) mapper.

Converts Schwab Trader API position JSON responses to ProviderHoldingData.
Contains Schwab-specific knowledge about JSON structure and type mappings.

Schwab Position Response Structure (nested in account response):
    {
        "securitiesAccount": {
            "positions": [
                {
                    "longQuantity": 100.0,
                    "averagePrice": 150.25,
                    "marketValue": 15500.00,
                    "currentDayCost": 15025.00,
                    "instrument": {
                        "assetType": "EQUITY",
                        "cusip": "037833100",
                        "symbol": "AAPL",
                        "description": "APPLE INC",
                        "netChange": 1.25
                    }
                }
            ]
        }
    }

Reference:
    - docs/architecture/provider-integration-architecture.md
    - Schwab Trader API: https://developer.schwab.com
"""

from decimal import Decimal, InvalidOperation
from typing import Any

import structlog

from src.domain.protocols.provider_protocol import ProviderHoldingData

logger = structlog.get_logger(__name__)


# =============================================================================
# Asset Type Mapping
# =============================================================================

# Schwab asset type → Dashtam asset type (matches transaction mapper)
SCHWAB_ASSET_TYPE_MAP: dict[str, str] = {
    "EQUITY": "equity",
    "STOCK": "equity",
    "ETF": "etf",
    "MUTUAL_FUND": "mutual_fund",
    "OPTION": "option",
    "FIXED_INCOME": "fixed_income",
    "BOND": "fixed_income",
    "CASH_EQUIVALENT": "cash_equivalent",
    "MONEY_MARKET": "cash_equivalent",
    "CURRENCY": "cash_equivalent",
    "FUTURES": "futures",
    "CRYPTO": "cryptocurrency",
    "INDEX": "index",
    "FOREX": "forex",
    "COLLECTIVE_INVESTMENT": "mutual_fund",
}


class SchwabHoldingMapper:
    """Mapper for converting Schwab position data to ProviderHoldingData.

    This mapper handles:
    - Extracting data from Schwab's nested JSON structure
    - Mapping Schwab asset types to Dashtam types
    - Converting numeric values to Decimal with proper precision
    - Handling both long and short positions
    - Generating unique position identifiers

    Thread-safe: No mutable state, can be shared across requests.

    Example:
        >>> mapper = SchwabHoldingMapper()
        >>> account_data = {"securitiesAccount": {"positions": [...]}}
        >>> holdings = mapper.map_holdings_from_account(account_data)
        >>> print(f"Mapped {len(holdings)} holdings")
    """

    def map_holding(self, data: dict[str, Any]) -> ProviderHoldingData | None:
        """Map single Schwab position JSON to ProviderHoldingData.

        Args:
            data: Single position object from Schwab account response.

        Returns:
            ProviderHoldingData if mapping succeeds, None if data is invalid
            or missing required fields.

        Example:
            >>> data = {
            ...     "longQuantity": 100,
            ...     "averagePrice": 150.25,
            ...     "marketValue": 15500,
            ...     "instrument": {"symbol": "AAPL", "assetType": "EQUITY", ...}
            ... }
            >>> result = mapper.map_holding(data)
            >>> result.symbol
            'AAPL'
        """
        try:
            return self._map_holding_internal(data)
        except (KeyError, TypeError, InvalidOperation, AttributeError, ValueError) as e:
            logger.warning(
                "schwab_holding_mapping_failed",
                error=str(e),
                error_type=type(e).__name__,
            )
            return None

    def map_holdings(
        self, data_list: list[dict[str, Any]]
    ) -> list[ProviderHoldingData]:
        """Map list of Schwab position JSON objects to ProviderHoldingData.

        Skips invalid positions and logs warnings. Never raises exceptions.

        Args:
            data_list: List of position objects from Schwab API.

        Returns:
            List of successfully mapped holdings. May be empty if all fail.

        Example:
            >>> holdings = mapper.map_holdings(positions_list)
            >>> print(f"Mapped {len(holdings)} holdings")
        """
        holdings: list[ProviderHoldingData] = []

        for data in data_list:
            holding = self.map_holding(data)
            if holding is not None:
                holdings.append(holding)

        return holdings

    def map_holdings_from_account(
        self, account_data: dict[str, Any]
    ) -> list[ProviderHoldingData]:
        """Extract and map holdings from full Schwab account response.

        This is the primary entry point when processing account data
        that was fetched with include_positions=True.

        Args:
            account_data: Full account object from Schwab API.
                Expected structure: {"securitiesAccount": {"positions": [...]}}

        Returns:
            List of successfully mapped holdings. May be empty.

        Example:
            >>> # account_data from GET /accounts/{id}?fields=positions
            >>> holdings = mapper.map_holdings_from_account(account_data)
        """
        # Extract positions from nested structure
        securities_account = account_data.get("securitiesAccount", {})
        positions = securities_account.get("positions", [])

        if not positions:
            logger.debug(
                "schwab_account_no_positions",
                has_securities_account=bool(securities_account),
            )
            return []

        return self.map_holdings(positions)

    def _map_holding_internal(self, data: dict[str, Any]) -> ProviderHoldingData | None:
        """Internal mapping logic.

        Raises exceptions on invalid data (caught by map_holding).
        """
        # Extract instrument details
        instrument = data.get("instrument", {})
        if not instrument:
            logger.debug("schwab_holding_missing_instrument")
            return None

        # Get symbol (required)
        symbol = instrument.get("symbol")
        if not symbol:
            logger.debug("schwab_holding_missing_symbol")
            return None

        # Get asset type
        schwab_asset_type = instrument.get("assetType", "UNKNOWN")
        asset_type = self._map_asset_type(schwab_asset_type)

        # Get security name
        security_name = (
            instrument.get("description")
            or instrument.get("underlyingSymbol")  # For options
            or symbol
        )

        # Calculate quantity (handle long and short positions)
        long_qty = self._parse_decimal(data.get("longQuantity", 0))
        short_qty = self._parse_decimal(data.get("shortQuantity", 0))
        quantity = long_qty - short_qty  # Net position

        # Skip zero-quantity positions
        if quantity == Decimal("0"):
            logger.debug(
                "schwab_holding_zero_quantity",
                symbol=symbol,
            )
            return None

        # Get price and value data
        average_price = self._parse_decimal_optional(data.get("averagePrice"))
        current_price = self._parse_decimal_optional(
            instrument.get("lastPrice")
            or data.get("currentDayProfitLoss")  # Fallback indicator
        )
        market_value = self._parse_decimal(data.get("marketValue", 0))

        # Calculate cost basis
        # Schwab provides currentDayCost for current day's purchases
        # For total cost basis, use averagePrice * quantity
        if average_price:
            cost_basis = abs(quantity) * average_price
        else:
            # Fall back to currentDayCost if available
            cost_basis = self._parse_decimal(data.get("currentDayCost", 0))

        # Generate unique position ID
        # Schwab doesn't provide explicit position IDs, so we create one
        # using account-agnostic identifiers
        cusip = instrument.get("cusip", "")
        position_id = self._generate_position_id(symbol, cusip, asset_type)

        return ProviderHoldingData(
            provider_holding_id=position_id,
            symbol=symbol,
            security_name=security_name,
            asset_type=asset_type,
            quantity=quantity,
            cost_basis=cost_basis,
            market_value=market_value,
            currency="USD",  # Schwab accounts are USD
            average_price=average_price,
            current_price=current_price,
            raw_data=data,
        )

    def _map_asset_type(self, schwab_asset_type: str) -> str:
        """Map Schwab asset type to Dashtam asset type.

        Args:
            schwab_asset_type: Asset type from Schwab API.

        Returns:
            Mapped asset type string, defaults to "other".

        Example:
            >>> mapper._map_asset_type("EQUITY")
            'equity'
            >>> mapper._map_asset_type("UNKNOWN_TYPE")
            'other'
        """
        if not schwab_asset_type:
            return "other"

        normalized = schwab_asset_type.upper().strip()
        mapped = SCHWAB_ASSET_TYPE_MAP.get(normalized)

        if mapped is None:
            logger.info(
                "schwab_unknown_asset_type",
                schwab_type=schwab_asset_type,
                defaulting_to="other",
            )
            return "other"

        return mapped

    def _parse_decimal(self, value: Any) -> Decimal:
        """Parse numeric value to Decimal with proper precision.

        Args:
            value: Numeric value (int, float, str, or None).

        Returns:
            Decimal representation, Decimal("0") for None/invalid.

        Example:
            >>> mapper._parse_decimal(150.25)
            Decimal('150.25')
            >>> mapper._parse_decimal(None)
            Decimal('0')
        """
        if value is None:
            return Decimal("0")

        try:
            return Decimal(str(value))
        except (InvalidOperation, ValueError):
            logger.warning(
                "schwab_invalid_decimal_value",
                value=value,
                value_type=type(value).__name__,
            )
            return Decimal("0")

    def _parse_decimal_optional(self, value: Any) -> Decimal | None:
        """Parse numeric value to Decimal, returning None for missing/invalid.

        Args:
            value: Numeric value (int, float, str, or None).

        Returns:
            Decimal representation or None.
        """
        if value is None:
            return None

        try:
            return Decimal(str(value))
        except (InvalidOperation, ValueError):
            return None

    def _generate_position_id(
        self,
        symbol: str,
        cusip: str,
        asset_type: str,
    ) -> str:
        """Generate unique position identifier.

        Schwab doesn't provide explicit position IDs, so we create
        a deterministic ID based on security identifiers.

        Args:
            symbol: Security ticker symbol.
            cusip: CUSIP identifier (if available).
            asset_type: Asset type string.

        Returns:
            Unique position identifier string.

        Example:
            >>> mapper._generate_position_id("AAPL", "037833100", "equity")
            'schwab_037833100_AAPL'
            >>> mapper._generate_position_id("AAPL", "", "equity")
            'schwab_equity_AAPL'
        """
        # Prefer CUSIP for uniqueness (handles symbol changes)
        if cusip:
            return f"schwab_{cusip}_{symbol}"

        # Fall back to asset_type + symbol
        return f"schwab_{asset_type}_{symbol}"
