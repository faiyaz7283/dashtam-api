"""Account database model.

This module defines the Account model for storing financial account data
synced from provider connections.

Architecture:
    - Accounts belong to provider connections (FK relationship)
    - Balance stored as Decimal with separate currency column
    - Account type stored as lowercase string
    - Provider metadata stored as JSONB for flexibility

Reference:
    - docs/architecture/account-domain-model.md
    - docs/architecture/repository-pattern.md
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


class Account(BaseMutableModel):
    """Account model for financial account storage.

    Represents a financial account (brokerage, checking, IRA, etc.)
    aggregated from a provider connection.

    Fields:
        id: UUID primary key (from BaseMutableModel)
        created_at: Timestamp when created (from BaseMutableModel)
        updated_at: Timestamp when last updated (from BaseMutableModel)
        connection_id: FK to provider_connections table
        provider_account_id: Provider's unique account identifier
        account_number_masked: Masked account number (****1234)
        name: Account name from provider
        account_type: Type (brokerage, checking, ira, etc.)
        balance: Current balance amount (Decimal)
        currency: ISO 4217 currency code
        available_balance: Available balance if different (nullable)
        is_active: Whether account is active on provider
        last_synced_at: Last successful sync timestamp
        provider_metadata: Provider-specific data (JSONB)

    Indexes:
        - ix_accounts_connection_id: FK lookup
        - ix_accounts_account_type: Filter by type
        - ix_accounts_is_active: Active account queries
        - idx_accounts_active: Partial index for active accounts (optimization)
        - uq_accounts_connection_provider: Unique (connection_id, provider_account_id)

    Example:
        account = Account(
            connection_id=connection_id,
            provider_account_id="SCHWAB-12345",
            account_number_masked="****1234",
            name="Individual Brokerage",
            account_type="brokerage",
            balance=Decimal("10000.00"),
            currency="USD",
        )
        session.add(account)
        await session.commit()
    """

    __tablename__ = "accounts"

    # Foreign key to provider_connections (CASCADE delete)
    connection_id: Mapped[UUID] = mapped_column(
        ForeignKey("provider_connections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="FK to provider_connections table",
    )

    # Provider's unique identifier
    provider_account_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Provider's unique account identifier",
    )

    # Masked account number for display
    account_number_masked: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Masked account number (****1234)",
    )

    # Account name
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Account name from provider",
    )

    # Account type (stored as lowercase string, mapped to enum)
    account_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Account type (brokerage, checking, ira, etc.)",
    )

    # Balance (Decimal for precision)
    balance: Mapped[Decimal] = mapped_column(
        Numeric(precision=19, scale=4),
        nullable=False,
        default=Decimal("0.0000"),
        comment="Current balance amount",
    )

    # Currency code
    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        default="USD",
        comment="ISO 4217 currency code",
    )

    # Available balance (nullable)
    available_balance: Mapped[Decimal | None] = mapped_column(
        Numeric(precision=19, scale=4),
        nullable=True,
        comment="Available balance (if different from balance)",
    )

    # Active status
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
        comment="Whether account is active on provider",
    )

    # Last sync timestamp
    last_synced_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Last successful sync timestamp",
    )

    # Provider-specific metadata (JSONB for flexibility)
    provider_metadata: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Provider-specific data (unstructured)",
    )

    # Table constraints and indexes
    __table_args__ = (
        # Unique constraint: one provider_account_id per connection
        UniqueConstraint(
            "connection_id",
            "provider_account_id",
            name="uq_accounts_connection_provider",
        ),
        # Partial index for active account queries (optimization)
        Index(
            "idx_accounts_active",
            "connection_id",
            postgresql_where="is_active = true",
        ),
    )

    def __repr__(self) -> str:
        """String representation for debugging.

        Returns:
            str: Human-readable representation of account.
        """
        return (
            f"<Account("
            f"id={self.id}, "
            f"name={self.name!r}, "
            f"account_type={self.account_type!r}, "
            f"balance={self.balance}"
            f")>"
        )
