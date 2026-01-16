"""Rate limit middleware for FastAPI.

This middleware intercepts all HTTP requests and applies rate limit
based on the endpoint configuration. It handles:
- IP-scoped rate limit for unauthenticated endpoints (login, register)
- User-scoped rate limit for authenticated endpoints (optional JWT extraction)
- Proper HTTP 429 responses with RFC 6585 headers
- Fail-open semantics (never blocks if rate limit infrastructure fails)

Architecture:
    Presentation Layer middleware that uses RateLimitProtocol (domain) via
    TokenBucketAdapter (infrastructure) from the container.

Usage:
    # In main.py
    from src.presentation.routers.api.middleware.rate_limit_middleware import RateLimitMiddleware

    app.add_middleware(RateLimitMiddleware)

Reference:
    - docs/architecture/rate-limit-architecture.md (Section 4, 6, 7)
"""

import json
from typing import TYPE_CHECKING, Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

from src.core.config import settings
from src.core.result import Success
from src.infrastructure.rate_limit.config import get_rule_for_endpoint

if TYPE_CHECKING:
    from src.domain.protocols import RateLimitProtocol
    from src.domain.protocols.logger_protocol import LoggerProtocol


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Starlette middleware for rate limit on HTTP requests.

    Intercepts all HTTP requests and applies token bucket rate limit
    based on endpoint configuration. Returns HTTP 429 when rate limit exceeded.

    Fail-Open Design:
        All errors result in allowing the request. Rate limit
        infrastructure failures should NEVER cause denial of service.

    Response Headers (RFC 6585):
        - Retry-After: Seconds until retry allowed (on 429)
        - X-RateLimit-Limit: Maximum tokens (bucket capacity)
        - X-RateLimit-Remaining: Tokens remaining
        - X-RateLimit-Reset: Seconds until bucket fully refills

    Attributes:
        _rate_limit: RateLimitProtocol implementation (lazy loaded from container).
        _logger: LoggerProtocol for structured logging (lazy loaded).
    """

    def __init__(self, app: ASGIApp) -> None:
        """Initialize rate limit middleware.

        Args:
            app: The ASGI application to wrap.
        """
        super().__init__(app)
        self._rate_limit: RateLimitProtocol | None = None
        self._logger: LoggerProtocol | None = None

    def _get_rate_limit(self) -> "RateLimitProtocol":
        """Lazy load rate limiter from container.

        Returns:
            RateLimitProtocol implementation.
        """
        if self._rate_limit is None:
            from src.core.container import get_rate_limit

            self._rate_limit = get_rate_limit()
        return self._rate_limit

    def _get_logger(self) -> "LoggerProtocol":
        """Lazy load logger from container.

        Returns:
            LoggerProtocol implementation.
        """
        if self._logger is None:
            from src.core.container import get_logger

            self._logger = get_logger()
        return self._logger

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """Intercept request and apply rate limit.

        Args:
            request: Incoming HTTP request.
            call_next: Next handler in middleware chain.

        Returns:
            Response: Either rate limit error (429) or downstream response.
        """
        # Skip rate limit for health checks and docs
        path = request.url.path
        if self._should_skip(path):
            return await call_next(request)

        # Build endpoint key: "METHOD /path"
        endpoint = f"{request.method} {path}"

        # Check if endpoint has a rate limit rule
        rule = get_rule_for_endpoint(endpoint)
        if rule is None or not rule.enabled:
            # No rule or disabled - allow request
            return await call_next(request)

        # Extract identifier based on scope
        identifier = self._extract_identifier(request, rule.scope.value)

        try:
            # Check rate limit
            rate_limit = self._get_rate_limit()
            result = await rate_limit.is_allowed(
                endpoint=endpoint,
                identifier=identifier,
                cost=rule.cost,
            )

            match result:
                case Success(value=rate_result):
                    if not rate_result.allowed:
                        # Rate limited - return 429
                        return self._build_429_response(
                            request=request,
                            retry_after=rate_result.retry_after,
                            limit=rate_result.limit,
                            remaining=rate_result.remaining,
                            reset_seconds=rate_result.reset_seconds,
                        )

                    # Allowed - continue to endpoint
                    response = await call_next(request)

                    # Add rate limit headers to response
                    response.headers["X-RateLimit-Limit"] = str(rate_result.limit)
                    response.headers["X-RateLimit-Remaining"] = str(
                        rate_result.remaining
                    )
                    response.headers["X-RateLimit-Reset"] = str(
                        rate_result.reset_seconds
                    )

                    return response

                case _:
                    # Failure result - fail-open
                    self._log_fail_open(
                        "rate_limit_result_failure", endpoint, identifier
                    )
                    return await call_next(request)

        except Exception as exc:
            # Fail-open on any exception
            self._log_fail_open(
                "rate_limit_middleware_exception",
                endpoint,
                identifier,
                error=str(exc),
            )
            return await call_next(request)

    def _should_skip(self, path: str) -> bool:
        """Check if path should skip rate limit.

        Args:
            path: Request URL path.

        Returns:
            True if rate limit should be skipped.
        """
        # Skip health checks, docs, and static files
        skip_prefixes = (
            "/health",
            "/docs",
            "/redoc",
            "/openapi.json",
            "/favicon.ico",
        )
        return path in ("/", "/health") or path.startswith(skip_prefixes)

    def _extract_identifier(self, request: Request, scope: str) -> str:
        """Extract rate limit identifier based on scope.

        Args:
            request: HTTP request.
            scope: Rate limit scope (ip, user, user_provider, global).

        Returns:
            Identifier string for rate limit key.
        """
        if scope == "global":
            return "global"

        # Get client IP (handles X-Forwarded-For from Traefik)
        client_ip = self._get_client_ip(request)

        if scope == "ip":
            return client_ip

        # For user/user_provider scope, try to extract user_id from JWT
        user_id = self._extract_user_id_from_jwt(request)

        if scope == "user":
            return user_id if user_id else client_ip

        if scope == "user_provider":
            # Extract provider from path (e.g., /api/v1/providers/{provider_id}/sync)
            provider_id = self._extract_provider_from_path(request.url.path)
            base_id = user_id if user_id else client_ip
            return f"{base_id}:{provider_id}" if provider_id else base_id

        # Default to IP
        return client_ip

    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP address from request.

        Handles X-Forwarded-For header from reverse proxy (Traefik).
        Takes first IP if multiple are present (client IP).

        Args:
            request: HTTP request.

        Returns:
            Client IP address.
        """
        # Check X-Forwarded-For (set by Traefik)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # Take first IP (client IP, rest are proxy chain)
            return forwarded_for.split(",")[0].strip()

        # Check X-Real-IP (alternative header)
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip.strip()

        # Fall back to direct client IP
        if request.client:
            return request.client.host

        return "unknown"

    def _extract_user_id_from_jwt(self, request: Request) -> str | None:
        """Extract user_id from JWT token (lightweight, no full validation).

        For rate limit purposes, we only need the user_id claim.
        Full token validation happens in auth dependencies.

        Args:
            request: HTTP request.

        Returns:
            User ID if extractable, None otherwise.
        """
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return None

        token = auth_header[7:]  # Remove "Bearer " prefix

        try:
            # Decode JWT payload without verification (just for user_id extraction)
            # Format: header.payload.signature
            parts = token.split(".")
            if len(parts) != 3:
                return None

            # Decode payload (base64url)
            import base64

            # Add padding if needed
            payload_b64 = parts[1]
            padding = 4 - len(payload_b64) % 4
            if padding != 4:
                payload_b64 += "=" * padding

            payload_bytes = base64.urlsafe_b64decode(payload_b64)
            payload = json.loads(payload_bytes)

            # Extract user_id from 'sub' claim
            user_id = payload.get("sub")
            return str(user_id) if user_id else None

        except Exception:
            # Any decode error - return None (will fall back to IP)
            return None

    def _extract_provider_from_path(self, path: str) -> str | None:
        """Extract provider_id from path for USER_PROVIDER scope.

        Args:
            path: Request URL path.

        Returns:
            Provider ID if found in path, None otherwise.
        """
        # Pattern: /api/v1/providers/{provider_id}/...
        parts = path.strip("/").split("/")
        try:
            if "providers" in parts:
                provider_idx = parts.index("providers")
                if provider_idx + 1 < len(parts):
                    return parts[provider_idx + 1]
        except (ValueError, IndexError):
            pass
        return None

    def _build_429_response(
        self,
        request: Request,
        retry_after: float,
        limit: int,
        remaining: int,
        reset_seconds: int,
    ) -> JSONResponse:
        """Build HTTP 429 rate limit response.

        Returns RFC 7807 compliant problem details response.

        Args:
            request: Original request.
            retry_after: Seconds until retry allowed.
            limit: Maximum tokens (bucket capacity).
            remaining: Tokens remaining (should be 0).
            reset_seconds: Seconds until bucket fully refills.

        Returns:
            JSONResponse with 429 status and proper headers.
        """
        # Round retry_after for cleaner display
        retry_after_int = max(1, int(retry_after + 0.5))

        # RFC 7807 Problem Details
        content = {
            "type": f"{settings.api_base_url}/errors/rate-limit-exceeded",
            "title": "Rate Limit Exceeded",
            "status": 429,
            "detail": f"Too many requests. Please try again in {retry_after_int} seconds.",
            "instance": request.url.path,
            "retry_after": retry_after_int,
        }

        return JSONResponse(
            status_code=429,
            content=content,
            headers={
                "Retry-After": str(retry_after_int),
                "X-RateLimit-Limit": str(limit),
                "X-RateLimit-Remaining": str(remaining),
                "X-RateLimit-Reset": str(reset_seconds),
            },
        )

    def _log_fail_open(
        self,
        event: str,
        endpoint: str,
        identifier: str,
        error: str | None = None,
    ) -> None:
        """Log fail-open event for monitoring.

        Args:
            event: Event type (for categorization).
            endpoint: Endpoint that was being rate limit checked.
            identifier: Rate limit identifier.
            error: Optional error message.
        """
        try:
            logger = self._get_logger()
            logger.warning(
                "Rate limit fail-open",
                event=event,
                endpoint=endpoint,
                identifier=identifier,
                error=error,
                result="fail_open",
            )
        except Exception:
            # Even logging failed - silently continue
            pass
