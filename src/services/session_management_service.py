"""Session management service for user-facing session control.

This service provides:
- List all active sessions (devices) for a user
- Revoke specific session (logout from device)
- Revoke all other sessions (keep current)
- Revoke all sessions (nuclear option)

Security:
- Authorization: users can only manage their own sessions
- Current session protection: cannot revoke current session individually
- Immediate revocation: Redis cache invalidation
- Audit logging: all session events logged
- Rate limiting: prevents abuse (configured in RateLimitConfig)

Dependencies:
- GeolocationService: IP → location conversion
- Redis: token blacklist (immediate revocation)
"""

import logging
from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from src.models.auth import RefreshToken
from src.services.geolocation_service import GeolocationService
from src.core.redis_client import get_redis_client

logger = logging.getLogger(__name__)


class SessionInfo:
    """Session information for API response."""

    def __init__(
        self,
        id: UUID,
        device_info: str | None,
        location: str | None,
        ip_address: str | None,
        last_activity: datetime | None,
        created_at: datetime,
        is_current: bool,
        is_trusted: bool,
    ):
        self.id = id
        self.device_info = device_info or "Unknown Device"
        self.location = location or "Unknown Location"
        self.ip_address = ip_address
        self.last_activity = last_activity or created_at
        self.created_at = created_at
        self.is_current = is_current
        self.is_trusted = is_trusted

    def to_dict(self) -> dict:
        """Convert to dict for JSON serialization."""
        return {
            "id": str(self.id),
            "device_info": self.device_info,
            "location": self.location,
            "ip_address": self.ip_address,
            "last_activity": self.last_activity.isoformat(),
            "created_at": self.created_at.isoformat(),
            "is_current": self.is_current,
            "is_trusted": self.is_trusted,
        }


