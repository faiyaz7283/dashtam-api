"""Integration tests for SSE Portfolio event delivery.

Tests the portfolio notification flow through Redis pub/sub, verifying
that portfolio events are properly delivered to the user's active SSE
connections.

Architecture:
    - Tests against real Redis (not mocked)
    - Uses test environment Redis
    - Tests portfolio event pub/sub delivery
    - Tests category filtering for portfolio events
    - Tests all 3 portfolio event types

Reference:
    - docs/architecture/sse-architecture.md
    - GitHub Issue #257
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
        logger=logging.getLogger("test.sse.portfolio.publisher"),
    )


@pytest_asyncio.fixture
async def sse_subscriber(redis_test_client):
    """Provide an SSE subscriber for each test."""
    return RedisSSESubscriber(
        redis_client=redis_test_client,
        enable_retention=False,
        logger=logging.getLogger("test.sse.portfolio.subscriber"),
    )


def create_portfolio_event(
    event_type: SSEEventType,
    user_id=None,
    data=None,
) -> SSEEvent:
    """Create a portfolio SSEEvent for testing."""
    return SSEEvent(
        event_type=event_type,
        user_id=user_id or uuid7(),
        data=data or {},
    )


# =============================================================================
# Portfolio Event Delivery Tests
# =============================================================================


@pytest.mark.integration
class TestPortfolioEventDelivery:
    """Test portfolio events are delivered through pub/sub."""

    @pytest.mark.asyncio
    async def test_balance_updated_event_delivered(
        self, redis_test_client, sse_publisher, sse_subscriber
    ):
        """Test PORTFOLIO_BALANCE_UPDATED event is delivered to user."""
        user_id = uuid7()
        account_id = uuid7()
        event = create_portfolio_event(
            event_type=SSEEventType.PORTFOLIO_BALANCE_UPDATED,
            user_id=user_id,
            data={
                "account_id": str(account_id),
                "previous_balance": "1000.00",
                "new_balance": "1500.00",
                "delta": "500.00",
                "currency": "USD",
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
        assert received.event_type == SSEEventType.PORTFOLIO_BALANCE_UPDATED
        assert received.data["account_id"] == str(account_id)
        assert received.data["new_balance"] == "1500.00"
        assert received.data["delta"] == "500.00"

    @pytest.mark.asyncio
    async def test_holdings_updated_event_delivered(
        self, redis_test_client, sse_publisher, sse_subscriber
    ):
        """Test PORTFOLIO_HOLDINGS_UPDATED event is delivered to user."""
        user_id = uuid7()
        account_id = uuid7()
        event = create_portfolio_event(
            event_type=SSEEventType.PORTFOLIO_HOLDINGS_UPDATED,
            user_id=user_id,
            data={
                "account_id": str(account_id),
                "holdings_count": 15,
                "created_count": 3,
                "updated_count": 10,
                "deactivated_count": 2,
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
        assert received.event_type == SSEEventType.PORTFOLIO_HOLDINGS_UPDATED
        assert received.data["account_id"] == str(account_id)
        assert received.data["holdings_count"] == 15
        assert received.data["created_count"] == 3

    @pytest.mark.asyncio
    async def test_networth_updated_event_delivered(
        self, redis_test_client, sse_publisher, sse_subscriber
    ):
        """Test PORTFOLIO_NETWORTH_UPDATED event is delivered to user."""
        user_id = uuid7()
        event = create_portfolio_event(
            event_type=SSEEventType.PORTFOLIO_NETWORTH_UPDATED,
            user_id=user_id,
            data={
                "previous_net_worth": "50000.00",
                "new_net_worth": "52500.75",
                "delta": "2500.75",
                "currency": "USD",
                "account_count": 5,
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
        assert received.event_type == SSEEventType.PORTFOLIO_NETWORTH_UPDATED
        assert received.data["new_net_worth"] == "52500.75"
        assert received.data["delta"] == "2500.75"
        assert received.data["account_count"] == 5


# =============================================================================
# Category Filtering Tests
# =============================================================================


@pytest.mark.integration
class TestPortfolioCategoryFiltering:
    """Test portfolio events are correctly categorized."""

    @pytest.mark.asyncio
    async def test_portfolio_category_filter_accepts_balance_event(
        self, sse_subscriber
    ):
        """Test portfolio category filter accepts balance update events."""
        user_id = uuid7()
        event = create_portfolio_event(
            event_type=SSEEventType.PORTFOLIO_BALANCE_UPDATED,
            user_id=user_id,
            data={"account_id": str(uuid7())},
        )

        assert sse_subscriber.filter_by_categories(event, ["portfolio"]) is True

    @pytest.mark.asyncio
    async def test_portfolio_category_filter_accepts_holdings_event(
        self, sse_subscriber
    ):
        """Test portfolio category filter accepts holdings update events."""
        user_id = uuid7()
        event = create_portfolio_event(
            event_type=SSEEventType.PORTFOLIO_HOLDINGS_UPDATED,
            user_id=user_id,
            data={"account_id": str(uuid7())},
        )

        assert sse_subscriber.filter_by_categories(event, ["portfolio"]) is True

    @pytest.mark.asyncio
    async def test_portfolio_category_filter_accepts_networth_event(
        self, sse_subscriber
    ):
        """Test portfolio category filter accepts networth update events."""
        user_id = uuid7()
        event = create_portfolio_event(
            event_type=SSEEventType.PORTFOLIO_NETWORTH_UPDATED,
            user_id=user_id,
            data={"new_net_worth": "50000.00"},
        )

        assert sse_subscriber.filter_by_categories(event, ["portfolio"]) is True

    @pytest.mark.asyncio
    async def test_portfolio_event_rejected_by_other_category(self, sse_subscriber):
        """Test portfolio events are rejected by non-portfolio category filter."""
        user_id = uuid7()
        event = create_portfolio_event(
            event_type=SSEEventType.PORTFOLIO_NETWORTH_UPDATED,
            user_id=user_id,
            data={"new_net_worth": "50000.00"},
        )

        # Portfolio event should not pass data_sync filter
        assert sse_subscriber.filter_by_categories(event, ["data_sync"]) is False

    @pytest.mark.asyncio
    async def test_portfolio_event_passes_no_filter(self, sse_subscriber):
        """Test portfolio events pass when no filter specified."""
        user_id = uuid7()
        event = create_portfolio_event(
            event_type=SSEEventType.PORTFOLIO_BALANCE_UPDATED,
            user_id=user_id,
        )

        assert sse_subscriber.filter_by_categories(event, None) is True


# =============================================================================
# Negative Delta Tests (Portfolio Value Decrease)
# =============================================================================


@pytest.mark.integration
class TestPortfolioNegativeDelta:
    """Test portfolio events with negative deltas (decreases)."""

    @pytest.mark.asyncio
    async def test_balance_decrease_event_delivered(
        self, redis_test_client, sse_publisher, sse_subscriber
    ):
        """Test balance decrease event is delivered correctly."""
        user_id = uuid7()
        account_id = uuid7()
        event = create_portfolio_event(
            event_type=SSEEventType.PORTFOLIO_BALANCE_UPDATED,
            user_id=user_id,
            data={
                "account_id": str(account_id),
                "previous_balance": "5000.00",
                "new_balance": "4500.00",
                "delta": "-500.00",
                "currency": "EUR",
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
        assert received.data["delta"] == "-500.00"
        assert received.data["currency"] == "EUR"

    @pytest.mark.asyncio
    async def test_networth_decrease_event_delivered(
        self, redis_test_client, sse_publisher, sse_subscriber
    ):
        """Test net worth decrease event is delivered correctly."""
        user_id = uuid7()
        event = create_portfolio_event(
            event_type=SSEEventType.PORTFOLIO_NETWORTH_UPDATED,
            user_id=user_id,
            data={
                "previous_net_worth": "100000.00",
                "new_net_worth": "95000.00",
                "delta": "-5000.00",
                "currency": "USD",
                "account_count": 3,
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
        assert received.data["delta"] == "-5000.00"
        assert received.data["previous_net_worth"] == "100000.00"
        assert received.data["new_net_worth"] == "95000.00"
