"""Audit trail protocol (port) for compliance tracking.

This protocol defines the contract for audit trail systems. Infrastructure adapters
implement this protocol to provide concrete audit implementations (PostgreSQL, MongoDB,
in-memory for testing, etc.).

Following hexagonal architecture:
- Domain defines the PORT (this protocol)
- Infrastructure provides ADAPTERS (PostgresAuditAdapter, etc.)
- Application layer uses the protocol (doesn't know about specific adapters)

Compliance:
    PCI-DSS: 7+ year retention, immutable audit trail
    SOC 2: Security event tracking (who/what/when/where)
    GDPR: Personal data access tracking

Usage:
    from src.domain.protocols import AuditProtocol
    from src.domain.enums import AuditAction

    # Dependency injection via container
    audit: AuditProtocol = Depends(get_audit)

    # Record audit event
    result = await audit.record(
        action=AuditAction.USER_LOGIN,
        user_id=user_id,
        resource_type="session",
        ip_address=request.client.host,
        user_agent=request.headers.get("User-Agent"),
        context={"method": "password", "mfa": True},
    )

    # Query audit trail
    result = await audit.query(
        user_id=user_id,
        action=AuditAction.USER_LOGIN,
        start_date=datetime.now() - timedelta(days=30),
        limit=100,
    )
"""

from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

from src.core.result import Result
from src.domain.enums import AuditAction
from src.domain.errors import AuditError


class AuditProtocol(Protocol):
    """Protocol for audit trail systems.

    Records immutable audit entries for compliance (PCI-DSS, SOC 2, GDPR).
    All implementations MUST ensure immutability (no updates/deletes).

    Implementations:
        - PostgresAuditAdapter: PostgreSQL with RULES for immutability
        - MySQLAuditAdapter: MySQL with TRIGGERS (future)
        - SQLiteAuditAdapter: SQLite for testing (future)
        - InMemoryAuditAdapter: In-memory for unit tests (future)

    Immutability:
        Implementations MUST enforce immutability at database level:
        - PostgreSQL: Use RULES to block UPDATE/DELETE
        - MySQL: Use TRIGGERS to block UPDATE/DELETE
        - SQLite: Use constraints + app-level enforcement
        - In-memory: Simple list append (testing only)

    Error Handling:
        All methods return Result types (Success or Failure).
        NEVER raise exceptions - wrap in Failure(AuditError(...)) instead.
    """

    async def record(
        self,
        *,
        action: AuditAction,
        resource_type: str,
        user_id: UUID | None = None,
        resource_id: UUID | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> Result[None, AuditError]:
        """Record an immutable audit entry.

        Creates a new audit log entry that cannot be modified or deleted after
        creation. This is the ONLY way to create audit entries.

        Args:
            action: What happened (enum for type safety and consistency).
            resource_type: What was affected (user, account, provider, session, etc.).
                Must be a valid resource type string.
            user_id: Who performed the action. None for system actions
                (scheduled tasks, automated processes, etc.).
            resource_id: Specific resource identifier (if applicable).
                Optional - use when action affects a specific resource.
            ip_address: Client IP address (required for auth events).
                Should be IPv4 or IPv6 string format.
            user_agent: Client user agent string (browser/app info).
            context: Additional event context (JSONB - extensible).
                Recommended fields vary by action type (see AuditAction docstrings).

        Returns:
            Result[None, AuditError]:
                - Success(None) if audit entry recorded successfully
                - Failure(AuditError) if recording failed (database error, etc.)

        Example:
            # Successful login
            result = await audit.record(
                action=AuditAction.USER_LOGIN,
                user_id=user_id,
                resource_type="session",
                resource_id=session_id,
                ip_address="192.168.1.1",
                user_agent="Mozilla/5.0...",
                context={
                    "method": "password",
                    "mfa": True,
                    "remember_me": False,
                },
            )

            # Failed login (no user_id available)
            result = await audit.record(
                action=AuditAction.USER_LOGIN_FAILED,
                user_id=None,  # Unknown user
                resource_type="session",
                ip_address="192.168.1.1",
                user_agent="Mozilla/5.0...",
                context={
                    "reason": "invalid_password",
                    "attempts": 3,
                    "email": "user@example.com",  # For correlation
                },
            )

            # System action (no user)
            result = await audit.record(
                action=AuditAction.PROVIDER_DATA_SYNCED,
                user_id=None,  # System action
                resource_type="provider",
                resource_id=provider_id,
                context={
                    "provider_name": "schwab",
                    "records_synced": 150,
                    "sync_duration_ms": 2340,
                },
            )

        Note:
            - Records are IMMUTABLE (cannot update or delete)
            - Timestamp is set automatically by database
            - All audit entries are retained for 7+ years (compliance)
            - Context is stored as JSONB for schema flexibility
        """
        ...

    async def query(
        self,
        *,
        user_id: UUID | None = None,
        action: AuditAction | None = None,
        resource_type: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Result[list[dict[str, Any]], AuditError]:
        """Query audit trail (read-only, for compliance reports).

        Retrieves audit entries matching the specified filters. Used for
        compliance reports, security investigations, and forensics.

        Args:
            user_id: Filter by user who performed actions.
                If None, returns entries for all users.
            action: Filter by specific action type.
                If None, returns all action types.
            resource_type: Filter by resource type (user, account, provider).
                If None, returns all resource types.
            start_date: From date (inclusive). Filters by created_at timestamp.
                If None, no lower bound (returns oldest entries).
            end_date: To date (inclusive). Filters by created_at timestamp.
                If None, no upper bound (returns newest entries).
            limit: Maximum results to return. Default 100, maximum 1000.
                Prevents accidentally fetching millions of records.
            offset: Pagination offset. Skip this many results.
                Use with limit for pagination: page_size=100, offset=page*100.

        Returns:
            Result[list[dict[str, Any]], AuditError]:
                - Success(entries) if query succeeded (list may be empty)
                - Failure(AuditError) if query failed (database error, etc.)

            Each entry dict contains:
                - id: str (UUID as string)
                - action: str (audit action type)
                - user_id: str | None (UUID as string)
                - resource_type: str
                - resource_id: str | None (UUID as string)
                - ip_address: str | None
                - user_agent: str | None
                - context: dict (JSONB context)
                - timestamp: str (ISO 8601 format)

        Example:
            # User activity report (last 30 days)
            result = await audit.query(
                user_id=user_id,
                start_date=datetime.now() - timedelta(days=30),
                limit=100,
            )

            # Failed login attempts (security investigation)
            result = await audit.query(
                action=AuditAction.USER_LOGIN_FAILED,
                start_date=datetime.now() - timedelta(hours=24),
                limit=50,
            )

            # All provider actions for compliance report
            result = await audit.query(
                resource_type="provider",
                start_date=quarter_start,
                end_date=quarter_end,
                limit=1000,
            )

            # Paginated results
            page = 2
            page_size = 100
            result = await audit.query(
                user_id=user_id,
                limit=page_size,
                offset=page * page_size,
            )

        Note:
            - Read-only operation (safe to call repeatedly)
            - Results ordered by timestamp DESC (newest first)
            - Limit capped at 1000 to prevent DoS
            - Use pagination for large result sets
            - NOT for application logic (use domain events instead)
            - Primarily for compliance reports and security investigations
        """
        ...
