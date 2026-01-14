"""Unit tests for AuthenticateUserHandler.

Tests cover:
- Successful authentication (returns AuthenticatedUser)
- Invalid credentials (user not found)
- Invalid credentials (wrong password)
- Email not verified
- Account locked
- Account inactive
- Failed login counter increment
- Event publishing (ATTEMPTED, SUCCEEDED, FAILED)

Architecture:
- Unit tests for application handler (mocked dependencies)
- Mock repository protocols
- Test handler logic, not persistence
- Async tests (handler uses async repositories)

Note: This handler ONLY authenticates. It does NOT generate tokens.
Token generation is handled by GenerateAuthTokensHandler (CQRS separation).
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, Mock
from uuid import UUID
from uuid_extensions import uuid7

import pytest

from src.application.commands.auth_commands import AuthenticateUser
from src.application.dtos import AuthenticatedUser
from src.application.commands.handlers.authenticate_user_handler import (
    AuthenticationError,
    AuthenticateUserHandler,
)
from src.core.result import Failure, Success
from src.domain.entities.user import User
from src.domain.events.auth_events import (
    UserLoginAttempted,
    UserLoginFailed,
    UserLoginSucceeded,
)


def create_mock_user(
    user_id: UUID | None = None,
    email: str = "test@example.com",
    password_hash: str = "hashed_password",
    is_verified: bool = True,
    is_active: bool = True,
    failed_login_attempts: int = 0,
    locked_until: datetime | None = None,
) -> Mock:
    """Create a mock User entity for testing."""
    mock_user = Mock(spec=User)
    mock_user.id = user_id or uuid7()
    mock_user.email = email
    mock_user.password_hash = password_hash
    mock_user.is_verified = is_verified
    mock_user.is_active = is_active
    mock_user.failed_login_attempts = failed_login_attempts
    mock_user.locked_until = locked_until
    mock_user.is_locked.return_value = (
        locked_until is not None and locked_until > datetime.now(UTC)
    )
    return mock_user


@pytest.mark.unit
class TestAuthenticateUserHandlerSuccess:
    """Test successful authentication scenarios."""

    @pytest.mark.asyncio
    async def test_authentication_success_returns_authenticated_user(self):
        """Test successful auth returns Success with AuthenticatedUser."""
        # Arrange
        mock_user = create_mock_user()

        mock_user_repo = AsyncMock()
        mock_user_repo.find_by_email.return_value = mock_user

        mock_password_service = Mock()
        mock_password_service.verify_password.return_value = True

        mock_event_bus = AsyncMock()

        handler = AuthenticateUserHandler(
            user_repo=mock_user_repo,
            password_service=mock_password_service,
            event_bus=mock_event_bus,
        )

        command = AuthenticateUser(
            email="test@example.com",
            password="SecurePass123!",
        )

        # Act
        result = await handler.handle(command)

        # Assert
        assert isinstance(result, Success)
        assert isinstance(result.value, AuthenticatedUser)
        assert result.value.user_id == mock_user.id
        assert result.value.email == mock_user.email
        assert result.value.roles == ["user"]

    @pytest.mark.asyncio
    async def test_authentication_success_verifies_password(self):
        """Test auth verifies password with password service."""
        # Arrange
        mock_user = create_mock_user(password_hash="stored_hash")

        mock_user_repo = AsyncMock()
        mock_user_repo.find_by_email.return_value = mock_user

        mock_password_service = Mock()
        mock_password_service.verify_password.return_value = True

        mock_event_bus = AsyncMock()

        handler = AuthenticateUserHandler(
            user_repo=mock_user_repo,
            password_service=mock_password_service,
            event_bus=mock_event_bus,
        )

        command = AuthenticateUser(
            email="test@example.com",
            password="MyPassword123!",
        )

        # Act
        await handler.handle(command)

        # Assert
        mock_password_service.verify_password.assert_called_once_with(
            "MyPassword123!",
            "stored_hash",
        )

    @pytest.mark.asyncio
    async def test_authentication_success_resets_failed_login_counter(self):
        """Test successful auth resets failed login counter."""
        # Arrange
        mock_user = create_mock_user(failed_login_attempts=3)

        mock_user_repo = AsyncMock()
        mock_user_repo.find_by_email.return_value = mock_user

        mock_password_service = Mock()
        mock_password_service.verify_password.return_value = True

        mock_event_bus = AsyncMock()

        handler = AuthenticateUserHandler(
            user_repo=mock_user_repo,
            password_service=mock_password_service,
            event_bus=mock_event_bus,
        )

        command = AuthenticateUser(
            email="test@example.com",
            password="SecurePass123!",
        )

        # Act
        await handler.handle(command)

        # Assert
        mock_user.reset_failed_login.assert_called_once()
        mock_user_repo.update.assert_called()


@pytest.mark.unit
class TestAuthenticateUserHandlerFailure:
    """Test authentication failure scenarios."""

    @pytest.mark.asyncio
    async def test_authentication_fails_when_user_not_found(self):
        """Test auth fails with INVALID_CREDENTIALS when user doesn't exist."""
        # Arrange
        mock_user_repo = AsyncMock()
        mock_user_repo.find_by_email.return_value = None

        mock_password_service = Mock()
        mock_event_bus = AsyncMock()

        handler = AuthenticateUserHandler(
            user_repo=mock_user_repo,
            password_service=mock_password_service,
            event_bus=mock_event_bus,
        )

        command = AuthenticateUser(
            email="nonexistent@example.com",
            password="SecurePass123!",
        )

        # Act
        result = await handler.handle(command)

        # Assert
        assert isinstance(result, Failure)
        assert result.error == AuthenticationError.INVALID_CREDENTIALS

    @pytest.mark.asyncio
    async def test_authentication_fails_when_password_wrong(self):
        """Test auth fails with INVALID_CREDENTIALS on wrong password."""
        # Arrange
        mock_user = create_mock_user()

        mock_user_repo = AsyncMock()
        mock_user_repo.find_by_email.return_value = mock_user

        mock_password_service = Mock()
        mock_password_service.verify_password.return_value = False

        mock_event_bus = AsyncMock()

        handler = AuthenticateUserHandler(
            user_repo=mock_user_repo,
            password_service=mock_password_service,
            event_bus=mock_event_bus,
        )

        command = AuthenticateUser(
            email="test@example.com",
            password="WrongPassword123!",
        )

        # Act
        result = await handler.handle(command)

        # Assert
        assert isinstance(result, Failure)
        assert result.error == AuthenticationError.INVALID_CREDENTIALS

    @pytest.mark.asyncio
    async def test_authentication_fails_when_email_not_verified(self):
        """Test auth fails with EMAIL_NOT_VERIFIED for unverified accounts."""
        # Arrange
        mock_user = create_mock_user(is_verified=False)

        mock_user_repo = AsyncMock()
        mock_user_repo.find_by_email.return_value = mock_user

        mock_password_service = Mock()
        mock_event_bus = AsyncMock()

        handler = AuthenticateUserHandler(
            user_repo=mock_user_repo,
            password_service=mock_password_service,
            event_bus=mock_event_bus,
        )

        command = AuthenticateUser(
            email="test@example.com",
            password="SecurePass123!",
        )

        # Act
        result = await handler.handle(command)

        # Assert
        assert isinstance(result, Failure)
        assert result.error == AuthenticationError.EMAIL_NOT_VERIFIED

    @pytest.mark.asyncio
    async def test_authentication_fails_when_account_locked(self):
        """Test auth fails with ACCOUNT_LOCKED for locked accounts."""
        # Arrange
        future_time = datetime.now(UTC) + timedelta(hours=1)
        mock_user = create_mock_user(locked_until=future_time)
        mock_user.is_locked.return_value = True

        mock_user_repo = AsyncMock()
        mock_user_repo.find_by_email.return_value = mock_user

        mock_password_service = Mock()
        mock_event_bus = AsyncMock()

        handler = AuthenticateUserHandler(
            user_repo=mock_user_repo,
            password_service=mock_password_service,
            event_bus=mock_event_bus,
        )

        command = AuthenticateUser(
            email="test@example.com",
            password="SecurePass123!",
        )

        # Act
        result = await handler.handle(command)

        # Assert
        assert isinstance(result, Failure)
        assert result.error == AuthenticationError.ACCOUNT_LOCKED

    @pytest.mark.asyncio
    async def test_authentication_fails_when_account_inactive(self):
        """Test auth fails with ACCOUNT_INACTIVE for deactivated accounts."""
        # Arrange
        mock_user = create_mock_user(is_active=False)

        mock_user_repo = AsyncMock()
        mock_user_repo.find_by_email.return_value = mock_user

        mock_password_service = Mock()
        mock_event_bus = AsyncMock()

        handler = AuthenticateUserHandler(
            user_repo=mock_user_repo,
            password_service=mock_password_service,
            event_bus=mock_event_bus,
        )

        command = AuthenticateUser(
            email="test@example.com",
            password="SecurePass123!",
        )

        # Act
        result = await handler.handle(command)

        # Assert
        assert isinstance(result, Failure)
        assert result.error == AuthenticationError.ACCOUNT_INACTIVE

    @pytest.mark.asyncio
    async def test_authentication_increments_failed_counter_on_wrong_password(self):
        """Test failed auth increments failed_login_attempts counter."""
        # Arrange
        mock_user = create_mock_user()

        mock_user_repo = AsyncMock()
        mock_user_repo.find_by_email.return_value = mock_user

        mock_password_service = Mock()
        mock_password_service.verify_password.return_value = False

        mock_event_bus = AsyncMock()

        handler = AuthenticateUserHandler(
            user_repo=mock_user_repo,
            password_service=mock_password_service,
            event_bus=mock_event_bus,
        )

        command = AuthenticateUser(
            email="test@example.com",
            password="WrongPassword123!",
        )

        # Act
        await handler.handle(command)

        # Assert
        mock_user.increment_failed_login.assert_called_once()
        mock_user_repo.update.assert_called_once()


