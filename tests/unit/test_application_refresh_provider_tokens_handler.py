"""Unit tests for RefreshProviderTokensHandler.

Tests the refresh provider tokens command handler business logic.
Uses mocked repository and event bus for isolation.

Reference:
    - docs/architecture/cqrs-pattern.md (Testing Strategy)
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest
from uuid_extensions import uuid7

from src.application.commands.handlers.refresh_provider_tokens_handler import (
    RefreshProviderTokensError,
    RefreshProviderTokensHandler,
)
from src.application.commands.provider_commands import RefreshProviderTokens
from src.core.result import Failure, Success
from src.domain.entities.provider_connection import ProviderConnection
from src.domain.enums.connection_status import ConnectionStatus
from src.domain.enums.credential_type import CredentialType
from src.domain.events.provider_events import (
    ProviderTokenRefreshAttempted,
    ProviderTokenRefreshFailed,
    ProviderTokenRefreshSucceeded,
)
from src.domain.protocols.event_bus_protocol import EventBusProtocol
from src.domain.protocols.provider_connection_repository import (
    ProviderConnectionRepository,
)
from src.domain.value_objects.provider_credentials import ProviderCredentials


# =============================================================================
# Test Fixtures
# =============================================================================


def create_test_credentials(
    credential_type: CredentialType = CredentialType.OAUTH2,
    expires_at: datetime | None = None,
) -> ProviderCredentials:
    """Create test credentials."""
    return ProviderCredentials(
        encrypted_data=b"test_encrypted_data",
        credential_type=credential_type,
        expires_at=expires_at or datetime.now(UTC) + timedelta(hours=1),
    )


def create_test_connection(
    connection_id: None = None,
    user_id: None = None,
    status: ConnectionStatus = ConnectionStatus.ACTIVE,
    credentials: ProviderCredentials | None = None,
) -> ProviderConnection:
    """Create a test provider connection."""
    return ProviderConnection(
        id=connection_id or uuid7(),
        user_id=user_id or uuid7(),
        provider_id=uuid7(),
        provider_slug="schwab",
        credentials=credentials or create_test_credentials(),
        status=status,
        alias="Test Account",
        last_sync_at=datetime.now(UTC),
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


def create_handler(
    repo_mock: AsyncMock | None = None,
    event_bus_mock: AsyncMock | None = None,
) -> tuple[RefreshProviderTokensHandler, AsyncMock, AsyncMock]:
    """Create handler with mocked dependencies."""
    repo = repo_mock or AsyncMock(spec=ProviderConnectionRepository)
    event_bus = event_bus_mock or AsyncMock(spec=EventBusProtocol)

    handler = RefreshProviderTokensHandler(
        connection_repo=repo,
        event_bus=event_bus,
    )

    return handler, repo, event_bus


# =============================================================================
# Success Tests
# =============================================================================


@pytest.mark.asyncio
async def test_refresh_provider_tokens_success():
    """Test successful token refresh."""
    # Arrange
    handler, repo, event_bus = create_handler()
    connection = create_test_connection()
    repo.find_by_id.return_value = connection

    new_credentials = create_test_credentials(
        expires_at=datetime.now(UTC) + timedelta(hours=2)
    )

    command = RefreshProviderTokens(
        connection_id=connection.id,
        credentials=new_credentials,
    )

    # Act
    result = await handler.handle(command)

    # Assert
    assert isinstance(result, Success)
    assert result.value is None  # Returns None on success

    # Verify repository interactions (uses save, not update)
    repo.find_by_id.assert_called_once_with(connection.id)
    repo.save.assert_called_once()

    # Verify credentials updated on saved connection
    saved_connection = repo.save.call_args[0][0]
    assert saved_connection.credentials == new_credentials

    # Verify 2 events emitted (Attempted + Succeeded)
    assert event_bus.publish.call_count == 2


@pytest.mark.asyncio
async def test_refresh_provider_tokens_emits_attempted_event():
    """Test that handler emits ProviderTokenRefreshAttempted event first."""
    # Arrange
    handler, repo, event_bus = create_handler()
    connection = create_test_connection()
    repo.find_by_id.return_value = connection

    command = RefreshProviderTokens(
        connection_id=connection.id,
        credentials=create_test_credentials(),
    )

    # Act
    await handler.handle(command)

    # Assert - First event should be Attempted
    first_event = event_bus.publish.call_args_list[0][0][0]
    assert isinstance(first_event, ProviderTokenRefreshAttempted)
    assert first_event.connection_id == connection.id
    assert first_event.user_id == connection.user_id
    assert first_event.provider_slug == "schwab"


@pytest.mark.asyncio
async def test_refresh_provider_tokens_emits_succeeded_event():
    """Test that handler emits ProviderTokenRefreshSucceeded event on success."""
    # Arrange
    handler, repo, event_bus = create_handler()
    connection = create_test_connection()
    repo.find_by_id.return_value = connection

    new_expires_at = datetime.now(UTC) + timedelta(hours=2)
    new_credentials = create_test_credentials(expires_at=new_expires_at)

    command = RefreshProviderTokens(
        connection_id=connection.id,
        credentials=new_credentials,
    )

    # Act
    await handler.handle(command)

    # Assert - Second event should be Succeeded
    second_event = event_bus.publish.call_args_list[1][0][0]
    assert isinstance(second_event, ProviderTokenRefreshSucceeded)
    assert second_event.connection_id == connection.id
    assert second_event.user_id == connection.user_id
    assert second_event.provider_slug == "schwab"


# =============================================================================
# Connection Not Found Tests
# =============================================================================


@pytest.mark.asyncio
async def test_refresh_provider_tokens_fails_when_connection_not_found():
    """Test token refresh fails when connection doesn't exist."""
    # Arrange
    handler, repo, event_bus = create_handler()
    repo.find_by_id.return_value = None

    command = RefreshProviderTokens(
        connection_id=uuid7(),
        credentials=create_test_credentials(),
    )

    # Act
    result = await handler.handle(command)

    # Assert
    assert isinstance(result, Failure)
    assert result.error == RefreshProviderTokensError.CONNECTION_NOT_FOUND
    repo.save.assert_not_called()


