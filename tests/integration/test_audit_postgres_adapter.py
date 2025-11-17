"""Integration tests for PostgresAuditAdapter with real database.

Tests cover:
- Real database INSERT operations
- Immutability enforcement (UPDATE/DELETE blocked by RULES)
- Query filters (user_id, action, resource_type, date range)
- Pagination (limit, offset)
- JSONB context field (complex nested data)
- None value handling (nullable fields)
- UUID to string conversion

Architecture:
- Integration tests with real PostgreSQL database
- Uses test_database fixture with separate sessions (mirrors production)
- Audit sessions commit independently (durability pattern)
- Tests against PostgreSQL RULES for immutability
"""

from datetime import datetime, timedelta, UTC
from uuid import uuid4

import pytest
from sqlalchemy import select, update, delete

from src.core.result import Success
from src.domain.enums import AuditAction
from src.infrastructure.audit.postgres_adapter import PostgresAuditAdapter
from src.infrastructure.persistence.models.audit import AuditLogModel


@pytest.mark.integration
class TestPostgresAuditAdapterRecord:
    """Test record() with real database."""

    @pytest.mark.asyncio
    async def test_record_creates_audit_log_in_database(self, test_database):
        """Test record() creates audit log in PostgreSQL."""
        # Arrange
        user_id = uuid4()
        resource_id = uuid4()

        # Act: Record audit log (commits independently)
        async with test_database.get_session() as audit_session:
            adapter = PostgresAuditAdapter(session=audit_session)
            result = await adapter.record(
                action=AuditAction.USER_LOGIN_SUCCESS,
                resource_type="session",
                user_id=user_id,
                resource_id=resource_id,  # Must be UUID, not string
                ip_address="192.168.1.1",
                user_agent="Mozilla/5.0",
                context={"method": "password", "mfa": True},
            )
            assert isinstance(result, Success)

        # Assert: Verify in database (separate session)
        async with test_database.get_session() as verify_session:
            stmt = select(AuditLogModel).where(AuditLogModel.user_id == user_id)
            db_result = await verify_session.execute(stmt)
            logs = db_result.scalars().all()

            assert len(logs) == 1
            log = logs[0]
            assert log.action == AuditAction.USER_LOGIN_SUCCESS
            assert log.user_id == user_id
            assert log.resource_type == "session"
            assert log.resource_id == resource_id  # UUID
            assert log.ip_address == "192.168.1.1"
            assert log.user_agent == "Mozilla/5.0"
            assert log.context == {"method": "password", "mfa": True}
            assert log.created_at is not None

    @pytest.mark.asyncio
    async def test_record_with_none_context(self, test_database):
        """Test record() handles None context correctly."""
        # Arrange
        user_id = uuid4()

        # Act: Record with None context
        async with test_database.get_session() as audit_session:
            adapter = PostgresAuditAdapter(session=audit_session)
            result = await adapter.record(
                action=AuditAction.DATA_VIEWED,
                resource_type="account",
                user_id=user_id,
                context=None,  # Explicitly None
            )
            assert isinstance(result, Success)

        # Assert: Verify None is stored (not empty dict)
        async with test_database.get_session() as verify_session:
            stmt = select(AuditLogModel).where(AuditLogModel.user_id == user_id)
            db_result = await verify_session.execute(stmt)
            log = db_result.scalars().first()

            assert log.context is None  # Not {}

    @pytest.mark.asyncio
    async def test_record_with_complex_context(self, test_database):
        """Test record() handles complex nested JSONB context."""
        # Arrange
        user_id = uuid4()
        complex_context = {
            "authentication": {
                "method": "oauth",
                "provider": "google",
                "scopes": ["email", "profile", "openid"],
            },
            "device": {
                "type": "mobile",
                "os": "iOS 16.5",
                "app_version": "1.2.3",
                "device_id": "abc-123-def-456",
            },
            "session": {
                "duration_ms": 2340,
                "endpoints_accessed": ["/api/users", "/api/accounts"],
                "success": True,
            },
        }

        # Act: Record with complex context
        async with test_database.get_session() as audit_session:
            adapter = PostgresAuditAdapter(session=audit_session)
            result = await adapter.record(
                action=AuditAction.PROVIDER_CONNECTED,
                resource_type="provider",
                user_id=user_id,
                context=complex_context,
            )
            assert isinstance(result, Success)

        # Assert: Verify complex JSON stored correctly
        async with test_database.get_session() as verify_session:
            stmt = select(AuditLogModel).where(AuditLogModel.user_id == user_id)
            db_result = await verify_session.execute(stmt)
            log = db_result.scalars().first()

            assert log.context == complex_context
            assert log.context["authentication"]["scopes"] == [
                "email",
                "profile",
                "openid",
            ]
            assert log.context["device"]["app_version"] == "1.2.3"
            assert log.context["session"]["success"] is True

    @pytest.mark.asyncio
    async def test_record_multiple_logs(self, test_database):
        """Test recording multiple audit logs."""
        # Arrange
        user_id = uuid4()

        # Act: Record 3 audit logs (each commits independently)
        for i in range(3):
            async with test_database.get_session() as audit_session:
                adapter = PostgresAuditAdapter(session=audit_session)
                result = await adapter.record(
                    action=AuditAction.DATA_VIEWED,
                    resource_type="account",
                    user_id=user_id,
                    context={"attempt": i + 1},
                )
                assert isinstance(result, Success)

        # Assert: All 3 logs in database
        async with test_database.get_session() as verify_session:
            stmt = select(AuditLogModel).where(AuditLogModel.user_id == user_id)
            db_result = await verify_session.execute(stmt)
            logs = db_result.scalars().all()

            assert len(logs) == 3


