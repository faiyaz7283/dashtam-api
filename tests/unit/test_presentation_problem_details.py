"""Unit tests for RFC 7807 Problem Details schemas.

Tests ProblemDetails and ErrorDetail Pydantic models following
established testing patterns from Phase 0.
"""

import pytest
from pydantic import ValidationError as PydanticValidationError

from src.presentation.api.v1.errors import ErrorDetail, ProblemDetails


@pytest.mark.unit
class TestErrorDetail:
    """Unit tests for ErrorDetail Pydantic model."""

    def test_create_error_detail_with_all_fields(self):
        """Test creating ErrorDetail with all required fields."""
        # Arrange & Act
        detail = ErrorDetail(
            field="email",
            code="invalid_email",
            message="Email address format is invalid",
        )

        # Assert
        assert detail.field == "email"
        assert detail.code == "invalid_email"
        assert detail.message == "Email address format is invalid"

    def test_error_detail_serializes_to_dict(self):
        """Test ErrorDetail serializes to dictionary correctly."""
        # Arrange
        detail = ErrorDetail(
            field="password",
            code="password_too_weak",
            message="Password must be at least 12 characters",
        )

        # Act
        serialized = detail.model_dump()

        # Assert
        assert serialized == {
            "field": "password",
            "code": "password_too_weak",
            "message": "Password must be at least 12 characters",
        }

    def test_error_detail_requires_all_fields(self):
        """Test ErrorDetail validation fails when fields missing."""
        # Act & Assert
        with pytest.raises(PydanticValidationError) as exc_info:
            ErrorDetail(field="email")  # type: ignore

        # Verify validation error mentions missing fields
        errors = exc_info.value.errors()
        missing_fields = {error["loc"][0] for error in errors}
        assert "code" in missing_fields
        assert "message" in missing_fields


