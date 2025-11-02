"""Session audit log model for tracking session lifecycle events.

This module provides the SessionAuditLog model used by the session_manager
package's DatabaseAuditBackend for persistent audit trails.

The model tracks:
- Session creation events
- Session revocation events
- Session access events (optional)
- Suspicious activity events

Compliance:
    - PCI-DSS Requirement 10.2: Automated audit trail
    - SOC 2: Access and activity logging
    - GDPR Article 15: Right to access audit data
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlmodel import Field, Column
from sqlalchemy import String, Text, Index

from src.models.base import DashtamBase


class SessionAuditLog(DashtamBase, table=True):
    """Audit log for session lifecycle events.

    Tracks all session-related operations for security monitoring,
    compliance, and incident investigation.

    Event Types:
        - session_created: New session established
        - session_revoked: Session terminated
        - session_accessed: Session used (optional, high-security)
        - suspicious_*: Suspicious activity detected

    Attributes:
        session_id: ID of the session being audited
        event_type: Type of event (created, revoked, accessed, suspicious_*)
        event_details: JSON or text details about the event
        user_id: User associated with the session (optional, for faster queries)
        ip_address: IP address where event originated
        user_agent: User agent string

    Indexes:
        - session_id: Fast session history lookup
        - event_type: Fast event type filtering
        - created_at: Time-based queries (most recent events)
        - user_id: Fast user audit history lookup

    Example:
        ```python
        # Log session creation
        audit_log = SessionAuditLog(
            session_id=session.id,
            event_type="session_created",
            event_details='{"device": "Chrome", "location": "San Francisco"}',
            user_id=session.user_id,
            ip_address="192.168.1.1",
            user_agent="Mozilla/5.0..."
        )
        session.add(audit_log)
        await session.commit()

        # Query user's session history
        result = await session.execute(
            select(SessionAuditLog)
            .where(SessionAuditLog.user_id == user_id)
            .order_by(SessionAuditLog.created_at.desc())
        )
        logs = result.scalars().all()
        ```

    Note:
        This model is designed to work with session_manager package's
        DatabaseAuditBackend. The package expects fields: session_id,
        event_type, event_details, and timestamp (created_at).
    """

    __tablename__ = "session_audit_logs"

    # Core audit fields (required by session_manager)
    session_id: UUID = Field(
        nullable=False,
        index=True,
        description="ID of the session being audited",
    )

    event_type: str = Field(
        sa_column=Column(String(100), nullable=False, index=True),
        description="Type of event (session_created, session_revoked, suspicious_*, etc.)",
    )

    event_details: Optional[str] = Field(
        default=None,
        sa_column=Column(Text, nullable=True),
        description="JSON or text details about the event (context, metadata)",
    )

    # Additional context fields (Dashtam-specific)
    user_id: Optional[UUID] = Field(
        default=None,
        nullable=True,
        index=True,
        description="User associated with the session (for faster user history queries)",
    )

    ip_address: Optional[str] = Field(
        default=None,
        sa_column=Column(String(45), nullable=True),  # IPv4: 15 chars, IPv6: 45 chars
        description="IP address where event originated",
    )

    user_agent: Optional[str] = Field(
        default=None,
        sa_column=Column(Text, nullable=True),
        description="User agent string of the client",
    )

    # Indexes for performance
    __table_args__ = (
        # Composite index for session history queries
        Index("ix_session_audit_session_created", "session_id", "created_at"),
        # Composite index for user history queries
        Index("ix_session_audit_user_created", "user_id", "created_at"),
        # Index for event type filtering
        Index("ix_session_audit_event_type", "event_type"),
    )

    @property
    def event_timestamp(self) -> datetime:
        """Timestamp of the event (alias for created_at).

        Provides more semantic naming for audit log queries.

        Returns:
            Event timestamp in UTC
        """
        return self.created_at

    def __repr__(self) -> str:
        """String representation for debugging."""
        return (
            f"<SessionAuditLog("
            f"id={self.id}, "
            f"session_id={self.session_id}, "
            f"event_type={self.event_type}, "
            f"timestamp={self.created_at}"
            f")>"
        )
