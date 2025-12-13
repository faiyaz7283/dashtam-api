"""GetProviderConnection query handler.

Handles requests to retrieve a single provider connection.
Returns DTO (not domain entity) to prevent leaking domain to presentation.

Architecture:
- Application layer handler (orchestrates data retrieval)
- Returns Result[DTO, str] (explicit error handling)
- NO domain events (queries are side-effect free)

Reference:
    - docs/architecture/cqrs-pattern.md
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from src.application.queries.provider_queries import GetProviderConnection
from src.core.result import Failure, Result, Success
from src.domain.enums.connection_status import ConnectionStatus
from src.domain.protocols.provider_connection_repository import (
    ProviderConnectionRepository,
)


@dataclass
class ProviderConnectionResult:
    """Single provider connection result DTO.

    Represents a provider connection for API response.
    Does NOT include sensitive data (credentials).

    Attributes:
        id: Connection unique identifier.
        user_id: Owning user's ID.
        provider_id: Provider registry ID.
        provider_slug: Provider identifier (e.g., "schwab").
        alias: User-defined nickname (if set).
        status: Current connection status.
        is_connected: Whether connection is usable.
        needs_reauthentication: Whether user needs to re-authenticate.
        connected_at: When connection was first established.
        last_sync_at: Last successful sync timestamp.
        created_at: Record creation timestamp.
        updated_at: Last modification timestamp.
    """

    id: UUID
    user_id: UUID
    provider_id: UUID
    provider_slug: str
    alias: str | None
    status: ConnectionStatus
    is_connected: bool
    needs_reauthentication: bool
    connected_at: datetime | None
    last_sync_at: datetime | None
    created_at: datetime
    updated_at: datetime


class GetProviderConnectionError:
    """GetProviderConnection-specific errors."""

    CONNECTION_NOT_FOUND = "Connection not found"
    NOT_OWNED_BY_USER = "Connection not owned by user"


class GetProviderConnectionHandler:
    """Handler for GetProviderConnection query.

    Retrieves a single provider connection by ID with ownership check.

    Dependencies (injected via constructor):
        - ProviderConnectionRepository: For data retrieval

    Returns:
        Result[ProviderConnectionResult, str]: Success(DTO) or Failure(error)
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
        self, query: GetProviderConnection
    ) -> Result[ProviderConnectionResult, str]:
        """Handle GetProviderConnection query.

        Retrieves connection, verifies ownership, and maps to DTO.

        Args:
            query: GetProviderConnection query with connection and user IDs.

        Returns:
            Success(ProviderConnectionResult): Connection found and owned by user.
            Failure(error): Connection not found or not owned by user.
        """
        # Fetch connection
        connection = await self._connection_repo.find_by_id(query.connection_id)

        # Verify exists
        if connection is None:
            return Failure(error=GetProviderConnectionError.CONNECTION_NOT_FOUND)

        # Verify ownership
        if connection.user_id != query.user_id:
            return Failure(error=GetProviderConnectionError.NOT_OWNED_BY_USER)

        # Map to DTO (no domain entity in response)
        dto = ProviderConnectionResult(
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

        return Success(value=dto)
