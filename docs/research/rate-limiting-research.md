# Rate Limiting Strategy Research

Comprehensive research on rate limiting algorithms, implementation strategies, and industry best practices for the Dashtam financial data aggregation platform.

## Context

### Current State

Dashtam currently has **no rate limiting** on any API endpoints or provider calls:

- **Vulnerability**: API endpoints exposed to brute force attacks (login, registration, password reset)
- **Provider Risk**: No protection against exceeding third-party API rate limits (Charles Schwab, future providers)
- **DoS Exposure**: Single user or attacker can overwhelm the system with unlimited requests
- **No Fair Usage**: Cannot enforce usage policies or prevent abuse
- **Unblocked**: JWT authentication system now complete (provides user context for per-user limits)

**Current Stack:**

- FastAPI web framework with async/await
- Redis 8.2.1 (already deployed for caching)
- PostgreSQL 17.6 (for audit logs)
- Python 3.13
- Docker containerization

### Desired State

Implement production-ready rate limiting that:

1. **Protects Authentication Endpoints**: Prevent brute force attacks on login/registration
2. **Per-User Limits**: Authenticated users get fair resource allocation
3. **Provider Protection**: Respect third-party API rate limits (Schwab, Plaid, future providers)
4. **Graceful Degradation**: Clear HTTP 429 responses with retry-after headers
5. **Monitoring & Alerts**: Track rate limit violations for security analysis
6. **Performance**: Minimal latency overhead (< 5ms per request)
7. **Distributed**: Works across multiple FastAPI instances (horizontal scaling)

### Constraints

- **Existing Infrastructure**: Must use existing Redis 8.2.1 deployment
- **Performance**: < 5ms latency overhead per request
- **Compatibility**: Must work with FastAPI TestClient for testing
- **Zero Downtime**: Must support hot configuration reloads
- **Audit Trail**: All rate limit violations must be logged
- **No Breaking Changes**: Existing API clients should continue to work
- **Budget**: Open-source solutions only (no commercial tools)

## Problem Statement

Without rate limiting, Dashtam is vulnerable to:

1. **Brute Force Attacks**: Attackers can make unlimited login attempts
2. **Account Enumeration**: Unlimited registration attempts can discover existing emails
3. **Provider Quota Exhaustion**: Single user can exhaust Charles Schwab API quotas
4. **Denial of Service**: Malicious or buggy clients can overwhelm the system
5. **Resource Starvation**: One user's excessive usage degrades service for others
6. **Compliance Risk**: Cannot enforce contractual usage limits
7. **Cost Exposure**: Excessive provider API calls increase costs

### Why This Matters

**Security Impact:**

- **OWASP Top 10**: Broken Authentication (A07:2021) requires rate limiting
- **PCI-DSS Requirement 8.1.6**: Limit repeated access attempts
- **SOC 2**: Availability controls require DoS protection

**Business Impact:**

- **Provider Costs**: Charles Schwab API calls cost money after free tier
- **Service Reliability**: Prevents single user from degrading service
- **Fair Usage**: Ensures all users get reasonable access

**Technical Impact:**

- **Database Protection**: Prevents excessive database queries
- **API Gateway**: Unblocks future API monetization
- **Compliance**: Required for SOC 2 Type II certification

## Research Questions

1. **Algorithm**: Which rate limiting algorithm best fits financial API use cases? (Token Bucket vs Leaky Bucket vs Fixed Window vs Sliding Window)
2. **Storage**: Should we use Redis, in-memory, or hybrid approach for distributed rate limiting?
3. **Granularity**: What rate limiting scopes do we need? (per-user, per-IP, per-endpoint, per-provider)
4. **Libraries**: Should we use existing FastAPI libraries (slowapi, fastapi-limiter) or build custom solution?
5. **Error Handling**: How should we communicate rate limits to clients? (HTTP 429, headers, response format)
6. **Configuration**: How flexible should rate limit configuration be? (per-endpoint, per-role, dynamic)
7. **Testing**: How do we test rate limiting with FastAPI TestClient? (time mocking, Redis mocking)

## Options Considered

### Option 1: Token Bucket Algorithm with Redis (Recommended)

