"""Asset type enumeration.

This module defines the security/asset classification for transactions.
Only populated for TRADE transactions.
"""

from enum import Enum


class AssetType(str, Enum):
    """Type of security/asset involved in transaction.

    Only populated for TRADE transactions. Captures what KIND of
    instrument was traded, separate from the action (buy/sell).

    This allows the same BUY subtype to work for:
    - Stocks: BUY + EQUITY
    - Options: BUY + OPTION (with option_type for call/put)
    - ETFs: BUY + ETF
    - Mutual Funds: BUY + MUTUAL_FUND
    - Bonds: BUY + FIXED_INCOME
    - Crypto: BUY + CRYPTOCURRENCY

    Examples:
        >>> # Stock purchase
        >>> asset_type = AssetType.EQUITY
        >>> # Option purchase
        >>> asset_type = AssetType.OPTION
        >>> # ETF purchase
        >>> asset_type = AssetType.ETF
    """

    EQUITY = "equity"  # Stocks (common, preferred)
    ETF = "etf"  # Exchange-traded funds
    OPTION = "option"  # Options contracts
    MUTUAL_FUND = "mutual_fund"  # Mutual funds
    FIXED_INCOME = "fixed_income"  # Bonds, CDs, treasuries
    FUTURES = "futures"  # Futures contracts
    CRYPTOCURRENCY = "cryptocurrency"  # Crypto assets
    CASH_EQUIVALENT = "cash_equivalent"  # Money market, etc.
    OTHER = "other"  # Unknown/other
