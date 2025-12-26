"""BalanceSnapshotRepository protocol for balance snapshot persistence.

Port (interface) for hexagonal architecture.
Infrastructure layer implements this protocol.

Reference:
    - docs/architecture/balance-tracking-architecture.md
"""

from datetime import datetime
from typing import Protocol
from uuid import UUID

from src.domain.entities.balance_snapshot import BalanceSnapshot
from src.domain.enums.snapshot_source import SnapshotSource


class BalanceSnapshotRepository(Protocol):
    """Balance snapshot repository protocol (port).

    Defines the interface for balance snapshot persistence operations.
    Infrastructure layer provides concrete implementation.

    This is a Protocol (not ABC) for structural typing.
    Implementations don't need to inherit from this.

    Methods:
        find_by_id: Retrieve snapshot by ID
        find_by_account_id: Retrieve all snapshots for an account
        find_by_account_id_in_range: Retrieve snapshots within date range
        find_latest_by_account_id: Get most recent snapshot for account
        find_by_user_id_in_range: Retrieve snapshots across all user accounts
        save: Create snapshot (no update - immutable)
        delete: Remove snapshot

    Example Implementation:
        >>> class PostgresBalanceSnapshotRepository:
        ...     async def find_by_id(self, id: UUID) -> BalanceSnapshot | None:
        ...         # Database logic here
        ...         pass
    """

    async def find_by_id(self, snapshot_id: UUID) -> BalanceSnapshot | None:
        """Find snapshot by ID.

        Args:
            snapshot_id: Snapshot's unique identifier.

        Returns:
            BalanceSnapshot if found, None otherwise.

        Example:
            >>> snapshot = await repo.find_by_id(snapshot_id)
            >>> if snapshot:
            ...     print(snapshot.balance)
        """
        ...

    async def find_by_account_id(
        self,
        account_id: UUID,
        source: SnapshotSource | None = None,
        limit: int | None = None,
    ) -> list[BalanceSnapshot]:
        """Find all snapshots for an account.

        Results are ordered by captured_at descending (most recent first).

        Args:
            account_id: Account's unique identifier.
            source: Optional filter by snapshot source.
            limit: Optional maximum number of results.

        Returns:
            List of snapshots (empty if none found).

        Example:
            >>> snapshots = await repo.find_by_account_id(account_id, limit=30)
            >>> for s in snapshots:
            ...     print(f"{s.captured_at}: {s.balance}")
        """
        ...

    async def find_by_account_id_in_range(
        self,
        account_id: UUID,
        start_date: datetime,
        end_date: datetime,
        source: SnapshotSource | None = None,
    ) -> list[BalanceSnapshot]:
        """Find snapshots for an account within date range.

        Results are ordered by captured_at ascending (oldest first) for charting.

        Args:
            account_id: Account's unique identifier.
            start_date: Start of date range (inclusive).
            end_date: End of date range (inclusive).
            source: Optional filter by snapshot source.

        Returns:
            List of snapshots within range (empty if none found).

        Example:
            >>> from datetime import datetime, timedelta
            >>> end = datetime.now(UTC)
            >>> start = end - timedelta(days=30)
            >>> snapshots = await repo.find_by_account_id_in_range(
            ...     account_id, start, end
            ... )
        """
        ...

    async def find_latest_by_account_id(
        self,
        account_id: UUID,
    ) -> BalanceSnapshot | None:
        """Find most recent snapshot for an account.

        Args:
            account_id: Account's unique identifier.

        Returns:
            Most recent BalanceSnapshot if found, None otherwise.

        Example:
            >>> latest = await repo.find_latest_by_account_id(account_id)
            >>> if latest:
            ...     print(f"Current balance: {latest.balance}")
        """
        ...

    async def find_by_user_id_in_range(
        self,
        user_id: UUID,
        start_date: datetime,
        end_date: datetime,
        source: SnapshotSource | None = None,
    ) -> list[BalanceSnapshot]:
        """Find snapshots across all accounts for a user within date range.

        Aggregates snapshots from all user's accounts.
        Results are ordered by captured_at ascending.

        Args:
            user_id: User's unique identifier.
            start_date: Start of date range (inclusive).
            end_date: End of date range (inclusive).
            source: Optional filter by snapshot source.

        Returns:
            List of snapshots across all accounts (empty if none found).

        Note:
            This requires joining through account → connection → user.

        Example:
            >>> snapshots = await repo.find_by_user_id_in_range(
            ...     user_id, start, end
            ... )
            >>> # Group by account for portfolio breakdown
        """
        ...

    async def find_latest_by_user_id(
        self,
        user_id: UUID,
    ) -> list[BalanceSnapshot]:
        """Find most recent snapshot for each of user's accounts.

        Returns one snapshot per account (the latest for each).
        Useful for current portfolio summary.

        Args:
            user_id: User's unique identifier.

        Returns:
            List of latest snapshots, one per account.

        Example:
            >>> latest_snapshots = await repo.find_latest_by_user_id(user_id)
            >>> total = sum(s.balance.amount for s in latest_snapshots)
        """
        ...

    async def save(self, snapshot: BalanceSnapshot) -> None:
        """Create snapshot in database.

        Snapshots are immutable - this only creates, never updates.
        Use delete() to remove incorrect snapshots.

        Args:
            snapshot: BalanceSnapshot entity to persist.

        Raises:
            DatabaseError: If database operation fails.
            IntegrityError: If snapshot ID already exists.

        Example:
            >>> snapshot = BalanceSnapshot(...)
            >>> await repo.save(snapshot)
        """
        ...

    async def delete(self, snapshot_id: UUID) -> None:
        """Remove snapshot from database.

        Hard delete - permanently removes the record.
        Used to remove erroneous snapshots.

        Args:
            snapshot_id: Snapshot's unique identifier.

        Raises:
            NotFoundError: If snapshot doesn't exist.
            DatabaseError: If database operation fails.

        Note:
            Use with caution - deleting snapshots breaks historical continuity.

        Example:
            >>> await repo.delete(snapshot_id)
        """
        ...

    async def count_by_account_id(self, account_id: UUID) -> int:
        """Count total snapshots for an account.

        Args:
            account_id: Account's unique identifier.

        Returns:
            Total number of snapshots.

        Example:
            >>> count = await repo.count_by_account_id(account_id)
            >>> print(f"Account has {count} balance snapshots")
        """
        ...
