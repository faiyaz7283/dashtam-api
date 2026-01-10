# Cache Usage Guide

Practical patterns for using the cache infrastructure in Dashtam.

---

## Quick Start

### Getting the Cache

```python
# In application layer (direct use)
from src.core.container import get_cache

cache = get_cache()
result = await cache.set("key", "value", ttl=3600)

# In presentation layer (FastAPI dependency)
from fastapi import Depends
from src.domain.protocols.cache_protocol import CacheProtocol
from src.core.container import get_cache

@router.get("/data")
async def get_data(cache: CacheProtocol = Depends(get_cache)):
    result = await cache.get("key")
    ...
```

### Basic Operations

```python
from src.core.result import Success, Failure

# Set a value with TTL
result = await cache.set("user:123", "John Doe", ttl=3600)
if isinstance(result, Success):
    print("Cached successfully")

# Get a value
result = await cache.get("user:123")
match result:
    case Success(value=val) if val is not None:
        print(f"Found: {val}")
    case Success(value=None):
        print("Cache miss")
    case Failure(error=err):
        print(f"Error: {err.message}")

# Delete a value
result = await cache.delete("user:123")
if isinstance(result, Success) and result.value:
    print("Deleted")
```

---

## Common Patterns

### Cache-Aside Pattern

The most common pattern - check cache first, fall back to database:

```python
async def get_user(user_id: str) -> User | None:
    cache_key = f"user:{user_id}"
    
    # Try cache first
    result = await cache.get_json(cache_key)
    
    match result:
        case Success(value=data) if data is not None:
            # Cache hit - return cached data
            return User.from_dict(data)
        case _:
            # Cache miss or error - fetch from database
            user = await user_repo.find_by_id(user_id)
            if user:
                # Store in cache for next time
                await cache.set_json(
                    cache_key,
                    user.to_dict(),
                    ttl=3600  # 1 hour
                )
            return user
```

### Batch Operations

Use `get_many` and `set_many` for efficient bulk operations:

```python
# Fetch multiple users at once
keys = [f"user:{uid}" for uid in user_ids]
result = await cache.get_many(keys)

if isinstance(result, Success):
    cached_users = {}
    missing_ids = []
    
    for key, value in result.value.items():
        user_id = key.split(":")[1]
        if value is not None:
            cached_users[user_id] = json.loads(value)
        else:
            missing_ids.append(user_id)
    
    # Fetch missing from database
    if missing_ids:
        db_users = await user_repo.find_by_ids(missing_ids)
        
        # Cache the fetched users
        to_cache = {
            f"user:{u.id}": json.dumps(u.to_dict())
            for u in db_users
        }
        await cache.set_many(to_cache, ttl=3600)

# Store multiple users at once
mapping = {
    f"user:{user.id}": json.dumps(user.to_dict())
    for user in users
}
await cache.set_many(mapping, ttl=3600)
```

### Rate Limiting Counter

Use atomic increment for rate limiting:

```python
async def check_rate_limit(user_id: str, endpoint: str) -> bool:
    key = f"rate_limit:{user_id}:{endpoint}"
    
    result = await cache.increment(key)
    
    match result:
        case Success(value=count):
            if count == 1:
                # First request - set expiration window
                await cache.expire(key, 60)  # 1 minute window
            
            if count > 100:  # 100 requests per minute
                return False  # Rate limited
            return True
        case Failure(_):
            # Fail open - allow request if cache fails
            return True
```

### Session Caching

Use the specialized `RedisSessionCache` for session management:

```python
from src.infrastructure.cache.session_cache import RedisSessionCache
from src.core.container import get_cache

session_cache = RedisSessionCache(cache=get_cache())

# Store session
await session_cache.set(session_data, ttl_seconds=1800)

# Get session
session = await session_cache.get(session_id)

# Delete session
await session_cache.delete(session_id)

# Get all sessions for a user
session_ids = await session_cache.get_user_session_ids(user_id)

# Delete all user sessions
deleted_count = await session_cache.delete_all_for_user(user_id)
```

### Pattern-Based Deletion

Delete multiple related keys at once:

