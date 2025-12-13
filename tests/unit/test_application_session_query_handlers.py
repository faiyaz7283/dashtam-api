"""Unit tests for session query handlers.

Tests cover:
- GetSessionHandler: cache-first lookup, authorization, not found
- ListSessionsHandler: list all sessions, filter active only, current session marking

Architecture:
- Unit tests for application handlers (mocked dependencies)
- Mock repository and cache protocols
- Test handler logic, not persistence
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, Mock
from uuid_extensions import uuid7

import pytest

from src.application.queries.handlers.get_session_handler import (
    GetSessionError,
    GetSessionHandler,
    SessionResult,
)
from src.application.queries.handlers.list_sessions_handler import (
    ListSessionsHandler,
    SessionListResult,
)
from src.application.queries.session_queries import GetSession, ListUserSessions
from src.core.result import Failure, Success
from src.domain.protocols.session_repository import SessionData


def create_mock_session_data(
    session_id=None,
    user_id=None,
    device_info="Chrome on Windows",
    ip_address="192.168.1.1",
    location="New York, US",
    is_revoked=False,
):
    """Create a mock SessionData for testing."""
    mock = Mock(spec=SessionData)
    mock.id = session_id or uuid7()
    mock.user_id = user_id or uuid7()
    mock.device_info = device_info
    mock.ip_address = ip_address
    mock.location = location
    mock.created_at = datetime.now(UTC)
    mock.last_activity_at = datetime.now(UTC)
    mock.expires_at = datetime.now(UTC) + timedelta(days=30)
    mock.is_revoked = is_revoked
    return mock


@pytest.mark.unit
class TestGetSessionHandlerSuccess:
    """Test successful session retrieval scenarios."""

    @pytest.mark.asyncio
    async def test_get_session_returns_session_from_cache(self):
        """Test handler returns session found in cache."""
        user_id = uuid7()
        session_id = uuid7()
        mock_session = create_mock_session_data(session_id=session_id, user_id=user_id)

        mock_cache = AsyncMock()
        mock_cache.get.return_value = mock_session

        mock_repo = AsyncMock()

        handler = GetSessionHandler(
            session_repo=mock_repo,
            session_cache=mock_cache,
        )

        query = GetSession(session_id=session_id, user_id=user_id)

        result = await handler.handle(query)

        assert isinstance(result, Success)
        assert isinstance(result.value, SessionResult)
        assert result.value.id == session_id
        mock_cache.get.assert_called_once_with(session_id)
        mock_repo.find_by_id.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_session_falls_back_to_database(self):
        """Test handler falls back to database on cache miss."""
        user_id = uuid7()
        session_id = uuid7()
        mock_session = create_mock_session_data(session_id=session_id, user_id=user_id)

        mock_cache = AsyncMock()
        mock_cache.get.return_value = None

        mock_repo = AsyncMock()
        mock_repo.find_by_id.return_value = mock_session

        handler = GetSessionHandler(
            session_repo=mock_repo,
            session_cache=mock_cache,
        )

        query = GetSession(session_id=session_id, user_id=user_id)

        result = await handler.handle(query)

        assert isinstance(result, Success)
        mock_cache.get.assert_called_once_with(session_id)
        mock_repo.find_by_id.assert_called_once_with(session_id)

    @pytest.mark.asyncio
    async def test_get_session_populates_cache_on_miss(self):
        """Test handler populates cache when found in database."""
        user_id = uuid7()
        session_id = uuid7()
        mock_session = create_mock_session_data(
            session_id=session_id, user_id=user_id, is_revoked=False
        )

        mock_cache = AsyncMock()
        mock_cache.get.return_value = None

        mock_repo = AsyncMock()
        mock_repo.find_by_id.return_value = mock_session

        handler = GetSessionHandler(
            session_repo=mock_repo,
            session_cache=mock_cache,
        )

        query = GetSession(session_id=session_id, user_id=user_id)

        await handler.handle(query)

        mock_cache.set.assert_called_once_with(mock_session)

    @pytest.mark.asyncio
    async def test_get_session_does_not_cache_revoked_session(self):
        """Test handler doesn't cache revoked sessions."""
        user_id = uuid7()
        session_id = uuid7()
        mock_session = create_mock_session_data(
            session_id=session_id, user_id=user_id, is_revoked=True
        )

        mock_cache = AsyncMock()
        mock_cache.get.return_value = None

        mock_repo = AsyncMock()
        mock_repo.find_by_id.return_value = mock_session

        handler = GetSessionHandler(
            session_repo=mock_repo,
            session_cache=mock_cache,
        )

        query = GetSession(session_id=session_id, user_id=user_id)

        await handler.handle(query)

        mock_cache.set.assert_not_called()