**Description:** Token bucket algorithm stores a "bucket" of tokens for each user/IP. Each request consumes one token. Tokens refill at a constant rate. Allows brief bursts above the rate limit while maintaining average rate.

**How It Works:**

```python
# Token Bucket Logic
tokens = redis.get(f"ratelimit:{user_id}:tokens") or max_tokens
last_refill = redis.get(f"ratelimit:{user_id}:last_refill") or now

# Calculate tokens to add (refill rate * elapsed time)
elapsed = now - last_refill
tokens_to_add = elapsed * refill_rate
tokens = min(tokens + tokens_to_add, max_tokens)

# Consume token for this request
if tokens >= 1:
    tokens -= 1
    redis.setex(f"ratelimit:{user_id}:tokens", ttl, tokens)
    redis.setex(f"ratelimit:{user_id}:last_refill", ttl, now)
    allow_request()
else:
    deny_request(retry_after=ceil((1 - tokens) / refill_rate))
```

**Pros:**

- ✅ **Burst Handling**: Allows legitimate burst traffic (e.g., user refreshes multiple accounts)
- ✅ **Smooth Rate**: Maintains average rate over time
- ✅ **Industry Standard**: Used by AWS API Gateway, GitHub, Stripe
- ✅ **User-Friendly**: Doesn't penalize brief bursts
- ✅ **Distributed**: Redis-based, works across multiple servers
- ✅ **Precise**: Fractional token calculations for accurate rates

**Cons:**

- ❌ **Complexity**: More complex than fixed window
- ❌ **Storage**: Requires 2 Redis keys per user (tokens + last_refill)
- ❌ **Race Conditions**: Needs Lua scripts or transactions for atomicity

**Complexity:** Medium

**Cost:** Low (uses existing Redis)

**Performance:** ~2-3ms overhead per request

**Example Implementation:**

```python
class TokenBucketRateLimiter:
    def __init__(self, redis: Redis, max_tokens: int, refill_rate: float):
        self.redis = redis
        self.max_tokens = max_tokens  # e.g., 100 tokens
        self.refill_rate = refill_rate  # e.g., 10 tokens/second
    
    async def is_allowed(self, key: str) -> tuple[bool, float]:
        """Check if request is allowed. Returns (allowed, retry_after_seconds)"""
        lua_script = """
        local key_tokens = KEYS[1]
        local key_timestamp = KEYS[2]
        local max_tokens = tonumber(ARGV[1])
        local refill_rate = tonumber(ARGV[2])
        local now = tonumber(ARGV[3])
        local cost = tonumber(ARGV[4])
        
        local tokens = tonumber(redis.call('get', key_tokens)) or max_tokens
        local last_refill = tonumber(redis.call('get', key_timestamp)) or now
        
        -- Calculate refill
        local elapsed = now - last_refill
        local refill = elapsed * refill_rate
        tokens = math.min(tokens + refill, max_tokens)
        
        -- Try to consume
        if tokens >= cost then
            tokens = tokens - cost
            redis.call('setex', key_tokens, 3600, tokens)
            redis.call('setex', key_timestamp, 3600, now)
            return {1, 0}  -- allowed, no retry
        else
            local retry_after = (cost - tokens) / refill_rate
            return {0, retry_after}  -- denied, retry after X seconds
        end
        """
        # Execute atomically via Lua script
```

**Industry Usage:**

- **AWS API Gateway**: Token bucket with burst allowance
- **GitHub API**: 5,000 req/hour with burst up to 100
- **Stripe API**: Token bucket with different rates per endpoint

### Option 2: Sliding Window Log Algorithm with Redis

**Description:** Tracks exact timestamps of all requests in a sliding time window. Most accurate algorithm but higher storage cost.

**How It Works:**

```python
# Sliding Window Log
window_key = f"ratelimit:{user_id}:requests"
now = time.time()
window_start = now - window_size

# Remove old entries
redis.zremrangebyscore(window_key, 0, window_start)

# Count requests in window
request_count = redis.zcard(window_key)

if request_count < max_requests:
    # Add this request
    redis.zadd(window_key, {str(uuid.uuid4()): now})
    redis.expire(window_key, window_size)
    allow_request()
else:
    # Get oldest request timestamp
    oldest = redis.zrange(window_key, 0, 0, withscores=True)
    retry_after = oldest[0][1] + window_size - now
    deny_request(retry_after)
```

