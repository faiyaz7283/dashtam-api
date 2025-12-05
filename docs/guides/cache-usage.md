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

### Not Yet Cached ❌ (Candidates)

#### HIGH PRIORITY

##### 1. User Data Lookups

**Current**: Direct DB call on every authenticated request
**Impact**: HIGH - called via `get_current_user` on every request

```python
# Current (src/application/commands/handlers/*.py)
user = await user_repo.find_by_id(user_id)  # DB every time

# Proposed
cache_key = f"user:{user_id}"
# Check cache first, fallback to DB
# TTL: 60-300 seconds
# Invalidation: On user update, password change
```

**Files affected**:

- `authenticate_user_handler.py`
- `refresh_access_token_handler.py`
- `create_session_handler.py`
- Auth middleware (`get_current_user`)

##### 2. Provider Connection Status

**Current**: Direct DB lookup for connection details
**Impact**: MEDIUM - called during provider operations

```python
# Current
connection = await provider_repo.find_by_id(connection_id)

# Proposed
cache_key = f"provider:connection:{connection_id}"
# TTL: 300 seconds
# Invalidation: On sync, disconnect, credential refresh
```

##### 3. Schwab API Responses

**Current**: External API call every time
**Impact**: HIGH - reduces external API calls, improves latency

```python
# Current
accounts = await schwab_provider.fetch_accounts(access_token)

# Proposed
cache_key = f"schwab:accounts:{user_id}"
# TTL: 60-300 seconds (balance freshness vs API rate limits)
# Invalidation: On explicit sync request
```

#### MEDIUM PRIORITY

##### 4. Account List per User

**Current**: DB query with joins
**Impact**: MEDIUM - called on dashboard loads

```python
# Proposed
cache_key = f"accounts:user:{user_id}"
# TTL: 300-900 seconds
# Invalidation: On account sync
```

##### 5. Security Config (Token Versions)

**Current**: DB lookup for token validation
**Impact**: MEDIUM - called on token refresh

```python
# Proposed
cache_key = f"security:global_min_version"
cache_key = f"user:{user_id}:min_token_version"
# TTL: 60 seconds (security-sensitive, short TTL)
# Invalidation: On rotation trigger
```

#### LOWER PRIORITY

##### 6. Transaction Lists

- Large data sets
- Short freshness window
- Consider pagination-aware caching

##### 7. Provider Credentials (Decrypted)

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
| User Data | ❌ Not cached | - | - |
| Provider Connections | ❌ Not cached | - | - |
| Schwab API | ❌ Not cached | - | - |
| Account Lists | ❌ Not cached | - | - |
| Security Config | ❌ Not cached | - | - |

### Adding New Cache Points

When adding caching to a new component:

1. **Identify access patterns**: How often is data accessed? How fresh must it be?
2. **Choose TTL**: Balance freshness vs cache hit rate
3. **Plan invalidation**: What events should clear the cache?
4. **Implement cache-aside**: Check cache → fallback to source → populate cache
5. **Add fail-open handling**: Never let cache failures break functionality
6. **Update this document**: Add to "Currently Cached" section

---

## Reference

- **Architecture**: `docs/architecture/cache-architecture.md`
- **Protocol**: `src/domain/protocols/cache_protocol.py`
- **Implementation**: `src/infrastructure/cache/redis_adapter.py`
- **Session Cache**: `src/infrastructure/cache/session_cache.py`
- **Container**: `src/core/container/infrastructure.py`
- **Tests**: `tests/integration/test_cache_redis.py`

---

**Created**: 2025-12-05 | **Last Updated**: 2025-12-05
