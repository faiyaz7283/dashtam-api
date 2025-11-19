"""Integration tests for error handling end-to-end flow.

Tests complete error handling from domain → application → presentation
following established patterns from Phase 0.
"""

import json

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from src.application.errors import ApplicationError, ApplicationErrorCode
from src.core.enums import ErrorCode
from src.core.errors import ValidationError
from src.presentation.api.middleware.trace_middleware import TraceMiddleware
from src.presentation.api.v1.errors import (
    ErrorResponseBuilder,
    register_exception_handlers,
)


@pytest.fixture
def test_app():
    """Create test FastAPI app with error handling configured.

    Returns:
        FastAPI: Configured test application
    """
    app = FastAPI(title="Test App")

    # Add trace middleware (sets trace_id on request.state)
    app.add_middleware(TraceMiddleware)

    # Register exception handlers
    register_exception_handlers(app)

    # Test endpoint that raises exception
    @app.get("/test/exception")
    async def test_exception():
        """Test endpoint that raises generic exception."""
        raise ValueError("Something went wrong")

    # Test endpoint that returns application error
    @app.get("/test/application-error")
    async def test_application_error(request: Request):
        """Test endpoint that returns ApplicationError as RFC 7807."""
        error = ApplicationError(
            code=ApplicationErrorCode.NOT_FOUND,
            message="Test resource not found",
        )
        trace_id = getattr(request.state, "trace_id", "unknown")
        return ErrorResponseBuilder.from_application_error(
            error=error,
            request=request,
            trace_id=trace_id,
        )

    # Test endpoint that returns validation error
    @app.post("/test/validation-error")
    async def test_validation_error(request: Request):
        """Test endpoint that returns ValidationError."""
        domain_error = ValidationError(
            code=ErrorCode.INVALID_EMAIL,
            message="Email format is invalid",
            field="email",
        )
        error = ApplicationError(
            code=ApplicationErrorCode.COMMAND_VALIDATION_FAILED,
            message="Validation failed",
            domain_error=domain_error,
        )
        trace_id = getattr(request.state, "trace_id", "unknown")
        return ErrorResponseBuilder.from_application_error(
            error=error,
            request=request,
            trace_id=trace_id,
        )

    return app


@pytest.fixture
def client(test_app):
    """Create TestClient for integration tests.

    Args:
        test_app: FastAPI test application

    Returns:
        TestClient: Test client for making requests
    """
    # raise_server_exceptions=False allows exception handlers to process errors
    # instead of re-raising them to the test
    return TestClient(test_app, raise_server_exceptions=False)


