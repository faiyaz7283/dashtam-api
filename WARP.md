# Dashtam Project Rules and Context

**Purpose**: Single source of truth for AI agents - architectural standards, development workflow, and project context.

**External Reference**:

- `~/references/starter/dashtam-feature-roadmap.md` - Feature roadmap with Phase 2-6 implementation details
- `~/references/dashtam-production-deployment-options.md` - Production deployment options, costs, TLS/auth, CI/CD, IaC

**Architecture Documentation**:

- `docs/architecture/hexagonal.md` - Hexagonal architecture theory, ports & adapters, dependency rule
- `docs/architecture/protocols.md` - Protocol-based design, structural typing, testing with protocols
- `docs/architecture/domain-driven-design.md` - Pragmatic DDD, entities vs value objects, domain events, patterns used/skipped

---

**Last Updated**: 2026-01-14

## 1. Project Overview

**Dashtam** is a secure, modern financial data aggregation platform built from the ground up with clean architecture principles.

**Core Architecture**:

- **Hexagonal Architecture**: Domain at center, infrastructure at edges
- **CQRS Pattern**: Commands (write) separated from Queries (read)
- **Domain-Driven Design**: Pragmatic DDD with domain events for critical workflows
- **Protocol-Based**: Structural typing with Python `Protocol` (not ABC)
- **Event Registry Pattern**: Single source of truth for domain events with automated container wiring

**Technology Stack**:

- **Backend**: FastAPI (async), Python 3.14+
- **Database**: PostgreSQL 17+ with async SQLAlchemy
- **Cache**: Redis 8.2+ (async)
- **Package Manager**: UV 0.9.21+ (NOT pip)
- **Containers**: Docker Compose v2, Traefik reverse proxy
- **Testing**: pytest with TestClient (synchronous strategy)
- **CI/CD**: GitHub Actions with Codecov

**Development Philosophy**:

- **Clean slate**: No legacy code, fresh implementation
- **Type safety**: Type hints everywhere, Result types for error handling
- **100% REST compliance**: Non-negotiable for all API endpoints
- **Test-driven**: 85%+ coverage target, all tests pass before merge
- **Documentation-first**: Architecture decisions documented before coding

---

## 2. Current Status

**For detailed feature history, PRs, version releases, and implementation details**: See `CHANGELOG.md`

**GitHub Releases**: <https://github.com/faiyaz7283/Dashtam/releases>

---

## Part 2: Architecture Standards

### 3. Hexagonal Architecture

**Core Principle**: Domain logic at the center, infrastructure at the edges. Domain depends on NOTHING.

**Layer Responsibilities**:

```text
┌─────────────────────────────────────────────────────┐
│ Presentation Layer (API)                            │
│ - FastAPI routers                                   │
│ - Request/response schemas                          │
│ - HTTP concerns only                                │
└──────────────────┬──────────────────────────────────┘
                   │ depends on
                   ↓
┌─────────────────────────────────────────────────────┐
│ Application Layer (Use Cases)                       │
│ - Commands & Queries (CQRS)                         │
│ - Command/Query Handlers                            │
│ - Event handlers                                    │
└──────────────────┬──────────────────────────────────┘
                   │ depends on
                   ↓
┌─────────────────────────────────────────────────────┐
│ Domain Layer (Business Logic) ← CORE                │
│ - Entities & Value Objects                          │
│ - Domain Events                                     │
│ - Protocols (Ports)                                 │
│ - NO framework imports                              │
└─────────────────────────────────────────────────────┘
                   ↑ implements
                   │
┌─────────────────────────────────────────────────────┐
│ Infrastructure Layer (Adapters)                     │
│ - Database repositories                             │
│ - External API clients                              │
│ - Provider implementations                          │
└─────────────────────────────────────────────────────┘
```

**Dependency Rule** (CRITICAL):

- ✅ Domain depends on NOTHING
- ✅ Infrastructure depends on Domain (implements ports)
- ✅ Application depends on Domain (uses entities, protocols)
- ✅ Presentation depends on Application (dispatches commands/queries)
- ❌ NEVER let Domain depend on Infrastructure or Presentation

**Ports & Adapters**:

```python
# Domain defines PORT (protocol) - src/domain/protocols/
class UserRepository(Protocol):
    async def find_by_email(self, email: str) -> User | None: ...
    async def save(self, user: User) -> None: ...

# Infrastructure implements ADAPTER - src/infrastructure/persistence/
class PostgresUserRepository:  # No inheritance!
    async def find_by_email(self, email: str) -> User | None:
        # Database logic here
        ...
```

**Protocol Location**: ALL protocols go in `src/domain/protocols/` (consolidated, no separate `domain/repositories/`).

---

### 4. Modern Python Patterns

**CRITICAL**: Use Python 3.14+ features consistently.

#### Protocol over ABC (Mandatory)

```python
# ✅ CORRECT: Use Protocol
from typing import Protocol

class CacheProtocol(Protocol):
    async def get(self, key: str) -> str | None: ...
    async def set(self, key: str, value: str, ttl: int) -> None: ...

# Implementation doesn't inherit
class RedisCache:  # No inheritance!
    async def get(self, key: str) -> str | None:
        return await self.redis.get(key)

# ❌ WRONG: Don't use ABC for new interfaces
from abc import ABC, abstractmethod
class CacheBackend(ABC):  # Don't do this
    @abstractmethod
    async def get(self, key: str) -> str | None:
        pass
```

#### Type Hints Everywhere

```python
# ✅ CORRECT: Modern type hints
def process_user(user_id: UUID, data: dict[str, Any]) -> User | None:
    ...

# ❌ WRONG: Old-style Optional, Dict, List
from typing import Optional, Dict, List
def process_user(user_id: UUID, data: Dict[str, Any]) -> Optional[User]:
    ...
```

**Rules**:

- All function parameters have type hints
- All return types specified
- Use `X | None` (NOT `Optional[X]`)
- Use `list`, `dict`, `set` (NOT `List`, `Dict`, `Set`)

#### Result Types (Railway-Oriented Programming)

