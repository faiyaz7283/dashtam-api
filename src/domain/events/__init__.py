"""Domain events module.

This module exports domain events and the event bus protocol for use throughout
the application. Events enable decoupling between domain logic and infrastructure
concerns (audit, logging, email, session management).

Usage:
    >>> from src.domain.events import (
    ...     UserRegistrationSucceeded,
    ...     UserPasswordChangeSucceeded,
    ...     DomainEvent,
    ... )
    >>>
    >>> # Create event
    >>> event = UserRegistrationSucceeded(
    ...     user_id=user_id,
    ...     email="test@example.com"
    ... )
    >>>
    >>> # Publish event
    >>> await event_bus.publish(event)

Reference:
    - docs/architecture/domain-events-architecture.md for technical details
    - docs/guides/domain-events-usage.md for usage guide
"""

from src.domain.events.auth_events import (
    # Auth Token Refresh Events (JWT rotation)
    AuthTokenRefreshAttempted,
    AuthTokenRefreshFailed,
    AuthTokenRefreshSucceeded,
    # Email Verification Events
    EmailVerificationAttempted,
    EmailVerificationFailed,
    EmailVerificationSucceeded,
    # Global Token Rotation Events (3-state)
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
    # Token Rejection Event (Security Monitoring)
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
    # User Token Rotation Events (3-state)
    UserTokenRotationAttempted,
    UserTokenRotationFailed,
    UserTokenRotationSucceeded,
)
from src.domain.events.authorization_events import (
    # Role Assignment Events (3-state)
    RoleAssignmentAttempted,
    RoleAssignmentFailed,
    RoleAssignmentSucceeded,
    # Role Revocation Events (3-state)
    RoleRevocationAttempted,
    RoleRevocationFailed,
    RoleRevocationSucceeded,
)
from src.domain.events.base_event import DomainEvent
from src.domain.events.provider_events import (
    # Provider Connection Events (3-state)
    ProviderConnectionAttempted,
    ProviderConnectionFailed,
    ProviderConnectionSucceeded,
    # Provider Disconnection Events (3-state)
    ProviderDisconnectionAttempted,
    ProviderDisconnectionFailed,
    ProviderDisconnectionSucceeded,
    # Provider Token Refresh Events (3-state)
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
    AllSessionsRevokedEvent,
    SessionActivityUpdatedEvent,
    SessionCreatedEvent,
    SessionEvictedEvent,
    SessionLimitExceededEvent,
    SessionProviderAccessEvent,
    SessionRevokedEvent,
    SuspiciousSessionActivityEvent,
)
from src.domain.events.data_events import (
    # Account Sync Events (3-state)
    AccountSyncAttempted,
    AccountSyncFailed,
    AccountSyncSucceeded,
    # File Import Events (3-state + operational)
    FileImportAttempted,
    FileImportFailed,
    FileImportProgress,
    FileImportSucceeded,
    # Holdings Sync Events (3-state)
    HoldingsSyncAttempted,
    HoldingsSyncFailed,
    HoldingsSyncSucceeded,
    # Transaction Sync Events (3-state)
    TransactionSyncAttempted,
    TransactionSyncFailed,
    TransactionSyncSucceeded,
)
from src.domain.events.sse_event import (
    SSEEvent,
    SSEEventCategory,
    SSEEventType,
    get_category_for_event_type,
)
from src.domain.events.sse_registry import (
    DOMAIN_TO_SSE_MAPPING,
    SSE_EVENT_REGISTRY,
    DomainToSSEMapping,
    SSEEventMetadata,
    get_all_sse_event_types,
    get_domain_event_to_sse_mapping,
    get_events_by_category,
    get_registry_statistics,
    get_sse_event_metadata,
)

