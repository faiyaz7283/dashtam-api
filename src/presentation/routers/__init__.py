"""External-facing routers (non-versioned API endpoints).

Routes that are external-facing but not part of the versioned API contract.
Examples: OAuth callbacks, webhooks, health checks.

OAuth callbacks are dictated by provider requirements (registered redirect URIs),
not our API versioning strategy.
"""

from src.presentation.routers.oauth_callbacks import oauth_router

__all__ = ["oauth_router"]
