"""Unit tests for ConnectProviderHandler.

Tests the connect provider command handler business logic.
Uses mocked repository and event bus for isolation.

Reference:
    - docs/architecture/cqrs-pattern.md (Testing Strategy)
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest
from uuid_extensions import uuid7

from src.application.commands.handlers.connect_provider_handler import (
    ConnectProviderError,
    ConnectProviderHandler,
)
from src.application.commands.provider_commands import ConnectProvider
from src.core.result import Failure, Success
from src.domain.enums.credential_type import CredentialType
from src.domain.events.provider_events import (
    ProviderConnectionAttempted,
    ProviderConnectionFailed,
    ProviderConnectionSucceeded,
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


def create_handler(
    repo_mock: AsyncMock | None = None,
    event_bus_mock: AsyncMock | None = None,
) -> tuple[ConnectProviderHandler, AsyncMock, AsyncMock]:
    """Create handler with mocked dependencies."""
    repo = repo_mock or AsyncMock(spec=ProviderConnectionRepository)
    event_bus = event_bus_mock or AsyncMock(spec=EventBusProtocol)

    handler = ConnectProviderHandler(
        connection_repo=repo,
        event_bus=event_bus,
    )

    return handler, repo, event_bus


# =============================================================================
# Success Tests
# =============================================================================


@pytest.mark.asyncio
async def test_connect_provider_success():
    """Test successful provider connection."""
    # Arrange
    handler, repo, event_bus = create_handler()
    credentials = create_test_credentials()

    command = ConnectProvider(
        user_id=uuid7(),
        provider_id=uuid7(),
        provider_slug="schwab",
        credentials=credentials,
        alias="My Account",
    )

    # Act
    result = await handler.handle(command)

    # Assert
    assert isinstance(result, Success)
    assert result.value is not None  # Returns connection_id

    # Verify repository called
    repo.save.assert_called_once()
    saved_connection = repo.save.call_args[0][0]
    assert saved_connection.provider_slug == "schwab"
    assert saved_connection.alias == "My Account"
    assert saved_connection.credentials == credentials

    # Verify 2 events emitted (Attempted + Succeeded)
    assert event_bus.publish.call_count == 2


@pytest.mark.asyncio
async def test_connect_provider_success_without_alias():
    """Test successful connection without alias."""
    # Arrange
    handler, repo, event_bus = create_handler()
    credentials = create_test_credentials()

    command = ConnectProvider(
        user_id=uuid7(),
        provider_id=uuid7(),
        provider_slug="fidelity",
        credentials=credentials,
    )

    # Act
    result = await handler.handle(command)

    # Assert
    assert isinstance(result, Success)
    saved_connection = repo.save.call_args[0][0]
    assert saved_connection.alias is None


@pytest.mark.asyncio
async def test_connect_provider_emits_attempted_event():
    """Test that handler emits ProviderConnectionAttempted event first."""
    # Arrange
    handler, repo, event_bus = create_handler()
    credentials = create_test_credentials()
    user_id = uuid7()
    provider_id = uuid7()

    command = ConnectProvider(
        user_id=user_id,
        provider_id=provider_id,
        provider_slug="schwab",
        credentials=credentials,
    )

    # Act
    await handler.handle(command)

    # Assert - First event should be Attempted
    first_event = event_bus.publish.call_args_list[0][0][0]
    assert isinstance(first_event, ProviderConnectionAttempted)
    assert first_event.user_id == user_id
    assert first_event.provider_id == provider_id
    assert first_event.provider_slug == "schwab"


@pytest.mark.asyncio
async def test_connect_provider_emits_succeeded_event():
    """Test that handler emits ProviderConnectionSucceeded event on success."""
    # Arrange
    handler, repo, event_bus = create_handler()
    credentials = create_test_credentials()
    user_id = uuid7()
    provider_id = uuid7()

    command = ConnectProvider(
        user_id=user_id,
        provider_id=provider_id,
        provider_slug="schwab",
        credentials=credentials,
    )

    # Act
    result = await handler.handle(command)

    # Assert - Second event should be Succeeded
    assert isinstance(result, Success)
    second_event = event_bus.publish.call_args_list[1][0][0]
    assert isinstance(second_event, ProviderConnectionSucceeded)
    assert second_event.user_id == user_id
    assert second_event.provider_id == provider_id
    assert second_event.connection_id == result.value


# =============================================================================
# Validation Error Tests
# =============================================================================


@pytest.mark.asyncio
async def test_connect_provider_fails_with_invalid_provider_slug_empty():
    """Test connection fails with empty provider slug."""
    # Arrange
    handler, repo, event_bus = create_handler()
    credentials = create_test_credentials()

    command = ConnectProvider(
        user_id=uuid7(),
        provider_id=uuid7(),
        provider_slug="",  # Empty
        credentials=credentials,
    )

    # Act
    result = await handler.handle(command)

    # Assert
    assert isinstance(result, Failure)
    assert result.error == ConnectProviderError.INVALID_PROVIDER_SLUG
    repo.save.assert_not_called()


@pytest.mark.asyncio
async def test_connect_provider_fails_with_invalid_provider_slug_too_long():
    """Test connection fails with provider slug exceeding 50 chars."""
    # Arrange
    handler, repo, event_bus = create_handler()
    credentials = create_test_credentials()

    command = ConnectProvider(
        user_id=uuid7(),
        provider_id=uuid7(),
        provider_slug="a" * 51,  # 51 chars
        credentials=credentials,
    )

    # Act
    result = await handler.handle(command)

    # Assert
    assert isinstance(result, Failure)
    assert result.error == ConnectProviderError.INVALID_PROVIDER_SLUG


@pytest.mark.asyncio
async def test_connect_provider_emits_failed_event_on_validation_error():
    """Test that handler emits ProviderConnectionFailed on validation error."""
    # Arrange
    handler, repo, event_bus = create_handler()
    credentials = create_test_credentials()

    command = ConnectProvider(
        user_id=uuid7(),
        provider_id=uuid7(),
        provider_slug="",  # Invalid
        credentials=credentials,
    )

    # Act
    await handler.handle(command)

    # Assert - Should emit Attempted then Failed
    assert event_bus.publish.call_count == 2
    first_event = event_bus.publish.call_args_list[0][0][0]
    second_event = event_bus.publish.call_args_list[1][0][0]

    assert isinstance(first_event, ProviderConnectionAttempted)
    assert isinstance(second_event, ProviderConnectionFailed)
    assert second_event.reason == ConnectProviderError.INVALID_PROVIDER_SLUG


# =============================================================================
# Database Error Tests
# =============================================================================


@pytest.mark.asyncio
async def test_connect_provider_handles_database_error():
    """Test connection handles database save error."""
    # Arrange
    handler, repo, event_bus = create_handler()
    repo.save.side_effect = Exception("Database connection lost")
    credentials = create_test_credentials()

    command = ConnectProvider(
        user_id=uuid7(),
        provider_id=uuid7(),
        provider_slug="schwab",
        credentials=credentials,
    )

    # Act
    result = await handler.handle(command)

    # Assert
    assert isinstance(result, Failure)
    assert ConnectProviderError.DATABASE_ERROR in result.error


@pytest.mark.asyncio
async def test_connect_provider_emits_failed_event_on_database_error():
    """Test that handler emits ProviderConnectionFailed on database error."""
    # Arrange
    handler, repo, event_bus = create_handler()
    repo.save.side_effect = Exception("DB error")
    credentials = create_test_credentials()

    command = ConnectProvider(
        user_id=uuid7(),
        provider_id=uuid7(),
        provider_slug="schwab",
        credentials=credentials,
    )

    # Act
    await handler.handle(command)

    # Assert
    assert event_bus.publish.call_count == 2
    second_event = event_bus.publish.call_args_list[1][0][0]
    assert isinstance(second_event, ProviderConnectionFailed)
    assert "Database error" in second_event.reason


# =============================================================================
# Credential Type Tests
# =============================================================================


@pytest.mark.asyncio
async def test_connect_provider_with_api_key_credentials():
    """Test connection with API key credentials."""
    # Arrange
    handler, repo, event_bus = create_handler()
    credentials = create_test_credentials(credential_type=CredentialType.API_KEY)

    command = ConnectProvider(
        user_id=uuid7(),
        provider_id=uuid7(),
        provider_slug="tradier",
        credentials=credentials,
    )

    # Act
    result = await handler.handle(command)

    # Assert
    assert isinstance(result, Success)
    saved_connection = repo.save.call_args[0][0]
    assert saved_connection.credentials.credential_type == CredentialType.API_KEY


@pytest.mark.asyncio
async def test_connect_provider_with_link_token_credentials():
    """Test connection with aggregator link token credentials."""
    # Arrange
    handler, repo, event_bus = create_handler()
    credentials = create_test_credentials(credential_type=CredentialType.LINK_TOKEN)

    command = ConnectProvider(
        user_id=uuid7(),
        provider_id=uuid7(),
        provider_slug="aggregator",
        credentials=credentials,
    )

    # Act
    result = await handler.handle(command)

    # Assert
    assert isinstance(result, Success)