@pytest.mark.unit
class TestProblemDetails:
    """Unit tests for ProblemDetails Pydantic model."""

    def test_create_problem_details_with_required_fields(self):
        """Test creating ProblemDetails with only required fields."""
        # Arrange & Act
        problem = ProblemDetails(
            type="https://api.dashtam.com/errors/not-found",
            title="Resource Not Found",
            status=404,
            detail="User with ID '123' does not exist",
            instance="/api/v1/users/123",
        )

        # Assert
        assert problem.type == "https://api.dashtam.com/errors/not-found"
        assert problem.title == "Resource Not Found"
        assert problem.status == 404
        assert problem.detail == "User with ID '123' does not exist"
        assert problem.instance == "/api/v1/users/123"
        assert problem.errors is None
        assert problem.trace_id is None

    def test_create_problem_details_with_field_errors(self):
        """Test creating ProblemDetails with field-specific errors."""
        # Arrange
        field_errors = [
            ErrorDetail(
                field="email",
                code="invalid_email",
                message="Email format is invalid",
            ),
            ErrorDetail(
                field="password",
                code="password_too_weak",
                message="Password too weak",
            ),
        ]

        # Act
        problem = ProblemDetails(
            type="https://api.dashtam.com/errors/validation-error",
            title="Validation Failed",
            status=400,
            detail="Request validation failed",
            instance="/api/v1/auth/register",
            errors=field_errors,
        )

        # Assert
        assert problem.status == 400
        assert problem.errors is not None
        assert len(problem.errors) == 2
        assert problem.errors[0].field == "email"
        assert problem.errors[1].field == "password"

    def test_create_problem_details_with_trace_id(self):
        """Test creating ProblemDetails with trace ID."""
        # Arrange & Act
        problem = ProblemDetails(
            type="https://api.dashtam.com/errors/internal-server-error",
            title="Internal Server Error",
            status=500,
            detail="An unexpected error occurred",
            instance="/api/v1/users",
            trace_id="550e8400-e29b-41d4-a716-446655440000",
        )

        # Assert
        assert problem.trace_id == "550e8400-e29b-41d4-a716-446655440000"

    def test_problem_details_serializes_to_dict(self):
        """Test ProblemDetails serializes to dictionary correctly."""
        # Arrange
        problem = ProblemDetails(
            type="https://api.dashtam.com/errors/not-found",
            title="Resource Not Found",
            status=404,
            detail="User not found",
            instance="/api/v1/users/123",
            trace_id="abc-123",
        )

        # Act
        serialized = problem.model_dump()

        # Assert
        assert serialized["type"] == "https://api.dashtam.com/errors/not-found"
        assert serialized["title"] == "Resource Not Found"
        assert serialized["status"] == 404
        assert serialized["detail"] == "User not found"
        assert serialized["instance"] == "/api/v1/users/123"
        assert serialized["trace_id"] == "abc-123"
        assert serialized["errors"] is None

    def test_problem_details_excludes_none_values(self):
        """Test ProblemDetails excludes None values when serializing."""
        # Arrange
        problem = ProblemDetails(
            type="https://api.dashtam.com/errors/not-found",
            title="Resource Not Found",
            status=404,
            detail="User not found",
            instance="/api/v1/users/123",
            # errors and trace_id not provided (None)
        )

        # Act
        serialized = problem.model_dump(exclude_none=True)

        # Assert
        assert "errors" not in serialized
        assert "trace_id" not in serialized
        # Required fields should still be present
        assert "type" in serialized
        assert "status" in serialized

    def test_problem_details_validation_error_example(self):
        """Test complete validation error RFC 7807 response."""
        # Arrange
        field_errors = [
            ErrorDetail(
                field="email",
                code="invalid_email",
                message="Email address format is invalid",
            )
        ]

        # Act
        problem = ProblemDetails(
            type="https://api.dashtam.com/errors/validation-error",
            title="Validation Failed",
            status=400,
            detail="The email address format is invalid",
            instance="/api/v1/auth/register",
            errors=field_errors,
            trace_id="550e8400-e29b-41d4-a716-446655440000",
        )

        # Assert
        serialized = problem.model_dump(exclude_none=True)
        assert serialized["type"] == "https://api.dashtam.com/errors/validation-error"
        assert serialized["title"] == "Validation Failed"
        assert serialized["status"] == 400
        assert serialized["errors"][0]["field"] == "email"
        assert serialized["trace_id"] == "550e8400-e29b-41d4-a716-446655440000"

    def test_problem_details_unauthorized_example(self):
        """Test complete unauthorized error RFC 7807 response."""
        # Arrange & Act
        problem = ProblemDetails(
            type="https://api.dashtam.com/errors/unauthorized",
            title="Authentication Required",
            status=401,
            detail="Valid authentication credentials are required",
            instance="/api/v1/accounts",
            trace_id="abc-def-123",
        )

        # Assert
        assert problem.status == 401
        assert problem.title == "Authentication Required"
        assert problem.errors is None

    def test_problem_details_requires_all_required_fields(self):
        """Test ProblemDetails validation fails when required fields missing."""
        # Act & Assert
        with pytest.raises(PydanticValidationError) as exc_info:
            ProblemDetails(  # type: ignore
                type="https://api.dashtam.com/errors/error",
                title="Error",
                # Missing status, detail, instance
            )

        # Verify validation error mentions missing fields
        errors = exc_info.value.errors()
        missing_fields = {error["loc"][0] for error in errors}
        assert "status" in missing_fields
        assert "detail" in missing_fields
        assert "instance" in missing_fields

    def test_problem_details_conflict_example(self):
        """Test complete conflict error RFC 7807 response."""
        # Arrange & Act
        problem = ProblemDetails(
            type="https://api.dashtam.com/errors/conflict",
            title="Resource Conflict",
            status=409,
            detail="User with email 'user@example.com' already exists",
            instance="/api/v1/users",
            trace_id="conflict-trace-123",
        )

        # Assert
        assert problem.status == 409
        assert problem.title == "Resource Conflict"
        assert "already exists" in problem.detail
