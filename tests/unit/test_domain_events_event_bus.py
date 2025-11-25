"""Unit tests for InMemoryEventBus.

Tests cover:
- Subscribe/publish basic flow
- Multiple handlers for same event
- Handler failure doesn't break others (fail-open)
- No handlers registered (no-op)
- Handler receives correct event data
- Async handler support
- Concurrent handler execution
- Error logging for handler failures

Architecture:
- Unit tests with mocked logger
- Tests fail-open behavior (critical requirement)
- Validates concurrent execution (asyncio.gather)
"""

import asyncio
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from src.domain.events.auth_events import (
    UserRegistrationSucceeded,
    UserPasswordChangeSucceeded,
)
from src.domain.events.base_event import DomainEvent
from src.infrastructure.events.in_memory_event_bus import InMemoryEventBus


@pytest.mark.unit
class TestInMemoryEventBusBasicFlow:
    """Test basic subscribe/publish flow."""

    @pytest.mark.asyncio
    async def test_subscribe_and_publish_single_handler(self):
        """Test subscribing single handler and publishing event."""
        # Arrange
        mock_logger = MagicMock()
        event_bus = InMemoryEventBus(logger=mock_logger)

        handler_called = False
        received_event = None

        async def test_handler(event: DomainEvent) -> None:
            nonlocal handler_called, received_event
            handler_called = True
            received_event = event

        event = UserRegistrationSucceeded(
            user_id=uuid4(), email="test@example.com", verification_token="test_token"
        )

        # Act
        event_bus.subscribe(UserRegistrationSucceeded, test_handler)
        await event_bus.publish(event)

        # Assert
        assert handler_called is True
        assert received_event is event
        assert received_event.email == "test@example.com"

    @pytest.mark.asyncio
    async def test_subscribe_multiple_handlers_same_event(self):
        """Test multiple handlers for same event type all execute."""
        # Arrange
        mock_logger = MagicMock()
        event_bus = InMemoryEventBus(logger=mock_logger)

        call_order = []

        async def handler_1(event: DomainEvent) -> None:
            call_order.append("handler_1")

        async def handler_2(event: DomainEvent) -> None:
            call_order.append("handler_2")

        async def handler_3(event: DomainEvent) -> None:
            call_order.append("handler_3")

        event = UserRegistrationSucceeded(
            user_id=uuid4(), email="test@example.com", verification_token="test_token"
        )

        # Act
        event_bus.subscribe(UserRegistrationSucceeded, handler_1)
        event_bus.subscribe(UserRegistrationSucceeded, handler_2)
        event_bus.subscribe(UserRegistrationSucceeded, handler_3)
        await event_bus.publish(event)

        # Assert - All 3 handlers called (order not guaranteed due to concurrent execution)
        assert len(call_order) == 3
        assert "handler_1" in call_order
        assert "handler_2" in call_order
        assert "handler_3" in call_order

    @pytest.mark.asyncio
    async def test_publish_with_no_handlers_registered(self):
        """Test publishing event with no handlers is no-op (not an error)."""
        # Arrange
        mock_logger = MagicMock()
        event_bus = InMemoryEventBus(logger=mock_logger)

        event = UserRegistrationSucceeded(
            user_id=uuid4(), email="test@example.com", verification_token="test_token"
        )

        # Act & Assert - Should not raise exception
        await event_bus.publish(event)

        # Logger should not be called (no handlers = no-op)
        mock_logger.debug.assert_not_called()


