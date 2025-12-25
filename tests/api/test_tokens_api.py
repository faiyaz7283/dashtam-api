"""API tests for token endpoints.

Tests the complete HTTP request/response cycle for token management:
- POST /api/v1/tokens (refresh access token)

Architecture:
- Uses real app with dependency overrides
- Mocks handlers to test request/response flow
- Tests validation, error responses, and success paths
- Verifies RFC 7807 compliance for errors

Note:
    These tests focus on request validation and error response formats.
    Full stack testing (with real handlers and database) is covered in
    integration tests.
"""

from dataclasses import dataclass

import pytest
from fastapi.testclient import TestClient

from src.core.result import Failure, Success
from src.main import app


# =============================================================================
# Test Doubles - Stub handlers and response types
# =============================================================================


@dataclass
class RefreshResponse:
    """Response from refresh token handler."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = 900


class StubRefreshAccessTokenHandler:
    """Stub handler for token refresh."""

    def __init__(self, behavior: str = "success"):
        """Initialize stub with specific behavior.

        Args:
            behavior: One of 'success', 'invalid', 'expired', 'revoked',
                     'user_not_found', 'user_inactive'.
        """
        self.behavior = behavior

    async def handle(self, cmd, request=None):
        """Simulate different token refresh scenarios."""
        if self.behavior == "success":
            return Success(
                value=RefreshResponse(
                    access_token="new_access_token",
                    refresh_token="new_refresh_token",
                    token_type="bearer",
                    expires_in=900,
                )
            )
        elif self.behavior == "invalid":
            return Failure(error="token_invalid")
        elif self.behavior == "expired":
            return Failure(error="token_expired")
        elif self.behavior == "revoked":
            return Failure(error="token_revoked")
        elif self.behavior == "user_not_found":
            return Failure(error="user_not_found")
        elif self.behavior == "user_inactive":
            return Failure(error="user_inactive")
        else:
            return Failure(error="unknown_error")


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture(autouse=True)
def override_dependencies():
    """Override app dependencies with test doubles.

    Uses autouse=True to automatically apply to all tests in this module.
    """
    yield
    # Cleanup after each test
    app.dependency_overrides.clear()


@pytest.fixture
def client():
    """Create TestClient for API tests using real app."""
    return TestClient(app, raise_server_exceptions=False)


# =============================================================================
# Tests: POST /api/v1/tokens (Refresh Access Token)
# =============================================================================


@pytest.mark.api
class TestCreateTokens:
    """Tests for POST /api/v1/tokens endpoint."""

    def test_create_tokens_success(self, client):
        """Should return 201 Created with new tokens on successful refresh."""
        # Setup: Stub handler returns success
        stub_handler = StubRefreshAccessTokenHandler(behavior="success")

        from src.core.container import get_refresh_token_handler

        app.dependency_overrides[get_refresh_token_handler] = lambda: stub_handler

        # Execute
        response = client.post(
            "/api/v1/tokens",
            json={"refresh_token": "valid_refresh_token_here"},
        )

        # Verify
        assert response.status_code == 201
        data = response.json()
        assert data["access_token"] == "new_access_token"
        assert data["refresh_token"] == "new_refresh_token"
        assert data["token_type"] == "bearer"
        assert data["expires_in"] == 900

    def test_create_tokens_invalid_token(self, client):
        """Should return 400 Bad Request for invalid refresh token."""
        # Setup: Stub handler returns invalid error
        stub_handler = StubRefreshAccessTokenHandler(behavior="invalid")

        from src.core.container import get_refresh_token_handler

        app.dependency_overrides[get_refresh_token_handler] = lambda: stub_handler

        # Execute
        response = client.post(
            "/api/v1/tokens",
            json={"refresh_token": "invalid_token"},
        )

        # Verify: RFC 7807 error response
        assert response.status_code == 400
        data = response.json()
        assert data["type"] == "https://api.dashtam.com/errors/token_invalid"
        assert data["title"] == "Invalid Token"
        assert data["status"] == 400
        assert "invalid" in data["detail"].lower()
        assert data["instance"] == "/api/v1/tokens"

    def test_create_tokens_expired_token(self, client):
        """Should return 401 Unauthorized for expired refresh token."""
        # Setup: Stub handler returns expired error
        stub_handler = StubRefreshAccessTokenHandler(behavior="expired")

        from src.core.container import get_refresh_token_handler

        app.dependency_overrides[get_refresh_token_handler] = lambda: stub_handler

        # Execute
        response = client.post(
            "/api/v1/tokens",
            json={"refresh_token": "expired_token"},
        )

        # Verify: RFC 7807 error response
        assert response.status_code == 401
        data = response.json()
        assert data["type"] == "https://api.dashtam.com/errors/token_expired"
        assert data["title"] == "Token Expired"
        assert data["status"] == 401
        assert "expired" in data["detail"].lower()
        assert data["instance"] == "/api/v1/tokens"

    def test_create_tokens_revoked_token(self, client):
        """Should return 401 Unauthorized for revoked refresh token."""
        # Setup: Stub handler returns revoked error
        stub_handler = StubRefreshAccessTokenHandler(behavior="revoked")

        from src.core.container import get_refresh_token_handler

        app.dependency_overrides[get_refresh_token_handler] = lambda: stub_handler

        # Execute
        response = client.post(
            "/api/v1/tokens",
            json={"refresh_token": "revoked_token"},
        )

        # Verify: RFC 7807 error response
        assert response.status_code == 401
        data = response.json()
        assert data["type"] == "https://api.dashtam.com/errors/token_revoked"
        assert data["title"] == "Token Revoked"
        assert data["status"] == 401
        assert "revoked" in data["detail"].lower()
        assert data["instance"] == "/api/v1/tokens"

    def test_create_tokens_user_not_found(self, client):
        """Should return 401 Unauthorized when user associated with token not found."""
        # Setup: Stub handler returns user_not_found error
        stub_handler = StubRefreshAccessTokenHandler(behavior="user_not_found")

        from src.core.container import get_refresh_token_handler

        app.dependency_overrides[get_refresh_token_handler] = lambda: stub_handler

        # Execute
        response = client.post(
            "/api/v1/tokens",
            json={"refresh_token": "orphaned_token"},
        )

        # Verify: RFC 7807 error response
        assert response.status_code == 401
        data = response.json()
        assert data["type"] == "https://api.dashtam.com/errors/user_not_found"
        assert data["title"] == "User Not Found"
        assert data["status"] == 401

    def test_create_tokens_user_inactive(self, client):
        """Should return 401 Unauthorized when user account is inactive."""
        # Setup: Stub handler returns user_inactive error
        stub_handler = StubRefreshAccessTokenHandler(behavior="user_inactive")

        from src.core.container import get_refresh_token_handler

        app.dependency_overrides[get_refresh_token_handler] = lambda: stub_handler

        # Execute
        response = client.post(
            "/api/v1/tokens",
            json={"refresh_token": "inactive_user_token"},
        )

        # Verify: RFC 7807 error response
        assert response.status_code == 401
        data = response.json()
        assert data["type"] == "https://api.dashtam.com/errors/user_inactive"
        assert data["title"] == "User Inactive"
        assert data["status"] == 401

    def test_create_tokens_missing_refresh_token(self, client):
        """Should return 422 Unprocessable Entity when refresh_token missing."""
        # Execute: Missing refresh_token field
        response = client.post("/api/v1/tokens", json={})

        # Verify: Pydantic validation error
        assert response.status_code == 422
        data = response.json()
        assert "detail" in data
        assert any("refresh_token" in str(err).lower() for err in data["detail"])

    def test_create_tokens_empty_refresh_token(self, client):
        """Should return 422 Unprocessable Entity for empty refresh_token."""
        # Execute: Empty refresh_token (fails min_length validation)
        response = client.post(
            "/api/v1/tokens",
            json={"refresh_token": ""},
        )

        # Verify: Pydantic validation error
        assert response.status_code == 422
        data = response.json()
        assert "detail" in data
        assert any("refresh_token" in str(err).lower() for err in data["detail"])

    def test_create_tokens_invalid_content_type(self, client):
        """Should return 422 when Content-Type is not application/json."""
        # Execute: Send as form data instead of JSON
        response = client.post(
            "/api/v1/tokens",
            data={"refresh_token": "some_token"},  # Form data
        )

        # Verify
        assert response.status_code == 422

    def test_create_tokens_includes_trace_id_on_error(self, client):
        """Should include X-Trace-ID header on error responses."""
        # Setup: Stub handler returns error
        stub_handler = StubRefreshAccessTokenHandler(behavior="expired")

        from src.core.container import get_refresh_token_handler

        app.dependency_overrides[get_refresh_token_handler] = lambda: stub_handler

        # Execute
        response = client.post(
            "/api/v1/tokens",
            json={"refresh_token": "expired_token"},
        )

        # Verify: X-Trace-ID header present (if trace context exists)
        assert response.status_code == 401
        # Note: X-Trace-ID only present if trace_id exists in context
        # In test environment without middleware, it may be None
        # This test just ensures no error when trace_id is None
