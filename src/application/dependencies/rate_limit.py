"""Rate limit FastAPI dependency.

Provides a `rate_limit` dependency for endpoint-level rate limit control.
Use this when you need:
- Custom rate limit keys (beyond what middleware extracts)
- Rate limit based on authenticated user (from CurrentUser dependency)
- Variable cost based on request parameters

For most endpoints, the middleware handles rate limit automatically.
Use this dependency for custom scenarios.

Architecture:
    Application Layer dependency that uses RateLimitProtocol (domain) via
    container. Can be combined with auth dependencies for user-scoped limits.

Usage:
    from src.application.dependencies.rate_limit import rate_limit

    @router.post("/expensive-operation")
    async def expensive_operation(
        current_user: CurrentUser = Depends(get_current_user),
        _rate_check: None = Depends(rate_limit(
            endpoint="POST /api/v1/expensive-operation",
            cost=5,  # Costs 5 tokens
        )),
    ):
        # Rate limit already checked
        ...

Reference:
    - docs/architecture/rate-limit-architecture.md (Section 4)
"""

from typing import TYPE_CHECKING, Annotated, Any, Callable, Coroutine

from fastapi import Depends, HTTPException, Request

from src.core.container import get_rate_limit
from src.core.result import Success

if TYPE_CHECKING:
    from src.domain.protocols import RateLimitProtocol


def rate_limit(
    endpoint: str,
    *,
    cost: int = 1,
    use_user_id: bool = True,
) -> Callable[..., Coroutine[Any, Any, None]]:
    """Create a rate limit dependency for a specific endpoint.

    Factory function that returns a FastAPI dependency for rate limit.
    The dependency raises HTTPException(429) if rate limit exceeded.

    Args:
        endpoint: Endpoint key for rate limit lookup (e.g., "POST /api/v1/reports").
            Must match a key in RATE_LIMIT_RULES configuration.
        cost: Number of tokens to consume. Default 1.
            Use higher values for expensive operations.
        use_user_id: If True and user is authenticated, use user_id as identifier.
            If False, always use IP. Default True.

    Returns:
        FastAPI dependency function that performs rate limit.

    Raises:
        HTTPException(429): When rate limit is exceeded.

    Usage:
        @router.post("/reports/generate")
        async def generate_report(
            current_user: CurrentUser = Depends(get_current_user),
            _: None = Depends(rate_limit("POST /api/v1/reports/generate", cost=5)),
        ):
            # Proceeds only if rate limit not exceeded
            ...

    Note:
        This dependency is for ADDITIONAL control beyond middleware.
        The middleware already applies rate limit based on configuration.
        Use this when you need:
        - Different cost than configured
        - Custom identifier logic
        - Explicit rate limit in endpoint definition
    """

    async def dependency(
        request: Request,
        rate_limiter: Annotated[RateLimitProtocol, Depends(get_rate_limit)],
    ) -> None:
        """Rate limit dependency implementation.

        Args:
            request: Current HTTP request.
            rate_limiter: Rate limiter from container.

        Raises:
            HTTPException(429): If rate limit exceeded.
        """
        # Extract identifier
        identifier = _extract_identifier(request, use_user_id)

        # Check rate limit
        result = await rate_limiter.is_allowed(
            endpoint=endpoint,
            identifier=identifier,
            cost=cost,
        )

        match result:
            case Success(value=rate_result):
                if not rate_result.allowed:
                    retry_after = max(1, int(rate_result.retry_after + 0.5))
                    raise HTTPException(
                        status_code=429,
                        detail=f"Rate limit exceeded. Retry in {retry_after} seconds.",
                        headers={
                            "Retry-After": str(retry_after),
                            "X-RateLimit-Limit": str(rate_result.limit),
                            "X-RateLimit-Remaining": str(rate_result.remaining),
                            "X-RateLimit-Reset": str(rate_result.reset_seconds),
                        },
                    )
            case _:
                # Fail-open: allow on errors
                pass

    return dependency


def _extract_identifier(request: Request, use_user_id: bool) -> str:
    """Extract rate limit identifier from request.

    Args:
        request: HTTP request.
        use_user_id: Whether to try extracting user_id from request state.

    Returns:
        Identifier string (user_id or IP).
    """
    # Try to get user_id from request state (set by auth middleware/dependency)
    if use_user_id:
        # Check if CurrentUser was set by auth dependency
        user = getattr(request.state, "current_user", None)
        if user and hasattr(user, "user_id"):
            return str(user.user_id)

    # Fall back to IP
    return _get_client_ip(request)


def _get_client_ip(request: Request) -> str:
    """Extract client IP from request.

    Args:
        request: HTTP request.

    Returns:
        Client IP address.
    """
    # Check X-Forwarded-For (from Traefik)
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()

    # Check X-Real-IP
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()

    # Direct client
    if request.client:
        return request.client.host

    return "unknown"


# Pre-configured dependencies for common use cases
# These can be used directly with Depends() without calling rate_limited()


async def rate_limit_expensive(
    request: Request,
    rate_limiter: Annotated[RateLimitProtocol, Depends(get_rate_limit)],
) -> None:
    """Rate limit for expensive operations (cost=5).

    Use as: Depends(rate_limit_expensive)
    """
    identifier = _extract_identifier(request, use_user_id=True)
    result = await rate_limiter.is_allowed(
        endpoint=f"{request.method} {request.url.path}",
        identifier=identifier,
        cost=5,
    )

    match result:
        case Success(value=rate_result):
            if not rate_result.allowed:
                retry_after = max(1, int(rate_result.retry_after + 0.5))
                raise HTTPException(
                    status_code=429,
                    detail=f"Rate limit exceeded. Retry in {retry_after} seconds.",
                    headers={
                        "Retry-After": str(retry_after),
                        "X-RateLimit-Limit": str(rate_result.limit),
                        "X-RateLimit-Remaining": str(rate_result.remaining),
                    },
                )
        case _:
            pass  # Fail-open
