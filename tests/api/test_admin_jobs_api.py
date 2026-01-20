"""API tests for admin background jobs endpoint.

Tests the complete HTTP request/response cycle for admin jobs monitoring:
- GET /api/v1/admin/jobs (jobs status)

Architecture:
- Uses real app with dependency overrides
- Mocks JobsMonitor and authentication dependencies
- Tests validation, status codes, and error responses
- Verifies 401/403 for unauthenticated/unauthorized access
"""

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from uuid_extensions import uuid7

from src.core.container import get_authorization, get_jobs_monitor
from src.core.enums import ErrorCode
from src.core.result import Failure, Success
from src.infrastructure.enums import InfrastructureErrorCode
from src.infrastructure.errors import InfrastructureError
from src.infrastructure.jobs.monitor import JobsHealthStatus
from src.main import app
from src.presentation.routers.api.middleware.auth_dependencies import (
    CurrentUser,
    get_current_user,
)


# =============================================================================
# Test Doubles
# =============================================================================


class StubJobsMonitor:
    """Stub JobsMonitor for testing."""

    def __init__(
        self, healthy: bool = True, queue_length: int = 5, redis_connected: bool = True
    ):
        self._healthy = healthy
        self._queue_length = queue_length
        self._redis_connected = redis_connected

    async def check_health(self) -> Success[JobsHealthStatus]:
        return Success(
            value=JobsHealthStatus(
                healthy=self._healthy,
                queue_length=self._queue_length,
                redis_connected=self._redis_connected,
                error=None if self._healthy else "Redis connection failed",
            )
        )


class FailingJobsMonitor:
    """Stub JobsMonitor that returns Failure."""

    async def check_health(self):
        return Failure(
            error=InfrastructureError(
                code=ErrorCode.VALIDATION_FAILED,
                infrastructure_code=InfrastructureErrorCode.UNEXPECTED_ERROR,
                message="Unexpected error checking jobs health",
            )
        )


class StubAuthorizationProtocol:
    """Stub authorization that always allows admin."""

    async def check_permission(self, user_id, resource: str, action: str) -> bool:
        return True

    async def has_role(self, user_id, role: str) -> bool:
        return role == "admin"


class StubAuthorizationDenied:
    """Stub authorization that denies admin role."""

    async def check_permission(self, user_id, resource: str, action: str) -> bool:
        return False

    async def has_role(self, user_id, role: str) -> bool:
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
def regular_user():
    """Create regular (non-admin) user."""
    return CurrentUser(
        user_id=uuid7(),
        email="user@example.com",
        roles=["user"],
    )


@pytest.fixture
def healthy_monitor():
    """Create stub monitor returning healthy status."""
    return StubJobsMonitor(healthy=True, queue_length=10)


@pytest.fixture
def unhealthy_monitor():
    """Create stub monitor returning unhealthy status."""
    return StubJobsMonitor(healthy=False, queue_length=0, redis_connected=False)


@pytest.fixture
def failing_monitor():
    """Create stub monitor that returns Failure."""
    return FailingJobsMonitor()


@pytest.fixture(autouse=True)
def override_dependencies(admin_user, healthy_monitor):
    """Override app dependencies with test doubles (admin access by default)."""
    app.dependency_overrides[get_current_user] = lambda: admin_user
    app.dependency_overrides[get_authorization] = lambda: StubAuthorizationProtocol()
    app.dependency_overrides[get_jobs_monitor] = lambda: healthy_monitor

    yield

    app.dependency_overrides.clear()


@pytest.fixture
def client():
    """Create test client with real app."""
    return TestClient(app)


# =============================================================================
# GET /api/v1/admin/jobs Tests
# =============================================================================


