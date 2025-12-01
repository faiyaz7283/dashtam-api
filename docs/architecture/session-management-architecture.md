# Session Management Architecture

## 1. Overview

### Purpose

Provide multi-device session management with rich metadata tracking, geolocation/device enrichment, and immediate revocation capabilities for Dashtam authentication.

### Key Requirements

**Multi-Device Support**:

- Track all active sessions per user
- Rich metadata (device, location, IP, user agent)
- User can view and manage all sessions
- Configurable session limits per user

**Security First**:

- Immediate session revocation (single or all)
- Password change revokes all sessions (via domain event)
- Session tied to refresh token lifecycle
- Redis cache for fast revocation checks

**Hexagonal Architecture**:

- Domain layer: Session entity, SessionRepository protocol
- Application layer: Commands, queries, handlers (CQRS)
- Infrastructure layer: PostgreSQL repository, Redis cache, enrichers
- Presentation layer: FastAPI endpoints

**Integration Requirements**:

- User Authentication: Login creates session, logout revokes session
- Domain events: SessionCreated, SessionRevoked
- Audit trail: All session operations logged (PCI-DSS compliance)

### Non-Goals

- ❌ Token breach rotation (versioning) - Deferred to F1.3b
- ❌ MFA integration - Deferred to Phase 2+
- ❌ Session analytics dashboard - Future enhancement
- ❌ Anomaly detection - Future enhancement

---

## 2. Architecture Decisions

### Decision 1: Hybrid Storage (PostgreSQL + Redis)

**Rationale**: Combine durability with speed for session management.

**Implementation**:

- **PostgreSQL**: Source of truth for sessions table
- **Redis**: Active session cache (< 5ms lookup), revocation checks

**Flow**:

```text
┌─────────────────────────────────────────────────────────────┐
│                    Session Operations                       │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  CREATE SESSION                                             │
│  ┌──────────┐    ┌──────────────┐    ┌──────────────┐       │
│  │ Handler  │───▶│  PostgreSQL  │───▶│    Redis     │       │
│  └──────────┘    │   (INSERT)   │    │  (SET cache) │       │
│                  └──────────────┘    └──────────────┘       │
│                                                             │
│  VALIDATE SESSION (on token refresh)                        │
│  ┌──────────┐    ┌──────────────┐                           │
│  │ Handler  │───▶│    Redis     │  Cache hit: < 5ms         │
│  └──────────┘    │  (GET cache) │  Cache miss: PostgreSQL   │
│                  └──────────────┘                           │
│                                                             │
│  REVOKE SESSION                                             │
│  ┌──────────┐    ┌──────────────┐    ┌──────────────┐       │
│  │ Handler  │───▶│  PostgreSQL  │───▶│    Redis     │       │
│  └──────────┘    │   (UPDATE)   │    │  (DELETE)    │       │
│                  └──────────────┘    └──────────────┘       │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**Trade-offs**:

- ✅ Pros: Fast revocation checks, durable audit trail, scalable
- ⚠️ Cons: Two storage systems to manage, cache invalidation complexity

### Decision 2: JWT Claims + Refresh Validation

**Rationale**: Stateless access token validation with revocation check on refresh.

**Implementation**:

- Access token (JWT, 15 min) contains `session_id` claim
- On token refresh: Verify session not revoked (Redis check first, PostgreSQL fallback)
- Revocation gap: Max 15 minutes (acceptable for most use cases)

**Flow**:

```text
┌─────────────────────────────────────────────────────────────┐
│                    Token Validation Flow                    │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  API REQUEST (with access token)                            │
│  ┌────────────┐   ┌──────────────┐                          │
│  │ Middleware │──▶│  JWT Verify  │  Stateless, no DB lookup │
│  └────────────┘   │  (signature) │                          │
│                   └──────────────┘                          │
│                        │                                    │
│                        ▼                                    │
│               session_id in claims ✓                        │
│               (No session lookup on every request)          │
│                                                             │
│  TOKEN REFRESH (with refresh token)                         │
│  ┌──────────┐    ┌──────────────┐    ┌──────────────┐       │
│  │ Handler  │───▶│    Redis     │───▶│ Session OK?  │       │
│  └──────────┘    │  (is_active) │    │ Issue new JWT│       │
│                  └──────────────┘    └──────────────┘       │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**Trade-offs**:

- ✅ Pros: Zero DB lookups on API requests, fast validation
- ⚠️ Cons: 15-minute revocation gap (mitigated by short token lifetime)

### Decision 3: Async Enrichers with Fail-Open

**Rationale**: Don't block login if geolocation/device parsing fails.

**Implementation**:

- Enrichers are optional (injected via DI)
- Called during session creation (async)
- On failure: Log warning, continue with partial data
- Latency: 50-200ms for enrichment (acceptable for login)

**Enricher Protocol**:

```python
class SessionEnricher(Protocol):
    """Protocol for session enrichment (geolocation, device info)."""
    
    async def enrich(
        self,
        ip_address: str | None,
        user_agent: str | None,
    ) -> EnrichmentResult:
        """Enrich session with metadata.
        
        Args:
            ip_address: Client IP address.
            user_agent: Browser user agent string.
            
        Returns:
            EnrichmentResult with location and device_info.
            On failure: Returns partial result (fail-open).
        """
        ...
```

**Trade-offs**:

- ✅ Pros: Login never blocked by enrichment failure, best-effort metadata
- ⚠️ Cons: Some sessions may have incomplete metadata

### Decision 4: Admin-Controlled Session Limits

**Rationale**: Internal/admin control over concurrent sessions. Users cannot modify their own limits - this is a business/security policy enforced by the system.

**Architecture**:

Session limits use a two-tier approach:

1. **Role-Based Defaults**: Session limits tied to user roles/subscription tiers
2. **Per-User Override**: Admin can override individual users (security flags, special cases)

**Implementation**:

