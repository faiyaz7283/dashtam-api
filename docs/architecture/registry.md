# Registry Pattern Architecture

## Architectural Standard for Dashtam

The Registry Pattern is a meta-architectural design that eliminates manual drift by establishing a **single source of truth** for system components and their relationships. This document defines the pattern abstractly so it can be applied across Dashtam wherever manual maintenance causes drift, inconsistency, or fragility.

---

## Problem Statement

### The Manual Drift Problem

In large codebases, **manual coordination** between related components causes **drift**:

**Symptoms**:

- Adding a new component requires updating multiple files manually
- Easy to forget steps (handler registration, enum additions, test updates)
- No compile-time or test-time enforcement of completeness
- Silent failures when wiring is incomplete
- Documentation becomes outdated quickly
- Code reviews miss coordination errors

**Example Scenario** (Before Registry Pattern):

```python
# Step 1: Define event (developer remembers)
class UserRegistered(DomainEvent):
    ...

# Step 2: Add handler method (might forget)
class LoggingHandler:
    def handle_user_registered(self, event):
        ...

# Step 3: Subscribe in container (often forgotten!)
event_bus.subscribe(UserRegistered, logging_handler.handle_user_registered)

# Step 4: Add audit action enum (frequently missed)
class AuditAction(Enum):
    USER_REGISTERED = "user_registered"

# Step 5: Update tests (sometimes skipped)
```

**Result**: Incomplete wiring, silent failures, production bugs.

---

## Solution Overview

The Registry Pattern eliminates manual coordination by creating a **metadata registry** that:

1. **Single Source of Truth**: All component relationships defined in one place
2. **Auto-Wiring**: Container reads registry and wires components automatically
3. **Self-Validating**: Tests fail if registry is incomplete
4. **Zero Drift**: Impossible to forget steps (tests enforce completeness)

### Before vs After

**Before (Manual)**:

```text
Developer adds component → Manual steps (5-10) → Easy to forget → Drift → Bugs
```

**After (Registry Pattern)**:

```text
Developer adds component → Update registry (1 step) → Tests enforce rest → Zero drift
```

---

## Core Principles

### 1. Single Source of Truth

**All** component metadata lives in **one** registry file.

**Good**:

```python
# src/domain/events/registry.py (ONLY PLACE)
EVENT_REGISTRY = [
    EventMetadata(
        event_class=UserRegistered,
        workflow="user_registration",
        requires_logging=True,
        requires_audit=True,
        audit_action="USER_REGISTERED",
    ),
]
```

**Bad**:

```python
# Metadata scattered across 5 files
# src/events.py, src/handlers.py, src/container.py, src/enums.py, src/tests.py
```

### 2. Metadata-Driven

Registry contains **metadata**, not **implementation**.

**Metadata includes**:

- Component identity (class, name)
- Relationships (requires X, connects to Y)
- Configuration (flags, enums, categories)
- Rules (validation requirements)

**Metadata does NOT include**:

- Business logic
- Implementation details
- Runtime data

### 3. Auto-Wiring from Registry

Container **reads** registry and **auto-wires** components.

```python
# src/core/container.py
for metadata in REGISTRY:
    if metadata.requires_handler:
        handler_method = getattr(handler, metadata.method_name)
        wire_component(metadata.component, handler_method)
```

**No manual wiring code** - all driven by registry metadata.

### 4. Self-Validating Tests

Tests **fail** if registry is incomplete.

```python
def test_all_components_have_handlers():
    """Verify every component has required handlers."""
    for metadata in REGISTRY:
        if metadata.requires_handler:
            assert handler_exists(metadata.method_name), \
                f"Missing handler: {metadata.method_name}"
```

**Zero false sense of security** - can't merge incomplete code.

---

## Architecture Components

### Component 1: Registry File

**Purpose**: Single source of truth for all metadata.

**Location**: `src/domain/<area>/registry.py`

**Structure**:

```python
from dataclasses import dataclass
from enum import Enum

# Enums for categorization
class ComponentCategory(Enum):
    CATEGORY_A = "a"
    CATEGORY_B = "b"

# Metadata dataclass
@dataclass(frozen=True, kw_only=True)
class ComponentMetadata:
    component_class: type
    category: ComponentCategory
    requires_x: bool = True
    requires_y: bool = False
    config_key: str | None = None

# The registry (list of metadata)
REGISTRY: list[ComponentMetadata] = [
    ComponentMetadata(
        component_class=ComponentA,
        category=ComponentCategory.CATEGORY_A,
        requires_x=True,
        config_key="component_a",
    ),
    # ... more entries
]
```

