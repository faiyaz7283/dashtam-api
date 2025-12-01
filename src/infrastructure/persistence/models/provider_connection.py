"""Provider connection database model.

This module defines the ProviderConnection model for storing user-provider
connection data including encrypted credentials.

Security:
    - encrypted_credentials: AES-256 encrypted credential blob
    - credentials_expires_at: Token expiration for proactive refresh
    - Domain never sees raw credentials (infrastructure handles encryption)

Reference:
    - docs/architecture/provider-domain-model.md
    - docs/architecture/repository-pattern.md
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, LargeBinary, String
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.persistence.base import BaseMutableModel


class ProviderConnection(BaseMutableModel):
    """Provider connection model for user-provider relationships.

    Stores the connection between a user and a financial data provider,
    including encrypted OAuth credentials and connection state.

    Fields:
        id: UUID primary key (from BaseMutableModel)
        created_at: Timestamp when connection was created (from BaseMutableModel)
        updated_at: Timestamp when connection was last updated (from BaseMutableModel)
        user_id: FK to users table (cascade delete)
        provider_id: UUID for future providers table (no FK constraint yet)
        provider_slug: Denormalized provider identifier (e.g., "schwab")
        status: Connection lifecycle state (pending, active, expired, etc.)
        alias: User-defined nickname for the connection
        credential_type: Type of credential (oauth2, api_key, etc.)
        encrypted_credentials: AES-256 encrypted credential blob
        credentials_expires_at: When credentials expire
        connected_at: When connection was first established
        last_sync_at: Last successful data synchronization

    Indexes:
        - idx_provider_connections_user_id: (user_id) for user queries
        - idx_provider_connections_user_provider: (user_id, provider_id) for unique lookups
        - idx_provider_connections_status: (status) for filtering active connections
        - idx_provider_connections_expires: (credentials_expires_at) for refresh jobs

    Example:
        conn = ProviderConnection(
            user_id=user_id,
            provider_id=provider_id,
            provider_slug="schwab",
            status="pending",
        )
        session.add(conn)
        await session.commit()
    """

    __tablename__ = "provider_connections"

    # User relationship (required)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="User who owns this connection",
    )

    # Provider identification
    provider_id: Mapped[UUID] = mapped_column(
        nullable=False,
        comment="Provider UUID (FK to providers table in future)",
    )

    provider_slug: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Denormalized provider identifier (e.g., 'schwab')",
    )

    # Connection state
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
        comment="Connection status: pending, active, expired, revoked, failed, disconnected",
    )

    alias: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="User-defined nickname (e.g., 'My Schwab IRA')",
    )

    # Credentials (stored as separate columns for query flexibility)
    credential_type: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        comment="Credential type: oauth2, api_key, link_token, certificate, custom",
    )

    encrypted_credentials: Mapped[bytes | None] = mapped_column(
        LargeBinary,
        nullable=True,
        comment="AES-256 encrypted credential blob (domain sees ProviderCredentials)",
    )

    credentials_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When credentials expire (for proactive refresh)",
    )

    # Timestamps
    connected_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When connection was first established",
    )

    last_sync_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Last successful data synchronization",
    )

    # Composite indexes for common queries
    __table_args__ = (
        Index(
            "idx_provider_connections_user_provider",
            "user_id",
            "provider_id",
        ),
        Index(
            "idx_provider_connections_active",
            "user_id",
            "status",
            postgresql_where="status = 'active'",
        ),
        Index(
            "idx_provider_connections_expiring",
            "credentials_expires_at",
            postgresql_where="status = 'active' AND credentials_expires_at IS NOT NULL",
        ),
    )

    def __repr__(self) -> str:
        """String representation for debugging.

        Returns:
            str: Human-readable representation of connection.
        """
        return (
            f"<ProviderConnection("
            f"id={self.id}, "
            f"user_id={self.user_id}, "
            f"provider_slug={self.provider_slug!r}, "
            f"status={self.status!r}"
            f")>"
        )
