"""Result types for railway-oriented programming.

This module implements the Result pattern to handle operations that can fail
without using exceptions. This approach makes error handling explicit and
testable.

Usage:
    def divide(a: float, b: float) -> Result[float, str]:
        if b == 0:
            return Failure("Division by zero")
        return Success(a / b)

    result = divide(10, 2)
    match result:
        case Success(value):
            print(f"Result: {value}")
        case Failure(error):
            print(f"Error: {error}")
"""

from dataclasses import dataclass
from typing import Generic, TypeVar

T = TypeVar("T")  # Success type
E = TypeVar("E")  # Error type


@dataclass(frozen=True, slots=True, kw_only=True)
class Success(Generic[T]):
    """Represents a successful operation result.

    Attributes:
        value: The successful result value.
    """

    value: T


@dataclass(frozen=True, slots=True, kw_only=True)
class Failure(Generic[E]):
    """Represents a failed operation result.

    Attributes:
        error: The error that occurred.
    """

    error: E


# Type alias for Result union
type Result[T, E] = Success[T] | Failure[E]
