"""Database Audit Backend for Rate Limiting.

This module implements PostgreSQL-based audit logging for rate limit violations.

Architecture:
    - Implements AuditBackend interface (Strategy Pattern)
    - Uses async SQLAlchemy for non-blocking database operations
    - Fail-open design: Audit failures don't block requests
    - Structured logging for observability

Example Usage:
    >>> from sqlalchemy.ext.asyncio import AsyncSession
    >>> from src.rate_limiting.audit_backends.database import DatabaseAuditBackend
    >>>
    >>> backend = DatabaseAuditBackend(db_session)
    >>> await backend.log_violation(
    ...     ip_address="192.168.1.1",
    ...     endpoint="/api/v1/auth/login",
    ...     rule_name="auth_login",
    ...     limit=5,
    ...     window_seconds=60,
    ...     violation_count=1
    ... )
"""

import logging
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.rate_limiting.audit_backends.base import AuditBackend
from src.rate_limiting.models import RateLimitAuditLog

logger = logging.getLogger(__name__)


class DatabaseAuditBackend(AuditBackend):
    """PostgreSQL audit backend for rate limit violations.

    Stores rate limit violations in the `rate_limit_audit_logs` table for
    security analysis, monitoring, and compliance reporting.

    Design:
        - Fail-open: Database errors are logged but don't block requests
        - Async operations: Non-blocking database writes
        - Structured logging: All operations logged for observability
        - Timezone-aware: All timestamps stored in UTC

    Attributes:
        session: AsyncSession for database operations

    Example:
        >>> backend = DatabaseAuditBackend(db_session)
        >>> await backend.log_violation(
        ...     ip_address="192.168.1.1",
        ...     endpoint="/api/v1/providers",
        ...     rule_name="provider_list",
        ...     limit=100,
        ...     window_seconds=60,
        ...     violation_count=1,
        ...     user_id=uuid.uuid4()
        ... )
    """

    def __init__(self, session: AsyncSession):
        """Initialize database audit backend.

        Args:
            session: Async database session for audit logging operations.

        Example:
            >>> from src.core.database import get_session
            >>> session = await anext(get_session())
            >>> backend = DatabaseAuditBackend(session)
        """
        self.session = session

    async def log_violation(
        self,
        ip_address: str,
        endpoint: str,
        rule_name: str,
        limit: int,
        window_seconds: int,
        violation_count: int,
        user_id: Optional[UUID] = None,
        timestamp: Optional[datetime] = None,
    ) -> None:
        """Log rate limit violation to PostgreSQL database.

        Creates an immutable audit record in the `rate_limit_audit_logs` table.
        Failures are logged but don't raise exceptions (fail-open design).

        Args:
            ip_address: Client IP address (IPv4 or IPv6)
            endpoint: API endpoint that was rate limited
            rule_name: Name of the rate limit rule violated
            limit: Maximum requests allowed in the window
            window_seconds: Time window for the limit (in seconds)
            violation_count: How many requests exceeded the limit
            user_id: Optional user ID if request was authenticated
            timestamp: Optional custom timestamp (defaults to current UTC time)

        Returns:
            None

        Raises:
            No exceptions raised - errors are logged and swallowed (fail-open)

        Example:
            >>> await backend.log_violation(
            ...     ip_address="192.168.1.1",
            ...     endpoint="/api/v1/auth/login",
            ...     rule_name="auth_login",
            ...     limit=5,
            ...     window_seconds=60,
            ...     violation_count=1
            ... )

        Logging:
            - INFO: Successful audit log creation
            - ERROR: Database failures (with full exception details)
        """
        try:
            # Use provided timestamp or default to current UTC time
            log_timestamp = timestamp or datetime.now(timezone.utc)

            # Create audit log entry
            audit_log = RateLimitAuditLog(
                timestamp=log_timestamp,
                user_id=user_id,
                ip_address=ip_address,
                endpoint=endpoint,
                rule_name=rule_name,
                limit=limit,
                window_seconds=window_seconds,
                violation_count=violation_count,
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
                    "user_id": str(user_id) if user_id else None,
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
