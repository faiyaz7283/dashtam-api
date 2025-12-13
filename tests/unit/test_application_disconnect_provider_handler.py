"""Unit tests for DisconnectProviderHandler.

Tests the disconnect provider command handler business logic.
Uses mocked repository and event bus for isolation.

Reference:
    - docs/architecture/cqrs-pattern.md (Testing Strategy)
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest
from uuid_extensions import uuid7

from src.application.commands.handlers.disconnect_provider_handler import (
    DisconnectProviderError,
    DisconnectProviderHandler,
)
from src.application.commands.provider_commands import DisconnectProvider
from src.core.result import Failure, Success
from src.domain.entities.provider_connection import ProviderConnection
from src.domain.enums.connection_status import ConnectionStatus
from src.domain.enums.credential_type import CredentialType
from src.domain.events.provider_events import (
    ProviderDisconnectionAttempted,
    ProviderDisconnectionFailed,
    ProviderDisconnectionSucceeded,
)
from src.domain.protocols.event_bus_protocol import EventBusProtocol
from src.domain.protocols.provider_connection_repository import (
    ProviderConnectionRepository,
)
from src.domain.value_objects.provider_credentials import ProviderCredentials


# =============================================================================
# Test Fixtures
# =============================================================================


def create_test_connection(
    connection_id: None = None,
    user_id: None = None,
    status: ConnectionStatus = ConnectionStatus.ACTIVE,
) -> ProviderConnection:
    """Create a test provider connection."""
    return ProviderConnection(
        id=connection_id or uuid7(),
        user_id=user_id or uuid7(),
        provider_id=uuid7(),
        provider_slug="schwab",
        credentials=ProviderCredentials(
            encrypted_data=b"test_data",
            credential_type=CredentialType.OAUTH2,
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        ),
        status=status,
        alias="Test Account",
        last_sync_at=datetime.now(UTC),
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


def create_handler(
    repo_mock: AsyncMock | None = None,
    event_bus_mock: AsyncMock | None = None,
) -> tuple[DisconnectProviderHandler, AsyncMock, AsyncMock]:
    """Create handler with mocked dependencies."""
    repo = repo_mock or AsyncMock(spec=ProviderConnectionRepository)
    event_bus = event_bus_mock or AsyncMock(spec=EventBusProtocol)

    handler = DisconnectProviderHandler(
        connection_repo=repo,
        event_bus=event_bus,
    )

    return handler, repo, event_bus


# =============================================================================
# Success Tests
# =============================================================================


@pytest.mark.asyncio
async def test_disconnect_provider_success():
    """Test successful provider disconnection."""
    # Arrange
    handler, repo, event_bus = create_handler()
    user_id = uuid7()
    connection = create_test_connection(user_id=user_id)
    repo.find_by_id.return_value = connection

    command = DisconnectProvider(
        user_id=user_id,
        connection_id=connection.id,
    )

    # Act
    result = await handler.handle(command)

    # Assert
    assert isinstance(result, Success)
    assert result.value is None  # Returns None on success

    # Verify repository interactions (uses save, not delete - keeps record)
    repo.find_by_id.assert_called_once_with(connection.id)
    repo.save.assert_called_once()

    # Verify connection transitioned to DISCONNECTED
    saved_connection = repo.save.call_args[0][0]
    assert saved_connection.status == ConnectionStatus.DISCONNECTED

    # Verify 2 events emitted (Attempted + Succeeded)
    assert event_bus.publish.call_count == 2


@pytest.mark.asyncio
async def test_disconnect_provider_emits_attempted_event():
    """Test that handler emits ProviderDisconnectionAttempted event first."""
    # Arrange
    handler, repo, event_bus = create_handler()
    user_id = uuid7()
    connection = create_test_connection(user_id=user_id)
    repo.find_by_id.return_value = connection

    command = DisconnectProvider(
        user_id=user_id,
        connection_id=connection.id,
    )

    # Act
    await handler.handle(command)

    # Assert - First event should be Attempted
    first_event = event_bus.publish.call_args_list[0][0][0]
    assert isinstance(first_event, ProviderDisconnectionAttempted)
    assert first_event.user_id == user_id
    assert first_event.connection_id == connection.id


@pytest.mark.asyncio
async def test_disconnect_provider_emits_succeeded_event():
    """Test that handler emits ProviderDisconnectionSucceeded event on success."""
    # Arrange
    handler, repo, event_bus = create_handler()
    user_id = uuid7()
    connection = create_test_connection(user_id=user_id)
    repo.find_by_id.return_value = connection

    command = DisconnectProvider(
        user_id=user_id,
        connection_id=connection.id,
    )

    # Act
    await handler.handle(command)

    # Assert - Second event should be Succeeded
    second_event = event_bus.publish.call_args_list[1][0][0]
    assert isinstance(second_event, ProviderDisconnectionSucceeded)
    assert second_event.user_id == user_id
    assert second_event.connection_id == connection.id
    assert second_event.provider_slug == "schwab"


# =============================================================================
# Authorization Error Tests
# =============================================================================


@pytest.mark.asyncio
async def test_disconnect_provider_fails_when_connection_not_found():
    """Test disconnection fails when connection doesn't exist."""
    # Arrange
    handler, repo, event_bus = create_handler()
    repo.find_by_id.return_value = None

    command = DisconnectProvider(
        user_id=uuid7(),
        connection_id=uuid7(),
    )

    # Act
    result = await handler.handle(command)

    # Assert
    assert isinstance(result, Failure)
    assert result.error == DisconnectProviderError.CONNECTION_NOT_FOUND
    repo.save.assert_not_called()


