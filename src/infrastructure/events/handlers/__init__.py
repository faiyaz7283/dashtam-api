"""Event handlers for infrastructure integration.

This module exports all event handlers that react to domain events and perform
infrastructure-specific side effects (logging, audit, email, session management).

Handlers:
    - LoggingEventHandler: Structured logging with appropriate severity levels
    - AuditEventHandler: Creates immutable audit trail records
    - EmailEventHandler: Sends email notifications (stub - logs intent)
    - SessionEventHandler: Manages session invalidation (stub - logs intent)

All handlers follow fail-open design - one handler failure doesn't break others.

Usage:
    >>> from src.infrastructure.events.handlers import (
    ...     LoggingEventHandler,
    ...     AuditEventHandler,
    ...     EmailEventHandler,
    ...     SessionEventHandler,
    ... )
    >>>
    >>> # Create handlers
    >>> logging_handler = LoggingEventHandler(logger=logger)
    >>> audit_handler = AuditEventHandler(database=database)
    >>> email_handler = EmailEventHandler(logger=logger)
    >>> session_handler = SessionEventHandler(logger=logger)
    >>>
    >>> # Subscribe to events in container
    >>> event_bus.subscribe(UserRegistrationSucceeded, logging_handler.handle_user_registration_succeeded)
    >>> event_bus.subscribe(UserRegistrationSucceeded, audit_handler.handle_user_registration_succeeded)
    >>> event_bus.subscribe(UserRegistrationSucceeded, email_handler.handle_user_registration_succeeded)

Reference:
    - docs/guides/domain-events-usage.md Section "Creating Event Handlers"
"""

from src.infrastructure.events.handlers.audit_event_handler import AuditEventHandler
from src.infrastructure.events.handlers.email_event_handler import EmailEventHandler
from src.infrastructure.events.handlers.logging_event_handler import LoggingEventHandler
from src.infrastructure.events.handlers.session_event_handler import SessionEventHandler

__all__ = [
    "LoggingEventHandler",
    "AuditEventHandler",
    "EmailEventHandler",
    "SessionEventHandler",
]
