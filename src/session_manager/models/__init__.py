"""Session manager domain models.

Exports:
    - SessionBase: Abstract interface for session models
    - SessionFilters: Dataclass for filtering session queries
"""

from .base import SessionBase
from .filters import SessionFilters

__all__ = ["SessionBase", "SessionFilters"]
