"""Unit tests for VerificationService.

Tests email verification workflows including:
- Token generation and email sending
- Token validation (invalid, expired, used)
- User activation and welcome email sending
- Security features (token hashing, single-use tokens)

Note:
    These tests ensure proper separation of concerns after extracting
    VerificationService from AuthService (Phase 3 refactoring).
"""

import asyncio
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

from fastapi import HTTPException

from src.models.user import User
from src.models.auth import EmailVerificationToken
from src.services.verification_service import VerificationService


class TestVerificationService:
    """Test suite for VerificationService.

    Tests the complete email verification workflow including security
    features like token hashing and single-use tokens.
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
        with patch("src.services.verification_service.PasswordService") as mock_cls:
            service = Mock()
            service.hash_password = Mock(return_value="hashed_token")
            service.verify_password = Mock(return_value=True)
            mock_cls.return_value = service
            yield service

    @pytest.fixture
    def mock_email_service(self):
        """Create a mock EmailService."""
        with patch("src.services.verification_service.EmailService") as mock_cls:
            service = AsyncMock()
            service.send_verification_email = AsyncMock()
            service.send_welcome_email = AsyncMock()
            mock_cls.return_value = service
            yield service

    @pytest.fixture
    def verification_service(
        self, mock_session, mock_password_service, mock_email_service
    ):
        """Create VerificationService with mocked dependencies."""
        return VerificationService(mock_session)

    @pytest.fixture
    def sample_user(self):
        """Create a sample user."""
        return User(
            id=uuid4(),
            email="test@example.com",
            password_hash="hashed_password",
            name="Test User",
            email_verified=False,
            is_active=True,
            created_at=datetime.now(timezone.utc),
        )

    @pytest.fixture
    def sample_verification_token(self, sample_user):
        """Create a valid verification token."""
        return EmailVerificationToken(
            id=uuid4(),
            user_id=sample_user.id,
            token_hash="hashed_token",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
            used_at=None,
            created_at=datetime.now(timezone.utc),
        )

    def test_create_verification_token_generates_token(
        self, verification_service, mock_session, mock_email_service
    ):
        """Test create_verification_token generates and stores token."""
        # Arrange
        user_id = uuid4()
        email = "test@example.com"
        user_name = "Test User"

        # Act
        token = asyncio.run(
            verification_service.create_verification_token(
                user_id=user_id, email=email, user_name=user_name
            )
        )

        # Assert
        assert token is not None
        assert isinstance(token, str)
        assert len(token) > 0
        mock_session.add.assert_called_once()
        mock_session.flush.assert_called_once()

    def test_create_verification_token_sends_email(
        self, verification_service, mock_email_service
    ):
        """Test create_verification_token sends verification email."""
        # Arrange
        user_id = uuid4()
        email = "test@example.com"
        user_name = "Test User"

        # Act
        asyncio.run(
            verification_service.create_verification_token(
                user_id=user_id, email=email, user_name=user_name
            )
        )

        # Assert
        mock_email_service.send_verification_email.assert_called_once()
        call_args = mock_email_service.send_verification_email.call_args
        assert call_args.kwargs["to_email"] == email
        assert call_args.kwargs["user_name"] == user_name
        assert "verification_token" in call_args.kwargs

    def test_create_verification_token_hashes_token(
        self, verification_service, mock_password_service
    ):
        """Test create_verification_token hashes token before storage."""
        # Arrange
        user_id = uuid4()
        email = "test@example.com"

        # Act
        asyncio.run(
            verification_service.create_verification_token(
                user_id=user_id, email=email, user_name="Test"
            )
        )

        # Assert
        mock_password_service.hash_password.assert_called_once()

    def test_create_verification_token_handles_email_failure(
        self, verification_service, mock_email_service, caplog
    ):
        """Test create_verification_token handles email sending failure gracefully."""
        # Arrange
        user_id = uuid4()
        email = "test@example.com"
        mock_email_service.send_verification_email.side_effect = Exception(
            "Email service unavailable"
        )

        # Act - should not raise exception
        token = asyncio.run(
            verification_service.create_verification_token(
                user_id=user_id, email=email, user_name="Test"
            )
        )

        # Assert
        assert token is not None  # Token still created
        assert "Failed to send verification email" in caplog.text

    def test_verify_email_success(
        self,
        verification_service,
        mock_session,
        sample_user,
        sample_verification_token,
        mock_email_service,
    ):
        """Test verify_email successfully verifies user."""
        # Arrange
        tokens_result = Mock()
        tokens_result.scalars = Mock(
            return_value=Mock(all=Mock(return_value=[sample_verification_token]))
        )

        user_result = Mock()
        user_result.scalar_one_or_none = Mock(return_value=sample_user)

        mock_session.execute = AsyncMock(side_effect=[tokens_result, user_result])

        # Act
        user = asyncio.run(verification_service.verify_email("plain_token"))

        # Assert
        assert user is not None
        assert user.email_verified is True
        assert user.email_verified_at is not None
        assert sample_verification_token.used_at is not None
        mock_session.commit.assert_called_once()

    def test_verify_email_sends_welcome_email(
        self,
        verification_service,
        mock_session,
        sample_user,
        sample_verification_token,
        mock_email_service,
    ):
        """Test verify_email sends welcome email after verification."""
        # Arrange
        tokens_result = Mock()
        tokens_result.scalars = Mock(
            return_value=Mock(all=Mock(return_value=[sample_verification_token]))
        )

        user_result = Mock()
        user_result.scalar_one_or_none = Mock(return_value=sample_user)

        mock_session.execute = AsyncMock(side_effect=[tokens_result, user_result])

        # Act
        asyncio.run(verification_service.verify_email("plain_token"))

        # Assert
        mock_email_service.send_welcome_email.assert_called_once()
        call_args = mock_email_service.send_welcome_email.call_args
        assert call_args.kwargs["to_email"] == sample_user.email
        assert call_args.kwargs["user_name"] == sample_user.name

    def test_verify_email_invalid_token(
        self, verification_service, mock_session, mock_password_service
    ):
        """Test verify_email fails with invalid token."""
        # Arrange - no matching tokens
        tokens_result = Mock()
        tokens_result.scalars = Mock(return_value=Mock(all=Mock(return_value=[])))

        mock_session.execute = AsyncMock(return_value=tokens_result)

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(verification_service.verify_email("invalid_token"))

        assert exc_info.value.status_code == 400
        assert "Invalid or already used" in exc_info.value.detail

    def test_verify_email_expired_token(
        self, verification_service, mock_session, sample_user
    ):
        """Test verify_email fails with expired token."""
        # Arrange - expired token
        expired_token = EmailVerificationToken(
            id=uuid4(),
            user_id=sample_user.id,
            token_hash="hashed_token",
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),  # Expired
            used_at=None,
            created_at=datetime.now(timezone.utc),
        )

        tokens_result = Mock()
        tokens_result.scalars = Mock(
            return_value=Mock(all=Mock(return_value=[expired_token]))
        )

        mock_session.execute = AsyncMock(return_value=tokens_result)

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(verification_service.verify_email("expired_token"))

        assert exc_info.value.status_code == 400
        assert "expired" in exc_info.value.detail.lower()

    def test_verify_email_already_used_token(
        self, verification_service, mock_session, sample_user, mock_password_service
    ):
        """Test verify_email fails with already used token."""
        # Arrange - Mock query to return no unused tokens (simulates used token scenario)
        # In real scenario, the query filters out used tokens with used_at.is_(None)
        tokens_result = Mock()
        tokens_result.scalars = Mock(return_value=Mock(all=Mock(return_value=[])))

        mock_session.execute = AsyncMock(return_value=tokens_result)

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(verification_service.verify_email("used_token"))

        assert exc_info.value.status_code == 400
        assert "Invalid or already used" in exc_info.value.detail

    def test_verify_email_user_not_found(
        self, verification_service, mock_session, sample_verification_token
    ):
        """Test verify_email fails when user doesn't exist."""
        # Arrange
        tokens_result = Mock()
        tokens_result.scalars = Mock(
            return_value=Mock(all=Mock(return_value=[sample_verification_token]))
        )

        user_result = Mock()
        user_result.scalar_one_or_none = Mock(return_value=None)  # User not found

        mock_session.execute = AsyncMock(side_effect=[tokens_result, user_result])

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(verification_service.verify_email("valid_token"))

        assert exc_info.value.status_code == 404
        assert "User not found" in exc_info.value.detail

    def test_verify_email_handles_welcome_email_failure(
        self,
        verification_service,
        mock_session,
        sample_user,
        sample_verification_token,
        mock_email_service,
        caplog,
    ):
        """Test verify_email handles welcome email failure gracefully."""
        # Arrange
        tokens_result = Mock()
        tokens_result.scalars = Mock(
            return_value=Mock(all=Mock(return_value=[sample_verification_token]))
        )

        user_result = Mock()
        user_result.scalar_one_or_none = Mock(return_value=sample_user)

        mock_session.execute = AsyncMock(side_effect=[tokens_result, user_result])

        mock_email_service.send_welcome_email.side_effect = Exception(
            "Email service down"
        )

        # Act - should not raise exception
        user = asyncio.run(verification_service.verify_email("plain_token"))

        # Assert
        assert user is not None
        assert user.email_verified is True  # Verification still completed
        assert "Failed to send welcome email" in caplog.text

    def test_verify_email_marks_single_use(
        self,
        verification_service,
        mock_session,
        sample_user,
        sample_verification_token,
    ):
        """Test verify_email marks token as used to prevent reuse."""
        # Arrange
        tokens_result = Mock()
        tokens_result.scalars = Mock(
            return_value=Mock(all=Mock(return_value=[sample_verification_token]))
        )

        user_result = Mock()
        user_result.scalar_one_or_none = Mock(return_value=sample_user)

        mock_session.execute = AsyncMock(side_effect=[tokens_result, user_result])

        # Act
        asyncio.run(verification_service.verify_email("plain_token"))

        # Assert
        assert sample_verification_token.used_at is not None
        mock_session.commit.assert_called_once()

    def test_verify_email_sets_verification_timestamp(
        self,
        verification_service,
        mock_session,
        sample_user,
        sample_verification_token,
    ):
        """Test verify_email sets email_verified_at timestamp."""
        # Arrange
        tokens_result = Mock()
        tokens_result.scalars = Mock(
            return_value=Mock(all=Mock(return_value=[sample_verification_token]))
        )

        user_result = Mock()
        user_result.scalar_one_or_none = Mock(return_value=sample_user)

        mock_session.execute = AsyncMock(side_effect=[tokens_result, user_result])

        # Act
        user = asyncio.run(verification_service.verify_email("plain_token"))

        # Assert
        assert user.email_verified_at is not None
        assert isinstance(user.email_verified_at, datetime)

    def test_verify_email_verifies_token_hash(
        self,
        verification_service,
        mock_session,
        sample_verification_token,
        mock_password_service,
    ):
        """Test verify_email uses password service to verify token hash."""
        # Arrange
        tokens_result = Mock()
        tokens_result.scalars = Mock(
            return_value=Mock(all=Mock(return_value=[sample_verification_token]))
        )

        mock_session.execute = AsyncMock(return_value=tokens_result)

        # Act
        asyncio.run(verification_service.verify_email("plain_token"))

        # Assert
        mock_password_service.verify_password.assert_called_once_with(
            "plain_token", "hashed_token"
        )
