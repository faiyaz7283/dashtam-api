"""Provider domain events (Phase 2 - Domain Layer).

Pattern: 3 events per workflow (ATTEMPTED → SUCCEEDED/FAILED)
- *Attempted: Action initiated (before business logic)
- *Succeeded: Operation completed successfully (after commit)
- *Failed: Operation failed (after rollback)

Workflows:
1. Provider Connection (user connects to provider)
2. Provider Disconnection (user disconnects from provider)
3. Provider Token Refresh (system refreshes credentials)

Handlers:
- LoggingEventHandler: ALL events
- AuditEventHandler: ALL events
- EmailEventHandler: SUCCEEDED only (connection/disconnection notifications)

Reference:
    - docs/architecture/provider-domain-model.md
"""

from dataclasses import dataclass
from uuid import UUID

from src.domain.events.base_event import DomainEvent


# ═══════════════════════════════════════════════════════════════
# Provider Connection (Workflow 1)
# ═══════════════════════════════════════════════════════════════


@dataclass(frozen=True, kw_only=True)
class ProviderConnectionAttempted(DomainEvent):
    """Provider connection attempt initiated.

    Emitted when user starts the provider connection flow
    (e.g., OAuth redirect initiated).

    Triggers:
    - LoggingEventHandler: Log attempt
    - AuditEventHandler: Record PROVIDER_CONNECTION_ATTEMPTED

    Attributes:
        user_id: User initiating connection.
        provider_id: Provider being connected to.
        provider_slug: Provider identifier for logging.
    """

    user_id: UUID
    provider_id: UUID
    provider_slug: str


@dataclass(frozen=True, kw_only=True)
class ProviderConnectionSucceeded(DomainEvent):
    """Provider connection completed successfully.

    Emitted after successful authentication and credential storage.

    Triggers:
    - LoggingEventHandler: Log success
    - AuditEventHandler: Record PROVIDER_CONNECTED
    - EmailEventHandler: Send provider connected notification

    Attributes:
        user_id: User who connected.
        connection_id: New connection ID.
        provider_id: Provider connected to.
        provider_slug: Provider identifier for logging.

    Note:
        NEVER include credentials in events.
    """

    user_id: UUID
    connection_id: UUID
    provider_id: UUID
    provider_slug: str


@dataclass(frozen=True, kw_only=True)
class ProviderConnectionFailed(DomainEvent):
    """Provider connection failed.

    Emitted when authentication fails, user cancels, or other error.

    Triggers:
    - LoggingEventHandler: Log failure
    - AuditEventHandler: Record PROVIDER_CONNECTION_FAILED

    Attributes:
        user_id: User who attempted connection.
        provider_id: Provider that failed to connect.
        provider_slug: Provider identifier for logging.
        reason: Failure reason (e.g., "user_cancelled", "oauth_error",
            "invalid_credentials", "provider_unavailable").
    """

    user_id: UUID
    provider_id: UUID
    provider_slug: str
    reason: str


# ═══════════════════════════════════════════════════════════════
# Provider Disconnection (Workflow 2)
# ═══════════════════════════════════════════════════════════════


@dataclass(frozen=True, kw_only=True)
class ProviderDisconnectionAttempted(DomainEvent):
    """Provider disconnection attempt initiated.

    Emitted when user requests to disconnect a provider.

    Triggers:
    - LoggingEventHandler: Log attempt
    - AuditEventHandler: Record PROVIDER_DISCONNECTION_ATTEMPTED

    Attributes:
        user_id: User initiating disconnection.
        connection_id: Connection being disconnected.
        provider_id: Provider being disconnected.
        provider_slug: Provider identifier for logging.
    """

    user_id: UUID
    connection_id: UUID
    provider_id: UUID
    provider_slug: str


@dataclass(frozen=True, kw_only=True)
class ProviderDisconnectionSucceeded(DomainEvent):
    """Provider disconnection completed successfully.

    Emitted after credentials are cleared and connection is removed.

    Triggers:
    - LoggingEventHandler: Log success
    - AuditEventHandler: Record PROVIDER_DISCONNECTED
    - EmailEventHandler: Send provider disconnected notification

    Attributes:
        user_id: User who disconnected.
        connection_id: Connection that was disconnected.
        provider_id: Provider that was disconnected.
        provider_slug: Provider identifier for logging.
    """

    user_id: UUID
    connection_id: UUID
    provider_id: UUID
    provider_slug: str


@dataclass(frozen=True, kw_only=True)
class ProviderDisconnectionFailed(DomainEvent):
    """Provider disconnection failed.

    Emitted when disconnection fails (rare - usually database error).

    Triggers:
    - LoggingEventHandler: Log failure
    - AuditEventHandler: Record PROVIDER_DISCONNECTION_FAILED

    Attributes:
        user_id: User who attempted disconnection.
        connection_id: Connection that failed to disconnect.
        provider_id: Provider that failed to disconnect.
        provider_slug: Provider identifier for logging.
        reason: Failure reason (e.g., "database_error", "connection_not_found").
    """

    user_id: UUID
    connection_id: UUID
    provider_id: UUID
    provider_slug: str
    reason: str


# ═══════════════════════════════════════════════════════════════
# Provider Token Refresh (Workflow 3)
# ═══════════════════════════════════════════════════════════════


@dataclass(frozen=True, kw_only=True)
class ProviderTokenRefreshAttempted(DomainEvent):
    """Provider token refresh attempt initiated.

    Emitted when system attempts to refresh expiring credentials.
    Typically triggered by background job or proactive refresh.

    Triggers:
    - LoggingEventHandler: Log attempt
    - AuditEventHandler: Record PROVIDER_TOKEN_REFRESH_ATTEMPTED

    Attributes:
        user_id: User whose credentials are being refreshed.
        connection_id: Connection being refreshed.
        provider_id: Provider whose tokens are refreshing.
        provider_slug: Provider identifier for logging.
    """

    user_id: UUID
    connection_id: UUID
    provider_id: UUID
    provider_slug: str


@dataclass(frozen=True, kw_only=True)
class ProviderTokenRefreshSucceeded(DomainEvent):
    """Provider token refresh completed successfully.

    Emitted after new credentials are stored.

    Triggers:
    - LoggingEventHandler: Log success
    - AuditEventHandler: Record PROVIDER_TOKEN_REFRESHED

    Attributes:
        user_id: User whose credentials were refreshed.
        connection_id: Connection that was refreshed.
        provider_id: Provider whose tokens were refreshed.
        provider_slug: Provider identifier for logging.

    Note:
        NEVER include credentials in events.
    """

    user_id: UUID
    connection_id: UUID
    provider_id: UUID
    provider_slug: str


@dataclass(frozen=True, kw_only=True)
class ProviderTokenRefreshFailed(DomainEvent):
    """Provider token refresh failed.

    Emitted when refresh fails - user may need to re-authenticate.

    Triggers:
    - LoggingEventHandler: Log failure
    - AuditEventHandler: Record PROVIDER_TOKEN_REFRESH_FAILED
    - EmailEventHandler: Notify user of required action (if needs_reauth)

    Attributes:
        user_id: User whose credentials failed to refresh.
        connection_id: Connection that failed to refresh.
        provider_id: Provider whose tokens failed to refresh.
        provider_slug: Provider identifier for logging.
        reason: Failure reason (e.g., "refresh_token_expired",
            "provider_revoked", "network_error").
        needs_user_action: Whether user must re-authenticate.
    """

    user_id: UUID
    connection_id: UUID
    provider_id: UUID
    provider_slug: str
    reason: str
    needs_user_action: bool = False
