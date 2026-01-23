"""Integration tests for SSE security multi-device delivery.

Tests the security notification flow through Redis pub/sub, verifying
that security events are properly delivered to all of a user's
active SSE connections (multi-device notification).

Architecture:
    - Tests against real Redis (not mocked)
    - Uses test environment Redis
    - Tests security event pub/sub delivery
    - Tests multi-device (multiple subscribers) notification
    - Tests category filtering for security events

Reference:
    - docs/architecture/sse-architecture.md Section 3.6
    - GitHub Issue #258
"""

import asyncio
import logging

import pytest
import pytest_asyncio
from uuid_extensions import uuid7

from src.domain.events.sse_event import SSEEvent, SSEEventType
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
        logger=logging.getLogger("test.sse.security.publisher"),
    )


@pytest_asyncio.fixture
async def sse_subscriber(redis_test_client):
    """Provide an SSE subscriber for each test."""
    return RedisSSESubscriber(
        redis_client=redis_test_client,
        enable_retention=False,
        logger=logging.getLogger("test.sse.security.subscriber"),
    )


@pytest_asyncio.fixture
async def sse_subscriber_2(redis_test_client):
    """Provide a second SSE subscriber for multi-device tests."""
    return RedisSSESubscriber(
        redis_client=redis_test_client,
        enable_retention=False,
        logger=logging.getLogger("test.sse.security.subscriber2"),
    )


def create_security_event(
    event_type: SSEEventType,
    user_id=None,
    data=None,
) -> SSEEvent:
    """Create a security SSEEvent for testing."""
    return SSEEvent(
        event_type=event_type,
        user_id=user_id or uuid7(),
        data=data or {},
    )


# =============================================================================
# Security Event Delivery Tests
# =============================================================================


