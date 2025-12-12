"""API tests for session endpoints.

Tests the complete HTTP request/response cycle for session management:
- POST /api/v1/sessions (create session / login)
- GET /api/v1/sessions (list sessions)
- GET /api/v1/sessions/{id} (get session)
- DELETE /api/v1/sessions/{id} (revoke session)
- DELETE /api/v1/sessions/current (logout)
- DELETE /api/v1/sessions (revoke all)

Architecture:
- Uses real app with dependency overrides
- Mocks handlers to test request/response flow
- Tests validation, authorization, and error responses
- Verifies RFC 7807 compliance for errors

Note:
    These tests focus on request validation, authorization checks,
    and error response formats. Full stack testing (with real handlers
    and database) is covered in integration tests.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from uuid_extensions import uuid7

from src.core.result import Failure, Success
from src.main import app


# =============================================================================
# Test Doubles - Stub handlers and response types
# =============================================================================


@dataclass
class AuthenticatedUser:
    """Result from authentication handler."""

    user_id: UUID
    email: str
    roles: list[str]


@dataclass
class CreateSessionResponse:
    """Result from create session handler."""

    session_id: UUID
    device_info: str | None
    location: str | None
    expires_at: datetime


@dataclass
class AuthTokens:
    """Result from token generation handler."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = 900


@dataclass
class SessionListItem:
    """Individual session in list result."""

    id: UUID
    device_info: str | None
    ip_address: str | None
    location: str | None
    created_at: datetime | None
    last_activity_at: datetime | None
    expires_at: datetime | None
    is_revoked: bool
    is_current: bool


@dataclass
class SessionListResult:
    """Result from list sessions handler."""

    sessions: list[SessionListItem]
    total_count: int
    active_count: int


@dataclass
class SessionResult:
    """Result from get session handler."""

    id: UUID
    user_id: UUID
    device_info: str | None
    ip_address: str | None
    location: str | None
    created_at: datetime | None
    last_activity_at: datetime | None
    expires_at: datetime | None
    is_revoked: bool
    is_current: bool = False


class StubAuthenticateUserHandler:
    """Stub handler for user authentication."""

    async def handle(self, cmd, request=None):
        """Check email patterns to simulate different scenarios."""
        email = cmd.email

        if "invalid" in email:
            return Failure(error="invalid_credentials")
        if "locked" in email:
            return Failure(error="account_locked")
        if "unverified" in email:
            return Failure(error="email_not_verified")

        # Success case
        return Success(
            value=AuthenticatedUser(
                user_id=uuid7(),
                email=email,
                roles=["user"],
            )
        )


class StubCreateSessionHandler:
    """Stub handler for session creation."""

    async def handle(self, cmd):
        """Always return success with mock session."""
        now = datetime.now(UTC)
        return Success(
            value=CreateSessionResponse(
                session_id=uuid7(),
                device_info="Chrome on macOS",
                location="New York, US",
                expires_at=now + timedelta(days=30),
            )
        )


class StubGenerateAuthTokensHandler:
    """Stub handler for token generation."""

    async def handle(self, cmd):
        """Always return success with mock tokens."""
        return Success(
            value=AuthTokens(
                access_token="mock_access_token",
                refresh_token="mock_refresh_token",
                token_type="bearer",
                expires_in=900,
            )
        )


class StubLogoutUserHandler:
    """Stub handler for logout."""

    async def handle(self, cmd, request=None):
        """Always return success."""
        return Success(value=None)


class StubListSessionsHandler:
    """Stub handler for listing sessions."""

    async def handle(self, query):
        """Return success with one mock session."""
        now = datetime.now(UTC)
        session = SessionListItem(
            id=uuid7(),
            device_info="Chrome on macOS",
            ip_address="192.168.1.1",
            location="New York, US",
            created_at=now,
            last_activity_at=now,
            expires_at=now + timedelta(days=30),
            is_revoked=False,
            is_current=True,
        )
        return Success(
            value=SessionListResult(
                sessions=[session],
                total_count=1,
                active_count=1,
            )
        )


class StubGetSessionHandler:
    """Stub handler for getting a session."""

    async def handle(self, query):
        """Return not found for UUID ending in '000f', else success."""
        if str(query.session_id).endswith("000f"):
            return Failure(error="session_not_found")

        now = datetime.now(UTC)
        return Success(
            value=SessionResult(
                id=query.session_id,
                user_id=query.user_id,
                device_info="Chrome on macOS",
                ip_address="192.168.1.1",
                location="New York, US",
                created_at=now,
                last_activity_at=now,
                expires_at=now + timedelta(days=30),
                is_revoked=False,
                is_current=True,
            )
        )