```python
# Role-based session tier configuration
# NOTE: These are just example tier names. 
SESSION_TIER_LIMITS: dict[str, int | None] = {
    "ultimate": None,   # Unlimited
    "premium": 50,
    "plus": 10,
    "essential": 5,
    "basic": 2,
    "free": 1,
}

@dataclass
class User:
    # ... existing fields ...
    session_tier: str = "free"        # Role-based tier (from authorization)
    max_sessions: int | None = None   # Admin override (takes precedence)


def get_max_sessions(user: User) -> int | None:
    """Get effective session limit for user.
    
    Priority:
        1. Admin override (user.max_sessions) if set
        2. Role-based tier limit
        3. Default: unlimited (if tier not found)
    """
    # Admin override takes precedence
    if user.max_sessions is not None:
        return user.max_sessions
    
    # Otherwise, use role-based tier
    return SESSION_TIER_LIMITS.get(user.session_tier)
```

**Session Creation Logic**:

```python
async def create_session(user_id: UUID, ...) -> Result[Session, SessionError]:
    user = await user_repo.find_by_id(user_id)
    max_sessions = get_max_sessions(user)
    
    if max_sessions is not None:
        active_count = await session_repo.count_active(user_id)
        if active_count >= max_sessions:
            # Revoke oldest session (FIFO)
            await session_repo.revoke_oldest(user_id, reason="max_sessions_exceeded")
    
    # Create new session
    ...
```

**Access Control**:

| Actor | Can Set Limit? | Method |
| ----- | -------------- | ------ |
| User | ❌ No | N/A - users cannot modify their own limits |
| Admin | ✅ Yes | `user.max_sessions` override |
| System/Billing | ✅ Yes | `user.session_tier` via role assignment |

**Example Scenarios**:

| User | session_tier | max_sessions (override) | Effective Limit |
| ---- | ------------ | ----------------------- | --------------- |
| Alice | "premium" | None | 50 (from tier) |
| Bob | "free" | None | 1 (from tier) |
| Charlie | "basic" | 10 | 10 (admin override) |
| Flagged User | "premium" | 1 | 1 (security restriction) |

**Trade-offs**:

- ✅ Pros: Full admin control, scales with subscription tiers
- ✅ Pros: Per-user override for special cases (security, VIP)
- ✅ Pros: Configuration-driven (adjust limits without code changes)
- ⚠️ Cons: Slightly more complex session creation logic

### Decision 5: Session Expiration Matches Refresh Token

**Rationale**: Simplify lifecycle management with 1:1 relationship.

**Implementation**:

- Session expires when refresh token expires (30 days)
- Both created together, both expire together
- Cleanup: One expiration policy to manage

**Trade-offs**:

- ✅ Pros: Consistent lifecycle, simple cleanup
- ⚠️ Cons: Cannot have session outlive refresh token (by design)

### Decision 6: Per-Session Provider Tracking

**Rationale**: Security audit trail for which providers each session accessed.

**Implementation**:

```python
@dataclass
class Session:
    # ... core fields ...
    
    # Provider tracking (Dashtam-specific)
    last_provider_accessed: str | None      # "schwab", "fidelity"
    last_provider_sync_at: datetime | None  # Last provider sync
    providers_accessed: list[str]           # ["schwab", "fidelity"]
```

**Trade-offs**:

- ✅ Pros: Audit trail per session, forensics for compromised sessions
- ⚠️ Cons: Requires updating session on each provider access

---

## 3. Domain Layer

### 3.1 Session Entity

**Location**: `src/domain/entities/session.py`

```python
"""Session domain entity for multi-device session management.

Pure business logic, no framework dependencies.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID


@dataclass(slots=True, kw_only=True)
class Session:
    """Session domain entity with multi-device tracking.
    
    Pure business logic with no infrastructure dependencies.
    Represents an authenticated session with rich metadata.
    
    Business Rules:
        - Session is active if not revoked and not expired
        - Session tied to refresh token (same lifecycle)
        - Revocation is immediate (no grace period)
        - Provider access tracked per session
    
    Attributes:
        id: Unique session identifier.
        user_id: User who owns this session.
        
        # Device Information
        device_info: Parsed device info ("Chrome on macOS").
        user_agent: Full user agent string.
        
        # Network Information
        ip_address: Client IP at session creation.
        location: Geographic location ("New York, US").
        
        # Timestamps
        created_at: When session was created.
        last_activity_at: Last activity timestamp.
        expires_at: When session expires (matches refresh token).
        
        # Security
        is_revoked: Whether session is revoked.
        is_trusted: Whether device is trusted (future: remember device).
        revoked_at: When session was revoked.
        revoked_reason: Why session was revoked.
        
        # Token Tracking
        refresh_token_id: Associated refresh token ID.
        
        # Security Tracking
        last_ip_address: Most recent IP (detect changes).
        suspicious_activity_count: Security event counter.
        
        # Provider Tracking (Dashtam-specific)
        last_provider_accessed: Last provider accessed.
        last_provider_sync_at: Last provider sync time.
        providers_accessed: List of providers accessed in this session.
    """
    
    # Identity
    id: UUID
    user_id: UUID
    
    # Device Information
    device_info: str | None = None
    user_agent: str | None = None
    
    # Network Information
    ip_address: str | None = None
    location: str | None = None
    
    # Timestamps
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    last_activity_at: datetime | None = None
    expires_at: datetime | None = None
    
    # Security
    is_revoked: bool = False
    is_trusted: bool = False
    revoked_at: datetime | None = None
    revoked_reason: str | None = None
    
    # Token Tracking
    refresh_token_id: UUID | None = None
    
    # Security Tracking
    last_ip_address: str | None = None
    suspicious_activity_count: int = 0
    
    # Provider Tracking
    last_provider_accessed: str | None = None
    last_provider_sync_at: datetime | None = None
    providers_accessed: list[str] = field(default_factory=list)
    
    def is_active(self) -> bool:
        """Check if session is active (not revoked, not expired).
        
        Returns:
            True if session is active, False otherwise.
        """
        if self.is_revoked:
            return False
        if self.expires_at and datetime.now(UTC) > self.expires_at:
            return False
        return True
    
    def revoke(self, reason: str) -> None:
        """Revoke this session.
        
        Args:
            reason: Why session is being revoked.
        """
        self.is_revoked = True
        self.revoked_at = datetime.now(UTC)
        self.revoked_reason = reason
    
    def update_activity(self, ip_address: str | None = None) -> None:
        """Update last activity timestamp and IP.
        
        Args:
            ip_address: Current client IP (optional).
        """
        self.last_activity_at = datetime.now(UTC)
        if ip_address:
            if self.ip_address and ip_address != self.ip_address:
                # IP changed - track for security
                self.last_ip_address = ip_address
            elif not self.ip_address:
                self.ip_address = ip_address
    
    def record_provider_access(self, provider_name: str) -> None:
        """Record provider access for audit trail.
        
        Args:
            provider_name: Provider that was accessed (e.g., "schwab").
        """
        self.last_provider_accessed = provider_name
        self.last_provider_sync_at = datetime.now(UTC)
        if provider_name not in self.providers_accessed:
            self.providers_accessed.append(provider_name)
    
    def increment_suspicious_activity(self) -> None:
        """Increment suspicious activity counter."""
        self.suspicious_activity_count += 1
```

