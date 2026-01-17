"""API tests for password reset endpoints.

Tests the complete HTTP request/response cycle for password reset:
- POST /api/v1/password-reset-tokens (request reset)
- POST /api/v1/password-resets (execute reset)

Architecture:
- Uses real app with dependency overrides
- Mocks handlers to test request/response flow
- Tests validation, error responses, and success paths
- Verifies RFC 9457 compliance for errors

Note:
    These tests focus on request validation and error response formats.
    Full stack testing (with real handlers and database) is covered in
    integration tests.
"""

import pytest
from fastapi.testclient import TestClient

from src.application.commands.handlers.confirm_password_reset_handler import (
    ConfirmPasswordResetHandler,
)
from src.application.commands.handlers.request_password_reset_handler import (
    RequestPasswordResetHandler,
)
from src.core.container.handler_factory import handler_factory
from src.core.result import Failure, Success
from src.main import app


# =============================================================================
# Test Doubles - Stub handlers
# =============================================================================


class StubRequestPasswordResetHandler:
    """Stub handler for password reset requests."""

    async def handle(self, cmd, request=None):
        """Always return success (security: no user enumeration)."""
        return Success(value=None)


class StubConfirmPasswordResetHandler:
    """Stub handler for password reset confirmation."""

    def __init__(self, behavior: str = "success"):
        """Initialize stub with specific behavior.

        Args:
            behavior: One of 'success', 'token_not_found', 'token_expired',
                     'token_already_used', 'user_not_found'.
        """
        self.behavior = behavior

    async def handle(self, cmd, request=None):
        """Simulate different password reset scenarios."""
        if self.behavior == "success":
            return Success(value=None)
        elif self.behavior == "token_not_found":
            return Failure(error="token_not_found")
        elif self.behavior == "token_expired":
            return Failure(error="token_expired")
        elif self.behavior == "token_already_used":
            return Failure(error="token_already_used")
        elif self.behavior == "user_not_found":
            return Failure(error="user_not_found")
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
# Tests: POST /api/v1/password-reset-tokens (Request Reset)
# =============================================================================


@pytest.mark.api
class TestCreatePasswordResetToken:
    """Tests for POST /api/v1/password-reset-tokens endpoint."""

    def test_create_password_reset_token_success(self, client):
        """Should always return 201 Created to prevent user enumeration."""
        # Setup: Stub handler always returns success
        stub_handler = StubRequestPasswordResetHandler()
        factory_key = handler_factory(RequestPasswordResetHandler)
        app.dependency_overrides[factory_key] = lambda: stub_handler

        # Execute
        response = client.post(
            "/api/v1/password-reset-tokens",
            json={"email": "user@example.com"},
        )

        # Verify: Always 201 for security
        assert response.status_code == 201
        data = response.json()
        assert "message" in data
        assert "email" in data["message"].lower() or "sent" in data["message"].lower()

    def test_create_password_reset_token_nonexistent_email(self, client):
        """Should still return 201 Created even for non-existent email."""
        # Setup: Stub handler always returns success (no user enumeration)
        stub_handler = StubRequestPasswordResetHandler()
        factory_key = handler_factory(RequestPasswordResetHandler)
        app.dependency_overrides[factory_key] = lambda: stub_handler

        # Execute: Non-existent email
        response = client.post(
            "/api/v1/password-reset-tokens",
            json={"email": "nonexistent@example.com"},
        )

        # Verify: Still returns 201 (security)
        assert response.status_code == 201

    def test_create_password_reset_token_invalid_email_format(self, client):
        """Should return 422 Unprocessable Entity for invalid email format."""
        # Execute: Invalid email format
        response = client.post(
            "/api/v1/password-reset-tokens",
            json={"email": "not-an-email"},
        )

        # Verify: RFC 9457 validation error response
        assert response.status_code == 422
        data = response.json()
        assert data["type"].endswith("/errors/validation-failed")
        assert "errors" in data
        assert any("email" in err.get("field", "").lower() for err in data["errors"])

    def test_create_password_reset_token_missing_email(self, client):
        """Should return 422 Unprocessable Entity when email missing."""
        # Execute: Missing email field
        response = client.post("/api/v1/password-reset-tokens", json={})

        # Verify: RFC 9457 validation error response
        assert response.status_code == 422
        data = response.json()
        assert data["type"].endswith("/errors/validation-failed")
        assert "errors" in data
        assert any("email" in err.get("field", "").lower() for err in data["errors"])


# =============================================================================
# Tests: POST /api/v1/password-resets (Execute Reset)
# =============================================================================


