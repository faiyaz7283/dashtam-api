"""Validation framework for input validation.

This module provides utility functions for common validation patterns.
All validation functions return Result types for consistent error handling.

Usage:
    from src.core.validation import validate_email, validate_not_empty
    from src.core.result import Success, Failure

    result = validate_email("user@example.com")
    match result:
        case Success(email):
            # Email is valid
            pass
        case Failure(error):
            # Handle validation error
            print(error.message)
"""

import re
from typing import Any

from src.core.errors import ErrorCode, ValidationError
from src.core.result import Failure, Result, Success


def validate_not_empty(value: Any, field_name: str) -> Result[Any, ValidationError]:
    """Validate that a value is not empty.

    Args:
        value: Value to validate.
        field_name: Name of the field being validated.

    Returns:
        Success with value if not empty, Failure with ValidationError otherwise.
    """
    if value is None or (isinstance(value, str) and not value.strip()):
        return Failure(
            error=ValidationError(
                code=ErrorCode.VALIDATION_FAILED,
                message=f"{field_name} cannot be empty",
                field=field_name,
            )
        )
    return Success(value=value)


def validate_email(email: str) -> Result[str, ValidationError]:
    """Validate email format.

    Args:
        email: Email address to validate.

    Returns:
        Success with email if valid, Failure with ValidationError otherwise.
    """
    # Basic email regex pattern
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"

    if not re.match(pattern, email):
        return Failure(
            error=ValidationError(
                code=ErrorCode.INVALID_EMAIL,
                message="Invalid email format",
                field="email",
            )
        )
    return Success(value=email)


def validate_min_length(
    value: str, min_length: int, field_name: str
) -> Result[str, ValidationError]:
    """Validate minimum string length.

    Args:
        value: String to validate.
        min_length: Minimum required length.
        field_name: Name of the field being validated.

    Returns:
        Success with value if valid, Failure with ValidationError otherwise.
    """
    if len(value) < min_length:
        return Failure(
            error=ValidationError(
                code=ErrorCode.VALIDATION_FAILED,
                message=f"{field_name} must be at least {min_length} characters",
                field=field_name,
            )
        )
    return Success(value=value)


def validate_max_length(
    value: str, max_length: int, field_name: str
) -> Result[str, ValidationError]:
    """Validate maximum string length.

    Args:
        value: String to validate.
        max_length: Maximum allowed length.
        field_name: Name of the field being validated.

    Returns:
        Success with value if valid, Failure with ValidationError otherwise.
    """
    if len(value) > max_length:
        return Failure(
            error=ValidationError(
                code=ErrorCode.VALIDATION_FAILED,
                message=f"{field_name} must be at most {max_length} characters",
                field=field_name,
            )
        )
    return Success(value=value)
