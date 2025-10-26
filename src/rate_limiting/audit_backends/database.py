"""Database Audit Backend for Rate Limiting.

This module implements database-agnostic audit logging for rate limit violations.
Apps provide their own model class (PostgreSQL, MySQL, SQLite, etc.).

Architecture:
    - Database Agnostic: Accepts any SQLModel/SQLAlchemy model class
    - Implements AuditBackend interface (Strategy Pattern)
    - Uses async operations for non-blocking database writes
    - Fail-open design: Audit failures don't block requests
    - Structured logging for observability

Example Usage (Dashtam - PostgreSQL):
    >>> from sqlalchemy.ext.asyncio import AsyncSession
    >>> from src.models.rate_limit_audit import RateLimitAuditLog
    >>> from src.rate_limiting.audit_backends.database import DatabaseAuditBackend
    >>>
    >>> backend = DatabaseAuditBackend(db_session, RateLimitAuditLog)
    >>> await backend.log_violation(
    ...     ip_address="192.168.1.1",
    ...     endpoint="/api/v1/auth/login",
    ...     rule_name="auth_login",
    ...     limit=5,
    ...     window_seconds=60,
    ...     violation_count=1,
    ...     identifier="user:abc-123"  # Optional app-defined tracking
    ... )

Example Usage (Other App - MySQL):
    >>> from my_app.models import MySQLRateLimitAuditLog  # Their implementation
    >>> backend = DatabaseAuditBackend(db_session, MySQLRateLimitAuditLog)
    >>> await backend.log_violation(...)  # Same interface, different database
"""

import logging
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.rate_limiting.audit_backends.base import AuditBackend

logger = logging.getLogger(__name__)


class DatabaseAuditBackend(AuditBackend):
    """Database-agnostic audit backend for rate limit violations.

    Accepts any model class that implements the RateLimitAuditLogBase interface.
    Apps provide their own database-specific implementation (PostgreSQL, MySQL, etc.).

    Design:
        - Database Agnostic: Works with any SQLModel/SQLAlchemy model
        - Fail-open: Database errors are logged but don't block requests
        - Async operations: Non-blocking database writes
        - Structured logging: All operations logged for observability
        - Timezone-aware: All timestamps stored in UTC

    Attributes:
        session: AsyncSession for database operations
        model_class: Model class to use for audit logs (app-provided)

    Example (Dashtam - PostgreSQL):
        >>> from src.models.rate_limit_audit import RateLimitAuditLog
        >>> backend = DatabaseAuditBackend(db_session, RateLimitAuditLog)
        >>> await backend.log_violation(
        ...     ip_address="192.168.1.1",
        ...     endpoint="/api/v1/providers",
        ...     rule_name="provider_list",
        ...     limit=100,
        ...     window_seconds=60,
        ...     violation_count=1,
        ...     identifier="user:abc-123"  # Dashtam's format
        ... )

    Example (Other App - MySQL):
        >>> from my_app.models import MySQLRateLimitAuditLog
        >>> backend = DatabaseAuditBackend(db_session, MySQLRateLimitAuditLog)
        >>> await backend.log_violation(...)  # Same interface
    """

    def __init__(self, session: AsyncSession, model_class):
        """Initialize database audit backend.

        Args:
            session: Async database session for audit logging operations
            model_class: Model class for audit logs (e.g., RateLimitAuditLog)
                Must implement RateLimitAuditLogBase interface

        Example (Dashtam):
            >>> from src.core.database import get_session
            >>> from src.models.rate_limit_audit import RateLimitAuditLog
            >>> session = await anext(get_session())
            >>> backend = DatabaseAuditBackend(session, RateLimitAuditLog)

        Example (Other App):
            >>> from my_app.models import MySQLRateLimitAuditLog
            >>> backend = DatabaseAuditBackend(session, MySQLRateLimitAuditLog)
        """
        self.session = session
        self.model_class = model_class

    async def log_violation(
        self,
        ip_address: str,
        endpoint: str,
        rule_name: str,
        limit: int,
        window_seconds: int,
        violation_count: int,
        identifier: Optional[str] = None,
        timestamp: Optional[datetime] = None,
    ) -> None:
        """Log rate limit violation to database.

        Creates an immutable audit record in the audit log table.
        Failures are logged but don't raise exceptions (fail-open design).

        Args:
            ip_address: Client IP address (IPv4 or IPv6)
            endpoint: API endpoint that was rate limited
            rule_name: Name of the rate limit rule violated
            limit: Maximum requests allowed in the window
            window_seconds: Time window for the limit (in seconds)
            violation_count: How many requests exceeded the limit
            identifier: Optional app-defined tracking
                - Format is application-specific
                - Examples: "user:uuid", "tenant:123", "session:abc", None
                - Dashtam uses: "user:{uuid}" or None
            timestamp: Optional custom timestamp (defaults to current UTC time)

        Returns:
            None

        Raises:
            No exceptions raised - errors are logged and swallowed (fail-open)

        Example (Anonymous):
            >>> await backend.log_violation(
            ...     ip_address="192.168.1.1",
            ...     endpoint="/api/v1/auth/login",
            ...     rule_name="auth_login",
            ...     limit=5,
            ...     window_seconds=60,
            ...     violation_count=1,
            ...     identifier=None  # No user tracking
            ... )

        Example (Authenticated):
            >>> await backend.log_violation(
            ...     ip_address="10.0.0.5",
            ...     endpoint="/api/v1/providers",
            ...     rule_name="api_user",
            ...     limit=100,
            ...     window_seconds=60,
            ...     violation_count=1,
            ...     identifier="user:abc-123-def-456"  # Dashtam's format
            ... )

        Logging:
            - INFO: Successful audit log creation
            - ERROR: Database failures (with full exception details)
        """
        try:
            # Use provided timestamp or default to current UTC time
            log_timestamp = timestamp or datetime.now(timezone.utc)

            # Create audit log entry using app-provided model class
            audit_log = self.model_class(
                timestamp=log_timestamp,
                ip_address=ip_address,
                endpoint=endpoint,
                rule_name=rule_name,
                limit=limit,
                window_seconds=window_seconds,
                violation_count=violation_count,
                identifier=identifier,  # App-defined tracking (can be None)
            )

            # Persist to database
            self.session.add(audit_log)
            await self.session.commit()

            logger.info(
                "Rate limit violation logged",
                extra={
                    "audit_log_id": str(audit_log.id),
                    "ip_address": ip_address,
                    "endpoint": endpoint,
                    "rule_name": rule_name,
                    "identifier": identifier,
                    "limit": limit,
                    "window_seconds": window_seconds,
                    "violation_count": violation_count,
                },
            )

        except Exception as e:
            # Fail-open: Log error but don't raise
            # Audit logging failures should not block rate limiting enforcement
            logger.error(
                f"Failed to log rate limit violation to database: {e}",
                extra={
                    "ip_address": ip_address,
                    "endpoint": endpoint,
                    "rule_name": rule_name,
                    "error": str(e),
                },
                exc_info=True,
            )
