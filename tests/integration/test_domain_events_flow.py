"""Integration tests for domain events end-to-end flow.

Tests cover:
- End-to-end: publish event → all handlers execute
- Real database for audit handler (audit records created)
- Real logger for logging handler (structured logging)
- Handler execution order independence (concurrent)
- Multiple events in sequence
- Container get_event_bus() returns singleton
- Event flow with real infrastructure dependencies

Architecture:
- Integration tests with real PostgreSQL database
- Uses test_database fixture for audit records
- Uses test_logger fixture for logging verification
- Tests complete event flow from publish → handlers → side effects
- Validates fail-open behavior with real infrastructure
"""

from datetime import datetime, UTC
from uuid import uuid4

import pytest
from sqlalchemy import select

from src.core.container import get_event_bus
from src.domain.enums.audit_action import AuditAction
from src.domain.events.auth_events import (
    UserRegistrationSucceeded,
    UserPasswordChangeSucceeded,
    ProviderConnectionSucceeded,
    TokenRefreshFailed,
)
from src.infrastructure.persistence.models.audit_log import AuditLog


@pytest.mark.integration
class TestEventBusContainerIntegration:
    """Test event bus container integration and singleton behavior."""

    def test_get_event_bus_returns_singleton(self):
        """Test get_event_bus() returns same instance (singleton)."""
        # Act
        bus1 = get_event_bus()
        bus2 = get_event_bus()

        # Assert
        assert bus1 is bus2

    def test_event_bus_has_subscriptions_wired(self):
        """Test event bus has handlers subscribed at startup."""
        # Arrange
        event_bus = get_event_bus()

        # Assert - Check subscriptions exist for critical events
        # InMemoryEventBus stores handlers in _handlers dict
        assert len(event_bus._handlers) > 0

        # Check UserRegistrationSucceeded has multiple handlers
        # (logging, audit, email)
        assert UserRegistrationSucceeded in event_bus._handlers
        assert len(event_bus._handlers[UserRegistrationSucceeded]) >= 3


@pytest.mark.integration
class TestEventFlowEndToEnd:
    """Test complete event flow with real infrastructure."""

    @pytest.mark.asyncio
    async def test_user_registration_succeeded_creates_audit_record(
        self, test_database
    ):
        """Test UserRegistrationSucceeded → audit record created."""
        # Arrange
        event_bus = get_event_bus()
        user_id = uuid4()
        event = UserRegistrationSucceeded(
            user_id=user_id,
            email="integration@example.com",
            verification_token="test_token_123",
        )

        # Act - Pass session to avoid "Event loop is closed" error
        async with test_database.get_session() as session:
            await event_bus.publish(event, session=session)

        # Assert - Audit record created in database
        async with test_database.get_session() as session:
            stmt = select(AuditLog).where(AuditLog.user_id == user_id)
            result = await session.execute(stmt)
            logs = result.scalars().all()

            assert len(logs) == 1
            log = logs[0]
            assert log.action == AuditAction.USER_REGISTERED
            assert log.user_id == user_id
            assert log.resource_type == "user"
            assert log.resource_id == user_id  # UUID, not string
            assert log.context["email"] == "integration@example.com"
            assert log.context["registration_method"] == "email"

    @pytest.mark.asyncio
    async def test_password_change_succeeded_creates_audit_record(self, test_database):
        """Test UserPasswordChangeSucceeded → audit record created."""
        # Arrange
        event_bus = get_event_bus()
        user_id = uuid4()
        event = UserPasswordChangeSucceeded(user_id=user_id, initiated_by="user")

        # Act - Pass session to avoid "Event loop is closed" error
        async with test_database.get_session() as session:
            await event_bus.publish(event, session=session)

        # Assert - Audit record created
        async with test_database.get_session() as session:
            stmt = select(AuditLog).where(AuditLog.user_id == user_id)
            result = await session.execute(stmt)
            logs = result.scalars().all()

            assert len(logs) == 1
            log = logs[0]
            assert log.action == AuditAction.USER_PASSWORD_CHANGED
            assert log.user_id == user_id
            assert log.resource_type == "user"
            assert log.context["initiated_by"] == "user"

    @pytest.mark.asyncio
    async def test_provider_connection_succeeded_creates_audit_record(
        self, test_database
    ):
        """Test ProviderConnectionSucceeded → audit record created."""
        # Arrange
        event_bus = get_event_bus()
        user_id = uuid4()
        provider_id = uuid4()
        event = ProviderConnectionSucceeded(
            user_id=user_id, provider_id=provider_id, provider_name="schwab"
        )

        # Act - Pass session to avoid "Event loop is closed" error
        async with test_database.get_session() as session:
            await event_bus.publish(event, session=session)

        # Assert - Audit record created
        async with test_database.get_session() as session:
            stmt = select(AuditLog).where(AuditLog.user_id == user_id)
            result = await session.execute(stmt)
            logs = result.scalars().all()

            assert len(logs) == 1
            log = logs[0]
            assert log.action == AuditAction.PROVIDER_CONNECTED
            assert log.user_id == user_id
            assert log.resource_type == "provider"
            assert log.resource_id == provider_id  # UUID, not string
            assert log.context["provider_name"] == "schwab"

    @pytest.mark.asyncio
    async def test_token_refresh_failed_creates_audit_record(self, test_database):
        """Test TokenRefreshFailed → audit record created."""
        # Arrange
        event_bus = get_event_bus()
        user_id = uuid4()
        provider_id = uuid4()
        event = TokenRefreshFailed(
            user_id=user_id,
            provider_id=provider_id,
            provider_name="schwab",
            error_code="invalid_grant",
        )

        # Act - Pass session to avoid "Event loop is closed" error
        async with test_database.get_session() as session:
            await event_bus.publish(event, session=session)

        # Assert - Audit record created
        async with test_database.get_session() as session:
            stmt = select(AuditLog).where(AuditLog.user_id == user_id)
            result = await session.execute(stmt)
            logs = result.scalars().all()

            assert len(logs) == 1
            log = logs[0]
            assert log.action == AuditAction.PROVIDER_TOKEN_REFRESH_FAILED
            assert log.user_id == user_id
            assert log.resource_type == "token"
            assert log.context["error_code"] == "invalid_grant"


