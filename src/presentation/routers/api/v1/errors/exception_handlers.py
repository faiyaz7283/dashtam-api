"""Global exception handlers for FastAPI application.

This module provides exception handlers that catch unhandled exceptions
and convert them to RFC 9457 Problem Details responses.

Handlers:
    http_exception_handler: Converts HTTPException to RFC 9457 format
    validation_exception_handler: Converts RequestValidationError to RFC 9457 format
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


# HTTP status code to (title, slug) mapping for RFC 9457
# Consolidated to avoid maintaining two separate dicts
_HTTP_STATUS_INFO: dict[int, tuple[str, str]] = {
    400: ("Bad Request", "bad-request"),
    401: ("Authentication Required", "unauthorized"),
    403: ("Access Denied", "forbidden"),
    404: ("Resource Not Found", "not-found"),
    405: ("Method Not Allowed", "method-not-allowed"),
    409: ("Resource Conflict", "conflict"),
    415: ("Unsupported Media Type", "unsupported-media-type"),
    422: ("Validation Failed", "validation-failed"),
    429: ("Too Many Requests", "rate-limit-exceeded"),
    500: ("Internal Server Error", "internal-server-error"),
    502: ("Bad Gateway", "bad-gateway"),
    503: ("Service Unavailable", "service-unavailable"),
}


def _get_status_title(status_code: int) -> str:
    """Get human-readable title for HTTP status code."""
    return _HTTP_STATUS_INFO.get(status_code, ("Error", "error"))[0]


def _get_error_slug(status_code: int) -> str:
    """Get kebab-case error slug for RFC 9457 type URL."""
    return _HTTP_STATUS_INFO.get(status_code, ("Error", "error"))[1]


async def http_exception_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    """Convert HTTPException to RFC 9457 Problem Details response.

    This handler ensures all HTTPException responses (e.g., from auth dependencies)
    are returned in RFC 9457 format for consistency.

    Args:
        request: FastAPI Request object.
        exc: HTTPException raised by handler or dependency.

    Returns:
        JSONResponse with RFC 9457 ProblemDetails.

    Example:
        >>> # When auth dependency raises HTTPException:
        >>> raise HTTPException(status_code=401, detail="Invalid token")
        >>> # Returns RFC 9457 response:
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

    # Derive error type slug and title from status code
    error_slug = _get_error_slug(exc.status_code)
    title = _get_status_title(exc.status_code)

    # Build RFC 9457 Problem Details
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
    """Convert RequestValidationError to RFC 9457 Problem Details response.

    This handler ensures Pydantic validation errors are returned in RFC 9457
    format with structured field-level errors.

    Args:
        request: FastAPI Request object.
        exc: RequestValidationError from Pydantic validation.

    Returns:
        JSONResponse with RFC 9457 ProblemDetails including field errors.

    Example:
        >>> # When Pydantic validation fails:
        >>> # POST /api/v1/users with invalid email
        >>> # Returns RFC 9457 response:
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

    # Convert Pydantic errors to RFC 9457 field errors
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

    # Build RFC 9457 Problem Details
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


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle unexpected Python exceptions.

    Converts any unhandled exception into RFC 9457 Problem Details response.
    Prevents leaking stack traces or internal details to API consumers.

    Args:
        request: FastAPI Request object
        exc: Unhandled exception

    Returns:
        JSONResponse with RFC 9457 ProblemDetails (500 Internal Server Error)

    Example:
        >>> # When any unhandled exception occurs:
        >>> raise ValueError("Something went wrong")
        >>> # Returns RFC 9457 response with trace_id for debugging
    """
    # Extract trace_id from request state (set by TraceMiddleware)
    trace_id = getattr(request.state, "trace_id", None)

    # Build RFC 9457 Problem Details
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
    # Handle HTTPException (auth dependencies, etc.) - convert to RFC 9457
    app.add_exception_handler(HTTPException, http_exception_handler)

    # Handle Pydantic validation errors - convert to RFC 9457 with field errors
    app.add_exception_handler(RequestValidationError, validation_exception_handler)

    # Handle all unhandled exceptions - catch-all for 500 errors
    app.add_exception_handler(Exception, generic_exception_handler)
