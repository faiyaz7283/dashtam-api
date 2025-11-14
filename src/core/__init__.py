"""Core shared kernel.

This module provides foundational utilities used across all architectural layers:
- Result types for railway-oriented programming
- Base error classes for domain-level error handling
- Validation framework for input validation

The core module has NO dependencies on other application layers.
"""

from src.core.errors import DomainError, ValidationError
from src.core.enums import ErrorCode
from src.core.result import Failure, Result, Success

__all__ = [
    "DomainError",
    "ErrorCode",
    "Failure",
    "Result",
    "Success",
    "ValidationError",
]
