# CQRS Registry Architecture

## Overview

The CQRS Registry is Dashtam's **single source of truth** for all commands and queries. It catalogs all 23 commands and 18 queries with metadata (category, result DTOs, event emission, transaction requirements), enabling auto-wired handler dependency injection via `handler_factory()`.

This is a **specific implementation** of Dashtam's general [Registry Pattern](registry.md), applied to CQRS command/query management.

---

## Problem Statement

### Manual Drift Problem

Before the CQRS Registry, adding a new command/query required **5+ manual steps**:

1. Define command/query dataclass
2. Create handler class
3. Add container factory function (`get_*_handler`)
4. Export from `__init__.py`
5. Update tests

**Problems**:

- ❌ **Drift**: Easy to forget factory function or export
- ❌ **Inconsistency**: ~35 manual factory functions (~1321 lines) with varying patterns
- ❌ **No SSOT**: Commands scattered across 13 files
- ❌ **Hard to audit**: No single place to see all CQRS operations
- ❌ **Fragile**: Adding handler requires updates in 3+ files

---

## Solution Overview

**CQRS Registry** centralizes ALL command/query metadata in `src/application/cqrs/registry.py`:

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

**Auto-generated from registry**:

1. ✅ Handler dependency injection via `handler_factory()`
2. ✅ Self-enforcing compliance tests
3. ✅ Helper functions for introspection
4. ✅ Statistics and validation

**Benefits**:

- ✅ **Single source of truth**: All 41 operations in one file
- ✅ **Zero drift**: Tests fail if handler missing
- ✅ **Auto-wiring**: `handler_factory()` resolves all dependencies
- ✅ **Auditability**: See all CQRS operations in one place
- ✅ **Consistency**: Standard metadata for all operations

---

## Architecture Components

### Component 1: Registry File

**Location**: `src/application/cqrs/registry.py`

**Structure**:

```python
from src.application.cqrs.metadata import (
    CommandMetadata,
    QueryMetadata,
    CQRSCategory,
    CachePolicy,
)

COMMAND_REGISTRY: list[CommandMetadata] = [
    # AUTH Commands (7)
    CommandMetadata(
        command_class=RegisterUser,
        handler_class=RegisterUserHandler,
        category=CQRSCategory.AUTH,
        has_result_dto=False,
        emits_events=True,
        requires_transaction=True,
    ),
    # ... 22 more commands (total 23)
]

QUERY_REGISTRY: list[QueryMetadata] = [
    # DATA_SYNC Queries (14)
    QueryMetadata(
        query_class=GetAccount,
        handler_class=GetAccountHandler,
        category=CQRSCategory.DATA_SYNC,
        is_paginated=False,
        cache_policy=CachePolicy.NONE,
    ),
    # ... 17 more queries (total 18)
]
```

### Component 2: Metadata Types

**Location**: `src/application/cqrs/metadata.py`

**CommandMetadata**:

```python
@dataclass(frozen=True, kw_only=True)
class CommandMetadata:
    command_class: type              # RegisterUser, etc.
    handler_class: type              # RegisterUserHandler
    category: CQRSCategory           # AUTH, SESSION, PROVIDER, etc.
    has_result_dto: bool = False     # Returns DTO (not just UUID/bool)
    result_dto_class: type | None = None
    emits_events: bool = True        # Most commands emit domain events
    requires_transaction: bool = True
```

**QueryMetadata**:

```python
@dataclass(frozen=True, kw_only=True)
class QueryMetadata:
    query_class: type               # GetAccount, etc.
    handler_class: type             # GetAccountHandler
    category: CQRSCategory          # DATA_SYNC, SESSION, PROVIDER
    is_paginated: bool = False      # ListAccountsByUser, etc.
    cache_policy: CachePolicy = CachePolicy.NONE
```

### Component 3: Categories

```python
class CQRSCategory(str, Enum):
    AUTH = "auth"           # Authentication (7 commands)
    SESSION = "session"     # Session management (6 commands, 2 queries)
    TOKEN = "token"         # Token generation/rotation (3 commands)
    PROVIDER = "provider"   # Provider connections (3 commands, 2 queries)
    DATA_SYNC = "data_sync" # Sync accounts/transactions/holdings (3 commands, 14 queries)
    IMPORT = "import"       # File imports (1 command)
```

---

## Handler Factory Integration

### Auto-Wired Dependency Injection

The `handler_factory()` function auto-wires all handler dependencies:

```python
# src/core/container/handler_factory.py
from src.core.container.handler_factory import handler_factory

# In router - dependencies auto-resolved from type hints
@router.post("/users", status_code=201)
async def create_user(
    handler: RegisterUserHandler = Depends(handler_factory(RegisterUserHandler)),
):
    result = await handler.handle(RegisterUser(...))
```

**How it works**:

1. Introspects handler `__init__` type hints
2. Resolves repositories with request database session
3. Resolves singletons (event bus, cache, etc.) from container
4. Creates handler instance with all dependencies injected

### Supported Dependency Types

**Repositories** (12 types):