### 3.2 SessionRepository Protocol

**Location**: `src/domain/protocols/session_repository.py`

```python
"""SessionRepository protocol (port) for domain layer.

This protocol defines the interface for session persistence that the
domain layer needs. Infrastructure provides concrete implementations.

Following hexagonal architecture:
- Domain defines what it needs (protocol/port)
- Infrastructure provides implementation (adapter)
- Domain has no knowledge of how sessions are stored
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID


@dataclass(slots=True, kw_only=True)
class SessionData:
    """Data transfer object for session information.
    
    Used by protocol methods to return session data without
    exposing infrastructure model classes to domain/application layers.
    """
    
    id: UUID
    user_id: UUID
    device_info: str | None
    user_agent: str | None
    ip_address: str | None
    location: str | None
    created_at: datetime
    last_activity_at: datetime | None
    expires_at: datetime | None
    is_revoked: bool
    is_trusted: bool
    revoked_at: datetime | None
    revoked_reason: str | None
    refresh_token_id: UUID | None
    last_ip_address: str | None
    suspicious_activity_count: int
    last_provider_accessed: str | None
    last_provider_sync_at: datetime | None
    providers_accessed: list[str]


class SessionRepository(Protocol):
    """Protocol for session persistence operations.
    
    Defines the contract that all session repository implementations
    must satisfy. Used for multi-device session management.
    
    Session Lifecycle:
        1. Created during login (tied to refresh token)
        2. Updated on activity (last_activity_at, provider access)
        3. Revoked on logout, password change, or admin action
        4. Expires when refresh token expires (30 days)
    
    Implementations:
        - PostgresSessionRepository: src/infrastructure/persistence/repositories/
    """
    
    async def save(self, session: SessionData) -> SessionData:
        """Create or update session.
        
        Args:
            session: Session data to save.
            
        Returns:
            Saved SessionData with any generated fields.
        """
        ...
    
    async def find_by_id(self, session_id: UUID) -> SessionData | None:
        """Find session by ID.
        
        Args:
            session_id: Session's unique identifier.
            
        Returns:
            SessionData if found, None otherwise.
        """
        ...
    
    async def find_active_by_user(self, user_id: UUID) -> list[SessionData]:
        """Find all active sessions for a user.
        
        Active = not revoked AND not expired.
        
        Args:
            user_id: User's unique identifier.
            
        Returns:
            List of active SessionData for the user.
        """
        ...
    
    async def count_active(self, user_id: UUID) -> int:
        """Count active sessions for a user.
        
        Used for session limit enforcement.
        
        Args:
            user_id: User's unique identifier.
            
        Returns:
            Number of active sessions.
        """
        ...
    
    async def revoke(self, session_id: UUID, reason: str) -> bool:
        """Revoke a single session.
        
        Args:
            session_id: Session to revoke.
            reason: Revocation reason for audit trail.
            
        Returns:
            True if session was revoked, False if not found.
        """
        ...
    
    async def revoke_all_for_user(
        self,
        user_id: UUID,
        reason: str,
        except_session_id: UUID | None = None,
    ) -> int:
        """Revoke all sessions for a user.
        
        Used for password change, logout all, security events.
        
        Args:
            user_id: User whose sessions to revoke.
            reason: Revocation reason for audit trail.
            except_session_id: Optional session to keep (current session).
            
        Returns:
            Number of sessions revoked.
        """
        ...
    
    async def revoke_oldest(self, user_id: UUID, reason: str) -> bool:
        """Revoke the oldest active session for a user.
        
        Used when max_sessions limit is reached.
        
        Args:
            user_id: User whose oldest session to revoke.
            reason: Revocation reason for audit trail.
            
        Returns:
            True if a session was revoked, False if no active sessions.
        """
        ...
    
    async def update_activity(
        self,
        session_id: UUID,
        ip_address: str | None = None,
    ) -> None:
        """Update session's last activity timestamp.
        
        Args:
            session_id: Session to update.
            ip_address: Current client IP (optional).
        """
        ...
    
    async def update_provider_access(
        self,
        session_id: UUID,
        provider_name: str,
    ) -> None:
        """Record provider access on session.
        
        Args:
            session_id: Session that accessed provider.
            provider_name: Provider that was accessed.
        """
        ...
    
    async def delete_expired(self) -> int:
        """Delete expired sessions (cleanup job).
        
        Returns:
            Number of sessions deleted.
        """
        ...
```

### 3.3 SessionEnricher Protocol

