"""Unit tests for TraceMiddleware (request tracing).

Tests cover:
- Trace ID generation for new requests
- Trace ID extraction from X-Trace-Id header
- Contextvars propagation
- Trace ID included in response headers
- get_trace_id() function

Architecture:
- Unit tests with mocked FastAPI Request/Response
- Tests middleware integration patterns
"""

from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest

from src.presentation.api.middleware.trace_middleware import (
    TraceMiddleware,
    get_trace_id,
)


@pytest.mark.unit
class TestTraceMiddlewareTraceIdGeneration:
    """Test TraceMiddleware trace ID generation."""

    @pytest.mark.asyncio
    async def test_generates_new_trace_id_when_missing(self):
        """Test middleware generates new trace ID when not in headers."""
        # Mock request without X-Trace-Id header
        mock_request = MagicMock()
        mock_request.headers = {}

        # Mock call_next
        mock_response = MagicMock()
        mock_response.headers = {}
        mock_call_next = AsyncMock(return_value=mock_response)

        # Create middleware
        middleware = TraceMiddleware(app=MagicMock())

        # Call middleware
        response = await middleware.dispatch(mock_request, mock_call_next)

        # Should have added X-Trace-Id to response
        assert "X-Trace-Id" in response.headers

        # Trace ID should be valid UUID
        trace_id = response.headers["X-Trace-Id"]
        UUID(trace_id)  # Raises ValueError if invalid

    @pytest.mark.asyncio
    async def test_uses_existing_trace_id_from_header(self):
        """Test middleware uses existing trace ID from request headers."""
        existing_trace_id = "12345678-1234-5678-1234-567812345678"

        # Mock request with X-Trace-Id header
        mock_request = MagicMock()
        mock_request.headers = {"X-Trace-Id": existing_trace_id}

        # Mock call_next
        mock_response = MagicMock()
        mock_response.headers = {}
        mock_call_next = AsyncMock(return_value=mock_response)

        # Create middleware
        middleware = TraceMiddleware(app=MagicMock())

        # Call middleware
        response = await middleware.dispatch(mock_request, mock_call_next)

        # Should use existing trace ID
        assert response.headers["X-Trace-Id"] == existing_trace_id


@pytest.mark.unit
class TestTraceMiddlewareContextPropagation:
    """Test TraceMiddleware contextvars propagation."""

    @pytest.mark.asyncio
    async def test_trace_id_available_during_request(self):
        """Test trace ID is available via get_trace_id() during request."""
        # Mock request
        mock_request = MagicMock()
        mock_request.headers = {}

        # Mock call_next that checks trace_id
        async def check_trace_id(request):
            # get_trace_id() should return current trace ID
            trace_id = get_trace_id()
            assert trace_id is not None
            UUID(trace_id)  # Should be valid UUID

            # Return mock response
            mock_response = MagicMock()
            mock_response.headers = {}
            return mock_response

        # Create middleware
        middleware = TraceMiddleware(app=MagicMock())

        # Call middleware
        await middleware.dispatch(mock_request, check_trace_id)

    @pytest.mark.asyncio
    async def test_trace_id_consistent_across_request(self):
        """Test trace ID remains consistent throughout request lifecycle."""
        # Mock request
        mock_request = MagicMock()
        mock_request.headers = {}

        trace_ids_captured = []

        # Mock call_next that captures trace_id multiple times
        async def capture_trace_ids(request):
            # Capture trace ID multiple times
            trace_ids_captured.append(get_trace_id())
            trace_ids_captured.append(get_trace_id())
            trace_ids_captured.append(get_trace_id())

            mock_response = MagicMock()
            mock_response.headers = {}
            return mock_response

        # Create middleware
        middleware = TraceMiddleware(app=MagicMock())

        # Call middleware
        await middleware.dispatch(mock_request, capture_trace_ids)

        # All captured trace IDs should be the same
        assert len(trace_ids_captured) == 3
        assert trace_ids_captured[0] == trace_ids_captured[1]
        assert trace_ids_captured[1] == trace_ids_captured[2]

    @pytest.mark.asyncio
    async def test_trace_id_cleared_after_request(self):
        """Test trace ID is cleared after request completes."""
        # Mock request
        mock_request = MagicMock()
        mock_request.headers = {}

        # Mock call_next
        mock_response = MagicMock()
        mock_response.headers = {}
        mock_call_next = AsyncMock(return_value=mock_response)

        # Create middleware
        middleware = TraceMiddleware(app=MagicMock())

        # Call middleware
        await middleware.dispatch(mock_request, mock_call_next)

        # After request, trace_id should be cleared (returns None)
        trace_id = get_trace_id()
        assert trace_id is None