@pytest.mark.integration
class TestSecurityEventDelivery:
    """Test security events are delivered through pub/sub."""

    @pytest.mark.asyncio
    async def test_session_new_event_delivered(
        self, redis_test_client, sse_publisher, sse_subscriber
    ):
        """Test SECURITY_SESSION_NEW event is delivered to user."""
        user_id = uuid7()
        session_id = uuid7()
        event = create_security_event(
            event_type=SSEEventType.SECURITY_SESSION_NEW,
            user_id=user_id,
            data={
                "session_id": str(session_id),
                "device_info": "Chrome on macOS",
                "location": "New York, US",
            },
        )

        received_events: list[SSEEvent] = []

        async def collect_events():
            async for e in sse_subscriber.subscribe(user_id):
                received_events.append(e)
                break

        subscriber_task = asyncio.create_task(collect_events())
        await asyncio.sleep(0.1)

        await sse_publisher.publish(event)

        try:
            await asyncio.wait_for(subscriber_task, timeout=2.0)
        except asyncio.TimeoutError:
            subscriber_task.cancel()
            try:
                await subscriber_task
            except asyncio.CancelledError:
                pass

        assert len(received_events) == 1
        received = received_events[0]
        assert received.event_type == SSEEventType.SECURITY_SESSION_NEW
        assert received.data["session_id"] == str(session_id)
        assert received.data["device_info"] == "Chrome on macOS"

    @pytest.mark.asyncio
    async def test_session_revoked_event_delivered(
        self, redis_test_client, sse_publisher, sse_subscriber
    ):
        """Test SECURITY_SESSION_REVOKED event is delivered to user."""
        user_id = uuid7()
        session_id = uuid7()
        event = create_security_event(
            event_type=SSEEventType.SECURITY_SESSION_REVOKED,
            user_id=user_id,
            data={
                "session_id": str(session_id),
                "device_info": "Firefox on Windows",
                "reason": "password_changed",
            },
        )

        received_events: list[SSEEvent] = []

        async def collect_events():
            async for e in sse_subscriber.subscribe(user_id):
                received_events.append(e)
                break

        subscriber_task = asyncio.create_task(collect_events())
        await asyncio.sleep(0.1)

        await sse_publisher.publish(event)

        try:
            await asyncio.wait_for(subscriber_task, timeout=2.0)
        except asyncio.TimeoutError:
            subscriber_task.cancel()
            try:
                await subscriber_task
            except asyncio.CancelledError:
                pass

        assert len(received_events) == 1
        received = received_events[0]
        assert received.event_type == SSEEventType.SECURITY_SESSION_REVOKED
        assert received.data["reason"] == "password_changed"

    @pytest.mark.asyncio
    async def test_password_changed_event_delivered(
        self, redis_test_client, sse_publisher, sse_subscriber
    ):
        """Test SECURITY_PASSWORD_CHANGED event is delivered to user."""
        user_id = uuid7()
        event = create_security_event(
            event_type=SSEEventType.SECURITY_PASSWORD_CHANGED,
            user_id=user_id,
            data={"initiated_by": "user"},
        )

        received_events: list[SSEEvent] = []

        async def collect_events():
            async for e in sse_subscriber.subscribe(user_id):
                received_events.append(e)
                break

        subscriber_task = asyncio.create_task(collect_events())
        await asyncio.sleep(0.1)

        await sse_publisher.publish(event)

        try:
            await asyncio.wait_for(subscriber_task, timeout=2.0)
        except asyncio.TimeoutError:
            subscriber_task.cancel()
            try:
                await subscriber_task
            except asyncio.CancelledError:
                pass

        assert len(received_events) == 1
        received = received_events[0]
        assert received.event_type == SSEEventType.SECURITY_PASSWORD_CHANGED
        assert received.data["initiated_by"] == "user"

    @pytest.mark.asyncio
    async def test_login_failed_event_delivered(
        self, redis_test_client, sse_publisher, sse_subscriber
    ):
        """Test SECURITY_LOGIN_FAILED event is delivered to user."""
        user_id = uuid7()
        event = create_security_event(
            event_type=SSEEventType.SECURITY_LOGIN_FAILED,
            user_id=user_id,
            data={"reason": "invalid_credentials"},
        )

        received_events: list[SSEEvent] = []

        async def collect_events():
            async for e in sse_subscriber.subscribe(user_id):
                received_events.append(e)
                break

        subscriber_task = asyncio.create_task(collect_events())
        await asyncio.sleep(0.1)

        await sse_publisher.publish(event)

        try:
            await asyncio.wait_for(subscriber_task, timeout=2.0)
        except asyncio.TimeoutError:
            subscriber_task.cancel()
            try:
                await subscriber_task
            except asyncio.CancelledError:
                pass

        assert len(received_events) == 1
        received = received_events[0]
        assert received.event_type == SSEEventType.SECURITY_LOGIN_FAILED
        assert received.data["reason"] == "invalid_credentials"

    @pytest.mark.asyncio
    async def test_suspicious_activity_event_delivered(
        self, redis_test_client, sse_publisher, sse_subscriber
    ):
        """Test SECURITY_SESSION_SUSPICIOUS event is delivered to user."""
        user_id = uuid7()
        session_id = uuid7()
        event = create_security_event(
            event_type=SSEEventType.SECURITY_SESSION_SUSPICIOUS,
            user_id=user_id,
            data={
                "session_id": str(session_id),
                "reason": "ip_change",
            },
        )

        received_events: list[SSEEvent] = []

        async def collect_events():
            async for e in sse_subscriber.subscribe(user_id):
                received_events.append(e)
                break

        subscriber_task = asyncio.create_task(collect_events())
        await asyncio.sleep(0.1)

        await sse_publisher.publish(event)

        try:
            await asyncio.wait_for(subscriber_task, timeout=2.0)
        except asyncio.TimeoutError:
            subscriber_task.cancel()
            try:
                await subscriber_task
            except asyncio.CancelledError:
                pass

        assert len(received_events) == 1
        received = received_events[0]
        assert received.event_type == SSEEventType.SECURITY_SESSION_SUSPICIOUS
        assert received.data["reason"] == "ip_change"