**Location**: `src/domain/protocols/session_enricher.py`

```python
"""SessionEnricher protocol for session metadata enrichment.

Defines interface for enriching sessions with geolocation and device info.
"""

from dataclasses import dataclass
from typing import Protocol


@dataclass(slots=True, kw_only=True)
class EnrichmentResult:
    """Result of session enrichment.
    
    Fields may be None if enrichment failed (fail-open).
    """
    
    device_info: str | None = None  # "Chrome on macOS"
    location: str | None = None      # "New York, US"


class SessionEnricher(Protocol):
    """Protocol for session enrichment (geolocation, device info).
    
    Implementations:
        - GeolocationEnricher: IP → location
        - DeviceEnricher: User-Agent → device info
        - CompositeEnricher: Combines multiple enrichers
    """
    
    async def enrich(
        self,
        ip_address: str | None,
        user_agent: str | None,
    ) -> EnrichmentResult:
        """Enrich session with metadata.
        
        Args:
            ip_address: Client IP address.
            user_agent: Browser user agent string.
            
        Returns:
            EnrichmentResult with location and device_info.
            On failure: Returns partial result (fail-open).
        """
        ...
```

### 3.4 SessionCacheProtocol

**Location**: `src/domain/protocols/session_cache.py`

```python
"""SessionCache protocol for Redis-backed session caching.

Provides fast session validation without database lookups.
"""

from typing import Protocol
from uuid import UUID


class SessionCache(Protocol):
    """Protocol for session caching (Redis).
    
    Used for fast session validation on token refresh.
    
    Cache Strategy:
        - Key: session:{session_id}
        - Value: "active" or "revoked"
        - TTL: Match session expiration (30 days)
        - On revoke: Delete from cache (immediate)
    """
    
    async def set_active(self, session_id: UUID, ttl_seconds: int) -> None:
        """Mark session as active in cache.
        
        Args:
            session_id: Session to cache.
            ttl_seconds: Time-to-live in seconds.
        """
        ...
    
    async def is_active(self, session_id: UUID) -> bool | None:
        """Check if session is active in cache.
        
        Args:
            session_id: Session to check.
            
        Returns:
            True if active, False if revoked, None if not in cache.
        """
        ...
    
    async def delete(self, session_id: UUID) -> None:
        """Remove session from cache (on revocation).
        
        Args:
            session_id: Session to remove.
        """
        ...
    
    async def delete_all_for_user(self, user_id: UUID) -> int:
        """Remove all cached sessions for a user.
        
        Args:
            user_id: User whose sessions to remove.
            
        Returns:
            Number of sessions removed.
        """
        ...
```

---

## 4. Application Layer

### 4.1 Commands (CQRS Write Operations)

**Location**: `src/application/commands/session_commands.py`

```python
"""Session commands for CQRS write operations."""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, kw_only=True)
class CreateSession:
    """Create a new session during login."""
    
    user_id: UUID
    ip_address: str | None = None
    user_agent: str | None = None
    refresh_token_id: UUID | None = None
    expires_at_seconds: int = 2592000  # 30 days default


@dataclass(frozen=True, kw_only=True)
class RevokeSession:
    """Revoke a single session."""
    
    session_id: UUID
    reason: str


@dataclass(frozen=True, kw_only=True)
class RevokeAllUserSessions:
    """Revoke all sessions for a user."""
    
    user_id: UUID
    reason: str
    except_current_session_id: UUID | None = None


@dataclass(frozen=True, kw_only=True)
class UpdateSessionActivity:
    """Update session's last activity."""
    
    session_id: UUID
    ip_address: str | None = None


@dataclass(frozen=True, kw_only=True)
class RecordProviderAccess:
    """Record provider access on session."""
    
    session_id: UUID
    provider_name: str
```

### 4.2 Queries (CQRS Read Operations)

**Location**: `src/application/queries/session_queries.py`

```python
"""Session queries for CQRS read operations."""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, kw_only=True)
class GetSession:
    """Get a single session by ID."""
    
    session_id: UUID


@dataclass(frozen=True, kw_only=True)
class ListUserSessions:
    """List all active sessions for a user."""
    
    user_id: UUID
    include_revoked: bool = False
```

### 4.3 Command Handlers

**Location**: `src/application/commands/handlers/create_session_handler.py`

```python
"""CreateSession command handler."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID
from uuid_extensions import uuid7

from src.core.result import Failure, Result, Success
from src.domain.entities.session import Session
from src.domain.protocols.event_bus_protocol import EventBusProtocol
from src.domain.protocols.session_cache import SessionCache
from src.domain.protocols.session_enricher import SessionEnricher
from src.domain.protocols.session_repository import SessionRepository
from src.domain.protocols.user_repository import UserRepository


@dataclass
class SessionCreated:
    """Result of successful session creation."""
    
    session_id: UUID
    device_info: str | None
    location: str | None


class CreateSessionHandler:
    """Handler for CreateSession command.
    
    Creates a new session with enrichment (geolocation, device info).
    Enforces user session limits if configured.
    """
    
    def __init__(
        self,
        session_repo: SessionRepository,
        user_repo: UserRepository,
        session_cache: SessionCache,
        enricher: SessionEnricher,
        event_bus: EventBusProtocol,
    ) -> None:
        self._session_repo = session_repo
        self._user_repo = user_repo
        self._session_cache = session_cache
        self._enricher = enricher
        self._event_bus = event_bus
    
    async def handle(
        self,
        command: "CreateSession",
    ) -> Result[SessionCreated, str]:
        """Handle CreateSession command.
        
        Args:
            command: CreateSession command with user_id and metadata.
            
        Returns:
            Success with SessionCreated or Failure with error message.
        """
        # Check user session limits
        user = await self._user_repo.find_by_id(command.user_id)
        if user and user.max_sessions is not None:
            active_count = await self._session_repo.count_active(command.user_id)
            if active_count >= user.max_sessions:
                # Revoke oldest session (FIFO)
                await self._session_repo.revoke_oldest(
                    command.user_id,
                    reason="max_sessions_exceeded",
                )
        
        # Enrich session with geolocation and device info
        enrichment = await self._enricher.enrich(
            ip_address=command.ip_address,
            user_agent=command.user_agent,
        )
        
        # Create session entity
        session_id = uuid7()
        expires_at = datetime.now(UTC) + timedelta(seconds=command.expires_at_seconds)
        
        session = Session(
            id=session_id,
            user_id=command.user_id,
            device_info=enrichment.device_info,
            user_agent=command.user_agent,
            ip_address=command.ip_address,
            location=enrichment.location,
            created_at=datetime.now(UTC),
            expires_at=expires_at,
            refresh_token_id=command.refresh_token_id,
        )
        
        # Persist to database
        await self._session_repo.save(session)
        
        # Cache for fast validation
        ttl = command.expires_at_seconds
        await self._session_cache.set_active(session_id, ttl)
        
        # Publish domain event
        from src.domain.events.session_events import SessionCreatedEvent
        await self._event_bus.publish(SessionCreatedEvent(
            session_id=session_id,
            user_id=command.user_id,
            device_info=enrichment.device_info,
            location=enrichment.location,
            ip_address=command.ip_address,
        ))
        
        return Success(value=SessionCreated(
            session_id=session_id,
            device_info=enrichment.device_info,
            location=enrichment.location,
        ))
```

