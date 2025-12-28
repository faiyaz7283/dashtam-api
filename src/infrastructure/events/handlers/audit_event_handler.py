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
    # Auth Token Refresh Events (JWT rotation)
    AuthTokenRefreshAttempted,
    AuthTokenRefreshFailed,
    AuthTokenRefreshSucceeded,
    # Email Verification Events
    EmailVerificationAttempted,
    EmailVerificationFailed,
    EmailVerificationSucceeded,
    # Global Token Rotation Events
    GlobalTokenRotationAttempted,
    GlobalTokenRotationFailed,
    GlobalTokenRotationSucceeded,
    # Password Reset Events
    PasswordResetConfirmAttempted,
    PasswordResetConfirmFailed,
    PasswordResetConfirmSucceeded,
    PasswordResetRequestAttempted,
    PasswordResetRequestFailed,
    PasswordResetRequestSucceeded,
    # Token Rejected Due to Rotation
    TokenRejectedDueToRotation,
    # User Login Events
    UserLoginAttempted,
    UserLoginFailed,
    UserLoginSucceeded,
    # User Logout Events
    UserLogoutAttempted,
    UserLogoutFailed,
    UserLogoutSucceeded,
    # User Password Change Events
    UserPasswordChangeAttempted,
    UserPasswordChangeFailed,
    UserPasswordChangeSucceeded,
    # User Registration Events
    UserRegistrationAttempted,
    UserRegistrationFailed,
    UserRegistrationSucceeded,
    # User Token Rotation Events
    UserTokenRotationAttempted,
    UserTokenRotationFailed,
    UserTokenRotationSucceeded,
)
from src.domain.events.authorization_events import (
    # Role Assignment Events
    RoleAssignmentAttempted,
    RoleAssignmentFailed,
    RoleAssignmentSucceeded,
    # Role Revocation Events
    RoleRevocationAttempted,
    RoleRevocationFailed,
    RoleRevocationSucceeded,
)
from src.domain.events.provider_events import (
    # Provider Connection Events
    ProviderConnectionAttempted,
    ProviderConnectionFailed,
    ProviderConnectionSucceeded,
    # Provider Disconnection Events
    ProviderDisconnectionAttempted,
    ProviderDisconnectionFailed,
    ProviderDisconnectionSucceeded,
    # Provider Token Refresh Events (OAuth)
    ProviderTokenRefreshAttempted,
    ProviderTokenRefreshFailed,
    ProviderTokenRefreshSucceeded,
)
from src.domain.events.rate_limit_events import (
    # Rate Limit Events
    RateLimitCheckAttempted,
    RateLimitCheckAllowed,
    RateLimitCheckDenied,
)
from src.domain.events.session_events import (
    # Session Events (operational - only those requiring audit)
    SessionRevokedEvent,
    SessionEvictedEvent,
    AllSessionsRevokedEvent,
    SessionProviderAccessEvent,
    SuspiciousSessionActivityEvent,
)
from src.domain.events.data_events import (
    # Account Sync Events
    AccountSyncAttempted,
    AccountSyncSucceeded,
    AccountSyncFailed,
    # Transaction Sync Events
    TransactionSyncAttempted,
    TransactionSyncSucceeded,
    TransactionSyncFailed,
    # Holdings Sync Events
    HoldingsSyncAttempted,
    HoldingsSyncSucceeded,
    HoldingsSyncFailed,
    # File Import Events
    FileImportAttempted,
    FileImportSucceeded,
    FileImportFailed,
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
        ...         UserRegistrationSucceeded(user_id=uuid7(), email="test@example.com"),
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
        """Helper to create audit record using session and metadata from event bus.

        Gets session from event bus. Session is REQUIRED for audit trail recording
        to ensure proper lifecycle management and compliance with F0.9.1 (Separate
        Audit Session).

        Also extracts request metadata (IP address, user agent) for PCI-DSS 10.2.7
        compliance. Metadata is optional and defaults to None if not provided.

        Args:
            **kwargs: Arguments to pass to audit.record().

        Raises:
            RuntimeError: If no session provided to event bus. This is a
                programming error - caller must pass session to event_bus.publish().

        Note:
            Session must be passed to event_bus.publish(event, session=session).
            Metadata can optionally be passed: event_bus.publish(event, session, metadata={}).
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

        # Get metadata from event bus (OPTIONAL - for PCI-DSS 10.2.7 compliance)
        metadata = self._event_bus.get_metadata()

        # Merge metadata into kwargs (use setdefault to not overwrite explicit values)
        if metadata:
            kwargs.setdefault("ip_address", metadata.get("ip_address"))
            kwargs.setdefault("user_agent", metadata.get("user_agent"))

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

    # =========================================================================
    # User Login Event Handlers
    # =========================================================================

    async def handle_user_login_attempted(
        self,
        event: UserLoginAttempted,
    ) -> None:
        """Record user login attempt audit (ATTEMPT).

        Args:
            event: UserLoginAttempted event with email.

        Audit Record:
            - action: USER_LOGIN_ATTEMPTED
            - user_id: None (user not authenticated yet)
            - resource_type: "session"
            - context: {email}
        """
        await self._create_audit_record(
            action=AuditAction.USER_LOGIN_ATTEMPTED,
            user_id=None,  # User not authenticated yet
            resource_type="session",
            resource_id=None,
            context={
                "event_id": str(event.event_id),
                "email": event.email,
            },
        )

    async def handle_user_login_succeeded(
        self,
        event: UserLoginSucceeded,
    ) -> None:
        """Record successful user login audit (SUCCESS).

        Args:
            event: UserLoginSucceeded event with user_id and session_id.

        Audit Record:
            - action: USER_LOGIN_SUCCESS
            - user_id: UUID of logged-in user
            - resource_type: "session"
            - resource_id: session_id
            - context: {email, session_id}
        """
        await self._create_audit_record(
            action=AuditAction.USER_LOGIN_SUCCESS,
            user_id=event.user_id,
            resource_type="session",
            resource_id=event.session_id,  # UUID or None
            context={
                "event_id": str(event.event_id),
                "email": event.email,
                "session_id": str(event.session_id) if event.session_id else None,
            },
        )

    async def handle_user_login_failed(
        self,
        event: UserLoginFailed,
    ) -> None:
        """Record failed user login audit (FAILURE).

        Args:
            event: UserLoginFailed event with error details.

        Audit Record:
            - action: USER_LOGIN_FAILED
            - user_id: UUID if found (for tracking lockout)
            - resource_type: "session"
            - context: {email, reason}
        """
        await self._create_audit_record(
            action=AuditAction.USER_LOGIN_FAILED,
            user_id=event.user_id,  # May be None if user not found
            resource_type="session",
            resource_id=None,
            context={
                "event_id": str(event.event_id),
                "email": event.email,
                "reason": event.reason,
            },
        )

    # =========================================================================
    # User Logout Event Handlers
    # =========================================================================

    async def handle_user_logout_attempted(
        self,
        event: UserLogoutAttempted,
    ) -> None:
        """Record user logout attempt audit (ATTEMPT).

        Args:
            event: UserLogoutAttempted event with user_id.

        Audit Record:
            - action: USER_LOGOUT (logout always succeeds, use single event)
            - user_id: UUID of user logging out
            - resource_type: "session"
            - context: {event_id}
        """
        await self._create_audit_record(
            action=AuditAction.USER_LOGOUT,
            user_id=event.user_id,
            resource_type="session",
            resource_id=None,
            context={
                "event_id": str(event.event_id),
            },
        )

    async def handle_user_logout_succeeded(
        self,
        event: UserLogoutSucceeded,
    ) -> None:
        """Record successful user logout audit (SUCCESS).

        Args:
            event: UserLogoutSucceeded event with user_id and session_id.

        Audit Record:
            - action: USER_LOGOUT
            - user_id: UUID of logged-out user
            - resource_type: "session"
            - resource_id: session_id
            - context: {session_id}
        """
        await self._create_audit_record(
            action=AuditAction.USER_LOGOUT,
            user_id=event.user_id,
            resource_type="session",
            resource_id=event.session_id,  # UUID or None
            context={
                "event_id": str(event.event_id),
                "session_id": str(event.session_id) if event.session_id else None,
            },
        )

    async def handle_user_logout_failed(
        self,
        event: UserLogoutFailed,
    ) -> None:
        """Record failed user logout audit (FAILURE).

        Args:
            event: UserLogoutFailed event with error details.

        Audit Record:
            - action: USER_LOGOUT (logout failure is rare)
            - user_id: UUID of user attempting logout
            - resource_type: "session"
            - context: {reason}
        """
        await self._create_audit_record(
            action=AuditAction.USER_LOGOUT,
            user_id=event.user_id,
            resource_type="session",
            resource_id=None,
            context={
                "event_id": str(event.event_id),
                "reason": event.reason,
            },
        )

    # =========================================================================
    # Email Verification Event Handlers
    # =========================================================================

    async def handle_email_verification_attempted(
        self,
        event: EmailVerificationAttempted,
    ) -> None:
        """Record email verification attempt audit (ATTEMPT).

        Args:
            event: EmailVerificationAttempted event with token.

        Audit Record:
            - action: USER_EMAIL_VERIFICATION_ATTEMPTED
            - user_id: None (token not verified yet)
            - resource_type: "user"
            - context: {token (truncated)}
        """
        await self._create_audit_record(
            action=AuditAction.USER_EMAIL_VERIFICATION_ATTEMPTED,
            user_id=None,  # Token not verified yet
            resource_type="user",
            resource_id=None,
            context={
                "event_id": str(event.event_id),
                "token": event.token,  # Already truncated in event
            },
        )

    async def handle_email_verification_succeeded(
        self,
        event: EmailVerificationSucceeded,
    ) -> None:
        """Record successful email verification audit (SUCCESS).

        Args:
            event: EmailVerificationSucceeded event with user_id and email.

        Audit Record:
            - action: USER_EMAIL_VERIFIED
            - user_id: UUID of verified user
            - resource_type: "user"
            - resource_id: user_id
            - context: {email}
        """
        await self._create_audit_record(
            action=AuditAction.USER_EMAIL_VERIFIED,
            user_id=event.user_id,
            resource_type="user",
            resource_id=event.user_id,
            context={
                "event_id": str(event.event_id),
                "email": event.email,
            },
        )

    async def handle_email_verification_failed(
        self,
        event: EmailVerificationFailed,
    ) -> None:
        """Record failed email verification audit (FAILURE).

        Args:
            event: EmailVerificationFailed event with error details.

        Audit Record:
            - action: USER_EMAIL_VERIFICATION_FAILED
            - user_id: None (verification failed)
            - resource_type: "user"
            - context: {token (truncated), reason}
        """
        await self._create_audit_record(
            action=AuditAction.USER_EMAIL_VERIFICATION_FAILED,
            user_id=None,  # Verification failed
            resource_type="user",
            resource_id=None,
            context={
                "event_id": str(event.event_id),
                "token": event.token,  # Already truncated in event
                "reason": event.reason,
            },
        )

    # =========================================================================
    # Auth Token Refresh Event Handlers (JWT Rotation)
    # =========================================================================

    async def handle_auth_token_refresh_attempted(
        self,
        event: AuthTokenRefreshAttempted,
    ) -> None:
        """Record auth token refresh attempt audit (ATTEMPT).

        Args:
            event: AuthTokenRefreshAttempted event with user_id.

        Audit Record:
            - action: AUTH_TOKEN_REFRESH_ATTEMPTED
            - user_id: UUID of user requesting refresh (if known)
            - resource_type: "token"
            - context: {event_id}
        """
        await self._create_audit_record(
            action=AuditAction.AUTH_TOKEN_REFRESH_ATTEMPTED,
            user_id=event.user_id,  # May be None if token invalid
            resource_type="token",
            resource_id=None,
            context={
                "event_id": str(event.event_id),
            },
        )

    async def handle_auth_token_refresh_succeeded(
        self,
        event: AuthTokenRefreshSucceeded,
    ) -> None:
        """Record successful auth token refresh audit (SUCCESS).

        Args:
            event: AuthTokenRefreshSucceeded event with user_id and session_id.

        Audit Record:
            - action: AUTH_TOKEN_REFRESHED
            - user_id: UUID of user whose tokens were refreshed
            - resource_type: "token"
            - resource_id: session_id
            - context: {session_id}
        """
        await self._create_audit_record(
            action=AuditAction.AUTH_TOKEN_REFRESHED,
            user_id=event.user_id,
            resource_type="token",
            resource_id=event.session_id,
            context={
                "event_id": str(event.event_id),
                "session_id": str(event.session_id),
            },
        )

    async def handle_auth_token_refresh_failed(
        self,
        event: AuthTokenRefreshFailed,
    ) -> None:
        """Record failed auth token refresh audit (FAILURE).

        Args:
            event: AuthTokenRefreshFailed event with error details.

        Audit Record:
            - action: AUTH_TOKEN_REFRESH_FAILED
            - user_id: UUID of user (if known)
            - resource_type: "token"
            - context: {reason}
        """
        await self._create_audit_record(
            action=AuditAction.AUTH_TOKEN_REFRESH_FAILED,
            user_id=event.user_id,  # May be None if token invalid
            resource_type="token",
            resource_id=None,
            context={
                "event_id": str(event.event_id),
                "reason": event.reason,
            },
        )

    # =========================================================================
    # Password Reset Request Event Handlers
    # =========================================================================

    async def handle_password_reset_request_attempted(
        self,
        event: PasswordResetRequestAttempted,
    ) -> None:
        """Record password reset request attempt audit (ATTEMPT).

        Args:
            event: PasswordResetRequestAttempted event with email.

        Audit Record:
            - action: USER_PASSWORD_RESET_REQUESTED
            - user_id: None (user not found yet)
            - resource_type: "user"
            - context: {email}
        """
        await self._create_audit_record(
            action=AuditAction.USER_PASSWORD_RESET_REQUESTED,
            user_id=None,  # User not found yet
            resource_type="user",
            resource_id=None,
            context={
                "event_id": str(event.event_id),
                "email": event.email,
            },
        )

    async def handle_password_reset_request_succeeded(
        self,
        event: PasswordResetRequestSucceeded,
    ) -> None:
        """Record successful password reset request audit (SUCCESS).

        Args:
            event: PasswordResetRequestSucceeded event with user_id and email.

        Audit Record:
            - action: USER_PASSWORD_RESET_REQUESTED
            - user_id: UUID of user requesting reset
            - resource_type: "user"
            - resource_id: user_id
            - context: {email}
        """
        await self._create_audit_record(
            action=AuditAction.USER_PASSWORD_RESET_REQUESTED,
            user_id=event.user_id,
            resource_type="user",
            resource_id=event.user_id,
            context={
                "event_id": str(event.event_id),
                "email": event.email,
            },
        )

    async def handle_password_reset_request_failed(
        self,
        event: PasswordResetRequestFailed,
    ) -> None:
        """Record failed password reset request audit (FAILURE).

        Args:
            event: PasswordResetRequestFailed event with error details.

        Audit Record:
            - action: USER_PASSWORD_RESET_FAILED
            - user_id: None (user not found)
            - resource_type: "user"
            - context: {email, reason}
        """
        await self._create_audit_record(
            action=AuditAction.USER_PASSWORD_RESET_FAILED,
            user_id=None,  # User not found
            resource_type="user",
            resource_id=None,
            context={
                "event_id": str(event.event_id),
                "email": event.email,
                "reason": event.reason,
            },
        )

    # =========================================================================
    # Password Reset Confirm Event Handlers
    # =========================================================================

    async def handle_password_reset_confirm_attempted(
        self,
        event: PasswordResetConfirmAttempted,
    ) -> None:
        """Record password reset confirm attempt audit (ATTEMPT).

        Args:
            event: PasswordResetConfirmAttempted event with token.

        Audit Record:
            - action: USER_PASSWORD_RESET_COMPLETED (use completed action)
            - user_id: None (token not verified yet)
            - resource_type: "user"
            - context: {token (truncated)}
        """
        await self._create_audit_record(
            action=AuditAction.USER_PASSWORD_RESET_COMPLETED,
            user_id=None,  # Token not verified yet
            resource_type="user",
            resource_id=None,
            context={
                "event_id": str(event.event_id),
                "token": event.token,  # Already truncated in event
            },
        )

    async def handle_password_reset_confirm_succeeded(
        self,
        event: PasswordResetConfirmSucceeded,
    ) -> None:
        """Record successful password reset confirm audit (SUCCESS).

        Args:
            event: PasswordResetConfirmSucceeded event with user_id and email.

        Audit Record:
            - action: USER_PASSWORD_RESET_COMPLETED
            - user_id: UUID of user whose password was reset
            - resource_type: "user"
            - resource_id: user_id
            - context: {email}
        """
        await self._create_audit_record(
            action=AuditAction.USER_PASSWORD_RESET_COMPLETED,
            user_id=event.user_id,
            resource_type="user",
            resource_id=event.user_id,
            context={
                "event_id": str(event.event_id),
                "email": event.email,
            },
        )

    async def handle_password_reset_confirm_failed(
        self,
        event: PasswordResetConfirmFailed,
    ) -> None:
        """Record failed password reset confirm audit (FAILURE).

        Args:
            event: PasswordResetConfirmFailed event with error details.

        Audit Record:
            - action: USER_PASSWORD_RESET_FAILED
            - user_id: None (reset failed)
            - resource_type: "user"
            - context: {token (truncated), reason}
        """
        await self._create_audit_record(
            action=AuditAction.USER_PASSWORD_RESET_FAILED,
            user_id=None,  # Reset failed
            resource_type="user",
            resource_id=None,
            context={
                "event_id": str(event.event_id),
                "token": event.token,  # Already truncated in event
                "reason": event.reason,
            },
        )

    # =========================================================================
    # Token Rejected Due to Rotation (Security Monitoring)
    # =========================================================================

    async def handle_token_rejected_due_to_rotation(
        self,
        event: TokenRejectedDueToRotation,
    ) -> None:
        """Record token rejection due to version mismatch audit.

        Security monitoring event for token rotation enforcement.

        Args:
            event: TokenRejectedDueToRotation event with version details.

        Audit Record:
            - action: TOKEN_REJECTED_VERSION_MISMATCH
            - user_id: UUID of user (if known)
            - resource_type: "token"
            - context: {token_version, required_version, rejection_reason}
        """
        await self._create_audit_record(
            action=AuditAction.TOKEN_REJECTED_VERSION_MISMATCH,
            user_id=event.user_id,  # May be None
            resource_type="token",
            resource_id=None,
            context={
                "event_id": str(event.event_id),
                "token_version": event.token_version,
                "required_version": event.required_version,
                "rejection_reason": event.rejection_reason,
            },
        )

    # =========================================================================
    # Global Token Rotation Event Handlers
    # =========================================================================

    async def handle_global_token_rotation_attempted(
        self,
        event: GlobalTokenRotationAttempted,
    ) -> None:
        """Record global token rotation attempt audit (ATTEMPT).

        Args:
            event: GlobalTokenRotationAttempted event.

        Audit Record:
            - action: GLOBAL_TOKEN_ROTATION_ATTEMPTED
            - user_id: None (system-level operation)
            - resource_type: "token"
            - context: {triggered_by, reason}
        """
        await self._create_audit_record(
            action=AuditAction.GLOBAL_TOKEN_ROTATION_ATTEMPTED,
            user_id=None,  # System-level operation
            resource_type="token",
            resource_id=None,
            context={
                "event_id": str(event.event_id),
                "triggered_by": event.triggered_by,
                "reason": event.reason,
            },
        )

    async def handle_global_token_rotation_succeeded(
        self,
        event: GlobalTokenRotationSucceeded,
    ) -> None:
        """Record successful global token rotation audit (SUCCESS).

        Args:
            event: GlobalTokenRotationSucceeded event.

        Audit Record:
            - action: GLOBAL_TOKEN_ROTATION_SUCCEEDED
            - user_id: None (system-level operation)
            - resource_type: "token"
            - context: {triggered_by, previous_version, new_version, reason, grace_period_seconds}
        """
        await self._create_audit_record(
            action=AuditAction.GLOBAL_TOKEN_ROTATION_SUCCEEDED,
            user_id=None,  # System-level operation
            resource_type="token",
            resource_id=None,
            context={
                "event_id": str(event.event_id),
                "triggered_by": event.triggered_by,
                "previous_version": event.previous_version,
                "new_version": event.new_version,
                "reason": event.reason,
                "grace_period_seconds": event.grace_period_seconds,
            },
        )

    async def handle_global_token_rotation_failed(
        self,
        event: GlobalTokenRotationFailed,
    ) -> None:
        """Record failed global token rotation audit (FAILURE).

        Args:
            event: GlobalTokenRotationFailed event.

        Audit Record:
            - action: GLOBAL_TOKEN_ROTATION_FAILED
            - user_id: None (system-level operation)
            - resource_type: "token"
            - context: {triggered_by, reason, failure_reason}
        """
        await self._create_audit_record(
            action=AuditAction.GLOBAL_TOKEN_ROTATION_FAILED,
            user_id=None,  # System-level operation
            resource_type="token",
            resource_id=None,
            context={
                "event_id": str(event.event_id),
                "triggered_by": event.triggered_by,
                "reason": event.reason,
                "failure_reason": event.failure_reason,
            },
        )

    # =========================================================================
    # User Token Rotation Event Handlers
    # =========================================================================

    async def handle_user_token_rotation_attempted(
        self,
        event: UserTokenRotationAttempted,
    ) -> None:
        """Record user token rotation attempt audit (ATTEMPT).

        Args:
            event: UserTokenRotationAttempted event.

        Audit Record:
            - action: USER_TOKEN_ROTATION_ATTEMPTED
            - user_id: UUID of user whose tokens are being rotated
            - resource_type: "token"
            - context: {triggered_by, reason}
        """
        await self._create_audit_record(
            action=AuditAction.USER_TOKEN_ROTATION_ATTEMPTED,
            user_id=event.user_id,
            resource_type="token",
            resource_id=None,
            context={
                "event_id": str(event.event_id),
                "triggered_by": event.triggered_by,
                "reason": event.reason,
            },
        )

    async def handle_user_token_rotation_succeeded(
        self,
        event: UserTokenRotationSucceeded,
    ) -> None:
        """Record successful user token rotation audit (SUCCESS).

        Args:
            event: UserTokenRotationSucceeded event.

        Audit Record:
            - action: USER_TOKEN_ROTATION_SUCCEEDED
            - user_id: UUID of user whose tokens were rotated
            - resource_type: "token"
            - context: {triggered_by, previous_version, new_version, reason}
        """
        await self._create_audit_record(
            action=AuditAction.USER_TOKEN_ROTATION_SUCCEEDED,
            user_id=event.user_id,
            resource_type="token",
            resource_id=None,
            context={
                "event_id": str(event.event_id),
                "triggered_by": event.triggered_by,
                "previous_version": event.previous_version,
                "new_version": event.new_version,
                "reason": event.reason,
            },
        )

    async def handle_user_token_rotation_failed(
        self,
        event: UserTokenRotationFailed,
    ) -> None:
        """Record failed user token rotation audit (FAILURE).

        Args:
            event: UserTokenRotationFailed event.

        Audit Record:
            - action: USER_TOKEN_ROTATION_FAILED
            - user_id: UUID of user whose tokens were being rotated
            - resource_type: "token"
            - context: {triggered_by, reason, failure_reason}
        """
        await self._create_audit_record(
            action=AuditAction.USER_TOKEN_ROTATION_FAILED,
            user_id=event.user_id,
            resource_type="token",
            resource_id=None,
            context={
                "event_id": str(event.event_id),
                "triggered_by": event.triggered_by,
                "reason": event.reason,
                "failure_reason": event.failure_reason,
            },
        )

    # =========================================================================
    # Role Assignment Event Handlers
    # =========================================================================

    async def handle_role_assignment_attempted(
        self,
        event: RoleAssignmentAttempted,
    ) -> None:
        """Record role assignment attempt audit (ATTEMPT).

        Args:
            event: RoleAssignmentAttempted event.

        Audit Record:
            - action: ROLE_ASSIGNMENT_ATTEMPTED
            - user_id: UUID of user receiving role
            - resource_type: "user"
            - context: {role, assigned_by}
        """
        await self._create_audit_record(
            action=AuditAction.ROLE_ASSIGNMENT_ATTEMPTED,
            user_id=event.user_id,
            resource_type="user",
            resource_id=event.user_id,
            context={
                "event_id": str(event.event_id),
                "role": event.role,
                "assigned_by": str(event.assigned_by),
            },
        )

    async def handle_role_assignment_succeeded(
        self,
        event: RoleAssignmentSucceeded,
    ) -> None:
        """Record successful role assignment audit (SUCCESS).

        Args:
            event: RoleAssignmentSucceeded event.

        Audit Record:
            - action: ROLE_ASSIGNED
            - user_id: UUID of user who received role
            - resource_type: "user"
            - context: {role, assigned_by}
        """
        await self._create_audit_record(
            action=AuditAction.ROLE_ASSIGNED,
            user_id=event.user_id,
            resource_type="user",
            resource_id=event.user_id,
            context={
                "event_id": str(event.event_id),
                "role": event.role,
                "assigned_by": str(event.assigned_by),
            },
        )

    async def handle_role_assignment_failed(
        self,
        event: RoleAssignmentFailed,
    ) -> None:
        """Record failed role assignment audit (FAILURE).

        Args:
            event: RoleAssignmentFailed event.

        Audit Record:
            - action: ROLE_ASSIGNMENT_FAILED
            - user_id: UUID of user targeted for role
            - resource_type: "user"
            - context: {role, assigned_by, reason}
        """
        await self._create_audit_record(
            action=AuditAction.ROLE_ASSIGNMENT_FAILED,
            user_id=event.user_id,
            resource_type="user",
            resource_id=event.user_id,
            context={
                "event_id": str(event.event_id),
                "role": event.role,
                "assigned_by": str(event.assigned_by),
                "reason": event.reason,
            },
        )

    # =========================================================================
    # Role Revocation Event Handlers
    # =========================================================================

    async def handle_role_revocation_attempted(
        self,
        event: RoleRevocationAttempted,
    ) -> None:
        """Record role revocation attempt audit (ATTEMPT).

        Args:
            event: RoleRevocationAttempted event.

        Audit Record:
            - action: ROLE_REVOCATION_ATTEMPTED
            - user_id: UUID of user losing role
            - resource_type: "user"
            - context: {role, revoked_by, reason}
        """
        await self._create_audit_record(
            action=AuditAction.ROLE_REVOCATION_ATTEMPTED,
            user_id=event.user_id,
            resource_type="user",
            resource_id=event.user_id,
            context={
                "event_id": str(event.event_id),
                "role": event.role,
                "revoked_by": str(event.revoked_by),
                "reason": event.reason,
            },
        )

    async def handle_role_revocation_succeeded(
        self,
        event: RoleRevocationSucceeded,
    ) -> None:
        """Record successful role revocation audit (SUCCESS).

        Args:
            event: RoleRevocationSucceeded event.

        Audit Record:
            - action: ROLE_REVOKED
            - user_id: UUID of user who lost role
            - resource_type: "user"
            - context: {role, revoked_by, reason}
        """
        await self._create_audit_record(
            action=AuditAction.ROLE_REVOKED,
            user_id=event.user_id,
            resource_type="user",
            resource_id=event.user_id,
            context={
                "event_id": str(event.event_id),
                "role": event.role,
                "revoked_by": str(event.revoked_by),
                "reason": event.reason,
            },
        )

    async def handle_role_revocation_failed(
        self,
        event: RoleRevocationFailed,
    ) -> None:
        """Record failed role revocation audit (FAILURE).

        Args:
            event: RoleRevocationFailed event.

        Audit Record:
            - action: ROLE_REVOCATION_FAILED
            - user_id: UUID of user targeted for revocation
            - resource_type: "user"
            - context: {role, revoked_by, reason}
        """
        await self._create_audit_record(
            action=AuditAction.ROLE_REVOCATION_FAILED,
            user_id=event.user_id,
            resource_type="user",
            resource_id=event.user_id,
            context={
                "event_id": str(event.event_id),
                "role": event.role,
                "revoked_by": str(event.revoked_by),
                "reason": event.reason,
            },
        )

    # =========================================================================
    # Provider Disconnection Event Handlers
    # =========================================================================

    async def handle_provider_disconnection_attempted(
        self,
        event: ProviderDisconnectionAttempted,
    ) -> None:
        """Record provider disconnection attempt audit (ATTEMPT).

        Args:
            event: ProviderDisconnectionAttempted event.

        Audit Record:
            - action: PROVIDER_DISCONNECTION_ATTEMPTED
            - user_id: UUID of user initiating disconnection
            - resource_type: "provider"
            - context: {connection_id, provider_id, provider_slug}
        """
        await self._create_audit_record(
            action=AuditAction.PROVIDER_DISCONNECTION_ATTEMPTED,
            user_id=event.user_id,
            resource_type="provider",
            resource_id=event.connection_id,
            context={
                "event_id": str(event.event_id),
                "connection_id": str(event.connection_id),
                "provider_id": str(event.provider_id),
                "provider_slug": event.provider_slug,
            },
        )

    async def handle_provider_disconnection_succeeded(
        self,
        event: ProviderDisconnectionSucceeded,
    ) -> None:
        """Record successful provider disconnection audit (SUCCESS).

        Args:
            event: ProviderDisconnectionSucceeded event.

        Audit Record:
            - action: PROVIDER_DISCONNECTED
            - user_id: UUID of user who disconnected
            - resource_type: "provider"
            - context: {connection_id, provider_id, provider_slug}
        """
        await self._create_audit_record(
            action=AuditAction.PROVIDER_DISCONNECTED,
            user_id=event.user_id,
            resource_type="provider",
            resource_id=event.connection_id,
            context={
                "event_id": str(event.event_id),
                "connection_id": str(event.connection_id),
                "provider_id": str(event.provider_id),
                "provider_slug": event.provider_slug,
            },
        )

    async def handle_provider_disconnection_failed(
        self,
        event: ProviderDisconnectionFailed,
    ) -> None:
        """Record failed provider disconnection audit (FAILURE).

        Args:
            event: ProviderDisconnectionFailed event.

        Audit Record:
            - action: PROVIDER_DISCONNECTION_FAILED
            - user_id: UUID of user who attempted disconnection
            - resource_type: "provider"
            - context: {connection_id, provider_id, provider_slug, reason}
        """
        await self._create_audit_record(
            action=AuditAction.PROVIDER_DISCONNECTION_FAILED,
            user_id=event.user_id,
            resource_type="provider",
            resource_id=event.connection_id,
            context={
                "event_id": str(event.event_id),
                "connection_id": str(event.connection_id),
                "provider_id": str(event.provider_id),
                "provider_slug": event.provider_slug,
                "reason": event.reason,
            },
        )

    # =========================================================================
    # Token Rejected Due to Rotation Event Handler (F7.7 Phase 4)
    # =========================================================================

    async def handle_token_rejected_due_to_rotation_operational(
        self,
        event: TokenRejectedDueToRotation,
    ) -> None:
        """Record token rejection audit (operational - security monitoring).

        Audit Record:
            - action: TOKEN_REJECTED_VERSION_MISMATCH
            - user_id: UUID of user whose token was rejected (if known)
            - resource_type: "token"
            - context: {token_version, required_version, rejection_reason}
        """
        await self._create_audit_record(
            action=AuditAction.TOKEN_REJECTED_VERSION_MISMATCH,
            user_id=event.user_id,
            resource_type="token",
            resource_id=None,
            context={
                "event_id": str(event.event_id),
                "token_version": event.token_version,
                "required_version": event.required_version,
                "rejection_reason": event.rejection_reason,
            },
        )

    # =========================================================================
    # Rate Limit Event Handlers (F7.7 Phase 4)
    # =========================================================================

    async def handle_rate_limit_check_attempted(
        self,
        event: RateLimitCheckAttempted,
    ) -> None:
        """Record rate limit check attempt audit.

        Audit Record:
            - action: RATE_LIMIT_CHECK_ATTEMPTED
            - user_id: None (rate limiting is per IP/identifier)
            - resource_type: "endpoint"
            - context: {identifier, scope, endpoint}
        """
        await self._create_audit_record(
            action=AuditAction.RATE_LIMIT_CHECK_ATTEMPTED,
            user_id=None,
            resource_type="endpoint",
            resource_id=None,
            context={
                "event_id": str(event.event_id),
                "identifier": event.identifier,
                "scope": event.scope,
                "endpoint": event.endpoint,
            },
        )

    async def handle_rate_limit_check_allowed(
        self,
        event: RateLimitCheckAllowed,
    ) -> None:
        """Record rate limit check allowed audit.

        Audit Record:
            - action: RATE_LIMIT_CHECK_ALLOWED
            - user_id: None
            - resource_type: "endpoint"
            - context: {identifier, scope, endpoint, remaining_tokens}
        """
        await self._create_audit_record(
            action=AuditAction.RATE_LIMIT_CHECK_ALLOWED,
            user_id=None,
            resource_type="endpoint",
            resource_id=None,
            context={
                "event_id": str(event.event_id),
                "identifier": event.identifier,
                "scope": event.scope,
                "endpoint": event.endpoint,
                "remaining_tokens": event.remaining_tokens,
            },
        )

    async def handle_rate_limit_check_denied(
        self,
        event: RateLimitCheckDenied,
    ) -> None:
        """Record rate limit check denied audit (security event).

        Audit Record:
            - action: RATE_LIMIT_CHECK_DENIED
            - user_id: None
            - resource_type: "endpoint"
            - context: {identifier, scope, endpoint, retry_after}
        """
        await self._create_audit_record(
            action=AuditAction.RATE_LIMIT_CHECK_DENIED,
            user_id=None,
            resource_type="endpoint",
            resource_id=None,
            context={
                "event_id": str(event.event_id),
                "identifier": event.identifier,
                "scope": event.scope,
                "endpoint": event.endpoint,
                "retry_after": event.retry_after,
            },
        )

    # =========================================================================
    # Session Event Handlers (F7.7 Phase 4 - Operational Events)
    # =========================================================================

    async def handle_session_revoked_operational(
        self,
        event: SessionRevokedEvent,
    ) -> None:
        """Record session revocation audit (operational - security event).

        Audit Record:
            - action: SESSION_REVOKED
            - user_id: UUID of user whose session was revoked
            - resource_type: "session"
            - context: {session_id, revoked_by, reason}
        """
        await self._create_audit_record(
            action=AuditAction.SESSION_REVOKED,
            user_id=event.user_id,
            resource_type="session",
            resource_id=event.session_id,
            context={
                "event_id": str(event.event_id),
                "session_id": str(event.session_id),
                "revoked_by_user": event.revoked_by_user,
                "reason": event.reason,
            },
        )

    async def handle_session_evicted_operational(
        self,
        event: SessionEvictedEvent,
    ) -> None:
        """Record session eviction audit (operational - limit enforcement).

        Audit Record:
            - action: SESSION_EVICTED
            - user_id: UUID of user whose session was evicted
            - resource_type: "session"
            - context: {session_id, reason}
        """
        await self._create_audit_record(
            action=AuditAction.SESSION_EVICTED,
            user_id=event.user_id,
            resource_type="session",
            resource_id=event.session_id,
            context={
                "event_id": str(event.event_id),
                "session_id": str(event.session_id),
                "reason": event.reason,
            },
        )

    async def handle_all_sessions_revoked_operational(
        self,
        event: AllSessionsRevokedEvent,
    ) -> None:
        """Record all sessions revoked audit (operational - security event).

        Audit Record:
            - action: ALL_SESSIONS_REVOKED
            - user_id: UUID of user whose sessions were revoked
            - resource_type: "session"
            - context: {revoked_by, reason, count}
        """
        await self._create_audit_record(
            action=AuditAction.ALL_SESSIONS_REVOKED,
            user_id=event.user_id,
            resource_type="session",
            resource_id=None,
            context={
                "event_id": str(event.event_id),
                "reason": event.reason,
                "session_count": event.session_count,
            },
        )

    async def handle_session_provider_access_operational(
        self,
        event: SessionProviderAccessEvent,
    ) -> None:
        """Record session provider access audit (operational - data access trail).

        Audit Record:
            - action: SESSION_PROVIDER_ACCESS
            - user_id: UUID of user accessing provider
            - resource_type: "provider"
            - context: {session_id, provider_id}
        """
        await self._create_audit_record(
            action=AuditAction.SESSION_PROVIDER_ACCESS,
            user_id=event.user_id,
            resource_type="provider",
            resource_id=None,
            context={
                "event_id": str(event.event_id),
                "session_id": str(event.session_id),
                "provider_name": event.provider_name,
            },
        )

    async def handle_suspicious_session_activity_operational(
        self,
        event: SuspiciousSessionActivityEvent,
    ) -> None:
        """Record suspicious session activity audit (operational - security alert).

        Audit Record:
            - action: SUSPICIOUS_SESSION_ACTIVITY
            - user_id: UUID of user with suspicious activity
            - resource_type: "session"
            - context: {session_id, reason}
        """
        await self._create_audit_record(
            action=AuditAction.SUSPICIOUS_SESSION_ACTIVITY,
            user_id=event.user_id,
            resource_type="session",
            resource_id=event.session_id,
            context={
                "event_id": str(event.event_id),
                "session_id": str(event.session_id),
                "activity_type": event.activity_type,
            },
        )

    # =========================================================================
    # Data Sync Event Handlers (F7.7 Phase 4)
    # =========================================================================

    # Account Sync Handlers
    async def handle_account_sync_attempted(
        self,
        event: AccountSyncAttempted,
    ) -> None:
        """Record account sync attempt audit (ATTEMPT).

        Audit Record:
            - action: ACCOUNT_SYNC_ATTEMPTED
            - user_id: UUID of user initiating sync
            - resource_type: "account"
            - context: {connection_id}
        """
        await self._create_audit_record(
            action=AuditAction.ACCOUNT_SYNC_ATTEMPTED,
            user_id=event.user_id,
            resource_type="account",
            resource_id=event.connection_id,
            context={
                "event_id": str(event.event_id),
                "connection_id": str(event.connection_id),
            },
        )

    async def handle_account_sync_succeeded(
        self,
        event: AccountSyncSucceeded,
    ) -> None:
        """Record successful account sync audit (SUCCESS).

        Audit Record:
            - action: ACCOUNT_SYNC_SUCCEEDED
            - user_id: UUID of user who synced
            - resource_type: "account"
            - context: {connection_id, account_count}
        """
        await self._create_audit_record(
            action=AuditAction.ACCOUNT_SYNC_SUCCEEDED,
            user_id=event.user_id,
            resource_type="account",
            resource_id=event.connection_id,
            context={
                "event_id": str(event.event_id),
                "connection_id": str(event.connection_id),
                "account_count": event.account_count,
            },
        )

    async def handle_account_sync_failed(
        self,
        event: AccountSyncFailed,
    ) -> None:
        """Record failed account sync audit (FAILURE).

        Audit Record:
            - action: ACCOUNT_SYNC_FAILED
            - user_id: UUID of user who attempted sync
            - resource_type: "account"
            - context: {connection_id, reason}
        """
        await self._create_audit_record(
            action=AuditAction.ACCOUNT_SYNC_FAILED,
            user_id=event.user_id,
            resource_type="account",
            resource_id=event.connection_id,
            context={
                "event_id": str(event.event_id),
                "connection_id": str(event.connection_id),
                "reason": event.reason,
            },
        )

    # Transaction Sync Handlers
    async def handle_transaction_sync_attempted(
        self,
        event: TransactionSyncAttempted,
    ) -> None:
        """Record transaction sync attempt audit (ATTEMPT - PCI-DSS cardholder data).

        Audit Record:
            - action: TRANSACTION_SYNC_ATTEMPTED
            - user_id: UUID of user initiating sync
            - resource_type: "transaction"
            - context: {connection_id, account_id}
        """
        await self._create_audit_record(
            action=AuditAction.TRANSACTION_SYNC_ATTEMPTED,
            user_id=event.user_id,
            resource_type="transaction",
            resource_id=event.connection_id,
            context={
                "event_id": str(event.event_id),
                "connection_id": str(event.connection_id),
                "account_id": str(event.account_id) if event.account_id else None,
            },
        )

    async def handle_transaction_sync_succeeded(
        self,
        event: TransactionSyncSucceeded,
    ) -> None:
        """Record successful transaction sync audit (SUCCESS - PCI-DSS cardholder data).

        Audit Record:
            - action: TRANSACTION_SYNC_SUCCEEDED
            - user_id: UUID of user who synced
            - resource_type: "transaction"
            - context: {connection_id, account_id, transaction_count}
        """
        await self._create_audit_record(
            action=AuditAction.TRANSACTION_SYNC_SUCCEEDED,
            user_id=event.user_id,
            resource_type="transaction",
            resource_id=event.connection_id,
            context={
                "event_id": str(event.event_id),
                "connection_id": str(event.connection_id),
                "account_id": str(event.account_id) if event.account_id else None,
                "transaction_count": event.transaction_count,
            },
        )

    async def handle_transaction_sync_failed(
        self,
        event: TransactionSyncFailed,
    ) -> None:
        """Record failed transaction sync audit (FAILURE).

        Audit Record:
            - action: TRANSACTION_SYNC_FAILED
            - user_id: UUID of user who attempted sync
            - resource_type: "transaction"
            - context: {connection_id, account_id, reason}
        """
        await self._create_audit_record(
            action=AuditAction.TRANSACTION_SYNC_FAILED,
            user_id=event.user_id,
            resource_type="transaction",
            resource_id=event.connection_id,
            context={
                "event_id": str(event.event_id),
                "connection_id": str(event.connection_id),
                "account_id": str(event.account_id) if event.account_id else None,
                "reason": event.reason,
            },
        )

    # Holdings Sync Handlers
    async def handle_holdings_sync_attempted(
        self,
        event: HoldingsSyncAttempted,
    ) -> None:
        """Record holdings sync attempt audit (ATTEMPT).

        Audit Record:
            - action: HOLDINGS_SYNC_ATTEMPTED
            - user_id: UUID of user initiating sync
            - resource_type: "holding"
            - context: {account_id}
        """
        await self._create_audit_record(
            action=AuditAction.HOLDINGS_SYNC_ATTEMPTED,
            user_id=event.user_id,
            resource_type="holding",
            resource_id=event.account_id,
            context={
                "event_id": str(event.event_id),
                "account_id": str(event.account_id),
            },
        )

    async def handle_holdings_sync_succeeded(
        self,
        event: HoldingsSyncSucceeded,
    ) -> None:
        """Record successful holdings sync audit (SUCCESS).

        Audit Record:
            - action: HOLDINGS_SYNC_SUCCEEDED
            - user_id: UUID of user who synced
            - resource_type: "holding"
            - context: {account_id, holding_count}
        """
        await self._create_audit_record(
            action=AuditAction.HOLDINGS_SYNC_SUCCEEDED,
            user_id=event.user_id,
            resource_type="holding",
            resource_id=event.account_id,
            context={
                "event_id": str(event.event_id),
                "account_id": str(event.account_id),
                "holding_count": event.holding_count,
            },
        )

    async def handle_holdings_sync_failed(
        self,
        event: HoldingsSyncFailed,
    ) -> None:
        """Record failed holdings sync audit (FAILURE).

        Audit Record:
            - action: HOLDINGS_SYNC_FAILED
            - user_id: UUID of user who attempted sync
            - resource_type: "holding"
            - context: {account_id, reason}
        """
        await self._create_audit_record(
            action=AuditAction.HOLDINGS_SYNC_FAILED,
            user_id=event.user_id,
            resource_type="holding",
            resource_id=event.account_id,
            context={
                "event_id": str(event.event_id),
                "account_id": str(event.account_id),
                "reason": event.reason,
            },
        )

    # File Import Handlers
    async def handle_file_import_attempted(
        self,
        event: FileImportAttempted,
    ) -> None:
        """Record file import attempt audit (ATTEMPT).

        Audit Record:
            - action: FILE_IMPORT_ATTEMPTED
            - user_id: UUID of user importing file
            - resource_type: "file"
            - context: {provider_slug, file_name, file_format}
        """
        await self._create_audit_record(
            action=AuditAction.FILE_IMPORT_ATTEMPTED,
            user_id=event.user_id,
            resource_type="file",
            resource_id=None,
            context={
                "event_id": str(event.event_id),
                "provider_slug": event.provider_slug,
                "file_name": event.file_name,
                "file_format": event.file_format,
            },
        )

    async def handle_file_import_succeeded(
        self,
        event: FileImportSucceeded,
    ) -> None:
        """Record successful file import audit (SUCCESS).

        Audit Record:
            - action: FILE_IMPORT_SUCCEEDED
            - user_id: UUID of user who imported file
            - resource_type: "file"
            - context: {provider_slug, file_name, file_format, account_count, transaction_count}
        """
        await self._create_audit_record(
            action=AuditAction.FILE_IMPORT_SUCCEEDED,
            user_id=event.user_id,
            resource_type="file",
            resource_id=None,
            context={
                "event_id": str(event.event_id),
                "provider_slug": event.provider_slug,
                "file_name": event.file_name,
                "file_format": event.file_format,
                "account_count": event.account_count,
                "transaction_count": event.transaction_count,
            },
        )

    async def handle_file_import_failed(
        self,
        event: FileImportFailed,
    ) -> None:
        """Record failed file import audit (FAILURE).

        Audit Record:
            - action: FILE_IMPORT_FAILED
            - user_id: UUID of user who attempted import
            - resource_type: "file"
            - context: {provider_slug, file_name, file_format, reason}
        """
        await self._create_audit_record(
            action=AuditAction.FILE_IMPORT_FAILED,
            user_id=event.user_id,
            resource_type="file",
            resource_id=None,
            context={
                "event_id": str(event.event_id),
                "provider_slug": event.provider_slug,
                "file_name": event.file_name,
                "file_format": event.file_format,
                "reason": event.reason,
            },
        )
