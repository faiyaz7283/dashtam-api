"""Unit tests for F7.7 Phase 4 critical new event handlers.

This module tests key new handler methods added in F7.7 Phase 4:
- LoggingEventHandler: 16 methods (token, rate limit, data sync)
- AuditEventHandler: 16 methods (same categories)

Session operational events are covered by integration tests due to complex
handler method naming (_operational suffix) and will be added separately.

Test Strategy:
- Mock protocols (LoggerProtocol, Database) to isolate handlers
- Test behavior, not implementation details
- Verify handlers process events without exceptions
- Verify correct data passed to protocol methods

Reference:
    - F7.7: Domain Events Compliance Audit
    - tests/unit/test_infrastructure_event_handlers.py (existing pattern)
"""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest

from src.domain.enums.audit_action import AuditAction
from src.domain.events.auth_events import TokenRejectedDueToRotation
from src.domain.events.data_events import (
    AccountSyncAttempted,
    AccountSyncFailed,
    AccountSyncSucceeded,
    FileImportAttempted,
    FileImportFailed,
    FileImportSucceeded,
    HoldingsSyncAttempted,
    HoldingsSyncFailed,
    HoldingsSyncSucceeded,
    TransactionSyncAttempted,
    TransactionSyncFailed,
    TransactionSyncSucceeded,
)
from src.domain.events.rate_limit_events import (
    RateLimitCheckAllowed,
    RateLimitCheckAttempted,
    RateLimitCheckDenied,
)
from src.infrastructure.events.handlers.audit_event_handler import AuditEventHandler
from src.infrastructure.events.handlers.logging_event_handler import LoggingEventHandler


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_logger():
    """Create mock LoggerProtocol."""
    logger = MagicMock()
    logger.info = MagicMock()
    logger.warning = MagicMock()
    return logger


@pytest.fixture
def mock_database():
    """Create mock Database with session context manager."""
    database = MagicMock()
    mock_session = MagicMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    database.get_session = MagicMock(return_value=mock_session)
    return database


@pytest.fixture
def mock_event_bus():
    """Create mock InMemoryEventBus with get_session method."""
    event_bus = MagicMock()
    mock_session = MagicMock()
    event_bus.get_session = MagicMock(return_value=mock_session)
    return event_bus


@pytest.fixture
def sample_user_id() -> UUID:
    """Sample user UUID for tests."""
    return UUID("12345678-1234-5678-1234-567812345678")


@pytest.fixture
def sample_connection_id() -> UUID:
    """Sample connection UUID for tests."""
    return UUID("11111111-1111-1111-1111-111111111111")


@pytest.fixture
def sample_account_id() -> UUID:
    """Sample account UUID for tests."""
    return UUID("22222222-2222-2222-2222-222222222222")


# =============================================================================
# LoggingEventHandler Tests - Token Rejected
# =============================================================================


@pytest.mark.unit
class TestLoggingEventHandlerTokenRejected:
    """Test LoggingEventHandler handles token rejected events."""

    @pytest.mark.asyncio
    async def test_token_rejected_logs_warning(self, mock_logger, sample_user_id):
        """Test TokenRejectedDueToRotation logged at WARNING level."""
        # Arrange
        handler = LoggingEventHandler(logger=mock_logger)
        event = TokenRejectedDueToRotation(
            user_id=sample_user_id,
            token_version=5,
            required_version=10,
            rejection_reason="global_rotation",
        )

        # Act
        await handler.handle_token_rejected_due_to_rotation(event)

        # Assert
        mock_logger.warning.assert_called_once()
        call_args = mock_logger.warning.call_args
        assert call_args[0][0] == "token_rejected_due_to_rotation"


# =============================================================================
# LoggingEventHandler Tests - Rate Limit
# =============================================================================


