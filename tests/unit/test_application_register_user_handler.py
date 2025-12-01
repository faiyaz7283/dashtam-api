"""Unit tests for RegisterUserHandler.

Tests cover:
- Successful user registration
- Email already exists (duplicate email)
- Event publishing (ATTEMPTED, SUCCEEDED, FAILED)
- Password hashing delegation
- Verification token generation
- Error handling

Architecture:
- Unit tests for application handler (mocked dependencies)
- Mock repository protocols
- Test handler logic, not persistence
- Async tests (handler uses async repositories)
"""

from unittest.mock import AsyncMock, Mock
from uuid import UUID
from uuid_extensions import uuid7

import pytest

from src.application.commands.auth_commands import RegisterUser
from src.application.commands.handlers.register_user_handler import (
    RegisterUserHandler,
    RegistrationError,
)
from src.core.result import Failure, Success
from src.domain.events.auth_events import (
    UserRegistrationAttempted,
    UserRegistrationFailed,
    UserRegistrationSucceeded,
)


@pytest.mark.unit
class TestRegisterUserHandlerSuccess:
    """Test successful user registration scenarios."""

    @pytest.mark.asyncio
    async def test_register_user_success_returns_user_id(self):
        """Test successful registration returns Success with user_id."""
        # Arrange
        mock_user_repo = AsyncMock()
        mock_user_repo.find_by_email.return_value = None  # No existing user
        mock_user_repo.save = AsyncMock()

        mock_verification_repo = AsyncMock()
        mock_verification_repo.save = AsyncMock()

        mock_password_service = Mock()
        mock_password_service.hash_password.return_value = "hashed_password_123"

        mock_event_bus = AsyncMock()

        handler = RegisterUserHandler(
            user_repo=mock_user_repo,
            verification_token_repo=mock_verification_repo,
            password_service=mock_password_service,
            event_bus=mock_event_bus,
        )

        command = RegisterUser(
            email="test@example.com",
            password="SecurePass123!",
        )

        # Act
        result = await handler.handle(command)

        # Assert
        assert isinstance(result, Success)
        assert isinstance(result.value, UUID)

    @pytest.mark.asyncio
    async def test_register_user_hashes_password(self):
        """Test registration delegates password hashing to service."""
        # Arrange
        mock_user_repo = AsyncMock()
        mock_user_repo.find_by_email.return_value = None

        mock_verification_repo = AsyncMock()
        mock_password_service = Mock()
        mock_password_service.hash_password.return_value = "hashed_value"
        mock_event_bus = AsyncMock()

        handler = RegisterUserHandler(
            user_repo=mock_user_repo,
            verification_token_repo=mock_verification_repo,
            password_service=mock_password_service,
            event_bus=mock_event_bus,
        )

        command = RegisterUser(
            email="test@example.com",
            password="MySecretPassword123!",
        )

        # Act
        await handler.handle(command)

        # Assert
        mock_password_service.hash_password.assert_called_once_with(
            "MySecretPassword123!"
        )

    @pytest.mark.asyncio
    async def test_register_user_saves_user_to_repository(self):
        """Test registration saves User entity to repository."""
        # Arrange
        mock_user_repo = AsyncMock()
        mock_user_repo.find_by_email.return_value = None

        mock_verification_repo = AsyncMock()
        mock_password_service = Mock()
        mock_password_service.hash_password.return_value = "hashed"
        mock_event_bus = AsyncMock()

        handler = RegisterUserHandler(
            user_repo=mock_user_repo,
            verification_token_repo=mock_verification_repo,
            password_service=mock_password_service,
            event_bus=mock_event_bus,
        )

        command = RegisterUser(
            email="test@example.com",
            password="SecurePass123!",
        )

        # Act
        await handler.handle(command)

        # Assert
        mock_user_repo.save.assert_called_once()
        saved_user = mock_user_repo.save.call_args[0][0]
        assert saved_user.email == "test@example.com"
        assert saved_user.password_hash == "hashed"
        assert saved_user.is_verified is False

    @pytest.mark.asyncio
    async def test_register_user_creates_verification_token(self):
        """Test registration creates verification token."""
        # Arrange
        mock_user_repo = AsyncMock()
        mock_user_repo.find_by_email.return_value = None

        mock_verification_repo = AsyncMock()
        mock_password_service = Mock()
        mock_password_service.hash_password.return_value = "hashed"
        mock_event_bus = AsyncMock()

        handler = RegisterUserHandler(
            user_repo=mock_user_repo,
            verification_token_repo=mock_verification_repo,
            password_service=mock_password_service,
            event_bus=mock_event_bus,
        )

        command = RegisterUser(
            email="test@example.com",
            password="SecurePass123!",
        )

        # Act
        await handler.handle(command)

        # Assert
        mock_verification_repo.save.assert_called_once()
        call_kwargs = mock_verification_repo.save.call_args[1]
        assert "user_id" in call_kwargs
        assert "token" in call_kwargs
        assert "expires_at" in call_kwargs
        assert isinstance(call_kwargs["user_id"], UUID)
        assert len(call_kwargs["token"]) == 64  # hex token


