# Route Registry Architecture

## Overview

The Route Metadata Registry is Dashtam's **single source of truth** for all API endpoints. It eliminates decorator sprawl by declaratively defining all 36 routes with their metadata (auth policies, rate limits, error specs, OpenAPI metadata) in a single registry. FastAPI routes, auth dependencies, rate limit rules, and OpenAPI documentation are **auto-generated** from this registry at startup.

This is a **specific implementation** of Dashtam's general [Registry Pattern](registry-pattern-architecture.md), applied to API route management.

---

## Problem Statement

### Decorator Sprawl and Manual Drift

**Before F8.2**, API routes were defined using FastAPI decorators scattered across 12 router files:

```python
# src/presentation/routers/api/v1/users.py
@router.post("/users", status_code=201, summary="Create user", tags=["Users"])
async def create_user(data: UserCreate):
    ...

# src/presentation/routers/api/v1/sessions.py
@router.post("/sessions", status_code=201, summary="Login", tags=["Authentication"])
async def create_session(data: LoginRequest):
    ...

# ... 34 more endpoints across 12 files
```

**Manual coordination required**:

1. Define route with `@router` decorator
2. Add auth dependency (`Depends(get_current_user)`)
3. Add rate limit rule in `src/infrastructure/rate_limit/config.py`
4. Add OpenAPI metadata (summary, tags, operation_id)
5. Add error specs for OpenAPI docs
6. Update tests for new endpoint

**Problems**:

- ❌ **Drift**: Easy to forget rate limit rules or auth dependencies
- ❌ **Inconsistency**: Auth policies vary by endpoint (some missing)
- ❌ **Duplication**: Metadata repeated in decorators, rate limits, tests
- ❌ **Hard to audit**: No single place to see all endpoints
- ❌ **Fragile**: Changing endpoint requires updates in 3+ files

---

## Solution Overview

**Route Metadata Registry** centralizes ALL route metadata in `src/presentation/routers/api/v1/routes/registry.py`:

```python
RouteMetadata(
    method=HTTPMethod.POST,
    path="/users",
    handler=create_user,
    resource="users",
    tags=["Users"],
    summary="Create user",
    operation_id="create_user",
    response_model=UserCreateResponse,
    status_code=201,
    errors=[
        ErrorSpec(status=400, description="Validation failed"),
        ErrorSpec(status=409, description="User already exists"),
    ],
    idempotency=IdempotencyLevel.NON_IDEMPOTENT,
    auth_policy=AuthPolicy(level=AuthLevel.PUBLIC),
    rate_limit_policy=RateLimitPolicy.AUTH_REGISTER,
)
```

**Auto-generated from registry**:

1. ✅ FastAPI routes registered with `router.add_api_route()`
2. ✅ Auth dependencies injected based on `auth_policy`
3. ✅ Rate limit rules generated from `rate_limit_policy`
4. ✅ OpenAPI metadata (summary, tags, operation_id, error specs)
5. ✅ Self-enforcing tests prevent drift

**Benefits**:

- ✅ **Single source of truth**: All 36 endpoints in one file
- ✅ **Zero drift**: Tests fail if metadata incomplete
- ✅ **Consistency**: Auth/rate limits enforced for all endpoints
- ✅ **Auditability**: See all API surface area in one place
- ✅ **Maintainability**: Change once, updates everywhere

---

## Architecture Components

### Component 1: Registry File

**Location**: `src/presentation/routers/api/v1/routes/registry.py`

**Structure**:

