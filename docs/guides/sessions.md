# Session Management Usage Guide

Quick reference guide for developers working with multi-device sessions in Dashtam.

**Target Audience**: Developers implementing session-related features

**Related Documentation**:

- Architecture: `docs/architecture/sessions.md` (why/what)
- Authentication: `docs/guides/authentication.md`

---

## Quick Reference

| Operation | Endpoint | Method | Description |
|-----------|----------|--------|-------------|
| Create Session | `/api/v1/sessions` | POST | Login creates session |
| List Sessions | `/api/v1/sessions` | GET | List user's active sessions |
| Get Session | `/api/v1/sessions/{id}` | GET | Get session details |
| Revoke Current | `/api/v1/sessions/current` | DELETE | Logout current session |
| Revoke Specific | `/api/v1/sessions/{id}` | DELETE | Revoke specific session |
| Revoke All | `/api/v1/sessions` | DELETE | Revoke all except current |

---

## 1. Session Creation (During Login)

### CreateSessionHandler Usage

```python
from src.application.commands import CreateSession
from src.application.commands.handlers import CreateSessionHandler
from src.core.container import get_create_session_handler

async def create_user_session(
    user_id: UUID,
    request: Request,
    handler: CreateSessionHandler,
) -> Session:
    """Create session after successful authentication."""
    result = await handler.handle(CreateSession(
        user_id=user_id,
        ip_address=request.client.host,
        user_agent=request.headers.get("user-agent"),
    ))
    
    if isinstance(result, Failure):
        # Handle session limit exceeded, etc.
        raise HTTPException(500, "Failed to create session")
    
    return result.value
```

### Session Metadata Enrichment

Sessions are automatically enriched with:

```python
@dataclass
class Session:
    id: UUID
    user_id: UUID
    
    # Enriched metadata
    device_info: str        # "Chrome on macOS"
    ip_address: str         # "192.168.1.1"
    location: str | None    # "New York, US" (if geolocation enabled)
    
    # Lifecycle
    created_at: datetime
    last_activity: datetime
    expires_at: datetime
    
    # State
    is_revoked: bool
    revoked_at: datetime | None
    revoked_reason: str | None
    
    # Token tracking
    refresh_token_hash: str
    token_rotation_count: int
```

---

## 2. Listing User Sessions

### Query Handler Usage

```python
from src.application.queries import ListSessions
from src.core.container import get_list_sessions_handler

@router.get("/sessions")
async def list_my_sessions(
    current_user: User = Depends(get_current_user),
    handler: ListSessionsHandler = Depends(get_list_sessions_handler),
) -> list[SessionResponse]:
    """List all active sessions for current user."""
    result = await handler.handle(ListSessions(
        user_id=current_user.id,
        include_revoked=False,  # Only active sessions
    ))
    
    if isinstance(result, Failure):
        raise HTTPException(500, "Failed to list sessions")
    
    return [SessionResponse.from_entity(s) for s in result.value]
```

### Response Format

```json
{
  "sessions": [
    {
      "id": "123e4567-e89b-12d3-a456-426614174000",
      "device_info": "Chrome on macOS",
      "ip_address": "192.168.1.1",
      "location": "New York, US",
      "created_at": "2025-01-15T10:30:00Z",
      "last_activity": "2025-01-15T14:22:00Z",
      "is_current": true
    },
    {
      "id": "987fcdeb-51a2-3b4c-d567-890123456789",
      "device_info": "Safari on iPhone",
      "ip_address": "10.0.0.5",
      "location": "Boston, US",
      "created_at": "2025-01-14T08:00:00Z",
      "last_activity": "2025-01-14T18:45:00Z",
      "is_current": false
    }
  ]
}
```

---

## 3. Revoking Sessions

### Revoke Current Session (Logout)

