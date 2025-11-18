"""Email event handler stub for domain events.

This module implements a STUB email handler that logs when emails would be sent.
Provides structure for future email service integration (SendGrid, AWS SES, etc.)
without blocking current development.

Email Templates Needed (Future):
    - welcome_email: Sent after UserRegistrationSucceeded
      - Subject: "Welcome to Dashtam!"
      - Body: Welcome message + email verification link
      - Variables: {user_email, verification_token}

    - password_changed_email: Sent after UserPasswordChangeSucceeded
      - Subject: "Your Dashtam password was changed"
      - Body: Security notification + support contact
      - Variables: {user_email, change_timestamp, ip_address}

Integration Strategy (Future Phase):
    1. Create EmailProtocol in src/domain/protocols/email_protocol.py
    2. Implement SendGridEmailAdapter or SESEmailAdapter in src/infrastructure/email/
    3. Add email template engine (Jinja2) in src/infrastructure/email/templates/
    4. Update this handler to use EmailProtocol instead of logging
    5. Add email sending to container with get_email_service()

Usage:
    >>> # Container wires up subscriptions at startup
    >>> event_bus = get_event_bus()
    >>> email_handler = EmailEventHandler(logger=get_logger())
    >>>
    >>> # Subscribe to SUCCEEDED events only
    >>> event_bus.subscribe(UserRegistrationSucceeded, email_handler.handle_user_registration_succeeded)
    >>> event_bus.subscribe(UserPasswordChangeSucceeded, email_handler.handle_user_password_change_succeeded)

Reference:
    - docs/architecture/domain-events-architecture.md (Lines 1304-1362)
"""

from src.domain.events.authentication_events import (
    UserPasswordChangeSucceeded,
    UserRegistrationSucceeded,
)
from src.domain.protocols.logger_protocol import LoggerProtocol


class EmailEventHandler:
    """Event handler stub for email sending.

    STUB IMPLEMENTATION: Currently logs when emails would be sent. Replace
    with real EmailProtocol implementation when email service is ready.

    Subscribes to SUCCEEDED events only (don't email on ATTEMPT or FAILURE).

    Attributes:
        _logger: Logger protocol implementation (from container).

    Example:
        >>> # Create handler
        >>> handler = EmailEventHandler(logger=get_logger())
        >>>
        >>> # Subscribe to events (in container)
        >>> event_bus.subscribe(UserRegistrationSucceeded, handler.handle_user_registration_succeeded)
        >>>
        >>> # Events automatically trigger email logging
        >>> await event_bus.publish(UserRegistrationSucceeded(
        ...     user_id=uuid4(),
        ...     email="test@example.com"
        ... ))
        >>> # Log output: {"event": "email_would_be_sent", "template": "welcome_email", ...}
    """

    def __init__(self, logger: LoggerProtocol) -> None:
        """Initialize email handler with logger.

        Args:
            logger: Logger protocol implementation from container. Used for
                structured logging of email events (stub only).

        Example:
            >>> from src.core.container import get_logger
            >>> logger = get_logger()
            >>> handler = EmailEventHandler(logger=logger)
        """
        self._logger = logger

    async def handle_user_registration_succeeded(
        self,
        event: UserRegistrationSucceeded,
    ) -> None:
        """Send welcome email after successful registration (STUB).

        STUB: Logs email would be sent. Future: Send actual email via EmailProtocol.

        Args:
            event: UserRegistrationSucceeded event with user_id and email.

        Email Template (Future):
            - Template: welcome_email
            - Subject: "Welcome to Dashtam!"
            - To: event.email
            - Variables:
                - user_email: event.email
                - verification_token: (generated from user_id)
                - verification_link: f"https://dashtam.com/verify?token={token}"

        Notes:
            - Email sent asynchronously (fail-open - don't block registration)
            - Includes email verification link (click to verify)
            - User can resend verification email if needed
        """
        self._logger.info(
            "email_would_be_sent",
            template="welcome_email",
            recipient=event.email,
            user_id=str(event.user_id),
            event_id=str(event.event_id),
            subject="Welcome to Dashtam!",
            # Future: Generate verification token and link
            note="STUB: Replace with EmailProtocol.send() when email service ready",
        )

    async def handle_user_password_change_succeeded(
        self,
        event: UserPasswordChangeSucceeded,
    ) -> None:
        """Send password change notification email (STUB).

        STUB: Logs email would be sent. Future: Send actual email via EmailProtocol.

        Args:
            event: UserPasswordChangeSucceeded event with user_id.

        Email Template (Future):
            - Template: password_changed_email
            - Subject: "Your Dashtam password was changed"
            - To: (fetch user email from database via user_id)
            - Variables:
                - change_timestamp: event.occurred_at
                - initiated_by: event.initiated_by
                - support_email: "support@dashtam.com"
                - support_message: "If you didn't make this change, contact us immediately."

        Notes:
            - CRITICAL security notification (user must be alerted)
            - Sent even if initiated_by="admin" (user should know)
            - Email sent asynchronously (fail-open)
            - Future: Fetch user email from database (not in event to keep events lean)
        """
        self._logger.info(
            "email_would_be_sent",
            template="password_changed_email",
            user_id=str(event.user_id),
            event_id=str(event.event_id),
            subject="Your Dashtam password was changed",
            initiated_by=event.initiated_by,
            change_timestamp=event.occurred_at.isoformat(),
            # Future: Fetch user email from database
            note="STUB: Replace with EmailProtocol.send() when email service ready. Fetch user email from DB.",
        )
