"""Route generator for the API Route Registry.

This module provides register_routes_from_registry(), which generates FastAPI routes
from RouteMetadata entries at application startup. It's the core of the Registry Pattern,
converting declarative metadata into runtime routes.

Functions:
    register_routes_from_registry: Generate all routes from registry
    _build_dependencies: Build FastAPI dependencies from auth policy
    _build_responses: Build OpenAPI responses dict from error specs

Usage:
    from src.presentation.routers.api.v1.routes.registry import ROUTE_REGISTRY
    from src.presentation.routers.api.v1.routes.generator import register_routes_from_registry

    v1_router = APIRouter(prefix="/api/v1")
    register_routes_from_registry(v1_router, ROUTE_REGISTRY)

Reference:
    - docs/architecture/registry-pattern-architecture.md
"""

from typing import Any

from fastapi import APIRouter, Depends

from src.presentation.routers.api.middleware.auth_dependencies import (
    get_current_user,
)
from src.presentation.routers.api.middleware.authorization_dependencies import (
    require_casbin_role,
)
from src.presentation.routers.api.v1.routes.metadata import (
    AuthLevel,
    AuthPolicy,
    RouteMetadata,
)


def register_routes_from_registry(
    router: APIRouter,
    registry: list[RouteMetadata],
) -> None:
    """Generate FastAPI routes from registry metadata.

    This function converts declarative RouteMetadata entries into runtime FastAPI
    routes using router.add_api_route(). It handles:
    - HTTP method and path
    - Handler function reference
    - Request/response models
    - Status codes
    - OpenAPI documentation (summary, description, operation_id)
    - Error responses
    - Auth dependencies (based on auth_policy)

    Args:
        router: FastAPI APIRouter to register routes on
        registry: List of RouteMetadata entries to convert into routes

    Example:
        >>> from fastapi import APIRouter
        >>> from src.presentation.routers.api.v1.routes.registry import ROUTE_REGISTRY
        >>>
        >>> v1_router = APIRouter(prefix="/api/v1")
        >>> register_routes_from_registry(v1_router, ROUTE_REGISTRY)
        >>> # Now v1_router has 36 routes registered

    Reference:
        - docs/architecture/registry-pattern-architecture.md
    """
    for metadata in registry:
        # Build dependencies based on auth policy
        dependencies = _build_dependencies(metadata.auth_policy)

        # Build OpenAPI responses from error specs
        responses = _build_responses(metadata.errors) if metadata.errors else None

        # Register route with FastAPI
        router.add_api_route(
            path=metadata.path,
            endpoint=metadata.handler,
            methods=[metadata.method.value],
            response_model=metadata.response_model,
            status_code=metadata.status_code,
            tags=list(metadata.tags),  # Convert Sequence to list for FastAPI
            summary=metadata.summary,
            description=metadata.description,
            operation_id=metadata.operation_id,
            responses=responses,
            dependencies=dependencies,
            deprecated=metadata.deprecated,
        )


def _build_dependencies(auth_policy: AuthPolicy) -> list[Any]:
    """Build FastAPI dependencies from auth policy.

    Converts declarative AuthPolicy into FastAPI Depends() dependencies that
    will be injected into the route handler.

    Auth policy mapping:
        PUBLIC: No dependencies (anyone can access)
        AUTHENTICATED: Depends(get_current_user) - requires valid JWT
        ADMIN: Depends(get_current_user) + Depends(require_casbin_role("admin"))
        MANUAL_AUTH: No dependencies (route handles auth manually)

    Args:
        auth_policy: Authentication policy from RouteMetadata

    Returns:
        List of FastAPI dependencies to inject

    Examples:
        >>> # Public route - no auth
        >>> _build_dependencies(AuthPolicy(level=AuthLevel.PUBLIC))
        []
        >>>
        >>> # Authenticated route - requires JWT
        >>> _build_dependencies(AuthPolicy(level=AuthLevel.AUTHENTICATED))
        [Depends(get_current_user)]
        >>>
        >>> # Admin route - requires JWT + admin role
        >>> _build_dependencies(AuthPolicy(level=AuthLevel.ADMIN, role="admin"))
        [Depends(get_current_user), Depends(require_casbin_role("admin"))]
        >>>
        >>> # Manual auth - route handles it
        >>> _build_dependencies(AuthPolicy(level=AuthLevel.MANUAL_AUTH, rationale="..."))
        []
    """
    match auth_policy.level:
        case AuthLevel.PUBLIC:
            # No authentication required
            return []

        case AuthLevel.AUTHENTICATED:
            # Requires valid JWT (CurrentUser injected)
            return [Depends(get_current_user)]

        case AuthLevel.ADMIN:
            # Requires JWT + admin role check (Casbin RBAC)
            role = auth_policy.role or "admin"
            return [
                Depends(get_current_user),
                Depends(require_casbin_role(role)),
            ]

        case AuthLevel.MANUAL_AUTH:
            # Route handles authentication manually (e.g., sessions with custom error mapping)
            # No dependencies - handler contains auth logic
            return []

        case _:
            # Unknown auth level - fail closed (no access)
            msg = f"Unknown auth level: {auth_policy.level}"
            raise ValueError(msg)


def _build_responses(errors: list[Any]) -> dict[int | str, dict[str, Any]]:
    """Build OpenAPI responses dict from error specifications.

    Converts list of ErrorSpec into FastAPI responses dict for OpenAPI schema.

    Args:
        errors: List of ErrorSpec from RouteMetadata

    Returns:
        Dict mapping status codes to response descriptions for OpenAPI

    Example:
        >>> from src.presentation.routers.api.v1.routes.metadata import ErrorSpec
        >>> errors = [
        ...     ErrorSpec(status=400, description="Validation error"),
        ...     ErrorSpec(status=404, description="User not found"),
        ... ]
        >>> _build_responses(errors)
        {
            400: {"description": "Validation error"},
            404: {"description": "User not found"}
        }
    """
    return {error.status: {"description": error.description} for error in errors}