```python
from src.application.commands import RevokeSession
from src.core.container import get_revoke_session_handler

@router.delete("/sessions/current", status_code=204)
async def logout(
    current_user: User = Depends(get_current_user),
    session_id: UUID = Depends(get_current_session_id),
    handler: RevokeSessionHandler = Depends(get_revoke_session_handler),
) -> None:
    """Logout current session."""
    await handler.handle(RevokeSession(
        session_id=session_id,
        user_id=current_user.id,
        reason="user_logout",
    ))
```

### Revoke Specific Session

```python
@router.delete("/sessions/{session_id}", status_code=204)
async def revoke_session(
    session_id: UUID,
    current_user: User = Depends(get_current_user),
    handler: RevokeSessionHandler = Depends(get_revoke_session_handler),
) -> None:
    """Revoke specific session (e.g., log out another device)."""
    result = await handler.handle(RevokeSession(
        session_id=session_id,
        user_id=current_user.id,
        reason="user_revoked",
    ))
    
    if isinstance(result, Failure):
        if result.error == "session_not_found":
            raise HTTPException(404, "Session not found")
        if result.error == "not_owner":
            raise HTTPException(403, "Cannot revoke this session")
```

### Revoke All Sessions (Security Action)

```python
from src.application.commands import RevokeAllSessions

@router.delete("/sessions", status_code=204)
async def revoke_all_sessions(
    current_user: User = Depends(get_current_user),
    current_session_id: UUID = Depends(get_current_session_id),
    handler: RevokeAllSessionsHandler = Depends(...),
) -> None:
    """Revoke all sessions except current (security: log out everywhere)."""
    await handler.handle(RevokeAllSessions(
        user_id=current_user.id,
        except_session_id=current_session_id,  # Keep current session
        reason="user_security_action",
    ))
```

---

## 4. Session Validation (Token Refresh)

### During Token Refresh

```python
# In RefreshAccessTokenHandler
async def handle(self, command: RefreshAccessToken) -> Result[TokenPair, str]:
    # 1. Validate refresh token
    token_result = await self._refresh_token_repo.find_by_token(
        command.refresh_token
    )
    if isinstance(token_result, Failure):
        return Failure("invalid_token")
    
    refresh_token = token_result.value
    
    # 2. Validate session is still active
    session_active = await self._session_cache.is_active(
        refresh_token.session_id
    )
    if not session_active:
        return Failure("session_revoked")
    
    # 3. Generate new tokens...
```

### Session Cache Check

```python
# Fast check via Redis (< 5ms)
session_active = await session_cache.is_active(session_id)

# If cache miss, fallback to database
if session_active is None:
    session = await session_repo.find_by_id(session_id)
    session_active = session and not session.is_revoked
```

---

## 5. Session Limits

### Configuration

```python
# Per-tier session limits
SESSION_TIER_LIMITS: dict[str, int | None] = {
    "ultimate": None,   # Unlimited
    "premium": 50,
    "plus": 10,
    "essential": 5,
    "basic": 2,
    "free": 1,
}
```

### Enforcement in Handler

```python
async def handle(self, command: CreateSession) -> Result[Session, str]:
    # Get user's session tier
    user = await self._user_repo.find_by_id(command.user_id)
    max_sessions = SESSION_TIER_LIMITS.get(user.session_tier, 1)
    
    # Check current session count
    active_count = await self._session_repo.count_active(command.user_id)
    
    if max_sessions is not None and active_count >= max_sessions:
        # Evict oldest session
        oldest = await self._session_repo.find_oldest_active(command.user_id)
        await self._session_repo.revoke(
            oldest.id,
            reason="session_limit_exceeded",
        )
    
    # Create new session
    ...
```

---

## 6. Session Events

### Events Emitted

```python
# Session creation
SessionCreated
{
    "session_id": UUID,
    "user_id": UUID,
    "device_info": str,
    "ip_address": str,
}

# Session revocation
SessionRevoked
{
    "session_id": UUID,
    "user_id": UUID,
    "reason": str,  # "user_logout", "password_changed", etc.
    "revoked_by": UUID | None,  # Admin or system
}
```

### Event Handler: Password Change