---

## 5. Infrastructure Layer

### 5.1 Database Model

**Location**: `src/infrastructure/persistence/models/session.py`

```python
"""Session database model for PostgreSQL."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import ARRAY, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import INET
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.persistence.base import BaseMutableModel


class SessionModel(BaseMutableModel):
    """Session model for multi-device session management.
    
    Stores session metadata with rich tracking for security and audit.
    
    Indexes:
        - idx_sessions_user_id: (user_id) for user's sessions
        - idx_sessions_user_active: (user_id) WHERE NOT is_revoked for active sessions
        - idx_sessions_expires_at: (expires_at) for cleanup queries
        - idx_sessions_refresh_token_id: (refresh_token_id) for token lookup
    
    Foreign Keys:
        - user_id: References users(id) ON DELETE CASCADE
        - refresh_token_id: References refresh_tokens(id) ON DELETE SET NULL
    """
    
    __tablename__ = "sessions"
    
    # User relationship
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="User who owns this session",
    )
    
    # Device Information
    device_info: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Parsed device info (Chrome on macOS)",
    )
    
    user_agent: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Full user agent string",
    )
    
    # Network Information (PostgreSQL INET type)
    ip_address: Mapped[str | None] = mapped_column(
        INET,
        nullable=True,
        comment="Client IP at session creation",
    )
    
    location: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Geographic location (New York, US)",
    )
    
    # Timestamps
    last_activity_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
        comment="Last activity timestamp",
    )
    
    expires_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
        index=True,
        comment="When session expires (matches refresh token)",
    )
    
    # Security
    is_revoked: Mapped[bool] = mapped_column(
        nullable=False,
        default=False,
        comment="Whether session is revoked",
    )
    
    is_trusted: Mapped[bool] = mapped_column(
        nullable=False,
        default=False,
        comment="Whether device is trusted",
    )
    
    revoked_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
        comment="When session was revoked",
    )
    
    revoked_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Why session was revoked",
    )
    
    # Token Tracking
    refresh_token_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("refresh_tokens.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Associated refresh token",
    )
    
    # Security Tracking
    last_ip_address: Mapped[str | None] = mapped_column(
        INET,
        nullable=True,
        comment="Most recent IP (detect changes)",
    )
    
    suspicious_activity_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Security event counter",
    )
    
    # Provider Tracking (PostgreSQL ARRAY)
    last_provider_accessed: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Last provider accessed (schwab, fidelity)",
    )
    
    last_provider_sync_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
        comment="Last provider sync time",
    )
    
    providers_accessed: Mapped[list[str]] = mapped_column(
        ARRAY(String(50)),
        nullable=False,
        default=[],
        comment="List of providers accessed in this session",
    )
    
    # Composite indexes
    __table_args__ = (
        Index(
            "idx_sessions_user_active",
            "user_id",
            postgresql_where="is_revoked = false",
        ),
        Index(
            "idx_sessions_cleanup",
            "expires_at",
            postgresql_where="is_revoked = false",
        ),
    )
    
    def __repr__(self) -> str:
        return (
            f"<SessionModel("
            f"id={self.id}, "
            f"user_id={self.user_id}, "
            f"device_info={self.device_info}, "
            f"is_revoked={self.is_revoked}"
            f")>"
        )
```

### 5.2 Alembic Migration

**Location**: `src/infrastructure/persistence/migrations/versions/xxx_create_sessions_table.py`

```python
"""Create sessions table.

Revision ID: xxx
Revises: yyy (refresh_tokens migration)
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import INET, ARRAY, UUID

revision = "xxx"
down_revision = "yyy"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sessions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("device_info", sa.String(255), nullable=True),
        sa.Column("user_agent", sa.Text, nullable=True),
        sa.Column("ip_address", INET, nullable=True),
        sa.Column("location", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_activity_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_revoked", sa.Boolean, nullable=False, default=False),
        sa.Column("is_trusted", sa.Boolean, nullable=False, default=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_reason", sa.Text, nullable=True),
        sa.Column("refresh_token_id", UUID(as_uuid=True), sa.ForeignKey("refresh_tokens.id", ondelete="SET NULL"), nullable=True),
        sa.Column("last_ip_address", INET, nullable=True),
        sa.Column("suspicious_activity_count", sa.Integer, nullable=False, default=0),
        sa.Column("last_provider_accessed", sa.String(50), nullable=True),
        sa.Column("last_provider_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("providers_accessed", ARRAY(sa.String(50)), nullable=False, default=[]),
    )
    
    # Indexes
    op.create_index("idx_sessions_user_id", "sessions", ["user_id"])
    op.create_index("idx_sessions_refresh_token_id", "sessions", ["refresh_token_id"])
    op.create_index("idx_sessions_expires_at", "sessions", ["expires_at"])
    op.create_index(
        "idx_sessions_user_active",
        "sessions",
        ["user_id"],
        postgresql_where=sa.text("is_revoked = false"),
    )
    
    # Add FK constraint to refresh_tokens.session_id
    op.add_column(
        "refresh_tokens",
        sa.Column("session_id_fk", UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_refresh_tokens_session_id",
        "refresh_tokens",
        "sessions",
        ["session_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint("fk_refresh_tokens_session_id", "refresh_tokens", type_="foreignkey")
    op.drop_column("refresh_tokens", "session_id_fk")
    op.drop_table("sessions")
```

