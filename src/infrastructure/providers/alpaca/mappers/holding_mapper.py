"""Alpaca holding (position) mapper.

Converts Alpaca Trading API position JSON responses to ProviderHoldingData.
Contains Alpaca-specific knowledge about JSON structure.

Alpaca Position Response Structure:
    {
        "asset_id": "b0b6dd9d-8b9b-48a9-ba46-b9d54906e415",
        "symbol": "AAPL",
        "exchange": "NASDAQ",
        "asset_class": "us_equity",
        "asset_marginable": true,
        "qty": "100",
        "avg_entry_price": "150.25",
        "side": "long",
        "market_value": "15500.00",
        "cost_basis": "15025.00",
        "unrealized_pl": "475.00",
        "unrealized_plpc": "0.0316",
        "current_price": "155.00",
        ...
    }

Reference:
    - https://docs.alpaca.markets/reference/getallopenpositions-1
"""

from decimal import Decimal, InvalidOperation
from typing import Any

import structlog

from src.domain.protocols.provider_protocol import ProviderHoldingData

logger = structlog.get_logger(__name__)


# =============================================================================
# Asset Type Mapping
# =============================================================================

# Alpaca asset_class → Dashtam asset type
ALPACA_ASSET_TYPE_MAP: dict[str, str] = {
    "us_equity": "equity",
    "crypto": "cryptocurrency",
    # Alpaca doesn't support these yet, but mapping for future
    "etf": "etf",
    "option": "option",
}


class AlpacaHoldingMapper:
    """Mapper for converting Alpaca position data to ProviderHoldingData.

    This mapper handles:
    - Extracting data from Alpaca's position JSON structure
    - Mapping Alpaca asset classes to Dashtam types
    - Converting numeric values to Decimal with proper precision
    - Handling both long and short positions

    Thread-safe: No mutable state, can be shared across requests.

    Example:
        >>> mapper = AlpacaHoldingMapper()
        >>> positions = [{"symbol": "AAPL", "qty": "100", ...}]
        >>> holdings = mapper.map_holdings(positions)
        >>> print(f"Mapped {len(holdings)} holdings")
    """

    def map_holding(self, data: dict[str, Any]) -> ProviderHoldingData | None:
        """Map single Alpaca position JSON to ProviderHoldingData.

        Args:
            data: Single position object from Alpaca API response.

        Returns:
            ProviderHoldingData if mapping succeeds, None if data is invalid
            or missing required fields.

        Example:
            >>> data = {
            ...     "asset_id": "abc123",
            ...     "symbol": "AAPL",
            ...     "qty": "100",
            ...     "market_value": "15500",
            ...     "cost_basis": "15000",
            ... }
            >>> result = mapper.map_holding(data)
            >>> result.symbol
            'AAPL'
        """
        try:
            return self._map_holding_internal(data)
        except (KeyError, TypeError, InvalidOperation, AttributeError, ValueError) as e:
            logger.warning(
                "alpaca_holding_mapping_failed",
                error=str(e),
                error_type=type(e).__name__,
            )
            return None

    def map_holdings(
        self, data_list: list[dict[str, Any]]
    ) -> list[ProviderHoldingData]:
        """Map list of Alpaca position JSON objects to ProviderHoldingData.

        Skips invalid positions and logs warnings. Never raises exceptions.

        Args:
            data_list: List of position objects from Alpaca API.

        Returns:
            List of successfully mapped holdings. May be empty if all fail.
        """
        holdings: list[ProviderHoldingData] = []

        for data in data_list:
            holding = self.map_holding(data)
            if holding is not None:
                holdings.append(holding)

        return holdings

    def _map_holding_internal(self, data: dict[str, Any]) -> ProviderHoldingData | None:
        """Internal mapping logic.

        Raises exceptions on invalid data (caught by map_holding).
        """
        # Get symbol (required)
        symbol = data.get("symbol")
        if not symbol:
            logger.debug("alpaca_holding_missing_symbol")
            return None

        # Get asset ID for unique identifier
        asset_id = data.get("asset_id", "")
        if not asset_id:
            # Fall back to symbol if no asset_id
            asset_id = f"alpaca_{symbol}"

        # Get asset type
        asset_class = data.get("asset_class", "us_equity")
        asset_type = self._map_asset_type(asset_class)

        # Get quantity (handle side for short positions)
        qty_str = data.get("qty", "0")
        quantity = self._parse_decimal(qty_str)
        side = data.get("side", "long")
        if side == "short":
            quantity = -abs(quantity)

        # Skip zero-quantity positions
        if quantity == Decimal("0"):
            logger.debug(
                "alpaca_holding_zero_quantity",
                symbol=symbol,
            )
            return None

        # Get price and value data
        cost_basis = self._parse_decimal(data.get("cost_basis", "0"))
        market_value = self._parse_decimal(data.get("market_value", "0"))
        avg_entry_price = self._parse_decimal_optional(data.get("avg_entry_price"))
        current_price = self._parse_decimal_optional(data.get("current_price"))

        # Security name - Alpaca doesn't provide this, use symbol
        # We could look it up via the assets API but that's extra calls
        security_name = symbol

        return ProviderHoldingData(
            provider_holding_id=asset_id,
            symbol=symbol,
            security_name=security_name,
            asset_type=asset_type,
            quantity=quantity,
            cost_basis=cost_basis,
            market_value=market_value,
            currency="USD",  # Alpaca only supports USD
            average_price=avg_entry_price,
            current_price=current_price,
            raw_data=data,
        )

    def _map_asset_type(self, asset_class: str) -> str:
        """Map Alpaca asset class to Dashtam asset type.

        Args:
            asset_class: Asset class from Alpaca API.

        Returns:
            Mapped asset type string, defaults to "other".
        """
        if not asset_class:
            return "other"

        normalized = asset_class.lower().strip()
        mapped = ALPACA_ASSET_TYPE_MAP.get(normalized)

        if mapped is None:
            logger.info(
                "alpaca_unknown_asset_type",
                alpaca_type=asset_class,
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
        """
        if value is None:
            return Decimal("0")

        try:
            return Decimal(str(value))
        except (InvalidOperation, ValueError):
            logger.warning(
                "alpaca_invalid_decimal_value",
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
