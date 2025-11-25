"""EmailProtocol - Port for email service implementations.

Defines the interface for sending emails in the application.
Infrastructure layer provides concrete implementations (StubEmailService, AWSEmailService).
"""

from typing import Protocol


class EmailProtocol(Protocol):
    """Email service protocol (port).

    Defines the interface for email operations.
    Infrastructure layer provides concrete implementations.

    This is a Protocol (not ABC) for structural typing.
    Implementations don't need to inherit from this.

    Methods:
        send_verification_email: Send email verification link
        send_password_reset_email: Send password reset link
        send_password_changed_notification: Notify user of password change

    Example Implementation:
        >>> class StubEmailService:
        ...     async def send_verification_email(
        ...         self,
        ...         to_email: str,
        ...         verification_url: str,
        ...     ) -> None:
        ...         # Log to console
        ...         print(f"[STUB] Verification email to {to_email}")
    """

    async def send_verification_email(
        self,
        to_email: str,
        verification_url: str,
    ) -> None:
        """Send email verification link to user.

        Args:
            to_email: Recipient email address.
            verification_url: Full URL with verification token.

        Example:
            >>> await email_service.send_verification_email(
            ...     to_email="user@example.com",
            ...     verification_url="https://app.com/verify?token=abc123",
            ... )
        """
        ...

    async def send_password_reset_email(
        self,
        to_email: str,
        reset_url: str,
    ) -> None:
        """Send password reset link to user.

        Args:
            to_email: Recipient email address.
            reset_url: Full URL with password reset token.

        Example:
            >>> await email_service.send_password_reset_email(
            ...     to_email="user@example.com",
            ...     reset_url="https://app.com/reset?token=xyz789",
            ... )
        """
        ...

    async def send_password_changed_notification(
        self,
        to_email: str,
    ) -> None:
        """Send notification that password was changed.

        Security notification to alert user of password change.

        Args:
            to_email: Recipient email address.

        Example:
            >>> await email_service.send_password_changed_notification(
            ...     to_email="user@example.com",
            ... )
        """
        ...
