"""RFC 7807 error response schemas and exception handlers.

This package contains RFC 7807 (Problem Details for HTTP APIs) Pydantic models,
error response builders, and global exception handlers for the presentation layer.

Exports:
    ErrorDetail: Individual field-specific error
    ProblemDetails: RFC 7807 compliant error response schema
    ErrorResponseBuilder: Utility for building RFC 7807 responses
    register_exception_handlers: Register global exception handlers with FastAPI
"""

from src.presentation.routers.api.v1.errors.error_response_builder import (
    ErrorResponseBuilder,
)
from src.presentation.routers.api.v1.errors.exception_handlers import (
    register_exception_handlers,
)
from src.presentation.routers.api.v1.errors.problem_details import (
    ErrorDetail,
    ProblemDetails,
)

__all__ = [
    "ErrorDetail",
    "ErrorResponseBuilder",
    "ProblemDetails",
    "register_exception_handlers",
]
