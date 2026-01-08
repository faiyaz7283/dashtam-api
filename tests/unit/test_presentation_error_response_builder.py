"""Unit tests for ErrorResponseBuilder utility.

Tests ErrorResponseBuilder class following established testing patterns from Phase 0.
"""

from unittest.mock import MagicMock

import pytest
from fastapi import status

from src.application.errors import ApplicationError, ApplicationErrorCode
from src.core.enums import ErrorCode
from src.core.errors import ValidationError
from src.presentation.routers.api.v1.errors import ErrorResponseBuilder


@pytest.mark.unit
class TestErrorResponseBuilder:
    """Unit tests for ErrorResponseBuilder utility class."""

    def test_from_application_error_not_found(self):
        """Test building RFC 7807 response for NOT_FOUND error."""
        # Arrange
        error = ApplicationError(
            code=ApplicationErrorCode.NOT_FOUND,
            message="User not found",
        )
        request = MagicMock()
        request.url.path = "/api/v1/users/123"
        trace_id = "550e8400-e29b-41d4-a716-446655440000"

        # Act
        response = ErrorResponseBuilder.from_application_error(
            error=error,
            request=request,
            trace_id=trace_id,
        )

        # Assert
        assert response.status_code == 404
        content = bytes(response.body).decode()
        assert "not_found" in content
        assert "Resource Not Found" in content
        assert "User not found" in content
        assert "/api/v1/users/123" in content
        assert trace_id in content

    def test_from_application_error_validation_failed(self):
        """Test building RFC 7807 response for COMMAND_VALIDATION_FAILED error."""
        # Arrange
        error = ApplicationError(
            code=ApplicationErrorCode.COMMAND_VALIDATION_FAILED,
            message="Email format is invalid",
        )
        request = MagicMock()
        request.url.path = "/api/v1/auth/register"
        trace_id = "abc-123"

        # Act
        response = ErrorResponseBuilder.from_application_error(
            error=error,
            request=request,
            trace_id=trace_id,
        )

        # Assert
        assert response.status_code == 400
        content = bytes(response.body).decode()
        assert "command_validation_failed" in content
        assert "Validation Failed" in content
        assert "Email format is invalid" in content

    def test_from_application_error_with_domain_error_field(self):
        """Test building response with domain error field details."""
        # Arrange
        domain_error = ValidationError(
            code=ErrorCode.INVALID_EMAIL,
            message="Email format is invalid",
            field="email",
        )
        error = ApplicationError(
            code=ApplicationErrorCode.COMMAND_VALIDATION_FAILED,
            message="User creation failed",
            domain_error=domain_error,
        )
        request = MagicMock()
        request.url.path = "/api/v1/users"
        trace_id = "trace-123"

        # Act
        response = ErrorResponseBuilder.from_application_error(
            error=error,
            request=request,
            trace_id=trace_id,
        )

        # Assert
        assert response.status_code == 400
        content = bytes(response.body).decode()
        # Should include field-specific error details
        assert "email" in content
        assert "invalid_email" in content

    def test_from_application_error_unauthorized(self):
        """Test building RFC 7807 response for UNAUTHORIZED error."""
        # Arrange
        error = ApplicationError(
            code=ApplicationErrorCode.UNAUTHORIZED,
            message="Authentication required",
        )
        request = MagicMock()
        request.url.path = "/api/v1/accounts"
        trace_id = "401-trace"

        # Act
        response = ErrorResponseBuilder.from_application_error(
            error=error,
            request=request,
            trace_id=trace_id,
        )

        # Assert
        assert response.status_code == 401
        content = bytes(response.body).decode()
        assert "unauthorized" in content
        assert "Authentication Required" in content

    def test_from_application_error_forbidden(self):
        """Test building RFC 7807 response for FORBIDDEN error."""
        # Arrange
        error = ApplicationError(
            code=ApplicationErrorCode.FORBIDDEN,
            message="Access denied",
        )
        request = MagicMock()
        request.url.path = "/api/v1/admin"
        trace_id = "403-trace"

        # Act
        response = ErrorResponseBuilder.from_application_error(
            error=error,
            request=request,
            trace_id=trace_id,
        )

        # Assert
        assert response.status_code == 403
        content = bytes(response.body).decode()
        assert "forbidden" in content
        assert "Access Denied" in content

    def test_from_application_error_conflict(self):
        """Test building RFC 7807 response for CONFLICT error."""
        # Arrange
        error = ApplicationError(
            code=ApplicationErrorCode.CONFLICT,
            message="Email already exists",
        )
        request = MagicMock()
        request.url.path = "/api/v1/users"
        trace_id = "409-trace"

        # Act
        response = ErrorResponseBuilder.from_application_error(
            error=error,
            request=request,
            trace_id=trace_id,
        )

        # Assert
        assert response.status_code == 409
        content = bytes(response.body).decode()
        assert "conflict" in content
        assert "Resource Conflict" in content

    def test_from_application_error_rate_limit_exceeded(self):
        """Test building RFC 7807 response for RATE_LIMIT_EXCEEDED error."""
        # Arrange
        error = ApplicationError(
            code=ApplicationErrorCode.RATE_LIMIT_EXCEEDED,
            message="Too many requests",
        )
        request = MagicMock()
        request.url.path = "/api/v1/auth/login"
        trace_id = "429-trace"

        # Act
        response = ErrorResponseBuilder.from_application_error(
            error=error,
            request=request,
            trace_id=trace_id,
        )

        # Assert
        assert response.status_code == 429
        content = bytes(response.body).decode()
        assert "rate_limit_exceeded" in content
        assert "Rate Limit Exceeded" in content

    def test_get_status_code_mapping(self):
        """Test _get_status_code maps all error codes correctly."""
        # Test all mappings
        assert (
            ErrorResponseBuilder._get_status_code(
                ApplicationErrorCode.COMMAND_VALIDATION_FAILED
            )
            == status.HTTP_400_BAD_REQUEST
        )
        assert (
            ErrorResponseBuilder._get_status_code(ApplicationErrorCode.UNAUTHORIZED)
            == status.HTTP_401_UNAUTHORIZED
        )
        assert (
            ErrorResponseBuilder._get_status_code(ApplicationErrorCode.FORBIDDEN)
            == status.HTTP_403_FORBIDDEN
        )
        assert (
            ErrorResponseBuilder._get_status_code(ApplicationErrorCode.NOT_FOUND)
            == status.HTTP_404_NOT_FOUND
        )
        assert (
            ErrorResponseBuilder._get_status_code(ApplicationErrorCode.CONFLICT)
            == status.HTTP_409_CONFLICT
        )
        assert (
            ErrorResponseBuilder._get_status_code(
                ApplicationErrorCode.RATE_LIMIT_EXCEEDED
            )
            == status.HTTP_429_TOO_MANY_REQUESTS
        )

    def test_get_status_code_defaults_to_500(self):
        """Test _get_status_code returns 500 for unmapped codes."""
        # Arrange - Use codes that map to 500
        codes_500 = [
            ApplicationErrorCode.COMMAND_EXECUTION_FAILED,
            ApplicationErrorCode.QUERY_FAILED,
        ]

        # Act & Assert
        for code in codes_500:
            assert (
                ErrorResponseBuilder._get_status_code(code)
                == status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def test_get_title_mapping(self):
        """Test _get_title maps all error codes correctly."""
        # Test all mappings
        assert (
            ErrorResponseBuilder._get_title(
                ApplicationErrorCode.COMMAND_VALIDATION_FAILED
            )
            == "Validation Failed"
        )
        assert (
            ErrorResponseBuilder._get_title(ApplicationErrorCode.UNAUTHORIZED)
            == "Authentication Required"
        )
        assert (
            ErrorResponseBuilder._get_title(ApplicationErrorCode.FORBIDDEN)
            == "Access Denied"
        )
        assert (
            ErrorResponseBuilder._get_title(ApplicationErrorCode.NOT_FOUND)
            == "Resource Not Found"
        )
        assert (
            ErrorResponseBuilder._get_title(ApplicationErrorCode.CONFLICT)
            == "Resource Conflict"
        )
        assert (
            ErrorResponseBuilder._get_title(ApplicationErrorCode.RATE_LIMIT_EXCEEDED)
            == "Rate Limit Exceeded"
        )

    def test_get_title_has_all_mappings(self):
        """Test _get_title maps COMMAND_EXECUTION_FAILED and QUERY_FAILED."""
        # These codes have explicit mappings (not default)
        assert (
            ErrorResponseBuilder._get_title(
                ApplicationErrorCode.COMMAND_EXECUTION_FAILED
            )
            == "Command Execution Failed"
        )
        assert (
            ErrorResponseBuilder._get_title(ApplicationErrorCode.QUERY_FAILED)
            == "Query Failed"
        )

    def test_response_excludes_none_values(self):
        """Test response JSON excludes None values."""
        # Arrange
        error = ApplicationError(
            code=ApplicationErrorCode.NOT_FOUND,
            message="User not found",
            # domain_error and details are None
        )
        request = MagicMock()
        request.url.path = "/api/v1/users/123"
        trace_id = "trace-123"

        # Act
        response = ErrorResponseBuilder.from_application_error(
            error=error,
            request=request,
            trace_id=trace_id,
        )

        # Assert
        content = bytes(response.body).decode()
        # errors field should not be in JSON when None
        assert '"errors":' not in content or '"errors": null' not in content
