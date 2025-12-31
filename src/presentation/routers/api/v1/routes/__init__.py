"""API Route Registry package.

This package implements the Route Metadata Registry pattern for API routes.
The registry is the single source of truth for all routes, generating FastAPI
routes, rate limit rules, auth dependencies, and OpenAPI metadata.

Modules:
    metadata: Core types (RouteMetadata, AuthPolicy, RateLimitPolicy, etc.)
    registry: ROUTE_REGISTRY - List of all route specifications
    generator: register_routes_from_registry() - Generate FastAPI routes
    derivations: Helpers to derive artifacts from registry

Usage:
    from src.presentation.routers.api.v1.routes import ROUTE_REGISTRY
    from src.presentation.routers.api.v1.routes.generator import register_routes_from_registry

    router = APIRouter(prefix="/api/v1")
    register_routes_from_registry(router, ROUTE_REGISTRY)
"""

__all__ = [
    # Metadata types
    "RouteMetadata",
    "HTTPMethod",
    "AuthPolicy",
    "AuthLevel",
    "RateLimitPolicy",
    "ErrorSpec",
    "IdempotencyLevel",
    "CachePolicy",
]