__all__ = [
    # Base event
    "DomainEvent",
    # User Registration Events (3-state)
    "UserRegistrationAttempted",
    "UserRegistrationSucceeded",
    "UserRegistrationFailed",
    # User Login Events (3-state)
    "UserLoginAttempted",
    "UserLoginSucceeded",
    "UserLoginFailed",
    # User Logout Events (3-state)
    "UserLogoutAttempted",
    "UserLogoutSucceeded",
    "UserLogoutFailed",
    # Email Verification Events (3-state)
    "EmailVerificationAttempted",
    "EmailVerificationSucceeded",
    "EmailVerificationFailed",
    # Auth Token Refresh Events (3-state)
    "AuthTokenRefreshAttempted",
    "AuthTokenRefreshSucceeded",
    "AuthTokenRefreshFailed",
    # Password Reset Request Events (3-state)
    "PasswordResetRequestAttempted",
    "PasswordResetRequestSucceeded",
    "PasswordResetRequestFailed",
    # Password Reset Confirm Events (3-state)
    "PasswordResetConfirmAttempted",
    "PasswordResetConfirmSucceeded",
    "PasswordResetConfirmFailed",
    # User Password Change Events (3-state)
    "UserPasswordChangeAttempted",
    "UserPasswordChangeSucceeded",
    "UserPasswordChangeFailed",
    # Provider Connection Events (3-state)
    "ProviderConnectionAttempted",
    "ProviderConnectionSucceeded",
    "ProviderConnectionFailed",
    # Provider Disconnection Events (3-state)
    "ProviderDisconnectionAttempted",
    "ProviderDisconnectionSucceeded",
    "ProviderDisconnectionFailed",
    # Provider Token Refresh Events (3-state)
    "ProviderTokenRefreshAttempted",
    "ProviderTokenRefreshSucceeded",
    "ProviderTokenRefreshFailed",
    # Global Token Rotation Events (3-state)
    "GlobalTokenRotationAttempted",
    "GlobalTokenRotationSucceeded",
    "GlobalTokenRotationFailed",
    # User Token Rotation Events (3-state)
    "UserTokenRotationAttempted",
    "UserTokenRotationSucceeded",
    "UserTokenRotationFailed",
    # Token Rejection Event (Security Monitoring)
    "TokenRejectedDueToRotation",
    # Role Assignment Events (3-state)
    "RoleAssignmentAttempted",
    "RoleAssignmentSucceeded",
    "RoleAssignmentFailed",
    # Role Revocation Events (3-state)
    "RoleRevocationAttempted",
    "RoleRevocationSucceeded",
    "RoleRevocationFailed",
    # Rate Limit Check Events (3-state)
    "RateLimitCheckAttempted",
    "RateLimitCheckAllowed",
    "RateLimitCheckDenied",
    # Session Management Events
    "AllSessionsRevokedEvent",
    "SessionActivityUpdatedEvent",
    "SessionCreatedEvent",
    "SessionEvictedEvent",
    "SessionLimitExceededEvent",
    "SessionProviderAccessEvent",
    "SessionRevokedEvent",
    "SuspiciousSessionActivityEvent",
    # Data Sync Events (3-state)
    "AccountSyncAttempted",
    "AccountSyncSucceeded",
    "AccountSyncFailed",
    "TransactionSyncAttempted",
    "TransactionSyncSucceeded",
    "TransactionSyncFailed",
    "HoldingsSyncAttempted",
    "HoldingsSyncSucceeded",
    "HoldingsSyncFailed",
    # File Import Events (3-state + operational)
    "FileImportAttempted",
    "FileImportSucceeded",
    "FileImportFailed",
    "FileImportProgress",
    # SSE Events (wire format for real-time notifications)
    "SSEEvent",
    "SSEEventCategory",
    "SSEEventType",
    "get_category_for_event_type",
    # SSE Registry (SSOT for event mappings)
    "DOMAIN_TO_SSE_MAPPING",
    "SSE_EVENT_REGISTRY",
    "DomainToSSEMapping",
    "SSEEventMetadata",
    "get_all_sse_event_types",
    "get_domain_event_to_sse_mapping",
    "get_events_by_category",
    "get_registry_statistics",
    "get_sse_event_metadata",
]