@pytest.mark.api
class TestCreatePasswordReset:
    """Tests for POST /api/v1/password-resets endpoint."""

    def test_create_password_reset_success(self, client):
        """Should return 201 Created on successful password reset."""
        # Setup: Stub handler returns success
        stub_handler = StubConfirmPasswordResetHandler(behavior="success")
        factory_key = handler_factory(ConfirmPasswordResetHandler)
        app.dependency_overrides[factory_key] = lambda: stub_handler

        # Execute
        response = client.post(
            "/api/v1/password-resets",
            json={
                "token": "a" * 64,  # 64-char hex token
                "new_password": "NewSecurePass123!",
            },
        )

        # Verify
        assert response.status_code == 201
        data = response.json()
        assert "message" in data
        assert (
            "password" in data["message"].lower() or "reset" in data["message"].lower()
        )

    def test_create_password_reset_token_not_found(self, client):
        """Should return 404 Not Found for invalid token."""
        # Setup: Stub handler returns token_not_found
        stub_handler = StubConfirmPasswordResetHandler(behavior="token_not_found")
        factory_key = handler_factory(ConfirmPasswordResetHandler)
        app.dependency_overrides[factory_key] = lambda: stub_handler

        # Execute
        response = client.post(
            "/api/v1/password-resets",
            json={
                "token": "b" * 64,  # Valid length but invalid token
                "new_password": "NewSecurePass123!",
            },
        )

        # Verify: RFC 9457 error response
        assert response.status_code == 404
        data = response.json()
        assert data["type"].endswith("/errors/not_found")
        assert data["title"] == "Resource Not Found"
        assert data["status"] == 404
        assert data["instance"] == "/api/v1/password-resets"

    def test_create_password_reset_token_expired(self, client):
        """Should return 400 Bad Request for expired token."""
        # Setup: Stub handler returns token_expired
        stub_handler = StubConfirmPasswordResetHandler(behavior="token_expired")
        factory_key = handler_factory(ConfirmPasswordResetHandler)
        app.dependency_overrides[factory_key] = lambda: stub_handler

        # Execute
        response = client.post(
            "/api/v1/password-resets",
            json={
                "token": "c" * 64,  # Valid length but expired
                "new_password": "NewSecurePass123!",
            },
        )

        # Verify: RFC 9457 error response
        assert response.status_code == 400
        data = response.json()
        assert data["type"].endswith("/errors/command_validation_failed")
        assert data["title"] == "Validation Failed"
        assert data["status"] == 400
        assert "expired" in data["detail"].lower()

    def test_create_password_reset_token_already_used(self, client):
        """Should return 400 Bad Request for already-used token."""
        # Setup: Stub handler returns token_already_used
        stub_handler = StubConfirmPasswordResetHandler(behavior="token_already_used")
        factory_key = handler_factory(ConfirmPasswordResetHandler)
        app.dependency_overrides[factory_key] = lambda: stub_handler

        # Execute
        response = client.post(
            "/api/v1/password-resets",
            json={
                "token": "d" * 64,  # Valid length but already used
                "new_password": "NewSecurePass123!",
            },
        )

        # Verify: RFC 9457 error response
        assert response.status_code == 400
        data = response.json()
        assert data["type"].endswith("/errors/command_validation_failed")
        assert data["title"] == "Validation Failed"
        assert data["status"] == 400
        assert "already" in data["detail"].lower()

    def test_create_password_reset_user_not_found(self, client):
        """Should return 404 Not Found when user associated with token not found."""
        # Setup: Stub handler returns user_not_found
        stub_handler = StubConfirmPasswordResetHandler(behavior="user_not_found")
        factory_key = handler_factory(ConfirmPasswordResetHandler)
        app.dependency_overrides[factory_key] = lambda: stub_handler

        # Execute
        response = client.post(
            "/api/v1/password-resets",
            json={
                "token": "e" * 64,  # Valid length but orphaned
                "new_password": "NewSecurePass123!",
            },
        )

        # Verify: RFC 9457 error response
        assert response.status_code == 404
        data = response.json()
        assert data["type"].endswith("/errors/not_found")
        assert data["title"] == "Resource Not Found"
        assert data["status"] == 404

    def test_create_password_reset_missing_token(self, client):
        """Should return 422 Unprocessable Entity when token missing."""
        # Execute: Missing token field
        response = client.post(
            "/api/v1/password-resets",
            json={"new_password": "NewSecurePass123!"},
        )

        # Verify: RFC 9457 validation error response
        assert response.status_code == 422
        data = response.json()
        assert data["type"].endswith("/errors/validation-failed")
        assert "errors" in data
        assert any("token" in err.get("field", "").lower() for err in data["errors"])

    def test_create_password_reset_missing_password(self, client):
        """Should return 422 Unprocessable Entity when new_password missing."""
        # Execute: Missing new_password field
        response = client.post(
            "/api/v1/password-resets",
            json={"token": "a" * 64},
        )

        # Verify: RFC 9457 validation error response
        assert response.status_code == 422
        data = response.json()
        assert data["type"].endswith("/errors/validation-failed")
        assert "errors" in data
        assert any("password" in err.get("field", "").lower() for err in data["errors"])

    def test_create_password_reset_token_too_short(self, client):
        """Should return 422 Unprocessable Entity for token < 64 chars."""
        # Execute: Token too short
        response = client.post(
            "/api/v1/password-resets",
            json={
                "token": "short",  # Less than 64 chars
                "new_password": "NewSecurePass123!",
            },
        )

        # Verify: RFC 9457 validation error response
        assert response.status_code == 422
        data = response.json()
        assert data["type"].endswith("/errors/validation-failed")
        assert "errors" in data
        assert any("token" in err.get("field", "").lower() for err in data["errors"])

    def test_create_password_reset_token_too_long(self, client):
        """Should return 422 Unprocessable Entity for token > 64 chars."""
        # Execute: Token too long
        response = client.post(
            "/api/v1/password-resets",
            json={
                "token": "a" * 65,  # More than 64 chars
                "new_password": "NewSecurePass123!",
            },
        )

        # Verify: RFC 9457 validation error response
        assert response.status_code == 422
        data = response.json()
        assert data["type"].endswith("/errors/validation-failed")
        assert "errors" in data
        assert any("token" in err.get("field", "").lower() for err in data["errors"])

    def test_create_password_reset_password_too_short(self, client):
        """Should return 422 Unprocessable Entity for password < 8 chars."""
        # Execute: Password too short
        response = client.post(
            "/api/v1/password-resets",
            json={
                "token": "a" * 64,
                "new_password": "short",  # Less than 8 chars
            },
        )

        # Verify: RFC 9457 validation error response
        assert response.status_code == 422
        data = response.json()
        assert data["type"].endswith("/errors/validation-failed")
        assert "errors" in data
        assert any("password" in err.get("field", "").lower() for err in data["errors"])