class StubRevokeSessionHandler:
    """Stub handler for revoking a session."""

    async def handle(self, cmd):
        """Return not found for UUID ending in '000f', else success."""
        if str(cmd.session_id).endswith("000f"):
            return Failure(error="session_not_found")
        return Success(value=True)


class StubRevokeAllSessionsHandler:
    """Stub handler for revoking all sessions."""

    async def handle(self, cmd):
        """Always return success with count of 3."""
        return Success(value=3)


class StubTokenService:
    """Stub token service for extracting user/session from token."""

    def __init__(self, user_id: UUID, session_id: UUID):
        self._user_id = user_id
        self._session_id = session_id

    def validate_access_token(self, token: str):
        """Return success with user_id and session_id."""
        return Success(
            value={
                "sub": str(self._user_id),
                "session_id": str(self._session_id),
            }
        )


class StubSessionCache:
    """Stub session cache for session revocation checks."""

    def __init__(self, cache=None):
        """Initialize stub cache (ignore actual cache parameter)."""
        pass

    async def get(self, session_id: UUID):
        """Always return None (cache miss, fall through to database)."""
        return None

    async def set(self, session):
        """No-op for caching."""
        pass


class StubSessionRepository:
    """Stub session repository for session revocation checks."""

    def __init__(self, session_id: UUID):
        self._session_id = session_id

    async def find_by_id(self, session_id: UUID):
        """Return non-revoked session."""
        from dataclasses import dataclass

        @dataclass
        class StubSession:
            id: UUID
            is_revoked: bool = False

        # Return valid session if ID matches
        if session_id == self._session_id:
            return StubSession(id=session_id, is_revoked=False)
        return None


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_user_id():
    """Generate a user ID for testing."""
    return uuid7()


@pytest.fixture
def mock_session_id():
    """Generate a session ID for testing."""
    return uuid7()


@pytest.fixture(autouse=True)
def override_dependencies(mock_user_id, mock_session_id):
    """Override app dependencies with test doubles."""
    from src.core.container import (
        get_authenticate_user_handler,
        get_cache,
        get_create_session_handler,
        get_db_session,
        get_generate_auth_tokens_handler,
        get_logout_user_handler,
        get_list_sessions_handler,
        get_get_session_handler,
        get_revoke_session_handler,
        get_revoke_all_sessions_handler,
    )
    from unittest.mock import AsyncMock

    # Override all session-related handlers
    app.dependency_overrides[get_authenticate_user_handler] = (
        lambda: StubAuthenticateUserHandler()
    )
    app.dependency_overrides[get_create_session_handler] = (
        lambda: StubCreateSessionHandler()
    )
    app.dependency_overrides[get_generate_auth_tokens_handler] = (
        lambda: StubGenerateAuthTokensHandler()
    )
    app.dependency_overrides[get_logout_user_handler] = lambda: StubLogoutUserHandler()
    app.dependency_overrides[get_list_sessions_handler] = (
        lambda: StubListSessionsHandler()
    )
    app.dependency_overrides[get_get_session_handler] = lambda: StubGetSessionHandler()
    app.dependency_overrides[get_revoke_session_handler] = (
        lambda: StubRevokeSessionHandler()
    )
    app.dependency_overrides[get_revoke_all_sessions_handler] = (
        lambda: StubRevokeAllSessionsHandler()
    )

    # Override cache dependency (used for session revocation checks)
    mock_cache = AsyncMock()
    app.dependency_overrides[get_cache] = lambda: mock_cache

    # Override db_session dependency (used for session revocation checks)
    mock_db_session = AsyncMock()
    app.dependency_overrides[get_db_session] = lambda: mock_db_session

    # Monkeypatch get_token_service used directly in sessions router
    # to validate Authorization header
    import src.core.container as container_module

    original_get_token_service = container_module.get_token_service

    def mock_get_token_service():
        return StubTokenService(mock_user_id, mock_session_id)

    container_module.get_token_service = mock_get_token_service

    # Monkeypatch SessionCache and SessionRepository used in helper functions
    import src.infrastructure.cache as cache_module
    import src.infrastructure.persistence.repositories as repo_module

    original_redis_session_cache = cache_module.RedisSessionCache
    original_session_repository = repo_module.SessionRepository

    cache_module.RedisSessionCache = StubSessionCache

    # SessionRepository needs session_id to return valid session
    def mock_session_repository_factory(session):
        return StubSessionRepository(mock_session_id)

    repo_module.SessionRepository = mock_session_repository_factory

    yield

    # Cleanup
    app.dependency_overrides.clear()
    container_module.get_token_service = original_get_token_service
    cache_module.RedisSessionCache = original_redis_session_cache
    repo_module.SessionRepository = original_session_repository


