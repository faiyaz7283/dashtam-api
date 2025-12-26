"""BalanceSnapshot domain entity.

Represents a point-in-time capture of account balance for historical tracking.
Balance snapshots are created during sync operations to build balance history.

Architecture:
    - Pure domain entity (no infrastructure dependencies)
    - Immutable after creation (no update methods)
    - Created during account/holdings sync operations
    - NO domain events (simple data capture)

Reference:
    - docs/architecture/balance-tracking-architecture.md

Usage:
    from uuid_extensions import uuid7
    from src.domain.entities import BalanceSnapshot
    from src.domain.enums import SnapshotSource
    from src.domain.value_objects import Money
    from decimal import Decimal

    snapshot = BalanceSnapshot(
        id=uuid7(),
        account_id=account.id,
        balance=Money(Decimal("10000.00"), "USD"),
        available_balance=Money(Decimal("9500.00"), "USD"),
        holdings_value=Money(Decimal("8500.00"), "USD"),
        cash_value=Money(Decimal("1500.00"), "USD"),
        currency="USD",
        source=SnapshotSource.ACCOUNT_SYNC,
    )
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from src.domain.enums.snapshot_source import SnapshotSource
from src.domain.errors.balance_snapshot_error import BalanceSnapshotError
from src.domain.value_objects.money import Money


@dataclass(frozen=True)
class BalanceSnapshot:
    """Point-in-time balance capture for historical tracking.

    Immutable record of account balance at a specific moment.
    Used for:
    - Portfolio value tracking over time
    - Performance calculations (daily/weekly/monthly gains)
    - Historical balance charts
    - Trend analysis

    Immutability:
        Snapshots are frozen (immutable) once created. Historical records
        should never be modified. If a correction is needed, create a new
        snapshot with corrected values.

    Capture Timing:
        Snapshots are created during sync operations. The captured_at
        timestamp reflects when the sync occurred, not when the provider
        reported the balance.

    Value Breakdown:
        - balance: Total account balance (market value)
        - available_balance: Available for trading/withdrawal
        - holdings_value: Total value of securities positions
        - cash_value: Cash/sweep balance

    Attributes:
        id: Unique snapshot identifier.
        account_id: FK to Account this snapshot belongs to.
        balance: Total account balance at capture time.
        available_balance: Available balance if different (pending, etc.).
        holdings_value: Total market value of holdings/positions.
        cash_value: Cash/money market balance.
        currency: ISO 4217 currency code.
        source: How/why snapshot was captured.
        provider_metadata: Additional provider data at capture time.
        captured_at: Timestamp when balance was captured.
        created_at: Record creation timestamp.

    Example:
        >>> snapshot = BalanceSnapshot(
        ...     id=uuid7(),
        ...     account_id=account.id,
        ...     balance=Money(Decimal("10000.00"), "USD"),
        ...     currency="USD",
        ...     source=SnapshotSource.ACCOUNT_SYNC,
        ... )
        >>> snapshot.balance.amount
        Decimal('10000.00')
    """

    # =========================================================================
    # Required Fields
    # =========================================================================

    id: UUID
    """Unique snapshot identifier."""

    account_id: UUID
    """FK to Account this snapshot belongs to."""

    balance: Money
    """Total account balance at capture time.

    This is the primary value tracked for portfolio analytics.
    """

    currency: str
    """ISO 4217 currency code (e.g., "USD").

    Must match account currency and all Money value currencies.
    """

    source: SnapshotSource
    """How/why this snapshot was captured.

    Enables filtering by capture method (manual vs automated).
    """

    # =========================================================================
    # Optional Value Breakdown
    # =========================================================================

    available_balance: Money | None = None
    """Available balance if different from total.

    May differ due to pending transactions, margin requirements, etc.
    """

    holdings_value: Money | None = None
    """Total market value of securities positions.

    Sum of all holding market values at capture time.
    """

    cash_value: Money | None = None
    """Cash/money market balance.

    Cash available in the account, typically:
    balance = holdings_value + cash_value
    """

    # =========================================================================
    # Metadata
    # =========================================================================

    provider_metadata: dict[str, Any] | None = field(
        default=None,
        hash=False,  # Exclude from hash (mutable type in frozen dataclass)
    )
    """Additional provider data at capture time.

    Preserves provider-specific balance details for:
    - Debugging sync issues
    - Future feature additions
    - Audit trail
    """

    # =========================================================================
    # Timestamps
    # =========================================================================

    captured_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    """Timestamp when balance was captured.

    This is the "as of" time for the balance values.
    """

    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    """Record creation timestamp."""

    # =========================================================================
    # Validation
    # =========================================================================

    def __post_init__(self) -> None:
        """Validate snapshot after initialization.

        Raises:
            ValueError: If required fields are invalid or currencies mismatch.

        Note:
            __post_init__ raises ValueError for construction errors.
            These are programming errors, not business logic failures.
        """
        # Validate currency format
        if not self.currency or len(self.currency) != 3:
            raise ValueError(BalanceSnapshotError.INVALID_CURRENCY)

        # Normalize currency to uppercase (work around frozen)
        if self.currency != self.currency.upper():
            object.__setattr__(self, "currency", self.currency.upper())

        # Validate balance currency matches
        if self.balance.currency != self.currency.upper():
            raise ValueError(
                f"Balance currency ({self.balance.currency}) must match "
                f"snapshot currency ({self.currency})"
            )

        # Validate optional Money fields currency consistency
        if (
            self.available_balance is not None
            and self.available_balance.currency != self.currency.upper()
        ):
            raise ValueError(
                f"Available balance currency ({self.available_balance.currency}) "
                f"must match snapshot currency ({self.currency})"
            )

        if (
            self.holdings_value is not None
            and self.holdings_value.currency != self.currency.upper()
        ):
            raise ValueError(
                f"Holdings value currency ({self.holdings_value.currency}) "
                f"must match snapshot currency ({self.currency})"
            )

        if (
            self.cash_value is not None
            and self.cash_value.currency != self.currency.upper()
        ):
            raise ValueError(
                f"Cash value currency ({self.cash_value.currency}) "
                f"must match snapshot currency ({self.currency})"
            )

    # =========================================================================
    # Query Methods (Read-Only)
    # =========================================================================

    def has_value_breakdown(self) -> bool:
        """Check if snapshot has holdings/cash value breakdown.

        Returns:
            True if both holdings_value and cash_value are present.

        Example:
            >>> snapshot.has_value_breakdown()
            True  # If holdings_value and cash_value are set
        """
        return self.holdings_value is not None and self.cash_value is not None

    def get_holdings_percentage(self) -> float | None:
        """Calculate percentage of portfolio in holdings.

        Returns:
            Percentage as float (0-100), or None if breakdown unavailable
            or balance is zero.

        Example:
            >>> snapshot.get_holdings_percentage()
            85.0  # 85% of portfolio in securities
        """
        if not self.has_value_breakdown() or self.balance.amount == 0:
            return None

        # holdings_value is guaranteed non-None after has_value_breakdown check
        assert self.holdings_value is not None  # noqa: S101
        return float((self.holdings_value.amount / self.balance.amount) * 100)

    def get_cash_percentage(self) -> float | None:
        """Calculate percentage of portfolio in cash.

        Returns:
            Percentage as float (0-100), or None if breakdown unavailable
            or balance is zero.

        Example:
            >>> snapshot.get_cash_percentage()
            15.0  # 15% of portfolio in cash
        """
        if not self.has_value_breakdown() or self.balance.amount == 0:
            return None

        # cash_value is guaranteed non-None after has_value_breakdown check
        assert self.cash_value is not None  # noqa: S101
        return float((self.cash_value.amount / self.balance.amount) * 100)

    def is_automated_capture(self) -> bool:
        """Check if snapshot was captured automatically.

        Returns:
            True if source is an automated sync operation.

        Example:
            >>> snapshot.source = SnapshotSource.SCHEDULED_SYNC
            >>> snapshot.is_automated_capture()
            True
        """
        return self.source.is_automated()

    def is_user_initiated_capture(self) -> bool:
        """Check if snapshot was triggered by user.

        Returns:
            True if source is user-initiated.

        Example:
            >>> snapshot.source = SnapshotSource.MANUAL_SYNC
            >>> snapshot.is_user_initiated_capture()
            True
        """
        return self.source.is_user_initiated()

    def calculate_change_from(
        self, previous: "BalanceSnapshot"
    ) -> tuple[Money, float] | None:
        """Calculate absolute and percentage change from previous snapshot.

        Args:
            previous: Earlier snapshot to compare against.

        Returns:
            Tuple of (change_amount, change_percent), or None if currencies differ.

        Example:
            >>> change, percent = current.calculate_change_from(previous)
            >>> print(f"Change: {change.amount} ({percent:.2f}%)")
            Change: 500.00 (5.26%)
        """
        if self.currency != previous.currency:
            return None

        change_amount = self.balance - previous.balance
        if previous.balance.amount == 0:
            change_percent = 0.0 if self.balance.amount == 0 else float("inf")
        else:
            change_percent = float(
                (change_amount.amount / previous.balance.amount) * 100
            )

        return change_amount, change_percent
