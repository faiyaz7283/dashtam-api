"""Transaction database model.

This module defines the Transaction model for storing financial transaction data
synced from provider accounts.

Architecture:
    - Transactions belong to accounts (FK relationship with CASCADE delete)
    - Amount stored as Decimal with separate currency column
    - Multiple Money fields: amount (required), unit_price (nullable), commission (nullable)
    - Four enums stored as lowercase strings: transaction_type, subtype, status, asset_type
    - Two date fields: transaction_date (required), settlement_date (nullable)
    - Provider metadata stored as JSONB for flexibility

Reference:
    - docs/architecture/repository-pattern.md
    - src/domain/entities/transaction.py
"""

from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import (
    Date,
    ForeignKey,
    Index,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.persistence.base import BaseMutableModel


class Transaction(BaseMutableModel):
    """Transaction model for financial transaction storage.

    Represents a historical financial transaction (trade, transfer, income, fee)
    aggregated from a provider account.

    Fields:
        id: UUID primary key (from BaseMutableModel)
        created_at: Timestamp when created (from BaseMutableModel)
        updated_at: Timestamp when last updated (from BaseMutableModel)
        account_id: FK to accounts table
        provider_transaction_id: Provider's unique transaction identifier
        transaction_type: High-level category (trade, transfer, income, fee, other)
        subtype: Specific action (buy, sell, deposit, dividend, etc.)
        status: Lifecycle state (pending, settled, failed, cancelled)
        amount: Transaction amount (positive=credit, negative=debit)
        currency: ISO 4217 currency code
        description: Human-readable description
        asset_type: Type of security (nullable, for TRADE only)
        symbol: Security ticker symbol (nullable, for TRADE only)
        security_name: Full security name (nullable)
        quantity: Number of shares/units (nullable, for TRADE only)
        unit_price_amount: Price per share (nullable, for TRADE only)
        commission_amount: Trading commission (nullable)
        transaction_date: Date transaction occurred
        settlement_date: Date funds/securities settled (nullable)
        provider_metadata: Provider-specific data (JSONB)

    Indexes:
        - ix_transactions_account_id: FK lookup
        - ix_transactions_transaction_type: Filter by type
        - ix_transactions_transaction_date: Date range queries
        - ix_transactions_symbol: Security transaction lookup
        - ix_transactions_status: Filter by status
        - idx_transactions_settled: Partial index for settled transactions
        - uq_transactions_account_provider: Unique (account_id, provider_transaction_id)

    Example:
        transaction = Transaction(
            account_id=account_id,
            provider_transaction_id="schwab-12345",
            transaction_type="trade",
            subtype="buy",
            status="settled",
            amount=Decimal("-1050.00"),
            currency="USD",
            description="Bought 10 shares of AAPL",
            asset_type="equity",
            symbol="AAPL",
            quantity=Decimal("10"),
            unit_price_amount=Decimal("105.00"),
            transaction_date=date(2025, 11, 28),
        )
        session.add(transaction)
        await session.commit()
    """

    __tablename__ = "transactions"

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

    # Provider's unique identifier (for deduplication)
    provider_transaction_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Provider's unique transaction identifier",
    )

    # =========================================================================
    # Classification (Enums stored as lowercase strings)
    # =========================================================================

    # High-level category
    transaction_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Transaction type (trade, transfer, income, fee, other)",
    )

    # Specific action within type
    subtype: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Transaction subtype (buy, sell, deposit, dividend, etc.)",
    )

    # Lifecycle status
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Transaction status (pending, settled, failed, cancelled)",
    )

    # =========================================================================
    # Financial Details
    # =========================================================================

    # Transaction amount (positive=credit, negative=debit)
    amount: Mapped[Decimal] = mapped_column(
        Numeric(precision=19, scale=4),
        nullable=False,
        comment="Transaction amount (positive=credit, negative=debit)",
    )

    # Currency code (shared by amount, unit_price, commission)
    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        default="USD",
        comment="ISO 4217 currency code",
    )

    # Human-readable description
    description: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        comment="Transaction description from provider",
    )

    # =========================================================================
    # Security Details (TRADE transactions only)
    # =========================================================================

    # Type of security (nullable for non-TRADE)
    asset_type: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Asset type (equity, option, etf, etc.) - TRADE only",
    )

    # Security ticker symbol
    symbol: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        index=True,
        comment="Security ticker symbol (AAPL, BTC-USD, etc.)",
    )

    # Full security name
    security_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Full security name (Apple Inc., etc.)",
    )

    # Number of shares/units (8 decimal places for crypto precision)
    quantity: Mapped[Decimal | None] = mapped_column(
        Numeric(precision=19, scale=8),
        nullable=True,
        comment="Number of shares/units traded",
    )

    # Price per share/unit (uses same currency as amount)
    unit_price_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(precision=19, scale=4),
        nullable=True,
        comment="Price per share/unit",
    )

    # Trading commission (uses same currency as amount)
    commission_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(precision=19, scale=4),
        nullable=True,
        comment="Trading commission/fee",
    )

    # =========================================================================
    # Dates
    # =========================================================================

    # Date transaction occurred (from provider)
    transaction_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        index=True,
        comment="Date transaction occurred",
    )

    # Date funds/securities settled (nullable)
    settlement_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        comment="Date funds/securities settled",
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
        # Unique constraint: one provider_transaction_id per account
        UniqueConstraint(
            "account_id",
            "provider_transaction_id",
            name="uq_transactions_account_provider",
        ),
        # Partial index for settled transaction queries (optimization)
        Index(
            "idx_transactions_settled",
            "account_id",
            "transaction_date",
            postgresql_where="status = 'settled'",
        ),
        # Composite index for date range queries by account
        Index(
            "idx_transactions_account_date",
            "account_id",
            "transaction_date",
        ),
    )

    def __repr__(self) -> str:
        """String representation for debugging.

        Returns:
            str: Human-readable representation of transaction.
        """
        return (
            f"<Transaction("
            f"id={self.id}, "
            f"type={self.transaction_type!r}, "
            f"subtype={self.subtype!r}, "
            f"amount={self.amount}, "
            f"symbol={self.symbol!r}"
            f")>"
        )