@pytest.mark.asyncio
async def test_disconnect_provider_fails_when_user_unauthorized():
    """Test disconnection fails when user doesn't own the connection."""
    # Arrange
    handler, repo, event_bus = create_handler()
    connection = create_test_connection(user_id=uuid7())  # Different user
    repo.find_by_id.return_value = connection

    command = DisconnectProvider(
        user_id=uuid7(),  # Different user
        connection_id=connection.id,
    )

    # Act
    result = await handler.handle(command)

    # Assert
    assert isinstance(result, Failure)
    assert result.error == DisconnectProviderError.NOT_OWNED_BY_USER
    repo.save.assert_not_called()


@pytest.mark.asyncio
async def test_disconnect_provider_emits_failed_event_on_not_found():
    """Test that handler emits ProviderDisconnectionFailed when not found."""
    # Arrange
    handler, repo, event_bus = create_handler()
    repo.find_by_id.return_value = None

    command = DisconnectProvider(
        user_id=uuid7(),
        connection_id=uuid7(),
    )

    # Act
    await handler.handle(command)

    # Assert - Should emit Attempted then Failed
    assert event_bus.publish.call_count == 2
    second_event = event_bus.publish.call_args_list[1][0][0]
    assert isinstance(second_event, ProviderDisconnectionFailed)
    assert second_event.reason == DisconnectProviderError.CONNECTION_NOT_FOUND


# =============================================================================
# Database Error Tests
# =============================================================================


@pytest.mark.asyncio
async def test_disconnect_provider_handles_database_save_error():
    """Test disconnection handles database save error."""
    # Arrange
    handler, repo, event_bus = create_handler()
    user_id = uuid7()
    connection = create_test_connection(user_id=user_id)
    repo.find_by_id.return_value = connection
    repo.save.side_effect = Exception("Foreign key constraint")

    command = DisconnectProvider(
        user_id=user_id,
        connection_id=connection.id,
    )

    # Act
    result = await handler.handle(command)

    # Assert
    assert isinstance(result, Failure)
    assert DisconnectProviderError.DATABASE_ERROR in result.error


@pytest.mark.asyncio
async def test_disconnect_provider_emits_failed_event_on_save_error():
    """Test that handler emits ProviderDisconnectionFailed on save error."""
    # Arrange
    handler, repo, event_bus = create_handler()
    user_id = uuid7()
    connection = create_test_connection(user_id=user_id)
    repo.find_by_id.return_value = connection
    repo.save.side_effect = Exception("DB save error")

    command = DisconnectProvider(
        user_id=user_id,
        connection_id=connection.id,
    )

    # Act
    await handler.handle(command)

    # Assert - Should emit Attempted then Failed (after save error)
    assert event_bus.publish.call_count == 2
    second_event = event_bus.publish.call_args_list[1][0][0]
    assert isinstance(second_event, ProviderDisconnectionFailed)
    assert "Database error" in second_event.reason
