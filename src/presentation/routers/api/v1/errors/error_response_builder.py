"""Error response builder for RFC 9457 Problem Details.

This module provides utilities to build RFC 9457 compliant error responses
from application layer errors.

Exports:
    ErrorResponseBuilder: Utility class for building RFC 9457 responses
"""

from fastapi import Request, status
from fastapi.responses import JSONResponse

from src.application.errors import ApplicationError, ApplicationErrorCode
from src.core.config import settings
from src.presentation.routers.api.v1.errors.problem_details import (
    ErrorDetail,
    ProblemDetails,
)


class ErrorResponseBuilder:
    """Build RFC 9457 Problem Details error responses.

    Converts application layer errors into standardized RFC 9457 JSON responses
    with appropriate HTTP status codes and structured error information.

    Example:
        >>> error = ApplicationError(
        ...     code=ApplicationErrorCode.COMMAND_VALIDATION_FAILED,
        ...     message="Email is invalid",
        ... )
        >>> response = ErrorResponseBuilder.from_application_error(
        ...     error=error,
        ...     request=request,
        ...     trace_id="550e8400-e29b-41d4-a716-446655440000",
        ... )
    """

    @staticmethod
    def from_application_error(
        error: ApplicationError,
        request: Request,
        trace_id: str,
    ) -> JSONResponse:
        """Convert ApplicationError to RFC 9457 JSON response.

        Args:
            error: Application layer error to convert
            request: FastAPI Request object (for instance URL)
            trace_id: Request trace ID for debugging

        Returns:
            JSONResponse with RFC 9457 ProblemDetails content

        Example:
            >>> error = ApplicationError(
            ...     code=ApplicationErrorCode.NOT_FOUND,
            ...     message="User not found",
            ... )
            >>> response = ErrorResponseBuilder.from_application_error(
            ...     error, request, trace_id
            ... )
            >>> # Returns 404 with ProblemDetails JSON
        """
        # Map application error code to HTTP status
        status_code = ErrorResponseBuilder._get_status_code(error.code)

        # Build RFC 9457 Problem Details
        problem = ProblemDetails(
            type=f"{settings.api_base_url}/errors/{error.code.value}",
            title=ErrorResponseBuilder._get_title(error.code),
            status=status_code,
            detail=error.message,
            instance=str(request.url.path),
            errors=None,
            trace_id=trace_id,
        )

        # Add field-specific errors if validation failure with domain error
        if error.domain_error and hasattr(error.domain_error, "field"):
            problem.errors = [
                ErrorDetail(
                    field=error.domain_error.field or "unknown",
                    code=error.domain_error.code.value,
                    message=error.domain_error.message,
                )
            ]

        return JSONResponse(
            status_code=status_code,
            content=problem.model_dump(exclude_none=True),
        )

    @staticmethod
    def _get_status_code(code: ApplicationErrorCode) -> int:
        """Map application error code to HTTP status code.

        Args:
            code: Application error code

        Returns:
            HTTP status code (400-599)

        Example:
            >>> ErrorResponseBuilder._get_status_code(
            ...     ApplicationErrorCode.NOT_FOUND
            ... )
            404
        """
        mapping = {
            ApplicationErrorCode.COMMAND_VALIDATION_FAILED: status.HTTP_400_BAD_REQUEST,
            ApplicationErrorCode.QUERY_VALIDATION_FAILED: status.HTTP_400_BAD_REQUEST,
            ApplicationErrorCode.COMMAND_EXECUTION_FAILED: status.HTTP_500_INTERNAL_SERVER_ERROR,
            ApplicationErrorCode.QUERY_FAILED: status.HTTP_500_INTERNAL_SERVER_ERROR,
            ApplicationErrorCode.QUERY_EXECUTION_FAILED: status.HTTP_500_INTERNAL_SERVER_ERROR,
            ApplicationErrorCode.EXTERNAL_SERVICE_ERROR: status.HTTP_502_BAD_GATEWAY,
            ApplicationErrorCode.UNAUTHORIZED: status.HTTP_401_UNAUTHORIZED,
            ApplicationErrorCode.FORBIDDEN: status.HTTP_403_FORBIDDEN,
            ApplicationErrorCode.NOT_FOUND: status.HTTP_404_NOT_FOUND,
            ApplicationErrorCode.CONFLICT: status.HTTP_409_CONFLICT,
            ApplicationErrorCode.RATE_LIMIT_EXCEEDED: status.HTTP_429_TOO_MANY_REQUESTS,
        }
        return mapping.get(code, status.HTTP_500_INTERNAL_SERVER_ERROR)

    @staticmethod
    def _get_title(code: ApplicationErrorCode) -> str:
        """Get human-readable title for application error code.

        Args:
            code: Application error code

        Returns:
            Human-readable title string

        Example:
            >>> ErrorResponseBuilder._get_title(
            ...     ApplicationErrorCode.NOT_FOUND
            ... )
            'Resource Not Found'
        """
        mapping = {
            ApplicationErrorCode.COMMAND_VALIDATION_FAILED: "Validation Failed",
            ApplicationErrorCode.QUERY_VALIDATION_FAILED: "Validation Failed",
            ApplicationErrorCode.COMMAND_EXECUTION_FAILED: "Command Execution Failed",
            ApplicationErrorCode.QUERY_FAILED: "Query Failed",
            ApplicationErrorCode.QUERY_EXECUTION_FAILED: "Query Execution Failed",
            ApplicationErrorCode.EXTERNAL_SERVICE_ERROR: "External Service Error",
            ApplicationErrorCode.UNAUTHORIZED: "Authentication Required",
            ApplicationErrorCode.FORBIDDEN: "Access Denied",
            ApplicationErrorCode.NOT_FOUND: "Resource Not Found",
            ApplicationErrorCode.CONFLICT: "Resource Conflict",
            ApplicationErrorCode.RATE_LIMIT_EXCEEDED: "Rate Limit Exceeded",
        }
        return mapping.get(code, "Internal Server Error")
