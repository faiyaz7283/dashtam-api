"""Session domain model base class.

This module defines the abstract SessionBase interface that applications
must implement with their chosen ORM (SQLModel, Django ORM, etc.).

Package defines REQUIRED fields and business logic interface.
Apps implement concrete models with their chosen database types.
"""

from abc import ABC
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID


class SessionBase(ABC):
    """Abstract base model for sessions.

    Package defines REQUIRED fields and business logic interface.
    Apps implement concrete models with their chosen ORM and database types.

    Design Principles:
        - Database Agnostic: No PostgreSQL, MySQL, or SQLite assumptions
        - ORM Freedom: Apps choose SQLModel, Django ORM, SQLAlchemy, etc.
        - Interface Definition: Defines structure, apps implement storage
        - Business Logic: Core session logic (is_active) defined here

    Required Fields:
        id: Session identifier (UUID recommended)
        user_id: User identifier (format determined by app)
        device_info: Device/browser information
        ip_address: Client IP (storage format determined by app)
            - PostgreSQL: INET type
            - MySQL: VARCHAR(45)
            - SQLite: TEXT
        user_agent: Full user agent string
        location: Geographic location (from IP enrichment)
        created_at: Session creation timestamp (timezone-aware UTC)
        last_activity: Last activity timestamp
        expires_at: Session expiration timestamp
        is_revoked: Whether session is revoked
        is_trusted: Whether device is trusted
        revoked_at: When session was revoked
        revoked_reason: Why session was revoked

    Business Logic:
        is_active(): Check if session is valid (not revoked, not expired)

    Example Implementation (Dashtam with SQLModel + PostgreSQL):
        ```python
        from sqlmodel import Field, SQLModel, Column
        from sqlalchemy.dialects.postgresql import INET

        class Session(SQLModel, SessionBase, table=True):
            __tablename__ = "sessions"

            id: UUID = Field(default_factory=uuid4, primary_key=True)
            user_id: str = Field(sa_column=Column(String(255)))
            ip_address: Optional[str] = Field(sa_column=Column(INET))  # PostgreSQL native
            # ... other fields ...

            def is_active(self) -> bool:
                return super().is_active()
        ```
    """

    # Required fields (apps implement with database-specific types)
    id: UUID
    user_id: str
    device_info: Optional[str]
    ip_address: Optional[str]  # Format depends on database (INET, VARCHAR, TEXT)
    user_agent: Optional[str]
    location: Optional[str]
    created_at: datetime  # Must be timezone-aware (UTC)
    last_activity: Optional[datetime]
    expires_at: Optional[datetime]
    is_revoked: bool
    is_trusted: bool
    revoked_at: Optional[datetime]
    revoked_reason: Optional[str]

    def is_active(self) -> bool:
        """Check if session is active (not revoked, not expired).

        Apps can override this method to add custom logic.

        Returns:
            True if session is active, False otherwise
        """
        if self.is_revoked:
            return False
        if self.expires_at and datetime.now(timezone.utc) > self.expires_at:
            return False
        return True
