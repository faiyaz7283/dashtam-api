"""Route metadata types for the API Route Registry.

This module defines the core types for the Route Metadata Registry pattern.
The registry is the single source of truth for all API routes, generating
FastAPI routes, rate limit rules, auth dependencies, and OpenAPI metadata.

Core types:
    RouteMetadata: Complete route specification (method, path, handler, auth, rate limits, etc.)
    HTTPMethod: HTTP method enum (GET, POST, PATCH, PUT, DELETE)
    AuthPolicy: Authentication policy (PUBLIC, AUTHENTICATED, ADMIN, MANUAL_AUTH)
    RateLimitPolicy: Rate limit policy enum (AUTH_LOGIN, API_READ, etc.)
    ErrorSpec: Error response specification for OpenAPI
    IdempotencyLevel: HTTP idempotency classification

Usage:
    from src.presentation.routers.api.v1.routes.metadata import RouteMetadata, HTTPMethod

    metadata = RouteMetadata(
        method=HTTPMethod.POST,
        path="/api/v1/users",
        handler=create_user_handler,
        response_model=UserCreateResponse,
        status_code=201,
        auth_policy=AuthPolicy.PUBLIC,
        rate_limit_policy=RateLimitPolicy.AUTH_REGISTER,
    )

Reference:
    - docs/architecture/registry-pattern-architecture.md
"""

from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from enum import Enum
from typing import Any

from pydantic import BaseModel


# =============================================================================
# HTTP Method Enum
# =============================================================================


class HTTPMethod(str, Enum):
    """HTTP methods for API routes.

    Attributes:
        GET: Safe, idempotent read operations
        POST: Non-idempotent create operations
        PUT: Idempotent complete replacement
        PATCH: Non-idempotent partial update
        DELETE: Idempotent delete operations
    """

    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    PATCH = "PATCH"
    DELETE = "DELETE"


# =============================================================================
# Authentication Policy
# =============================================================================


@dataclass(frozen=True, kw_only=True)
class AuthPolicy:
    """Authentication policy for a route.

    Defines who can access the route and what dependencies to inject.

    Attributes:
        level: Authentication level (public, authenticated, admin, manual_auth)
        role: Optional Casbin role requirement (e.g., "admin")
        permission: Optional Casbin permission requirement
        rationale: Optional explanation for MANUAL_AUTH routes

    Examples:
        >>> # Public route (no auth)
        >>> AuthPolicy(level=AuthLevel.PUBLIC)
        >>>
        >>> # Authenticated route (any logged-in user)
        >>> AuthPolicy(level=AuthLevel.AUTHENTICATED)
        >>>
        >>> # Admin-only route
        >>> AuthPolicy(level=AuthLevel.ADMIN, role="admin")
        >>>
        >>> # Manual auth (custom token parsing)
        >>> AuthPolicy(
        ...     level=AuthLevel.MANUAL_AUTH,
        ...     rationale="Custom 401/403 mapping for session endpoints"
        ... )
    """

    level: "AuthLevel"
    role: str | None = None
    permission: str | None = None
    rationale: str | None = None


class AuthLevel(str, Enum):
    """Authentication levels for routes.

    Attributes:
        PUBLIC: No authentication required (e.g., registration, login)
        AUTHENTICATED: Requires valid JWT (AuthenticatedUser dependency)
        ADMIN: Requires admin role (CurrentUser + Casbin check)
        MANUAL_AUTH: Route handles auth manually (e.g., sessions with custom error mapping)
    """

    PUBLIC = "public"
    AUTHENTICATED = "authenticated"
    ADMIN = "admin"
    MANUAL_AUTH = "manual_auth"


# =============================================================================
# Rate Limit Policy
# =============================================================================


class RateLimitPolicy(str, Enum):
    """Rate limit policy for routes.

    Each policy maps to a RateLimitRule with specific limits and scope.
    Policies are organized by endpoint category and sensitivity.

    Auth endpoints (IP-scoped, restrictive):
        AUTH_LOGIN: 5/min per IP (credential stuffing prevention)
        AUTH_REGISTER: 3/min per IP (mass account creation prevention)
        AUTH_PASSWORD_RESET: 3/min per IP, slow refill (email flooding prevention)
        AUTH_TOKEN_REFRESH: 10/min per user (automated token refresh)

    Provider endpoints (user-scoped, moderate):
        PROVIDER_CONNECT: 5/min per user (OAuth flow rate limiting)
        PROVIDER_SYNC: 10/min per user-provider (external API protection)

    API endpoints (user-scoped, generous):
        API_READ: 100/min per user (read operations)
        API_WRITE: 50/min per user (write operations)

    Expensive operations (user-scoped, restrictive):
        EXPENSIVE_EXPORT: 5 burst, 1/min per user (large data queries)
        REPORT: 10 burst, 2/min per user (computation-heavy)

    Global limits (emergency brake):
        GLOBAL: 10k/min across all users (DDoS protection, disabled by default)

    Reference:
        - docs/architecture/rate-limit-architecture.md
    """

    # Auth endpoints (IP-scoped)
    AUTH_LOGIN = "auth_login"
    AUTH_REGISTER = "auth_register"
    AUTH_PASSWORD_RESET = "auth_password_reset"
    AUTH_TOKEN_REFRESH = "auth_token_refresh"

    # Provider endpoints (user-scoped or user-provider-scoped)
    PROVIDER_CONNECT = "provider_connect"
    PROVIDER_SYNC = "provider_sync"

    # Standard API endpoints (user-scoped)
    API_READ = "api_read"
    API_WRITE = "api_write"

    # Expensive operations (user-scoped, restrictive)
    EXPENSIVE_EXPORT = "expensive_export"
    REPORT = "report"

    # Global limits (emergency brake)
    GLOBAL = "global"


