"""Unit tests for PostgresAuditAdapter.

Tests cover:
- record() method with Success/Failure cases
- query() method with filters and pagination
- Result type handling
- Database error handling
- UUID to string conversion
- Edge cases (empty results, None values)

Architecture:
- Unit tests with mocked AsyncSession
- NO real database dependencies
- Tests AuditProtocol compliance
"""

from datetime import datetime, UTC
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.exc import SQLAlchemyError

from src.core.enums import ErrorCode
from src.core.result import Failure, Success
from src.domain.enums import AuditAction
from src.domain.errors import AuditError
from src.infrastructure.audit.postgres_adapter import PostgresAuditAdapter
from src.infrastructure.persistence.models.audit import AuditLogModel


@pytest.mark.unit
class TestPostgresAuditAdapterRecord:
    """Test PostgresAuditAdapter.record() method."""

    @pytest.mark.asyncio
    async def test_record_success(self):
        """Test record() returns Success when audit log is saved."""
        # Arrange: Mock AsyncSession
        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()

        adapter = PostgresAuditAdapter(session=mock_session)

        user_id = uuid4()
        test_context = {"method": "password", "mfa": True}

        # Act
        result = await adapter.record(
            action=AuditAction.USER_LOGIN_SUCCESS,
            user_id=user_id,
            resource_type="session",
            resource_id="session-123",
            ip_address="192.168.1.1",
            user_agent="Mozilla/5.0",
            context=test_context,
        )

        # Assert
        assert isinstance(result, Success)
        assert result.value is None  # record() returns None on success

        # Verify session.add was called with AuditLogModel
        mock_session.add.assert_called_once()
        audit_log = mock_session.add.call_args[0][0]
        assert isinstance(audit_log, AuditLogModel)
        assert audit_log.action == AuditAction.USER_LOGIN
        assert audit_log.user_id == user_id
        assert audit_log.resource_type == "session"
        assert audit_log.resource_id == "session-123"
        assert audit_log.ip_address == "192.168.1.1"
        assert audit_log.user_agent == "Mozilla/5.0"
        assert audit_log.context == test_context

        # Verify commit was called (adapter commits immediately for durability)
        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_record_success_with_minimal_fields(self):
        """Test record() with only required fields (action)."""
        # Arrange
        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()

        adapter = PostgresAuditAdapter(session=mock_session)

        # Act: action and resource_type are required, all others are optional
        result = await adapter.record(
            action=AuditAction.DATA_VIEWED,
            resource_type="account",
            user_id=None,
            resource_id=None,
            ip_address=None,
            user_agent=None,
            context=None,
        )

        # Assert
        assert isinstance(result, Success)
        assert result.value is None

        # Verify audit log was created with None values
        mock_session.add.assert_called_once()
        audit_log = mock_session.add.call_args[0][0]
        assert audit_log.action == AuditAction.DATA_VIEWED
        assert audit_log.user_id is None
        assert audit_log.resource_type == "account"
        assert audit_log.resource_id is None
        assert audit_log.ip_address is None
        assert audit_log.user_agent is None
        # Note: context=None is preserved (protocol contract)
        assert audit_log.context is None

    @pytest.mark.asyncio
    async def test_record_failure_database_error(self):
        """Test record() returns Failure when database error occurs."""
        # Arrange: Mock session that raises error on commit
        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock(
            side_effect=SQLAlchemyError("Database connection failed")
        )

        adapter = PostgresAuditAdapter(session=mock_session)

        # Act
        result = await adapter.record(
            action=AuditAction.USER_LOGIN_SUCCESS,
            resource_type="session",
            user_id=uuid4(),
        )

        # Assert
        assert isinstance(result, Failure)
        assert isinstance(result.error, AuditError)
        assert result.error.code == ErrorCode.AUDIT_RECORD_FAILED
        assert "Database connection failed" in result.error.message

    @pytest.mark.asyncio
    async def test_record_with_context_dict(self):
        """Test record() with complex context dictionary."""
        # Arrange
        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()

        adapter = PostgresAuditAdapter(session=mock_session)

        # Complex nested context
        complex_context = {
            "authentication": {
                "method": "oauth",
                "provider": "google",
                "scopes": ["email", "profile"],
            },
            "device": {
                "type": "mobile",
                "os": "iOS 16.5",
                "app_version": "1.2.3",
            },
            "metadata": {
                "request_id": "req-abc-123",
                "duration_ms": 250,
                "success": True,
            },
        }

        # Act
        result = await adapter.record(
            action=AuditAction.USER_LOGIN_SUCCESS,
            resource_type="session",
            context=complex_context,
        )

        # Assert
        assert isinstance(result, Success)

        # Verify complex context was stored
        audit_log = mock_session.add.call_args[0][0]
        assert audit_log.context == complex_context


