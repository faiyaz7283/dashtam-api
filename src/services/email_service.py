"""Email service for sending transactional emails via AWS SES.

This service handles all email operations including:
- Sending email verification emails
- Sending password reset emails
- Sending welcome emails
- Generic email sending with HTML templates

Note: This service is asynchronous (uses `async def`) because
email sending involves I/O operations (HTTP calls to AWS SES).
See docs/development/architecture/async-vs-sync-patterns.md for details.
"""

import logging
from typing import Optional, Dict, Any
from datetime import datetime

import boto3
from botocore.exceptions import ClientError

from src.core.config import get_settings

logger = logging.getLogger(__name__)


class EmailService:
    """Service for sending emails via AWS SES.

    This service provides async email sending functionality using AWS SES.
    In development mode, emails can be logged instead of sent for testing.

    Features:
        - HTML email support with plain text fallback
        - Template-based emails for common scenarios
        - Development mode (logs emails instead of sending)
        - Error handling with graceful degradation
        - AWS SES integration with proper credentials

    Attributes:
        ses_client: Boto3 SES client
        from_email: Configured sender email address
        from_name: Configured sender display name
        development_mode: Whether to log emails instead of sending
    """

    def __init__(self, development_mode: bool = False):
        """Initialize email service with AWS SES configuration.

        Args:
            development_mode: If True, log emails instead of sending.
                            Useful for local development without AWS credentials.
        """
        settings = get_settings()

        self.from_email = settings.SES_FROM_EMAIL
        self.from_name = settings.SES_FROM_NAME
        self.development_mode = development_mode

        # Initialize SES client only if not in development mode
        if not self.development_mode:
            try:
                self.ses_client = boto3.client(
                    "ses",
                    region_name=settings.AWS_REGION,
                    aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                    aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                )
                logger.info("AWS SES client initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize AWS SES client: {e}")
                # Fall back to development mode if AWS credentials are invalid
                self.development_mode = True
                logger.warning(
                    "Falling back to development mode (emails will be logged)"
                )
        else:
            self.ses_client = None
            logger.info("Email service in development mode (emails will be logged)")

    async def send_email(
        self,
        to_email: str,
        subject: str,
        html_body: str,
        text_body: Optional[str] = None,
    ) -> bool:
        """Send an email via AWS SES or log it in development mode.

        Args:
            to_email: Recipient email address
            subject: Email subject line
            html_body: HTML email body
            text_body: Plain text fallback (optional)

        Returns:
            True if email sent successfully (or logged in dev mode), False otherwise

        Example:
            >>> service = EmailService()
            >>> success = await service.send_email(
            ...     to_email="user@example.com",
            ...     subject="Welcome!",
            ...     html_body="<h1>Welcome to Dashtam!</h1>",
            ...     text_body="Welcome to Dashtam!"
            ... )
            >>> success
            True
        """
        # Development mode: log email instead of sending
        if self.development_mode:
            logger.info("=" * 80)
            logger.info("📧 EMAIL (Development Mode - Not Sent)")
            logger.info("=" * 80)
            logger.info(f"From: {self.from_name} <{self.from_email}>")
            logger.info(f"To: {to_email}")
            logger.info(f"Subject: {subject}")
            logger.info("-" * 80)
            logger.info("HTML Body:")
            logger.info(html_body[:500] + "..." if len(html_body) > 500 else html_body)
            if text_body:
                logger.info("-" * 80)
                logger.info("Text Body:")
                logger.info(
                    text_body[:500] + "..." if len(text_body) > 500 else text_body
                )
            logger.info("=" * 80)
            return True

        # Production mode: send via AWS SES
        try:
            # Prepare email body
            body_data: Dict[str, Any] = {
                "Html": {
                    "Charset": "UTF-8",
                    "Data": html_body,
                }
            }

            # Add text fallback if provided
            if text_body:
                body_data["Text"] = {
                    "Charset": "UTF-8",
                    "Data": text_body,
                }

            # Send email via SES
            response = self.ses_client.send_email(
                Source=f"{self.from_name} <{self.from_email}>",
                Destination={
                    "ToAddresses": [to_email],
                },
                Message={
                    "Subject": {
                        "Charset": "UTF-8",
                        "Data": subject,
                    },
                    "Body": body_data,
                },
            )

            message_id = response.get("MessageId", "unknown")
            logger.info(
                f"Email sent successfully to {to_email} (MessageId: {message_id})"
            )
            return True

        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            error_message = e.response["Error"]["Message"]
            logger.error(
                f"AWS SES error sending email to {to_email}: {error_code} - {error_message}"
            )
            return False

        except Exception as e:
            logger.error(f"Unexpected error sending email to {to_email}: {e}")
            return False

    async def send_verification_email(
        self, to_email: str, verification_token: str, user_name: Optional[str] = None
    ) -> bool:
        """Send email verification email to user.

        Args:
            to_email: User's email address
            verification_token: Unique verification token
            user_name: User's name for personalization (optional)

        Returns:
            True if email sent successfully, False otherwise

        Example:
            >>> service = EmailService()
            >>> success = await service.send_verification_email(
            ...     to_email="user@example.com",
            ...     verification_token="abc123def456",
            ...     user_name="John Doe"
            ... )
        """
        settings = get_settings()

        # Generate verification URL
        # TODO: Update this with actual frontend URL when available
        verification_url = (
            f"https://localhost:3000/verify-email?token={verification_token}"
        )

        greeting = f"Hi {user_name}," if user_name else "Hello,"

        subject = "Verify Your Dashtam Account"

        html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
    <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
        <h2 style="color: #4A90E2;">Welcome to Dashtam!</h2>
        
        <p>{greeting}</p>
        
        <p>Thank you for signing up for Dashtam, your secure financial data aggregation platform.</p>
        
        <p>To complete your registration and verify your email address, please click the button below:</p>
        
        <div style="text-align: center; margin: 30px 0;">
            <a href="{verification_url}" 
               style="background-color: #4A90E2; 
                      color: white; 
                      padding: 12px 30px; 
                      text-decoration: none; 
                      border-radius: 5px; 
                      display: inline-block;">
                Verify Email Address
            </a>
        </div>
        
        <p>Or copy and paste this link into your browser:</p>
        <p style="word-break: break-all; color: #4A90E2;">{verification_url}</p>
        
        <p style="margin-top: 30px; color: #666; font-size: 14px;">
            This verification link will expire in {settings.EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS} hours.
        </p>
        
        <p style="color: #666; font-size: 14px;">
            If you didn't create a Dashtam account, please ignore this email.
        </p>
        
        <hr style="border: none; border-top: 1px solid #eee; margin: 30px 0;">
        
        <p style="color: #999; font-size: 12px; text-align: center;">
            © {datetime.utcnow().year} Dashtam. All rights reserved.
        </p>
    </div>