# =============================================================================
# Multi-Device Notification Tests
# =============================================================================


@pytest.mark.integration
class TestMultiDeviceNotification:
    """Test security events are delivered to multiple devices (subscribers)."""

    @pytest.mark.asyncio
    async def test_security_event_delivered_to_multiple_subscribers(
        self, redis_test_client, sse_publisher, sse_subscriber, sse_subscriber_2
    ):
        """Test security event reaches all user's active SSE connections.

        Simulates a user logged in on multiple devices (phone, laptop).
        When a security event occurs, all devices should receive it.
        """
        user_id = uuid7()
        event = create_security_event(
            event_type=SSEEventType.SECURITY_PASSWORD_CHANGED,
            user_id=user_id,
            data={"initiated_by": "user"},
        )

        received_by_device1: list[SSEEvent] = []
        received_by_device2: list[SSEEvent] = []

        async def collect_device1_events():
            async for e in sse_subscriber.subscribe(user_id):
                received_by_device1.append(e)
                break

        async def collect_device2_events():
            async for e in sse_subscriber_2.subscribe(user_id):
                received_by_device2.append(e)
                break

        # Start both subscribers (simulating two devices)
        task1 = asyncio.create_task(collect_device1_events())
        task2 = asyncio.create_task(collect_device2_events())
        await asyncio.sleep(0.1)

        # Publish security event
        await sse_publisher.publish(event)

        # Wait for both to receive
        try:
            await asyncio.wait_for(
                asyncio.gather(task1, task2, return_exceptions=True),
                timeout=2.0,
            )
        except asyncio.TimeoutError:
            for task in [task1, task2]:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        # Both devices should receive the event
        assert len(received_by_device1) == 1
        assert len(received_by_device2) == 1
        assert (
            received_by_device1[0].event_type == SSEEventType.SECURITY_PASSWORD_CHANGED
        )
        assert (
            received_by_device2[0].event_type == SSEEventType.SECURITY_PASSWORD_CHANGED
        )

    @pytest.mark.asyncio
    async def test_session_revoked_notifies_other_devices(
        self, redis_test_client, sse_publisher, sse_subscriber, sse_subscriber_2
    ):
        """Test session revocation event notifies other active sessions.

        When user revokes a session (e.g., logout from one device),
        other active sessions should be notified.
        """
        user_id = uuid7()
        revoked_session_id = uuid7()

        event = create_security_event(
            event_type=SSEEventType.SECURITY_SESSION_REVOKED,
            user_id=user_id,
            data={
                "session_id": str(revoked_session_id),
                "device_info": "Safari on iPhone",
                "reason": "user_logout",
            },
        )

        received_by_device1: list[SSEEvent] = []
        received_by_device2: list[SSEEvent] = []

        async def collect_device1_events():
            async for e in sse_subscriber.subscribe(user_id):
                received_by_device1.append(e)
                break

        async def collect_device2_events():
            async for e in sse_subscriber_2.subscribe(user_id):
                received_by_device2.append(e)
                break

        task1 = asyncio.create_task(collect_device1_events())
        task2 = asyncio.create_task(collect_device2_events())
        await asyncio.sleep(0.1)

        await sse_publisher.publish(event)

        try:
            await asyncio.wait_for(
                asyncio.gather(task1, task2, return_exceptions=True),
                timeout=2.0,
            )
        except asyncio.TimeoutError:
            for task in [task1, task2]:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        # Both devices receive notification about the revoked session
        assert len(received_by_device1) == 1
        assert len(received_by_device2) == 1
        assert received_by_device1[0].data["session_id"] == str(revoked_session_id)


# =============================================================================
# Category Filtering Tests
# =============================================================================


