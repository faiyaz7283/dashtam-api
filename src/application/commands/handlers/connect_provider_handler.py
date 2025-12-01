"""ConnectProvider command handler.

Handles provider connection requests. Creates new connection record
and transitions to ACTIVE status with provided credentials.

Architecture:
- Application layer handler (orchestrates business logic)
- Imports only from domain layer (entities, protocols, events)
- Uses Result types for error handling
- Emits 3-state domain events (Attempted → Succeeded/Failed)

Reference:
    - docs/architecture/cqrs-pattern.md
    - docs/architecture/provider-domain-model.md
"""

from datetime import UTC, datetime
from uuid import UUID

from uuid_extensions import uuid7

from src.application.commands.provider_commands import ConnectProvider
from src.core.result import Failure, Result, Success
from src.domain.entities.provider_connection import ProviderConnection
from src.domain.enums.connection_status import ConnectionStatus
from src.domain.events.provider_events import (
    ProviderConnectionAttempted,
    ProviderConnectionFailed,
    ProviderConnectionSucceeded,
)
from src.domain.protocols.event_bus_protocol import EventBusProtocol
from src.domain.protocols.provider_connection_repository import (
    ProviderConnectionRepository,
)


class ConnectProviderError:
    """ConnectProvider-specific errors."""

    INVALID_CREDENTIALS = "Invalid or missing credentials"
    INVALID_PROVIDER_SLUG = "Invalid provider slug"
    DATABASE_ERROR = "Database error occurred"


class ConnectProviderHandler:
    """Handler for ConnectProvider command.

    Creates a new provider connection with ACTIVE status.
    The actual OAuth/API authentication happens in infrastructure layer
    before this handler is called.

    Dependencies (injected via constructor):
        - ProviderConnectionRepository: For persistence
        - EventBusProtocol: For domain events

    Returns:
        Result[UUID, str]: Success(connection_id) or Failure(error)
    """

    def __init__(
        self,
        connection_repo: ProviderConnectionRepository,
        event_bus: EventBusProtocol,
    ) -> None:
        """Initialize handler with dependencies.

        Args:
            connection_repo: Provider connection repository.
            event_bus: Event bus for publishing domain events.
        """
        self._connection_repo = connection_repo
        self._event_bus = event_bus

    async def handle(self, cmd: ConnectProvider) -> Result[UUID, str]:
        """Handle ConnectProvider command.

        Creates a new provider connection record with ACTIVE status.
        Emits domain events for audit trail and side effects.

        Args:
            cmd: ConnectProvider command with user, provider, and credentials.

        Returns:
            Success(connection_id): Connection created successfully.
            Failure(error): Validation or database error.

        Side Effects:
            - Publishes ProviderConnectionAttempted event (always)
            - Publishes ProviderConnectionSucceeded event (on success)
            - Publishes ProviderConnectionFailed event (on failure)
            - Creates ProviderConnection in database (on success)
        """
        # Step 1: Emit ATTEMPTED event
        await self._event_bus.publish(
            ProviderConnectionAttempted(
                event_id=uuid7(),
                occurred_at=datetime.now(UTC),
                user_id=cmd.user_id,
                provider_id=cmd.provider_id,
                provider_slug=cmd.provider_slug,
            )
        )

        try:
            # Step 2: Validate credentials
            if cmd.credentials is None:
                await self._emit_failed(cmd, ConnectProviderError.INVALID_CREDENTIALS)
                return Failure(error=ConnectProviderError.INVALID_CREDENTIALS)

            # Step 3: Validate provider_slug
            if not cmd.provider_slug or len(cmd.provider_slug) > 50:
                await self._emit_failed(cmd, ConnectProviderError.INVALID_PROVIDER_SLUG)
                return Failure(error=ConnectProviderError.INVALID_PROVIDER_SLUG)

            # Step 4: Create connection entity
            connection_id = uuid7()
            now = datetime.now(UTC)

            connection = ProviderConnection(
                id=connection_id,
                user_id=cmd.user_id,
                provider_id=cmd.provider_id,
                provider_slug=cmd.provider_slug,
                status=ConnectionStatus.ACTIVE,
                alias=cmd.alias,
                credentials=cmd.credentials,
                connected_at=now,
                created_at=now,
                updated_at=now,
            )

            # Step 5: Save to database
            await self._connection_repo.save(connection)

            # Step 6: Emit SUCCEEDED event
            await self._event_bus.publish(
                ProviderConnectionSucceeded(
                    event_id=uuid7(),
                    occurred_at=datetime.now(UTC),
                    user_id=cmd.user_id,
                    connection_id=connection_id,
                    provider_id=cmd.provider_id,
                    provider_slug=cmd.provider_slug,
                )
            )

            return Success(value=connection_id)

        except Exception as e:
            # Catch-all for database errors
            error_msg = f"{ConnectProviderError.DATABASE_ERROR}: {str(e)}"
            await self._emit_failed(cmd, error_msg)
            return Failure(error=error_msg)

    async def _emit_failed(self, cmd: ConnectProvider, reason: str) -> None:
        """Emit ProviderConnectionFailed event.

        Args:
            cmd: Original command.
            reason: Failure reason.
        """
        await self._event_bus.publish(
            ProviderConnectionFailed(
                event_id=uuid7(),
                occurred_at=datetime.now(UTC),
                user_id=cmd.user_id,
                provider_id=cmd.provider_id,
                provider_slug=cmd.provider_slug,
                reason=reason,
            )
        )
