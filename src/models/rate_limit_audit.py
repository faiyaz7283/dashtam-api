"""Rate Limit Audit Log Model (Dashtam's PostgreSQL Implementation).

This module provides Dashtam's implementation of the rate limiting audit log
using PostgreSQL's native INET type and SQLModel ORM.

Architecture:
    - Implements RateLimitAuditLogBase interface from rate limiting package
    - Uses PostgreSQL-specific features (INET, TIMESTAMPTZ)
    - Managed by Dashtam's Alembic migrations
    - No coupling to rate limiting package internals

Design Decisions:
    - PostgreSQL INET: Native IP validation, efficient storage (4-16 bytes)
    - No Foreign Keys: Audit logs are immutable and independent
    - Optional Identifier: Flexible user/tenant/session tracking
    - SQLModel: Matches Dashtam's ORM choice
    - Alembic: Managed by Dashtam's migration system

Usage:
    This is Dashtam's implementation choice. Rate limiting package
    accepts any model that implements the RateLimitAuditLogBase interface.

Example:
    >>> from src.models.rate_limit_audit import RateLimitAuditLog
    >>> log = RateLimitAuditLog(
    ...     ip_address="192.168.1.1",
    ...     endpoint="POST /api/v1/auth/login",
    ...     identifier="user:abc-123-def-456",
    ...     rule_name="auth_login",
    ...     limit=5,
    ...     window_seconds=60,
    ...     violation_count=1
    ... )
"""

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel, Column
from sqlalchemy import String, DateTime, Integer
from sqlalchemy.dialects.postgresql import INET
from pydantic import ConfigDict, field_validator


class RateLimitAuditLog(SQLModel, table=True):
    """PostgreSQL audit log for rate limit violations.

    Dashtam's implementation using PostgreSQL INET and SQLModel.
    Implements the RateLimitAuditLogBase interface from rate limiting package.

    PostgreSQL Features:
        - INET type: Native IP address storage (IPv4/IPv6)
        - TIMESTAMPTZ: Timezone-aware timestamps
        - Efficient indexes: IP ranges, time-based queries

    Attributes:
        id: Unique identifier (UUID)
        ip_address: Client IP (PostgreSQL INET type)
        endpoint: Rate limit endpoint key (e.g., "POST /api/v1/auth/login")
        rule_name: Rule that was violated (e.g., "auth_login")
        limit: Maximum requests allowed
        window_seconds: Time window in seconds
        violation_count: How many requests exceeded limit
        identifier: Optional Dashtam-specific tracking
            - Format: "user:{uuid}" for authenticated users
            - Format: None for anonymous requests (e.g., login attempts)
            - Future: "tenant:{id}", "session:{id}", etc.
        timestamp: When violation occurred (UTC)
        created_at: When audit entry created (UTC)

    Indexes:
        - id (primary key)
        - timestamp (time-based queries, retention policies)
        - ip_address (security analysis, IP blocking)
        - endpoint (query violations by endpoint)
        - identifier (user/tenant tracking)

    Examples:
        # Anonymous request (login attempt)
        >>> log = RateLimitAuditLog(
        ...     ip_address="192.168.1.1",
        ...     endpoint="POST /api/v1/auth/login",
        ...     identifier=None,  # No user yet
        ...     rule_name="auth_login",
        ...     limit=5,
        ...     window_seconds=60,
        ...     violation_count=1
        ... )

        # Authenticated request (API call)
        >>> log = RateLimitAuditLog(
        ...     ip_address="10.0.0.5",
        ...     endpoint="GET /api/v1/providers",
        ...     identifier="user:abc-123-def-456",  # Dashtam format
        ...     rule_name="api_user",
        ...     limit=100,
        ...     window_seconds=60,
        ...     violation_count=1
        ... )

    Security Queries:
        # Find all violations from IP
        >>> logs = session.exec(
        ...     select(RateLimitAuditLog)
        ...     .where(RateLimitAuditLog.ip_address == "192.168.1.1")
        ... ).all()

        # Find violations from subnet (PostgreSQL INET operator)
        >>> logs = session.exec(
        ...     select(RateLimitAuditLog)
        ...     .where(RateLimitAuditLog.ip_address.op("<<")("192.168.0.0/16"))
        ... ).all()

        # Find violations by user
        >>> logs = session.exec(
        ...     select(RateLimitAuditLog)
        ...     .where(RateLimitAuditLog.identifier.like("user:%"))
        ... ).all()

        # Find recent violations
        >>> from datetime import timedelta
        >>> cutoff = datetime.now(timezone.utc) - timedelta(hours=1)
        >>> logs = session.exec(
        ...     select(RateLimitAuditLog)
        ...     .where(RateLimitAuditLog.timestamp >= cutoff)
        ... ).all()
    """

    __tablename__ = "rate_limit_audit_logs"

    id: UUID = Field(
        default_factory=uuid4,
        primary_key=True,
        index=True,
        description="Unique identifier for audit log entry",
    )

    # PostgreSQL INET type (native IP handling)
    ip_address: str = Field(
        sa_column=Column(INET, nullable=False, index=True),
        description="Client IP address (PostgreSQL INET - IPv4/IPv6 native)",
    )

    endpoint: str = Field(
        sa_column=Column(String(255), nullable=False, index=True),
        description="Rate limit endpoint key",
    )

    rule_name: str = Field(
        sa_column=Column(String(100), nullable=False),
        description="Name of rate limit rule violated",
    )

    limit: int = Field(
        sa_column=Column(Integer, nullable=False),
        description="Maximum requests allowed in time window",
    )

    window_seconds: int = Field(
        sa_column=Column(Integer, nullable=False),
        description="Time window in seconds",
    )

    violation_count: int = Field(
        default=1,
        sa_column=Column(Integer, nullable=False),
        description="How many requests exceeded the limit",
    )

    # Optional: Dashtam-specific identifier
    identifier: Optional[str] = Field(
        default=None,
        sa_column=Column(String(255), nullable=True, index=True),
        description="Dashtam's tracking format: 'user:{uuid}', or None for anonymous",
    )

    # Timestamps (timezone-aware TIMESTAMPTZ)
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_type=DateTime(timezone=True),
        nullable=False,
        index=True,
        description="When rate limit violation occurred",
    )

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_type=DateTime(timezone=True),
        nullable=False,
        description="When audit entry was created",
    )

    # Validators (timezone enforcement)
    @field_validator("timestamp", "created_at", mode="before")
    @classmethod
    def ensure_timezone_aware(cls, v: Optional[datetime]) -> Optional[datetime]:
        """Ensure datetime fields are timezone-aware (UTC).

        Args:
            v: Datetime value to validate.

        Returns:
            Timezone-aware datetime in UTC.

        Raises:
            ValueError: If datetime cannot be made timezone-aware.
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