@pytest.mark.integration
class TestSecurityCategoryFiltering:
    """Test security events are properly filtered by category."""

    @pytest.mark.asyncio
    async def test_security_category_filter_passes_security_events(
        self, redis_test_client, sse_publisher, sse_subscriber
    ):
        """Test security category filter passes security events."""
        user_id = uuid7()
        security_event = create_security_event(
            event_type=SSEEventType.SECURITY_SESSION_NEW,
            user_id=user_id,
            data={"session_id": str(uuid7())},
        )

        received_events: list[SSEEvent] = []

        async def collect_events():
            # Only subscribe to security category
            async for e in sse_subscriber.subscribe(user_id, categories=["security"]):
                received_events.append(e)
                break

        subscriber_task = asyncio.create_task(collect_events())
        await asyncio.sleep(0.1)

        await sse_publisher.publish(security_event)

        try:
            await asyncio.wait_for(subscriber_task, timeout=2.0)
        except asyncio.TimeoutError:
            subscriber_task.cancel()
            try:
                await subscriber_task
            except asyncio.CancelledError:
                pass

        # Security event should be received
        assert len(received_events) == 1
        assert received_events[0].event_type == SSEEventType.SECURITY_SESSION_NEW

    @pytest.mark.asyncio
    async def test_security_category_filter_rejects_other_events(
        self, redis_test_client, sse_publisher, sse_subscriber
    ):
        """Test security category filter rejects non-security events."""
        user_id = uuid7()

        # Non-security event
        sync_event = create_security_event(
            event_type=SSEEventType.SYNC_ACCOUNTS_COMPLETED,
            user_id=user_id,
            data={"account_count": 5},
        )

        # Security event (will be sent after)
        security_event = create_security_event(
            event_type=SSEEventType.SECURITY_PASSWORD_CHANGED,
            user_id=user_id,
            data={"initiated_by": "user"},
        )

        received_events: list[SSEEvent] = []

        async def collect_events():
            # Only subscribe to security category
            async for e in sse_subscriber.subscribe(user_id, categories=["security"]):
                received_events.append(e)
                # Stop after first event
                break

        subscriber_task = asyncio.create_task(collect_events())
        await asyncio.sleep(0.1)

        # Publish sync event (should be filtered out)
        await sse_publisher.publish(sync_event)
        await asyncio.sleep(0.05)

        # Publish security event (should be received)
        await sse_publisher.publish(security_event)

        try:
            await asyncio.wait_for(subscriber_task, timeout=2.0)
        except asyncio.TimeoutError:
            subscriber_task.cancel()
            try:
                await subscriber_task
            except asyncio.CancelledError:
                pass

        # Only security event should be received
        assert len(received_events) == 1
        assert received_events[0].event_type == SSEEventType.SECURITY_PASSWORD_CHANGED

    @pytest.mark.asyncio
    async def test_no_filter_receives_all_security_events(
        self, redis_test_client, sse_publisher, sse_subscriber
    ):
        """Test subscriber without filter receives all events including security."""
        user_id = uuid7()

        events_to_send = [
            create_security_event(
                event_type=SSEEventType.SYNC_ACCOUNTS_COMPLETED,
                user_id=user_id,
                data={"type": "sync"},
            ),
            create_security_event(
                event_type=SSEEventType.SECURITY_SESSION_NEW,
                user_id=user_id,
                data={"type": "security"},
            ),
        ]

        received_events: list[SSEEvent] = []

        async def collect_events():
            # No category filter - receive all events
            async for e in sse_subscriber.subscribe(user_id):
                received_events.append(e)
                if len(received_events) >= 2:
                    break

        subscriber_task = asyncio.create_task(collect_events())
        await asyncio.sleep(0.1)

        for event in events_to_send:
            await sse_publisher.publish(event)
            await asyncio.sleep(0.01)

        try:
            await asyncio.wait_for(subscriber_task, timeout=2.0)
        except asyncio.TimeoutError:
            subscriber_task.cancel()
            try:
                await subscriber_task
            except asyncio.CancelledError:
                pass

        # Both events should be received
        assert len(received_events) == 2
        event_types = {e.event_type for e in received_events}
        assert SSEEventType.SYNC_ACCOUNTS_COMPLETED in event_types
        assert SSEEventType.SECURITY_SESSION_NEW in event_types