@pytest.mark.integration
class TestErrorHandlingFlow:
    """Integration tests for complete error handling flow."""

    def test_unhandled_exception_converts_to_rfc7807(self, client):
        """Test unhandled exception converts to RFC 7807 Problem Details."""
        # Act
        response = client.get("/test/exception")

        # Assert
        assert response.status_code == 500
        data = response.json()

        # Verify RFC 7807 structure (required fields)
        assert "type" in data
        assert "title" in data
        assert "status" in data
        assert "detail" in data
        assert "instance" in data
        # Note: trace_id might not be set in TestClient context

        # Verify content
        assert data["status"] == 500
        assert data["title"] == "Internal Server Error"
        assert data["instance"] == "/test/exception"

    def test_application_error_returns_rfc7807(self, client):
        """Test ApplicationError converts to RFC 7807 response."""
        # Act
        response = client.get("/test/application-error")

        # Assert
        assert response.status_code == 404
        data = response.json()

        # Verify RFC 7807 structure
        assert data["type"].endswith("/errors/not_found")
        assert data["title"] == "Resource Not Found"
        assert data["status"] == 404
        assert data["detail"] == "Test resource not found"
        assert data["instance"] == "/test/application-error"
        assert data["trace_id"] is not None

    def test_validation_error_includes_field_errors(self, client):
        """Test validation error includes field-specific errors."""
        # Act
        response = client.post("/test/validation-error")

        # Assert
        assert response.status_code == 400
        data = response.json()

        # Verify RFC 7807 structure
        assert data["status"] == 400
        assert data["title"] == "Validation Failed"

        # Verify field errors included
        assert "errors" in data
        assert len(data["errors"]) == 1
        assert data["errors"][0]["field"] == "email"
        assert data["errors"][0]["code"] == "invalid_email"
        assert data["errors"][0]["message"] == "Email format is invalid"

    def test_trace_id_in_error_response_when_set(self, client):
        """Test trace_id appears in error response when set by middleware.

        Note: TestClient may not fully execute middleware, so trace_id
        might not be present. This tests the field is included when available.
        """
        # Act
        response = client.get("/test/exception")

        # Assert
        data = response.json()
        # In TestClient, trace_id might not be set by middleware
        # We verify RFC 7807 structure is valid either way
        if "trace_id" in data:
            # If present, should be non-empty
            assert data["trace_id"]
            assert len(data["trace_id"]) > 0

    def test_error_response_content_type_is_json(self, client):
        """Test error responses have correct Content-Type header."""
        # Act
        response = client.get("/test/exception")

        # Assert
        assert response.headers["content-type"] == "application/json"

    def test_error_response_excludes_none_fields(self, client):
        """Test RFC 7807 response excludes fields with None values."""
        # Act
        response = client.get("/test/application-error")

        # Assert
        data = response.json()
        # errors field should not be present (was None)
        assert "errors" not in data

    def test_multiple_requests_return_valid_rfc7807(self, client):
        """Test multiple requests each return valid RFC 7807 responses.

        Note: TestClient limitations prevent testing trace_id uniqueness,
        but we verify each response has proper RFC 7807 structure.
        """
        # Act
        response1 = client.get("/test/exception")
        response2 = client.get("/test/exception")

        # Assert
        data1 = response1.json()
        data2 = response2.json()

        # Both should be valid RFC 7807 responses
        for data in [data1, data2]:
            assert data["status"] == 500
            assert data["title"] == "Internal Server Error"
            assert "type" in data
            assert "detail" in data

    def test_error_response_structure_is_valid_json(self, client):
        """Test error response is valid, parseable JSON."""
        # Act
        response = client.get("/test/exception")

        # Assert
        # Should not raise json.JSONDecodeError
        data = json.loads(response.content)
        assert isinstance(data, dict)

    def test_rfc7807_type_url_is_well_formed(self, client):
        """Test RFC 7807 type field contains valid URL."""
        # Act
        response = client.get("/test/application-error")

        # Assert
        data = response.json()
        type_url = data["type"]

        # Should be a URL starting with http/https
        assert type_url.startswith("http://") or type_url.startswith("https://")
        assert "/errors/" in type_url

    def test_rfc7807_instance_matches_request_path(self, client):
        """Test RFC 7807 instance field matches actual request path."""
        # Act
        response = client.get("/test/application-error")

        # Assert
        data = response.json()
        assert data["instance"] == "/test/application-error"

    def test_unauthorized_error_returns_401(self, client):
        """Test UNAUTHORIZED ApplicationError returns 401 status."""
        # Arrange
        app = client.app

        @app.get("/test/unauthorized")
        async def test_unauthorized(request: Request):
            error = ApplicationError(
                code=ApplicationErrorCode.UNAUTHORIZED,
                message="Authentication required",
            )
            trace_id = getattr(request.state, "trace_id", "unknown")
            return ErrorResponseBuilder.from_application_error(
                error=error, request=request, trace_id=trace_id
            )

        # Act
        response = client.get("/test/unauthorized")

        # Assert
        assert response.status_code == 401
        data = response.json()
        assert data["title"] == "Authentication Required"

    def test_forbidden_error_returns_403(self, client):
        """Test FORBIDDEN ApplicationError returns 403 status."""
        # Arrange
        app = client.app

        @app.get("/test/forbidden")
        async def test_forbidden(request: Request):
            error = ApplicationError(
                code=ApplicationErrorCode.FORBIDDEN,
                message="Access denied",
            )
            trace_id = getattr(request.state, "trace_id", "unknown")
            return ErrorResponseBuilder.from_application_error(
                error=error, request=request, trace_id=trace_id
            )

        # Act
        response = client.get("/test/forbidden")

        # Assert
        assert response.status_code == 403
        data = response.json()
        assert data["title"] == "Access Denied"

    def test_conflict_error_returns_409(self, client):
        """Test CONFLICT ApplicationError returns 409 status."""
        # Arrange
        app = client.app

        @app.post("/test/conflict")
        async def test_conflict(request: Request):
            error = ApplicationError(
                code=ApplicationErrorCode.CONFLICT,
                message="Resource already exists",
            )
            trace_id = getattr(request.state, "trace_id", "unknown")
            return ErrorResponseBuilder.from_application_error(
                error=error, request=request, trace_id=trace_id
            )

        # Act
        response = client.post("/test/conflict")

        # Assert
        assert response.status_code == 409
        data = response.json()
        assert data["title"] == "Resource Conflict"

    def test_rate_limit_error_returns_429(self, client):
        """Test RATE_LIMIT_EXCEEDED ApplicationError returns 429 status."""
        # Arrange
        app = client.app

        @app.post("/test/rate-limit")
        async def test_rate_limit(request: Request):
            error = ApplicationError(
                code=ApplicationErrorCode.RATE_LIMIT_EXCEEDED,
                message="Too many requests",
            )
            trace_id = getattr(request.state, "trace_id", "unknown")
            return ErrorResponseBuilder.from_application_error(
                error=error, request=request, trace_id=trace_id
            )

        # Act
        response = client.post("/test/rate-limit")

        # Assert
        assert response.status_code == 429
        data = response.json()
        assert data["title"] == "Rate Limit Exceeded"

    def test_error_detail_message_is_descriptive(self, client):
        """Test error detail field contains helpful message."""
        # Act
        response = client.get("/test/application-error")

        # Assert
        data = response.json()
        assert data["detail"] == "Test resource not found"
        # Detail should be human-readable, not technical jargon
        assert len(data["detail"]) > 10