@pytest.mark.unit
class TestAuthenticateUserHandlerEvents:
    """Test domain event publishing during authentication."""

    @pytest.mark.asyncio
    async def test_authentication_publishes_attempted_event(self):
        """Test auth always publishes ATTEMPTED event first."""
        # Arrange
        mock_user = create_mock_user()

        mock_user_repo = AsyncMock()
        mock_user_repo.find_by_email.return_value = mock_user

        mock_password_service = Mock()
        mock_password_service.verify_password.return_value = True

        mock_event_bus = AsyncMock()

        handler = AuthenticateUserHandler(
            user_repo=mock_user_repo,
            password_service=mock_password_service,
            event_bus=mock_event_bus,
        )

        command = AuthenticateUser(
            email="test@example.com",
            password="SecurePass123!",
        )

        # Act
        await handler.handle(command)

        # Assert - First call should be ATTEMPTED event
        first_call = mock_event_bus.publish.call_args_list[0]
        event = first_call[0][0]
        assert isinstance(event, UserLoginAttempted)
        assert event.email == "test@example.com"

    @pytest.mark.asyncio
    async def test_authentication_publishes_succeeded_event_on_success(self):
        """Test successful auth publishes SUCCEEDED event."""
        # Arrange
        mock_user = create_mock_user()

        mock_user_repo = AsyncMock()
        mock_user_repo.find_by_email.return_value = mock_user

        mock_password_service = Mock()
        mock_password_service.verify_password.return_value = True

        mock_event_bus = AsyncMock()

        handler = AuthenticateUserHandler(
            user_repo=mock_user_repo,
            password_service=mock_password_service,
            event_bus=mock_event_bus,
        )

        command = AuthenticateUser(
            email="test@example.com",
            password="SecurePass123!",
        )

        # Act
        await handler.handle(command)

        # Assert - Second call should be SUCCEEDED event
        second_call = mock_event_bus.publish.call_args_list[1]
        event = second_call[0][0]
        assert isinstance(event, UserLoginSucceeded)
        assert event.user_id == mock_user.id

    @pytest.mark.asyncio
    async def test_authentication_publishes_failed_event_on_failure(self):
        """Test failed auth publishes FAILED event."""
        # Arrange
        mock_user_repo = AsyncMock()
        mock_user_repo.find_by_email.return_value = None

        mock_password_service = Mock()
        mock_event_bus = AsyncMock()

        handler = AuthenticateUserHandler(
            user_repo=mock_user_repo,
            password_service=mock_password_service,
            event_bus=mock_event_bus,
        )

        command = AuthenticateUser(
            email="nonexistent@example.com",
            password="SecurePass123!",
        )

        # Act
        await handler.handle(command)

        # Assert - Second call should be FAILED event
        second_call = mock_event_bus.publish.call_args_list[1]
        event = second_call[0][0]
        assert isinstance(event, UserLoginFailed)
        assert event.reason == AuthenticationError.INVALID_CREDENTIALS
