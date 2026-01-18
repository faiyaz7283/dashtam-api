"""API tests for events SSE endpoint.

Tests the complete HTTP request/response cycle for the SSE events endpoint:
- GET /api/v1/events (Server-Sent Events stream)

Architecture:
    - Uses FastAPI TestClient with real app + dependency overrides
    - Tests authentication (401 without auth)
    - Tests response headers (content-type, cache control)
    - Tests streaming response format
    - Mocks SSE subscriber to control event delivery

Note:
    TestClient with streaming responses requires careful handling.
    We use iter_lines() for streaming tests.

Reference:
    - src/presentation/routers/api/v1/events.py
    - docs/architecture/sse-architecture.md
"""

from collections.abc import AsyncIterator
from dataclasses import dataclass
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from uuid_extensions import uuid7

from src.core.container.sse import get_sse_subscriber
from src.domain.events.sse_event import SSEEvent, SSEEventType
from src.main import app


# =============================================================================
# Test Doubles
# =============================================================================


@dataclass
class MockCurrentUser:
    """Mock user for auth override."""

    user_id: UUID
    email: str = "test@example.com"
    roles: list[str] | None = None

    def __post_init__(self):
        if self.roles is None:
            self.roles = ["user"]


class MockSSESubscriber:
    """Mock SSE subscriber for testing.

    Yields a configurable number of events then stops.
    """

    def __init__(
        self,
        events: list[SSEEvent] | None = None,
        missed_events: list[SSEEvent] | None = None,
        enable_retention: bool = False,
    ) -> None:
        self._events = events or []
        self._missed_events = missed_events or []
        self._enable_retention = enable_retention

    async def subscribe(
        self,
        user_id: UUID,
        categories: list[str] | None = None,
    ) -> AsyncIterator[SSEEvent]:
        """Yield configured events."""
        for event in self._events:
            yield event

    async def get_missed_events(
        self,
        user_id: UUID,
        last_event_id: UUID,
        categories: list[str] | None = None,
    ) -> list[SSEEvent]:
        """Return configured missed events."""
        if not self._enable_retention:
            return []
        return self._missed_events


def create_test_event(
    event_type: SSEEventType = SSEEventType.SYNC_ACCOUNTS_COMPLETED,
    user_id: UUID | None = None,
    data: dict[str, object] | None = None,
) -> SSEEvent:
    """Create an SSEEvent for testing."""
    return SSEEvent(
        event_type=event_type,
        user_id=user_id or uuid7(),
        data=data or {"test": "data"},
    )


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_user_id():
    """Provide consistent user ID for tests."""
    return uuid7()


@pytest.fixture
def client():
    """Provide test client."""
    return TestClient(app)


@pytest.fixture
def authenticated_client(mock_user_id):
    """Provide test client with mocked authentication."""
    from src.presentation.routers.api.middleware.auth_dependencies import (
        get_current_user,
    )

    mock_user = MockCurrentUser(user_id=mock_user_id)

    async def mock_get_current_user():
        return mock_user

    app.dependency_overrides[get_current_user] = mock_get_current_user

    yield TestClient(app)

    app.dependency_overrides.pop(get_current_user, None)


# =============================================================================
# Authentication Tests
# =============================================================================


@pytest.mark.api
class TestEventsAuthentication:
    """Tests for SSE endpoint authentication."""

    def test_events_requires_authentication(self, client):
        """GET /api/v1/events returns 401 without authentication."""
        # Clear any auth overrides
        from src.presentation.routers.api.middleware.auth_dependencies import (
            get_current_user,
        )

        app.dependency_overrides.pop(get_current_user, None)

        response = client.get("/api/v1/events")

        # Should be 401 Unauthorized
        assert response.status_code == 401

    def test_events_accessible_with_authentication(
        self, authenticated_client, mock_user_id
    ):
        """GET /api/v1/events returns 200 with authentication."""
        # Mock subscriber to yield no events (ends stream immediately)
        mock_subscriber = MockSSESubscriber(events=[])
        app.dependency_overrides[get_sse_subscriber] = lambda: mock_subscriber

        response = authenticated_client.get("/api/v1/events")

        # Should be 200 OK
        assert response.status_code == 200

        app.dependency_overrides.pop(get_sse_subscriber, None)


# =============================================================================
# Response Header Tests
# =============================================================================


@pytest.mark.api
class TestEventsResponseHeaders:
    """Tests for SSE response headers."""

    def test_events_content_type_is_event_stream(
        self, authenticated_client, mock_user_id
    ):
        """GET /api/v1/events has correct Content-Type header."""
        mock_subscriber = MockSSESubscriber(events=[])
        app.dependency_overrides[get_sse_subscriber] = lambda: mock_subscriber

        response = authenticated_client.get("/api/v1/events")

        assert response.headers["content-type"] == "text/event-stream; charset=utf-8"

        app.dependency_overrides.pop(get_sse_subscriber, None)

    def test_events_has_cache_control_header(self, authenticated_client, mock_user_id):
        """GET /api/v1/events has Cache-Control: no-cache header."""
        mock_subscriber = MockSSESubscriber(events=[])
        app.dependency_overrides[get_sse_subscriber] = lambda: mock_subscriber

        response = authenticated_client.get("/api/v1/events")

        assert response.headers["cache-control"] == "no-cache"

        app.dependency_overrides.pop(get_sse_subscriber, None)

    def test_events_has_connection_header(self, authenticated_client, mock_user_id):
        """GET /api/v1/events has Connection: keep-alive header."""
        mock_subscriber = MockSSESubscriber(events=[])
        app.dependency_overrides[get_sse_subscriber] = lambda: mock_subscriber

        response = authenticated_client.get("/api/v1/events")

        assert response.headers.get("connection") == "keep-alive"

        app.dependency_overrides.pop(get_sse_subscriber, None)