```python
# Delete all sessions for a user
result = await cache.delete_pattern(f"session:user123:*")
if isinstance(result, Success):
    print(f"Deleted {result.value} sessions")

# Invalidate all cached data for an entity
await cache.delete_pattern(f"user:{user_id}:*")
```

---

## Key Naming Conventions

Use hierarchical, namespace-prefixed keys:

```python
# Pattern: {namespace}:{entity_type}:{id}[:sub_resource]

# User data
USER_KEY = "user:{user_id}"
USER_PROFILE_KEY = "user:{user_id}:profile"
USER_SETTINGS_KEY = "user:{user_id}:settings"

# Sessions
SESSION_KEY = "session:{session_id}"
USER_SESSIONS_KEY = "user:{user_id}:sessions"

# Rate limiting
RATE_LIMIT_KEY = "rate_limit:{user_id}:{endpoint}"

# Provider tokens
PROVIDER_TOKEN_KEY = "provider:token:{provider}:{user_id}"

# Authorization
AUTHZ_PERMISSIONS_KEY = "authz:{user_id}:permissions"
```

---

## TTL Strategy

Choose TTLs based on data characteristics:

```python
# Recommended TTL values (in seconds)
TTL_SESSION = 1800           # 30 minutes - security sensitive
TTL_USER = 3600              # 1 hour - changes occasionally
TTL_PROVIDER_TOKEN = 3300    # 55 minutes - refresh before expiry
TTL_RATE_LIMIT = 60          # 1 minute - sliding window
TTL_STATIC_DATA = 86400      # 24 hours - rarely changes
TTL_PERMISSIONS = 300        # 5 minutes - balance freshness/performance
```

---

## Error Handling (Fail-Open)

Cache operations should **never break core functionality**:

```python
async def get_user_with_fallback(user_id: str) -> User | None:
    cache_key = f"user:{user_id}"
    
    # Try cache - but don't fail if cache is down
    cache_result = await cache.get_json(cache_key)
    
    if isinstance(cache_result, Success) and cache_result.value is not None:
        return User.from_dict(cache_result.value)
    
    # Cache miss OR cache error - fall back to database
    # This is the "fail-open" pattern
    user = await user_repo.find_by_id(user_id)
    
    if user:
        # Try to cache, but don't fail if it doesn't work
        await cache.set_json(cache_key, user.to_dict(), ttl=3600)
    
    return user
```

---

## Testing

### Integration Tests

Cache tests require a real Redis instance (no mocking):

```python
import pytest
from src.core.result import Success

@pytest.mark.integration
class TestCacheOperations:
    @pytest.mark.asyncio
    async def test_set_and_get(self, cache_adapter):
        # Set value
        result = await cache_adapter.set("test:key", "value", ttl=60)
        assert isinstance(result, Success)
        
        # Get value
        result = await cache_adapter.get("test:key")
        assert isinstance(result, Success)
        assert result.value == "value"
    
    @pytest.mark.asyncio
    async def test_batch_operations(self, cache_adapter):
        # Set multiple
        mapping = {"key1": "val1", "key2": "val2"}
        result = await cache_adapter.set_many(mapping, ttl=60)
        assert isinstance(result, Success)
        
        # Get multiple
        result = await cache_adapter.get_many(["key1", "key2", "missing"])
        assert isinstance(result, Success)
        assert result.value["key1"] == "val1"
        assert result.value["missing"] is None
```

### Using Test Fixtures

```python
@pytest.mark.asyncio
async def test_session_cache(session_cache):
    """Test uses session_cache fixture from conftest.py."""
    from uuid import uuid4
    from datetime import datetime, UTC
    
    session_data = SessionData(
        id=uuid4(),
        user_id=uuid4(),
        created_at=datetime.now(UTC),
        # ... other fields
    )
    
    await session_cache.set(session_data)
    result = await session_cache.get(session_data.id)
    
    assert result is not None
    assert result.id == session_data.id
```

---

## Health Checks

Verify cache connectivity:

```python
async def check_cache_health() -> bool:
    result = await cache.ping()
    return isinstance(result, Success) and result.value is True

# In health check endpoint
@router.get("/health")
async def health_check(cache: CacheProtocol = Depends(get_cache)):
    cache_healthy = await cache.ping()
    
    return {
        "status": "healthy" if isinstance(cache_healthy, Success) else "degraded",
        "cache": "up" if isinstance(cache_healthy, Success) else "down"
    }
```

---

## Common Mistakes to Avoid

### ❌ Don't Cache Sensitive Data Without Encryption

```python
# WRONG: Caching password or tokens in plain text
await cache.set(f"user:{user_id}:password", hashed_password)

# RIGHT: Don't cache passwords at all, or encrypt sensitive data
# Passwords should never be cached
```

### ❌ Don't Use PII in Cache Keys

```python
# WRONG: Email in key
await cache.set(f"user:john@example.com", data)

# RIGHT: Use opaque IDs
await cache.set(f"user:{user_id}", data)
```

### ❌ Don't Forget TTL for Session Data

```python
# WRONG: No TTL on security-sensitive data
await cache.set(f"session:{session_id}", data)

# RIGHT: Always use TTL
await cache.set(f"session:{session_id}", data, ttl=1800)
```

### ❌ Don't Let Cache Failures Break Your App

```python
# WRONG: Raising exception on cache failure
result = await cache.get("key")
if isinstance(result, Failure):
    raise CacheError("Cache failed!")  # App crashes

# RIGHT: Fail open - continue without cache
result = await cache.get("key")
if isinstance(result, Failure):
    logger.warning("Cache unavailable, falling back to database")
    # Continue with database lookup
```

---

## Cache Application in Dashtam

This section documents where caching is currently applied and where it should be added.

### Currently Cached ✅

#### 1. Session Management

**Location**: `src/infrastructure/cache/session_cache.py`
**Used by**: `CreateSessionHandler`, `GetSessionHandler`, `RevokeSessionHandler`

```python
# Write-through caching with database as source of truth
await session_cache.set(session_data, ttl_seconds=1800)
session = await session_cache.get(session_id)

# User→sessions index for bulk operations
session_ids = await session_cache.get_user_session_ids(user_id)
```

- TTL: 30 days (matches session expiration)
- Pattern: Write-through (cache + DB)
- Invalidation: On session revocation

#### 2. Authorization (Casbin RBAC)

**Location**: `src/infrastructure/authorization/casbin_adapter.py`
**Used by**: `require_permission()`, `require_role()` dependencies

```python
# Permission check results cached
cache_key = f"authz:{user_id}:{resource}:{action}"
await cache.set(cache_key, "1" if allowed else "0", ttl=300)

# Pattern-based invalidation on role changes
await cache.delete_pattern(f"authz:{user_id}:*")
```

- TTL: 5 minutes
- Pattern: Cache-aside with invalidation
- Invalidation: On role assignment/revocation

#### 3. OAuth State (CSRF Protection)

**Location**: `src/presentation/routers/api/v1/providers.py`
**Used by**: `initiate_connection()`, `oauth_callback()`

```python
# Store state during OAuth initiation
cache_key = f"oauth:state:{state}"
await cache.set(cache_key, f"{user_id}:{provider_slug}:{alias}", ttl=600)

# Retrieve and delete (one-time use) during callback
cached_value = await cache.get(cache_key)
await cache.delete(cache_key)
```

- TTL: 10 minutes
- Pattern: One-time use token
- Invalidation: Deleted after retrieval

#### 4. Rate Limiting (Token Bucket)

**Location**: `src/infrastructure/rate_limit/redis_storage.py`
**Used by**: Rate limit middleware

```python
# Uses Redis directly with Lua scripts for atomic operations
# Keys: "{key_base}:tokens", "{key_base}:time"
await redis.evalsha(token_bucket_sha, ...)
```

- TTL: Based on rate limit window
- Pattern: Atomic Lua scripts (not CacheProtocol)
- Policy: Fail-open (allow on Redis failure)

### Cache Optimization ✅

**Implemented**: 2025-12-25 | **Phases 1-9 Complete**

#### 1. Provider Connection Cache ✅

**Location**: `src/infrastructure/cache/provider_connection_cache.py`
**Used by**: `GetProviderConnectionHandler`

