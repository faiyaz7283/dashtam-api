# Rate Limiting Implementation Guide

Token Bucket algorithm with Redis storage for Dashtam financial API, designed with strict SOLID principles adherence and pluggable architecture for maximum flexibility and reusability.

---

## Executive Summary

### Objective

Implement a production-ready, SOLID-compliant rate limiting system for Dashtam that:

- Protects authentication endpoints from brute force attacks
- Respects provider API rate limits (Charles Schwab: 100 requests/minute)
- Provides fair usage enforcement for authenticated users
- Maintains excellent user experience with burst handling
- Achieves <5ms p95 latency overhead
- Follows strict SOLID principles for maintainability and extensibility

### Scope

**In Scope:**

- Token Bucket algorithm implementation with Redis storage
- FastAPI middleware integration
- Per-endpoint rate limit configuration (single source of truth)
- Multiple scopes: IP-based (auth), user-based (API), provider-based (Schwab)
- Comprehensive test coverage (unit, integration, smoke tests)
- Pluggable architecture (Strategy Pattern for algorithms and storage)
- HTTP 429 responses with Retry-After headers
- Rate limit response headers (X-RateLimit-*)
- Audit logging for rate limit violations

**Out of Scope:**

- Additional algorithms (sliding window, fixed window) - designed for but not implemented initially
- Alternative storage backends (PostgreSQL, in-memory) - designed for but not implemented initially
- Admin dashboard for rate limit monitoring (future enhancement)
- Dynamic rate limit adjustment based on system load (future enhancement)
- Rate limit bypass tokens/allowlists (future enhancement)

### Impact

**Expected Benefits:**

- **Security:** 99.9% reduction in successful brute force attacks on authentication endpoints
- **Compliance:** PCI-DSS 8.1.6, OWASP A07:2021, SOC 2 availability controls
- **Provider Protection:** Zero Charles Schwab API quota violations
- **User Experience:** <0.1% false positive rate (legitimate users blocked)
- **Performance:** <5ms p95 latency overhead (target: 2-3ms)
- **Maintainability:** SOLID-compliant, testable, extensible architecture

**Key Stakeholders:**

- **End Users:** Protected from service degradation, smooth experience with burst handling
- **Development Team:** Clean, maintainable codebase following SOLID principles
- **Security/Compliance:** PCI-DSS and SOC 2 compliance achieved
- **Operations:** Auditability and monitoring capabilities

### Status

**Current Status:** Phase 3 Complete (Testing & Validation)

**Priority:** P1 (High)

**Progress:** 3/5 phases complete (60%)

