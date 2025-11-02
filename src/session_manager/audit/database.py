"""Database-agnostic audit backend implementation.

Works with any database - app provides AsyncSession and audit model.
Package NEVER creates audit tables - app manages schema via Alembic.
"""

from typing import Any, Dict, Type

from sqlalchemy.ext.asyncio import AsyncSession

from ..models.base import SessionBase
from .base import SessionAuditBackend


class DatabaseAuditBackend(SessionAuditBackend):
    """Database audit backend.

    Writes audit logs to database using app-provided model.
    Package NEVER creates tables - app manages schema via Alembic.

    Design Pattern:
        - Database-agnostic (PostgreSQL, MySQL, SQLite)
        - App provides AsyncSession and concrete audit model
        - Persistent, queryable audit trail
        - Zero schema coupling

    Example (Dashtam):
        ```python
        from src.models.session_audit import SessionAuditLog
        from src.core.database import get_session

        db_session = await anext(get_session())
        audit = DatabaseAuditBackend(
            db_session=db_session,
            audit_model=SessionAuditLog
        )
        ```

    App's Audit Model Example:
        ```python
        class SessionAuditLog(SQLModel, table=True):
            __tablename__ = "session_audit_logs"

            id: UUID = Field(default_factory=uuid4, primary_key=True)
            session_id: UUID = Field(nullable=False, index=True)
            event_type: str = Field(...)  # "created", "revoked", etc.
            event_details: Optional[str] = Field(default=None)
            timestamp: datetime = Field(...)
        ```
    """

    def __init__(self, db_session: AsyncSession, audit_model: Type):
        """Initialize with app's database session and audit model.

        Args:
            db_session: AsyncSession for database operations (app provides)
            audit_model: App's concrete audit log class
        """
        self.db = db_session
        self.audit_model = audit_model

    async def log_session_created(
        self, session: SessionBase, context: Dict[str, Any]
    ) -> None:
        """Log session creation event to database.

        Args:
            session: Newly created session
            context: Additional context (IP, device, location, etc.)
        """
        audit_log = self.audit_model(
            session_id=session.id,
            event_type="session_created",
            event_details=str(context),  # JSON or string representation
            # App model should have timestamp with default=now()
        )

        self.db.add(audit_log)
        await self.db.commit()

    async def log_session_revoked(
        self, session_id: str, reason: str, context: Dict[str, Any]
    ) -> None:
        """Log session revocation event to database.

        Args:
            session_id: Revoked session ID
            reason: Revocation reason
            context: Who revoked it, from where
        """
        audit_log = self.audit_model(
            session_id=session_id,
            event_type="session_revoked",
            event_details=f"Reason: {reason}, Context: {context}",
        )

        self.db.add(audit_log)
        await self.db.commit()

    async def log_session_accessed(
        self, session_id: str, context: Dict[str, Any]
    ) -> None:
        """Log session access event to database.

        Args:
            session_id: Accessed session ID
            context: Access metadata (endpoint, operation, IP)
        """
        audit_log = self.audit_model(
            session_id=session_id,
            event_type="session_accessed",
            event_details=str(context),
        )

        self.db.add(audit_log)
        await self.db.commit()

    async def log_suspicious_activity(
        self, session_id: str, event: str, context: Dict[str, Any]
    ) -> None:
        """Log suspicious activity to database.

        Args:
            session_id: Session involved
            event: Suspicious event type
            context: Event details
        """
        audit_log = self.audit_model(
            session_id=session_id,
            event_type=f"suspicious_{event}",
            event_details=str(context),
        )

        self.db.add(audit_log)
        await self.db.commit()
