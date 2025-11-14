"""Trace middleware to inject a trace_id per request.

- Adds X-Trace-Id response header
- Exposes get_trace_id() helper for logging calls outside request handlers
"""

from __future__ import annotations

from contextvars import ContextVar
from typing import Awaitable, Callable
from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

trace_id_context: ContextVar[str | None] = ContextVar("trace_id", default=None)


def get_trace_id() -> str | None:
    """Return the current trace ID.

    Returns None when called outside of request context.
    Use this in logging calls to automatically include trace_id.

    Returns:
        str | None: The current request trace ID, or None if no active request.
    """
    return trace_id_context.get()


class TraceMiddleware(BaseHTTPMiddleware):
    """Starlette middleware that injects a trace ID into each request context."""

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """Intercept a request to set and propagate a trace ID.

        Args:
            request (Request): Incoming request.
            call_next (Callable[[Request], Awaitable[Response]]): Next handler.

        Returns:
            Response: Response with X-Trace-Id header added.
        """
        trace_id = request.headers.get("X-Trace-Id") or str(uuid4())
        trace_id_context.set(trace_id)
        try:
            response = await call_next(request)
            response.headers["X-Trace-Id"] = trace_id
            return response
        finally:
            # Clear context after request to prevent leakage
            trace_id_context.set(None)