@pytest.mark.unit
class TestLoggingEventHandlerRateLimit:
    """Test LoggingEventHandler handles rate limit events."""

    @pytest.mark.asyncio
    async def test_rate_limit_attempted_logs_info(self, mock_logger):
        """Test RateLimitCheckAttempted logged at INFO level."""
        # Arrange
        handler = LoggingEventHandler(logger=mock_logger)
        event = RateLimitCheckAttempted(
            endpoint="/api/v1/users",
            identifier="127.0.0.1",
            scope="ip",
            cost=1,
        )

        # Act
        await handler.handle_rate_limit_check_attempted(event)

        # Assert
        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args
        assert call_args[0][0] == "rate_limit_check_attempted"

    @pytest.mark.asyncio
    async def test_rate_limit_allowed_logs_info(self, mock_logger):
        """Test RateLimitCheckAllowed logged at INFO level."""
        # Arrange
        handler = LoggingEventHandler(logger=mock_logger)
        event = RateLimitCheckAllowed(
            endpoint="/api/v1/users",
            identifier="127.0.0.1",
            scope="ip",
            remaining_tokens=95,
            execution_time_ms=2.5,
        )

        # Act
        await handler.handle_rate_limit_check_allowed(event)

        # Assert
        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args
        assert call_args[0][0] == "rate_limit_check_allowed"

    @pytest.mark.asyncio
    async def test_rate_limit_denied_logs_warning(self, mock_logger):
        """Test RateLimitCheckDenied logged at WARNING level."""
        # Arrange
        handler = LoggingEventHandler(logger=mock_logger)
        event = RateLimitCheckDenied(
            endpoint="/api/v1/users",
            identifier="127.0.0.1",
            scope="ip",
            retry_after=60.0,
            execution_time_ms=2.5,
        )

        # Act
        await handler.handle_rate_limit_check_denied(event)

        # Assert
        mock_logger.warning.assert_called_once()
        call_args = mock_logger.warning.call_args
        assert call_args[0][0] == "rate_limit_check_denied"


# =============================================================================
# LoggingEventHandler Tests - Data Sync Events
# =============================================================================


