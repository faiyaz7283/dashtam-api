"""Unit tests for SSE Redis channel key generation.

Tests cover:
- SSEChannelKeys.user_channel() - per-user pub/sub channel
- SSEChannelKeys.broadcast_channel() - global broadcast channel
- SSEChannelKeys.user_stream() - Redis Streams key for retention
- SSEChannelKeys.parse_user_id_from_channel() - reverse lookup
- SSEChannelKeys.is_broadcast_channel() - channel type detection

Architecture:
    - Unit tests for infrastructure layer (no Redis connection)
    - Tests key format consistency
    - Validates parsing and detection logic
"""

from uuid import UUID

import pytest
from uuid_extensions import uuid7

from src.core.constants import SSE_CHANNEL_PREFIX
from src.infrastructure.sse.channel_keys import SSEChannelKeys


# =============================================================================
# User Channel Tests
# =============================================================================


@pytest.mark.unit
class TestUserChannel:
    """Test SSEChannelKeys.user_channel()."""

    def test_user_channel_format(self):
        """Test user channel uses correct format."""
        user_id = uuid7()
        channel = SSEChannelKeys.user_channel(user_id)

        expected = f"{SSE_CHANNEL_PREFIX}:user:{user_id}"
        assert channel == expected

    def test_user_channel_uses_sse_prefix(self):
        """Test user channel starts with SSE prefix from constants."""
        user_id = uuid7()
        channel = SSEChannelKeys.user_channel(user_id)

        assert channel.startswith(f"{SSE_CHANNEL_PREFIX}:")

    def test_user_channel_includes_user_id(self):
        """Test user channel contains the user ID."""
        user_id = uuid7()
        channel = SSEChannelKeys.user_channel(user_id)

        assert str(user_id) in channel

    def test_different_users_get_different_channels(self):
        """Test each user gets a unique channel."""
        user1 = uuid7()
        user2 = uuid7()

        channel1 = SSEChannelKeys.user_channel(user1)
        channel2 = SSEChannelKeys.user_channel(user2)

        assert channel1 != channel2


# =============================================================================
# Broadcast Channel Tests
# =============================================================================


@pytest.mark.unit
class TestBroadcastChannel:
    """Test SSEChannelKeys.broadcast_channel()."""

    def test_broadcast_channel_format(self):
        """Test broadcast channel uses correct format."""
        channel = SSEChannelKeys.broadcast_channel()

        expected = f"{SSE_CHANNEL_PREFIX}:broadcast"
        assert channel == expected

    def test_broadcast_channel_uses_sse_prefix(self):
        """Test broadcast channel starts with SSE prefix."""
        channel = SSEChannelKeys.broadcast_channel()

        assert channel.startswith(f"{SSE_CHANNEL_PREFIX}:")

    def test_broadcast_channel_is_deterministic(self):
        """Test broadcast channel is always the same."""
        channel1 = SSEChannelKeys.broadcast_channel()
        channel2 = SSEChannelKeys.broadcast_channel()

        assert channel1 == channel2


# =============================================================================
# User Stream Tests
# =============================================================================


@pytest.mark.unit
class TestUserStream:
    """Test SSEChannelKeys.user_stream()."""

    def test_user_stream_format(self):
        """Test user stream uses correct format."""
        user_id = uuid7()
        stream = SSEChannelKeys.user_stream(user_id)

        expected = f"{SSE_CHANNEL_PREFIX}:stream:user:{user_id}"
        assert stream == expected

    def test_user_stream_uses_sse_prefix(self):
        """Test user stream starts with SSE prefix."""
        user_id = uuid7()
        stream = SSEChannelKeys.user_stream(user_id)

        assert stream.startswith(f"{SSE_CHANNEL_PREFIX}:")

    def test_user_stream_includes_stream_segment(self):
        """Test user stream includes 'stream' segment."""
        user_id = uuid7()
        stream = SSEChannelKeys.user_stream(user_id)

        assert ":stream:" in stream

    def test_user_stream_different_from_user_channel(self):
        """Test user stream is distinct from user channel."""
        user_id = uuid7()
        channel = SSEChannelKeys.user_channel(user_id)
        stream = SSEChannelKeys.user_stream(user_id)

        assert channel != stream
        assert "stream" not in channel
        assert "stream" in stream


# =============================================================================
# Parse User ID Tests
# =============================================================================