```python
class PasswordChangeSessionHandler:
    """Revoke all sessions when user changes password."""
    
    async def handle(self, event: PasswordChanged) -> None:
        await self._session_repo.revoke_all(
            user_id=event.user_id,
            reason="password_changed",
        )
        
        # Clear session cache
        await self._session_cache.delete_all(event.user_id)
```

---

## 7. Session Cache (Redis)

### Cache Operations

```python
from src.infrastructure.cache import RedisSessionCache

class RedisSessionCache:
    """Session cache with 30-day TTL."""
    
    KEY_PREFIX = "session"
    TTL_SECONDS = 30 * 24 * 60 * 60  # 30 days
    
    async def set(self, session: Session) -> None:
        """Cache session after creation."""
        key = f"{self.KEY_PREFIX}:{session.id}"
        await self._cache.set(
            key,
            session.model_dump_json(),
            ttl=self.TTL_SECONDS,
        )
    
    async def is_active(self, session_id: UUID) -> bool | None:
        """Check if session is active (None = cache miss)."""
        key = f"{self.KEY_PREFIX}:{session_id}"
        result = await self._cache.get(key)
        
        if isinstance(result, Failure) or result.value is None:
            return None  # Cache miss
        
        session = Session.model_validate_json(result.value)
        return not session.is_revoked
    
    async def delete(self, session_id: UUID) -> None:
        """Remove session from cache on revocation."""
        key = f"{self.KEY_PREFIX}:{session_id}"
        await self._cache.delete(key)
```

---

## 8. Device Information Parsing

### User Agent Parsing

```python
from src.infrastructure.enrichers import DeviceEnricher

class DeviceEnricher:
    """Parse user agent to human-readable device info."""
    
    def enrich(self, user_agent: str | None) -> str:
        if not user_agent:
            return "Unknown device"
        
        # Parse browser and OS
        # Returns: "Chrome on macOS", "Safari on iPhone", etc.
        browser = self._parse_browser(user_agent)
        os = self._parse_os(user_agent)
        
        return f"{browser} on {os}"
```

### Location Enrichment (IP Geolocation)

```python
from src.infrastructure.enrichers import IPLocationEnricher

class IPLocationEnricher:
    """Resolve IP to location using MaxMind GeoIP2."""
    
    async def enrich(self, ip_address: str) -> LocationEnrichmentResult:
        """Resolve IP address to geographic location.
        
        Returns:
            LocationEnrichmentResult with city, country, coordinates.
            Returns empty for private IPs or if database not available.
        """
        if self._is_private_ip(ip_address):
            return LocationEnrichmentResult()  # No location for private IPs
        
        # Lookup in MaxMind GeoLite2-City database
        response = self._reader.city(ip_address)
        
        return LocationEnrichmentResult(
            location=f"{response.city.name}, {response.country.iso_code}",
            city=response.city.name,
            country_code=response.country.iso_code,
            latitude=response.location.latitude,
            longitude=response.location.longitude,
        )
```

**Behavior**:

- **Private IPs**: Returns empty (no meaningful location for RFC 1918 addresses)
- **Fail-open**: Returns empty on errors (never blocks session creation)
- **Lazy loading**: Database loaded on first lookup
- **Performance**: ~10-20ms for database lookup (in-memory file)

---

## 9. GeoIP2 Setup (IP Geolocation)

### Overview

Dashtam uses **MaxMind GeoLite2-City** database for IP geolocation. This enriches sessions with
geographic information (city, country, coordinates) for public IP addresses.

**Features**:

- **Free**: GeoLite2 database is free with MaxMind account
- **Accurate**: City-level geolocation for most IPs
- **Fast**: In-memory database lookups (~10-20ms)
- **Fail-open**: Sessions create even if geolocation fails
- **Optional**: Geolocation can be disabled without breaking sessions

### Setup Instructions

#### Step 1: Sign Up for MaxMind Account

1. Go to <https://www.maxmind.com/en/geolite2/signup>
2. Create free GeoLite2 account
3. Verify email address

#### Step 2: Download GeoLite2-City Database