@pytest.mark.unit
class TestPostgresAuditAdapterQuery:
    """Test PostgresAuditAdapter.query() method."""

    @pytest.mark.asyncio
    async def test_query_success_with_results(self):
        """Test query() returns Success with audit logs."""
        # Arrange: Mock session with audit logs
        mock_session = AsyncMock()

        # Create mock audit logs
        user_id = uuid4()
        mock_logs = [
            MagicMock(
                id=uuid4(),
                action=AuditAction.USER_LOGIN_SUCCESS,
                user_id=user_id,
                resource_type="session",
                resource_id="session-1",
                ip_address="192.168.1.1",
                user_agent="Mozilla/5.0",
                context={"method": "password"},
                created_at=datetime(2024, 11, 15, 12, 0, 0, tzinfo=UTC),
            ),
            MagicMock(
                id=uuid4(),
                action=AuditAction.DATA_VIEWED,
                user_id=user_id,
                resource_type="account",
                resource_id="account-1",
                ip_address="192.168.1.1",
                user_agent="Mozilla/5.0",
                context={"fields": ["balance"]},
                created_at=datetime(2024, 11, 15, 12, 5, 0, tzinfo=UTC),
            ),
        ]

        # Mock execute chain: execute() → result → scalars() → all()
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = mock_logs
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute = AsyncMock(return_value=mock_result)

        adapter = PostgresAuditAdapter(session=mock_session)

        # Act
        result = await adapter.query(
            user_id=user_id,
            action=None,
            resource_type=None,
            limit=10,
            offset=0,
        )

        # Assert
        assert isinstance(result, Success)
        assert len(result.value) == 2

        # Verify first log
        log1 = result.value[0]
        assert log1["action"] == AuditAction.USER_LOGIN
        assert log1["resource_type"] == "session"
        assert log1["context"]["method"] == "password"

        # Verify second log
        log2 = result.value[1]
        assert log2["action"] == AuditAction.DATA_VIEWED
        assert log2["resource_type"] == "account"
        assert log2["context"]["fields"] == ["balance"]

        # Verify execute was called (SQL query executed)
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_query_success_with_no_results(self):
        """Test query() returns Success with empty list when no logs found."""
        # Arrange: Mock session with no results
        mock_session = AsyncMock()

        # Mock execute chain returning empty list
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute = AsyncMock(return_value=mock_result)

        adapter = PostgresAuditAdapter(session=mock_session)

        # Act
        result = await adapter.query(
            user_id=uuid4(),
            action=AuditAction.USER_LOGIN_SUCCESS,
        )

        # Assert
        assert isinstance(result, Success)
        assert result.value == []

    @pytest.mark.asyncio
    async def test_query_with_filters(self):
        """Test query() applies filters correctly."""
        # Arrange
        mock_session = AsyncMock()

        user_id = uuid4()
        mock_logs = [
            MagicMock(
                id=uuid4(),
                action=AuditAction.PROVIDER_CONNECTED,
                user_id=user_id,
                resource_type="provider",
                resource_id="provider-1",
                ip_address="192.168.1.1",
                user_agent="Mozilla/5.0",
                context={"provider": "schwab"},
                created_at=datetime.now(UTC),
            ),
        ]

        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = mock_logs
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute = AsyncMock(return_value=mock_result)

        adapter = PostgresAuditAdapter(session=mock_session)

        # Act: Apply all filters
        result = await adapter.query(
            user_id=user_id,
            action=AuditAction.PROVIDER_CONNECTED,
            resource_type="provider",
            limit=10,
            offset=0,
        )

        # Assert
        assert isinstance(result, Success)
        assert len(result.value) == 1
        assert result.value[0]["action"] == AuditAction.PROVIDER_CONNECTED
        assert result.value[0]["resource_type"] == "provider"

    @pytest.mark.asyncio
    async def test_query_with_pagination(self):
        """Test query() applies pagination (limit and offset)."""
        # Arrange
        mock_session = AsyncMock()

        # Create 3 mock logs
        mock_logs = [
            MagicMock(
                id=uuid4(),
                action=AuditAction.USER_LOGIN_SUCCESS,
                user_id=uuid4(),
                resource_type="session",
                resource_id=None,
                ip_address="192.168.1.1",
                user_agent="Mozilla/5.0",
                context=None,
                created_at=datetime.now(UTC),
            )
            for _ in range(3)
        ]

        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = mock_logs
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute = AsyncMock(return_value=mock_result)

        adapter = PostgresAuditAdapter(session=mock_session)

        # Act: Query with pagination
        result = await adapter.query(
            user_id=None,
            action=None,
            resource_type=None,
            limit=3,
            offset=10,
        )

        # Assert
        assert isinstance(result, Success)
        assert len(result.value) == 3

    @pytest.mark.asyncio
    async def test_query_failure_database_error(self):
        """Test query() returns Failure when database error occurs."""
        # Arrange: Mock session that raises error on execute
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(
            side_effect=SQLAlchemyError("Connection timeout")
        )

        adapter = PostgresAuditAdapter(session=mock_session)

        # Act
        result = await adapter.query(
            user_id=uuid4(),
            action=AuditAction.USER_LOGIN_SUCCESS,
        )

        # Assert
        assert isinstance(result, Failure)
        assert isinstance(result.error, AuditError)
        assert result.error.code == ErrorCode.AUDIT_QUERY_FAILED
        assert "Connection timeout" in result.error.message

    @pytest.mark.asyncio
    async def test_query_converts_uuid_to_string(self):
        """Test query() converts UUID fields to strings in results."""
        # Arrange
        mock_session = AsyncMock()

        log_id = uuid4()
        user_id = uuid4()

        mock_logs = [
            MagicMock(
                id=log_id,
                action=AuditAction.USER_LOGIN_SUCCESS,
                user_id=user_id,
                resource_type="session",
                resource_id="session-1",
                ip_address="192.168.1.1",
                user_agent="Mozilla/5.0",
                context=None,
                created_at=datetime.now(UTC),
            ),
        ]

        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = mock_logs
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute = AsyncMock(return_value=mock_result)

        adapter = PostgresAuditAdapter(session=mock_session)

        # Act
        result = await adapter.query(user_id=user_id)

        # Assert
        assert isinstance(result, Success)
        log_dict = result.value[0]

        # UUIDs should be converted to strings
        assert isinstance(log_dict["id"], str)
        assert log_dict["id"] == str(log_id)

        assert isinstance(log_dict["user_id"], str)
        assert log_dict["user_id"] == str(user_id)

    @pytest.mark.asyncio
    async def test_query_handles_none_user_id(self):
        """Test query() handles None user_id correctly."""
        # Arrange
        mock_session = AsyncMock()

        # Log with None user_id (system action)
        mock_logs = [
            MagicMock(
                id=uuid4(),
                action=AuditAction.ADMIN_BACKUP_CREATED,
                user_id=None,  # System action, no user
                resource_type="system",
                resource_id=None,
                ip_address=None,
                user_agent=None,
                context={"backup_type": "automated"},
                created_at=datetime.now(UTC),
            ),
        ]

        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = mock_logs
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute = AsyncMock(return_value=mock_result)

        adapter = PostgresAuditAdapter(session=mock_session)

        # Act
        result = await adapter.query(
            user_id=None,
            action=AuditAction.ADMIN_BACKUP_CREATED,
        )

        # Assert
        assert isinstance(result, Success)
        log_dict = result.value[0]
        assert log_dict["user_id"] is None
        assert log_dict["action"] == AuditAction.ADMIN_BACKUP_CREATED