**Completed Phases:**
- ✅ Phase 1: Core Infrastructure (PR #48)
- ✅ Phase 2: Middleware Integration (PR #49)
- ✅ Phase 3: Testing & Validation (PR #50 pending)

**Remaining Phases:**
- ⏳ Phase 4: Monitoring & Observability (optional)
- ⏳ Phase 5: Performance Optimization (optional)

## Current State

### Overview

Dashtam currently has NO rate limiting protection. All endpoints are completely open to unlimited requests:

- Authentication endpoints vulnerable to brute force attacks
- No protection against provider API quota exhaustion (Schwab: 100/min limit)
- No fair usage enforcement for authenticated users
- Potential for accidental or malicious DoS
- Non-compliant with PCI-DSS 8.1.6 (limit repeated access attempts)

### Issues and Limitations

1. **Security Vulnerability: Brute Force Attacks**
   - Impact: Critical
   - Affected components: `/auth/login`, `/auth/register`, `/auth/password-reset`
   - Risk: Account takeover, credential stuffing, enumeration attacks

2. **Provider API Quota Exhaustion**
   - Impact: High
   - Affected components: All Schwab API calls (accounts, transactions, balances)
   - Risk: Service suspension, API access revoked, degraded user experience

3. **No Fair Usage Enforcement**
   - Impact: Medium
   - Affected components: All authenticated API endpoints
   - Risk: Resource exhaustion, service degradation for legitimate users

4. **Compliance Gap**
   - Impact: High
   - Affected components: PCI-DSS 8.1.6, SOC 2 availability controls
   - Risk: Failed audits, regulatory issues

### Dependencies

- **Redis 8.2.1:** Already deployed and operational (includes Lua support)
- **FastAPI Middleware System:** Built-in, no additional dependencies
- **Async SQLAlchemy:** For database operations (if needed for storage alternatives)
- **Pydantic v2:** For configuration validation (already in use)

## Goals and Objectives

### Primary Goals

1. **Security: Prevent Brute Force Attacks**
   - Success metric: Number of successful brute force attempts
   - Target: Zero successful attacks

2. **Provider Protection: Respect API Limits**
   - Success metric: Charles Schwab API quota violations
   - Target: Zero violations (100 req/min limit respected)

3. **Performance: Minimal Latency Overhead**
   - Success metric: p95 latency added by rate limiting
   - Target: <5ms (aim for 2-3ms with Redis Lua)

4. **User Experience: Low False Positive Rate**
   - Success metric: Percentage of legitimate users blocked
   - Target: <0.1% false positive rate

5. **Code Quality: SOLID Compliance**
   - Success metric: Adherence to all 5 SOLID principles
   - Target: 100% compliance (explicit mapping documented)

### Secondary Goals

1. **Extensibility:** Pluggable architecture for future algorithm/storage additions
2. **Observability:** Comprehensive audit logging for security analysis
3. **Reusability:** Design for extraction to standalone package (future)

### Non-Goals

- **Real-time rate limit analytics dashboard** - Future enhancement
- **Dynamic rate limit adjustment** - Future enhancement
- **Multiple simultaneous algorithms** - Initial implementation uses one
- **Distributed rate limiting across multiple Redis instances** - Single Redis sufficient

## Implementation Strategy

### Approach

### Token Bucket Algorithm with Redis Storage (Custom Implementation)

This approach was chosen after comprehensive research (see `docs/research/rate-limiting-research.md`) scoring **37/40** against 7 alternatives:

**Why Token Bucket?**

- Industry standard (AWS, GitHub, Stripe, Cloudflare)
- Best burst handling for financial APIs (refresh multiple accounts simultaneously)
- Excellent user experience (save up capacity, use when needed)
- Performance: 2-3ms overhead with Redis Lua scripts
- Flexible: per-user, per-IP, per-endpoint, per-provider scopes

**Why Redis?**

- Already deployed (Redis 8.2.1)
- Lua scripts enable atomic operations (prevents race conditions)
- Fast (2-3ms) and distributed-ready
- Industry standard for rate limiting

**Why Custom Implementation (not SlowAPI)?**

- SlowAPI scored 29/40 (lower than token bucket)
- Lacks per-user rate limiting (only per-IP)
- Inflexible for per-endpoint configuration
- Custom implementation: Full control, SOLID-compliant, pluggable

### Key Decisions

#### Decision 1: Strict SOLID Principles Adherence

**Context:** Architecture must be maintainable, extensible, and testable long-term.

**Options Considered:**

1. **Quick implementation without abstractions** - Fast but unmaintainable
2. **SOLID-compliant with abstractions** - More upfront work but clean architecture
3. **Over-engineered with patterns** - Excessive complexity

**Decision:** SOLID-compliant with abstractions (Option 2)

**Rationale:**

Every component explicitly maps to SOLID principles:

- **S (Single Responsibility):**
  - `RateLimitAlgorithm`: Only algorithm logic
  - `RateLimitStorage`: Only storage operations
  - `RateLimiterService`: Only orchestration
  - `RateLimitMiddleware`: Only HTTP interception
  - `RateLimitConfig`: Only configuration

- **O (Open/Closed):**
  - Open for extension: Add algorithms via inheritance
  - Closed for modification: Core interfaces never change
  - Decorator pattern for middleware registration

- **L (Liskov Substitution):**
  - Any `RateLimitAlgorithm` implementation is swappable
  - Any `RateLimitStorage` implementation is swappable
  - Contracts guaranteed via abstract base classes

- **I (Interface Segregation):**
  - Minimal interfaces (no fat interfaces)
  - `RateLimitAlgorithm`: Single method `is_allowed()`
  - `RateLimitStorage`: Single method `check_and_consume()`
  - Clients depend only on what they use

- **D (Dependency Inversion):**
  - `RateLimiterService` depends on abstractions (base classes)
  - Not on concrete implementations (Redis, Token Bucket)
  - Dependency injection via factories

#### Decision 2: Single Source of Truth for Configuration

**Context:** Avoid duplication between .env files and configuration code.

**Options Considered:**

1. **Environment variables only** - Scattered configuration
2. **Database-driven configuration** - Runtime complexity
3. **Python configuration file (SSOT)** - Centralized, type-safe

**Decision:** Python configuration file (`src/rate_limiting/config.py`) as single source of truth

**Rationale:**

- ✅ **SRP:** Configuration isolated in one module
- ✅ **OCP:** Add new endpoints without modifying core logic
- ✅ **Co-location:** Configuration lives with the feature it configures (rate_limiting/)
- ✅ Type-safe with Pydantic validation
- ✅ Complete flexibility: each endpoint can use different strategy + storage
- ✅ No duplication (DRY principle)
- ✅ Easy to understand and modify
- ✅ Self-contained: Rate limiting package has everything (config, service, middleware, models)
- ❌ .env only for infrastructure (Redis URL, not rate limits)

#### Decision 3: Separate Package Architecture

**Context:** Rate limiting is a complete feature/bounded context, not a business service. Where should it live in the codebase for maximum clarity, maintainability, and extractability?

**Options Considered:**

1. **Flat structure:** `services/rate_limiter.py`, `services/token_bucket.py`, etc.
   - ❌ Scattered files, no cohesion
   - ❌ Hard to understand complete feature
   - ❌ Difficult to extract or reuse

2. **Bundled under services:** `services/rate_limiting/` with submodules
   - ✅ Cohesive module
   - ❌ Conceptually confusing (is rate limiting a "service"?)
   - ❌ Mixed with business logic services (auth, email, token)
   - ❌ Harder to extract (tied to services/ semantics)

3. **Separate package:** `src/rate_limiting/` at root level
   - ✅ **True module independence** (self-contained feature)
   - ✅ **Conceptual clarity** (infrastructure, not business logic)
   - ✅ **Clean separation** (services/ = business logic, rate_limiting/ = infrastructure)
   - ✅ **Easy extraction** (copy entire package to new project)
   - ✅ **DDD alignment** (bounded context)
   - ✅ **Co-location** (config, middleware, models all in one place)

**Decision:** Separate package architecture (`src/rate_limiting/`)

**Rationale:**

Rate limiting is a **feature/bounded context**, not a business service:

- ✅ **Package by Feature:** Rate limiting is infrastructure (like logging, caching), not business logic (like payments, orders)
- ✅ **True Module Independence:** Complete package can exist standalone without coupling to services/
- ✅ **Cleaner Architecture:**
  - `services/` = Business logic (auth, token, email, payments)
  - `rate_limiting/` = Infrastructure feature (rate limiting, throttling)
  - `providers/` = External integrations (Schwab, Plaid)
- ✅ **Better Extractability:** Can be extracted to separate package (e.g., `dashtam-rate-limiting` on PyPI) without restructuring
- ✅ **SOLID at Package Level:**
  - **S:** Rate limiting package has single responsibility (rate limiting!)
  - **O:** Can extend without touching other packages
  - **L:** Entire package can be swapped with alternative implementation
  - **I:** Clean interface exposed via `__init__.py`
  - **D:** Application depends on rate_limiting abstraction, not internal implementation
- ✅ **DDD Alignment:** Rate limiting is a bounded context (self-contained domain)
- ✅ **Co-location Benefits:** Can bundle config.py, middleware.py, models.py together (true self-containment)
- ✅ **Plugin Architecture:** Discoverable and registrable just like any other feature

#### Decision 4: Redis Lua Scripts for Atomicity

**Context:** Token bucket requires multiple operations that must be atomic.

**Options Considered:**

1. **Multiple Redis commands** - Race conditions, incorrect behavior
2. **Redis transactions (MULTI/EXEC)** - Still vulnerable to race conditions
3. **Redis Lua scripts** - Atomic, server-side execution

**Decision:** Redis Lua scripts for all token bucket operations

**Rationale:**

- ✅ **Correctness:** Atomic operations prevent race conditions
- ✅ **Performance:** 1ms faster than multiple network calls
- ✅ **Built-in:** Lua included in Redis 8.2.1 (no installation)
- ✅ Industry standard for rate limiting
- ✅ Server-side math (no clock skew issues)

### Constraints

- **Technical:** Must use Redis 8.2.1 (already deployed)
- **Performance:** <5ms p95 latency overhead requirement
- **Compatibility:** Must work with FastAPI async patterns
- **Testing:** Synchronous test pattern (FastAPI TestClient)
- **Coverage:** 85%+ target (critical components 95%+)
- **Development:** All work in Docker containers (WARP.md rule)

## Phases and Steps

**Note:** Phases are organized logically without rigid timelines. Complete each phase before proceeding to the next.

### Phase 1: Core Infrastructure & SOLID Foundation

**Objective:** Establish configuration, abstractions, and token bucket implementation with strict SOLID compliance.

**Status:** ⏳ Pending

**SOLID Principles Applied:** All 5 (S, O, L, I, D)

**Target Directory Structure:**

```text
src/
├── rate_limiting/              # Self-contained rate limiting package ✨
│   ├── __init__.py             # Package exports
│   ├── config.py               # Rate limit configuration (SSOT)
│   ├── service.py              # Orchestrator service
│   ├── factory.py              # Dependency injection
│   ├── middleware.py           # FastAPI middleware (Phase 2)
│   ├── models.py               # Audit log model (Phase 4)
│   ├── algorithms/
│   │   ├── __init__.py
│   │   ├── base.py             # Abstract algorithm interface
│   │   └── token_bucket.py     # Token bucket implementation
│   ├── storage/
│   │   ├── __init__.py
│   │   ├── base.py             # Abstract storage interface
│   │   └── redis_storage.py    # Redis implementation with Lua
│   └── tests/                  # Co-located tests (for independence) 🧪
│       ├── __init__.py
│       ├── test_config.py      # Configuration tests
│       ├── test_algorithms.py  # Algorithm tests
│       ├── test_storage.py     # Storage tests
│       └── test_service.py     # Service tests
│
├── services/                   # Business logic services
│   ├── auth_service.py
│   ├── token_service.py
│   ├── email_service.py
│   └── ...
│
├── providers/                  # Financial provider integrations
│   ├── registry.py
│   └── ...
│
└── main.py                     # Application entry point
```

**Key Architectural Principles:**

- **Self-Containment:** Everything rate limiting related in `src/rate_limiting/`
- **Package by Feature:** Rate limiting is a bounded context (DDD)
- **Clean Separation:**
  - `services/` = Business logic (auth, payments, orders)
  - `rate_limiting/` = Infrastructure (rate limiting, throttling)
  - `providers/` = External integrations (Schwab, Plaid)
- **SOLID at Package Level:** Rate limiting package is independently deployable/replaceable
- **Pluggable:** Can be extracted to PyPI package without restructuring
- **Co-located Tests:** Tests live in `src/rate_limiting/tests/` for complete independence
  - Rate limiting package can be copied to another project with tests intact
  - Aligns with DDD bounded context philosophy (self-contained domain)
  - Enables future extraction to standalone PyPI package
  - Project-wide tests stay in `tests/` (integration, smoke, etc.)
  - Pytest configured to discover tests in both locations (see `pytest.ini`)

#### Step 1.1: Create Configuration Module (Single Source of Truth)

**Description:** Create `src/rate_limiting/config.py` as the ONLY location for rate limit configuration.

**SOLID Mapping:**

- **S:** Configuration has single responsibility
- **O:** Open for adding new endpoints, closed for modification to existing
- **I:** Minimal interface (configuration data only)

**Actions:**

```python
# src/rate_limiting/config.py

from enum import Enum
from typing import Dict, Literal
from pydantic import BaseModel, Field

class RateLimitStrategy(str, Enum):
    """Available rate limiting strategies."""
    TOKEN_BUCKET = "token_bucket"
    SLIDING_WINDOW = "sliding_window"  # Future
    FIXED_WINDOW = "fixed_window"      # Future

class RateLimitStorage(str, Enum):
    """Available storage backends."""
    REDIS = "redis"
    POSTGRES = "postgres"  # Future
    MEMORY = "memory"      # Testing only

class RateLimitRule(BaseModel):
    """Configuration for a single rate limit rule.
    
    Each endpoint can have completely independent configuration:
    - Different algorithm (token_bucket, sliding_window, etc.)
    - Different storage (redis, postgres, memory)
    - Different limits (max_tokens, refill_rate)
    - Different scope (ip, user, endpoint, provider_user)
    """
    
    strategy: RateLimitStrategy = RateLimitStrategy.TOKEN_BUCKET
    storage: RateLimitStorage = RateLimitStorage.REDIS
    max_tokens: int = Field(gt=0, description="Maximum tokens in bucket")
    refill_rate: float = Field(gt=0, description="Tokens per second")
    scope: Literal["ip", "user", "endpoint", "provider_user"]
    enabled: bool = True
    
    class Config:
        frozen = True  # Immutable for safety

class RateLimitConfig:
    """Single Source of Truth for all rate limiting configuration.
    
    CRITICAL: This is the ONLY place where rate limits are defined.
    Do NOT duplicate configuration in .env files or elsewhere.
    """
    
    # Global defaults
    DEFAULT_STRATEGY = RateLimitStrategy.TOKEN_BUCKET
    DEFAULT_STORAGE = RateLimitStorage.REDIS
    
    # Per-endpoint rules (complete flexibility)
    RULES: Dict[str, RateLimitRule] = {
        # Authentication endpoints (IP-based, before login)
        "auth.login": RateLimitRule(
            strategy=RateLimitStrategy.TOKEN_BUCKET,
            storage=RateLimitStorage.REDIS,
            max_tokens=20,
            refill_rate=5/60,  # 5 per minute
            scope="ip",
            enabled=True
        ),
        "auth.register": RateLimitRule(
            strategy=RateLimitStrategy.TOKEN_BUCKET,
            storage=RateLimitStorage.REDIS,
            max_tokens=10,
            refill_rate=2/60,  # 2 per minute
            scope="ip",
            enabled=True
        ),
        "auth.password_reset_request": RateLimitRule(
            strategy=RateLimitStrategy.TOKEN_BUCKET,
            storage=RateLimitStorage.REDIS,
            max_tokens=5,
            refill_rate=1/300,  # 1 per 5 minutes
            scope="ip",
            enabled=True
        ),
        
        # Authenticated user endpoints (user-based)
        "providers.list": RateLimitRule(
            strategy=RateLimitStrategy.TOKEN_BUCKET,
            storage=RateLimitStorage.REDIS,
            max_tokens=100,
            refill_rate=100/60,  # 100 per minute
            scope="user",
            enabled=True
        ),
        "providers.accounts": RateLimitRule(
            strategy=RateLimitStrategy.TOKEN_BUCKET,
            storage=RateLimitStorage.REDIS,
            max_tokens=100,
            refill_rate=100/60,  # 100 per minute
            scope="user",
            enabled=True
        ),
        
        # Provider-specific limits (per user per provider)
        "provider.schwab.api": RateLimitRule(
            strategy=RateLimitStrategy.TOKEN_BUCKET,
            storage=RateLimitStorage.REDIS,
            max_tokens=100,
            refill_rate=100/60,  # Schwab's limit: 100/min
            scope="provider_user",
            enabled=True
        ),
    }
    
    @classmethod
    def get_rule(cls, endpoint_key: str) -> RateLimitRule:
        """Get rate limit rule for an endpoint.
        
        Args:
            endpoint_key: Endpoint identifier (e.g., 'auth.login')
            
        Returns:
            RateLimitRule configuration
            
        Raises:
            KeyError: If endpoint has no rate limit configured
        """
        if endpoint_key not in cls.RULES:
            raise KeyError(f"No rate limit configured for endpoint: {endpoint_key}")
        return cls.RULES[endpoint_key]
    
    @classmethod
    def is_enabled(cls, endpoint_key: str) -> bool:
        """Check if rate limiting is enabled for an endpoint."""
        try:
            rule = cls.get_rule(endpoint_key)
            return rule.enabled
        except KeyError:
            return False  # No rule = no rate limiting
```

**Verification:**

- [ ] File created: `src/rate_limiting/config.py`
- [ ] All rate limits defined in RULES dictionary
- [ ] Pydantic models validate configuration
- [ ] Type hints complete
- [ ] Docstrings complete (Google style)
- [ ] No environment variables for rate limits (.env only for infra)

**Deliverables:**

- `src/rate_limiting/config.py` (SSOT configuration)

#### Step 1.2: Create Algorithm Abstraction (Interface Segregation + Liskov)

**Description:** Create abstract base class for rate limiting algorithms.

**SOLID Mapping:**

- **S:** Algorithm interface has single responsibility (algorithm logic)
- **O:** Open for new algorithms, closed for modification
- **L:** All implementations must be substitutable
- **I:** Minimal interface (one method: `is_allowed`)
- **D:** Service depends on abstraction, not concrete implementations

**Actions:**

```python
# src/rate_limiting/algorithms/base.py

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.rate_limiting.storage.base import RateLimitStorage
    from src.rate_limiting.config import RateLimitRule

class RateLimitAlgorithm(ABC):
    """Abstract base class for rate limiting algorithms.
    
    This interface ensures all rate limiting algorithms are substitutable
    (Liskov Substitution Principle) and have minimal interface (Interface
    Segregation Principle).
    
    Any algorithm implementation must satisfy this contract:
    - Given a storage backend, key, and configuration
    - Return whether the request is allowed and retry_after time
    
    The algorithm does NOT know about HTTP, FastAPI, or business logic.
    It only knows about: tokens, time, and math.
    """
    
    @abstractmethod
    async def is_allowed(
        self,
        storage: "RateLimitStorage",
        key: str,
        rule: "RateLimitRule",
        cost: int = 1
    ) -> tuple[bool, float]:
        """Check if a request is allowed under this rate limit.
        
        Args:
            storage: Storage backend to use for state persistence
            key: Unique identifier for this rate limit (e.g., "user:123:endpoint")
            rule: Rate limit configuration (max_tokens, refill_rate, etc.)
            cost: Number of tokens to consume (default: 1)
            
        Returns:
            Tuple of (allowed, retry_after):
            - allowed: True if request should be allowed, False if rate limited
            - retry_after: Seconds to wait before retrying (0 if allowed)
            
        Raises:
            None: This method must never raise exceptions. Handle errors gracefully.
        """
        pass
```

**Verification:**

- [ ] File created: `src/rate_limiting/algorithms/base.py`
- [ ] Abstract base class with `@abstractmethod`
- [ ] Minimal interface (Interface Segregation)
- [ ] Type hints complete
- [ ] Docstring explains Liskov Substitution contract
- [ ] No concrete implementation (pure abstraction)

**Deliverables:**

- `src/rate_limiting/algorithms/base.py`
- `src/rate_limiting/algorithms/__init__.py`

#### Step 1.3: Create Storage Abstraction (Interface Segregation + Liskov)

**Description:** Create abstract base class for storage backends.

**SOLID Mapping:**

- **S:** Storage interface has single responsibility (state persistence)
- **O:** Open for new storage backends, closed for modification
- **L:** All implementations must be substitutable (Redis, Postgres, Memory)
- **I:** Minimal interface (one method: `check_and_consume`)
- **D:** Algorithm depends on abstraction, not concrete storage

**Actions:**

```python
# src/rate_limiting/storage/base.py

from abc import ABC, abstractmethod

class RateLimitStorage(ABC):
    """Abstract base class for rate limit storage backends.
    
    This interface ensures all storage implementations are substitutable
    (Liskov Substitution Principle) and have minimal interface (Interface
    Segregation Principle).
    
    The storage backend does NOT know about:
    - Algorithms (token bucket, sliding window, etc.)
    - HTTP/FastAPI
    - Business logic
    
    It only knows about: keys, values, atomicity, and persistence.
    """
    
    @abstractmethod
    async def check_and_consume(
        self,
        key: str,
        max_tokens: int,
        refill_rate: float,
        cost: int = 1
    ) -> tuple[bool, float, int]:
        """Atomically check and consume tokens from rate limit bucket.
        
        This operation MUST be atomic to prevent race conditions in
        distributed systems. Implementation should use:
        - Redis: Lua scripts
        - Postgres: Database transactions
        - Memory: Thread locks
        
        Args:
            key: Unique identifier for this rate limit bucket
            max_tokens: Maximum tokens in bucket (capacity)
            refill_rate: Tokens per second refill rate
            cost: Number of tokens to consume (default: 1)
            
        Returns:
            Tuple of (allowed, retry_after, remaining_tokens):
            - allowed: True if request allowed, False if rate limited
            - retry_after: Seconds to wait before retrying (0 if allowed)
            - remaining_tokens: Tokens remaining after this request
            
        Raises:
            None: This method must handle errors gracefully and never raise.
                  If storage fails, fail open (allow request) to prevent
                  rate limiting from becoming a single point of failure.
        """
        pass
    
    @abstractmethod
    async def get_remaining(self, key: str, max_tokens: int) -> int:
        """Get remaining tokens without consuming any.
        
        Used for informational purposes (e.g., response headers).
        
        Args:
            key: Unique identifier for this rate limit bucket
            max_tokens: Maximum tokens in bucket (for new buckets)
            
        Returns:
            Number of tokens remaining (0 to max_tokens)
        """
        pass
    
    @abstractmethod
    async def reset(self, key: str) -> None:
        """Reset a rate limit bucket (for testing or admin operations).
        
        Args:
            key: Unique identifier for this rate limit bucket
        """
        pass
```

**Verification:**

- [ ] File created: `src/rate_limiting/storage/base.py`
- [ ] Abstract base class with `@abstractmethod`
- [ ] Minimal interface (Interface Segregation)
- [ ] Type hints complete
- [ ] Docstring explains atomicity requirements
- [ ] Fail-open strategy documented

**Deliverables:**

- `src/rate_limiting/storage/base.py`
- `src/rate_limiting/storage/__init__.py`

#### Step 1.4: Implement Token Bucket Algorithm

**Description:** Implement concrete token bucket algorithm following abstraction.

**SOLID Mapping:**

- **S:** Only token bucket math (no storage, HTTP, or business logic)
- **O:** Closed for modification (implements interface)
- **L:** Substitutable with any other algorithm implementation
- **I:** Uses minimal storage interface
- **D:** Depends on storage abstraction, not concrete Redis

**Actions:**

```python
# src/rate_limiting/algorithms/token_bucket.py

import time
import logging
from typing import TYPE_CHECKING

from src.rate_limiting.algorithms.base import RateLimitAlgorithm

if TYPE_CHECKING:
    from src.rate_limiting.storage.base import RateLimitStorage
    from src.rate_limiting.config import RateLimitRule

logger = logging.getLogger(__name__)

class TokenBucketAlgorithm(RateLimitAlgorithm):
    """Token Bucket rate limiting algorithm.
    
    Token bucket allows burst traffic by accumulating tokens over time.
    Users can "save up" tokens and use them all at once for legitimate
    burst usage (e.g., refreshing multiple accounts simultaneously).
    
    Algorithm:
    1. Bucket starts full (max_tokens)
    2. Tokens refill at constant rate (refill_rate per second)
    3. Each request consumes tokens (cost)
    4. If not enough tokens: request denied
    5. Tokens cap at max_tokens (can't save infinite capacity)
    
    Example:
        max_tokens=100, refill_rate=10/sec
        
        Time 0s:  100 tokens (full)
        Time 5s:  User makes 50 requests → 50 tokens remain
        Time 10s: 50 + (10*5) = 100 tokens (refilled, capped)
        
        User makes 80 requests → 20 tokens remain
        User tries 30 more → DENIED (need 30, have 20)
        Retry after: (30-20)/10 = 1 second
    
    Why this algorithm?
    - Industry standard (AWS, GitHub, Stripe)
    - Best user experience (smooth burst handling)
    - Perfect for financial APIs (multiple account refreshes)
    - Scored 37/40 in research comparison
    
    SOLID Compliance:
    - S: Only algorithm logic (no storage, HTTP, business logic)
    - O: Implements interface, closed for modification
    - L: Substitutable with any other algorithm
    - I: Uses minimal storage interface
    - D: Depends on storage abstraction
    """
    
    async def is_allowed(
        self,
        storage: "RateLimitStorage",
        key: str,
        rule: "RateLimitRule",
        cost: int = 1
    ) -> tuple[bool, float]:
        """Check if request is allowed under token bucket algorithm.
        
        Delegates atomic operations to storage backend (Redis Lua script).
        
        Args:
            storage: Storage backend (Redis, Postgres, Memory)
            key: Unique rate limit key (e.g., "user:123:endpoint")
            rule: Rate limit configuration
            cost: Tokens to consume (default: 1)
            
        Returns:
            (allowed, retry_after) tuple
        """
        try:
            # Delegate to storage for atomic check-and-consume
            allowed, retry_after, remaining = await storage.check_and_consume(
                key=key,
                max_tokens=rule.max_tokens,
                refill_rate=rule.refill_rate,
                cost=cost
            )
            
            if not allowed:
                logger.warning(
                    f"Rate limit exceeded: key={key}, "
                    f"remaining={remaining}, retry_after={retry_after:.2f}s"
                )
            
            return allowed, retry_after
            
        except Exception as e:
            # Fail open: if storage fails, allow request
            # This prevents rate limiting from being a single point of failure
            logger.error(
                f"Rate limit storage error (failing open): {e}",
                exc_info=True
            )
            return True, 0.0
```

**Verification:**

- [ ] File created: `src/rate_limiting/algorithms/token_bucket.py`
- [ ] Implements `RateLimitAlgorithm` interface
- [ ] Complete docstring explaining algorithm
- [ ] Error handling (fail open strategy)
- [ ] Logging for debugging
- [ ] Type hints complete
- [ ] SOLID compliance documented in docstring

**Deliverables:**

- `src/rate_limiting/algorithms/token_bucket.py`

#### Step 1.5: Implement Redis Storage with Lua Script

**Description:** Implement Redis storage backend with atomic Lua script.

**SOLID Mapping:**

- **S:** Only Redis operations (no algorithm, HTTP, or business logic)
- **O:** Closed for modification (implements interface)
- **L:** Substitutable with Postgres/Memory implementations
- **I:** Uses minimal Redis interface
- **D:** Depends on Redis client abstraction (via dependency injection)

**Actions:**

```python
# src/rate_limiting/storage/redis_storage.py

import time
import logging
from typing import Optional
from redis.asyncio import Redis

from src.rate_limiting.storage.base import RateLimitStorage

logger = logging.getLogger(__name__)

# Lua script for atomic token bucket operations
# This script runs INSIDE Redis, preventing race conditions
TOKEN_BUCKET_LUA = """
local key = KEYS[1]
local max_tokens = tonumber(ARGV[1])
local refill_rate = tonumber(ARGV[2])
local cost = tonumber(ARGV[3])
local now = tonumber(ARGV[4])

-- Get current state (tokens and last_refill_time)
local state = redis.call('HMGET', key, 'tokens', 'last_refill')
local tokens = tonumber(state[1]) or max_tokens
local last_refill = tonumber(state[2]) or now

-- Calculate refill since last access
local time_passed = math.max(0, now - last_refill)
local refill_amount = time_passed * refill_rate
local new_tokens = math.min(max_tokens, tokens + refill_amount)

-- Check if we have enough tokens
local allowed = new_tokens >= cost

if allowed then
    -- Consume tokens
    new_tokens = new_tokens - cost
    redis.call('HSET', key, 'tokens', new_tokens, 'last_refill', now)
    redis.call('EXPIRE', key, 3600)  -- 1 hour TTL
    return {1, 0, new_tokens}  -- allowed, retry_after, remaining
else
    -- Calculate retry_after
    local tokens_needed = cost - new_tokens
    local retry_after = tokens_needed / refill_rate
    redis.call('HSET', key, 'tokens', new_tokens, 'last_refill', now)
    redis.call('EXPIRE', key, 3600)
    return {0, retry_after, new_tokens}  -- denied, retry_after, remaining
end
"""

class RedisRateLimitStorage(RateLimitStorage):
    """Redis storage backend for rate limiting using Lua scripts.
    
    Uses Redis Lua scripts for atomic operations to prevent race conditions
    in distributed systems. All token bucket operations (read, calculate,
    write) happen atomically inside Redis.
    
    Why Redis + Lua?
    - Atomic operations (prevents race conditions)
    - Fast (2-3ms) with connection pooling
    - Server-side math (no clock skew)
    - Industry standard for rate limiting
    - Already deployed (Redis 8.2.1)
    
    SOLID Compliance:
    - S: Only Redis operations (storage responsibility)
    - O: Implements interface, closed for modification
    - L: Substitutable with Postgres/Memory storage
    - I: Uses minimal Redis interface
    - D: Depends on Redis client abstraction (injected)
    """
    
    def __init__(self, redis_client: Redis):
        """Initialize Redis storage.
        
        Args:
            redis_client: Redis async client (injected dependency)
        """
        self.redis = redis_client
        self._lua_script = None  # Cached script SHA
    
    async def _ensure_script_loaded(self) -> str:
        """Load Lua script into Redis (cached for performance).
        
        Returns:
            Script SHA hash for EVALSHA command
        """
        if self._lua_script is None:
            self._lua_script = await self.redis.script_load(TOKEN_BUCKET_LUA)
        return self._lua_script
    
    async def check_and_consume(
        self,
        key: str,
        max_tokens: int,
        refill_rate: float,
        cost: int = 1
    ) -> tuple[bool, float, int]:
        """Atomically check and consume tokens using Redis Lua script.
        
        Args:
            key: Rate limit key (e.g., "ratelimit:user:123:endpoint")
            max_tokens: Maximum bucket capacity
            refill_rate: Tokens per second refill rate
            cost: Tokens to consume
            
        Returns:
            (allowed, retry_after, remaining_tokens)
        """
        try:
            script_sha = await self._ensure_script_loaded()
            now = time.time()
            
            # Execute Lua script atomically
            result = await self.redis.evalsha(
                script_sha,
                1,  # Number of keys
                key,
                max_tokens,
                refill_rate,
                cost,
                now
            )
            
            allowed = bool(result[0])
            retry_after = float(result[1])
            remaining = int(result[2])
            
            return allowed, retry_after, remaining
            
        except Exception as e:
            # Fail open: if Redis fails, allow request
            logger.error(
                f"Redis error in check_and_consume (failing open): {e}",
                exc_info=True
            )
            return True, 0.0, max_tokens
    
    async def get_remaining(self, key: str, max_tokens: int) -> int:
        """Get remaining tokens without consuming any.
        
        Args:
            key: Rate limit key
            max_tokens: Maximum tokens (for new buckets)
            
        Returns:
            Remaining tokens (0 to max_tokens)
        """
        try:
            state = await self.redis.hmget(key, 'tokens', 'last_refill')
            if state[0] is None:
                return max_tokens  # New bucket, full
            
            tokens = float(state[0])
            last_refill = float(state[1])
            now = time.time()
            
            # Calculate refill
            time_passed = max(0, now - last_refill)
            refill_amount = time_passed * (max_tokens / 60.0)  # Assume 1/min
            current_tokens = min(max_tokens, tokens + refill_amount)
            
            return int(current_tokens)
            
        except Exception as e:
            logger.error(f"Redis error in get_remaining: {e}")
            return max_tokens  # Fail open
    
    async def reset(self, key: str) -> None:
        """Reset a rate limit bucket.
        
        Args:
            key: Rate limit key to reset
        """
        try:
            await self.redis.delete(key)
        except Exception as e:
            logger.error(f"Redis error in reset: {e}")
```

**Verification:**

- [ ] File created: `src/rate_limiting/storage/redis_storage.py`
- [ ] Implements `RateLimitStorage` interface
- [ ] Lua script for atomic operations
- [ ] Error handling (fail open)
- [ ] Logging for debugging
- [ ] Connection pooling support
- [ ] Type hints complete
- [ ] SOLID compliance documented

**Deliverables:**

- `src/rate_limiting/storage/redis_storage.py`

#### Step 1.6: Create Rate Limiter Service (Dependency Inversion)

**Description:** Create orchestrating service that connects algorithm + storage.

**SOLID Mapping:**

- **S:** Only orchestration (connect algorithm + storage + config)
- **O:** Open for new algorithms/storage, closed for modification
- **L:** Any algorithm/storage is substitutable
- **I:** Minimal interface (one method: `is_allowed`)
- **D:** Depends on abstractions (RateLimitAlgorithm, RateLimitStorage), not concrete implementations

**Actions:**

```python
# src/rate_limiting/service.py

import logging
from typing import Optional

from src.rate_limiting.algorithms.base import RateLimitAlgorithm
from src.rate_limiting.storage.base import RateLimitStorage
from src.rate_limiting.config import RateLimitConfig, RateLimitRule

logger = logging.getLogger(__name__)

class RateLimiterService:
    """Rate limiter service - orchestrates algorithm and storage.
    
    This service is the glue between:
    - Configuration (what limits to apply)
    - Algorithm (how to calculate limits)
    - Storage (where to persist state)
    
    It does NOT contain algorithm logic or storage logic.
    It only coordinates components.
    
    SOLID Compliance:
    - S: Single responsibility (orchestration only)
    - O: Open for new algorithms/storage, closed for modification
    - L: Any algorithm/storage implementation works
    - I: Minimal interface (one public method)
    - D: Depends on abstractions, not concrete implementations
    
    Example usage:
        algorithm = TokenBucketAlgorithm()
        storage = RedisRateLimitStorage(redis_client)
        service = RateLimiterService(algorithm, storage)
        
        allowed, retry_after = await service.is_allowed(
            endpoint="auth.login",
            identifier="192.168.1.1"
        )
    """
    
    def __init__(
        self,
        algorithm: RateLimitAlgorithm,
        storage: RateLimitStorage
    ):
        """Initialize rate limiter service.
        
        Args:
            algorithm: Rate limiting algorithm (injected dependency)
            storage: Storage backend (injected dependency)
        """
        self.algorithm = algorithm
        self.storage = storage
    
    async def is_allowed(
        self,
        endpoint: str,
        identifier: str,
        cost: int = 1
    ) -> tuple[bool, float, Optional[RateLimitRule]]:
        """Check if a request is allowed under rate limits.
        
        Args:
            endpoint: Endpoint key (e.g., 'auth.login')
            identifier: Request identifier (IP, user_id, etc.)
            cost: Number of tokens to consume (default: 1)
            
        Returns:
            Tuple of (allowed, retry_after, rule):
            - allowed: True if request allowed, False if rate limited
            - retry_after: Seconds to wait before retrying (0 if allowed)
            - rule: Applied rate limit rule (None if no rule configured)
        """
        try:
            # Get configuration for this endpoint
            rule = RateLimitConfig.get_rule(endpoint)
            
            if not rule.enabled:
                # Rate limiting disabled for this endpoint
                return True, 0.0, rule
            
            # Build rate limit key
            key = self._build_key(endpoint, identifier, rule.scope)
            
            # Delegate to algorithm
            allowed, retry_after = await self.algorithm.is_allowed(
                storage=self.storage,
                key=key,
                rule=rule,
                cost=cost
            )
            
            return allowed, retry_after, rule
            
        except KeyError:
            # No rate limit configured for this endpoint
            return True, 0.0, None
        except Exception as e:
            # Unexpected error: fail open
            logger.error(
                f"Rate limiter error (failing open): endpoint={endpoint}, "
                f"identifier={identifier}, error={e}",
                exc_info=True
            )
            return True, 0.0, None
    
    def _build_key(self, endpoint: str, identifier: str, scope: str) -> str:
        """Build Redis key for rate limit bucket.
        
        Key format: ratelimit:{scope}:{identifier}:{endpoint}
        
        Args:
            endpoint: Endpoint key
            identifier: Request identifier (IP, user_id, etc.)
            scope: Rate limit scope (ip, user, endpoint, provider_user)
            
        Returns:
            Redis key string
        """
        return f"ratelimit:{scope}:{identifier}:{endpoint}"
```

**Verification:**

- [ ] File created: `src/rate_limiting/service.py`
- [ ] Accepts injected dependencies (algorithm, storage)
- [ ] Minimal interface (one public method)
- [ ] Error handling (fail open)
- [ ] Logging for debugging
- [ ] Type hints complete
- [ ] SOLID principles documented in docstring

**Deliverables:**

- `src/rate_limiting/service.py`
- `src/rate_limiting/__init__.py` (exports)

### Phase 2: FastAPI Integration & Middleware

**Objective:** Integrate rate limiting with FastAPI via middleware, implement HTTP 429 responses, add rate limit headers.

**Status:** ⏳ Pending

**SOLID Principles Applied:** S, O, D

#### Step 2.1: Create Rate Limit Middleware

**Description:** Create FastAPI middleware to intercept requests and enforce rate limits.

**SOLID Mapping:**

- **S:** Single responsibility (HTTP interception only)
- **O:** Open for extension (new endpoints), closed for modification
- **D:** Depends on RateLimiterService abstraction

**Actions:**

```python
# src/rate_limiting/middleware.py

import logging
from typing import Callable, Optional
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from src.rate_limiting.service import RateLimiterService
from src.rate_limiting.config import RateLimitRule

logger = logging.getLogger(__name__)

class RateLimitMiddleware(BaseHTTPMiddleware):
    """FastAPI middleware for rate limiting.
    
    Intercepts all HTTP requests before they reach endpoints and
    enforces rate limits based on configuration.
    
    Responsibilities:
    - Extract request information (IP, user_id, endpoint)
    - Call RateLimiterService to check limits
    - Return HTTP 429 if rate limited
    - Add rate limit headers to all responses
    
    Does NOT contain:
    - Algorithm logic (delegated to algorithm)
    - Storage logic (delegated to storage)
    - Business logic (delegated to endpoints)
    
    SOLID Compliance:
    - S: Single responsibility (HTTP interception)
    - O: Closed for modification (uses service abstraction)
    - D: Depends on RateLimiterService abstraction
    """
    
    def __init__(
        self,
        app: ASGIApp,
        rate_limiter: RateLimiterService
    ):
        """Initialize rate limit middleware.
        
        Args:
            app: FastAPI application
            rate_limiter: Rate limiter service (injected dependency)
        """
        super().__init__(app)
        self.rate_limiter = rate_limiter
    
    async def dispatch(
        self,
        request: Request,
        call_next: Callable
    ) -> Response:
        """Intercept request and enforce rate limits.
        
        Args:
            request: Incoming HTTP request
            call_next: Next middleware/endpoint in chain
            
        Returns:
            HTTP response (429 if rate limited, otherwise from endpoint)
        """
        # Extract endpoint key and identifier
        endpoint_key = self._get_endpoint_key(request)
        identifier = await self._get_identifier(request)
        
        # Check rate limit
        allowed, retry_after, rule = await self.rate_limiter.is_allowed(
            endpoint=endpoint_key,
            identifier=identifier
        )
        
        if not allowed:
            # Rate limited: return HTTP 429
            return self._rate_limit_response(
                request=request,
                retry_after=retry_after,
                rule=rule
            )
        
        # Allowed: proceed to endpoint
        response = await call_next(request)
        
        # Add rate limit headers
        if rule:
            self._add_rate_limit_headers(response, rule, identifier)
        
        return response
    
    def _get_endpoint_key(self, request: Request) -> str:
        """Extract endpoint key from request.
        
        Maps HTTP path to configuration key.
        
        Args:
            request: HTTP request
            
        Returns:
            Endpoint key (e.g., 'auth.login')
        """
        path = request.url.path
        
        # Map paths to endpoint keys
        endpoint_map = {
            "/api/v1/auth/login": "auth.login",
            "/api/v1/auth/register": "auth.register",
            "/api/v1/auth/password-reset": "auth.password_reset_request",
            "/api/v1/providers": "providers.list",
            "/api/v1/providers/accounts": "providers.accounts",
        }
        
        return endpoint_map.get(path, "unknown")
    
    async def _get_identifier(self, request: Request) -> str:
        """Extract identifier for rate limiting.
        
        Uses:
        - User ID (if authenticated)
        - IP address (if not authenticated)
        
        Args:
            request: HTTP request
            
        Returns:
            Identifier string (user_id or IP)
        """
        # Try to get authenticated user
        user = request.state.user if hasattr(request.state, "user") else None
        if user:
            return f"user:{user.id}"
        
        # Fall back to IP address
        client_ip = request.client.host if request.client else "unknown"
        return f"ip:{client_ip}"
    
    def _rate_limit_response(
        self,
        request: Request,
        retry_after: float,
        rule: Optional[RateLimitRule]
    ) -> JSONResponse:
        """Create HTTP 429 rate limit response.
        
        Args:
            request: HTTP request that was rate limited
            retry_after: Seconds to wait before retrying
            rule: Applied rate limit rule
            
        Returns:
            JSONResponse with 429 status
        """
        response_data = {
            "error": "Rate limit exceeded",
            "message": f"Too many requests. Please try again in {int(retry_after)} seconds.",
            "retry_after": int(retry_after)
        }
        
        headers = {
            "Retry-After": str(int(retry_after)),
            "X-RateLimit-Limit": str(rule.max_tokens) if rule else "unknown",
            "X-RateLimit-Remaining": "0",
            "X-RateLimit-Reset": str(int(retry_after))
        }
        
        logger.warning(
            f"Rate limit exceeded: path={request.url.path}, "
            f"identifier={self._get_identifier(request)}, "
            f"retry_after={retry_after:.2f}s"
        )
        
        return JSONResponse(
            status_code=429,
            content=response_data,
            headers=headers
        )
    
    def _add_rate_limit_headers(
        self,
        response: Response,
        rule: RateLimitRule,
        identifier: str
    ) -> None:
        """Add rate limit headers to response.
        
        Headers:
        - X-RateLimit-Limit: Maximum requests allowed
        - X-RateLimit-Remaining: Requests remaining
        - X-RateLimit-Reset: Seconds until full reset
        
        Args:
            response: HTTP response
            rule: Applied rate limit rule
            identifier: Request identifier
        """
        # TODO: Get actual remaining tokens from storage
        response.headers["X-RateLimit-Limit"] = str(rule.max_tokens)
        response.headers["X-RateLimit-Remaining"] = str(rule.max_tokens)  # Placeholder
        response.headers["X-RateLimit-Reset"] = str(60)  # Placeholder
```

**Verification:**

- [ ] File created: `src/rate_limiting/middleware.py`
- [ ] Extends `BaseHTTPMiddleware`
- [ ] Accepts injected RateLimiterService
- [ ] Returns HTTP 429 with Retry-After header
- [ ] Adds X-RateLimit-* headers
- [ ] Logging for rate limit violations
- [ ] Type hints complete

**Deliverables:**

- `src/rate_limiting/middleware.py`
- `src/middleware/__init__.py`

#### Step 2.2: Create Factory Function (Dependency Injection)

**Description:** Create factory function to instantiate rate limiter with dependencies.

**SOLID Mapping:**

- **D:** Dependency Inversion - factory creates dependencies and injects them

**Actions:**

```python
# src/rate_limiting/factory.py

from redis.asyncio import Redis
from src.core.database import get_redis
from src.rate_limiting.service import RateLimiterService
from src.rate_limiting.algorithms.token_bucket import TokenBucketAlgorithm
from src.rate_limiting.storage.redis_storage import RedisRateLimitStorage

async def get_rate_limiter_service() -> RateLimiterService:
    """Factory function to create rate limiter service with dependencies.
    
    This function implements Dependency Inversion Principle:
    - High-level service (RateLimiterService) depends on abstractions
    - This factory creates concrete implementations and injects them
    - Easy to swap implementations by changing factory
    
    Returns:
        Configured RateLimiterService instance
    """
    # Get Redis client (async)
    redis_client = await get_redis()
    
    # Create storage backend (concrete implementation)
    storage = RedisRateLimitStorage(redis_client)
    
    # Create algorithm (concrete implementation)
    algorithm = TokenBucketAlgorithm()
    
    # Create and return service (injected dependencies)
    return RateLimiterService(algorithm=algorithm, storage=storage)
```

**Verification:**

- [ ] File created: `src/rate_limiting/factory.py`
- [ ] Creates concrete implementations
- [ ] Injects dependencies into service
- [ ] Async function (Redis client is async)
- [ ] Type hints complete

**Deliverables:**

- `src/rate_limiting/factory.py`

#### Step 2.3: Register Middleware in main.py

**Description:** Add rate limiting middleware to FastAPI application.

**Actions:**

```python
# src/main.py (additions)

from src.rate_limiting.middleware import RateLimitMiddleware
from src.rate_limiting.factory import get_rate_limiter_service

# ... existing code ...

# Add rate limiting middleware
@app.on_event("startup")
async def startup_rate_limiter():
    """Initialize rate limiter on startup."""
    rate_limiter = await get_rate_limiter_service()
    app.add_middleware(RateLimitMiddleware, rate_limiter=rate_limiter)

# ... rest of main.py ...
```

**Verification:**

- [ ] Middleware registered in main.py
- [ ] Factory function called on startup
- [ ] Middleware applied to all routes
- [ ] No import errors
- [ ] Development environment starts successfully

**Deliverables:**

- Updated `src/main.py`

### Phase 3: Testing & Validation

**Objective:** Comprehensive test coverage following testing guide patterns.

**Status:** ✅ Complete

**Test Strategy:** Independent bounded context (DDD pattern) with co-located tests for future extraction as standalone package.

**Implementation Summary:**
- All tests co-located in `src/rate_limiting/tests/` (not in main test suite)
- Rate limiting tests run manually in development only
- Not part of CI/CD (316 main tests unchanged)
- Future: Extractable as standalone package with own CI/CD

**Actual Tests Implemented:**
- Step 3.1: Token bucket algorithm tests (8 tests) - Completed in Phase 1
- Step 3.2: Redis storage unit tests (25 tests) - Completed in Phase 3 with fakeredis
- Step 3.3: Service integration tests (13 tests) - Completed in Phase 1  
- Step 3.4: Middleware API tests (19 tests) - Completed in Phase 2
- Step 3.5: Smoke tests - Deferred (will be added after workflow established)

**Total Rate Limiting Tests: 65 tests** (all passing)

**Test Execution:**
```bash
# Run all rate limiting tests in development
docker compose exec app uv run pytest src/rate_limiting/tests/ -v
```

#### Step 3.1: Unit Tests - Token Bucket Algorithm

**Description:** Test token bucket algorithm logic in isolation.

**Actions:**

```python
# tests/unit/services/rate_limiting/test_token_bucket_algorithm.py

import pytest
from unittest.mock import AsyncMock, MagicMock
from src.rate_limiting.algorithms.token_bucket import TokenBucketAlgorithm
from src.rate_limiting.config import RateLimitRule, RateLimitStrategy, RateLimitStorage as StorageEnum

class TestTokenBucketAlgorithm:
    """Unit tests for TokenBucketAlgorithm.
    
    Tests algorithm logic WITHOUT actual Redis/storage.
    Uses mocked storage to test algorithm behavior.
    """
    
    @pytest.fixture
    def algorithm(self):
        """Create algorithm instance."""
        return TokenBucketAlgorithm()
    
    @pytest.fixture
    def mock_storage(self):
        """Create mocked storage."""
        storage = AsyncMock()
        return storage
    
    @pytest.fixture
    def rule(self):
        """Create test rate limit rule."""
        return RateLimitRule(
            strategy=RateLimitStrategy.TOKEN_BUCKET,
            storage=StorageEnum.REDIS,
            max_tokens=10,
            refill_rate=1.0,  # 1 token per second
            scope="user"
        )
    
    async def test_allowed_request(self, algorithm, mock_storage, rule):
        """Test that request is allowed when tokens available."""
        # Mock storage returns: allowed=True, retry_after=0, remaining=9
        mock_storage.check_and_consume.return_value = (True, 0.0, 9)
        
        allowed, retry_after = await algorithm.is_allowed(
            storage=mock_storage,
            key="test:key",
            rule=rule,
            cost=1
        )
        
        assert allowed is True
        assert retry_after == 0.0
        mock_storage.check_and_consume.assert_called_once()
    
    async def test_denied_request(self, algorithm, mock_storage, rule):
        """Test that request is denied when insufficient tokens."""
        # Mock storage returns: allowed=False, retry_after=5.0, remaining=0
        mock_storage.check_and_consume.return_value = (False, 5.0, 0)
        
        allowed, retry_after = await algorithm.is_allowed(
            storage=mock_storage,
            key="test:key",
            rule=rule,
            cost=1
        )
        
        assert allowed is False
        assert retry_after == 5.0
        mock_storage.check_and_consume.assert_called_once()
    
    async def test_storage_failure_fail_open(self, algorithm, mock_storage, rule):
        """Test that algorithm fails open when storage raises exception."""
        # Mock storage raises exception
        mock_storage.check_and_consume.side_effect = Exception("Redis down")
        
        allowed, retry_after = await algorithm.is_allowed(
            storage=mock_storage,
            key="test:key",
            rule=rule,
            cost=1
        )
        
        # Should fail open (allow request)
        assert allowed is True
        assert retry_after == 0.0
    
    async def test_cost_parameter(self, algorithm, mock_storage, rule):
        """Test that cost parameter is passed to storage."""
        mock_storage.check_and_consume.return_value = (True, 0.0, 5)
        
        await algorithm.is_allowed(
            storage=mock_storage,
            key="test:key",
            rule=rule,
            cost=5  # Consume 5 tokens
        )
        
        # Verify cost was passed to storage
        call_args = mock_storage.check_and_consume.call_args
        assert call_args.kwargs['cost'] == 5
```

**Verification:**

- [ ] File created
- [ ] Tests algorithm logic WITHOUT actual storage
- [ ] Tests success case (tokens available)
- [ ] Tests failure case (insufficient tokens)
- [ ] Tests error handling (fail open)
- [ ] Tests cost parameter
- [ ] 100% coverage of algorithm code
- [ ] All tests pass

**Deliverables:**

- `tests/unit/services/rate_limiting/test_token_bucket_algorithm.py`

#### Step 3.2: Unit Tests - Redis Storage

**Description:** Test Redis storage with fakeredis (in-memory emulation).

**Status:** ✅ Complete

**Actual Implementation:** Used fakeredis[lua] instead of test container for faster, isolated unit tests.

**Test File:** `src/rate_limiting/tests/test_redis_storage.py` (25 tests, 574 lines)

**Test Coverage:**
- Initial bucket state and first request handling (2 tests)
- Token consumption and depletion (3 tests)
- Token refill over time with asyncio.sleep (2 tests)
- Retry-after calculation accuracy (2 tests)
- get_remaining() method (3 tests)
- reset() method (2 tests)
- Error handling and fail-open behavior (4 tests)
- Lua script loading and caching (2 tests)
- Atomicity with concurrent requests (1 test)
- Edge cases: zero cost, high cost, extreme refill rates (4 tests)

**Key Features:**
- Uses fakeredis for fast, isolated testing (no external Redis needed)
- Tests actual Lua script execution (fakeredis includes Lua support)
- Comprehensive coverage of all Redis storage methods
- All 25 tests passing in ~16 seconds

**Actions:**

```python
# tests/unit/services/rate_limiting/test_redis_storage.py

import pytest
import time
from src.rate_limiting.storage.redis_storage import RedisRateLimitStorage

class TestRedisRateLimitStorage:
    """Unit tests for RedisRateLimitStorage.
    
    Tests Redis operations with actual Redis test container.
    Tests Lua script behavior and atomicity.
    """
    
    @pytest.fixture
    async def storage(self, test_redis):
        """Create storage instance with test Redis."""
        return RedisRateLimitStorage(test_redis)
    
    async def test_initial_bucket_full(self, storage):
        """Test that new bucket starts full."""
        allowed, retry_after, remaining = await storage.check_and_consume(
            key="test:new:bucket",
            max_tokens=100,
            refill_rate=10.0,
            cost=1
        )
        
        assert allowed is True
        assert retry_after == 0.0
        assert remaining == 99  # Started at 100, consumed 1
    
    async def test_token_consumption(self, storage):
        """Test that tokens are consumed correctly."""
        key = "test:consumption"
        
        # Consume 50 tokens
        allowed1, _, remaining1 = await storage.check_and_consume(
            key=key, max_tokens=100, refill_rate=10.0, cost=50
        )
        assert allowed1 is True
        assert remaining1 == 50
        
        # Consume 30 more tokens
        allowed2, _, remaining2 = await storage.check_and_consume(
            key=key, max_tokens=100, refill_rate=10.0, cost=30
        )
        assert allowed2 is True
        assert remaining2 == 20
    
    async def test_insufficient_tokens(self, storage):
        """Test denial when insufficient tokens."""
        key = "test:insufficient"
        
        # Consume all tokens
        await storage.check_and_consume(
            key=key, max_tokens=10, refill_rate=1.0, cost=10
        )
        
        # Try to consume more (should be denied)
        allowed, retry_after, remaining = await storage.check_and_consume(
            key=key, max_tokens=10, refill_rate=1.0, cost=5
        )
        
        assert allowed is False
        assert retry_after > 0  # Should suggest waiting
        assert remaining == 0
    
    async def test_token_refill(self, storage):
        """Test that tokens refill over time."""
        key = "test:refill"
        
        # Consume all tokens
        await storage.check_and_consume(
            key=key, max_tokens=10, refill_rate=5.0, cost=10  # 5 per second
        )
        
        # Wait 1 second (should refill 5 tokens)
        time.sleep(1.0)
        
        # Try to consume 5 tokens (should succeed)
        allowed, retry_after, remaining = await storage.check_and_consume(
            key=key, max_tokens=10, refill_rate=5.0, cost=5
        )
        
        assert allowed is True
        assert retry_after == 0.0
    
    async def test_bucket_cap(self, storage):
        """Test that bucket doesn't exceed max_tokens."""
        key = "test:cap"
        
        # Consume 5 tokens
        await storage.check_and_consume(
            key=key, max_tokens=10, refill_rate=10.0, cost=5
        )
        
        # Wait 5 seconds (would refill 50 tokens, but capped at 10)
        time.sleep(5.0)
        
        # Try to consume 10 tokens (should succeed)
        allowed, retry_after, remaining = await storage.check_and_consume(
            key=key, max_tokens=10, refill_rate=10.0, cost=10
        )
        
        assert allowed is True
        assert remaining == 0  # Had exactly 10, consumed 10
    
    async def test_get_remaining(self, storage):
        """Test get_remaining method."""
        key = "test:remaining"
        
        # Consume 3 tokens
        await storage.check_and_consume(
            key=key, max_tokens=10, refill_rate=1.0, cost=3
        )
        
        # Get remaining
        remaining = await storage.get_remaining(key, max_tokens=10)
        assert remaining == 7  # 10 - 3 = 7
    
    async def test_reset(self, storage):
        """Test reset method."""
        key = "test:reset"
        
        # Consume all tokens
        await storage.check_and_consume(
            key=key, max_tokens=10, refill_rate=1.0, cost=10
        )
        
        # Reset
        await storage.reset(key)
        
        # Should be able to consume again
        allowed, _, remaining = await storage.check_and_consume(
            key=key, max_tokens=10, refill_rate=1.0, cost=5
        )
        
        assert allowed is True
        assert remaining == 5  # Fresh bucket
```

**Verification:**

- [ ] File created
- [ ] Tests with actual Redis container
- [ ] Tests initial state (full bucket)
- [ ] Tests token consumption
- [ ] Tests insufficient tokens (denial)
- [ ] Tests token refill over time
- [ ] Tests bucket capping (max_tokens)
- [ ] Tests get_remaining method
- [ ] Tests reset method
- [ ] All tests pass

**Deliverables:**

- `tests/unit/services/rate_limiting/test_redis_storage.py`

#### Step 3.3: Integration Tests - Rate Limiter Service

**Description:** Test RateLimiterService with real algorithm + storage.

**Actions:**

```python
# tests/integration/test_rate_limiter_service.py

import pytest
from src.rate_limiting.service import RateLimiterService
from src.rate_limiting.algorithms.token_bucket import TokenBucketAlgorithm
from src.rate_limiting.storage.redis_storage import RedisRateLimitStorage
from src.rate_limiting.config import RateLimitConfig

class TestRateLimiterServiceIntegration:
    """Integration tests for RateLimiterService.
    
    Tests full service with real algorithm + Redis storage.
    """
    
    @pytest.fixture
    async def service(self, test_redis):
        """Create service with real dependencies."""
        storage = RedisRateLimitStorage(test_redis)
        algorithm = TokenBucketAlgorithm()
        return RateLimiterService(algorithm, storage)
    
    async def test_auth_login_rate_limit(self, service):
        """Test rate limiting for auth.login endpoint."""
        identifier = "ip:192.168.1.1"
        
        # Should allow up to 20 requests (configured limit)
        for i in range(20):
            allowed, retry_after, rule = await service.is_allowed(
                endpoint="auth.login",
                identifier=identifier
            )
            assert allowed is True, f"Request {i+1} should be allowed"
            assert retry_after == 0.0
            assert rule is not None
        
        # 21st request should be denied
        allowed, retry_after, rule = await service.is_allowed(
            endpoint="auth.login",
            identifier=identifier
        )
        assert allowed is False
        assert retry_after > 0
    
    async def test_different_identifiers_independent(self, service):
        """Test that different identifiers have independent limits."""
        user1 = "ip:192.168.1.1"
        user2 = "ip:192.168.1.2"
        
        # Exhaust user1's limit
        for _ in range(20):
            await service.is_allowed("auth.login", user1)
        
        # User1 should be denied
        allowed1, _, _ = await service.is_allowed("auth.login", user1)
        assert allowed1 is False
        
        # User2 should still be allowed
        allowed2, _, _ = await service.is_allowed("auth.login", user2)
        assert allowed2 is True
    
    async def test_no_rate_limit_configured(self, service):
        """Test endpoint with no rate limit configured."""
        allowed, retry_after, rule = await service.is_allowed(
            endpoint="unknown.endpoint",
            identifier="user:123"
        )
        
        # Should allow (no limit configured)
        assert allowed is True
        assert retry_after == 0.0
        assert rule is None
    
    async def test_key_building(self, service):
        """Test that rate limit keys are scoped correctly."""
        # Two different endpoints, same identifier
        # Should have independent limits
        
        identifier = "user:123"
        
        # Exhaust limit for providers.list
        for _ in range(100):
            await service.is_allowed("providers.list", identifier)
        
        # providers.list should be denied
        allowed1, _, _ = await service.is_allowed("providers.list", identifier)
        assert allowed1 is False
        
        # providers.accounts should still be allowed (different endpoint)
        allowed2, _, _ = await service.is_allowed("providers.accounts", identifier)
        assert allowed2 is True
```

**Verification:**

- [ ] File created
- [ ] Tests full service flow (config → algorithm → storage)
- [ ] Tests actual rate limits from configuration
- [ ] Tests independent identifiers
- [ ] Tests independent endpoints
- [ ] Tests unconfigured endpoints (allow by default)
- [ ] Tests key scoping
- [ ] All tests pass

**Deliverables:**

- `tests/integration/test_rate_limiter_service.py`

#### Step 3.4: API Tests - Middleware Integration

**Description:** Test rate limiting via HTTP requests (FastAPI TestClient).

**Actions:**

```python
# tests/api/test_rate_limiting_api.py

import pytest
from fastapi.testclient import TestClient

class TestRateLimitingAPI:
    """API tests for rate limiting middleware.
    
    Tests via actual HTTP requests to verify middleware behavior.
    """
    
    def test_auth_login_rate_limit_http(self, client: TestClient):
        """Test rate limiting on /auth/login endpoint."""
        # Make 20 requests (should all succeed)
        for i in range(20):
            response = client.post(
                "/api/v1/auth/login",
                json={"email": "test@example.com", "password": "wrong"}
            )
            # Login fails (wrong password) but not rate limited
            assert response.status_code in [200, 401], f"Request {i+1} not rate limited"
        
        # 21st request should be rate limited
        response = client.post(
            "/api/v1/auth/login",
            json={"email": "test@example.com", "password": "wrong"}
        )
        assert response.status_code == 429
        assert "retry_after" in response.json()
        assert "Retry-After" in response.headers
    
    def test_rate_limit_headers_present(self, client: TestClient):
        """Test that X-RateLimit-* headers are added."""
        response = client.post(
            "/api/v1/auth/login",
            json={"email": "test@example.com", "password": "wrong"}
        )
        
        assert "X-RateLimit-Limit" in response.headers
        assert "X-RateLimit-Remaining" in response.headers
        assert "X-RateLimit-Reset" in response.headers
    
    def test_rate_limit_429_response_format(self, client: TestClient):
        """Test HTTP 429 response format."""
        # Exhaust limit
        for _ in range(20):
            client.post("/api/v1/auth/login", json={"email": "test@example.com", "password": "x"})
        
        # Get rate limited response
        response = client.post("/api/v1/auth/login", json={"email": "test@example.com", "password": "x"})
        
        assert response.status_code == 429
        data = response.json()
        assert "error" in data
        assert "message" in data
        assert "retry_after" in data
        assert data["retry_after"] > 0
    
    def test_different_endpoints_independent(self, client: TestClient):
        """Test that rate limits are independent per endpoint."""
        # Exhaust /auth/login limit
        for _ in range(20):
            client.post("/api/v1/auth/login", json={"email": "test@example.com", "password": "x"})
        
        # /auth/login should be rate limited
        response1 = client.post("/api/v1/auth/login", json={"email": "test@example.com", "password": "x"})
        assert response1.status_code == 429
        
        # /auth/register should NOT be rate limited (different endpoint)
        response2 = client.post(
            "/api/v1/auth/register",
            json={"email": "new@example.com", "password": "Password123!", "full_name": "Test"}
        )
        assert response2.status_code != 429  # Not rate limited
```

**Verification:**

- [ ] File created
- [ ] Tests via HTTP requests (TestClient)
- [ ] Tests 429 response on rate limit
- [ ] Tests Retry-After header
- [ ] Tests X-RateLimit-* headers
- [ ] Tests response body format
- [ ] Tests independent endpoints
- [ ] All tests pass

**Deliverables:**

- `tests/api/test_rate_limiting_api.py`

#### Step 3.5: Smoke Tests - End-to-End Scenarios

**Description:** Create smoke tests for critical rate limiting scenarios.

**Actions:**

```python
# tests/smoke/test_rate_limiting_smoke.py

import pytest
import time
from fastapi.testclient import TestClient

class TestRateLimitingSmoke:
    """Smoke tests for rate limiting - critical user journeys."""
    
    def test_brute_force_protection(self, client: TestClient):
        """Test that brute force attacks are blocked."""
        # Attempt 25 login requests (limit is 20)
        for i in range(25):
            response = client.post(
                "/api/v1/auth/login",
                json={"email": "victim@example.com", "password": f"attempt{i}"}
            )
            
            if i < 20:
                # First 20 should reach endpoint (even if login fails)
                assert response.status_code in [200, 401]
            else:
                # After 20, should be rate limited
                assert response.status_code == 429
    
    def test_burst_handling_for_legitimate_users(self, client: TestClient, auth_headers):
        """Test that legitimate burst traffic is allowed."""
        # Authenticated user refreshing multiple accounts at once
        # Should be able to make 100 requests in quick succession
        
        for i in range(100):
            response = client.get(
                "/api/v1/providers/accounts",
                headers=auth_headers
            )
            assert response.status_code == 200, f"Request {i+1} should be allowed"
        
        # 101st request should be rate limited
        response = client.get("/api/v1/providers/accounts", headers=auth_headers)
        assert response.status_code == 429
    
    def test_rate_limit_recovery_after_wait(self, client: TestClient):
        """Test that rate limit recovers after waiting."""
        # Exhaust limit
        for _ in range(20):
            client.post("/api/v1/auth/login", json={"email": "test@example.com", "password": "x"})
        
        # Should be rate limited
        response1 = client.post("/api/v1/auth/login", json={"email": "test@example.com", "password": "x"})
        assert response1.status_code == 429
        retry_after = response1.json()["retry_after"]
        
        # Wait for recovery
        time.sleep(retry_after + 1)
        
        # Should be allowed again
        response2 = client.post("/api/v1/auth/login", json={"email": "test@example.com", "password": "x"})
        assert response2.status_code != 429
```

**Verification:**

- [ ] File created
- [ ] Tests brute force protection
- [ ] Tests burst handling for legitimate users
- [ ] Tests rate limit recovery after waiting
- [ ] All tests pass
- [ ] Critical user journeys covered

**Deliverables:**

- `tests/smoke/test_rate_limiting_smoke.py`

### Phase 4: Monitoring, Audit & Observability

**Objective:** Add comprehensive logging, audit trails, and monitoring capabilities.

**Status:** ⏳ Pending

#### Step 4.1: Audit Logging for Rate Limit Violations

**Description:** Log all rate limit violations to database for security analysis.

**Actions:**

```python
# src/rate_limiting/models.py

from datetime import datetime, UTC
from typing import Optional
from sqlmodel import Field, SQLModel

class RateLimitAuditLog(SQLModel, table=True):
    """Audit log for rate limiting violations.
    
    Tracks all rate limit violations for security analysis and
    detection of attack patterns.
    """
    __tablename__ = "rate_limit_audit_logs"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    
    # Request identification
    endpoint: str = Field(index=True)
    identifier: str = Field(index=True)  # IP or user_id
    scope: str  # ip, user, endpoint, provider_user
    
    # Rate limit details
    limit_type: str  # token_bucket, sliding_window, etc.
    max_tokens: int
    refill_rate: float
    retry_after: float
    
    # Request metadata
    path: str
    method: str
    user_agent: Optional[str] = None
    client_ip: str
    
    # Timestamps
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    
    class Config:
        from_attributes = True
```

**Verification:**

- [ ] Model created
- [ ] Database migration created
- [ ] Audit logging integrated in middleware
- [ ] Queries work correctly
- [ ] Indexed for performance

**Deliverables:**

- `src/rate_limiting/models.py`
- Alembic migration for audit log table
- Updated middleware to log violations

#### Step 4.2: Metrics and Monitoring

**Description:** Add metrics for rate limiting performance and behavior.

**Actions:**

- Add logging for:
  - Rate limit hits (denied requests)
  - Rate limit misses (allowed requests)
  - Storage latency (Redis response time)
  - Algorithm execution time
  - Fail-open events (when storage unavailable)

**Verification:**

- [ ] Structured logging added
- [ ] Log levels appropriate
- [ ] No PII in logs
- [ ] Metrics easily parseable

**Deliverables:**

- Enhanced logging in all components

### Phase 5: Documentation & Deployment

**Objective:** Complete documentation and prepare for production deployment.

**Status:** ⏳ Pending

#### Step 5.1: Update Environment Configuration

**Description:** Add rate limiting configuration to all environment files.

**Actions:**

```bash
# env/.env.dev (only infrastructure config)
REDIS_URL=redis://dashtam-dev-redis:6379

# env/.env.test
REDIS_URL=redis://dashtam-test-redis:6379

# env/.env.prod.example
REDIS_URL=redis://production-redis:6379
```

**Verification:**

- [ ] All .env.example files updated
- [ ] NO rate limit rules in .env (only in rate_limit_config.py)
- [ ] Only infrastructure configuration in .env
- [ ] Documentation explains configuration SSOT

**Deliverables:**

- Updated environment files
- `env/README.md` with rate limiting section

#### Step 5.2: API Documentation

**Description:** Document rate limiting behavior in API docs.

**Actions:**

Create `docs/api-flows/rate-limiting.md` explaining:

- Rate limit headers
- HTTP 429 responses
- Retry-After behavior
- Per-endpoint limits
- Best practices for clients

**Verification:**

- [ ] Documentation complete
- [ ] Examples provided
- [ ] Lint-clean markdown
- [ ] Follows api-flow-template.md

**Deliverables:**

- `docs/api-flows/rate-limiting.md`

#### Step 5.3: Update WARP.md

**Description:** Document rate limiting as completed feature in WARP.md.

**Actions:**

Add to WARP.md Current Status:

```markdown
- ✅ **P1 RATE LIMITING COMPLETE** (October 2025)
  - ✅ Token Bucket algorithm with Redis storage
  - ✅ SOLID-compliant pluggable architecture
  - ✅ FastAPI middleware integration
  - ✅ Comprehensive test coverage (unit, integration, API, smoke)
  - ✅ Per-endpoint configuration (single source of truth)
  - ✅ Audit logging for security analysis
  - ✅ <5ms p95 latency overhead
```

**Verification:**

- [ ] WARP.md updated
- [ ] Current status reflects completion
- [ ] Links to documentation added

**Deliverables:**

- Updated `WARP.md`

#### Step 5.4: Deployment Checklist

**Description:** Create pre-deployment checklist.

**Actions:**

**Pre-Deployment Verification:**

- [ ] All tests passing (295+ tests)
- [ ] Code coverage ≥85% overall
- [ ] Rate limiting coverage ≥95%
- [ ] Lint clean (`make lint`)
- [ ] Markdown lint clean (`make lint-md`)
- [ ] Redis connection verified in all environments
- [ ] Configuration reviewed and approved
- [ ] Rate limits match security requirements
- [ ] Audit logging verified
- [ ] Performance benchmarks met (<5ms p95)
- [ ] Documentation complete
- [ ] WARP.md updated
- [ ] PR approved and merged

**Deployment Steps:**

1. Merge to development branch
2. Deploy to test environment
3. Run smoke tests in test environment
4. Monitor for 24 hours
5. Deploy to production
6. Monitor rate limit metrics
7. Verify audit logs collecting correctly

**Rollback Plan:**

If issues detected:

```bash
# Quick rollback (remove middleware)
# Edit src/main.py: Comment out middleware registration
# Restart application

# Complete rollback (revert PR)
git revert <commit-hash>
git push origin development
```

**Verification:**

- [ ] Checklist complete
- [ ] All items verified
- [ ] Ready for production

**Deliverables:**

- Deployment checklist
- Rollback procedures documented

## Testing and Verification

### Testing Strategy

**Test Levels:**

- **Unit tests (70%):**
  - Algorithm logic (TokenBucketAlgorithm)
  - Storage operations (RedisRateLimitStorage)
  - Service orchestration (RateLimiterService)
  - Configuration loading (RateLimitConfig)
  - Target: 100% coverage of rate limiting code

- **Integration tests (20%):**
  - Full service with real Redis
  - Configuration → algorithm → storage flow
  - Multiple endpoints and identifiers
  - Target: All critical paths covered

- **API tests (10%):**
  - HTTP 429 responses
  - Rate limit headers
  - Middleware behavior
  - Target: All rate-limited endpoints tested

- **Smoke tests:**
  - Brute force protection
  - Burst handling for legitimate users
  - Rate limit recovery
  - Target: All critical user journeys

### Verification Checklist

**Pre-Implementation:**

- [x] Research complete (rate-limiting-research.md)
- [x] Architecture reviewed and approved
- [x] SOLID principles mapped to components
- [ ] Configuration SSOT designed
- [ ] All abstractions defined

**During Implementation:**

- [ ] Each phase tested before proceeding
- [ ] Unit tests written alongside code
- [ ] Integration tests verify full flow
- [ ] Code reviewed for SOLID compliance
- [ ] Documentation updated continuously

**Post-Implementation:**

- [ ] All tests passing (100% pass rate)
- [ ] Coverage ≥85% overall (≥95% rate limiting)
- [ ] Performance benchmarks met (<5ms p95)
- [ ] No regressions in existing tests
- [ ] Documentation complete and lint-clean
- [ ] WARP.md updated
- [ ] Deployment checklist verified

### Performance Benchmarks

| Metric | Baseline | Target | Actual |
|--------|----------|--------|--------|
| p50 latency overhead | 0ms | <2ms | [TBD] |
| p95 latency overhead | 0ms | <5ms | [TBD] |
| p99 latency overhead | 0ms | <10ms | [TBD] |
| Redis operations/sec | N/A | 10,000+ | [TBD] |
| False positive rate | 100% | <0.1% | [TBD] |
| Brute force prevention | 0% | 99.9% | [TBD] |

## Rollback Plan

### When to Rollback

Rollback should be triggered if:

- **Critical failure:** Rate limiting blocks all legitimate users
- **Performance degradation:** >10ms p95 latency added
- **Redis failure:** Rate limiting causes cascading failures
- **False positives:** >1% legitimate users blocked
- **Security bypass:** Rate limits can be circumvented

### Rollback Procedure

#### Quick Rollback (Emergency - 5 minutes)

```bash
# 1. SSH into production server
ssh production-server

# 2. Edit main.py to disable middleware
vi src/main.py

# Comment out these lines:
# @app.on_event("startup")
# async def startup_rate_limiter():
#     rate_limiter = await get_rate_limiter_service()
#     app.add_middleware(RateLimitMiddleware, rate_limiter=rate_limiter)

# 3. Restart application
docker compose -f compose/docker-compose.prod.yml restart app

# 4. Verify rate limiting disabled
curl -I https://api.dashtam.com/health
# Should NOT have X-RateLimit-* headers
```

**Expected Time:** 5 minutes

#### Complete Rollback (Revert PR)

#### Step 1: Revert Git Commit

```bash
# Identify commit hash
git log --oneline | grep "rate limiting"

# Revert commit
git revert <commit-hash>
git push origin development

# Verify revert
git log --oneline
```

#### Step 2: Redeploy

```bash
# Pull reverted code
git pull origin development

# Rebuild and restart
docker compose -f compose/docker-compose.prod.yml up -d --build

# Verify services healthy
docker compose -f compose/docker-compose.prod.yml ps
```

#### Step 3: Clean Up Redis

```bash
# Clear rate limit keys (optional)
docker compose -f compose/docker-compose.prod.yml exec redis redis-cli
> KEYS ratelimit:*
> DEL <keys>  # Or let them expire naturally
```

**Expected Time:** 15 minutes

### Post-Rollback Actions

- [ ] Notify team in Slack/communication channel
- [ ] Document failure reasons in incident report
- [ ] Create GitHub issue with detailed error logs
- [ ] Plan corrective actions and timeline
- [ ] Update implementation guide with lessons learned
- [ ] Schedule post-mortem meeting

## Risk Assessment

### High-Risk Items

#### Risk 1: False Positives Blocking Legitimate Users

**Probability:** Medium

**Impact:** High (degraded user experience)

**Description:** Legitimate users with burst traffic patterns (e.g., refreshing multiple accounts) get rate limited incorrectly.

**Mitigation:**

- Generous limits for authenticated users (100 req/min)
- Token bucket algorithm (best burst handling)
- Comprehensive testing with real usage patterns
- Gradual rollout with monitoring

**Contingency:**

- Quick rollback procedure (disable middleware)
- Adjust limits in `rate_limit_config.py` and redeploy
- Temporarily disable rate limiting for specific users (admin override)

#### Risk 2: Redis Failure Causes Service Unavailability

**Probability:** Low

**Impact:** Critical (service down)

**Description:** If Redis becomes unavailable and rate limiting doesn't fail open correctly, entire API could become unavailable.

**Mitigation:**

- Fail-open strategy implemented (algorithm + storage)
- Comprehensive error handling and logging
- Redis health monitoring and alerting
- Redundant Redis instance (future enhancement)

**Contingency:**

- Rate limiting fails open automatically (allows requests)
- Monitor for fail-open events in logs
- Quick rollback if failing open causes issues
- Emergency Redis restart procedure

#### Risk 3: Performance Degradation (>5ms Latency)

**Probability:** Low

**Impact:** Medium (user experience)

**Description:** Rate limiting adds more latency than target (<5ms p95).

**Mitigation:**

- Redis Lua scripts (atomic, fast)
- Connection pooling (already configured)
- Performance testing before deployment
- Benchmarking against target metrics

**Contingency:**

- Optimize Lua script (reduce operations)
- Adjust Redis connection pool settings
- Consider caching rate limit checks (if safe)
- Disable rate limiting for specific endpoints

### Medium-Risk Items

#### Risk 4: Configuration Errors

**Probability:** Medium

**Impact:** Medium

**Description:** Incorrect rate limits in configuration (too strict or too lenient).

**Mitigation:**

- Single source of truth (rate_limit_config.py)
- Type-safe Pydantic validation
- Comprehensive testing of all configured limits
- Code review of configuration changes

**Contingency:**

- Update configuration and redeploy (5 minutes)
- No code changes needed (configuration-driven)

#### Risk 5: Insufficient Audit Logging

**Probability:** Low

**Impact:** Medium

**Description:** Rate limit violations not properly logged for security analysis.

**Mitigation:**

- Comprehensive audit log model
- Database persistence (not just logs)
- Indexed for query performance
- Testing of audit log insertion

**Contingency:**

- Enable debug logging temporarily
- Manual log analysis
- Backfill audit logs from Redis keys

### Risk Matrix

| Risk | Probability | Impact | Mitigation | Status |
|------|-------------|--------|------------|--------|
| False positives | Medium | High | Generous limits + burst handling | ⏳ |
| Redis failure | Low | Critical | Fail-open strategy | ✅ |
| Performance | Low | Medium | Lua scripts + benchmarking | ⏳ |
| Config errors | Medium | Medium | Type-safe SSOT + validation | ✅ |
| Audit gaps | Low | Medium | Database persistence | ⏳ |

## Success Criteria

### Quantitative Metrics

- **Test Coverage:** ≥85% overall, ≥95% for rate limiting code
- **Performance:** <5ms p95 latency overhead (target: 2-3ms)
- **Reliability:** 99.9% uptime for rate limiting service
- **Security:** Zero successful brute force attacks
- **Compliance:** Zero Charles Schwab API quota violations
- **User Experience:** <0.1% false positive rate

### Qualitative Metrics

- **Code Quality:** 100% SOLID principles adherence (explicitly mapped)
- **Maintainability:** Easy to add new algorithms/storage backends
- **Extensibility:** Pluggable architecture demonstrated
- **Observability:** Comprehensive audit logs and metrics
- **Documentation:** Complete, lint-clean, follows templates

### Acceptance Criteria

- [ ] All 5 phases complete
- [ ] All tests passing (unit, integration, API, smoke)
- [ ] Code coverage targets met (≥85% overall, ≥95% rate limiting)
- [ ] Performance benchmarks met (<5ms p95 latency)
- [ ] SOLID principles explicitly documented for each component
- [ ] Configuration SSOT working (no duplication in .env)
- [ ] Fail-open strategy tested and verified
- [ ] Audit logging working correctly
- [ ] Documentation complete and approved
- [ ] Deployed to test environment successfully
- [ ] Smoke tests pass in test environment
- [ ] Ready for production deployment

### SOLID Compliance Verification

Every component must explicitly demonstrate SOLID adherence:

| Component | S | O | L | I | D |
|-----------|---|---|---|---|---|
| RateLimitConfig | ✅ | ✅ | N/A | ✅ | N/A |
| RateLimitAlgorithm (base) | ✅ | ✅ | ✅ | ✅ | ✅ |
| TokenBucketAlgorithm | ✅ | ✅ | ✅ | ✅ | ✅ |
| RateLimitStorage (base) | ✅ | ✅ | ✅ | ✅ | ✅ |
| RedisRateLimitStorage | ✅ | ✅ | ✅ | ✅ | ✅ |
| RateLimiterService | ✅ | ✅ | ✅ | ✅ | ✅ |
| RateLimitMiddleware | ✅ | ✅ | N/A | ✅ | ✅ |

Legend:

- ✅ = Fully compliant
- N/A = Not applicable (e.g., no inheritance needed)

## Deliverables

### Code Deliverables

- [ ] `src/rate_limiting/config.py` - Configuration SSOT
- [ ] `src/rate_limiting/algorithms/base.py` - Algorithm abstraction
- [ ] `src/rate_limiting/algorithms/token_bucket.py` - Token bucket implementation
- [ ] `src/rate_limiting/storage/base.py` - Storage abstraction
- [ ] `src/rate_limiting/storage/redis_storage.py` - Redis implementation
- [ ] `src/rate_limiting/service.py` - Orchestrating service
- [ ] `src/rate_limiting/factory.py` - Dependency injection factory
- [ ] `src/rate_limiting/middleware.py` - FastAPI middleware
- [ ] `src/rate_limiting/models.py` - Audit log model
- [ ] Updated `src/main.py` - Middleware registration

### Test Deliverables

- [ ] `tests/unit/services/rate_limiting/test_token_bucket_algorithm.py` - Algorithm tests
- [ ] `tests/unit/services/rate_limiting/test_redis_storage.py` - Storage tests
- [ ] `tests/integration/test_rate_limiter_service.py` - Service integration tests
- [ ] `tests/api/test_rate_limiting_api.py` - API endpoint tests
- [ ] `tests/smoke/test_rate_limiting_smoke.py` - End-to-end smoke tests

### Documentation Deliverables

- [ ] `docs/research/rate-limiting-research.md` - Research document (already exists)
- [ ] `docs/development/implementation/rate-limiting-implementation.md` - This document
- [ ] `docs/api-flows/rate-limiting.md` - API documentation for clients
- [ ] `env/README.md` - Updated with rate limiting section
- [ ] Updated `WARP.md` - Feature completion status

### Infrastructure Deliverables

- [ ] Updated environment files (.env.dev, .env.test, .env.prod.example)
- [ ] Alembic migration for rate_limit_audit_logs table
- [ ] Deployment checklist and rollback procedures

## Next Steps

### Immediate Actions (Post-Implementation)

1. **Performance Monitoring:** Monitor p95 latency for 48 hours
2. **Audit Log Analysis:** Review rate limit violations for patterns
3. **User Feedback:** Collect feedback on false positives
4. **Documentation Review:** Ensure all docs up-to-date

### Follow-Up Tasks

1. **Admin Dashboard** (P2): Web UI for viewing rate limit status
2. **Dynamic Limits** (P2): Adjust limits based on system load
3. **Allowlist/Bypass** (P2): Admin override for specific users
4. **Additional Storage Backends** (P3): PostgreSQL implementation
5. **Additional Algorithms** (P3): Sliding window, fixed window

### Future Enhancements

1. **Standalone Package:** Extract to reusable PyPI package
2. **Multi-Region Support:** Distributed rate limiting across regions
3. **Machine Learning:** Anomaly detection for attack patterns
4. **Client SDK:** Rate limit client library with automatic retry

## References

### Internal Documentation

- [Rate Limiting Research](../../research/rate-limiting-research.md) - Comprehensive algorithm comparison
- [Testing Guide](../guides/testing-guide.md) - Testing patterns and conventions
- Project Rules: See WARP.md in project root (not in MkDocs site)

### External Resources

- [Token Bucket Algorithm - Wikipedia](https://en.wikipedia.org/wiki/Token_bucket)
- [Redis Lua Scripting](https://redis.io/docs/manual/programmability/eval-intro/)
- [FastAPI Middleware](https://fastapi.tiangolo.com/advanced/middleware/)
- [SOLID Principles - Uncle Bob](https://blog.cleancoder.com/uncle-bob/2020/10/18/Solid-Relevance.html)
- [AWS API Gateway Rate Limiting](https://docs.aws.amazon.com/apigateway/latest/developerguide/api-gateway-request-throttling.html)
- [GitHub API Rate Limiting](https://docs.github.com/en/rest/overview/resources-in-the-rest-api#rate-limiting)
- [Stripe API Rate Limiting](https://stripe.com/docs/rate-limits)

### Compliance References

- [PCI-DSS 8.1.6](https://www.pcisecuritystandards.org/) - Limit repeated access attempts
- [OWASP A07:2021](https://owasp.org/Top10/A07_2021-Identification_and_Authentication_Failures/) - Authentication failures
- [SOC 2 Availability](https://www.aicpa.org/interestareas/frc/assuranceadvisoryservices/socforserviceorganizations) - DoS protection

### Related Issues

- Issue #[TBD]: Rate limiting implementation tracking
- PR #[TBD]: Rate limiting implementation PR

---

## Document Information

**Template:** [implementation-template.md](../../templates/implementation-template.md)
**Created:** 2025-10-25
**Last Updated:** 2025-10-25