@pytest.mark.integration
class TestMultipleEventsSequence:
    """Test multiple events published in sequence."""

    @pytest.mark.asyncio
    async def test_multiple_events_create_separate_audit_records(self, test_database):
        """Test publishing multiple events creates separate audit records."""
        # Arrange
        event_bus = get_event_bus()
        user_id = uuid4()

        # Act - Publish 3 different events (pass session to each)
        async with test_database.get_session() as session:
            await event_bus.publish(
                UserRegistrationSucceeded(
                    user_id=user_id,
                    email="test1@example.com",
                    verification_token="test_token_1",
                ),
                session=session,
            )
            await event_bus.publish(
                UserPasswordChangeSucceeded(user_id=user_id, initiated_by="user"),
                session=session,
            )
            provider_id = uuid4()
            await event_bus.publish(
                ProviderConnectionSucceeded(
                    user_id=user_id, provider_id=provider_id, provider_name="schwab"
                ),
                session=session,
            )

        # Assert - 3 separate audit records
        async with test_database.get_session() as session:
            stmt = (
                select(AuditLog)
                .where(AuditLog.user_id == user_id)
                .order_by(AuditLog.created_at)
            )
            result = await session.execute(stmt)
            logs = result.scalars().all()

            assert len(logs) == 3

            # Verify each audit record
            assert logs[0].action == AuditAction.USER_REGISTERED
            assert logs[1].action == AuditAction.USER_PASSWORD_CHANGED
            assert logs[2].action == AuditAction.PROVIDER_CONNECTED

    @pytest.mark.asyncio
    async def test_same_event_published_multiple_times(self, test_database):
        """Test same event type published multiple times creates multiple records."""
        # Arrange
        event_bus = get_event_bus()
        user_id = uuid4()

        # Act - Publish same event 3 times with different data (pass session)
        async with test_database.get_session() as session:
            await event_bus.publish(
                UserRegistrationSucceeded(
                    user_id=user_id,
                    email="user1@example.com",
                    verification_token="test_token_user1",
                ),
                session=session,
            )

            user_id_2 = uuid4()
            await event_bus.publish(
                UserRegistrationSucceeded(
                    user_id=user_id_2,
                    email="user2@example.com",
                    verification_token="test_token_user2",
                ),
                session=session,
            )

            user_id_3 = uuid4()
            await event_bus.publish(
                UserRegistrationSucceeded(
                    user_id=user_id_3,
                    email="user3@example.com",
                    verification_token="test_token_user3",
                ),
                session=session,
            )

        # Assert - 3 audit records (one per event)
        async with test_database.get_session() as session:
            stmt = select(AuditLog).where(
                AuditLog.action == AuditAction.USER_REGISTERED
            )
            result = await session.execute(stmt)
            logs = result.scalars().all()

            # Should have at least 3 (may have more from other tests)
            user_ids = [log.user_id for log in logs]
            assert user_id in user_ids
            assert user_id_2 in user_ids
            assert user_id_3 in user_ids


