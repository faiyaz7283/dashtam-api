-- token_bucket.lua
-- Atomic token bucket rate limit script
--
-- KEYS[1]: Base key for bucket (e.g., "rate_limit:ip:192.0.2.10:POST /sessions")
-- ARGV[1]: max_tokens (bucket capacity, integer)
-- ARGV[2]: refill_rate (tokens per minute, float)
-- ARGV[3]: cost (tokens to consume, integer)
-- ARGV[4]: now (current timestamp in seconds since epoch, float)
--
-- Returns array: { allowed (0/1), retry_after (float seconds), remaining_tokens (int) }
-- Notes:
--   - Initializes missing buckets as full (max_tokens)
--   - Uses SETEX with TTL = ceil((max_tokens/refill_rate)*60) + 60 buffer seconds
--   - Fail-open policy must be enforced by caller on Redis errors

local base = KEYS[1]
local tokens_key = base .. ":tokens"
local time_key = base .. ":time"

local max_tokens = tonumber(ARGV[1])
local refill_rate = tonumber(ARGV[2])
local cost = tonumber(ARGV[3])
local now = tonumber(ARGV[4])

-- Load current state
local tokens = tonumber(redis.call("GET", tokens_key))
local last_refill = tonumber(redis.call("GET", time_key))

-- Initialize if first request
if not tokens or not last_refill then
  tokens = max_tokens
  last_refill = now
end

-- Refill tokens
local elapsed = now - last_refill
if elapsed < 0 then
  -- Guard against clock skew: treat as zero
  elapsed = 0
end
local tokens_to_add = elapsed * (refill_rate / 60.0)
local current = tokens + tokens_to_add
if current > max_tokens then
  current = max_tokens
end

-- TTL: time to full refill + 60s buffer
local ttl = math.ceil((max_tokens / refill_rate) * 60) + 60

if current >= cost then
  -- Allowed path: optionally consume tokens
  local new_tokens = current - cost
  redis.call("SETEX", tokens_key, ttl, new_tokens)
  redis.call("SETEX", time_key, ttl, now)
  return {1, 0.0, math.floor(new_tokens)}
else
  -- Denied path: compute retry_after
  local needed = cost - current
  local retry_after = needed / (refill_rate / 60.0)
  redis.call("SETEX", tokens_key, ttl, current)
  redis.call("SETEX", time_key, ttl, now)
  return {0, retry_after, math.floor(current)}
end
