"""Unit tests for GetProviderConnectionHandler.

Tests the get provider connection query handler business logic.
Uses mocked repository for isolation.

Reference:
    - docs/architecture/cqrs-pattern.md (Testing Strategy)
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest
from uuid_extensions import uuid7

from src.application.queries.handlers.get_provider_handler import (
    GetProviderConnectionError,
    GetProviderConnectionHandler,
    ProviderConnectionResult,
)
from src.application.queries.provider_queries import GetProviderConnection
from src.core.result import Failure, Success
from src.domain.entities.provider_connection import ProviderConnection
from src.domain.enums.connection_status import ConnectionStatus
from src.domain.enums.credential_type import CredentialType
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
    expires_at: datetime | None = None,
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
            expires_at=expires_at or datetime.now(UTC) + timedelta(hours=1),
        ),
        status=status,
        alias="Test Account",
        last_sync_at=datetime.now(UTC),
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


def create_handler(
    repo_mock: AsyncMock | None = None,
    cache_mock: AsyncMock | None = None,
) -> tuple[GetProviderConnectionHandler, AsyncMock, AsyncMock]:
    """Create handler with mocked dependencies.
    
    Returns:
        Tuple of (handler, repo_mock, cache_mock)
    """
    repo = repo_mock or AsyncMock(spec=ProviderConnectionRepository)
    cache = cache_mock or AsyncMock()
    
    # Configure cache mock to return None by default (cache miss)
    cache.get.return_value = None
    cache.set.return_value = None

    handler = GetProviderConnectionHandler(
        connection_repo=repo,
        connection_cache=cache,
    )

    return handler, repo, cache


# =============================================================================
# Success Tests
# =============================================================================


@pytest.mark.asyncio
async def test_get_provider_connection_success():
    """Test successful provider connection retrieval."""
    # Arrange
    handler, repo, cache = create_handler()
    user_id = uuid7()
    connection = create_test_connection(user_id=user_id)
    repo.find_by_id.return_value = connection

    query = GetProviderConnection(
        connection_id=connection.id,
        user_id=user_id,
    )

    # Act
    result = await handler.handle(query)

    # Assert
    assert isinstance(result, Success)
    assert isinstance(result.value, ProviderConnectionResult)
    assert result.value.id == connection.id
    assert result.value.provider_slug == "schwab"
    assert result.value.status == ConnectionStatus.ACTIVE
    assert result.value.alias == "Test Account"

    # Verify repository called
    repo.find_by_id.assert_called_once_with(connection.id)


@pytest.mark.asyncio
async def test_get_provider_connection_returns_dto_not_entity():
    """Test that handler returns DTO, not domain entity."""
    # Arrange
    handler, repo, cache = create_handler()
    user_id = uuid7()
    connection = create_test_connection(user_id=user_id)
    repo.find_by_id.return_value = connection

    query = GetProviderConnection(
        connection_id=connection.id,
        user_id=user_id,
    )

    # Act
    result = await handler.handle(query)

    # Assert
    assert isinstance(result, Success)
    # Should be DTO type, not ProviderConnection entity
    assert isinstance(result.value, ProviderConnectionResult)
    assert not isinstance(result.value, ProviderConnection)
    # DTO should have is_connected and needs_reauthentication computed fields
    assert hasattr(result.value, "is_connected")
    assert hasattr(result.value, "needs_reauthentication")


@pytest.mark.asyncio
async def test_get_provider_connection_includes_timestamps():
    """Test that DTO includes timestamps."""
    # Arrange
    handler, repo, cache = create_handler()
    user_id = uuid7()
    connection = create_test_connection(user_id=user_id)
    repo.find_by_id.return_value = connection

    query = GetProviderConnection(
        connection_id=connection.id,
        user_id=user_id,
    )

    # Act
    result = await handler.handle(query)

    # Assert
    assert isinstance(result, Success)
    assert result.value.created_at == connection.created_at
    assert result.value.updated_at == connection.updated_at
    assert result.value.last_sync_at == connection.last_sync_at


# =============================================================================
# Not Found Tests
# =============================================================================


@pytest.mark.asyncio
async def test_get_provider_connection_fails_when_not_found():
    """Test retrieval fails when connection doesn't exist."""
    # Arrange
    handler, repo, cache = create_handler()
    repo.find_by_id.return_value = None

    query = GetProviderConnection(
        connection_id=uuid7(),
        user_id=uuid7(),
    )

    # Act
    result = await handler.handle(query)

    # Assert
    assert isinstance(result, Failure)
    assert result.error == GetProviderConnectionError.CONNECTION_NOT_FOUND


# =============================================================================
# Authorization Tests
# =============================================================================


@pytest.mark.asyncio
async def test_get_provider_connection_fails_when_not_owned():
    """Test retrieval fails when user doesn't own the connection."""
    # Arrange
    handler, repo, cache = create_handler()
    connection = create_test_connection(user_id=uuid7())  # Different user
    repo.find_by_id.return_value = connection

    query = GetProviderConnection(
        connection_id=connection.id,
        user_id=uuid7(),  # Different user
    )

    # Act
    result = await handler.handle(query)

    # Assert
    assert isinstance(result, Failure)
    assert result.error == GetProviderConnectionError.NOT_OWNED_BY_USER


# =============================================================================
# Status Tests
# =============================================================================


@pytest.mark.asyncio
async def test_get_provider_connection_with_different_statuses():
    """Test retrieval returns correct status for various connection states."""
    # Arrange
    handler, repo, cache = create_handler()
    user_id = uuid7()

    statuses = [
        ConnectionStatus.ACTIVE,
        ConnectionStatus.PENDING,
        ConnectionStatus.EXPIRED,
        ConnectionStatus.REVOKED,
    ]

    for status in statuses:
        connection = create_test_connection(user_id=user_id, status=status)
        repo.find_by_id.return_value = connection

        query = GetProviderConnection(
            connection_id=connection.id,
            user_id=user_id,
        )

        # Act
        result = await handler.handle(query)

        # Assert
        assert isinstance(result, Success)
        assert result.value.status == status
