"""Snapshot source enumeration.

Defines the source/trigger of a balance snapshot capture.

Architecture:
    - Domain layer enum (no infrastructure dependencies)
    - Used in BalanceSnapshot entity to track origin
    - Enables analytics by source type

Reference:
    - docs/architecture/balance-tracking-architecture.md

Usage:
    from src.domain.enums import SnapshotSource

    snapshot = BalanceSnapshot(
        source=SnapshotSource.MANUAL_SYNC,
        ...
    )
"""

from enum import StrEnum


class SnapshotSource(StrEnum):
    """Source/trigger of a balance snapshot.

    Tracks how/why a balance snapshot was captured.
    Enables filtering and analytics by capture method.

    Values:
        ACCOUNT_SYNC: Captured during account data sync.
        HOLDINGS_SYNC: Captured during holdings sync operation.
        MANUAL_SYNC: User-initiated sync request.
        SCHEDULED_SYNC: Automated background sync job.
        INITIAL_CONNECTION: First sync after provider connection.

    Example:
        >>> snapshot.source == SnapshotSource.MANUAL_SYNC
        True
    """

    ACCOUNT_SYNC = "account_sync"
    """Captured during account data sync."""

    HOLDINGS_SYNC = "holdings_sync"
    """Captured during holdings sync operation."""

    MANUAL_SYNC = "manual_sync"
    """User-initiated sync request."""

    SCHEDULED_SYNC = "scheduled_sync"
    """Automated background sync job."""

    INITIAL_CONNECTION = "initial_connection"
    """First sync after provider connection."""

    # -------------------------------------------------------------------------
    # Query Methods
    # -------------------------------------------------------------------------

    def is_automated(self) -> bool:
        """Check if snapshot was captured automatically.

        Returns:
            True if source is automated (scheduled or sync operations).
        """
        return self in {
            SnapshotSource.ACCOUNT_SYNC,
            SnapshotSource.HOLDINGS_SYNC,
            SnapshotSource.SCHEDULED_SYNC,
        }

    def is_user_initiated(self) -> bool:
        """Check if snapshot was triggered by user action.

        Returns:
            True if source is user-initiated.
        """
        return self in {
            SnapshotSource.MANUAL_SYNC,
            SnapshotSource.INITIAL_CONNECTION,
        }
