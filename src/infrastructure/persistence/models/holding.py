"""Holding database model.

This module defines the Holding model for storing portfolio position data
synced from provider accounts.

Architecture:
    - Holdings belong to accounts (FK relationship with CASCADE delete)
    - Money fields: cost_basis, market_value, average_price, current_price
    - All amounts stored as Decimal with separate currency column
    - Asset type stored as lowercase string
    - Provider metadata stored as JSONB for flexibility

Reference:
    - docs/architecture/repository-pattern.md
    - src/domain/entities/holding.py
"""

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.persistence.base import BaseMutableModel


class Holding(BaseMutableModel):
    """Holding model for portfolio position storage.

    Represents an investment holding (position) synced from a provider account.
    Holdings show what the user currently owns in their investment accounts.

    Fields:
        id: UUID primary key (from BaseMutableModel)
        created_at: Timestamp when created (from BaseMutableModel)
        updated_at: Timestamp when last updated (from BaseMutableModel)
        account_id: FK to accounts table
        provider_holding_id: Provider's unique identifier for this position
        symbol: Security ticker symbol (AAPL, TSLA, etc.)
        security_name: Full security name (Apple Inc., etc.)
        asset_type: Type of security (equity, etf, option, etc.)
        quantity: Number of shares/units held
        cost_basis_amount: Total cost paid for this position
        market_value_amount: Current market value of the position
        currency: ISO 4217 currency code
        average_price_amount: Average price per share (nullable)
        current_price_amount: Current market price per share (nullable)
        is_active: Whether position is still held (quantity > 0)
        last_synced_at: Last successful sync timestamp
        provider_metadata: Provider-specific data (JSONB)

    Indexes:
        - ix_holdings_account_id: FK lookup
        - ix_holdings_symbol: Security lookup
        - ix_holdings_asset_type: Filter by asset type
        - ix_holdings_is_active: Active position queries
        - idx_holdings_active: Partial index for active holdings (optimization)
        - uq_holdings_account_provider: Unique (account_id, provider_holding_id)

    Example:
        holding = Holding(
            account_id=account_id,
            provider_holding_id="SCHWAB-AAPL-123",
            symbol="AAPL",
            security_name="Apple Inc.",
            asset_type="equity",
            quantity=Decimal("100"),
            cost_basis_amount=Decimal("15000.00"),
            market_value_amount=Decimal("17500.00"),
            currency="USD",
        )
        session.add(holding)
        await session.commit()
    """

    __tablename__ = "holdings"

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

    # Provider's unique identifier (for deduplication during sync)
    provider_holding_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Provider's unique identifier for this position",
    )

    # =========================================================================
    # Security Details
    # =========================================================================

    # Security ticker symbol
    symbol: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Security ticker symbol (AAPL, TSLA, etc.)",
    )

    # Full security name
    security_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Full security name (Apple Inc., etc.)",
    )

    # Type of security (stored as lowercase string, mapped to enum)
    asset_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Asset type (equity, etf, option, etc.)",
    )

    # =========================================================================
    # Position Details
    # =========================================================================

    # Number of shares/units (8 decimal places for crypto/fractional shares)
    quantity: Mapped[Decimal] = mapped_column(
        Numeric(precision=19, scale=8),
        nullable=False,
        comment="Number of shares/units held",
    )

    # Total cost paid for this position
    cost_basis_amount: Mapped[Decimal] = mapped_column(
        Numeric(precision=19, scale=4),
        nullable=False,
        comment="Total cost paid for this position",
    )

    # Current market value
    market_value_amount: Mapped[Decimal] = mapped_column(
        Numeric(precision=19, scale=4),
        nullable=False,
        comment="Current market value of the position",
    )

    # Currency code (shared by all money fields)
    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        default="USD",
        comment="ISO 4217 currency code",
    )

    # Average price per share (nullable)
    average_price_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(precision=19, scale=4),
        nullable=True,
        comment="Average price per share (cost_basis / quantity)",
    )

    # Current market price per share (nullable)
    current_price_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(precision=19, scale=4),
        nullable=True,
        comment="Current market price per share",
    )

    # =========================================================================
    # Status
    # =========================================================================

    # Active status (quantity > 0)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
        comment="Whether position is still held (quantity > 0)",
    )

    # Last sync timestamp
    last_synced_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Last successful sync timestamp",
    )

    # =========================================================================
    # Metadata
    # =========================================================================

    # Provider-specific metadata (JSONB for flexibility)
    provider_metadata: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Provider-specific data (unstructured)",
    )

    # =========================================================================
    # Table Constraints and Indexes
    # =========================================================================

    __table_args__ = (
        # Unique constraint: one provider_holding_id per account
        UniqueConstraint(
            "account_id",
            "provider_holding_id",
            name="uq_holdings_account_provider",
        ),
        # Partial index for active holding queries (optimization)
        Index(
            "idx_holdings_active",
            "account_id",
            postgresql_where="is_active = true",
        ),
        # Composite index for account + symbol queries
        Index(
            "idx_holdings_account_symbol",
            "account_id",
            "symbol",
        ),
    )

    def __repr__(self) -> str:
        """String representation for debugging.

        Returns:
            str: Human-readable representation of holding.
        """
        return (
            f"<Holding("
            f"id={self.id}, "
            f"symbol={self.symbol!r}, "
            f"quantity={self.quantity}, "
            f"market_value={self.market_value_amount}"
            f")>"
        )
