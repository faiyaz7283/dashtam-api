"""Database persistence infrastructure.

This module provides database-related functionality including:
- Base model for all database entities
- Database connection and session management
- Repository implementations (added in later features)
"""

from src.infrastructure.persistence.base import BaseModel
from src.infrastructure.persistence.database import Database

__all__ = [
    "BaseModel",
    "Database",
]
