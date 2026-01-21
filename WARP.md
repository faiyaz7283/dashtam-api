# Dashtam API — Project Rules and Context

**Purpose**: API-specific rules and architecture. For shared rules, see `~/dashtam/WARP.md`.

**⚠️ IMPORTANT**: See `~/dashtam/WARP.md` for WARP.md structure rules. Do NOT duplicate Global rules here.

---

## Global Rules Reference

**See `~/dashtam/WARP.md` for complete definitions of these universal rules:**

- **Rule 1**: Repository Structure (meta repo, submodules)
- **Rule 2**: Development Philosophy (clean architecture, type safety, latest stable)
- **Rule 3**: Modern Python Patterns (Protocol over ABC, type hints, Result types)
- **Rule 4**: Docker Containerization (Makefile commands, code quality)
- **Rule 5**: Git Workflow (branches, conventional commits, releases)
- **Rule 6**: Code Quality Standards (Ruff, mypy, docstrings)
- **Rule 7**: Testing Philosophy (coverage targets, test types)
- **Rule 8**: Environment Configuration (.env files, idempotent setup)
- **Rule 9**: Documentation Standards (markdown linting, MkDocs)
- **Rule 10**: AI Agent Instructions (mandatory pre-development process)
- **Rule 11**: GitHub Project (unified platform tracking)
- **Rule 12**: GitHub Issues Workflow (issue lifecycle, labels, milestones)

---

## API-Specific Rules

### 1. Technology Stack

**Backend**: FastAPI (async), Python 3.14+ (latest stable)
**Database**: PostgreSQL 17+ (latest stable) with async SQLAlchemy
**Cache**: Redis 8.2+ (latest stable) (async)
**Package Manager**: UV (latest stable)
**Containers**: Docker Compose v2, Traefik reverse proxy
**Testing**: pytest with TestClient
**CI/CD**: GitHub Actions with Codecov

**Version Policy**: Always use latest stable versions. Check `pyproject.toml` for current versions.

### 2. Architecture: Hexagonal + CQRS + Domain Events

**Core Principle**: Domain logic at the center, infrastructure at the edges. Domain depends on NOTHING.

**Layer Responsibilities**:

```
┌─────────────────────────────────────────────────────┐
│ Presentation Layer (API)                            │
│ - FastAPI routers                                   │
│ - Request/response schemas                          │
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

**Protocol Location**: ALL protocols go in `src/domain/protocols/` (consolidated).

### 3. CQRS Pattern

**Commands** (write operations):

```python
@dataclass(frozen=True, kw_only=True)
class RegisterUser:
    email: str
    password: str

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

class GetUserHandler:
    async def handle(self, query: GetUser) -> Result[User, Error]:
        return await self.users.find_by_id(query.user_id)
```

### 4. Domain Events (3-State ATTEMPT → OUTCOME Pattern)

**CRITICAL**: All critical workflows use 3-state pattern for audit semantic accuracy.

**Pattern**:
1. `*Attempted` - Before business logic (audit: ATTEMPTED)
2. `*Succeeded` - After successful commit (audit: outcome)
3. `*Failed` - After failure (audit: FAILED)

**Example Events**:
```python
UserRegistrationAttempted, UserRegistrationSucceeded, UserRegistrationFailed
UserLoginAttempted, UserLoginSucceeded, UserLoginFailed
AccountSyncAttempted, AccountSyncSucceeded, AccountSyncFailed
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
- `LoggingEventHandler` - Logs all events
- `AuditEventHandler` - Creates audit records
- `EmailEventHandler` - Sends notifications (SUCCEEDED only)
- `SessionEventHandler` - Manages sessions

**When to Use Events**:
- ✅ Critical workflows: 3+ side effects OR requires ATTEMPT → OUTCOME audit
- ✅ Operational events: Single-state observability/monitoring
- ❌ NOT for simple reads or single-step operations

### 5. Event Registry Pattern (Single Source of Truth)

**Location**: `src/domain/events/registry.py`

**Purpose**:
- Single source of truth for all events
- Self-enforcing (tests fail if handlers missing)
- Auto-wiring (container uses registry)

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