@pytest.fixture
def client():
    """Create TestClient for API tests using real app."""
    return TestClient(app, raise_server_exceptions=False)


# =============================================================================
# POST /api/v1/sessions (Create Session / Login)
# =============================================================================


@pytest.mark.api
class TestCreateSession:
    """Tests for POST /api/v1/sessions endpoint."""

    def test_create_session_success(self, client):
        """Test successful session creation returns 201 with tokens."""
        response = client.post(
            "/api/v1/sessions",
            json={"email": "test@example.com", "password": "Password123!"},
        )

        assert response.status_code == 201
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        assert data["expires_in"] == 900

    def test_create_session_invalid_credentials(self, client):
        """Test invalid credentials returns 401."""
        response = client.post(
            "/api/v1/sessions",
            json={"email": "invalid@example.com", "password": "wrongpassword"},
        )

        assert response.status_code == 401
        data = response.json()
        assert data["title"] == "Invalid Credentials"
        assert data["status"] == 401

    def test_create_session_account_locked(self, client):
        """Test locked account returns 403."""
        response = client.post(
            "/api/v1/sessions",
            json={"email": "locked@example.com", "password": "Password123!"},
        )

        assert response.status_code == 403
        data = response.json()
        assert data["title"] == "Account Locked"

    def test_create_session_email_not_verified(self, client):
        """Test unverified email returns 403."""
        response = client.post(
            "/api/v1/sessions",
            json={"email": "unverified@example.com", "password": "Password123!"},
        )

        assert response.status_code == 403
        data = response.json()
        assert data["title"] == "Email Not Verified"

    def test_create_session_missing_email(self, client):
        """Test missing email returns 422 validation error."""
        response = client.post(
            "/api/v1/sessions",
            json={"password": "Password123!"},
        )

        assert response.status_code == 422

    def test_create_session_missing_password(self, client):
        """Test missing password returns 422 validation error."""
        response = client.post(
            "/api/v1/sessions",
            json={"email": "test@example.com"},
        )

        assert response.status_code == 422


# =============================================================================
# GET /api/v1/sessions (List Sessions)
# =============================================================================