# =============================================================================
# Streaming Response Tests
# =============================================================================


@pytest.mark.api
class TestEventsStreaming:
    """Tests for SSE event streaming."""

    def test_events_includes_retry_hint(self, authenticated_client, mock_user_id):
        """GET /api/v1/events starts with retry interval hint."""
        mock_subscriber = MockSSESubscriber(events=[])
        app.dependency_overrides[get_sse_subscriber] = lambda: mock_subscriber

        response = authenticated_client.get("/api/v1/events")
        content = response.text

        # Should include retry: directive
        assert "retry:" in content

        app.dependency_overrides.pop(get_sse_subscriber, None)

    def test_events_streams_single_event(self, authenticated_client, mock_user_id):
        """GET /api/v1/events streams event in SSE format."""
        event = create_test_event(
            event_type=SSEEventType.SYNC_ACCOUNTS_COMPLETED,
            user_id=mock_user_id,
            data={"count": 5},
        )
        mock_subscriber = MockSSESubscriber(events=[event])
        app.dependency_overrides[get_sse_subscriber] = lambda: mock_subscriber

        response = authenticated_client.get("/api/v1/events")
        content = response.text

        # Should include event fields
        assert f"id: {event.event_id}" in content
        assert "event: sync.accounts.completed" in content
        assert "data:" in content
        assert '"count": 5' in content or '"count":5' in content

        app.dependency_overrides.pop(get_sse_subscriber, None)

    def test_events_streams_multiple_events(self, authenticated_client, mock_user_id):
        """GET /api/v1/events streams multiple events in order."""
        events = [
            create_test_event(
                event_type=SSEEventType.SYNC_ACCOUNTS_STARTED,
                user_id=mock_user_id,
                data={"step": 1},
            ),
            create_test_event(
                event_type=SSEEventType.SYNC_ACCOUNTS_COMPLETED,
                user_id=mock_user_id,
                data={"step": 2},
            ),
        ]
        mock_subscriber = MockSSESubscriber(events=events)
        app.dependency_overrides[get_sse_subscriber] = lambda: mock_subscriber

        response = authenticated_client.get("/api/v1/events")
        content = response.text

        # Both events should be present
        assert "event: sync.accounts.started" in content
        assert "event: sync.accounts.completed" in content
        assert '"step": 1' in content or '"step":1' in content
        assert '"step": 2' in content or '"step":2' in content

        app.dependency_overrides.pop(get_sse_subscriber, None)


# =============================================================================
# Query Parameter Tests
# =============================================================================


@pytest.mark.api
class TestEventsQueryParams:
    """Tests for SSE endpoint query parameters."""

    def test_events_accepts_categories_param(self, authenticated_client, mock_user_id):
        """GET /api/v1/events accepts categories query param."""
        mock_subscriber = MockSSESubscriber(events=[])
        app.dependency_overrides[get_sse_subscriber] = lambda: mock_subscriber

        # Should not fail validation
        response = authenticated_client.get(
            "/api/v1/events?categories=data_sync&categories=provider"
        )

        assert response.status_code == 200

        app.dependency_overrides.pop(get_sse_subscriber, None)

    def test_events_accepts_last_event_id_param(
        self, authenticated_client, mock_user_id
    ):
        """GET /api/v1/events accepts Last-Event-ID query param."""
        mock_subscriber = MockSSESubscriber(events=[])
        app.dependency_overrides[get_sse_subscriber] = lambda: mock_subscriber

        event_id = str(uuid7())

        # Should not fail validation
        response = authenticated_client.get(f"/api/v1/events?Last-Event-ID={event_id}")

        assert response.status_code == 200

        app.dependency_overrides.pop(get_sse_subscriber, None)


# =============================================================================
# Route Registry Compliance Tests
# =============================================================================


@pytest.mark.api
class TestEventsRouteRegistry:
    """Tests to verify events endpoint is in route registry."""

    def test_events_endpoint_exists(self, authenticated_client):
        """GET /api/v1/events endpoint exists and is accessible."""
        mock_subscriber = MockSSESubscriber(events=[])
        app.dependency_overrides[get_sse_subscriber] = lambda: mock_subscriber

        response = authenticated_client.get("/api/v1/events")

        # Should not be 404
        assert response.status_code != 404

        app.dependency_overrides.pop(get_sse_subscriber, None)

    def test_events_has_correct_path(self):
        """Events endpoint is registered at /api/v1/events."""
        from src.presentation.routers.api.v1.routes.registry import ROUTE_REGISTRY

        events_routes = [r for r in ROUTE_REGISTRY if r.path == "/events"]

        assert len(events_routes) == 1
        assert events_routes[0].resource == "events"
        assert events_routes[0].operation_id == "get_events"
