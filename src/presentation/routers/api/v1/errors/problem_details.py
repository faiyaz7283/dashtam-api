"""RFC 7807 Problem Details for HTTP APIs.

This module implements RFC 7807 (Problem Details for HTTP APIs) using Pydantic
models for structured error responses.

RFC 7807: https://tools.ietf.org/html/rfc7807

Exports:
    ErrorDetail: Individual field-specific error
    ProblemDetails: RFC 7807 compliant error response schema
"""

from pydantic import BaseModel, Field


class ErrorDetail(BaseModel):
    """Individual field-specific error.

    Used for validation errors where multiple fields may have errors.

    Attributes:
        field: Name of the field with error
        code: Machine-readable error code
        message: Human-readable error message

    Examples:
        >>> error = ErrorDetail(
        ...     field="email",
        ...     code="invalid_email",
        ...     message="Email address format is invalid",
        ... )
    """

    field: str = Field(..., description="Field name")
    code: str = Field(..., description="Machine-readable error code")
    message: str = Field(..., description="Human-readable error message")


class ProblemDetails(BaseModel):
    """RFC 7807 Problem Details for HTTP APIs.

    Standard error response format providing structured information about errors
    in HTTP APIs. All fields follow RFC 7807 specification.

    Attributes:
        type: URI reference identifying the problem type
        title: Short, human-readable summary of the problem type
        status: HTTP status code for this occurrence
        detail: Human-readable explanation specific to this occurrence
        instance: URI reference identifying the specific occurrence
        errors: Optional list of field-specific errors (for validation failures)
        trace_id: Optional request trace ID for debugging

    Examples:
        >>> # Validation error
        >>> problem = ProblemDetails(
        ...     type="https://api.dashtam.com/errors/validation-error",
        ...     title="Validation Failed",
        ...     status=400,
        ...     detail="The email address format is invalid",
        ...     instance="/api/v1/auth/register",
        ...     errors=[
        ...         ErrorDetail(
        ...             field="email",
        ...             code="invalid_email",
        ...             message="Email address format is invalid",
        ...         )
        ...     ],
        ...     trace_id="550e8400-e29b-41d4-a716-446655440000",
        ... )
        >>>
        >>> # Not found error
        >>> problem = ProblemDetails(
        ...     type="https://api.dashtam.com/errors/not-found",
        ...     title="Resource Not Found",
        ...     status=404,
        ...     detail="User with ID '123' does not exist",
        ...     instance="/api/v1/users/123",
        ...     trace_id="550e8400-e29b-41d4-a716-446655440000",
        ... )
    """

    type: str = Field(
        ...,
        description="URI reference identifying the problem type",
        examples=["https://api.dashtam.com/errors/validation-error"],
    )
    title: str = Field(
        ...,
        description="Short, human-readable summary",
        examples=["Validation Failed"],
    )
    status: int = Field(
        ...,
        description="HTTP status code",
        examples=[400],
    )
    detail: str = Field(
        ...,
        description="Human-readable explanation",
        examples=["The email address format is invalid"],
    )
    instance: str = Field(
        ...,
        description="URI reference identifying this occurrence",
        examples=["/api/v1/auth/register"],
    )
    errors: list[ErrorDetail] | None = Field(
        None,
        description="List of field-specific errors",
    )
    trace_id: str | None = Field(
        None,
        description="Request trace ID for debugging",
    )
