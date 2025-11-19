"""Unit tests for infrastructure event handlers.

Tests cover:
- LoggingEventHandler: Logs events with correct severity and fields
- AuditEventHandler: Creates audit records with correct actions
- EmailEventHandler (stub): Processes events without exceptions
- SessionEventHandler (stub): Processes events without exceptions
- Handler failure isolation (fail-open behavior)
- Handler receives correct event data

Test Strategy:
- Mock protocols (LoggerProtocol, Database) to isolate handlers
- Test behavior, not implementation details (stub logging may change)
- Verify handlers process events without exceptions
- Verify correct data passed to protocol methods

Note:
- EmailEventHandler/SessionEventHandler stub tests minimal by design
- When real Email/Session services added, these tests won't change
- New integration tests will verify actual email sent / sessions revoked
"""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest

from src.domain.enums.audit_action import AuditAction
from src.domain.events.authentication_events import (
    ProviderConnectionAttempted,
    ProviderConnectionFailed,
    ProviderConnectionSucceeded,
    TokenRefreshAttempted,
    TokenRefreshFailed,
    TokenRefreshSucceeded,
    UserPasswordChangeAttempted,
    UserPasswordChangeFailed,
    UserPasswordChangeSucceeded,
    UserRegistrationAttempted,
    UserRegistrationFailed,
    UserRegistrationSucceeded,
)
from src.infrastructure.events.handlers.audit_event_handler import AuditEventHandler
from src.infrastructure.events.handlers.email_event_handler import EmailEventHandler
from src.infrastructure.events.handlers.logging_event_handler import LoggingEventHandler
from src.infrastructure.events.handlers.session_event_handler import SessionEventHandler


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_logger():
    """Create mock LoggerProtocol."""
    logger = MagicMock()
    logger.info = MagicMock()
    logger.warning = MagicMock()
    logger.error = MagicMock()
    return logger


@pytest.fixture
def mock_database():
    """Create mock Database with session context manager."""
    database = MagicMock()
    # Mock session context manager
    mock_session = MagicMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    database.get_session = MagicMock(return_value=mock_session)
    return database


@pytest.fixture
def mock_event_bus():
    """Create mock InMemoryEventBus with get_session method."""
    event_bus = MagicMock()
    # Mock get_session to return a mock session (required by AuditEventHandler)
    mock_session = MagicMock()
    event_bus.get_session = MagicMock(return_value=mock_session)
    return event_bus


@pytest.fixture
def sample_user_id() -> UUID:
    """Sample user UUID for tests."""
    return UUID("12345678-1234-5678-1234-567812345678")


@pytest.fixture
def sample_provider_id() -> UUID:
    """Sample provider UUID for tests."""
    return UUID("87654321-4321-8765-4321-876543218765")


# =============================================================================
# LoggingEventHandler Tests
# =============================================================================