@pytest.mark.unit
class TestInMemoryEventBusFailOpen:
    """Test fail-open behavior (critical requirement)."""

    @pytest.mark.asyncio
    async def test_handler_failure_does_not_break_other_handlers(self):
        """Test one handler failure doesn't prevent other handlers from executing."""
        # Arrange
        mock_logger = MagicMock()
        event_bus = InMemoryEventBus(logger=mock_logger)

        successful_handlers = []

        async def failing_handler(event: DomainEvent) -> None:
            raise ValueError("Handler intentionally failed")

        async def successful_handler_1(event: DomainEvent) -> None:
            successful_handlers.append("handler_1")

        async def successful_handler_2(event: DomainEvent) -> None:
            successful_handlers.append("handler_2")

        event = UserRegistrationSucceeded(
            user_id=uuid4(), email="test@example.com", verification_token="test_token"
        )

        # Act
        event_bus.subscribe(UserRegistrationSucceeded, successful_handler_1)
        event_bus.subscribe(UserRegistrationSucceeded, failing_handler)
        event_bus.subscribe(UserRegistrationSucceeded, successful_handler_2)

        # Should not raise exception
        await event_bus.publish(event)

        # Assert - Both successful handlers executed
        assert len(successful_handlers) == 2
        assert "handler_1" in successful_handlers
        assert "handler_2" in successful_handlers

        # Assert - Failure was logged
        mock_logger.warning.assert_called_once()
        call_args = mock_logger.warning.call_args
        assert call_args[0][0] == "event_handler_failed"
        assert call_args[1]["error_type"] == "ValueError"
        assert call_args[1]["error_message"] == "Handler intentionally failed"

    @pytest.mark.asyncio
    async def test_multiple_handler_failures_all_logged(self):
        """Test multiple handler failures all logged separately."""
        # Arrange
        mock_logger = MagicMock()
        event_bus = InMemoryEventBus(logger=mock_logger)

        async def failing_handler_1(event: DomainEvent) -> None:
            raise ValueError("Handler 1 failed")

        async def failing_handler_2(event: DomainEvent) -> None:
            raise RuntimeError("Handler 2 failed")

        async def successful_handler(event: DomainEvent) -> None:
            pass  # Success

        event = UserRegistrationSucceeded(
            user_id=uuid4(), email="test@example.com", verification_token="test_token"
        )

        # Act
        event_bus.subscribe(UserRegistrationSucceeded, failing_handler_1)
        event_bus.subscribe(UserRegistrationSucceeded, failing_handler_2)
        event_bus.subscribe(UserRegistrationSucceeded, successful_handler)
        await event_bus.publish(event)

        # Assert - Both failures logged
        assert mock_logger.warning.call_count == 2

        # Check both errors were logged
        warning_calls = mock_logger.warning.call_args_list
        error_messages = [call[1]["error_message"] for call in warning_calls]
        assert "Handler 1 failed" in error_messages
        assert "Handler 2 failed" in error_messages


@pytest.mark.unit
class TestInMemoryEventBusEventData:
    """Test handlers receive correct event data."""

    @pytest.mark.asyncio
    async def test_handler_receives_complete_event_data(self):
        """Test handler receives all event fields correctly."""
        # Arrange
        mock_logger = MagicMock()
        event_bus = InMemoryEventBus(logger=mock_logger)

        received_data = {}

        async def capture_handler(event: UserRegistrationSucceeded) -> None:
            received_data["user_id"] = event.user_id
            received_data["email"] = event.email
            received_data["event_id"] = event.event_id
            received_data["occurred_at"] = event.occurred_at

        user_id = uuid4()
        event = UserRegistrationSucceeded(
            user_id=user_id, email="test@example.com", verification_token="test_token"
        )

        # Act
        event_bus.subscribe(UserRegistrationSucceeded, capture_handler)
        await event_bus.publish(event)

        # Assert
        assert received_data["user_id"] == user_id
        assert received_data["email"] == "test@example.com"
        assert received_data["event_id"] == event.event_id
        assert received_data["occurred_at"] == event.occurred_at

    @pytest.mark.asyncio
    async def test_different_event_types_routed_correctly(self):
        """Test different event types routed to correct handlers."""
        # Arrange
        mock_logger = MagicMock()
        event_bus = InMemoryEventBus(logger=mock_logger)

        received_events = []

        async def registration_handler(event: UserRegistrationSucceeded) -> None:
            received_events.append(("registration", event))

        async def password_change_handler(event: UserPasswordChangeSucceeded) -> None:
            received_events.append(("password_change", event))

        registration_event = UserRegistrationSucceeded(
            user_id=uuid4(), email="test@example.com", verification_token="test_token"
        )

        password_event = UserPasswordChangeSucceeded(
            user_id=uuid4(), initiated_by="user"
        )

        # Act
        event_bus.subscribe(UserRegistrationSucceeded, registration_handler)
        event_bus.subscribe(UserPasswordChangeSucceeded, password_change_handler)

        await event_bus.publish(registration_event)
        await event_bus.publish(password_event)

        # Assert
        assert len(received_events) == 2
        assert received_events[0][0] == "registration"
        assert received_events[0][1] is registration_event
        assert received_events[1][0] == "password_change"
        assert received_events[1][1] is password_event


