"""Base model and mixins for all database entities.

This module provides:
- BaseModel: Base class for ALL models (provides id, created_at)
- TimestampMixin: Internal mixin that adds updated_at
- BaseMutableModel: Recommended base for mutable models (combines above)

Following hexagonal architecture:
- This is an infrastructure concern (database implementation detail)
- Domain entities should NOT inherit from this
- Domain entities are mapped to/from database models

Usage:
    # For mutable models (can be updated) - RECOMMENDED
    class UserModel(BaseMutableModel):
        __tablename__ = "users"
        email: Mapped[str]
        # Has: id, created_at, updated_at

    # For immutable models (cannot be updated)
    class AuditLogModel(BaseModel):
        __tablename__ = "audit_logs"
        action: Mapped[str]
        # Has: id, created_at (no updated_at)

Architecture:
    BaseModel (id, created_at)
        ↑
        ├── BaseMutableModel (+ updated_at via TimestampMixin)
        │   ├── UserModel
        │   └── ProviderModel
        │
        └── AuditLogModel (immutable, no updated_at)

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
    """Base class for all database models (mutable and immutable).

    Provides common fields that ALL database models need:
    - id: UUID primary key (auto-generated)
    - created_at: Timestamp when record was created (UTC)

    For mutable models, also inherit from TimestampMixin to get updated_at.

    Example:
        # Mutable model (can be updated)
        class UserModel(TimestampMixin, BaseModel):
            __tablename__ = "users"
            email: Mapped[str]
            # Has: id, created_at, updated_at

        # Immutable model (cannot be updated)
        class AuditLogModel(BaseModel):
            __tablename__ = "audit_logs"
            action: Mapped[str]
            # Has: id, created_at (no updated_at)

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

    # Timestamp for creation (all models have this)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),  # Database sets this on INSERT
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

        Note:
            Mutable models that use TimestampMixin will have updated_at
            added to the dictionary via the mixin's to_dict() extension.
        """
        return {
            "id": str(self.id),
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class TimestampMixin:
    """Mixin for mutable models that track updates.

    Adds updated_at field that automatically updates on record modification.

    Note:
        This is typically used via BaseMutableModel, not directly.
        Use BaseMutableModel instead of mixing TimestampMixin + BaseModel manually.

    Direct usage (advanced):
        class CustomModel(TimestampMixin, SomeOtherMixin, BaseModel):
            __tablename__ = "custom"
            # Order matters for MRO!

    Recommended usage:
        Use BaseMutableModel instead (see below).
    """

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),  # Database sets this on INSERT
        onupdate=func.now(),  # Database automatically updates this on UPDATE
    )

    def to_dict(self) -> dict[str, Any]:
        """Extend BaseModel.to_dict() to include updated_at.

        Returns:
            dict: Dictionary representation including updated_at.

        Note:
            This method extends the base to_dict() method using Python's
            MRO (Method Resolution Order). It calls super().to_dict() to
            get id and created_at, then adds updated_at.
        """
        # Get base fields (id, created_at) from BaseModel
        data: dict[str, Any] = super().to_dict()  # type: ignore[misc]
        # Add updated_at from this mixin
        data["updated_at"] = self.updated_at.isoformat() if self.updated_at else None
        return data


class BaseMutableModel(TimestampMixin, BaseModel):
    """Base class for mutable database models.

    Combines TimestampMixin + BaseModel with proper MRO (Method Resolution Order).
    Use this for any model that can be modified after creation.

    Provides:
        - id: UUID primary key (from BaseModel)
        - created_at: Timestamp when created (from BaseModel)
        - updated_at: Timestamp when last updated (from TimestampMixin)

    Usage:
        class UserModel(BaseMutableModel):
            __tablename__ = "users"
            email: Mapped[str]
            password_hash: Mapped[str]
            # Has: id, created_at, updated_at

        class ProviderModel(BaseMutableModel):
            __tablename__ = "providers"
            name: Mapped[str]
            # Has: id, created_at, updated_at

    When NOT to use:
        For immutable models (like audit logs), use BaseModel directly:

        class AuditLogModel(BaseModel):  # No updated_at
            __tablename__ = "audit_logs"
            action: Mapped[str]
            # Has: id, created_at (no updated_at)

    Benefits:
        - No need to remember mixin order (handled here)
        - Single source of truth for MRO
        - Explicit intent ("this model is mutable")
        - Easy to extend with more mixins in the future

    Future Extension Example:
        # Add more mixins here in correct order
        class BaseMutableModel(SoftDeleteMixin, TimestampMixin, BaseModel):
            # All mutable models get soft-delete + timestamps
            pass
    """

    __abstract__ = True
