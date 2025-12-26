"""BalanceSnapshot database model.

This module defines the BalanceSnapshot model for storing historical
balance captures for portfolio tracking and analytics.

Architecture:
    - Snapshots belong to accounts (FK relationship with CASCADE delete)
    - Balance fields: balance, available_balance, holdings_value, cash_value
    - All amounts stored as Decimal with separate currency column
    - Source stored as lowercase string (mapped to SnapshotSource enum)
    - Provider metadata stored as JSONB for flexibility
    - Immutable records (no update operations)

Reference:
    - docs/architecture/balance-tracking-architecture.md
    - src/domain/entities/balance_snapshot.py
"""

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.persistence.base import BaseModel


class BalanceSnapshot(BaseModel):
    """BalanceSnapshot model for historical balance tracking.

    Represents a point-in-time capture of account balance for historical
    tracking and portfolio analytics. Snapshots are immutable once created.

    Fields:
        id: UUID primary key (from BaseImmutableModel)
        created_at: Timestamp when created (from BaseImmutableModel)
        account_id: FK to accounts table
        balance_amount: Total account balance at capture time
        currency: ISO 4217 currency code
        source: How/why snapshot was captured (account_sync, manual_sync, etc.)
        available_balance_amount: Available balance if different (nullable)
        holdings_value_amount: Total market value of holdings (nullable)
        cash_value_amount: Cash/money market balance (nullable)
        captured_at: Timestamp when balance was captured
        provider_metadata: Provider-specific data at capture time (JSONB)

    Indexes:
        - ix_balance_snapshots_account_id: FK lookup
        - ix_balance_snapshots_captured_at: Time-based queries
        - ix_balance_snapshots_source: Filter by source
        - idx_balance_snapshots_account_time: Composite for time range queries

    Note:
        This model extends BaseImmutableModel which has no updated_at column
        since balance snapshots are never modified after creation.

    Example:
        snapshot = BalanceSnapshot(
            account_id=account_id,
            balance_amount=Decimal("10000.00"),
            currency="USD",
            source="account_sync",
            holdings_value_amount=Decimal("8500.00"),
            cash_value_amount=Decimal("1500.00"),
        )
        session.add(snapshot)
        await session.commit()
    """

    __tablename__ = "balance_snapshots"

    # =========================================================================
    # Core Identifiers
    # =========================================================================

    # Foreign key to accounts (CASCADE delete)
    account_id: Mapped[UUID] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="FK to accounts table",
    )

    # =========================================================================
    # Balance Values
    # =========================================================================

    # Total account balance at capture time
    balance_amount: Mapped[Decimal] = mapped_column(
        Numeric(precision=19, scale=4),
        nullable=False,
        comment="Total account balance at capture time",
    )

    # Currency code (shared by all money fields)
    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        default="USD",
        comment="ISO 4217 currency code",
    )

    # Available balance if different (nullable)
    available_balance_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(precision=19, scale=4),
        nullable=True,
        comment="Available balance (if different from total)",
    )

    # Holdings market value (nullable)
    holdings_value_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(precision=19, scale=4),
        nullable=True,
        comment="Total market value of holdings/positions",
    )

    # Cash balance (nullable)
    cash_value_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(precision=19, scale=4),
        nullable=True,
        comment="Cash/money market balance",
    )

    # =========================================================================
    # Source & Timing
    # =========================================================================

    # Snapshot source (stored as lowercase string, mapped to enum)
    source: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="How/why snapshot was captured (account_sync, manual_sync, etc.)",
    )

    # Capture timestamp (when balance was recorded)
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        comment="Timestamp when balance was captured",
    )

    # =========================================================================
    # Metadata
    # =========================================================================

    # Provider-specific metadata (JSONB for flexibility)
    provider_metadata: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Provider-specific data at capture time",
    )

    # =========================================================================
    # Table Constraints and Indexes
    # =========================================================================

    __table_args__ = (
        # Composite index for account + time range queries (most common pattern)
        Index(
            "idx_balance_snapshots_account_time",
            "account_id",
            "captured_at",
        ),
        # Composite index for account + source + time (filtered queries)
        Index(
            "idx_balance_snapshots_account_source_time",
            "account_id",
            "source",
            "captured_at",
        ),
    )

    def __repr__(self) -> str:
        """String representation for debugging.

        Returns:
            str: Human-readable representation of balance snapshot.
        """
        return (
            f"<BalanceSnapshot("
            f"id={self.id}, "
            f"account_id={self.account_id}, "
            f"balance={self.balance_amount}, "
            f"captured_at={self.captured_at}"
            f")>"
        )
