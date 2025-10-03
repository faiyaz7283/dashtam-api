"""User model for authentication and provider ownership.

This module defines the User model which represents application users
who can connect multiple financial providers.
"""

from datetime import datetime, timezone
from typing import Optional, List, TYPE_CHECKING

from sqlmodel import Field, Relationship, Column
from sqlalchemy import String, DateTime
from pydantic import field_validator

from src.models.base import DashtamBase

if TYPE_CHECKING:
    from src.models.provider import Provider


class User(DashtamBase, table=True):
    """Application user model.

    Represents a user who can connect and manage multiple financial
    provider instances. For now, this is a simplified model without
    authentication details (can be extended later).

    Attributes:
        email: User's email address (unique).
        name: User's full name.
        is_verified: Whether email is verified.
        last_login: Last login timestamp.
        providers: List of provider instances owned by user.
    """

    __tablename__ = "users"

    email: str = Field(
        sa_column=Column(String(255), unique=True, index=True),
        description="User's email address",
    )

    name: str = Field(description="User's full name")

    is_verified: bool = Field(default=False, description="Whether email is verified")

    last_login: Optional[datetime] = Field(
        default=None,
        sa_type=DateTime(timezone=True),
        description="Last login timestamp",
    )

    # Relationships
    providers: List["Provider"] = Relationship(
        back_populates="user", cascade_delete=True
    )

    # Validators to ensure timezone awareness
    @field_validator("last_login", mode="before")
    @classmethod
    def ensure_timezone_aware(cls, v: Optional[datetime]) -> Optional[datetime]:
        """Ensure datetime fields are timezone-aware (UTC)."""
        if v is None:
            return None
        if v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v.astimezone(timezone.utc)

    @property
    def active_providers_count(self) -> int:
        """Count of active provider connections."""
        if not self.providers:
            return 0
        return sum(1 for p in self.providers if p.is_connected)

    @property
    def display_name(self) -> str:
        """Get display name (name or email)."""
        return self.name or self.email.split("@")[0]
