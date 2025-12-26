"""Provider category classification.

Defines the type of financial provider (brokerage, bank, credit card, etc.).
Used to determine applicable features and entities for each provider.

Reference:
    - docs/architecture/provider-domain-model.md
"""

from enum import Enum


class ProviderCategory(str, Enum):
    """Financial provider category classification.

    Determines the type of financial institution. Different categories
    have different features - brokerages have holdings, banks have
    pending transactions, etc.

    Examples:
        >>> category = ProviderCategory.BROKERAGE
        >>> category.value
        'brokerage'
    """

    BROKERAGE = "brokerage"
    """Brokerage/investment provider (Schwab, Fidelity, TD Ameritrade)."""

    BANK = "bank"
    """Traditional banking provider (Chase, Bank of America, Wells Fargo)."""

    CREDIT_CARD = "credit_card"
    """Credit card provider (American Express, Discover, Capital One)."""

    LOAN = "loan"
    """Loan provider (mortgages, auto loans, personal loans)."""

    CRYPTO = "crypto"
    """Cryptocurrency exchange (Coinbase, Kraken, Binance)."""

    AGGREGATOR = "aggregator"
    """Data aggregator connecting multiple institutions (Plaid, MX, Yodlee)."""

    OTHER = "other"
    """Uncategorized provider type."""

    @classmethod
    def values(cls) -> list[str]:
        """Get all category values as strings.

        Returns:
            List of category string values.
        """
        return [category.value for category in cls]

    @classmethod
    def is_valid(cls, value: str) -> bool:
        """Check if a string is a valid provider category.

        Args:
            value: String to check.

        Returns:
            True if value is a valid category.
        """
        return value in cls.values()

    def supports_holdings(self) -> bool:
        """Check if this category typically supports holdings/positions.

        Returns:
            True if providers of this category have holdings.
        """
        return self in (ProviderCategory.BROKERAGE, ProviderCategory.CRYPTO)
