"""Unit tests for AuthService orchestration and delegation.

Tests that AuthService properly orchestrates authentication workflows and
delegates to specialized services. The detailed logic is tested in the
respective service tests:
- VerificationService tests: test_verification_service.py
- PasswordResetService tests: test_password_reset_service.py
- PasswordService tests: test_password_service.py
- JWTService tests: test_jwt_service.py

These tests verify:
- User registration workflow with verification delegation
- Login workflow with credential validation and token generation
- Token refresh workflow with validation
- Logout workflow with token revocation
- Profile management (get by ID/email, update)
- Password change workflow
- Proper delegation to specialized services
"""

import asyncio
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

from fastapi import HTTPException

from src.models.user import User
from src.models.auth import RefreshToken
from src.services.auth_service import AuthService


class TestAuthServiceRegistration:
    """Test suite for user registration workflow."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock AsyncSession."""
        session = AsyncMock()
        session.add = Mock()
        session.commit = AsyncMock()
        session.flush = AsyncMock()
        session.refresh = AsyncMock()
        return session

    @pytest.fixture
    def mock_password_service(self):
        """Create a mock PasswordService."""
        with patch("src.services.auth_service.PasswordService") as mock_cls:
            service = Mock()
            service.hash_password = Mock(return_value="hashed_password")
            service.validate_password_strength = Mock(return_value=(True, None))
            mock_cls.return_value = service
            yield service

    @pytest.fixture
    def mock_verification_service(self):
        """Create a mock VerificationService."""
        with patch("src.services.auth_service.VerificationService") as mock_cls:
            service = AsyncMock()
            service.create_verification_token = AsyncMock(return_value="token123")
            mock_cls.return_value = service
            yield service

    @pytest.fixture
    def auth_service(self, mock_session, mock_password_service, mock_verification_service):
        """Create AuthService with mocked dependencies."""
        return AuthService(mock_session)

    def test_register_user_success(
        self, auth_service, mock_session, mock_password_service, mock_verification_service
    ):
        """Test successful user registration."""
        # Arrange - no existing user
        result = Mock()
        result.scalar_one_or_none = Mock(return_value=None)
        mock_session.execute = AsyncMock(return_value=result)

        # Act
        user = asyncio.run(
            auth_service.register_user(
                email="new@example.com", password="SecurePass123!", name="New User"
            )
        )

        # Assert
        assert user is not None
        assert user.email == "new@example.com"
        assert user.name == "New User"
        assert user.email_verified is False
        assert user.is_active is True
        mock_password_service.validate_password_strength.assert_called_once()
        mock_password_service.hash_password.assert_called_once_with("SecurePass123!")
        mock_verification_service.create_verification_token.assert_called_once()
        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()

    def test_register_user_duplicate_email(self, auth_service, mock_session):
        """Test registration fails with duplicate email."""
        # Arrange - existing user
        existing_user = User(
            id=uuid4(),
            email="existing@example.com",
            password_hash="hash",
            email_verified=True,
            is_active=True,
        )
        result = Mock()
        result.scalar_one_or_none = Mock(return_value=existing_user)
        mock_session.execute = AsyncMock(return_value=result)

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(
                auth_service.register_user(
                    email="existing@example.com", password="SecurePass123!"
                )
            )

        assert exc_info.value.status_code == 400
        assert "already registered" in exc_info.value.detail.lower()

    def test_register_user_weak_password(
        self, auth_service, mock_session, mock_password_service
    ):
        """Test registration fails with weak password."""
        # Arrange
        result = Mock()
        result.scalar_one_or_none = Mock(return_value=None)
        mock_session.execute = AsyncMock(return_value=result)

        mock_password_service.validate_password_strength = Mock(
            return_value=(False, "Password too weak")
        )

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(
                auth_service.register_user(email="new@example.com", password="weak")
            )

        assert exc_info.value.status_code == 400
        assert "Password too weak" in exc_info.value.detail

    def test_register_user_delegates_verification(
        self, auth_service, mock_session, mock_verification_service
    ):
        """Test registration delegates to VerificationService."""
        # Arrange
        result = Mock()
        result.scalar_one_or_none = Mock(return_value=None)
        mock_session.execute = AsyncMock(return_value=result)

        # Act
        user = asyncio.run(
            auth_service.register_user(
                email="test@example.com", password="SecurePass123!", name="Test User"
            )
        )

        # Assert - VerificationService called with correct params
        mock_verification_service.create_verification_token.assert_called_once()
        call_args = mock_verification_service.create_verification_token.call_args
        assert call_args.kwargs["user_id"] == user.id
        assert call_args.kwargs["email"] == "test@example.com"
        assert call_args.kwargs["user_name"] == "Test User"


