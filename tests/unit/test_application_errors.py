"""Unit tests for application layer errors.

Tests ApplicationError dataclass and ApplicationErrorCode enum following
established testing patterns from Phase 0.
"""

import pytest

from src.application.errors import ApplicationError, ApplicationErrorCode
from src.core.enums import ErrorCode
from src.core.errors import ValidationError


@pytest.mark.unit
class TestApplicationErrorCode:
    """Unit tests for ApplicationErrorCode enum."""

    def test_enum_has_all_expected_codes(self):
        """Test enum contains all required error codes."""
        expected_codes = {
            "COMMAND_VALIDATION_FAILED",
            "COMMAND_EXECUTION_FAILED",
            "QUERY_VALIDATION_FAILED",
            "QUERY_EXECUTION_FAILED",
            "QUERY_FAILED",
            "UNAUTHORIZED",
            "FORBIDDEN",
            "NOT_FOUND",
            "CONFLICT",
            "RATE_LIMIT_EXCEEDED",
            "EXTERNAL_SERVICE_ERROR",
        }

        actual_codes = {code.name for code in ApplicationErrorCode}

        assert actual_codes == expected_codes

    def test_enum_values_are_snake_case(self):
        """Test enum values use snake_case convention."""
        for code in ApplicationErrorCode:
            # Value should be lowercase with underscores
            assert code.value == code.value.lower()
            assert " " not in code.value
            # If value has multiple words, should use underscores
            if "_" in code.name:
                assert "_" in code.value

    def test_command_validation_failed_value(self):
        """Test COMMAND_VALIDATION_FAILED has correct value."""
        assert (
            ApplicationErrorCode.COMMAND_VALIDATION_FAILED.value
            == "command_validation_failed"
        )

    def test_unauthorized_value(self):
        """Test UNAUTHORIZED has correct value."""
        assert ApplicationErrorCode.UNAUTHORIZED.value == "unauthorized"

    def test_not_found_value(self):
        """Test NOT_FOUND has correct value."""
        assert ApplicationErrorCode.NOT_FOUND.value == "not_found"


@pytest.mark.unit
class TestApplicationError:
    """Unit tests for ApplicationError dataclass."""

    def test_create_error_with_required_fields(self):
        """Test creating ApplicationError with only required fields."""
        # Arrange & Act
        error = ApplicationError(
            code=ApplicationErrorCode.NOT_FOUND,
            message="User not found",
        )

        # Assert
        assert error.code == ApplicationErrorCode.NOT_FOUND
        assert error.message == "User not found"
        assert error.domain_error is None
        assert error.details is None

    def test_create_error_with_domain_error(self):
        """Test creating ApplicationError with wrapped domain error."""
        # Arrange
        domain_error = ValidationError(
            code=ErrorCode.INVALID_EMAIL,
            message="Email format is invalid",
            field="email",
        )

        # Act
        error = ApplicationError(
            code=ApplicationErrorCode.COMMAND_VALIDATION_FAILED,
            message="User creation failed: validation error",
            domain_error=domain_error,
        )

        # Assert
        assert error.code == ApplicationErrorCode.COMMAND_VALIDATION_FAILED
        assert error.message == "User creation failed: validation error"
        assert error.domain_error == domain_error
        assert error.domain_error.field == "email"

    def test_create_error_with_details(self):
        """Test creating ApplicationError with additional details."""
        # Arrange & Act
        error = ApplicationError(
            code=ApplicationErrorCode.QUERY_FAILED,
            message="User query failed",
            details={"user_id": "123e4567-e89b-12d3-a456-426614174000"},
        )

        # Assert
        assert error.code == ApplicationErrorCode.QUERY_FAILED
        assert error.message == "User query failed"
        assert error.details is not None
        assert "user_id" in error.details
        assert error.details["user_id"] == "123e4567-e89b-12d3-a456-426614174000"

    def test_create_error_with_all_fields(self):
        """Test creating ApplicationError with all optional fields."""
        # Arrange
        domain_error = ValidationError(
            code=ErrorCode.INVALID_EMAIL,
            message="Email format is invalid",
            field="email",
        )

        # Act
        error = ApplicationError(
            code=ApplicationErrorCode.COMMAND_VALIDATION_FAILED,
            message="Command validation failed",
            domain_error=domain_error,
            details={"field": "email", "value": "invalid-email"},
        )

        # Assert
        assert error.code == ApplicationErrorCode.COMMAND_VALIDATION_FAILED
        assert error.message == "Command validation failed"
        assert error.domain_error == domain_error
        assert error.details == {"field": "email", "value": "invalid-email"}

    def test_error_is_immutable(self):
        """Test ApplicationError is frozen (immutable)."""
        # Arrange
        error = ApplicationError(
            code=ApplicationErrorCode.NOT_FOUND,
            message="User not found",
        )

        # Act & Assert
        with pytest.raises(AttributeError):
            error.message = "Different message"  # type: ignore

    def test_error_uses_keyword_only_args(self):
        """Test ApplicationError requires keyword arguments."""
        # Act & Assert - positional args should fail
        with pytest.raises(TypeError):
            ApplicationError(  # type: ignore
                ApplicationErrorCode.NOT_FOUND,
                "User not found",
            )

    def test_unauthorized_error(self):
        """Test creating UNAUTHORIZED error."""
        # Arrange & Act
        error = ApplicationError(
            code=ApplicationErrorCode.UNAUTHORIZED,
            message="Authentication required",
        )

        # Assert
        assert error.code == ApplicationErrorCode.UNAUTHORIZED
        assert error.message == "Authentication required"

    def test_forbidden_error(self):
        """Test creating FORBIDDEN error."""
        # Arrange & Act
        error = ApplicationError(
            code=ApplicationErrorCode.FORBIDDEN,
            message="Access denied to resource",
        )

        # Assert
        assert error.code == ApplicationErrorCode.FORBIDDEN
        assert error.message == "Access denied to resource"

    def test_conflict_error(self):
        """Test creating CONFLICT error."""
        # Arrange & Act
        error = ApplicationError(
            code=ApplicationErrorCode.CONFLICT,
            message="Email already exists",
            details={"field": "email"},
        )

        # Assert
        assert error.code == ApplicationErrorCode.CONFLICT
        assert error.message == "Email already exists"
        assert error.details == {"field": "email"}

    def test_rate_limit_exceeded_error(self):
        """Test creating RATE_LIMIT_EXCEEDED error."""
        # Arrange & Act
        error = ApplicationError(
            code=ApplicationErrorCode.RATE_LIMIT_EXCEEDED,
            message="Too many requests",
            details={"retry_after": "60"},
        )

        # Assert
        assert error.code == ApplicationErrorCode.RATE_LIMIT_EXCEEDED
        assert error.message == "Too many requests"
        assert error.details == {"retry_after": "60"}
