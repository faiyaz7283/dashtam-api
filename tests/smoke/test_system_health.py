"""Smoke Tests: System Health & Infrastructure

These tests validate that core system infrastructure is operational:
- Health check endpoint
- API documentation availability
- Basic system responsiveness

These are quick, independent tests that don't require authentication
or complex setup. They verify the system is "alive" and ready to serve requests.
"""

import pytest


@pytest.mark.smoke
def test_smoke_health_check(client):
    """Smoke: System health check endpoint is operational.

    Validates:
    - Health check endpoint responds
    - Returns correct status
    - Application is running

    This is typically the first test run in smoke test suite to verify
    basic system availability before running more complex auth flow tests.
    """
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"


@pytest.mark.smoke
def test_smoke_api_docs_accessible(client):
    """Smoke: API documentation is accessible.

    Validates:
    - OpenAPI documentation endpoint works
    - Swagger UI is available
    - Critical for developer experience

    If this fails, it indicates the FastAPI app may not be configured
    correctly or the docs endpoint has been disabled.
    """
    response = client.get("/docs")
    assert response.status_code == 200