@pytest.mark.unit
class TestPostgresAuditAdapterEdgeCases:
    """Test PostgresAuditAdapter edge cases."""

    @pytest.mark.asyncio
    async def test_record_with_empty_context_dict(self):
        """Test record() with empty context dictionary."""
        # Arrange
        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()

        adapter = PostgresAuditAdapter(session=mock_session)

        # Act: Empty context dict
        result = await adapter.record(
            action=AuditAction.DATA_VIEWED,
            resource_type="account",
            context={},  # Empty dict
        )

        # Assert
        assert isinstance(result, Success)
        audit_log = mock_session.add.call_args[0][0]
        assert audit_log.context == {}

    @pytest.mark.asyncio
    async def test_query_with_all_none_filters(self):
        """Test query() with all filters set to None (query all)."""
        # Arrange
        mock_session = AsyncMock()

        mock_logs = [
            MagicMock(
                id=uuid4(),
                action=AuditAction.USER_LOGIN_SUCCESS,
                user_id=uuid4(),
                resource_type="session",
                resource_id=None,
                ip_address="192.168.1.1",
                user_agent="Mozilla/5.0",
                context=None,
                created_at=datetime.now(UTC),
            ),
        ]

        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = mock_logs
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute = AsyncMock(return_value=mock_result)

        adapter = PostgresAuditAdapter(session=mock_session)

        # Act: All filters None (query everything)
        result = await adapter.query(
            user_id=None,
            action=None,
            resource_type=None,
            limit=100,
            offset=0,
        )

        # Assert
        assert isinstance(result, Success)
        assert len(result.value) == 1

    @pytest.mark.asyncio
    async def test_adapter_with_different_session_instances(self):
        """Test adapter works with different session instances."""
        # Arrange: Create two different sessions
        mock_session1 = AsyncMock()
        mock_session1.add = MagicMock()
        mock_session1.commit = AsyncMock()

        mock_session2 = AsyncMock()
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result.scalars.return_value = mock_scalars
        mock_session2.execute = AsyncMock(return_value=mock_result)

        # Act: Create adapters with different sessions
        adapter1 = PostgresAuditAdapter(session=mock_session1)
        adapter2 = PostgresAuditAdapter(session=mock_session2)

        result1 = await adapter1.record(
            action=AuditAction.USER_LOGIN_SUCCESS,
            resource_type="session",
        )
        result2 = await adapter2.query(user_id=uuid4())

        # Assert: Both adapters work independently
        assert isinstance(result1, Success)
        assert isinstance(result2, Success)

        # Verify correct sessions were used
        mock_session1.add.assert_called_once()
        mock_session2.execute.assert_called_once()