**Process for Adding New Events**:
1. Define event dataclass in `*_events.py`
2. Add entry to `EVENT_REGISTRY`
3. Run tests → they tell you what's missing
4. Add handler methods
5. Add AuditAction enum (if needed)
6. Tests pass ✅ (container auto-wires)

### 6. CQRS Registry Pattern (Handler Auto-Wiring)

**Location**: `src/application/cqrs/registry.py`

**Purpose**:
- Single source of truth for all CQRS operations
- Auto-wiring with `handler_factory()`

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

### 7. Application Services

**Location**: `src/application/services/`

**Key Service**: `OwnershipVerifier` - verifies ownership chains (Entity → Connection → User)

**Methods**:
- `verify_connection_ownership(connection_id, user_id)` → Connection
- `verify_account_ownership(account_id, user_id)` → Account
- `verify_holding_ownership(holding_id, user_id)` → Holding
- `verify_transaction_ownership(transaction_id, user_id)` → Transaction

**Benefits**:
- ✅ DRY: Single implementation for ownership verification
- ✅ Consistent error handling across all handlers
- ✅ Easy to test

### 8. File and Directory Structure

```
src/
├── core/               # Shared kernel (Result, errors, config, container, constants)
├── domain/             # Business logic (DEPENDS ON NOTHING)
│   ├── entities/
│   ├── value_objects/
│   ├── protocols/      # ALL protocols here
│   ├── events/
│   ├── enums/
│   ├── errors/
│   ├── types.py        # Annotated types
│   └── validators.py   # Validation functions
├── application/        # Use cases (commands, queries, event handlers)
│   └── services/       # Session-scoped services
├── infrastructure/     # Adapters (implements domain protocols)
│   ├── persistence/
│   ├── external/
│   └── providers/
│       └── base_api_client.py
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

**Naming Conventions** (PEP 8):
- **Python files**: `snake_case.py` matching class name
- **Python classes**: `PascalCase`
- **Python directories**: `snake_case/`
- **Documentation**: `kebab-case.md`
- **Config files**: `kebab-case.yml`

### 9. Dependency Injection (Centralized Container)

**Location**: `src/core/container.py`

**Two-Tier Pattern**:

**Application-Scoped** (singletons with `@lru_cache()`):
- `get_cache()` → `CacheProtocol`
- `get_secrets()` → `SecretsProtocol`
- `get_database()` → `Database`
- `get_event_bus()` → `EventBusProtocol`

**Request-Scoped** (per-request with `yield`):
- `get_db_session()` → `AsyncSession`
- Handler factories (create new instances per request)

**Protocol-First Pattern**:

```python
# Container returns protocol
def get_user_repository(session: AsyncSession) -> UserRepository:
    from src.infrastructure.persistence.repositories.user_repository import (
        UserRepository as UserRepositoryImpl
    )
    return UserRepositoryImpl(session=session)

# Handler depends on protocol
class RegisterUserHandler:
    def __init__(self, user_repo: UserRepository):  # Protocol, not impl
        self._user_repo = user_repo
```

### 10. REST API Design

**CRITICAL**: 100% RESTful compliance is NON-NEGOTIABLE.

**Resource-Oriented URLs** (Mandatory):

```
✅ CORRECT (nouns):
/users
/users/{id}
/sessions              # Login = POST /sessions (creates session)
/tokens                # Refresh = POST /tokens (creates token)
/providers
/accounts
/accounts/{id}/transactions

❌ WRONG (verbs):
/createUser
/getAccounts
/loginUser
/auth/login            # Controller-style - NOT allowed
```

**HTTP Methods & Status Codes**:

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

**Schema Separation** (Mandatory):

All request/response schemas in `src/schemas/` - NO inline Pydantic models in routers.

**Error Handling** (RFC 9457 Problem Details):

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

**Usage**:

```python
from src.core.errors import ApplicationError, ApplicationErrorCode
from src.presentation.api.error_response_builder import ErrorResponseBuilder

error = ApplicationError(
    code=ApplicationErrorCode.NOT_FOUND,
    message="User not found"
)

