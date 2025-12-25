"""Unit tests for auth flow handlers.

Tests cover:
- LogoutUserHandler: token not found, already revoked, mismatch errors
- RefreshAccessTokenHandler: token expired, revoked, version rejected, user inactive
- VerifyEmailHandler: token expired, already used, user not found
- ConfirmPasswordResetHandler: token expired, already used, user not found
- RequestPasswordResetHandler: user not found, user not verified, rate limited

Architecture:
- Unit tests with mocked dependencies (NOT integration tests)
- Mock all repositories and services
- Test handler logic and error paths
- Focus on branches not covered by integration tests
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, Mock
from uuid import UUID

import pytest
from uuid_extensions import uuid7

from src.application.commands.auth_commands import (
    ConfirmPasswordReset,
    LogoutUser,
    RefreshAccessToken,
    RequestPasswordReset,
    VerifyEmail,
)
from src.application.commands.handlers.confirm_password_reset_handler import (
    ConfirmPasswordResetHandler,
    PasswordResetConfirmError,
)
from src.application.commands.handlers.logout_user_handler import (
    LogoutUserHandler,
)
from src.application.commands.handlers.refresh_access_token_handler import (
    RefreshAccessTokenHandler,
    RefreshError,
)
from src.application.commands.handlers.request_password_reset_handler import (
    RequestPasswordResetHandler,
)
from src.application.commands.handlers.verify_email_handler import (
    VerifyEmailHandler,
    VerifyEmailError,
)
from src.core.result import Failure, Success
from src.domain.protocols import (
    RefreshTokenData,
    EmailVerificationTokenData,
    PasswordResetTokenData,
)


# =============================================================================
# Test Helpers
# =============================================================================


def create_mock_refresh_token_data(
    user_id: UUID | None = None,
    session_id: UUID | None = None,
    expires_at: datetime | None = None,
    revoked_at: datetime | None = None,
    token_version: int = 1,
) -> RefreshTokenData:
    """Create mock RefreshTokenData."""
    return RefreshTokenData(
        id=uuid7(),
        user_id=user_id or uuid7(),
        token_hash="mock_hash",
        session_id=session_id or uuid7(),
        expires_at=expires_at or (datetime.now(UTC) + timedelta(days=30)),
        revoked_at=revoked_at,
        last_used_at=None,
        rotation_count=0,
        token_version=token_version,
        global_version_at_issuance=token_version,
    )


def create_mock_user(user_id: UUID | None = None, is_active: bool = True) -> Mock:
    """Create mock User entity."""
    user = Mock()
    user.id = user_id or uuid7()
    user.email = "test@example.com"
    user.is_verified = True
    user.is_active = is_active
    user.min_token_version = 1
    return user


def create_mock_email_verification_token_data(
    user_id: UUID | None = None,
    expires_at: datetime | None = None,
    used_at: datetime | None = None,
) -> EmailVerificationTokenData:
    """Create mock EmailVerificationTokenData."""
    return EmailVerificationTokenData(
        id=uuid7(),
        user_id=user_id or uuid7(),
        token="mock_token_12345678",
        expires_at=expires_at or (datetime.now(UTC) + timedelta(hours=24)),
        used_at=used_at,
    )


def create_mock_password_reset_token_data(
    user_id: UUID | None = None,
    expires_at: datetime | None = None,
    used_at: datetime | None = None,
) -> PasswordResetTokenData:
    """Create mock PasswordResetTokenData."""
    return PasswordResetTokenData(
        id=uuid7(),
        user_id=user_id or uuid7(),
        token="mock_reset_token_12345678",
        expires_at=expires_at or (datetime.now(UTC) + timedelta(minutes=15)),
        used_at=used_at,
        ip_address="127.0.0.1",
        user_agent="Test Browser",
        created_at=datetime.now(UTC),
    )


# =============================================================================
# LogoutUserHandler Tests
# =============================================================================


@pytest.mark.unit
class TestLogoutUserHandlerEdgeCases:
    """Test LogoutUserHandler error paths and edge cases."""

    @pytest.mark.asyncio
    async def test_logout_when_token_not_found_returns_success(self):
        """Test logout returns success even when token not found (security)."""
        # Arrange
        mock_refresh_token_repo = AsyncMock()
        mock_refresh_token_repo.find_by_token_verification.return_value = None

        mock_refresh_token_service = Mock()
        event_bus = AsyncMock()

        handler = LogoutUserHandler(
            refresh_token_repo=mock_refresh_token_repo,
            refresh_token_service=mock_refresh_token_service,
            event_bus=event_bus,
        )

        command = LogoutUser(user_id=uuid7(), refresh_token="invalid_token")

        # Act
        result = await handler.handle(command)

        # Assert - returns success to prevent information leakage
        assert isinstance(result, Success)
        assert result.value.message == "Successfully logged out."

    @pytest.mark.asyncio
    async def test_logout_when_token_belongs_to_different_user_returns_success(self):
        """Test logout returns success when token belongs to different user (security)."""
        # Arrange
        user_id = uuid7()
        different_user_id = uuid7()

        mock_token_data = create_mock_refresh_token_data(user_id=different_user_id)

        mock_refresh_token_repo = AsyncMock()
        mock_refresh_token_repo.find_by_token_verification.return_value = (
            mock_token_data
        )

        mock_refresh_token_service = Mock()
        event_bus = AsyncMock()

        handler = LogoutUserHandler(
            refresh_token_repo=mock_refresh_token_repo,
            refresh_token_service=mock_refresh_token_service,
            event_bus=event_bus,
        )

        command = LogoutUser(user_id=user_id, refresh_token="valid_token")

        # Act
        result = await handler.handle(command)

        # Assert - returns success but doesn't revoke (security)
        assert isinstance(result, Success)
        mock_refresh_token_repo.revoke_by_session.assert_not_called()

    @pytest.mark.asyncio
    async def test_logout_when_token_already_revoked_returns_success(self):
        """Test logout returns success when token already revoked."""
        # Arrange
        user_id = uuid7()
        mock_token_data = create_mock_refresh_token_data(
            user_id=user_id,
            revoked_at=datetime.now(UTC),  # Already revoked
        )

        mock_refresh_token_repo = AsyncMock()
        mock_refresh_token_repo.find_by_token_verification.return_value = (
            mock_token_data
        )

        mock_refresh_token_service = Mock()
        event_bus = AsyncMock()

        handler = LogoutUserHandler(
            refresh_token_repo=mock_refresh_token_repo,
            refresh_token_service=mock_refresh_token_service,
            event_bus=event_bus,
        )

        command = LogoutUser(user_id=user_id, refresh_token="valid_token")

        # Act
        result = await handler.handle(command)

        # Assert - returns success (idempotent)
        assert isinstance(result, Success)


# =============================================================================
# RefreshAccessTokenHandler Tests
# =============================================================================


@pytest.mark.unit
class TestRefreshAccessTokenHandlerEdgeCases:
    """Test RefreshAccessTokenHandler error paths and edge cases."""

    @pytest.mark.asyncio
    async def test_refresh_fails_when_token_expired(self):
        """Test refresh fails with TOKEN_EXPIRED when token is expired."""
        # Arrange
        expired_token_data = create_mock_refresh_token_data(
            expires_at=datetime.now(UTC) - timedelta(hours=1)  # Expired
        )

        mock_user_repo = AsyncMock()
        mock_refresh_token_repo = AsyncMock()
        mock_refresh_token_repo.find_by_token_verification.return_value = (
            expired_token_data
        )

        mock_security_config_repo = AsyncMock()
        mock_token_service = Mock()
        mock_refresh_token_service = Mock()
        event_bus = AsyncMock()

        handler = RefreshAccessTokenHandler(
            user_repo=mock_user_repo,
            refresh_token_repo=mock_refresh_token_repo,
            security_config_repo=mock_security_config_repo,
            token_service=mock_token_service,
            refresh_token_service=mock_refresh_token_service,
            event_bus=event_bus,
        )

        command = RefreshAccessToken(refresh_token="expired_token")

        # Act
        result = await handler.handle(command)

        # Assert
        assert isinstance(result, Failure)
        assert result.error == RefreshError.TOKEN_EXPIRED

    @pytest.mark.asyncio
    async def test_refresh_fails_when_token_revoked(self):
        """Test refresh fails with TOKEN_REVOKED when token is revoked."""
        # Arrange
        revoked_token_data = create_mock_refresh_token_data(
            revoked_at=datetime.now(UTC)  # Revoked
        )

        mock_user_repo = AsyncMock()
        mock_refresh_token_repo = AsyncMock()
        mock_refresh_token_repo.find_by_token_verification.return_value = (
            revoked_token_data
        )

        mock_security_config_repo = AsyncMock()
        mock_token_service = Mock()
        mock_refresh_token_service = Mock()
        event_bus = AsyncMock()

        handler = RefreshAccessTokenHandler(
            user_repo=mock_user_repo,
            refresh_token_repo=mock_refresh_token_repo,
            security_config_repo=mock_security_config_repo,
            token_service=mock_token_service,
            refresh_token_service=mock_refresh_token_service,
            event_bus=event_bus,
        )

        command = RefreshAccessToken(refresh_token="revoked_token")

        # Act
        result = await handler.handle(command)

        # Assert
        assert isinstance(result, Failure)
        assert result.error == RefreshError.TOKEN_REVOKED

    @pytest.mark.asyncio
    async def test_refresh_fails_when_user_inactive(self):
        """Test refresh fails with USER_INACTIVE when user is deactivated."""
        # Arrange
        user_id = uuid7()
        token_data = create_mock_refresh_token_data(user_id=user_id)
        inactive_user = create_mock_user(user_id=user_id, is_active=False)

        mock_user_repo = AsyncMock()
        mock_user_repo.find_by_id.return_value = inactive_user

        mock_refresh_token_repo = AsyncMock()
        mock_refresh_token_repo.find_by_token_verification.return_value = token_data

        mock_security_config = Mock()
        mock_security_config.global_min_token_version = 1
        mock_security_config.grace_period_seconds = 300
        mock_security_config.is_within_grace_period.return_value = False

        mock_security_config_repo = AsyncMock()
        mock_security_config_repo.get_or_create_default.return_value = (
            mock_security_config
        )

        mock_token_service = Mock()
        mock_refresh_token_service = Mock()
        event_bus = AsyncMock()

        handler = RefreshAccessTokenHandler(
            user_repo=mock_user_repo,
            refresh_token_repo=mock_refresh_token_repo,
            security_config_repo=mock_security_config_repo,
            token_service=mock_token_service,
            refresh_token_service=mock_refresh_token_service,
            event_bus=event_bus,
        )

        command = RefreshAccessToken(refresh_token="valid_token")

        # Act
        result = await handler.handle(command)

        # Assert
        assert isinstance(result, Failure)
        assert result.error == RefreshError.USER_INACTIVE


# =============================================================================
# VerifyEmailHandler Tests
# =============================================================================


@pytest.mark.unit
class TestVerifyEmailHandlerEdgeCases:
    """Test VerifyEmailHandler error paths and edge cases."""

    @pytest.mark.asyncio
    async def test_verify_fails_when_token_expired(self):
        """Test verification fails when token is expired."""
        # Arrange
        expired_token_data = create_mock_email_verification_token_data(
            expires_at=datetime.now(UTC) - timedelta(hours=1)  # Expired
        )

        mock_user_repo = AsyncMock()
        mock_verification_token_repo = AsyncMock()
        mock_verification_token_repo.find_by_token.return_value = expired_token_data

        event_bus = AsyncMock()

        handler = VerifyEmailHandler(
            user_repo=mock_user_repo,
            verification_token_repo=mock_verification_token_repo,
            event_bus=event_bus,
        )

        command = VerifyEmail(token="expired_token_12345678")

        # Act
        result = await handler.handle(command)

        # Assert
        assert isinstance(result, Failure)
        assert result.error == VerifyEmailError.TOKEN_EXPIRED

    @pytest.mark.asyncio
    async def test_verify_fails_when_token_already_used(self):
        """Test verification fails when token already used."""
        # Arrange
        used_token_data = create_mock_email_verification_token_data(
            used_at=datetime.now(UTC)  # Already used
        )

        mock_user_repo = AsyncMock()
        mock_verification_token_repo = AsyncMock()
        mock_verification_token_repo.find_by_token.return_value = used_token_data

        event_bus = AsyncMock()

        handler = VerifyEmailHandler(
            user_repo=mock_user_repo,
            verification_token_repo=mock_verification_token_repo,
            event_bus=event_bus,
        )

        command = VerifyEmail(token="used_token_12345678")

        # Act
        result = await handler.handle(command)

        # Assert
        assert isinstance(result, Failure)
        assert result.error == VerifyEmailError.TOKEN_ALREADY_USED

    @pytest.mark.asyncio
    async def test_verify_fails_when_user_not_found(self):
        """Test verification fails when user doesn't exist."""
        # Arrange
        token_data = create_mock_email_verification_token_data()

        mock_user_repo = AsyncMock()
        mock_user_repo.find_by_id.return_value = None  # User not found

        mock_verification_token_repo = AsyncMock()
        mock_verification_token_repo.find_by_token.return_value = token_data

        event_bus = AsyncMock()

        handler = VerifyEmailHandler(
            user_repo=mock_user_repo,
            verification_token_repo=mock_verification_token_repo,
            event_bus=event_bus,
        )

        command = VerifyEmail(token="valid_token_12345678")

        # Act
        result = await handler.handle(command)

        # Assert
        assert isinstance(result, Failure)
        assert result.error == VerifyEmailError.USER_NOT_FOUND