@pytest.mark.unit
class TestRegisterUserHandlerFailure:
    """Test user registration failure scenarios."""

    @pytest.mark.asyncio
    async def test_register_user_fails_when_email_exists(self):
        """Test registration fails when email already registered."""
        # Arrange
        existing_user = Mock()
        existing_user.id = uuid7()
        existing_user.email = "existing@example.com"

        mock_user_repo = AsyncMock()
        mock_user_repo.find_by_email.return_value = existing_user

        mock_verification_repo = AsyncMock()
        mock_password_service = Mock()
        mock_event_bus = AsyncMock()

        handler = RegisterUserHandler(
            user_repo=mock_user_repo,
            verification_token_repo=mock_verification_repo,
            password_service=mock_password_service,
            event_bus=mock_event_bus,
        )

        command = RegisterUser(
            email="existing@example.com",
            password="SecurePass123!",
        )

        # Act
        result = await handler.handle(command)

        # Assert
        assert isinstance(result, Failure)
        assert RegistrationError.EMAIL_ALREADY_EXISTS in result.error

    @pytest.mark.asyncio
    async def test_register_user_duplicate_email_does_not_save(self):
        """Test duplicate email does not save user or token."""
        # Arrange
        existing_user = Mock()
        existing_user.id = uuid7()

        mock_user_repo = AsyncMock()
        mock_user_repo.find_by_email.return_value = existing_user

        mock_verification_repo = AsyncMock()
        mock_password_service = Mock()
        mock_event_bus = AsyncMock()

        handler = RegisterUserHandler(
            user_repo=mock_user_repo,
            verification_token_repo=mock_verification_repo,
            password_service=mock_password_service,
            event_bus=mock_event_bus,
        )

        command = RegisterUser(
            email="existing@example.com",
            password="SecurePass123!",
        )

        # Act
        await handler.handle(command)

        # Assert
        mock_user_repo.save.assert_not_called()
        mock_verification_repo.save.assert_not_called()


@pytest.mark.unit
class TestRegisterUserHandlerEvents:
    """Test domain event publishing during registration."""

    @pytest.mark.asyncio
    async def test_register_user_publishes_attempted_event(self):
        """Test registration always publishes ATTEMPTED event first."""
        # Arrange
        mock_user_repo = AsyncMock()
        mock_user_repo.find_by_email.return_value = None

        mock_verification_repo = AsyncMock()
        mock_password_service = Mock()
        mock_password_service.hash_password.return_value = "hashed"
        mock_event_bus = AsyncMock()

        handler = RegisterUserHandler(
            user_repo=mock_user_repo,
            verification_token_repo=mock_verification_repo,
            password_service=mock_password_service,
            event_bus=mock_event_bus,
        )

        command = RegisterUser(
            email="test@example.com",
            password="SecurePass123!",
        )

        # Act
        await handler.handle(command)

        # Assert - First call should be ATTEMPTED event
        first_call = mock_event_bus.publish.call_args_list[0]
        event = first_call[0][0]
        assert isinstance(event, UserRegistrationAttempted)
        assert event.email == "test@example.com"

    @pytest.mark.asyncio
    async def test_register_user_publishes_succeeded_event_on_success(self):
        """Test successful registration publishes SUCCEEDED event."""
        # Arrange
        mock_user_repo = AsyncMock()
        mock_user_repo.find_by_email.return_value = None

        mock_verification_repo = AsyncMock()
        mock_password_service = Mock()
        mock_password_service.hash_password.return_value = "hashed"
        mock_event_bus = AsyncMock()

        handler = RegisterUserHandler(
            user_repo=mock_user_repo,
            verification_token_repo=mock_verification_repo,
            password_service=mock_password_service,
            event_bus=mock_event_bus,
        )

        command = RegisterUser(
            email="test@example.com",
            password="SecurePass123!",
        )

        # Act
        await handler.handle(command)

        # Assert - Second call should be SUCCEEDED event
        second_call = mock_event_bus.publish.call_args_list[1]
        event = second_call[0][0]
        assert isinstance(event, UserRegistrationSucceeded)
        assert event.email == "test@example.com"
        assert event.user_id is not None
        assert event.verification_token is not None

    @pytest.mark.asyncio
    async def test_register_user_publishes_failed_event_on_duplicate_email(self):
        """Test duplicate email publishes FAILED event."""
        # Arrange
        existing_user = Mock()
        existing_user.id = uuid7()

        mock_user_repo = AsyncMock()
        mock_user_repo.find_by_email.return_value = existing_user

        mock_verification_repo = AsyncMock()
        mock_password_service = Mock()
        mock_event_bus = AsyncMock()

        handler = RegisterUserHandler(
            user_repo=mock_user_repo,
            verification_token_repo=mock_verification_repo,
            password_service=mock_password_service,
            event_bus=mock_event_bus,
        )

        command = RegisterUser(
            email="existing@example.com",
            password="SecurePass123!",
        )

        # Act
        await handler.handle(command)

        # Assert - Second call should be FAILED event
        second_call = mock_event_bus.publish.call_args_list[1]
        event = second_call[0][0]
        assert isinstance(event, UserRegistrationFailed)
        assert event.email == "existing@example.com"
        assert RegistrationError.EMAIL_ALREADY_EXISTS in event.reason

    @pytest.mark.asyncio
    async def test_register_user_publishes_exactly_two_events_on_success(self):
        """Test successful registration publishes exactly 2 events."""
        # Arrange
        mock_user_repo = AsyncMock()
        mock_user_repo.find_by_email.return_value = None

        mock_verification_repo = AsyncMock()
        mock_password_service = Mock()
        mock_password_service.hash_password.return_value = "hashed"
        mock_event_bus = AsyncMock()

        handler = RegisterUserHandler(
            user_repo=mock_user_repo,
            verification_token_repo=mock_verification_repo,
            password_service=mock_password_service,
            event_bus=mock_event_bus,
        )

        command = RegisterUser(
            email="test@example.com",
            password="SecurePass123!",
        )

        # Act
        await handler.handle(command)

        # Assert
        assert mock_event_bus.publish.call_count == 2
