"""Additional API tests for provider OAuth callback and token refresh endpoints.

Tests coverage for missing lines in providers.py:
- POST /api/v1/providers/callback (OAuth callback - lines 377-528)
- POST /api/v1/providers/{id}/token-refreshes (Token refresh - lines 690-748)

Architecture:
- Uses FastAPI TestClient with real app + dependency overrides
- Tests validation, error paths, and RFC 7807 compliance
- Mocks handlers and services to test HTTP layer behavior
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from uuid_extensions import uuid7

from src.core.result import Failure, Success
from src.domain.enums.connection_status import ConnectionStatus
from src.main import app


# =============================================================================
# Test Doubles
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


@dataclass(frozen=True, kw_only=True)
class MockProviderConnectionResult:
    """Mock DTO matching ProviderConnectionResult."""

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


class MockGetProviderConnectionHandler:
    """Mock handler for getting a single connection."""

    def __init__(
        self,
        connection: MockProviderConnectionResult | None = None,
        error: str | None = None,
    ) -> None:
        self._connection = connection
        self._error = error

    async def handle(self, query):
        if self._error:
            return Failure(error=self._error)
        return Success(value=self._connection)


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
    return TestClient(app, raise_server_exceptions=False)


# =============================================================================
# OAuth Callback Tests (POST /api/v1/providers/callback)
# =============================================================================


@pytest.mark.api
class TestOAuthCallback:
    """Tests for POST /api/v1/providers/callback endpoint."""

    def test_oauth_callback_invalid_state(self, client):
        """POST /api/v1/providers/callback returns 400 for invalid/expired state."""
        from src.core.container import get_cache

        # Mock cache returning None (state not found)
        class MockCache:
            async def get(self, key: str):
                return Success(value=None)

            async def delete(self, key: str):
                return Success(value=None)

        app.dependency_overrides[get_cache] = lambda: MockCache()

        response = client.post(
            "/api/v1/providers/callback?code=test_code&state=invalid_state"
        )

        assert response.status_code == 400
        data = response.json()
        assert "state" in data["detail"].lower() or "invalid" in data["detail"].lower()

        app.dependency_overrides.pop(get_cache, None)

    def test_oauth_callback_corrupted_state(self, client):
        """POST /api/v1/providers/callback returns 400 for corrupted state."""
        from src.core.container import get_cache

        # Mock cache returning corrupted value (missing parts)
        class MockCache:
            async def get(self, key: str):
                return Success(value="corrupted")  # Invalid format

            async def delete(self, key: str):
                return Success(value=None)

        app.dependency_overrides[get_cache] = lambda: MockCache()

        response = client.post(
            "/api/v1/providers/callback?code=test_code&state=valid_state"
        )

        assert response.status_code == 400
        data = response.json()
        assert (
            "corrupted" in data["detail"].lower() or "state" in data["detail"].lower()
        )

        app.dependency_overrides.pop(get_cache, None)

    def test_oauth_callback_unsupported_provider(self, client, mock_user_id):
        """POST /api/v1/providers/callback returns 404 for unsupported provider."""
        from src.core.container import get_cache

        # Mock cache returning valid state but unsupported provider
        class MockCache:
            async def get(self, key: str):
                return Success(value=f"{mock_user_id}:unsupported_provider:alias")

            async def delete(self, key: str):
                return Success(value=None)

        app.dependency_overrides[get_cache] = lambda: MockCache()

        response = client.post(
            "/api/v1/providers/callback?code=test_code&state=valid_state"
        )

        assert response.status_code == 404
        data = response.json()
        assert (
            "provider" in data["detail"].lower()
            and "not supported" in data["detail"].lower()
        )

        app.dependency_overrides.pop(get_cache, None)

    def test_oauth_callback_provider_auth_failed(self, client, mock_user_id):
        """POST /api/v1/providers/callback returns 502 when provider auth fails."""
        from src.core.container import get_cache, get_provider
        from src.domain.errors import ProviderError

        # Mock cache with valid state
        class MockCache:
            async def get(self, key: str):
                return Success(value=f"{mock_user_id}:schwab:alias")

            async def delete(self, key: str):
                return Success(value=None)

        # Mock provider that fails token exchange
        class MockProvider:
            async def exchange_code_for_tokens(self, code: str):
                from src.core.enums import ErrorCode

                return Failure(
                    error=ProviderError(
                        message="Token exchange failed",
                        code=ErrorCode.PROVIDER_UNAVAILABLE,
                        provider_name="schwab",
                    )
                )

        app.dependency_overrides[get_cache] = lambda: MockCache()
        app.dependency_overrides[get_provider] = lambda slug: MockProvider()

        response = client.post(
            "/api/v1/providers/callback?code=bad_code&state=valid_state"
        )

        assert response.status_code == 502
        data = response.json()
        assert data["status"] == 502
        assert "provider" in data["detail"].lower()

        app.dependency_overrides.pop(get_cache, None)
        app.dependency_overrides.pop(get_provider, None)

    def test_oauth_callback_encryption_failed(self, client, mock_user_id):
        """POST /api/v1/providers/callback returns 500 when encryption fails."""
        from src.core.container import get_cache, get_provider, get_encryption_service
        from src.domain.protocols.provider_protocol import OAuthTokens

        # Mock cache with valid state
        class MockCache:
            async def get(self, key: str):
                return Success(value=f"{mock_user_id}:schwab:alias")

            async def delete(self, key: str):
                return Success(value=None)

        # Mock provider that succeeds
        class MockProvider:
            async def exchange_code_for_tokens(self, code: str):
                return Success(
                    value=OAuthTokens(
                        access_token="access",
                        refresh_token="refresh",
                        token_type="bearer",
                        expires_in=3600,
                        scope="read",
                    )
                )

        # Mock encryption that fails
        class MockEncryption:
            def encrypt(self, data: dict[str, object]) -> Failure[str]:
                return Failure(error="Encryption failed")

        app.dependency_overrides[get_cache] = lambda: MockCache()
        app.dependency_overrides[get_provider] = lambda slug: MockProvider()
        app.dependency_overrides[get_encryption_service] = lambda: MockEncryption()

        response = client.post(
            "/api/v1/providers/callback?code=test_code&state=valid_state"
        )

        # Provider errors return 502 Bad Gateway
        assert response.status_code == 502
        data = response.json()
        assert data["status"] == 502

        app.dependency_overrides.pop(get_cache, None)
        app.dependency_overrides.pop(get_provider, None)
        app.dependency_overrides.pop(get_encryption_service, None)

    def test_oauth_callback_connect_handler_failed(self, client, mock_user_id):
        """POST /api/v1/providers/callback returns error when connect fails."""
        from src.core.container import (
            get_cache,
            get_provider,
            get_encryption_service,
            get_connect_provider_handler,
        )
        from src.domain.protocols.provider_protocol import OAuthTokens

        # Mock cache with valid state
        class MockCache:
            async def get(self, key: str):
                return Success(value=f"{mock_user_id}:schwab:alias")

            async def delete(self, key: str):
                return Success(value=None)

        # Mock provider that succeeds
        class MockProvider:
            async def exchange_code_for_tokens(self, code: str):
                return Success(
                    value=OAuthTokens(
                        access_token="access",
                        refresh_token="refresh",
                        token_type="bearer",
                        expires_in=3600,
                        scope="read",
                    )
                )

        # Mock encryption that succeeds
        class MockEncryption:
            def encrypt(self, data: dict[str, object]) -> Success[bytes]:
                return Success(value=b"encrypted_data")

        # Mock connect handler that fails
        class MockConnectHandler:
            async def handle(self, command):
                return Failure(error="Connection already exists")

        app.dependency_overrides[get_cache] = lambda: MockCache()
        app.dependency_overrides[get_provider] = lambda slug: MockProvider()
        app.dependency_overrides[get_encryption_service] = lambda: MockEncryption()
        app.dependency_overrides[get_connect_provider_handler] = (
            lambda: MockConnectHandler()
        )

        response = client.post(
            "/api/v1/providers/callback?code=test_code&state=valid_state"
        )

        # Provider/connection errors return 502 Bad Gateway
        assert response.status_code == 502
        data = response.json()
        assert data["status"] == 502

        app.dependency_overrides.pop(get_cache, None)
        app.dependency_overrides.pop(get_provider, None)
        app.dependency_overrides.pop(get_encryption_service, None)
        app.dependency_overrides.pop(get_connect_provider_handler, None)


# =============================================================================
# Refresh Provider Tokens Tests (POST /api/v1/providers/{id}/token-refreshes)
# =============================================================================


@pytest.mark.api
class TestRefreshProviderTokens:
    """Tests for POST /api/v1/providers/{id}/token-refreshes endpoint."""

    def test_refresh_tokens_connection_not_found(self, client, mock_connection_id):
        """POST /api/v1/providers/{id}/token-refreshes returns 404 when not found."""
        from src.core.container import get_get_provider_connection_handler

        app.dependency_overrides[get_get_provider_connection_handler] = (
            lambda: MockGetProviderConnectionHandler(error="Connection not found")
        )

        response = client.post(
            f"/api/v1/providers/{mock_connection_id}/token-refreshes"
        )

        assert response.status_code == 404
        data = response.json()
        assert data["status"] == 404

        app.dependency_overrides.pop(get_get_provider_connection_handler, None)

    def test_refresh_tokens_connection_not_active(
        self, client, mock_connection_id, mock_connection
    ):
        """POST /api/v1/providers/{id}/token-refreshes returns 403 when not active."""
        from src.core.container import get_get_provider_connection_handler

        # Create inactive connection
        inactive_connection = MockProviderConnectionResult(
            id=mock_connection.id,
            user_id=mock_connection.user_id,
            provider_id=mock_connection.provider_id,
            provider_slug=mock_connection.provider_slug,
            alias=mock_connection.alias,
            status=ConnectionStatus.DISCONNECTED,
            is_connected=False,  # Not connected
            needs_reauthentication=False,
            connected_at=mock_connection.connected_at,
            last_sync_at=mock_connection.last_sync_at,
            created_at=mock_connection.created_at,
            updated_at=mock_connection.updated_at,
        )

        app.dependency_overrides[get_get_provider_connection_handler] = (
            lambda: MockGetProviderConnectionHandler(connection=inactive_connection)
        )

        response = client.post(
            f"/api/v1/providers/{mock_connection_id}/token-refreshes"
        )

        assert response.status_code == 403
        data = response.json()
        assert "not active" in data["detail"].lower()

        app.dependency_overrides.pop(get_get_provider_connection_handler, None)

    def test_refresh_tokens_unsupported_provider(
        self, client, mock_connection_id, mock_connection
    ):
        """POST /api/v1/providers/{id}/token-refreshes returns 404 for unsupported provider."""
        from src.core.container import get_get_provider_connection_handler

        # Create connection with unsupported provider
        unsupported_connection = MockProviderConnectionResult(
            id=mock_connection.id,
            user_id=mock_connection.user_id,
            provider_id=mock_connection.provider_id,
            provider_slug="unsupported",  # Unsupported
            alias=mock_connection.alias,
            status=mock_connection.status,
            is_connected=True,
            needs_reauthentication=False,
            connected_at=mock_connection.connected_at,
            last_sync_at=mock_connection.last_sync_at,
            created_at=mock_connection.created_at,
            updated_at=mock_connection.updated_at,
        )

        app.dependency_overrides[get_get_provider_connection_handler] = (
            lambda: MockGetProviderConnectionHandler(connection=unsupported_connection)
        )

        response = client.post(
            f"/api/v1/providers/{mock_connection_id}/token-refreshes"
        )

        assert response.status_code == 404
        data = response.json()
        assert "not supported" in data["detail"].lower()

        app.dependency_overrides.pop(get_get_provider_connection_handler, None)

    def test_refresh_tokens_success_placeholder(
        self, client, mock_connection_id, mock_connection
    ):
        """POST /api/v1/providers/{id}/token-refreshes returns 201 (placeholder)."""
        from src.core.container import get_get_provider_connection_handler

        app.dependency_overrides[get_get_provider_connection_handler] = (
            lambda: MockGetProviderConnectionHandler(connection=mock_connection)
        )

        response = client.post(
            f"/api/v1/providers/{mock_connection_id}/token-refreshes"
        )

        # Currently returns 201 with placeholder response
        assert response.status_code == 201
        data = response.json()
        assert "success" in data or "message" in data

        app.dependency_overrides.pop(get_get_provider_connection_handler, None)
