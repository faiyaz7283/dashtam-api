"""Provider commands (CQRS write operations).

Commands represent user intent to change provider connection state.
All commands are immutable (frozen=True) and use keyword-only arguments (kw_only=True).

Pattern:
- Commands are data containers (no logic)
- Handlers execute business logic
- Commands don't return values (handlers return Result types)

Reference:
    - docs/architecture/cqrs-pattern.md
    - docs/architecture/provider-domain-model.md
"""

from dataclasses import dataclass
from uuid import UUID

from src.domain.value_objects.provider_credentials import ProviderCredentials


@dataclass(frozen=True, kw_only=True)
class ConnectProvider:
    """Connect user to a financial provider.

    Initiates or completes a provider connection. The actual OAuth/API
    authentication happens in infrastructure layer - this command receives
    the resulting credentials and creates the connection record.

    State Transition: PENDING → ACTIVE (or creates new connection)

    Attributes:
        user_id: User initiating the connection.
        provider_id: Provider being connected to (from provider registry).
        provider_slug: Provider identifier for logging (e.g., "schwab").
        credentials: Encrypted credentials from successful authentication.
        alias: Optional user-defined nickname (e.g., "My Schwab IRA").

    Example:
        >>> command = ConnectProvider(
        ...     user_id=user_id,
        ...     provider_id=schwab_provider_id,
        ...     provider_slug="schwab",
        ...     credentials=encrypted_oauth_credentials,
        ...     alias="Personal Account",
        ... )
        >>> result = await handler.handle(command)
    """

    user_id: UUID
    provider_id: UUID
    provider_slug: str
    credentials: ProviderCredentials
    alias: str | None = None


@dataclass(frozen=True, kw_only=True)
class DisconnectProvider:
    """Disconnect user from a financial provider.

    Removes an existing provider connection. This marks the connection
    as DISCONNECTED and clears credentials. The record is kept for
    audit trail purposes.

    State Transition: any → DISCONNECTED

    Attributes:
        user_id: User requesting disconnection (for ownership verification).
        connection_id: Connection to disconnect.

    Example:
        >>> command = DisconnectProvider(
        ...     user_id=user_id,
        ...     connection_id=connection_id,
        ... )
        >>> result = await handler.handle(command)
    """

    user_id: UUID
    connection_id: UUID


@dataclass(frozen=True, kw_only=True)
class RefreshProviderTokens:
    """Refresh provider credentials after token refresh.

    Updates credentials for an existing active connection. Called after
    successfully refreshing OAuth tokens or API keys.

    State Transition: ACTIVE → ACTIVE (credentials updated)

    Attributes:
        connection_id: Connection to update.
        credentials: New encrypted credentials from refresh.

    Note:
        This command does NOT perform the actual token refresh with the
        provider. The infrastructure layer handles that and provides
        the new credentials to this command.

    Example:
        >>> command = RefreshProviderTokens(
        ...     connection_id=connection_id,
        ...     credentials=refreshed_credentials,
        ... )
        >>> result = await handler.handle(command)
    """

    connection_id: UUID
    credentials: ProviderCredentials
