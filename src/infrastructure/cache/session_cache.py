"""Redis implementation of SessionCache protocol.

Provides fast (<5ms) session lookups via Redis caching.
Uses write-through caching: writes go to both cache and database.

Key Patterns:
    - session:{session_id} -> JSON serialized SessionData
    - user:{user_id}:sessions -> Redis Set of session IDs

Architecture:
    - Implements SessionCache protocol (structural typing)
    - Uses RedisAdapter for low-level operations
    - Returns None on cache miss (fail-open for resilience)
    - Database is always source of truth

Reference:
    - docs/architecture/session-management-architecture.md
"""

import json
import logging
from dataclasses import asdict
from datetime import UTC, datetime
from uuid import UUID

from src.core.result import Success
from src.domain.protocols.session_repository import SessionData
from src.infrastructure.cache.redis_adapter import RedisAdapter


logger = logging.getLogger(__name__)

# Default session TTL (30 days in seconds)
DEFAULT_SESSION_TTL = 30 * 24 * 60 * 60  # 2,592,000 seconds


class RedisSessionCache:
    """Redis implementation of SessionCache protocol.

    Provides fast session lookups and maintains user->sessions index
    for efficient bulk operations.

    Note: Does NOT inherit from SessionCache protocol (uses structural typing).

    Key Patterns:
        - session:{session_id} -> Full session data (JSON)
        - user:{user_id}:sessions -> Set of session IDs

    Attributes:
        _redis: RedisAdapter instance for cache operations.
    """

    def __init__(self, redis_adapter: RedisAdapter) -> None:
        """Initialize session cache.

        Args:
            redis_adapter: RedisAdapter instance for Redis operations.
        """
        self._redis = redis_adapter

    def _session_key(self, session_id: UUID) -> str:
        """Generate cache key for session data.

        Args:
            session_id: Session identifier.

        Returns:
            Cache key string.
        """
        return f"session:{session_id}"

    def _user_sessions_key(self, user_id: UUID) -> str:
        """Generate cache key for user's session set.

        Args:
            user_id: User identifier.

        Returns:
            Cache key string.
        """
        return f"user:{user_id}:sessions"

    async def get(self, session_id: UUID) -> SessionData | None:
        """Get session data from cache.

        Args:
            session_id: Session identifier.

        Returns:
            SessionData if cached, None otherwise (cache miss or error).
        """
        key = self._session_key(session_id)
        result = await self._redis.get_json(key)

        match result:
            case Success(value=None):
                return None
            case Success(value=data) if data is not None:
                try:
                    return self._from_dict(data)
                except (KeyError, TypeError, ValueError) as e:
                    logger.warning(
                        "Failed to deserialize session from cache",
                        extra={"session_id": str(session_id), "error": str(e)},
                    )
                    return None
            case _:
                # Cache error - fail open (return None)
                logger.warning(
                    "Cache error getting session",
                    extra={"session_id": str(session_id)},
                )
                return None

    async def set(
        self,
        session_data: SessionData,
        *,
        ttl_seconds: int | None = None,
    ) -> None:
        """Store session data in cache.

        Also maintains the user->sessions index.

        Args:
            session_data: Session data to cache.
            ttl_seconds: Cache TTL in seconds. If None, calculates from
                session expires_at. Defaults to 30 days if no expiry.
        """
        # Calculate TTL
        if ttl_seconds is None:
            if session_data.expires_at is not None:
                now = datetime.now(UTC)
                # Handle timezone-naive expires_at
                expires_at = session_data.expires_at
                if expires_at.tzinfo is None:
                    expires_at = expires_at.replace(tzinfo=UTC)
                ttl_seconds = max(1, int((expires_at - now).total_seconds()))
            else:
                ttl_seconds = DEFAULT_SESSION_TTL

        # Store session data
        key = self._session_key(session_data.id)
        data = self._to_dict(session_data)

        result = await self._redis.set_json(key, data, ttl=ttl_seconds)
        if not isinstance(result, Success):
            logger.warning(
                "Failed to cache session",
                extra={"session_id": str(session_data.id)},
            )
            return

        # Add to user's session index
        await self.add_user_session(session_data.user_id, session_data.id)

    async def delete(self, session_id: UUID) -> bool:
        """Remove session from cache.

        Note: Does NOT remove from user index (caller should use remove_user_session).

        Args:
            session_id: Session identifier.

        Returns:
            True if deleted, False if not found or error.
        """
        key = self._session_key(session_id)
        result = await self._redis.delete(key)

        match result:
            case Success(value=deleted):
                return deleted
            case _:
                logger.warning(
                    "Cache error deleting session",
                    extra={"session_id": str(session_id)},
                )
                return False

    async def delete_all_for_user(self, user_id: UUID) -> int:
        """Remove all sessions for a user from cache.

        Removes session data and clears user's session index.

        Args:
            user_id: User identifier.

        Returns:
            Number of sessions removed from cache.
        """
        # Get all session IDs for user
        session_ids = await self.get_user_session_ids(user_id)

        if not session_ids:
            return 0

        # Delete each session
        deleted_count = 0
        for session_id in session_ids:
            if await self.delete(session_id):
                deleted_count += 1

        # Clear the user's session index
        user_key = self._user_sessions_key(user_id)
        await self._redis.delete(user_key)

        return deleted_count

    async def exists(self, session_id: UUID) -> bool:
        """Check if session exists in cache (quick validation).

        Args:
            session_id: Session identifier.

        Returns:
            True if session exists in cache, False otherwise.
        """
        key = self._session_key(session_id)
        result = await self._redis.exists(key)

        match result:
            case Success(value=exists):
                return exists
            case _:
                return False

    async def get_user_session_ids(self, user_id: UUID) -> list[UUID]:
        """Get all session IDs for a user from cache.

        Args:
            user_id: User identifier.

        Returns:
            List of session IDs, empty if none cached or error.
        """
        key = self._user_sessions_key(user_id)
        result = await self._redis.get(key)

        match result:
            case Success(value=None):
                return []
            case Success(value=data) if data is not None:
                try:
                    # Stored as JSON array of UUID strings
                    ids = json.loads(data)
                    return [UUID(id_str) for id_str in ids]
                except (json.JSONDecodeError, ValueError) as e:
                    logger.warning(
                        "Failed to parse user session IDs from cache",
                        extra={"user_id": str(user_id), "error": str(e)},
                    )
                    return []
            case _:
                return []

    async def add_user_session(self, user_id: UUID, session_id: UUID) -> None:
        """Add session ID to user's session set.

        Args:
            user_id: User identifier.
            session_id: Session identifier.
        """
        key = self._user_sessions_key(user_id)

        # Get current list
        current_ids = await self.get_user_session_ids(user_id)

        # Add new session if not already present
        if session_id not in current_ids:
            current_ids.append(session_id)

        # Store updated list
        data = json.dumps([str(sid) for sid in current_ids])
        await self._redis.set(key, data, ttl=DEFAULT_SESSION_TTL)

    async def remove_user_session(self, user_id: UUID, session_id: UUID) -> None:
        """Remove session ID from user's session set.

        Args:
            user_id: User identifier.
            session_id: Session identifier.
        """
        key = self._user_sessions_key(user_id)

        # Get current list
        current_ids = await self.get_user_session_ids(user_id)

        # Remove session if present
        if session_id in current_ids:
            current_ids.remove(session_id)

        if current_ids:
            # Store updated list
            data = json.dumps([str(sid) for sid in current_ids])
            await self._redis.set(key, data, ttl=DEFAULT_SESSION_TTL)
        else:
            # No sessions left, delete the key
            await self._redis.delete(key)

    async def update_last_activity(
        self,
        session_id: UUID,
        ip_address: str | None = None,
    ) -> bool:
        """Update session's last activity in cache.

        Lightweight update - only modifies last_activity_at and optionally last_ip_address.

        Args:
            session_id: Session identifier.
            ip_address: Current IP address (optional).

        Returns:
            True if updated, False if session not in cache.
        """
        # Get current session data
        session_data = await self.get(session_id)
        if session_data is None:
            return False

        # Create updated copy
        now = datetime.now(UTC)
        updated_data = SessionData(
            id=session_data.id,
            user_id=session_data.user_id,
            device_info=session_data.device_info,
            user_agent=session_data.user_agent,
            ip_address=session_data.ip_address,
            location=session_data.location,
            created_at=session_data.created_at,
            last_activity_at=now,
            expires_at=session_data.expires_at,
            is_revoked=session_data.is_revoked,
            is_trusted=session_data.is_trusted,
            revoked_at=session_data.revoked_at,
            revoked_reason=session_data.revoked_reason,
            refresh_token_id=session_data.refresh_token_id,
            last_ip_address=ip_address if ip_address else session_data.last_ip_address,
            suspicious_activity_count=session_data.suspicious_activity_count,
            last_provider_accessed=session_data.last_provider_accessed,
            last_provider_sync_at=session_data.last_provider_sync_at,
            providers_accessed=session_data.providers_accessed,
        )

        # Store updated data (preserves existing TTL by calculating from expires_at)
        await self.set(updated_data)
        return True

    # =========================================================================
    # Serialization helpers
    # =========================================================================

    def _to_dict(self, session_data: SessionData) -> dict[str, object]:
        """Convert SessionData to dict for JSON serialization.

        Args:
            session_data: SessionData to convert.

        Returns:
            Dictionary representation.
        """
        data = asdict(session_data)

        # Convert UUID to string
        data["id"] = str(session_data.id)
        data["user_id"] = str(session_data.user_id)

        if session_data.refresh_token_id:
            data["refresh_token_id"] = str(session_data.refresh_token_id)

        # Convert datetime to ISO string
        for dt_field in [
            "created_at",
            "last_activity_at",
            "expires_at",
            "revoked_at",
            "last_provider_sync_at",
        ]:
            if data.get(dt_field) is not None:
                data[dt_field] = data[dt_field].isoformat()

        return data

    def _from_dict(self, data: dict[str, object]) -> SessionData:
        """Convert dict to SessionData.

        Args:
            data: Dictionary from cache.

        Returns:
            SessionData instance.

        Raises:
            KeyError: If required field missing.
            ValueError: If UUID or datetime parsing fails.
        """
        # Parse UUIDs - cast to str for UUID constructor
        session_id = UUID(str(data["id"]))
        user_id = UUID(str(data["user_id"]))
        refresh_token_id_raw = data.get("refresh_token_id")
        refresh_token_id = (
            UUID(str(refresh_token_id_raw)) if refresh_token_id_raw else None
        )

        # Parse datetimes with explicit string cast
        def parse_dt(val: object | None) -> datetime | None:
            if val is None:
                return None
            return datetime.fromisoformat(str(val))

        # Extract values with explicit type casting
        device_info = str(data["device_info"]) if data.get("device_info") else None
        user_agent = str(data["user_agent"]) if data.get("user_agent") else None
        ip_address = str(data["ip_address"]) if data.get("ip_address") else None
        location = str(data["location"]) if data.get("location") else None
        revoked_reason = (
            str(data["revoked_reason"]) if data.get("revoked_reason") else None
        )
        last_ip = str(data["last_ip_address"]) if data.get("last_ip_address") else None
        last_provider = (
            str(data["last_provider_accessed"])
            if data.get("last_provider_accessed")
            else None
        )

        # Extract boolean and int with defaults
        is_revoked = bool(data.get("is_revoked", False))
        is_trusted = bool(data.get("is_trusted", False))
        suspicious_raw = data.get("suspicious_activity_count", 0)
        # Value is int from JSON - safe to cast
        suspicious_count = int(suspicious_raw) if suspicious_raw else 0  # type: ignore[call-overload]

        # Extract list with proper typing
        providers_raw = data.get("providers_accessed")
        providers_accessed: list[str] | None = (
            list(providers_raw) if isinstance(providers_raw, list) else None
        )

        return SessionData(
            id=session_id,
            user_id=user_id,
            device_info=device_info,
            user_agent=user_agent,
            ip_address=ip_address,
            location=location,
            created_at=parse_dt(data.get("created_at")),
            last_activity_at=parse_dt(data.get("last_activity_at")),
            expires_at=parse_dt(data.get("expires_at")),
            is_revoked=is_revoked,
            is_trusted=is_trusted,
            revoked_at=parse_dt(data.get("revoked_at")),
            revoked_reason=revoked_reason,
            refresh_token_id=refresh_token_id,
            last_ip_address=last_ip,
            suspicious_activity_count=suspicious_count,
            last_provider_accessed=last_provider,
            last_provider_sync_at=parse_dt(data.get("last_provider_sync_at")),
            providers_accessed=providers_accessed,
        )
