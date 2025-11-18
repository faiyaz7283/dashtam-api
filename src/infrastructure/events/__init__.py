"""Infrastructure event implementations.

This module exports the in-memory event bus implementation and event handlers
for infrastructure integration (logging, audit, email, session).

Event Bus:
    - InMemoryEventBus: Production event bus with fail-open behavior

Event Handlers:
    - LoggingEventHandler: Structured logging for all domain events
    - AuditEventHandler: Audit trail creation for compliance
    - EmailEventHandler: Email notifications (stub)
    - SessionEventHandler: Session management (stub)

Usage:
    >>> from src.infrastructure.events import InMemoryEventBus
    >>> from src.infrastructure.events.handlers import (
    ...     LoggingEventHandler,
    ...     AuditEventHandler,
    ... )
    >>>
    >>> # Create event bus
    >>> event_bus = InMemoryEventBus(logger=logger)
    >>>
    >>> # Wire up handlers
    >>> logging_handler = LoggingEventHandler(logger=logger)
    >>> audit_handler = AuditEventHandler(database=database)
    >>>
    >>> event_bus.subscribe(UserRegistrationSucceeded, logging_handler.handle_user_registration_succeeded)
    >>> event_bus.subscribe(UserRegistrationSucceeded, audit_handler.handle_user_registration_succeeded)

Reference:
    - docs/architecture/domain-events-architecture.md for architecture
    - docs/guides/domain-events-usage.md for usage patterns
"""

from src.infrastructure.events.in_memory_event_bus import InMemoryEventBus

__all__ = [
    "InMemoryEventBus",
]