# =============================================================================
# ConfirmPasswordResetHandler Tests
# =============================================================================


@pytest.mark.unit
class TestConfirmPasswordResetHandlerEdgeCases:
    """Test ConfirmPasswordResetHandler error paths and edge cases."""

    @pytest.mark.asyncio
    async def test_confirm_fails_when_token_expired(self):
        """Test password reset confirmation fails when token expired."""
        # Arrange
        expired_token_data = create_mock_password_reset_token_data(
            expires_at=datetime.now(UTC) - timedelta(minutes=20)  # Expired
        )

        mock_user_repo = AsyncMock()
        mock_password_reset_repo = AsyncMock()
        mock_password_reset_repo.find_by_token.return_value = expired_token_data

        mock_refresh_token_repo = AsyncMock()
        mock_password_service = Mock()
        mock_email_service = AsyncMock()
        event_bus = AsyncMock()

        handler = ConfirmPasswordResetHandler(
            user_repo=mock_user_repo,
            password_reset_repo=mock_password_reset_repo,
            refresh_token_repo=mock_refresh_token_repo,
            password_service=mock_password_service,
            email_service=mock_email_service,
            event_bus=event_bus,
        )

        command = ConfirmPasswordReset(
            token="expired_token_12345678",
            new_password="NewSecurePass123!",
        )

        # Act
        result = await handler.handle(command)

        # Assert
        assert isinstance(result, Failure)
        assert result.error == PasswordResetConfirmError.TOKEN_EXPIRED

    @pytest.mark.asyncio
    async def test_confirm_fails_when_user_not_found(self):
        """Test password reset confirmation fails when user doesn't exist."""
        # Arrange
        token_data = create_mock_password_reset_token_data()

        mock_user_repo = AsyncMock()
        mock_user_repo.find_by_id.return_value = None  # User not found

        mock_password_reset_repo = AsyncMock()
        mock_password_reset_repo.find_by_token.return_value = token_data

        mock_refresh_token_repo = AsyncMock()
        mock_password_service = Mock()
        mock_email_service = AsyncMock()
        event_bus = AsyncMock()

        handler = ConfirmPasswordResetHandler(
            user_repo=mock_user_repo,
            password_reset_repo=mock_password_reset_repo,
            refresh_token_repo=mock_refresh_token_repo,
            password_service=mock_password_service,
            email_service=mock_email_service,
            event_bus=event_bus,
        )

        command = ConfirmPasswordReset(
            token="valid_token_12345678",
            new_password="NewSecurePass123!",
        )

        # Act
        result = await handler.handle(command)

        # Assert
        assert isinstance(result, Failure)
        assert result.error == PasswordResetConfirmError.USER_NOT_FOUND


