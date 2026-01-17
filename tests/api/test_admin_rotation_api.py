"""API tests for admin token rotation endpoints.

Tests the complete HTTP request/response cycle for admin rotation:
- POST /api/v1/admin/security/rotations (global rotation)
- POST /api/v1/admin/users/{user_id}/rotations (per-user rotation)
- GET /api/v1/admin/security/config (get security config)

Architecture:
- Uses real app with dependency overrides
- Mocks handlers, database, and authentication dependencies
- Tests validation, status codes, and error responses
- Verifies RFC 9457 compliance for errors
- Verifies 401/403 for unauthenticated/unauthorized access
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from src.application.commands.handlers.trigger_global_rotation_handler import (
    TriggerGlobalTokenRotationHandler,
)
from src.application.commands.handlers.trigger_user_rotation_handler import (
    TriggerUserTokenRotationHandler,
)
from src.core.container.handler_factory import handler_factory
from src.core.result import Failure, Success
from src.main import app
from src.presentation.routers.api.middleware.auth_dependencies import CurrentUser
from uuid_extensions import uuid7


# =============================================================================
# Test Doubles
# =============================================================================


@dataclass
class GlobalRotationResult:
    """Result from global rotation handler."""

    previous_version: int
    new_version: int
    grace_period_seconds: int


@dataclass
class UserRotationResult:
    """Result from user rotation handler."""

    user_id: UUID
    previous_version: int
    new_version: int


@dataclass
class SecurityConfig:
    """Security configuration entity."""

    global_min_token_version: int
    grace_period_seconds: int
    last_rotation_at: datetime | None
    last_rotation_reason: str | None


class StubGlobalRotationHandler:
    """Stub handler for global token rotation."""

    def __init__(self):
        self.global_version = 1
        self.grace_period = 300
        self.last_reason = None

    async def handle(self, command):
        previous = self.global_version
        self.global_version += 1
        self.last_reason = command.reason

        return Success(
            value=GlobalRotationResult(
                previous_version=previous,
                new_version=self.global_version,
                grace_period_seconds=self.grace_period,
            )
        )


class StubUserRotationHandler:
    """Stub handler for per-user token rotation."""

    def __init__(self):
        self.user_versions: dict[UUID, int] = {}

    async def handle(self, command):
        user_id = command.user_id

        # Simulate user not found for special test UUID ending in '000f'
        if str(user_id).endswith("000f"):
            return Failure(error="user_not_found")

        # Initialize or get user version
        if user_id not in self.user_versions:
            self.user_versions[user_id] = 1

        previous = self.user_versions[user_id]
        self.user_versions[user_id] += 1

        return Success(
            value=UserRotationResult(
                user_id=user_id,
                previous_version=previous,
                new_version=self.user_versions[user_id],
            )
        )


class StubSecurityConfigRepository:
    """Stub repository for security config."""

    def __init__(self, global_rotation_handler: StubGlobalRotationHandler):
        self._global_handler = global_rotation_handler

    async def get_or_create_default(self):
        return SecurityConfig(
            global_min_token_version=self._global_handler.global_version,
            grace_period_seconds=self._global_handler.grace_period,
            last_rotation_at=datetime.now(UTC)
            if self._global_handler.last_reason
            else None,
            last_rotation_reason=self._global_handler.last_reason,
        )


class StubAuthorizationProtocol:
    """Stub authorization that always allows admin."""

    async def check_permission(self, user_id: UUID, resource: str, action: str) -> bool:
        return True

    async def has_role(self, user_id: UUID, role: str) -> bool:
        # Return True for admin role
        return role == "admin"


class StubAuthorizationDenied:
    """Stub authorization that denies admin role."""

    async def check_permission(self, user_id: UUID, resource: str, action: str) -> bool:
        return False

    async def has_role(self, user_id: UUID, role: str) -> bool:
        return False


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def admin_user():
    """Create admin user for authenticated requests."""
    return CurrentUser(
        user_id=uuid7(),
        email="admin@example.com",
        roles=["admin"],
    )


@pytest.fixture
def global_handler():
    """Create stub global rotation handler."""
    return StubGlobalRotationHandler()


@pytest.fixture
def user_handler():
    """Create stub user rotation handler."""
    return StubUserRotationHandler()


@pytest.fixture(autouse=True)
def override_dependencies(global_handler, user_handler, admin_user):
    """Override app dependencies with test doubles."""
    from src.core.container import (
        get_db_session,
        get_authorization,
    )
    from src.presentation.routers.api.middleware.auth_dependencies import (
        get_current_user,
    )

    # Use handler_factory pattern for handler overrides
    global_factory_key = handler_factory(TriggerGlobalTokenRotationHandler)
    user_factory_key = handler_factory(TriggerUserTokenRotationHandler)

    app.dependency_overrides[global_factory_key] = lambda: global_handler
    app.dependency_overrides[user_factory_key] = lambda: user_handler

    # Mock authentication - return admin user
    app.dependency_overrides[get_current_user] = lambda: admin_user

    # Mock authorization - allow admin role
    app.dependency_overrides[get_authorization] = lambda: StubAuthorizationProtocol()

    # Mock db_session for security config endpoint
    async def mock_db_session():
        # Return a stub that won't be used (repository is mocked below)
        return None

    app.dependency_overrides[get_db_session] = mock_db_session

    # Monkeypatch SecurityConfigRepository to return our stub
    import src.presentation.routers.api.v1.admin.token_rotation as rotation_module

    original_repo = getattr(rotation_module, "SecurityConfigRepository", None)

    def stub_repo_factory(session: object) -> StubSecurityConfigRepository:
        return StubSecurityConfigRepository(global_handler)

    setattr(rotation_module, "SecurityConfigRepository", stub_repo_factory)

    yield

    # Cleanup
    app.dependency_overrides.clear()
    if original_repo is not None:
        setattr(rotation_module, "SecurityConfigRepository", original_repo)


@pytest.fixture
def client():
    """Create test client with real app."""
    return TestClient(app)


# =============================================================================
# Global Rotation Tests
# =============================================================================


@pytest.mark.api
class TestGlobalRotationEndpoint:
    """Test POST /api/v1/admin/security/rotations endpoint."""

    def test_global_rotation_returns_201_created(self, client):
        """Test successful rotation returns 201 Created."""
        response = client.post(
            "/api/v1/admin/security/rotations",
            json={"reason": "Security breach detected"},
        )

        assert response.status_code == status.HTTP_201_CREATED

    def test_global_rotation_returns_version_info(self, client):
        """Test rotation response includes version information."""
        response = client.post(
            "/api/v1/admin/security/rotations",
            json={"reason": "Test rotation"},
        )

        data = response.json()
        assert "previous_version" in data
        assert "new_version" in data
        assert "grace_period_seconds" in data
        assert data["new_version"] == data["previous_version"] + 1

    def test_global_rotation_increments_version(self, client):
        """Test multiple rotations increment version."""
        # First rotation
        response1 = client.post(
            "/api/v1/admin/security/rotations",
            json={"reason": "First rotation"},
        )
        version1 = response1.json()["new_version"]

        # Second rotation
        response2 = client.post(
            "/api/v1/admin/security/rotations",
            json={"reason": "Second rotation"},
        )
        version2 = response2.json()["new_version"]

        assert version2 == version1 + 1

    def test_global_rotation_requires_reason(self, client):
        """Test rotation requires reason field."""
        response = client.post(
            "/api/v1/admin/security/rotations",
            json={},
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_global_rotation_returns_grace_period(self, client):
        """Test rotation response includes grace period."""
        response = client.post(
            "/api/v1/admin/security/rotations",
            json={"reason": "Test"},
        )

        data = response.json()
        assert "grace_period_seconds" in data
        assert isinstance(data["grace_period_seconds"], int)


# =============================================================================
# Per-User Rotation Tests
# =============================================================================


@pytest.mark.api
class TestUserRotationEndpoint:
    """Test POST /api/v1/admin/users/{user_id}/rotations endpoint."""

    def test_user_rotation_returns_201_created(self, client):
        """Test successful rotation returns 201 Created."""
        user_id = str(uuid7())
        response = client.post(
            f"/api/v1/admin/users/{user_id}/rotations",
            json={"reason": "Password changed"},
        )

        assert response.status_code == status.HTTP_201_CREATED

    def test_user_rotation_returns_user_id(self, client):
        """Test rotation response includes user_id."""
        user_id = str(uuid7())
        response = client.post(
            f"/api/v1/admin/users/{user_id}/rotations",
            json={"reason": "Suspicious activity"},
        )

        data = response.json()
        assert "user_id" in data
        assert data["user_id"] == user_id

    def test_user_rotation_returns_version_info(self, client):
        """Test rotation response includes version information."""
        user_id = str(uuid7())
        response = client.post(
            f"/api/v1/admin/users/{user_id}/rotations",
            json={"reason": "Test"},
        )

        data = response.json()
        assert "previous_version" in data
        assert "new_version" in data
        assert data["new_version"] == data["previous_version"] + 1

    def test_user_rotation_returns_404_for_nonexistent_user(self, client):
        """Test rotation returns 404 for non-existent user."""
        # Use a valid UUID ending in '000f' to trigger not found in stub handler
        notfound_uuid = "00000000-0000-0000-0000-00000000000f"

        response = client.post(
            f"/api/v1/admin/users/{notfound_uuid}/rotations",
            json={"reason": "Test"},
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        data = response.json()
        assert data["title"] == "Resource Not Found"

    def test_user_rotation_requires_reason(self, client):
        """Test rotation requires reason field."""
        user_id = str(uuid7())
        response = client.post(
            f"/api/v1/admin/users/{user_id}/rotations",
            json={},
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


# =============================================================================
# Security Config Tests
# =============================================================================


@pytest.mark.api
class TestSecurityConfigEndpoint:
    """Test GET /api/v1/admin/security/config endpoint."""

    def test_get_config_returns_200(self, client):
        """Test config retrieval returns 200 OK."""
        response = client.get("/api/v1/admin/security/config")

        assert response.status_code == status.HTTP_200_OK

    def test_get_config_returns_version(self, client):
        """Test config includes global_min_token_version."""
        response = client.get("/api/v1/admin/security/config")

        data = response.json()
        assert "global_min_token_version" in data
        assert isinstance(data["global_min_token_version"], int)

    def test_get_config_returns_grace_period(self, client):
        """Test config includes grace_period_seconds."""
        response = client.get("/api/v1/admin/security/config")

        data = response.json()
        assert "grace_period_seconds" in data
        assert isinstance(data["grace_period_seconds"], int)

    def test_get_config_reflects_rotation(self, client):
        """Test config reflects rotation changes."""
        # Initial config
        response1 = client.get("/api/v1/admin/security/config")
        initial_version = response1.json()["global_min_token_version"]

        # Perform rotation
        client.post(
            "/api/v1/admin/security/rotations",
            json={"reason": "Test rotation"},
        )

        # Check updated config
        response2 = client.get("/api/v1/admin/security/config")
        new_version = response2.json()["global_min_token_version"]

        assert new_version == initial_version + 1

    def test_get_config_includes_last_rotation_info(self, client):
        """Test config includes last rotation metadata after rotation."""
        # Perform rotation
        client.post(
            "/api/v1/admin/security/rotations",
            json={"reason": "Audit test rotation"},
        )

        # Check config
        response = client.get("/api/v1/admin/security/config")
        data = response.json()

        assert data["last_rotation_reason"] == "Audit test rotation"
        assert data["last_rotation_at"] is not None


# =============================================================================
# Authentication & Authorization Tests
# =============================================================================


@pytest.mark.api
class TestAdminAuthenticationRequired:
    """Test that admin endpoints require authentication."""

    def test_global_rotation_returns_401_without_auth(self):
        """Test global rotation returns 401 without authentication."""
        # Clear all overrides to test without auth
        app.dependency_overrides.clear()

        try:
            client = TestClient(app)
            response = client.post(
                "/api/v1/admin/security/rotations",
                json={"reason": "Test rotation"},
            )

            # Returns 401 from HTTPBearer when no Authorization header
            assert (
                response.status_code
                in (
                    status.HTTP_401_UNAUTHORIZED,
                    status.HTTP_403_FORBIDDEN,  # May return 403 if auth check passes but authz fails
                )
            )
        finally:
            app.dependency_overrides.clear()

    def test_user_rotation_returns_401_without_auth(self):
        """Test per-user rotation returns 401 without authentication."""
        app.dependency_overrides.clear()

        try:
            client = TestClient(app)
            user_id = str(uuid7())
            response = client.post(
                f"/api/v1/admin/users/{user_id}/rotations",
                json={"reason": "Test rotation"},
            )

            assert response.status_code in (
                status.HTTP_401_UNAUTHORIZED,
                status.HTTP_403_FORBIDDEN,
            )
        finally:
            app.dependency_overrides.clear()

    def test_get_config_returns_401_without_auth(self):
        """Test get config returns 401 without authentication."""
        app.dependency_overrides.clear()

        try:
            client = TestClient(app)
            response = client.get("/api/v1/admin/security/config")

            assert response.status_code in (
                status.HTTP_401_UNAUTHORIZED,
                status.HTTP_403_FORBIDDEN,
            )
        finally:
            app.dependency_overrides.clear()


@pytest.mark.api
class TestAdminAuthorizationRequired:
    """Test that admin endpoints require admin role."""

    def test_global_rotation_returns_403_without_admin_role(self):
        """Test global rotation returns 403 for non-admin user."""
        from src.core.container import get_authorization
        from src.presentation.routers.api.middleware.auth_dependencies import (
            get_current_user,
        )

        # Setup: authenticated but non-admin user
        regular_user = CurrentUser(
            user_id=uuid7(),
            email="user@example.com",
            roles=["user"],  # Not admin
        )

        app.dependency_overrides[get_current_user] = lambda: regular_user
        app.dependency_overrides[get_authorization] = lambda: StubAuthorizationDenied()

        try:
            client = TestClient(app)
            response = client.post(
                "/api/v1/admin/security/rotations",
                json={"reason": "Test rotation"},
            )

            assert response.status_code == status.HTTP_403_FORBIDDEN
        finally:
            app.dependency_overrides.clear()

    def test_user_rotation_returns_403_without_admin_role(self):
        """Test per-user rotation returns 403 for non-admin user."""
        from src.core.container import get_authorization
        from src.presentation.routers.api.middleware.auth_dependencies import (
            get_current_user,
        )

        regular_user = CurrentUser(
            user_id=uuid7(),
            email="user@example.com",
            roles=["user"],
        )

        app.dependency_overrides[get_current_user] = lambda: regular_user
        app.dependency_overrides[get_authorization] = lambda: StubAuthorizationDenied()

        try:
            client = TestClient(app)
            user_id = str(uuid7())
            response = client.post(
                f"/api/v1/admin/users/{user_id}/rotations",
                json={"reason": "Test rotation"},
            )

            assert response.status_code == status.HTTP_403_FORBIDDEN
        finally:
            app.dependency_overrides.clear()

    def test_get_config_returns_403_without_admin_role(self):
        """Test get config returns 403 for non-admin user."""
        from src.core.container import get_authorization
        from src.presentation.routers.api.middleware.auth_dependencies import (
            get_current_user,
        )

        regular_user = CurrentUser(
            user_id=uuid7(),
            email="user@example.com",
            roles=["user"],
        )

        app.dependency_overrides[get_current_user] = lambda: regular_user
        app.dependency_overrides[get_authorization] = lambda: StubAuthorizationDenied()

        try:
            client = TestClient(app)
            response = client.get("/api/v1/admin/security/config")

            assert response.status_code == status.HTTP_403_FORBIDDEN
        finally:
            app.dependency_overrides.clear()
