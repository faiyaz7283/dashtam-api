"""Unit tests for PasswordResetService.

Tests password reset workflows including:
- Token generation and email sending
- Token validation (invalid, expired, used)
- Password updates with strength validation
- Session revocation on password change (security)
- Email confirmation sending

Note:
    These tests moved from test_auth_service_password_reset.py after
    extracting PasswordResetService from AuthService (Phase 3 refactoring).
"""

import asyncio
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

from fastapi import HTTPException

from src.models.user import User
from src.models.auth import RefreshToken, PasswordResetToken
from src.services.password_reset_service import PasswordResetService


class TestPasswordResetService:
    """Test suite for PasswordResetService.

    Tests the complete password reset workflow including security features
    like automatic session revocation.
    """

    @pytest.fixture
    def mock_session(self):
        """Create a mock AsyncSession for database operations."""
        session = AsyncMock()
        session.add = Mock()
        session.commit = AsyncMock()
        session.refresh = AsyncMock()
        session.flush = AsyncMock()
        return session

    @pytest.fixture
    def mock_password_service(self):
        """Create a mock PasswordService."""
        with patch("src.services.password_reset_service.PasswordService") as mock_cls:
            service = Mock()
            service.verify_password = Mock(return_value=True)
            service.hash_password = Mock(return_value="hashed_new_password")
            service.validate_password_strength = Mock(return_value=(True, None))
            mock_cls.return_value = service
            yield service

    @pytest.fixture
    def mock_email_service(self):
        """Create a mock EmailService."""
        with patch("src.services.password_reset_service.EmailService") as mock_cls:
            service = AsyncMock()
            service.send_password_changed_notification = AsyncMock()
            service.send_password_reset_email = AsyncMock()
            mock_cls.return_value = service
            yield service

    @pytest.fixture
    def password_reset_service(
        self, mock_session, mock_password_service, mock_email_service
    ):
        """Create PasswordResetService with mocked dependencies."""
        return PasswordResetService(mock_session)

    @pytest.fixture
    def sample_user(self):
        """Create a sample user."""
        return User(
            id=uuid4(),
            email="test@example.com",
            password_hash="old_hashed_password",
            name="Test User",
            email_verified=True,
            is_active=True,
            created_at=datetime.now(timezone.utc),
        )

    @pytest.fixture
    def sample_reset_token(self, sample_user):
        """Create a valid password reset token."""
        return PasswordResetToken(
            id=uuid4(),
            user_id=sample_user.id,
            token_hash="hashed_reset_token",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            used_at=None,
            created_at=datetime.now(timezone.utc),
        )

    def test_reset_password_revokes_single_session(
        self, password_reset_service, mock_session, sample_user, sample_reset_token
    ):
        """Test password reset uses TokenRotationService to rotate tokens."""
        # Arrange
        sample_user.min_token_version = 1  # Current user version

        refresh_token = RefreshToken(
            id=uuid4(),
            user_id=sample_user.id,
            token_hash="hashed_token_1",
            token_version=1,  # Matches user version
            expires_at=datetime.now(timezone.utc) + timedelta(days=30),
            is_revoked=False,
            created_at=datetime.now(timezone.utc),
        )

        # Mock database queries for password reset
        reset_token_result = Mock()
        reset_token_result.scalars = Mock(
            return_value=Mock(all=Mock(return_value=[sample_reset_token]))
        )

        user_result = Mock()
        user_result.scalar_one_or_none = Mock(return_value=sample_user)

        # Mock database queries for TokenRotationService
        user_version_result = Mock()
        user_version_result.scalar_one = Mock(return_value=1)  # Current min_token_version

        max_token_version_result = Mock()
        max_token_version_result.scalar = Mock(return_value=1)  # Max token version in use

        update_user_result = Mock()  # UPDATE users SET min_token_version=2

        revoke_tokens_result = Mock()
        revoke_tokens_result.scalars = Mock(
            return_value=Mock(all=Mock(return_value=[refresh_token.id]))
        )  # RETURNING clause

        mock_session.execute = AsyncMock(
            side_effect=[
                reset_token_result,  # SELECT PasswordResetToken
                user_result,  # SELECT User
                user_version_result,  # TokenRotationService: SELECT min_token_version
                max_token_version_result,  # TokenRotationService: SELECT MAX(token_version)
                update_user_result,  # TokenRotationService: UPDATE users
                revoke_tokens_result,  # TokenRotationService: UPDATE refresh_tokens
            ]
        )

        # Act
        user = asyncio.run(
            password_reset_service.reset_password(
                token="plain_reset_token", new_password="NewSecurePass123!"
            )
        )

        # Assert
        assert user is not None
        assert user.id == sample_user.id
        mock_session.commit.assert_called()

    def test_reset_password_revokes_multiple_sessions(
        self, password_reset_service, mock_session, sample_user, sample_reset_token
    ):
        """Test password reset rotates tokens affecting all active sessions."""
        # Arrange
        sample_user.min_token_version = 1

        token_ids = [uuid4() for _ in range(3)]

        reset_token_result = Mock()
        reset_token_result.scalars = Mock(
            return_value=Mock(all=Mock(return_value=[sample_reset_token]))
        )

        user_result = Mock()
        user_result.scalar_one_or_none = Mock(return_value=sample_user)

        # TokenRotationService mocks
        user_version_result = Mock()
        user_version_result.scalar_one = Mock(return_value=1)

        max_token_version_result = Mock()
        max_token_version_result.scalar = Mock(return_value=1)

        update_user_result = Mock()

        revoke_tokens_result = Mock()
        revoke_tokens_result.scalars = Mock(
            return_value=Mock(all=Mock(return_value=token_ids))  # 3 tokens revoked
        )

        mock_session.execute = AsyncMock(
            side_effect=[
                reset_token_result,
                user_result,
                user_version_result,
                max_token_version_result,
                update_user_result,
                revoke_tokens_result,
            ]
        )

        # Act
        user = asyncio.run(
            password_reset_service.reset_password(
                token="plain_reset_token", new_password="NewSecurePass456!"
            )
        )

        # Assert
        assert user is not None
        mock_session.commit.assert_called()

    def test_reset_password_with_no_active_sessions(
        self, password_reset_service, mock_session, sample_user, sample_reset_token
    ):
        """Test password reset succeeds with no active sessions to rotate."""
        # Arrange
        sample_user.min_token_version = 1

        reset_token_result = Mock()
        reset_token_result.scalars = Mock(
            return_value=Mock(all=Mock(return_value=[sample_reset_token]))
        )

        user_result = Mock()
        user_result.scalar_one_or_none = Mock(return_value=sample_user)

        # TokenRotationService mocks
        user_version_result = Mock()
        user_version_result.scalar_one = Mock(return_value=1)

        max_token_version_result = Mock()
        max_token_version_result.scalar = Mock(return_value=0)  # No tokens

        update_user_result = Mock()

        revoke_tokens_result = Mock()
        revoke_tokens_result.scalars = Mock(
            return_value=Mock(all=Mock(return_value=[]))  # No tokens to revoke
        )

        mock_session.execute = AsyncMock(
            side_effect=[
                reset_token_result,
                user_result,
                user_version_result,
                max_token_version_result,
                update_user_result,
                revoke_tokens_result,
            ]
        )

        # Act
        user = asyncio.run(
            password_reset_service.reset_password(
                token="plain_reset_token", new_password="NewSecurePass789!"
            )
        )

        # Assert
        assert user is not None
        mock_session.commit.assert_called()

    def test_reset_password_marks_token_as_used(
        self, password_reset_service, mock_session, sample_user, sample_reset_token
    ):
        """Test password reset marks token as used to prevent reuse."""
        # Arrange
        sample_user.min_token_version = 1

        reset_token_result = Mock()
        reset_token_result.scalars = Mock(
            return_value=Mock(all=Mock(return_value=[sample_reset_token]))
        )

        user_result = Mock()
        user_result.scalar_one_or_none = Mock(return_value=sample_user)

        # TokenRotationService mocks
        user_version_result = Mock()
        user_version_result.scalar_one = Mock(return_value=1)

        max_token_version_result = Mock()
        max_token_version_result.scalar = Mock(return_value=0)

        update_user_result = Mock()

        revoke_tokens_result = Mock()
        revoke_tokens_result.scalars = Mock(return_value=Mock(all=Mock(return_value=[])))

        mock_session.execute = AsyncMock(
            side_effect=[
                reset_token_result,
                user_result,
                user_version_result,
                max_token_version_result,
                update_user_result,
                revoke_tokens_result,
            ]
        )

        # Act
        asyncio.run(
            password_reset_service.reset_password(
                token="plain_reset_token", new_password="NewSecurePass!"
            )
        )

        # Assert
        assert sample_reset_token.used_at is not None
        mock_session.commit.assert_called()

    def test_reset_password_invalid_token(
        self, password_reset_service, mock_session, mock_password_service
    ):
        """Test password reset fails with invalid token."""
        # Arrange - no matching tokens
        reset_token_result = Mock()
        reset_token_result.scalars = Mock(return_value=Mock(all=Mock(return_value=[])))

        mock_session.execute = AsyncMock(return_value=reset_token_result)

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(
                password_reset_service.reset_password(
                    token="invalid_token", new_password="NewPass123!"
                )
            )

        assert exc_info.value.status_code == 400
        assert "Invalid or already used" in exc_info.value.detail

    def test_reset_password_expired_token(
        self, password_reset_service, mock_session, sample_user, mock_password_service
    ):
        """Test password reset fails with expired token."""
        # Arrange - expired token
        expired_token = PasswordResetToken(
            id=uuid4(),
            user_id=sample_user.id,
            token_hash="hashed_reset_token",
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),  # Expired
            used_at=None,
            created_at=datetime.now(timezone.utc),
        )

        reset_token_result = Mock()
        reset_token_result.scalars = Mock(
            return_value=Mock(all=Mock(return_value=[expired_token]))
        )

        mock_session.execute = AsyncMock(return_value=reset_token_result)

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(
                password_reset_service.reset_password(
                    token="expired_token", new_password="NewPass123!"
                )
            )

        assert exc_info.value.status_code == 400
        assert "expired" in exc_info.value.detail.lower()

    def test_request_reset_prevents_email_enumeration(
        self, password_reset_service, mock_session
    ):
        """Test request_reset doesn't reveal if email exists (security)."""
        # Arrange - non-existent email
        user_result = Mock()
        user_result.scalar_one_or_none = Mock(return_value=None)

        mock_session.execute = AsyncMock(return_value=user_result)

        # Act - should succeed silently without revealing email doesn't exist
        asyncio.run(password_reset_service.request_reset("nonexistent@example.com"))

        # Assert - no exception raised, no email sent
        mock_session.commit.assert_not_called()

    def test_request_reset_success_for_active_user(
        self, password_reset_service, mock_session, sample_user, mock_email_service
    ):
        """Test request_reset sends email for active user."""
        # Arrange
        user_result = Mock()
        user_result.scalar_one_or_none = Mock(return_value=sample_user)

        mock_session.execute = AsyncMock(return_value=user_result)

        # Act
        asyncio.run(password_reset_service.request_reset(sample_user.email))

        # Assert
        mock_email_service.send_password_reset_email.assert_called_once()
        call_args = mock_email_service.send_password_reset_email.call_args
        assert call_args.kwargs["to_email"] == sample_user.email
        assert call_args.kwargs["user_name"] == sample_user.name
        assert "reset_token" in call_args.kwargs
        mock_session.add.assert_called_once()
        mock_session.flush.assert_called_once()
        mock_session.commit.assert_called_once()

    def test_request_reset_ignores_inactive_user(
        self, password_reset_service, mock_session, sample_user, mock_email_service
    ):
        """Test request_reset silently ignores inactive users."""
        # Arrange - inactive user
        sample_user.is_active = False

        user_result = Mock()
        user_result.scalar_one_or_none = Mock(return_value=sample_user)

        mock_session.execute = AsyncMock(return_value=user_result)

        # Act
        asyncio.run(password_reset_service.request_reset(sample_user.email))

        # Assert - no email sent, no token created
        mock_email_service.send_password_reset_email.assert_not_called()
        mock_session.add.assert_not_called()
        mock_session.commit.assert_not_called()

    def test_request_reset_handles_email_sending_failure(
        self,
        password_reset_service,
        mock_session,
        sample_user,
        mock_email_service,
        caplog,
    ):
        """Test request_reset handles email sending failure gracefully."""
        # Arrange
        user_result = Mock()
        user_result.scalar_one_or_none = Mock(return_value=sample_user)

        mock_session.execute = AsyncMock(return_value=user_result)

        mock_email_service.send_password_reset_email.side_effect = Exception(
            "Email service unavailable"
        )

        # Act - should not raise exception
        asyncio.run(password_reset_service.request_reset(sample_user.email))

        # Assert
        assert "Failed to send password reset email" in caplog.text
        mock_session.commit.assert_called_once()  # Token still created

    def test_request_reset_creates_hashed_token(
        self, password_reset_service, mock_session, sample_user, mock_password_service
    ):
        """Test request_reset hashes token before storage."""
        # Arrange
        user_result = Mock()
        user_result.scalar_one_or_none = Mock(return_value=sample_user)

        mock_session.execute = AsyncMock(return_value=user_result)

        # Act
        asyncio.run(password_reset_service.request_reset(sample_user.email))

        # Assert
        mock_password_service.hash_password.assert_called()
        mock_session.add.assert_called_once()