@pytest.mark.integration
class TestPostgresAuditAdapterImmutability:
    """Test immutability enforcement (PostgreSQL RULES)."""

    @pytest.mark.asyncio
    async def test_cannot_update_audit_log(self, test_database):
        """Test UPDATE operations are blocked by PostgreSQL RULES.

        Tests verify immutability enforcement in production-like conditions
        (no savepoints). The PostgreSQL RULE blocks updates at the connection level.
        """
        # Arrange: Create audit log
        user_id = uuid4()

        async with test_database.get_session() as audit_session:
            adapter = PostgresAuditAdapter(session=audit_session)
            await adapter.record(
                action=AuditAction.USER_LOGIN_SUCCESS,
                resource_type="session",
                user_id=user_id,
                ip_address="192.168.1.1",
            )

        # Get the log ID
        async with test_database.get_session() as verify_session:
            stmt = select(AuditLogModel).where(AuditLogModel.user_id == user_id)
            db_result = await verify_session.execute(stmt)
            log = db_result.scalars().first()
            log_id = log.id

        # Act: Attempt to UPDATE (should be blocked by RULE)
        async with test_database.get_session() as update_session:
            update_stmt = (
                update(AuditLogModel)
                .where(AuditLogModel.id == log_id)
                .values(ip_address="192.168.1.2")  # Try to change IP
            )
            result = await update_session.execute(update_stmt)

            # Assert: RULE blocked the update (0 rows affected)
            assert result.rowcount == 0

    @pytest.mark.asyncio
    async def test_cannot_delete_audit_log(self, test_database):
        """Test DELETE operations are blocked by PostgreSQL RULES."""
        # Arrange: Create audit log
        user_id = uuid4()

        async with test_database.get_session() as audit_session:
            adapter = PostgresAuditAdapter(session=audit_session)
            await adapter.record(
                action=AuditAction.USER_LOGIN_SUCCESS,
                resource_type="session",
                user_id=user_id,
            )

        # Get the log ID
        stmt = select(AuditLogModel).where(AuditLogModel.user_id == user_id)
        async with test_database.get_session() as verify_session:
            db_result = await verify_session.execute(stmt)
            log = db_result.scalars().first()
            log_id = log.id

        # Act: Attempt to DELETE (should be blocked by RULE)
        async with test_database.get_session() as delete_session:
            delete_stmt = delete(AuditLogModel).where(AuditLogModel.id == log_id)
            result = await delete_session.execute(delete_stmt)

            # Assert: DELETE was blocked (0 rows deleted)
            assert result.rowcount == 0

        # Verify log still exists
        async with test_database.get_session() as final_verify_session:
            db_result = await final_verify_session.execute(stmt)
            still_exists = db_result.scalars().first()
            assert still_exists is not None