```python
# Cache-first strategy
cache_key = CacheKeys.provider_connection(connection_id)
connection = await connection_cache.get(connection_id)
if connection is None:
    connection = await connection_repo.find_by_id(connection_id)
    if connection:
        await connection_cache.set(connection)
```

- TTL: 5 minutes (300 seconds)
- Pattern: Cache-aside with population on miss
- Invalidation: Manual or on provider operations
- Performance: ~10x faster (<5ms vs ~50ms)

#### 2. Schwab API Response Cache ✅

**Location**: `src/infrastructure/providers/schwab/schwab_provider.py`
**Used by**: `fetch_accounts()` method

```python
# External API caching
cache_key = CacheKeys.schwab_accounts(user_id)
if accounts_cache:
    cached = await accounts_cache.get(cache_key)
    if cached:
        return Success(value=cached)

# Fetch from API and cache result
accounts = await self._accounts_api.get_accounts(access_token)
if accounts_cache and isinstance(accounts, Success):
    await accounts_cache.set(cache_key, accounts.value, ttl=ttl_schwab_accounts)
```

- TTL: 5 minutes (300 seconds)
- Pattern: Cache-first with API fallback
- Invalidation: Time-based expiration
- Impact: 70-90% reduction in Schwab API calls

#### 3. Account List Cache ✅

**Location**: `src/application/queries/handlers/list_accounts_handler.py`
**Used by**: `ListAccountsByUserHandler`

```python
# Cache unfiltered user account lists
if accounts_cache and filters is None:
    cache_key = CacheKeys.accounts_user(user_id)
    cached = await accounts_cache.get(cache_key)
    if cached:
        return Success(value=cached)

# Fetch from DB and cache
accounts = await self._account_repo.find_by_user_id(user_id)
if accounts_cache:
    await accounts_cache.set(cache_key, accounts, ttl=ttl_accounts_list)
```

- TTL: 5 minutes (300 seconds)
- Pattern: Cache-aside, only caches unfiltered lists
- Invalidation: Time-based expiration
- Impact: 50-70% reduction in DB queries

#### 4. Security Config Cache ✅

**Location**: `src/application/commands/handlers/refresh_access_token_handler.py`
**Used by**: `RefreshAccessTokenHandler`

```python
# Cache security config for token validation
config = await self._get_cached_security_config(user_id, accounts_cache)

# Helper method uses cache-first strategy
async def _get_cached_security_config(user_id, cache):
    global_key = CacheKeys.security_global_version()
    user_key = CacheKeys.security_user_version(user_id)
    # Try cache first, fall back to DB
```

- TTL: 1 minute (60 seconds) - security-sensitive
- Pattern: Cache-first with short TTL
- Invalidation: `SecurityConfigRepository` clears on version updates
- Impact: Reduces DB load on token refresh operations

#### 5. Cache Metrics & Observability ✅

**Location**: `src/infrastructure/cache/cache_metrics.py`

```python
metrics = CacheMetrics()
metrics.record_hit("provider")
metrics.record_miss("provider")
metrics.record_error("provider")

stats = metrics.get_stats("provider")
# Returns: hits, misses, errors, total_requests, hit_rate
```

- Thread-safe operation tracking
- Per-namespace statistics
- Hit rate calculation
- Used for performance monitoring

#### 6. Centralized Cache Keys ✅

**Location**: `src/infrastructure/cache/cache_keys.py`

```python
# All cache keys constructed through CacheKeys class
CacheKeys.provider_connection(connection_id)
CacheKeys.schwab_accounts(user_id)
CacheKeys.accounts_user(user_id)
CacheKeys.security_global_version()
CacheKeys.security_user_version(user_id)
```

- Single source of truth for cache key patterns
- Documented in `docs/architecture/cache-keys.md`
- Prevents key collisions

#### 7. Future Cache Candidates (Lower Priority)

##### Transaction Lists

- Large data sets
- Short freshness window
- Consider pagination-aware caching

##### Provider Credentials (Decrypted)

- Security concern: encrypted at rest
- If cached, needs very short TTL
- Consider memory-only caching

### Implementation Status