class SessionManagementService:
    """Manage user sessions (refresh tokens) with visibility and control."""

    def __init__(self, session: AsyncSession, geo_service: GeolocationService):
        """Initialize session management service.

        Args:
            session: Database session
            geo_service: Geolocation service for IP lookups
        """
        self.session = session
        self.geo_service = geo_service
        self.redis = get_redis_client()

    async def list_sessions(
        self, user_id: UUID, current_token_id: UUID | None = None
    ) -> list[SessionInfo]:
        """List all active sessions for user with enriched metadata.

        Args:
            user_id: User UUID
            current_token_id: ID of current refresh token (from JWT jti claim)

        Returns:
            List of SessionInfo objects (sorted by last_activity DESC)

        Example:
            ```python
            sessions = await service.list_sessions(
                user_id=user.id,
                current_token_id=UUID("...")
            )
            for session in sessions:
                print(f"{session.device_info} - {session.location}")
            ```
        """
        # Query non-revoked refresh tokens for user
        result = await self.session.execute(
            select(RefreshToken)
            .where(
                RefreshToken.user_id == user_id,
                ~RefreshToken.is_revoked,
                RefreshToken.expires_at > datetime.now(timezone.utc),
            )
            .order_by(RefreshToken.last_used_at.desc().nullsfirst())
        )
        tokens = result.scalars().all()

        sessions = []
        for token in tokens:
            # Enrich location if missing (backfill)
            if not token.location and token.ip_address:
                token.location = self.geo_service.get_location(str(token.ip_address))
                await self.session.commit()

            # Detect current session (compare token ID with JWT jti)
            is_current = current_token_id and token.id == current_token_id

            session_info = SessionInfo(
                id=token.id,
                device_info=token.device_info,
                location=token.location,
                ip_address=str(token.ip_address) if token.ip_address else None,
                last_activity=token.last_used_at,
                created_at=token.created_at,
                is_current=is_current,
                is_trusted=token.is_trusted_device,
            )
            sessions.append(session_info)

        logger.info(f"Listed {len(sessions)} sessions for user {user_id}")
        return sessions

    async def revoke_session(
        self,
        user_id: UUID,
        session_id: UUID,
        current_session_id: UUID | None,
        revoked_by_ip: str,
        revoked_by_device: str,
    ) -> None:
        """Revoke specific session with audit trail.

        Args:
            user_id: User UUID (authorization check)
            session_id: Session to revoke
            current_session_id: Current session (cannot revoke self)
            revoked_by_ip: IP address of revocation request
            revoked_by_device: Device info of revocation request

        Raises:
            HTTPException(400): If trying to revoke current session
            HTTPException(404): If session not found or not owned by user

        Example:
            ```python
            await service.revoke_session(
                user_id=user.id,
                session_id=UUID("..."),
                current_session_id=UUID("..."),
                revoked_by_ip="192.168.1.1",
                revoked_by_device="Chrome on macOS"
            )
            ```
        """
        # Cannot revoke current session (use logout endpoint instead)
        if session_id == current_session_id:
            raise HTTPException(
                status_code=400,
                detail="Cannot revoke current session. Use logout endpoint instead.",
            )

        # Query session
        result = await self.session.execute(
            select(RefreshToken).where(
                RefreshToken.id == session_id, RefreshToken.user_id == user_id
            )
        )
        token = result.scalar_one_or_none()

        if not token:
            raise HTTPException(
                status_code=404, detail="Session not found or not owned by user"
            )

        if token.is_revoked:
            raise HTTPException(status_code=400, detail="Session already revoked")

        # Revoke session
        token.revoke()
        await self.session.commit()

        # Invalidate in Redis cache (if cached)
        await self._invalidate_token_cache(token.id)

        # Audit log
        logger.info(
            f"Session revoked: user={user_id}, session={session_id}, "
            f"revoked_by_ip={revoked_by_ip}, revoked_by_device={revoked_by_device}"
        )

        # TODO: Send email alert if revoked from different device/IP

    async def revoke_other_sessions(
        self, user_id: UUID, current_session_id: UUID | None
    ) -> int:
        """Revoke all sessions except current.

        Args:
            user_id: User UUID
            current_session_id: Current session to keep active

        Returns:
            Count of revoked sessions

        Example:
            ```python
            count = await service.revoke_other_sessions(
                user_id=user.id,
                current_session_id=UUID("...")
            )
            print(f"Revoked {count} sessions")
            ```
        """
        # Query all non-current, non-revoked tokens
        query = select(RefreshToken).where(
            RefreshToken.user_id == user_id, ~RefreshToken.is_revoked
        )

        # Exclude current session
        if current_session_id:
            query = query.where(RefreshToken.id != current_session_id)

        result = await self.session.execute(query)
        tokens = result.scalars().all()

        # Bulk revoke
        revoked_count = 0
        for token in tokens:
            token.revoke()
            await self._invalidate_token_cache(token.id)
            revoked_count += 1

        await self.session.commit()

        logger.info(
            f"Bulk session revocation: user={user_id}, "
            f"revoked_count={revoked_count}, current_kept={current_session_id}"
        )

        return revoked_count

    async def revoke_all_sessions(self, user_id: UUID) -> int:
        """Revoke ALL sessions (nuclear option).

        Args:
            user_id: User UUID

        Returns:
            Count of revoked sessions

        Example:
            ```python
            count = await service.revoke_all_sessions(user_id=user.id)
            print(f"Revoked all {count} sessions")
            ```

        Notes:
            - User will be logged out immediately
            - Use for account compromise response
            - Creates audit log entry
        """
        # Query all non-revoked tokens
        result = await self.session.execute(
            select(RefreshToken).where(
                RefreshToken.user_id == user_id, ~RefreshToken.is_revoked
            )
        )
        tokens = result.scalars().all()

        # Bulk revoke
        revoked_count = 0
        for token in tokens:
            token.revoke()
            await self._invalidate_token_cache(token.id)
            revoked_count += 1

        await self.session.commit()

        logger.info(
            f"Full session revocation: user={user_id}, revoked_count={revoked_count}"
        )

        return revoked_count

    async def _invalidate_token_cache(self, token_id: UUID) -> None:
        """Invalidate token in Redis cache (immediate revocation).

        Args:
            token_id: Refresh token UUID

        Notes:
            - Adds token to blacklist with 30-day TTL
            - Checked on token refresh (immediate revocation)
        """
        if self.redis:
            # Add to blacklist (30-day TTL matches token expiration)
            key = f"revoked_token:{token_id}"
            await self.redis.setex(key, 2592000, "1")  # 30 days in seconds