1. Log in to MaxMind account
2. Navigate to **Download Files** section
3. Locate **GeoLite2 City**
4. Click **Download GZIP** (e.g., `GeoLite2-City_20251223.tar.gz`)

#### Step 3: Extract and Place Database File

```bash
# Extract tar.gz
tar -xzvf GeoLite2-City_20251223.tar.gz

# Copy .mmdb file to project
cp GeoLite2-City_20251223/GeoLite2-City.mmdb /path/to/Dashtam/data/geoip/
```

**Directory Structure**:

```text
Dashtam/
├── data/
│   └── geoip/
│       └── GeoLite2-City.mmdb  # Database file (~60MB)
├── src/
└── tests/
```

#### Step 4: Configure Database Path

Database path is configured in `.env` files:

```bash
# env/.env.dev
GEOIP_DB_PATH=/app/data/geoip/GeoLite2-City.mmdb

# env/.env.test
GEOIP_DB_PATH=/app/data/geoip/GeoLite2-City.mmdb

# env/.env.prod
GEOIP_DB_PATH=/app/data/geoip/GeoLite2-City.mmdb
```

**Disabling Geolocation** (optional):

```bash
# Set to empty string or comment out
GEOIP_DB_PATH=
```

#### Step 5: Verify Installation

```python
# In Docker container
from src.infrastructure.enrichers import IPLocationEnricher
from src.infrastructure.logging.console_adapter import ConsoleLoggerAdapter

logger = ConsoleLoggerAdapter()
enricher = IPLocationEnricher(logger=logger)

# Test with Google Public DNS
result = await enricher.enrich("8.8.8.8")
print(result.location)  # Should print: "US" or "Mountain View, US"
```

### Database Updates

**Manual Updates** (current approach):

1. Download new database from MaxMind monthly
2. Replace `data/geoip/GeoLite2-City.mmdb`
3. Restart application (database is lazy-loaded)

**Automated Updates** (planned for v1.1.0):

- F7.3: Background job system will automate monthly database updates
- Zero-downtime updates with atomic file replacement

### Configuration Options

```python
# src/core/config.py
class Settings:
    geoip_db_path: str | None = "/app/data/geoip/GeoLite2-City.mmdb"
```

**Behavior by Configuration**:

| `geoip_db_path` | Behavior |
|----------------|----------|
| Valid path | IP geolocation enabled |
| `None` or empty | IP geolocation disabled (location always empty) |
| Invalid path | Warning logged, geolocation disabled |

### Volume Mounts (Docker)

The database file is accessible in all Docker environments:

```yaml
# compose/docker-compose.dev.yml
services:
  app:
    volumes:
      - ..:/app  # Mounts entire project (includes data/geoip/)
```

**Path Mapping**:

- **Host**: `/Users/you/Dashtam/data/geoip/GeoLite2-City.mmdb`
- **Container**: `/app/data/geoip/GeoLite2-City.mmdb`

---

## 10. Testing Sessions

### Unit Testing Handler

```python
import pytest
from unittest.mock import AsyncMock

async def test_create_session_success():
    session_repo = AsyncMock()
    session_cache = AsyncMock()
    device_enricher = AsyncMock()
    device_enricher.enrich.return_value = "Chrome on macOS"
    
    handler = CreateSessionHandler(
        session_repo=session_repo,
        session_cache=session_cache,
        device_enricher=device_enricher,
        event_bus=AsyncMock(),
    )
    
    result = await handler.handle(CreateSession(
        user_id=uuid7(),
        ip_address="192.168.1.1",
        user_agent="Mozilla/5.0...",
    ))
    
    assert isinstance(result, Success)
    session_repo.save.assert_called_once()
    session_cache.set.assert_called_once()
```

### API Testing