# =============================================================================
# Idempotency Level
# =============================================================================


class IdempotencyLevel(str, Enum):
    """HTTP idempotency classification.

    Attributes:
        SAFE: No side effects (GET, HEAD, OPTIONS) - cacheable
        IDEMPOTENT: Side effects, but repeatable (PUT, DELETE) - safe to retry
        NON_IDEMPOTENT: Side effects, not repeatable (POST, PATCH) - do not retry

    Reference:
        - RFC 7231 Section 4.2 (HTTP Semantics)
    """

    SAFE = "safe"
    IDEMPOTENT = "idempotent"
    NON_IDEMPOTENT = "non_idempotent"


# =============================================================================
# Error Specification
# =============================================================================


@dataclass(frozen=True, kw_only=True)
class ErrorSpec:
    """Error response specification for OpenAPI documentation.

    Attributes:
        status: HTTP status code (e.g., 400, 404, 500)
        description: Human-readable error description
        model: Optional Pydantic model for response (defaults to ProblemDetails)

    Examples:
        >>> ErrorSpec(status=400, description="Validation error")
        >>> ErrorSpec(status=404, description="User not found")
        >>> ErrorSpec(status=409, description="Email already registered")
    """

    status: int
    description: str
    model: type[BaseModel] | None = None


# =============================================================================
# Cache Policy
# =============================================================================


class CachePolicy(str, Enum):
    """HTTP caching policy for GET endpoints.

    Attributes:
        NONE: No caching headers (default for most endpoints)
        PRIVATE: Cache-Control: private (user-specific data)
        NO_STORE: Cache-Control: no-store (sensitive data, never cache)

    Reference:
        - RFC 7234 (HTTP Caching)
    """

    NONE = "none"
    PRIVATE = "private"
    NO_STORE = "no_store"


# =============================================================================
# Route Metadata (SSOT)
# =============================================================================


@dataclass(frozen=True, kw_only=True)
class RouteMetadata:
    """Complete specification for an API route (Single Source of Truth).

    This dataclass contains all metadata needed to generate a FastAPI route,
    including method, path, handler, auth policy, rate limits, and OpenAPI docs.

    Identity fields:
        method: HTTP method (GET, POST, etc.)
        path: URL path with placeholders (e.g., "/api/v1/accounts/{account_id}")
        handler: Async function that implements the endpoint

    Grouping fields:
        resource: Resource category (e.g., "accounts", "users")
        tags: OpenAPI tags (e.g., ["Accounts"])
        version: API version (e.g., "v1")

    OpenAPI documentation:
        summary: Short endpoint description (appears in OpenAPI UI)
        description: Detailed endpoint description (markdown supported)
        operation_id: Stable operation ID for client generation

    Request/Response:
        request_model: Optional Pydantic model for request body
        response_model: Pydantic model for success response
        status_code: Expected success status (e.g., 200, 201, 204)
        errors: List of possible error responses for OpenAPI

    Behavior:
        idempotency: HTTP idempotency level (safe, idempotent, non_idempotent)
        auth_policy: Authentication policy (public, authenticated, admin, manual_auth)
        rate_limit_policy: Rate limit policy (auth_login, api_read, etc.)
        cache_policy: HTTP caching policy for GETs (none, private, no_store)

    Deprecation:
        deprecated: Whether endpoint is deprecated
        replacement: Optional replacement endpoint path

    Examples:
        >>> # Simple GET endpoint
        >>> RouteMetadata(
        ...     method=HTTPMethod.GET,
        ...     path="/api/v1/users/me",
        ...     handler=get_current_user_handler,
        ...     resource="users",
        ...     tags=["Users"],
        ...     summary="Get current user",
        ...     response_model=UserResponse,
        ...     status_code=200,
        ...     idempotency=IdempotencyLevel.SAFE,
        ...     auth_policy=AuthPolicy(level=AuthLevel.AUTHENTICATED),
        ...     rate_limit_policy=RateLimitPolicy.API_READ,
        ... )
        >>>
        >>> # POST endpoint with request body
        >>> RouteMetadata(
        ...     method=HTTPMethod.POST,
        ...     path="/api/v1/users",
        ...     handler=create_user_handler,
        ...     resource="users",
        ...     tags=["Users"],
        ...     summary="Create user",
        ...     description="Register a new user account. Sends verification email.",
        ...     operation_id="create_user",
        ...     request_model=UserCreateRequest,
        ...     response_model=UserCreateResponse,
        ...     status_code=201,
        ...     errors=[
        ...         ErrorSpec(status=400, description="Validation error"),
        ...         ErrorSpec(status=409, description="Email already registered"),
        ...     ],
        ...     idempotency=IdempotencyLevel.NON_IDEMPOTENT,
        ...     auth_policy=AuthPolicy(level=AuthLevel.PUBLIC),
        ...     rate_limit_policy=RateLimitPolicy.AUTH_REGISTER,
        ... )

    Reference:
        - docs/architecture/registry-pattern-architecture.md
    """

    # Identity
    method: HTTPMethod
    path: str
    handler: Callable[..., Awaitable[Any]]

    # Grouping
    resource: str
    tags: Sequence[str]
    version: str = "v1"

    # OpenAPI documentation
    summary: str
    description: str | None = None
    operation_id: str | None = None

    # Request/Response
    request_model: type[BaseModel] | None = None
    response_model: type[BaseModel] | None = None
    status_code: int = 200
    errors: list[ErrorSpec] | None = None

    # Behavior
    idempotency: IdempotencyLevel
    auth_policy: AuthPolicy
    rate_limit_policy: RateLimitPolicy
    cache_policy: CachePolicy = CachePolicy.NONE

    # Deprecation
    deprecated: bool = False
    replacement: str | None = None
