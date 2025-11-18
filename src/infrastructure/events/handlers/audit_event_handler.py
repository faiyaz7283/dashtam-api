"""Audit event handler for domain events.

This module implements audit trail recording for all critical domain events.
Maps each event to the appropriate AuditAction enum and creates audit records
with full context for PCI-DSS, SOC 2, and GDPR compliance.

Event → Audit Action Mapping:
    - UserRegistrationAttempted → USER_REGISTRATION_ATTEMPTED
    - UserRegistrationSucceeded → USER_REGISTERED
    - UserRegistrationFailed → USER_REGISTRATION_FAILED
    - UserPasswordChangeAttempted → USER_PASSWORD_CHANGE_ATTEMPTED
    - UserPasswordChangeSucceeded → USER_PASSWORD_CHANGED
    - UserPasswordChangeFailed → USER_PASSWORD_CHANGE_FAILED
    - ProviderConnectionAttempted → PROVIDER_CONNECTION_ATTEMPTED
    - ProviderConnectionSucceeded → PROVIDER_CONNECTED
    - ProviderConnectionFailed → PROVIDER_CONNECTION_FAILED
    - TokenRefreshAttempted → PROVIDER_TOKEN_REFRESH_ATTEMPTED
    - TokenRefreshSucceeded → PROVIDER_TOKEN_REFRESHED
    - TokenRefreshFailed → PROVIDER_TOKEN_REFRESH_FAILED

Audit Record Structure:
    - action: AuditAction enum (machine-readable)
    - user_id: UUID (when available - None for ATTEMPTED registration)
    - resource_type: Resource being acted upon (user, provider, token)
    - resource_id: Resource UUID (when available)
    - context: JSONB freeform dict with event-specific fields
    - ip_address: Client IP (for security audit)

Usage:
    >>> # Container wires up subscriptions at startup
    >>> event_bus = get_event_bus()
    >>> audit_handler = AuditEventHandler(audit=get_audit())
    >>>
    >>> # Subscribe to all 12 events
    >>> event_bus.subscribe(UserRegistrationAttempted, audit_handler.handle_user_registration_attempted)
    >>> # ... and 11 more subscriptions

Reference:
    - docs/architecture/domain-events-architecture.md (Lines 1172-1303)
    - docs/architecture/audit-trail-architecture.md
"""

from typing import Any

from src.domain.enums.audit_action import AuditAction
from src.domain.events.authentication_events import (
    ProviderConnectionAttempted,
    ProviderConnectionFailed,
    ProviderConnectionSucceeded,
    TokenRefreshAttempted,
    TokenRefreshFailed,
    TokenRefreshSucceeded,
    UserPasswordChangeAttempted,
    UserPasswordChangeFailed,
    UserPasswordChangeSucceeded,
    UserRegistrationAttempted,
    UserRegistrationFailed,
    UserRegistrationSucceeded,
)
from src.infrastructure.persistence.database import Database


