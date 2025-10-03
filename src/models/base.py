"""Base model classes for all database models.

This module provides abstract base classes that all database models inherit from.
These base classes include common fields like id, timestamps, and common methods
that are shared across all models in the application.

The base models use SQLModel which combines SQLAlchemy and Pydantic, providing
both database ORM functionality and data validation.

Example:
    >>> from src.models.base import DashtamBase
    >>>
    >>> class User(DashtamBase, table=True):
    >>>     __tablename__ = "users"
    >>>
    >>>     email: str = Field(unique=True, index=True)
    >>>     name: str
"""

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel
from pydantic import ConfigDict


class DashtamBase(SQLModel, table=False):
    """Base model for all Dashtam database models.

    This abstract base class provides common fields and functionality that
    all database models in the application inherit. It includes:
    - UUID primary key
    - Automatic timestamp tracking (created_at, updated_at)
    - Soft delete capability (deleted_at)
    - Common utility methods

    Attributes:
        id: UUID primary key, automatically generated.
        created_at: Timestamp when the record was created.
        updated_at: Timestamp when the record was last updated.
        deleted_at: Timestamp when the record was soft deleted (if applicable).
        is_active: Boolean flag for enabling/disabling records.

    Note:
        This is an abstract base class. Always inherit from it with table=True:
        >>> class MyModel(DashtamBase, table=True):
        >>>     __tablename__ = "my_table"
    """

    # Primary key - UUID for better distribution and security
    id: UUID = Field(
        default_factory=uuid4,
        primary_key=True,
        index=True,
        description="Unique identifier for the record",
    )

    # Timestamps
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp when the record was created",
    )

    updated_at: Optional[datetime] = Field(
        default=None, description="Timestamp when the record was last updated"
    )

    # Soft delete support
    deleted_at: Optional[datetime] = Field(
        default=None, description="Timestamp when the record was soft deleted"
    )

    # Active flag for enabling/disabling records
    is_active: bool = Field(default=True, description="Whether the record is active")

    # Note: All child classes should explicitly define __tablename__
    # Example: __tablename__ = "users"

    def soft_delete(self) -> None:
        """Mark the record as deleted without removing from database.

        Soft delete allows records to be "deleted" while preserving them
        for audit trails, recovery, or historical analysis.

        Example:
            >>> user = await session.get(User, user_id)
            >>> user.soft_delete()
            >>> await session.commit()
        """
        self.deleted_at = datetime.now(timezone.utc)
        self.is_active = False

    def restore(self) -> None:
        """Restore a soft-deleted record.

        Removes the deletion timestamp and reactivates the record.

        Example:
            >>> user = await session.get(User, user_id)
            >>> user.restore()
            >>> await session.commit()
        """
        self.deleted_at = None
        self.is_active = True

    @property
    def is_deleted(self) -> bool:
        """Check if the record has been soft deleted.

        Returns:
            True if the record has been soft deleted, False otherwise.

        Example:
            >>> if user.is_deleted:
            >>>     print("User has been deleted")
        """
        return self.deleted_at is not None

    model_config = ConfigDict(
        from_attributes=True,  # Allow reading from ORM objects (SQLAlchemy)
        use_enum_values=True,  # Use enum values instead of names
        validate_assignment=True,  # Validate field assignments
    )


class TimestampBase(SQLModel, table=False):
    """Base model for entities that only need timestamp tracking.

    A lighter base class for models that need timestamp tracking but not
    all the features of DashtamBase (like soft delete or UUID primary keys).

    Useful for:
    - Log tables
    - Audit tables
    - Simple lookup tables

    Attributes:
        created_at: When the record was created.
        updated_at: When the record was last modified.

    Example:
        >>> class AuditLog(TimestampBase, table=True):
        >>>     __tablename__ = "audit_logs"
        >>>     id: int = Field(primary_key=True)
        >>>     action: str
        >>>     user_id: UUID
    """

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When the record was created",
    )

    updated_at: Optional[datetime] = Field(
        default=None, description="When the record was last modified"
    )

    model_config = ConfigDict(
        from_attributes=True,
        validate_assignment=True,
    )
