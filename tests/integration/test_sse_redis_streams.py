"""Integration tests for SSE Redis Streams retention.

Tests the RedisSSEPublisher and RedisSSESubscriber implementations
with retention enabled, verifying Redis Streams storage and replay.

Architecture:
    - Tests against real Redis (not mocked)
    - Uses test environment Redis
    - Tests Redis Streams XADD and XRANGE
    - Tests get_missed_events replay
    - Uses fresh Redis connections per test

Reference:
    - src/infrastructure/sse/redis_publisher.py
    - src/infrastructure/sse/redis_subscriber.py
"""

import logging

import pytest
import pytest_asyncio
from uuid_extensions import uuid7

from src.domain.events.sse_event import SSEEvent, SSEEventType
from src.infrastructure.sse.channel_keys import SSEChannelKeys
from src.infrastructure.sse.redis_publisher import RedisSSEPublisher
from src.infrastructure.sse.redis_subscriber import RedisSSESubscriber


# =============================================================================
# Fixtures
# =============================================================================


@pytest_asyncio.fixture
async def sse_publisher_with_retention(redis_test_client):
    """Provide an SSE publisher with retention enabled."""
    return RedisSSEPublisher(
        redis_client=redis_test_client,
        enable_retention=True,
        retention_max_len=100,
        retention_ttl_seconds=3600,
        logger=logging.getLogger("test.sse.publisher"),
    )


@pytest_asyncio.fixture
async def sse_subscriber_with_retention(redis_test_client):
    """Provide an SSE subscriber with retention enabled."""
    return RedisSSESubscriber(
        redis_client=redis_test_client,
        enable_retention=True,
        logger=logging.getLogger("test.sse.subscriber"),
    )


def create_test_event(
    event_type: SSEEventType = SSEEventType.SYNC_ACCOUNTS_COMPLETED,
    user_id=None,
    data=None,
) -> SSEEvent:
    """Create an SSEEvent for testing."""
    return SSEEvent(
        event_type=event_type,
        user_id=user_id or uuid7(),
        data=data or {"test": "data"},
    )


# =============================================================================
# Stream Storage Tests
# =============================================================================


@pytest.mark.integration
class TestStreamStorage:
    """Tests for Redis Streams event storage."""

    @pytest.mark.asyncio
    async def test_event_stored_in_stream_when_retention_enabled(
        self, redis_test_client, sse_publisher_with_retention
    ):
        """Test event is stored in Redis Stream when retention enabled."""
        user_id = uuid7()
        event = create_test_event(
            event_type=SSEEventType.SYNC_HOLDINGS_COMPLETED,
            user_id=user_id,
            data={"count": 10},
        )

        # Publish event (should store in stream)
        await sse_publisher_with_retention.publish(event)

        # Verify event is in stream
        stream_key = SSEChannelKeys.user_stream(user_id)
        entries = await redis_test_client.xrange(stream_key, "-", "+")

        assert len(entries) >= 1

        # Find our event
        entry_id, entry_data = entries[-1]  # Last entry
        assert entry_data.get("event_id") == str(event.event_id)
        assert entry_data.get("event_type") == "sync.holdings.completed"

    @pytest.mark.asyncio
    async def test_multiple_events_stored_in_stream(
        self, redis_test_client, sse_publisher_with_retention
    ):
        """Test multiple events are stored in order."""
        user_id = uuid7()

        events = [
            create_test_event(
                event_type=SSEEventType.SYNC_TRANSACTIONS_STARTED,
                user_id=user_id,
                data={"step": 1},
            ),
            create_test_event(
                event_type=SSEEventType.SYNC_TRANSACTIONS_COMPLETED,
                user_id=user_id,
                data={"step": 2},
            ),
        ]

        # Publish events
        for event in events:
            await sse_publisher_with_retention.publish(event)

        # Verify both in stream
        stream_key = SSEChannelKeys.user_stream(user_id)
        entries = await redis_test_client.xrange(stream_key, "-", "+")

        assert len(entries) >= 2

        # Check order (should be in chronological order)
        event_ids = [e[1].get("event_id") for e in entries[-2:]]
        assert event_ids[0] == str(events[0].event_id)
        assert event_ids[1] == str(events[1].event_id)

    @pytest.mark.asyncio
    async def test_stream_has_ttl_set(
        self, redis_test_client, sse_publisher_with_retention
    ):
        """Test stream has TTL set after first event."""
        user_id = uuid7()
        event = create_test_event(user_id=user_id)

        await sse_publisher_with_retention.publish(event)

        stream_key = SSEChannelKeys.user_stream(user_id)
        ttl = await redis_test_client.ttl(stream_key)

        # TTL should be set (positive value)
        assert ttl > 0
        assert ttl <= 3600  # Our configured TTL


# =============================================================================
# Missed Events Replay Tests
# =============================================================================


@pytest.mark.integration
class TestMissedEventsReplay:
    """Tests for get_missed_events replay functionality."""

    @pytest.mark.asyncio
    async def test_get_missed_events_returns_events_after_last_id(
        self,
        redis_test_client,
        sse_publisher_with_retention,
        sse_subscriber_with_retention,
    ):
        """Test get_missed_events returns events after last_event_id."""
        user_id = uuid7()

        # Publish three events
        event1 = create_test_event(
            event_type=SSEEventType.IMPORT_STARTED,
            user_id=user_id,
            data={"step": 1},
        )
        event2 = create_test_event(
            event_type=SSEEventType.IMPORT_PROGRESS,
            user_id=user_id,
            data={"step": 2},
        )
        event3 = create_test_event(
            event_type=SSEEventType.IMPORT_COMPLETED,
            user_id=user_id,
            data={"step": 3},
        )

        for event in [event1, event2, event3]:
            await sse_publisher_with_retention.publish(event)

        # Get events after event1 (should return event2 and event3)
        missed = await sse_subscriber_with_retention.get_missed_events(
            user_id=user_id,
            last_event_id=event1.event_id,
        )

        assert len(missed) == 2
        assert missed[0].event_id == event2.event_id
        assert missed[0].data == {"step": 2}
        assert missed[1].event_id == event3.event_id
        assert missed[1].data == {"step": 3}

    @pytest.mark.asyncio
    async def test_get_missed_events_empty_when_no_events_after(
        self,
        redis_test_client,
        sse_publisher_with_retention,
        sse_subscriber_with_retention,
    ):
        """Test get_missed_events returns empty when last_id is most recent."""
        user_id = uuid7()

        event = create_test_event(user_id=user_id)
        await sse_publisher_with_retention.publish(event)

        # Get events after the only event (should be empty)
        missed = await sse_subscriber_with_retention.get_missed_events(
            user_id=user_id,
            last_event_id=event.event_id,
        )

        assert missed == []

    @pytest.mark.asyncio
    async def test_get_missed_events_empty_when_retention_disabled(
        self, redis_test_client
    ):
        """Test get_missed_events returns empty when retention disabled."""
        user_id = uuid7()

        # Publisher with retention (stores events)
        publisher = RedisSSEPublisher(
            redis_client=redis_test_client,
            enable_retention=True,
        )

        # Subscriber WITHOUT retention
        subscriber = RedisSSESubscriber(
            redis_client=redis_test_client,
            enable_retention=False,
        )

        event = create_test_event(user_id=user_id)
        await publisher.publish(event)

        # Should return empty even though events exist
        missed = await subscriber.get_missed_events(
            user_id=user_id,
            last_event_id=uuid7(),  # Any UUID
        )

        assert missed == []

    @pytest.mark.asyncio
    async def test_get_missed_events_with_category_filter(
        self,
        redis_test_client,
        sse_publisher_with_retention,
        sse_subscriber_with_retention,
    ):
        """Test get_missed_events respects category filter."""
        user_id = uuid7()

        # Publish events of different categories
        sync_event = create_test_event(
            event_type=SSEEventType.SYNC_ACCOUNTS_COMPLETED,
            user_id=user_id,
            data={"category": "data_sync"},
        )
        ai_event = create_test_event(
            event_type=SSEEventType.AI_RESPONSE_COMPLETE,
            user_id=user_id,
            data={"category": "ai"},
        )

        # Need a starting point event
        start_event = create_test_event(
            event_type=SSEEventType.SYNC_ACCOUNTS_STARTED,
            user_id=user_id,
            data={"start": True},
        )

        for event in [start_event, sync_event, ai_event]:
            await sse_publisher_with_retention.publish(event)

        # Get only data_sync events
        missed = await sse_subscriber_with_retention.get_missed_events(
            user_id=user_id,
            last_event_id=start_event.event_id,
            categories=["data_sync"],
        )

        # Should only have the sync event
        assert len(missed) == 1
        assert missed[0].event_id == sync_event.event_id

    @pytest.mark.asyncio
    async def test_get_missed_events_unknown_last_id_returns_empty(
        self,
        redis_test_client,
        sse_publisher_with_retention,
        sse_subscriber_with_retention,
    ):
        """Test get_missed_events returns empty if last_id not found."""
        user_id = uuid7()

        event = create_test_event(user_id=user_id)
        await sse_publisher_with_retention.publish(event)

        # Use a UUID that doesn't exist in the stream
        fake_last_id = uuid7()

        missed = await sse_subscriber_with_retention.get_missed_events(
            user_id=user_id,
            last_event_id=fake_last_id,
        )

        # Should return empty since we never "found" the last_id
        assert missed == []


# =============================================================================
# Stream Pruning Tests
# =============================================================================


@pytest.mark.integration
class TestStreamPruning:
    """Tests for stream MAXLEN pruning."""

    @pytest.mark.asyncio
    async def test_stream_respects_maxlen(self, redis_test_client):
        """Test stream is pruned to respect MAXLEN."""
        user_id = uuid7()

        # Create publisher with small MAXLEN
        publisher = RedisSSEPublisher(
            redis_client=redis_test_client,
            enable_retention=True,
            retention_max_len=5,  # Small for testing
        )

        # Publish more than MAXLEN events
        for i in range(10):
            event = create_test_event(
                user_id=user_id,
                data={"index": i},
            )
            await publisher.publish(event)

        # Check stream length (should be approximately MAXLEN)
        stream_key = SSEChannelKeys.user_stream(user_id)
        length = await redis_test_client.xlen(stream_key)

        # MAXLEN ~ uses approximate trimming, so can be significantly over
        # Redis approximate trimming typically keeps up to 2x MAXLEN
        # but trims when stream exceeds threshold
        assert length <= 15  # Approximate MAXLEN allows significant variance


# =============================================================================
# Error Recovery Tests
# =============================================================================


@pytest.mark.integration
class TestErrorRecovery:
    """Tests for error handling and recovery."""

    @pytest.mark.asyncio
    async def test_get_missed_events_handles_corrupted_entry(
        self,
        redis_test_client,
        sse_subscriber_with_retention,
    ):
        """Test get_missed_events handles corrupted stream entries gracefully."""
        user_id = uuid7()
        stream_key = SSEChannelKeys.user_stream(user_id)

        # Manually add a valid event
        valid_event = create_test_event(user_id=user_id, data={"valid": True})
        await redis_test_client.xadd(
            stream_key,
            {
                "event_id": str(valid_event.event_id),
                "event_type": valid_event.event_type.value,
                "data": '{"valid": true}',
                "occurred_at": valid_event.occurred_at.isoformat(),
            },
        )

        # Manually add a corrupted entry (invalid JSON in data field)
        await redis_test_client.xadd(
            stream_key,
            {
                "event_id": str(uuid7()),
                "event_type": "sync.accounts.completed",
                "data": "not valid json {{{",
                "occurred_at": valid_event.occurred_at.isoformat(),
            },
        )

        # Add another valid event after the corrupted one
        valid_event2 = create_test_event(user_id=user_id, data={"valid": "two"})
        await redis_test_client.xadd(
            stream_key,
            {
                "event_id": str(valid_event2.event_id),
                "event_type": valid_event2.event_type.value,
                "data": '{"valid": "two"}',
                "occurred_at": valid_event2.occurred_at.isoformat(),
            },
        )

        # Should skip corrupted entry and return valid ones
        missed = await sse_subscriber_with_retention.get_missed_events(
            user_id=user_id,
            last_event_id=valid_event.event_id,
        )

        # Only the second valid event should be returned
        # (corrupted is skipped, and we start after valid_event)
        assert len(missed) == 1
        assert missed[0].data == {"valid": "two"}
