"""Redis channel naming conventions for SSE pub/sub.

This module provides centralized channel key generation for SSE,
following the same pattern as CacheKeys in src/infrastructure/cache/cache_keys.py.

Channel Patterns:
    sse:user:{user_id}           - Per-user event channel (pub/sub)
    sse:broadcast                - Global broadcast channel (pub/sub)
    sse:stream:user:{user_id}    - Redis Stream for event retention

Reference:
    - docs/architecture/sse-architecture.md (Section 5.2)
"""

from uuid import UUID

from src.core.constants import SSE_CHANNEL_PREFIX


class SSEChannelKeys:
    """Centralized Redis channel key generation for SSE.

    All SSE-related Redis keys are generated here to ensure consistent
    naming and avoid magic strings throughout the codebase.

    Note:
        Prefix comes from src/core/constants.py (DRY compliance).

    Example:
        >>> channel = SSEChannelKeys.user_channel(user_id)
        >>> # Returns "sse:user:01234567-89ab-cdef-..."
    """

    @staticmethod
    def user_channel(user_id: UUID) -> str:
        """Get Redis pub/sub channel for user.

        Args:
            user_id: User's UUID.

        Returns:
            Channel name for user-specific events.

        Example:
            >>> SSEChannelKeys.user_channel(UUID("abc123..."))
            "sse:user:abc123..."
        """
        return f"{SSE_CHANNEL_PREFIX}:user:{user_id}"

    @staticmethod
    def broadcast_channel() -> str:
        """Get Redis pub/sub channel for broadcasts.

        Returns:
            Channel name for system-wide broadcasts.

        Example:
            >>> SSEChannelKeys.broadcast_channel()
            "sse:broadcast"
        """
        return f"{SSE_CHANNEL_PREFIX}:broadcast"

    @staticmethod
    def user_stream(user_id: UUID) -> str:
        """Get Redis Stream key for event retention.

        Used when sse_enable_retention is True. Stores events for
        Last-Event-ID replay on reconnection.

        Args:
            user_id: User's UUID.

        Returns:
            Stream key for event retention.

        Example:
            >>> SSEChannelKeys.user_stream(UUID("abc123..."))
            "sse:stream:user:abc123..."
        """
        return f"{SSE_CHANNEL_PREFIX}:stream:user:{user_id}"

    @staticmethod
    def parse_user_id_from_channel(channel: str) -> UUID | None:
        """Extract user_id from channel name.

        Useful for processing messages from Redis pub/sub where
        channel name is provided.

        Args:
            channel: Channel name (e.g., "sse:user:abc123...").

        Returns:
            UUID if valid user channel, None otherwise.

        Example:
            >>> SSEChannelKeys.parse_user_id_from_channel("sse:user:abc123...")
            UUID("abc123...")
            >>> SSEChannelKeys.parse_user_id_from_channel("sse:broadcast")
            None
        """
        parts = channel.split(":")
        if len(parts) == 3 and parts[0] == SSE_CHANNEL_PREFIX and parts[1] == "user":
            try:
                return UUID(parts[2])
            except ValueError:
                return None
        return None

    @staticmethod
    def is_broadcast_channel(channel: str) -> bool:
        """Check if channel is the broadcast channel.

        Args:
            channel: Channel name to check.

        Returns:
            True if broadcast channel, False otherwise.
        """
        return channel == f"{SSE_CHANNEL_PREFIX}:broadcast"
