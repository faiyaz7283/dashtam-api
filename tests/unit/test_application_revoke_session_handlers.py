"""Unit tests for session revoke handlers.

Tests cover:
- RevokeSessionHandler: single session revocation, authorization, already revoked
- RevokeAllSessionsHandler: bulk revocation, except_session_id, cache clearing

Architecture:
- Unit tests for application handlers (mocked dependencies)
- Mock repository, cache, and event bus protocols
- Test handler logic, not persistence
"""

from unittest.mock import AsyncMock, Mock
from uuid_extensions import uuid7

import pytest

from src.application.commands.handlers.revoke_all_sessions_handler import (
    RevokeAllSessionsHandler,
)
from src.application.commands.handlers.revoke_session_handler import (
    RevokeSessionError,
    RevokeSessionHandler,
)
from src.application.commands.session_commands import (
    RevokeAllUserSessions,
    RevokeSession,
)
from src.core.result import Failure, Success
from src.domain.events.session_events import (
    AllSessionsRevocationAttempted,
    AllSessionsRevokedEvent,
    SessionRevocationAttempted,
    SessionRevocationFailed,
    SessionRevokedEvent,
)
from src.domain.protocols.session_repository import SessionData


def create_mock_session_data(
    session_id=None,
    user_id=None,
    device_info="Chrome on Windows",
    is_revoked=False,
):
    """Create a mock SessionData for testing."""
    mock = Mock(spec=SessionData)
    mock.id = session_id or uuid7()
    mock.user_id = user_id or uuid7()
    mock.device_info = device_info
    mock.is_revoked = is_revoked
    mock.revoked_at = None
    mock.revoked_reason = None
    return mock


@pytest.mark.unit
class TestRevokeSessionHandlerSuccess:
    """Test successful session revocation scenarios."""

    @pytest.mark.asyncio
    async def test_revoke_session_returns_success(self):
        """Test successful revocation returns Success with session_id."""
        user_id = uuid7()
        session_id = uuid7()
        mock_session = create_mock_session_data(session_id=session_id, user_id=user_id)

        mock_repo = AsyncMock()
        mock_repo.find_by_id.return_value = mock_session

        mock_cache = AsyncMock()
        mock_event_bus = AsyncMock()

        handler = RevokeSessionHandler(
            session_repo=mock_repo,
            session_cache=mock_cache,
            event_bus=mock_event_bus,
        )

        command = RevokeSession(
            session_id=session_id,
            user_id=user_id,
            reason="user_logout",
        )

        result = await handler.handle(command)

        assert isinstance(result, Success)
        assert result.value == session_id

    @pytest.mark.asyncio
    async def test_revoke_session_marks_session_revoked(self):
        """Test revocation marks session as revoked."""
        user_id = uuid7()
        session_id = uuid7()
        mock_session = create_mock_session_data(session_id=session_id, user_id=user_id)

        mock_repo = AsyncMock()
        mock_repo.find_by_id.return_value = mock_session

        mock_cache = AsyncMock()
        mock_event_bus = AsyncMock()

        handler = RevokeSessionHandler(
            session_repo=mock_repo,
            session_cache=mock_cache,
            event_bus=mock_event_bus,
        )

        command = RevokeSession(
            session_id=session_id,
            user_id=user_id,
            reason="password_changed",
        )

        await handler.handle(command)

        assert mock_session.is_revoked is True
        assert mock_session.revoked_reason == "password_changed"
        mock_repo.save.assert_called_once_with(mock_session)

    @pytest.mark.asyncio
    async def test_revoke_session_removes_from_cache(self):
        """Test revocation removes session from cache."""
        user_id = uuid7()
        session_id = uuid7()
        mock_session = create_mock_session_data(session_id=session_id, user_id=user_id)

        mock_repo = AsyncMock()
        mock_repo.find_by_id.return_value = mock_session

        mock_cache = AsyncMock()
        mock_event_bus = AsyncMock()

        handler = RevokeSessionHandler(
            session_repo=mock_repo,
            session_cache=mock_cache,
            event_bus=mock_event_bus,
        )

        command = RevokeSession(
            session_id=session_id,
            user_id=user_id,
            reason="user_logout",
        )

        await handler.handle(command)

        mock_cache.delete.assert_called_once_with(session_id)
        mock_cache.remove_user_session.assert_called_once_with(user_id, session_id)

    @pytest.mark.asyncio
    async def test_revoke_session_publishes_3_state_events(self):
        """Test revocation publishes ATTEMPTED and SUCCEEDED events."""
        user_id = uuid7()
        session_id = uuid7()
        mock_session = create_mock_session_data(
            session_id=session_id,
            user_id=user_id,
            device_info="Safari on macOS",
        )

        mock_repo = AsyncMock()
        mock_repo.find_by_id.return_value = mock_session

        mock_cache = AsyncMock()
        mock_event_bus = AsyncMock()

        handler = RevokeSessionHandler(
            session_repo=mock_repo,
            session_cache=mock_cache,
            event_bus=mock_event_bus,
        )

        command = RevokeSession(
            session_id=session_id,
            user_id=user_id,
            reason="security_concern",
        )

        await handler.handle(command)

        # Verify 2 events: ATTEMPTED + SUCCEEDED
        assert mock_event_bus.publish.call_count == 2

        # First call: ATTEMPTED
        attempted_event = mock_event_bus.publish.call_args_list[0][0][0]
        assert isinstance(attempted_event, SessionRevocationAttempted)
        assert attempted_event.session_id == session_id
        assert attempted_event.user_id == user_id

        # Second call: SUCCEEDED (SessionRevokedEvent)
        succeeded_event = mock_event_bus.publish.call_args_list[1][0][0]
        assert isinstance(succeeded_event, SessionRevokedEvent)
        assert succeeded_event.session_id == session_id
        assert succeeded_event.user_id == user_id
        assert succeeded_event.reason == "security_concern"
        assert succeeded_event.device_info == "Safari on macOS"