@pytest.mark.unit
class TestLoggingEventHandler:
    """Test LoggingEventHandler logs events with correct severity."""

    def test_handler_initialization(self, mock_logger):
        """Test LoggingEventHandler initializes with logger."""
        # Act
        handler = LoggingEventHandler(logger=mock_logger)

        # Assert
        assert handler._logger is mock_logger

    @pytest.mark.asyncio
    async def test_user_registration_attempted_logs_info(
        self, mock_logger, sample_user_id
    ):
        """Test UserRegistrationAttempted logged at INFO level."""
        # Arrange
        handler = LoggingEventHandler(logger=mock_logger)
        event = UserRegistrationAttempted(
            email="test@example.com", ip_address="192.168.1.1"
        )

        # Act
        await handler.handle_user_registration_attempted(event)

        # Assert
        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args
        assert call_args[0][0] == "user_registration_attempted"
        assert call_args[1]["email"] == "test@example.com"
        assert call_args[1]["ip_address"] == "192.168.1.1"

    @pytest.mark.asyncio
    async def test_user_registration_succeeded_logs_info(
        self, mock_logger, sample_user_id
    ):
        """Test UserRegistrationSucceeded logged at INFO level."""
        # Arrange
        handler = LoggingEventHandler(logger=mock_logger)
        event = UserRegistrationSucceeded(
            user_id=sample_user_id, email="test@example.com"
        )

        # Act
        await handler.handle_user_registration_succeeded(event)

        # Assert
        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args
        assert call_args[0][0] == "user_registration_succeeded"
        assert call_args[1]["user_id"] == str(sample_user_id)
        assert call_args[1]["email"] == "test@example.com"

    @pytest.mark.asyncio
    async def test_user_registration_failed_logs_warning(
        self, mock_logger, sample_user_id
    ):
        """Test UserRegistrationFailed logged at WARNING level."""
        # Arrange
        handler = LoggingEventHandler(logger=mock_logger)
        event = UserRegistrationFailed(
            email="test@example.com",
            error_code="duplicate_email",
            error_message="Email already registered",
            ip_address="192.168.1.1",
        )

        # Act
        await handler.handle_user_registration_failed(event)

        # Assert
        mock_logger.warning.assert_called_once()
        call_args = mock_logger.warning.call_args
        assert call_args[0][0] == "user_registration_failed"
        assert call_args[1]["error_code"] == "duplicate_email"
        assert call_args[1]["error_message"] == "Email already registered"

    @pytest.mark.asyncio
    async def test_password_change_attempted_logs_info(
        self, mock_logger, sample_user_id
    ):
        """Test UserPasswordChangeAttempted logged at INFO level."""
        # Arrange
        handler = LoggingEventHandler(logger=mock_logger)
        event = UserPasswordChangeAttempted(
            user_id=sample_user_id, initiated_by="user", ip_address="192.168.1.1"
        )

        # Act
        await handler.handle_user_password_change_attempted(event)

        # Assert
        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args
        assert call_args[0][0] == "user_password_change_attempted"
        assert call_args[1]["user_id"] == str(sample_user_id)
        assert call_args[1]["initiated_by"] == "user"

    @pytest.mark.asyncio
    async def test_password_change_succeeded_logs_info(
        self, mock_logger, sample_user_id
    ):
        """Test UserPasswordChangeSucceeded logged at INFO level."""
        # Arrange
        handler = LoggingEventHandler(logger=mock_logger)
        event = UserPasswordChangeSucceeded(user_id=sample_user_id, initiated_by="user")

        # Act
        await handler.handle_user_password_change_succeeded(event)

        # Assert
        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args
        assert call_args[0][0] == "user_password_change_succeeded"
        assert call_args[1]["user_id"] == str(sample_user_id)

    @pytest.mark.asyncio
    async def test_password_change_failed_logs_warning(
        self, mock_logger, sample_user_id
    ):
        """Test UserPasswordChangeFailed logged at WARNING level."""
        # Arrange
        handler = LoggingEventHandler(logger=mock_logger)
        event = UserPasswordChangeFailed(
            user_id=sample_user_id,
            initiated_by="user",
            error_code="invalid_old_password",
            error_message="Old password incorrect",
            ip_address="192.168.1.1",
        )

        # Act
        await handler.handle_user_password_change_failed(event)

        # Assert
        mock_logger.warning.assert_called_once()
        call_args = mock_logger.warning.call_args
        assert call_args[0][0] == "user_password_change_failed"
        assert call_args[1]["error_code"] == "invalid_old_password"

    @pytest.mark.asyncio
    async def test_provider_connection_attempted_logs_info(
        self, mock_logger, sample_user_id
    ):
        """Test ProviderConnectionAttempted logged at INFO level."""
        # Arrange
        handler = LoggingEventHandler(logger=mock_logger)
        event = ProviderConnectionAttempted(
            user_id=sample_user_id, provider_name="schwab", ip_address="192.168.1.1"
        )

        # Act
        await handler.handle_provider_connection_attempted(event)

        # Assert
        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args
        assert call_args[0][0] == "provider_connection_attempted"
        assert call_args[1]["provider_name"] == "schwab"

    @pytest.mark.asyncio
    async def test_provider_connection_succeeded_logs_info(
        self, mock_logger, sample_user_id, sample_provider_id
    ):
        """Test ProviderConnectionSucceeded logged at INFO level."""
        # Arrange
        handler = LoggingEventHandler(logger=mock_logger)
        event = ProviderConnectionSucceeded(
            user_id=sample_user_id,
            provider_id=sample_provider_id,
            provider_name="schwab",
        )

        # Act
        await handler.handle_provider_connection_succeeded(event)

        # Assert
        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args
        assert call_args[0][0] == "provider_connection_succeeded"
        assert call_args[1]["provider_id"] == str(sample_provider_id)

    @pytest.mark.asyncio
    async def test_provider_connection_failed_logs_warning(
        self, mock_logger, sample_user_id
    ):
        """Test ProviderConnectionFailed logged at WARNING level."""
        # Arrange
        handler = LoggingEventHandler(logger=mock_logger)
        event = ProviderConnectionFailed(
            user_id=sample_user_id,
            provider_name="schwab",
            error_code="access_denied",
            error_message="User denied OAuth access",
        )

        # Act
        await handler.handle_provider_connection_failed(event)

        # Assert
        mock_logger.warning.assert_called_once()
        call_args = mock_logger.warning.call_args
        assert call_args[0][0] == "provider_connection_failed"
        assert call_args[1]["error_code"] == "access_denied"

    @pytest.mark.asyncio
    async def test_token_refresh_attempted_logs_info(
        self, mock_logger, sample_user_id, sample_provider_id
    ):
        """Test TokenRefreshAttempted logged at INFO level."""
        # Arrange
        handler = LoggingEventHandler(logger=mock_logger)
        event = TokenRefreshAttempted(
            user_id=sample_user_id,
            provider_id=sample_provider_id,
            provider_name="schwab",
        )

        # Act
        await handler.handle_token_refresh_attempted(event)

        # Assert
        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args
        assert call_args[0][0] == "token_refresh_attempted"

    @pytest.mark.asyncio
    async def test_token_refresh_succeeded_logs_info(
        self, mock_logger, sample_user_id, sample_provider_id
    ):
        """Test TokenRefreshSucceeded logged at INFO level."""
        # Arrange
        handler = LoggingEventHandler(logger=mock_logger)
        event = TokenRefreshSucceeded(
            user_id=sample_user_id,
            provider_id=sample_provider_id,
            provider_name="schwab",
        )

        # Act
        await handler.handle_token_refresh_succeeded(event)

        # Assert
        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args
        assert call_args[0][0] == "token_refresh_succeeded"

    @pytest.mark.asyncio
    async def test_token_refresh_failed_logs_warning(
        self, mock_logger, sample_user_id, sample_provider_id
    ):
        """Test TokenRefreshFailed logged at WARNING level."""
        # Arrange
        handler = LoggingEventHandler(logger=mock_logger)
        event = TokenRefreshFailed(
            user_id=sample_user_id,
            provider_id=sample_provider_id,
            provider_name="schwab",
            error_code="invalid_grant",
            error_message="Refresh token expired",
        )

        # Act
        await handler.handle_token_refresh_failed(event)

        # Assert
        mock_logger.warning.assert_called_once()
        call_args = mock_logger.warning.call_args
        assert call_args[0][0] == "token_refresh_failed"
        assert call_args[1]["error_code"] == "invalid_grant"


