"""Domain entities for business logic.

Pure business logic entities with no framework dependencies.
"""

from src.domain.entities.session import Session
from src.domain.entities.user import User

__all__ = ["Session", "User"]
