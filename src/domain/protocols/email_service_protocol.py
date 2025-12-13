"""EmailServiceProtocol - Domain protocol for email operations.

This protocol defines the interface for sending emails.
Infrastructure provides concrete implementations (Stub, AWS SES, etc.).

Following hexagonal architecture:
- Domain defines what it needs (protocol/port)
- Infrastructure provides implementation (adapter)
- Application layer uses protocol, not concrete implementation
"""

from typing import Protocol


class EmailServiceProtocol(Protocol):
    """Protocol for email sending operations.

    Defines the contract that all email service implementations must satisfy.
    Used for sending verification emails, password reset emails, etc.

    Implementations:
        - StubEmailService: src/infrastructure/email/stub_email_service.py (dev/test)
        - SESEmailService: src/infrastructure/email/ses_email_service.py (production)
    """

    async def send_verification_email(
        self,
        to_email: str,
        verification_url: str,
    ) -> None:
        """Send email verification email.

        Args:
            to_email: Recipient email address.
            verification_url: Full URL with verification token.
        """
        ...

    async def send_password_reset_email(
        self,
        to_email: str,
        reset_url: str,
    ) -> None:
        """Send password reset email.

        Args:
            to_email: Recipient email address.
            reset_url: Full URL with password reset token.
        """
        ...

    async def send_password_changed_notification(
        self,
        to_email: str,
    ) -> None:
        """Send notification that password was changed.

        Args:
            to_email: Recipient email address.
        """
        ...