</body>
</html>
"""

        text_body = f"""
{greeting}

Thank you for signing up for Dashtam, your secure financial data aggregation platform.

To complete your registration and verify your email address, please visit:
{verification_url}

This verification link will expire in {settings.EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS} hours.

If you didn't create a Dashtam account, please ignore this email.

© {datetime.utcnow().year} Dashtam. All rights reserved.
"""

        return await self.send_email(
            to_email=to_email, subject=subject, html_body=html_body, text_body=text_body
        )

    async def send_password_reset_email(
        self, to_email: str, reset_token: str, user_name: Optional[str] = None
    ) -> bool:
        """Send password reset email to user.

        Args:
            to_email: User's email address
            reset_token: Unique password reset token
            user_name: User's name for personalization (optional)

        Returns:
            True if email sent successfully, False otherwise

        Example:
            >>> service = EmailService()
            >>> success = await service.send_password_reset_email(
            ...     to_email="user@example.com",
            ...     reset_token="xyz789abc123",
            ...     user_name="John Doe"
            ... )
        """
        settings = get_settings()

        # Generate reset URL
        # TODO: Update this with actual frontend URL when available
        reset_url = f"https://localhost:3000/reset-password?token={reset_token}"

        greeting = f"Hi {user_name}," if user_name else "Hello,"

        subject = "Reset Your Dashtam Password"

        html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
    <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
        <h2 style="color: #4A90E2;">Password Reset Request</h2>
        
        <p>{greeting}</p>
        
        <p>We received a request to reset the password for your Dashtam account.</p>
        
        <p>To reset your password, please click the button below:</p>
        
        <div style="text-align: center; margin: 30px 0;">
            <a href="{reset_url}" 
               style="background-color: #4A90E2; 
                      color: white; 
                      padding: 12px 30px; 
                      text-decoration: none; 
                      border-radius: 5px; 
                      display: inline-block;">
                Reset Password
            </a>
        </div>
        
        <p>Or copy and paste this link into your browser:</p>
        <p style="word-break: break-all; color: #4A90E2;">{reset_url}</p>
        
        <p style="margin-top: 30px; color: #666; font-size: 14px;">
            This password reset link will expire in {settings.PASSWORD_RESET_TOKEN_EXPIRE_HOURS} hour(s).
        </p>
        
        <p style="color: #E74C3C; font-weight: bold;">
            If you didn't request a password reset, please ignore this email and your password will remain unchanged.
        </p>
        
        <hr style="border: none; border-top: 1px solid #eee; margin: 30px 0;">
        
        <p style="color: #999; font-size: 12px; text-align: center;">
            © {datetime.utcnow().year} Dashtam. All rights reserved.
        </p>
    </div>
</body>
</html>
"""

        text_body = f"""
{greeting}

We received a request to reset the password for your Dashtam account.

To reset your password, please visit:
{reset_url}

This password reset link will expire in {settings.PASSWORD_RESET_TOKEN_EXPIRE_HOURS} hour(s).

If you didn't request a password reset, please ignore this email and your password will remain unchanged.

© {datetime.utcnow().year} Dashtam. All rights reserved.
"""

        return await self.send_email(
            to_email=to_email, subject=subject, html_body=html_body, text_body=text_body
        )

    async def send_welcome_email(
        self, to_email: str, user_name: Optional[str] = None
    ) -> bool:
        """Send welcome email to newly registered and verified user.

        Args:
            to_email: User's email address
            user_name: User's name for personalization (optional)

        Returns:
            True if email sent successfully, False otherwise

        Example:
            >>> service = EmailService()
            >>> success = await service.send_welcome_email(
            ...     to_email="user@example.com",
            ...     user_name="John Doe"
            ... )
        """
        greeting = f"Hi {user_name}," if user_name else "Hello,"

        subject = "Welcome to Dashtam!"

        html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
    <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
        <h2 style="color: #4A90E2;">Welcome to Dashtam! 🎉</h2>
        
        <p>{greeting}</p>
        
        <p>Your email has been verified and your account is now active!</p>
        
        <p>With Dashtam, you can securely:</p>
        <ul>
            <li>Connect your financial accounts from multiple institutions</li>
            <li>View all your accounts in one unified dashboard</li>
            <li>Access transaction history and financial data</li>
            <li>Keep your financial information secure with bank-level encryption</li>
        </ul>
        
        <p>Ready to get started? Log in to your account and connect your first financial institution.</p>
        
        <div style="text-align: center; margin: 30px 0;">
            <a href="https://localhost:3000/login" 
               style="background-color: #4A90E2; 
                      color: white; 
                      padding: 12px 30px; 
                      text-decoration: none; 
                      border-radius: 5px; 
                      display: inline-block;">
                Go to Dashboard
            </a>
        </div>
        
        <p>If you have any questions or need assistance, feel free to reach out to our support team.</p>
        
        <hr style="border: none; border-top: 1px solid #eee; margin: 30px 0;">
        
        <p style="color: #999; font-size: 12px; text-align: center;">
            © {datetime.utcnow().year} Dashtam. All rights reserved.
        </p>
    </div>
