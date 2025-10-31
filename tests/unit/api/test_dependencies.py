"""Unit tests for API dependencies.

Tests authentication and dependency injection functions used across all API endpoints:
- get_current_user: JWT authentication with user lookup
- get_current_verified_user: Email verification check
- get_optional_current_user: Optional authentication
- get_client_ip: IP address extraction (proxy-aware)
- get_user_agent: User-Agent header extraction
- Service factory dependencies (AuthService, TokenService, etc.)
"""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

from fastapi import HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials

from src.api.dependencies import (
    get_current_user,
    get_current_verified_user,
    get_optional_current_user,
    get_client_ip,
    get_user_agent,
    get_auth_service,
    get_token_service,
    get_verification_service,
    get_password_reset_service,
)
from src.models.user import User
from src.services.jwt_service import JWTError


class TestGetCurrentUser:
    """Test suite for get_current_user dependency."""

    @pytest.fixture
    def mock_credentials(self):
        """Create mock HTTP Bearer credentials."""
        return HTTPAuthorizationCredentials(
            scheme="Bearer", credentials="valid_jwt_token"
        )

    @pytest.fixture
    def mock_session(self):
        """Create mock async session."""
        return AsyncMock()

    @pytest.fixture
    def active_user(self):
        """Create an active, unlocked user."""
        return User(
            id=uuid4(),
            email="user@example.com",
            password_hash="hash",
            email_verified=True,
            is_active=True,
            is_locked=False,
            min_token_version=1,
            created_at=datetime.now(timezone.utc),
        )

    @pytest.mark.asyncio
    async def test_get_current_user_success(
        self, mock_credentials, mock_session, active_user, monkeypatch
    ):
        """Test successful authentication and user retrieval."""
        # Arrange
        mock_jwt_service = Mock()
        mock_jwt_service.verify_token_type = Mock(return_value={"version": 1})
        mock_jwt_service.get_user_id_from_token = Mock(return_value=active_user.id)

        monkeypatch.setattr("src.api.dependencies.JWTService", lambda: mock_jwt_service)

        result = Mock()
        result.scalar_one_or_none = Mock(return_value=active_user)
        mock_session.execute = AsyncMock(return_value=result)

        # Act
        user = await get_current_user(mock_credentials, mock_session)

        # Assert
        assert user is not None
        assert user.id == active_user.id
        assert user.email == "user@example.com"
        mock_jwt_service.verify_token_type.assert_called_once_with(
            "valid_jwt_token", "access"
        )

    @pytest.mark.asyncio
    async def test_get_current_user_jwt_error(
        self, mock_credentials, mock_session, monkeypatch
    ):
        """Test authentication fails with invalid JWT."""
        # Arrange
        mock_jwt_service = Mock()
        mock_jwt_service.verify_token_type = Mock(side_effect=JWTError("Invalid token"))

        monkeypatch.setattr("src.api.dependencies.JWTService", lambda: mock_jwt_service)

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(mock_credentials, mock_session)

        assert exc_info.value.status_code == 401
        assert "Invalid token" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_get_current_user_no_user_id(
        self, mock_credentials, mock_session, monkeypatch
    ):
        """Test authentication fails when token has no user ID."""
        # Arrange
        mock_jwt_service = Mock()
        mock_jwt_service.verify_token_type = Mock()
        mock_jwt_service.get_user_id_from_token = Mock(return_value=None)

        monkeypatch.setattr("src.api.dependencies.JWTService", lambda: mock_jwt_service)

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(mock_credentials, mock_session)

        assert exc_info.value.status_code == 401
        assert "Invalid authentication token" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_get_current_user_not_found(
        self, mock_credentials, mock_session, monkeypatch
    ):
        """Test authentication fails when user doesn't exist."""
        # Arrange
        mock_jwt_service = Mock()
        mock_jwt_service.verify_token_type = Mock()
        mock_jwt_service.get_user_id_from_token = Mock(return_value=uuid4())

        monkeypatch.setattr("src.api.dependencies.JWTService", lambda: mock_jwt_service)

        result = Mock()
        result.scalar_one_or_none = Mock(return_value=None)
        mock_session.execute = AsyncMock(return_value=result)

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(mock_credentials, mock_session)

        assert exc_info.value.status_code == 401
        assert "User not found" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_get_current_user_inactive(
        self, mock_credentials, mock_session, active_user, monkeypatch
    ):
        """Test authentication fails for inactive user."""
        # Arrange
        active_user.is_active = False

        mock_jwt_service = Mock()
        mock_jwt_service.verify_token_type = Mock(return_value={"version": 1})
        mock_jwt_service.get_user_id_from_token = Mock(return_value=active_user.id)

        monkeypatch.setattr("src.api.dependencies.JWTService", lambda: mock_jwt_service)

        result = Mock()
        result.scalar_one_or_none = Mock(return_value=active_user)
        mock_session.execute = AsyncMock(return_value=result)

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(mock_credentials, mock_session)

        assert exc_info.value.status_code == 403
        assert "inactive" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_get_current_user_locked(
        self, mock_credentials, mock_session, active_user, monkeypatch
    ):
        """Test authentication fails for locked user."""
        # Arrange - lock account for 1 hour
        active_user.account_locked_until = datetime.now(timezone.utc) + timedelta(
            hours=1
        )

        mock_jwt_service = Mock()
        mock_jwt_service.verify_token_type = Mock(return_value={"version": 1})
        mock_jwt_service.get_user_id_from_token = Mock(return_value=active_user.id)

        monkeypatch.setattr("src.api.dependencies.JWTService", lambda: mock_jwt_service)

        result = Mock()
        result.scalar_one_or_none = Mock(return_value=active_user)
        mock_session.execute = AsyncMock(return_value=result)

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(mock_credentials, mock_session)

        assert exc_info.value.status_code == 403
        assert "locked" in exc_info.value.detail.lower()