class TestAuthServiceEmailVerification:
    """Test suite for email verification delegation."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock AsyncSession."""
        return AsyncMock()

    @pytest.fixture
    def mock_verification_service(self):
        """Create a mock VerificationService."""
        with patch("src.services.auth_service.VerificationService") as mock_cls:
            service = AsyncMock()
            verified_user = User(
                id=uuid4(),
                email="verified@example.com",
                password_hash="hash",
                email_verified=True,
                is_active=True,
            )
            service.verify_email = AsyncMock(return_value=verified_user)
            mock_cls.return_value = service
            yield service

    @pytest.fixture
    def auth_service(self, mock_session, mock_verification_service):
        """Create AuthService with mocked dependencies."""
        with patch("src.services.auth_service.PasswordService"):
            return AuthService(mock_session)

    def test_verify_email_delegates_to_service(
        self, auth_service, mock_verification_service
    ):
        """Test verify_email delegates to VerificationService."""
        # Act
        user = asyncio.run(auth_service.verify_email("test_token"))

        # Assert
        assert user is not None
        assert user.email_verified is True
        mock_verification_service.verify_email.assert_called_once_with("test_token")


class TestAuthServiceLogin:
    """Test suite for login workflow."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock AsyncSession."""
        session = AsyncMock()
        session.commit = AsyncMock()
        session.flush = AsyncMock()
        session.refresh = AsyncMock()
        session.add = Mock()
        return session

    @pytest.fixture
    def mock_password_service(self):
        """Create a mock PasswordService."""
        with patch("src.services.auth_service.PasswordService") as mock_cls:
            service = Mock()
            service.verify_password = Mock(return_value=True)
            service.hash_password = Mock(return_value="new_hash")
            service.needs_rehash = Mock(return_value=False)
            mock_cls.return_value = service
            yield service

    @pytest.fixture
    def mock_jwt_service(self):
        """Create a mock JWTService."""
        with patch("src.services.auth_service.JWTService") as mock_cls:
            service = Mock()
            service.create_access_token = Mock(return_value="access_token_123")
            mock_cls.return_value = service
            yield service

    @pytest.fixture
    def verified_user(self):
        """Create a verified, active user."""
        return User(
            id=uuid4(),
            email="active@example.com",
            password_hash="hashed_password",
            name="Active User",
            email_verified=True,
            is_active=True,
            created_at=datetime.now(timezone.utc),
        )

    @pytest.fixture
    def auth_service(
        self, mock_session, mock_password_service, mock_jwt_service, verified_user
    ):
        """Create AuthService with mocked dependencies."""
        with patch("src.services.auth_service.VerificationService"), patch(
            "src.services.auth_service.PasswordResetService"
        ):
            return AuthService(mock_session)

    def test_login_success(
        self,
        auth_service,
        mock_session,
        verified_user,
        mock_password_service,
        mock_jwt_service,
    ):
        """Test successful login."""
        # Arrange
        result = Mock()
        result.scalar_one_or_none = Mock(return_value=verified_user)
        mock_session.execute = AsyncMock(return_value=result)

        # Act
        access_token, refresh_token, user = asyncio.run(
            auth_service.login(email="active@example.com", password="correct_password")
        )

        # Assert
        assert access_token == "access_token_123"
        assert refresh_token is not None
        assert user.email == "active@example.com"
        assert user.last_login_at is not None
        mock_password_service.verify_password.assert_called_once()
        mock_jwt_service.create_access_token.assert_called_once()
        mock_session.add.assert_called_once()  # refresh token
        mock_session.commit.assert_called_once()

    def test_login_invalid_email(self, auth_service, mock_session):
        """Test login fails with invalid email."""
        # Arrange - user not found
        result = Mock()
        result.scalar_one_or_none = Mock(return_value=None)
        mock_session.execute = AsyncMock(return_value=result)

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(
                auth_service.login(email="nonexistent@example.com", password="password")
            )

        assert exc_info.value.status_code == 401
        assert "Invalid email or password" in exc_info.value.detail

    def test_login_wrong_password(
        self, auth_service, mock_session, verified_user, mock_password_service
    ):
        """Test login fails with wrong password."""
        # Arrange
        result = Mock()
        result.scalar_one_or_none = Mock(return_value=verified_user)
        mock_session.execute = AsyncMock(return_value=result)

        mock_password_service.verify_password = Mock(return_value=False)

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(
                auth_service.login(email="active@example.com", password="wrong_password")
            )

        assert exc_info.value.status_code == 401
        assert "Invalid email or password" in exc_info.value.detail

    def test_login_inactive_user(self, auth_service, mock_session, verified_user):
        """Test login fails for inactive user."""
        # Arrange
        verified_user.is_active = False
        result = Mock()
        result.scalar_one_or_none = Mock(return_value=verified_user)
        mock_session.execute = AsyncMock(return_value=result)

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(
                auth_service.login(email="active@example.com", password="password")
            )

        assert exc_info.value.status_code == 403
        assert "disabled" in exc_info.value.detail.lower()

    def test_login_unverified_email(self, auth_service, mock_session, verified_user):
        """Test login fails for unverified email."""
        # Arrange
        verified_user.email_verified = False
        result = Mock()
        result.scalar_one_or_none = Mock(return_value=verified_user)
        mock_session.execute = AsyncMock(return_value=result)

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(
                auth_service.login(email="active@example.com", password="password")
            )

        assert exc_info.value.status_code == 403
        assert "not verified" in exc_info.value.detail.lower()

    def test_login_rehashes_password_if_needed(
        self,
        auth_service,
        mock_session,
        verified_user,
        mock_password_service,
    ):
        """Test login rehashes password if bcrypt rounds changed."""
        # Arrange
        result = Mock()
        result.scalar_one_or_none = Mock(return_value=verified_user)
        mock_session.execute = AsyncMock(return_value=result)

        mock_password_service.needs_rehash = Mock(return_value=True)
        original_hash = verified_user.password_hash

        # Act
        asyncio.run(
            auth_service.login(email="active@example.com", password="password")
        )

        # Assert - verify password was rehashed
        assert mock_password_service.needs_rehash.called
        assert verified_user.password_hash == "new_hash"
        assert verified_user.password_hash != original_hash


