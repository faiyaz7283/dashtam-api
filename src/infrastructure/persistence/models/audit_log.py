"""Audit log database model for compliance tracking.

This module defines the AuditLog model for storing immutable audit trail records.
Used for PCI-DSS, SOC 2, and GDPR compliance.

CRITICAL: This table is IMMUTABLE. Records cannot be modified or deleted.
Immutability is enforced by PostgreSQL RULES in the migration.
"""

from typing import Any
from uuid import UUID

from sqlalchemy import Index, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.persistence.base import BaseModel


class AuditLog(BaseModel):
    """Audit log model - IMMUTABLE (cannot be updated or deleted).

    This model stores all audit trail records for compliance and security
    forensics. Records are append-only and cannot be modified after creation.

    Immutability Enforcement:
        - Database level: PostgreSQL RULES block UPDATE/DELETE operations
        - Application level: No update methods in repository
        - See migration: add_audit_logs_table for RULES definition

    Known Limitation:
        - TRUNCATE bypasses RULES (table owner can TRUNCATE)
        - For development: TRUNCATE should only be used for testing cleanup
        - For production: Implement separate owner user (see roadmap)

    Compliance:
        - PCI-DSS: 7+ year retention, immutable audit trail
        - SOC 2: Security event tracking (who/what/when/where)
        - GDPR: Personal data access tracking

    Fields:
        id: UUID primary key (from BaseModel)
        created_at: Timestamp when logged (from BaseModel, immutable)
        action: What happened (e.g., "user_login", "password_changed")
        user_id: Who performed the action (None for system actions)
        resource_type: What was affected (e.g., "user", "account", "provider")
        resource_id: Specific resource identifier (optional)
        ip_address: Where from (required for auth events)
        user_agent: Client information
        context: Additional event context (JSONB - extensible)

    Indexes:
        - idx_audit_user_action: (user_id, action) for user activity queries
        - idx_audit_resource: (resource_type, resource_id) for resource audits
        - created_at: Indexed via BaseModel for time-range queries

    Note:
        This model inherits from BaseModel (NOT BaseMutableModel) because
        audit logs are immutable and should not have updated_at field.

    Example:
        # Create audit log (via repository)
        audit_log = AuditLogModel(
            action="user_login",
            user_id=user_id,
            resource_type="session",
            ip_address="192.168.1.1",
            user_agent="Mozilla/5.0...",
            context={"method": "password", "mfa": True},
        )
        session.add(audit_log)
        await session.commit()

        # Query audit logs
        result = await session.execute(
            select(AuditLogModel)
            .where(AuditLogModel.user_id == user_id)
            .order_by(AuditLogModel.created_at.desc())
            .limit(100)
        )
        logs = result.scalars().all()
    """

    __tablename__ = "audit_logs"

    # What happened (indexed for filtering by action type)
    action: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment="Audit action type (e.g., user_login, password_changed)",
    )

    # Who did it (indexed for user activity queries, nullable for system actions)
    user_id: Mapped[UUID | None] = mapped_column(
        index=True,
        nullable=True,
        comment="User who performed the action (None for system actions)",
    )

    # What was affected (indexed for resource queries)
    resource_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment="Type of resource affected (user, account, provider, etc.)",
    )

    resource_id: Mapped[UUID | None] = mapped_column(
        index=True,
        nullable=True,
        comment="Specific resource identifier (if applicable)",
    )

    # Where and how (nullable, but required for auth events)
    ip_address: Mapped[str | None] = mapped_column(
        String(45),  # IPv6 max length
        nullable=True,
        comment="Client IP address (required for authentication events)",
    )

    user_agent: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="Client user agent string",
    )

    # Extensible context (JSONB in PostgreSQL for flexible schema)
    context: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
        default=None,
        comment="Additional event context (JSONB - extensible without schema changes)",
    )

    # Composite indexes for common query patterns
    __table_args__ = (
        # User activity queries: "Show me all login attempts by user X"
        Index("idx_audit_user_action", "user_id", "action"),
        # Resource audit queries: "Show me all changes to account Y"
        Index("idx_audit_resource", "resource_type", "resource_id"),
        # Note: created_at is already indexed via BaseModel
    )

    def __repr__(self) -> str:
        """String representation for debugging.

        Returns:
            str: Human-readable representation of audit log.
        """
        return (
            f"<AuditLog("
            f"id={self.id}, "
            f"action={self.action!r}, "
            f"user_id={self.user_id}, "
            f"created_at={self.created_at}"
            f")>"
        )
