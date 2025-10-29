"""Global security configuration model.

This module defines the SecurityConfig singleton model which stores
system-wide security parameters, including global token version for
emergency rotation scenarios.
"""

from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, Column
from sqlalchemy import String, Integer, DateTime, Text
from pydantic import field_validator

from src.models.base import DashtamBase


class SecurityConfig(DashtamBase, table=True):
    """Global security configuration singleton.

    Stores system-wide security settings including the global minimum
    token version for emergency rotation scenarios (e.g., encryption
    key compromise, database breach).

    This table should contain exactly one row at all times.

    Attributes:
        global_min_token_version: Minimum token version accepted globally.
        updated_at: When global version was last updated.
        updated_by: Who initiated the global rotation (admin identifier).
        reason: Why global rotation was performed (audit trail).
    """

    __tablename__ = "security_config"

    global_min_token_version: int = Field(
        default=1,
        sa_column=Column(Integer, nullable=False),
        description="Minimum token version accepted globally",
    )
    updated_at: datetime = Field(
        sa_type=DateTime(timezone=True),
        nullable=False,
        description="When global version was last updated",
    )
    updated_by: Optional[str] = Field(
        default=None,
        sa_column=Column(String(255), nullable=True),
        description="Who initiated the global rotation",
    )
    reason: Optional[str] = Field(
        default=None,
        sa_column=Column(Text, nullable=True),
        description="Why global rotation was performed",
    )

    @field_validator("updated_at", mode="before")
    @classmethod
    def ensure_timezone_aware(cls, v: Optional[datetime]) -> Optional[datetime]:
        """Ensure datetime fields are timezone-aware (UTC)."""
        if v is None:
            return None
        if v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v.astimezone(timezone.utc)
