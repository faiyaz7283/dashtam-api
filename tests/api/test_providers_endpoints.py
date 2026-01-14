"""API tests for provider connection endpoints.

Tests the complete HTTP request/response cycle for provider management:
- GET /api/v1/providers (list provider connections)
- GET /api/v1/providers/{id} (get connection details)
- POST /api/v1/providers (initiate OAuth flow)
- PATCH /api/v1/providers/{id} (update connection)
- DELETE /api/v1/providers/{id} (disconnect provider)

Architecture:
- Uses FastAPI TestClient with real app + dependency overrides
- Tests validation, authorization, and RFC 7807 error responses
- Mocks handlers to test HTTP layer behavior
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from uuid_extensions import uuid7

from src.application.commands.handlers.disconnect_provider_handler import (
    DisconnectProviderHandler,
)
from src.application.queries.handlers.get_provider_handler import (
    GetProviderConnectionHandler,
)
from src.application.queries.handlers.list_providers_handler import (
    ListProviderConnectionsHandler,
)
from src.core.container.handler_factory import handler_factory
from src.core.result import Failure, Success
from src.domain.enums.connection_status import ConnectionStatus
from src.main import app


# =============================================================================
# Test Doubles (matching actual application DTOs)
# =============================================================================


@dataclass(frozen=True, kw_only=True)
class MockProviderConnectionResult:
    """Mock DTO matching ProviderConnectionResult from get_provider_handler.py."""

    id: UUID
    user_id: UUID
    provider_id: UUID
    provider_slug: str
    alias: str | None
    status: ConnectionStatus
    is_connected: bool
    needs_reauthentication: bool
    connected_at: datetime | None
    last_sync_at: datetime | None
    created_at: datetime
    updated_at: datetime


@dataclass
class MockProviderConnectionListResult:
    """Mock result matching ProviderConnectionListResult."""

    connections: list[MockProviderConnectionResult]
    total_count: int
    active_count: int


class MockListProviderConnectionsHandler:
    """Mock handler for listing connections."""

    def __init__(
        self,
        connections: list[MockProviderConnectionResult] | None = None,
        error: str | None = None,
    ) -> None:
        self._connections = connections or []
        self._error = error

    async def handle(self, query: Any) -> Success[object] | Failure[str]:
        if self._error:
            return Failure(error=self._error)
        result = MockProviderConnectionListResult(
            connections=self._connections,
            total_count=len(self._connections),
            active_count=sum(1 for c in self._connections if c.is_connected),
        )
        return Success(value=result)


class MockGetProviderConnectionHandler:
    """Mock handler for getting a single connection."""

    def __init__(
        self,
        connection: MockProviderConnectionResult | None = None,
        error: str | None = None,
    ) -> None:
        self._connection = connection
        self._error = error

    async def handle(self, query: Any) -> Success[object] | Failure[str]:
        if self._error:
            return Failure(error=self._error)
        return Success(value=self._connection)


class MockDisconnectProviderHandler:
    """Mock handler for disconnecting provider."""

    def __init__(
        self,
        connection_id: UUID | None = None,
        error: str | None = None,
    ) -> None:
        self._connection_id = connection_id
        self._error = error

    async def handle(self, command: Any) -> Success[object] | Failure[str]:
        if self._error:
            return Failure(error=self._error)
        return Success(value=self._connection_id)


# =============================================================================
# Authentication Mock
# =============================================================================


@dataclass
class MockCurrentUser:
    """Mock user for auth override."""

    user_id: UUID
    email: str = "test@example.com"
    roles: list[str] | None = None

    def __post_init__(self):
        if self.roles is None:
            self.roles = ["user"]


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_user_id():
    """Provide consistent user ID for tests."""
    return uuid7()


@pytest.fixture
def mock_connection_id():
    """Provide consistent connection ID for tests."""
    return uuid7()


@pytest.fixture
def mock_provider_id():
    """Provide consistent provider ID for tests."""
    return UUID("00000000-0000-0000-0000-000000000001")


@pytest.fixture
def mock_connection(mock_connection_id, mock_user_id, mock_provider_id):
    """Create a mock provider connection result."""
    now = datetime.now(UTC)
    return MockProviderConnectionResult(
        id=mock_connection_id,
        user_id=mock_user_id,
        provider_id=mock_provider_id,
        provider_slug="schwab",
        alias="My Schwab Account",
        status=ConnectionStatus.ACTIVE,
        is_connected=True,
        needs_reauthentication=False,
        connected_at=now,
        last_sync_at=now - timedelta(hours=1),
        created_at=now - timedelta(days=7),
        updated_at=now,
    )


@pytest.fixture(autouse=True)
def override_auth(mock_user_id):
    """Override authentication for all tests."""
    from src.presentation.routers.api.middleware.auth_dependencies import (
        get_current_user,
    )

    mock_user = MockCurrentUser(user_id=mock_user_id)

    async def mock_get_current_user():
        return mock_user

    app.dependency_overrides[get_current_user] = mock_get_current_user
    yield
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def client():
    """Provide test client."""
    return TestClient(app)


# =============================================================================
# List Providers Tests (GET /api/v1/providers)
# =============================================================================


@pytest.mark.api
class TestListProviders:
    """Tests for GET /api/v1/providers endpoint."""

    def test_list_providers_returns_empty_list(self, client):
        """GET /api/v1/providers returns empty list when no connections."""
        factory_key = handler_factory(ListProviderConnectionsHandler)
        app.dependency_overrides[factory_key] = (
            lambda: MockListProviderConnectionsHandler(connections=[])
        )

        response = client.get("/api/v1/providers")

        assert response.status_code == 200
        data = response.json()
        assert data["connections"] == []

        app.dependency_overrides.pop(factory_key, None)

    def test_list_providers_returns_connections(self, client, mock_connection):
        """GET /api/v1/providers returns list of connections."""
        factory_key = handler_factory(ListProviderConnectionsHandler)
        app.dependency_overrides[factory_key] = (
            lambda: MockListProviderConnectionsHandler(connections=[mock_connection])
        )

        response = client.get("/api/v1/providers")

        assert response.status_code == 200
        data = response.json()
        assert len(data["connections"]) == 1
        assert data["connections"][0]["provider_slug"] == "schwab"

        app.dependency_overrides.pop(factory_key, None)

    def test_list_providers_handler_error_returns_rfc7807(self, client):
        """GET /api/v1/providers returns RFC 7807 error on handler failure."""
        factory_key = handler_factory(ListProviderConnectionsHandler)
        app.dependency_overrides[factory_key] = (
            lambda: MockListProviderConnectionsHandler(error="Database unavailable")
        )

        response = client.get("/api/v1/providers")

        assert response.status_code == 500
        data = response.json()
        assert "type" in data
        assert "title" in data
        assert data["status"] == 500

        app.dependency_overrides.pop(factory_key, None)


# =============================================================================
# Get Provider Tests (GET /api/v1/providers/{id})
# =============================================================================


@pytest.mark.api
class TestGetProvider:
    """Tests for GET /api/v1/providers/{id} endpoint."""

    def test_get_provider_returns_connection(
        self, client, mock_connection_id, mock_connection
    ):
        """GET /api/v1/providers/{id} returns connection details."""
        factory_key = handler_factory(GetProviderConnectionHandler)
        app.dependency_overrides[factory_key] = (
            lambda: MockGetProviderConnectionHandler(connection=mock_connection)
        )

        response = client.get(f"/api/v1/providers/{mock_connection_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(mock_connection_id)
        assert data["provider_slug"] == "schwab"

        app.dependency_overrides.pop(factory_key, None)

    def test_get_provider_not_found(self, client, mock_connection_id):
        """GET /api/v1/providers/{id} returns 404 when not found."""
        factory_key = handler_factory(GetProviderConnectionHandler)
        app.dependency_overrides[factory_key] = (
            lambda: MockGetProviderConnectionHandler(error="Connection not found")
        )

        response = client.get(f"/api/v1/providers/{mock_connection_id}")

        assert response.status_code == 404
        data = response.json()
        assert data["status"] == 404

        app.dependency_overrides.pop(factory_key, None)

    def test_get_provider_forbidden(self, client, mock_connection_id):
        """GET /api/v1/providers/{id} returns 403 when not owned by user."""
        factory_key = handler_factory(GetProviderConnectionHandler)
        app.dependency_overrides[factory_key] = (
            lambda: MockGetProviderConnectionHandler(
                error="Connection not owned by user"
            )
        )

        response = client.get(f"/api/v1/providers/{mock_connection_id}")

        assert response.status_code == 403

        app.dependency_overrides.pop(factory_key, None)

    def test_get_provider_invalid_uuid(self, client):
        """GET /api/v1/providers/{id} returns 422 for invalid UUID."""
        response = client.get("/api/v1/providers/not-a-uuid")

        assert response.status_code == 422


# =============================================================================
# Initiate Connection Tests (POST /api/v1/providers)
# =============================================================================


@pytest.mark.api
class TestInitiateConnection:
    """Tests for POST /api/v1/providers endpoint."""

    def test_initiate_connection_returns_auth_url(self, client):
        """POST /api/v1/providers returns authorization URL."""
        from src.core.container import get_cache

        # Mock cache for state storage
        class MockCache:
            async def set(self, key: str, value: str, ttl: int) -> Success[None]:
                return Success(value=None)

            async def get(self, key: str) -> Success[None]:
                return Success(value=None)

            async def delete(self, key: str) -> Success[None]:
                return Success(value=None)

        app.dependency_overrides[get_cache] = lambda: MockCache()

        response = client.post(
            "/api/v1/providers",
            json={"provider_slug": "schwab"},
        )

        assert response.status_code == 201
        data = response.json()
        assert "authorization_url" in data
        assert "state" in data
        assert "schwab" in data["authorization_url"].lower()

        app.dependency_overrides.pop(get_cache, None)

    def test_initiate_connection_unsupported_provider(self, client):
        """POST /api/v1/providers returns 404 for unsupported provider."""
        response = client.post(
            "/api/v1/providers",
            json={"provider_slug": "unsupported_provider"},
        )

        assert response.status_code == 404

    def test_initiate_connection_missing_provider_slug(self, client):
        """POST /api/v1/providers returns 422 when provider_slug missing."""
        response = client.post("/api/v1/providers", json={})

        assert response.status_code == 422


# =============================================================================
# Update Provider Tests (PATCH /api/v1/providers/{id})
# =============================================================================


@pytest.mark.api
class TestUpdateProvider:
    """Tests for PATCH /api/v1/providers/{id} endpoint."""

    def test_update_provider_returns_connection(
        self, client, mock_connection_id, mock_connection
    ):
        """PATCH /api/v1/providers/{id} returns updated connection."""
        factory_key = handler_factory(GetProviderConnectionHandler)
        app.dependency_overrides[factory_key] = (
            lambda: MockGetProviderConnectionHandler(connection=mock_connection)
        )

        response = client.patch(
            f"/api/v1/providers/{mock_connection_id}",
            json={"alias": "Updated Alias"},
        )

        assert response.status_code == 200

        app.dependency_overrides.pop(factory_key, None)

    def test_update_provider_not_found(self, client, mock_connection_id):
        """PATCH /api/v1/providers/{id} returns 404 when not found."""
        factory_key = handler_factory(GetProviderConnectionHandler)
        app.dependency_overrides[factory_key] = (
            lambda: MockGetProviderConnectionHandler(error="Connection not found")
        )

        response = client.patch(
            f"/api/v1/providers/{mock_connection_id}",
            json={"alias": "Updated Alias"},
        )

        assert response.status_code == 404

        app.dependency_overrides.pop(factory_key, None)


# =============================================================================
# Disconnect Provider Tests (DELETE /api/v1/providers/{id})
# =============================================================================


@pytest.mark.api
class TestDisconnectProvider:
    """Tests for DELETE /api/v1/providers/{id} endpoint."""

    def test_disconnect_provider_returns_no_content(self, client, mock_connection_id):
        """DELETE /api/v1/providers/{id} returns 204 No Content."""
        factory_key = handler_factory(DisconnectProviderHandler)
        app.dependency_overrides[factory_key] = lambda: MockDisconnectProviderHandler(
            connection_id=mock_connection_id
        )

        response = client.delete(f"/api/v1/providers/{mock_connection_id}")

        assert response.status_code == 204

        app.dependency_overrides.pop(factory_key, None)

    def test_disconnect_provider_not_found(self, client, mock_connection_id):
        """DELETE /api/v1/providers/{id} returns 404 when not found."""
        factory_key = handler_factory(DisconnectProviderHandler)
        app.dependency_overrides[factory_key] = lambda: MockDisconnectProviderHandler(
            error="Connection not found"
        )

        response = client.delete(f"/api/v1/providers/{mock_connection_id}")

        assert response.status_code == 404

        app.dependency_overrides.pop(factory_key, None)

    def test_disconnect_provider_forbidden(self, client, mock_connection_id):
        """DELETE /api/v1/providers/{id} returns 403 when not owned by user."""
        factory_key = handler_factory(DisconnectProviderHandler)
        app.dependency_overrides[factory_key] = lambda: MockDisconnectProviderHandler(
            error="Connection not owned by user"
        )

        response = client.delete(f"/api/v1/providers/{mock_connection_id}")

        assert response.status_code == 403

        app.dependency_overrides.pop(factory_key, None)