### 5.3 Redis Session Cache

**Location**: `src/infrastructure/cache/session_cache.py`

```python
"""Redis-backed session cache for fast validation."""

from uuid import UUID

from src.domain.protocols.cache_protocol import CacheProtocol
from src.domain.protocols.session_cache import SessionCache


class RedisSessionCache:
    """Redis implementation of SessionCache protocol.
    
    Cache Strategy:
        - Key pattern: session:{session_id}
        - Value: "1" (active)
        - TTL: Match session expiration
        - On revoke: Delete key (immediate invalidation)
    """
    
    def __init__(self, cache: CacheProtocol) -> None:
        self._cache = cache
    
    async def set_active(self, session_id: UUID, ttl_seconds: int) -> None:
        """Mark session as active in cache."""
        key = f"session:{session_id}"
        await self._cache.set(key, "1", ttl_seconds)
    
    async def is_active(self, session_id: UUID) -> bool | None:
        """Check if session is active in cache.
        
        Returns:
            True if active (key exists), None if not in cache.
        """
        key = f"session:{session_id}"
        value = await self._cache.get(key)
        if value is None:
            return None  # Cache miss
        return True  # Key exists = active
    
    async def delete(self, session_id: UUID) -> None:
        """Remove session from cache."""
        key = f"session:{session_id}"
        await self._cache.delete(key)
    
    async def delete_all_for_user(self, user_id: UUID) -> int:
        """Remove all cached sessions for a user.
        
        Note: This requires scanning keys, which is expensive.
        In practice, we track session IDs separately or accept
        eventual consistency (sessions expire naturally).
        """
        # For MVP: Sessions expire naturally
        # Future: Maintain user:{user_id}:sessions SET for efficient deletion
        return 0
```

### 5.4 Enrichers

**Location**: `src/infrastructure/enrichers/device_enricher.py`

```python
"""Device enricher using user-agents library."""

from user_agents import parse

from src.domain.protocols.session_enricher import EnrichmentResult, SessionEnricher
from src.domain.protocols.logger_protocol import LoggerProtocol


class DeviceEnricher:
    """Enricher that parses user agent strings.
    
    Uses user-agents library to extract device info.
    Fail-open: Returns None device_info on parse failure.
    """
    
    def __init__(self, logger: LoggerProtocol) -> None:
        self._logger = logger
    
    async def enrich(
        self,
        ip_address: str | None,
        user_agent: str | None,
    ) -> EnrichmentResult:
        """Parse user agent to extract device info."""
        device_info = None
        
        if user_agent:
            try:
                ua = parse(user_agent)
                browser = ua.browser.family
                os = ua.os.family
                device_info = f"{browser} on {os}"
            except Exception as e:
                self._logger.warning(
                    "device_enrichment_failed",
                    error=str(e),
                    user_agent=user_agent[:100],  # Truncate for logging
                )
        
        return EnrichmentResult(device_info=device_info)
```

**Location**: `src/infrastructure/enrichers/geolocation_enricher.py`

```python
"""Geolocation enricher using IP2Location Lite."""

from src.domain.protocols.session_enricher import EnrichmentResult, SessionEnricher
from src.domain.protocols.logger_protocol import LoggerProtocol


class GeolocationEnricher:
    """Enricher that looks up IP geolocation.
    
    Uses IP2Location Lite (free local database).
    Fail-open: Returns None location on lookup failure.
    """
    
    def __init__(self, logger: LoggerProtocol, db_path: str | None = None) -> None:
        self._logger = logger
        self._db_path = db_path
        self._db = None
    
    async def enrich(
        self,
        ip_address: str | None,
        user_agent: str | None,
    ) -> EnrichmentResult:
        """Lookup IP geolocation."""
        location = None
        
        if ip_address and self._db_path:
            try:
                # Lazy load database
                if self._db is None:
                    import IP2Location
                    self._db = IP2Location.IP2Location(self._db_path)
                
                rec = self._db.get_all(ip_address)
                if rec and rec.city and rec.country_short:
                    location = f"{rec.city}, {rec.country_short}"
            except Exception as e:
                self._logger.warning(
                    "geolocation_enrichment_failed",
                    error=str(e),
                    ip_address=ip_address,
                )
        
        return EnrichmentResult(location=location)
```

**Location**: `src/infrastructure/enrichers/composite_enricher.py`

```python
"""Composite enricher combining multiple enrichers."""

from src.domain.protocols.session_enricher import EnrichmentResult, SessionEnricher


class CompositeEnricher:
    """Combines multiple enrichers into one.
    
    Runs all enrichers and merges results.
    """
    
    def __init__(self, enrichers: list[SessionEnricher]) -> None:
        self._enrichers = enrichers
    
    async def enrich(
        self,
        ip_address: str | None,
        user_agent: str | None,
    ) -> EnrichmentResult:
        """Run all enrichers and merge results."""
        device_info = None
        location = None
        
        for enricher in self._enrichers:
            result = await enricher.enrich(ip_address, user_agent)
            if result.device_info and not device_info:
                device_info = result.device_info
            if result.location and not location:
                location = result.location
        
        return EnrichmentResult(
            device_info=device_info,
            location=location,
        )
```

