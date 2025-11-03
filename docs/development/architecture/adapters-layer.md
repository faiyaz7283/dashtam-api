# Adapters Layer Architecture

Comprehensive guide to the adapters layer pattern used in Dashtam for integrating reusable packages with application-specific infrastructure.

---

## Overview

Dashtam follows **Hexagonal Architecture (Ports & Adapters)** for organizing code that bridges generic, reusable packages with application-specific infrastructure. This pattern ensures:

- **Clear separation** between business logic and infrastructure
- **Testability** of packages without application dependencies
- **Reusability** of packages across projects
- **Consistency** across all cross-cutting concerns

### Core Principle

> Reusable packages define WHAT (business logic), adapters define HOW (integration), infrastructure provides primitives (database, cache).

---

## Directory Structure

```text
src/
├── <package_name>/              # Self-contained, reusable packages
│   ├── models/                  # Package-specific models/interfaces
│   ├── storage/                 # Storage abstractions
│   ├── backends/                # Backend implementations
│   ├── factory.py               # Generic factory (DI container)
│   └── service.py               # Orchestrator service
│
├── adapters/                    # APPLICATION ADAPTERS (this guide)
│   ├── rate_limiter.py          # Wires rate_limiter → Dashtam
│   └── session_manager.py       # Wires session_manager → Dashtam
│
├── core/                        # Core infrastructure primitives
│   ├── database.py              # DB connection management
│   ├── config.py                # Settings management
│   └── cache/                   # Cache infrastructure
│
├── config/                      # Configuration DATA (not code)
│   ├── rate_limits.py           # Rate limit rules (constants)
│   └── app_settings.py          # Application settings (data)
│
├── models/                      # Application domain models
│   ├── user.py                  # Core domain models
│   ├── session.py               # Session adapter model
│   └── session_audit.py         # Audit models
│
└── api/                         # Presentation layer
    ├── dependencies.py          # FastAPI dependencies (imports adapters)
    └── v1/                      # API endpoints
```

---

## Design Patterns

### Hexagonal Architecture (Ports & Adapters)

```text
┌─────────────────────────────────────────────────────────────┐
│  Domain Layer (Packages)                                    │
│  - src/rate_limiter/, src/session_manager/                  │
│  - Pure business logic                                      │
│  - Framework-agnostic                                       │
│  - Defines interfaces (ports)                               │
│  - Reusable across projects                                 │
└─────────────────────────────────────────────────────────────┘
                            ↑
                            │ Ports (interfaces)
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  Adapter Layer (src/adapters/)                              │
│  - Application-specific wiring                              │
│  - Bridges domain ↔ infrastructure                          │
│  - Wires package factories with Dashtam models              │
│  - Configuration instantiation                              │
└─────────────────────────────────────────────────────────────┘
                            ↑
                            │ Uses
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  Infrastructure Layer (src/core/)                           │
│  - Database connections (AsyncSession)                      │
│  - Cache clients (Redis, memory)                            │
│  - Configuration (Settings)                                 │
│  - Logging, monitoring                                      │
│  - Shared across all features                               │
└─────────────────────────────────────────────────────────────┘
```

### Dependency Inversion Principle

- **High-level modules** (packages) depend on abstractions
- **Low-level modules** (infrastructure) implement abstractions
- **Adapters** wire them together without creating coupling

---

## What Goes Where?

### `src/<package>/` - Domain/Business Logic

**Purpose**: Self-contained, reusable business logic

**Contains**:

- Abstract interfaces (ports)
- Generic implementations
- Business rules and algorithms
- Framework-agnostic code

**Examples**:

```python
# src/rate_limiter/factory.py
def get_rate_limiter_service(
    audit_model: Type[RateLimitAuditBase],  # Abstract
    redis_client: Any,                      # Abstract
    rules: Dict[str, RateLimitRule],        # Configuration
) -> RateLimiterService:
    """Generic factory - no Dashtam coupling."""
    pass

# src/session_manager/factory.py
def get_session_manager(
    session_model: Type[SessionBase],       # Abstract
    audit_model: Type[SessionAuditBase],    # Abstract
    db_session: Any,                        # Abstract
    config: SessionConfig,
) -> SessionManagerService:
    """Generic factory - no Dashtam coupling."""
    pass
```