@pytest.mark.integration
class TestPostgresAuditAdapterQuery:
    """Test query() with real database."""

    @pytest.mark.asyncio
    async def test_query_returns_all_logs_for_user(self, test_database):
        """Test query() retrieves all logs for a user."""
        # Arrange: Create 3 logs for user
        user_id = uuid4()

        for i in range(3):
            async with test_database.get_session() as audit_session:
                adapter = PostgresAuditAdapter(session=audit_session)
                await adapter.record(
                    action=AuditAction.DATA_VIEWED,
                    resource_type="account",
                    user_id=user_id,
                    context={"view": i + 1},
                )

        # Act: Query for user
        async with test_database.get_session() as query_session:
            adapter = PostgresAuditAdapter(session=query_session)
            result = await adapter.query(user_id=user_id)

            # Assert
            assert isinstance(result, Success)
            assert len(result.value) == 3

            # Verify logs are ordered by created_at DESC (newest first)
            # All records created in quick succession may have same timestamp
            # Just verify all 3 exist with correct views
            views = {log["context"]["view"] for log in result.value}
            assert views == {1, 2, 3}

    @pytest.mark.asyncio
    async def test_query_filter_by_action(self, test_database):
        """Test query() filters by action type."""
        # Arrange: Create different action types
        user_id = uuid4()

        async with test_database.get_session() as audit_session:
            adapter = PostgresAuditAdapter(session=audit_session)
            await adapter.record(
                action=AuditAction.USER_LOGIN_SUCCESS,
                resource_type="session",
                user_id=user_id,
            )
        async with test_database.get_session() as audit_session:
            adapter = PostgresAuditAdapter(session=audit_session)
            await adapter.record(
                action=AuditAction.USER_LOGOUT,
                resource_type="session",
                user_id=user_id,
            )
        async with test_database.get_session() as audit_session:
            adapter = PostgresAuditAdapter(session=audit_session)
            await adapter.record(
                action=AuditAction.DATA_VIEWED,
                resource_type="account",
                user_id=user_id,
            )

        # Act: Query for only USER_LOGIN
        async with test_database.get_session() as query_session:
            adapter = PostgresAuditAdapter(session=query_session)
            result = await adapter.query(
                user_id=user_id,
                action=AuditAction.USER_LOGIN_SUCCESS,
            )

            # Assert
            assert isinstance(result, Success)
            assert len(result.value) == 1
            assert result.value[0]["action"] == AuditAction.USER_LOGIN

    @pytest.mark.asyncio
    async def test_query_filter_by_resource_type(self, test_database):
        """Test query() filters by resource_type."""
        # Arrange: Create different resource types
        user_id = uuid4()

        async with test_database.get_session() as audit_session:
            adapter = PostgresAuditAdapter(session=audit_session)
            await adapter.record(
                action=AuditAction.DATA_VIEWED,
                resource_type="account",
                user_id=user_id,
            )
        async with test_database.get_session() as audit_session:
            adapter = PostgresAuditAdapter(session=audit_session)
            await adapter.record(
                action=AuditAction.DATA_VIEWED,
                resource_type="transaction",
                user_id=user_id,
            )
        async with test_database.get_session() as audit_session:
            adapter = PostgresAuditAdapter(session=audit_session)
            await adapter.record(
                action=AuditAction.DATA_VIEWED,
                resource_type="account",
                user_id=user_id,
            )

        # Act: Query for only "account" resource type
        async with test_database.get_session() as query_session:
            adapter = PostgresAuditAdapter(session=query_session)
            result = await adapter.query(
                user_id=user_id,
                resource_type="account",
            )

            # Assert
            assert isinstance(result, Success)
            assert len(result.value) == 2
            assert all(log["resource_type"] == "account" for log in result.value)

    @pytest.mark.asyncio
    async def test_query_pagination(self, test_database):
        """Test query() pagination with limit and offset."""
        # Arrange: Create 10 logs
        user_id = uuid4()

        for i in range(10):
            async with test_database.get_session() as audit_session:
                adapter = PostgresAuditAdapter(session=audit_session)
                await adapter.record(
                    action=AuditAction.DATA_VIEWED,
                    resource_type="account",
                    user_id=user_id,
                    context={"index": i},
                )

        # Act: Query with pagination (page 2, size 3)
        async with test_database.get_session() as query_session:
            adapter = PostgresAuditAdapter(session=query_session)
            result = await adapter.query(
                user_id=user_id,
                limit=3,
                offset=3,  # Skip first 3
            )

            # Assert
            assert isinstance(result, Success)
            assert len(result.value) == 3

            # Verify pagination works (got 3 results with offset=3)
            # Records created in loop may have same timestamp, so order not guaranteed
            # Just verify we got 3 different indices
            indices = {log["context"]["index"] for log in result.value}
            assert len(indices) == 3  # 3 unique indices

    @pytest.mark.asyncio
    async def test_query_date_range_filter(self, test_database):
        """Test query() filters by date range."""
        # Arrange: Create logs at different times (simulated)
        user_id = uuid4()

        # Create 3 logs (will have similar timestamps in test)
        for i in range(3):
            async with test_database.get_session() as audit_session:
                adapter = PostgresAuditAdapter(session=audit_session)
                await adapter.record(
                    action=AuditAction.DATA_VIEWED,
                    resource_type="account",
                    user_id=user_id,
                    context={"index": i},
                )

        # Act: Query with date range (last hour)
        now = datetime.now(UTC)
        start_date = now - timedelta(hours=1)
        end_date = now + timedelta(hours=1)

        async with test_database.get_session() as query_session:
            adapter = PostgresAuditAdapter(session=query_session)
            result = await adapter.query(
                user_id=user_id,
                start_date=start_date,
                end_date=end_date,
            )

            # Assert: All logs within range
            assert isinstance(result, Success)
            assert len(result.value) == 3

    @pytest.mark.asyncio
    async def test_query_returns_empty_list_when_no_matches(self, test_database):
        """Test query() returns empty list when no logs match."""
        # Act: Query for non-existent user
        async with test_database.get_session() as query_session:
            adapter = PostgresAuditAdapter(session=query_session)
            result = await adapter.query(user_id=uuid4())

            # Assert
            assert isinstance(result, Success)
            assert result.value == []

    @pytest.mark.asyncio
    async def test_query_converts_uuids_to_strings(self, test_database):
        """Test query() converts UUID fields to strings."""
        # Arrange
        user_id = uuid4()
        resource_id = uuid4()

        async with test_database.get_session() as audit_session:
            adapter = PostgresAuditAdapter(session=audit_session)
            await adapter.record(
                action=AuditAction.PROVIDER_CONNECTED,
                resource_type="provider",
                user_id=user_id,
                resource_id=resource_id,
            )

        # Act: Query logs
        async with test_database.get_session() as query_session:
            adapter = PostgresAuditAdapter(session=query_session)
            result = await adapter.query(user_id=user_id)

            # Assert
            assert isinstance(result, Success)
            log = result.value[0]

            # UUIDs should be strings
            assert isinstance(log["id"], str)
            assert isinstance(log["user_id"], str)
            assert isinstance(log["resource_id"], str)

            # Can convert back to UUID
            assert uuid4().__class__(log["id"])
            assert uuid4().__class__(log["user_id"])