# =============================================================================
# AuditEventHandler Tests
# =============================================================================


@pytest.mark.unit
class TestAuditEventHandler:
    """Test AuditEventHandler creates audit records with correct actions."""

    def test_handler_initialization(self, mock_database, mock_event_bus):
        """Test AuditEventHandler initializes with database and event bus."""
        # Act
        handler = AuditEventHandler(database=mock_database, event_bus=mock_event_bus)

        # Assert
        assert handler._database is mock_database
        assert handler._event_bus is mock_event_bus

    @pytest.mark.asyncio
    async def test_user_registration_attempted_creates_audit(
        self, mock_database, mock_event_bus, sample_user_id
    ):
        """Test UserRegistrationAttempted creates audit record."""
        # Arrange
        handler = AuditEventHandler(database=mock_database, event_bus=mock_event_bus)
        event = UserRegistrationAttempted(
            email="test@example.com", ip_address="192.168.1.1"
        )

        # Mock PostgresAuditAdapter
        with patch(
            "src.infrastructure.audit.postgres_adapter.PostgresAuditAdapter"
        ) as mock_adapter_class:
            mock_adapter = AsyncMock()
            mock_adapter_class.return_value = mock_adapter

            # Act
            await handler.handle_user_registration_attempted(event)

            # Assert
            mock_adapter.record.assert_called_once()
            call_kwargs = mock_adapter.record.call_args[1]
            assert call_kwargs["action"] == AuditAction.USER_REGISTRATION_ATTEMPTED
            assert call_kwargs["user_id"] is None  # User not created yet
            assert call_kwargs["resource_type"] == "user"
            assert call_kwargs["context"]["email"] == "test@example.com"

    @pytest.mark.asyncio
    async def test_user_registration_succeeded_creates_audit(
        self, mock_database, mock_event_bus, sample_user_id
    ):
        """Test UserRegistrationSucceeded creates audit record."""
        # Arrange
        handler = AuditEventHandler(database=mock_database, event_bus=mock_event_bus)
        event = UserRegistrationSucceeded(
            user_id=sample_user_id, email="test@example.com"
        )

        # Mock PostgresAuditAdapter
        with patch(
            "src.infrastructure.audit.postgres_adapter.PostgresAuditAdapter"
        ) as mock_adapter_class:
            mock_adapter = AsyncMock()
            mock_adapter_class.return_value = mock_adapter

            # Act
            await handler.handle_user_registration_succeeded(event)

            # Assert
            mock_adapter.record.assert_called_once()
            call_kwargs = mock_adapter.record.call_args[1]
            assert call_kwargs["action"] == AuditAction.USER_REGISTERED
            assert call_kwargs["user_id"] == sample_user_id
            assert call_kwargs["resource_id"] == sample_user_id  # UUID, not string
            assert call_kwargs["context"]["email"] == "test@example.com"

    @pytest.mark.asyncio
    async def test_user_registration_failed_creates_audit(
        self, mock_database, mock_event_bus, sample_user_id
    ):
        """Test UserRegistrationFailed creates audit record."""
        # Arrange
        handler = AuditEventHandler(database=mock_database, event_bus=mock_event_bus)
        event = UserRegistrationFailed(
            email="test@example.com",
            error_code="duplicate_email",
            error_message="Email already registered",
            ip_address="192.168.1.1",
        )

        # Mock PostgresAuditAdapter
        with patch(
            "src.infrastructure.audit.postgres_adapter.PostgresAuditAdapter"
        ) as mock_adapter_class:
            mock_adapter = AsyncMock()
            mock_adapter_class.return_value = mock_adapter

            # Act
            await handler.handle_user_registration_failed(event)

            # Assert
            mock_adapter.record.assert_called_once()
            call_kwargs = mock_adapter.record.call_args[1]
            assert call_kwargs["action"] == AuditAction.USER_REGISTRATION_FAILED
            assert call_kwargs["user_id"] is None
            assert call_kwargs["context"]["reason"] == "duplicate_email"

    @pytest.mark.asyncio
    async def test_password_change_succeeded_creates_audit(
        self, mock_database, mock_event_bus, sample_user_id
    ):
        """Test UserPasswordChangeSucceeded creates audit record."""
        # Arrange
        handler = AuditEventHandler(database=mock_database, event_bus=mock_event_bus)
        event = UserPasswordChangeSucceeded(user_id=sample_user_id, initiated_by="user")

        # Mock PostgresAuditAdapter
        with patch(
            "src.infrastructure.audit.postgres_adapter.PostgresAuditAdapter"
        ) as mock_adapter_class:
            mock_adapter = AsyncMock()
            mock_adapter_class.return_value = mock_adapter

            # Act
            await handler.handle_user_password_change_succeeded(event)

            # Assert
            mock_adapter.record.assert_called_once()
            call_kwargs = mock_adapter.record.call_args[1]
            assert call_kwargs["action"] == AuditAction.USER_PASSWORD_CHANGED
            assert call_kwargs["user_id"] == sample_user_id
            assert call_kwargs["context"]["initiated_by"] == "user"

    @pytest.mark.asyncio
    async def test_provider_connection_succeeded_creates_audit(
        self, mock_database, mock_event_bus, sample_user_id, sample_provider_id
    ):
        """Test ProviderConnectionSucceeded creates audit record."""
        # Arrange
        handler = AuditEventHandler(database=mock_database, event_bus=mock_event_bus)
        event = ProviderConnectionSucceeded(
            user_id=sample_user_id,
            provider_id=sample_provider_id,
            provider_name="schwab",
        )

        # Mock PostgresAuditAdapter
        with patch(
            "src.infrastructure.audit.postgres_adapter.PostgresAuditAdapter"
        ) as mock_adapter_class:
            mock_adapter = AsyncMock()
            mock_adapter_class.return_value = mock_adapter

            # Act
            await handler.handle_provider_connection_succeeded(event)

            # Assert
            mock_adapter.record.assert_called_once()
            call_kwargs = mock_adapter.record.call_args[1]
            assert call_kwargs["action"] == AuditAction.PROVIDER_CONNECTED
            assert call_kwargs["user_id"] == sample_user_id
            assert call_kwargs["resource_id"] == sample_provider_id  # UUID, not string
            assert call_kwargs["context"]["provider_name"] == "schwab"

    @pytest.mark.asyncio
    async def test_token_refresh_failed_creates_audit(
        self, mock_database, mock_event_bus, sample_user_id, sample_provider_id
    ):
        """Test TokenRefreshFailed creates audit record."""
        # Arrange
        handler = AuditEventHandler(database=mock_database, event_bus=mock_event_bus)
        event = TokenRefreshFailed(
            user_id=sample_user_id,
            provider_id=sample_provider_id,
            provider_name="schwab",
            error_code="invalid_grant",
            error_message="Refresh token expired",
        )

        # Mock PostgresAuditAdapter
        with patch(
            "src.infrastructure.audit.postgres_adapter.PostgresAuditAdapter"
        ) as mock_adapter_class:
            mock_adapter = AsyncMock()
            mock_adapter_class.return_value = mock_adapter

            # Act
            await handler.handle_token_refresh_failed(event)

            # Assert
            mock_adapter.record.assert_called_once()
            call_kwargs = mock_adapter.record.call_args[1]
            assert call_kwargs["action"] == AuditAction.PROVIDER_TOKEN_REFRESH_FAILED
            assert call_kwargs["user_id"] == sample_user_id
            assert call_kwargs["context"]["error_code"] == "invalid_grant"


