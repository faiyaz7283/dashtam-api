"""Domain Events Registry - Single Source of Truth.

This registry catalogs ALL domain events in the system with their metadata.
Used for:
- Container wiring (automated subscription)
- Validation tests (verify no drift)
- Documentation generation (always accurate)
- Gap detection (missing handlers, audit actions, etc.)

Architecture:
- Domain layer (no dependencies on infrastructure)
- Imported by container for automated wiring
- Verified by tests to catch drift

Adding new events:
1. Define event dataclass in appropriate *_events.py file
2. Add entry to EVENT_REGISTRY below
3. Run tests - they'll tell you what's missing:
   - Handler methods needed
   - AuditAction enums needed
   - Container subscriptions needed (auto-wired)

Reference:
    - docs/architecture/domain-events-architecture.md
    - F7.7 Phase 1.5: Event Registry implementation
"""

from dataclasses import dataclass
from enum import Enum
from typing import Type

from src.domain.events.auth_events import (
    AuthTokenRefreshAttempted,
    AuthTokenRefreshFailed,
    AuthTokenRefreshSucceeded,
    EmailVerificationAttempted,
    EmailVerificationFailed,
    EmailVerificationSucceeded,
    GlobalTokenRotationAttempted,
    GlobalTokenRotationFailed,
    GlobalTokenRotationSucceeded,
    PasswordResetConfirmAttempted,
    PasswordResetConfirmFailed,
    PasswordResetConfirmSucceeded,
    PasswordResetRequestAttempted,
    PasswordResetRequestFailed,
    PasswordResetRequestSucceeded,
    TokenRejectedDueToRotation,
    UserLoginAttempted,
    UserLoginFailed,
    UserLoginSucceeded,
    UserLogoutAttempted,
    UserLogoutFailed,
    UserLogoutSucceeded,
    UserPasswordChangeAttempted,
    UserPasswordChangeFailed,
    UserPasswordChangeSucceeded,
    UserRegistrationAttempted,
    UserRegistrationFailed,
    UserRegistrationSucceeded,
    UserTokenRotationAttempted,
    UserTokenRotationFailed,
    UserTokenRotationSucceeded,
)
from src.domain.events.authorization_events import (
    RoleAssignmentAttempted,
    RoleAssignmentFailed,
    RoleAssignmentSucceeded,
    RoleRevocationAttempted,
    RoleRevocationFailed,
    RoleRevocationSucceeded,
)
from src.domain.events.base_event import DomainEvent
from src.domain.events.provider_events import (
    ProviderConnectionAttempted,
    ProviderConnectionFailed,
    ProviderConnectionSucceeded,
    ProviderDisconnectionAttempted,
    ProviderDisconnectionFailed,
    ProviderDisconnectionSucceeded,
    ProviderTokenRefreshAttempted,
    ProviderTokenRefreshFailed,
    ProviderTokenRefreshSucceeded,
)
from src.domain.events.rate_limit_events import (
    RateLimitCheckAllowed,
    RateLimitCheckAttempted,
    RateLimitCheckDenied,
)
from src.domain.events.session_events import (
    # 3-state workflow events
    SessionRevocationAttempted,
    SessionRevokedEvent,
    SessionRevocationFailed,
    AllSessionsRevocationAttempted,
    AllSessionsRevokedEvent,
    AllSessionsRevocationFailed,
    # Operational events
    SessionActivityUpdatedEvent,
    SessionCreatedEvent,
    SessionEvictedEvent,
    SessionLimitExceededEvent,
    SessionProviderAccessEvent,
    SuspiciousSessionActivityEvent,
)
from src.domain.events.data_events import (
    AccountSyncAttempted,
    AccountSyncSucceeded,
    AccountSyncFailed,
    TransactionSyncAttempted,
    TransactionSyncSucceeded,
    TransactionSyncFailed,
    HoldingsSyncAttempted,
    HoldingsSyncSucceeded,
    HoldingsSyncFailed,
    FileImportAttempted,
    FileImportSucceeded,
    FileImportFailed,
    FileImportProgress,
)