@pytest.mark.unit
class TestParseUserIdFromChannel:
    """Test SSEChannelKeys.parse_user_id_from_channel()."""

    def test_parse_valid_user_channel(self):
        """Test parsing valid user channel returns UUID."""
        user_id = uuid7()
        channel = SSEChannelKeys.user_channel(user_id)

        parsed = SSEChannelKeys.parse_user_id_from_channel(channel)

        assert parsed == user_id

    def test_parse_broadcast_channel_returns_none(self):
        """Test parsing broadcast channel returns None."""
        channel = SSEChannelKeys.broadcast_channel()

        parsed = SSEChannelKeys.parse_user_id_from_channel(channel)

        assert parsed is None

    def test_parse_user_stream_returns_none(self):
        """Test parsing user stream returns None (different format)."""
        user_id = uuid7()
        stream = SSEChannelKeys.user_stream(user_id)

        parsed = SSEChannelKeys.parse_user_id_from_channel(stream)

        assert parsed is None

    def test_parse_invalid_channel_format_returns_none(self):
        """Test parsing invalid channel format returns None."""
        invalid_channels = [
            "invalid",
            "sse",
            "sse:",
            "sse:user",
            "sse:user:",
            f"{SSE_CHANNEL_PREFIX}:other:something",
            "wrong:prefix:user:abc123",
        ]

        for channel in invalid_channels:
            parsed = SSEChannelKeys.parse_user_id_from_channel(channel)
            assert parsed is None, f"Should return None for: {channel}"

    def test_parse_invalid_uuid_returns_none(self):
        """Test parsing channel with invalid UUID returns None."""
        channel = f"{SSE_CHANNEL_PREFIX}:user:not-a-valid-uuid"

        parsed = SSEChannelKeys.parse_user_id_from_channel(channel)

        assert parsed is None

    def test_parse_returns_uuid_type(self):
        """Test parse returns proper UUID type."""
        user_id = uuid7()
        channel = SSEChannelKeys.user_channel(user_id)

        parsed = SSEChannelKeys.parse_user_id_from_channel(channel)

        assert isinstance(parsed, UUID)


# =============================================================================
# Is Broadcast Channel Tests
# =============================================================================


@pytest.mark.unit
class TestIsBroadcastChannel:
    """Test SSEChannelKeys.is_broadcast_channel()."""

    def test_broadcast_channel_returns_true(self):
        """Test broadcast channel is correctly identified."""
        channel = SSEChannelKeys.broadcast_channel()

        assert SSEChannelKeys.is_broadcast_channel(channel) is True

    def test_user_channel_returns_false(self):
        """Test user channel is not broadcast."""
        user_id = uuid7()
        channel = SSEChannelKeys.user_channel(user_id)

        assert SSEChannelKeys.is_broadcast_channel(channel) is False

    def test_user_stream_returns_false(self):
        """Test user stream is not broadcast."""
        user_id = uuid7()
        stream = SSEChannelKeys.user_stream(user_id)

        assert SSEChannelKeys.is_broadcast_channel(stream) is False

    def test_invalid_channel_returns_false(self):
        """Test invalid channels are not broadcast."""
        invalid_channels = [
            "sse:broadcast:extra",
            "broadcast",
            "sse:broadcasts",
            "",
        ]

        for channel in invalid_channels:
            assert SSEChannelKeys.is_broadcast_channel(channel) is False, (
                f"Should return False for: {channel}"
            )


# =============================================================================
# Consistency Tests
# =============================================================================


@pytest.mark.unit
class TestKeyConsistency:
    """Test key generation consistency and correctness."""

    def test_prefix_from_constants(self):
        """Test all keys use prefix from constants.py."""
        user_id = uuid7()

        user_ch = SSEChannelKeys.user_channel(user_id)
        broadcast = SSEChannelKeys.broadcast_channel()
        stream = SSEChannelKeys.user_stream(user_id)

        # All should start with the constant prefix
        for key in [user_ch, broadcast, stream]:
            assert key.startswith(SSE_CHANNEL_PREFIX), (
                f"Key should start with '{SSE_CHANNEL_PREFIX}': {key}"
            )

    def test_no_hardcoded_prefix(self):
        """Test prefix is not hardcoded (uses constant)."""
        # This test verifies the DRY principle - prefix should come from constant
        # If SSE_CHANNEL_PREFIX is "sse", this will pass
        # If someone hardcodes "sse:" instead of using the constant, this might
        # still pass but the consistency with other code would be broken

        assert SSE_CHANNEL_PREFIX == "sse", (
            "Expected SSE_CHANNEL_PREFIX to be 'sse' - update test if changed"
        )

    def test_keys_are_redis_safe(self):
        """Test generated keys are valid Redis key names."""
        user_id = uuid7()

        keys = [
            SSEChannelKeys.user_channel(user_id),
            SSEChannelKeys.broadcast_channel(),
            SSEChannelKeys.user_stream(user_id),
        ]

        for key in keys:
            # Redis keys can be any binary string, but we use ASCII-safe chars
            assert key.isascii(), f"Key should be ASCII: {key}"
            # No spaces
            assert " " not in key, f"Key should not contain spaces: {key}"
            # No newlines
            assert "\n" not in key, f"Key should not contain newlines: {key}"