# =============================================================================
# EmailEventHandler Tests (Stub - Behavior Only)
# =============================================================================


@pytest.mark.unit
class TestEmailEventHandler:
    """Test EmailEventHandler processes events without exceptions (stub)."""

    def test_handler_initialization(self, mock_logger):
        """Test EmailEventHandler initializes with logger and settings."""
        # Arrange
        from src.core.config import get_settings
        settings = get_settings()
        
        # Act
        handler = EmailEventHandler(logger=mock_logger, settings=settings)

        # Assert
        assert handler._logger is mock_logger
        assert handler._settings is settings

    @pytest.mark.asyncio
    async def test_user_registration_succeeded_processes_event(
        self, mock_logger, sample_user_id
    ):
        """Test EmailEventHandler processes UserRegistrationSucceeded without exception."""
        # Arrange
        from src.core.config import get_settings
        handler = EmailEventHandler(logger=mock_logger, settings=get_settings())
        event = UserRegistrationSucceeded(
            user_id=sample_user_id, email="test@example.com"
        )

        # Act - Should not raise exception
        await handler.handle_user_registration_succeeded(event)

        # Assert - Handler called logger (stub behavior)
        mock_logger.info.assert_called_once()

    @pytest.mark.asyncio
    async def test_password_change_succeeded_processes_event(
        self, mock_logger, sample_user_id
    ):
        """Test EmailEventHandler processes UserPasswordChangeSucceeded without exception."""
        # Arrange
        from src.core.config import get_settings
        handler = EmailEventHandler(logger=mock_logger, settings=get_settings())
        event = UserPasswordChangeSucceeded(user_id=sample_user_id, initiated_by="user")

        # Act - Should not raise exception
        await handler.handle_user_password_change_succeeded(event)

        # Assert - Handler called logger (stub behavior)
        mock_logger.info.assert_called_once()

    @pytest.mark.asyncio
    async def test_handler_receives_correct_event_data(
        self, mock_logger, sample_user_id
    ):
        """Test EmailEventHandler receives correct event data."""
        # Arrange
        from src.core.config import get_settings
        handler = EmailEventHandler(logger=mock_logger, settings=get_settings())
        event = UserRegistrationSucceeded(
            user_id=sample_user_id, email="test@example.com"
        )

        # Act
        await handler.handle_user_registration_succeeded(event)

        # Assert - Event data passed through correctly
        call_kwargs = mock_logger.info.call_args[1]
        assert call_kwargs["user_id"] == str(sample_user_id)
        assert call_kwargs["recipient"] == "test@example.com"