| Component | Status | TTL | Invalidation |
|-----------|--------|-----|---------------|
| Sessions | ✅ Implemented | 30 days | On revoke |
| Authorization | ✅ Implemented | 5 min | On role change |
| OAuth State | ✅ Implemented | 10 min | One-time use |
| Rate Limits | ✅ Implemented | Window-based | Automatic |
| Provider Connections | ✅ F6.11 (Phase 4) | 5 min | Manual |
| Schwab API | ✅ F6.11 (Phase 5) | 5 min | Time-based |
| Account Lists | ✅ F6.11 (Phase 6) | 5 min | Time-based |
| Security Config | ✅ F6.11 (Phase 7) | 1 min | On rotation |
| Cache Metrics | ✅ F6.11 (Phase 2) | N/A | N/A |
| Cache Keys | ✅ F6.11 (Phase 2) | N/A | N/A |

### Adding New Cache Points

When adding caching to a new component:

1. **Define cache key pattern**: Add to `CacheKeys` class in `cache_keys.py`
2. **Add TTL setting**: Add to `Settings` class in `core/config.py`
3. **Update env templates**: Add to all `.env.*.example` files
4. **Document pattern**: Add to `docs/architecture/cache-keys.md`
5. **Implement cache-aside**: Check cache → fallback to source → populate cache
6. **Add metrics tracking**: Use `CacheMetrics` for observability
7. **Add fail-open handling**: Never let cache failures break functionality
8. **Write integration tests**: Verify cache hit/miss/invalidation
9. **Update this document**: Add to "Cache Optimization (F6.11)" section

#### Example: Adding Transaction Cache

```python
# 1. Add to CacheKeys (cache_keys.py)
class CacheKeys:
    @staticmethod
    def transactions_account(account_id: UUID) -> str:
        """Cache key for transactions by account."""
        return f"{settings.CACHE_KEY_PREFIX}:transactions:account:{account_id}"

# 2. Add TTL to Settings (core/config.py)
class Settings(BaseSettings):
    CACHE_TTL_TRANSACTIONS: int = Field(default=300, ge=60, le=3600)

# 3. Update handler with cache-first strategy
class ListTransactionsHandler:
    async def handle(self, query):
        if transactions_cache:
            cache_key = CacheKeys.transactions_account(query.account_id)
            cached = await transactions_cache.get(cache_key)
            if cached:
                metrics.record_hit("transactions")
                return Success(value=cached)
            metrics.record_miss("transactions")
        
        # Fetch from DB
        transactions = await self._transaction_repo.find_by_account_id(...)
        
        # Populate cache
        if transactions_cache:
            await transactions_cache.set(
                cache_key,
                transactions,
                ttl=settings.CACHE_TTL_TRANSACTIONS,
            )
        
        return Success(value=transactions)
```

---

### Not Yet Cached ❌

#### Lower Priority Candidates

##### User Data Lookups

**Status**: Deferred to v1.1.0+ (Phase 3 skipped in F6.11)
**Reason**: Low ROI - user data accessed infrequently

```python
# Proposed (if needed)
cache_key = CacheKeys.user_data(user_id)
# TTL: 60-300 seconds
# Invalidation: On user update, password change
```

##### Transaction Lists (Paginated)

- Large data sets require pagination-aware caching
- Short freshness window
- Consider implementing when usage patterns are established

---

## Reference

- **Architecture**: `docs/architecture/cache.md`
- **Key Patterns**: `docs/architecture/cache-keys.md`
- **Protocol**: `src/domain/protocols/cache_protocol.py`
- **Implementation**: `src/infrastructure/cache/redis_adapter.py`
- **Session Cache**: `src/infrastructure/cache/session_cache.py`
- **Provider Connection Cache**: `src/infrastructure/cache/provider_connection_cache.py`
- **Cache Keys**: `src/infrastructure/cache/cache_keys.py`
- **Cache Metrics**: `src/infrastructure/cache/cache_metrics.py`
- **Container**: `src/core/container/infrastructure.py`
- **Tests**: `tests/integration/test_cache_*.py`

---

**Created**: 2025-12-05 | **Last Updated**: 2025-12-25 (F6.11)