@pytest.mark.unit
class TestTraceMiddlewareResponseHeaders:
    """Test TraceMiddleware response header injection."""

    @pytest.mark.asyncio
    async def test_adds_trace_id_to_response_headers(self):
        """Test middleware adds X-Trace-Id to response headers."""
        # Mock request
        mock_request = MagicMock()
        mock_request.headers = {}

        # Mock call_next
        mock_response = MagicMock()
        mock_response.headers = {}
        mock_call_next = AsyncMock(return_value=mock_response)

        # Create middleware
        middleware = TraceMiddleware(app=MagicMock())

        # Call middleware
        response = await middleware.dispatch(mock_request, mock_call_next)

        # Response should have X-Trace-Id header
        assert "X-Trace-Id" in response.headers
        assert len(response.headers["X-Trace-Id"]) > 0

    @pytest.mark.asyncio
    async def test_response_trace_id_matches_request(self):
        """Test response trace ID matches the one used during request."""
        # Mock request
        mock_request = MagicMock()
        mock_request.headers = {}

        captured_trace_id = None

        # Mock call_next that captures trace_id
        async def capture_trace_id(request):
            nonlocal captured_trace_id
            captured_trace_id = get_trace_id()

            mock_response = MagicMock()
            mock_response.headers = {}
            return mock_response

        # Create middleware
        middleware = TraceMiddleware(app=MagicMock())

        # Call middleware
        response = await middleware.dispatch(mock_request, capture_trace_id)

        # Response header should match captured trace_id
        assert response.headers["X-Trace-Id"] == captured_trace_id

    @pytest.mark.asyncio
    async def test_preserves_existing_response_headers(self):
        """Test middleware preserves existing response headers."""
        # Mock request
        mock_request = MagicMock()
        mock_request.headers = {}

        # Mock call_next returning response with existing headers
        mock_response = MagicMock()
        mock_response.headers = {
            "Content-Type": "application/json",
            "X-Custom-Header": "custom-value",
        }
        mock_call_next = AsyncMock(return_value=mock_response)

        # Create middleware
        middleware = TraceMiddleware(app=MagicMock())

        # Call middleware
        response = await middleware.dispatch(mock_request, mock_call_next)

        # Existing headers should be preserved
        assert response.headers["Content-Type"] == "application/json"
        assert response.headers["X-Custom-Header"] == "custom-value"
        # And trace ID added
        assert "X-Trace-Id" in response.headers


@pytest.mark.unit
class TestGetTraceIdFunction:
    """Test get_trace_id() utility function."""

    def test_get_trace_id_returns_none_outside_request(self):
        """Test get_trace_id() returns None when called outside request context."""
        trace_id = get_trace_id()
        assert trace_id is None

    @pytest.mark.asyncio
    async def test_get_trace_id_returns_string(self):
        """Test get_trace_id() returns string trace ID during request."""
        # Mock request
        mock_request = MagicMock()
        mock_request.headers = {}

        # Mock call_next that checks trace_id type
        async def check_trace_id_type(request):
            trace_id = get_trace_id()
            assert isinstance(trace_id, str)

            mock_response = MagicMock()
            mock_response.headers = {}
            return mock_response

        # Create middleware
        middleware = TraceMiddleware(app=MagicMock())

        # Call middleware
        await middleware.dispatch(mock_request, check_trace_id_type)


@pytest.mark.unit
class TestTraceMiddlewareErrorHandling:
    """Test TraceMiddleware error handling."""

    @pytest.mark.asyncio
    async def test_middleware_propagates_exceptions(self):
        """Test middleware propagates exceptions from downstream."""
        # Mock request
        mock_request = MagicMock()
        mock_request.headers = {}

        # Mock call_next that raises exception
        mock_call_next = AsyncMock(side_effect=ValueError("Downstream error"))

        # Create middleware
        middleware = TraceMiddleware(app=MagicMock())

        # Middleware should propagate exception
        with pytest.raises(ValueError, match="Downstream error"):
            await middleware.dispatch(mock_request, mock_call_next)


@pytest.mark.unit
class TestTraceMiddlewareIntegration:
    """Test TraceMiddleware integration patterns."""

    @pytest.mark.asyncio
    async def test_middleware_with_multiple_requests(self):
        """Test middleware handles multiple requests with different trace IDs."""
        # Create middleware
        middleware = TraceMiddleware(app=MagicMock())

        trace_ids = []

        # Simulate multiple requests
        for i in range(3):
            mock_request = MagicMock()
            mock_request.headers = {}

            # Mock call_next that captures trace_id
            async def capture_trace_id(request):
                trace_ids.append(get_trace_id())
                mock_response = MagicMock()
                mock_response.headers = {}
                return mock_response

            await middleware.dispatch(mock_request, capture_trace_id)

        # All trace IDs should be different
        assert len(trace_ids) == 3
        assert len(set(trace_ids)) == 3  # All unique

    @pytest.mark.asyncio
    async def test_middleware_call_next_invoked(self):
        """Test middleware calls next middleware/handler in chain."""
        # Mock request
        mock_request = MagicMock()
        mock_request.headers = {}

        # Mock call_next
        mock_response = MagicMock()
        mock_response.headers = {}
        mock_call_next = AsyncMock(return_value=mock_response)

        # Create middleware
        middleware = TraceMiddleware(app=MagicMock())

        # Call middleware
        await middleware.dispatch(mock_request, mock_call_next)

        # call_next should be invoked once
        mock_call_next.assert_called_once_with(mock_request)