```python
from src.presentation.routers.api.v1.routes.metadata import (
    RouteMetadata,
    HTTPMethod,
    AuthPolicy,
    AuthLevel,
    RateLimitPolicy,
    IdempotencyLevel,
    ErrorSpec,
)
from src.presentation.routers.api.v1.users import create_user
from src.presentation.routers.api.v1.sessions import (
    create_session,
    delete_current_session,
    list_sessions,
    # ... other handlers
)

ROUTE_REGISTRY: list[RouteMetadata] = [
    # Users (1 endpoint)
    RouteMetadata(
        method=HTTPMethod.POST,
        path="/users",
        handler=create_user,
        resource="users",
        tags=["Users"],
        summary="Create user",
        operation_id="create_user",
        response_model=UserCreateResponse,
        status_code=201,
        errors=[
            ErrorSpec(status=400, description="Validation failed"),
            ErrorSpec(status=409, description="User already exists"),
        ],
        idempotency=IdempotencyLevel.NON_IDEMPOTENT,
        auth_policy=AuthPolicy(level=AuthLevel.PUBLIC),
        rate_limit_policy=RateLimitPolicy.AUTH_REGISTER,
    ),
    
    # Sessions (6 endpoints)
    RouteMetadata(
        method=HTTPMethod.POST,
        path="/sessions",
        handler=create_session,
        resource="sessions",
        tags=["Authentication"],
        summary="Login user",
        operation_id="create_session",
        response_model=SessionResponse,
        status_code=201,
        errors=[
            ErrorSpec(status=400, description="Invalid credentials"),
            ErrorSpec(status=429, description="Rate limit exceeded"),
        ],
        idempotency=IdempotencyLevel.NON_IDEMPOTENT,
        auth_policy=AuthPolicy(
            level=AuthLevel.MANUAL_AUTH,
            rationale="Sessions endpoint handles auth manually (creates tokens)",
        ),
        rate_limit_policy=RateLimitPolicy.AUTH_LOGIN,
    ),
    
    # ... 34 more endpoints (total 36)
]
```

**Key Properties**:

- **Exhaustive**: All 36 endpoints registered
- **Type-safe**: `RouteMetadata` dataclass with type hints
- **Immutable**: `frozen=True` prevents accidental modification
- **Centralized**: Single file, easy to audit

### Component 2: Metadata Types

**Location**: `src/presentation/routers/api/v1/routes/metadata.py`

**RouteMetadata Dataclass**:

```python
@dataclass(frozen=True, kw_only=True)
class RouteMetadata:
    """Metadata for a single API route."""
    
    # Core routing
    method: HTTPMethod
    path: str
    handler: Callable
    
    # OpenAPI documentation
    resource: str
    tags: list[str]
    summary: str
    operation_id: str
    description: str | None = None
    
    # Request/Response
    request_model: type[BaseModel] | None = None
    response_model: type[BaseModel] | None = None
    status_code: int = 200
    
    # Error handling (RFC 7807)
    errors: list[ErrorSpec] = field(default_factory=list)
    
    # Policies
    auth_policy: AuthPolicy
    rate_limit_policy: RateLimitPolicy
    idempotency: IdempotencyLevel
```

**Supporting Enums**:

```python
class HTTPMethod(str, Enum):
    """HTTP methods for API routes."""
    GET = "GET"
    POST = "POST"
    PATCH = "PATCH"
    DELETE = "DELETE"

class AuthLevel(str, Enum):
    """Authentication/authorization levels."""
    PUBLIC = "public"              # No auth required
    AUTHENTICATED = "authenticated"  # Requires valid token
    ADMIN = "admin"                # Requires admin role
    MANUAL_AUTH = "manual_auth"    # Handler manages auth

class RateLimitPolicy(str, Enum):
    """Rate limit policies for endpoints."""
    AUTH_LOGIN = "auth_login"              # 5 req/min (IP scope)
    AUTH_REGISTER = "auth_register"        # 3 req/hour (IP scope)
    AUTH_TOKEN_REFRESH = "auth_token_refresh"  # 10 req/min (USER scope)
    AUTH_PASSWORD_RESET = "auth_password_reset"  # 3 req/hour (IP scope)
    API_READ = "api_read"                  # 100 req/min (USER scope)
    API_WRITE = "api_write"                # 50 req/min (USER scope)
    PROVIDER_CONNECT = "provider_connect"  # 5 req/hour (USER scope)
    PROVIDER_SYNC = "provider_sync"        # 10 req/min (USER_PROVIDER scope)

class IdempotencyLevel(str, Enum):
    """HTTP idempotency semantics."""
    SAFE = "safe"                  # GET (no side effects)
    IDEMPOTENT = "idempotent"      # PUT, DELETE (same result if repeated)
    NON_IDEMPOTENT = "non_idempotent"  # POST (creates new resource)

@dataclass(frozen=True, kw_only=True)
class ErrorSpec:
    """Error specification for OpenAPI documentation."""
    status: int
    description: str
    model: type[BaseModel] | None = None
```