class EventCategory(Enum):
    """Event categories for organization and filtering."""

    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    PROVIDER = "provider"
    DATA_SYNC = "data_sync"
    SESSION = "session"
    RATE_LIMIT = "rate_limit"
    ADMIN = "admin"


class WorkflowPhase(Enum):
    """3-state workflow phases for ATTEMPT → OUTCOME pattern."""

    ATTEMPTED = "attempted"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    ALLOWED = "allowed"  # For rate limit events (special case)
    DENIED = "denied"  # For rate limit events (special case)
    OPERATIONAL = "operational"  # For single-state operational events


@dataclass(frozen=True)
class EventMetadata:
    """Metadata for a domain event.

    Attributes:
        event_class: The event dataclass.
        category: Event category.
        workflow_name: Name of workflow (e.g., "user_registration").
        phase: Workflow phase (attempted/succeeded/failed/operational).
        requires_logging: LoggingEventHandler handles this event.
        requires_audit: AuditEventHandler handles this event.
        requires_email: EmailEventHandler handles this event.
        requires_session: SessionEventHandler handles this event.
        audit_action_name: Expected AuditAction enum name (for validation).
    """

    event_class: Type[DomainEvent]
    category: EventCategory
    workflow_name: str
    phase: WorkflowPhase
    requires_logging: bool = True  # Default: all events logged
    requires_audit: bool = True  # Default: all events audited
    requires_email: bool = False  # Default: no email
    requires_session: bool = False  # Default: no session handling
    audit_action_name: str = ""  # Auto-computed if empty


# ═══════════════════════════════════════════════════════════════
# EVENT REGISTRY - Single Source of Truth
# ═══════════════════════════════════════════════════════════════

