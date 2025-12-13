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

from src.core.config import Settings
from src.domain.events.auth_events import (
    EmailVerificationSucceeded,
    PasswordResetConfirmSucceeded,
    PasswordResetRequestSucceeded,
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
        _settings: Application settings for configuration (e.g., verification URL).

    Example:
        >>> # Create handler
        >>> handler = EmailEventHandler(logger=get_logger(), settings=get_settings())
        >>>
        >>> # Subscribe to events (in container)
        >>> event_bus.subscribe(UserRegistrationSucceeded, handler.handle_user_registration_succeeded)
        >>>
        >>> # Events automatically trigger email logging
        >>> await event_bus.publish(UserRegistrationSucceeded(
        ...     user_id=uuid7(),
        ...     email="test@example.com"
        ... ))
        >>> # Log output: {"event": "email_would_be_sent", "template": "welcome_email", ...}
    """

    def __init__(self, logger: LoggerProtocol, settings: Settings) -> None:
        """Initialize email handler with logger and settings.

        Args:
            logger: Logger protocol implementation from container. Used for
                structured logging of email events (stub only).
            settings: Application settings providing configuration such as
                verification_url_base for email links.

        Example:
            >>> from src.core.container import get_logger, get_settings
            >>> logger = get_logger()
            >>> settings = get_settings()
            >>> handler = EmailEventHandler(logger=logger, settings=settings)
        """
        self._logger = logger
        self._settings = settings

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
                - verification_link: f"{settings.verification_url_base}/verify?token={{token}}"

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

    async def handle_password_reset_request_succeeded(
        self,
        event: PasswordResetRequestSucceeded,
    ) -> None:
        """Send password reset email after successful request (STUB).

        STUB: Logs email would be sent. Future: Send actual email via EmailProtocol.

        Args:
            event: PasswordResetRequestSucceeded event with user_id, email, and reset_token.

        Email Template (Future):
            - Template: password_reset_email
            - Subject: "Reset your Dashtam password"
            - To: event.email
            - Variables:
                - user_email: event.email
                - reset_token: event.reset_token
                - reset_link: f"{settings.reset_url_base}/reset?token={{token}}"
                - expiration: "This link expires in 1 hour"

        Notes:
            - Email sent asynchronously (fail-open - don't block request)
            - Includes password reset link with token
            - Link expires after 1 hour (security requirement)
            - User can request new reset email if needed
        """
        self._logger.info(
            "email_would_be_sent",
            template="password_reset_email",
            recipient=event.email,
            user_id=str(event.user_id),
            event_id=str(event.event_id),
            subject="Reset your Dashtam password",
            # Future: Generate reset link with token
            note="STUB: Replace with EmailProtocol.send() when email service ready. Include reset link.",
        )

    async def handle_password_reset_confirm_succeeded(
        self,
        event: PasswordResetConfirmSucceeded,
    ) -> None:
        """Send password reset confirmation email (STUB).

        STUB: Logs email would be sent. Future: Send actual email via EmailProtocol.

        Args:
            event: PasswordResetConfirmSucceeded event with user_id and email.

        Email Template (Future):
            - Template: password_reset_completed_email
            - Subject: "Your Dashtam password was reset"
            - To: event.email
            - Variables:
                - user_email: event.email
                - reset_timestamp: event.occurred_at
                - support_email: "support@dashtam.com"
                - support_message: "If you didn't make this change, contact us immediately."

        Notes:
            - CRITICAL security notification (user must be alerted)
            - Sent after password reset is complete
            - Email sent asynchronously (fail-open)
        """
        self._logger.info(
            "email_would_be_sent",
            template="password_reset_completed_email",
            recipient=event.email,
            user_id=str(event.user_id),
            event_id=str(event.event_id),
            subject="Your Dashtam password was reset",
            reset_timestamp=event.occurred_at.isoformat(),
            note="STUB: Replace with EmailProtocol.send() when email service ready.",
        )

    async def handle_email_verification_succeeded(
        self,
        event: EmailVerificationSucceeded,
    ) -> None:
        """Send welcome email after email verification (STUB - Optional).

        STUB: Logs email would be sent. Future: Send actual email via EmailProtocol.

        Args:
            event: EmailVerificationSucceeded event with user_id and email.

        Email Template (Future):
            - Template: email_verified_welcome_email
            - Subject: "Welcome to Dashtam! Your email is verified"
            - To: event.email
            - Variables:
                - user_email: event.email
                - dashboard_link: f"{settings.app_base_url}/dashboard"
                - getting_started_guide: Link to user guide

        Notes:
            - Optional welcome email (user already received one at registration)
            - Email sent asynchronously (fail-open)
            - Can be disabled in settings if redundant
        """
        self._logger.info(
            "email_would_be_sent",
            template="email_verified_welcome_email",
            recipient=event.email,
            user_id=str(event.user_id),
            event_id=str(event.event_id),
            subject="Welcome to Dashtam! Your email is verified",
            note="STUB: Optional welcome email. Replace with EmailProtocol.send() when ready.",
        )
