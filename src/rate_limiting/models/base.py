"""Database-agnostic audit log model.

This module defines the abstract structure for rate limit audit logs.
Apps implement their own database-specific versions based on this structure.

Architecture:
    - Database Agnostic: No dependency on PostgreSQL, MySQL, or any specific database
    - Interface Definition: Defines required fields for any audit backend
    - Portability: Enables rate limiting package to work with any database
    - Extensibility: Apps create their own implementations (PostgreSQL, MySQL, SQLite)

Usage:
    Rate limiting package depends only on this abstract structure.
    Apps create concrete implementations for their chosen database.

Example (PostgreSQL):
    >>> from src.rate_limiting.models.postgresql import RateLimitAuditLog
    >>> log = RateLimitAuditLog(
    ...     ip_address="192.168.1.1",
    ...     endpoint="POST /api/v1/auth/login",
    ...     identifier="user:abc-123",
    ...     rule_name="auth_login",
    ...     limit=5,
    ...     window_seconds=60,
    ...     violation_count=1
    ... )

Example (MySQL - in another app):
    >>> from my_app.models import MySQLRateLimitAuditLog  # Their implementation
    >>> log = MySQLRateLimitAuditLog(
    ...     ip_address="10.0.0.1",  # VARCHAR(45) in MySQL
    ...     endpoint="GET /api/users",
    ...     identifier="tenant:456",
    ...     # ... same interface, different database ...
    ... )
"""

from abc import ABC
from datetime import datetime
from typing import Optional
from uuid import UUID


class RateLimitAuditLogBase(ABC):
    """Abstract base model for rate limit audit logs.

    This defines the REQUIRED fields for any audit backend implementation.
    Apps create their own database-specific implementations following this structure.

    Required Fields:
        id: Primary key (UUID recommended for distributed systems)
        ip_address: Client IP address
            - Storage format depends on database (INET, VARCHAR, etc.)
            - Must handle both IPv4 and IPv6
        endpoint: Rate limit endpoint key (e.g., "POST /api/v1/auth/login")
        rule_name: Which rate limit rule was violated
        limit: Maximum requests allowed in time window
        window_seconds: Time window in seconds
        violation_count: How many requests over the limit
        timestamp: When the violation occurred (timezone-aware UTC)
        created_at: When the audit record was created (timezone-aware UTC)

    Optional Fields:
        identifier: App-defined user/tenant/session tracking
            - Format is application-specific
            - Examples: "user:uuid", "tenant:123", "session:abc", None
            - Enables flexible tracking without forcing schema dependencies

    Design Principles:
        - No Foreign Keys: Audit logs are immutable and independent
        - Denormalized: Store what you need, don't rely on joins
        - Timezone-Aware: All timestamps in UTC
        - Portable: Works with any database backend

    Example Implementation (PostgreSQL):
        ```python
        from sqlmodel import Field, SQLModel, Column
        from sqlalchemy.dialects.postgresql import INET

        class RateLimitAuditLog(SQLModel, table=True):
            __tablename__ = "rate_limit_audit_logs"

            id: UUID = Field(default_factory=uuid4, primary_key=True)
            ip_address: str = Field(sa_column=Column(INET))  # PostgreSQL native
            endpoint: str = Field(...)
            rule_name: str = Field(...)
            limit: int = Field(...)
            window_seconds: int = Field(...)
            violation_count: int = Field(default=1)
            identifier: Optional[str] = Field(default=None)
            timestamp: datetime = Field(...)
            created_at: datetime = Field(...)
        ```

    Example Implementation (MySQL):
        ```python
        class MySQLRateLimitAuditLog(SQLModel, table=True):
            __tablename__ = "rate_limit_audit_logs"

            id: UUID = Field(default_factory=uuid4, primary_key=True)
            ip_address: str = Field(sa_column=Column(String(45)))  # VARCHAR
            # ... rest same as PostgreSQL ...
        ```
    """

    # Required fields (abstract - apps implement with database-specific types)
    id: UUID
    ip_address: str  # Format depends on database (INET, VARCHAR, etc.)
    endpoint: str
    rule_name: str
    limit: int
    window_seconds: int
    violation_count: int
    timestamp: datetime  # Must be timezone-aware (UTC)
    created_at: datetime  # Must be timezone-aware (UTC)

    # Optional fields
    identifier: Optional[str] = (
        None  # App-defined tracking (user, tenant, session, etc.)
    )