EVENT_REGISTRY: list[EventMetadata] = [
    # ═══════════════════════════════════════════════════════════
    # Authentication Events (28 events)
    # ═══════════════════════════════════════════════════════════
    # User Registration (Workflow 1)
    EventMetadata(
        event_class=UserRegistrationAttempted,
        category=EventCategory.AUTHENTICATION,
        workflow_name="user_registration",
        phase=WorkflowPhase.ATTEMPTED,
        audit_action_name="USER_REGISTRATION_ATTEMPTED",
    ),
    EventMetadata(
        event_class=UserRegistrationSucceeded,
        category=EventCategory.AUTHENTICATION,
        workflow_name="user_registration",
        phase=WorkflowPhase.SUCCEEDED,
        requires_email=True,  # Send verification email
        audit_action_name="USER_REGISTERED",
    ),
    EventMetadata(
        event_class=UserRegistrationFailed,
        category=EventCategory.AUTHENTICATION,
        workflow_name="user_registration",
        phase=WorkflowPhase.FAILED,
        audit_action_name="USER_REGISTRATION_FAILED",
    ),
    # User Login (Workflow 2)
    EventMetadata(
        event_class=UserLoginAttempted,
        category=EventCategory.AUTHENTICATION,
        workflow_name="user_login",
        phase=WorkflowPhase.ATTEMPTED,
        audit_action_name="USER_LOGIN_ATTEMPTED",
    ),
    EventMetadata(
        event_class=UserLoginSucceeded,
        category=EventCategory.AUTHENTICATION,
        workflow_name="user_login",
        phase=WorkflowPhase.SUCCEEDED,
        audit_action_name="USER_LOGIN_SUCCESS",
    ),
    EventMetadata(
        event_class=UserLoginFailed,
        category=EventCategory.AUTHENTICATION,
        workflow_name="user_login",
        phase=WorkflowPhase.FAILED,
        audit_action_name="USER_LOGIN_FAILED",
    ),
    # Email Verification (Workflow 3)
    EventMetadata(
        event_class=EmailVerificationAttempted,
        category=EventCategory.AUTHENTICATION,
        workflow_name="email_verification",
        phase=WorkflowPhase.ATTEMPTED,
        audit_action_name="USER_EMAIL_VERIFICATION_ATTEMPTED",
    ),
    EventMetadata(
        event_class=EmailVerificationSucceeded,
        category=EventCategory.AUTHENTICATION,
        workflow_name="email_verification",
        phase=WorkflowPhase.SUCCEEDED,
        requires_email=True,  # Send confirmation email
        audit_action_name="USER_EMAIL_VERIFIED",
    ),
    EventMetadata(
        event_class=EmailVerificationFailed,
        category=EventCategory.AUTHENTICATION,
        workflow_name="email_verification",
        phase=WorkflowPhase.FAILED,
        audit_action_name="USER_EMAIL_VERIFICATION_FAILED",
    ),
    # User Password Change (Workflow 4)
    EventMetadata(
        event_class=UserPasswordChangeAttempted,
        category=EventCategory.AUTHENTICATION,
        workflow_name="user_password_change",
        phase=WorkflowPhase.ATTEMPTED,
        audit_action_name="USER_PASSWORD_CHANGE_ATTEMPTED",
    ),
    EventMetadata(
        event_class=UserPasswordChangeSucceeded,
        category=EventCategory.AUTHENTICATION,
        workflow_name="user_password_change",
        phase=WorkflowPhase.SUCCEEDED,
        requires_email=True,  # Send password changed notification
        requires_session=True,  # Revoke all sessions
        audit_action_name="USER_PASSWORD_CHANGED",
    ),
    EventMetadata(
        event_class=UserPasswordChangeFailed,
        category=EventCategory.AUTHENTICATION,
        workflow_name="user_password_change",
        phase=WorkflowPhase.FAILED,
        audit_action_name="USER_PASSWORD_CHANGE_FAILED",
    ),
    # Auth Token Refresh (Workflow 5)
    EventMetadata(
        event_class=AuthTokenRefreshAttempted,
        category=EventCategory.AUTHENTICATION,
        workflow_name="auth_token_refresh",
        phase=WorkflowPhase.ATTEMPTED,
        audit_action_name="AUTH_TOKEN_REFRESH_ATTEMPTED",
    ),
    EventMetadata(
        event_class=AuthTokenRefreshSucceeded,
        category=EventCategory.AUTHENTICATION,
        workflow_name="auth_token_refresh",
        phase=WorkflowPhase.SUCCEEDED,
        audit_action_name="AUTH_TOKEN_REFRESHED",
    ),
    EventMetadata(
        event_class=AuthTokenRefreshFailed,
        category=EventCategory.AUTHENTICATION,
        workflow_name="auth_token_refresh",
        phase=WorkflowPhase.FAILED,
        audit_action_name="AUTH_TOKEN_REFRESH_FAILED",
    ),
    # User Logout (Workflow 6)
    EventMetadata(
        event_class=UserLogoutAttempted,
        category=EventCategory.AUTHENTICATION,
        workflow_name="user_logout",
        phase=WorkflowPhase.ATTEMPTED,
        audit_action_name="USER_LOGOUT_ATTEMPTED",
    ),
    EventMetadata(
        event_class=UserLogoutSucceeded,
        category=EventCategory.AUTHENTICATION,
        workflow_name="user_logout",
        phase=WorkflowPhase.SUCCEEDED,
        requires_session=True,  # Session cleanup
        audit_action_name="USER_LOGOUT",
    ),
    EventMetadata(
        event_class=UserLogoutFailed,
        category=EventCategory.AUTHENTICATION,
        workflow_name="user_logout",
        phase=WorkflowPhase.FAILED,
        audit_action_name="USER_LOGOUT_FAILED",
    ),
    # Password Reset Request (Workflow 7)
    EventMetadata(
        event_class=PasswordResetRequestAttempted,
        category=EventCategory.AUTHENTICATION,
        workflow_name="password_reset_request",
        phase=WorkflowPhase.ATTEMPTED,
        audit_action_name="PASSWORD_RESET_REQUEST_ATTEMPTED",
    ),
    EventMetadata(
        event_class=PasswordResetRequestSucceeded,
        category=EventCategory.AUTHENTICATION,
        workflow_name="password_reset_request",
        phase=WorkflowPhase.SUCCEEDED,
        requires_email=True,  # Send reset link email
        audit_action_name="USER_PASSWORD_RESET_REQUESTED",
    ),
    EventMetadata(
        event_class=PasswordResetRequestFailed,
        category=EventCategory.AUTHENTICATION,
        workflow_name="password_reset_request",
        phase=WorkflowPhase.FAILED,
        audit_action_name="USER_PASSWORD_RESET_FAILED",
    ),
    # Password Reset Confirm (Workflow 8)
    EventMetadata(
        event_class=PasswordResetConfirmAttempted,
        category=EventCategory.AUTHENTICATION,
        workflow_name="password_reset_confirm",
        phase=WorkflowPhase.ATTEMPTED,
        audit_action_name="PASSWORD_RESET_CONFIRM_ATTEMPTED",
    ),
    EventMetadata(
        event_class=PasswordResetConfirmSucceeded,
        category=EventCategory.AUTHENTICATION,
        workflow_name="password_reset_confirm",
        phase=WorkflowPhase.SUCCEEDED,
        requires_email=True,  # Send password changed notification
        requires_session=True,  # Revoke all sessions
        audit_action_name="USER_PASSWORD_RESET_COMPLETED",
    ),
    EventMetadata(
        event_class=PasswordResetConfirmFailed,
        category=EventCategory.AUTHENTICATION,
        workflow_name="password_reset_confirm",
        phase=WorkflowPhase.FAILED,
        audit_action_name="PASSWORD_RESET_CONFIRM_FAILED",
    ),
    # Global Token Rotation (Workflow 9)
    EventMetadata(
        event_class=GlobalTokenRotationAttempted,
        category=EventCategory.AUTHENTICATION,
        workflow_name="global_token_rotation",
        phase=WorkflowPhase.ATTEMPTED,
        audit_action_name="GLOBAL_TOKEN_ROTATION_ATTEMPTED",
    ),
    EventMetadata(
        event_class=GlobalTokenRotationSucceeded,
        category=EventCategory.AUTHENTICATION,
        workflow_name="global_token_rotation",
        phase=WorkflowPhase.SUCCEEDED,
        audit_action_name="GLOBAL_TOKEN_ROTATION_SUCCEEDED",
    ),
    EventMetadata(
        event_class=GlobalTokenRotationFailed,
        category=EventCategory.AUTHENTICATION,
        workflow_name="global_token_rotation",
        phase=WorkflowPhase.FAILED,
        audit_action_name="GLOBAL_TOKEN_ROTATION_FAILED",
    ),
    # User Token Rotation (Workflow 10)
    EventMetadata(
        event_class=UserTokenRotationAttempted,
        category=EventCategory.AUTHENTICATION,
        workflow_name="user_token_rotation",
        phase=WorkflowPhase.ATTEMPTED,
        audit_action_name="USER_TOKEN_ROTATION_ATTEMPTED",
    ),
    EventMetadata(
        event_class=UserTokenRotationSucceeded,
        category=EventCategory.AUTHENTICATION,
        workflow_name="user_token_rotation",
        phase=WorkflowPhase.SUCCEEDED,
        audit_action_name="USER_TOKEN_ROTATION_SUCCEEDED",
    ),
    EventMetadata(
        event_class=UserTokenRotationFailed,
        category=EventCategory.AUTHENTICATION,
        workflow_name="user_token_rotation",
        phase=WorkflowPhase.FAILED,
        audit_action_name="USER_TOKEN_ROTATION_FAILED",
    ),
    # Token Rejected (Operational Event)
    EventMetadata(
        event_class=TokenRejectedDueToRotation,
        category=EventCategory.AUTHENTICATION,
        workflow_name="token_rejected_due_to_rotation",
        phase=WorkflowPhase.OPERATIONAL,
        audit_action_name="TOKEN_REJECTED_VERSION_MISMATCH",
    ),
    # ═══════════════════════════════════════════════════════════
    # Authorization Events (6 events)
    # ═══════════════════════════════════════════════════════════
    # Role Assignment (Workflow 1)
    EventMetadata(
        event_class=RoleAssignmentAttempted,
        category=EventCategory.AUTHORIZATION,
        workflow_name="role_assignment",
        phase=WorkflowPhase.ATTEMPTED,
        audit_action_name="ROLE_ASSIGNMENT_ATTEMPTED",
    ),
    EventMetadata(
        event_class=RoleAssignmentSucceeded,
        category=EventCategory.AUTHORIZATION,
        workflow_name="role_assignment",
        phase=WorkflowPhase.SUCCEEDED,
        audit_action_name="ROLE_ASSIGNED",
    ),
    EventMetadata(
        event_class=RoleAssignmentFailed,
        category=EventCategory.AUTHORIZATION,
        workflow_name="role_assignment",
        phase=WorkflowPhase.FAILED,
        audit_action_name="ROLE_ASSIGNMENT_FAILED",
    ),
    # Role Revocation (Workflow 2)
    EventMetadata(
        event_class=RoleRevocationAttempted,
        category=EventCategory.AUTHORIZATION,
        workflow_name="role_revocation",
        phase=WorkflowPhase.ATTEMPTED,
        audit_action_name="ROLE_REVOCATION_ATTEMPTED",
    ),
    EventMetadata(
        event_class=RoleRevocationSucceeded,
        category=EventCategory.AUTHORIZATION,
        workflow_name="role_revocation",
        phase=WorkflowPhase.SUCCEEDED,
        audit_action_name="ROLE_REVOKED",
    ),
    EventMetadata(
        event_class=RoleRevocationFailed,
        category=EventCategory.AUTHORIZATION,
        workflow_name="role_revocation",
        phase=WorkflowPhase.FAILED,
        audit_action_name="ROLE_REVOCATION_FAILED",
    ),
    # ═══════════════════════════════════════════════════════════
    # Provider Events (9 events)
    # ═══════════════════════════════════════════════════════════
    # Provider Connection (Workflow 1)
    EventMetadata(
        event_class=ProviderConnectionAttempted,
        category=EventCategory.PROVIDER,
        workflow_name="provider_connection",
        phase=WorkflowPhase.ATTEMPTED,
        audit_action_name="PROVIDER_CONNECTION_ATTEMPTED",
    ),
    EventMetadata(
        event_class=ProviderConnectionSucceeded,
        category=EventCategory.PROVIDER,
        workflow_name="provider_connection",
        phase=WorkflowPhase.SUCCEEDED,
        audit_action_name="PROVIDER_CONNECTED",
    ),
    EventMetadata(
        event_class=ProviderConnectionFailed,
        category=EventCategory.PROVIDER,
        workflow_name="provider_connection",
        phase=WorkflowPhase.FAILED,
        audit_action_name="PROVIDER_CONNECTION_FAILED",
    ),
    # Provider Disconnection (Workflow 2)
    EventMetadata(
        event_class=ProviderDisconnectionAttempted,
        category=EventCategory.PROVIDER,
        workflow_name="provider_disconnection",
        phase=WorkflowPhase.ATTEMPTED,
        audit_action_name="PROVIDER_DISCONNECTION_ATTEMPTED",
    ),
    EventMetadata(
        event_class=ProviderDisconnectionSucceeded,
        category=EventCategory.PROVIDER,
        workflow_name="provider_disconnection",
        phase=WorkflowPhase.SUCCEEDED,
        audit_action_name="PROVIDER_DISCONNECTED",
    ),
    EventMetadata(
        event_class=ProviderDisconnectionFailed,
        category=EventCategory.PROVIDER,
        workflow_name="provider_disconnection",
        phase=WorkflowPhase.FAILED,
        audit_action_name="PROVIDER_DISCONNECTION_FAILED",
    ),
    # Provider Token Refresh (Workflow 3)
    EventMetadata(
        event_class=ProviderTokenRefreshAttempted,
        category=EventCategory.PROVIDER,
        workflow_name="provider_token_refresh",
        phase=WorkflowPhase.ATTEMPTED,
        audit_action_name="PROVIDER_TOKEN_REFRESH_ATTEMPTED",
    ),
    EventMetadata(
        event_class=ProviderTokenRefreshSucceeded,
        category=EventCategory.PROVIDER,
        workflow_name="provider_token_refresh",
        phase=WorkflowPhase.SUCCEEDED,
        audit_action_name="PROVIDER_TOKEN_REFRESHED",
    ),
    EventMetadata(
        event_class=ProviderTokenRefreshFailed,
        category=EventCategory.PROVIDER,
        workflow_name="provider_token_refresh",
        phase=WorkflowPhase.FAILED,
        audit_action_name="PROVIDER_TOKEN_REFRESH_FAILED",
    ),
    # ═══════════════════════════════════════════════════════════
    # Rate Limit Events (3 events)
    # ═══════════════════════════════════════════════════════════
    EventMetadata(
        event_class=RateLimitCheckAttempted,
        category=EventCategory.RATE_LIMIT,
        workflow_name="rate_limit_check",
        phase=WorkflowPhase.ATTEMPTED,
        audit_action_name="RATE_LIMIT_CHECK_ATTEMPTED",
    ),
    EventMetadata(
        event_class=RateLimitCheckAllowed,
        category=EventCategory.RATE_LIMIT,
        workflow_name="rate_limit_check",
        phase=WorkflowPhase.ALLOWED,
        audit_action_name="RATE_LIMIT_CHECK_ALLOWED",
    ),
    EventMetadata(
        event_class=RateLimitCheckDenied,
        category=EventCategory.RATE_LIMIT,
        workflow_name="rate_limit_check",
        phase=WorkflowPhase.DENIED,
        audit_action_name="RATE_LIMIT_CHECK_DENIED",
    ),
    # ═══════════════════════════════════════════════════════════
    # Session Events (14 events - 3-state workflows + operational)
    # ═══════════════════════════════════════════════════════════
    # Session Creation (operational - single-state)
    EventMetadata(
        event_class=SessionCreatedEvent,
        category=EventCategory.SESSION,
        workflow_name="session_created",
        phase=WorkflowPhase.OPERATIONAL,  # Single-state workflow event
        requires_audit=False,  # Not required (informational)
        audit_action_name="SESSION_CREATED",
    ),
    # Session Revocation (3-state workflow)
    EventMetadata(
        event_class=SessionRevocationAttempted,
        category=EventCategory.SESSION,
        workflow_name="session_revocation",
        phase=WorkflowPhase.ATTEMPTED,
        audit_action_name="SESSION_REVOCATION_ATTEMPTED",
    ),
    EventMetadata(
        event_class=SessionRevokedEvent,
        category=EventCategory.SESSION,
        workflow_name="session_revocation",
        phase=WorkflowPhase.SUCCEEDED,
        audit_action_name="SESSION_REVOKED",
    ),
    EventMetadata(
        event_class=SessionRevocationFailed,
        category=EventCategory.SESSION,
        workflow_name="session_revocation",
        phase=WorkflowPhase.FAILED,
        audit_action_name="SESSION_REVOCATION_FAILED",
    ),
    # Session Evicted (operational - single-state)
    EventMetadata(
        event_class=SessionEvictedEvent,
        category=EventCategory.SESSION,
        workflow_name="session_evicted",
        phase=WorkflowPhase.OPERATIONAL,  # Single-state workflow event
        audit_action_name="SESSION_EVICTED",
    ),
    # All Sessions Revocation (3-state workflow)
    EventMetadata(
        event_class=AllSessionsRevocationAttempted,
        category=EventCategory.SESSION,
        workflow_name="all_sessions_revocation",
        phase=WorkflowPhase.ATTEMPTED,
        audit_action_name="ALL_SESSIONS_REVOCATION_ATTEMPTED",
    ),
    EventMetadata(
        event_class=AllSessionsRevokedEvent,
        category=EventCategory.SESSION,
        workflow_name="all_sessions_revocation",
        phase=WorkflowPhase.SUCCEEDED,
        audit_action_name="ALL_SESSIONS_REVOKED",
    ),
    EventMetadata(
        event_class=AllSessionsRevocationFailed,
        category=EventCategory.SESSION,
        workflow_name="all_sessions_revocation",
        phase=WorkflowPhase.FAILED,
        audit_action_name="ALL_SESSIONS_REVOCATION_FAILED",
    ),
    # Operational Events (lightweight, no audit unless security-relevant)
    EventMetadata(
        event_class=SessionActivityUpdatedEvent,
        category=EventCategory.SESSION,
        workflow_name="session_activity_updated",
        phase=WorkflowPhase.OPERATIONAL,
        requires_audit=False,  # Lightweight telemetry
        audit_action_name="SESSION_ACTIVITY_UPDATED",
    ),
    EventMetadata(
        event_class=SessionProviderAccessEvent,
        category=EventCategory.SESSION,
        workflow_name="session_provider_access",
        phase=WorkflowPhase.OPERATIONAL,
        requires_audit=True,  # Security-relevant (track provider access)
        audit_action_name="SESSION_PROVIDER_ACCESS",
    ),
    EventMetadata(
        event_class=SuspiciousSessionActivityEvent,
        category=EventCategory.SESSION,
        workflow_name="suspicious_session_activity",
        phase=WorkflowPhase.OPERATIONAL,
        requires_audit=True,  # Security-relevant
        audit_action_name="SUSPICIOUS_SESSION_ACTIVITY",
    ),
    EventMetadata(
        event_class=SessionLimitExceededEvent,
        category=EventCategory.SESSION,
        workflow_name="session_limit_exceeded",
        phase=WorkflowPhase.OPERATIONAL,
        requires_audit=False,  # Informational
        audit_action_name="SESSION_LIMIT_EXCEEDED",
    ),
    # ═══════════════════════════════════════════════════════════
    # Data Sync Events (13 events - F7.7 Phase 2)
    # ═══════════════════════════════════════════════════════════
    # Account Sync (3 events)
    EventMetadata(
        event_class=AccountSyncAttempted,
        category=EventCategory.DATA_SYNC,
        workflow_name="account_sync",
        phase=WorkflowPhase.ATTEMPTED,
        audit_action_name="ACCOUNT_SYNC_ATTEMPTED",
    ),
    EventMetadata(
        event_class=AccountSyncSucceeded,
        category=EventCategory.DATA_SYNC,
        workflow_name="account_sync",
        phase=WorkflowPhase.SUCCEEDED,
        audit_action_name="ACCOUNT_SYNC_SUCCEEDED",
    ),
    EventMetadata(
        event_class=AccountSyncFailed,
        category=EventCategory.DATA_SYNC,
        workflow_name="account_sync",
        phase=WorkflowPhase.FAILED,
        audit_action_name="ACCOUNT_SYNC_FAILED",
    ),
    # Transaction Sync (3 events)
    EventMetadata(
        event_class=TransactionSyncAttempted,
        category=EventCategory.DATA_SYNC,
        workflow_name="transaction_sync",
        phase=WorkflowPhase.ATTEMPTED,
        audit_action_name="TRANSACTION_SYNC_ATTEMPTED",
    ),
    EventMetadata(
        event_class=TransactionSyncSucceeded,
        category=EventCategory.DATA_SYNC,
        workflow_name="transaction_sync",
        phase=WorkflowPhase.SUCCEEDED,
        audit_action_name="TRANSACTION_SYNC_SUCCEEDED",
    ),
    EventMetadata(
        event_class=TransactionSyncFailed,
        category=EventCategory.DATA_SYNC,
        workflow_name="transaction_sync",
        phase=WorkflowPhase.FAILED,
        audit_action_name="TRANSACTION_SYNC_FAILED",
    ),
    # Holdings Sync (3 events)
    EventMetadata(
        event_class=HoldingsSyncAttempted,
        category=EventCategory.DATA_SYNC,
        workflow_name="holdings_sync",
        phase=WorkflowPhase.ATTEMPTED,
        audit_action_name="HOLDINGS_SYNC_ATTEMPTED",
    ),
    EventMetadata(
        event_class=HoldingsSyncSucceeded,
        category=EventCategory.DATA_SYNC,
        workflow_name="holdings_sync",
        phase=WorkflowPhase.SUCCEEDED,
        audit_action_name="HOLDINGS_SYNC_SUCCEEDED",
    ),
    EventMetadata(
        event_class=HoldingsSyncFailed,
        category=EventCategory.DATA_SYNC,
        workflow_name="holdings_sync",
        phase=WorkflowPhase.FAILED,
        audit_action_name="HOLDINGS_SYNC_FAILED",
    ),
    # File Import (4 events: 3-state + operational progress)
    EventMetadata(
        event_class=FileImportAttempted,
        category=EventCategory.DATA_SYNC,
        workflow_name="file_import",
        phase=WorkflowPhase.ATTEMPTED,
        audit_action_name="FILE_IMPORT_ATTEMPTED",
    ),
    EventMetadata(
        event_class=FileImportSucceeded,
        category=EventCategory.DATA_SYNC,
        workflow_name="file_import",
        phase=WorkflowPhase.SUCCEEDED,
        audit_action_name="FILE_IMPORT_SUCCEEDED",
    ),
    EventMetadata(
        event_class=FileImportFailed,
        category=EventCategory.DATA_SYNC,
        workflow_name="file_import",
        phase=WorkflowPhase.FAILED,
        audit_action_name="FILE_IMPORT_FAILED",
    ),
    EventMetadata(
        event_class=FileImportProgress,
        category=EventCategory.DATA_SYNC,
        workflow_name="file_import",
        phase=WorkflowPhase.OPERATIONAL,
        requires_logging=True,
        requires_audit=False,  # Progress events don't need audit records
        audit_action_name="FILE_IMPORT_PROGRESS",  # For registry consistency
    ),
]