@pytest.mark.unit
class TestGetSessionHandlerFailure:
    """Test session retrieval failure scenarios."""

    @pytest.mark.asyncio
    async def test_get_session_returns_not_found(self):
        """Test handler returns NOT_FOUND when session doesn't exist."""
        mock_cache = AsyncMock()
        mock_cache.get.return_value = None

        mock_repo = AsyncMock()
        mock_repo.find_by_id.return_value = None

        handler = GetSessionHandler(
            session_repo=mock_repo,
            session_cache=mock_cache,
        )

        query = GetSession(session_id=uuid7(), user_id=uuid7())

        result = await handler.handle(query)

        assert isinstance(result, Failure)
        assert result.error == GetSessionError.SESSION_NOT_FOUND

    @pytest.mark.asyncio
    async def test_get_session_returns_not_owner(self):
        """Test handler returns NOT_OWNER when user doesn't own session."""
        owner_id = uuid7()
        other_user_id = uuid7()
        session_id = uuid7()
        mock_session = create_mock_session_data(session_id=session_id, user_id=owner_id)

        mock_cache = AsyncMock()
        mock_cache.get.return_value = mock_session

        mock_repo = AsyncMock()

        handler = GetSessionHandler(
            session_repo=mock_repo,
            session_cache=mock_cache,
        )

        query = GetSession(session_id=session_id, user_id=other_user_id)

        result = await handler.handle(query)

        assert isinstance(result, Failure)
        assert result.error == GetSessionError.NOT_OWNER


@pytest.mark.unit
class TestListSessionsHandlerSuccess:
    """Test successful session listing scenarios."""

    @pytest.mark.asyncio
    async def test_list_sessions_returns_all_sessions(self):
        """Test handler returns all sessions for user."""
        user_id = uuid7()
        sessions = [
            create_mock_session_data(user_id=user_id, is_revoked=False),
            create_mock_session_data(user_id=user_id, is_revoked=False),
            create_mock_session_data(user_id=user_id, is_revoked=True),
        ]

        mock_repo = AsyncMock()
        mock_repo.find_by_user_id.return_value = sessions

        handler = ListSessionsHandler(session_repo=mock_repo)

        query = ListUserSessions(user_id=user_id, active_only=False)

        result = await handler.handle(query)

        assert isinstance(result, Success)
        assert isinstance(result.value, SessionListResult)
        assert result.value.total_count == 3
        assert result.value.active_count == 2

    @pytest.mark.asyncio
    async def test_list_sessions_with_active_only_filter(self):
        """Test handler filters to active sessions only."""
        user_id = uuid7()
        active_sessions = [
            create_mock_session_data(user_id=user_id, is_revoked=False),
            create_mock_session_data(user_id=user_id, is_revoked=False),
        ]

        mock_repo = AsyncMock()
        mock_repo.find_by_user_id.return_value = active_sessions

        handler = ListSessionsHandler(session_repo=mock_repo)

        query = ListUserSessions(user_id=user_id, active_only=True)

        await handler.handle(query)

        mock_repo.find_by_user_id.assert_called_once_with(
            user_id=user_id, active_only=True
        )

    @pytest.mark.asyncio
    async def test_list_sessions_marks_current_session(self):
        """Test handler marks current session in list."""
        user_id = uuid7()
        current_session_id = uuid7()
        other_session_id = uuid7()

        sessions = [
            create_mock_session_data(session_id=current_session_id, user_id=user_id),
            create_mock_session_data(session_id=other_session_id, user_id=user_id),
        ]

        mock_repo = AsyncMock()
        mock_repo.find_by_user_id.return_value = sessions

        handler = ListSessionsHandler(session_repo=mock_repo)

        query = ListUserSessions(
            user_id=user_id,
            active_only=False,
            current_session_id=current_session_id,
        )

        result = await handler.handle(query)

        assert isinstance(result, Success)
        current = next(s for s in result.value.sessions if s.id == current_session_id)
        other = next(s for s in result.value.sessions if s.id == other_session_id)
        assert current.is_current is True
        assert other.is_current is False

    @pytest.mark.asyncio
    async def test_list_sessions_returns_empty_list(self):
        """Test handler returns empty list when no sessions."""
        user_id = uuid7()

        mock_repo = AsyncMock()
        mock_repo.find_by_user_id.return_value = []

        handler = ListSessionsHandler(session_repo=mock_repo)

        query = ListUserSessions(user_id=user_id, active_only=False)

        result = await handler.handle(query)

        assert isinstance(result, Success)
        assert result.value.total_count == 0
        assert result.value.active_count == 0
        assert result.value.sessions == []
