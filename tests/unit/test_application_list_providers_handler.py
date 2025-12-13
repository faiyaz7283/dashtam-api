"""Unit tests for ListProviderConnectionsHandler.

Tests the list provider connections query handler business logic.
Uses mocked repository for isolation.

Reference:
    - docs/architecture/cqrs-pattern.md (Testing Strategy)
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest
from uuid_extensions import uuid7

from src.application.queries.handlers.list_providers_handler import (
    ListProviderConnectionsHandler,
    ProviderConnectionListResult,
)
from src.application.queries.provider_queries import ListProviderConnections
from src.core.result import Success
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
    provider_slug: str = "schwab",
    status: ConnectionStatus = ConnectionStatus.ACTIVE,
    alias: str | None = "Test Account",
) -> ProviderConnection:
    """Create a test provider connection."""
    return ProviderConnection(
        id=connection_id or uuid7(),
        user_id=user_id or uuid7(),
        provider_id=uuid7(),
        provider_slug=provider_slug,
        credentials=ProviderCredentials(
            encrypted_data=b"test_data",
            credential_type=CredentialType.OAUTH2,
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        ),
        status=status,
        alias=alias,
        last_sync_at=datetime.now(UTC),
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


def create_handler(
    repo_mock: AsyncMock | None = None,
) -> tuple[ListProviderConnectionsHandler, AsyncMock]:
    """Create handler with mocked dependencies."""
    repo = repo_mock or AsyncMock(spec=ProviderConnectionRepository)

    handler = ListProviderConnectionsHandler(
        connection_repo=repo,
    )

    return handler, repo


# =============================================================================
# Success Tests
# =============================================================================


@pytest.mark.asyncio
async def test_list_provider_connections_success():
    """Test successful listing of provider connections."""
    # Arrange
    handler, repo = create_handler()
    user_id = uuid7()
    connections = [
        create_test_connection(user_id=user_id, provider_slug="schwab"),
        create_test_connection(user_id=user_id, provider_slug="fidelity"),
    ]
    repo.find_by_user_id.return_value = connections

    query = ListProviderConnections(user_id=user_id)

    # Act
    result = await handler.handle(query)

    # Assert
    assert isinstance(result, Success)
    assert isinstance(result.value, ProviderConnectionListResult)
    assert result.value.total_count == 2
    assert len(result.value.connections) == 2

    # Verify repository called
    repo.find_by_user_id.assert_called_once_with(user_id)


@pytest.mark.asyncio
async def test_list_provider_connections_returns_dto_list():
    """Test that handler returns list of DTOs."""
    # Arrange
    handler, repo = create_handler()
    user_id = uuid7()
    connections = [
        create_test_connection(user_id=user_id),
    ]
    repo.find_by_user_id.return_value = connections

    query = ListProviderConnections(user_id=user_id)

    # Act
    result = await handler.handle(query)

    # Assert
    assert isinstance(result, Success)
    # DTOs should not be domain entities
    for conn in result.value.connections:
        assert not isinstance(conn, ProviderConnection)
        # Should have id attribute (DTO)
        assert hasattr(conn, "id")
        # Should have computed fields
        assert hasattr(conn, "is_connected")
        assert hasattr(conn, "needs_reauthentication")


@pytest.mark.asyncio
async def test_list_provider_connections_empty_result():
    """Test listing returns empty result when user has no connections."""
    # Arrange
    handler, repo = create_handler()
    user_id = uuid7()
    repo.find_by_user_id.return_value = []

    query = ListProviderConnections(user_id=user_id)

    # Act
    result = await handler.handle(query)

    # Assert
    assert isinstance(result, Success)
    assert result.value.total_count == 0
    assert len(result.value.connections) == 0


# =============================================================================
# Filter Tests
# =============================================================================


@pytest.mark.asyncio
async def test_list_provider_connections_active_only():
    """Test listing with active_only filter."""
    # Arrange
    handler, repo = create_handler()
    user_id = uuid7()
    connections = [
        create_test_connection(user_id=user_id, status=ConnectionStatus.ACTIVE),
        create_test_connection(user_id=user_id, status=ConnectionStatus.PENDING),
    ]
    repo.find_active_by_user.return_value = [connections[0]]

    query = ListProviderConnections(user_id=user_id, active_only=True)

    # Act
    result = await handler.handle(query)

    # Assert
    assert isinstance(result, Success)
    assert result.value.total_count == 1
    assert result.value.connections[0].status == ConnectionStatus.ACTIVE

    # Verify correct repository method called
    repo.find_active_by_user.assert_called_once_with(user_id)
    repo.find_by_user_id.assert_not_called()


@pytest.mark.asyncio
async def test_list_provider_connections_all_statuses():
    """Test listing returns all statuses when active_only is False."""
    # Arrange
    handler, repo = create_handler()
    user_id = uuid7()
    connections = [
        create_test_connection(user_id=user_id, status=ConnectionStatus.ACTIVE),
        create_test_connection(user_id=user_id, status=ConnectionStatus.EXPIRED),
        create_test_connection(user_id=user_id, status=ConnectionStatus.DISCONNECTED),
    ]
    repo.find_by_user_id.return_value = connections

    query = ListProviderConnections(user_id=user_id, active_only=False)

    # Act
    result = await handler.handle(query)

    # Assert
    assert isinstance(result, Success)
    assert result.value.total_count == 3

    # Verify find_by_user_id used, not find_active_by_user
    repo.find_by_user_id.assert_called_once_with(user_id)


# =============================================================================
# DTO Mapping Tests
# =============================================================================


@pytest.mark.asyncio
async def test_list_provider_connections_maps_all_fields():
    """Test that all connection fields are properly mapped to DTOs."""
    # Arrange
    handler, repo = create_handler()
    user_id = uuid7()
    connection = create_test_connection(
        user_id=user_id,
        provider_slug="tradier",
        alias="Trading Account",
        status=ConnectionStatus.PENDING,
    )
    repo.find_by_user_id.return_value = [connection]

    query = ListProviderConnections(user_id=user_id)

    # Act
    result = await handler.handle(query)

    # Assert
    assert isinstance(result, Success)
    dto = result.value.connections[0]
    assert dto.id == connection.id
    assert dto.provider_id == connection.provider_id
    assert dto.provider_slug == "tradier"
    assert dto.status == ConnectionStatus.PENDING
    assert dto.alias == "Trading Account"
    assert dto.last_sync_at == connection.last_sync_at
    assert dto.created_at == connection.created_at