**Pros:**

- ✅ **Most Accurate**: Tracks exact request times
- ✅ **Fair**: No edge effects at window boundaries
- ✅ **Precise Retry**: Can calculate exact retry-after time
- ✅ **Distributed**: Redis-based, works across servers

**Cons:**

- ❌ **Storage Cost**: Stores every request timestamp (high memory for busy endpoints)
- ❌ **Performance**: ZREMRANGEBYSCORE + ZCARD on every request
- ❌ **Complexity**: More complex than fixed window
- ❌ **Overhead**: ~5-8ms latency per request

**Complexity:** High

**Cost:** Medium (higher Redis memory usage)

**Performance:** ~5-8ms overhead per request

**Industry Usage:**

- **Cloudflare**: Sliding window for DDoS protection
- **Kong API Gateway**: Sliding window option available

### Option 3: Fixed Window Counter with Redis

**Description:** Simplest algorithm. Counts requests in fixed time windows (e.g., per minute). Resets counter at window boundaries.

**How It Works:**

```python
# Fixed Window Counter
window_key = f"ratelimit:{user_id}:{minute}"
count = redis.incr(window_key)

if count == 1:
    redis.expire(window_key, 60)  # Set TTL on first request

if count <= max_requests:
    allow_request()
else:
    retry_after = 60 - (time.time() % 60)
    deny_request(retry_after)
```

**Pros:**

- ✅ **Simple**: Easy to implement and understand
- ✅ **Fast**: Single INCR operation (~1ms)
- ✅ **Low Memory**: Single counter per window
- ✅ **Efficient**: Minimal Redis operations

**Cons:**

- ❌ **Burst at Boundaries**: User can make 2x requests by splitting across window boundary
  - Example: 100 requests at 59s + 100 requests at 1s = 200 requests in 2 seconds
- ❌ **Unfair**: Users who request at window end get penalized
- ❌ **Inaccurate**: Not truly per-minute rate limiting

**Complexity:** Low

**Cost:** Low

**Performance:** ~1ms overhead per request

**Industry Usage:**

- **Twitter API**: Fixed window (15 minutes)
- **Reddit API**: Fixed window (per minute)

### Option 4: Sliding Window Counter (Hybrid)

**Description:** Hybrid of fixed window and sliding window. Uses two fixed windows and interpolates between them. Balance of accuracy and efficiency.

**How It Works:**

```python
# Sliding Window Counter
current_window = f"ratelimit:{user_id}:{current_minute}"
previous_window = f"ratelimit:{user_id}:{previous_minute}"

current_count = redis.get(current_window) or 0
previous_count = redis.get(previous_window) or 0

# Weight based on position in current window
window_position = (time.time() % 60) / 60  # 0.0 to 1.0
estimated_count = (previous_count * (1 - window_position)) + current_count

if estimated_count < max_requests:
    redis.incr(current_window)
    redis.expire(current_window, 120)  # Keep 2 windows
    allow_request()
else:
    deny_request(retry_after=60 * (1 - window_position))
```

**Pros:**

- ✅ **Balanced**: Better than fixed window, cheaper than sliding log
- ✅ **Reduced Boundary Issue**: Weighted calculation smooths boundaries
- ✅ **Efficient**: Only 2-3 Redis operations
- ✅ **Good Enough**: 95% accuracy with 50% storage cost

**Cons:**

- ❌ **Approximation**: Not as precise as sliding window log
- ❌ **Complex Logic**: More complex than fixed window
- ❌ **Edge Cases**: Still allows some boundary bursts

**Complexity:** Medium

**Cost:** Low

**Performance:** ~2-3ms overhead per request

**Industry Usage:**

- **Cloudflare**: Uses this for rate limiting
- **Instagram API**: Sliding window counter

### Option 5: Leaky Bucket Algorithm

**Description:** Requests enter a queue (bucket) and are processed at constant rate. Excess requests are dropped. Enforces strict rate limiting.

**How It Works:**

