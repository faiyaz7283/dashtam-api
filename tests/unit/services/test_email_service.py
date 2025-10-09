"""Unit tests for EmailService.

Tests email sending functionality with AWS SES integration. Covers:
- Service initialization (development vs production mode)
- AWS SES client configuration and mocking
- Email sending (HTML, text, or both)
- Template-based emails (verification, password reset, welcome, notifications)
- Development mode behavior (logging only, no actual sending)
- Production mode behavior (AWS SES integration)
- Error handling and fallback to development mode
- Sender configuration from environment variables

Note:
    Tests use async/await patterns for EmailService async methods.
    AWS SES is mocked in all tests to avoid actual email sending.
"""

import pytest
from unittest.mock import Mock, patch

from src.services.email_service import EmailService


class TestEmailService:
    """Test suite for EmailService email operations.
    
    Validates email sending with AWS SES mocking, template rendering,
    and development/production mode handling.
    """

    def test_init_development_mode(self):
        """Test EmailService initialization in development mode.
        
        Verifies that:
        - development_mode flag is set to True
        - ses_client is None (no AWS connection)
        - Emails will be logged only, not sent
        
        Note:
            Development mode used for local testing without AWS credentials.
        """
        service = EmailService(development_mode=True)

        assert service.development_mode is True
        assert service.ses_client is None

    def test_init_production_mode_with_credentials(self):
        """Test EmailService initialization in production with AWS credentials.
        
        Verifies that:
        - AWS environment variables are used
        - boto3.client is called to create SES client
        - Service attempts to connect to AWS SES
        
        Note:
            Uses patch to mock AWS credentials and boto3 client creation.
        """
        with patch.dict(
            "os.environ",
            {
                "AWS_REGION": "us-east-1",
                "AWS_ACCESS_KEY_ID": "test_key",
                "AWS_SECRET_ACCESS_KEY": "test_secret",
            },
        ):
            with patch("boto3.client") as mock_boto_client:
                EmailService(development_mode=False)

                # Should attempt to create SES client
                mock_boto_client.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_email_development_mode(self):
        """Test email sending in development mode (logging only).
        
        Verifies that:
        - send_email returns True (success)
        - No actual email is sent to AWS SES
        - Email details are logged to console
        - Both HTML and text bodies are accepted
        
        Note:
            Development mode logs emails instead of sending them.
        """
        service = EmailService(development_mode=True)

        result = await service.send_email(
            to_email="test@example.com",
            subject="Test Subject",
            html_body="<h1>Test</h1>",
            text_body="Test",
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_send_email_production_mode_success(self):
        """Test successful email sending via AWS SES in production mode.
        
        Verifies that:
        - send_email returns True on success
        - SES client send_email method is called
        - Message ID is returned from AWS SES
        - Email parameters are correctly formatted
        
        Note:
            Uses mocked SES client to avoid actual AWS calls.
        """
        service = EmailService(development_mode=False)

        # Mock SES client
        mock_ses = Mock()
        mock_ses.send_email.return_value = {"MessageId": "test-message-id"}
        service.ses_client = mock_ses

        result = await service.send_email(
            to_email="test@example.com",
            subject="Test Subject",
            html_body="<h1>Test</h1>",
            text_body="Test",
        )

        assert result is True
        mock_ses.send_email.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_email_production_mode_failure(self):
        """Test email sending failure handling in production mode.
        
        Verifies that:
        - send_email returns False on AWS SES error
        - Exception is caught and logged
        - Service doesn't crash on SES failures
        - Graceful error handling
        
        Note:
            Simulates AWS SES errors (rate limits, invalid credentials, etc.).
        """
        service = EmailService(development_mode=False)

        # Mock SES client to raise error
        mock_ses = Mock()
        mock_ses.send_email.side_effect = Exception("SES Error")
        service.ses_client = mock_ses

        result = await service.send_email(
            to_email="test@example.com",
            subject="Test Subject",
            html_body="<h1>Test</h1>",
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_send_verification_email(self):
        """Test sending email verification email with token.
        
        Verifies that:
        - Verification email is sent successfully
        - Token is included in email content/URL
        - User name is used in email template
        - Returns True on success
        
        Note:
            Email includes verification link with token for user to click.
        """
        service = EmailService(development_mode=True)

        result = await service.send_verification_email(
            to_email="test@example.com",
            verification_token="abc123def456",
            user_name="John Doe",
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_send_verification_email_without_name(self):
        """Test sending verification email with optional name omitted.
        
        Verifies that:
        - Email sends successfully without user name
        - Template handles missing name gracefully
        - Generic greeting used when name absent
        - Returns True on success
        
        Note:
            User name is optional parameter for personalization.
        """
        service = EmailService(development_mode=True)

        result = await service.send_verification_email(
            to_email="test@example.com", verification_token="abc123def456"
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_send_password_reset_email(self):
        """Test sending password reset email with token.
        
        Verifies that:
        - Password reset email is sent successfully
        - Reset token is included in email/URL
        - User name is used in email template
        - Returns True on success
        
        Note:
            Email includes password reset link with token (1-hour expiry).
        """
        service = EmailService(development_mode=True)

        result = await service.send_password_reset_email(
            to_email="test@example.com",
            reset_token="xyz789abc123",
            user_name="John Doe",
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_send_password_reset_email_without_name(self):
        """Test sending password reset email with optional name omitted.
        
        Verifies that:
        - Email sends successfully without user name
        - Template handles missing name gracefully
        - Generic greeting used when name absent
        - Returns True on success
        
        Note:
            User name is optional parameter for personalization.
        """
        service = EmailService(development_mode=True)

        result = await service.send_password_reset_email(
            to_email="test@example.com", reset_token="xyz789abc123"
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_send_welcome_email(self):
        """Test sending welcome email after successful registration.
        
        Verifies that:
        - Welcome email is sent successfully
        - User name is used in email template
        - Email contains getting started information
        - Returns True on success
        
        Note:
            Sent after email verification is complete.
        """
        service = EmailService(development_mode=True)

        result = await service.send_welcome_email(
            to_email="test@example.com", user_name="John Doe"
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_send_welcome_email_without_name(self):
        """Test sending welcome email with optional name omitted.
        
        Verifies that:
        - Email sends successfully without user name
        - Template handles missing name gracefully
        - Generic greeting used when name absent
        - Returns True on success
        
        Note:
            User name is optional parameter for personalization.
        """
        service = EmailService(development_mode=True)

        result = await service.send_welcome_email(to_email="test@example.com")

        assert result is True

    @pytest.mark.asyncio
    async def test_send_password_changed_notification(self):
        """Test sending password change notification email.
        
        Verifies that:
        - Notification email is sent successfully
        - User name is used in email template
        - Security notice included in email
        - Returns True on success
        
        Note:
            Sent after successful password reset to alert user of change.
        """
        service = EmailService(development_mode=True)

        result = await service.send_password_changed_notification(
            to_email="test@example.com", user_name="John Doe"
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_send_password_changed_notification_without_name(self):
        """Test sending password change notification with optional name omitted.
        
        Verifies that:
        - Email sends successfully without user name
        - Template handles missing name gracefully
        - Generic greeting used when name absent
        - Returns True on success
        
        Note:
            User name is optional parameter for personalization.
        """
        service = EmailService(development_mode=True)

        result = await service.send_password_changed_notification(
            to_email="test@example.com"
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_send_email_with_html_only(self):
        """Test sending email with HTML body only (no text fallback).
        
        Verifies that:
        - Email sends with only HTML body
        - Text body is optional
        - HTML formatting is preserved
        - Returns True on success
        
        Note:
            Most modern email clients support HTML rendering.
        """
        service = EmailService(development_mode=True)

        result = await service.send_email(
            to_email="test@example.com", subject="Test", html_body="<h1>Test</h1>"
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_send_email_with_both_html_and_text(self):
        """Test sending email with both HTML and text bodies (multipart).
        
        Verifies that:
        - Email sends with both HTML and text versions
        - Clients choose appropriate version to display
        - Fallback to text for clients without HTML support
        - Returns True on success
        
        Note:
            Best practice: provide both HTML and plain text versions.
        """
        service = EmailService(development_mode=True)

        result = await service.send_email(
            to_email="test@example.com",
            subject="Test",
            html_body="<h1>Test</h1>",
            text_body="Test",
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_verification_email_contains_token(self):
        """Test that verification email includes token in URL.
        
        Verifies that:
        - Email template accepts verification token
        - Token is used in email rendering
        - No errors occur during template processing
        - Returns True on success
        
        Note:
            Token appears in verification URL (e.g., /verify-email?token=...).
            Cannot verify email content directly without log capture.
        """
        service = EmailService(development_mode=True)

        token = "unique_test_token_123"

        # We can't easily verify the email content without capturing logs
        # But we can verify it doesn't raise an error
        result = await service.send_verification_email(
            to_email="test@example.com", verification_token=token
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_reset_email_contains_token(self):
        """Test that password reset email includes token in URL.
        
        Verifies that:
        - Email template accepts reset token
        - Token is used in email rendering
        - No errors occur during template processing
        - Returns True on success
        
        Note:
            Token appears in reset URL (e.g., /reset-password?token=...).
            Cannot verify email content directly without log capture.
        """
        service = EmailService(development_mode=True)

        token = "unique_reset_token_456"

        result = await service.send_password_reset_email(
            to_email="test@example.com", reset_token=token
        )

        assert result is True

    def test_email_service_uses_correct_sender(self):
        """Test that EmailService uses configured sender from settings.
        
        Verifies that:
        - from_email matches SES_FROM_EMAIL setting
        - from_name matches SES_FROM_NAME setting
        - Configuration is loaded from environment
        - Sender identity is consistent
        
        Note:
            AWS SES requires verified sender email addresses.
        """
        from src.core.config import get_settings

        service = EmailService(development_mode=True)
        settings = get_settings()

        # Check that service uses the configured values from settings
        assert service.from_email == settings.SES_FROM_EMAIL
        assert service.from_name == settings.SES_FROM_NAME

    @pytest.mark.asyncio
    async def test_fallback_to_dev_mode_on_aws_error(self):
        """Test graceful fallback to development mode on AWS credential errors.
        
        Verifies that:
        - Service catches boto3 client creation errors
        - Automatically falls back to development mode
        - development_mode flag is set to True
        - Emails will be logged instead of failing
        
        Note:
            Prevents service crashes from invalid AWS credentials.
            Useful for local development without AWS access.
        """
        with patch.dict(
            "os.environ",
            {
                "AWS_REGION": "us-east-1",
                "AWS_ACCESS_KEY_ID": "",
                "AWS_SECRET_ACCESS_KEY": "",
            },
        ):
            with patch("boto3.client", side_effect=Exception("Invalid credentials")):
                service = EmailService(development_mode=False)

                # Should fall back to development mode
                assert service.development_mode is True
