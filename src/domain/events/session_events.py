"""Session domain events for event-driven architecture.

This module contains two types of events:

1. **Workflow Events** (3-state pattern):
   - SessionCreatedEvent, SessionRevokedEvent, AllSessionsRevokedEvent
   - Emitted during critical workflows (login creates session, logout revokes)
   - Trigger audit, logging, cache updates
   - Note: These integrate with existing auth workflow events
     (UserLoginSucceeded creates session, UserPasswordChangeSucceeded revokes all)

2. **Operational Events** (single state, NOT 3-state):
   - SessionActivityUpdatedEvent, SessionProviderAccessEvent
   - SuspiciousSessionActivityEvent, SessionLimitExceededEvent
   - Used for telemetry, monitoring, security tracking
   - Handlers must be lightweight (<10ms)
   - Do NOT require audit unless security-relevant

See Decision 6 in docs/architecture/domain-events-architecture.md for
operational event guidelines.

Reference:
    - docs/architecture/session-management-architecture.md
    - docs/architecture/domain-events-architecture.md (Decision 6)
"""

from dataclasses import dataclass, field
from uuid import UUID

from src.domain.events.base_event import DomainEvent


@dataclass(frozen=True, kw_only=True, slots=True)
class SessionCreatedEvent(DomainEvent):
    """Emitted when a new session is created.

    Triggered during successful login. Handlers may:
    - Cache session in Redis
    - Log session creation for audit
    - Send notification (if configured)

    Attributes:
        session_id: The new session's ID.
        user_id: User who logged in.
        device_info: Parsed device info ("Chrome on macOS").
        ip_address: Client IP address.
        location: Geographic location.
        user_agent: Full user agent string.
    """

    session_id: UUID
    user_id: UUID
    device_info: str | None = None
    ip_address: str | None = None
    location: str | None = None
    user_agent: str | None = None


@dataclass(frozen=True, kw_only=True, slots=True)
class SessionRevokedEvent(DomainEvent):
    """Emitted when a single session is revoked.

    Triggered during logout or session deletion. Handlers may:
    - Remove from cache
    - Log revocation for audit
    - Clean up associated resources

    Attributes:
        session_id: The revoked session's ID.
        user_id: User who owned the session.
        reason: Why session was revoked.
        device_info: Device info of revoked session (for notifications).
        revoked_by_user: Whether user initiated (vs admin/system).
    """

    session_id: UUID
    user_id: UUID
    reason: str
    device_info: str | None = None
    revoked_by_user: bool = True


@dataclass(frozen=True, kw_only=True, slots=True)
class SessionEvictedEvent(DomainEvent):
    """Emitted when a session is evicted due to limit enforcement.

    Triggered when a new session causes the oldest to be automatically
    revoked (FIFO eviction). Handlers may:
    - Log eviction for audit
    - Send notification to user

    Attributes:
        session_id: The evicted session's ID.
        user_id: User who owns the session.
        reason: Why session was evicted (e.g., "session_limit_exceeded").
        device_info: Device info of evicted session.
    """

    session_id: UUID
    user_id: UUID
    reason: str
    device_info: str | None = None


@dataclass(frozen=True, kw_only=True, slots=True)
class AllSessionsRevokedEvent(DomainEvent):
    """Emitted when all sessions for a user are revoked.

    Triggered during password change or security event. Handlers may:
    - Clear all cached sessions
    - Log bulk revocation for audit
    - Send security notification

    Attributes:
        user_id: User whose sessions were revoked.
        reason: Why sessions were revoked.
        session_count: Number of sessions revoked.
        except_session_id: Session that was NOT revoked (current session).
    """

    user_id: UUID
    reason: str
    session_count: int
    except_session_id: UUID | None = None


@dataclass(frozen=True, kw_only=True, slots=True)
class SessionActivityUpdatedEvent(DomainEvent):
    """Emitted when session activity is updated.

    **Operational Event** (single state, NOT 3-state pattern).
    Used for telemetry/monitoring, not a business workflow.

    Triggered when user performs actions. Handlers may:
    - Update cache with new activity timestamp
    - Track for security monitoring

    Handler Requirements:
    - Lightweight (<10ms)
    - Fail-silent (never block business flow)
    - No audit record (unless security threshold exceeded)

    Attributes:
        session_id: The session's ID.
        user_id: User who owns the session.
        ip_address: Current client IP.
        ip_changed: Whether IP changed from session creation.
    """

    session_id: UUID
    user_id: UUID
    ip_address: str | None = None
    ip_changed: bool = False


@dataclass(frozen=True, kw_only=True, slots=True)
class SessionProviderAccessEvent(DomainEvent):
    """Emitted when a session accesses a financial provider.

    **Operational Event** (single state, NOT 3-state pattern).
    Security-relevant: triggers audit record for compliance.

    Dashtam-specific event for tracking provider access per session.
    Used for audit trail when investigating compromised sessions.

    Handler Requirements:
    - May write audit record (security-relevant)
    - Should be lightweight otherwise

    Attributes:
        session_id: The session's ID.
        user_id: User who owns the session.
        provider_name: Provider that was accessed.
    """

    session_id: UUID
    user_id: UUID
    provider_name: str


@dataclass(frozen=True, kw_only=True, slots=True)
class SuspiciousSessionActivityEvent(DomainEvent):
    """Emitted when suspicious activity is detected in a session.

    **Operational Event** (single state, NOT 3-state pattern).
    Security-relevant: triggers audit record and may trigger alerts.

    Triggered by anomaly detection. Handlers may:
    - Alert user via email (if threshold exceeded)
    - Log for security review (audit record)
    - Auto-revoke if threshold exceeded

    Handler Requirements:
    - Security audit record required
    - May trigger alerts (async, non-blocking)

    Attributes:
        session_id: The session's ID.
        user_id: User who owns the session.
        activity_type: Type of suspicious activity.
        details: Additional context about the activity.
        suspicious_count: Total suspicious events for this session.
    """

    session_id: UUID
    user_id: UUID
    activity_type: str
    details: dict[str, str] = field(default_factory=dict)
    suspicious_count: int = 0


@dataclass(frozen=True, kw_only=True, slots=True)
class SessionLimitExceededEvent(DomainEvent):
    """Emitted when user's session limit is exceeded.

    **Operational Event** (single state, NOT 3-state pattern).
    Informational event for monitoring session limit enforcement.

    Triggered during login when new session would exceed limit.
    Handlers may:
    - Log for metrics/monitoring
    - Alert admin (if configured)

    Handler Requirements:
    - Lightweight (<10ms)
    - Fail-silent (never block login flow)
    - No audit record required (informational only)

    Attributes:
        user_id: User who exceeded limit.
        current_count: Current number of active sessions.
        max_sessions: User's session limit.
        evicted_session_id: Session that was evicted (FIFO).
    """

    user_id: UUID
    current_count: int
    max_sessions: int
    evicted_session_id: UUID | None = None
