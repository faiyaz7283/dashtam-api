"""Rate Limiter middleware for FastAPI.

This module provides HTTP middleware to enforce rate limits on all incoming
requests. It integrates with the Rate Limiter service to check limits before
allowing requests to proceed to endpoints.

SOLID Principles:
    - S: Single responsibility (HTTP interception and rate limit enforcement)
    - O: Open for extension (new endpoints via configuration, not code changes)
    - D: Depends on RateLimiterService abstraction (not concrete implementation)

Key Design Decisions:
    1. Middleware is HTTP-layer only (no business logic)
       - Extracts HTTP request information (IP, user_id, endpoint)
       - Calls Rate Limiter service for decision
       - Returns HTTP 429 or proceeds to endpoint

    2. Graceful handling of authentication
       - Supports both authenticated (user-scoped) and unauthenticated (IP-scoped) requests
       - Falls back to IP if user not authenticated
       - Never breaks requests due to auth extraction failures

    3. Standard HTTP rate limit headers
       - Retry-After: Seconds until retry allowed (required by RFC 6585)
       - X-RateLimit-Limit: Maximum requests allowed
       - X-RateLimit-Remaining: Requests remaining (after this request)
       - X-RateLimit-Reset: Seconds until bucket fully reset

Usage:
    ```python
    from src.rate_limiter.middleware import RateLimitMiddleware
    from src.rate_limiter.factory import get_rate_limiter_service

    # In main.py startup
    rate_limiter = await get_rate_limiter_service()
    app.add_middleware(RateLimitMiddleware, rate_limiter=rate_limiter)
    ```
"""

import logging
import re
from typing import Callable, Optional

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from src.rate_limiter.config import RateLimitRule
from src.rate_limiter.service import RateLimiterService
from src.services.jwt_service import JWTService, JWTError

