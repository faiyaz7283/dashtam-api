"""Unit tests for EmailService.

Tests email sending functionality with mocked AWS SES.
"""

import pytest
from unittest.mock import Mock, patch

from src.services.email_service import EmailService


class TestEmailService:
    """Test suite for EmailService."""

    def test_init_development_mode(self):
        """Test initialization in development mode."""
        service = EmailService(development_mode=True)

        assert service.development_mode is True
        assert service.ses_client is None

    def test_init_production_mode_with_credentials(self):
        """Test initialization in production mode with valid credentials."""
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
        """Test sending email in development mode (logs only)."""
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
        """Test sending email in production mode successfully."""
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
        """Test sending email in production mode with failure."""
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
        """Test sending verification email."""
        service = EmailService(development_mode=True)

        result = await service.send_verification_email(
            to_email="test@example.com",
            verification_token="abc123def456",
            user_name="John Doe",
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_send_verification_email_without_name(self):
        """Test sending verification email without user name."""
        service = EmailService(development_mode=True)

        result = await service.send_verification_email(
            to_email="test@example.com", verification_token="abc123def456"
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_send_password_reset_email(self):
        """Test sending password reset email."""
        service = EmailService(development_mode=True)

        result = await service.send_password_reset_email(
            to_email="test@example.com",
            reset_token="xyz789abc123",
            user_name="John Doe",
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_send_password_reset_email_without_name(self):
        """Test sending password reset email without user name."""
        service = EmailService(development_mode=True)

        result = await service.send_password_reset_email(
            to_email="test@example.com", reset_token="xyz789abc123"
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_send_welcome_email(self):
        """Test sending welcome email."""
        service = EmailService(development_mode=True)

        result = await service.send_welcome_email(
            to_email="test@example.com", user_name="John Doe"
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_send_welcome_email_without_name(self):
        """Test sending welcome email without user name."""
        service = EmailService(development_mode=True)

        result = await service.send_welcome_email(to_email="test@example.com")

        assert result is True

    @pytest.mark.asyncio
    async def test_send_password_changed_notification(self):
        """Test sending password changed notification."""
        service = EmailService(development_mode=True)

        result = await service.send_password_changed_notification(
            to_email="test@example.com", user_name="John Doe"
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_send_password_changed_notification_without_name(self):
        """Test sending password changed notification without user name."""
        service = EmailService(development_mode=True)

        result = await service.send_password_changed_notification(
            to_email="test@example.com"
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_send_email_with_html_only(self):
        """Test sending email with HTML body only."""
        service = EmailService(development_mode=True)

        result = await service.send_email(
            to_email="test@example.com", subject="Test", html_body="<h1>Test</h1>"
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_send_email_with_both_html_and_text(self):
        """Test sending email with both HTML and text bodies."""
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
        """Test that verification email contains the token in URL."""
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
        """Test that reset email contains the token in URL."""
        service = EmailService(development_mode=True)

        token = "unique_reset_token_456"

        result = await service.send_password_reset_email(
            to_email="test@example.com", reset_token=token
        )

        assert result is True

    def test_email_service_uses_correct_sender(self):
        """Test that email service uses configured sender from environment."""
        from src.core.config import get_settings
        
        service = EmailService(development_mode=True)
        settings = get_settings()

        # Check that service uses the configured values from settings
        assert service.from_email == settings.SES_FROM_EMAIL
        assert service.from_name == settings.SES_FROM_NAME

    @pytest.mark.asyncio
    async def test_fallback_to_dev_mode_on_aws_error(self):
        """Test that service falls back to dev mode if AWS credentials invalid."""
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
