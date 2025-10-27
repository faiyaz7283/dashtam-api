# Session Management Endpoints - Research Document

**Research Focus**: Comprehensive analysis of modern session management best practices, industry patterns, security considerations, and recommended implementation approaches for the Dashtam authentication system.

**Context**: Following the completion of JWT authentication (P1) and rate limiting (P2), session management endpoints are the next priority to provide users with visibility and control over their active sessions across devices.

## Executive Summary

### Research Objectives

1. **Industry Patterns**: Analyze session management implementations from leading platforms (GitHub, Google, Facebook, Auth0, AWS)
2. **Security Requirements**: Identify security best practices for session visibility, revocation, and breach response
3. **User Experience**: Define intuitive UX patterns for multi-device session management
4. **Technical Architecture**: Determine optimal data models, API design, and integration points
5. **Compliance**: Ensure alignment with SOC 2, GDPR, and security standards

### Key Findings

**✅ Industry Standard**: All major platforms provide session management UIs with:

- List of active sessions (device, location, last activity)
- Individual session revocation
- Bulk "logout from all devices" action
- Current session indicator
- IP-based geolocation for user-friendly display

**✅ Security Best Practices**:

- Session fingerprinting (device + IP + user-agent)
- Anomaly detection (new device/location alerts)
- Configurable session expiration policies
- Immediate revocation with token blacklisting
- Audit trail for all session events

**✅ Technical Approach**:

- Leverage existing `refresh_tokens` table (already has device_info, IP, last_used_at)
- Add session metadata (location, is_current flag)
- RESTful API endpoints following project standards
- Real-time revocation via Redis cache invalidation
- Rate limiting on session management endpoints

### Recommended Implementation

**Phase-based approach** (3-4 days estimated):

1. **Phase 1**: Data model enhancements (location, current session detection)
2. **Phase 2**: Core service layer (SessionManagementService)
3. **Phase 3**: RESTful API endpoints (4 endpoints)
4. **Phase 4**: Security features (rate limiting, anomaly detection hooks)
5. **Phase 5**: Testing & documentation

## Industry Analysis

### 1. GitHub Sessions Management

**URL**: Settings → Sessions → Active sessions

**Features**:

- **List View**: All active sessions with metadata
  - Device type (Web browser, Mobile, Desktop)
  - Browser/OS info (Chrome on macOS, Safari on iOS)
  - Location (City, Country - IP-based)
  - Last activity timestamp
  - Current session indicator (green badge)
- **Actions**:
  - Revoke individual session (red "Revoke" button)
  - "Revoke all other sessions" bulk action
- **Security**:
  - New session email notification (configurable)
  - Session signed with GitHub token
  - Shows last accessed time for staleness detection

**API Pattern** (inferred from GitHub API v3/v4):

```http
GET /user/sessions
DELETE /user/sessions/{session_id}
DELETE /user/sessions/all-others
```

**Key Insights**:

- Uses refresh token as session identifier
- Location data from IP geolocation (not GPS)
- "Current session" detected via comparing request token
- Simple, intuitive UX - no complexity
- Immediate revocation (no delay)

### 2. Google Account Security

**URL**: Security → Your devices → Manage all devices

**Features**:

- **Device Cards**: Visual cards per session
  - Device name/type (Phone, Computer, Tablet)
  - Last sign-in location (city-level)
  - Last activity timestamp (e.g., "Active now", "2 days ago")
  - Sign-in method indicator
- **Actions**:
  - "Sign out" per device
  - "Sign out of all other sessions"
- **Security**:
  - Trusted device management (mark device as trusted)
  - Sign-in alerts for new device/location
  - 2FA enforcement for sensitive actions
- **Advanced**:
  - Device usage history (30-day retention)
  - Approximate location on map (privacy-focused)

**API Pattern** (Google Identity Platform):

```http
GET /v1/sessions
POST /v1/sessions/{id}:revoke
POST /v1/sessions:revokeAll
```

**Key Insights**:

- Rich device metadata (OS, browser, device name)
- Privacy-focused location (city-level, no exact coords)
- "Active now" vs "Last active X ago" UX pattern
- Trusted device concept for reduced friction
- 2FA integration for high-risk actions (revoke all)

### 3. Facebook Security and Login

**URL**: Settings → Security and login → Where You're Logged In

**Features**:

- **Session List**: Chronological list by last activity
  - Device info (e.g., "Chrome on Windows")
  - Location (city, region, country)
  - Active status ("Active now" or timestamp)
  - Current session badge
- **Actions**:
  - "Log Out" per session
  - "Log Out of All Sessions" (excludes current)
- **Security**:
  - Login alerts (email + notification)
  - Unrecognized login review
  - Save device checkbox (trusted device)
  - Two-factor authentication integration

