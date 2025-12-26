"""Alpaca transaction mapper.

Converts Alpaca Trading API activity JSON responses to ProviderTransactionData.
Contains Alpaca-specific knowledge about JSON structure and activity types.

Alpaca Activity Types:
    FILL - Order fill (trade execution)
    DIV - Dividend
    DIVCGL - Dividend (capital gain long term)
    DIVCGS - Dividend (capital gain short term)
    DIVNRA - Dividend (non-resident alien tax)
    DIVFT - Dividend (foreign tax withheld)
    DIVTXEX - Dividend (tax exempt)
    INT - Interest
    JNLC - Journal entry (cash)
    JNLS - Journal entry (stock)
    MA - Merger/Acquisition
    NC - Name change
    PTC - Pass-through charge
    REO - Reorg fee
    SC - Symbol change
    SSO - Stock spinoff
    SSP - Stock split

Activity Response Structure (Trade Fill):
    {
        "id": "20210301000000000::8c51c51d-2ccb-4a7c-9bc1-f31b0a7b0ae9",
        "activity_type": "FILL",
        "transaction_time": "2021-03-01T09:30:00Z",
        "type": "fill",
        "price": "150.25",
        "qty": "100",
        "side": "buy",
        "symbol": "AAPL",
        "leaves_qty": "0",
        "order_id": "abc123",
        "cum_qty": "100",
        "order_status": "filled"
    }

Activity Response Structure (Non-Trade):
    {
        "id": "20211025000000000::c3599cf9-a5fe-44a2-863a-49f0d3276ae4",
        "activity_type": "JNLC",
        "date": "2021-10-25",
        "net_amount": "100000",
        "description": "",
        "status": "executed"
    }

Reference:
    - https://docs.alpaca.markets/reference/getaccountactivities-1
"""

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

import structlog

from src.domain.protocols.provider_protocol import ProviderTransactionData

logger = structlog.get_logger(__name__)


# =============================================================================
# Transaction Type Mapping
# =============================================================================

# Alpaca activity_type → Dashtam transaction_type
ALPACA_TRANSACTION_TYPE_MAP: dict[str, str] = {
    # Trade types
    "FILL": "trade",
    # Income types
    "DIV": "income",
    "DIVCGL": "income",
    "DIVCGS": "income",
    "DIVNRA": "income",
    "DIVFT": "income",
    "DIVTXEX": "income",
    "INT": "income",
    # Transfer types
    "JNLC": "transfer",
    "JNLS": "transfer",
    "WIRE": "transfer",
    "ACH": "transfer",
    # Fee types
    "FEE": "fee",
    "PTC": "fee",
    "REO": "fee",
    # Other/corporate actions
    "MA": "other",
    "NC": "other",
    "SC": "other",
    "SSO": "other",
    "SSP": "other",
}

# Alpaca side → Dashtam subtype (for trades)
ALPACA_TRADE_SUBTYPE_MAP: dict[str, str] = {
    "buy": "buy",
    "sell": "sell",
    "buy_to_cover": "buy_to_cover",
    "sell_short": "short_sell",
}


class AlpacaTransactionMapper:
    """Mapper for converting Alpaca activity data to ProviderTransactionData.

    This mapper handles:
    - Extracting data from Alpaca's activity JSON structure
    - Mapping Alpaca activity types to Dashtam transaction types
    - Determining subtypes based on trade side
    - Converting amounts and dates with proper precision
    - Handling both trade and non-trade activities

    Thread-safe: No mutable state, can be shared across requests.

    Example:
        >>> mapper = AlpacaTransactionMapper()
        >>> activities = [{"activity_type": "FILL", "symbol": "AAPL", ...}]
        >>> transactions = mapper.map_transactions(activities)
        >>> print(f"Mapped {len(transactions)} transactions")
    """

    def map_transaction(self, data: dict[str, Any]) -> ProviderTransactionData | None:
        """Map single Alpaca activity JSON to ProviderTransactionData.

        Args:
            data: Single activity object from Alpaca API response.

        Returns:
            ProviderTransactionData if mapping succeeds, None if data is invalid
            or missing required fields.
        """
        try:
            return self._map_transaction_internal(data)
        except (KeyError, TypeError, InvalidOperation, AttributeError, ValueError) as e:
            logger.warning(
                "alpaca_transaction_mapping_failed",
                error=str(e),
                error_type=type(e).__name__,
            )
            return None

    def map_transactions(
        self, data_list: list[dict[str, Any]]
    ) -> list[ProviderTransactionData]:
        """Map list of Alpaca activity JSON objects to ProviderTransactionData.

        Skips invalid activities and logs warnings. Never raises exceptions.

        Args:
            data_list: List of activity objects from Alpaca API.

        Returns:
            List of successfully mapped transactions. May be empty if all fail.
        """
        transactions: list[ProviderTransactionData] = []

        for data in data_list:
            txn = self.map_transaction(data)
            if txn is not None:
                transactions.append(txn)

        return transactions

    def _map_transaction_internal(
        self, data: dict[str, Any]
    ) -> ProviderTransactionData | None:
        """Internal mapping logic.

        Raises exceptions on invalid data (caught by map_transaction).
        """
        # Extract transaction ID (required)
        txn_id = data.get("id")
        if not txn_id:
            logger.debug("alpaca_transaction_missing_id")
            return None

        # Get activity type
        activity_type = data.get("activity_type", "UNKNOWN")
        transaction_type = self._map_transaction_type(activity_type)

        # Parse transaction date
        txn_date = self._parse_date(data)
        if txn_date is None:
            logger.debug("alpaca_transaction_missing_date", txn_id=txn_id)
            return None

        # Determine if this is a trade or non-trade activity
        is_trade = activity_type == "FILL"

        if is_trade:
            return self._map_trade_activity(data, txn_id, transaction_type, txn_date)
        else:
            return self._map_non_trade_activity(
                data, txn_id, transaction_type, txn_date, activity_type
            )

    def _map_trade_activity(
        self,
        data: dict[str, Any],
        txn_id: str,
        transaction_type: str,
        txn_date: date,
    ) -> ProviderTransactionData:
        """Map a trade (FILL) activity."""
        # Get trade details
        symbol = data.get("symbol", "")
        side = data.get("side", "")
        subtype = self._map_trade_subtype(side)

        # Parse amounts
        qty = self._parse_decimal(data.get("qty", "0"))
        price = self._parse_decimal(data.get("price", "0"))

        # Calculate total amount (negative for buys, positive for sells)
        total_amount = qty * price
        if side in ("buy", "buy_to_cover"):
            total_amount = -total_amount

        # Build description
        description = f"{side.upper()} {qty} {symbol} @ ${price}"

        return ProviderTransactionData(
            provider_transaction_id=txn_id,
            transaction_type=transaction_type,
            subtype=subtype,
            amount=total_amount,
            currency="USD",
            description=description,
            transaction_date=txn_date,
            status="executed",
            symbol=symbol,
            security_name=symbol,  # Alpaca doesn't provide full name
            asset_type="equity",  # Alpaca trades are typically equity
            quantity=qty,
            unit_price=price,
            commission=Decimal("0"),  # Alpaca is commission-free
            raw_data=data,
        )

    def _map_non_trade_activity(
        self,
        data: dict[str, Any],
        txn_id: str,
        transaction_type: str,
        txn_date: date,
        activity_type: str,
    ) -> ProviderTransactionData:
        """Map a non-trade activity (dividend, transfer, etc.)."""
        # Parse amount
        amount = self._parse_decimal(data.get("net_amount", "0"))

        # Get description
        description = data.get("description", "")
        if not description:
            description = self._generate_description(activity_type, amount)

        # Get status
        status = data.get("status", "executed")

        # For dividend activities, try to get the symbol
        symbol = data.get("symbol")

        return ProviderTransactionData(
            provider_transaction_id=txn_id,
            transaction_type=transaction_type,
            subtype=self._get_non_trade_subtype(activity_type),
            amount=amount,
            currency="USD",
            description=description,
            transaction_date=txn_date,
            status=status,
            symbol=symbol,
            security_name=symbol if symbol else None,
            raw_data=data,
        )

    def _map_transaction_type(self, activity_type: str) -> str:
        """Map Alpaca activity type to Dashtam transaction type.

        Args:
            activity_type: Activity type from Alpaca API.

        Returns:
            Mapped transaction type string, defaults to "other".
        """
        if not activity_type:
            return "other"

        normalized = activity_type.upper().strip()
        mapped = ALPACA_TRANSACTION_TYPE_MAP.get(normalized)

        if mapped is None:
            logger.info(
                "alpaca_unknown_activity_type",
                alpaca_type=activity_type,
                defaulting_to="other",
            )
            return "other"

        return mapped

    def _map_trade_subtype(self, side: str) -> str | None:
        """Map Alpaca trade side to Dashtam subtype.

        Args:
            side: Trade side from Alpaca API (buy, sell, etc.).

        Returns:
            Mapped subtype or None.
        """
        if not side:
            return None

        normalized = side.lower().strip()
        return ALPACA_TRADE_SUBTYPE_MAP.get(normalized)

    def _get_non_trade_subtype(self, activity_type: str) -> str | None:
        """Get subtype for non-trade activities.

        Args:
            activity_type: Alpaca activity type.

        Returns:
            Subtype string or None.
        """
        subtypes = {
            "DIV": "dividend",
            "DIVCGL": "dividend_capital_gain_long",
            "DIVCGS": "dividend_capital_gain_short",
            "INT": "interest",
            "JNLC": "journal_cash",
            "JNLS": "journal_stock",
        }
        return subtypes.get(activity_type.upper())

    def _generate_description(self, activity_type: str, amount: Decimal) -> str:
        """Generate a description for activities without one.

        Args:
            activity_type: Alpaca activity type.
            amount: Transaction amount.

        Returns:
            Generated description string.
        """
        descriptions = {
            "JNLC": "Journal entry (cash)",
            "JNLS": "Journal entry (stock)",
            "DIV": "Dividend",
            "INT": "Interest",
            "WIRE": "Wire transfer",
            "ACH": "ACH transfer",
        }
        base = descriptions.get(activity_type, activity_type)
        if amount >= 0:
            return f"{base}: ${amount}"
        return f"{base}: -${abs(amount)}"

    def _parse_date(self, data: dict[str, Any]) -> date | None:
        """Parse transaction date from Alpaca activity data.

        Alpaca uses different date fields for different activity types:
        - Trade fills: transaction_time (ISO timestamp)
        - Non-trade: date (YYYY-MM-DD)

        Args:
            data: Activity data dict.

        Returns:
            Parsed date or None if missing/invalid.
        """
        # Try transaction_time first (for trades)
        txn_time = data.get("transaction_time")
        if txn_time:
            try:
                # Parse ISO timestamp
                if isinstance(txn_time, str):
                    dt = datetime.fromisoformat(txn_time.replace("Z", "+00:00"))
                    return dt.date()
            except (ValueError, TypeError):
                pass

        # Try date field (for non-trades)
        date_str = data.get("date")
        if date_str:
            try:
                if isinstance(date_str, str):
                    return date.fromisoformat(date_str)
            except (ValueError, TypeError):
                pass

        # Try created_at as fallback
        created_at = data.get("created_at")
        if created_at:
            try:
                if isinstance(created_at, str):
                    dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                    return dt.date()
            except (ValueError, TypeError):
                pass

        return None

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
