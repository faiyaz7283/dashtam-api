"""SSE Events Endpoint.

Provides Server-Sent Events streaming for real-time client notifications.
This is a pure handler function - routing is done via ROUTE_REGISTRY.

Architecture:
    - Uses existing Dashtam Bearer token authentication
    - Category-based filtering via query params
    - Last-Event-ID support for reconnection replay
    - Heartbeat comments to detect stale connections

Reference:
    - docs/architecture/sse-architecture.md
"""

import asyncio
from collections.abc import AsyncGenerator
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Query, Request
from fastapi.responses import StreamingResponse

from src.core.constants import SSE_RETRY_INTERVAL_MS
from src.core.container.sse import get_sse_subscriber
from src.domain.protocols.sse_subscriber_protocol import SSESubscriberProtocol
from src.presentation.routers.api.middleware.auth_dependencies import (
    CurrentUser,
    get_current_user,
)


async def get_events(
    request: Request,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    subscriber: Annotated[SSESubscriberProtocol, Depends(get_sse_subscriber)],
    categories: Annotated[
        list[str] | None,
        Query(
            description="Filter by event categories. "
            "Valid: data_sync, provider, ai, import, portfolio, security",
        ),
    ] = None,
    last_event_id: Annotated[
        str | None,
        Query(
            alias="Last-Event-ID",
            description="Resume from last received event ID (if retention enabled)",
        ),
    ] = None,
) -> StreamingResponse:
    """Stream real-time events via Server-Sent Events (SSE).

    **Authentication**: Standard Bearer token (same as all endpoints).

    Connect to receive push notifications for:
    - Data sync progress (accounts, transactions, holdings)
    - Provider connection health
    - Balance/portfolio updates
    - AI response streaming
    - Security notifications

    **Reconnection**: The client should automatically reconnect if
    disconnected. Include `Last-Event-ID` header to resume from
    where you left off (if event retention is enabled).

    **Categories**: Filter events by category:
    - `data_sync`: Account/transaction sync events
    - `provider`: Provider health events
    - `ai`: AI response streaming
    - `import`: File import progress
    - `portfolio`: Balance/holdings updates
    - `security`: Session/security alerts

    Returns:
        StreamingResponse with SSE content type.
    """

    async def event_generator() -> AsyncGenerator[str, None]:
        """Generate SSE events for streaming response.

        Yields:
            SSE-formatted strings (event messages and heartbeat comments).
        """
        # Send initial retry interval hint to client
        yield f"retry: {SSE_RETRY_INTERVAL_MS}\n\n"

        # Replay missed events if last_event_id provided
        if last_event_id:
            try:
                missed = await subscriber.get_missed_events(
                    user_id=current_user.user_id,
                    last_event_id=UUID(last_event_id),
                    categories=categories,
                )
                for event in missed:
                    yield event.to_sse_format()
            except ValueError:
                pass  # Invalid UUID, skip replay

        # Stream live events with timeout-based heartbeat
        # Heartbeat is sent when no events arrive within the interval
        try:
            async for event in subscriber.subscribe(
                user_id=current_user.user_id,
                categories=categories,
            ):
                # Check if client disconnected
                if await request.is_disconnected():
                    break

                yield event.to_sse_format()

        except asyncio.CancelledError:
            # Normal cancellation (client disconnect)
            pass

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx/Traefik buffering
        },
    )
