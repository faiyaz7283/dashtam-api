"""Transaction type enumeration.

This module defines the high-level transaction type classification.
Part of the two-level classification system (Type + Subtype).
"""

from enum import Enum


class TransactionType(str, Enum):
    """High-level transaction category (normalized across providers).

    We use simplified, normalized types rather than provider-specific ones.
    This allows consistent behavior across different providers while
    the subtype field captures the specific action.

    Provider Mapping Examples
    -------------------------
    Schwab TRADE -> TRADE
    Schwab ACH_RECEIPT -> TRANSFER
    Schwab DIVIDEND_OR_INTEREST -> INCOME
    Chase buy/sell -> TRADE
    Chase dividend -> INCOME
    """

    # Security transactions (executed trades)
    TRADE = "trade"  # Buy/sell/short/cover of any security

    # Cash movements
    TRANSFER = "transfer"  # Deposits, withdrawals, ACH, wire, etc.

    # Income (passive)
    INCOME = "income"  # Dividends, interest, distributions

    # Fees and charges
    FEE = "fee"  # Account fees, commissions, other charges

    # Other/Administrative
    OTHER = "other"  # Journal entries, adjustments, uncategorized

    @classmethod
    def security_related(cls) -> list["TransactionType"]:
        """Return types that may involve securities.

        Returns:
            List of transaction types that can involve securities.
            INCOME is included because dividends are tied to securities.

        Examples:
            >>> TransactionType.security_related()
            [TransactionType.TRADE, TransactionType.INCOME]
        """
        return [cls.TRADE, cls.INCOME]