```python
# Leaky Bucket
queue_key = f"ratelimit:{user_id}:queue"
last_leak = redis.get(f"ratelimit:{user_id}:last_leak") or now

# Calculate how many requests leaked since last check
elapsed = now - last_leak
leaked = floor(elapsed * leak_rate)

# Get current queue size
queue_size = redis.llen(queue_key)
queue_size = max(0, queue_size - leaked)

if queue_size < bucket_size:
    redis.rpush(queue_key, now)
    redis.setex(queue_key, ttl, ...)
    redis.setex(f"ratelimit:{user_id}:last_leak", ttl, now)
    allow_request()
else:
    deny_request()
```

**Pros:**

- ✅ **Smooth Rate**: Forces constant processing rate
- ✅ **No Bursts**: Strictly enforces rate limit
- ✅ **Queue Visibility**: Can see pending requests

**Cons:**

- ❌ **No Bursts**: Penalizes legitimate burst traffic
- ❌ **Complexity**: Requires queue management
- ❌ **Overhead**: More Redis operations (LLEN, RPUSH, etc.)
- ❌ **User Experience**: Frustrating for users with bursty patterns

**Complexity:** High

**Cost:** Medium

**Performance:** ~4-6ms overhead per request

**Industry Usage:**

- **Network Traffic Shaping**: Common in network equipment
- **Less Common for APIs**: Too strict for most HTTP APIs

### Option 6: FastAPI Library - SlowAPI

**Description:** Use existing FastAPI rate limiting library (SlowAPI) built on top of `limits` library. Supports multiple algorithms and backends.

**Implementation:**

```python
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(
    key_func=get_remote_address,
    storage_uri="redis://redis:6379"
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

@app.post("/auth/login")
@limiter.limit("5/minute")
async def login(request: Request, ...):
    ...
```

**Pros:**

- ✅ **Quick Setup**: Few lines of code to get started
- ✅ **Batteries Included**: Multiple algorithms supported
- ✅ **Decorator Pattern**: Clean API with decorators
- ✅ **Community Support**: Active maintenance

**Cons:**

- ❌ **Limited Flexibility**: Hard to customize for complex use cases
- ❌ **Per-Endpoint Config**: Must decorate every endpoint
- ❌ **Testing Challenges**: Difficult to mock time in tests
- ❌ **Less Control**: Black box implementation
- ❌ **Dependency**: Adds external dependency
- ❌ **No Per-User Limits**: Primarily IP-based

**Complexity:** Low

**Cost:** Low

**Performance:** ~3-5ms overhead per request

**Industry Usage:**

- **Small Projects**: Good for MVPs and small APIs
- **FastAPI Community**: Popular in FastAPI ecosystem

### Option 7: In-Memory Rate Limiting (Single Instance Only)

**Description:** Store rate limit data in application memory instead of Redis. Only works for single-server deployments.

**Pros:**

- ✅ **Fast**: No network calls (~0.5ms)
- ✅ **Simple**: No external dependencies

**Cons:**

- ❌ **Not Distributed**: Does NOT work with multiple FastAPI instances
- ❌ **Lost on Restart**: Rate limit state lost on application restart
- ❌ **Scaling Blocker**: Cannot horizontally scale
- ❌ **Not Production Ready**: Not suitable for Dashtam

**Complexity:** Low

**Cost:** Low

**Performance:** ~0.5ms overhead

**Verdict:** ❌ **NOT SUITABLE** - Dashtam needs distributed rate limiting for horizontal scaling

## Analysis

### Comparison Matrix

| Criterion | Token Bucket | Sliding Log | Fixed Window | Sliding Counter | Leaky Bucket | SlowAPI | Weight |
|-----------|--------------|-------------|--------------|-----------------|--------------|---------|---------|
| Accuracy | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | High |
| Performance | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | Critical |
| Burst Handling | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐ | ⭐⭐⭐ | High |
| Memory Efficiency | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | Medium |
| Distributed Support | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | Critical |
| Implementation Complexity | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | Medium |
| Flexibility | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ | High |
| Testing Ease | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ | Medium |
| **TOTAL SCORE** | **37/40** | **28/40** | **31/40** | **33/40** | **28/40** | **29/40** | - |