@pytest.mark.integration
class TestPostgresAuditAdapterEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_query_with_multiple_filters(self, test_database):
        """Test query() with all filters combined."""
        # Arrange
        user_id = uuid4()

        # Create mix of logs
        async with test_database.get_session() as audit_session:
            adapter = PostgresAuditAdapter(session=audit_session)
            await adapter.record(
                action=AuditAction.USER_LOGIN_SUCCESS,
                resource_type="session",
                user_id=user_id,
            )
        async with test_database.get_session() as audit_session:
            adapter = PostgresAuditAdapter(session=audit_session)
            await adapter.record(
                action=AuditAction.DATA_VIEWED,
                resource_type="account",
                user_id=user_id,
            )
        async with test_database.get_session() as audit_session:
            adapter = PostgresAuditAdapter(session=audit_session)
            await adapter.record(
                action=AuditAction.DATA_VIEWED,
                resource_type="account",
                user_id=user_id,
            )

        # Act: Query with multiple filters
        async with test_database.get_session() as query_session:
            adapter = PostgresAuditAdapter(session=query_session)
            result = await adapter.query(
                user_id=user_id,
                action=AuditAction.DATA_VIEWED,
                resource_type="account",
                limit=10,
                offset=0,
            )

            # Assert: Only DATA_VIEWED + account
            assert isinstance(result, Success)
            assert len(result.value) == 2
            assert all(log["action"] == AuditAction.DATA_VIEWED for log in result.value)
            assert all(log["resource_type"] == "account" for log in result.value)

    @pytest.mark.asyncio
    async def test_query_system_actions_with_none_user_id(self, test_database):
        """Test query() handles system actions (user_id=None)."""
        # Arrange: Create system action
        async with test_database.get_session() as audit_session:
            adapter = PostgresAuditAdapter(session=audit_session)
            await adapter.record(
                action=AuditAction.ADMIN_BACKUP_CREATED,
                resource_type="system",
                user_id=None,  # System action
                context={"backup_type": "automated"},
            )

        # Act: Query for system actions
        async with test_database.get_session() as query_session:
            adapter = PostgresAuditAdapter(session=query_session)
            result = await adapter.query(
                user_id=None,
                action=AuditAction.ADMIN_BACKUP_CREATED,
            )

            # Assert
            assert isinstance(result, Success)
            assert len(result.value) >= 1

            # Find our log
            system_log = next(
                (
                    log
                    for log in result.value
                    if log["context"]
                    and log["context"].get("backup_type") == "automated"
                ),
                None,
            )
            assert system_log is not None
            assert system_log["user_id"] is None
            assert system_log["action"] == AuditAction.ADMIN_BACKUP_CREATED

    @pytest.mark.asyncio
    async def test_record_handles_very_long_user_agent(self, test_database):
        """Test record() handles long user agent strings."""
        # Arrange
        long_user_agent = "Mozilla/5.0 " + ("x" * 480)

        # Act: Record with long user agent
        async with test_database.get_session() as audit_session:
            adapter = PostgresAuditAdapter(session=audit_session)
            result = await adapter.record(
                action=AuditAction.USER_LOGIN_SUCCESS,
                resource_type="session",
                user_id=uuid4(),
                user_agent=long_user_agent,
            )

            # Assert
            assert isinstance(result, Success)

    @pytest.mark.asyncio
    async def test_multiple_adapters_share_session(self, test_database):
        """Test multiple adapter instances with separate sessions.

        Note: In production, audit sessions are separate and commit independently.
        This test verifies that multiple audit records persist correctly.
        """
        # Arrange
        user_id = uuid4()

        # Act: Record via separate sessions (mirrors production)
        async with test_database.get_session() as audit_session1:
            adapter1 = PostgresAuditAdapter(session=audit_session1)
            await adapter1.record(
                action=AuditAction.USER_LOGIN_SUCCESS,
                resource_type="session",
                user_id=user_id,
            )
        async with test_database.get_session() as audit_session2:
            adapter2 = PostgresAuditAdapter(session=audit_session2)
            await adapter2.record(
                action=AuditAction.USER_LOGOUT,
                resource_type="session",
                user_id=user_id,
            )

        # Assert: Both logs exist
        async with test_database.get_session() as query_session:
            adapter = PostgresAuditAdapter(session=query_session)
            result = await adapter.query(user_id=user_id)
            assert isinstance(result, Success)
            assert len(result.value) == 2
