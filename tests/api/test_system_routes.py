"""API tests for non-versioned system routes.

Validates behavior of root, health, and config endpoints exposed by the
system router, including /health/jobs endpoint for background jobs monitoring.
"""

import pytest
from fastapi.testclient import TestClient

from src.core.config import settings
from src.core.container import get_jobs_monitor
from src.core.enums import ErrorCode
from src.core.result import Failure, Success
from src.infrastructure.enums import InfrastructureErrorCode
from src.infrastructure.errors import InfrastructureError
from src.infrastructure.jobs.monitor import JobsHealthStatus
from src.main import app


client = TestClient(app)


def test_root_endpoint_returns_status_and_version() -> None:
    """Root endpoint should return operational status and app version."""
    response = client.get("/")

    assert response.status_code == 200
    data = response.json()

    assert data["message"] == "Dashtam API"
    assert data["status"] == "operational"
    assert data["version"] == settings.app_version


def test_health_endpoint_returns_healthy_status() -> None:
    """Health endpoint should return a healthy status indicator."""
    response = client.get("/health")

    assert response.status_code == 200
    data = response.json()

    assert data == {"status": "healthy"}


def test_config_endpoint_behavior_depends_on_environment() -> None:
    """Config endpoint should be dev-only and return 403 otherwise."""
    response = client.get("/config")

    if settings.is_development:
        assert response.status_code == 200
        data = response.json()

        assert data["environment"] == settings.environment.value
        assert data["api"]["name"] == settings.app_name
        assert data["api"]["version"] == settings.app_version
    else:
        assert response.status_code == 403
        assert (
            response.json()["detail"] == "Config endpoint only available in development"
        )


# =============================================================================
# /health/jobs endpoint tests
# =============================================================================


class StubJobsMonitor:
    """Stub JobsMonitor for testing."""

    def __init__(self, healthy: bool = True, queue_length: int = 5):
        self._healthy = healthy
        self._queue_length = queue_length

    async def check_health(self) -> Success[JobsHealthStatus]:
        return Success(
            value=JobsHealthStatus(
                healthy=self._healthy,
                queue_length=self._queue_length,
                redis_connected=self._healthy,
                error=None if self._healthy else "Connection failed",
            )
        )


class FailingJobsMonitor:
    """Stub JobsMonitor that returns Failure."""

    async def check_health(self):
        return Failure(
            error=InfrastructureError(
                code=ErrorCode.VALIDATION_FAILED,
                infrastructure_code=InfrastructureErrorCode.UNEXPECTED_ERROR,
                message="Unexpected error",
            )
        )


@pytest.fixture
def healthy_jobs_client():
    """Create client with healthy jobs mock."""
    app.dependency_overrides[get_jobs_monitor] = lambda: StubJobsMonitor(healthy=True)
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def unhealthy_jobs_client():
    """Create client with unhealthy jobs mock."""
    app.dependency_overrides[get_jobs_monitor] = lambda: StubJobsMonitor(healthy=False)
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def failing_jobs_client():
    """Create client with failing jobs monitor."""
    app.dependency_overrides[get_jobs_monitor] = lambda: FailingJobsMonitor()
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_health_jobs_returns_healthy_when_jobs_service_healthy(
    healthy_jobs_client,
) -> None:
    """Health jobs endpoint should return healthy status when jobs service is healthy."""
    response = healthy_jobs_client.get("/health/jobs")

    assert response.status_code == 200
    data = response.json()
    assert data == {"status": "healthy"}


def test_health_jobs_returns_unhealthy_when_jobs_service_unhealthy(
    unhealthy_jobs_client,
) -> None:
    """Health jobs endpoint should return unhealthy when jobs service is down."""
    response = unhealthy_jobs_client.get("/health/jobs")

    assert response.status_code == 200
    data = response.json()
    assert data == {"status": "unhealthy"}


def test_health_jobs_returns_unhealthy_on_monitor_failure(failing_jobs_client) -> None:
    """Health jobs endpoint should return unhealthy when monitor fails."""
    response = failing_jobs_client.get("/health/jobs")

    assert response.status_code == 200
    data = response.json()
    assert data == {"status": "unhealthy"}
