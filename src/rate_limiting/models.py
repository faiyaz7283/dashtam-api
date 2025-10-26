"""Rate Limiting Data Models (DEPRECATED).

DEPRECATION NOTICE:
    This module is deprecated. The concrete RateLimitAuditLog model
    has been moved to src/models/rate_limit_audit.py (Dashtam's implementation).
    
    Rate limiting package now only provides the abstract interface.
    Apps implement their own database-specific models.

Migration Path:
    OLD: from src.rate_limiting.models import RateLimitAuditLog
    NEW: from src.models.rate_limit_audit import RateLimitAuditLog

Architecture Change:
    - Rate limiting package: Only provides abstract interface
    - Dashtam app: Implements PostgreSQL + SQLModel version
    - Other apps: Can implement MySQL, MongoDB, etc.
"""

import warnings

warnings.warn(
    "src.rate_limiting.models is deprecated. "
    "Import from src.models.rate_limit_audit instead.",
    DeprecationWarning,
    stacklevel=2,
)

# Re-export for backward compatibility (temporary)
from src.models.rate_limit_audit import RateLimitAuditLog  # noqa: F401

__all__ = ["RateLimitAuditLog"]

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel, Column
from sqlalchemy import String, DateTime, Integer
from pydantic import ConfigDict, field_validator


class RateLimitAuditLog(SQLModel, table=True):
    """Audit log for rate limit violations.

    Records all rate limit enforcement events for security analysis,
    monitoring, and compliance.

    Attributes:
        id: Unique identifier for audit log entry
        timestamp: When the rate limit violation occurred (UTC)
        user_id: User who triggered the rate limit (if authenticated)
        ip_address: Client IP address
        endpoint: API endpoint that was rate limited
        rule_name: Name of the rate limit rule that was violated
        limit: Maximum requests allowed
        window_seconds: Time window for the limit
        violation_count: How many requests over the limit
        created_at: When this audit entry was created

    Constraints:
        - Immutable: No updates or deletes allowed
        - Required fields: timestamp, ip_address, endpoint, rule_name
        - Optional user_id: Not all requests are authenticated
        - created_at: Auto-populated on insert

    Example:
        >>> log = RateLimitAuditLog(
        ...     ip_address="192.168.1.1",
        ...     endpoint="/api/v1/auth/login",
        ...     rule_name="auth_login",
        ...     limit=5,
        ...     window_seconds=60,
        ...     violation_count=1
        ... )
    """

    __tablename__ = "rate_limit_audit_logs"

    id: UUID = Field(
        default_factory=uuid4,
        primary_key=True,
        index=True,
        description="Unique identifier for the audit log entry",
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_type=DateTime(timezone=True),
        nullable=False,
        index=True,
        description="When the rate limit violation occurred",
    )
    user_id: Optional[UUID] = Field(
        default=None,
        foreign_key="users.id",
        nullable=True,
        index=True,
        ondelete="CASCADE",
        description="ID of user who triggered the rate limit (if authenticated)",
    )
    ip_address: str = Field(
        sa_column=Column(String(45), nullable=False, index=True),
        description="Client IP address (IPv4 or IPv6)",
    )
    endpoint: str = Field(
        sa_column=Column(String(255), nullable=False, index=True),
        description="API endpoint that was rate limited",
    )
    rule_name: str = Field(
        sa_column=Column(String(100), nullable=False),
        description="Name of the rate limit rule that was violated",
    )
    limit: int = Field(
        sa_column=Column(Integer, nullable=False),
        description="Maximum requests allowed",
    )
    window_seconds: int = Field(
        sa_column=Column(Integer, nullable=False),
        description="Time window for the limit (in seconds)",
    )
    violation_count: int = Field(
        default=1,
        sa_column=Column(Integer, nullable=False),
        description="How many requests over the limit",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_type=DateTime(timezone=True),
        nullable=False,
        description="When this audit entry was created",
    )

    # Validators to ensure timezone awareness
    @field_validator("timestamp", "created_at", mode="before")
    @classmethod
    def ensure_timezone_aware(cls, v: Optional[datetime]) -> Optional[datetime]:
        """Ensure datetime fields are timezone-aware (UTC).
        
        Args:
            v: Datetime value to validate.
        
        Returns:
            Timezone-aware datetime in UTC.
        """
        if v is None:
            return None
        if v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v.astimezone(timezone.utc)

    model_config = ConfigDict(
        from_attributes=True,
        validate_assignment=True,
    )