---

## 6. Presentation Layer

### 6.1 API Endpoints (REST Compliant)

**Location**: `src/presentation/api/v1/sessions.py` (extend existing)

```python
"""Sessions resource router.

RESTful endpoints for session management.

Endpoints:
    GET  /api/v1/sessions          - List user's sessions
    GET  /api/v1/sessions/{id}     - Get single session
    DELETE /api/v1/sessions/{id}   - Revoke single session
    DELETE /api/v1/sessions        - Revoke all sessions (logout all)
    
Existing (from F1.1):
    POST /api/v1/sessions          - Create session (login)
    DELETE /api/v1/sessions/current - Delete current session (logout)
"""

# New endpoints to add:

@router.get(
    "",
    response_model=SessionListResponse,
    summary="List sessions",
    description="List all active sessions for the current user.",
)
async def list_sessions(
    current_user: CurrentUser,
    handler: ListSessionsHandler = Depends(get_list_sessions_handler),
) -> SessionListResponse:
    """List all active sessions for current user.
    
    GET /api/v1/sessions → 200 OK
    """
    ...


@router.get(
    "/{session_id}",
    response_model=SessionResponse,
    summary="Get session",
    description="Get details of a specific session.",
)
async def get_session(
    session_id: UUID,
    current_user: CurrentUser,
    handler: GetSessionHandler = Depends(get_get_session_handler),
) -> SessionResponse:
    """Get single session details.
    
    GET /api/v1/sessions/{id} → 200 OK
    """
    ...


@router.delete(
    "/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke session",
    description="Revoke a specific session.",
)
async def revoke_session(
    session_id: UUID,
    current_user: CurrentUser,
    handler: RevokeSessionHandler = Depends(get_revoke_session_handler),
):
    """Revoke single session.
    
    DELETE /api/v1/sessions/{id} → 204 No Content
    """
    ...


@router.delete(
    "",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke all sessions",
    description="Revoke all sessions except current (logout all devices).",
)
async def revoke_all_sessions(
    current_user: CurrentUser,
    current_session_id: UUID = Depends(get_current_session_id),
    handler: RevokeAllSessionsHandler = Depends(get_revoke_all_sessions_handler),
):
    """Revoke all sessions except current.
    
    DELETE /api/v1/sessions → 204 No Content
    """
    ...
```

### 6.2 Response Schemas

**Location**: `src/schemas/session_schemas.py`

```python
"""Session response schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class SessionResponse(BaseModel):
    """Single session response."""
    
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    device_info: str | None
    ip_address: str | None
    location: str | None
    created_at: datetime
    last_activity_at: datetime | None
    is_current: bool = False  # Marked if this is the current session
    
    # Provider tracking (optional, for detailed view)
    last_provider_accessed: str | None = None
    providers_accessed: list[str] = []


class SessionListResponse(BaseModel):
    """List of sessions response."""
    
    sessions: list[SessionResponse]
    total: int
```

---

## 7. Domain Events

**Location**: `src/domain/events/session_events.py`

```python
"""Session domain events."""

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID
from uuid_extensions import uuid7


@dataclass(frozen=True, kw_only=True)
class SessionCreatedEvent:
    """Published when a new session is created."""
    
    event_id: UUID = field(default_factory=uuid7)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    
    session_id: UUID
    user_id: UUID
    device_info: str | None
    location: str | None
    ip_address: str | None


@dataclass(frozen=True, kw_only=True)
class SessionRevokedEvent:
    """Published when a session is revoked."""
    
    event_id: UUID = field(default_factory=uuid7)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    
    session_id: UUID
    user_id: UUID
    reason: str


@dataclass(frozen=True, kw_only=True)
class AllSessionsRevokedEvent:
    """Published when all user sessions are revoked."""
    
    event_id: UUID = field(default_factory=uuid7)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    
    user_id: UUID
    reason: str
    sessions_revoked: int
    except_session_id: UUID | None = None
```

---

## 8. Integration with F1.1

### 8.1 Login Flow - 3-Handler CQRS Orchestration

**Session creation uses 3 handlers orchestrated by the presentation layer**:

> See `docs/architecture/authentication-architecture.md` Section 10 for full details.

```python
# src/presentation/api/v1/sessions.py
@router.post("/sessions", status_code=201)
async def create_session(
    request: Request,
    data: SessionCreateRequest,
    auth_handler: AuthenticateUserHandler = Depends(get_authenticate_user_handler),
    session_handler: CreateSessionHandler = Depends(get_create_session_handler),
    token_handler: GenerateAuthTokensHandler = Depends(get_generate_auth_tokens_handler),
) -> SessionCreateResponse:
    """Orchestrate login flow with 3 handlers."""
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    # Step 1: Authenticate user credentials
    auth_result = await auth_handler.handle(
        AuthenticateUser(email=data.email, password=data.password)
    )
    if isinstance(auth_result, Failure):
        raise appropriate_http_error(auth_result.error)

    # Step 2: Create session with device/location enrichment
    session_result = await session_handler.handle(
        CreateSession(
            user_id=auth_result.value.user_id,
            ip_address=ip_address,
            user_agent=user_agent,
        )
    )
    if isinstance(session_result, Failure):
        raise appropriate_http_error(session_result.error)

    # Step 3: Generate tokens with session_id
    token_result = await token_handler.handle(
        GenerateAuthTokens(
            user_id=auth_result.value.user_id,
            email=auth_result.value.email,
            roles=auth_result.value.roles,
            session_id=session_result.value.session_id,
        )
    )
    if isinstance(token_result, Failure):
        raise appropriate_http_error(token_result.error)

    return SessionCreateResponse(
        access_token=token_result.value.access_token,
        refresh_token=token_result.value.refresh_token,
    )
```

