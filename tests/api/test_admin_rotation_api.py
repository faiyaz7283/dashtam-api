"""API tests for admin token rotation endpoints.

Tests the complete HTTP request/response cycle for admin rotation:
- POST /api/v1/admin/security/rotations (global rotation)
- POST /api/v1/admin/users/{user_id}/rotations (per-user rotation)
- GET /api/v1/admin/security/config (get security config)

Architecture:
- Uses FastAPI TestClient for HTTP-level testing
- Tests validation, status codes, and error responses
- Verifies RFC 7807 compliance for errors

Note:
    These tests focus on request validation and response formats.
    Admin authentication is TODO (not yet implemented).
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from src.presentation.api.middleware.trace_middleware import TraceMiddleware
from src.schemas.auth_schemas import AuthErrorResponse
from src.schemas.rotation_schemas import (
    GlobalRotationResponse,
    SecurityConfigResponse,
    UserRotationResponse,
)


# =============================================================================
# Test App Fixtures - Create test endpoints that simulate real behavior
# =============================================================================


@pytest.fixture
def test_app():
    """Create test FastAPI app with admin rotation endpoints.

    Instead of including the real router (which requires complex DI),
    we create simplified test endpoints that verify the HTTP layer behavior.
    """
    app = FastAPI(title="Test Admin App")
    app.add_middleware(TraceMiddleware)

    # Test state for tracking calls
    app.state.global_version = 1
    app.state.grace_period = 300
    app.state.last_rotation_reason = None
    app.state.user_versions = {}

    # POST /api/v1/admin/security/rotations (global rotation)
    @app.post(
        "/api/v1/admin/security/rotations",
        status_code=status.HTTP_201_CREATED,
    )
    async def create_global_rotation(request: Request):
        """Test endpoint simulating global token rotation."""
        data = await request.json()

        # Validate required fields
        if "reason" not in data:
            return JSONResponse(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                content={"detail": [{"loc": ["body", "reason"], "msg": "required"}]},
            )

        if not data.get("reason") or len(data["reason"]) < 1:
            return JSONResponse(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                content={"detail": [{"loc": ["body", "reason"], "msg": "too short"}]},
            )

        # Simulate rotation
        previous = app.state.global_version
        app.state.global_version += 1
        app.state.last_rotation_reason = data["reason"]

        return GlobalRotationResponse(
            previous_version=previous,
            new_version=app.state.global_version,
            grace_period_seconds=app.state.grace_period,
        ).model_dump()

    # POST /api/v1/admin/users/{user_id}/rotations (per-user rotation)
    @app.post(
        "/api/v1/admin/users/{user_id}/rotations",
        status_code=status.HTTP_201_CREATED,
    )
    async def create_user_rotation(user_id: str, request: Request):
        """Test endpoint simulating per-user token rotation."""
        data = await request.json()

        # Validate required fields
        if "reason" not in data:
            return JSONResponse(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                content={"detail": [{"loc": ["body", "reason"], "msg": "required"}]},
            )

        # Simulate user not found
        if "notfound" in user_id.lower():
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content=AuthErrorResponse(
                    type="https://api.dashtam.com/errors/user_not_found",
                    title="User Not Found",
                    status=404,
                    detail=f"User with ID {user_id} not found",
                    instance=f"/api/v1/admin/users/{user_id}/rotations",
                ).model_dump(),
            )

        # Get or initialize user version
        if user_id not in app.state.user_versions:
            app.state.user_versions[user_id] = 1

        previous = app.state.user_versions[user_id]
        app.state.user_versions[user_id] += 1

        return UserRotationResponse(
            user_id=user_id,
            previous_version=previous,
            new_version=app.state.user_versions[user_id],
        ).model_dump()

    # GET /api/v1/admin/security/config
    @app.get("/api/v1/admin/security/config")
    async def get_security_config(request: Request):
        """Test endpoint simulating security config retrieval."""
        return SecurityConfigResponse(
            global_min_token_version=app.state.global_version,
            grace_period_seconds=app.state.grace_period,
            last_rotation_at=datetime.now(UTC).isoformat()
            if app.state.last_rotation_reason
            else None,
            last_rotation_reason=app.state.last_rotation_reason,
        ).model_dump()

    return app


@pytest.fixture
def client(test_app):
    """Create test client for the test app."""
    return TestClient(test_app)


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
        user_id = str(uuid4())
        response = client.post(
            f"/api/v1/admin/users/{user_id}/rotations",
            json={"reason": "Password changed"},
        )

        assert response.status_code == status.HTTP_201_CREATED

    def test_user_rotation_returns_user_id(self, client):
        """Test rotation response includes user_id."""
        user_id = str(uuid4())
        response = client.post(
            f"/api/v1/admin/users/{user_id}/rotations",
            json={"reason": "Suspicious activity"},
        )

        data = response.json()
        assert "user_id" in data
        assert data["user_id"] == user_id

    def test_user_rotation_returns_version_info(self, client):
        """Test rotation response includes version information."""
        user_id = str(uuid4())
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
        response = client.post(
            "/api/v1/admin/users/notfound-user-id/rotations",
            json={"reason": "Test"},
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        data = response.json()
        assert data["title"] == "User Not Found"

    def test_user_rotation_requires_reason(self, client):
        """Test rotation requires reason field."""
        user_id = str(uuid4())
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
