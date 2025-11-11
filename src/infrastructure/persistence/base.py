"""Base model for all database entities.

This module provides the base SQLAlchemy model that all database models
will inherit from. It includes common fields like UUID primary key and
timestamps (created_at, updated_at).

Following hexagonal architecture:
- This is an infrastructure concern (database implementation detail)
- Domain entities should NOT inherit from this
- Domain entities are mapped to/from database models

Note: While we use PostgreSQL for Dashtam, we keep the base model
reasonably database-agnostic by using SQLAlchemy's Uuid type which
works across different databases.
"""

from datetime import datetime
from typing import Any
from uuid import UUID as PythonUUID, uuid4

from sqlalchemy import DateTime, Uuid, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class BaseModel(DeclarativeBase):
    """Base class for all database models.

    Provides common fields that all database models need:
    - id: UUID primary key (auto-generated)
    - created_at: Timestamp when record was created (UTC)
    - updated_at: Timestamp when record was last updated (UTC)

    This is an infrastructure concern - domain entities should not
    inherit from or depend on this class.
    """

    __abstract__ = True

    # Every model gets a UUID primary key
    id: Mapped[PythonUUID] = mapped_column(
        Uuid,  # SQLAlchemy's generic UUID type
        primary_key=True,
        default=uuid4,
        nullable=False,
    )

    # Timestamps for audit trail
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),  # Database sets this on INSERT
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),  # Database sets this on INSERT
        onupdate=func.now(),  # Database updates this on UPDATE
    )

    def __repr__(self) -> str:
        """String representation for debugging.

        Returns:
            str: String showing class name and ID.
        """
        return f"<{self.__class__.__name__}(id={self.id})>"

    def to_dict(self) -> dict[str, Any]:
        """Convert model to dictionary (for debugging/logging).

        Returns:
            dict: Dictionary representation of the model.
        """
        return {
            "id": str(self.id),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
