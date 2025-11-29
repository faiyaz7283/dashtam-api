"""ProviderConnectionRepository protocol for provider connection persistence.

Port (interface) for hexagonal architecture.
Infrastructure layer implements this protocol.

Reference:
    - docs/architecture/provider-domain-model.md
"""

from typing import Protocol
from uuid import UUID

from src.domain.entities.provider_connection import ProviderConnection


class ProviderConnectionRepository(Protocol):
    """Provider connection repository protocol (port).

    Defines the interface for provider connection persistence operations.
    Infrastructure layer provides concrete implementation.

    This is a Protocol (not ABC) for structural typing.
    Implementations don't need to inherit from this.

    Methods:
        find_by_id: Retrieve connection by ID
        find_by_user_id: Retrieve all connections for user
        find_by_user_and_provider: Retrieve connections for user + provider
        find_active_by_user: Retrieve active connections for user
        save: Create or update connection
        delete: Remove connection

    Example Implementation:
        >>> class PostgresProviderConnectionRepository:
        ...     async def find_by_id(self, id: UUID) -> ProviderConnection | None:
        ...         # Database logic here
        ...         pass
    """

    async def find_by_id(self, connection_id: UUID) -> ProviderConnection | None:
        """Find connection by ID.

        Args:
            connection_id: Connection's unique identifier.

        Returns:
            ProviderConnection if found, None otherwise.

        Example:
            >>> conn = await repo.find_by_id(connection_id)
            >>> if conn:
            ...     print(conn.provider_slug)
        """
        ...

    async def find_by_user_id(self, user_id: UUID) -> list[ProviderConnection]:
        """Find all connections for a user.

        Returns connections in all statuses (including disconnected).

        Args:
            user_id: User's unique identifier.

        Returns:
            List of connections (empty if none found).

        Example:
            >>> connections = await repo.find_by_user_id(user_id)
            >>> for conn in connections:
            ...     print(f"{conn.provider_slug}: {conn.status.value}")
        """
        ...

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

        Example:
            >>> connections = await repo.find_by_user_and_provider(user_id, schwab_id)
            >>> # User might have multiple Schwab accounts
            >>> for conn in connections:
            ...     print(conn.alias)
        """
        ...

    async def find_active_by_user(self, user_id: UUID) -> list[ProviderConnection]:
        """Find all active connections for a user.

        Only returns connections with status=ACTIVE.

        Args:
            user_id: User's unique identifier.

        Returns:
            List of active connections (empty if none found).

        Example:
            >>> active = await repo.find_active_by_user(user_id)
            >>> for conn in active:
            ...     if conn.can_sync():
            ...         # Perform sync
        """
        ...

    async def save(self, connection: ProviderConnection) -> None:
        """Create or update connection in database.

        Uses upsert semantics - creates if not exists, updates if exists.

        Args:
            connection: ProviderConnection entity to persist.

        Raises:
            DatabaseError: If database operation fails.

        Example:
            >>> conn = ProviderConnection(...)
            >>> await repo.save(conn)
        """
        ...

    async def delete(self, connection_id: UUID) -> None:
        """Remove connection from database.

        Hard delete - permanently removes the record.
        For soft delete, use mark_disconnected() on the entity instead.

        Args:
            connection_id: Connection's unique identifier.

        Raises:
            NotFoundError: If connection doesn't exist.
            DatabaseError: If database operation fails.

        Note:
            Consider using mark_disconnected() for audit trail instead of delete.

        Example:
            >>> await repo.delete(connection_id)
        """
        ...

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

        Example:
            >>> expiring = await repo.find_expiring_soon(minutes=15)
            >>> for conn in expiring:
            ...     # Trigger refresh
        """
        ...
