"""Schwab transaction mapper.

Converts Schwab Trader API transaction JSON responses to ProviderTransactionData.
Contains Schwab-specific knowledge about JSON structure and type mappings.

Transaction Type Mapping (Schwab → Dashtam):
    TRADE → TRADE (BUY/SELL based on transactionSubType)
    DIVIDEND_OR_INTEREST → INCOME (DIVIDEND or INTEREST based on context)
    JOURNAL → TRANSFER or OTHER
    ELECTRONIC_FUND → TRANSFER
    WIRE → TRANSFER
    CHECK → TRANSFER
    RECEIVE_AND_DELIVER → TRADE or TRANSFER
    FEE → FEE

Reference:
    - docs/architecture/provider-integration-architecture.md
    - Schwab Trader API: https://developer.schwab.com
"""

from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

import structlog

from src.domain.protocols.provider_protocol import ProviderTransactionData

logger = structlog.get_logger(__name__)


# =============================================================================
# Transaction Type Mapping
# =============================================================================

# Schwab transaction type → Dashtam TransactionType string
SCHWAB_TRANSACTION_TYPE_MAP: dict[str, str] = {
    # Trade types
    "TRADE": "trade",
    "RECEIVE_AND_DELIVER": "trade",  # Security transfers (in-kind)
    # Income types
    "DIVIDEND_OR_INTEREST": "income",
    "DIVIDEND": "income",
    "INTEREST": "income",
    "CAPITAL_GAINS": "income",
    "DIVIDEND_REINVEST": "income",
    # Transfer types
    "ELECTRONIC_FUND": "transfer",
    "ACH_RECEIPT": "transfer",
    "ACH_DISBURSEMENT": "transfer",
    "WIRE_IN": "transfer",
    "WIRE_OUT": "transfer",
    "CHECK": "transfer",
    "JOURNAL": "transfer",
    "INTERNAL_TRANSFER": "transfer",
    "CASH_RECEIPT": "transfer",
    "CASH_DISBURSEMENT": "transfer",
    # Fee types
    "SERVICE_FEE": "fee",
    "MARGIN_INTEREST": "fee",
    "ADR_FEE": "fee",
    "FOREIGN_TAX_WITHHELD": "fee",
    # Other/fallback
    "ADJUSTMENT": "other",
    "CORPORATE_ACTION": "other",
    "UNKNOWN": "other",
}

# Schwab trade subtype → Dashtam subtype
SCHWAB_TRADE_SUBTYPE_MAP: dict[str, str] = {
    "BUY": "buy",
    "SELL": "sell",
    "BUY_TO_OPEN": "buy",
    "BUY_TO_CLOSE": "buy_to_cover",
    "SELL_TO_OPEN": "short_sell",
    "SELL_TO_CLOSE": "sell",
    "SELL_SHORT": "short_sell",
    "BUY_TO_COVER": "buy_to_cover",
    # Option-specific
    "EXERCISE": "exercise",
    "ASSIGNMENT": "assignment",
    "EXPIRATION": "expiration",
    "EXPIRE": "expiration",
}

# Schwab asset type → Dashtam asset type
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
}


class SchwabTransactionMapper:
    """Mapper for converting Schwab transaction data to ProviderTransactionData.

    This mapper handles:
    - Extracting data from Schwab's nested JSON structure
    - Mapping Schwab transaction types to Dashtam types
    - Determining subtypes based on Schwab transactionSubType
    - Converting amounts and dates with proper precision
    - Extracting security details for trade transactions

    Thread-safe: No mutable state, can be shared across requests.

    Example:
        >>> mapper = SchwabTransactionMapper()
        >>> schwab_data = {"type": "TRADE", "netAmount": -1000, ...}
        >>> result = mapper.map_transaction(schwab_data)
        >>> if result is not None:
        ...     print(f"Transaction: {result.description}")
    """

    def map_transaction(self, data: dict[str, Any]) -> ProviderTransactionData | None:
        """Map single Schwab transaction JSON to ProviderTransactionData.

        Args:
            data: Single transaction object from Schwab API response.

        Returns:
            ProviderTransactionData if mapping succeeds, None if data is invalid
            or missing required fields.

        Example:
            >>> data = {"activityId": "123", "type": "TRADE", ...}
            >>> result = mapper.map_transaction(data)
        """
        try:
            return self._map_transaction_internal(data)
        except (KeyError, TypeError, InvalidOperation, AttributeError, ValueError) as e:
            logger.warning(
                "schwab_transaction_mapping_failed",
                error=str(e),
                error_type=type(e).__name__,
            )
            return None

    def map_transactions(
        self, data_list: list[dict[str, Any]]
    ) -> list[ProviderTransactionData]:
        """Map list of Schwab transaction JSON objects to ProviderTransactionData.

        Skips invalid transactions and logs warnings. Never raises exceptions.

        Args:
            data_list: List of transaction objects from Schwab API.

        Returns:
            List of successfully mapped transactions. May be empty if all fail.

        Example:
            >>> transactions = mapper.map_transactions(schwab_response)
            >>> print(f"Mapped {len(transactions)} transactions")
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
        # Extract transaction ID
        txn_id = data.get("activityId") or data.get("transactionId")
        if not txn_id:
            logger.debug("schwab_transaction_missing_id")
            return None

        # Parse transaction date
        txn_date = self._parse_date(data)
        if txn_date is None:
            logger.debug("schwab_transaction_missing_date", txn_id=str(txn_id))
            return None

        # Get transaction type and subtype
        schwab_type = data.get("type", "UNKNOWN")
        schwab_subtype = data.get("transactionSubType") or data.get("subType")

        transaction_type = self._map_transaction_type(schwab_type)
        subtype = self._map_subtype(schwab_type, schwab_subtype, data)

        # Parse amount
        amount = self._parse_decimal(data.get("netAmount", 0))

        # Parse settlement date
        settlement_date = self._parse_settlement_date(data)

        # Get transaction info and instrument details
        txn_info = data.get("transactionItem", {}) or {}
        instrument = txn_info.get("instrument", {}) or {}

        # Extract security details for trades
        symbol = instrument.get("symbol")
        security_name = instrument.get("description")
        asset_type = self._map_asset_type(instrument.get("assetType"))
        quantity = (
            self._parse_decimal(txn_info.get("amount"))
            if txn_info.get("amount")
            else None
        )
        unit_price = (
            self._parse_decimal(txn_info.get("price"))
            if txn_info.get("price")
            else None
        )
        commission = (
            self._parse_decimal(data.get("totalCommission"))
            if data.get("totalCommission")
            else None
        )

        # Get description
        description = data.get("description", "") or self._generate_description(
            transaction_type, subtype, symbol, amount
        )

        # Get status
        status = data.get("status", "EXECUTED")

        return ProviderTransactionData(
            provider_transaction_id=str(txn_id),
            transaction_type=transaction_type,
            subtype=subtype,
            amount=amount,
            currency="USD",  # Schwab transactions are in USD
            description=description,
            transaction_date=txn_date,
            status=status,
            settlement_date=settlement_date,
            symbol=symbol,
            security_name=security_name,
            asset_type=asset_type,
            quantity=quantity,
            unit_price=unit_price,
            commission=commission,
            raw_data=data,
        )

    def _map_transaction_type(self, schwab_type: str) -> str:
        """Map Schwab transaction type to Dashtam type.

        Args:
            schwab_type: Transaction type from Schwab API.

        Returns:
            Mapped transaction type string, defaults to "other".
        """
        normalized = schwab_type.upper().strip()
        return SCHWAB_TRANSACTION_TYPE_MAP.get(normalized, "other")

    def _map_subtype(
        self, schwab_type: str, schwab_subtype: str | None, data: dict[str, Any]
    ) -> str | None:
        """Map Schwab transaction subtype to Dashtam subtype.

        Uses multiple signals to determine the most accurate subtype:
        - Direct subtype mapping for trades
        - Amount sign for transfers (positive=in, negative=out)
        - Context for income types (dividend vs interest)

        Args:
            schwab_type: Transaction type from Schwab.
            schwab_subtype: Transaction subtype from Schwab (if any).
            data: Full transaction data for context.

        Returns:
            Mapped subtype string or None if not applicable.
        """
        normalized_type = schwab_type.upper().strip()

        # Trade subtypes
        if normalized_type in ("TRADE", "RECEIVE_AND_DELIVER"):
            if schwab_subtype:
                return SCHWAB_TRADE_SUBTYPE_MAP.get(
                    schwab_subtype.upper().strip(),
                    "buy",  # Default to buy
                )
            # Infer from amount if no subtype
            amount = data.get("netAmount", 0)
            return "sell" if amount > 0 else "buy"

        # Income subtypes
        if normalized_type in (
            "DIVIDEND_OR_INTEREST",
            "DIVIDEND",
            "INTEREST",
            "CAPITAL_GAINS",
        ):
            if "INTEREST" in normalized_type or (
                schwab_subtype and "INTEREST" in schwab_subtype.upper()
            ):
                return "interest"
            if "CAPITAL" in normalized_type or (
                schwab_subtype and "CAPITAL" in schwab_subtype.upper()
            ):
                return "capital_gain"
            return "dividend"

        # Transfer subtypes
        if normalized_type in (
            "ELECTRONIC_FUND",
            "ACH_RECEIPT",
            "ACH_DISBURSEMENT",
            "WIRE_IN",
            "WIRE_OUT",
            "CHECK",
            "JOURNAL",
            "INTERNAL_TRANSFER",
            "CASH_RECEIPT",
            "CASH_DISBURSEMENT",
        ):
            # Determine direction from type name or amount
            if "RECEIPT" in normalized_type or "IN" in normalized_type:
                return "deposit"
            if "DISBURSEMENT" in normalized_type or "OUT" in normalized_type:
                return "withdrawal"
            # Fall back to amount sign
            amount = data.get("netAmount", 0)
            if "WIRE" in normalized_type:
                return "wire_in" if amount > 0 else "wire_out"
            return "deposit" if amount > 0 else "withdrawal"

        # Fee subtypes
        if normalized_type in (
            "SERVICE_FEE",
            "MARGIN_INTEREST",
            "ADR_FEE",
            "FOREIGN_TAX_WITHHELD",
        ):
            if "MARGIN" in normalized_type:
                return "margin_interest"
            return "account_fee"

        # Dividend reinvestment is a special case - it's a buy
        if normalized_type == "DIVIDEND_REINVEST":
            return "buy"

        return None

    def _map_asset_type(self, schwab_asset_type: str | None) -> str | None:
        """Map Schwab asset type to Dashtam asset type.

        Args:
            schwab_asset_type: Asset type from Schwab API.

        Returns:
            Mapped asset type string or None.
        """
        if not schwab_asset_type:
            return None

        normalized = schwab_asset_type.upper().strip()
        return SCHWAB_ASSET_TYPE_MAP.get(normalized, "other")

    def _parse_date(self, data: dict[str, Any]) -> date | None:
        """Parse transaction date from Schwab data.

        Tries multiple date fields in order of preference.

        Args:
            data: Transaction data dict.

        Returns:
            Parsed date or None if no valid date found.
        """
        # Try multiple date fields
        date_fields = ["tradeDate", "transactionDate", "settlementDate", "time"]

        for field in date_fields:
            date_str = data.get(field)
            if date_str:
                try:
                    # Handle both date-only and datetime formats
                    return date.fromisoformat(str(date_str)[:10])
                except (ValueError, TypeError):
                    continue

        return None

    def _parse_settlement_date(self, data: dict[str, Any]) -> date | None:
        """Parse settlement date from Schwab data.

        Args:
            data: Transaction data dict.

        Returns:
            Parsed settlement date or None.
        """
        settle_date_str = data.get("settlementDate")
        if settle_date_str:
            try:
                return date.fromisoformat(str(settle_date_str)[:10])
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
                "schwab_invalid_decimal_value",
                value=value,
                value_type=type(value).__name__,
            )
            return Decimal("0")

    def _generate_description(
        self,
        transaction_type: str,
        subtype: str | None,
        symbol: str | None,
        amount: Decimal,
    ) -> str:
        """Generate a description when none is provided.

        Args:
            transaction_type: Mapped transaction type.
            subtype: Mapped subtype.
            symbol: Security symbol (if applicable).
            amount: Transaction amount.

        Returns:
            Generated description string.
        """
        parts = []

        if subtype:
            parts.append(subtype.replace("_", " ").title())
        else:
            parts.append(transaction_type.title())

        if symbol:
            parts.append(symbol)

        if amount:
            parts.append(f"${abs(amount):.2f}")

        return " ".join(parts) if parts else "Transaction"
