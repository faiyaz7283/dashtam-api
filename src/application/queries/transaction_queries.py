"""Transaction queries for CQRS read operations.

Queries represent requests for transaction data. They are immutable dataclasses
with question-like names that describe what information is being requested.

All transaction queries are account-scoped (multi-tenancy boundary) and include
user_id for ownership verification via Account->ProviderConnection chain.

Architecture:
- Queries are immutable (frozen dataclasses)
- NO business logic in queries (just data transfer)
- Handlers perform actual data retrieval and business rules
- NO domain events (queries are side-effect free)

Reference:
    - docs/architecture/cqrs-pattern.md
"""

from dataclasses import dataclass
from datetime import date
from uuid import UUID


@dataclass(frozen=True, kw_only=True)
class GetTransaction:
    """Query to retrieve a single transaction by ID.

    Requires ownership verification: Transaction->Account->ProviderConnection->User

    Attributes:
        transaction_id: Transaction unique identifier.
        user_id: User requesting the transaction (for ownership check).

    Example:
        >>> query = GetTransaction(
        ...     transaction_id=transaction_id,
        ...     user_id=current_user_id,
        ... )
        >>> result = await handler.handle(query)
    """

    transaction_id: UUID
    user_id: UUID


@dataclass(frozen=True, kw_only=True)
class ListTransactionsByAccount:
    """Query to list transactions for a specific account.

    Returns transactions ordered by transaction_date DESC (most recent first).
    Supports pagination and optional type filtering.

    Attributes:
        account_id: Account to retrieve transactions for.
        user_id: User requesting transactions (for ownership check).
        limit: Maximum number of transactions to return (default 50).
        offset: Number of transactions to skip for pagination (default 0).
        transaction_type: Optional filter by transaction type (e.g., "trade", "transfer").

    Example:
        >>> # Get first page of all transactions
        >>> query = ListTransactionsByAccount(
        ...     account_id=account_id,
        ...     user_id=current_user_id,
        ...     limit=50,
        ...     offset=0,
        ... )
        >>> # Get only trades
        >>> trades_query = ListTransactionsByAccount(
        ...     account_id=account_id,
        ...     user_id=current_user_id,
        ...     transaction_type="trade",
        ... )
    """

    account_id: UUID
    user_id: UUID
    limit: int = 50
    offset: int = 0
    transaction_type: str | None = None


@dataclass(frozen=True, kw_only=True)
class ListTransactionsByDateRange:
    """Query to list transactions within a date range.

    Queries by transaction_date (not created_at). Returns transactions
    ordered by transaction_date ASC (chronological).

    Useful for financial reports, tax documents, and historical analysis.

    Attributes:
        account_id: Account to retrieve transactions for.
        user_id: User requesting transactions (for ownership check).
        start_date: Start of date range (inclusive).
        end_date: End of date range (inclusive).

    Example:
        >>> # Get all transactions for 2024
        >>> query = ListTransactionsByDateRange(
        ...     account_id=account_id,
        ...     user_id=current_user_id,
        ...     start_date=date(2024, 1, 1),
        ...     end_date=date(2024, 12, 31),
        ... )
    """

    account_id: UUID
    user_id: UUID
    start_date: date
    end_date: date


@dataclass(frozen=True, kw_only=True)
class ListSecurityTransactions:
    """Query to list all transactions for a specific security/symbol.

    Returns TRADE transactions only (filters by symbol field).
    Ordered by transaction_date DESC (most recent first).

    Useful for cost basis calculation, P&L analysis, and trade history.

    Attributes:
        account_id: Account to retrieve transactions for.
        user_id: User requesting transactions (for ownership check).
        symbol: Security ticker symbol (e.g., "AAPL", "TSLA", "BTC-USD").
        limit: Maximum number of transactions to return (default 50).

    Example:
        >>> # Get all AAPL trades
        >>> query = ListSecurityTransactions(
        ...     account_id=account_id,
        ...     user_id=current_user_id,
        ...     symbol="AAPL",
        ...     limit=100,
        ... )
    """

    account_id: UUID
    user_id: UUID
    symbol: str
    limit: int = 50
