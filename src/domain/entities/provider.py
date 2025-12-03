"""Provider domain entity.

Represents a financial data provider (Schwab, Chase, Plaid, etc.)
that users can connect to for data aggregation.

This is a relatively static entity - providers are typically seeded
at deployment and rarely change. It serves as a registry of supported
providers with their configuration metadata.

Reference:
    - docs/architecture/provider-domain-model.md
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID

from src.domain.enums.credential_type import CredentialType


@dataclass
class Provider:
    """Financial data provider entity.

    Represents a supported provider in the system. Providers are typically
    seeded at deployment (e.g., Schwab) and can be enabled/disabled.

    Attributes:
        id: Unique provider identifier.
        slug: URL-safe identifier (e.g., "schwab", "chase"). Unique.
        name: Human-readable name (e.g., "Charles Schwab").
        credential_type: Default authentication mechanism for this provider.
        description: Optional description for UI display.
        logo_url: Optional URL to provider logo for UI.
        website_url: Optional provider website URL.
        is_active: Whether provider is available for new connections.
        created_at: When provider was added to registry.
        updated_at: When provider was last modified.

    Example:
        >>> provider = Provider(
        ...     id=uuid7(),
        ...     slug="schwab",
        ...     name="Charles Schwab",
        ...     credential_type=CredentialType.OAUTH2,
        ...     is_active=True,
        ... )
        >>> provider.slug
        'schwab'
    """

    id: UUID
    slug: str
    name: str
    credential_type: CredentialType
    description: str | None = None
    logo_url: str | None = None
    website_url: str | None = None
    is_active: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        """Validate provider after initialization.

        Raises:
            ValueError: If required fields are invalid.
        """
        if not self.slug:
            raise ValueError("Provider slug cannot be empty")

        if len(self.slug) > 50:
            raise ValueError("Provider slug cannot exceed 50 characters")

        # Slug must be URL-safe (lowercase, alphanumeric, hyphens)
        if not self.slug.replace("-", "").replace("_", "").isalnum():
            raise ValueError(
                "Provider slug must be alphanumeric with hyphens/underscores"
            )

        if self.slug != self.slug.lower():
            raise ValueError("Provider slug must be lowercase")

        if not self.name:
            raise ValueError("Provider name cannot be empty")

        if len(self.name) > 100:
            raise ValueError("Provider name cannot exceed 100 characters")

    def __repr__(self) -> str:
        """Return repr for debugging.

        Returns:
            str: String representation.
        """
        return (
            f"Provider(slug={self.slug!r}, name={self.name!r}, "
            f"is_active={self.is_active})"
        )

    def __str__(self) -> str:
        """Return string representation.

        Returns:
            str: Human-readable string.
        """
        status = "active" if self.is_active else "inactive"
        return f"{self.name} ({self.slug}) - {status}"