**Key Properties**:

- Immutable (`frozen=True`)
- Type-safe (dataclass with type hints)
- Exhaustive (every component listed)
- Centralized (one file)

### Component 2: Auto-Wiring Container

**Purpose**: Read registry and wire components automatically.

**Location**: `src/core/container/<area>.py`

**Pattern**:

```python
def get_wired_component():
    """Wire components based on registry."""
    component = create_base_component()
    
    # Auto-wire from registry
    for metadata in REGISTRY:
        if metadata.requires_x:
            x_handler = get_x_handler(metadata)
            component.connect(metadata.component_class, x_handler)
        
        if metadata.requires_y:
            y_handler = get_y_handler(metadata)
            component.connect(metadata.component_class, y_handler)
    
    return component
```

**Benefits**:

- Eliminates ~500 lines of manual wiring
- Can't forget to wire components
- Easy to add new relationships (update registry only)

### Component 3: Self-Validating Tests

**Purpose**: Enforce registry completeness.

**Location**: `tests/unit/test_<area>_registry_compliance.py`

**Pattern**:

```python
def test_all_components_have_required_handlers():
    """Verify registry completeness."""
    for metadata in REGISTRY:
        if metadata.requires_x:
            handler = get_x_handler()
            method_name = compute_method_name(metadata)
            assert hasattr(handler, method_name), \
                f"Missing handler method: {method_name}"
```

**Key Tests**:

1. **Completeness**: All components have required handlers
2. **Consistency**: Enum values match registry entries
3. **Count Accuracy**: Expected totals match actual
4. **No Orphans**: No handlers without registry entries

---

## Implementation Guide

### Step 1: Identify Candidates

**Look for these patterns**:

- Multiple files require manual coordination
- Adding new component requires 5+ manual steps
- Drift happens frequently (PRs miss steps)
- Silent failures when wiring incomplete
- Tests don't catch missing wiring

**Good Candidates**:

- ✅ Event handlers and subscriptions
- ✅ Route registration and middleware
- ✅ Validation rules and error handlers
- ✅ Feature flags and configuration
- ✅ Plugin systems

**Poor Candidates**:

- ❌ Business logic (belongs in domain)
- ❌ One-off configurations
- ❌ Simple key-value mappings

### Step 2: Design Metadata Structure

**Questions to answer**:

1. What is the "component" being registered?
2. What relationships does each component have?
3. What configuration does each component need?
4. What validation rules apply?

**Example** (Event System):

```python
@dataclass(frozen=True, kw_only=True)
class EventMetadata:
    # Identity
    event_class: type
    category: EventCategory
    workflow_name: str
    
    # Relationships
    requires_logging: bool = True
    requires_audit: bool = True
    requires_email: bool = False
    
    # Configuration
    audit_action_name: str
    phase: WorkflowPhase
```

### Step 3: Create Registry File

**Template**:

```python
# src/domain/<area>/registry.py

from dataclasses import dataclass
from enum import Enum

# 1. Define enums for categorization
class ComponentCategory(Enum):
    TYPE_A = "a"
    TYPE_B = "b"

# 2. Define metadata dataclass
@dataclass(frozen=True, kw_only=True)
class ComponentMetadata:
    component_class: type
    category: ComponentCategory
    # ... add relationship/config fields

# 3. Create registry constant
REGISTRY: list[ComponentMetadata] = [
    # List all components here
]

# 4. Add helper functions
def get_all_components() -> list[type]:
    return [m.component_class for m in REGISTRY]

def get_statistics() -> dict[str, int]:
    return {
        "total": len(REGISTRY),
        "by_category": ...,
    }
```

### Step 4: Implement Auto-Wiring

**Template**:

```python
# src/core/container/<area>.py

from src.domain.<area>.registry import REGISTRY

def get_wired_component():
    """Auto-wire from registry (zero manual code)."""
    component = BaseComponent()
    
    for metadata in REGISTRY:
        # Compute handler method name from metadata
        method_name = f"handle_{metadata.workflow_name}"
        
        # Wire based on metadata flags
        if metadata.requires_x:
            handler = get_x_handler()
            handler_method = getattr(handler, method_name, None)
            if handler_method:
                component.wire(metadata.component_class, handler_method)
    
    return component
```

### Step 5: Create Self-Validating Tests

**Template**:

```python
# tests/unit/test_<area>_registry_compliance.py

from src.domain.<area>.registry import REGISTRY

def test_all_components_have_handlers():
    """Verify every component has required handlers."""
    missing = []
    
    for metadata in REGISTRY:
        if metadata.requires_handler:
            method_name = f"handle_{metadata.workflow_name}"
            if not hasattr(handler, method_name):
                missing.append(method_name)
    
    assert not missing, \
        f"Missing handlers: {missing}\n" \
        f"Add methods to handler class or update registry"

def test_registry_count_matches_actual():
    """Verify registry count matches implementation."""
    expected = len(REGISTRY)
    actual = count_actual_components()
    assert actual == expected
```

### Step 6: Strict Mode (Optional)

Add environment-controlled enforcement:

```python
# src/core/config.py
class Settings(BaseSettings):
    strict_mode: bool = False  # Fail-fast if incomplete

# src/core/container.py
if settings.strict_mode and not handler_method:
    raise RuntimeError(f"Missing handler: {method_name}")
```

**Use Cases**:

- **Development**: `strict_mode=False` (graceful, allows WIP)
- **Production**: `strict_mode=True` (fail-fast, prevents silent failures)

---

## When to Use This Pattern

### ✅ Use When

1. **Multiple manual steps** required to add new component
2. **Drift happens frequently** (PRs miss coordination)
3. **Silent failures** when wiring incomplete
4. **Relationships are complex** (component needs 3+ handlers)
5. **Team size > 1** (coordination overhead)

### ❌ Don't Use When

1. **Simple mappings** (dict or enum sufficient)
2. **One-off configurations** (not worth overhead)
3. **Business logic** (belongs in domain, not registry)
4. **Extremely dynamic** (components added at runtime)

### Decision Tree

```text
Does adding a new component require 5+ manual steps?
  ├─ Yes → Consider Registry Pattern
  └─ No  → Use simpler approach

Does incomplete wiring cause silent failures?
  ├─ Yes → Registry Pattern strongly recommended
  └─ No  → Simpler approach OK

Do PRs frequently miss coordination steps?
  ├─ Yes → Registry Pattern solves this
  └─ No  → Current approach working
```

---

## Real-World Example: Domain Events

### Problem (Before Registry Pattern)

Adding a new domain event required **10 manual steps**:

1. Define event class
2. Add logging handler method
3. Add audit handler method
4. Add email handler method (if needed)
5. Subscribe logging handler in container
6. Subscribe audit handler in container
7. Subscribe email handler in container
8. Add AuditAction enum
9. Update tests
10. Update documentation

**Result**: Frequent drift, incomplete wiring, silent failures.

### Solution (Registry Pattern)

**1 manual step**: Add entry to `EVENT_REGISTRY`:

```python
EVENT_REGISTRY = [
    EventMetadata(
        event_class=UserRegistered,
        category=EventCategory.AUTHENTICATION,
        workflow_name="user_registration",
        phase=WorkflowPhase.SUCCEEDED,
        requires_logging=True,
        requires_audit=True,
        requires_email=True,
        audit_action_name="USER_REGISTERED",
    ),
]
```

**Everything else enforced by tests**:

- Tests fail if handler methods missing
- Tests fail if audit action missing
- Tests fail if wiring incomplete

**Code Reduction**:

- Container: 571 lines → 168 lines (**71% reduction**)
- Zero manual subscription code
- Self-validating (tests enforce completeness)

### Results

- **69 events** fully managed by registry
- **143 subscriptions** auto-wired
- **Zero drift** (impossible to forget steps)
- **100% test coverage** of registry compliance

**Reference**: `src/domain/events/registry.py`, `src/core/container/events.py`

---

## Benefits & Trade-offs

### Benefits

#### 1. Zero Drift

**Before**: Easy to forget steps → Incomplete wiring → Bugs  
**After**: Tests fail if incomplete → Can't merge → Zero drift

#### 2. Massive Code Reduction

**Before**: 500+ lines of manual wiring code  
**After**: ~50 lines registry + ~100 lines auto-wire = **70% reduction**

#### 3. Self-Documenting

Registry **is** the documentation:

```python
# Clear at a glance:
EventMetadata(
    event_class=UserRegistered,
    requires_logging=True,    # ← Has logging handler
    requires_audit=True,      # ← Has audit handler
    requires_email=True,      # ← Has email handler
)
```

#### 4. Onboarding Simplified

**New developers**:

- Before: "Where do I wire this? Oh no, I forgot 3 steps..."
- After: "Add to registry. Tests tell me what's missing."

#### 5. Refactoring Safety

**Rename component**:

- Before: Grep 10 files, hope you didn't miss any
- After: Update registry, tests fail if missed

### Trade-offs

#### 1. Upfront Complexity

**Initial setup** takes longer than manual approach.

**Mitigation**: Use template (this doc), follow implementation guide.

#### 2. Indirection

**Registry adds layer** between definition and usage.

**Mitigation**: Good naming, clear documentation, IDE navigation.

#### 3. Test Overhead

**Must maintain** registry compliance tests.

**Mitigation**: Tests are mostly boilerplate, copy from domain events example.

#### 4. Not for Everything

**Don't overuse** - only for coordination-heavy patterns.

**Mitigation**: Follow "When to Use" decision tree.

---

## Implemented Applications

The Registry Pattern has been successfully applied to multiple Dashtam components:

### 1. Domain Events Registry

**Purpose**: Auto-wire domain events to their handlers with zero manual subscription code.

**Results**:

- 69 events fully managed by registry
- 143 subscriptions auto-wired
- 71% code reduction in container (571 → 168 lines)
- Zero drift (impossible to forget handler wiring)

**Reference**: `docs/architecture/domain-events.md` (Section 5.1)

### 2. Provider Integration Registry

**Purpose**: Single source of truth for all financial provider integrations with self-enforcing validation.

**Registry Structure**:

```python
# src/domain/providers/registry.py
PROVIDER_REGISTRY: dict[Provider, ProviderMetadata] = {
    Provider.SCHWAB: ProviderMetadata(
        slug="schwab",
        display_name="Charles Schwab",
        category=ProviderCategory.BROKERAGE,
        auth_type=ProviderAuthType.OAUTH,
        capabilities=[ProviderCapability.ACCOUNTS, ProviderCapability.TRANSACTIONS],
        required_settings=["schwab_client_id", "schwab_client_secret"],
    ),
    # ... Alpaca, Chase
}
```

**Results**:

- 3 providers cataloged with complete metadata
- 19 self-enforcing compliance tests
- 100% coverage for provider registry module
- Discovered drift: Alpaca missing from manual OAUTH_PROVIDERS set
- 30% code reduction in container

**Reference**: `docs/architecture/provider-registry.md`

### 3. Rate Limit Rules Registry

**Purpose**: Self-enforcing validation for rate limit rules to prevent configuration drift.

**Registry Structure**:

```python
# src/infrastructure/rate_limit/config.py
RATE_LIMIT_RULES: dict[str, RateLimitRule] = {
    "POST /api/v1/auth/login": RateLimitRule(
        max_tokens=5,
        refill_rate=5.0,
        scope=RateLimitScope.IP,
        cost=1,
        enabled=True,
    ),
    # ... 24 more endpoint rules
}
```

**Results**:

- 25 endpoint rules validated with 23 self-enforcing tests
- 100% coverage for rate limit config module
- 5 test classes: Completeness, Consistency, Pattern Matching, Statistics, Future-Proofing
- Zero drift: Tests fail if rules have invalid config (negative tokens, invalid scope, malformed patterns)

**Reference**: `docs/architecture/rate-limit.md` (Section 5: Registry Pattern)

### 4. Validation Rules Registry

**Purpose**: Single source of truth for all validation rules with self-documenting metadata and self-enforcing compliance tests.

**Registry Structure**:

```python
# src/domain/validators/registry.py
VALIDATION_RULES_REGISTRY: dict[str, ValidationRuleMetadata] = {
    "email": ValidationRuleMetadata(
        rule_name="email",
        validator_function=validate_email,
        field_constraints={"min_length": 5, "max_length": 255},
        description="Email address with format validation and lowercase normalization",
        examples=["user@example.com", "test.user@domain.co.uk"],
        category=ValidationCategory.AUTHENTICATION,
    ),
    # ... password, verification_token, refresh_token
}
```

**Results**:

- 4 validation rules cataloged with complete metadata (descriptions, examples, constraints)
- 18 self-enforcing compliance tests (100% passing)
- 100% coverage for validation registry module
- 4 helper functions for easy access (`get_validation_rule`, `get_all_validation_rules`, `get_rules_by_category`, `get_statistics`)
- Zero drift: Tests fail if validators lack metadata or examples

**Reference**: `docs/architecture/validation-registry.md`

### 5. Route Metadata Registry

**Purpose**: Single source of truth for all API endpoints with auto-generated routes, auth dependencies, rate limit rules, and OpenAPI documentation.

**Registry Structure**:

```python
# src/presentation/routers/api/v1/routes/registry.py
ROUTE_REGISTRY: list[RouteMetadata] = [
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
    # ... 35 more endpoints (total 36)
]
```

**Results**:

- 36 API endpoints cataloged with complete metadata
- 18 self-enforcing compliance tests (100% passing)
- FastAPI routes auto-generated from registry at startup
- Auth dependencies auto-injected based on auth_policy
- Rate limit rules auto-generated (two-tier configuration pattern)
- 12 router files converted from decorator-based to pure handler functions
- Zero drift: Tests fail if routes missing, auth policies inconsistent, or rate limits incomplete

**Reference**: `docs/architecture/route-registry.md`

---

## Future Applications

### Candidate Areas

#### 1. Feature Flags

**Current**: Scattered feature checks, hard to audit

**Registry Pattern**:

```python
FEATURE_REGISTRY = [
    FeatureMetadata(
        name="multi_factor_auth",
        enabled_environments=["production", "staging"],
        requires_migration=True,
        rollout_percentage=100,
    ),
]
```

### Evaluation Criteria

For each candidate area, ask:

1. ✅ **Coordination Burden**: Does it require 5+ manual steps?
2. ✅ **Drift Risk**: Do PRs frequently miss steps?
3. ✅ **Consistency**: Should all components follow same pattern?
4. ✅ **Team Size**: Are multiple developers touching this code?

If **3+ answers are yes** → Registry Pattern likely worth it.

---

## Best Practices

### 1. Keep Registry Pure

**Do**: Metadata only (classes, enums, flags, strings)  
**Don't**: Business logic, implementation details, runtime data

```python
# ✅ Good: Pure metadata
ComponentMetadata(
    component_class=UserService,
    requires_cache=True,
    cache_ttl_seconds=300,
)

# ❌ Bad: Implementation details
ComponentMetadata(
    component_class=UserService,
    get_cache=lambda: Redis(...),  # Implementation!
)
```

### 2. Type-Safe Metadata

**Always use**:

- `@dataclass(frozen=True, kw_only=True)`
- Type hints on all fields
- Enums for categories (not strings)

```python
# ✅ Good: Type-safe
@dataclass(frozen=True, kw_only=True)
class Metadata:
    component: type
    category: ComponentCategory  # Enum
    requires_x: bool

# ❌ Bad: Stringly-typed
class Metadata:
    def __init__(self, component, category, requires_x):
        self.category = category  # str? bool? who knows
```

### 3. Self-Validating Tests

**Must have these tests**:

1. **Completeness**: All components have required handlers
2. **Consistency**: Enums match registry entries
3. **Count Accuracy**: Registry totals match actual
4. **No Orphans**: No handlers without registry entries

### 4. Document Registry Location

**In architecture docs**, be explicit:

```markdown
## Registry Location

**Single source of truth**: `src/domain/<area>/registry.py`

All component metadata lives here. Do NOT scatter metadata across files.
```

### 5. Version Registry Carefully

**Breaking changes** to registry structure require migration:

- Add new optional fields (backward compatible)
- Deprecate old fields before removing
- Provide migration script if needed

### 6. Keep Helper Functions

**Add to registry file**:

```python
def get_all_components() -> list[type]:
    """Get all registered component classes."""
    return [m.component_class for m in REGISTRY]

def get_by_category(category: Category) -> list[Metadata]:
    """Get metadata filtered by category."""
    return [m for m in REGISTRY if m.category == category]

def get_statistics() -> dict[str, int]:
    """Get registry statistics for documentation."""
    return {
        "total": len(REGISTRY),
        "categories": ...,
    }
```

### 7. Fail-Fast in Production

**Use strict mode**:

```python
# .env.production
STRICT_MODE=true  # Fail immediately if wiring incomplete
```

**Benefit**: Catches issues at startup, not in production.

---

## Conclusion

The Registry Pattern is a **meta-architectural design** that eliminates manual drift by establishing a **single source of truth** for component relationships. It trades upfront complexity for **long-term maintainability, zero drift, and massive code reduction**.

**When to Use**:

- Multiple manual steps to add components
- Frequent drift in PRs
- Silent failures when incomplete
- Team size > 1

**When NOT to Use**:

- Simple mappings (dict/enum sufficient)
- One-off configurations
- Business logic (belongs in domain)

**First Implementation**: Domain Events  
**Status**: ✅ Production-Ready Architectural Standard  
**Future**: API Routes, Provider Integration, Validation Rules, Feature Flags

---

**Created**: 2025-12-27 | **Last Updated**: 2026-01-10
