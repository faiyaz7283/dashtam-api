# Cache Key Patterns Design

This document defines the cache key patterns and TTL strategies for Dashtam's application-level caching (F6.11 Cache Optimization).

## Design Principles

1. **Namespace Isolation**: All keys use configurable prefix (default: `dashtam`)
2. **Clear Hierarchy**: Keys follow pattern `{prefix}:{domain}:{resource}:{id}`
3. **Invalidation-Friendly**: Hierarchical structure supports targeted invalidation
4. **Type Safety**: All IDs converted to strings for consistency

## Cache Key Patterns

### User Data Cache (HIGH Priority)

**Pattern**: `{prefix}:user:{user_id}`

**Cached Entity**: User entity (id, email, hashed_password, roles, etc.)

**TTL**: 5 minutes (300 seconds)

**Invalidation Triggers**:
- User data updated (email, password, roles changed)
- User deleted

**Example**:
```
dashtam:user:123e4567-e89b-12d3-a456-426614174000
```

**Use Cases**:
- Authentication lookup (email → user)
- Authorization checks (user roles)
- Profile displays

---

### Provider Connection Cache (HIGH Priority)

**Pattern**: `{prefix}:provider:conn:{connection_id}`

**Cached Entity**: ProviderConnection entity (connection status, credentials, etc.)

**TTL**: 5 minutes (300 seconds)

**Invalidation Triggers**:
- Connection status changed (connected, disconnected, expired)
- Credentials refreshed
- Connection deleted

**Example**:
```
dashtam:provider:conn:456e7890-e89b-12d3-a456-426614174001
```

**Use Cases**:
- Provider status checks
- OAuth token validation
- Connection management API calls

---

### Schwab Accounts Cache (HIGH Priority)

**Pattern**: `{prefix}:schwab:accounts:{user_id}`

**Cached Data**: List of account data from Schwab API (raw ProviderAccountData)

**TTL**: 5 minutes (300 seconds)

**Invalidation Triggers**:
- Manual account sync requested
- TTL expires (stale data acceptable for read performance)

**Example**:
```
dashtam:schwab:accounts:123e4567-e89b-12d3-a456-426614174000
```

**Use Cases**:
- Account list API calls
- Reduce Schwab API rate limit pressure

**Note**: This caches the raw API response before entity mapping, reducing external API calls.

---

### Schwab Transactions Cache (MEDIUM Priority)

**Pattern**: `{prefix}:schwab:tx:{account_id}:{start_date}:{end_date}`

**Cached Data**: List of transaction data from Schwab API (raw ProviderTransactionData)

**TTL**: 5 minutes (300 seconds)

**Invalidation Triggers**:
- Manual transaction sync requested
- TTL expires

**Example**:
```
dashtam:schwab:tx:789e0123-e89b-12d3-a456-426614174002:2025-01-01:2025-01-31
```

**Use Cases**:
- Transaction list API calls with date ranges
- Reduce Schwab API rate limit pressure
- Immutable historical data (safe to cache aggressively)

**Note**: Date range is part of key to support different query windows. Historical transactions are immutable, making them ideal for caching.

---

### Account List Cache (MEDIUM Priority)

**Pattern**: `{prefix}:accounts:user:{user_id}`

**Cached Data**: List of Account entities for user (after entity mapping)

**TTL**: 5 minutes (300 seconds)

**Invalidation Triggers**:
- Account created/updated/deleted for user
- Manual account sync requested

**Example**:
```
dashtam:accounts:user:123e4567-e89b-12d3-a456-426614174000
```

**Use Cases**:
- Account list API calls
- Dashboard displays

**Note**: This caches the mapped entities (not raw API data), reducing database queries.

---

### Security Version Cache (Existing - NO CHANGES)

**Global Version Pattern**: `{prefix}:security:global_version`

**User Version Pattern**: `{prefix}:security:user_version:{user_id}`

**TTL**: 1 minute (60 seconds)

**Use Cases**:
- Token breach rotation (hybrid versioning)
- Emergency token invalidation

**Note**: Already implemented in F1.3b. NO changes needed for F6.11.

---

## TTL Configuration Strategy

All TTLs are configurable via environment variables (src/core/config.py):

```python
# Cache Configuration
cache_key_prefix: str = "dashtam"
cache_user_ttl: int = 300          # User data: 5 minutes
cache_provider_ttl: int = 300      # Provider connections: 5 minutes
cache_schwab_ttl: int = 300        # Schwab API responses: 5 minutes
cache_accounts_ttl: int = 300      # Account lists: 5 minutes
cache_security_ttl: int = 60       # Security config: 1 minute
```

### Rationale for 5-Minute TTL

- **Balance**: Fresh enough for UX, stale enough for performance gains
- **Acceptable Staleness**: User/account data changes infrequently
- **Schwab Rate Limits**: Reduces API pressure while maintaining reasonable freshness
- **Fail-Open Safety**: Short TTL = less risk if invalidation fails

### Security Cache: 1-Minute TTL

