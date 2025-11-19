"""Application layer errors.

This package contains error types for the application layer (command/query handlers).

Exports:
    ApplicationError: Application layer error dataclass
    ApplicationErrorCode: Application-level error code enum
"""

from src.application.errors.application_error import (
    ApplicationError,
    ApplicationErrorCode,
)

__all__ = [
    "ApplicationError",
    "ApplicationErrorCode",
]