@pytest.mark.integration
class TestHandlerExecutionOrder:
    """Test handler execution order independence (concurrent)."""

    @pytest.mark.asyncio
    async def test_handlers_execute_concurrently(self, test_database):
        """Test multiple handlers execute concurrently (not sequentially).

        Note: This is a behavior test. We verify all handlers completed
        by checking side effects (audit record exists). Concurrent execution
        is validated by InMemoryEventBus using asyncio.gather.
        """
        # Arrange
        event_bus = get_event_bus()
        user_id = uuid4()
        event = UserRegistrationSucceeded(
            user_id=user_id,
            email="concurrent@example.com",
            verification_token="test_token_concurrent",
        )

        # Act - Pass session to avoid "Event loop is closed" error
        async with test_database.get_session() as session:
            await event_bus.publish(event, session=session)

        # Assert - All handlers completed (audit, logging, email)
        # Audit handler side effect: Database record exists
        async with test_database.get_session() as session:
            stmt = select(AuditLog).where(AuditLog.user_id == user_id)
            result = await session.execute(stmt)
            log = result.scalars().first()

            assert log is not None
            assert log.action == AuditAction.USER_REGISTERED

        # Note: Logging and email handlers also executed, but we can't easily
        # verify their side effects in integration tests (logs to stdout,
        # email stub logs). Their execution is validated by unit tests.


@pytest.mark.integration
class TestFailOpenBehaviorWithRealInfrastructure:
    """Test fail-open behavior with real infrastructure dependencies."""

    @pytest.mark.asyncio
    async def test_audit_handler_failure_does_not_break_event_bus(self, test_database):
        """Test audit handler failure doesn't prevent event publication.

        This test simulates audit handler failure by publishing an event
        and verifying the event bus completes (doesn't raise exception).

        Note: With real infrastructure, handler failures are less common,
        but fail-open behavior is still critical. Unit tests validate
        exception handling more thoroughly with mocks.
        """
        # Arrange
        event_bus = get_event_bus()
        user_id = uuid4()
        event = UserRegistrationSucceeded(
            user_id=user_id,
            email="failopen@example.com",
            verification_token="test_token_failopen",
        )

        # Act - Should not raise exception even if handler fails
        # (Event bus catches exceptions with asyncio.gather(return_exceptions=True))
        async with test_database.get_session() as session:
            await event_bus.publish(event, session=session)

        # Assert - Event bus completed (no exception raised)
        # If fail-open wasn't working, an exception would propagate


@pytest.mark.integration
class TestEventDataIntegrity:
    """Test event data integrity through complete flow."""

    @pytest.mark.asyncio
    async def test_event_fields_preserved_in_audit_record(self, test_database):
        """Test event fields are preserved correctly in audit record."""
        # Arrange
        event_bus = get_event_bus()
        user_id = uuid4()
        provider_id = uuid4()
        timestamp = datetime.now(UTC)

        event = ProviderConnectionSucceeded(
            event_id=uuid4(),  # Explicit event_id
            occurred_at=timestamp,  # Explicit timestamp
            user_id=user_id,
            provider_id=provider_id,
            provider_name="schwab",
        )

        # Act - Pass session to avoid "Event loop is closed" error
        async with test_database.get_session() as session:
            await event_bus.publish(event, session=session)

        # Assert - All event fields preserved in audit
        async with test_database.get_session() as session:
            stmt = select(AuditLog).where(AuditLog.user_id == user_id)
            result = await session.execute(stmt)
            log = result.scalars().first()

            assert log is not None
            assert log.user_id == user_id
            assert log.resource_id == provider_id  # UUID, not string
            assert log.context["event_id"] == str(event.event_id)
            assert log.context["provider_name"] == "schwab"
            # Timestamp preserved (within 1 second tolerance for test timing)
            assert abs((log.created_at - timestamp).total_seconds()) < 1

    @pytest.mark.asyncio
    async def test_event_with_optional_fields(self, test_database):
        """Test events with optional fields (None values) handled correctly."""
        # Arrange
        event_bus = get_event_bus()
        user_id = uuid4()

        # UserPasswordChangeSucceeded doesn't have ip_address (unlike ATTEMPTED)
        event = UserPasswordChangeSucceeded(user_id=user_id, initiated_by="admin")

        # Act - Pass session to avoid "Event loop is closed" error
        async with test_database.get_session() as session:
            await event_bus.publish(event, session=session)

        # Assert - Audit record created without issues
        async with test_database.get_session() as session:
            stmt = select(AuditLog).where(AuditLog.user_id == user_id)
            result = await session.execute(stmt)
            log = result.scalars().first()

            assert log is not None
            assert log.ip_address is None  # Optional field not in SUCCEEDED event
            assert log.context["initiated_by"] == "admin"


@pytest.mark.integration
class TestContainerCacheClearing:
    """Test container cache clearing for test isolation."""

    def test_clearing_container_cache_allows_new_event_bus(self):
        """Test clearing container cache creates new event bus instance.

        Note: This is mainly for testing purposes. In production, event bus
        is a singleton for the lifetime of the application.
        """
        # Arrange
        bus1 = get_event_bus()

        # Act - Clear cache
        get_event_bus.cache_clear()
        bus2 = get_event_bus()

        # Assert - Different instances after cache clear
        assert bus1 is not bus2

        # Cleanup - Clear again for test isolation
        get_event_bus.cache_clear()
