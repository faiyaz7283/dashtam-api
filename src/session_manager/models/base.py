"""Session domain model base class.

This module defines the abstract SessionBase interface that applications
must implement with their chosen ORM (SQLModel, Django ORM, etc.).

Package defines REQUIRED fields and business logic interface.
Apps implement concrete models with their chosen database types.
"""

from abc import ABC, abstractmethod
from datetime import datetime, timezone


class SessionBase(ABC):
    """Abstract interface for session models.

    This is a proper ABC that defines the INTERFACE contract for sessions,
    not the data structure. Apps implement concrete models with their chosen
    ORM and database types.

    Design Principles:
        - Interface Definition: Defines required methods and properties
        - Database Agnostic: No assumptions about storage
        - ORM Freedom: Apps choose SQLModel, Django ORM, SQLAlchemy, etc.
        - Business Logic: Core validation logic provided as default implementation

    Required Properties/Attributes (implement in concrete class):
        id: Session identifier (UUID recommended)
        user_id: User identifier (format determined by app)
        device_info: Device/browser information
        ip_address: Client IP (storage format determined by app)
        user_agent: Full user agent string
        location: Geographic location (from IP enrichment)
        created_at: Session creation timestamp (timezone-aware UTC)
        last_activity: Last activity timestamp
        expires_at: Session expiration timestamp
        is_revoked: Whether session is revoked
        is_trusted: Whether device is trusted
        revoked_at: When session was revoked
        revoked_reason: Why session was revoked

    Required Methods:
        is_session_active(): Check if session is valid (not revoked, not expired)

    Example Implementation (Dashtam with SQLModel + PostgreSQL):
        ```python
        from sqlmodel import Field, SQLModel, Column
        from sqlalchemy.dialects.postgresql import INET

        class Session(SQLModel, SessionBase, table=True):
            __tablename__ = "sessions"

            id: UUID = Field(default_factory=uuid4, primary_key=True)
            user_id: UUID = Field(foreign_key="users.id")
            ip_address: Optional[str] = Field(sa_column=Column(INET))
            is_revoked: bool = Field(default=False)
            is_trusted: bool = Field(default=False)
            # ... other fields ...

            def is_session_active(self) -> bool:
                # Use base implementation or override
                return super().is_session_active()
        ```

    Note:
        Concrete implementations MUST provide all required fields as
        database columns/attributes. This ABC only defines the interface.
    """

    # Abstract method that concrete classes must implement
    @abstractmethod
    def is_session_active(self) -> bool:
        """Check if session is active (not revoked, not expired).

        Default implementation checks:
        - Session is not revoked
        - Session has not expired

        Concrete classes can override to add custom logic.

        Returns:
            True if session is active, False otherwise
        """
        # Note: This is a default implementation that can be used by calling super().is_session_active()
        # Concrete classes can access self.is_revoked and self.expires_at
        # because they must implement these as fields
        if self.is_revoked:  # type: ignore
            return False
        if self.expires_at and datetime.now(timezone.utc) > self.expires_at:  # type: ignore
            return False
        return True
