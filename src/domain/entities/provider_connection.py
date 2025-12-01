"""Provider connection domain entity.

Represents the connection between a user and a financial data provider.
Authentication-agnostic - domain has no knowledge of OAuth, API keys, etc.

Architecture:
    - Pure domain entity (no infrastructure dependencies)
    - Uses Result types (railway-oriented programming)
    - NO event collection (handlers create events)
    - State machine with validated transitions

Reference:
    - docs/architecture/provider-domain-model.md

Usage:
    from uuid_extensions import uuid7
    from src.domain.entities import ProviderConnection
    from src.domain.enums import ConnectionStatus

    connection = ProviderConnection(
        id=uuid7(),
        user_id=user.id,
        provider_id=provider_uuid,
        provider_slug="schwab",
        status=ConnectionStatus.PENDING,
    )

    # After successful authentication
    result = connection.mark_connected(credentials)
    match result:
        case Success(_):
            assert connection.is_connected()
        case Failure(error):
            # Handle error
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID

from src.core.result import Failure, Result, Success
from src.domain.enums.connection_status import ConnectionStatus
from src.domain.errors.provider_connection_error import ProviderConnectionError
from src.domain.value_objects.provider_credentials import ProviderCredentials


@dataclass
class ProviderConnection:
    """Connection between a user and a financial data provider.

    Represents the user's connection to an external provider like Schwab,
    Chase, or Plaid. The connection tracks status, credentials, and sync state.

    Authentication Agnostic:
        Domain layer has no knowledge of authentication mechanisms.
        Credentials are stored as opaque encrypted blobs with a type hint
        for the infrastructure layer to handle.

    State Machine:
        PENDING → ACTIVE ↔ EXPIRED/REVOKED → DISCONNECTED

    Railway-Oriented Programming:
        All state transition methods return Result[None, str] instead of
        raising exceptions. Use pattern matching to handle success/failure.

    Attributes:
        id: Unique connection identifier.
        user_id: Owning user's ID.
        provider_id: FK to Provider registry (infrastructure).
        provider_slug: Denormalized provider identifier for logging.
        alias: User-defined nickname (e.g., "My Schwab IRA").
        status: Current connection status.
        credentials: Encrypted credentials (None when pending/disconnected).
        connected_at: When connection was first established.
        last_sync_at: Last successful data synchronization.
        created_at: Record creation timestamp.
        updated_at: Last modification timestamp.

    Example:
        >>> conn = ProviderConnection(
        ...     id=uuid7(),
        ...     user_id=user_id,
        ...     provider_id=provider_id,
        ...     provider_slug="schwab",
        ...     status=ConnectionStatus.PENDING,
        ... )
        >>> conn.is_connected()
        False
        >>> result = conn.mark_connected(credentials)
        >>> match result:
        ...     case Success(_): print("Connected!")
        ...     case Failure(e): print(f"Error: {e}")
    """

    id: UUID
    user_id: UUID
    provider_id: UUID
    provider_slug: str
    status: ConnectionStatus
    alias: str | None = None
    credentials: ProviderCredentials | None = None
    connected_at: datetime | None = None
    last_sync_at: datetime | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        """Validate connection after initialization.

        Raises:
            ValueError: If required fields are invalid.

        Note:
            __post_init__ still raises ValueError for construction errors.
            These are programming errors, not business logic failures.
        """
        if not self.provider_slug:
            raise ValueError(ProviderConnectionError.INVALID_PROVIDER_SLUG)

        if len(self.provider_slug) > 50:
            raise ValueError(ProviderConnectionError.INVALID_PROVIDER_SLUG)

        if self.alias is not None and len(self.alias) > 100:
            raise ValueError(ProviderConnectionError.INVALID_ALIAS)

        # Validate status consistency
        if self.status == ConnectionStatus.ACTIVE and self.credentials is None:
            raise ValueError(ProviderConnectionError.ACTIVE_WITHOUT_CREDENTIALS)

    # -------------------------------------------------------------------------
    # Query Methods (Read-Only)
    # -------------------------------------------------------------------------

    def is_connected(self) -> bool:
        """Check if connection is active and usable.

        Returns:
            bool: True if status is ACTIVE and credentials exist.
        """
        return self.status == ConnectionStatus.ACTIVE and self.credentials is not None

    def needs_reauthentication(self) -> bool:
        """Check if connection requires user to re-authenticate.

        Returns:
            bool: True if status is EXPIRED, REVOKED, or FAILED.
        """
        return self.status in ConnectionStatus.needs_reauth_states()

    def is_credentials_expired(self) -> bool:
        """Check if credentials have passed expiration time.

        Returns:
            bool: True if credentials exist and are expired.
        """
        if self.credentials is None:
            return False
        return self.credentials.is_expired()

    def is_credentials_expiring_soon(self) -> bool:
        """Check if credentials will expire within 5 minutes.

        Returns:
            bool: True if credentials exist and expiring soon.
        """
        if self.credentials is None:
            return False
        return self.credentials.is_expiring_soon()

    def can_sync(self) -> bool:
        """Check if connection can perform data synchronization.

        Returns:
            bool: True if connected and credentials not expired.
        """
        return self.is_connected() and not self.is_credentials_expired()

    # -------------------------------------------------------------------------
    # State Transition Methods (Return Result)
    # -------------------------------------------------------------------------

    def mark_connected(self, credentials: ProviderCredentials) -> Result[None, str]:
        """Transition to ACTIVE status with credentials.

        Called after successful authentication. Updates status and
        records connection timestamp.

        Args:
            credentials: Encrypted credentials from provider.

        Returns:
            Success(None): Transition successful.
            Failure(error): Credentials missing or invalid state transition.

        Side Effects (on success):
            - Sets status to ACTIVE
            - Stores credentials
            - Sets connected_at if first connection
            - Updates updated_at
        """
        if credentials is None:
            return Failure(error=ProviderConnectionError.CREDENTIALS_REQUIRED)

        # Allow from PENDING, EXPIRED, REVOKED, FAILED
        allowed_from = [
            ConnectionStatus.PENDING,
            ConnectionStatus.EXPIRED,
            ConnectionStatus.REVOKED,
            ConnectionStatus.FAILED,
        ]
        if self.status not in allowed_from:
            return Failure(error=ProviderConnectionError.CANNOT_TRANSITION_TO_ACTIVE)

        self.status = ConnectionStatus.ACTIVE
        self.credentials = credentials
        self.updated_at = datetime.now(UTC)

        if self.connected_at is None:
            self.connected_at = datetime.now(UTC)

        return Success(value=None)

    def mark_disconnected(self) -> Result[None, str]:
        """Transition to DISCONNECTED status.

        Called when user explicitly removes the connection.
        Terminal state - credentials are cleared.

        Returns:
            Success(None): Transition successful (always succeeds).

        Side Effects:
            - Sets status to DISCONNECTED
            - Clears credentials
            - Updates updated_at
        """
        self.status = ConnectionStatus.DISCONNECTED
        self.credentials = None
        self.updated_at = datetime.now(UTC)
        return Success(value=None)

    def mark_expired(self) -> Result[None, str]:
        """Transition to EXPIRED status.

        Called when credentials have expired and cannot be refreshed.

        Returns:
            Success(None): Transition successful.
            Failure(error): Not currently ACTIVE.

        Side Effects (on success):
            - Sets status to EXPIRED
            - Updates updated_at
            - Does NOT clear credentials (may still contain refresh token)
        """
        if self.status != ConnectionStatus.ACTIVE:
            return Failure(error=ProviderConnectionError.CANNOT_TRANSITION_TO_EXPIRED)

        self.status = ConnectionStatus.EXPIRED
        self.updated_at = datetime.now(UTC)
        return Success(value=None)

    def mark_revoked(self) -> Result[None, str]:
        """Transition to REVOKED status.

        Called when user or provider explicitly revokes access.

        Returns:
            Success(None): Transition successful.
            Failure(error): Not currently ACTIVE.

        Side Effects (on success):
            - Sets status to REVOKED
            - Updates updated_at
            - Does NOT clear credentials (audit trail)
        """
        if self.status != ConnectionStatus.ACTIVE:
            return Failure(error=ProviderConnectionError.CANNOT_TRANSITION_TO_REVOKED)

        self.status = ConnectionStatus.REVOKED
        self.updated_at = datetime.now(UTC)
        return Success(value=None)

    def mark_failed(self) -> Result[None, str]:
        """Transition to FAILED status.

        Called when authentication attempt fails.

        Returns:
            Success(None): Transition successful.
            Failure(error): Not currently PENDING.

        Side Effects (on success):
            - Sets status to FAILED
            - Updates updated_at
        """
        if self.status != ConnectionStatus.PENDING:
            return Failure(error=ProviderConnectionError.CANNOT_TRANSITION_TO_FAILED)

        self.status = ConnectionStatus.FAILED
        self.updated_at = datetime.now(UTC)
        return Success(value=None)

    def update_credentials(self, credentials: ProviderCredentials) -> Result[None, str]:
        """Update credentials after token refresh.

        Called when credentials are refreshed without user interaction.

        Args:
            credentials: New encrypted credentials.

        Returns:
            Success(None): Update successful.
            Failure(error): Credentials missing or not ACTIVE.

        Side Effects (on success):
            - Updates credentials
            - Updates updated_at
        """
        if credentials is None:
            return Failure(error=ProviderConnectionError.CREDENTIALS_REQUIRED)

        if self.status != ConnectionStatus.ACTIVE:
            return Failure(error=ProviderConnectionError.NOT_CONNECTED)

        self.credentials = credentials
        self.updated_at = datetime.now(UTC)
        return Success(value=None)

    def record_sync(self) -> Result[None, str]:
        """Record successful data synchronization.

        Updates last_sync_at timestamp.

        Returns:
            Success(None): Sync recorded.
            Failure(error): Not currently ACTIVE.

        Side Effects (on success):
            - Updates last_sync_at
            - Updates updated_at
        """
        if self.status != ConnectionStatus.ACTIVE:
            return Failure(error=ProviderConnectionError.NOT_CONNECTED)

        self.last_sync_at = datetime.now(UTC)
        self.updated_at = datetime.now(UTC)
        return Success(value=None)