class TestAuthServiceTokenRefresh:
    """Test suite for token refresh workflow."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock AsyncSession."""
        return AsyncMock()

    @pytest.fixture
    def mock_password_service(self):
        """Create a mock PasswordService."""
        with patch("src.services.auth_service.PasswordService") as mock_cls:
            service = Mock()
            service.verify_password = Mock(return_value=True)
            mock_cls.return_value = service
            yield service

    @pytest.fixture
    def mock_jwt_service(self):
        """Create a mock JWTService."""
        with patch("src.services.auth_service.JWTService") as mock_cls:
            service = Mock()
            service.create_access_token = Mock(return_value="new_access_token_456")
            mock_cls.return_value = service
            yield service

    @pytest.fixture
    def active_user(self):
        """Create an active user."""
        return User(
            id=uuid4(),
            email="user@example.com",
            password_hash="hash",
            email_verified=True,
            is_active=True,
        )

    @pytest.fixture
    def valid_refresh_token_record(self, active_user):
        """Create a valid refresh token record."""
        return RefreshToken(
            id=uuid4(),
            user_id=active_user.id,
            token_hash="hashed_refresh_token",
            expires_at=datetime.now(timezone.utc) + timedelta(days=30),
            is_revoked=False,
            created_at=datetime.now(timezone.utc),
        )

    @pytest.fixture
    def auth_service(
        self, mock_session, mock_password_service, mock_jwt_service
    ):
        """Create AuthService with mocked dependencies."""
        with patch("src.services.auth_service.VerificationService"), patch(
            "src.services.auth_service.PasswordResetService"
        ):
            return AuthService(mock_session)

    def test_refresh_access_token_success(
        self,
        auth_service,
        mock_session,
        active_user,
        valid_refresh_token_record,
        mock_jwt_service,
    ):
        """Test successful token refresh."""
        # Arrange
        tokens_result = Mock()
        tokens_result.scalars = Mock(
            return_value=Mock(all=Mock(return_value=[valid_refresh_token_record]))
        )

        user_result = Mock()
        user_result.scalar_one_or_none = Mock(return_value=active_user)

        mock_session.execute = AsyncMock(side_effect=[tokens_result, user_result])

        # Act
        new_access_token = asyncio.run(
            auth_service.refresh_access_token("plain_refresh_token")
        )

        # Assert
        assert new_access_token == "new_access_token_456"
        mock_jwt_service.create_access_token.assert_called_once_with(
            user_id=active_user.id, email=active_user.email
        )

    def test_refresh_access_token_invalid_token(
        self, auth_service, mock_session, mock_password_service
    ):
        """Test token refresh fails with invalid token."""
        # Arrange - no matching tokens
        tokens_result = Mock()
        tokens_result.scalars = Mock(return_value=Mock(all=Mock(return_value=[])))

        mock_session.execute = AsyncMock(return_value=tokens_result)

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(auth_service.refresh_access_token("invalid_token"))

        assert exc_info.value.status_code == 401
        assert "Invalid or revoked" in exc_info.value.detail

    def test_refresh_access_token_expired(
        self, auth_service, mock_session, active_user, valid_refresh_token_record
    ):
        """Test token refresh fails with expired token."""
        # Arrange - expired token
        valid_refresh_token_record.expires_at = datetime.now(timezone.utc) - timedelta(
            days=1
        )

        tokens_result = Mock()
        tokens_result.scalars = Mock(
            return_value=Mock(all=Mock(return_value=[valid_refresh_token_record]))
        )

        mock_session.execute = AsyncMock(return_value=tokens_result)

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(auth_service.refresh_access_token("expired_token"))

        assert exc_info.value.status_code == 401
        assert "expired" in exc_info.value.detail.lower()

    def test_refresh_access_token_inactive_user(
        self, auth_service, mock_session, active_user, valid_refresh_token_record
    ):
        """Test token refresh fails for inactive user."""
        # Arrange - inactive user
        active_user.is_active = False

        tokens_result = Mock()
        tokens_result.scalars = Mock(
            return_value=Mock(all=Mock(return_value=[valid_refresh_token_record]))
        )

        user_result = Mock()
        user_result.scalar_one_or_none = Mock(return_value=active_user)

        mock_session.execute = AsyncMock(side_effect=[tokens_result, user_result])

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(auth_service.refresh_access_token("valid_token"))

        assert exc_info.value.status_code == 401
        assert "inactive" in exc_info.value.detail.lower()


