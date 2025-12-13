"""StubEmailService - Console logging implementation for development.

Fake email service that logs to console instead of sending real emails.
Used in development, testing, and CI environments.
"""

from src.domain.protocols.logger_protocol import LoggerProtocol


class StubEmailService:
    """Stub email service for development (logs to console).

    Implements EmailProtocol by logging email details instead of sending.
    No external dependencies, no AWS account required.

    Use in development/testing to:
    - See what emails would be sent
    - Verify verification URLs and reset links
    - Test authentication flows without AWS SES

    Attributes:
        logger: Logger for outputting email details.

    Example:
        >>> from src.core.container import get_logger
        >>> email_service = StubEmailService(logger=get_logger())
        >>> await email_service.send_verification_email(
        ...     to_email="user@example.com",
        ...     verification_url="https://app.com/verify?token=abc123",
        ... )
        # Logs: [EMAIL STUB] Would send verification email to user@example.com...
    """

    def __init__(self, logger: LoggerProtocol) -> None:
        """Initialize stub email service with logger.

        Args:
            logger: Logger instance for console output.
        """
        self.logger = logger

    async def send_verification_email(
        self,
        to_email: str,
        verification_url: str,
    ) -> None:
        """Log email verification details to console.

        Args:
            to_email: Recipient email address.
            verification_url: Full URL with verification token.
        """
        self.logger.info(
            "[EMAIL STUB] Would send verification email",
            to_email=to_email,
            subject="Verify your Dashtam account",
            verification_url=verification_url,
            template="verification_email",
        )
        # In development, copy this URL to test:
        self.logger.info(
            "[EMAIL STUB] Copy verification URL to browser",
            url=verification_url,
        )

    async def send_password_reset_email(
        self,
        to_email: str,
        reset_url: str,
    ) -> None:
        """Log password reset details to console.

        Args:
            to_email: Recipient email address.
            reset_url: Full URL with password reset token.
        """
        self.logger.info(
            "[EMAIL STUB] Would send password reset email",
            to_email=to_email,
            subject="Reset your Dashtam password",
            reset_url=reset_url,
            template="password_reset_email",
        )
        # In development, copy this URL to test:
        self.logger.info(
            "[EMAIL STUB] Copy reset URL to browser",
            url=reset_url,
        )

    async def send_password_changed_notification(
        self,
        to_email: str,
    ) -> None:
        """Log password changed notification to console.

        Args:
            to_email: Recipient email address.
        """
        self.logger.info(
            "[EMAIL STUB] Would send password changed notification",
            to_email=to_email,
            subject="Your Dashtam password was changed",
            template="password_changed_notification",
        )