logger = logging.getLogger(__name__)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """FastAPI middleware for Rate Limiter.

    Intercepts all HTTP requests before they reach endpoints and enforces
    rate limits based on configuration. Returns HTTP 429 if rate limited,
    otherwise allows request to proceed.

    Responsibilities:
        - Extract request information (IP, user_id, endpoint)
        - Build endpoint key from HTTP method and path
        - Call RateLimiterService to check limits
        - Return HTTP 429 if rate limited with proper headers
        - Add rate limit headers to all responses

    Does NOT contain:
        - Algorithm logic (delegated to algorithm layer)
        - Storage logic (delegated to storage layer)
        - Business logic (delegated to endpoints)
        - Configuration (delegated to config layer)

    SOLID Compliance:
        - S: Single responsibility (HTTP interception only)
        - O: Closed for modification (uses service abstraction)
        - D: Depends on RateLimiterService abstraction

    Lazy Initialization Pattern:
        The Rate Limiter service is initialized on first request rather than
        at middleware registration. This is required because:
        - FastAPI middleware must be registered before app starts
        - Rate Limiter needs async Redis client (created during request)
        - Lazy init ensures Redis is available when needed

    Examples:
        Basic usage (no dependency injection needed):
        ```python
        from src.rate_limiter.middleware import RateLimitMiddleware

        # In main.py - simply add middleware
        app.add_middleware(RateLimitMiddleware)
        ```
    """

    def __init__(self, app: ASGIApp):
        """Initialize rate limit middleware.

        Args:
            app: FastAPI/Starlette application instance.

        Note:
            Rate Limiter service is initialized lazily on first request.
            Audit backend creates fresh database session per violation.
            This follows FastAPI best practices for middleware with async
            dependencies that must be created after app startup.
        """
        super().__init__(app)
        self._rate_limiter: Optional[RateLimiterService] = None
        self.jwt_service = JWTService()
        self._logger = logging.getLogger(__name__)

    async def _get_rate_limiter(self) -> RateLimiterService:
        """Get or create Rate Limiter service (lazy initialization).

        Returns:
            Initialized RateLimiterService instance.

        Note:
            Creates Rate Limiter on first call, then caches for subsequent requests.
            Thread-safe as middleware dispatch is called sequentially per request.
        """
        if self._rate_limiter is None:
            from src.rate_limiter.factory import get_rate_limiter_service

            self._rate_limiter = await get_rate_limiter_service()
            self._logger.info("Rate Limiter middleware initialized (lazy)")

        return self._rate_limiter

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Intercept request and enforce rate limits.

        This is the main middleware entry point. It:
        1. Extracts endpoint key (e.g., "POST /api/v1/auth/login")
        2. Extracts identifier (user_id or IP address)
        3. Calls Rate Limiter service to check if allowed
        4. Returns HTTP 429 if rate limited
        5. Proceeds to endpoint if allowed
        6. Adds rate limit headers to response

        Args:
            request: Incoming HTTP request.
            call_next: Next middleware/endpoint in chain.

        Returns:
            HTTP response (429 if rate limited, otherwise from endpoint).

        Note:
            This method never raises exceptions. All errors are caught,
            logged, and requests are allowed to proceed (fail-open).
        """
        try:
            # Get or initialize Rate Limiter (lazy initialization)
            rate_limiter = await self._get_rate_limiter()

            # Extract endpoint key and identifier
            endpoint_key = self._get_endpoint_key(request)
            identifier = await self._get_identifier(request)

            # Check rate limit
            allowed, retry_after, rule = await rate_limiter.is_allowed(
                endpoint=endpoint_key,
                identifier=identifier,
            )

            if not allowed:
                # Rate limited: return HTTP 429
                return await self._rate_limit_response(
                    request=request,
                    retry_after=retry_after,
                    rule=rule,
                    identifier=identifier,
                )

            # Allowed: proceed to endpoint
            response = await call_next(request)

            # Add rate limit headers to response
            if rule:
                await self._add_rate_limit_headers(
                    response=response,
                    rule=rule,
                    endpoint_key=endpoint_key,
                    identifier=identifier,
                    rate_limiter=rate_limiter,
                )

            return response

        except Exception as e:
            # Fail-open: Allow request if middleware fails
            logger.error(
                f"Rate limit middleware failed: {e}. Allowing request (fail-open)."
            )
            return await call_next(request)

    def _get_endpoint_key(self, request: Request) -> str:
        """Extract endpoint key from request.

        Builds endpoint key in format "METHOD /path" to match configuration
        keys in RateLimitConfig.RULES.

        Handles path parameters by replacing UUID patterns with {param_name}
        placeholders to match configuration keys.

        Args:
            request: HTTP request.

        Returns:
            Endpoint key (e.g., "POST /api/v1/auth/login" or
            "GET /api/v1/providers/{provider_id}").

        Examples:
            >>> _get_endpoint_key(Request(method="POST", path="/api/v1/auth/login"))
            "POST /api/v1/auth/login"

            >>> _get_endpoint_key(Request(method="GET", path="/api/v1/providers/123e4567-e89b-12d3-a456-426614174000"))
            "GET /api/v1/providers/{provider_id}"
        """
        method = request.method
        path = request.url.path

        # Replace UUID path parameters with placeholders
        # Example: /api/v1/providers/123e4567-... -> /api/v1/providers/{provider_id}
        uuid_pattern = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"

        if re.search(uuid_pattern, path):
            # Detect which parameter by path structure
            if "/providers/" in path and "/authorization" not in path:
                # /api/v1/providers/{provider_id}
                path = re.sub(
                    r"/providers/" + uuid_pattern,
                    "/providers/{provider_id}",
                    path,
                )
            elif "/authorization/callback" in path:
                # /api/v1/providers/{provider_id}/authorization/callback
                path = re.sub(
                    r"/providers/" + uuid_pattern + r"/",
                    "/providers/{provider_id}/",
                    path,
                )
            elif "/authorization" in path:
                # /api/v1/providers/{provider_id}/authorization
                path = re.sub(
                    r"/providers/" + uuid_pattern + r"/",
                    "/providers/{provider_id}/",
                    path,
                )

        return f"{method} {path}"

    async def _get_identifier(self, request: Request) -> str:
        """Extract identifier for Rate Limiter.

        Determines identifier based on authentication status:
        - If authenticated: Use user ID from JWT token
        - If not authenticated: Use client IP address

        This allows different rate limit scopes:
        - User-scoped: Track rate limits per user (more generous)
        - IP-scoped: Track rate limits per IP (more restrictive)

        Args:
            request: HTTP request.

        Returns:
            Identifier string in format "user:{user_id}" or "ip:{ip_address}".

        Examples:
            Authenticated request:
            >>> await _get_identifier(request_with_jwt)
            "user:123e4567-e89b-12d3-a456-426614174000"

            Unauthenticated request:
            >>> await _get_identifier(request_no_auth)
            "ip:192.168.1.100"

        Note:
            This method never raises exceptions. If user extraction fails,
            it falls back to IP address.
        """
        try:
            # Try to extract user ID from JWT token
            user_id = await self._extract_user_id_from_token(request)
            if user_id:
                return user_id

        except Exception as e:
            # Log error but continue with IP fallback
            logger.debug(
                f"Failed to extract user ID from token: {e}. "
                f"Falling back to IP address."
            )

        # Fall back to IP address
        client_ip = self._get_client_ip(request)
        return client_ip

    async def _extract_user_id_from_token(self, request: Request) -> Optional[str]:
        """Extract user ID from JWT access token.

        Attempts to extract and validate JWT token from Authorization header.
        Returns user ID if token is valid, None otherwise.

        Args:
            request: HTTP request.

        Returns:
            User ID string in format "user:{uuid}" or None if not authenticated.

        Raises:
            No exceptions are raised. All errors are caught and None is returned.
        """
        try:
            # Check for Authorization header
            auth_header = request.headers.get("Authorization")
            if not auth_header or not auth_header.startswith("Bearer "):
                return None

            # Extract token
            token = auth_header.replace("Bearer ", "")

            # Verify it's an access token and extract user ID
            self.jwt_service.verify_token_type(token, "access")
            user_id = self.jwt_service.get_user_id_from_token(token)

            if user_id:
                return f"user:{user_id}"

        except (JWTError, Exception):
            # Silently fail - not all requests are authenticated
            pass

        return None

    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP address from request.

        Handles both direct connections and proxy scenarios (X-Forwarded-For).

        Args:
            request: HTTP request.

        Returns:
            IP address string in format "ip:{address}".

        Examples:
            Direct connection:
            >>> _get_client_ip(request)
            "ip:192.168.1.100"

            Behind proxy:
            >>> _get_client_ip(request_with_proxy)
            "ip:203.0.113.45"
        """
        # Check for X-Forwarded-For header (proxy/load balancer)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # Take first IP if multiple (client IP)
            client_ip = forwarded_for.split(",")[0].strip()
            return f"ip:{client_ip}"

        # Fall back to direct client IP
        if request.client:
            return f"ip:{request.client.host}"

        # Last resort fallback
        return "ip:unknown"

    async def _rate_limit_response(
        self,
        request: Request,
        retry_after: float,
        rule: Optional[RateLimitRule],
        identifier: str,
    ) -> JSONResponse:
        """Create HTTP 429 rate limit response.

        Builds standardized rate limit exceeded response with:
        - HTTP 429 status code
        - Retry-After header (RFC 6585)
        - X-RateLimit-* headers
        - JSON error message with details

        Args:
            request: HTTP request that was rate limited.
            retry_after: Seconds to wait before retrying.
            rule: Applied rate limit rule (or None if no rule).
            identifier: Request identifier (for logging).

        Returns:
            JSONResponse with 429 status and rate limit headers.

        Example Response:
            ```json
            {
                "error": "Rate limit exceeded",
                "message": "Too many requests. Please try again in 12 seconds.",
                "retry_after": 12,
                "endpoint": "POST /api/v1/auth/login"
            }
            ```
        """
        endpoint_key = self._get_endpoint_key(request)

        # Build response body
        response_data = {
            "error": "Rate limit exceeded",
            "message": (
                f"Too many requests. Please try again in {int(retry_after)} seconds."
            ),
            "retry_after": int(retry_after),
            "endpoint": endpoint_key,
        }

        # Build response headers
        headers = {
            "Retry-After": str(int(retry_after)),
            "X-RateLimit-Limit": str(rule.max_tokens) if rule else "unknown",
            "X-RateLimit-Remaining": "0",
            "X-RateLimit-Reset": str(int(retry_after)),
        }

        # Log rate limit violation (structured logging)
        logger.warning(
            f"Rate limit exceeded: endpoint={endpoint_key}, "
            f"identifier={identifier}, "
            f"retry_after={retry_after:.2f}s"
        )

        # Audit rate limit violation to database (fail-open)
        if rule:
            await self._audit_violation(
                identifier=identifier,
                endpoint=endpoint_key,
                rule=rule,
            )

        return JSONResponse(status_code=429, content=response_data, headers=headers)

    async def _add_rate_limit_headers(
        self,
        response: Response,
        rule: RateLimitRule,
        endpoint_key: str,
        identifier: str,
        rate_limiter: RateLimiterService,
    ) -> None:
        """Add rate limit headers to successful response.

        Adds informational headers to response so clients can track their
        rate limit status:
        - X-RateLimit-Limit: Maximum requests allowed in window
        - X-RateLimit-Remaining: Requests remaining after this one
        - X-RateLimit-Reset: Seconds until bucket fully resets

        Args:
            response: HTTP response to add headers to.
            rule: Applied rate limit rule.
            endpoint_key: Endpoint key for this request.
            identifier: Request identifier.

        Note:
            This method modifies the response object in place.
            Remaining tokens are fetched from storage to provide accurate counts.
        """
        try:
            # Get remaining tokens from storage
            key = rate_limiter._build_key(
                endpoint=endpoint_key,
                identifier=identifier,
                scope=rule.scope,
            )
            remaining = await rate_limiter.storage.get_remaining(
                key=key,
                max_tokens=rule.max_tokens,
            )

            # Add headers
            response.headers["X-RateLimit-Limit"] = str(rule.max_tokens)
            response.headers["X-RateLimit-Remaining"] = str(remaining)

            # Calculate reset time (time to fully refill bucket)
            # For token bucket: (max_tokens / refill_rate) * 60 seconds
            reset_seconds = int((rule.max_tokens / rule.refill_rate) * 60)
            response.headers["X-RateLimit-Reset"] = str(reset_seconds)

        except Exception as e:
            # Don't break response if header addition fails
            logger.error(f"Failed to add rate limit headers: {e}")

    async def _audit_violation(
        self,
        identifier: str,
        endpoint: str,
        rule: RateLimitRule,
    ) -> None:
        """Audit rate limit violation to configured backend.

        Creates a fresh database session for each audit log to avoid
        session lifecycle issues. The backend handles session cleanup.

        Fail-open design: Audit failures are logged but don't block the response.

        Args:
            identifier: Request identifier ("user:{uuid}" or "ip:{address}").
            endpoint: Endpoint key that was rate limited.
            rule: Rate limit rule that was violated.

        Note:
            This method never raises exceptions. All errors are caught and logged.
            The audit backend itself also has fail-open error handling.
        """
        try:
            # Parse identifier to extract IP address
            # Format: "user:{uuid}" or "ip:{address}"
            ip_address = "unknown"

            if identifier.startswith("ip:"):
                ip_address = identifier.replace("ip:", "")
            # For user identifiers, we can't determine IP from identifier alone
            # The IP should ideally be passed from request context, but for now
            # we'll set it to "unknown" for user-scoped violations

            # Create fresh database session for audit logging
            from src.core.database import get_session
            from src.models.rate_limit_audit import RateLimitAuditLog
            from src.rate_limiter.audit_backends.database import DatabaseAuditBackend

            async for session in get_session():
                # Create database-agnostic audit backend with Dashtam's model
                audit_backend = DatabaseAuditBackend(
                    session=session,
                    model_class=RateLimitAuditLog,
                )

                # Log violation to audit backend
                # Note: rule doesn't have 'name' or 'window_seconds' attributes
                # Use endpoint as rule_name and calculate window from refill_rate
                window_seconds = int((rule.max_tokens / rule.refill_rate) * 60)

                await audit_backend.log_violation(
                    identifier=identifier,  # Pass raw identifier
                    ip_address=ip_address,
                    endpoint=endpoint,
                    rule_name=endpoint,  # Use endpoint as rule name
                    limit=rule.max_tokens,
                    window_seconds=window_seconds,
                    violation_count=1,
                )
                break  # Only need one iteration

        except Exception as e:
            # Fail-open: Log error but don't propagate
            logger.error(
                f"Failed to audit rate limit violation: {e}",
                extra={
                    "identifier": identifier,
                    "endpoint": endpoint,
                    "rule_name": rule.name,
                },
            )
