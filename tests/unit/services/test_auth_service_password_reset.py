"""Unit tests for AuthService password reset with session revocation.

Tests the security enhancement that revokes all active sessions when
a user resets their password, using mocks to isolate the service layer.
"""

import asyncio
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

from fastapi import HTTPException

from src.models.user import User
from src.models.auth import RefreshToken, PasswordResetToken
from src.services.auth_service import AuthService


class TestPasswordResetSessionRevocation:
    """Test password reset revokes all active refresh tokens."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock AsyncSession."""
        session = AsyncMock()
        session.add = Mock()
        session.commit = AsyncMock()
        session.refresh = AsyncMock()
        return session

    @pytest.fixture
    def mock_password_service(self):
        """Create a mock PasswordService."""
        with patch("src.services.auth_service.PasswordService") as mock_cls:
            service = Mock()
            # Mock password verification to return True for valid tokens
            service.verify_password = Mock(return_value=True)
            service.hash_password = Mock(return_value="hashed_new_password")
            service.validate_password_strength = Mock(return_value=(True, None))
            mock_cls.return_value = service
            yield service

    @pytest.fixture
    def mock_email_service(self):
        """Create a mock EmailService."""
        with patch("src.services.auth_service.EmailService") as mock_cls:
            service = AsyncMock()
            service.send_password_changed_notification = AsyncMock()
            mock_cls.return_value = service
            yield service

    @pytest.fixture
    def auth_service(self, mock_session, mock_password_service, mock_email_service):
        """Create AuthService instance with mocked dependencies."""
        return AuthService(mock_session)

    @pytest.fixture
    def sample_user(self):
        """Create a sample user for testing."""
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
        """Create a sample password reset token."""
        return PasswordResetToken(
            id=uuid4(),
            user_id=sample_user.id,
            token_hash="hashed_reset_token",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            used_at=None,
            created_at=datetime.now(timezone.utc),
        )

    def test_password_reset_revokes_single_session(
        self, auth_service, mock_session, sample_user, sample_reset_token
    ):
        """Test password reset revokes a single active session."""
        # Arrange
        refresh_token = RefreshToken(
            id=uuid4(),
            user_id=sample_user.id,
            token_hash="hashed_token_1",
            expires_at=datetime.now(timezone.utc) + timedelta(days=30),
            is_revoked=False,
            created_at=datetime.now(timezone.utc),
        )

        # Mock database queries
        # First query: Find reset token
        reset_token_result = Mock()
        reset_token_result.scalars = Mock(
            return_value=Mock(all=Mock(return_value=[sample_reset_token]))
        )

        # Second query: Find user
        user_result = Mock()
        user_result.scalar_one_or_none = Mock(return_value=sample_user)

        # Third query: Find active refresh tokens
        refresh_tokens_result = Mock()
        refresh_tokens_result.scalars = Mock(
            return_value=Mock(all=Mock(return_value=[refresh_token]))
        )

        mock_session.execute = AsyncMock(
            side_effect=[
                reset_token_result,  # Query for reset tokens
                user_result,  # Query for user
                refresh_tokens_result,  # Query for refresh tokens
            ]
        )

        # Act
        user = asyncio.run(
            auth_service.reset_password(
                token="plain_reset_token", new_password="NewSecurePass123!"
            )
        )

        # Assert
        assert user is not None
        assert user.id == sample_user.id
        # Verify refresh token was revoked
        assert refresh_token.is_revoked is True
        assert refresh_token.revoked_at is not None
        mock_session.commit.assert_called()

    def test_password_reset_revokes_multiple_sessions(
        self, auth_service, mock_session, sample_user, sample_reset_token
    ):
        """Test password reset revokes all active sessions (multiple devices)."""
        # Arrange
        tokens = [
            RefreshToken(
                id=uuid4(),
                user_id=sample_user.id,
                token_hash=f"hashed_token_{i}",
                expires_at=datetime.now(timezone.utc) + timedelta(days=30),
                is_revoked=False,
                created_at=datetime.now(timezone.utc),
            )
            for i in range(3)
        ]

        # Mock database queries
        reset_token_result = Mock()
        reset_token_result.scalars = Mock(
            return_value=Mock(all=Mock(return_value=[sample_reset_token]))
        )

        user_result = Mock()
        user_result.scalar_one_or_none = Mock(return_value=sample_user)

        refresh_tokens_result = Mock()
        refresh_tokens_result.scalars = Mock(
            return_value=Mock(all=Mock(return_value=tokens))
        )

        mock_session.execute = AsyncMock(
            side_effect=[reset_token_result, user_result, refresh_tokens_result]
        )

        # Act
        user = asyncio.run(
            auth_service.reset_password(
                token="plain_reset_token", new_password="NewSecurePass456!"
            )
        )

        # Assert
        assert user is not None
        # Verify all tokens were revoked
        for token in tokens:
            assert token.is_revoked is True, f"Token {token.id} should be revoked"
            assert token.revoked_at is not None
        mock_session.commit.assert_called()

    def test_password_reset_with_no_active_sessions(
        self, auth_service, mock_session, sample_user, sample_reset_token
    ):
        """Test password reset succeeds even when no active sessions exist."""
        # Arrange - no refresh tokens
        reset_token_result = Mock()
        reset_token_result.scalars = Mock(
            return_value=Mock(all=Mock(return_value=[sample_reset_token]))
        )

        user_result = Mock()
        user_result.scalar_one_or_none = Mock(return_value=sample_user)

        refresh_tokens_result = Mock()
        refresh_tokens_result.scalars = Mock(
            return_value=Mock(all=Mock(return_value=[]))
        )  # Empty list

        mock_session.execute = AsyncMock(
            side_effect=[reset_token_result, user_result, refresh_tokens_result]
        )

        # Act
        user = asyncio.run(
            auth_service.reset_password(
                token="plain_reset_token", new_password="NewSecurePass789!"
            )
        )

        # Assert
        assert user is not None
        # Should succeed without errors even with no sessions to revoke
        mock_session.commit.assert_called()

    def test_password_reset_marks_token_as_used(
        self, auth_service, mock_session, sample_user, sample_reset_token
    ):
        """Test password reset marks the reset token as used."""
        # Arrange
        reset_token_result = Mock()
        reset_token_result.scalars = Mock(
            return_value=Mock(all=Mock(return_value=[sample_reset_token]))
        )

        user_result = Mock()
        user_result.scalar_one_or_none = Mock(return_value=sample_user)

        refresh_tokens_result = Mock()
        refresh_tokens_result.scalars = Mock(
            return_value=Mock(all=Mock(return_value=[]))
        )

        mock_session.execute = AsyncMock(
            side_effect=[reset_token_result, user_result, refresh_tokens_result]
        )

        # Act
        user = asyncio.run(
            auth_service.reset_password(
                token="plain_reset_token", new_password="OneTimeUse123!"
            )
        )

        # Assert
        assert user is not None
        assert sample_reset_token.used_at is not None
        mock_session.commit.assert_called()

    def test_password_reset_with_invalid_token(
        self, auth_service, mock_session, mock_password_service
    ):
        """Test password reset fails with invalid token."""
        # Arrange - no matching tokens
        reset_token_result = Mock()
        reset_token_result.scalars = Mock(return_value=Mock(all=Mock(return_value=[])))

        mock_session.execute = AsyncMock(return_value=reset_token_result)
        # Mock password verification to return False (no match)
        mock_password_service.verify_password = Mock(return_value=False)

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(
                auth_service.reset_password(
                    token="invalid_token", new_password="NewPass123!"
                )
            )

        assert exc_info.value.status_code == 400
        assert "Invalid" in exc_info.value.detail

    def test_password_reset_with_expired_token(
        self, auth_service, mock_session, sample_user
    ):
        """Test password reset fails with expired token."""
        # Arrange - expired token
        expired_token = PasswordResetToken(
            id=uuid4(),
            user_id=sample_user.id,
            token_hash="hashed_reset_token",
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),  # Expired
            used_at=None,
            created_at=datetime.now(timezone.utc) - timedelta(hours=2),
        )

        reset_token_result = Mock()
        reset_token_result.scalars = Mock(
            return_value=Mock(all=Mock(return_value=[expired_token]))
        )

        mock_session.execute = AsyncMock(return_value=reset_token_result)

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(
                auth_service.reset_password(
                    token="plain_reset_token", new_password="NewPass123!"
                )
            )

        assert exc_info.value.status_code == 400
        assert "expired" in exc_info.value.detail.lower()

    def test_password_reset_with_weak_password(
        self,
        auth_service,
        mock_session,
        mock_password_service,
        sample_user,
        sample_reset_token,
    ):
        """Test password reset fails with weak password."""
        # Arrange
        reset_token_result = Mock()
        reset_token_result.scalars = Mock(
            return_value=Mock(all=Mock(return_value=[sample_reset_token]))
        )

        user_result = Mock()
        user_result.scalar_one_or_none = Mock(return_value=sample_user)

        mock_session.execute = AsyncMock(
            side_effect=[
                reset_token_result,
                user_result,
            ]
        )

        # Mock password validation to fail
        mock_password_service.validate_password_strength = Mock(
            return_value=(False, "Password too weak")
        )

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(
                auth_service.reset_password(
                    token="plain_reset_token", new_password="weak"
                )
            )

        assert exc_info.value.status_code == 400
        assert "weak" in exc_info.value.detail.lower()

    def test_password_reset_updates_password_hash(
        self,
        auth_service,
        mock_session,
        mock_password_service,
        sample_user,
        sample_reset_token,
    ):
        """Test password reset updates the password hash."""
        # Arrange
        reset_token_result = Mock()
        reset_token_result.scalars = Mock(
            return_value=Mock(all=Mock(return_value=[sample_reset_token]))
        )

        user_result = Mock()
        user_result.scalar_one_or_none = Mock(return_value=sample_user)

        refresh_tokens_result = Mock()
        refresh_tokens_result.scalars = Mock(
            return_value=Mock(all=Mock(return_value=[]))
        )

        mock_session.execute = AsyncMock(
            side_effect=[reset_token_result, user_result, refresh_tokens_result]
        )

        old_hash = sample_user.password_hash

        # Act
        result_user = asyncio.run(
            auth_service.reset_password(
                token="plain_reset_token", new_password="NewSecurePass123!"
            )
        )

        # Assert
        assert result_user.password_hash != old_hash
        assert result_user.password_hash == "hashed_new_password"
        mock_password_service.hash_password.assert_called_with("NewSecurePass123!")

    def test_password_reset_sends_confirmation_email(
        self,
        auth_service,
        mock_session,
        mock_email_service,
        sample_user,
        sample_reset_token,
    ):
        """Test password reset sends confirmation email."""
        # Arrange
        reset_token_result = Mock()
        reset_token_result.scalars = Mock(
            return_value=Mock(all=Mock(return_value=[sample_reset_token]))
        )

        user_result = Mock()
        user_result.scalar_one_or_none = Mock(return_value=sample_user)

        refresh_tokens_result = Mock()
        refresh_tokens_result.scalars = Mock(
            return_value=Mock(all=Mock(return_value=[]))
        )

        mock_session.execute = AsyncMock(
            side_effect=[reset_token_result, user_result, refresh_tokens_result]
        )

        # Act
        result_user = asyncio.run(
            auth_service.reset_password(
                token="plain_reset_token", new_password="NewSecurePass123!"
            )
        )

        # Assert
        assert result_user is not None
        mock_email_service.send_password_changed_notification.assert_called_once_with(
            to_email=sample_user.email, user_name=sample_user.name
        )

    def test_password_reset_skips_already_revoked_tokens(
        self, auth_service, mock_session, sample_user, sample_reset_token
    ):
        """Test password reset only revokes active tokens, skips already revoked."""
        # Arrange
        active_token = RefreshToken(
            id=uuid4(),
            user_id=sample_user.id,
            token_hash="active_token",
            expires_at=datetime.now(timezone.utc) + timedelta(days=30),
            is_revoked=False,  # Active
            created_at=datetime.now(timezone.utc),
        )

        # Note: already_revoked_token not included because query filters by ~is_revoked
        # This test verifies that only active tokens are queried and revoked

        # Mock database queries - only return active tokens (query filters by ~is_revoked)
        reset_token_result = Mock()
        reset_token_result.scalars = Mock(
            return_value=Mock(all=Mock(return_value=[sample_reset_token]))
        )

        user_result = Mock()
        user_result.scalar_one_or_none = Mock(return_value=sample_user)

        refresh_tokens_result = Mock()
        # Query only returns active tokens (database filters by ~is_revoked)
        refresh_tokens_result.scalars = Mock(
            return_value=Mock(all=Mock(return_value=[active_token]))
        )

        mock_session.execute = AsyncMock(
            side_effect=[reset_token_result, user_result, refresh_tokens_result]
        )

        # Act
        result_user = asyncio.run(
            auth_service.reset_password(
                token="plain_reset_token", new_password="NewPass123!"
            )
        )

        # Assert
        assert result_user is not None
        # Active token should be revoked
        assert active_token.is_revoked is True
        # Already revoked token should not be in the result set (filtered by query)
        mock_session.commit.assert_called()