return ErrorResponseBuilder.from_application_error(
    error=error,
    request_path="/api/v1/users/123"
)
```

### 11. Route Metadata Registry Pattern

**Location**: `src/presentation/routers/api/v1/routes/registry.py`

**Purpose**:
- Single source of truth for all endpoints
- Auto-generated routes, auth, rate limits, OpenAPI docs

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

**Handler Pattern** (pure functions, no decorators):

```python
# Pure handler function (registered in ROUTE_REGISTRY)
async def create_user(
    data: UserCreate,
    handler: RegisterUserHandler = Depends(get_register_handler),
) -> UserCreateResponse:
    result = await handler.handle(RegisterUser(**data.model_dump()))
    if isinstance(result, Failure):
        return ErrorResponseBuilder.from_application_error(...)
    return UserCreateResponse(id=result.value, email=data.email)
```

### 12. Docker & Environments

**Environment Domains**:
- Development: `https://dashtam.local`
- Test: `https://test.dashtam.local`

**Container Names**:
- Dev: `dashtam-dev-app`, `dashtam-dev-db`, `dashtam-dev-cache`
- Test: `dashtam-test-app`, `dashtam-test-db`, `dashtam-test-cache`

**Container Usage Guidelines**:
- **Dev container**: Use for `uv lock`, `uv add`, package management
- **Test container**: Use for running tests via `make test`, `make verify`
- **CRITICAL**: Always use dev container for `uv lock` to ensure lockfile updates

### 13. Traefik Reverse Proxy

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

### 14. Secrets Management

**Hexagonal Pattern**: Protocol + multiple adapters

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

### 15. Logging & Audit

**Structured Logging** (structlog):

```python
logger.info(
    "user_registered",
    user_id=str(user_id),
    email=user.email,
    ip_address=request.client.host,
)
```

**Audit Trail** (ATTEMPT → OUTCOME Pattern):

```python
# Step 1: Record ATTEMPT (before business logic)
await audit.record(action=AuditAction.USER_REGISTRATION_ATTEMPTED, ...)

# Step 2: Execute business logic
session.add(user)
await session.commit()

# Step 3: Record OUTCOME (after commit)
await audit.record(action=AuditAction.USER_REGISTERED, ...)
```

**Security**: NEVER log passwords, tokens, API keys, SSNs.

### 16. Authentication & Security

**JWT + Opaque Refresh Tokens**:
- **Access Token**: JWT (short-lived, 15 min)
- **Refresh Token**: Opaque (long-lived, 30 days, bcrypt hashed)

**Token Flow**:
```
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

**Authorization** (Casbin RBAC):

```python
@router.get("/admin/users")
async def list_users(
    _: None = Depends(require_role(UserRole.ADMIN))
):
    ...
```

**Rate Limiting** (Token Bucket):

Algorithm: Token bucket with Redis Lua scripts (atomic, no race conditions)

**Response Headers** (RFC 6585):
```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1699488000
Retry-After: 60  (only on 429)
```

### 17. Context7 MCP Integration

**CRITICAL**: ALWAYS use Context7 MCP for library/framework documentation queries.

**When to use**:
- Writing code that uses FastAPI, SQLAlchemy, Redis, etc.
- Explaining APIs, setup steps, configuration
- User asks "how to" questions about any framework

**Why**: Ensures up-to-date, version-specific documentation.

**Tools Available**:
- `resolve-library-id` - Find Context7-compatible library ID
- `query-docs` - Fetch latest documentation and code examples

### 18. Key Technical Decisions

**Why Hexagonal Architecture?**
- Testability: Domain testable without database/APIs
- Flexibility: Swap implementations without touching business logic
- Maintainability: Clear boundaries, explicit dependencies

**Why CQRS?**
- Performance: Optimize reads separately from writes
- Clarity: Explicit user intent (commands) vs data needs (queries)
- Caching: Aggressive query caching without invalidation complexity

**Why Protocol Over ABC?**
- Pythonic: Structural typing (duck typing with safety)
- Flexible: No inheritance required, easier testing
- Modern: Standard Python feature, type checkers understand

**Why Result Types?**
- Explicit: Errors are part of return type (no hidden exceptions)
- Safe: Force error handling at compile time
- Railway: Clear success/failure paths

**Why Event Registry Pattern?**
- Single Source of Truth: All events cataloged in one place
- Self-Enforcing: Tests fail if handlers missing
- Auto-Wiring: Container uses registry, no manual subscription
- Future-Proof: Can't drift silently

---

**Last Updated**: 2026-01-21