@pytest.mark.unit
class TestRevokeSessionHandlerFailure:
    """Test session revocation failure scenarios."""

    @pytest.mark.asyncio
    async def test_revoke_session_returns_not_found(self):
        """Test revocation fails with NOT_FOUND when session doesn't exist."""
        session_id = uuid7()
        user_id = uuid7()

        mock_repo = AsyncMock()
        mock_repo.find_by_id.return_value = None

        mock_cache = AsyncMock()
        mock_event_bus = AsyncMock()

        handler = RevokeSessionHandler(
            session_repo=mock_repo,
            session_cache=mock_cache,
            event_bus=mock_event_bus,
        )

        command = RevokeSession(
            session_id=session_id,
            user_id=user_id,
            reason="user_logout",
        )

        result = await handler.handle(command)

        assert isinstance(result, Failure)
        assert result.error == RevokeSessionError.SESSION_NOT_FOUND

        # Verify ATTEMPTED + FAILED events emitted
        assert mock_event_bus.publish.call_count == 2
        attempted_event = mock_event_bus.publish.call_args_list[0][0][0]
        assert isinstance(attempted_event, SessionRevocationAttempted)
        failed_event = mock_event_bus.publish.call_args_list[1][0][0]
        assert isinstance(failed_event, SessionRevocationFailed)
        assert failed_event.failure_reason == "session_not_found"

    @pytest.mark.asyncio
    async def test_revoke_session_returns_not_owner(self):
        """Test revocation fails with NOT_OWNER when user doesn't own session."""
        owner_id = uuid7()
        other_user_id = uuid7()
        session_id = uuid7()
        mock_session = create_mock_session_data(session_id=session_id, user_id=owner_id)

        mock_repo = AsyncMock()
        mock_repo.find_by_id.return_value = mock_session

        mock_cache = AsyncMock()
        mock_event_bus = AsyncMock()

        handler = RevokeSessionHandler(
            session_repo=mock_repo,
            session_cache=mock_cache,
            event_bus=mock_event_bus,
        )

        command = RevokeSession(
            session_id=session_id,
            user_id=other_user_id,
            reason="user_logout",
        )

        result = await handler.handle(command)

        assert isinstance(result, Failure)
        assert result.error == RevokeSessionError.NOT_OWNER

    @pytest.mark.asyncio
    async def test_revoke_session_returns_already_revoked(self):
        """Test revocation fails with ALREADY_REVOKED for revoked session."""
        user_id = uuid7()
        session_id = uuid7()
        mock_session = create_mock_session_data(
            session_id=session_id, user_id=user_id, is_revoked=True
        )

        mock_repo = AsyncMock()
        mock_repo.find_by_id.return_value = mock_session

        mock_cache = AsyncMock()
        mock_event_bus = AsyncMock()

        handler = RevokeSessionHandler(
            session_repo=mock_repo,
            session_cache=mock_cache,
            event_bus=mock_event_bus,
        )

        command = RevokeSession(
            session_id=session_id,
            user_id=user_id,
            reason="user_logout",
        )

        result = await handler.handle(command)

        assert isinstance(result, Failure)
        assert result.error == RevokeSessionError.ALREADY_REVOKED