class TestGetCurrentVerifiedUser:
    """Test suite for get_current_verified_user dependency."""

    @pytest.fixture
    def verified_user(self):
        """Create a verified user."""
        return User(
            id=uuid4(),
            email="verified@example.com",
            password_hash="hash",
            email_verified=True,
            is_active=True,
        )

    @pytest.mark.asyncio
    async def test_get_current_verified_user_success(self, verified_user):
        """Test verified user passes check."""
        # Act
        user = await get_current_verified_user(verified_user)

        # Assert
        assert user is not None
        assert user.email_verified is True

    @pytest.mark.asyncio
    async def test_get_current_verified_user_not_verified(self, verified_user):
        """Test unverified user fails check."""
        # Arrange
        verified_user.email_verified = False

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await get_current_verified_user(verified_user)

        assert exc_info.value.status_code == 403
        assert "verification required" in exc_info.value.detail.lower()


class TestGetOptionalCurrentUser:
    """Test suite for get_optional_current_user dependency."""

    @pytest.fixture
    def mock_session(self):
        """Create mock async session."""
        return AsyncMock()

    @pytest.fixture
    def active_user(self):
        """Create an active user."""
        return User(
            id=uuid4(),
            email="user@example.com",
            password_hash="hash",
            email_verified=True,
            is_active=True,
            is_locked=False,
        )

    @pytest.mark.asyncio
    async def test_optional_user_with_valid_token(
        self, mock_session, active_user, monkeypatch
    ):
        """Test optional authentication with valid token."""
        # Arrange
        mock_request = Mock(spec=Request)
        mock_request.headers = {"Authorization": "Bearer valid_token"}

        mock_jwt_service = Mock()
        mock_jwt_service.verify_token_type = Mock()
        mock_jwt_service.get_user_id_from_token = Mock(return_value=active_user.id)

        monkeypatch.setattr("src.api.dependencies.JWTService", lambda: mock_jwt_service)

        result = Mock()
        result.scalar_one_or_none = Mock(return_value=active_user)
        mock_session.execute = AsyncMock(return_value=result)

        # Act
        user = await get_optional_current_user(mock_request, mock_session)

        # Assert
        assert user is not None
        assert user.id == active_user.id

    @pytest.mark.asyncio
    async def test_optional_user_no_auth_header(self, mock_session):
        """Test optional authentication without Authorization header."""
        # Arrange
        mock_request = Mock(spec=Request)
        mock_request.headers = {}

        # Act
        user = await get_optional_current_user(mock_request, mock_session)

        # Assert
        assert user is None

    @pytest.mark.asyncio
    async def test_optional_user_invalid_auth_header(self, mock_session):
        """Test optional authentication with malformed Authorization header."""
        # Arrange
        mock_request = Mock(spec=Request)
        mock_request.headers = {"Authorization": "Invalid format"}

        # Act
        user = await get_optional_current_user(mock_request, mock_session)

        # Assert
        assert user is None

    @pytest.mark.asyncio
    async def test_optional_user_jwt_error(self, mock_session, monkeypatch):
        """Test optional authentication silently fails on JWT error."""
        # Arrange
        mock_request = Mock(spec=Request)
        mock_request.headers = {"Authorization": "Bearer invalid_token"}

        mock_jwt_service = Mock()
        mock_jwt_service.verify_token_type = Mock(side_effect=JWTError("Invalid"))

        monkeypatch.setattr("src.api.dependencies.JWTService", lambda: mock_jwt_service)

        # Act
        user = await get_optional_current_user(mock_request, mock_session)

        # Assert
        assert user is None

    @pytest.mark.asyncio
    async def test_optional_user_inactive(self, mock_session, active_user, monkeypatch):
        """Test optional authentication returns None for inactive user."""
        # Arrange
        active_user.is_active = False

        mock_request = Mock(spec=Request)
        mock_request.headers = {"Authorization": "Bearer valid_token"}

        mock_jwt_service = Mock()
        mock_jwt_service.verify_token_type = Mock()
        mock_jwt_service.get_user_id_from_token = Mock(return_value=active_user.id)

        monkeypatch.setattr("src.api.dependencies.JWTService", lambda: mock_jwt_service)

        result = Mock()
        result.scalar_one_or_none = Mock(return_value=active_user)
        mock_session.execute = AsyncMock(return_value=result)

        # Act
        user = await get_optional_current_user(mock_request, mock_session)

        # Assert
        assert user is None

    @pytest.mark.asyncio
    async def test_optional_user_locked(self, mock_session, active_user, monkeypatch):
        """Test optional authentication returns None for locked user."""
        # Arrange - lock account for 1 hour
        active_user.account_locked_until = datetime.now(timezone.utc) + timedelta(
            hours=1
        )

        mock_request = Mock(spec=Request)
        mock_request.headers = {"Authorization": "Bearer valid_token"}

        mock_jwt_service = Mock()
        mock_jwt_service.verify_token_type = Mock()
        mock_jwt_service.get_user_id_from_token = Mock(return_value=active_user.id)

        monkeypatch.setattr("src.api.dependencies.JWTService", lambda: mock_jwt_service)

        result = Mock()
        result.scalar_one_or_none = Mock(return_value=active_user)
        mock_session.execute = AsyncMock(return_value=result)

        # Act
        user = await get_optional_current_user(mock_request, mock_session)

        # Assert
        assert user is None