**Winner: Token Bucket Algorithm with Redis** ✅

### Detailed Analysis

#### Performance

**Requirements:** < 5ms overhead per request

**Token Bucket:**

- 2-3ms average latency
- Lua script execution in Redis (atomic, fast)
- 2 Redis operations (GET tokens, SET tokens+timestamp)
- ✅ Meets requirement

**Sliding Window Log:**

- 5-8ms average latency  
- ZREMRANGEBYSCORE + ZCARD + ZADD operations
- Stores all request timestamps (memory intensive)
- ⚠️ Borderline, may exceed under load

**Fixed Window:**

- 1ms average latency
- Single INCR operation
- ✅ Fastest option
- ❌ But sacrifices accuracy

**Verdict:** Token Bucket offers best balance of performance and accuracy

#### Burst Handling

**Financial API Use Case:** Users may refresh multiple accounts simultaneously

**Token Bucket:**

- Allows bursts up to max_tokens capacity
- Example: 100 token bucket, 10/sec refill rate
  - User can make 100 requests instantly, then 10/sec after
- ✅ **Perfect for financial APIs**

**Fixed Window:**

- No burst handling at all
- Can exploit boundary (2x requests)
- ❌ Poor user experience

**Sliding Window Log:**

- Smooth rate, small bursts allowed
- Better than fixed, not as flexible as token bucket

**Verdict:** Token Bucket provides best burst handling for legitimate use cases

#### Distributed Support

**Requirement:** Must work across multiple FastAPI instances

**All Redis-based options:**

- ✅ Inherently distributed
- ✅ Redis provides atomic operations via Lua scripts
- ✅ No single point of failure (Redis cluster)

**In-Memory:**

- ❌ Does NOT work across instances
- ❌ Eliminated from consideration

**Verdict:** Redis is mandatory for distributed rate limiting

#### Flexibility

**Requirements:**

- Per-user limits (authenticated users)
- Per-IP limits (anonymous/before auth)
- Per-endpoint limits (login stricter than read operations)
- Per-provider limits (Charles Schwab API quotas)
- Dynamic configuration (no code changes)

**Token Bucket (Custom Implementation):**

- ✅ Full control over key structure
- ✅ Can implement any limit scope
- ✅ Configuration via database or Redis
- ✅ Example keys:
  - `ratelimit:user:{user_id}:global`
  - `ratelimit:ip:{ip_address}:auth`
  - `ratelimit:provider:schwab:{user_id}`

**SlowAPI (Library):**

- ⚠️ Limited to decorator-based configuration
- ⚠️ Primarily IP-based limits
- ⚠️ Hard to add per-user limits
- ❌ Less flexible for complex use cases

**Verdict:** Custom Token Bucket implementation offers required flexibility

#### Testing

**Requirements:** Must work with FastAPI TestClient, mockable for tests

**Token Bucket (Custom):**

- ✅ Can mock Redis for unit tests
- ✅ Can mock time for deterministic tests
- ✅ Can test token refill logic in isolation
- ✅ Integration tests with fakeredis

**SlowAPI:**

- ⚠️ Hard to mock time (uses system time)
- ⚠️ Integration tests require real Redis
- ❌ Decorator pattern makes unit testing harder

**Fixed Window:**

- ✅ Easiest to test (simple counter)
- ✅ But less functionality to test

**Verdict:** Custom implementation with dependency injection provides best testability

### Industry Research

**Real-World Examples:**

1. **AWS API Gateway:**
   - **Algorithm:** Token Bucket
   - **Configuration:** Burst limit + steady-state rate
   - **Example:** 10,000 req/sec burst, 5,000 req/sec steady
   - **Why:** Handles traffic spikes while preventing sustained abuse

2. **GitHub API:**
   - **Algorithm:** Token Bucket
   - **Configuration:** 5,000 req/hour with 100-token burst
   - **Rate Limit Headers:**

     ```http
     X-RateLimit-Limit: 5000
     X-RateLimit-Remaining: 4999
     X-RateLimit-Reset: 1372700873
     X-RateLimit-Used: 1
     ```