class TestAuthServiceLogout:
    """Test suite for logout workflow."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock AsyncSession."""
        session = AsyncMock()
        session.commit = AsyncMock()
        return session

    @pytest.fixture
    def mock_password_service(self):
        """Create a mock PasswordService."""
        with patch("src.services.auth_service.PasswordService") as mock_cls:
            service = Mock()
            service.verify_password = Mock(return_value=True)
            mock_cls.return_value = service
            yield service

    @pytest.fixture
    def valid_refresh_token_record(self):
        """Create a valid refresh token record."""
        return RefreshToken(
            id=uuid4(),
            user_id=uuid4(),
            token_hash="hashed_token",
            expires_at=datetime.now(timezone.utc) + timedelta(days=30),
            is_revoked=False,
            created_at=datetime.now(timezone.utc),
        )

    @pytest.fixture
    def auth_service(self, mock_session, mock_password_service):
        """Create AuthService with mocked dependencies."""
        with patch("src.services.auth_service.VerificationService"), patch(
            "src.services.auth_service.PasswordResetService"
        ), patch("src.services.auth_service.JWTService"):
            return AuthService(mock_session)

    def test_logout_success(
        self, auth_service, mock_session, valid_refresh_token_record
    ):
        """Test successful logout."""
        # Arrange
        tokens_result = Mock()
        tokens_result.scalars = Mock(
            return_value=Mock(all=Mock(return_value=[valid_refresh_token_record]))
        )

        mock_session.execute = AsyncMock(return_value=tokens_result)

        # Act
        asyncio.run(auth_service.logout("plain_refresh_token"))

        # Assert
        assert valid_refresh_token_record.is_revoked is True
        assert valid_refresh_token_record.revoked_at is not None
        mock_session.commit.assert_called_once()

    def test_logout_invalid_token(self, auth_service, mock_session):
        """Test logout with invalid token doesn't raise error (security)."""
        # Arrange - no matching tokens
        tokens_result = Mock()
        tokens_result.scalars = Mock(return_value=Mock(all=Mock(return_value=[])))

        mock_session.execute = AsyncMock(return_value=tokens_result)

        # Act - should not raise exception
        asyncio.run(auth_service.logout("invalid_token"))

        # Assert - no commit (no token to revoke)
        mock_session.commit.assert_not_called()