@pytest.mark.api
class TestListSessions:
    """Tests for GET /api/v1/sessions endpoint."""

    def test_list_sessions_unauthorized_no_token(self, client):
        """Test listing sessions without token returns 401."""
        response = client.get("/api/v1/sessions")

        assert response.status_code == 401
        data = response.json()
        assert data["title"] == "Unauthorized"

    def test_list_sessions_success(self, client):
        """Test successful session listing returns 200."""
        response = client.get(
            "/api/v1/sessions",
            headers={"Authorization": "Bearer mock_token"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total_count"] == 1
        assert data["active_count"] == 1
        assert len(data["sessions"]) == 1
        assert data["sessions"][0]["device_info"] == "Chrome on macOS"
        assert data["sessions"][0]["is_current"] is True


# =============================================================================
# GET /api/v1/sessions/{id} (Get Session)
# =============================================================================


@pytest.mark.api
class TestGetSession:
    """Tests for GET /api/v1/sessions/{id} endpoint."""

    def test_get_session_unauthorized(self, client):
        """Test getting session without token returns 401."""
        session_id = str(uuid7())
        response = client.get(f"/api/v1/sessions/{session_id}")

        assert response.status_code == 401

    def test_get_session_success(self, client):
        """Test successful session retrieval returns 200."""
        session_id = str(uuid7())
        response = client.get(
            f"/api/v1/sessions/{session_id}",
            headers={"Authorization": "Bearer mock_token"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == session_id
        assert data["device_info"] == "Chrome on macOS"

    def test_get_session_not_found(self, client):
        """Test session not found returns 404."""
        # Use valid UUID ending in '000f' to trigger not found in stub
        notfound_id = "00000000-0000-0000-0000-00000000000f"
        response = client.get(
            f"/api/v1/sessions/{notfound_id}",
            headers={"Authorization": "Bearer mock_token"},
        )

        assert response.status_code == 404
        data = response.json()
        assert data["title"] == "Not Found"


# =============================================================================
# DELETE /api/v1/sessions/{id} (Revoke Session)
# =============================================================================


@pytest.mark.api
class TestRevokeSession:
    """Tests for DELETE /api/v1/sessions/{id} endpoint."""

    def test_revoke_session_unauthorized(self, client):
        """Test revoking session without token returns 401."""
        session_id = str(uuid7())
        response = client.delete(f"/api/v1/sessions/{session_id}")

        assert response.status_code == 401

    def test_revoke_session_success(self, client):
        """Test successful session revocation returns 204."""
        session_id = str(uuid7())
        response = client.delete(
            f"/api/v1/sessions/{session_id}",
            headers={"Authorization": "Bearer mock_token"},
        )

        assert response.status_code == 204

    def test_revoke_session_not_found(self, client):
        """Test revoking non-existent session returns 404."""
        # Use valid UUID ending in '000f' to trigger not found in stub
        notfound_id = "00000000-0000-0000-0000-00000000000f"
        response = client.delete(
            f"/api/v1/sessions/{notfound_id}",
            headers={"Authorization": "Bearer mock_token"},
        )

        assert response.status_code == 404


# =============================================================================
# DELETE /api/v1/sessions/current (Logout)
# =============================================================================


@pytest.mark.api
class TestDeleteCurrentSession:
    """Tests for DELETE /api/v1/sessions/current endpoint."""

    def test_logout_unauthorized(self, client):
        """Test logout without token returns 401."""
        response = client.request(
            "DELETE",
            "/api/v1/sessions/current",
            json={"refresh_token": "mock_refresh_token"},
        )

        assert response.status_code == 401

    def test_logout_success(self, client):
        """Test successful logout returns 204."""
        response = client.request(
            "DELETE",
            "/api/v1/sessions/current",
            json={"refresh_token": "mock_refresh_token"},
            headers={"Authorization": "Bearer mock_token"},
        )

        assert response.status_code == 204


# =============================================================================
# DELETE /api/v1/sessions (Revoke All Sessions)
# =============================================================================


@pytest.mark.api
class TestRevokeAllSessions:
    """Tests for DELETE /api/v1/sessions endpoint."""

    def test_revoke_all_unauthorized(self, client):
        """Test revoking all sessions without token returns 401."""
        response = client.delete("/api/v1/sessions")

        assert response.status_code == 401

    def test_revoke_all_success(self, client):
        """Test successful revoke all returns 200 with count."""
        response = client.delete(
            "/api/v1/sessions",
            headers={"Authorization": "Bearer mock_token"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["revoked_count"] == 3
        assert "3 session(s) revoked successfully" in data["message"]


# =============================================================================
# Response Format Tests
# =============================================================================


@pytest.mark.api
class TestSessionResponseFormats:
    """Tests for session response formatting."""

    def test_session_response_includes_all_fields(self, client):
        """Test session response includes all expected fields."""
        session_id = str(uuid7())
        response = client.get(
            f"/api/v1/sessions/{session_id}",
            headers={"Authorization": "Bearer mock_token"},
        )

        assert response.status_code == 200
        data = response.json()

        # Verify all fields present
        assert "id" in data
        assert "device_info" in data
        assert "ip_address" in data
        assert "location" in data
        assert "created_at" in data
        assert "last_activity_at" in data
        assert "expires_at" in data
        assert "is_current" in data
        assert "is_revoked" in data

    def test_error_response_is_rfc7807_compliant(self, client):
        """Test error responses follow RFC 7807 format."""
        response = client.get("/api/v1/sessions")  # No auth token

        assert response.status_code == 401
        data = response.json()

        # RFC 7807 required fields
        assert "type" in data
        assert "title" in data
        assert "status" in data
        assert "detail" in data
        assert "instance" in data

    def test_create_session_response_format(self, client):
        """Test create session response contains required token fields."""
        response = client.post(
            "/api/v1/sessions",
            json={"email": "test@example.com", "password": "Password123!"},
        )

        assert response.status_code == 201
        data = response.json()

        # Token response fields
        assert "access_token" in data
        assert "refresh_token" in data
        assert "token_type" in data
        assert "expires_in" in data

    def test_list_sessions_response_format(self, client):
        """Test list sessions response contains required fields."""
        response = client.get(
            "/api/v1/sessions",
            headers={"Authorization": "Bearer mock_token"},
        )

        assert response.status_code == 200
        data = response.json()

        # List response fields
        assert "sessions" in data
        assert "total_count" in data
        assert "active_count" in data
        assert isinstance(data["sessions"], list)