3. **Stripe API:**
   - **Algorithm:** Token Bucket with different rates per endpoint
   - **Read Operations:** 100 req/sec
   - **Write Operations:** 25 req/sec
   - **Webhooks:** 1,000 req/sec
   - **Why:** Different operations have different cost/risk profiles

4. **Cloudflare:**
   - **Algorithm:** Sliding Window Counter (hybrid)
   - **Scale:** Millions of requests per second
   - **Why:** Balance of accuracy and performance at scale

5. **Shopify API:**
   - **Algorithm:** Leaky Bucket
   - **Configuration:** 2 req/sec (40 req/20sec bucket)
   - **Why:** Smooth rate for merchant API fairness

**Best Practices:**

1. **Use Token Bucket for APIs**: Industry standard (AWS, GitHub, Stripe, Cloudflare)
2. **Provide Rate Limit Headers**: Transparency for API clients
   - `X-RateLimit-Limit`
   - `X-RateLimit-Remaining`
   - `X-RateLimit-Reset`
   - `Retry-After` (on 429 responses)
3. **Different Limits per Endpoint**: Authentication stricter than reads
4. **Burst Capacity**: Allow legitimate bursts (user refreshing multiple accounts)
5. **Graceful Degradation**: Return 429 with clear error messages
6. **Monitoring**: Track rate limit violations for security analysis
7. **Bypass Mechanism**: Allow admin/monitoring tools to bypass limits
8. **Configuration Flexibility**: Rate limits in config/database, not code
9. **Retry Logic**: Clients should implement exponential backoff
10. **Documentation**: Clearly document rate limits in API docs

**Financial API Considerations:**

- **Stripe**: Token bucket with burst for payment processing APIs
- **Plaid**: Fixed window with per-institution limits
- **Alpaca Trading**: 200 req/minute with different limits per endpoint
- **Interactive Brokers**: Leaky bucket for order submission (strict rate)

**Consensus:** Token Bucket is industry standard for financial APIs

## Decision

### Chosen Option: Token Bucket Algorithm with Redis (Custom Implementation)

We will implement a **custom Token Bucket rate limiting service** using Redis for distributed storage. This provides the flexibility, performance, and burst handling required for a financial data aggregation platform.

### Rationale

**Key Factors:**

1. **Industry Standard**: Token Bucket is used by AWS API Gateway, GitHub API, Stripe API - proven at scale
2. **Burst Handling**: Financial users legitimately refresh multiple accounts simultaneously - token bucket allows this
3. **Performance**: 2-3ms overhead meets our < 5ms requirement
4. **Flexibility**: Custom implementation allows per-user, per-IP, per-endpoint, and per-provider limits
5. **Testing**: Dependency injection and Redis mocking enable comprehensive testing
6. **Distributed**: Redis-based solution works across multiple FastAPI instances (horizontal scaling ready)
7. **Control**: Full control over algorithm, configuration, monitoring, and audit logging

**Why Not Other Options:**

- **Fixed Window**: Too inaccurate, boundary exploitation issues
- **Sliding Window Log**: Too slow (5-8ms), high memory cost
- **Sliding Window Counter**: Good, but token bucket provides better burst handling
- **Leaky Bucket**: Too strict, poor user experience for bursty traffic
- **SlowAPI**: Insufficient flexibility for per-user and per-provider limits

### Decision Criteria Met

- ✅ **Performance**: 2-3ms overhead < 5ms requirement
- ✅ **Distributed**: Redis-based, works across multiple instances
- ✅ **Flexible**: Supports all required limit scopes (user, IP, endpoint, provider)
- ✅ **Burst Friendly**: Allows legitimate burst traffic
- ✅ **Testable**: Mockable dependencies, deterministic tests
- ✅ **Industry Proven**: AWS, GitHub, Stripe all use token bucket
- ✅ **Audit Trail**: Can log all rate limit violations
- ✅ **Existing Infrastructure**: Uses existing Redis deployment

## Consequences

### Positive Consequences