```python
def test_list_sessions(client: TestClient, auth_headers, test_session):
    response = client.get(
        "/api/v1/sessions",
        headers=auth_headers,
    )
    
    assert response.status_code == 200
    data = response.json()
    assert len(data["sessions"]) >= 1
    assert any(s["id"] == str(test_session.id) for s in data["sessions"])

def test_revoke_session(client: TestClient, auth_headers, other_session):
    response = client.delete(
        f"/api/v1/sessions/{other_session.id}",
        headers=auth_headers,
    )
    
    assert response.status_code == 204
```

---

## 11. Common Patterns

### Pattern 1: Get Current Session from JWT

```python
from src.presentation.routers.api.middleware.auth_middleware import (
    get_current_user,
    get_current_session_id,
)

@router.get("/sessions/current")
async def get_current_session(
    current_user: User = Depends(get_current_user),
    session_id: UUID = Depends(get_current_session_id),
    session_repo: SessionRepository = Depends(get_session_repo),
) -> SessionResponse:
    """Get details of current session."""
    session = await session_repo.find_by_id(session_id)
    return SessionResponse.from_entity(session)
```

### Pattern 2: Update Last Activity

```python
async def update_session_activity(
    session_id: UUID,
    session_cache: RedisSessionCache,
) -> None:
    """Update last_activity timestamp (called on token refresh)."""
    session = await session_cache.get(session_id)
    if session:
        session.last_activity = datetime.now(UTC)
        await session_cache.set(session)
```

### Pattern 3: Admin View All Sessions

```python
@router.get("/admin/users/{user_id}/sessions")
async def admin_list_user_sessions(
    user_id: UUID,
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_role(UserRole.ADMIN)),
    handler: ListSessionsHandler = Depends(...),
) -> list[SessionResponse]:
    """Admin: List all sessions for any user."""
    result = await handler.handle(ListSessions(
        user_id=user_id,
        include_revoked=True,  # Show all including revoked
    ))
    return [SessionResponse.from_entity(s) for s in result.value]
```

---

## 12. Troubleshooting

### Session not found after login

1. Check session was saved to database
2. Check session was cached in Redis
3. Check session_id in JWT payload matches

### Token refresh fails with "session_revoked"

1. Check session.is_revoked in database
2. Check if password was changed (revokes all sessions)
3. Check if admin revoked sessions
4. Check Redis cache is consistent with database

### Session limit not enforced

1. Check user's session_tier is set correctly
2. Check SESSION_TIER_LIMITS configuration
3. Check count_active query filters is_revoked=False

### Location is always empty/null

1. **Check database file exists**:

   ```bash
   # In container
   ls -lh /app/data/geoip/GeoLite2-City.mmdb
   ```

2. **Check GEOIP_DB_PATH setting**:

   ```bash
   echo $GEOIP_DB_PATH
   ```

3. **Check logs for warnings**:

   ```text
   "GeoIP database file not found"
   "GeoIP database not configured"
   "Failed to initialize GeoIP database"
   ```

4. **Verify with test IP**:

   ```python
   result = await enricher.enrich("8.8.8.8")  # Google DNS
   # Should return location if working
   ```

5. **Check IP is public** (not private):
   - Private IPs (192.168.x.x, 10.x.x.x, 127.0.0.1) always return empty location
   - Use public IP for testing (e.g., 8.8.8.8)

### Geolocation is slow (>100ms)

1. **Check database is being reused** (lazy loading):
   - First lookup: ~20-50ms (loads database)
   - Subsequent lookups: ~5-10ms (reuses loaded database)

2. **Check disk I/O**:
   - Database file should be cached in memory by OS
   - SSD recommended for Docker volume mounts

3. **Check Docker volume mount performance**:
   - Consider copying database into container image for production

### Tests skip geolocation tests

**Expected behavior** - Tests skip if database not available:

```text
test_public_ip_lookup_with_real_database SKIPPED
test_ip_not_in_database_returns_empty SKIPPED
```

**To run these tests**:

1. Ensure database exists at `/app/data/geoip/GeoLite2-City.mmdb` in test container
2. Database is automatically mounted via project directory volume
3. Tests will pass if database accessible, skip if not

---

**Created**: 2025-12-05 | **Last Updated**: 2025-12-25