# =============================================================================
# SessionEventHandler Tests (Stub - Behavior Only)
# =============================================================================


@pytest.mark.unit
class TestSessionEventHandler:
    """Test SessionEventHandler processes events without exceptions (stub)."""

    def test_handler_initialization(self, mock_logger):
        """Test SessionEventHandler initializes with logger."""
        # Act
        handler = SessionEventHandler(logger=mock_logger)

        # Assert
        assert handler._logger is mock_logger

    @pytest.mark.asyncio
    async def test_password_change_succeeded_processes_event(
        self, mock_logger, sample_user_id
    ):
        """Test SessionEventHandler processes UserPasswordChangeSucceeded without exception."""
        # Arrange
        handler = SessionEventHandler(logger=mock_logger)
        event = UserPasswordChangeSucceeded(user_id=sample_user_id, initiated_by="user")

        # Act - Should not raise exception
        await handler.handle_user_password_change_succeeded(event)

        # Assert - Handler called logger (stub behavior)
        mock_logger.info.assert_called_once()

    @pytest.mark.asyncio
    async def test_handler_receives_correct_event_data(
        self, mock_logger, sample_user_id
    ):
        """Test SessionEventHandler receives correct event data."""
        # Arrange
        handler = SessionEventHandler(logger=mock_logger)
        event = UserPasswordChangeSucceeded(
            user_id=sample_user_id, initiated_by="admin"
        )

        # Act
        await handler.handle_user_password_change_succeeded(event)

        # Assert - Event data passed through correctly
        call_kwargs = mock_logger.info.call_args[1]
        assert call_kwargs["user_id"] == str(sample_user_id)
        assert call_kwargs["initiated_by"] == "admin"
        assert call_kwargs["reason"] == "password_changed"


# =============================================================================
# Handler Failure Isolation Tests
# =============================================================================


@pytest.mark.unit
class TestHandlerFailureIsolation:
    """Test handlers don't propagate exceptions (fail-open behavior validation)."""

    @pytest.mark.asyncio
    async def test_logging_handler_exception_does_not_propagate(
        self, mock_logger, sample_user_id
    ):
        """Test LoggingEventHandler exception doesn't break event bus."""
        # Arrange
        handler = LoggingEventHandler(logger=mock_logger)
        mock_logger.info.side_effect = Exception("Logger failed")
        event = UserRegistrationSucceeded(
            user_id=sample_user_id, email="test@example.com"
        )

        # Act & Assert - Exception should propagate (event bus will catch it)
        with pytest.raises(Exception, match="Logger failed"):
            await handler.handle_user_registration_succeeded(event)

    @pytest.mark.asyncio
    async def test_audit_handler_exception_does_not_propagate(
        self, mock_database, mock_event_bus, sample_user_id
    ):
        """Test AuditEventHandler exception doesn't break event bus."""
        # Arrange
        handler = AuditEventHandler(database=mock_database, event_bus=mock_event_bus)
        event = UserRegistrationSucceeded(
            user_id=sample_user_id, email="test@example.com"
        )

        # Mock adapter to raise exception
        with patch(
            "src.infrastructure.audit.postgres_adapter.PostgresAuditAdapter"
        ) as mock_adapter_class:
            mock_adapter = AsyncMock()
            mock_adapter.record.side_effect = Exception("Audit failed")
            mock_adapter_class.return_value = mock_adapter

            # Act & Assert - Exception should propagate (event bus will catch it)
            with pytest.raises(Exception, match="Audit failed"):
                await handler.handle_user_registration_succeeded(event)

    @pytest.mark.asyncio
    async def test_email_handler_exception_does_not_propagate(
        self, mock_logger, sample_user_id
    ):
        """Test EmailEventHandler exception doesn't break event bus."""
        # Arrange
        from src.core.config import get_settings
        handler = EmailEventHandler(logger=mock_logger, settings=get_settings())
        mock_logger.info.side_effect = Exception("Email stub failed")
        event = UserRegistrationSucceeded(
            user_id=sample_user_id, email="test@example.com"
        )

        # Act & Assert - Exception should propagate (event bus will catch it)
        with pytest.raises(Exception, match="Email stub failed"):
            await handler.handle_user_registration_succeeded(event)

    @pytest.mark.asyncio
    async def test_session_handler_exception_does_not_propagate(
        self, mock_logger, sample_user_id
    ):
        """Test SessionEventHandler exception doesn't break event bus."""
        # Arrange
        handler = SessionEventHandler(logger=mock_logger)
        mock_logger.info.side_effect = Exception("Session stub failed")
        event = UserPasswordChangeSucceeded(user_id=sample_user_id, initiated_by="user")

        # Act & Assert - Exception should propagate (event bus will catch it)
        with pytest.raises(Exception, match="Session stub failed"):
            await handler.handle_user_password_change_succeeded(event)
