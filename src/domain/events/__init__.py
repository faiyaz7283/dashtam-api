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
from src.domain.events.base_event import DomainEvent
from src.domain.protocols.event_bus_protocol import EventBusProtocol, EventHandler

__all__ = [
    # Base event
    "DomainEvent",
    # Protocols
    "EventBusProtocol",
    "EventHandler",
    # User Registration Events (3-state)
    "UserRegistrationAttempted",
    "UserRegistrationSucceeded",
    "UserRegistrationFailed",
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