@pytest.mark.unit
class TestRevokeAllSessionsHandlerSuccess:
    """Test successful bulk session revocation scenarios."""

    @pytest.mark.asyncio
    async def test_revoke_all_sessions_returns_count(self):
        """Test bulk revocation returns count of revoked sessions."""
        user_id = uuid7()

        mock_repo = AsyncMock()
        mock_repo.revoke_all_for_user.return_value = 5

        mock_cache = AsyncMock()
        mock_event_bus = AsyncMock()

        handler = RevokeAllSessionsHandler(
            session_repo=mock_repo,
            session_cache=mock_cache,
            event_bus=mock_event_bus,
        )

        command = RevokeAllUserSessions(
            user_id=user_id,
            reason="password_changed",
        )

        result = await handler.handle(command)

        assert isinstance(result, Success)
        assert result.value == 5

    @pytest.mark.asyncio
    async def test_revoke_all_sessions_clears_cache(self):
        """Test bulk revocation clears all user sessions from cache."""
        user_id = uuid7()

        mock_repo = AsyncMock()
        mock_repo.revoke_all_for_user.return_value = 3

        mock_cache = AsyncMock()
        mock_event_bus = AsyncMock()

        handler = RevokeAllSessionsHandler(
            session_repo=mock_repo,
            session_cache=mock_cache,
            event_bus=mock_event_bus,
        )

        command = RevokeAllUserSessions(
            user_id=user_id,
            reason="security_event",
        )

        await handler.handle(command)

        mock_cache.delete_all_for_user.assert_called_once_with(user_id)

    @pytest.mark.asyncio
    async def test_revoke_all_sessions_publishes_3_state_events(self):
        """Test bulk revocation publishes ATTEMPTED and SUCCEEDED events."""
        user_id = uuid7()

        mock_repo = AsyncMock()
        mock_repo.revoke_all_for_user.return_value = 3

        mock_cache = AsyncMock()
        mock_event_bus = AsyncMock()

        handler = RevokeAllSessionsHandler(
            session_repo=mock_repo,
            session_cache=mock_cache,
            event_bus=mock_event_bus,
        )

        command = RevokeAllUserSessions(
            user_id=user_id,
            reason="logout_everywhere",
        )

        await handler.handle(command)

        # Verify 2 events: ATTEMPTED + SUCCEEDED
        assert mock_event_bus.publish.call_count == 2

        # First call: ATTEMPTED
        attempted_event = mock_event_bus.publish.call_args_list[0][0][0]
        assert isinstance(attempted_event, AllSessionsRevocationAttempted)
        assert attempted_event.user_id == user_id
        assert attempted_event.reason == "logout_everywhere"

        # Second call: SUCCEEDED (AllSessionsRevokedEvent)
        succeeded_event = mock_event_bus.publish.call_args_list[1][0][0]
        assert isinstance(succeeded_event, AllSessionsRevokedEvent)
        assert succeeded_event.user_id == user_id
        assert succeeded_event.reason == "logout_everywhere"
        assert succeeded_event.session_count == 3

    @pytest.mark.asyncio
    async def test_revoke_all_sessions_with_except_session_id(self):
        """Test bulk revocation excludes current session."""
        user_id = uuid7()
        current_session_id = uuid7()
        excluded_session = create_mock_session_data(
            session_id=current_session_id, user_id=user_id, is_revoked=False
        )

        mock_repo = AsyncMock()
        mock_repo.revoke_all_for_user.return_value = 4
        mock_repo.find_by_id.return_value = excluded_session

        mock_cache = AsyncMock()
        mock_event_bus = AsyncMock()

        handler = RevokeAllSessionsHandler(
            session_repo=mock_repo,
            session_cache=mock_cache,
            event_bus=mock_event_bus,
        )

        command = RevokeAllUserSessions(
            user_id=user_id,
            reason="password_changed",
            except_session_id=current_session_id,
        )

        await handler.handle(command)

        mock_repo.revoke_all_for_user.assert_called_once_with(
            user_id=user_id,
            reason="password_changed",
            except_session_id=current_session_id,
        )

    @pytest.mark.asyncio
    async def test_revoke_all_sessions_re_caches_excluded_session(self):
        """Test excluded session is re-cached after bulk clear."""
        user_id = uuid7()
        current_session_id = uuid7()
        excluded_session = create_mock_session_data(
            session_id=current_session_id, user_id=user_id, is_revoked=False
        )

        mock_repo = AsyncMock()
        mock_repo.revoke_all_for_user.return_value = 4
        mock_repo.find_by_id.return_value = excluded_session

        mock_cache = AsyncMock()
        mock_event_bus = AsyncMock()

        handler = RevokeAllSessionsHandler(
            session_repo=mock_repo,
            session_cache=mock_cache,
            event_bus=mock_event_bus,
        )

        command = RevokeAllUserSessions(
            user_id=user_id,
            reason="password_changed",
            except_session_id=current_session_id,
        )

        await handler.handle(command)

        # Cache should be cleared, then excluded session re-cached
        mock_cache.delete_all_for_user.assert_called_once()
        mock_cache.set.assert_called_once_with(excluded_session)

    @pytest.mark.asyncio
    async def test_revoke_all_sessions_returns_zero_when_no_sessions(self):
        """Test bulk revocation returns zero when no sessions to revoke."""
        user_id = uuid7()

        mock_repo = AsyncMock()
        mock_repo.revoke_all_for_user.return_value = 0

        mock_cache = AsyncMock()
        mock_event_bus = AsyncMock()

        handler = RevokeAllSessionsHandler(
            session_repo=mock_repo,
            session_cache=mock_cache,
            event_bus=mock_event_bus,
        )

        command = RevokeAllUserSessions(
            user_id=user_id,
            reason="test",
        )

        result = await handler.handle(command)

        assert isinstance(result, Success)
        assert result.value == 0
