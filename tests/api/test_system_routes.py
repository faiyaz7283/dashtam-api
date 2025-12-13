"""API tests for non-versioned system routes.

Validates behavior of root, health, and config endpoints exposed by the
system router.
"""

from fastapi.testclient import TestClient

from src.core.config import settings
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