class TestAuthServiceProfileManagement:
    """Test suite for profile management operations."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock AsyncSession."""
        session = AsyncMock()
        session.commit = AsyncMock()
        session.refresh = AsyncMock()
        return session

    @pytest.fixture
    def sample_user(self):
        """Create a sample user."""
        return User(
            id=uuid4(),
            email="user@example.com",
            password_hash="hash",
            name="Original Name",
            email_verified=True,
            is_active=True,
        )

    @pytest.fixture
    def auth_service(self, mock_session):
        """Create AuthService with mocked dependencies."""
        with patch("src.services.auth_service.PasswordService"), patch(
            "src.services.auth_service.JWTService"
        ), patch("src.services.auth_service.VerificationService"), patch(
            "src.services.auth_service.PasswordResetService"
        ):
            return AuthService(mock_session)

    def test_get_user_by_id_success(self, auth_service, mock_session, sample_user):
        """Test get_user_by_id returns user."""
        # Arrange
        result = Mock()
        result.scalar_one_or_none = Mock(return_value=sample_user)
        mock_session.execute = AsyncMock(return_value=result)

        # Act
        user = asyncio.run(auth_service.get_user_by_id(sample_user.id))

        # Assert
        assert user is not None
        assert user.id == sample_user.id

    def test_get_user_by_id_not_found(self, auth_service, mock_session):
        """Test get_user_by_id returns None when not found."""
        # Arrange
        result = Mock()
        result.scalar_one_or_none = Mock(return_value=None)
        mock_session.execute = AsyncMock(return_value=result)

        # Act
        user = asyncio.run(auth_service.get_user_by_id(uuid4()))

        # Assert
        assert user is None

    def test_get_user_by_email_success(self, auth_service, mock_session, sample_user):
        """Test get_user_by_email returns user."""
        # Arrange
        result = Mock()
        result.scalar_one_or_none = Mock(return_value=sample_user)
        mock_session.execute = AsyncMock(return_value=result)

        # Act
        user = asyncio.run(auth_service.get_user_by_email(sample_user.email))

        # Assert
        assert user is not None
        assert user.email == sample_user.email

    def test_update_user_profile_success(self, auth_service, mock_session, sample_user):
        """Test update_user_profile updates name."""
        # Arrange
        result = Mock()
        result.scalar_one_or_none = Mock(return_value=sample_user)
        mock_session.execute = AsyncMock(return_value=result)

        # Act
        user = asyncio.run(
            auth_service.update_user_profile(user_id=sample_user.id, name="New Name")
        )

        # Assert
        assert user.name == "New Name"
        mock_session.commit.assert_called_once()
        mock_session.refresh.assert_called_once()

    def test_update_user_profile_user_not_found(self, auth_service, mock_session):
        """Test update_user_profile fails when user not found."""
        # Arrange
        result = Mock()
        result.scalar_one_or_none = Mock(return_value=None)
        mock_session.execute = AsyncMock(return_value=result)

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(auth_service.update_user_profile(user_id=uuid4(), name="New"))

        assert exc_info.value.status_code == 404
        assert "User not found" in exc_info.value.detail
