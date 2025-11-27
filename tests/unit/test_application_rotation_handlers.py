"""Unit tests for token rotation handlers.

Tests cover:
- TriggerGlobalTokenRotationHandler: global version increment, event emission
- TriggerUserTokenRotationHandler: user version increment, user not found

Architecture:
- Unit tests for application handlers (mocked dependencies)
- Mock repository and event bus protocols
- Test handler logic, not persistence
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from src.application.commands.handlers.trigger_global_rotation_handler import (
    TriggerGlobalTokenRotationHandler,
)
from src.application.commands.handlers.trigger_user_rotation_handler import (
    TriggerUserTokenRotationHandler,
)
from src.application.commands.rotation_commands import (
    TriggerGlobalTokenRotation,
    TriggerUserTokenRotation,
)
from src.core.result import Failure, Success
from src.domain.entities.security_config import SecurityConfig
from src.domain.events.auth_events import (
    GlobalTokenRotationAttempted,
    GlobalTokenRotationFailed,
    GlobalTokenRotationSucceeded,
    UserTokenRotationAttempted,
    UserTokenRotationFailed,
    UserTokenRotationSucceeded,
)


def _create_mock_security_config(
    global_min_token_version: int = 1,
    grace_period_seconds: int = 300,
) -> SecurityConfig:
    """Create a mock SecurityConfig for testing."""
    return SecurityConfig(
        id=1,
        global_min_token_version=global_min_token_version,
        grace_period_seconds=grace_period_seconds,
        last_rotation_at=None,
        last_rotation_reason=None,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


def _create_mock_user(
    user_id=None,
    email: str = "test@example.com",
    min_token_version: int = 1,
):
    """Create a mock User for testing."""
    mock = Mock()
    mock.id = user_id or uuid4()
    mock.email = email
    mock.min_token_version = min_token_version
    mock.updated_at = datetime.now(UTC)
    return mock


# =============================================================================
# TriggerGlobalTokenRotationHandler Tests
# =============================================================================


@pytest.mark.unit
class TestTriggerGlobalRotationHandlerSuccess:
    """Test successful global rotation scenarios."""

    @pytest.mark.asyncio
    async def test_global_rotation_returns_success(self):
        """Test successful rotation returns Success with version info."""
        mock_config = _create_mock_security_config(global_min_token_version=1)
        updated_config = _create_mock_security_config(
            global_min_token_version=2,
            grace_period_seconds=300,
        )

        mock_repo = AsyncMock()
        mock_repo.get_or_create_default.return_value = mock_config
        mock_repo.update_global_version.return_value = updated_config

        mock_event_bus = AsyncMock()

        handler = TriggerGlobalTokenRotationHandler(
            security_config_repo=mock_repo,
            event_bus=mock_event_bus,
        )

        command = TriggerGlobalTokenRotation(
            reason="Security breach detected",
            triggered_by="admin",
        )

        result = await handler.handle(command)

        assert isinstance(result, Success)
        assert result.value.previous_version == 1
        assert result.value.new_version == 2
        assert result.value.grace_period_seconds == 300

    @pytest.mark.asyncio
    async def test_global_rotation_increments_version(self):
        """Test rotation increments global_min_token_version."""
        mock_config = _create_mock_security_config(global_min_token_version=5)
        updated_config = _create_mock_security_config(global_min_token_version=6)

        mock_repo = AsyncMock()
        mock_repo.get_or_create_default.return_value = mock_config
        mock_repo.update_global_version.return_value = updated_config

        mock_event_bus = AsyncMock()

        handler = TriggerGlobalTokenRotationHandler(
            security_config_repo=mock_repo,
            event_bus=mock_event_bus,
        )

        command = TriggerGlobalTokenRotation(
            reason="Patch applied",
            triggered_by="admin",
        )

        await handler.handle(command)

        # Verify update_global_version was called with incremented version
        mock_repo.update_global_version.assert_called_once()
        call_args = mock_repo.update_global_version.call_args
        assert call_args.kwargs["new_version"] == 6
        assert call_args.kwargs["reason"] == "Patch applied"

    @pytest.mark.asyncio
    async def test_global_rotation_emits_attempted_event(self):
        """Test rotation emits GlobalTokenRotationAttempted event first."""
        mock_config = _create_mock_security_config()
        mock_repo = AsyncMock()
        mock_repo.get_or_create_default.return_value = mock_config
        mock_repo.update_global_version.return_value = mock_config

        mock_event_bus = AsyncMock()

        handler = TriggerGlobalTokenRotationHandler(
            security_config_repo=mock_repo,
            event_bus=mock_event_bus,
        )

        command = TriggerGlobalTokenRotation(
            reason="Test reason",
            triggered_by="admin_user",
        )

        await handler.handle(command)

        # First call should be ATTEMPTED event
        first_call = mock_event_bus.publish.call_args_list[0]
        event = first_call[0][0]
        assert isinstance(event, GlobalTokenRotationAttempted)
        assert event.triggered_by == "admin_user"
        assert event.reason == "Test reason"

    @pytest.mark.asyncio
    async def test_global_rotation_emits_succeeded_event(self):
        """Test successful rotation emits GlobalTokenRotationSucceeded event."""
        mock_config = _create_mock_security_config(global_min_token_version=3)
        updated_config = _create_mock_security_config(
            global_min_token_version=4,
            grace_period_seconds=600,
        )

        mock_repo = AsyncMock()
        mock_repo.get_or_create_default.return_value = mock_config
        mock_repo.update_global_version.return_value = updated_config

        mock_event_bus = AsyncMock()

        handler = TriggerGlobalTokenRotationHandler(
            security_config_repo=mock_repo,
            event_bus=mock_event_bus,
        )

        command = TriggerGlobalTokenRotation(
            reason="Breach response",
            triggered_by="security_admin",
        )

        await handler.handle(command)

        # Second call should be SUCCEEDED event
        second_call = mock_event_bus.publish.call_args_list[1]
        event = second_call[0][0]
        assert isinstance(event, GlobalTokenRotationSucceeded)
        assert event.triggered_by == "security_admin"
        assert event.previous_version == 3
        assert event.new_version == 4
        assert event.reason == "Breach response"
        assert event.grace_period_seconds == 600


@pytest.mark.unit
class TestTriggerGlobalRotationHandlerFailure:
    """Test global rotation failure scenarios."""

    @pytest.mark.asyncio
    async def test_global_rotation_emits_failed_event_on_error(self):
        """Test rotation emits GlobalTokenRotationFailed on repository error."""
        mock_repo = AsyncMock()
        mock_repo.get_or_create_default.side_effect = Exception("Database error")

        mock_event_bus = AsyncMock()

        handler = TriggerGlobalTokenRotationHandler(
            security_config_repo=mock_repo,
            event_bus=mock_event_bus,
        )

        command = TriggerGlobalTokenRotation(
            reason="Test",
            triggered_by="admin",
        )

        result = await handler.handle(command)

        assert isinstance(result, Failure)
        assert "Database error" in result.error

        # Check FAILED event was emitted
        failed_call = mock_event_bus.publish.call_args_list[-1]
        event = failed_call[0][0]
        assert isinstance(event, GlobalTokenRotationFailed)
        assert "Database error" in event.failure_reason

    @pytest.mark.asyncio
    async def test_global_rotation_returns_failure_on_update_error(self):
        """Test rotation returns Failure when update fails."""
        mock_config = _create_mock_security_config()
        mock_repo = AsyncMock()
        mock_repo.get_or_create_default.return_value = mock_config
        mock_repo.update_global_version.side_effect = Exception("Update failed")

        mock_event_bus = AsyncMock()

        handler = TriggerGlobalTokenRotationHandler(
            security_config_repo=mock_repo,
            event_bus=mock_event_bus,
        )

        command = TriggerGlobalTokenRotation(
            reason="Test",
            triggered_by="admin",
        )

        result = await handler.handle(command)

        assert isinstance(result, Failure)
        assert "Update failed" in result.error


# =============================================================================
# TriggerUserTokenRotationHandler Tests
# =============================================================================


@pytest.mark.unit
class TestTriggerUserRotationHandlerSuccess:
    """Test successful per-user rotation scenarios."""

    @pytest.mark.asyncio
    async def test_user_rotation_returns_success(self):
        """Test successful rotation returns Success with user version info."""
        user_id = uuid4()
        mock_user = _create_mock_user(user_id=user_id, min_token_version=1)

        mock_repo = AsyncMock()
        mock_repo.find_by_id.return_value = mock_user

        mock_event_bus = AsyncMock()

        handler = TriggerUserTokenRotationHandler(
            user_repo=mock_repo,
            event_bus=mock_event_bus,
        )

        command = TriggerUserTokenRotation(
            user_id=user_id,
            reason="Password changed",
            triggered_by="user_self",
        )

        result = await handler.handle(command)

        assert isinstance(result, Success)
        assert result.value.user_id == user_id
        assert result.value.previous_version == 1
        assert result.value.new_version == 2

    @pytest.mark.asyncio
    async def test_user_rotation_increments_user_version(self):
        """Test rotation increments user.min_token_version."""
        user_id = uuid4()
        mock_user = _create_mock_user(user_id=user_id, min_token_version=3)

        mock_repo = AsyncMock()
        mock_repo.find_by_id.return_value = mock_user

        mock_event_bus = AsyncMock()

        handler = TriggerUserTokenRotationHandler(
            user_repo=mock_repo,
            event_bus=mock_event_bus,
        )

        command = TriggerUserTokenRotation(
            user_id=user_id,
            reason="Suspicious activity",
            triggered_by="admin",
        )

        await handler.handle(command)

        # Verify version was incremented
        assert mock_user.min_token_version == 4
        mock_repo.update.assert_called_once_with(mock_user)

    @pytest.mark.asyncio
    async def test_user_rotation_emits_attempted_event(self):
        """Test rotation emits UserTokenRotationAttempted event first."""
        user_id = uuid4()
        mock_user = _create_mock_user(user_id=user_id)

        mock_repo = AsyncMock()
        mock_repo.find_by_id.return_value = mock_user

        mock_event_bus = AsyncMock()

        handler = TriggerUserTokenRotationHandler(
            user_repo=mock_repo,
            event_bus=mock_event_bus,
        )

        command = TriggerUserTokenRotation(
            user_id=user_id,
            reason="Log out everywhere",
            triggered_by="user_self",
        )

        await handler.handle(command)

        # First call should be ATTEMPTED event
        first_call = mock_event_bus.publish.call_args_list[0]
        event = first_call[0][0]
        assert isinstance(event, UserTokenRotationAttempted)
        assert event.user_id == user_id
        assert event.triggered_by == "user_self"
        assert event.reason == "Log out everywhere"

    @pytest.mark.asyncio
    async def test_user_rotation_emits_succeeded_event(self):
        """Test successful rotation emits UserTokenRotationSucceeded event."""
        user_id = uuid4()
        mock_user = _create_mock_user(user_id=user_id, min_token_version=2)

        mock_repo = AsyncMock()
        mock_repo.find_by_id.return_value = mock_user

        mock_event_bus = AsyncMock()

        handler = TriggerUserTokenRotationHandler(
            user_repo=mock_repo,
            event_bus=mock_event_bus,
        )

        command = TriggerUserTokenRotation(
            user_id=user_id,
            reason="Admin action",
            triggered_by="admin_123",
        )

        await handler.handle(command)

        # Second call should be SUCCEEDED event
        second_call = mock_event_bus.publish.call_args_list[1]
        event = second_call[0][0]
        assert isinstance(event, UserTokenRotationSucceeded)
        assert event.user_id == user_id
        assert event.triggered_by == "admin_123"
        assert event.previous_version == 2
        assert event.new_version == 3
        assert event.reason == "Admin action"


@pytest.mark.unit
class TestTriggerUserRotationHandlerFailure:
    """Test per-user rotation failure scenarios."""

    @pytest.mark.asyncio
    async def test_user_rotation_returns_not_found(self):
        """Test rotation returns Failure when user doesn't exist."""
        user_id = uuid4()

        mock_repo = AsyncMock()
        mock_repo.find_by_id.return_value = None

        mock_event_bus = AsyncMock()

        handler = TriggerUserTokenRotationHandler(
            user_repo=mock_repo,
            event_bus=mock_event_bus,
        )

        command = TriggerUserTokenRotation(
            user_id=user_id,
            reason="Test",
            triggered_by="admin",
        )

        result = await handler.handle(command)

        assert isinstance(result, Failure)
        assert result.error == "user_not_found"

    @pytest.mark.asyncio
    async def test_user_rotation_emits_failed_event_for_not_found(self):
        """Test rotation emits UserTokenRotationFailed when user not found."""
        user_id = uuid4()

        mock_repo = AsyncMock()
        mock_repo.find_by_id.return_value = None

        mock_event_bus = AsyncMock()

        handler = TriggerUserTokenRotationHandler(
            user_repo=mock_repo,
            event_bus=mock_event_bus,
        )

        command = TriggerUserTokenRotation(
            user_id=user_id,
            reason="Test reason",
            triggered_by="admin",
        )

        await handler.handle(command)

        # Check FAILED event was emitted (second call after ATTEMPTED)
        failed_call = mock_event_bus.publish.call_args_list[1]
        event = failed_call[0][0]
        assert isinstance(event, UserTokenRotationFailed)
        assert event.user_id == user_id
        assert event.failure_reason == "user_not_found"
