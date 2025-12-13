"""Provider database model.

This module defines the Provider model for storing provider registry data.
Providers are typically seeded at deployment and represent supported
financial data providers (Schwab, Chase, Plaid, etc.).

Reference:
    - docs/architecture/provider-domain-model.md
"""

from sqlalchemy import Boolean, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.persistence.base import BaseMutableModel


class Provider(BaseMutableModel):
    """Provider model for the provider registry.

    Stores metadata about supported financial data providers.
    Providers are typically seeded at deployment via migrations.

    Fields:
        id: UUID primary key (from BaseMutableModel)
        created_at: Timestamp when provider was added (from BaseMutableModel)
        updated_at: Timestamp when provider was last modified (from BaseMutableModel)
        slug: URL-safe unique identifier (e.g., "schwab")
        name: Human-readable name (e.g., "Charles Schwab")
        credential_type: Authentication mechanism (oauth2, api_key, etc.)
        description: Optional description for UI display
        logo_url: Optional URL to provider logo
        website_url: Optional provider website URL
        is_active: Whether provider is available for new connections

    Indexes:
        - idx_providers_slug: (slug) UNIQUE - primary lookup key
        - idx_providers_active: (is_active) - filter active providers

    Example:
        provider = Provider(
            slug="schwab",
            name="Charles Schwab",
            credential_type="oauth2",
            is_active=True,
        )
        session.add(provider)
        await session.commit()
    """

    __tablename__ = "providers"

    # Primary identifier (unique, URL-safe)
    slug: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        unique=True,
        index=True,
        comment="URL-safe unique identifier (e.g., 'schwab')",
    )

    # Display name
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Human-readable name (e.g., 'Charles Schwab')",
    )

    # Authentication type
    credential_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="Credential type: oauth2, api_key, link_token, certificate, custom",
    )

    # Optional metadata
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Optional description for UI display",
    )

    logo_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="Optional URL to provider logo",
    )

    website_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="Optional provider website URL",
    )

    # Status
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
        comment="Whether provider is available for new connections",
    )

    # Indexes
    __table_args__ = (
        Index(
            "idx_providers_active_slug",
            "is_active",
            "slug",
            postgresql_where="is_active = true",
        ),
    )

    def __repr__(self) -> str:
        """String representation for debugging.

        Returns:
            str: Human-readable representation of provider.
        """
        return (
            f"<Provider("
            f"slug={self.slug!r}, "
            f"name={self.name!r}, "
            f"is_active={self.is_active}"
            f")>"
        )
