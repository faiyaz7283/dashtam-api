"""ListProviderConnections query handler.

Handles requests to list provider connections for a user.
Returns DTO list (not domain entities) to prevent leaking domain to presentation.

Architecture:
- Application layer handler (orchestrates data retrieval)
- Returns Result[DTO, str] (explicit error handling)
- NO domain events (queries are side-effect free)

Reference:
    - docs/architecture/cqrs-pattern.md
"""

from dataclasses import dataclass

from src.application.queries.handlers.get_provider_handler import (
    ProviderConnectionResult,
)
from src.application.queries.provider_queries import ListProviderConnections
from src.core.result import Result, Success
from src.domain.entities.provider_connection import ProviderConnection
from src.domain.enums.connection_status import ConnectionStatus
from src.domain.protocols.provider_connection_repository import (
    ProviderConnectionRepository,
)


@dataclass
class ProviderConnectionListResult:
    """Provider connection list result DTO.

    Contains list of connections with summary counts.

    Attributes:
        connections: List of connection DTOs.
        total_count: Total number of connections.
        active_count: Number of ACTIVE connections.
    """

    connections: list[ProviderConnectionResult]
    total_count: int
    active_count: int


class ListProviderConnectionsHandler:
    """Handler for ListProviderConnections query.

    Retrieves all provider connections for a user, optionally filtered
    to active only.

    Dependencies (injected via constructor):
        - ProviderConnectionRepository: For data retrieval
    """

    def __init__(
        self,
        connection_repo: ProviderConnectionRepository,
    ) -> None:
        """Initialize handler with dependencies.

        Args:
            connection_repo: Provider connection repository.
        """
        self._connection_repo = connection_repo

    async def handle(
        self, query: ListProviderConnections
    ) -> Result[ProviderConnectionListResult, str]:
        """Handle ListProviderConnections query.

        Retrieves connections from repository and maps to DTOs.

        Args:
            query: ListProviderConnections query with user ID and filters.

        Returns:
            Success(ProviderConnectionListResult): List of connection DTOs.
            Never returns Failure (empty list is valid result).
        """
        # Fetch connections based on filter
        if query.active_only:
            connections = await self._connection_repo.find_active_by_user(query.user_id)
        else:
            connections = await self._connection_repo.find_by_user_id(query.user_id)

        # Count active (may differ if active_only=False)
        active_count = sum(
            1 for c in connections if c.status == ConnectionStatus.ACTIVE
        )

        # Map to DTOs
        connection_dtos = [self._to_dto(conn) for conn in connections]

        return Success(
            value=ProviderConnectionListResult(
                connections=connection_dtos,
                total_count=len(connection_dtos),
                active_count=active_count,
            )
        )

    def _to_dto(self, connection: ProviderConnection) -> ProviderConnectionResult:
        """Map domain entity to DTO.

        Args:
            connection: Domain entity.

        Returns:
            ProviderConnectionResult DTO.
        """
        return ProviderConnectionResult(
            id=connection.id,
            user_id=connection.user_id,
            provider_id=connection.provider_id,
            provider_slug=connection.provider_slug,
            alias=connection.alias,
            status=connection.status,
            is_connected=connection.is_connected(),
            needs_reauthentication=connection.needs_reauthentication(),
            connected_at=connection.connected_at,
            last_sync_at=connection.last_sync_at,
            created_at=connection.created_at,
            updated_at=connection.updated_at,
        )