@pytest.mark.unit
class TestLoggingEventHandlerDataSync:
    """Test LoggingEventHandler handles data sync events."""

    @pytest.mark.asyncio
    async def test_account_sync_attempted_logs_info(
        self, mock_logger, sample_user_id, sample_connection_id
    ):
        """Test AccountSyncAttempted logged at INFO level."""
        # Arrange
        handler = LoggingEventHandler(logger=mock_logger)
        event = AccountSyncAttempted(
            user_id=sample_user_id,
            connection_id=sample_connection_id,
        )

        # Act
        await handler.handle_account_sync_attempted(event)

        # Assert
        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args
        assert call_args[0][0] == "account_sync_attempted"

    @pytest.mark.asyncio
    async def test_account_sync_succeeded_logs_info(
        self, mock_logger, sample_user_id, sample_connection_id
    ):
        """Test AccountSyncSucceeded logged at INFO level."""
        # Arrange
        handler = LoggingEventHandler(logger=mock_logger)
        event = AccountSyncSucceeded(
            user_id=sample_user_id,
            connection_id=sample_connection_id,
            account_count=5,
        )

        # Act
        await handler.handle_account_sync_succeeded(event)

        # Assert
        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args
        assert call_args[0][0] == "account_sync_succeeded"

    @pytest.mark.asyncio
    async def test_account_sync_failed_logs_warning(
        self, mock_logger, sample_user_id, sample_connection_id
    ):
        """Test AccountSyncFailed logged at WARNING level."""
        # Arrange
        handler = LoggingEventHandler(logger=mock_logger)
        event = AccountSyncFailed(
            user_id=sample_user_id,
            connection_id=sample_connection_id,
            reason="api_error",
        )

        # Act
        await handler.handle_account_sync_failed(event)

        # Assert
        mock_logger.warning.assert_called_once()
        call_args = mock_logger.warning.call_args
        assert call_args[0][0] == "account_sync_failed"

    @pytest.mark.asyncio
    async def test_transaction_sync_attempted_logs_info(
        self, mock_logger, sample_user_id, sample_connection_id, sample_account_id
    ):
        """Test TransactionSyncAttempted logged at INFO level."""
        # Arrange
        handler = LoggingEventHandler(logger=mock_logger)
        event = TransactionSyncAttempted(
            user_id=sample_user_id,
            connection_id=sample_connection_id,
            account_id=sample_account_id,
        )

        # Act
        await handler.handle_transaction_sync_attempted(event)

        # Assert
        mock_logger.info.assert_called_once()

    @pytest.mark.asyncio
    async def test_transaction_sync_succeeded_logs_info(
        self, mock_logger, sample_user_id, sample_connection_id, sample_account_id
    ):
        """Test TransactionSyncSucceeded logged at INFO level."""
        # Arrange
        handler = LoggingEventHandler(logger=mock_logger)
        event = TransactionSyncSucceeded(
            user_id=sample_user_id,
            connection_id=sample_connection_id,
            account_id=sample_account_id,
            transaction_count=42,
        )

        # Act
        await handler.handle_transaction_sync_succeeded(event)

        # Assert
        mock_logger.info.assert_called_once()

    @pytest.mark.asyncio
    async def test_transaction_sync_failed_logs_warning(
        self, mock_logger, sample_user_id, sample_connection_id, sample_account_id
    ):
        """Test TransactionSyncFailed logged at WARNING level."""
        # Arrange
        handler = LoggingEventHandler(logger=mock_logger)
        event = TransactionSyncFailed(
            user_id=sample_user_id,
            connection_id=sample_connection_id,
            account_id=sample_account_id,
            reason="rate_limited",
        )

        # Act
        await handler.handle_transaction_sync_failed(event)

        # Assert
        mock_logger.warning.assert_called_once()

    @pytest.mark.asyncio
    async def test_holdings_sync_attempted_logs_info(
        self, mock_logger, sample_user_id, sample_account_id
    ):
        """Test HoldingsSyncAttempted logged at INFO level."""
        # Arrange
        handler = LoggingEventHandler(logger=mock_logger)
        event = HoldingsSyncAttempted(
            user_id=sample_user_id,
            account_id=sample_account_id,
        )

        # Act
        await handler.handle_holdings_sync_attempted(event)

        # Assert
        mock_logger.info.assert_called_once()

    @pytest.mark.asyncio
    async def test_holdings_sync_succeeded_logs_info(
        self, mock_logger, sample_user_id, sample_account_id
    ):
        """Test HoldingsSyncSucceeded logged at INFO level."""
        # Arrange
        handler = LoggingEventHandler(logger=mock_logger)
        event = HoldingsSyncSucceeded(
            user_id=sample_user_id,
            account_id=sample_account_id,
            holding_count=15,
        )

        # Act
        await handler.handle_holdings_sync_succeeded(event)

        # Assert
        mock_logger.info.assert_called_once()

    @pytest.mark.asyncio
    async def test_holdings_sync_failed_logs_warning(
        self, mock_logger, sample_user_id, sample_account_id
    ):
        """Test HoldingsSyncFailed logged at WARNING level."""
        # Arrange
        handler = LoggingEventHandler(logger=mock_logger)
        event = HoldingsSyncFailed(
            user_id=sample_user_id,
            account_id=sample_account_id,
            reason="unauthorized",
        )

        # Act
        await handler.handle_holdings_sync_failed(event)

        # Assert
        mock_logger.warning.assert_called_once()

    @pytest.mark.asyncio
    async def test_file_import_attempted_logs_info(self, mock_logger, sample_user_id):
        """Test FileImportAttempted logged at INFO level."""
        # Arrange
        handler = LoggingEventHandler(logger=mock_logger)
        event = FileImportAttempted(
            user_id=sample_user_id,
            provider_slug="chase",
            file_name="transactions.qfx",
            file_format="qfx",
        )

        # Act
        await handler.handle_file_import_attempted(event)

        # Assert
        mock_logger.info.assert_called_once()

    @pytest.mark.asyncio
    async def test_file_import_succeeded_logs_info(self, mock_logger, sample_user_id):
        """Test FileImportSucceeded logged at INFO level."""
        # Arrange
        handler = LoggingEventHandler(logger=mock_logger)
        event = FileImportSucceeded(
            user_id=sample_user_id,
            provider_slug="chase",
            file_name="transactions.qfx",
            file_format="qfx",
            account_count=2,
            transaction_count=100,
        )

        # Act
        await handler.handle_file_import_succeeded(event)

        # Assert
        mock_logger.info.assert_called_once()

    @pytest.mark.asyncio
    async def test_file_import_failed_logs_warning(self, mock_logger, sample_user_id):
        """Test FileImportFailed logged at WARNING level."""
        # Arrange
        handler = LoggingEventHandler(logger=mock_logger)
        event = FileImportFailed(
            user_id=sample_user_id,
            provider_slug="chase",
            file_name="transactions.qfx",
            file_format="qfx",
            reason="invalid_format",
        )

        # Act
        await handler.handle_file_import_failed(event)

        # Assert
        mock_logger.warning.assert_called_once()