### Component 3: Route Generator

**Location**: `src/presentation/routers/api/v1/routes/generator.py`

**Purpose**: Convert registry entries into FastAPI routes.

```python
def register_routes_from_registry(
    router: APIRouter,
    registry: list[RouteMetadata]
) -> None:
    """Generate FastAPI routes from registry metadata.
    
    For each registry entry:
    1. Generate auth dependencies from auth_policy
    2. Create FastAPI route with router.add_api_route()
    3. Inject metadata (summary, tags, operation_id, errors)
    """
    for entry in registry:
        # Build dependencies (auth, rate limit, etc.)
        dependencies = _build_dependencies(entry)
        
        # Register route with FastAPI
        router.add_api_route(
            path=entry.path,
            endpoint=entry.handler,
            methods=[entry.method.value],
            response_model=entry.response_model,
            status_code=entry.status_code,
            summary=entry.summary,
            description=entry.description,
            operation_id=entry.operation_id,
            tags=entry.tags,
            dependencies=dependencies,
            responses=_build_error_responses(entry.errors),
        )

def _build_dependencies(entry: RouteMetadata) -> list[Depends]:
    """Build FastAPI dependencies from metadata."""
    deps = []
    
    # Auth dependencies
    if entry.auth_policy.level == AuthLevel.AUTHENTICATED:
        deps.append(Depends(get_current_user))
    elif entry.auth_policy.level == AuthLevel.ADMIN:
        deps.append(Depends(require_role(UserRole.ADMIN)))
    # MANUAL_AUTH and PUBLIC have no injected dependencies
    
    return deps
```

### Component 4: Rate Limit Generation

**Two-Tier Configuration Pattern** (like CSS classes):

**Tier 1: Policy Assignment** (`registry.py`):

```python
RouteMetadata(
    path="/sessions",
    rate_limit_policy=RateLimitPolicy.AUTH_LOGIN,  # ← Assign policy
    ...
)
```

**Tier 2: Policy Implementation** (`derivations.py`):

```python
def build_rate_limit_rules(registry: list[RouteMetadata]) -> dict[str, RateLimitRule]:
    """Generate rate limit rules from registry."""
    
    # Define what each policy means
    policy_rules = {
        RateLimitPolicy.AUTH_LOGIN: RateLimitRule(
            max_tokens=5,
            refill_rate=5.0,
            cost=1,
            scope=RateLimitScope.IP,
            enabled=True,
        ),
        RateLimitPolicy.API_READ: RateLimitRule(
            max_tokens=100,
            refill_rate=100.0,
            cost=1,
            scope=RateLimitScope.USER,
            enabled=True,
        ),
        # ... other policies
    }
    
    # Map each endpoint to its rule
    rules = {}
    for entry in registry:
        endpoint_key = f"{entry.method.value} /api/v1{entry.path}"
        rules[endpoint_key] = policy_rules[entry.rate_limit_policy]
    
    return rules
```

**Auto-Generated Rules** (`from_registry.py`):

```python
from src.presentation.routers.api.v1.routes.registry import ROUTE_REGISTRY
from src.presentation.routers.api.v1.routes.derivations import build_rate_limit_rules

# Generated at module load time
RATE_LIMIT_RULES = build_rate_limit_rules(ROUTE_REGISTRY)
```

**Benefits**:

- ✅ Modify rate limits in **one place** (derivations.py)
- ✅ Apply same policy to **multiple endpoints** (like CSS class)
- ✅ Registry stays clean (just policy name, not full config)
- ✅ Type-safe (enum ensures valid policies)

### Component 5: Handler Pattern (Pure Functions)

**Old Pattern** (decorator-based):

```python
# ❌ OLD: Router created, decorators applied
router = APIRouter()

@router.post("/users", status_code=201, summary="Create user")
async def create_user(data: UserCreate):
    ...
```

**New Pattern** (pure functions):

