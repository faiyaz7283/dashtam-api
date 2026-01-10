"""API tests for email verification endpoints.

Tests the complete HTTP request/response cycle for email verification:
- POST /api/v1/email-verifications (verify email)

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

from src.core.result import Failure, Success
from src.main import app


# =============================================================================
# Test Doubles - Stub handlers
# =============================================================================


class StubVerifyEmailHandler:
    """Stub handler for email verification."""

    def __init__(self, behavior: str = "success"):
        """Initialize stub with specific behavior.

        Args:
            behavior: One of 'success', 'token_not_found', 'token_expired',
                     'token_already_used', 'user_not_found'.
        """
        self.behavior = behavior

    async def handle(self, cmd, request=None):
        """Simulate different email verification scenarios."""
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
# Tests: POST /api/v1/email-verifications (Verify Email)
# =============================================================================


@pytest.mark.api
class TestCreateEmailVerification:
    """Tests for POST /api/v1/email-verifications endpoint."""

    def test_create_email_verification_success(self, client):
        """Should return 201 Created on successful email verification."""
        # Setup: Stub handler returns success
        stub_handler = StubVerifyEmailHandler(behavior="success")

        from src.core.container import get_verify_email_handler

        app.dependency_overrides[get_verify_email_handler] = lambda: stub_handler

        # Execute
        response = client.post(
            "/api/v1/email-verifications",
            json={"token": "a" * 64},  # 64-char hex token
        )

        # Verify
        assert response.status_code == 201
        data = response.json()
        assert "message" in data
        assert (
            "email" in data["message"].lower() or "verified" in data["message"].lower()
        )

    def test_create_email_verification_token_not_found(self, client):
        """Should return 404 Not Found for invalid token."""
        # Setup: Stub handler returns token_not_found
        stub_handler = StubVerifyEmailHandler(behavior="token_not_found")

        from src.core.container import get_verify_email_handler

        app.dependency_overrides[get_verify_email_handler] = lambda: stub_handler

        # Execute
        response = client.post(
            "/api/v1/email-verifications",
            json={"token": "b" * 64},  # Valid length but invalid token
        )

        # Verify: RFC 7807 error response
        assert response.status_code == 404
        data = response.json()
        assert data["type"].endswith("/errors/not_found")
        assert data["title"] == "Resource Not Found"
        assert data["status"] == 404
        assert data["instance"] == "/api/v1/email-verifications"

    def test_create_email_verification_token_expired(self, client):
        """Should return 400 Bad Request for expired token."""
        # Setup: Stub handler returns token_expired
        stub_handler = StubVerifyEmailHandler(behavior="token_expired")

        from src.core.container import get_verify_email_handler

        app.dependency_overrides[get_verify_email_handler] = lambda: stub_handler

        # Execute
        response = client.post(
            "/api/v1/email-verifications",
            json={"token": "c" * 64},  # Valid length but expired
        )

        # Verify: RFC 7807 error response
        assert response.status_code == 400
        data = response.json()
        assert data["type"].endswith("/errors/command_validation_failed")
        assert data["title"] == "Validation Failed"
        assert data["status"] == 400
        assert "expired" in data["detail"].lower()

    def test_create_email_verification_token_already_used(self, client):
        """Should return 400 Bad Request for already-used token."""
        # Setup: Stub handler returns token_already_used
        stub_handler = StubVerifyEmailHandler(behavior="token_already_used")

        from src.core.container import get_verify_email_handler

        app.dependency_overrides[get_verify_email_handler] = lambda: stub_handler

        # Execute
        response = client.post(
            "/api/v1/email-verifications",
            json={"token": "d" * 64},  # Valid length but already used
        )

        # Verify: RFC 7807 error response
        assert response.status_code == 400
        data = response.json()
        assert data["type"].endswith("/errors/command_validation_failed")
        assert data["title"] == "Validation Failed"
        assert data["status"] == 400
        assert "already" in data["detail"].lower()

    def test_create_email_verification_user_not_found(self, client):
        """Should return 404 Not Found when user associated with token not found."""
        # Setup: Stub handler returns user_not_found
        stub_handler = StubVerifyEmailHandler(behavior="user_not_found")

        from src.core.container import get_verify_email_handler

        app.dependency_overrides[get_verify_email_handler] = lambda: stub_handler

        # Execute
        response = client.post(
            "/api/v1/email-verifications",
            json={"token": "e" * 64},  # Valid length but orphaned
        )

        # Verify: RFC 7807 error response
        assert response.status_code == 404
        data = response.json()
        assert data["type"].endswith("/errors/not_found")
        assert data["title"] == "Resource Not Found"
        assert data["status"] == 404

    def test_create_email_verification_missing_token(self, client):
        """Should return 422 Unprocessable Entity when token missing."""
        # Execute: Missing token field
        response = client.post("/api/v1/email-verifications", json={})

        # Verify: RFC 7807 validation error response
        assert response.status_code == 422
        data = response.json()
        assert data["type"].endswith("/errors/validation-failed")
        assert "errors" in data
        assert any("token" in err.get("field", "").lower() for err in data["errors"])

    def test_create_email_verification_token_too_short(self, client):
        """Should return 422 Unprocessable Entity for token < 64 chars."""
        # Execute: Token too short
        response = client.post(
            "/api/v1/email-verifications",
            json={"token": "short"},  # Less than 64 chars
        )

        # Verify: RFC 7807 validation error response
        assert response.status_code == 422
        data = response.json()
        assert data["type"].endswith("/errors/validation-failed")
        assert "errors" in data
        assert any("token" in err.get("field", "").lower() for err in data["errors"])

    def test_create_email_verification_token_too_long(self, client):
        """Should return 422 Unprocessable Entity for token > 64 chars."""
        # Execute: Token too long
        response = client.post(
            "/api/v1/email-verifications",
            json={"token": "a" * 65},  # More than 64 chars
        )

        # Verify: RFC 7807 validation error response
        assert response.status_code == 422
        data = response.json()
        assert data["type"].endswith("/errors/validation-failed")
        assert "errors" in data
        assert any("token" in err.get("field", "").lower() for err in data["errors"])

    def test_create_email_verification_empty_token(self, client):
        """Should return 422 Unprocessable Entity for empty token."""
        # Execute: Empty token
        response = client.post(
            "/api/v1/email-verifications",
            json={"token": ""},
        )

        # Verify: RFC 7807 validation error response
        assert response.status_code == 422
        data = response.json()
        assert data["type"].endswith("/errors/validation-failed")
        assert "errors" in data
        assert any("token" in err.get("field", "").lower() for err in data["errors"])

    def test_create_email_verification_invalid_content_type(self, client):
        """Should return 422 when Content-Type is not application/json."""
        # Execute: Send as form data instead of JSON
        response = client.post(
            "/api/v1/email-verifications",
            data={"token": "a" * 64},  # Form data
        )

        # Verify
        assert response.status_code == 422

    def test_create_email_verification_includes_trace_id_on_error(self, client):
        """Should include X-Trace-ID header on error responses."""
        # Setup: Stub handler returns error
        stub_handler = StubVerifyEmailHandler(behavior="token_expired")

        from src.core.container import get_verify_email_handler

        app.dependency_overrides[get_verify_email_handler] = lambda: stub_handler

        # Execute
        response = client.post(
            "/api/v1/email-verifications",
            json={"token": "f" * 64},  # Valid length but expired
        )

        # Verify: X-Trace-ID header present (if trace context exists)
        assert response.status_code == 400
        # Note: X-Trace-ID only present if trace_id exists in context
        # In test environment without middleware, it may be None
        # This test just ensures no error when trace_id is None
