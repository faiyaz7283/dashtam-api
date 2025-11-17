"""PostgreSQL implementation of AuditProtocol.

This adapter provides immutable audit logging using PostgreSQL with:
- Database RULES blocking UPDATE/DELETE operations
- Async SQLAlchemy for database operations
- Result types for error handling (no exceptions)
- JSONB storage for flexible context data

Following hexagonal architecture:
- Infrastructure implements domain protocol (AuditProtocol)
- Domain doesn't know about PostgreSQL or SQLAlchemy
- Easy to swap implementations (MongoDB, MySQL, in-memory for testing)

Immutability:
    Records are immutable by design:
    - PostgreSQL RULES block UPDATE operations (see migration)
    - PostgreSQL RULES block DELETE operations (see migration)
    - Only INSERT operations are allowed
    - TRUNCATE requires table owner privileges (documented limitation)

Compliance:
    PCI-DSS: 7+ year retention, immutable audit trail
    SOC 2: Security event tracking (who/what/when/where)
    GDPR: Personal data access tracking

Usage:
    from src.infrastructure.audit.postgres_adapter import PostgresAuditAdapter
    from src.domain.enums import AuditAction

    # Inject via container
    adapter = PostgresAuditAdapter(session)

    # Record audit event
    result = await adapter.record(
        action=AuditAction.USER_LOGIN,
        user_id=user_id,
        resource_type="session",
        ip_address="192.168.1.1",
        context={"method": "password"},
    )
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.enums import ErrorCode
from src.core.result import Failure, Result, Success
from src.domain.enums import AuditAction
from src.domain.errors import AuditError
from src.infrastructure.persistence.models.audit import AuditLogModel


class PostgresAuditAdapter:
    """PostgreSQL implementation of AuditProtocol.

    Provides immutable audit logging with PostgreSQL database RULES
    enforcing immutability at the database level.

    This adapter is stateless - all state lives in the database.
    Sessions are managed by FastAPI dependency injection.

    Attributes:
        session: SQLAlchemy async session for database operations.

    Thread Safety:
        This adapter is NOT thread-safe (uses provided session).
        FastAPI creates new session per request (safe).
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize adapter with database session.

        Args:
            session: SQLAlchemy async session (injected by container).
                Session lifecycle managed by FastAPI dependency injection.
        """
        self.session = session

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

        Creates new audit log entry in PostgreSQL. Entry cannot be modified
        or deleted after creation (enforced by database RULES).

        Args:
            action: What happened (enum for type safety).
            resource_type: What was affected (user, account, provider, etc.).
            user_id: Who performed the action (None for system actions).
            resource_id: Specific resource identifier (optional).
            ip_address: Client IP address (required for auth events).
            user_agent: Client user agent string (browser/app info).
            context: Additional event context (stored as JSONB).

        Returns:
            Result[None, AuditError]:
                - Success(None) if audit entry recorded
                - Failure(AuditError) if database operation failed

        Example:
            # Successful login
            result = await adapter.record(
                action=AuditAction.USER_LOGIN,
                user_id=user_id,
                resource_type="session",
                resource_id=session_id,
                ip_address="192.168.1.1",
                user_agent="Mozilla/5.0...",
                context={
                    "method": "password",
                    "mfa": True,
                },
            )

            # Handle result
            match result:
                case Success():
                    logger.info("Audit logged", action=action.value)
                case Failure(error):
                    logger.error("Audit failed", error=error.message)

        Note:
            - Timestamp is set automatically by database (created_at)
            - Context is stored as JSONB (flexible schema)
            - Immutability enforced by PostgreSQL RULES
            - Foreign key to users table (not enforced yet - users table doesn't exist)
        """
        try:
            # Create audit log model
            audit_log = AuditLogModel(
                action=action.value,  # Convert enum to string
                user_id=user_id,
                resource_type=resource_type,
                resource_id=resource_id,
                ip_address=ip_address,
                user_agent=user_agent,
                context=context,  # Pass through None (matches protocol)
            )

            # Insert into database (only operation allowed)
            self.session.add(audit_log)
            await self.session.commit()  # Commit immediately for durability

            return Success(value=None)

        except SQLAlchemyError as e:
            # Rollback audit session on error
            await self.session.rollback()
            # Catch database errors (connection, constraint violations, etc.)
            return Failure(
                error=AuditError(
                    message=f"Failed to record audit log: {str(e)}",
                    code=ErrorCode.AUDIT_RECORD_FAILED,
                    details={
                        "action": action.value,
                        "resource_type": resource_type,
                        "error_type": type(e).__name__,
                    },
                )
            )
        except Exception as e:
            # Catch unexpected errors (should be rare)
            return Failure(
                error=AuditError(
                    message=f"Unexpected error recording audit log: {str(e)}",
                    code=ErrorCode.AUDIT_RECORD_FAILED,
                    details={
                        "action": action.value,
                        "resource_type": resource_type,
                        "error_type": type(e).__name__,
                    },
                )
            )

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

        Retrieves audit entries matching the specified filters.
        Used for compliance reports, security investigations, forensics.

        Args:
            user_id: Filter by user who performed actions (None = all users).
            action: Filter by specific action type (None = all actions).
            resource_type: Filter by resource type (None = all types).
            start_date: From date inclusive (None = no lower bound).
            end_date: To date inclusive (None = no upper bound).
            limit: Maximum results (default 100, capped at 1000).
            offset: Pagination offset (skip this many results).

        Returns:
            Result[list[dict[str, Any]], AuditError]:
                - Success(entries) if query succeeded (list may be empty)
                - Failure(AuditError) if database operation failed

            Each entry dict contains:
                - id: str (UUID as string)
                - action: str (audit action type)
                - user_id: str | None (UUID as string)
                - resource_type: str
                - resource_id: str | None (UUID as string)
                - ip_address: str | None
                - user_agent: str | None
                - context: dict (JSONB context)
                - created_at: str (ISO 8601 format)

        Example:
            # User activity report (last 30 days)
            result = await adapter.query(
                user_id=user_id,
                start_date=datetime.now() - timedelta(days=30),
                limit=100,
            )

            match result:
                case Success(entries):
                    for entry in entries:
                        print(f"{entry['action']} at {entry['created_at']}")
                case Failure(error):
                    logger.error("Query failed", error=error.message)

        Note:
            - Read-only operation (safe to call repeatedly)
            - Results ordered by created_at DESC (newest first)
            - Limit capped at 1000 to prevent DoS
            - UUIDs converted to strings for JSON serialization
            - Dates converted to ISO 8601 strings
        """
        try:
            # Cap limit at 1000 to prevent DoS
            limit = min(limit, 1000)

            # Build query with filters
            query = select(AuditLogModel)

            # Apply filters
            if user_id is not None:
                query = query.where(AuditLogModel.user_id == user_id)

            if action is not None:
                query = query.where(AuditLogModel.action == action.value)

            if resource_type is not None:
                query = query.where(AuditLogModel.resource_type == resource_type)

            if start_date is not None:
                query = query.where(AuditLogModel.created_at >= start_date)

            if end_date is not None:
                query = query.where(AuditLogModel.created_at <= end_date)

            # Order by created_at DESC (newest first)
            query = query.order_by(AuditLogModel.created_at.desc())

            # Apply pagination
            query = query.limit(limit).offset(offset)

            # Execute query
            result = await self.session.execute(query)
            audit_logs = result.scalars().all()

            # Convert models to dicts with string UUIDs
            entries: list[dict[str, Any]] = []
            for log in audit_logs:
                entry: dict[str, Any] = {
                    "id": str(log.id),
                    "action": log.action,
                    "resource_type": log.resource_type,
                    "ip_address": log.ip_address,
                    "user_agent": log.user_agent,
                    "context": log.context,
                    "created_at": log.created_at.isoformat(),
                }
                # Add optional fields with proper typing
                if log.user_id is not None:
                    entry["user_id"] = str(log.user_id)
                else:
                    entry["user_id"] = None

                if log.resource_id is not None:
                    entry["resource_id"] = str(log.resource_id)
                else:
                    entry["resource_id"] = None

                entries.append(entry)

            return Success(value=entries)

        except SQLAlchemyError as e:
            # Catch database errors (connection, query errors, etc.)
            error_details: dict[str, Any] = {
                "error_type": type(e).__name__,
            }
            if user_id is not None:
                error_details["user_id"] = str(user_id)
            if action is not None:
                error_details["action"] = action.value
            if resource_type is not None:
                error_details["resource_type"] = resource_type

            return Failure(
                error=AuditError(
                    message=f"Failed to query audit logs: {str(e)}",
                    code=ErrorCode.AUDIT_QUERY_FAILED,
                    details=error_details,
                )
            )
        except Exception as e:
            # Catch unexpected errors (should be rare)
            error_details_exc: dict[str, Any] = {
                "error_type": type(e).__name__,
            }
            if user_id is not None:
                error_details_exc["user_id"] = str(user_id)
            if action is not None:
                error_details_exc["action"] = action.value
            if resource_type is not None:
                error_details_exc["resource_type"] = resource_type

            return Failure(
                error=AuditError(
                    message=f"Unexpected error querying audit logs: {str(e)}",
                    code=ErrorCode.AUDIT_QUERY_FAILED,
                    details=error_details_exc,
                )
            )