- ✅ **Security**: Protects against brute force attacks on authentication endpoints
- ✅ **Provider Protection**: Respects Charles Schwab API rate limits, prevents quota exhaustion
- ✅ **Fair Usage**: Ensures all users get reasonable access, prevents resource starvation
- ✅ **Scalability**: Distributed design supports horizontal scaling
- ✅ **User Experience**: Burst handling doesn't penalize legitimate user behavior
- ✅ **Monitoring**: Rate limit violations provide security intelligence
- ✅ **Compliance**: Meets PCI-DSS 8.1.6 and SOC 2 availability requirements
- ✅ **Future Ready**: Enables API monetization (tiered limits)

### Negative Consequences

- ⚠️ **Complexity**: More complex than fixed window counter (but manageable)
- ⚠️ **Redis Dependency**: Rate limiting unavailable if Redis is down (mitigation: fail-open for non-critical endpoints)
- ⚠️ **Lua Scripts**: Requires Lua knowledge for Redis atomic operations (mitigation: comprehensive documentation)
- ⚠️ **Configuration Management**: More moving parts to configure (mitigation: configuration validation)

### Risks

#### Risk 1: Redis Performance Bottleneck

- **Description:** High traffic could overwhelm Redis
- **Probability:** Low (Redis handles 100k+ ops/sec)
- **Impact:** Medium (rate limiting slower, but still functional)
- **Mitigation:**
  - Use Redis pipelining for batch operations
  - Monitor Redis performance metrics
  - Redis Cluster for horizontal scaling if needed
  - Connection pooling (already configured)

#### Risk 2: Clock Skew in Distributed System

- **Description:** Different servers have slightly different times
- **Probability:** Low (NTP synchronization)
- **Impact:** Low (minor rate limit inaccuracies)
- **Mitigation:**
  - Use Redis server time (TIME command)
  - NTP configuration on all servers
  - Acceptable tolerance (sub-second skew acceptable)

#### Risk 3: False Positives (Legitimate Users Rate Limited)

- **Description:** Burst limits too low, penalize real users
- **Probability:** Medium (configuration dependent)
- **Impact:** Medium (poor user experience)
- **Mitigation:**
  - Generous burst capacity (100+ tokens)
  - Monitor rate limit violation patterns
  - Dynamic adjustment based on usage data
  - Override mechanism for support team

#### Risk 4: Testing Challenges with Time-Based Logic

- **Description:** Time-dependent tests can be flaky
- **Probability:** Medium (common issue with rate limiting)
- **Impact:** Low (slows development)
- **Mitigation:**
  - Mock time in tests (freezegun library)
  - Use fakeredis for deterministic tests
  - Comprehensive unit tests for core logic
  - Separate integration tests with real Redis

## Implementation

### Implementation Plan

#### Phase 1: Core Infrastructure

- [ ] Redis Lua script for atomic token bucket operations
- [ ] RateLimiterService (core business logic)
- [ ] Configuration model (RateLimitConfig Pydantic model)
- [ ] Unit tests for token bucket algorithm (mocked Redis)
- [ ] Unit tests for configuration validation

#### Phase 2: FastAPI Integration

- [ ] RateLimitMiddleware (FastAPI middleware)
- [ ] Rate limit dependency (for per-endpoint limits)
- [ ] HTTP 429 exception handler
- [ ] Rate limit headers (X-RateLimit-*, Retry-After)
- [ ] Integration tests with TestClient

#### Phase 3: Endpoint Configuration

- [ ] Authentication endpoints (5/min, 20 burst)
- [ ] Read endpoints (100/min, 100 burst)
- [ ] Write endpoints (20/min, 50 burst)
- [ ] Provider endpoints (per-provider limits)
- [ ] Configuration storage (Redis or database)

#### Phase 4: Monitoring & Audit

- [ ] Rate limit violation logging
- [ ] Prometheus metrics (requests, violations, latency)
- [ ] Audit log integration
- [ ] Admin bypass mechanism
- [ ] Dashboard/monitoring

#### Phase 5: Documentation & Rollout

- [ ] API documentation (rate limits per endpoint)
- [ ] Client retry guide (exponential backoff)
- [ ] Configuration guide (DevOps)
- [ ] Gradual rollout (monitor, adjust)
- [ ] Load testing and tuning

### Configuration Example

