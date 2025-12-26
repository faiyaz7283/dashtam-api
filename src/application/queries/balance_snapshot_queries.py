"""Balance snapshot queries (CQRS read operations).

Queries represent requests for balance snapshot data. They are immutable
dataclasses with question-like names. Queries NEVER change state.

Pattern:
- Queries are data containers (no logic)
- Handlers fetch and return data
- Queries never change state
- Queries do NOT emit domain events

Reference:
    - docs/architecture/cqrs-pattern.md
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, kw_only=True)
class GetBalanceHistory:
    """Get balance history for an account within a date range.

    Used for portfolio charting and performance tracking.
    Returns snapshots ordered by captured_at ascending (oldest first).

    Attributes:
        account_id: Account whose balance history to retrieve.
        user_id: User requesting (for ownership verification).
        start_date: Start of date range (inclusive).
        end_date: End of date range (inclusive).
        source: Optional filter by snapshot source.

    Example:
        >>> query = GetBalanceHistory(
        ...     account_id=account_id,
        ...     user_id=user_id,
        ...     start_date=datetime(2024, 1, 1),
        ...     end_date=datetime(2024, 12, 31),
        ... )
        >>> result = await handler.handle(query)
    """

    account_id: UUID
    user_id: UUID
    start_date: datetime
    end_date: datetime
    source: str | None = None


@dataclass(frozen=True, kw_only=True)
class GetLatestBalanceSnapshots:
    """Get the most recent balance snapshot for each of user's accounts.

    Used for portfolio summary/dashboard view.
    Returns one snapshot per account (the latest for each).

    Attributes:
        user_id: User whose portfolio summary to retrieve.

    Example:
        >>> query = GetLatestBalanceSnapshots(user_id=user_id)
        >>> result = await handler.handle(query)
        >>> total = sum(s.balance for s in result.snapshots)
    """

    user_id: UUID


@dataclass(frozen=True, kw_only=True)
class ListBalanceSnapshotsByAccount:
    """List balance snapshots for a specific account.

    Returns snapshots ordered by captured_at descending (most recent first).
    Optionally limited to N most recent snapshots.

    Attributes:
        account_id: Account whose snapshots to list.
        user_id: User requesting (for ownership verification).
        limit: Optional maximum number of snapshots to return.
        source: Optional filter by snapshot source.

    Example:
        >>> query = ListBalanceSnapshotsByAccount(
        ...     account_id=account_id,
        ...     user_id=user_id,
        ...     limit=30,
        ... )
        >>> result = await handler.handle(query)
    """

    account_id: UUID
    user_id: UUID
    limit: int | None = None
    source: str | None = None


@dataclass(frozen=True, kw_only=True)
class GetUserBalanceHistory:
    """Get aggregate balance history across all user accounts.

    Used for total portfolio value charting over time.
    Returns snapshots from all accounts within date range.

    Attributes:
        user_id: User whose portfolio history to retrieve.
        start_date: Start of date range (inclusive).
        end_date: End of date range (inclusive).
        source: Optional filter by snapshot source.

    Example:
        >>> query = GetUserBalanceHistory(
        ...     user_id=user_id,
        ...     start_date=datetime(2024, 1, 1),
        ...     end_date=datetime(2024, 12, 31),
        ... )
        >>> result = await handler.handle(query)
    """

    user_id: UUID
    start_date: datetime
    end_date: datetime
    source: str | None = None