```python
# ✅ NEW: Pure function, NO decorators
async def create_user(
    data: UserCreate,
    handler: RegisterUserHandler = Depends(get_register_handler),
) -> UserCreateResponse:
    """Create new user account.
    
    Handler registered in ROUTE_REGISTRY, not via decorator.
    """
    result = await handler.handle(RegisterUser(**data.model_dump()))
    
    if isinstance(result, Failure):
        return ErrorResponseBuilder.from_application_error(
            error=result.error,
            request_path="/api/v1/users"
        )
    
    user_id = result.value
    return UserCreateResponse(id=user_id, email=data.email)
```

**Benefits**:

- ✅ **Testable**: Pure functions easy to test (no FastAPI mocks)
- ✅ **Reusable**: Can call from multiple routes if needed
- ✅ **No coupling**: No dependency on FastAPI decorators
- ✅ **Clean**: Handler signature is just function parameters

---

## Self-Enforcing Tests

**Location**: `tests/api/test_route_metadata_registry_compliance.py`

**Test Classes** (18 tests total):

### 1. Registry Completeness (6 tests)

```python
def test_all_routes_are_registered():
    """Every FastAPI route must have a registry entry."""
    # Introspect v1_router.routes
    actual_routes = {f"{method} {path}" for route in v1_router.routes}
    
    # Compare with registry
    expected_routes = {f"{e.method.value} /api/v1{e.path}" for e in ROUTE_REGISTRY}
    
    assert actual_routes == expected_routes, "Drift detected!"

def test_operation_ids_are_unique():
    """Operation IDs must be unique (OpenAPI requirement)."""
    operation_ids = [e.operation_id for e in ROUTE_REGISTRY]
    duplicates = [op for op in set(operation_ids) if operation_ids.count(op) > 1]
    assert not duplicates, f"Duplicate operation IDs: {duplicates}"

def test_all_handlers_are_callable():
    """Every handler must be a callable function."""
    for entry in ROUTE_REGISTRY:
        assert callable(entry.handler), f"{entry.path} has non-callable handler"

def test_all_routes_have_tags():
    """Every route must have tags for OpenAPI grouping."""
    for entry in ROUTE_REGISTRY:
        assert entry.tags, f"{entry.path} has no tags"

def test_all_routes_have_operation_id():
    """Every route must have operation_id for client generation."""
    for entry in ROUTE_REGISTRY:
        assert entry.operation_id, f"{entry.path} has no operation_id"

def test_all_routes_have_resource_name():
    """Every route must have resource name for grouping."""
    for entry in ROUTE_REGISTRY:
        assert entry.resource, f"{entry.path} has no resource name"
```

### 2. Auth Policy Enforcement (3 tests)

```python
def test_public_routes_have_no_auth_dependencies():
    """PUBLIC routes should not inject auth dependencies."""
    for entry in ROUTE_REGISTRY:
        if entry.auth_policy.level == AuthLevel.PUBLIC:
            sig = inspect.signature(entry.handler)
            for param in sig.parameters.values():
                assert "CurrentUser" not in str(param.annotation)

def test_authenticated_routes_have_auth_or_manual():
    """AUTHENTICATED routes must have CurrentUser OR MANUAL_AUTH."""
    for entry in ROUTE_REGISTRY:
        if entry.auth_policy.level == AuthLevel.AUTHENTICATED:
            sig = inspect.signature(entry.handler)
            has_auth = any("CurrentUser" in str(p.annotation) for p in sig.parameters.values())
            is_manual = entry.auth_policy.level == AuthLevel.MANUAL_AUTH
            assert has_auth or is_manual

def test_manual_auth_routes_have_rationale():
    """MANUAL_AUTH routes must document why."""
    for entry in ROUTE_REGISTRY:
        if entry.auth_policy.level == AuthLevel.MANUAL_AUTH:
            assert entry.auth_policy.rationale
            assert len(entry.auth_policy.rationale) > 10
```

### 3. Rate Limit Coverage (4 tests)

