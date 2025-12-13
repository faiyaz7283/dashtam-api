"""ProviderConnectionRepository - SQLAlchemy implementation.

Adapter for hexagonal architecture.
Maps between domain ProviderConnection entities and database ProviderConnectionModel.

Reference:
    - docs/architecture/repository-pattern.md
"""

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.provider_connection import ProviderConnection
from src.domain.enums.connection_status import ConnectionStatus
from src.domain.enums.credential_type import CredentialType
from src.domain.value_objects.provider_credentials import ProviderCredentials
from src.infrastructure.persistence.models.provider_connection import (
    ProviderConnection as ProviderConnectionModel,
)


class ProviderConnectionRepository:
    """SQLAlchemy implementation of ProviderConnectionRepository protocol.

    This is an adapter that implements the ProviderConnectionRepository port.
    It handles the mapping between domain ProviderConnection entities and
    database ProviderConnectionModel.

    This class does NOT inherit from the protocol (Protocol uses structural typing).

    Attributes:
        session: SQLAlchemy async session for database operations.

    Example:
        >>> async with get_session() as session:
        ...     repo = ProviderConnectionRepository(session)
        ...     conn = await repo.find_by_id(connection_id)
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository with database session.

        Args:
            session: SQLAlchemy async session.
        """
        self.session = session

    async def find_by_id(self, connection_id: UUID) -> ProviderConnection | None:
        """Find connection by ID.

        Args:
            connection_id: Connection's unique identifier.

        Returns:
            Domain ProviderConnection entity if found, None otherwise.
        """
        stmt = select(ProviderConnectionModel).where(
            ProviderConnectionModel.id == connection_id
        )
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()

        if model is None:
            return None

        return self._to_domain(model)

    async def find_by_user_id(self, user_id: UUID) -> list[ProviderConnection]:
        """Find all connections for a user.

        Returns connections in all statuses (including disconnected).

        Args:
            user_id: User's unique identifier.

        Returns:
            List of connections (empty if none found).
        """
        stmt = select(ProviderConnectionModel).where(
            ProviderConnectionModel.user_id == user_id
        )
        result = await self.session.execute(stmt)
        models = result.scalars().all()

        return [self._to_domain(model) for model in models]

    async def find_by_user_and_provider(
        self,
        user_id: UUID,
        provider_id: UUID,
    ) -> list[ProviderConnection]:
        """Find all connections for user + provider combination.

        User may have multiple connections to same provider (different accounts).

        Args:
            user_id: User's unique identifier.
            provider_id: Provider's unique identifier.

        Returns:
            List of connections (empty if none found).
        """
        stmt = select(ProviderConnectionModel).where(
            ProviderConnectionModel.user_id == user_id,
            ProviderConnectionModel.provider_id == provider_id,
        )
        result = await self.session.execute(stmt)
        models = result.scalars().all()

        return [self._to_domain(model) for model in models]

    async def find_active_by_user(self, user_id: UUID) -> list[ProviderConnection]:
        """Find all active connections for a user.

        Only returns connections with status=ACTIVE.

        Args:
            user_id: User's unique identifier.

        Returns:
            List of active connections (empty if none found).
        """
        stmt = select(ProviderConnectionModel).where(
            ProviderConnectionModel.user_id == user_id,
            ProviderConnectionModel.status == ConnectionStatus.ACTIVE.value,
        )
        result = await self.session.execute(stmt)
        models = result.scalars().all()

        return [self._to_domain(model) for model in models]

    async def save(self, connection: ProviderConnection) -> None:
        """Create or update connection in database.

        Uses merge semantics - creates if not exists, updates if exists.

        Args:
            connection: ProviderConnection entity to persist.
        """
        # Check if exists
        stmt = select(ProviderConnectionModel).where(
            ProviderConnectionModel.id == connection.id
        )
        result = await self.session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing is None:
            # Create new
            model = self._to_model(connection)
            self.session.add(model)
        else:
            # Update existing
            existing.user_id = connection.user_id
            existing.provider_id = connection.provider_id
            existing.provider_slug = connection.provider_slug
            existing.status = connection.status.value
            existing.alias = connection.alias
            existing.connected_at = connection.connected_at
            existing.last_sync_at = connection.last_sync_at
            existing.updated_at = connection.updated_at

            # Handle credentials
            if connection.credentials is not None:
                existing.credential_type = connection.credentials.credential_type.value
                existing.encrypted_credentials = connection.credentials.encrypted_data
                existing.credentials_expires_at = connection.credentials.expires_at
            else:
                existing.credential_type = None
                existing.encrypted_credentials = None
                existing.credentials_expires_at = None

        await self.session.commit()

    async def delete(self, connection_id: UUID) -> None:
        """Remove connection from database.

        Hard delete - permanently removes the record.

        Args:
            connection_id: Connection's unique identifier.

        Raises:
            NoResultFound: If connection doesn't exist.
        """
        stmt = select(ProviderConnectionModel).where(
            ProviderConnectionModel.id == connection_id
        )
        result = await self.session.execute(stmt)
        model = result.scalar_one()  # Raises NoResultFound if not found

        await self.session.delete(model)
        await self.session.commit()

    async def find_expiring_soon(
        self,
        minutes: int = 30,
    ) -> list[ProviderConnection]:
        """Find connections with credentials expiring soon.

        Used by background job to proactively refresh credentials.

        Args:
            minutes: Time threshold in minutes (default 30).

        Returns:
            List of active connections with credentials expiring within threshold.
        """
        threshold = datetime.now(UTC) + timedelta(minutes=minutes)

        stmt = select(ProviderConnectionModel).where(
            ProviderConnectionModel.status == ConnectionStatus.ACTIVE.value,
            ProviderConnectionModel.credentials_expires_at.isnot(None),
            ProviderConnectionModel.credentials_expires_at <= threshold,
        )
        result = await self.session.execute(stmt)
        models = result.scalars().all()

        return [self._to_domain(model) for model in models]

    def _to_domain(self, model: ProviderConnectionModel) -> ProviderConnection:
        """Convert database model to domain entity.

        Args:
            model: SQLAlchemy ProviderConnectionModel instance.

        Returns:
            Domain ProviderConnection entity.
        """
        # Reconstruct credentials value object if data exists
        credentials = None
        if (
            model.encrypted_credentials is not None
            and model.credential_type is not None
        ):
            credentials = ProviderCredentials(
                encrypted_data=model.encrypted_credentials,
                credential_type=CredentialType(model.credential_type),
                expires_at=model.credentials_expires_at,
            )

        return ProviderConnection(
            id=model.id,
            user_id=model.user_id,
            provider_id=model.provider_id,
            provider_slug=model.provider_slug,
            status=ConnectionStatus(model.status),
            alias=model.alias,
            credentials=credentials,
            connected_at=model.connected_at,
            last_sync_at=model.last_sync_at,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    def _to_model(self, entity: ProviderConnection) -> ProviderConnectionModel:
        """Convert domain entity to database model.

        Args:
            entity: Domain ProviderConnection entity.

        Returns:
            SQLAlchemy ProviderConnectionModel instance.
        """
        # Extract credential fields
        credential_type = None
        encrypted_credentials = None
        credentials_expires_at = None

        if entity.credentials is not None:
            credential_type = entity.credentials.credential_type.value
            encrypted_credentials = entity.credentials.encrypted_data
            credentials_expires_at = entity.credentials.expires_at

        return ProviderConnectionModel(
            id=entity.id,
            user_id=entity.user_id,
            provider_id=entity.provider_id,
            provider_slug=entity.provider_slug,
            status=entity.status.value,
            alias=entity.alias,
            credential_type=credential_type,
            encrypted_credentials=encrypted_credentials,
            credentials_expires_at=credentials_expires_at,
            connected_at=entity.connected_at,
            last_sync_at=entity.last_sync_at,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )
