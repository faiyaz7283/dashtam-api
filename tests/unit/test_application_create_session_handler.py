"""Unit tests for CreateSessionHandler.

Tests cover:
- Successful session creation (returns CreateSessionResponse)
- Device info enrichment from user agent
- Location enrichment from IP address
- Session limit enforcement (per user tier)
- Session eviction when at limit
- Event publishing (SessionCreated, SessionEvicted)
- Session caching

Architecture:
- Unit tests for application handler (mocked dependencies)
- Mock repository and enricher protocols
- Test handler logic, not persistence details
- Async tests (handler uses async repositories)

Note: This handler ONLY creates sessions. It does NOT authenticate users
or generate tokens (CQRS separation).
"""

from dataclasses import dataclass
from unittest.mock import AsyncMock, Mock
from uuid import UUID
from uuid_extensions import uuid7

import pytest

from src.application.commands.handlers.create_session_handler import (
    CreateSessionError,
    CreateSessionHandler,
    CreateSessionResponse,
)
from src.application.commands.session_commands import CreateSession
from src.core.result import Failure, Success
from src.domain.entities.user import User
from src.domain.events.session_events import SessionCreatedEvent, SessionEvictedEvent
from src.domain.protocols.session_repository import SessionData


def create_mock_user(
    user_id: UUID | None = None,
    session_tier: str = "basic",
    max_sessions: int | None = 3,
) -> Mock:
    """Create a mock User entity for testing."""
    mock_user = Mock(spec=User)
    mock_user.id = user_id or uuid7()
    mock_user.session_tier = session_tier
    mock_user.max_sessions = max_sessions
    mock_user.get_max_sessions.return_value = max_sessions
    return mock_user


def create_mock_session_data(
    session_id: UUID | None = None,
    user_id: UUID | None = None,
) -> Mock:
    """Create a mock SessionData for testing."""
    mock_session = Mock(spec=SessionData)
    mock_session.id = session_id or uuid7()
    mock_session.user_id = user_id or uuid7()
    mock_session.device_info = "Chrome on Windows"
    mock_session.is_revoked = False
    mock_session.revoked_at = None
    mock_session.revoked_reason = None
    return mock_session


@dataclass
class MockDeviceResult:
    """Mock device enrichment result."""

    device_info: str | None


@dataclass
class MockLocationResult:
    """Mock location enrichment result."""

    location: str | None


