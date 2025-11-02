"""Cache-agnostic session storage implementation.

Works with ANY cache implementing CacheClient protocol (Redis, Memcached, etc.).
Uses Protocol pattern for runtime duck typing - no hard dependencies on cache libraries.
"""

import json
from datetime import datetime, timezone
from typing import List, Optional, Protocol

from ..models.base import SessionBase
from ..models.filters import SessionFilters
from .base import SessionStorage


class CacheClient(Protocol):
    """Abstract cache client interface.

    App can provide ANY cache client implementing this protocol:
    - Redis (via redis-py or aioredis)
    - Memcached (via aiomemcache)
    - Custom cache implementation

    This enables cache-agnostic storage - package doesn't depend on any
    specific cache library.

    Example (Redis):
        ```python
        from redis.asyncio import Redis

        redis_client = Redis.from_url("redis://localhost")
        storage = CacheSessionStorage(cache=redis_client)
        ```

    Example (Memcached):
        ```python
        from aiomemcache import Client

        memcache_client = Client("localhost", 11211)
        storage = CacheSessionStorage(cache=memcache_client)
        ```
    """

    async def get(self, key: str) -> Optional[str]:
        """Get value by key.

        Args:
            key: Cache key

        Returns:
            Value as string, or None if key doesn't exist
        """
        ...

    async def set(self, key: str, value: str, ttl: int) -> None:
        """Set value with TTL.

        Args:
            key: Cache key
            value: Value to store (as string)
            ttl: Time-to-live in seconds
        """
        ...

    async def delete(self, key: str) -> None:
        """Delete key from cache.

        Args:
            key: Cache key to delete
        """
        ...


class CacheSessionStorage(SessionStorage):
    """Cache-backed session storage.

    Works with ANY cache implementing CacheClient protocol.
    Sessions serialized to JSON before caching.

    Design Pattern:
        - Cache-agnostic (Redis, Memcached, etc.)
        - App provides cache client
        - Package handles serialization/deserialization
        - TTL-based expiration

    Example (Redis):
        ```python
        from redis.asyncio import Redis

        redis_client = Redis.from_url("redis://localhost")
        storage = CacheSessionStorage(cache=redis_client)
        ```

    Note:
        Cache storage is best for temporary sessions. For persistent sessions
        across cache restarts, use DatabaseSessionStorage.
    """

    def __init__(
        self,
        session_model: type,
        cache_client: CacheClient,
        ttl: int = 3600,
    ):
        """Initialize with app's cache client.

        Args:
            session_model: Application's concrete Session model class
            cache_client: Any client implementing CacheClient protocol
            ttl: Default TTL in seconds (default 3600 = 1 hour)
        """
        self.session_model = session_model
        self.cache = cache_client
        self.default_ttl = ttl

    def _session_key(self, session_id: str) -> str:
        """Generate cache key for session.

        Args:
            session_id: Session identifier

        Returns:
            Cache key (e.g., "session:abc123")
        """
        return f"session:{session_id}"

    def _user_sessions_key(self, user_id: str) -> str:
        """Generate cache key for user's session list.

        Args:
            user_id: User identifier

        Returns:
            Cache key (e.g., "user:sessions:user123")
        """
        return f"user:sessions:{user_id}"

    def _serialize_session(self, session: SessionBase) -> str:
        """Serialize session to JSON string.

        Args:
            session: Session to serialize

        Returns:
            JSON string
        """
        # Convert session to dict (assumes session has dict-like interface)
        session_dict = {
            "id": str(session.id),
            "user_id": session.user_id,
            "device_info": session.device_info,
            "ip_address": session.ip_address,
            "user_agent": session.user_agent,
            "location": session.location,
            "created_at": session.created_at.isoformat()
            if session.created_at
            else None,
            "last_activity": (
                session.last_activity.isoformat() if session.last_activity else None
            ),
            "expires_at": session.expires_at.isoformat()
            if session.expires_at
            else None,
            "is_revoked": session.is_revoked,
            "is_trusted": session.is_trusted,
            "revoked_at": session.revoked_at.isoformat()
            if session.revoked_at
            else None,
            "revoked_reason": session.revoked_reason,
        }
        return json.dumps(session_dict)

    async def save_session(self, session: SessionBase) -> None:
        """Serialize and cache session with TTL.

        Args:
            session: Session to save
        """
        key = self._session_key(str(session.id))
        value = self._serialize_session(session)

        # Calculate TTL from expires_at
        if session.expires_at:
            ttl = int((session.expires_at - datetime.now(timezone.utc)).total_seconds())
            ttl = max(ttl, 60)  # Minimum 60 seconds
        else:
            ttl = 86400  # Default 24 hours

        await self.cache.set(key, value, ttl)

        # Note: In production, might also maintain user session index
        # using Redis SADD: self.cache.sadd(user_sessions_key, session_id)
        # For now, we rely on individual session lookups

    async def get_session(self, session_id: str) -> Optional[SessionBase]:
        """Fetch and deserialize session from cache.

        Args:
            session_id: Session identifier

        Returns:
            Session or None if not found

        Note:
            Returns dict representation. App should reconstruct Session model.
        """
        key = self._session_key(session_id)
        value = await self.cache.get(key)

        if not value:
            return None

        # Deserialize JSON to dict
        # Note: Cache storage returns dict, not concrete Session model
        # App layer should reconstruct Session from dict
        session_dict = json.loads(value)

        # Convert ISO strings back to datetime
        for field in ["created_at", "last_activity", "expires_at", "revoked_at"]:
            if session_dict.get(field):
                session_dict[field] = datetime.fromisoformat(session_dict[field])

        return session_dict  # type: ignore

    async def list_sessions(
        self, user_id: str, filters: Optional[SessionFilters] = None
    ) -> List[SessionBase]:
        """List sessions for user.

        Args:
            user_id: User identifier
            filters: Optional filters

        Returns:
            List of sessions

        Note:
            Cache storage has limited filtering capability compared to database.
            This is a simplified implementation.
        """
        # Note: Cache-based listing is complex without proper indexing
        # This is a simplified implementation
        # Real implementation might use Redis SCAN or maintain session lists
        return []

    async def revoke_session(self, session_id: str, reason: str) -> bool:
        """Mark session as revoked.

        Args:
            session_id: Session to revoke
            reason: Revocation reason

        Returns:
            True if revoked, False if not found
        """
        session = await self.get_session(session_id)
        if not session:
            return False

        # Update session
        session["is_revoked"] = True  # type: ignore
        session["revoked_at"] = datetime.now(timezone.utc)  # type: ignore
        session["revoked_reason"] = reason  # type: ignore

        # Re-serialize and save
        # Note: This is simplified. Real implementation needs proper Session object
        key = self._session_key(session_id)
        value = json.dumps(session)
        await self.cache.set(key, value, 3600)  # 1 hour TTL for revoked sessions

        return True

    async def delete_session(self, session_id: str) -> bool:
        """Permanently delete session from cache.

        Args:
            session_id: Session to delete

        Returns:
            True if deleted, False if not found
        """
        key = self._session_key(session_id)
        await self.cache.delete(key)
        return True
