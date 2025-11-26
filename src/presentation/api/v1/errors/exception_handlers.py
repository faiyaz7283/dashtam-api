"""Global exception handlers for FastAPI application.

This module provides exception handlers that catch unhandled exceptions
and convert them to RFC 7807 Problem Details responses.

Exports:
    register_exception_handlers: Register all exception handlers with FastAPI app
"""

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from src.core.config import settings
from src.presentation.api.v1.errors.problem_details import ProblemDetails


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
    # Handle all unhandled exceptions
    app.add_exception_handler(Exception, generic_exception_handler)

    # Future: Add specific exception handlers
    # app.add_exception_handler(ValueError, value_error_handler)
    # app.add_exception_handler(RequestValidationError, validation_error_handler)