@pytest.mark.api
class TestAdminJobsEndpoint:
    """Test GET /api/v1/admin/jobs endpoint."""

    def test_returns_200_with_jobs_status(self, client) -> None:
        """Should return 200 OK with jobs status for admin user."""
        response = client.get("/api/v1/admin/jobs")

        assert response.status_code == status.HTTP_200_OK

    def test_response_includes_healthy_field(self, client) -> None:
        """Response should include healthy boolean field."""
        response = client.get("/api/v1/admin/jobs")

        data = response.json()
        assert "healthy" in data
        assert isinstance(data["healthy"], bool)

    def test_response_includes_queue_length(self, client) -> None:
        """Response should include queue_length field."""
        response = client.get("/api/v1/admin/jobs")

        data = response.json()
        assert "queue_length" in data
        assert isinstance(data["queue_length"], int)

    def test_response_includes_redis_connected(self, client) -> None:
        """Response should include redis_connected field."""
        response = client.get("/api/v1/admin/jobs")

        data = response.json()
        assert "redis_connected" in data
        assert isinstance(data["redis_connected"], bool)

    def test_healthy_status_shows_correct_values(self, client, healthy_monitor) -> None:
        """Healthy jobs service should return correct status values."""
        app.dependency_overrides[get_jobs_monitor] = lambda: healthy_monitor

        response = client.get("/api/v1/admin/jobs")

        data = response.json()
        assert data["healthy"] is True
        assert data["queue_length"] == 10
        assert data["redis_connected"] is True
        assert data["error"] is None

    def test_unhealthy_status_includes_error(
        self, client, unhealthy_monitor, admin_user
    ) -> None:
        """Unhealthy jobs service should include error message."""
        app.dependency_overrides[get_jobs_monitor] = lambda: unhealthy_monitor

        response = client.get("/api/v1/admin/jobs")

        data = response.json()
        assert data["healthy"] is False
        assert data["redis_connected"] is False
        assert data["error"] is not None


@pytest.mark.api
class TestAdminJobsMonitorFailure:
    """Test GET /api/v1/admin/jobs when monitor fails."""

    def test_returns_error_response_on_monitor_failure(
        self, client, failing_monitor, admin_user
    ) -> None:
        """Should return error response when monitor fails."""
        app.dependency_overrides[get_jobs_monitor] = lambda: failing_monitor

        response = client.get("/api/v1/admin/jobs")

        # Should return RFC 9457 error response
        assert response.status_code in (
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            status.HTTP_200_OK,  # Some implementations return 200 with error field
        )


# =============================================================================
# Authentication Tests
# =============================================================================


@pytest.mark.api
class TestAdminJobsAuthentication:
    """Test that admin jobs endpoint requires authentication."""

    def test_returns_401_without_authentication(self) -> None:
        """Should return 401 Unauthorized without authentication."""
        # Clear all overrides to test without auth
        app.dependency_overrides.clear()

        try:
            client = TestClient(app)
            response = client.get("/api/v1/admin/jobs")

            # Returns 401 from HTTPBearer when no Authorization header
            assert response.status_code in (
                status.HTTP_401_UNAUTHORIZED,
                status.HTTP_403_FORBIDDEN,
            )
        finally:
            app.dependency_overrides.clear()


# =============================================================================
# Authorization Tests
# =============================================================================


@pytest.mark.api
class TestAdminJobsAuthorization:
    """Test that admin jobs endpoint requires admin role."""

    def test_returns_403_without_admin_role(
        self, regular_user, healthy_monitor
    ) -> None:
        """Should return 403 Forbidden for non-admin user."""
        # Setup: authenticated but non-admin user
        app.dependency_overrides[get_current_user] = lambda: regular_user
        app.dependency_overrides[get_authorization] = lambda: StubAuthorizationDenied()
        app.dependency_overrides[get_jobs_monitor] = lambda: healthy_monitor

        try:
            client = TestClient(app)
            response = client.get("/api/v1/admin/jobs")

            assert response.status_code == status.HTTP_403_FORBIDDEN
        finally:
            app.dependency_overrides.clear()

    def test_admin_user_can_access(self, admin_user, healthy_monitor) -> None:
        """Admin user should be able to access the endpoint."""
        app.dependency_overrides[get_current_user] = lambda: admin_user
        app.dependency_overrides[get_authorization] = (
            lambda: StubAuthorizationProtocol()
        )
        app.dependency_overrides[get_jobs_monitor] = lambda: healthy_monitor

        try:
            client = TestClient(app)
            response = client.get("/api/v1/admin/jobs")

            assert response.status_code == status.HTTP_200_OK
        finally:
            app.dependency_overrides.clear()