@pytest.mark.unit
class TestInMemoryEventBusAsyncSupport:
    """Test async handler support and concurrent execution."""

    @pytest.mark.asyncio
    async def test_async_handlers_execute_concurrently(self):
        """Test async handlers execute concurrently (not sequentially)."""
        # Arrange
        mock_logger = MagicMock()
        event_bus = InMemoryEventBus(logger=mock_logger)

        execution_order = []

        async def slow_handler(event: DomainEvent) -> None:
            execution_order.append("slow_start")
            await asyncio.sleep(0.1)  # Simulate slow operation
            execution_order.append("slow_end")

        async def fast_handler(event: DomainEvent) -> None:
            execution_order.append("fast_start")
            await asyncio.sleep(0.01)  # Fast operation
            execution_order.append("fast_end")

        event = UserRegistrationSucceeded(
            user_id=uuid4(), email="test@example.com", verification_token="test_token"
        )

        # Act
        event_bus.subscribe(UserRegistrationSucceeded, slow_handler)
        event_bus.subscribe(UserRegistrationSucceeded, fast_handler)
        await event_bus.publish(event)

        # Assert - Fast handler completes before slow handler (concurrent execution)
        # If sequential: [slow_start, slow_end, fast_start, fast_end]
        # If concurrent: both start, fast finishes first
        assert "slow_start" in execution_order
        assert "fast_start" in execution_order
        assert "fast_end" in execution_order
        assert "slow_end" in execution_order

        # Fast handler should finish before slow handler finishes
        fast_end_idx = execution_order.index("fast_end")
        slow_end_idx = execution_order.index("slow_end")
        assert fast_end_idx < slow_end_idx

    @pytest.mark.asyncio
    async def test_handler_with_async_operations(self):
        """Test handler can perform async operations."""
        # Arrange
        mock_logger = MagicMock()
        event_bus = InMemoryEventBus(logger=mock_logger)

        async_operation_completed = False

        async def async_handler(event: DomainEvent) -> None:
            nonlocal async_operation_completed
            # Simulate async I/O (database write, API call, etc.)
            await asyncio.sleep(0.01)
            async_operation_completed = True

        event = UserRegistrationSucceeded(
            user_id=uuid4(), email="test@example.com", verification_token="test_token"
        )

        # Act
        event_bus.subscribe(UserRegistrationSucceeded, async_handler)
        await event_bus.publish(event)

        # Assert
        assert async_operation_completed is True


