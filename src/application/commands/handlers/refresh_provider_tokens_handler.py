"""RefreshProviderTokens command handler.

Handles provider credential refresh. Updates credentials for an
existing active connection after successful token refresh.

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
from typing import cast
from uuid import UUID

from uuid_extensions import uuid7

from src.application.commands.provider_commands import RefreshProviderTokens
from src.core.result import Failure, Result, Success
from src.domain.events.provider_events import (
    ProviderTokenRefreshAttempted,
    ProviderTokenRefreshFailed,
    ProviderTokenRefreshSucceeded,
)
from src.domain.protocols.event_bus_protocol import EventBusProtocol
from src.domain.protocols.provider_connection_repository import (
    ProviderConnectionRepository,
)


class RefreshProviderTokensError:
    """RefreshProviderTokens-specific errors."""

    CONNECTION_NOT_FOUND = "Connection not found"
    INVALID_CREDENTIALS = "Invalid or missing credentials"
    NOT_ACTIVE = "Connection is not active"
    DATABASE_ERROR = "Database error occurred"


class RefreshProviderTokensHandler:
    """Handler for RefreshProviderTokens command.

    Updates credentials for an existing active connection. The actual
    token refresh with the provider happens in infrastructure layer
    before this handler is called.

    Dependencies (injected via constructor):
        - ProviderConnectionRepository: For persistence
        - EventBusProtocol: For domain events
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

    async def handle(self, cmd: RefreshProviderTokens) -> Result[None, str]:
        """Handle RefreshProviderTokens command.

        Finds the connection, verifies it's active, and updates credentials.

        Args:
            cmd: RefreshProviderTokens command with connection ID and new credentials.

        Returns:
            Success(None): Credentials updated successfully.
            Failure(error): Connection not found, not active, or database error.

        Side Effects:
            - Publishes ProviderTokenRefreshAttempted event (always)
            - Publishes ProviderTokenRefreshSucceeded event (on success)
            - Publishes ProviderTokenRefreshFailed event (on failure)
            - Updates ProviderConnection credentials in database (on success)
        """
        # Fetch connection to get user and provider details for events
        connection = await self._connection_repo.find_by_id(cmd.connection_id)

        # Use placeholders if connection not found
        user_id = connection.user_id if connection else cmd.connection_id
        provider_id = connection.provider_id if connection else cmd.connection_id
        provider_slug = connection.provider_slug if connection else "unknown"

        # Step 1: Emit ATTEMPTED event
        await self._event_bus.publish(
            ProviderTokenRefreshAttempted(
                event_id=uuid7(),
                occurred_at=datetime.now(UTC),
                user_id=user_id,
                connection_id=cmd.connection_id,
                provider_id=provider_id,
                provider_slug=provider_slug,
            )
        )

        try:
            # Step 2: Verify connection exists
            if connection is None:
                await self._emit_failed(
                    cmd,
                    user_id,
                    provider_id,
                    provider_slug,
                    RefreshProviderTokensError.CONNECTION_NOT_FOUND,
                    needs_user_action=False,
                )
                return cast(Result[None, str], Failure(error=RefreshProviderTokensError.CONNECTION_NOT_FOUND))

            # Step 3: Validate credentials
            if cmd.credentials is None:
                await self._emit_failed(
                    cmd,
                    connection.user_id,
                    connection.provider_id,
                    connection.provider_slug,
                    RefreshProviderTokensError.INVALID_CREDENTIALS,
                    needs_user_action=False,
                )
                return cast(Result[None, str], Failure(error=RefreshProviderTokensError.INVALID_CREDENTIALS))

            # Step 4: Update credentials (domain validates ACTIVE status)
            result = connection.update_credentials(cmd.credentials)

            match result:
                case Failure():
                    # Connection is not active
                    await self._emit_failed(
                        cmd,
                        connection.user_id,
                        connection.provider_id,
                        connection.provider_slug,
                        RefreshProviderTokensError.NOT_ACTIVE,
                        needs_user_action=True,
                    )
                    return cast(Result[None, str], Failure(error=RefreshProviderTokensError.NOT_ACTIVE))
                case _:
                    pass  # Success case continues

            # Step 5: Save to database
            await self._connection_repo.save(connection)

            # Step 6: Emit SUCCEEDED event
            await self._event_bus.publish(
                ProviderTokenRefreshSucceeded(
                    event_id=uuid7(),
                    occurred_at=datetime.now(UTC),
                    user_id=connection.user_id,
                    connection_id=cmd.connection_id,
                    provider_id=connection.provider_id,
                    provider_slug=connection.provider_slug,
                )
            )

            return Success(value=None)

        except Exception as e:
            # Catch-all for database errors
            error_msg = f"{RefreshProviderTokensError.DATABASE_ERROR}: {str(e)}"
            await self._emit_failed(
                cmd,
                user_id,
                provider_id,
                provider_slug,
                error_msg,
                needs_user_action=False,
            )
            return cast(Result[None, str], Failure(error=error_msg))

    async def _emit_failed(
        self,
        cmd: RefreshProviderTokens,
        user_id: UUID,
        provider_id: UUID,
        provider_slug: str,
        reason: str,
        needs_user_action: bool,
    ) -> None:
        """Emit ProviderTokenRefreshFailed event.

        Args:
            cmd: Original command.
            user_id: User UUID.
            provider_id: Provider UUID.
            provider_slug: Provider slug for logging.
            reason: Failure reason.
            needs_user_action: Whether user needs to re-authenticate.
        """
        await self._event_bus.publish(
            ProviderTokenRefreshFailed(
                event_id=uuid7(),
                occurred_at=datetime.now(UTC),
                user_id=user_id,
                connection_id=cmd.connection_id,
                provider_id=provider_id,
                provider_slug=provider_slug,
                reason=reason,
                needs_user_action=needs_user_action,
            )
        )
