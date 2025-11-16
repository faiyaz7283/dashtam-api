"""Core enums package.

Exports all core-level enums for convenient importing.

Usage:
    from src.core.enums import ErrorCode, Environment
"""

from src.core.enums.environment import Environment
from src.core.enums.error_code import ErrorCode

__all__ = ["ErrorCode", "Environment"]