**Handler responsibilities**:

- `AuthenticateUserHandler`: Verify credentials, check locks → `AuthenticatedUser`
- `CreateSessionHandler`: Device/location enrichment, session limits → `session_id`
- `GenerateAuthTokensHandler`: Generate JWT + refresh token → `AuthTokens`

### 8.2 Password Change Integration

The existing `SessionEventHandler` stub will be replaced with real implementation:

```python
# In session_event_handler.py (replace stub)

class SessionEventHandler:
    """Event handler for session revocation on password change."""
    
    def __init__(
        self,
        session_repo: SessionRepository,
        session_cache: SessionCache,
        refresh_token_repo: RefreshTokenRepository,
        logger: LoggerProtocol,
    ) -> None:
        self._session_repo = session_repo
        self._session_cache = session_cache
        self._refresh_token_repo = refresh_token_repo
        self._logger = logger
    
    async def handle_user_password_change_succeeded(
        self,
        event: UserPasswordChangeSucceeded,
    ) -> None:
        """Revoke all user sessions after password change."""
        # Revoke all sessions
        count = await self._session_repo.revoke_all_for_user(
            user_id=event.user_id,
            reason="password_changed",
        )
        
        # Revoke all refresh tokens
        await self._refresh_token_repo.revoke_all_for_user(
            user_id=event.user_id,
            reason="password_changed",
        )
        
        # Invalidate cache
        await self._session_cache.delete_all_for_user(event.user_id)
        
        self._logger.info(
            "sessions_revoked_on_password_change",
            user_id=str(event.user_id),
            sessions_revoked=count,
        )
```

---

## 9. Testing Strategy

### 9.1 Unit Tests (Domain + Application)

**Location**: `tests/unit/test_domain_session_entity.py`

- Session.is_active() - returns True when not revoked and not expired
- Session.is_active() - returns False when revoked
- Session.is_active() - returns False when expired
- Session.revoke() - sets is_revoked, revoked_at, revoked_reason
- Session.update_activity() - updates last_activity_at
- Session.record_provider_access() - tracks provider access

**Location**: `tests/unit/test_application_create_session_handler.py`

- CreateSessionHandler - creates session successfully
- CreateSessionHandler - enforces max_sessions limit
- CreateSessionHandler - enriches with device and location
- CreateSessionHandler - publishes SessionCreatedEvent

### 9.2 Integration Tests (Infrastructure)

**Location**: `tests/integration/test_session_repository_postgres.py`

- Save and retrieve session
- Find active sessions by user
- Count active sessions
- Revoke single session
- Revoke all user sessions
- Revoke oldest session (FIFO)
- Delete expired sessions

**Location**: `tests/integration/test_session_cache_redis.py`

- Set and check active session
- Delete session from cache
- Cache miss returns None

### 9.3 API Tests (Presentation)

**Location**: `tests/api/test_session_endpoints.py`

- GET /sessions - list user sessions
- GET /sessions/{id} - get single session
- DELETE /sessions/{id} - revoke single session
- DELETE /sessions - revoke all except current
- Unauthorized access returns 401

---

## 10. Files to Create/Modify

### New Files

```text
src/domain/entities/session.py
src/domain/protocols/session_repository.py
src/domain/protocols/session_enricher.py
src/domain/protocols/session_cache.py
src/domain/events/session_events.py

src/application/commands/session_commands.py
src/application/commands/handlers/create_session_handler.py
src/application/commands/handlers/revoke_session_handler.py
src/application/commands/handlers/revoke_all_sessions_handler.py
src/application/queries/session_queries.py
src/application/queries/handlers/list_sessions_handler.py
src/application/queries/handlers/get_session_handler.py

src/infrastructure/persistence/models/session.py
src/infrastructure/persistence/repositories/session_repository.py
src/infrastructure/persistence/migrations/versions/xxx_create_sessions_table.py
src/infrastructure/cache/session_cache.py
src/infrastructure/enrichers/__init__.py
src/infrastructure/enrichers/device_enricher.py
src/infrastructure/enrichers/geolocation_enricher.py
src/infrastructure/enrichers/composite_enricher.py

src/schemas/session_schemas.py

tests/unit/test_domain_session_entity.py
tests/unit/test_application_create_session_handler.py
tests/unit/test_application_revoke_session_handler.py
tests/integration/test_session_repository_postgres.py
tests/integration/test_session_cache_redis.py
tests/api/test_session_endpoints.py
```

### Modified Files

```text
src/domain/entities/__init__.py (add Session export)
src/domain/entities/user.py (add max_sessions field)
src/domain/protocols/__init__.py (add new protocols)
src/presentation/api/v1/sessions.py (add new endpoints)
src/core/container.py (add session dependencies)
src/application/commands/handlers/login_user_handler.py (create session on login)
src/infrastructure/events/handlers/session_event_handler.py (replace stub)
```

---

## 11. Dependencies

### External Packages

```text
user-agents>=2.2.0      # Device fingerprinting
IP2Location>=8.10.0     # Geolocation (optional, requires local DB file)
```

---

## 12. Success Criteria

- [ ] Session entity with all metadata fields
- [ ] SessionRepository protocol in domain/protocols/
- [ ] PostgreSQL repository implementation
- [ ] Sessions table migration (Alembic)
- [ ] Redis session cache for fast validation
- [ ] GeolocationEnricher (IP2Location Lite)
- [ ] DeviceEnricher (user-agents library)
- [ ] Session CQRS commands and queries
- [ ] 4 session endpoints (GET list, GET one, DELETE one, DELETE all)
- [ ] User.max_sessions field for session limits
- [ ] Login creates session
- [ ] Password change revokes all sessions (event handler)
- [ ] All tests passing (85%+ coverage)
- [ ] Documentation complete

---

**Created**: 2025-11-26 | **Last Updated**: 2025-11-26