- **Critical Path**: Token validation happens on every authenticated request
- **Low Tolerance**: Security decisions require fresher data
- **High Churn**: Version increments are rare but must propagate quickly

---

## Cache Invalidation Patterns

### Pattern 1: Direct Key Deletion

```python
# After update/delete operation
await cache.delete(f"{prefix}:user:{user_id}")
```

**Use Cases**: Single entity updates (user, provider connection)

---

### Pattern 2: Multi-Key Deletion

```python
# Invalidate multiple related caches
keys = [
    f"{prefix}:user:{user_id}",
    f"{prefix}:accounts:user:{user_id}",
]
await asyncio.gather(*[cache.delete(key) for key in keys])
```

**Use Cases**: Updates affecting multiple cache entries (account sync invalidates both accounts and Schwab caches)

---

### Pattern 3: TTL Expiration (Passive)

```python
# No explicit invalidation - rely on TTL
await cache.set(key, value, ttl=settings.cache_schwab_ttl)
```

**Use Cases**: Schwab API responses (historical data, low-risk staleness)

---

## Implementation Example (Cache-Aside Pattern)

```python
async def get_cached_user(
    user_id: UUID,
    cache: CacheProtocol,
    repository: UserRepository,
    settings: Settings,
) -> Result[User | None, CacheError]:
    """Retrieve user from cache or database (cache-aside pattern)."""
    cache_key = f"{settings.cache_key_prefix}:user:{user_id}"
    
    # Step 1: Try cache (fail-open on error)
    try:
        cached = await cache.get(cache_key)
        if cached:
            user_dict = json.loads(cached)
            return Success(value=User(**user_dict))
    except Exception:
        # Fail-open: Cache error should not block request
        pass
    
    # Step 2: Cache miss - fetch from database
    result = await repository.find_by_id(user_id)
    
    # Step 3: Update cache on success (fail-open)
    if isinstance(result, Success) and result.value:
        try:
            user_json = json.dumps(result.value.to_dict())
            await cache.set(cache_key, user_json, ttl=settings.cache_user_ttl)
        except Exception:
            # Fail-open: Cache write failure should not block response
            pass
    
    return result
```

---

## Cache Key Construction Utilities

To ensure consistency, cache key construction will be centralized in `src/infrastructure/cache/cache_keys.py`:

```python
from dataclasses import dataclass
from uuid import UUID
from datetime import date


@dataclass
class CacheKeys:
    """Centralized cache key construction utilities."""
    
    prefix: str
    
    def user(self, user_id: UUID) -> str:
        """User data cache key."""
        return f"{self.prefix}:user:{user_id}"
    
    def provider_connection(self, connection_id: UUID) -> str:
        """Provider connection cache key."""
        return f"{self.prefix}:provider:conn:{connection_id}"
    
    def schwab_accounts(self, user_id: UUID) -> str:
        """Schwab accounts cache key."""
        return f"{self.prefix}:schwab:accounts:{user_id}"
    
    def schwab_transactions(
        self,
        account_id: UUID,
        start_date: date,
        end_date: date,
    ) -> str:
        """Schwab transactions cache key."""
        return f"{self.prefix}:schwab:tx:{account_id}:{start_date}:{end_date}"
    
    def account_list(self, user_id: UUID) -> str:
        """Account list cache key."""
        return f"{self.prefix}:accounts:user:{user_id}"
```

**Usage**:
```python
from src.core.container import get_settings
from src.infrastructure.cache.cache_keys import CacheKeys

settings = get_settings()
keys = CacheKeys(prefix=settings.cache_key_prefix)

cache_key = keys.user(user_id)  # dashtam:user:{user_id}
```

---

## Performance Impact Estimates

Based on cache hit rate assumptions (70-90% after warm-up):

| Cache Target | Expected Reduction | Primary Benefit |
|--------------|-------------------|-----------------|
| User Data | 70-90% fewer DB queries | Authentication/authorization performance |
| Provider Connections | 60-80% fewer DB queries | Provider status checks |
| Schwab Accounts | 70-90% fewer API calls | Reduced rate limit pressure, faster account lists |
| Schwab Transactions | 70-90% fewer API calls | Reduced rate limit pressure, faster transaction history |
| Account Lists | 50-70% fewer DB queries | Dashboard load performance |

**Overall Expected Impact**: 10-30% reduction in API response latency for cached operations.

---

## Testing Strategy

### Cache Hit/Miss Tests (Integration)
- Verify cache miss triggers database/API lookup
- Verify cache hit returns cached value
- Verify cache invalidation removes stale data

### Fail-Open Tests (Integration)
- Verify Redis down = no errors (fallback to DB/API)
- Verify cache write failure = no errors (request completes)

### TTL Tests (Integration)
- Verify expired cache entries trigger refresh
- Verify fresh cache entries return cached value

### Key Construction Tests (Unit)
- Verify CacheKeys utility generates correct patterns
- Verify UUID → string conversion

---

**Created**: 2025-12-25 | **Last Updated**: 2025-12-25