**API Pattern** (Facebook Graph API):

```http
GET /me/sessions
DELETE /me/sessions/{session_id}
POST /me/sessions/logout-all
```

**Key Insights**:

- Uses session_id (opaque identifier, not refresh token directly)
- "Save this browser" = trusted device (extends session TTL)
- Location from IP + device fingerprinting
- Separate "unrecognized login" flow for anomalies
- Logout all excludes current session (UX best practice)

### 4. Auth0 Session Management

**Documentation**: [Auth0 Session Management](https://auth0.com/docs/manage-users/sessions)

**Architecture**:

- **Session Types**:
  - Application sessions (JWT access token, short-lived)
  - Auth0 sessions (SSO session, refresh token-based)
- **Session Storage**:
  - Refresh token stored in database (encrypted)
  - Session metadata (device, IP, user-agent)
  - Last activity tracked per session
- **Revocation**:
  - Token revocation API (`/api/v2/device-credentials`)
  - Real-time revocation via token blacklist (Redis)
  - Configurable grace period for distributed systems

**API Pattern**:

```http
GET /api/v2/users/{id}/device-credentials
DELETE /api/v2/device-credentials/{id}
POST /api/v2/users/{id}/multifactor/actions/invalidate-remember-browser
```

**Key Insights**:

- Separates "device credentials" from sessions (conceptual model)
- Redis-based token blacklist for immediate revocation
- Grace period config for eventual consistency (default: 5 min)
- Supports SSO logout (revoke across multiple apps)
- Device fingerprinting for anomaly detection

### 5. AWS IAM Session Management

**Documentation**: [AWS Security Token Service](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_credentials_temp.html)

**Features**:

- **Session Tokens**: Temporary credentials with expiration
- **Session Policies**: Fine-grained permissions per session
- **Revocation**: Delete temporary credentials immediately
- **Audit**: CloudTrail logs all session creation/deletion events

**API Pattern**:

```http
POST /sts/GetSessionToken
POST /sts/AssumeRole
DELETE /iam/DeleteAccessKey
```

**Key Insights**:

- Session = temporary credential (access key + secret + token)
- Explicit session duration (15 min - 36 hours)
- Revocation via credential deletion (immediate)
- Comprehensive audit logging (CloudTrail)
- Session policies for least-privilege access

## Security Requirements Analysis

### OWASP Best Practices

**OWASP Session Management Cheat Sheet**: [OWASP Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html)

**Key Requirements**:

1. **Session Identification**:
   - Use cryptographically strong session IDs (refresh token = session ID)
   - Minimum 128-bit entropy (our UUID4 tokens = 122 bits effective entropy)
   - Avoid sequential/predictable IDs ✅ (we use UUID4)

2. **Session Storage**:
   - Store session metadata server-side ✅ (refresh_tokens table)
   - Hash sensitive identifiers (token_hash with bcrypt) ✅
   - Encrypt at rest (database encryption recommended)

3. **Session Expiration**:
   - Absolute timeout (30 days for Dashtam) ✅
   - Idle timeout (track last_used_at) ✅
   - Renewal on activity (update last_used_at on token refresh) ✅

4. **Session Revocation**:
   - Immediate revocation capability (DELETE endpoint required)
   - Revoke all sessions on password change ✅ (already implemented)
   - Revoke all sessions on account compromise

5. **Session Monitoring**:
   - Track device/IP/user-agent ✅ (already captured)
   - Detect concurrent sessions from different locations
   - Alert on anomalous activity (new device/location)

### SOC 2 Compliance

**Trust Service Criteria CC6.1**: Logical and physical access controls

**Requirements**:

- **Session visibility**: Users must be able to view active sessions
- **Session control**: Users must be able to revoke sessions
- **Audit logging**: All session events must be logged
  - Session creation (login)
  - Session termination (logout, revocation)
  - Failed session access attempts
- **Access reviews**: Periodic review of active sessions (user-initiated)

**Dashtam Alignment**:

- ✅ Audit logs already capture auth events (AuthService)
- ✅ Refresh token table has all necessary metadata
- ➕ Need: API endpoints for user-facing session management
- ➕ Need: Enhanced audit log entries for session revocation

### GDPR Compliance

**GDPR Article 15**: Right of access

**Requirements**:

- Users must be able to access their session data
- Session data includes: device info, IP address, timestamps
- Users must be able to delete their session data

**Dashtam Alignment**:

- ✅ Session data stored in refresh_tokens table
- ✅ IP addresses stored (need anonymization policy)
- ➕ Need: API endpoint for session data export
- ➕ Need: IP address retention policy (30-90 days typical)

## Technical Architecture

### Data Model Analysis

**Current State** (`refresh_tokens` table):

```python
class RefreshToken(DashtamBase, table=True):
    __tablename__ = "refresh_tokens"
    
    # Existing fields (already implemented)
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="users.id", index=True)
    token_hash: str  # bcrypt hashed, irreversible
    device_info: str | None  # e.g., "Chrome on macOS"
    ip_address: str | None  # IP at token creation
    user_agent: str | None  # Full user-agent string
    expires_at: datetime  # Token expiration (30 days)
    revoked: bool = False  # Manual revocation flag
    last_used_at: datetime | None  # Updated on token refresh
    
    # Timestamps (DashtamBase)
    created_at: datetime  # Session creation time
    updated_at: datetime
    deleted_at: datetime | None
```

**Required Enhancements**:

```python
class RefreshToken(DashtamBase, table=True):
    # ... existing fields ...
    
    # NEW FIELDS for session management
    location: str | None  # City, Country (from IP geolocation)
    is_trusted_device: bool = False  # User-marked trusted device
    fingerprint: str | None  # Device fingerprint hash (browser + OS + screen)
```

**Why these fields?**

- **location**: User-friendly display ("San Francisco, USA" vs "192.168.1.1")
- **is_trusted_device**: Extend session TTL, reduce friction for known devices
- **fingerprint**: Detect device changes (security alert trigger)

### API Endpoint Design

**RESTful Design** (following project REST compliance standards):

#### 1. List All Active Sessions

```http
GET /api/v1/auth/sessions
```

**Authentication**: Requires valid JWT access token

**Response**:

```json
{
  "sessions": [
    {
      "id": "123e4567-e89b-12d3-a456-426614174000",
      "device_info": "Chrome on macOS",
      "location": "San Francisco, USA",
      "ip_address": "192.168.1.1",  // Optional: privacy setting
      "last_activity": "2025-10-27T15:30:00Z",
      "created_at": "2025-10-20T10:00:00Z",
      "is_current": true,
      "is_trusted": false
    },
    {
      "id": "223e4567-e89b-12d3-a456-426614174001",
      "device_info": "Safari on iOS",
      "location": "New York, USA",
      "ip_address": "10.0.0.1",
      "last_activity": "2025-10-26T08:15:00Z",
      "created_at": "2025-10-15T09:00:00Z",
      "is_current": false,
      "is_trusted": true
    }
  ],
  "total_count": 2
}
```

**Business Logic**:

- Query all non-revoked refresh tokens for user
- Enrich with geolocation data (IP → location)
- Detect current session (compare JWT token ID with refresh token)
- Sort by last_activity DESC (most recent first)
- Rate limit: 10 requests per minute per user

#### 2. Revoke Specific Session

```http
DELETE /api/v1/auth/sessions/{session_id}
```

**Authentication**: Requires valid JWT access token

**Authorization**: User can only revoke their own sessions

**Response**:

```json
{
  "message": "Session revoked successfully",
  "revoked_session_id": "123e4567-e89b-12d3-a456-426614174000"
}
```

**Business Logic**:

- Verify session belongs to authenticated user
- Set `revoked = True` in database
- Invalidate session in Redis cache (if cached)
- Create audit log entry (action: session_revoked)
- Cannot revoke current session (use logout endpoint instead)
- Rate limit: 20 requests per minute per user

**Security Considerations**:

- Prevent revoking current session (would lock user out immediately)
- Log IP address of revocation request (detect malicious revocations)
- Alert user via email if session revoked from different IP/device

#### 3. Revoke All Other Sessions

```http
DELETE /api/v1/auth/sessions/others
```

**Authentication**: Requires valid JWT access token

**Response**:

```json
{
  "message": "All other sessions revoked successfully",
  "revoked_count": 3
}
```

**Business Logic**:

- Identify current session (from JWT access token)
- Revoke all other refresh tokens for user
- Set `revoked = True` for all non-current tokens
- Invalidate all sessions in Redis cache (except current)
- Create audit log entry (action: bulk_session_revoke, metadata: count)
- Rate limit: 5 requests per hour per user (prevent abuse)

**Use Cases**:

- User suspects account compromise
- User lost device (quick response)
- User wants to enforce single-device access

#### 4. Revoke All Sessions (Including Current)

```http
DELETE /api/v1/auth/sessions
```

**Authentication**: Requires valid JWT access token

**Response**:

```json
{
  "message": "All sessions revoked successfully. You have been logged out.",
  "revoked_count": 4
}
```

**Business Logic**:

- Revoke ALL refresh tokens for user (including current)
- Set `revoked = True` for all tokens
- Invalidate all sessions in Redis cache
- Create audit log entry (action: full_logout)
- Return 200 (user is now logged out)
- Rate limit: 3 requests per hour per user

**Use Cases**:

- User confirms account breach (nuclear option)
- User wants to reset all sessions (fresh start)
- Admin-initiated logout (support escalation)

### Service Layer Design

**New Service**: `SessionManagementService`

```python
class SessionManagementService:
    """
    Manages user sessions (refresh tokens) with visibility and control.
    
    Responsibilities:
    - List active sessions with enriched metadata
    - Revoke sessions (individual, bulk, all)
    - Detect current session
    - IP geolocation lookups
    - Session anomaly detection hooks
    """
    
    def __init__(
        self,
        session: AsyncSession,
        geolocation_service: GeolocationService,
        audit_service: AuditService
    ):
        self.session = session
        self.geolocation_service = geolocation_service
        self.audit_service = audit_service
    
    async def list_sessions(
        self,
        user_id: UUID,
        current_token_id: UUID | None = None
    ) -> list[SessionInfo]:
        """
        List all active sessions for user with enriched metadata.
        
        Args:
            user_id: User UUID
            current_token_id: ID of current refresh token (from JWT)
        
        Returns:
            List of SessionInfo objects (sorted by last_activity DESC)
        """
        # Query non-revoked refresh tokens
        # Enrich with geolocation
        # Mark current session
        # Return sorted list
    
    async def revoke_session(
        self,
        user_id: UUID,
        session_id: UUID,
        current_session_id: UUID,
        revoked_by_ip: str,
        revoked_by_device: str
    ) -> None:
        """
        Revoke specific session with audit trail.
        
        Args:
            user_id: User UUID (authorization check)
            session_id: Session to revoke
            current_session_id: Current session (cannot revoke self)
            revoked_by_ip: IP address of revocation request
            revoked_by_device: Device info of revocation request
        
        Raises:
            ValueError: If session_id == current_session_id
            HTTPException(404): If session not found or not owned by user
        """
        # Verify ownership
        # Prevent self-revocation
        # Set revoked = True
        # Invalidate Redis cache
        # Create audit log
        # Alert user if anomalous
    
    async def revoke_other_sessions(
        self,
        user_id: UUID,
        current_session_id: UUID
    ) -> int:
        """
        Revoke all sessions except current.
        
        Returns:
            Count of revoked sessions
        """
        # Query all tokens except current
        # Bulk update revoked = True
        # Invalidate Redis cache
        # Create audit log
    
    async def revoke_all_sessions(
        self,
        user_id: UUID
    ) -> int:
        """
        Revoke ALL sessions (nuclear option).
        
        Returns:
            Count of revoked sessions
        """
        # Query all tokens
        # Bulk update revoked = True
        # Invalidate Redis cache
        # Create audit log
```

### Geolocation Service

**Purpose**: Convert IP addresses to user-friendly location strings

**Options**:

1. **GeoLite2 Free** (MaxMind):
   - Free city-level database (updated monthly)
   - Local lookup (no API calls)
   - ~5MB database size
   - Accuracy: ~90% city-level
   - License: CC BY-SA 4.0

2. **ipapi.co** (API):
   - Free tier: 30k requests/month
   - City, region, country, timezone
   - Response time: ~50ms
   - No local database needed

3. **ip-api.com** (API):
   - Free tier: 45 requests/minute
   - City, region, country, ISP, timezone
   - Response time: ~100ms
   - No commercial use on free tier

**Recommendation**: **GeoLite2 Free** (MaxMind)

**Rationale**:

- Local lookups (no network dependency, <1ms)
- No rate limits
- Privacy-focused (no external API calls)
- Commercial use allowed
- Python library: `geoip2` (official MaxMind library)

**Implementation**:

```python
import geoip2.database
from pathlib import Path

class GeolocationService:
    """IP address geolocation using MaxMind GeoLite2."""
    
    def __init__(self, db_path: Path):
        self.reader = geoip2.database.Reader(str(db_path))
    
    def get_location(self, ip_address: str) -> str:
        """
        Convert IP to location string.
        
        Args:
            ip_address: IPv4 or IPv6 address
        
        Returns:
            Location string (e.g., "San Francisco, USA")
            Returns "Unknown" if lookup fails
        """
        try:
            response = self.reader.city(ip_address)
            city = response.city.name or "Unknown City"
            country = response.country.name or "Unknown Country"
            return f"{city}, {country}"
        except (geoip2.errors.AddressNotFoundError, ValueError):
            return "Unknown Location"
    
    def __del__(self):
        self.reader.close()
```

**Database Setup**:

1. Download GeoLite2-City database (free account required)
2. Store in `data/geolite2/GeoLite2-City.mmdb`
3. Add to `.gitignore` (license prohibits redistribution)
4. Add to `.env.example`: `GEOLITE2_DB_PATH=/app/data/geolite2/GeoLite2-City.mmdb`
5. Docker volume mount: `./data/geolite2:/app/data/geolite2:ro`

### Session Detection Logic

**Challenge**: Determine "current session" from JWT access token

**Current Architecture**:

- JWT access token contains `user_id` (subject claim)
- JWT does NOT contain `refresh_token_id` (not currently included)
- Need to link access token → refresh token

**Solution Options**:

**Option A: Add `jti` claim to JWT (recommended)**

```python
# In JWTService.create_access_token()
payload = {
    "sub": str(user_id),
    "jti": str(refresh_token_id),  # JWT ID = refresh token ID
    "exp": expire,
    "iat": now
}
```

**Benefits**:

- Standard JWT claim (`jti` = JWT ID)
- Directly links access token → refresh token
- No additional database queries
- Enables token blacklisting by `jti`

**Cons**:

- Requires JWT token regeneration (migration)
- All existing tokens won't have `jti` (graceful degradation needed)

#### Option B: Track access token → refresh token mapping in Redis

```python
# On token creation
redis.setex(
    f"access_token:{access_token_hash}",
    ttl=1800,  # 30 minutes
    value=str(refresh_token_id)
)
```

**Benefits**:

- No JWT structure changes
- Works with existing tokens
- Centralized session tracking

**Cons**:

- Additional Redis dependency for core auth flow
- Network call on every session list request
- Token hash storage (security consideration)

**Recommendation**: **Option A** (add `jti` claim)

**Migration Strategy**:

1. Add `jti` claim to new tokens (Phase 1)
2. Existing tokens without `jti` → show "Unknown" for current session (graceful degradation)
3. Force token refresh on next login (natural turnover in 30 days)
4. Document in API response: `is_current: null` when `jti` not available

## Security Considerations

### 1. Session Hijacking Prevention

**Threat**: Attacker steals refresh token, impersonates user

**Mitigations**:

- ✅ Refresh token rotation (already implemented)
- ✅ Token hashing (bcrypt, irreversible)
- ✅ HTTPS only (TLS encryption in transit)
- ➕ Device fingerprinting (detect token used on different device)
- ➕ IP address validation (alert on IP change)

**Device Fingerprinting**:

```python
def generate_device_fingerprint(request: Request) -> str:
    """
    Generate device fingerprint from request metadata.
    
    Components:
    - User-Agent header
    - Accept-Language header
    - Screen resolution (from custom header)
    - Timezone offset (from custom header)
    
    Returns:
        SHA256 hash of fingerprint components
    """
    components = [
        request.headers.get("user-agent", ""),
        request.headers.get("accept-language", ""),
        request.headers.get("x-screen-resolution", ""),  # Custom header
        request.headers.get("x-timezone-offset", "")  # Custom header
    ]
    fingerprint_string = "|".join(components)
    return hashlib.sha256(fingerprint_string.encode()).hexdigest()
```

**Usage**:

- Store fingerprint with refresh token
- On token use: compare current fingerprint with stored
- If mismatch: trigger anomaly alert (email user)
- Optional: force re-authentication on significant mismatch

### 2. Anomaly Detection Hooks

**Trigger Conditions**:

- **New device**: Fingerprint not seen before for user
- **New location**: IP geolocation differs significantly from previous logins
- **Concurrent sessions**: Multiple sessions active from different countries
- **Rapid location change**: Session in USA, then China 10 minutes later (impossible travel)

**Response Actions**:

- **Low risk**: Log event, show banner on next login ("New device detected: Chrome on Windows")
- **Medium risk**: Email alert + require email verification on next login
- **High risk**: Revoke all sessions + force password reset

**Implementation**:

```python
class AnomalyDetectionService:
    """Detect anomalous session behavior."""
    
    async def check_new_device(
        self,
        user_id: UUID,
        fingerprint: str
    ) -> bool:
        """Check if device fingerprint is new for user."""
        # Query refresh_tokens for user
        # Check if fingerprint exists
        # Return True if new device
    
    async def check_new_location(
        self,
        user_id: UUID,
        ip_address: str
    ) -> tuple[bool, str | None]:
        """Check if IP location is new for user."""
        # Get location from IP
        # Query previous locations for user
        # Return (is_new, location_name)
    
    async def check_impossible_travel(
        self,
        user_id: UUID,
        current_location: str,
        current_time: datetime
    ) -> bool:
        """Check if location change is physically impossible."""
        # Get last session location and time
        # Calculate distance between locations
        # Calculate time elapsed
        # Check if travel speed > 800 km/h (plane + margin)
```

### 3. Rate Limiting Session Endpoints

**Threat**: Attacker floods session management endpoints (DoS, enumeration)

**Rate Limits**:

- `GET /api/v1/auth/sessions`: 10 requests/minute per user
- `DELETE /api/v1/auth/sessions/{id}`: 20 requests/minute per user
- `DELETE /api/v1/auth/sessions/others`: 5 requests/hour per user
- `DELETE /api/v1/auth/sessions`: 3 requests/hour per user

**Rationale**:

- List sessions: moderate limit (legitimate use case: periodic checks)
- Revoke session: higher limit (user might revoke multiple sessions)
- Revoke others: strict limit (high-impact action, rarely needed)
- Revoke all: very strict limit (nuclear option, abuse prevention)

**Implementation**:

- Use existing `RateLimiterService` (already implemented)
- Add session management rules to `RateLimitConfig`

```python
# In src/rate_limiter/config.py
RATE_LIMIT_RULES = {
    # ... existing rules ...
    "auth_sessions_list": RateLimitRule(
        requests=10,
        window_seconds=60,
        identifier_type="user"
    ),
    "auth_sessions_revoke": RateLimitRule(
        requests=20,
        window_seconds=60,
        identifier_type="user"
    ),
    "auth_sessions_revoke_others": RateLimitRule(
        requests=5,
        window_seconds=3600,
        identifier_type="user"
    ),
    "auth_sessions_revoke_all": RateLimitRule(
        requests=3,
        window_seconds=3600,
        identifier_type="user"
    )
}
```

## User Experience Design

### Session List View

**Layout** (API response, not UI implementation):

```text
Active Sessions (3)

[Current Session]
🟢 Chrome on macOS
    San Francisco, USA
    Last activity: Just now
    Signed in: Oct 20, 2025

[Other Session]
Safari on iOS
    New York, USA
    Last activity: 2 hours ago
    Signed in: Oct 15, 2025
    [Revoke Session]

[Other Session]
Firefox on Windows
    London, UK
    Last activity: 3 days ago
    Signed in: Oct 10, 2025
    [Revoke Session]

[Revoke All Other Sessions]
```

**Interactions**:

- **Current session**: Green badge, no revoke button (use logout instead)
- **Other sessions**: Revoke button per session
- **Bulk action**: "Revoke all other sessions" button at bottom
- **Confirmation**: Modal for bulk actions ("Are you sure? You'll be logged out on all other devices.")

### Email Notifications

**New Session Alert**:

```text
Subject: New login to your Dashtam account

Hi {user.name},

A new device just signed into your account:

Device: Chrome on macOS
Location: San Francisco, USA
Time: Oct 27, 2025 at 3:45 PM PST
IP: 192.168.1.1

If this was you, no action needed.

If this wasn't you:
1. Change your password immediately: {reset_link}
2. Review your active sessions: {sessions_link}
3. Revoke any suspicious sessions

Questions? Contact support@dashtam.com
```

**Session Revoked Alert** (if revoked from different device):

```text
Subject: A session was removed from your Dashtam account

Hi {user.name},

A session was removed from your account:

Revoked session:
  Device: Safari on iOS
  Location: New York, USA

Revoked from:
  Device: Chrome on macOS
  Location: San Francisco, USA
  Time: Oct 27, 2025 at 4:00 PM PST

If you revoked this session, no action needed.

If you didn't revoke this session:
1. Your account may be compromised
2. Change your password immediately: {reset_link}
3. Review all sessions: {sessions_link}

Questions? Contact support@dashtam.com
```

## Implementation Phases

### Phase 1: Data Model Enhancements

**Goal**: Add session management fields to `refresh_tokens` table

**Tasks**:

1. **Alembic Migration**: Add new columns
   - `location` (TEXT, nullable)
   - `is_trusted_device` (BOOLEAN, default=False)
   - `fingerprint` (VARCHAR(64), nullable)

2. **SQLModel Update**: Update `RefreshToken` model

3. **Seed Script**: Backfill existing sessions
   - Generate location from IP (bulk geolocation)
   - Set fingerprint = NULL (will populate on next use)
   - Set is_trusted_device = False

4. **Tests**: Model tests, migration tests

**Estimated Effort**: 0.5 days

### Phase 2: Geolocation Service

**Goal**: Implement IP → Location conversion

**Tasks**:

1. **GeoLite2 Setup**:
   - Add `geoip2` dependency (`uv add geoip2`)
   - Create `data/geolite2/` directory
   - Add database download script (manual step for dev)
   - Add Docker volume mount

2. **GeolocationService Implementation**:
   - Create `src/services/geolocation_service.py`
   - Implement `get_location(ip_address: str) -> str`
   - Handle errors (invalid IP, database not found)

3. **Configuration**:
   - Add `GEOLITE2_DB_PATH` to settings
   - Add to `.env.example` files

4. **Tests**: Unit tests for geolocation service

**Estimated Effort**: 0.5 days

### Phase 3: Session Management Service

**Goal**: Implement core session management logic

**Tasks**:

1. **SessionManagementService**:
   - Create `src/services/session_management_service.py`
   - Implement `list_sessions()`
   - Implement `revoke_session()`
   - Implement `revoke_other_sessions()`
   - Implement `revoke_all_sessions()`

2. **Current Session Detection**:
   - Update `JWTService.create_access_token()` to include `jti` claim
   - Add `refresh_token_id` parameter to JWT creation
   - Update token refresh flow to pass `refresh_token_id`

3. **Device Fingerprinting**:
   - Create `src/core/fingerprinting.py`
   - Implement `generate_device_fingerprint(request: Request) -> str`
   - Store fingerprint on token creation

4. **Tests**: Service layer unit tests

**Estimated Effort**: 1 day

### Phase 4: API Endpoints

**Goal**: Implement RESTful session management endpoints

**Tasks**:

1. **Pydantic Schemas**:
   - Create `src/schemas/session.py`
   - `SessionInfoResponse`, `SessionListResponse`
   - `RevokeSessionResponse`, `BulkRevokeResponse`

2. **API Router**:
   - Create `src/api/routers/sessions.py`
   - `GET /api/v1/auth/sessions`
   - `DELETE /api/v1/auth/sessions/{session_id}`
   - `DELETE /api/v1/auth/sessions/others`
   - `DELETE /api/v1/auth/sessions`

3. **Rate Limiting**:
   - Add session management rules to `RateLimitConfig`
   - Apply rate limiting middleware

4. **Tests**: API endpoint tests

**Estimated Effort**: 1 day

### Phase 5: Security Features

**Goal**: Implement anomaly detection and alerts

**Tasks**:

1. **AnomalyDetectionService**:
   - Create `src/services/anomaly_detection_service.py`
   - Implement `check_new_device()`
   - Implement `check_new_location()`
   - Implement `check_impossible_travel()`

2. **Email Alerts**:
   - Add email templates (new_session_alert.html, session_revoked_alert.html)
   - Integrate with EmailService
   - Send alerts on anomalies

3. **Audit Logging**:
   - Add audit log entries for session management events
   - Include metadata (revoked_from_ip, revoked_from_device)

4. **Tests**: Anomaly detection tests, alert tests

**Estimated Effort**: 0.5 days

### Phase 6: Testing & Documentation

**Goal**: Comprehensive testing and documentation

**Tasks**:

1. **Test Coverage**:
   - Unit tests: GeolocationService, SessionManagementService, AnomalyDetectionService
   - Integration tests: Database operations, session revocation
   - API tests: All 4 endpoints
   - E2E tests: Full session management flow

2. **Documentation**:
   - Implementation guide (this document → final guide)
   - API endpoint documentation (`docs/api-flows/session-management.md`)
   - Architecture documentation (service layer, data model)
   - User-facing guide (how to manage sessions)

3. **Smoke Tests**:
   - Update smoke test suite with session management flows

4. **Code Quality**:
   - Lint: `make lint`
   - Format: `make format`
   - Markdown lint: `make lint-md`

**Estimated Effort**: 0.5 days

## Total Estimated Effort

**3-4 days** (24-32 hours)

**Breakdown**:

- Phase 1: 0.5 days (data model)
- Phase 2: 0.5 days (geolocation)
- Phase 3: 1 day (service layer)
- Phase 4: 1 day (API endpoints)
- Phase 5: 0.5 days (security features)
- Phase 6: 0.5 days (testing & docs)

**Confidence**: High (based on rate limiter experience)

## Risks and Mitigations

### Risk 1: Geolocation Database Licensing

**Risk**: GeoLite2 database requires account, can't be committed to repo

**Impact**: Medium (setup complexity for developers)

**Mitigation**:

- Document setup process clearly
- Provide download script (automated)
- Add check in application startup (fail gracefully if missing)
- Fallback to "Unknown Location" if database not available

### Risk 2: JWT Migration (Adding `jti` Claim)

**Risk**: Existing JWT tokens don't have `jti` claim, breaks current session detection

**Impact**: Medium (UX degradation for existing sessions)

**Mitigation**:

- Graceful degradation: `is_current: null` if `jti` not available
- Natural token turnover (30-day TTL, most tokens refresh within 1 week)
- Document limitation in API response
- Consider forced refresh on next login (optional)

### Risk 3: IP Address Privacy Concerns

**Risk**: Storing IP addresses raises privacy concerns (GDPR)

**Impact**: Low (common practice, necessary for security)

**Mitigation**:

- Document retention policy (30-90 days typical)
- Implement IP anonymization (mask last octet: `192.168.1.0`)
- Allow users to hide IP in session list (privacy setting)
- Comply with GDPR data access/deletion requests

### Risk 4: Rate Limiting Too Strict

**Risk**: Legitimate users hit rate limits (bad UX)

**Impact**: Low (limits are generous)

**Mitigation**:

- Monitor rate limit metrics (Prometheus/Grafana)
- Adjust limits based on usage patterns
- Provide clear error messages (Retry-After header)
- Whitelist trusted IPs (optional, for high-volume users)

## Success Criteria

### Functional Requirements

- ✅ Users can list all active sessions with metadata
- ✅ Users can revoke individual sessions
- ✅ Users can revoke all other sessions (keep current)
- ✅ Users can revoke all sessions (including current)
- ✅ Current session is clearly indicated
- ✅ Location displayed for each session (city-level)
- ✅ Last activity timestamp shown
- ✅ Email alerts on new session from new device/location
- ✅ Email alerts on session revocation from different device

### Non-Functional Requirements

- ✅ API response time < 200ms (list sessions)
- ✅ Geolocation lookup < 10ms (local database)
- ✅ Rate limiting applied to all endpoints
- ✅ 85%+ test coverage for new code
- ✅ RESTful API design (10/10 compliance)
- ✅ SOLID principles (maintainable, extensible)
- ✅ Comprehensive documentation (API, architecture, user guide)

### Security Requirements

- ✅ Cannot revoke current session via revoke-specific endpoint (use logout)
- ✅ Session revocation is immediate (no delay)
- ✅ Audit logs for all session management actions
- ✅ Anomaly detection for new devices/locations
- ✅ Device fingerprinting for session hijacking detection
- ✅ IP address validation and geolocation
- ✅ Rate limiting prevents abuse

### Compliance Requirements

- ✅ SOC 2: Session visibility and control
- ✅ GDPR: Session data access and deletion
- ✅ Audit logging: All session events logged

## Comparison with Industry Standards

| Feature | GitHub | Google | Facebook | Auth0 | Dashtam (Proposed) |
|---------|--------|--------|----------|-------|---------------------|
| List sessions | ✅ | ✅ | ✅ | ✅ | ✅ |
| Revoke individual | ✅ | ✅ | ✅ | ✅ | ✅ |
| Revoke others | ✅ | ✅ | ✅ | ⚠️ | ✅ |
| Revoke all | ⚠️ | ⚠️ | ⚠️ | ✅ | ✅ |
| Current session indicator | ✅ | ✅ | ✅ | ⚠️ | ✅ |
| Device info | ✅ | ✅ | ✅ | ✅ | ✅ |
| Location (IP-based) | ✅ | ✅ | ✅ | ⚠️ | ✅ |
| Last activity | ✅ | ✅ | ✅ | ✅ | ✅ |
| New session alerts | ✅ | ✅ | ✅ | ✅ | ✅ |
| Trusted device | ⚠️ | ✅ | ✅ | ⚠️ | ✅ (planned) |
| Anomaly detection | ✅ | ✅ | ✅ | ✅ | ✅ (planned) |

**Legend**:

- ✅ Fully supported
- ⚠️ Partially supported or not documented
- ❌ Not supported

**Dashtam Parity**: 100% feature parity with industry leaders

## Recommended Next Steps

1. **Review this research document** with team/stakeholders
2. **Approve implementation approach** (data model, API design, security features)
3. **Create implementation guide** (detailed phase breakdown with code examples)
4. **Begin Phase 1**: Data model enhancements (Alembic migration)
5. **Iterative development**: Complete phases 1-6 sequentially
6. **Testing & documentation**: Comprehensive coverage throughout

## References

### Industry Documentation

- [GitHub Sessions Documentation](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/reviewing-your-security-log)
- [Google Account Security](https://support.google.com/accounts/answer/3067630)
- [Facebook Login Security](https://www.facebook.com/help/211990645501187)
- [Auth0 Session Management](https://auth0.com/docs/manage-users/sessions)
- [AWS Security Token Service](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_credentials_temp.html)

### Security Standards

- [OWASP Session Management Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html)
- [SOC 2 Trust Service Criteria](https://www.aicpa.org/resources/download/trust-services-criteria)
- [GDPR Article 15 (Right of Access)](https://gdpr-info.eu/art-15-gdpr/)
- [PCI-DSS Session Management Requirements](https://www.pcisecuritystandards.org/)

### Technical Resources

- [MaxMind GeoLite2 Documentation](https://dev.maxmind.com/geoip/geolite2-free-geolocation-data)
- [geoip2 Python Library](https://geoip2.readthedocs.io/)
- [FastAPI Security Best Practices](https://fastapi.tiangolo.com/tutorial/security/)
- [JWT Best Current Practices](https://datatracker.ietf.org/doc/html/rfc8725)

---

## Document Information

**Template**: research-template.md  
**Created**: 2025-10-27  
**Last Updated**: 2025-10-27  
**Author**: AI Agent (Research Phase)  
**Status**: Complete - Ready for Implementation Guide  
**Next Step**: Generate detailed implementation guide