class TestRequestMetadata:
    """Test suite for request metadata extraction."""

    def test_get_client_ip_from_x_forwarded_for(self):
        """Test IP extraction from X-Forwarded-For header (proxy scenario)."""
        # Arrange
        mock_request = Mock(spec=Request)
        mock_request.headers = {"X-Forwarded-For": "203.0.113.1, 198.51.100.2"}

        # Act
        ip = get_client_ip(mock_request)

        # Assert
        assert ip == "203.0.113.1"

    def test_get_client_ip_direct_connection(self):
        """Test IP extraction from direct connection."""
        # Arrange
        mock_request = Mock(spec=Request)
        mock_request.headers = {}
        mock_request.client = Mock()
        mock_request.client.host = "203.0.113.50"

        # Act
        ip = get_client_ip(mock_request)

        # Assert
        assert ip == "203.0.113.50"

    def test_get_client_ip_no_client(self):
        """Test IP extraction returns None when no client info available."""
        # Arrange
        mock_request = Mock(spec=Request)
        mock_request.headers = {}
        mock_request.client = None

        # Act
        ip = get_client_ip(mock_request)

        # Assert
        assert ip is None

    def test_get_user_agent_present(self):
        """Test User-Agent extraction."""
        # Arrange
        mock_request = Mock(spec=Request)
        mock_request.headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0)"}

        # Act
        user_agent = get_user_agent(mock_request)

        # Assert
        assert user_agent == "Mozilla/5.0 (Windows NT 10.0)"

    def test_get_user_agent_missing(self):
        """Test User-Agent extraction returns None when header missing."""
        # Arrange
        mock_request = Mock(spec=Request)
        mock_request.headers = {}

        # Act
        user_agent = get_user_agent(mock_request)

        # Assert
        assert user_agent is None


class TestServiceFactories:
    """Test suite for service factory dependencies."""

    def test_get_auth_service(self):
        """Test AuthService factory."""
        # Arrange
        mock_session = AsyncMock()

        # Act
        service = get_auth_service(mock_session)

        # Assert
        assert service is not None
        assert service.__class__.__name__ == "AuthService"

    def test_get_token_service(self):
        """Test TokenService factory."""
        # Arrange
        mock_session = AsyncMock()

        # Act
        service = get_token_service(mock_session)

        # Assert
        assert service is not None
        assert service.__class__.__name__ == "TokenService"

    def test_get_verification_service(self):
        """Test VerificationService factory."""
        # Arrange
        mock_session = AsyncMock()

        # Act
        service = get_verification_service(mock_session)

        # Assert
        assert service is not None
        assert service.__class__.__name__ == "VerificationService"

    def test_get_password_reset_service(self):
        """Test PasswordResetService factory."""
        # Arrange
        mock_session = AsyncMock()

        # Act
        service = get_password_reset_service(mock_session)

        # Assert
        assert service is not None
        assert service.__class__.__name__ == "PasswordResetService"