# ═══════════════════════════════════════════════════════════════
# Computed Views (for validation and introspection)
# ═══════════════════════════════════════════════════════════════


def get_all_events() -> list[Type[DomainEvent]]:
    """Get all registered event classes.

    Returns:
        List of event classes in registry.
    """
    return [meta.event_class for meta in EVENT_REGISTRY]


def get_events_requiring_handler(handler_type: str) -> list[Type[DomainEvent]]:
    """Get events requiring specific handler.

    Args:
        handler_type: "logging", "audit", "email", or "session"

    Returns:
        List of event classes requiring that handler.

    Raises:
        ValueError: If handler_type is invalid.
    """
    field_map = {
        "logging": "requires_logging",
        "audit": "requires_audit",
        "email": "requires_email",
        "session": "requires_session",
    }

    if handler_type not in field_map:
        raise ValueError(
            f"Invalid handler_type: {handler_type}. "
            f"Must be one of: {list(field_map.keys())}"
        )

    field = field_map[handler_type]
    return [meta.event_class for meta in EVENT_REGISTRY if getattr(meta, field)]


def get_workflow_events(workflow_name: str) -> dict[WorkflowPhase, Type[DomainEvent]]:
    """Get all events for a workflow.

    Args:
        workflow_name: Workflow name (e.g., "user_registration")

    Returns:
        Dict mapping phase to event class.
    """
    return {
        meta.phase: meta.event_class
        for meta in EVENT_REGISTRY
        if meta.workflow_name == workflow_name
    }


def get_expected_audit_actions() -> dict[Type[DomainEvent], str]:
    """Get mapping of event to expected AuditAction enum name.

    Returns:
        Dict mapping event class to audit action name.
    """
    return {
        meta.event_class: meta.audit_action_name
        for meta in EVENT_REGISTRY
        if meta.requires_audit
    }


def get_statistics() -> dict[str, int | dict[str, int]]:
    """Get registry statistics.

    Returns:
        Dict with counts by category, handler requirements, etc.
    """
    from collections import Counter

    return {
        "total_events": len(EVENT_REGISTRY),
        "by_category": dict(Counter(meta.category.value for meta in EVENT_REGISTRY)),
        "by_phase": dict(Counter(meta.phase.value for meta in EVENT_REGISTRY)),
        "requiring_logging": sum(1 for m in EVENT_REGISTRY if m.requires_logging),
        "requiring_audit": sum(1 for m in EVENT_REGISTRY if m.requires_audit),
        "requiring_email": sum(1 for m in EVENT_REGISTRY if m.requires_email),
        "requiring_session": sum(1 for m in EVENT_REGISTRY if m.requires_session),
        "total_workflows": len({m.workflow_name for m in EVENT_REGISTRY}),
    }
