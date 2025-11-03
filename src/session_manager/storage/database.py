"""Database-agnostic session storage implementation.

Works with ANY SQLAlchemy-compatible database (PostgreSQL, MySQL, SQLite).
App provides AsyncSession and concrete Session model.
Package NEVER creates tables - app manages schema via Alembic.
"""

from datetime import datetime, timezone
from typing import List, Optional, Type

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.base import SessionBase
from ..models.filters import SessionFilters
from .base import SessionStorage


class DatabaseSessionStorage(SessionStorage):
    """Database-agnostic storage implementation.

    Works with ANY SQLAlchemy-compatible database (PostgreSQL, MySQL, SQLite).
    App provides AsyncSession and concrete Session model.
    Package NEVER creates tables - app manages schema via Alembic.

    Design Pattern:
        - Database-agnostic (works with PostgreSQL, MySQL, SQLite)
        - App controls connection string (determines database type)
        - App provides AsyncSession (from their database configuration)
        - App provides Session model (with database-specific types)

    Example (PostgreSQL):
        ```python
        from src.models.session import Session  # App's SQLModel
        from src.core.database import get_session

        db_session = await anext(get_session())
        storage = DatabaseSessionStorage(db_session, Session)
        ```

    Example (MySQL):
        ```python
        # Same interface, different database!
        db_session = await anext(get_session())  # MySQL AsyncSession
        storage = DatabaseSessionStorage(db_session, Session)
        ```
    """

    def __init__(self, db_session: AsyncSession, session_model: Type[SessionBase]):
        """Initialize storage with app's database session and model.

        Args:
            db_session: AsyncSession for database operations (app provides)
            session_model: App's concrete Session class (e.g., Dashtam's SQLModel)
        """
        self.db = db_session
        self.session_model = session_model
        # If session_model is an adapter with table_model attribute, use that for queries
        # Otherwise use session_model directly
        self.table_model = getattr(session_model, "table_model", session_model)

    async def save_session(self, session: SessionBase) -> None:
        """Persist app's Session model to database.

        Args:
            session: Session instance to save

        Raises:
            Exception: If database operation fails
        """
        self.db.add(session)
        await self.db.commit()
        await self.db.refresh(session)

    async def get_session(self, session_id: str) -> Optional[SessionBase]:
        """Query returns app's concrete Session model.

        Args:
            session_id: Session identifier

        Returns:
            App's concrete Session model or None if not found
        """
        result = await self.db.execute(
            select(self.table_model).where(self.table_model.id == session_id)
        )
        db_model = result.scalar_one_or_none()
        if db_model is None:
            return None
        # If session_model is an adapter, wrap the result
        if hasattr(self.session_model, "from_refresh_token"):
            return self.session_model.from_refresh_token(db_model)
        return db_model

    async def list_sessions(
        self, user_id: str, filters: Optional[SessionFilters] = None
    ) -> List[SessionBase]:
        """List sessions using app's model with optional filters.

        Args:
            user_id: User ID to list sessions for
            filters: Optional filters (active_only, device_type, etc.)

        Returns:
            List of app's concrete Session models
        """
        stmt = select(self.table_model).where(self.table_model.user_id == user_id)

        # Apply filters if provided
        if filters:
            if filters.active_only:
                now = datetime.now(timezone.utc)
                stmt = stmt.where(
                    self.table_model.is_revoked == False,  # noqa: E712
                    (self.table_model.expires_at == None)  # noqa: E711
                    | (self.table_model.expires_at > now),
                )

            if filters.device_type:
                # Partial match on device_info field
                stmt = stmt.where(
                    self.table_model.device_info.contains(filters.device_type)
                )

            if filters.ip_address:
                stmt = stmt.where(self.table_model.ip_address == filters.ip_address)

            if filters.location:
                stmt = stmt.where(self.table_model.location.contains(filters.location))

            if filters.created_after:
                stmt = stmt.where(self.table_model.created_at >= filters.created_after)

            if filters.created_before:
                stmt = stmt.where(self.table_model.created_at <= filters.created_before)

            if filters.is_trusted is not None:
                stmt = stmt.where(self.table_model.is_trusted == filters.is_trusted)

        # Order by most recent first
        stmt = stmt.order_by(self.table_model.created_at.desc())

        result = await self.db.execute(stmt)
        db_models = list(result.scalars().all())

        # If session_model is an adapter, wrap the results
        if hasattr(self.session_model, "from_refresh_token"):
            return [self.session_model.from_refresh_token(model) for model in db_models]
        return db_models

    async def revoke_session(self, session_id: str, reason: str) -> bool:
        """Mark session as revoked.

        Args:
            session_id: Session to revoke
            reason: Revocation reason

        Returns:
            True if revoked, False if session not found
        """
        session = await self.get_session(session_id)
        if not session:
            return False

        session.is_revoked = True
        session.revoked_at = datetime.now(timezone.utc)
        session.revoked_reason = reason

        await self.db.commit()
        return True

    async def delete_session(self, session_id: str) -> bool:
        """Permanently delete session.

        Args:
            session_id: Session to delete

        Returns:
            True if deleted, False if session not found
        """
        session = await self.get_session(session_id)
        if not session:
            return False

        await self.db.delete(session)
        await self.db.commit()
        return True