# =============================================================================
# AuditEventHandler Tests - Token Rejected
# =============================================================================


@pytest.mark.unit
class TestAuditEventHandlerTokenRejected:
    """Test AuditEventHandler handles token rejected events."""

    @pytest.mark.asyncio
    async def test_token_rejected_creates_audit_record(
        self, mock_database, mock_event_bus, sample_user_id
    ):
        """Test TokenRejectedDueToRotation creates audit record."""
        # Arrange
        handler = AuditEventHandler(database=mock_database, event_bus=mock_event_bus)
        event = TokenRejectedDueToRotation(
            user_id=sample_user_id,
            token_version=5,
            required_version=10,
            rejection_reason="global_rotation",
        )

        # Mock _create_audit_record
        with patch.object(handler, "_create_audit_record", new=AsyncMock()) as mock:
            # Act
            await handler.handle_token_rejected_due_to_rotation(event)

            # Assert
            mock.assert_called_once()
            call_kwargs = mock.call_args.kwargs
            assert call_kwargs["action"] == AuditAction.TOKEN_REJECTED_VERSION_MISMATCH


# =============================================================================
# AuditEventHandler Tests - Rate Limit
# =============================================================================


@pytest.mark.unit
class TestAuditEventHandlerRateLimit:
    """Test AuditEventHandler handles rate limit events."""

    @pytest.mark.asyncio
    async def test_rate_limit_attempted_creates_audit_record(
        self, mock_database, mock_event_bus
    ):
        """Test RateLimitCheckAttempted creates audit record."""
        # Arrange
        handler = AuditEventHandler(database=mock_database, event_bus=mock_event_bus)
        event = RateLimitCheckAttempted(
            endpoint="/api/v1/users",
            identifier="127.0.0.1",
            scope="ip",
            cost=1,
        )

        # Mock _create_audit_record
        with patch.object(handler, "_create_audit_record", new=AsyncMock()) as mock:
            # Act
            await handler.handle_rate_limit_check_attempted(event)

            # Assert
            mock.assert_called_once()
            call_kwargs = mock.call_args.kwargs
            assert call_kwargs["action"] == AuditAction.RATE_LIMIT_CHECK_ATTEMPTED

    @pytest.mark.asyncio
    async def test_rate_limit_allowed_creates_audit_record(
        self, mock_database, mock_event_bus
    ):
        """Test RateLimitCheckAllowed creates audit record."""
        # Arrange
        handler = AuditEventHandler(database=mock_database, event_bus=mock_event_bus)
        event = RateLimitCheckAllowed(
            endpoint="/api/v1/users",
            identifier="127.0.0.1",
            scope="ip",
            remaining_tokens=95,
            execution_time_ms=2.5,
        )

        # Mock _create_audit_record
        with patch.object(handler, "_create_audit_record", new=AsyncMock()) as mock:
            # Act
            await handler.handle_rate_limit_check_allowed(event)

            # Assert
            mock.assert_called_once()
            call_kwargs = mock.call_args.kwargs
            assert call_kwargs["action"] == AuditAction.RATE_LIMIT_CHECK_ALLOWED

    @pytest.mark.asyncio
    async def test_rate_limit_denied_creates_audit_record(
        self, mock_database, mock_event_bus
    ):
        """Test RateLimitCheckDenied creates audit record."""
        # Arrange
        handler = AuditEventHandler(database=mock_database, event_bus=mock_event_bus)
        event = RateLimitCheckDenied(
            endpoint="/api/v1/users",
            identifier="127.0.0.1",
            scope="ip",
            retry_after=60.0,
            execution_time_ms=2.5,
        )

        # Mock _create_audit_record
        with patch.object(handler, "_create_audit_record", new=AsyncMock()) as mock:
            # Act
            await handler.handle_rate_limit_check_denied(event)

            # Assert
            mock.assert_called_once()
            call_kwargs = mock.call_args.kwargs
            assert call_kwargs["action"] == AuditAction.RATE_LIMIT_CHECK_DENIED


