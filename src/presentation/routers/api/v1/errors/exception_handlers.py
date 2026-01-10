"""Global exception handlers for FastAPI application.

This module provides exception handlers that catch unhandled exceptions
and convert them to RFC 7807 Problem Details responses.

Handlers:
    http_exception_handler: Converts HTTPException to RFC 7807 format
    validation_exception_handler: Converts RequestValidationError to RFC 7807 format
    generic_exception_handler: Catches all unhandled exceptions

Exports:
    register_exception_handlers: Register all exception handlers with FastAPI app
"""

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from src.core.config import settings
from src.presentation.routers.api.v1.errors.problem_details import (
    ErrorDetail,
    ProblemDetails,
)


# HTTP status code to title mapping for RFC 7807
_HTTP_STATUS_TITLES: dict[int, str] = {
    400: "Bad Request",
    401: "Authentication Required",
    403: "Access Denied",
    404: "Resource Not Found",
    405: "Method Not Allowed",
    409: "Resource Conflict",
    415: "Unsupported Media Type",
    422: "Validation Failed",
    429: "Too Many Requests",
    500: "Internal Server Error",
    502: "Bad Gateway",
    503: "Service Unavailable",
}


async def http_exception_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    """Convert HTTPException to RFC 7807 Problem Details response.

    This handler ensures all HTTPException responses (e.g., from auth dependencies)
    are returned in RFC 7807 format for consistency.

    Args:
        request: FastAPI Request object.
        exc: HTTPException raised by handler or dependency.

    Returns:
        JSONResponse with RFC 7807 ProblemDetails.

    Example:
        >>> # When auth dependency raises HTTPException:
        >>> raise HTTPException(status_code=401, detail="Invalid token")
        >>> # Returns RFC 7807 response:
        >>> # {
        >>> #   "type": "https://api.dashtam.com/errors/unauthorized",
        >>> #   "title": "Authentication Required",
        >>> #   "status": 401,
        >>> #   "detail": "Invalid token",
        >>> #   "instance": "/api/v1/accounts",
        >>> #   "trace_id": "..."
        >>> # }
    """
    # Type narrowing: FastAPI registers this handler only for HTTPException
    assert isinstance(exc, HTTPException)

    # Extract trace_id from request state (set by TraceMiddleware)
    trace_id = getattr(request.state, "trace_id", None)

    # Derive error type slug from status code
    error_slug = _get_error_slug(exc.status_code)
    title = _HTTP_STATUS_TITLES.get(exc.status_code, "Error")

    # Build RFC 7807 Problem Details
    problem = ProblemDetails(
        type=f"{settings.api_base_url}/errors/{error_slug}",
        title=title,
        status=exc.status_code,
        detail=exc.detail if isinstance(exc.detail, str) else str(exc.detail),
        instance=str(request.url.path),
        errors=None,
        trace_id=trace_id,
    )

    # Preserve any headers from HTTPException (e.g., WWW-Authenticate)
    headers = getattr(exc, "headers", None)

    return JSONResponse(
        status_code=exc.status_code,
        content=problem.model_dump(exclude_none=True),
        headers=headers,
    )


