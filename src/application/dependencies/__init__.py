"""Application layer dependencies.

FastAPI dependencies for cross-cutting concerns like rate limit.
These are injected via Depends() in presentation layer endpoints.

Usage:
    from src.application.dependencies import rate_limit

    @router.post("/expensive")
    async def expensive_op(
        _: None = Depends(rate_limit("POST /api/v1/expensive", cost=5)),
    ):
        ...
"""

from src.application.dependencies.rate_limit import (
    rate_limit,
    rate_limit_expensive,
)

__all__ = [
    "rate_limit",
    "rate_limit_expensive",
]