- `UserRepository`, `AccountRepository`, `TransactionRepository`
- `HoldingRepository`, `ProviderConnectionRepository`, `SessionRepository`
- `RefreshTokenRepository`, `SecurityConfigRepository`, `BalanceSnapshotRepository`
- `EmailVerificationTokenRepository`, `PasswordResetTokenRepository`, `ProviderRepository`

**Singletons** (18 types):

- `EventBusProtocol`, `PasswordHashingProtocol`, `TokenGenerationProtocol`
- `EncryptionProtocol`, `CacheProtocol`, `SessionCache`, `DeviceEnricher`
- `LocationEnricher`, `ProviderFactoryProtocol`, and more

---

## Helper Functions

**Location**: `src/application/cqrs/computed_views.py`

```python
# Get all commands/queries
commands = get_all_commands()       # List of 23 command classes
queries = get_all_queries()         # List of 18 query classes

# Filter by category
auth_commands = get_commands_by_category(CQRSCategory.AUTH)
data_queries = get_queries_by_category(CQRSCategory.DATA_SYNC)

# Get metadata for specific command/query
meta = get_command_metadata(RegisterUser)
meta = get_query_metadata(GetAccount)

# Statistics
stats = get_statistics()
# {
#   "total_commands": 23,
#   "total_queries": 18,
#   "total_operations": 41,
#   "commands_by_category": {"auth": 7, "session": 6, ...},
#   ...
# }

# Validation
errors = validate_registry_consistency()  # Returns [] if valid
```

---

## Self-Enforcing Tests

**Location**: `tests/unit/test_cqrs_registry_compliance.py`

**Test Classes**:

1. **TestRegistryCompleteness** - All commands/queries registered, no duplicates
2. **TestHandlerCompliance** - All handlers have `handle()` method
3. **TestNamingConventions** - Commands imperative (Verb*), queries interrogative (Get*/List*)
4. **TestCategoryConsistency** - Categories match expected patterns
5. **TestMetadataConsistency** - DTO flags consistent, events/transactions majority
6. **TestHelperFunctions** - Helper functions work correctly
7. **TestStatistics** - Statistics are accurate

**Key Tests**:

```python
def test_all_command_handlers_have_handle_method(self) -> None:
    """All command handlers must implement handle()."""
    missing = []
    for meta in COMMAND_REGISTRY:
        if not hasattr(meta.handler_class, "handle"):
            missing.append(meta.handler_class.__name__)
    assert not missing, f"Missing handle() method: {missing}"

def test_command_names_are_imperative(self) -> None:
    """Commands should have imperative names (verbs)."""
    imperative_prefixes = (
        "Register", "Authenticate", "Verify", "Refresh", "Request",
        "Confirm", "Logout", "Create", "Revoke", "Link", "Record",
        "Update", "Generate", "Trigger", "Connect", "Disconnect",
        "Sync", "Import",
    )
    for meta in COMMAND_REGISTRY:
        name = meta.command_class.__name__
        assert any(name.startswith(prefix) for prefix in imperative_prefixes)
```

---

## Usage Examples

### Adding a New Command

1. Define command dataclass in `src/application/commands/`:

```python
@dataclass(frozen=True, kw_only=True)
class NewCommand:
    user_id: UUID
    data: str
```

2. Create handler in `src/application/commands/handlers/`:

```python
class NewCommandHandler:
    def __init__(self, user_repo: UserRepository, event_bus: EventBusProtocol):
        self._user_repo = user_repo
        self._event_bus = event_bus
    
    async def handle(self, cmd: NewCommand) -> Result[UUID, str]:
        ...
```

3. Add to registry:

```python
CommandMetadata(
    command_class=NewCommand,
    handler_class=NewCommandHandler,
    category=CQRSCategory.AUTH,
    emits_events=True,
)
```

4. Use in router:

```python
@router.post("/new-endpoint")
async def new_endpoint(
    handler: NewCommandHandler = Depends(handler_factory(NewCommandHandler)),
):
    ...
```

**That's it!** Tests will fail if handler missing `handle()` method.

### Testing with Mocked Handlers

```python
from src.core.container.handler_factory import handler_factory

def test_endpoint(client):
    factory_key = handler_factory(NewCommandHandler)
    app.dependency_overrides[factory_key] = lambda: MockHandler()
    
    response = client.post("/new-endpoint", json={...})
    assert response.status_code == 200
    
    app.dependency_overrides.clear()
```

---

## Statistics

**Current Registry Stats**:

- **Total Commands**: 23
- **Total Queries**: 18
- **Total Operations**: 41
- **Commands by Category**: AUTH (7), SESSION (6), TOKEN (3), PROVIDER (3), DATA_SYNC (3), IMPORT (1)
- **Queries by Category**: SESSION (2), PROVIDER (2), DATA_SYNC (14)
- **Commands with Result DTO**: 6
- **Commands Emitting Events**: 23 (100%)
- **Commands Requiring Transaction**: 22 (96%)
- **Paginated Queries**: 10

---

## References

- [Registry Pattern](registry.md) - Meta-architectural pattern
- [Route Registry](route-registry.md) - API endpoint registry
- [Domain Events Registry](domain-events.md) - Event registry
- [Dependency Injection](dependency-injection.md) - DI architecture