@pytest.mark.asyncio
async def test_refresh_provider_tokens_emits_failed_event_on_not_found():
    """Test that handler emits ProviderTokenRefreshFailed when not found."""
    # Arrange
    handler, repo, event_bus = create_handler()
    repo.find_by_id.return_value = None

    command = RefreshProviderTokens(
        connection_id=uuid7(),
        credentials=create_test_credentials(),
    )

    # Act
    await handler.handle(command)

    # Assert - Should emit Attempted then Failed
    assert event_bus.publish.call_count == 2
    second_event = event_bus.publish.call_args_list[1][0][0]
    assert isinstance(second_event, ProviderTokenRefreshFailed)
    assert second_event.reason == RefreshProviderTokensError.CONNECTION_NOT_FOUND


# =============================================================================
# Connection Status Tests
# =============================================================================


@pytest.mark.asyncio
async def test_refresh_provider_tokens_fails_when_connection_disconnected():
    """Test token refresh fails when connection is disconnected."""
    # Arrange
    handler, repo, event_bus = create_handler()
    connection = create_test_connection(status=ConnectionStatus.DISCONNECTED)
    repo.find_by_id.return_value = connection

    command = RefreshProviderTokens(
        connection_id=connection.id,
        credentials=create_test_credentials(),
    )

    # Act
    result = await handler.handle(command)

    # Assert
    assert isinstance(result, Failure)
    assert result.error == RefreshProviderTokensError.NOT_ACTIVE
    repo.save.assert_not_called()


@pytest.mark.asyncio
async def test_refresh_provider_tokens_emits_failed_event_on_inactive_connection():
    """Test that handler emits ProviderTokenRefreshFailed for inactive connection."""
    # Arrange
    handler, repo, event_bus = create_handler()
    connection = create_test_connection(status=ConnectionStatus.EXPIRED)
    repo.find_by_id.return_value = connection

    command = RefreshProviderTokens(
        connection_id=connection.id,
        credentials=create_test_credentials(),
    )

    # Act
    await handler.handle(command)

    # Assert
    second_event = event_bus.publish.call_args_list[1][0][0]
    assert isinstance(second_event, ProviderTokenRefreshFailed)
    assert second_event.reason == RefreshProviderTokensError.NOT_ACTIVE


# =============================================================================
# Database Error Tests
# =============================================================================


@pytest.mark.asyncio
async def test_refresh_provider_tokens_handles_database_save_error():
    """Test token refresh handles database save error."""
    # Arrange
    handler, repo, event_bus = create_handler()
    connection = create_test_connection()
    repo.find_by_id.return_value = connection
    repo.save.side_effect = Exception("Constraint violation")

    command = RefreshProviderTokens(
        connection_id=connection.id,
        credentials=create_test_credentials(),
    )

    # Act
    result = await handler.handle(command)

    # Assert
    assert isinstance(result, Failure)
    assert RefreshProviderTokensError.DATABASE_ERROR in result.error


@pytest.mark.asyncio
async def test_refresh_provider_tokens_emits_failed_event_on_save_error():
    """Test that handler emits ProviderTokenRefreshFailed on save error."""
    # Arrange
    handler, repo, event_bus = create_handler()
    connection = create_test_connection()
    repo.find_by_id.return_value = connection
    repo.save.side_effect = Exception("DB save error")

    command = RefreshProviderTokens(
        connection_id=connection.id,
        credentials=create_test_credentials(),
    )

    # Act
    await handler.handle(command)

    # Assert - Should emit Attempted then Failed (after save error)
    assert event_bus.publish.call_count == 2
    second_event = event_bus.publish.call_args_list[1][0][0]
    assert isinstance(second_event, ProviderTokenRefreshFailed)
    assert "Database error" in second_event.reason