</body>
</html>
"""

        text_body = f"""
{greeting}

Your email has been verified and your account is now active!

With Dashtam, you can securely:
- Connect your financial accounts from multiple institutions
- View all your accounts in one unified dashboard
- Access transaction history and financial data
- Keep your financial information secure with bank-level encryption

Ready to get started? Log in to your account and connect your first financial institution at:
https://localhost:3000/login

If you have any questions or need assistance, feel free to reach out to our support team.

© {datetime.utcnow().year} Dashtam. All rights reserved.
"""

        return await self.send_email(
            to_email=to_email, subject=subject, html_body=html_body, text_body=text_body
        )

    async def send_password_changed_notification(
        self, to_email: str, user_name: Optional[str] = None
    ) -> bool:
        """Send notification email after password is successfully changed.

        Args:
            to_email: User's email address
            user_name: User's name for personalization (optional)

        Returns:
            True if email sent successfully, False otherwise

        Example:
            >>> service = EmailService()
            >>> success = await service.send_password_changed_notification(
            ...     to_email="user@example.com",
            ...     user_name="John Doe"
            ... )
        """
        greeting = f"Hi {user_name}," if user_name else "Hello,"

        subject = "Your Dashtam Password Was Changed"

        html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
    <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
        <h2 style="color: #4A90E2;">Password Changed Successfully</h2>
        
        <p>{greeting}</p>
        
        <p>This is a confirmation that the password for your Dashtam account was successfully changed.</p>
        
        <p style="color: #E74C3C; font-weight: bold; margin-top: 20px;">
            If you did not make this change, please contact our support team immediately.
        </p>
        
        <div style="text-align: center; margin: 30px 0;">
            <a href="mailto:support@dashtam.com" 
               style="background-color: #E74C3C; 
                      color: white; 
                      padding: 12px 30px; 
                      text-decoration: none; 
                      border-radius: 5px; 
                      display: inline-block;">
                Contact Support
            </a>
        </div>
        
        <p style="color: #666; font-size: 14px;">
            Changed at: {datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")} UTC
        </p>
        
        <hr style="border: none; border-top: 1px solid #eee; margin: 30px 0;">
        
        <p style="color: #999; font-size: 12px; text-align: center;">
            © {datetime.utcnow().year} Dashtam. All rights reserved.
        </p>
    </div>
</body>
</html>
"""

        text_body = f"""
{greeting}

This is a confirmation that the password for your Dashtam account was successfully changed.

If you did not make this change, please contact our support team immediately at support@dashtam.com

Changed at: {datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")} UTC

© {datetime.utcnow().year} Dashtam. All rights reserved.
"""

        return await self.send_email(
            to_email=to_email, subject=subject, html_body=html_body, text_body=text_body
        )
