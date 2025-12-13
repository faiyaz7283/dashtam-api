"""Provider repository protocol.

Defines the interface for provider persistence operations.
Providers are typically seeded at deployment and rarely change.
"""

from typing import Protocol
from uuid import UUID

from src.domain.entities.provider import Provider


class ProviderRepository(Protocol):
    """Protocol for provider persistence operations.

    Defines the contract for storing and retrieving provider data.
    Infrastructure layer provides concrete implementations (e.g., PostgreSQL).

    **Design Principles**:
    - Read methods return domain entities (Provider), not database models
    - Providers are relatively static (seeded at deployment)
    - Most operations are reads (list, get by slug/id)
    - Write operations typically admin-only or migration scripts

    **Implementation Notes**:
    - Caching recommended since providers rarely change
    - slug is unique and the primary lookup key
    - is_active filters available providers from inactive ones
    """

    async def find_by_id(self, provider_id: UUID) -> Provider | None:
        """Find provider by ID.

        Args:
            provider_id: Unique provider identifier.

        Returns:
            Provider entity if found, None otherwise.

        Example:
            >>> provider = await repo.find_by_id(provider_id)
            >>> if provider:
            ...     print(f"Found: {provider.name}")
        """
        ...

    async def find_by_slug(self, slug: str) -> Provider | None:
        """Find provider by slug.

        This is the primary lookup method - slug is human-readable
        and used in URLs, configs, and API requests.

        Args:
            slug: Provider slug (e.g., "schwab", "chase").

        Returns:
            Provider entity if found, None otherwise.

        Example:
            >>> provider = await repo.find_by_slug("schwab")
            >>> if provider:
            ...     print(f"Found: {provider.name}")
        """
        ...

    async def list_all(self) -> list[Provider]:
        """List all providers (including inactive).

        Returns:
            List of all providers in the registry.

        Example:
            >>> providers = await repo.list_all()
            >>> print(f"Total providers: {len(providers)}")
        """
        ...

    async def list_active(self) -> list[Provider]:
        """List only active providers.

        Returns providers available for new connections.

        Returns:
            List of active providers.

        Example:
            >>> providers = await repo.list_active()
            >>> for p in providers:
            ...     print(f"{p.name} ({p.slug})")
        """
        ...

    async def save(self, provider: Provider) -> None:
        """Save a provider (create or update).

        Creates new provider if ID doesn't exist, updates if it does.
        Typically used in migrations/seeding, not runtime operations.

        Args:
            provider: Provider entity to save.

        Raises:
            DuplicateSlugError: If slug already exists for different provider.

        Example:
            >>> provider = Provider(
            ...     id=uuid7(),
            ...     slug="schwab",
            ...     name="Charles Schwab",
            ...     credential_type=CredentialType.OAUTH2,
            ... )
            >>> await repo.save(provider)
        """
        ...

    async def exists_by_slug(self, slug: str) -> bool:
        """Check if provider with slug exists.

        Args:
            slug: Provider slug to check.

        Returns:
            True if provider exists, False otherwise.

        Example:
            >>> if await repo.exists_by_slug("schwab"):
            ...     print("Schwab is already registered")
        """
        ...
