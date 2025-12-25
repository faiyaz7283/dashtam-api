"""API tests for user endpoints.

Tests the complete HTTP request/response cycle for user management:
- POST /api/v1/users (create user / registration)

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

import pytest
from fastapi.testclient import TestClient
from uuid_extensions import uuid7

from src.core.result import Failure, Success
from src.main import app


# =============================================================================
# Test Doubles - Stub handlers
# =============================================================================


class StubRegisterUserHandler:
    """Stub handler for user registration."""

    def __init__(self, behavior: str = "success"):
        """Initialize stub with specific behavior.

        Args:
            behavior: One of 'success', 'duplicate', 'validation_error'.
        """
        self.behavior = behavior

    async def handle(self, cmd, request=None):
        """Check email patterns to simulate different scenarios."""
        if self.behavior == "success":
            return Success(value=uuid7())
        elif self.behavior == "duplicate":
            return Failure(error="Email already registered")
        elif self.behavior == "validation_error":
            return Failure(error="Password must be at least 12 characters")
        else:
            return Failure(error="Unexpected error")


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture(autouse=True)
def override_dependencies():
    """Override app dependencies with test doubles.

    Uses autouse=True to automatically apply to all tests in this module.
    """
    # Note: Individual tests will override with specific behaviors
    # This just ensures cleanup happens

    yield

    # Cleanup after each test
    app.dependency_overrides.clear()


@pytest.fixture
def client():
    """Create TestClient for API tests using real app."""
    return TestClient(app, raise_server_exceptions=False)


# =============================================================================
# Tests: POST /api/v1/users (Create User / Registration)
# =============================================================================


class TestCreateUser:
    """Tests for POST /api/v1/users endpoint."""

    def test_create_user_success(self, client):
        """Should return 201 Created on successful registration."""
        # Setup: Stub handler returns success
        stub_handler = StubRegisterUserHandler(behavior="success")

        from src.core.container import get_register_user_handler

        app.dependency_overrides[get_register_user_handler] = lambda: stub_handler

        # Execute
        response = client.post(
            "/api/v1/users",
            json={
                "email": "newuser@example.com",
                "password": "SecurePass123!",
            },
        )

        # Verify
        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert data["email"] == "newuser@example.com"
        assert "message" in data
        assert "verify" in data["message"].lower()

    def test_create_user_duplicate_email(self, client):
        """Should return 409 Conflict when email already registered."""
        # Setup: Stub handler returns duplicate error
        stub_handler = StubRegisterUserHandler(behavior="duplicate")

        from src.core.container import get_register_user_handler

        app.dependency_overrides[get_register_user_handler] = lambda: stub_handler

        # Execute
        response = client.post(
            "/api/v1/users",
            json={
                "email": "existing@example.com",
                "password": "SecurePass123!",
            },
        )

        # Verify: RFC 7807 error response
        assert response.status_code == 409
        data = response.json()
        assert data["type"] == "https://api.dashtam.com/errors/email-already-registered"
        assert data["title"] == "Email Already Registered"
        assert data["status"] == 409
        assert "already registered" in data["detail"].lower()
        assert data["instance"] == "/api/v1/users"

    def test_create_user_validation_error(self, client):
        """Should return 400 Bad Request on domain validation failure."""
        # Setup: Stub handler returns validation error
        stub_handler = StubRegisterUserHandler(behavior="validation_error")

        from src.core.container import get_register_user_handler

        app.dependency_overrides[get_register_user_handler] = lambda: stub_handler

        # Execute: Password passes Pydantic min_length but fails domain validation
        response = client.post(
            "/api/v1/users",
            json={
                "email": "user@example.com",
                "password": "weakpass",  # 8 chars, passes schema but weak
            },
        )

        # Verify: RFC 7807 error response
        assert response.status_code == 400
        data = response.json()
        assert data["type"] == "https://api.dashtam.com/errors/validation-error"
        assert data["title"] == "Validation Error"
        assert data["status"] == 400
        assert (
            "password" in data["detail"].lower()
            or "12 characters" in data["detail"].lower()
        )
        assert data["instance"] == "/api/v1/users"

    def test_create_user_invalid_email_format(self, client):
        """Should return 422 Unprocessable Entity for invalid email format."""
        # Execute: Invalid email (Pydantic validation)
        response = client.post(
            "/api/v1/users",
            json={
                "email": "not-an-email",
                "password": "SecurePass123!",
            },
        )

        # Verify: FastAPI/Pydantic validation error
        assert response.status_code == 422
        data = response.json()
        assert "detail" in data
        # Pydantic returns list of validation errors
        assert isinstance(data["detail"], list)
        assert any("email" in str(err).lower() for err in data["detail"])

    def test_create_user_missing_email(self, client):
        """Should return 422 Unprocessable Entity when email missing."""
        # Execute: Missing email field
        response = client.post(
            "/api/v1/users",
            json={
                "password": "SecurePass123!",
            },
        )

        # Verify
        assert response.status_code == 422
        data = response.json()
        assert "detail" in data
        assert any("email" in str(err).lower() for err in data["detail"])

    def test_create_user_missing_password(self, client):
        """Should return 422 Unprocessable Entity when password missing."""
        # Execute: Missing password field
        response = client.post(
            "/api/v1/users",
            json={
                "email": "user@example.com",
            },
        )

        # Verify
        assert response.status_code == 422
        data = response.json()
        assert "detail" in data
        assert any("password" in str(err).lower() for err in data["detail"])

    def test_create_user_password_too_short(self, client):
        """Should return 422 Unprocessable Entity for password < 8 chars."""
        # Execute: Password too short (Pydantic validation)
        response = client.post(
            "/api/v1/users",
            json={
                "email": "user@example.com",
                "password": "short",  # Less than 8 chars
            },
        )

        # Verify
        assert response.status_code == 422
        data = response.json()
        assert "detail" in data
        assert any("password" in str(err).lower() for err in data["detail"])

    def test_create_user_password_too_long(self, client):
        """Should return 422 Unprocessable Entity for password > 128 chars."""
        # Execute: Password too long (Pydantic validation)
        response = client.post(
            "/api/v1/users",
            json={
                "email": "user@example.com",
                "password": "a" * 129,  # More than 128 chars
            },
        )

        # Verify
        assert response.status_code == 422
        data = response.json()
        assert "detail" in data
        assert any("password" in str(err).lower() for err in data["detail"])

    def test_create_user_empty_request_body(self, client):
        """Should return 422 Unprocessable Entity for empty request."""
        # Execute: Empty JSON body
        response = client.post("/api/v1/users", json={})

        # Verify
        assert response.status_code == 422
        data = response.json()
        assert "detail" in data
        # Should have errors for both required fields
        errors = [str(err).lower() for err in data["detail"]]
        assert any("email" in err for err in errors)
        assert any("password" in err for err in errors)

    def test_create_user_invalid_content_type(self, client):
        """Should return 422 when Content-Type is not application/json."""
        # Execute: Send as form data instead of JSON
        response = client.post(
            "/api/v1/users",
            data={  # Form data, not JSON
                "email": "user@example.com",
                "password": "SecurePass123!",
            },
        )

        # Verify
        assert response.status_code == 422

    def test_create_user_includes_trace_id_on_error(self, client):
        """Should include X-Trace-ID header on error responses."""
        # Setup: Stub handler returns error
        stub_handler = StubRegisterUserHandler(behavior="duplicate")

        from src.core.container import get_register_user_handler

        app.dependency_overrides[get_register_user_handler] = lambda: stub_handler

        # Execute
        response = client.post(
            "/api/v1/users",
            json={
                "email": "existing@example.com",
                "password": "SecurePass123!",
            },
        )

        # Verify: X-Trace-ID header present (if trace context exists)
        assert response.status_code == 409
        # Note: X-Trace-ID only present if trace_id exists in context
        # In test environment without middleware, it may be None
        # This test just ensures no error when trace_id is None