class AuditEventHandler:
    """Event handler for audit trail recording.

    Maps domain events to AuditAction enums and creates audit records with
    full context for compliance (PCI-DSS, SOC 2, GDPR). Supports ATTEMPT →
    OUTCOME audit pattern for security event tracking.

    Manages its own database sessions for audit writes to ensure proper
    session lifecycle (commit per audit write, independent of business logic).

    Attributes:
        _database: Database instance for creating audit sessions.

    Example:
        >>> # Create handler
        >>> handler = AuditEventHandler(database=get_database())
        >>>
        >>> # Subscribe to events (in container)
        >>> event_bus.subscribe(UserRegistered, handler.handle_user_registration_succeeded)
        >>>
        >>> # Events automatically audited when published
        >>> await event_bus.publish(UserRegistrationSucceeded(
        ...     user_id=uuid4(),
        ...     email="test@example.com"
        ... ))
        >>> # Audit record created: action=USER_REGISTERED, user_id=..., context={email: ...}
    """

    def __init__(self, database: Database) -> None:
        """Initialize audit handler with database instance.

        Args:
            database: Database instance from container. Handler creates
                audit sessions per event for proper lifecycle management.

        Example:
            >>> from src.core.container import get_database
            >>> database = get_database()
            >>> handler = AuditEventHandler(database=database)
        """
        self._database = database

    async def _create_audit_record(self, **kwargs: Any) -> None:
        """Helper to create audit record with own session lifecycle.

        Args:
            **kwargs: Arguments to pass to audit.record().

        Note:
            Creates new database session, writes audit record, commits, closes.
            This ensures audit writes are independent of business logic transactions.
        """
        from src.infrastructure.audit.postgres_adapter import PostgresAuditAdapter

        async with self._database.get_session() as session:
            audit = PostgresAuditAdapter(session=session)
            await audit.record(**kwargs)
            # Session auto-commits on context exit (success path)

    # =========================================================================
    # User Registration Event Handlers
    # =========================================================================

    async def handle_user_registration_attempted(
        self,
        event: UserRegistrationAttempted,
    ) -> None:
        """Record user registration attempt audit (ATTEMPT).

        Args:
            event: UserRegistrationAttempted event with email and IP.

        Audit Record:
            - action: USER_REGISTRATION_ATTEMPTED
            - user_id: None (user not created yet)
            - resource_type: "user"
            - context: {email, registration_method: "email"}
        """
        await self._create_audit_record(
            action=AuditAction.USER_REGISTRATION_ATTEMPTED,
            user_id=None,  # User not created yet
            resource_type="user",
            resource_id=None,
            ip_address=event.ip_address,
            context={
                "event_id": str(event.event_id),
                "email": event.email,
                "registration_method": "email",
            },
        )

    async def handle_user_registration_succeeded(
        self,
        event: UserRegistrationSucceeded,
    ) -> None:
        """Record successful user registration audit (SUCCESS).

        Args:
            event: UserRegistrationSucceeded event with user_id and email.

        Audit Record:
            - action: USER_REGISTERED
            - user_id: UUID of created user
            - resource_type: "user"
            - resource_id: user_id
            - context: {email, registration_method: "email"}
        """
        await self._create_audit_record(
            action=AuditAction.USER_REGISTERED,
            user_id=event.user_id,
            resource_type="user",
            resource_id=event.user_id,  # UUID, not string
            context={
                "event_id": str(event.event_id),
                "email": event.email,
                "registration_method": "email",
                "email_verified": False,  # Email verification happens separately
            },
        )

    async def handle_user_registration_failed(
        self,
        event: UserRegistrationFailed,
    ) -> None:
        """Record failed user registration audit (FAILURE).

        Args:
            event: UserRegistrationFailed event with error details.

        Audit Record:
            - action: USER_REGISTRATION_FAILED
            - user_id: None (user not created)
            - resource_type: "user"
            - context: {email, reason (error_code)}
        """
        await self._create_audit_record(
            action=AuditAction.USER_REGISTRATION_FAILED,
            user_id=None,  # User not created
            resource_type="user",
            resource_id=None,
            ip_address=event.ip_address,
            context={
                "event_id": str(event.event_id),
                "email": event.email,
                "reason": event.error_code,
                "error_message": event.error_message,
            },
        )

    # =========================================================================
    # User Password Change Event Handlers
    # =========================================================================

    async def handle_user_password_change_attempted(
        self,
        event: UserPasswordChangeAttempted,
    ) -> None:
        """Record password change attempt audit (ATTEMPT).

        Args:
            event: UserPasswordChangeAttempted event with user_id.

        Audit Record:
            - action: USER_PASSWORD_CHANGE_ATTEMPTED
            - user_id: UUID of user attempting change
            - resource_type: "user"
            - resource_id: user_id
            - context: {initiated_by}
        """
        await self._create_audit_record(
            action=AuditAction.USER_PASSWORD_CHANGE_ATTEMPTED,
            user_id=event.user_id,
            resource_type="user",
            resource_id=event.user_id,  # UUID, not string
            ip_address=event.ip_address,
            context={
                "event_id": str(event.event_id),
                "initiated_by": event.initiated_by,
            },
        )

    async def handle_user_password_change_succeeded(
        self,
        event: UserPasswordChangeSucceeded,
    ) -> None:
        """Record successful password change audit (SUCCESS).

        Args:
            event: UserPasswordChangeSucceeded event with user_id.

        Audit Record:
            - action: USER_PASSWORD_CHANGED
            - user_id: UUID of user whose password was changed
            - resource_type: "user"
            - resource_id: user_id
            - context: {initiated_by, method: "self_service"}
        """
        await self._create_audit_record(
            action=AuditAction.USER_PASSWORD_CHANGED,
            user_id=event.user_id,
            resource_type="user",
            resource_id=event.user_id,  # UUID, not string
            context={
                "event_id": str(event.event_id),
                "initiated_by": event.initiated_by,
                "method": "self_service"
                if event.initiated_by == "user"
                else "admin_reset",
            },
        )

    async def handle_user_password_change_failed(
        self,
        event: UserPasswordChangeFailed,
    ) -> None:
        """Record failed password change audit (FAILURE).

        Args:
            event: UserPasswordChangeFailed event with error details.

        Audit Record:
            - action: USER_PASSWORD_CHANGE_FAILED
            - user_id: UUID of user whose password change failed
            - resource_type: "user"
            - resource_id: user_id
            - context: {reason (error_code), initiated_by}
        """
        await self._create_audit_record(
            action=AuditAction.USER_PASSWORD_CHANGE_FAILED,
            user_id=event.user_id,
            resource_type="user",
            resource_id=event.user_id,  # UUID, not string
            ip_address=event.ip_address,
            context={
                "event_id": str(event.event_id),
                "reason": event.error_code,
                "error_message": event.error_message,
                "initiated_by": event.initiated_by,
            },
        )

    # =========================================================================
    # Provider Connection Event Handlers
    # =========================================================================

    async def handle_provider_connection_attempted(
        self,
        event: ProviderConnectionAttempted,
    ) -> None:
        """Record provider connection attempt audit (ATTEMPT).

        Args:
            event: ProviderConnectionAttempted event with provider name.

        Audit Record:
            - action: PROVIDER_CONNECTION_ATTEMPTED
            - user_id: UUID of user attempting connection
            - resource_type: "provider"
            - context: {provider_name, connection_method: "oauth"}
        """
        await self._create_audit_record(
            action=AuditAction.PROVIDER_CONNECTION_ATTEMPTED,
            user_id=event.user_id,
            resource_type="provider",
            resource_id=None,  # Provider not created yet
            ip_address=event.ip_address,
            context={
                "event_id": str(event.event_id),
                "provider_name": event.provider_name,
                "connection_method": "oauth",
            },
        )

    async def handle_provider_connection_succeeded(
        self,
        event: ProviderConnectionSucceeded,
    ) -> None:
        """Record successful provider connection audit (SUCCESS).

        Args:
            event: ProviderConnectionSucceeded event with provider_id.

        Audit Record:
            - action: PROVIDER_CONNECTED
            - user_id: UUID of user who connected provider
            - resource_type: "provider"
            - resource_id: provider_id
            - context: {provider_name, connection_method: "oauth"}
        """
        await self._create_audit_record(
            action=AuditAction.PROVIDER_CONNECTED,
            user_id=event.user_id,
            resource_type="provider",
            resource_id=event.provider_id,  # UUID, not string
            context={
                "event_id": str(event.event_id),
                "provider_name": event.provider_name,
                "connection_method": "oauth",
            },
        )

    async def handle_provider_connection_failed(
        self,
        event: ProviderConnectionFailed,
    ) -> None:
        """Record failed provider connection audit (FAILURE).

        Args:
            event: ProviderConnectionFailed event with error details.

        Audit Record:
            - action: PROVIDER_CONNECTION_FAILED
            - user_id: UUID of user whose connection failed
            - resource_type: "provider"
            - context: {provider_name, reason (error_code), error_code}
        """
        await self._create_audit_record(
            action=AuditAction.PROVIDER_CONNECTION_FAILED,
            user_id=event.user_id,
            resource_type="provider",
            resource_id=None,  # Provider not created
            context={
                "event_id": str(event.event_id),
                "provider_name": event.provider_name,
                "reason": event.error_code,
                "error_code": event.error_code,
                "error_message": event.error_message,
            },
        )

    # =========================================================================
    # Token Refresh Event Handlers
    # =========================================================================

    async def handle_token_refresh_attempted(
        self,
        event: TokenRefreshAttempted,
    ) -> None:
        """Record token refresh attempt audit (ATTEMPT).

        Args:
            event: TokenRefreshAttempted event with provider details.

        Audit Record:
            - action: PROVIDER_TOKEN_REFRESH_ATTEMPTED
            - user_id: UUID of user whose token is being refreshed
            - resource_type: "token"
            - resource_id: provider_id
            - context: {provider_name, token_type: "access"}
        """
        await self._create_audit_record(
            action=AuditAction.PROVIDER_TOKEN_REFRESH_ATTEMPTED,
            user_id=event.user_id,
            resource_type="token",
            resource_id=event.provider_id,  # UUID, not string
            context={
                "event_id": str(event.event_id),
                "provider_name": event.provider_name,
                "token_type": "access",
            },
        )

    async def handle_token_refresh_succeeded(
        self,
        event: TokenRefreshSucceeded,
    ) -> None:
        """Record successful token refresh audit (SUCCESS).

        Args:
            event: TokenRefreshSucceeded event with provider details.

        Audit Record:
            - action: PROVIDER_TOKEN_REFRESHED
            - user_id: UUID of user whose token was refreshed
            - resource_type: "token"
            - resource_id: provider_id
            - context: {provider_name, token_type: "access"}
        """
        await self._create_audit_record(
            action=AuditAction.PROVIDER_TOKEN_REFRESHED,
            user_id=event.user_id,
            resource_type="token",
            resource_id=event.provider_id,  # UUID, not string
            context={
                "event_id": str(event.event_id),
                "provider_name": event.provider_name,
                "token_type": "access",
            },
        )

    async def handle_token_refresh_failed(
        self,
        event: TokenRefreshFailed,
    ) -> None:
        """Record failed token refresh audit (FAILURE).

        Args:
            event: TokenRefreshFailed event with error details.

        Audit Record:
            - action: PROVIDER_TOKEN_REFRESH_FAILED
            - user_id: UUID of user whose token refresh failed
            - resource_type: "token"
            - resource_id: provider_id
            - context: {provider_name, error_code, error_message}
        """
        await self._create_audit_record(
            action=AuditAction.PROVIDER_TOKEN_REFRESH_FAILED,
            user_id=event.user_id,
            resource_type="token",
            resource_id=event.provider_id,  # UUID, not string
            context={
                "event_id": str(event.event_id),
                "provider_name": event.provider_name,
                "error_code": event.error_code,
                "error_message": event.error_message,
            },
        )