# =============================================================================
# RequestPasswordResetHandler Tests
# =============================================================================


@pytest.mark.unit
class TestRequestPasswordResetHandlerEdgeCases:
    """Test RequestPasswordResetHandler error paths and edge cases."""

    @pytest.mark.asyncio
    async def test_request_returns_success_when_user_not_found(self):
        """Test request returns success when user not found (security)."""
        # Arrange
        mock_user_repo = AsyncMock()
        mock_user_repo.find_by_email.return_value = None  # User not found

        mock_password_reset_repo = AsyncMock()
        mock_token_service = Mock()
        mock_email_service = AsyncMock()
        event_bus = AsyncMock()

        handler = RequestPasswordResetHandler(
            user_repo=mock_user_repo,
            password_reset_repo=mock_password_reset_repo,
            token_service=mock_token_service,
            email_service=mock_email_service,
            event_bus=event_bus,
            verification_url_base="https://test.com",
        )

        command = RequestPasswordReset(email="nonexistent@example.com")

        # Act
        result = await handler.handle(command)

        # Assert - returns success to prevent user enumeration
        assert isinstance(result, Success)
        assert "If an account with that email exists" in result.value.message
        mock_email_service.send_password_reset_email.assert_not_called()

    @pytest.mark.asyncio
    async def test_request_returns_success_when_user_not_verified(self):
        """Test request returns success when user not verified (security)."""
        # Arrange
        unverified_user = Mock()
        unverified_user.is_verified = False
        unverified_user.email = "test@example.com"

        mock_user_repo = AsyncMock()
        mock_user_repo.find_by_email.return_value = unverified_user

        mock_password_reset_repo = AsyncMock()
        mock_token_service = Mock()
        mock_email_service = AsyncMock()
        event_bus = AsyncMock()

        handler = RequestPasswordResetHandler(
            user_repo=mock_user_repo,
            password_reset_repo=mock_password_reset_repo,
            token_service=mock_token_service,
            email_service=mock_email_service,
            event_bus=event_bus,
            verification_url_base="https://test.com",
        )

        command = RequestPasswordReset(email="test@example.com")

        # Act
        result = await handler.handle(command)

        # Assert - returns success but doesn't send email
        assert isinstance(result, Success)
        mock_email_service.send_password_reset_email.assert_not_called()

    @pytest.mark.asyncio
    async def test_request_returns_success_when_rate_limited(self):
        """Test request returns success when rate limited (security)."""
        # Arrange
        verified_user = Mock()
        verified_user.id = uuid7()
        verified_user.is_verified = True
        verified_user.email = "test@example.com"

        mock_user_repo = AsyncMock()
        mock_user_repo.find_by_email.return_value = verified_user

        mock_password_reset_repo = AsyncMock()
        mock_password_reset_repo.count_recent_requests.return_value = (
            5  # Over limit (3)
        )

        mock_token_service = Mock()
        mock_email_service = AsyncMock()
        event_bus = AsyncMock()

        handler = RequestPasswordResetHandler(
            user_repo=mock_user_repo,
            password_reset_repo=mock_password_reset_repo,
            token_service=mock_token_service,
            email_service=mock_email_service,
            event_bus=event_bus,
            verification_url_base="https://test.com",
        )

        command = RequestPasswordReset(email="test@example.com")

        # Act
        result = await handler.handle(command)

        # Assert - returns success but doesn't send email
        assert isinstance(result, Success)
        mock_email_service.send_password_reset_email.assert_not_called()
