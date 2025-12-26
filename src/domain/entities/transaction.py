"""Transaction domain entity.

Represents a historical financial activity record (trade, deposit, withdrawal, etc.).
"""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from src.domain.enums.asset_type import AssetType
from src.domain.enums.transaction_status import TransactionStatus
from src.domain.enums.transaction_subtype import TransactionSubtype
from src.domain.enums.transaction_type import TransactionType
from src.domain.value_objects.money import Money


@dataclass(frozen=True, kw_only=True)
class Transaction:
    """Financial transaction entity.

    Represents a **historical financial activity record** that has occurred in
    an account. Transactions are immutable - once created, they cannot be
    modified (only synced from provider updates).

    **Scope**: This entity represents PAST ACTIVITY ONLY. It does NOT include:
    - Holdings/Positions (current securities held)
    - Orders (pending instructions to buy/sell)
    - Watchlists
    - Market data

    **Design Principles**:
    - Immutable: No update methods, historical records don't change
    - Provider-agnostic: Two-level classification (type + subtype)
    - Secure: Trade transactions require security details (symbol, quantity, etc.)
    - Traceable: provider_transaction_id enables deduplication

    **Lifecycle**:
        1. Provider sync creates Transaction (status=PENDING or SETTLED)
        2. Stored in repository via save() or save_many()
        3. Status may update from PENDING → SETTLED via re-sync
        4. Never deleted (audit trail), only marked as CANCELLED if voided

    Attributes:
        id: Unique transaction identifier.
        account_id: Account this transaction belongs to.
        provider_transaction_id: Provider's unique ID for this transaction.
        transaction_type: High-level category (TRADE, TRANSFER, INCOME, FEE, OTHER).
        subtype: Specific action within type (BUY, SELL, DEPOSIT, etc.).
        status: Lifecycle state (PENDING, SETTLED, FAILED, CANCELLED).
        amount: Transaction amount (positive=credit, negative=debit).
        description: Human-readable transaction description.
        asset_type: Type of security (required for TRADE transactions).
        symbol: Security ticker/symbol (e.g., "AAPL", "BTC-USD").
        security_name: Full security name (e.g., "Apple Inc.").
        quantity: Number of shares/units (required for TRADE transactions).
        unit_price: Price per share/unit (required for TRADE transactions).
        commission: Trading commission/fee (if applicable).
        transaction_date: Date transaction occurred (from provider).
        settlement_date: Date funds/securities settled (T+0 to T+2).
        provider_metadata: Raw provider response data (for debugging/future use).
        created_at: Timestamp when transaction was first synced.
        updated_at: Timestamp of last sync update.

    Example:
        >>> from uuid_extensions import uuid7
        >>> # Stock purchase
        >>> transaction = Transaction(
        ...     id=uuid7(),
        ...     account_id=account_id,
        ...     provider_transaction_id="schwab-12345",
        ...     transaction_type=TransactionType.TRADE,
        ...     subtype=TransactionSubtype.BUY,
        ...     status=TransactionStatus.SETTLED,
        ...     amount=Money(amount=Decimal("-1050.00"), currency="USD"),
        ...     description="Bought 10 shares of AAPL",
        ...     asset_type=AssetType.EQUITY,
        ...     symbol="AAPL",
        ...     security_name="Apple Inc.",
        ...     quantity=Decimal("10"),
        ...     unit_price=Money(amount=Decimal("105.00"), currency="USD"),
        ...     commission=Money(amount=Decimal("0.00"), currency="USD"),
        ...     transaction_date=date(2025, 11, 28),
        ...     settlement_date=date(2025, 11, 30),
        ...     created_at=datetime.now(UTC),
        ...     updated_at=datetime.now(UTC),
        ... )
        >>> assert transaction.is_trade()
        >>> assert transaction.is_debit()
        >>> assert transaction.has_security_details()
    """

    # ========================================================================
    # Core Identifiers
    # ========================================================================

    id: UUID
    """Unique transaction identifier."""

    account_id: UUID
    """Account this transaction belongs to."""

    provider_transaction_id: str
    """Provider's unique ID for this transaction.

    Used for deduplication during sync operations. Format varies by provider:
    - Schwab: Numeric ID (e.g., "123456789")
    - Chase: Alphanumeric (e.g., "CHK-ABC123...")
    """

    # ========================================================================
    # Classification
    # ========================================================================

    transaction_type: TransactionType
    """High-level category (TRADE, TRANSFER, INCOME, FEE, OTHER)."""

    subtype: TransactionSubtype
    """Specific action within type (BUY, SELL, DEPOSIT, DIVIDEND, etc.)."""

    status: TransactionStatus
    """Lifecycle state (PENDING, SETTLED, FAILED, CANCELLED)."""

    # ========================================================================
    # Financial Details
    # ========================================================================

    amount: Money
    """Transaction amount.

    Convention:
    - Positive: Credit to account (deposits, income, sales)
    - Negative: Debit from account (withdrawals, purchases, fees)

    For TRADE transactions:
    - BUY: Negative amount (cash out)
    - SELL: Positive amount (cash in)
    - SHORT_SELL: Positive amount (proceeds received)
    - BUY_TO_COVER: Negative amount (covering short)
    """

    description: str
    """Human-readable transaction description from provider."""

    # ========================================================================
    # Security Details (TRADE transactions only)
    # ========================================================================

    asset_type: AssetType | None = None
    """Type of security (EQUITY, OPTION, ETF, etc.).

    Required for TRADE transactions, None for non-trade transactions.
    """

    symbol: str | None = None
    """Security ticker symbol (e.g., "AAPL", "TSLA", "BTC-USD").

    Required for TRADE transactions, None for non-trade transactions.
    Format varies by asset type:
    - Stocks/ETFs: Exchange ticker (e.g., "AAPL")
    - Options: OCC format (e.g., "AAPL250117C00150000")
    - Crypto: Pair format (e.g., "BTC-USD")
    """

    security_name: str | None = None
    """Full security name (e.g., "Apple Inc.", "Bitcoin USD").

    Optional but recommended for TRADE transactions.
    """

    quantity: Decimal | None = None
    """Number of shares/units traded.

    Required for TRADE transactions, None for non-trade transactions.
    - Stocks/ETFs: Whole or fractional shares (e.g., 10.5)
    - Options: Contracts (e.g., 2)
    - Crypto: Fractional units (e.g., 0.00123456)

    Precision: Up to 8 decimal places.
    """

    unit_price: Money | None = None
    """Price per share/unit.

    Required for TRADE transactions, None for non-trade transactions.
    - Stocks/ETFs: Price per share
    - Options: Price per contract
    - Crypto: Price per coin/token
    """

    commission: Money | None = None
    """Trading commission/fee charged by broker.

    Optional for TRADE transactions, None for non-trade transactions.
    Many modern brokers charge $0 commission.
    """

    # ========================================================================
    # Dates
    # ========================================================================

    transaction_date: date
    """Date the transaction occurred (from provider).

    This is the "as-of" date for the transaction, not when we synced it.
    """

    settlement_date: date | None = None
    """Date funds/securities settled.

    Settlement periods vary:
    - Stocks/ETFs: T+2 (2 business days after transaction_date)
    - Options: T+1
    - Cash transfers: T+0 to T+3 (depends on method)

    None for transactions that don't settle (e.g., adjustments).
    """

    # ========================================================================
    # Metadata
    # ========================================================================

    provider_metadata: dict[str, Any] | None = None
    """Raw provider response data.

    Preserves the original provider API response for:
    - Debugging sync issues
    - Future feature additions (without re-sync)
    - Audit trail of provider data

    Example (Schwab):
        {
            "activityId": 123456789,
            "type": "TRADE",
            "status": "EXECUTED",
            "subAccount": "MARGIN",
            ...
        }
    """

    # ========================================================================
    # Timestamps
    # ========================================================================

    created_at: datetime
    """Timestamp when transaction was first synced from provider."""

    updated_at: datetime
    """Timestamp of last sync update from provider."""

    # ========================================================================
    # Query Methods
    # ========================================================================

    def is_trade(self) -> bool:
        """Check if this is a trade transaction.

        Returns:
            True if transaction_type is TRADE.

        Example:
            >>> if transaction.is_trade():
            ...     print(f"Traded {transaction.quantity} shares of {transaction.symbol}")
        """
        return self.transaction_type == TransactionType.TRADE

    def is_transfer(self) -> bool:
        """Check if this is a transfer transaction.

        Returns:
            True if transaction_type is TRANSFER.

        Example:
            >>> if transaction.is_transfer():
            ...     print(f"Transfer: {transaction.description}")
        """
        return self.transaction_type == TransactionType.TRANSFER

    def is_income(self) -> bool:
        """Check if this is an income transaction.

        Returns:
            True if transaction_type is INCOME.

        Example:
            >>> if transaction.is_income():
            ...     print(f"Income: {transaction.amount}")
        """
        return self.transaction_type == TransactionType.INCOME

    def is_fee(self) -> bool:
        """Check if this is a fee transaction.

        Returns:
            True if transaction_type is FEE.

        Example:
            >>> if transaction.is_fee():
            ...     print(f"Fee charged: {transaction.amount}")
        """
        return self.transaction_type == TransactionType.FEE

    def is_debit(self) -> bool:
        """Check if this transaction debits the account.

        Returns:
            True if amount is negative (money leaving account).

        Example:
            >>> if transaction.is_debit():
            ...     print("Cash out of account")
        """
        return self.amount.amount < 0

    def is_credit(self) -> bool:
        """Check if this transaction credits the account.

        Returns:
            True if amount is positive (money entering account).

        Example:
            >>> if transaction.is_credit():
            ...     print("Cash into account")
        """
        return self.amount.amount > 0

    def is_settled(self) -> bool:
        """Check if this transaction has settled.

        Returns:
            True if status is SETTLED.

        Example:
            >>> if transaction.is_settled():
            ...     # Include in balance calculations
        """
        return self.status == TransactionStatus.SETTLED

    def has_security_details(self) -> bool:
        """Check if this transaction has security-related fields populated.

        Returns:
            True if symbol, quantity, and unit_price are all present.

        Example:
            >>> if transaction.has_security_details():
            ...     cost_basis = transaction.quantity * transaction.unit_price.amount
        """
        return (
            self.symbol is not None
            and self.quantity is not None
            and self.unit_price is not None
        )