# =============================================================================
# AuditEventHandler Tests - Data Sync Events
# =============================================================================


@pytest.mark.unit
class TestAuditEventHandlerDataSync:
    """Test AuditEventHandler handles data sync events."""

    @pytest.mark.asyncio
    async def test_account_sync_attempted_creates_audit_record(
        self, mock_database, mock_event_bus, sample_user_id, sample_connection_id
    ):
        """Test AccountSyncAttempted creates audit record."""
        # Arrange
        handler = AuditEventHandler(database=mock_database, event_bus=mock_event_bus)
        event = AccountSyncAttempted(
            user_id=sample_user_id,
            connection_id=sample_connection_id,
        )

        # Mock _create_audit_record
        with patch.object(handler, "_create_audit_record", new=AsyncMock()) as mock:
            # Act
            await handler.handle_account_sync_attempted(event)

            # Assert
            mock.assert_called_once()
            call_kwargs = mock.call_args.kwargs
            assert call_kwargs["action"] == AuditAction.ACCOUNT_SYNC_ATTEMPTED

    @pytest.mark.asyncio
    async def test_account_sync_succeeded_creates_audit_record(
        self, mock_database, mock_event_bus, sample_user_id, sample_connection_id
    ):
        """Test AccountSyncSucceeded creates audit record."""
        # Arrange
        handler = AuditEventHandler(database=mock_database, event_bus=mock_event_bus)
        event = AccountSyncSucceeded(
            user_id=sample_user_id,
            connection_id=sample_connection_id,
            account_count=5,
        )

        # Mock _create_audit_record
        with patch.object(handler, "_create_audit_record", new=AsyncMock()) as mock:
            # Act
            await handler.handle_account_sync_succeeded(event)

            # Assert
            mock.assert_called_once()
            call_kwargs = mock.call_args.kwargs
            assert call_kwargs["action"] == AuditAction.ACCOUNT_SYNC_SUCCEEDED

    @pytest.mark.asyncio
    async def test_account_sync_failed_creates_audit_record(
        self, mock_database, mock_event_bus, sample_user_id, sample_connection_id
    ):
        """Test AccountSyncFailed creates audit record."""
        # Arrange
        handler = AuditEventHandler(database=mock_database, event_bus=mock_event_bus)
        event = AccountSyncFailed(
            user_id=sample_user_id,
            connection_id=sample_connection_id,
            reason="api_error",
        )

        # Mock _create_audit_record
        with patch.object(handler, "_create_audit_record", new=AsyncMock()) as mock:
            # Act
            await handler.handle_account_sync_failed(event)

            # Assert
            mock.assert_called_once()
            call_kwargs = mock.call_args.kwargs
            assert call_kwargs["action"] == AuditAction.ACCOUNT_SYNC_FAILED

    @pytest.mark.asyncio
    async def test_transaction_sync_attempted_creates_audit_record(
        self,
        mock_database,
        mock_event_bus,
        sample_user_id,
        sample_connection_id,
        sample_account_id,
    ):
        """Test TransactionSyncAttempted creates audit record."""
        # Arrange
        handler = AuditEventHandler(database=mock_database, event_bus=mock_event_bus)
        event = TransactionSyncAttempted(
            user_id=sample_user_id,
            connection_id=sample_connection_id,
            account_id=sample_account_id,
        )

        # Mock _create_audit_record
        with patch.object(handler, "_create_audit_record", new=AsyncMock()) as mock:
            # Act
            await handler.handle_transaction_sync_attempted(event)

            # Assert
            mock.assert_called_once()
            call_kwargs = mock.call_args.kwargs
            assert call_kwargs["action"] == AuditAction.TRANSACTION_SYNC_ATTEMPTED

    @pytest.mark.asyncio
    async def test_transaction_sync_succeeded_creates_audit_record(
        self,
        mock_database,
        mock_event_bus,
        sample_user_id,
        sample_connection_id,
        sample_account_id,
    ):
        """Test TransactionSyncSucceeded creates audit record."""
        # Arrange
        handler = AuditEventHandler(database=mock_database, event_bus=mock_event_bus)
        event = TransactionSyncSucceeded(
            user_id=sample_user_id,
            connection_id=sample_connection_id,
            account_id=sample_account_id,
            transaction_count=42,
        )

        # Mock _create_audit_record
        with patch.object(handler, "_create_audit_record", new=AsyncMock()) as mock:
            # Act
            await handler.handle_transaction_sync_succeeded(event)

            # Assert
            mock.assert_called_once()
            call_kwargs = mock.call_args.kwargs
            assert call_kwargs["action"] == AuditAction.TRANSACTION_SYNC_SUCCEEDED

    @pytest.mark.asyncio
    async def test_transaction_sync_failed_creates_audit_record(
        self,
        mock_database,
        mock_event_bus,
        sample_user_id,
        sample_connection_id,
        sample_account_id,
    ):
        """Test TransactionSyncFailed creates audit record."""
        # Arrange
        handler = AuditEventHandler(database=mock_database, event_bus=mock_event_bus)
        event = TransactionSyncFailed(
            user_id=sample_user_id,
            connection_id=sample_connection_id,
            account_id=sample_account_id,
            reason="rate_limited",
        )

        # Mock _create_audit_record
        with patch.object(handler, "_create_audit_record", new=AsyncMock()) as mock:
            # Act
            await handler.handle_transaction_sync_failed(event)

            # Assert
            mock.assert_called_once()
            call_kwargs = mock.call_args.kwargs
            assert call_kwargs["action"] == AuditAction.TRANSACTION_SYNC_FAILED

    @pytest.mark.asyncio
    async def test_holdings_sync_attempted_creates_audit_record(
        self, mock_database, mock_event_bus, sample_user_id, sample_account_id
    ):
        """Test HoldingsSyncAttempted creates audit record."""
        # Arrange
        handler = AuditEventHandler(database=mock_database, event_bus=mock_event_bus)
        event = HoldingsSyncAttempted(
            user_id=sample_user_id,
            account_id=sample_account_id,
        )

        # Mock _create_audit_record
        with patch.object(handler, "_create_audit_record", new=AsyncMock()) as mock:
            # Act
            await handler.handle_holdings_sync_attempted(event)

            # Assert
            mock.assert_called_once()
            call_kwargs = mock.call_args.kwargs
            assert call_kwargs["action"] == AuditAction.HOLDINGS_SYNC_ATTEMPTED

    @pytest.mark.asyncio
    async def test_holdings_sync_succeeded_creates_audit_record(
        self, mock_database, mock_event_bus, sample_user_id, sample_account_id
    ):
        """Test HoldingsSyncSucceeded creates audit record."""
        # Arrange
        handler = AuditEventHandler(database=mock_database, event_bus=mock_event_bus)
        event = HoldingsSyncSucceeded(
            user_id=sample_user_id,
            account_id=sample_account_id,
            holding_count=15,
        )

        # Mock _create_audit_record
        with patch.object(handler, "_create_audit_record", new=AsyncMock()) as mock:
            # Act
            await handler.handle_holdings_sync_succeeded(event)

            # Assert
            mock.assert_called_once()
            call_kwargs = mock.call_args.kwargs
            assert call_kwargs["action"] == AuditAction.HOLDINGS_SYNC_SUCCEEDED

    @pytest.mark.asyncio
    async def test_holdings_sync_failed_creates_audit_record(
        self, mock_database, mock_event_bus, sample_user_id, sample_account_id
    ):
        """Test HoldingsSyncFailed creates audit record."""
        # Arrange
        handler = AuditEventHandler(database=mock_database, event_bus=mock_event_bus)
        event = HoldingsSyncFailed(
            user_id=sample_user_id,
            account_id=sample_account_id,
            reason="unauthorized",
        )

        # Mock _create_audit_record
        with patch.object(handler, "_create_audit_record", new=AsyncMock()) as mock:
            # Act
            await handler.handle_holdings_sync_failed(event)

            # Assert
            mock.assert_called_once()
            call_kwargs = mock.call_args.kwargs
            assert call_kwargs["action"] == AuditAction.HOLDINGS_SYNC_FAILED

    @pytest.mark.asyncio
    async def test_file_import_attempted_creates_audit_record(
        self, mock_database, mock_event_bus, sample_user_id
    ):
        """Test FileImportAttempted creates audit record."""
        # Arrange
        handler = AuditEventHandler(database=mock_database, event_bus=mock_event_bus)
        event = FileImportAttempted(
            user_id=sample_user_id,
            provider_slug="chase",
            file_name="transactions.qfx",
            file_format="qfx",
        )

        # Mock _create_audit_record
        with patch.object(handler, "_create_audit_record", new=AsyncMock()) as mock:
            # Act
            await handler.handle_file_import_attempted(event)

            # Assert
            mock.assert_called_once()
            call_kwargs = mock.call_args.kwargs
            assert call_kwargs["action"] == AuditAction.FILE_IMPORT_ATTEMPTED

    @pytest.mark.asyncio
    async def test_file_import_succeeded_creates_audit_record(
        self, mock_database, mock_event_bus, sample_user_id
    ):
        """Test FileImportSucceeded creates audit record."""
        # Arrange
        handler = AuditEventHandler(database=mock_database, event_bus=mock_event_bus)
        event = FileImportSucceeded(
            user_id=sample_user_id,
            provider_slug="chase",
            file_name="transactions.qfx",
            file_format="qfx",
            account_count=2,
            transaction_count=100,
        )

        # Mock _create_audit_record
        with patch.object(handler, "_create_audit_record", new=AsyncMock()) as mock:
            # Act
            await handler.handle_file_import_succeeded(event)

            # Assert
            mock.assert_called_once()
            call_kwargs = mock.call_args.kwargs
            assert call_kwargs["action"] == AuditAction.FILE_IMPORT_SUCCEEDED

    @pytest.mark.asyncio
    async def test_file_import_failed_creates_audit_record(
        self, mock_database, mock_event_bus, sample_user_id
    ):
        """Test FileImportFailed creates audit record."""
        # Arrange
        handler = AuditEventHandler(database=mock_database, event_bus=mock_event_bus)
        event = FileImportFailed(
            user_id=sample_user_id,
            provider_slug="chase",
            file_name="transactions.qfx",
            file_format="qfx",
            reason="invalid_format",
        )

        # Mock _create_audit_record
        with patch.object(handler, "_create_audit_record", new=AsyncMock()) as mock:
            # Act
            await handler.handle_file_import_failed(event)

            # Assert
            mock.assert_called_once()
            call_kwargs = mock.call_args.kwargs
            assert call_kwargs["action"] == AuditAction.FILE_IMPORT_FAILED