async def validation_exception_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    """Convert RequestValidationError to RFC 7807 Problem Details response.

    This handler ensures Pydantic validation errors are returned in RFC 7807
    format with structured field-level errors.

    Args:
        request: FastAPI Request object.
        exc: RequestValidationError from Pydantic validation.

    Returns:
        JSONResponse with RFC 7807 ProblemDetails including field errors.

    Example:
        >>> # When Pydantic validation fails:
        >>> # POST /api/v1/users with invalid email
        >>> # Returns RFC 7807 response:
        >>> # {
        >>> #   "type": "https://api.dashtam.com/errors/validation-failed",
        >>> #   "title": "Validation Failed",
        >>> #   "status": 422,
        >>> #   "detail": "Request validation failed",
        >>> #   "instance": "/api/v1/users",
        >>> #   "errors": [
        >>> #     {"field": "email", "code": "value_error", "message": "Invalid email"}
        >>> #   ],
        >>> #   "trace_id": "..."
        >>> # }
    """
    # Type narrowing: FastAPI registers this handler only for RequestValidationError
    assert isinstance(exc, RequestValidationError)

    # Extract trace_id from request state (set by TraceMiddleware)
    trace_id = getattr(request.state, "trace_id", None)

    # Convert Pydantic errors to RFC 7807 field errors
    field_errors: list[ErrorDetail] = []
    for error in exc.errors():
        # Extract field path (e.g., ["body", "email"] -> "email")
        loc = error.get("loc", [])
        # Skip "body" prefix if present
        field_parts = [str(p) for p in loc if p != "body"]
        field_name = ".".join(field_parts) if field_parts else "unknown"

        field_errors.append(
            ErrorDetail(
                field=field_name,
                code=error.get("type", "validation_error"),
                message=error.get("msg", "Validation failed"),
            )
        )

    # Build RFC 7807 Problem Details
    problem = ProblemDetails(
        type=f"{settings.api_base_url}/errors/validation-failed",
        title="Validation Failed",
        status=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail="Request validation failed. Check 'errors' for details.",
        instance=str(request.url.path),
        errors=field_errors if field_errors else None,
        trace_id=trace_id,
    )

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=problem.model_dump(exclude_none=True),
    )


def _get_error_slug(status_code: int) -> str:
    """Get error slug for RFC 7807 type URL from HTTP status code.

    Args:
        status_code: HTTP status code.

    Returns:
        Kebab-case error slug for URL.
    """
    slug_map: dict[int, str] = {
        400: "bad-request",
        401: "unauthorized",
        403: "forbidden",
        404: "not-found",
        405: "method-not-allowed",
        409: "conflict",
        415: "unsupported-media-type",
        422: "validation-failed",
        429: "rate-limit-exceeded",
        500: "internal-server-error",
        502: "bad-gateway",
        503: "service-unavailable",
    }
    return slug_map.get(status_code, "error")


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle unexpected Python exceptions.

    Converts any unhandled exception into RFC 7807 Problem Details response.
    Prevents leaking stack traces or internal details to API consumers.

    Args:
        request: FastAPI Request object
        exc: Unhandled exception

    Returns:
        JSONResponse with RFC 7807 ProblemDetails (500 Internal Server Error)

    Example:
        >>> # When any unhandled exception occurs:
        >>> raise ValueError("Something went wrong")
        >>> # Returns RFC 7807 response with trace_id for debugging
    """
    # Extract trace_id from request state (set by TraceMiddleware)
    trace_id = getattr(request.state, "trace_id", None)

    # Build RFC 7807 Problem Details
    problem = ProblemDetails(
        type=f"{settings.api_base_url}/errors/internal-server-error",
        title="Internal Server Error",
        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="An unexpected error occurred. Please contact support with the trace ID.",
        instance=str(request.url.path),
        errors=None,
        trace_id=trace_id,
    )

    # Log the exception (without exposing to client)
    # TODO: Add structured logging in F0.8+ when logger is available
    # logger.error(
    #     "Unhandled exception",
    #     exc_type=type(exc).__name__,
    #     exc_message=str(exc),
    #     trace_id=trace_id,
    #     request_path=request.url.path,
    #     request_method=request.method,
    # )

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=problem.model_dump(exclude_none=True),
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Register all exception handlers with FastAPI application.

    This function should be called during application initialization
    to register global exception handlers.

    Args:
        app: FastAPI application instance

    Example:
        >>> from fastapi import FastAPI
        >>> app = FastAPI()
        >>> register_exception_handlers(app)
    """
    # Handle HTTPException (auth dependencies, etc.) - convert to RFC 7807
    app.add_exception_handler(HTTPException, http_exception_handler)

    # Handle Pydantic validation errors - convert to RFC 7807 with field errors
    app.add_exception_handler(RequestValidationError, validation_exception_handler)

    # Handle all unhandled exceptions - catch-all for 500 errors
    app.add_exception_handler(Exception, generic_exception_handler)