@pytest.mark.unit
class TestCreateSessionHandlerSuccess:
    """Test successful session creation scenarios."""

    @pytest.mark.asyncio
    async def test_create_session_returns_response(self):
        """Test successful session creation returns Success with response."""
        # Arrange
        user_id = uuid7()
        mock_user = create_mock_user(user_id=user_id, max_sessions=None)

        mock_session_repo = AsyncMock()
        mock_session_cache = AsyncMock()

        mock_user_repo = AsyncMock()
        mock_user_repo.find_by_id.return_value = mock_user

        mock_device_enricher = AsyncMock()
        mock_device_enricher.enrich.return_value = MockDeviceResult(
            device_info="Chrome 120 on Windows 10"
        )

        mock_location_enricher = AsyncMock()
        mock_location_enricher.enrich.return_value = MockLocationResult(
            location="New York, US"
        )

        mock_event_bus = AsyncMock()

        handler = CreateSessionHandler(
            session_repo=mock_session_repo,
            session_cache=mock_session_cache,
            user_repo=mock_user_repo,
            device_enricher=mock_device_enricher,
            location_enricher=mock_location_enricher,
            event_bus=mock_event_bus,
        )

        command = CreateSession(
            user_id=user_id,
            ip_address="192.168.1.1",
            user_agent="Mozilla/5.0 Chrome/120.0",
        )

        # Act
        result = await handler.handle(command)

        # Assert
        assert isinstance(result, Success)
        assert isinstance(result.value, CreateSessionResponse)
        assert result.value.session_id is not None
        assert result.value.device_info == "Chrome 120 on Windows 10"
        assert result.value.location == "New York, US"

    @pytest.mark.asyncio
    async def test_create_session_enriches_device_info(self):
        """Test session creation enriches device info from user agent."""
        # Arrange
        user_id = uuid7()
        mock_user = create_mock_user(user_id=user_id, max_sessions=None)
        user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0"

        mock_session_repo = AsyncMock()
        mock_session_cache = AsyncMock()

        mock_user_repo = AsyncMock()
        mock_user_repo.find_by_id.return_value = mock_user

        mock_device_enricher = AsyncMock()
        mock_device_enricher.enrich.return_value = MockDeviceResult(
            device_info="Chrome 120 on Windows 10"
        )

        mock_location_enricher = AsyncMock()
        mock_location_enricher.enrich.return_value = MockLocationResult(location=None)

        mock_event_bus = AsyncMock()

        handler = CreateSessionHandler(
            session_repo=mock_session_repo,
            session_cache=mock_session_cache,
            user_repo=mock_user_repo,
            device_enricher=mock_device_enricher,
            location_enricher=mock_location_enricher,
            event_bus=mock_event_bus,
        )

        command = CreateSession(
            user_id=user_id,
            ip_address="192.168.1.1",
            user_agent=user_agent,
        )

        # Act
        await handler.handle(command)

        # Assert
        mock_device_enricher.enrich.assert_called_once_with(user_agent)

    @pytest.mark.asyncio
    async def test_create_session_enriches_location(self):
        """Test session creation enriches location from IP address."""
        # Arrange
        user_id = uuid7()
        mock_user = create_mock_user(user_id=user_id, max_sessions=None)
        ip_address = "8.8.8.8"

        mock_session_repo = AsyncMock()
        mock_session_cache = AsyncMock()

        mock_user_repo = AsyncMock()
        mock_user_repo.find_by_id.return_value = mock_user

        mock_device_enricher = AsyncMock()
        mock_device_enricher.enrich.return_value = MockDeviceResult(device_info=None)

        mock_location_enricher = AsyncMock()
        mock_location_enricher.enrich.return_value = MockLocationResult(
            location="Mountain View, US"
        )

        mock_event_bus = AsyncMock()

        handler = CreateSessionHandler(
            session_repo=mock_session_repo,
            session_cache=mock_session_cache,
            user_repo=mock_user_repo,
            device_enricher=mock_device_enricher,
            location_enricher=mock_location_enricher,
            event_bus=mock_event_bus,
        )

        command = CreateSession(
            user_id=user_id,
            ip_address=ip_address,
            user_agent="Chrome",
        )

        # Act
        await handler.handle(command)

        # Assert
        mock_location_enricher.enrich.assert_called_once_with(ip_address)

    @pytest.mark.asyncio
    async def test_create_session_saves_to_database(self):
        """Test session is persisted to database."""
        # Arrange
        user_id = uuid7()
        mock_user = create_mock_user(user_id=user_id, max_sessions=None)

        mock_session_repo = AsyncMock()
        mock_session_cache = AsyncMock()

        mock_user_repo = AsyncMock()
        mock_user_repo.find_by_id.return_value = mock_user

        mock_device_enricher = AsyncMock()
        mock_device_enricher.enrich.return_value = MockDeviceResult(device_info=None)

        mock_location_enricher = AsyncMock()
        mock_location_enricher.enrich.return_value = MockLocationResult(location=None)

        mock_event_bus = AsyncMock()

        handler = CreateSessionHandler(
            session_repo=mock_session_repo,
            session_cache=mock_session_cache,
            user_repo=mock_user_repo,
            device_enricher=mock_device_enricher,
            location_enricher=mock_location_enricher,
            event_bus=mock_event_bus,
        )

        command = CreateSession(
            user_id=user_id,
            ip_address="192.168.1.1",
            user_agent="Chrome",
        )

        # Act
        await handler.handle(command)

        # Assert
        mock_session_repo.save.assert_called_once()
        saved_session = mock_session_repo.save.call_args[0][0]
        assert saved_session.user_id == user_id
        assert saved_session.is_revoked is False

    @pytest.mark.asyncio
    async def test_create_session_caches_session(self):
        """Test session is cached in Redis."""
        # Arrange
        user_id = uuid7()
        mock_user = create_mock_user(user_id=user_id, max_sessions=None)

        mock_session_repo = AsyncMock()
        mock_session_cache = AsyncMock()

        mock_user_repo = AsyncMock()
        mock_user_repo.find_by_id.return_value = mock_user

        mock_device_enricher = AsyncMock()
        mock_device_enricher.enrich.return_value = MockDeviceResult(device_info=None)

        mock_location_enricher = AsyncMock()
        mock_location_enricher.enrich.return_value = MockLocationResult(location=None)

        mock_event_bus = AsyncMock()

        handler = CreateSessionHandler(
            session_repo=mock_session_repo,
            session_cache=mock_session_cache,
            user_repo=mock_user_repo,
            device_enricher=mock_device_enricher,
            location_enricher=mock_location_enricher,
            event_bus=mock_event_bus,
        )

        command = CreateSession(
            user_id=user_id,
            ip_address="192.168.1.1",
            user_agent="Chrome",
        )

        # Act
        await handler.handle(command)

        # Assert
        mock_session_cache.set.assert_called_once()


@pytest.mark.unit
class TestCreateSessionHandlerFailure:
    """Test session creation failure scenarios."""

    @pytest.mark.asyncio
    async def test_create_session_fails_when_user_not_found(self):
        """Test session creation fails with USER_NOT_FOUND when user doesn't exist."""
        # Arrange
        mock_session_repo = AsyncMock()
        mock_session_cache = AsyncMock()

        mock_user_repo = AsyncMock()
        mock_user_repo.find_by_id.return_value = None

        mock_device_enricher = AsyncMock()
        mock_location_enricher = AsyncMock()
        mock_event_bus = AsyncMock()

        handler = CreateSessionHandler(
            session_repo=mock_session_repo,
            session_cache=mock_session_cache,
            user_repo=mock_user_repo,
            device_enricher=mock_device_enricher,
            location_enricher=mock_location_enricher,
            event_bus=mock_event_bus,
        )

        command = CreateSession(
            user_id=uuid7(),
            ip_address="192.168.1.1",
            user_agent="Chrome",
        )

        # Act
        result = await handler.handle(command)

        # Assert
        assert isinstance(result, Failure)
        assert result.error == CreateSessionError.USER_NOT_FOUND


@pytest.mark.unit
class TestCreateSessionHandlerSessionLimit:
    """Test session limit enforcement and eviction."""

    @pytest.mark.asyncio
    async def test_create_session_evicts_oldest_when_at_limit(self):
        """Test oldest session is evicted when user is at session limit."""
        # Arrange
        user_id = uuid7()
        mock_user = create_mock_user(user_id=user_id, max_sessions=3)
        oldest_session = create_mock_session_data(user_id=user_id)

        mock_session_repo = AsyncMock()
        mock_session_repo.count_active_sessions.return_value = 3  # At limit
        mock_session_repo.get_oldest_active_session.return_value = oldest_session

        mock_session_cache = AsyncMock()

        mock_user_repo = AsyncMock()
        mock_user_repo.find_by_id.return_value = mock_user

        mock_device_enricher = AsyncMock()
        mock_device_enricher.enrich.return_value = MockDeviceResult(device_info=None)

        mock_location_enricher = AsyncMock()
        mock_location_enricher.enrich.return_value = MockLocationResult(location=None)

        mock_event_bus = AsyncMock()

        handler = CreateSessionHandler(
            session_repo=mock_session_repo,
            session_cache=mock_session_cache,
            user_repo=mock_user_repo,
            device_enricher=mock_device_enricher,
            location_enricher=mock_location_enricher,
            event_bus=mock_event_bus,
        )

        command = CreateSession(
            user_id=user_id,
            ip_address="192.168.1.1",
            user_agent="Chrome",
        )

        # Act
        result = await handler.handle(command)

        # Assert
        assert isinstance(result, Success)
        mock_session_repo.get_oldest_active_session.assert_called_once_with(user_id)
        # Oldest session should be revoked
        assert oldest_session.is_revoked is True

    @pytest.mark.asyncio
    async def test_create_session_does_not_evict_when_under_limit(self):
        """Test no eviction when user is under session limit."""
        # Arrange
        user_id = uuid7()
        mock_user = create_mock_user(user_id=user_id, max_sessions=3)

        mock_session_repo = AsyncMock()
        mock_session_repo.count_active_sessions.return_value = 2  # Under limit

        mock_session_cache = AsyncMock()

        mock_user_repo = AsyncMock()
        mock_user_repo.find_by_id.return_value = mock_user

        mock_device_enricher = AsyncMock()
        mock_device_enricher.enrich.return_value = MockDeviceResult(device_info=None)

        mock_location_enricher = AsyncMock()
        mock_location_enricher.enrich.return_value = MockLocationResult(location=None)

        mock_event_bus = AsyncMock()

        handler = CreateSessionHandler(
            session_repo=mock_session_repo,
            session_cache=mock_session_cache,
            user_repo=mock_user_repo,
            device_enricher=mock_device_enricher,
            location_enricher=mock_location_enricher,
            event_bus=mock_event_bus,
        )

        command = CreateSession(
            user_id=user_id,
            ip_address="192.168.1.1",
            user_agent="Chrome",
        )

        # Act
        await handler.handle(command)

        # Assert - Eviction method should not be called
        mock_session_repo.get_oldest_active_session.assert_not_called()

    @pytest.mark.asyncio
    async def test_create_session_no_limit_for_unlimited_tier(self):
        """Test users with unlimited tier have no session limit."""
        # Arrange
        user_id = uuid7()
        mock_user = create_mock_user(
            user_id=user_id, session_tier="unlimited", max_sessions=None
        )

        mock_session_repo = AsyncMock()
        mock_session_cache = AsyncMock()

        mock_user_repo = AsyncMock()
        mock_user_repo.find_by_id.return_value = mock_user

        mock_device_enricher = AsyncMock()
        mock_device_enricher.enrich.return_value = MockDeviceResult(device_info=None)

        mock_location_enricher = AsyncMock()
        mock_location_enricher.enrich.return_value = MockLocationResult(location=None)

        mock_event_bus = AsyncMock()

        handler = CreateSessionHandler(
            session_repo=mock_session_repo,
            session_cache=mock_session_cache,
            user_repo=mock_user_repo,
            device_enricher=mock_device_enricher,
            location_enricher=mock_location_enricher,
            event_bus=mock_event_bus,
        )

        command = CreateSession(
            user_id=user_id,
            ip_address="192.168.1.1",
            user_agent="Chrome",
        )

        # Act
        await handler.handle(command)

        # Assert - Should not check session count for unlimited users
        mock_session_repo.count_active_sessions.assert_not_called()


@pytest.mark.unit
class TestCreateSessionHandlerEvents:
    """Test domain event publishing during session creation."""

    @pytest.mark.asyncio
    async def test_create_session_publishes_created_event(self):
        """Test session creation publishes SessionCreatedEvent."""
        # Arrange
        user_id = uuid7()
        mock_user = create_mock_user(user_id=user_id, max_sessions=None)

        mock_session_repo = AsyncMock()
        mock_session_cache = AsyncMock()

        mock_user_repo = AsyncMock()
        mock_user_repo.find_by_id.return_value = mock_user

        mock_device_enricher = AsyncMock()
        mock_device_enricher.enrich.return_value = MockDeviceResult(
            device_info="Chrome on Windows"
        )

        mock_location_enricher = AsyncMock()
        mock_location_enricher.enrich.return_value = MockLocationResult(
            location="New York, US"
        )

        mock_event_bus = AsyncMock()

        handler = CreateSessionHandler(
            session_repo=mock_session_repo,
            session_cache=mock_session_cache,
            user_repo=mock_user_repo,
            device_enricher=mock_device_enricher,
            location_enricher=mock_location_enricher,
            event_bus=mock_event_bus,
        )

        command = CreateSession(
            user_id=user_id,
            ip_address="192.168.1.1",
            user_agent="Chrome",
        )

        # Act
        result = await handler.handle(command)

        # Assert
        mock_event_bus.publish.assert_called()
        published_event = mock_event_bus.publish.call_args_list[-1][0][0]
        assert isinstance(published_event, SessionCreatedEvent)
        assert published_event.user_id == user_id
        assert isinstance(result, Success)
        assert published_event.session_id == result.value.session_id
        assert published_event.device_info == "Chrome on Windows"
        assert published_event.location == "New York, US"

    @pytest.mark.asyncio
    async def test_create_session_publishes_evicted_event_on_eviction(self):
        """Test session eviction publishes SessionEvictedEvent."""
        # Arrange
        user_id = uuid7()
        mock_user = create_mock_user(user_id=user_id, max_sessions=3)
        oldest_session = create_mock_session_data(user_id=user_id)

        mock_session_repo = AsyncMock()
        mock_session_repo.count_active_sessions.return_value = 3  # At limit
        mock_session_repo.get_oldest_active_session.return_value = oldest_session

        mock_session_cache = AsyncMock()

        mock_user_repo = AsyncMock()
        mock_user_repo.find_by_id.return_value = mock_user

        mock_device_enricher = AsyncMock()
        mock_device_enricher.enrich.return_value = MockDeviceResult(device_info=None)

        mock_location_enricher = AsyncMock()
        mock_location_enricher.enrich.return_value = MockLocationResult(location=None)

        mock_event_bus = AsyncMock()

        handler = CreateSessionHandler(
            session_repo=mock_session_repo,
            session_cache=mock_session_cache,
            user_repo=mock_user_repo,
            device_enricher=mock_device_enricher,
            location_enricher=mock_location_enricher,
            event_bus=mock_event_bus,
        )

        command = CreateSession(
            user_id=user_id,
            ip_address="192.168.1.1",
            user_agent="Chrome",
        )

        # Act
        await handler.handle(command)

        # Assert - Should have published eviction event first, then created event
        assert mock_event_bus.publish.call_count == 2
        first_event = mock_event_bus.publish.call_args_list[0][0][0]
        assert isinstance(first_event, SessionEvictedEvent)
        assert first_event.user_id == user_id
        assert first_event.session_id == oldest_session.id
        assert first_event.reason == "session_limit_exceeded"