```python
def test_all_registry_entries_have_rate_limit_policy():
    """Every endpoint must have rate limit policy."""
    for entry in ROUTE_REGISTRY:
        assert entry.rate_limit_policy is not None

def test_rate_limit_rules_cover_all_registry_entries():
    """Generated rules must cover all endpoints."""
    generated_rules = build_rate_limit_rules(ROUTE_REGISTRY)
    for entry in ROUTE_REGISTRY:
        endpoint_key = f"{entry.method.value} /api/v1{entry.path}"
        assert endpoint_key in generated_rules

def test_no_orphaned_rate_limit_rules():
    """Rules should only exist for registered routes."""
    registry_endpoints = {f"{e.method.value} /api/v1{e.path}" for e in ROUTE_REGISTRY}
    for rule_endpoint in RATE_LIMIT_RULES.keys():
        assert rule_endpoint in registry_endpoints

def test_rate_limit_rules_have_positive_values():
    """Rules must have valid positive values."""
    for endpoint, rule in RATE_LIMIT_RULES.items():
        assert rule.max_tokens > 0
        assert rule.refill_rate > 0
        assert rule.cost > 0
```

### 4. Metadata Consistency (4 tests)

```python
def test_registry_matches_fastapi_routes():
    """Registry metadata must match generated FastAPI routes."""
    for entry in ROUTE_REGISTRY:
        endpoint_key = f"{entry.method.value} /api/v1{entry.path}"
        fastapi_route = get_route_from_router(v1_router, endpoint_key)
        
        assert fastapi_route.summary == entry.summary
        assert fastapi_route.status_code == entry.status_code

def test_response_models_are_defined():
    """All non-204 routes must have response_model."""
    for entry in ROUTE_REGISTRY:
        if entry.status_code == 204:
            assert entry.response_model is None
        else:
            assert entry.response_model is not None

def test_error_specs_are_valid():
    """Error specs must have valid HTTP status codes."""
    valid_statuses = {400, 401, 403, 404, 409, 415, 422, 429, 500, 502, 503}
    for entry in ROUTE_REGISTRY:
        for error_spec in entry.errors:
            assert error_spec.status in valid_statuses
            assert error_spec.description

def test_path_parameters_match_handler_signature():
    """Path params must exist in handler signature."""
    for entry in ROUTE_REGISTRY:
        path_params = re.findall(r"\{(\w+)\}", entry.path)
        if path_params:
            sig = inspect.signature(entry.handler)
            handler_params = set(sig.parameters.keys())
            missing = set(path_params) - handler_params
            assert not missing, f"{entry.path} missing params: {missing}"
```

### 5. Statistics Reporting (1 test)

```python
def test_registry_statistics():
    """Report comprehensive registry statistics (always passes)."""
    stats = {
        "Total Endpoints": len(ROUTE_REGISTRY),
        "HTTP Methods": count_by(lambda e: e.method.value),
        "Auth Policies": count_by(lambda e: e.auth_policy.level.value),
        "Rate Limit Policies": count_by(lambda e: e.rate_limit_policy.value),
        "Idempotency Levels": count_by(lambda e: e.idempotency.value),
    }
    print_statistics(stats)  # Visible with pytest -v -s
    assert True  # Always passes (informational)
```

**Benefits**:

- ✅ **Zero drift**: Tests fail if registry incomplete
- ✅ **Self-updating**: Tests adapt to registry changes automatically
- ✅ **Comprehensive**: 18 tests cover all aspects
- ✅ **Fast**: All tests run in <1 second

---

## Integration with Existing Systems

### RFC 7807 Error Handling

Route registry includes error specs for OpenAPI docs:

```python
RouteMetadata(
    path="/users",
    errors=[
        ErrorSpec(status=400, description="Validation failed"),
        ErrorSpec(status=409, description="User already exists"),
    ],
    ...
)
```

Handlers return RFC 7807 Problem Details:

```python
async def create_user(...) -> UserCreateResponse:
    result = await handler.handle(...)
    
    if isinstance(result, Failure):
        # RFC 7807 error response
        return ErrorResponseBuilder.from_application_error(
            error=result.error,
            request_path="/api/v1/users"
        )
    
    return UserCreateResponse(id=result.value, ...)
```

**Reference**: `docs/guides/error-handling-guide.md`

### Dependency Injection

Handlers use FastAPI `Depends()` for dependencies:

```python
async def create_user(
    data: UserCreate,
    handler: RegisterUserHandler = Depends(get_register_handler),
) -> UserCreateResponse:
    ...
```

Container functions return protocol types:

```python
def get_register_handler() -> RegisterUserHandler:
    from src.core.container import get_user_repository
    return RegisterUserHandler(user_repo=get_user_repository())
```