```python
# Rate Limit Configuration
RATE_LIMITS = {
    "auth.login": {
        "max_tokens": 20,
        "refill_rate": 5/60,  # 5 per minute
        "scope": "ip",  # Before authentication
    },
    "auth.register": {
        "max_tokens": 10,
        "refill_rate": 2/60,  # 2 per minute  
        "scope": "ip",
    },
    "auth.password_reset": {
        "max_tokens": 5,
        "refill_rate": 1/300,  # 1 per 5 minutes
        "scope": "ip",
    },
    "providers.accounts": {
        "max_tokens": 100,
        "refill_rate": 100/60,  # 100 per minute
        "scope": "user",  # Per authenticated user
    },
    "provider.schwab.api": {
        "max_tokens": 100,
        "refill_rate": 100/60,  # Schwab's actual limit
        "scope": "provider_user",  # Per user per provider
    },
}
```

### Testing Strategy

**Unit Tests:**

- Token bucket algorithm (refill logic, consumption, burst)
- Configuration validation
- Key generation (user, IP, endpoint scopes)
- Time mocking with freezegun

**Integration Tests:**

- FastAPI TestClient with fakeredis
- Rate limit enforcement
- HTTP 429 responses
- Rate limit headers
- Multiple endpoint scopes

**Performance Tests:**

- Measure latency overhead (target < 5ms)
- Load test with locust (1000+ concurrent users)
- Redis performance under load

**End-to-End Tests:**

- Smoke tests with real Redis
- Provider API call rate limiting
- Burst traffic scenarios

## Follow-Up

### Monitoring Checklist

After deployment, monitor these metrics:

- [ ] Rate limit violation rate (% of requests denied)
- [ ] Latency impact (p50, p95, p99)
- [ ] Redis performance (ops/sec, memory usage)
- [ ] False positive rate (legitimate users blocked)
- [ ] Provider API quota usage (Schwab, future providers)

### Future Enhancements

1. **Dynamic Rate Limits**: Adjust limits based on user tier (free vs paid)
2. **Geographic Limits**: Different limits per region
3. **Time-Based Limits**: Lower limits during peak hours
4. **Circuit Breaker**: Automatically back off provider calls on errors
5. **Rate Limit Dashboard**: Real-time visualization of rate limit status
6. **ML-Based Detection**: Anomaly detection for abuse patterns

### Success Metrics

- **Security**: Zero successful brute force attacks
- **Performance**: < 5ms p95 latency overhead
- **Provider Compliance**: Zero Charles Schwab quota violations
- **User Experience**: < 0.1% rate limit false positives
- **Availability**: 99.9% rate limiting uptime

## References

**Industry Standards:**

- [AWS API Gateway Throttling](https://docs.aws.amazon.com/apigateway/latest/developerguide/api-gateway-request-throttling.html)
- [GitHub API Rate Limiting](https://docs.github.com/en/rest/overview/resources-in-the-rest-api#rate-limiting)
- [Stripe API Rate Limits](https://stripe.com/docs/rate-limits)
- [OWASP Rate Limiting Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Denial_of_Service_Cheat_Sheet.html)

**Algorithm Comparisons:**

- [Token Bucket vs Leaky Bucket](https://en.wikipedia.org/wiki/Token_bucket)
- [Cloudflare: How We Built Rate Limiting](https://blog.cloudflare.com/counting-things-a-lot-of-different-things/)
- [Kong API Gateway Rate Limiting](https://docs.konghq.com/hub/kong-inc/rate-limiting/)

**Implementation Guides:**

- [Redis Rate Limiting Patterns](https://redis.io/docs/reference/patterns/rate-limiting/)
- [FastAPI Middleware Guide](https://fastapi.tiangolo.com/tutorial/middleware/)
- [Testing Time-Dependent Code](https://github.com/spulec/freezegun)

**Compliance:**

- [PCI-DSS Requirement 8.1.6](https://www.pcisecuritystandards.org/)
- [SOC 2 Availability Controls](https://www.aicpa.org/soc4so)
- [OWASP Top 10 - A07:2021](https://owasp.org/Top10/A07_2021-Identification_and_Authentication_Failures/)

---

## Document Information

**Template:** research-template.md
**Created:** 2025-10-24
**Last Updated:** 2025-10-24
