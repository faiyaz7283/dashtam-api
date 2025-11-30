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
from src.domain.events.auth_events import (
    # User Password Change Events
    UserPasswordChangeAttempted,
    UserPasswordChangeFailed,
    UserPasswordChangeSucceeded,
    # User Registration Events
    UserRegistrationAttempted,
    UserRegistrationFailed,
    UserRegistrationSucceeded,
)
from src.domain.events.provider_events import (
    # Provider Connection Events
    ProviderConnectionAttempted,
    ProviderConnectionFailed,
    ProviderConnectionSucceeded,
    # Provider Token Refresh Events (OAuth)
    ProviderTokenRefreshAttempted,
    ProviderTokenRefreshFailed,
    ProviderTokenRefreshSucceeded,
)
from src.infrastructure.events.in_memory_event_bus import InMemoryEventBus
from src.infrastructure.persistence.database import Database


class AuditEventHandler:
    """Event handler for audit trail recording.

    Maps domain events to AuditAction enums and creates audit records with
    full context for compliance (PCI-DSS, SOC 2, GDPR). Supports ATTEMPT →
    OUTCOME audit pattern for security event tracking.

    REQUIRES database session from event bus to ensure proper lifecycle
    management and compliance with F0.9.1 (Separate Audit Session). Session
    MUST be passed to event_bus.publish(event, session=session).

    Attributes:
        _database: Database instance (kept for future use/debugging).
        _event_bus: Event bus instance to get required session from.

    Example:
        >>> # Create handler
        >>> handler = AuditEventHandler(
        ...     database=get_database(),
        ...     event_bus=get_event_bus()
        ... )
        >>>
        >>> # Subscribe to events (in container)
        >>> event_bus.subscribe(UserRegistered, handler.handle_user_registration_succeeded)
        >>>
        >>> # Events automatically audited when published with session
        >>> async with database.get_session() as session:
        ...     await event_bus.publish(
        ...         UserRegistrationSucceeded(user_id=uuid4(), email="test@example.com"),
        ...         session=session
        ...     )
        >>> # Audit record created using provided session
    """

    def __init__(self, database: Database, event_bus: InMemoryEventBus) -> None:
        """Initialize audit handler with database and event bus.

        Args:
            database: Database instance from container (kept for future use).
            event_bus: Event bus instance to get REQUIRED session from during
                event handling. Session must be passed to event_bus.publish().

        Example:
            >>> from src.core.container import get_database, get_event_bus
            >>> database = get_database()
            >>> event_bus = get_event_bus()
            >>> handler = AuditEventHandler(database=database, event_bus=event_bus)
        """
        self._database = database
        self._event_bus = event_bus

    async def _create_audit_record(self, **kwargs: Any) -> None:
        """Helper to create audit record using session from event bus.

        Gets session from event bus. Session is REQUIRED for audit trail recording
        to ensure proper lifecycle management and compliance with F0.9.1 (Separate
        Audit Session).

        Args:
            **kwargs: Arguments to pass to audit.record().

        Raises:
            RuntimeError: If no session provided to event bus. This is a
                programming error - caller must pass session to event_bus.publish().

        Note:
            Session must be passed to event_bus.publish(event, session=session).
            See docs/architecture/domain-events-architecture.md for session
            lifecycle management patterns.
        """
        from src.infrastructure.audit.postgres_adapter import PostgresAuditAdapter

        # Get session from event bus (REQUIRED)
        session = self._event_bus.get_session()

        if session is None:
            raise RuntimeError(
                "AuditEventHandler requires a database session for audit recording. "
                "No session was provided to event_bus.publish(). "
                "\n\nUsage: "
                "\n  async with database.get_session() as session:"
                "\n      await event_bus.publish(event, session=session)"
                "\n\nSee docs/architecture/domain-events-architecture.md for details."
            )

        # Use session from event bus (proper lifecycle)
        audit = PostgresAuditAdapter(session=session)
        await audit.record(**kwargs)

    # =========================================================================
    # User Registration Event Handlers
    # =========================================================================

    async def handle_user_registration_attempted(
        self,
        event: UserRegistrationAttempted,
    ) -> None:
        """Record user registration attempt audit (ATTEMPT).

        Args:
            event: UserRegistrationAttempted event with email.

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
            - context: {email, reason}
        """
        await self._create_audit_record(
            action=AuditAction.USER_REGISTRATION_FAILED,
            user_id=None,  # User not created
            resource_type="user",
            resource_id=None,
            context={
                "event_id": str(event.event_id),
                "email": event.email,
                "reason": event.reason,
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
            - context: {event_id}
        """
        await self._create_audit_record(
            action=AuditAction.USER_PASSWORD_CHANGE_ATTEMPTED,
            user_id=event.user_id,
            resource_type="user",
            resource_id=event.user_id,  # UUID, not string
            context={
                "event_id": str(event.event_id),
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
            - context: {reason}
        """
        await self._create_audit_record(
            action=AuditAction.USER_PASSWORD_CHANGE_FAILED,
            user_id=event.user_id,
            resource_type="user",
            resource_id=event.user_id,  # UUID, not string
            context={
                "event_id": str(event.event_id),
                "reason": event.reason,
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
            event: ProviderConnectionAttempted event with provider slug.

        Audit Record:
            - action: PROVIDER_CONNECTION_ATTEMPTED
            - user_id: UUID of user attempting connection
            - resource_type: "provider"
            - context: {provider_slug, provider_id}
        """
        await self._create_audit_record(
            action=AuditAction.PROVIDER_CONNECTION_ATTEMPTED,
            user_id=event.user_id,
            resource_type="provider",
            resource_id=event.provider_id,
            context={
                "event_id": str(event.event_id),
                "provider_slug": event.provider_slug,
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
            - resource_id: connection_id
            - context: {provider_slug, connection_id}
        """
        await self._create_audit_record(
            action=AuditAction.PROVIDER_CONNECTED,
            user_id=event.user_id,
            resource_type="provider",
            resource_id=event.connection_id,
            context={
                "event_id": str(event.event_id),
                "provider_id": str(event.provider_id),
                "provider_slug": event.provider_slug,
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
            - context: {provider_slug, reason}
        """
        await self._create_audit_record(
            action=AuditAction.PROVIDER_CONNECTION_FAILED,
            user_id=event.user_id,
            resource_type="provider",
            resource_id=event.provider_id,
            context={
                "event_id": str(event.event_id),
                "provider_slug": event.provider_slug,
                "reason": event.reason,
            },
        )

    # =========================================================================
    # Provider Token Refresh Event Handlers (OAuth)
    # =========================================================================

    async def handle_provider_token_refresh_attempted(
        self,
        event: ProviderTokenRefreshAttempted,
    ) -> None:
        """Record provider token refresh attempt audit (ATTEMPT).

        Args:
            event: ProviderTokenRefreshAttempted event with provider details.

        Audit Record:
            - action: PROVIDER_TOKEN_REFRESH_ATTEMPTED
            - user_id: UUID of user whose token is being refreshed
            - resource_type: "token"
            - resource_id: connection_id
            - context: {provider_slug, connection_id}
        """
        await self._create_audit_record(
            action=AuditAction.PROVIDER_TOKEN_REFRESH_ATTEMPTED,
            user_id=event.user_id,
            resource_type="token",
            resource_id=event.connection_id,
            context={
                "event_id": str(event.event_id),
                "provider_id": str(event.provider_id),
                "provider_slug": event.provider_slug,
            },
        )

    async def handle_provider_token_refresh_succeeded(
        self,
        event: ProviderTokenRefreshSucceeded,
    ) -> None:
        """Record successful provider token refresh audit (SUCCESS).

        Args:
            event: ProviderTokenRefreshSucceeded event with provider details.

        Audit Record:
            - action: PROVIDER_TOKEN_REFRESHED
            - user_id: UUID of user whose token was refreshed
            - resource_type: "token"
            - resource_id: connection_id
            - context: {provider_slug, connection_id}
        """
        await self._create_audit_record(
            action=AuditAction.PROVIDER_TOKEN_REFRESHED,
            user_id=event.user_id,
            resource_type="token",
            resource_id=event.connection_id,
            context={
                "event_id": str(event.event_id),
                "provider_id": str(event.provider_id),
                "provider_slug": event.provider_slug,
            },
        )

    async def handle_provider_token_refresh_failed(
        self,
        event: ProviderTokenRefreshFailed,
    ) -> None:
        """Record failed provider token refresh audit (FAILURE).

        Args:
            event: ProviderTokenRefreshFailed event with error details.

        Audit Record:
            - action: PROVIDER_TOKEN_REFRESH_FAILED
            - user_id: UUID of user whose token refresh failed
            - resource_type: "token"
            - resource_id: connection_id
            - context: {provider_slug, reason, needs_user_action}
        """
        await self._create_audit_record(
            action=AuditAction.PROVIDER_TOKEN_REFRESH_FAILED,
            user_id=event.user_id,
            resource_type="token",
            resource_id=event.connection_id,
            context={
                "event_id": str(event.event_id),
                "provider_id": str(event.provider_id),
                "provider_slug": event.provider_slug,
                "reason": event.reason,
                "needs_user_action": event.needs_user_action,
            },
        )