**Reference**: `docs/architecture/dependency-injection-architecture.md`

### CQRS Pattern

Handlers dispatch to CQRS command/query handlers:

```python
async def create_user(...) -> UserCreateResponse:
    # Create command
    command = RegisterUser(email=data.email, password=data.password)
    
    # Dispatch to command handler
    result = await handler.handle(command)
    
    # Return response or error
    ...
```

**Reference**: `docs/architecture/cqrs-pattern.md`

---

## Evolution and Maintenance

### Adding a New Endpoint

**Process** (enforced by tests):

1. **Write handler function** (pure function, no decorator)
2. **Add entry to ROUTE_REGISTRY**
3. **Run tests** → they tell you what's missing
4. **Add missing pieces** (auth deps, rate limits, etc.)
5. **Tests pass** ✅

**Example**:

```python
# Step 1: Write handler
async def get_account_balance(
    account_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
) -> BalanceResponse:
    ...

# Step 2: Add to registry
RouteMetadata(
    method=HTTPMethod.GET,
    path="/accounts/{account_id}/balance",
    handler=get_account_balance,
    resource="accounts",
    tags=["Accounts"],
    summary="Get account balance",
    operation_id="get_account_balance",
    response_model=BalanceResponse,
    status_code=200,
    errors=[
        ErrorSpec(status=404, description="Account not found"),
    ],
    idempotency=IdempotencyLevel.SAFE,
    auth_policy=AuthPolicy(level=AuthLevel.AUTHENTICATED),
    rate_limit_policy=RateLimitPolicy.API_READ,
)

# Step 3-5: Run tests, fix issues, tests pass
```

### Changing Rate Limits

**Modify policy definition** (affects all endpoints with that policy):

```python
# src/presentation/routers/api/v1/routes/derivations.py
RateLimitPolicy.API_READ: RateLimitRule(
    max_tokens=200,  # ← Changed from 100
    refill_rate=200.0,
    ...
)
```

All endpoints with `rate_limit_policy=RateLimitPolicy.API_READ` now use new limit.

### Deprecating an Endpoint

**Mark in registry** (future feature):

```python
RouteMetadata(
    path="/legacy-endpoint",
    deprecated=True,
    deprecation_message="Use /v2/new-endpoint instead",
    ...
)
```

Generator can add deprecation warnings to OpenAPI docs.

---

## Comparison with Other Registries

| Registry | Purpose | Scope | Components |
|----------|---------|-------|------------|
| **Route Registry** | API endpoints | 36 routes | Metadata, Generator, Rate Limits, Tests |
| **Provider Registry** | OAuth providers | 1 provider (Schwab) | Metadata, Adapters, Validators, Tests |
| **Domain Events Registry** | Domain events | 50+ events | Metadata, Handlers, Auto-Wiring, Tests |
| **Validation Registry** | Validators | 20+ validators | Metadata, Rules, Decorators, Tests |

**Common Pattern**: Single source of truth + Auto-generation + Self-enforcing tests.

---

## Benefits

### Before Registry (Manual)

- **12 router files** with scattered decorators
- **Manual rate limit rules** in separate file
- **Inconsistent auth** (some endpoints missing)
- **OpenAPI gaps** (missing summaries, tags)
- **Hard to audit** (can't see all endpoints)
- **Drift-prone** (easy to forget rate limits)

### After Registry (Automated)

- **1 registry file** with all 36 endpoints
- **Auto-generated rate limits** (zero drift)
- **Consistent auth** (enforced by tests)
- **Complete OpenAPI** (metadata from registry)
- **Easy audit** (single file shows all routes)
- **Zero drift** (tests catch incomplete metadata)

---

## References

- **Implementation**: `src/presentation/routers/api/v1/routes/`
- **Tests**: `tests/api/test_route_metadata_registry_compliance.py`
- **General Pattern**: [Registry Pattern Architecture](registry-pattern-architecture.md)
- **Error Handling**: [Error Handling Guide](../guides/error-handling-guide.md)
- **User Documentation**: `WARP.md` Section 9a (Route Metadata Registry Pattern)

---

**Created**: 2025-12-31 | **Last Updated**: 2025-12-31