```python
# Domain functions return Result (NO exceptions)
from core.result import Result, Success, Failure

def create_user(email: str) -> Result[User, ValidationError]:
    if not is_valid_email(email):
        return Failure(ValidationError("Invalid email"))
    return Success(user)
```

#### Pattern Matching with kw_only Dataclasses

**IMPORTANT**: When `Success` and `Failure` use `kw_only=True`, mypy reports errors with positional pattern matching.

```python
# ❌ WRONG - mypy error with kw_only dataclasses
match result:
    case Success(value):   # Error: requires keyword argument
        return value
    case Failure(error):   # Error: requires keyword argument  
        return handle_error(error)

# ✅ CORRECT - Use isinstance() checks instead
if isinstance(result, Failure):
    return Failure(error=result.error)

# After isinstance check, type narrowing gives us Success
value = result.value
```

**Full Pattern** (used throughout Dashtam):

```python
async def fetch_accounts(self, access_token: str) -> Result[list[Account], ProviderError]:
    result = await self._accounts_api.get_accounts(access_token)
    
    # Handle failure case first
    if isinstance(result, Failure):
        return Failure(error=result.error)
    
    # After isinstance, type narrowing knows this is Success
    raw_accounts = result.value
    
    # Continue processing...
    mapped = [self._mapper.map(acc) for acc in raw_accounts]
    return Success(value=mapped)
```

**When to Use Each**:

- **isinstance() checks**: When dataclasses use `kw_only=True` (Dashtam's pattern)
- **Pattern matching**: Only when dataclasses use positional arguments (no `kw_only`)

#### Annotated Types (Centralized Validation)

**File Structure**:

```text
src/domain/
├── types.py          # Annotated types (Email, Password, Money, etc.)
└── validators.py     # Validation functions (reusable)
```

```python
# src/domain/validators.py
def validate_email(v: str) -> str:
    """Validate email format."""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(pattern, v):
        raise ValueError(f"Invalid email format: {v}")
    return v.lower()

# src/domain/types.py
from typing import Annotated
from pydantic import Field, AfterValidator

Email = Annotated[
    str,
    Field(min_length=5, max_length=255),
    AfterValidator(validate_email)
]

Password = Annotated[
    str,
    Field(min_length=12, max_length=128),
    AfterValidator(validate_strong_password)
]

# Usage everywhere - validation included automatically
class UserCreate(BaseModel):
    email: Email
    password: Password
```

**Benefits**: Single source of truth, consistent validation, easy updates.

---

### 5. CQRS & Domain Events

#### CQRS Pattern (Command Query Responsibility Segregation)

**Principle**: Separate reads (Queries) from writes (Commands).

**Commands** (write operations):

```python
@dataclass(frozen=True, kw_only=True)
class RegisterUser:
    email: str
    password: str
    # Represents user INTENT

class RegisterUserHandler:
    async def handle(self, cmd: RegisterUser) -> Result[UUID, Error]:
        user = User(email=cmd.email, ...)
        await self.users.save(user)
        return Success(user.id)
```

**Queries** (read operations):

```python
@dataclass(frozen=True, kw_only=True)
class GetUser:
    user_id: UUID
    # Represents data NEED

class GetUserHandler:
    async def handle(self, query: GetUser) -> Result[User, Error]:
        return await self.users.find_by_id(query.user_id)
```

#### Domain Events (3-State ATTEMPT → OUTCOME Pattern)

**CRITICAL**: All critical workflows use 3-state pattern for audit semantic accuracy.

**Pattern**:

1. `*Attempted` - Before business logic (audit: ATTEMPTED)
2. `*Succeeded` - After successful commit (audit: outcome)
3. `*Failed` - After failure (audit: FAILED)

**Example Events**:

```python
# Authentication events
UserRegistrationAttempted, UserRegistrationSucceeded, UserRegistrationFailed
UserLoginAttempted, UserLoginSucceeded, UserLoginFailed

# Data sync events
AccountSyncAttempted, AccountSyncSucceeded, AccountSyncFailed
TransactionSyncAttempted, TransactionSyncSucceeded, TransactionSyncFailed
```

**Event Definition**:

```python
@dataclass(frozen=True, kw_only=True)
class UserRegistrationSucceeded(DomainEvent):
    """Emitted after successful user registration."""
    user_id: UUID
    email: str
```

**Event Handlers** (multiple per event):

- `LoggingEventHandler` - Logs all events (INFO/WARNING)
- `AuditEventHandler` - Creates audit records
- `EmailEventHandler` - Sends notifications (SUCCEEDED only)
- `SessionEventHandler` - Manages sessions (password change, etc.)

**When to Use Events**:

- ✅ **Critical workflows**: 3+ side effects OR requires ATTEMPT → OUTCOME audit
- ✅ **Operational events**: Single-state observability/monitoring (activity tracking, security monitoring) - NOT 3-state pattern
- ❌ **NOT for** simple reads or single-step operations

**Reference**: `docs/architecture/domain-events.md`

---

### 6. Event Registry Pattern (Single Source of Truth)

**Core Principle**: All domain events cataloged in `src/domain/events/registry.py` with automated container wiring.

**Purpose**:

- Single source of truth for all events
- Self-enforcing (tests fail if handlers missing)
- Auto-wiring (container uses registry)
- Gap detection built-in
- Future-proof (can't drift silently)

**Architecture**:

```text
src/domain/events/
├── registry.py           # EVENT_REGISTRY - single source of truth
├── auth_events.py        # Authentication events
├── provider_events.py    # Provider events
├── data_events.py        # Data sync events
├── session_events.py     # Session events
└── rate_limit_events.py  # Rate limit events
```

**Registry Entry Pattern**:

```python
EventMetadata(
    event_class=UserRegistrationAttempted,
    category=EventCategory.AUTHENTICATION,
    workflow_name="user_registration",
    phase=WorkflowPhase.ATTEMPTED,
    requires_logging=True,
    requires_audit=True,
    requires_email=False,
    requires_session=False,
    audit_action_name="USER_REGISTRATION_ATTEMPTED",
)
```

**Process for Adding New Events** (enforced by design):

1. Define event dataclass in `*_events.py`
2. Add entry to `EVENT_REGISTRY`
3. Run tests → they tell you what's missing
4. Add handler methods
5. Add AuditAction enum (if needed)
6. Tests pass ✅ (container auto-wires)

**Container Auto-Wiring** (in `src/core/container/events.py`):

```python
# Registry-driven subscription - replaces manual wiring
for metadata in EVENT_REGISTRY:
    if metadata.requires_logging:
        event_bus.subscribe(
            metadata.event_class,
            _get_handler_method(logging_handler, metadata)
        )
    if metadata.requires_audit:
        event_bus.subscribe(
            metadata.event_class,
            _get_handler_method(audit_handler, metadata)
        )
```

**Validation Tests** (prevent drift):

- `test_all_events_have_handler_methods()` - Fails if handler methods missing
- `test_all_events_have_audit_actions()` - Fails if AuditAction enum missing
- `test_registry_statistics()` - Verify counts match expectations

**Reference**: `src/domain/events/registry.py`, `tests/unit/test_domain_events_registry_compliance.py`

---

### 6a. CQRS Registry Pattern (Handler Auto-Wiring)

**Core Principle**: All commands and queries cataloged in `src/application/cqrs/registry.py` with automated handler dependency injection via `handler_factory()`.

**Purpose**:

- Single source of truth for all CQRS operations (23 commands, 18 queries)
- Self-enforcing (tests fail if handler missing `handle()` method)
- Auto-wiring (handler_factory introspects type hints, resolves dependencies)
- Zero manual factory functions (legacy ~1321 lines deleted)

**Architecture**:

```text
src/application/cqrs/
├── __init__.py           # Public exports
├── metadata.py           # CommandMetadata, QueryMetadata, CQRSCategory
├── registry.py           # COMMAND_REGISTRY, QUERY_REGISTRY
└── computed_views.py     # Helper functions (get_all_commands, get_statistics, etc.)
```

**Registry Entry Pattern**:

```python
CommandMetadata(
    command_class=RegisterUser,
    handler_class=RegisterUserHandler,
    category=CQRSCategory.AUTH,
    has_result_dto=False,
    emits_events=True,
    requires_transaction=True,
)
```

**Handler Factory Usage** (in routers):

```python
from src.core.container.handler_factory import handler_factory

@router.post("/users", status_code=201)
async def create_user(
    handler: RegisterUserHandler = Depends(handler_factory(RegisterUserHandler)),
):
    result = await handler.handle(RegisterUser(...))
```

**How handler_factory Works**:

1. Introspects handler `__init__` type hints
2. Resolves repositories with request database session
3. Resolves singletons (event bus, cache, etc.) from container
4. Creates handler instance with all dependencies injected

**Test Dependency Overrides**:

```python
factory_key = handler_factory(RegisterUserHandler)
app.dependency_overrides[factory_key] = lambda: mock_handler
```

**Validation Tests** (prevent drift):

- `test_all_command_handlers_have_handle_method()` - Fails if handler missing
- `test_command_names_are_imperative()` - Commands must be Verb* pattern
- `test_query_names_are_interrogative()` - Queries must be Get*/List* pattern

**Reference**: `docs/architecture/cqrs-registry.md`, `tests/unit/test_cqrs_registry_compliance.py`

---

### 7. File and Directory Structure

**Core Principle**: Hexagonal layers with protocol consolidation and flat test/docs structure.

#### Layer Structure

```text
src/
├── core/               # Shared kernel (Result, errors, config, container)
├── domain/             # Business logic (DEPENDS ON NOTHING)
│   ├── entities/
│   ├── value_objects/
│   ├── protocols/      # ALL protocols here (repositories, services, etc.)
│   ├── events/
│   ├── enums/
│   ├── errors/
│   ├── types.py        # Annotated types
│   └── validators.py   # Validation functions
├── application/        # Use cases (commands, queries, event handlers)
├── infrastructure/     # Adapters (implements domain protocols)
│   ├── persistence/
│   ├── external/
│   └── providers/
├── presentation/       # API endpoints (FastAPI routers)
└── schemas/            # Request/response schemas

tests/              # Flat structure with naming patterns
├── unit/           # test_<layer>_<component>.py
├── integration/    # test_<component>_<technology>.py
├── api/            # test_<domain>_endpoints.py
└── smoke/          # test_<feature>_flow.py

docs/               # Flat structure with naming patterns
├── architecture/   # domain-events.md, etc.
├── api/            # auth-login.md, providers-oauth-flow.md
└── guides/         # import-guidelines.md, etc.
```

#### Naming Conventions (PEP 8)

- **Python files**: `snake_case.py` matching class name (`user_repository.py` → `UserRepository`)
- **Python classes**: `PascalCase` (`RegisterUserHandler`)
- **Python directories**: `snake_case/` (`auth_strategies/`)
- **Documentation**: `kebab-case.md` (`oauth-flow.md`)
- **Test files**: Pattern-based naming (see test structure above)
- **Config files**: `kebab-case.yml` (`docker-compose.dev.yml`)

#### Protocol Consolidation (CRITICAL)

ALL protocols in `src/domain/protocols/` - NO separate `domain/repositories/` directory:

- `user_repository.py`, `cache_protocol.py`, `event_bus_protocol.py`, etc.
- Domain exports from single location
- Infrastructure imports protocols, implements without inheritance

#### Flat Structure for Tests and Docs

**Tests**: NO nested subdirectories within `unit/`, `integration/`, `api/`, `smoke/`. Use file naming patterns for organization.

**Docs**: NO nested subdirectories within `architecture/`, `api/`, `guides/`. Use `kebab-case-with-context.md` naming.

**Reference**: `docs/architecture/directory-structure.md`

---

### 8. Dependency Injection (Centralized Container)

**Core Principle**: All dependencies managed through `src/core/container.py` using two-tier pattern.

#### Two-Tier Pattern

**Application-Scoped** (singletons with `@lru_cache()`):

- `get_cache()` → `CacheProtocol` (Redis connection pool)
- `get_secrets()` → `SecretsProtocol` (env/AWS adapter)
- `get_database()` → `Database` (connection pool)
- `get_event_bus()` → `EventBusProtocol` (in-memory/RabbitMQ)

**Request-Scoped** (per-request with `yield`):

- `get_db_session()` → `AsyncSession` (new transaction per request)
- Handler factories (create new instances per request)

#### Protocol-First Pattern

Container returns **protocol types**, creates **concrete implementations**:

```python
# ✅ Container returns protocol
def get_user_repository(session: AsyncSession) -> UserRepository:
    from src.infrastructure.persistence.repositories.user_repository import (
        UserRepository as UserRepositoryImpl
    )
    return UserRepositoryImpl(session=session)

# ✅ Handler depends on protocol
class RegisterUserHandler:
    def __init__(self, user_repo: UserRepository):  # Protocol, not impl
        self._user_repo = user_repo
```

#### Layer-Specific Usage

- **Domain layer**: NO container imports (pure)
- **Application layer**: Use container directly (`cache = get_cache()`)
- **Infrastructure layer**: Can use container for dependencies
- **Presentation layer**: Use FastAPI `Depends()` for ALL dependencies

#### Testing

- **Unit tests**: Mock container functions (`patch("src.core.container.get_cache")`)
- **Integration tests**: Create fresh instances directly (bypass container)
- **API tests**: Use `app.dependency_overrides` for test dependencies

**Reference**: `docs/architecture/dependency-injection.md`

---

### 9. API Design (REST Compliance)

**CRITICAL**: 100% RESTful compliance is NON-NEGOTIABLE. NO controller-style exceptions.

#### Resource-Oriented URLs (Mandatory)

```text
✅ CORRECT (nouns):
/users
/users/{id}
/sessions              # Login = POST /sessions (creates session)
/tokens                # Refresh = POST /tokens (creates token)
/providers
/providers/{id}
/accounts
/accounts/{id}/transactions

❌ WRONG (verbs):
/createUser
/getAccounts
/loginUser
/auth/login            # Controller-style - NOT allowed
/token-rotation
/providers/{id}/refresh
```

**How to Model Actions as Resources**:

| Action | Resource Endpoint | HTTP Method |
|--------|-------------------|-------------|
| Login | `POST /sessions` | 201 Created |
| Logout | `DELETE /sessions/current` | 204 No Content |
| Token refresh | `POST /tokens` | 201 Created |
| Email verification | `POST /email-verifications` | 201 Created |
| Password reset request | `POST /password-reset-tokens` | 201 Created |
| Provider token refresh | `POST /providers/{id}/token-refreshes` | 201 Created |

#### HTTP Methods & Status Codes

**Methods**:

- **GET**: Retrieve (safe, idempotent)
- **POST**: Create new resources (returns 201 Created)
- **PATCH**: Partial update (returns 200 OK)
- **PUT**: Complete replacement (returns 200 OK)
- **DELETE**: Remove resources (returns 204 No Content)

**Status Codes**:

- **200**: Success (GET, PATCH, PUT)
- **201**: Created (POST)
- **204**: No Content (DELETE)
- **400**: Bad Request (validation errors)
- **401**: Unauthorized (authentication required)
- **403**: Forbidden (no permission)
- **404**: Not Found
- **409**: Conflict (duplicate resource)
- **429**: Too Many Requests (rate limited)
- **500**: Internal Server Error

#### Schema Separation (Mandatory)

**All request/response schemas in `src/schemas/`** - NO inline Pydantic models in routers.

```python
# ✅ CORRECT: Schema in src/schemas/user_schemas.py
class UserCreate(BaseModel):
    email: EmailStr
    password: str

# Router imports schema
from src.schemas.user_schemas import UserCreate

@router.post("/users", status_code=201)
async def create_user(data: UserCreate):
    ...

# ❌ WRONG: Inline schema in router
@router.post("/users")
async def create_user(data: dict):  # No!
    ...
```

#### Error Handling (RFC 7807 Problem Details)

**CRITICAL**: All API errors use RFC 7807 Problem Details format. **AuthErrorResponse removed in v1.6.3**.

**Error Response Format**:

```json
{
  "type": "https://api.dashtam.com/errors/validation_failed",
  "title": "Validation Failed",
  "status": 400,
  "detail": "Request validation failed",
  "instance": "/api/v1/users",
  "errors": [
    {"field": "email", "message": "Invalid format", "code": "invalid_format"}
  ],
  "trace_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Usage in Handlers**:

```python
from src.core.errors import ApplicationError, ApplicationErrorCode
from src.presentation.api.error_response_builder import ErrorResponseBuilder

# Return RFC 7807 error
error = ApplicationError(
    code=ApplicationErrorCode.NOT_FOUND,
    message="User not found"
)

return ErrorResponseBuilder.from_application_error(
    error=error,
    request_path="/api/v1/users/123"
)
```

**Key Fields**:

- `type`: Error type URL (match on this, NOT status code)
- `title`: Human-readable error type name
- `status`: HTTP status code
- `detail`: Context-specific error message
- `instance`: Request path
- `errors`: Field-level validation errors (optional)
- `trace_id`: UUID for log correlation

**Reference**: `docs/guides/error-handling.md` (comprehensive guide with client examples)

---

### 9a. Route Metadata Registry Pattern

**Core Principle**: All API routes defined declaratively in single registry, generated at startup.

**Purpose**:

- Single source of truth for all endpoints
- Self-enforcing (tests fail if routes missing)
- Auto-generated routes, auth, rate limits, OpenAPI docs
- Prevents decorator sprawl
- Future-proof (can't drift silently)

**Architecture**:

```text
src/presentation/routers/api/v1/routes/
├── metadata.py      # RouteMetadata types, enums
├── registry.py      # ROUTE_REGISTRY - 36 endpoints
├── generator.py     # FastAPI route generation
└── derivations.py   # Rate limit rule builders
```

**Registry Entry Pattern**:

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

**Route Generation** (automatic):

```python
# src/presentation/routers/api/v1/__init__.py
from src.presentation.routers.api.v1.routes.registry import ROUTE_REGISTRY
from src.presentation.routers.api/v1/routes.generator import register_routes_from_registry

v1_router = APIRouter(prefix="/api/v1")
register_routes_from_registry(v1_router, ROUTE_REGISTRY)

# Generates 36 FastAPI routes with:
# - Auth dependencies (from auth_policy)
# - Rate limit rules (from rate_limit_policy)
# - OpenAPI metadata (summary, tags, operation_id)
# - Error specs (for OpenAPI docs)
```

**Handler Pattern** (pure functions, no decorators):

```python
# src/presentation/routers/api/v1/users.py

# ❌ OLD: Decorator-based (removed)
# @router.post("/users", status_code=201)
# async def create_user(data: UserCreate): ...

# ✅ NEW: Pure handler function (registered in ROUTE_REGISTRY)
async def create_user(
    data: UserCreate,
    handler: RegisterUserHandler = Depends(get_register_handler),
) -> UserCreateResponse:
    result = await handler.handle(RegisterUser(**data.model_dump()))
    match result:
        case Success(user_id):
            return UserCreateResponse(id=user_id, email=data.email)
        case Failure(error):
            return ErrorResponseBuilder.from_application_error(
                error=error,
                request_path="/api/v1/users"
            )
```

**Rate Limit Generation** (two-tier pattern):

```python
# Tier 1: Policy assignment in registry.py
rate_limit_policy=RateLimitPolicy.AUTH_LOGIN

# Tier 2: Policy implementation in derivations.py
RateLimitPolicy.AUTH_LOGIN: RateLimitRule(
    max_tokens=5,
    refill_rate=5.0,
    cost=1,
    scope=RateLimitScope.IP,
    enabled=True
)

# Auto-generated rules in infrastructure/rate_limit/from_registry.py
RATE_LIMIT_RULES = build_rate_limit_rules(ROUTE_REGISTRY)
```

**Self-Enforcing Tests** (prevent drift):

- `test_all_routes_are_registered()` - Fails if FastAPI routes don't match registry
- `test_operation_ids_are_unique()` - Fails if duplicate operation IDs
- `test_auth_policy_enforced()` - Fails if auth dependencies missing
- `test_rate_limit_rules_cover_all()` - Fails if rate limit rules missing
- `test_registry_matches_fastapi_metadata()` - Fails if metadata inconsistent

**Benefits**:

- ✅ Add route to registry → tests validate, FastAPI generates, rate limits apply
- ✅ Remove route from registry → tests catch orphaned code
- ✅ Change metadata → tests verify consistency
- ✅ Zero manual updates needed when routes change

**Reference**: `tests/api/test_route_metadata_registry_compliance.py`

---

## Part 3: Development Workflow

### 10. Feature Development Process

**CRITICAL**: ALL feature development follows this two-phase process.

#### Pre-Development Phase (Planning)

**Before coding, complete these steps**:

**Step 0: Create Feature Branch** (MANDATORY FIRST)

```bash
git checkout development
git pull origin development
git checkout -b feature/<feature-name>  # e.g., feature/user-authentication
```

**Step 1: Feature Understanding**:

- [ ] Requirements understood (what to build)
- [ ] Success criteria identified (how to know it's done)
- [ ] Dependencies identified (existing code touched)

**Step 2: Architecture Analysis**:

- [ ] Identified architectural layer(s): core, domain, application, infrastructure, presentation
- [ ] No business logic in wrong layer (API layer is thin)
- [ ] No framework imports in domain layer

**Step 3: REST API Compliance** (if API changes)

- [ ] Resource-oriented URLs (nouns, NOT verbs)
- [ ] Proper HTTP methods and status codes
- [ ] Schemas in `src/schemas/` (not inline)

**Step 4: Database Design** (if applicable)

- [ ] Alembic migration needed
- [ ] Repository protocol in `domain/protocols/`
- [ ] Entity ↔ Model separation

**Step 5: Testing Strategy**:

- [ ] Domain layer: Unit tests (95%+ coverage)
- [ ] Application layer: Unit tests with mocked repos (90%+)
- [ ] Infrastructure layer: Integration tests ONLY (70%+)
- [ ] Presentation layer: API tests (85%+)

**Step 6: Create TODO List & Get Approval**:

- [ ] TODO list created with implementation phases
- [ ] Plan presented to user
- [ ] **USER APPROVAL RECEIVED** ✅

**DO NOT CODE without user approval.**

#### Development Phase (Implementation)

**After approval, implement following the TODO list**:

**Implementation Checklist**:

- [ ] **File naming**: `snake_case.py`, classes `PascalCase`
- [ ] **Type hints**: All parameters and return types
- [ ] **Protocol over ABC**: No inheritance for interfaces
- [ ] **Result types**: Domain returns `Result[T, E]`, no exceptions
- [ ] **Google-style docstrings**: All public functions
- [ ] **DRY principle**: No code duplication (extract at 2nd occurrence)

**Testing Checklist**:

- [ ] Unit tests for domain/application logic
- [ ] Integration tests for infrastructure adapters
- [ ] API tests for endpoints
- [ ] All tests pass: `make test`
- [ ] Coverage ≥85%

**Quality Checklist**:

- [ ] Lint passes: `make lint`
- [ ] Format applied: `make format`
- [ ] Type check passes: mypy
- [ ] Markdown linted: `make lint-md FILE="path"` (if docs changed)
- [ ] MkDocs builds: `make docs-build` (zero warnings)

**Commit Checklist**:

- [ ] Conventional commit format: `feat(scope): description`
- [ ] Reference issues: "Closes #42"
- [ ] PR created to `development` branch

---

### 11. Git Workflow (Git Flow)

#### Branch Structure

**Primary Branches**:

- `main` - Production-ready code (protected)
- `development` - Integration branch (protected)

**Supporting Branches**:

- `feature/*` - New features (from development)
- `fix/*` - Bug fixes (from development)
- `release/*` - Release preparation (from development)
- `hotfix/*` - Emergency production fixes (from main)

#### Commit Convention (Conventional Commits)

**Format**: `<type>(<scope>): <subject>`

**Types**:

- `feat:` - New features
- `fix:` - Bug fixes
- `docs:` - Documentation only
- `refactor:` - Code restructuring
- `test:` - Test additions/changes
- `chore:` - Maintenance, dependencies
- `perf:` - Performance improvements
- `ci:` - CI/CD changes

**Examples**:

```bash
git commit -m "feat(auth): add JWT authentication"
git commit -m "fix(api): handle token expiration correctly"
git commit -m "docs(api): update endpoint documentation"
git commit -m "test(integration): add user registration tests"
```

#### Branch Protection

**Both `main` and `development` are protected**:

- ✅ Required: All CI checks passing
- ✅ Required: At least 1 approval
- ✅ Required: Conversations resolved
- ❌ No direct commits (PR required)
- ❌ No force pushes

#### Release Workflow (CRITICAL)

**After every release to main, IMMEDIATELY sync main back into development**:

```bash
# After PR to main is merged:
git checkout development
git pull origin development
git fetch origin main
git merge origin/main --no-edit
git push origin development
```

**Why this matters**: Prevents version drift conflicts. When main receives a release merge, it may have slightly different commit history. If development continues without syncing, the next release PR will have conflicts in version-related files (pyproject.toml, uv.lock, CHANGELOG.md, WARP.md).

**Complete Release Checklist**:

1. [ ] Update version in `pyproject.toml`
2. [ ] Run `uv lock` (inside **dev** container: `docker exec dashtam-dev-app uv lock`)
3. [ ] Update `CHANGELOG.md` with release notes
4. [ ] Commit, push, create PR to `development`
5. [ ] Wait for CI, merge PR to `development`
6. [ ] Create PR from `development` → `main`
7. [ ] Merge PR to `main`
8. [ ] Tag release: `git tag -a vX.Y.Z -m "message"`
9. [ ] Push tag: `git push origin vX.Y.Z`
10. [ ] **SYNC BACK**: Merge `main` into `development` (see commands above)

#### Version Bumping & Tagging Strategy

**Semantic Versioning**: `MAJOR.MINOR.PATCH` (e.g., v1.2.1)

- **MAJOR**: Breaking changes to public API
- **MINOR**: New features (backward compatible)
- **PATCH**: Bug fixes, internal refactors (backward compatible)

**Key Rules**:

1. **Version in pyproject.toml** can be bumped anytime in development
2. **Tags only on main** after release merge
3. **Sync main → development** only after releasing to main
4. **CHANGELOG.md** updated with each version bump

---

### 12. Testing Strategy

**Target Coverage**: 85%+ overall, 95%+ for critical components

**Test Pyramid**:

```text
           ▲
          ╱ ╲ 10% E2E (Smoke Tests)
         ╱───╲ - Complete user flows
        ╱     ╲
       ╱       ╲ 20% Integration Tests
      ╱─────────╲ - Database, Redis operations
     ╱           ╲
    ╱             ╲ 70% Unit Tests
   ╱───────────────╲ - Domain entities, handlers
```

**By Layer**:

| Layer | Test Type | What to Test | Coverage |
|-------|-----------|--------------|----------|
| Domain | Unit | Entities, value objects, business logic | 95%+ |
| Application | Unit | Command/query handlers (mocked repos) | 90%+ |
| Infrastructure | Integration | Database ops, cache, external APIs | 70%+ |
| Presentation | API | Endpoints, auth, rate limiting | 85%+ |

**Test File Naming** (flat structure):

```text
tests/
├── unit/
│   ├── test_domain_user_entity.py
│   ├── test_application_register_handler.py
│   └── test_core_config.py
├── integration/
│   ├── test_database_postgres.py
│   └── test_cache_redis.py
├── api/
│   └── test_auth_endpoints.py
└── smoke/
    └── test_user_registration_flow.py
```

**Running Tests**:

```bash
make test              # All tests with coverage
make test-unit         # Unit tests only
make test-integration  # Integration tests only
make test-smoke        # E2E smoke tests
```

**Type Safety in Tests**:

Tests are type-checked with `check_untyped_defs = true` in mypy. Key patterns:

- `cast(UUID, uuid7())` for UUID generation
- `isinstance(result, Success)` before accessing `.value` on Result types
- `assert obj is not None` before accessing optional attributes
- Use specific `# type: ignore[error-code]` for intentional type violations
- Protocol-compliant signatures in test stubs (match exact method signatures)

**Reference**: `docs/architecture/testing.md` (Type Safety section)

**IMPORTANT**: All tests run in Docker. NEVER run tests on host machine.

---

## Part 4: Infrastructure & Deployment

### 13. Docker & Environments

**CRITICAL**: ALL development, testing, and execution in Docker containers.

**Directory Structure**:

```text
compose/
├── docker-compose.traefik.yml    # Traefik reverse proxy
├── docker-compose.dev.yml        # Development environment
├── docker-compose.test.yml       # Test environment
└── docker-compose.ci.yml         # CI/CD environment

env/
├── .env.dev.example              # Development template
├── .env.test.example             # Test template
└── .env.ci.example               # CI template
```

**Environments**:

| Environment | Domain | Database Port | Redis Port |
|-------------|--------|---------------|------------|
| Development | `https://dashtam.local` | 5432 | 6379 |
| Test | `https://test.dashtam.local` | 5433 | 6380 |
| CI | Internal only | Internal | Internal |

**Commands**:

```bash
make dev-up       # Start development (auto-starts Traefik)
make dev-logs     # View logs
make dev-shell    # Shell in app container
make dev-down     # Stop development

make test-up      # Start test environment
make test         # Run all tests
make test-down    # Stop test environment
```

**Container Usage Guidelines**:

- **Dev container** (`dashtam-dev-app`): Use for `uv lock`, `uv add`, package management, and any operations that modify project files
- **Test container** (`dashtam-test-app`): Use for running tests via `make test`, `make verify`
- **CRITICAL**: Always use dev container for `uv lock` to ensure lockfile updates are written to host filesystem

---

### 14. Traefik Reverse Proxy

**Purpose**: Domain-based routing, automatic SSL, no port conflicts.

**Benefits**:

- ✅ No port collisions (dev/test on same machine)
- ✅ Domain routing (`dashtam.local`, `test.dashtam.local`)
- ✅ Automatic SSL with mkcert (wildcard `*.dashtam.local`)
- ✅ Production-like setup in development

**Setup**:

```bash
make traefik-up   # Start Traefik (once per machine)
make certs        # Generate SSL certificates (once)
```

**Service Labels** (in docker-compose):

```yaml
services:
  app:
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.dashtam-dev.rule=Host(`dashtam.local`)"
      - "traefik.http.routers.dashtam-dev.entrypoints=websecure"
      - "traefik.http.routers.dashtam-dev.tls=true"
      - "traefik.http.services.dashtam-dev.loadbalancer.server.port=8000"
```

---

### 15. Secrets Management

**Hexagonal Pattern**: Protocol + multiple adapters.

**CRITICAL**: NEVER hardcode secrets in code or Docker Compose files.

**Architecture**:

```python
# Domain defines PORT
class SecretsProtocol(Protocol):
    async def get_secret(self, key: str) -> str | None: ...

# Infrastructure implements ADAPTERS
class EnvAdapter:        # Development: .env files
class AWSAdapter:        # Production: AWS Secrets Manager
```

**Environment-Specific**:

| Environment | Backend | Source |
|-------------|---------|--------|
| Development | `env` | `.env.dev` file |
| Test | `env` | `.env.test` file |
| Production | `aws` | AWS Secrets Manager |

**Docker Compose** (use `env_file`, NOT hardcoded):

```yaml
services:
  app:
    env_file:
      - ../env/.env.dev
    # ❌ WRONG: environment: SECRET_KEY: hardcoded-value
```

---

### 16. Logging & Audit

#### Structured Logging

**Use `structlog`** - JSON structured logs.

```python
logger.info(
    "user_registered",
    user_id=str(user_id),
    email=user.email,
    ip_address=request.client.host,
)
```

**Output**:

```json
{
  "event": "user_registered",
  "user_id": "123e4567-...",
  "timestamp": "2025-11-08T04:00:00Z",
  "level": "info"
}
```

**Security**: NEVER log passwords, tokens, API keys, SSNs.

#### Audit Trail (PCI-DSS Compliance)

**ATTEMPT → OUTCOME Pattern**:

```python
# Step 1: Record ATTEMPT (before business logic)
await audit.record(action=AuditAction.USER_REGISTRATION_ATTEMPTED, ...)

# Step 2: Execute business logic
session.add(user)
await session.commit()  # User NOW exists

# Step 3: Record OUTCOME (after commit)
await audit.record(action=AuditAction.USER_REGISTERED, ...)

# If failure:
await audit.record(action=AuditAction.USER_REGISTRATION_FAILED, ...)
```

**Critical**: Audit records go to separate session (persists even if business transaction fails).

**Retention**: 7 years minimum (PCI-DSS requirement).

---

### 17. Authentication & Security

#### JWT + Opaque Refresh Tokens

**Strategy**:

- **Access Token**: JWT (short-lived, 15 min)
- **Refresh Token**: Opaque (long-lived, 30 days, bcrypt hashed)

**Token Flow**:

```text
1. Login → POST /sessions → Returns access_token + refresh_token
2. API Call → Authorization: Bearer {access_token}
3. Token Refresh → POST /tokens → Returns new access_token + refresh_token
4. Logout → DELETE /sessions/current → Revokes refresh token
```

**Security Features**:

- Email verification required before login
- Account lockout after 5 failed attempts
- Bcrypt password hashing (12 rounds)
- Refresh token rotation on use

#### Authorization (Casbin RBAC)

**Role Hierarchy**: `admin > user > readonly`

**FastAPI Dependencies**:

```python
@router.get("/admin/users")
async def list_users(
    _: None = Depends(require_role(UserRole.ADMIN))
):
    ...

@router.delete("/providers/{id}")
async def delete_provider(
    _: None = Depends(require_permission(Permission.PROVIDERS_DELETE))
):
    ...
```

#### Rate Limiting (Token Bucket)

**Algorithm**: Token bucket with Redis Lua scripts (atomic, no race conditions).

**Response Headers** (RFC 6585):

```text
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1699488000
Retry-After: 60  (only on 429)
```

**Fail-Open**: Never blocks if Redis fails.

---

## Part 5: Documentation Standards

### 18. Documentation Quality

**CRITICAL**: All documentation must pass quality checks before commit.

#### Markdown Linting (Mandatory)

```bash
# Lint markdown file
make lint-md FILE="docs/architecture/new-doc.md"

# Lint markdown file directory
make lint-md DIR="docs/"

# Must return zero violations before commit
```

**Common Violations**:

- **MD022**: Add blank line before AND after headings
- **MD032**: Add blank line before AND after lists
- **MD031**: Add blank line before AND after code blocks
- **MD040**: Add language identifier to code blocks

#### MkDocs Documentation

```bash
make docs-serve   # Live preview (http://localhost:8000)
make docs-build   # Must pass with ZERO warnings
```

**Deployment**: Automatic via GitHub Actions to `https://faiyaz7283.github.io/Dashtam/`

#### Document Structure

- **One topic per document**
- **Size soft limits**: Architecture docs ≤2000 lines, others ≤1000 lines
- **Mermaid diagrams** for all flows (NO image files)
- **ONLY Metadata at bottom**: `**Created**: YYYY-MM-DD | **Last Updated**: YYYY-MM-DD`

---

## Part 6: AI Agent Instructions

### 19. AI Agent Workflow

**CRITICAL**: AI agents MUST follow the development workflow for ALL features.

#### Context7 MCP Integration (Mandatory)

**ALWAYS use Context7 MCP for library/framework documentation queries**:

- When writing code that uses external libraries (FastAPI, SQLAlchemy, Redis, etc.)
- When explaining APIs, setup steps, or configuration
- When the user asks "how to" questions about any framework
- **Automatically invoke Context7 tools without requiring explicit "use context7" mention**

**Why**: Ensures up-to-date, version-specific documentation instead of relying on potentially outdated training data.

**MCP Configuration**: Context7 is configured with API key `ctx7sk-139cda41-b3d4-424b-81e6-9af9111a0c73` in Warp.

**Tools Available**:

- `resolve-library-id` - Find Context7-compatible library ID
- `query-docs` - Fetch latest documentation and code examples

**Example Usage**:

```python
# When user asks: "How do I create async FastAPI endpoints?"
# 1. Call resolve-library-id with libraryName="fastapi"
# 2. Call query-docs with libraryId="/fastapi/fastapi" and query="async endpoints"
# 3. Provide answer with current, official documentation
```

#### Mandatory Process

**Phase 1: Pre-Development**:

1. Create feature branch FIRST (`git checkout -b feature/<name>`)
2. Analyze architecture placement (which layers?)
3. Verify REST compliance (if API changes)
4. Plan testing strategy
5. **Create TODO list**
6. **Present plan and WAIT for approval**
7. **❌ DO NOT CODE without approval**

**Phase 2: Development**:

1. Implement following TODO list
2. Use `mark_todo_as_done` as you complete items
3. Test continuously (unit → integration → API)
4. Run quality checks (`make lint`, `make test`)
5. Commit with conventional commits
6. **NEVER commit without user request**

#### TODO List Management

```python
# Create TODO list during planning
create_todo_list([
    {"title": "Phase 1: Database Schema", "details": "..."},
    {"title": "Phase 2: Domain Layer", "details": "..."},
    ...
])

# Mark items complete as you go
mark_todo_as_done(["todo-id-1", "todo-id-2"])

# Check progress
read_todos()
```

#### Architecture Verification

**Before implementing, verify**:

- [ ] Domain layer has NO framework imports
- [ ] All protocols in `src/domain/protocols/`
- [ ] Repositories return domain entities (not models)
- [ ] Commands/queries are immutable dataclasses
- [ ] Events use past tense naming

#### Common Mistakes to Avoid

**❌ Wrong layer placement**:

```python
# WRONG: Business logic in API layer
@router.post("/users")
async def create_user(data: UserCreate):
    if not is_valid_email(data.email):  # ❌ Validation in router
        raise HTTPException(400)
    await session.execute(...)  # ❌ Database in router
```

**✅ Correct layer placement**:

```python
# Router dispatches to handler
@router.post("/users", status_code=201)
async def create_user(
    data: UserCreate,
    handler: RegisterUserHandler = Depends(get_register_handler),
) -> UserResponse:
    result = await handler.handle(RegisterUser(email=data.email, ...))
    match result:
        case Success(user_id):
            return UserResponse(id=user_id, ...)
        case Failure(error):
            raise HTTPException(400, detail=error.message)
```

**❌ Other mistakes**:

- Skipping user approval before coding
- Not testing incrementally
- Forgetting REST compliance verification
- Committing without running tests
- Using ABC instead of Protocol

---

## Part 7: Quick Reference

### 20. Development Checklist Summary

**Pre-Development** (Get Approval First):

- [ ] Feature branch created (`feature/<name>`)
- [ ] Architecture layer(s) identified
- [ ] REST compliance verified (if API)
- [ ] Testing strategy planned
- [ ] TODO list created
- [ ] **User approval received**

**During Development**:

- [ ] Type hints on all functions
- [ ] Google-style docstrings
- [ ] DRY principle (no duplication)
- [ ] Unit tests for domain/application
- [ ] Integration tests for infrastructure
- [ ] API tests for endpoints

**Before Commit**:

- [ ] `make lint` passes
- [ ] `make format` applied
- [ ] `make test` passes (all tests)
- [ ] Coverage ≥85%
- [ ] `make lint-md` passes (if docs changed)
- [ ] `make docs-build` passes (zero warnings)
- [ ] Conventional commit message

---

### 21. Key Technical Decisions

#### Why Hexagonal Architecture?

- **Testability**: Domain testable without database/APIs
- **Flexibility**: Swap implementations without touching business logic
- **Maintainability**: Clear boundaries, explicit dependencies
- **Longevity**: Framework-agnostic domain survives upgrades

**See**: `docs/architecture/hexagonal.md` for complete architectural details, layer responsibilities, ports & adapters pattern, and integration with other patterns.

#### Why CQRS?

- **Performance**: Optimize reads separately from writes
- **Clarity**: Explicit user intent (commands) vs data needs (queries)
- **Caching**: Aggressive query caching without invalidation complexity

#### Why Protocol Over ABC?

- **Pythonic**: Structural typing (duck typing with safety)
- **Flexible**: No inheritance required, easier testing
- **Modern**: Standard Python feature, type checkers understand

**See**: `docs/architecture/protocols.md` for structural vs nominal typing, protocol implementations across Dashtam, testing strategies, and common pitfalls.

#### Why Result Types?

- **Explicit**: Errors are part of return type (no hidden exceptions)
- **Safe**: Force error handling at compile time
- **Railway**: Clear success/failure paths

#### Why UV Over pip?

- **Speed**: 10-100x faster dependency resolution
- **Modern**: Built-in virtual environment, project management
- **Reliable**: Deterministic builds with `uv.lock`

#### Why Event Registry Pattern?

- **Single Source of Truth**: All events cataloged in one place
- **Self-Enforcing**: Tests fail if handlers missing
- **Auto-Wiring**: Container uses registry, no manual subscription
- **Future-Proof**: Can't drift silently

---

## Summary: Key Rules for AI Agents

**Process**:

1. ✅ Create feature branch FIRST
2. ✅ Pre-development phase: Analyze → Plan → Present → Get approval
3. ✅ **NEVER code without user approval** of TODO list
4. ✅ Test incrementally (after each phase)
5. ✅ **NEVER commit without user request**

**Architecture**:

1. ✅ Hexagonal architecture - Domain depends on nothing
2. ✅ CQRS pattern - Separate commands from queries
3. ✅ Protocol over ABC - Structural typing
4. ✅ Result types - Domain returns Result, no exceptions
5. ✅ REST compliance - 100% RESTful (no controller-style endpoints)
6. ✅ Event Registry - Single source of truth for domain events

**Quality**:

1. ✅ All tests pass: `make test`
2. ✅ Code quality: `make lint`, `make format`
3. ✅ Markdown linting: `make lint-md` (zero violations)
4. ✅ MkDocs builds: `make docs-build` (zero warnings)
5. ✅ Conventional commits: `feat:`, `fix:`, `docs:` format

**External Reference**:

- `~/references/starter/dashtam-feature-roadmap.md` - Phase 2-6 implementation details

---

**Last Updated**: 2026-01-10