**Rules**:

- ✅ No imports from `src.models` (application models)
- ✅ No imports from `src.core` (infrastructure)
- ✅ No FastAPI dependencies
- ✅ Type hints use abstractions (`Any`, `Protocol`, abstract base classes)
- ✅ Can be tested without application infrastructure

### `src/adapters/` - Application Integration Layer

**Purpose**: Wire packages with Dashtam-specific infrastructure

**Contains**:

- Adapter functions/classes
- Dashtam model wiring
- Configuration instantiation
- Dependency injection setup

**Examples**:

```python
# src/adapters/session_manager.py
from src.models.session import Session                    # Dashtam model
from src.models.session_audit import SessionAuditLog      # Dashtam model
from src.session_manager.factory import get_session_manager
from src.session_manager.models.config import SessionConfig

async def get_session_manager_service(
    db_session: AsyncSession,
) -> SessionManagerService:
    """Adapter: Wires session_manager package with Dashtam models."""
    config = SessionConfig(
        storage_type="database",
        backend_type="database",
        audit_type="database",
    )
    
    return get_session_manager(
        session_model=Session,              # Dashtam's Session adapter
        audit_model=SessionAuditLog,        # Dashtam's audit model
        config=config,
        db_session=db_session,
    )
```

```python
# src/adapters/rate_limiter.py (future)
from src.models.rate_limit_audit import RateLimitAudit
from src.config.rate_limits import RATE_LIMIT_RULES
from src.rate_limiter.factory import get_rate_limiter_service

def get_rate_limiter(redis_client) -> RateLimiterService:
    """Adapter: Wires rate_limiter package with Dashtam."""
    return get_rate_limiter_service(
        audit_model=RateLimitAudit,         # Dashtam's audit model
        rules=RATE_LIMIT_RULES,             # Dashtam's rules
        redis_client=redis_client,
    )
```

**Rules**:

- ✅ Imports from `src.models` (application models)
- ✅ Imports from `src.core` (infrastructure)
- ✅ Imports from `src.<package>` (packages)
- ✅ Imports from `src.config` (configuration data)
- ✅ One adapter per package
- ❌ No business logic (delegate to package)
- ❌ No HTTP/API concerns (that's `src.api`)

### `src/core/` - Infrastructure Primitives

**Purpose**: Shared infrastructure used by all features

**Contains**:

- Database connection management
- Cache client initialization
- Settings/configuration loading
- Logging setup
- Shared utilities

**Examples**:

```python
# src/core/database.py
async def get_session() -> AsyncSession:
    """Provide database session."""
    pass

# src/core/config.py
def get_settings() -> Settings:
    """Load application settings."""
    pass

# src/core/cache/redis.py
def get_redis_client() -> RedisClient:
    """Initialize Redis client."""
    pass
```

**Rules**:

- ✅ Framework-agnostic utilities
- ✅ Shared across all features
- ✅ No business logic
- ❌ No package-specific code
- ❌ No adapters (that's `src.adapters`)

### `src/config/` - Configuration Data

**Purpose**: Application configuration data (not code)

**Contains**:

- Constants
- Rules and thresholds
- Feature flags
- Environment-specific settings

**Examples**:

```python
# src/config/rate_limits.py
RATE_LIMIT_RULES = {
    "POST /api/v1/auth/login": RateLimitRule(
        max_tokens=10,
        refill_rate=0.33,
        scope="ip",
    ),
    # ... more rules
}

def get_rate_limit_rule(endpoint: str) -> RateLimitRule | None:
    """Helper to retrieve rule."""
    return RATE_LIMIT_RULES.get(endpoint)
```

**Rules**:

- ✅ Python dictionaries, lists, constants
- ✅ Helper functions to query configuration
- ❌ No factories (that's `src.adapters`)
- ❌ No service instantiation
- ❌ No dependency injection

### `src/api/dependencies.py` - FastAPI Dependencies

**Purpose**: Provide dependency injection for FastAPI endpoints

**Contains**:

- FastAPI `Depends()` functions
- Imports from `src.adapters`
- Infrastructure dependency injection (db, cache)

**Examples**:

```python
# src/api/dependencies.py
from src.adapters.session_manager import get_session_manager_service
from src.core.database import get_session

async def get_session_manager(
    db_session: AsyncSession = Depends(get_session),
) -> SessionManagerService:
    """FastAPI dependency for SessionManagerService."""
    return await get_session_manager_service(db_session)

# Usage in endpoints
@router.get("/auth/sessions")
async def list_sessions(
    session_manager: SessionManagerService = Depends(get_session_manager),
):
    sessions = await session_manager.list_sessions(...)
    return sessions
```

**Rules**:

- ✅ Imports from `src.adapters`
- ✅ Uses `Depends()` for dependency injection
- ✅ Thin wrappers over adapters
- ❌ No business logic
- ❌ No direct package imports (use adapters)

---

## Benefits of This Pattern

### 1. Testability

**Packages can be tested independently:**

```python
# Test rate_limiter without Dashtam infrastructure
from src.rate_limiter.factory import get_rate_limiter_service

def test_rate_limiting():
    # Mock audit model
    class MockAudit:
        pass
    
    # Mock Redis client
    mock_redis = MockRedisClient()
    
    service = get_rate_limiter_service(
        audit_model=MockAudit,
        redis_client=mock_redis,
        rules={...},
    )
    
    # Test without database or real Redis
    assert service.check_limit(...) == True
```

### 2. Reusability

**Packages can be extracted and used elsewhere:**

```bash
# Extract session_manager package
cp -r src/session_manager/ ../other-project/src/

# Create new adapter for other project
# other-project/src/adapters/session_manager.py
from other_project.models import Session
from session_manager.factory import get_session_manager

def get_session_service(db):
    return get_session_manager(
        session_model=Session,  # Different app's model
        ...
    )
```

### 3. Maintainability

**Clear boundaries make changes predictable:**

- Change business logic → Edit package
- Change Dashtam models → Edit adapter
- Change infrastructure → Edit `src/core`
- Change configuration → Edit `src/config`

### 4. Consistency

**Same pattern for all cross-cutting concerns:**

- Rate limiting → `src/adapters/rate_limiter.py`
- Session management → `src/adapters/session_manager.py`
- Future features → `src/adapters/<feature>.py`

---

## Implementation Checklist

When creating a new package and adapter:

### Package (src/<package>/)

- [ ] Define abstract interfaces (ports)
- [ ] Implement generic business logic
- [ ] Create generic factory function
- [ ] NO imports from `src.models`, `src.core`, `src.api`
- [ ] Use type hints with abstractions (`Any`, `Protocol`)
- [ ] Add unit tests (no infrastructure dependencies)

### Adapter (src/adapters/<package>.py)

- [ ] Import Dashtam-specific models
- [ ] Import package's generic factory
- [ ] Create adapter function that wires models to factory
- [ ] Handle configuration instantiation
- [ ] Return fully configured service
- [ ] Add integration tests (with real infrastructure)

### FastAPI Dependencies (src/api/dependencies.py)

- [ ] Import adapter function
- [ ] Create FastAPI dependency using `Depends()`
- [ ] Inject infrastructure dependencies (db, cache)
- [ ] Return service from adapter

### Configuration (src/config/)

- [ ] Create configuration data file (if needed)
- [ ] Define constants, rules, thresholds
- [ ] Add helper functions to query config
- [ ] NO service instantiation or factories

---

## Migration Guide

### Existing Code Using `src/core/`

If you have existing factory code in `src/core/`:

**Before:**

```python
# src/core/session.py
def get_session_manager(db_session):
    backend = JWTSessionBackend(...)
    storage = DatabaseSessionStorage(...)
    audit = LoggerAuditBackend()
    
    return SessionManagerService(
        backend=backend,
        storage=storage,
        audit=audit,
    )
```

**After:**

```python
# src/adapters/session_manager.py
from src.session_manager.factory import get_session_manager

async def get_session_manager_service(db_session):
    return get_session_manager(
        session_model=Session,
        audit_model=SessionAuditLog,
        config=SessionConfig(...),
        db_session=db_session,
    )
```

**Steps:**

1. Create new adapter in `src/adapters/<package>.py`
2. Import package's generic factory
3. Wire Dashtam models to factory
4. Update imports in `src/api/dependencies.py`
5. Delete old factory in `src/core/`
6. Run tests to verify migration

---

## Future Improvements

### Rate Limiter Migration

**Current State**: Rate limiter uses middleware-based wiring

**Future Enhancement**: Create `src/adapters/rate_limiter.py`

**Plan**:

```python
# src/adapters/rate_limiter.py (to be created)
from src.models.rate_limit_audit import RateLimitAudit
from src.config.rate_limits import RATE_LIMIT_RULES
from src.rate_limiter.factory import get_rate_limiter_service

def get_rate_limiter(redis_client) -> RateLimiterService:
    """Adapter: Wires rate_limiter package with Dashtam."""
    return get_rate_limiter_service(
        audit_model=RateLimitAudit,
        rules=RATE_LIMIT_RULES,
        redis_client=redis_client,
    )
```

**Benefits**:

- Consistent with session manager pattern
- Easier to test rate limiting in isolation
- Clearer separation of concerns

---

## Common Pitfalls

### ❌ Don't: Import Application Models in Packages

```python
# src/session_manager/storage/database.py
from src.models.session import Session  # ❌ WRONG - creates coupling

class DatabaseSessionStorage:
    async def save_session(self, session: Session):  # Coupled to Dashtam
        pass
```

### ✅ Do: Use Abstractions in Packages

```python
# src/session_manager/storage/database.py
from src.session_manager.models.base import SessionBase  # ✅ CORRECT

class DatabaseSessionStorage:
    async def save_session(self, session: SessionBase):  # Abstract interface
        pass
```

### ❌ Don't: Put Business Logic in Adapters

```python
# src/adapters/session_manager.py
async def get_session_manager_service(db_session):
    service = get_session_manager(...)
    
    # ❌ WRONG - business logic in adapter
    if not service.validate_session(...):
        service.revoke_session(...)
    
    return service
```

### ✅ Do: Keep Adapters Thin (Wiring Only)

```python
# src/adapters/session_manager.py
async def get_session_manager_service(db_session):
    # ✅ CORRECT - just wiring
    return get_session_manager(
        session_model=Session,
        audit_model=SessionAuditLog,
        config=SessionConfig(...),
        db_session=db_session,
    )
```

### ❌ Don't: Put Factories in `src/config/`

```python
# src/config/session_settings.py
def get_session_manager(db):  # ❌ WRONG - factory in config
    return SessionManagerService(...)
```

### ✅ Do: Keep Configuration as Data

```python
# src/config/session_settings.py
SESSION_TTL_DAYS = 30  # ✅ CORRECT - data only
SESSION_BACKEND = "database"
```

---

## References

### Design Patterns

- **Hexagonal Architecture**: Alistair Cockburn, 2005
- **Ports and Adapters**: Martin Fowler, 2014
- **Dependency Inversion Principle**: Robert C. Martin (SOLID), 2000

### Industry Examples

- **Spring Framework**: `@Adapter` annotation for integration layer
- **NestJS**: Providers and modules for dependency injection
- **FastAPI**: Dependency injection via `Depends()`

### Internal Documentation

- [Session Manager Architecture](session-manager-package.md)
- [Rate Limiter Architecture](../../../src/rate_limiter/docs/architecture.md)
- [RESTful API Design](restful-api-design.md)

---

## Metadata

- **Created**: 2025-11-03
- **Last Updated**: 2025-11-03
- **Status**: Active (Best Practice Standard)
- **Applies To**: All reusable packages (session_manager, rate_limiter, future packages)
- **Related**: Hexagonal Architecture, Dependency Inversion, Adapter Pattern
