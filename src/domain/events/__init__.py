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
    EmailVerificationAttempted,
    EmailVerificationFailed,
    EmailVerificationSucceeded,
    ProviderConnectionAttempted,
    ProviderConnectionFailed,
    ProviderConnectionSucceeded,
    TokenRefreshAttempted,
    TokenRefreshFailed,
    TokenRefreshSucceeded,
    UserLoginAttempted,
    UserLoginFailed,
    UserLoginSucceeded,
    UserPasswordChangeAttempted,
    UserPasswordChangeFailed,
    UserPasswordChangeSucceeded,
    UserRegistrationAttempted,
    UserRegistrationFailed,
    UserRegistrationSucceeded,
)
from src.domain.events.base_event import DomainEvent

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
    # Email Verification Events (3-state)
    "EmailVerificationAttempted",
    "EmailVerificationSucceeded",
    "EmailVerificationFailed",
    # User Password Change Events (3-state)
    "UserPasswordChangeAttempted",
    "UserPasswordChangeSucceeded",
    "UserPasswordChangeFailed",
    # Provider Connection Events (3-state)
    "ProviderConnectionAttempted",
    "ProviderConnectionSucceeded",
    "ProviderConnectionFailed",
    # Token Refresh Events (3-state)
    "TokenRefreshAttempted",
    "TokenRefreshSucceeded",
    "TokenRefreshFailed",
]
