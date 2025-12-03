"""Provider repository implementation.

PostgreSQL implementation of the ProviderRepository protocol.
Maps between Provider domain entity and Provider database model.

Reference:
    - docs/architecture/repository-pattern.md
"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.provider import Provider
from src.domain.enums.credential_type import CredentialType
from src.infrastructure.persistence.models.provider import Provider as ProviderModel


class ProviderRepository:
    """PostgreSQL implementation of ProviderRepository protocol.

    Handles persistence of Provider entities using SQLAlchemy async sessions.

    **Implementation Notes**:
    - Maps between domain entity (dataclass) and database model (SQLAlchemy)
    - Uses select() for queries (SQLAlchemy 2.0 style)
    - Caching could be added here since providers rarely change
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository with database session.

        Args:
            session: SQLAlchemy async session.
        """
        self._session = session

    async def find_by_id(self, provider_id: UUID) -> Provider | None:
        """Find provider by ID.

        Args:
            provider_id: Unique provider identifier.

        Returns:
            Provider entity if found, None otherwise.
        """
        stmt = select(ProviderModel).where(ProviderModel.id == provider_id)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()

        if model is None:
            return None

        return self._to_entity(model)

    async def find_by_slug(self, slug: str) -> Provider | None:
        """Find provider by slug.

        Args:
            slug: Provider slug (e.g., "schwab").

        Returns:
            Provider entity if found, None otherwise.
        """
        stmt = select(ProviderModel).where(ProviderModel.slug == slug)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()

        if model is None:
            return None

        return self._to_entity(model)

    async def list_all(self) -> list[Provider]:
        """List all providers (including inactive).

        Returns:
            List of all providers in the registry.
        """
        stmt = select(ProviderModel).order_by(ProviderModel.name)
        result = await self._session.execute(stmt)
        models = result.scalars().all()

        return [self._to_entity(m) for m in models]

    async def list_active(self) -> list[Provider]:
        """List only active providers.

        Returns:
            List of active providers.
        """
        stmt = (
            select(ProviderModel)
            .where(ProviderModel.is_active.is_(True))
            .order_by(ProviderModel.name)
        )
        result = await self._session.execute(stmt)
        models = result.scalars().all()

        return [self._to_entity(m) for m in models]

    async def save(self, provider: Provider) -> None:
        """Save a provider (create or update).

        Args:
            provider: Provider entity to save.
        """
        # Check if provider exists
        stmt = select(ProviderModel).where(ProviderModel.id == provider.id)
        result = await self._session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing is None:
            # Create new
            model = self._to_model(provider)
            self._session.add(model)
        else:
            # Update existing
            existing.slug = provider.slug
            existing.name = provider.name
            existing.credential_type = provider.credential_type.value
            existing.description = provider.description
            existing.logo_url = provider.logo_url
            existing.website_url = provider.website_url
            existing.is_active = provider.is_active
            existing.updated_at = provider.updated_at

        await self._session.flush()

    async def exists_by_slug(self, slug: str) -> bool:
        """Check if provider with slug exists.

        Args:
            slug: Provider slug to check.

        Returns:
            True if provider exists, False otherwise.
        """
        stmt = select(ProviderModel.id).where(ProviderModel.slug == slug)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none() is not None

    def _to_entity(self, model: ProviderModel) -> Provider:
        """Map database model to domain entity.

        Args:
            model: Database model.

        Returns:
            Domain entity.
        """
        return Provider(
            id=model.id,
            slug=model.slug,
            name=model.name,
            credential_type=CredentialType(model.credential_type),
            description=model.description,
            logo_url=model.logo_url,
            website_url=model.website_url,
            is_active=model.is_active,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    def _to_model(self, entity: Provider) -> ProviderModel:
        """Map domain entity to database model.

        Args:
            entity: Domain entity.

        Returns:
            Database model.
        """
        return ProviderModel(
            id=entity.id,
            slug=entity.slug,
            name=entity.name,
            credential_type=entity.credential_type.value,
            description=entity.description,
            logo_url=entity.logo_url,
            website_url=entity.website_url,
            is_active=entity.is_active,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )
