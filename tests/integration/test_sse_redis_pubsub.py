"""Integration tests for SSE Redis pub/sub.

Tests the RedisSSEPublisher and RedisSSESubscriber implementations
against a real Redis instance, verifying pub/sub round-trip delivery.

Architecture:
    - Tests against real Redis (not mocked)
    - Uses test environment Redis
    - Tests pub/sub event delivery
    - Tests broadcast channel
    - Tests category filtering
    - Uses fresh Redis connections per test (bypasses singleton)

Reference:
    - src/infrastructure/sse/redis_publisher.py
    - src/infrastructure/sse/redis_subscriber.py
"""

import asyncio
import logging

import pytest
import pytest_asyncio
from uuid_extensions import uuid7

from src.domain.events.sse_event import SSEEvent, SSEEventCategory, SSEEventType
from src.infrastructure.sse.redis_publisher import RedisSSEPublisher
from src.infrastructure.sse.redis_subscriber import RedisSSESubscriber


# =============================================================================
# Fixtures
# =============================================================================


@pytest_asyncio.fixture
async def sse_publisher(redis_test_client):
    """Provide an SSE publisher for each test."""
    return RedisSSEPublisher(
        redis_client=redis_test_client,
        enable_retention=False,
        logger=logging.getLogger("test.sse.publisher"),
    )


@pytest_asyncio.fixture
async def sse_subscriber(redis_test_client):
    """Provide an SSE subscriber for each test."""
    return RedisSSESubscriber(
        redis_client=redis_test_client,
        enable_retention=False,
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
# Publisher Tests
# =============================================================================


@pytest.mark.integration
class TestSSEPublisher:
    """Integration tests for RedisSSEPublisher."""

    @pytest.mark.asyncio
    async def test_publish_does_not_raise(self, sse_publisher):
        """Test publish completes without raising."""
        event = create_test_event()
        # Should not raise - fail-open design
        await sse_publisher.publish(event)

    @pytest.mark.asyncio
    async def test_publish_to_user_does_not_raise(self, sse_publisher):
        """Test publish_to_user completes without raising."""
        user_id = uuid7()
        event = create_test_event(user_id=user_id)
        await sse_publisher.publish_to_user(user_id, event)

    @pytest.mark.asyncio
    async def test_broadcast_does_not_raise(self, sse_publisher):
        """Test broadcast completes without raising."""
        event = create_test_event()
        await sse_publisher.broadcast(event)


# =============================================================================
# Subscriber Tests
# =============================================================================


@pytest.mark.integration
class TestSSESubscriber:
    """Integration tests for RedisSSESubscriber."""

    @pytest.mark.asyncio
    async def test_validate_categories_valid(self, sse_subscriber):
        """Test category validation with valid categories."""
        categories = ["data_sync", "provider"]
        result = sse_subscriber.validate_categories(categories)

        assert len(result) == 2
        assert SSEEventCategory.DATA_SYNC in result
        assert SSEEventCategory.PROVIDER in result

    @pytest.mark.asyncio
    async def test_validate_categories_invalid_raises(self, sse_subscriber):
        """Test category validation raises for invalid category."""
        with pytest.raises(ValueError) as exc_info:
            sse_subscriber.validate_categories(["invalid_category"])

        assert "Invalid category" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_validate_categories_none_returns_empty(self, sse_subscriber):
        """Test category validation with None returns empty list."""
        result = sse_subscriber.validate_categories(None)
        assert result == []

    @pytest.mark.asyncio
    async def test_filter_by_categories_none_passes_all(self, sse_subscriber):
        """Test filter passes all events when categories is None."""
        event = create_test_event(event_type=SSEEventType.AI_RESPONSE_CHUNK)
        assert sse_subscriber.filter_by_categories(event, None) is True

    @pytest.mark.asyncio
    async def test_filter_by_categories_matches(self, sse_subscriber):
        """Test filter passes events matching category."""
        event = create_test_event(event_type=SSEEventType.SYNC_ACCOUNTS_COMPLETED)
        assert sse_subscriber.filter_by_categories(event, ["data_sync"]) is True

    @pytest.mark.asyncio
    async def test_filter_by_categories_rejects(self, sse_subscriber):
        """Test filter rejects events not in category."""
        event = create_test_event(event_type=SSEEventType.AI_RESPONSE_CHUNK)
        assert sse_subscriber.filter_by_categories(event, ["data_sync"]) is False


# =============================================================================
# Pub/Sub Round-Trip Tests
# =============================================================================


@pytest.mark.integration
class TestPubSubRoundTrip:
    """Integration tests for pub/sub round-trip delivery."""

    @pytest.mark.asyncio
    async def test_pubsub_roundtrip_single_event(
        self, redis_test_client, sse_publisher, sse_subscriber
    ):
        """Test single event is delivered via pub/sub."""
        user_id = uuid7()
        event = create_test_event(
            event_type=SSEEventType.SYNC_TRANSACTIONS_COMPLETED,
            user_id=user_id,
            data={"count": 42},
        )

        received_events: list[SSEEvent] = []

        async def collect_events():
            async for e in sse_subscriber.subscribe(user_id):
                received_events.append(e)
                # Stop after first event
                break

        # Start subscriber in background
        subscriber_task = asyncio.create_task(collect_events())

        # Give subscriber time to connect
        await asyncio.sleep(0.1)

        # Publish event
        await sse_publisher.publish(event)

        # Wait for event to be received (with timeout)
        try:
            await asyncio.wait_for(subscriber_task, timeout=2.0)
        except asyncio.TimeoutError:
            subscriber_task.cancel()
            try:
                await subscriber_task
            except asyncio.CancelledError:
                pass

        # Verify event was received
        assert len(received_events) == 1
        received = received_events[0]
        assert received.event_type == SSEEventType.SYNC_TRANSACTIONS_COMPLETED
        assert received.data == {"count": 42}
        assert received.event_id == event.event_id

    @pytest.mark.asyncio
    async def test_pubsub_roundtrip_multiple_events(
        self, redis_test_client, sse_publisher, sse_subscriber
    ):
        """Test multiple events are delivered in order."""
        user_id = uuid7()
        events_to_send = [
            create_test_event(
                event_type=SSEEventType.SYNC_ACCOUNTS_STARTED,
                user_id=user_id,
                data={"step": 1},
            ),
            create_test_event(
                event_type=SSEEventType.SYNC_ACCOUNTS_COMPLETED,
                user_id=user_id,
                data={"step": 2},
            ),
        ]

        received_events: list[SSEEvent] = []

        async def collect_events():
            async for e in sse_subscriber.subscribe(user_id):
                received_events.append(e)
                if len(received_events) >= 2:
                    break

        subscriber_task = asyncio.create_task(collect_events())
        await asyncio.sleep(0.1)

        # Publish events
        for event in events_to_send:
            await sse_publisher.publish(event)
            await asyncio.sleep(0.01)  # Small delay between publishes

        try:
            await asyncio.wait_for(subscriber_task, timeout=2.0)
        except asyncio.TimeoutError:
            subscriber_task.cancel()
            try:
                await subscriber_task
            except asyncio.CancelledError:
                pass

        # Verify both events received
        assert len(received_events) == 2
        assert received_events[0].data == {"step": 1}
        assert received_events[1].data == {"step": 2}

    @pytest.mark.asyncio
    async def test_pubsub_category_filtering(
        self, redis_test_client, sse_publisher, sse_subscriber
    ):
        """Test subscriber only receives events matching category filter."""
        user_id = uuid7()

        # Events of different categories
        sync_event = create_test_event(
            event_type=SSEEventType.SYNC_ACCOUNTS_COMPLETED,
            user_id=user_id,
            data={"category": "data_sync"},
        )
        ai_event = create_test_event(
            event_type=SSEEventType.AI_RESPONSE_CHUNK,
            user_id=user_id,
            data={"category": "ai"},
        )

        received_events: list[SSEEvent] = []

        async def collect_events():
            # Only subscribe to data_sync category
            async for e in sse_subscriber.subscribe(user_id, categories=["data_sync"]):
                received_events.append(e)
                # We only expect one event, but give time for both to arrive
                if len(received_events) >= 1:
                    # Wait a bit to ensure ai_event doesn't arrive
                    await asyncio.sleep(0.1)
                    break

        subscriber_task = asyncio.create_task(collect_events())
        await asyncio.sleep(0.1)

        # Publish both events
        await sse_publisher.publish(ai_event)  # Should be filtered out
        await sse_publisher.publish(sync_event)  # Should be received

        try:
            await asyncio.wait_for(subscriber_task, timeout=2.0)
        except asyncio.TimeoutError:
            subscriber_task.cancel()
            try:
                await subscriber_task
            except asyncio.CancelledError:
                pass

        # Only sync event should be received
        assert len(received_events) == 1
        assert received_events[0].data == {"category": "data_sync"}

    @pytest.mark.asyncio
    async def test_broadcast_received_by_subscriber(
        self, redis_test_client, sse_publisher, sse_subscriber
    ):
        """Test broadcast events are received by subscriber."""
        user_id = uuid7()
        event = create_test_event(
            event_type=SSEEventType.SECURITY_SESSION_EXPIRING,
            user_id=uuid7(),  # Different user - but broadcast should still arrive
            data={"broadcast": True},
        )

        received_events: list[SSEEvent] = []

        async def collect_events():
            async for e in sse_subscriber.subscribe(user_id):
                received_events.append(e)
                break

        subscriber_task = asyncio.create_task(collect_events())
        await asyncio.sleep(0.1)

        # Broadcast (not publish to specific user)
        await sse_publisher.broadcast(event)

        try:
            await asyncio.wait_for(subscriber_task, timeout=2.0)
        except asyncio.TimeoutError:
            subscriber_task.cancel()
            try:
                await subscriber_task
            except asyncio.CancelledError:
                pass

        # Broadcast should be received
        assert len(received_events) == 1
        assert received_events[0].data == {"broadcast": True}

    @pytest.mark.asyncio
    async def test_event_isolation_between_users(
        self, redis_test_client, sse_publisher, sse_subscriber
    ):
        """Test events for one user are not received by another."""
        user1 = uuid7()
        user2 = uuid7()

        event_for_user1 = create_test_event(
            event_type=SSEEventType.SYNC_ACCOUNTS_COMPLETED,
            user_id=user1,
            data={"for": "user1"},
        )

        received_by_user2: list[SSEEvent] = []
        no_event_received = True

        async def collect_user2_events():
            nonlocal no_event_received
            async for e in sse_subscriber.subscribe(user2):
                received_by_user2.append(e)
                no_event_received = False
                break

        # Subscribe as user2
        subscriber_task = asyncio.create_task(collect_user2_events())
        await asyncio.sleep(0.1)

        # Publish to user1 (user2 should NOT receive)
        await sse_publisher.publish(event_for_user1)

        # Wait briefly - user2 should NOT receive anything
        try:
            await asyncio.wait_for(subscriber_task, timeout=0.5)
        except asyncio.TimeoutError:
            # Expected - no event should arrive
            subscriber_task.cancel()
            try:
                await subscriber_task
            except asyncio.CancelledError:
                pass

        # User2 should not have received user1's event
        assert len(received_by_user2) == 0
        assert no_event_received is True


# =============================================================================
# Error Handling Tests
# =============================================================================


@pytest.mark.integration
class TestErrorHandling:
    """Test error handling in pub/sub operations."""

    @pytest.mark.asyncio
    async def test_publisher_fail_open_on_invalid_redis(self):
        """Test publisher doesn't raise even with bad Redis connection."""
        from redis.asyncio import Redis

        # Create publisher with disconnected client
        # (Connection will fail but publisher should not raise)
        bad_client: Redis[bytes] = Redis.from_url(  # type: ignore[type-arg]
            "redis://nonexistent-host:6379",
            socket_connect_timeout=0.1,
        )
        publisher = RedisSSEPublisher(
            redis_client=bad_client,
            logger=logging.getLogger("test.fail"),
        )

        event = create_test_event()

        # Should not raise (fail-open)
        await publisher.publish(event)
        await publisher.broadcast(event)

        await bad_client.aclose()
