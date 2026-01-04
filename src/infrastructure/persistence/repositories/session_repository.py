"""SessionRepository - SQLAlchemy implementation of SessionRepository protocol.

Adapter for hexagonal architecture.
Maps between domain SessionData DTOs and database Session models.

This repository handles all session persistence operations including:
- CRUD operations
- Active session counting (for limit enforcement)
- Bulk revocation (password change, security events)
- Session cleanup (expired session removal)

Reference:
    - docs/architecture/session-management-architecture.md
"""

from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID

from sqlalchemy import and_, delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.protocols.session_repository import SessionData
from src.infrastructure.persistence.models.session import Session as SessionModel


class SessionRepository:
    """SQLAlchemy implementation of SessionRepository protocol.

    This is an adapter that implements the SessionRepository port.
    It handles mapping between SessionData DTOs and Session database models.

    This class does NOT inherit from SessionRepository protocol
    (Protocol uses structural typing - duck typing with type safety).

    Attributes:
        session: SQLAlchemy async session for database operations.

    Example:
        >>> async with get_session() as db_session:
        ...     repo = SessionRepository(db_session)
        ...     session_data = await repo.find_by_id(session_id)
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository with database session.

        Args:
            session: SQLAlchemy async session.
        """
        self._session = session

    async def save(self, session_data: SessionData) -> None:
        """Save or update a session.

        Creates new session if it doesn't exist, updates if it does.
        Uses merge to handle both insert and update scenarios.

        Args:
            session_data: Session data to persist.
        """
        # Check if session exists
        existing = await self._session.get(SessionModel, session_data.id)

        if existing is None:
            # Create new session
            session_model = self._to_model(session_data)
            self._session.add(session_model)
        else:
            # Update existing session
            self._update_model(existing, session_data)

        await self._session.commit()

    async def find_by_id(self, session_id: UUID) -> SessionData | None:
        """Find session by ID.

        Args:
            session_id: Session identifier.

        Returns:
            SessionData if found, None otherwise.
        """
        session_model = await self._session.get(SessionModel, session_id)

        if session_model is None:
            return None

        return self._to_dto(session_model)

    async def find_by_user_id(
        self,
        user_id: UUID,
        *,
        active_only: bool = False,
    ) -> list[SessionData]:
        """Find all sessions for a user.

        Args:
            user_id: User identifier.
            active_only: If True, only return active (non-revoked, non-expired) sessions.

        Returns:
            List of session data, empty if none found.
            Ordered by created_at descending (newest first).
        """
        stmt = select(SessionModel).where(SessionModel.user_id == user_id)

        if active_only:
            now = datetime.now(UTC)
            stmt = stmt.where(
                and_(
                    SessionModel.is_revoked.is_(False),
                    SessionModel.expires_at > now,
                )
            )

        stmt = stmt.order_by(SessionModel.created_at.desc())
        result = await self._session.execute(stmt)
        session_models = result.scalars().all()

        return [self._to_dto(model) for model in session_models]

    async def find_by_refresh_token_id(
        self,
        refresh_token_id: UUID,
    ) -> SessionData | None:
        """Find session by refresh token ID.

        Used during token refresh to locate associated session.

        Args:
            refresh_token_id: Refresh token identifier.

        Returns:
            SessionData if found, None otherwise.
        """
        stmt = select(SessionModel).where(
            SessionModel.refresh_token_id == refresh_token_id
        )
        result = await self._session.execute(stmt)
        session_model = result.scalar_one_or_none()

        if session_model is None:
            return None

        return self._to_dto(session_model)

    async def count_active_sessions(self, user_id: UUID) -> int:
        """Count active sessions for a user.

        Used to enforce session limits. A session is active if:
        - is_revoked is False
        - expires_at is in the future

        Args:
            user_id: User identifier.

        Returns:
            Number of active sessions.
        """
        now = datetime.now(UTC)
        stmt = select(func.count()).where(
            and_(
                SessionModel.user_id == user_id,
                SessionModel.is_revoked.is_(False),
                SessionModel.expires_at > now,
            )
        )
        result = await self._session.execute(stmt)
        return result.scalar_one()

    async def delete(self, session_id: UUID) -> bool:
        """Delete a session (hard delete).

        Args:
            session_id: Session identifier.

        Returns:
            True if deleted, False if not found.
        """
        stmt = delete(SessionModel).where(SessionModel.id == session_id)
        result = await self._session.execute(stmt)
        await self._session.commit()
        return (cast(Any, result).rowcount or 0) > 0

    async def delete_all_for_user(self, user_id: UUID) -> int:
        """Delete all sessions for a user (hard delete).

        Used during account deletion or security reset.

        Args:
            user_id: User identifier.

        Returns:
            Number of sessions deleted.
        """
        stmt = delete(SessionModel).where(SessionModel.user_id == user_id)
        result = await self._session.execute(stmt)
        await self._session.commit()
        return cast(Any, result).rowcount or 0

    async def revoke_all_for_user(
        self,
        user_id: UUID,
        reason: str,
        *,
        except_session_id: UUID | None = None,
    ) -> int:
        """Revoke all sessions for a user (soft delete).

        Used during password change or security event.
        Optionally excludes the current session.

        Args:
            user_id: User identifier.
            reason: Revocation reason for audit.
            except_session_id: Session ID to exclude (e.g., current session).

        Returns:
            Number of sessions revoked.
        """
        now = datetime.now(UTC)

        # Build where clause
        conditions = [
            SessionModel.user_id == user_id,
            SessionModel.is_revoked.is_(False),
        ]

        if except_session_id is not None:
            conditions.append(SessionModel.id != except_session_id)

        stmt = (
            update(SessionModel)
            .where(and_(*conditions))
            .values(
                is_revoked=True,
                revoked_at=now,
                revoked_reason=reason,
            )
        )

        result = await self._session.execute(stmt)
        await self._session.commit()
        return cast(Any, result).rowcount or 0

    async def get_oldest_active_session(
        self,
        user_id: UUID,
    ) -> SessionData | None:
        """Get the oldest active session for a user.

        Used when enforcing session limits (FIFO eviction).

        Args:
            user_id: User identifier.

        Returns:
            Oldest active session data, None if no active sessions.
        """
        now = datetime.now(UTC)
        stmt = (
            select(SessionModel)
            .where(
                and_(
                    SessionModel.user_id == user_id,
                    SessionModel.is_revoked.is_(False),
                    SessionModel.expires_at > now,
                )
            )
            .order_by(SessionModel.created_at.asc())
            .limit(1)
        )

        result = await self._session.execute(stmt)
        session_model = result.scalar_one_or_none()

        if session_model is None:
            return None

        return self._to_dto(session_model)

    async def cleanup_expired_sessions(
        self,
        *,
        before: datetime | None = None,
    ) -> int:
        """Clean up expired sessions (batch operation).

        Called by scheduled job to remove old sessions.
        Deletes sessions that are either:
        - Expired (expires_at < before)
        - Revoked more than retention period ago

        Args:
            before: Delete sessions expired before this time.
                   Defaults to now.

        Returns:
            Number of sessions cleaned up.
        """
        if before is None:
            before = datetime.now(UTC)

        # Delete expired or revoked sessions
        stmt = delete(SessionModel).where(
            SessionModel.expires_at < before,
        )

        result = await self._session.execute(stmt)
        await self._session.commit()
        return cast(Any, result).rowcount or 0

    # =========================================================================
    # Additional utility methods (not in protocol but useful)
    # =========================================================================

    async def update_activity(
        self,
        session_id: UUID,
        ip_address: str | None = None,
    ) -> bool:
        """Update session activity timestamp and optionally IP.

        Called on each authenticated request to track activity.

        Args:
            session_id: Session identifier.
            ip_address: Current client IP (for detecting changes).

        Returns:
            True if updated, False if session not found.
        """
        now = datetime.now(UTC)
        values: dict[str, object] = {"last_activity_at": now}

        if ip_address is not None:
            values["last_ip_address"] = ip_address

        stmt = (
            update(SessionModel).where(SessionModel.id == session_id).values(**values)
        )

        result = await self._session.execute(stmt)
        await self._session.commit()
        return (cast(Any, result).rowcount or 0) > 0

    async def update_provider_access(
        self,
        session_id: UUID,
        provider_name: str,
    ) -> bool:
        """Record provider access in session.

        Updates last_provider_accessed, last_provider_sync_at,
        and adds to providers_accessed array.

        Args:
            session_id: Session identifier.
            provider_name: Name of provider accessed.

        Returns:
            True if updated, False if session not found.
        """
        now = datetime.now(UTC)

        # First, get current providers_accessed
        session_model = await self._session.get(SessionModel, session_id)
        if session_model is None:
            return False

        # Update providers list
        current_providers = session_model.providers_accessed or []
        if provider_name not in current_providers:
            current_providers = [*current_providers, provider_name]

        # Update fields
        session_model.last_provider_accessed = provider_name
        session_model.last_provider_sync_at = now
        session_model.providers_accessed = current_providers

        await self._session.commit()
        return True

    async def increment_suspicious_activity(
        self,
        session_id: UUID,
    ) -> int:
        """Increment suspicious activity counter.

        Args:
            session_id: Session identifier.

        Returns:
            New counter value, or -1 if session not found.
        """
        session_model = await self._session.get(SessionModel, session_id)
        if session_model is None:
            return -1

        session_model.suspicious_activity_count += 1
        await self._session.commit()
        return session_model.suspicious_activity_count

    async def set_refresh_token_id(
        self,
        session_id: UUID,
        refresh_token_id: UUID,
    ) -> bool:
        """Set the refresh token ID for a session.

        Called after refresh token is created to link it to session.

        Args:
            session_id: Session identifier.
            refresh_token_id: Refresh token identifier.

        Returns:
            True if updated, False if session not found.
        """
        stmt = (
            update(SessionModel)
            .where(SessionModel.id == session_id)
            .values(refresh_token_id=refresh_token_id)
        )

        result = await self._session.execute(stmt)
        await self._session.commit()
        return (cast(Any, result).rowcount or 0) > 0

    # =========================================================================
    # Mapping methods
    # =========================================================================

    def _to_dto(self, model: SessionModel) -> SessionData:
        """Convert database model to SessionData DTO.

        Args:
            model: SQLAlchemy Session model instance.

        Returns:
            SessionData DTO.
        """
        return SessionData(
            id=model.id,
            user_id=model.user_id,
            device_info=model.device_info,
            user_agent=model.user_agent,
            ip_address=str(model.ip_address) if model.ip_address else None,
            location=model.location,
            created_at=model.created_at,
            last_activity_at=model.last_activity_at,
            expires_at=model.expires_at,
            is_revoked=model.is_revoked,
            is_trusted=model.is_trusted,
            revoked_at=model.revoked_at,
            revoked_reason=model.revoked_reason,
            refresh_token_id=model.refresh_token_id,
            last_ip_address=str(model.last_ip_address)
            if model.last_ip_address
            else None,
            suspicious_activity_count=model.suspicious_activity_count,
            last_provider_accessed=model.last_provider_accessed,
            last_provider_sync_at=model.last_provider_sync_at,
            providers_accessed=list(model.providers_accessed)
            if model.providers_accessed
            else None,
        )

    def _to_model(self, dto: SessionData) -> SessionModel:
        """Convert SessionData DTO to database model.

        Args:
            dto: SessionData DTO.

        Returns:
            SQLAlchemy Session model instance.
        """
        return SessionModel(
            id=dto.id,
            user_id=dto.user_id,
            device_info=dto.device_info,
            user_agent=dto.user_agent,
            ip_address=dto.ip_address,
            location=dto.location,
            created_at=dto.created_at,  # Explicit: override DB default
            last_activity_at=dto.last_activity_at,
            expires_at=dto.expires_at,
            is_revoked=dto.is_revoked,
            is_trusted=dto.is_trusted,
            revoked_at=dto.revoked_at,
            revoked_reason=dto.revoked_reason,
            refresh_token_id=dto.refresh_token_id,
            last_ip_address=dto.last_ip_address,
            suspicious_activity_count=dto.suspicious_activity_count,
            last_provider_accessed=dto.last_provider_accessed,
            last_provider_sync_at=dto.last_provider_sync_at,
            providers_accessed=dto.providers_accessed,
        )

    def _update_model(self, model: SessionModel, dto: SessionData) -> None:
        """Update existing model with DTO values.

        Updates all mutable fields. Does not change id or user_id.

        Args:
            model: Existing SQLAlchemy model to update.
            dto: SessionData DTO with new values.
        """
        model.device_info = dto.device_info
        model.user_agent = dto.user_agent
        model.ip_address = dto.ip_address
        model.location = dto.location
        model.last_activity_at = dto.last_activity_at
        model.expires_at = dto.expires_at
        model.is_revoked = dto.is_revoked
        model.is_trusted = dto.is_trusted
        model.revoked_at = dto.revoked_at
        model.revoked_reason = dto.revoked_reason
        model.refresh_token_id = dto.refresh_token_id
        model.last_ip_address = dto.last_ip_address
        model.suspicious_activity_count = dto.suspicious_activity_count
        model.last_provider_accessed = dto.last_provider_accessed
        model.last_provider_sync_at = dto.last_provider_sync_at
        model.providers_accessed = dto.providers_accessed