@pytest.mark.unit
class TestInMemoryEventBusLogging:
    """Test logging behavior."""

    @pytest.mark.asyncio
    async def test_event_publishing_logged_at_debug_level(self):
        """Test event publishing logged with debug level."""
        # Arrange
        mock_logger = MagicMock()
        event_bus = InMemoryEventBus(logger=mock_logger)

        async def dummy_handler(event: DomainEvent) -> None:
            pass

        event = UserRegistrationSucceeded(
            user_id=uuid4(), email="test@example.com", verification_token="test_token"
        )

        # Act
        event_bus.subscribe(UserRegistrationSucceeded, dummy_handler)
        await event_bus.publish(event)

        # Assert
        mock_logger.debug.assert_called_once()
        call_args = mock_logger.debug.call_args
        assert call_args[0][0] == "event_publishing"
        assert call_args[1]["event_type"] == "UserRegistrationSucceeded"
        assert call_args[1]["event_id"] == str(event.event_id)
        assert call_args[1]["handler_count"] == 1

    @pytest.mark.asyncio
    async def test_handler_failure_logged_with_details(self):
        """Test handler failure logged with complete error context."""
        # Arrange
        mock_logger = MagicMock()
        event_bus = InMemoryEventBus(logger=mock_logger)

        async def failing_handler(event: DomainEvent) -> None:
            raise ValueError("Test error message")

        event = UserRegistrationSucceeded(
            user_id=uuid4(), email="test@example.com", verification_token="test_token"
        )

        # Act
        event_bus.subscribe(UserRegistrationSucceeded, failing_handler)
        await event_bus.publish(event)

        # Assert
        mock_logger.warning.assert_called_once()
        call_args = mock_logger.warning.call_args
        assert call_args[0][0] == "event_handler_failed"
        assert call_args[1]["event_type"] == "UserRegistrationSucceeded"
        assert call_args[1]["event_id"] == str(event.event_id)
        assert call_args[1]["handler_name"] == "failing_handler"
        assert call_args[1]["error_type"] == "ValueError"
        assert call_args[1]["error_message"] == "Test error message"
        assert "exc_info" in call_args[1]  # Stack trace included


@pytest.mark.unit
class TestInMemoryEventBusEdgeCases:
    """Test edge cases and boundary conditions."""

    @pytest.mark.asyncio
    async def test_subscribe_same_handler_twice(self):
        """Test subscribing same handler twice results in two calls."""
        # Arrange
        mock_logger = MagicMock()
        event_bus = InMemoryEventBus(logger=mock_logger)

        call_count = 0

        async def handler(event: DomainEvent) -> None:
            nonlocal call_count
            call_count += 1

        event = UserRegistrationSucceeded(
            user_id=uuid4(), email="test@example.com", verification_token="test_token"
        )

        # Act - Subscribe same handler twice
        event_bus.subscribe(UserRegistrationSucceeded, handler)
        event_bus.subscribe(UserRegistrationSucceeded, handler)
        await event_bus.publish(event)

        # Assert - Handler called twice (no deduplication)
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_publish_multiple_events_in_sequence(self):
        """Test publishing multiple events in sequence works correctly."""
        # Arrange
        mock_logger = MagicMock()
        event_bus = InMemoryEventBus(logger=mock_logger)

        received_emails = []

        async def handler(event: UserRegistrationSucceeded) -> None:
            received_emails.append(event.email)

        event1 = UserRegistrationSucceeded(
            user_id=uuid4(), email="user1@example.com", verification_token="token1"
        )
        event2 = UserRegistrationSucceeded(
            user_id=uuid4(), email="user2@example.com", verification_token="token2"
        )
        event3 = UserRegistrationSucceeded(
            user_id=uuid4(), email="user3@example.com", verification_token="token3"
        )

        # Act
        event_bus.subscribe(UserRegistrationSucceeded, handler)
        await event_bus.publish(event1)
        await event_bus.publish(event2)
        await event_bus.publish(event3)

        # Assert
        assert received_emails == [
            "user1@example.com",
            "user2@example.com",
            "user3@example.com",
        ]

    @pytest.mark.asyncio
    async def test_handler_returning_value_ignored(self):
        """Test handler return value is ignored (handlers should return None)."""
        # Arrange
        mock_logger = MagicMock()
        event_bus = InMemoryEventBus(logger=mock_logger)

        async def handler_with_return(event: DomainEvent) -> str:
            return "This return value should be ignored"

        event = UserRegistrationSucceeded(
            user_id=uuid4(), email="test@example.com", verification_token="test_token"
        )

        # Act & Assert - Should not raise exception
        event_bus.subscribe(UserRegistrationSucceeded, handler_with_return)
        result = await event_bus.publish(event)

        # publish() returns None
        assert result is None
