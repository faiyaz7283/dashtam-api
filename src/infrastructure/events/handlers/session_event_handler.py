"""Session event handler stub for domain events.

This module implements a STUB session handler that logs when sessions would be
revoked. Provides structure for future session management service integration
(token service, Redis session store, etc.) without blocking current development.

Session Revocation Strategy (Future):
    - Store active sessions: Redis hash or PostgreSQL table
    - Key: user_id → List of session tokens (JWT JTI claims)
    - On password change: Revoke ALL sessions for user_id
    - Force re-login on all devices (security requirement)

Token Service Integration (Future Phase):
    1. Create SessionProtocol in src/domain/protocols/session_protocol.py
    2. Implement RedisSessionAdapter in src/infrastructure/session/
    3. Store session metadata: {jti, user_id, device_info, created_at, expires_at}
    4. Update this handler to use SessionProtocol.revoke_all_user_sessions()
    5. Add session service to container with get_session_service()

Security Requirements:
    - Password change MUST revoke all sessions (prevent unauthorized access)
    - Users must re-login after password change (inconvenient but secure)
    - Session revocation must be immediate (no grace period)
    - Works with JWT tokens by checking revocation list on each request

Usage:
    >>> # Container wires up subscriptions at startup
    >>> event_bus = get_event_bus()
    >>> session_handler = SessionEventHandler(logger=get_logger())
    >>>
    >>> # Subscribe to UserPasswordChangeSucceeded only
    >>> event_bus.subscribe(UserPasswordChangeSucceeded, session_handler.handle_user_password_change_succeeded)

Reference:
    - docs/architecture/domain-events-architecture.md (Lines 1363-1421)
"""

from src.domain.events.authentication_events import UserPasswordChangeSucceeded
from src.domain.protocols.logger_protocol import LoggerProtocol


class SessionEventHandler:
    """Event handler stub for session revocation.

    STUB IMPLEMENTATION: Currently logs when sessions would be revoked. Replace
    with real SessionProtocol implementation when session service is ready.

    Subscribes to UserPasswordChangeSucceeded only (revoke sessions after
    password change for security).

    Attributes:
        _logger: Logger protocol implementation (from container).

    Example:
        >>> # Create handler
        >>> handler = SessionEventHandler(logger=get_logger())
        >>>
        >>> # Subscribe to events (in container)
        >>> event_bus.subscribe(UserPasswordChangeSucceeded, handler.handle_user_password_change_succeeded)
        >>>
        >>> # Events automatically trigger session revocation logging
        >>> await event_bus.publish(UserPasswordChangeSucceeded(
        ...     user_id=uuid4(),
        ...     initiated_by="user"
        ... ))
        >>> # Log output: {"event": "sessions_would_be_revoked", "user_id": "...", ...}
    """

    def __init__(self, logger: LoggerProtocol) -> None:
        """Initialize session handler with logger.

        Args:
            logger: Logger protocol implementation from container. Used for
                structured logging of session events (stub only).

        Example:
            >>> from src.core.container import get_logger
            >>> logger = get_logger()
            >>> handler = SessionEventHandler(logger=logger)
        """
        self._logger = logger

    async def handle_user_password_change_succeeded(
        self,
        event: UserPasswordChangeSucceeded,
    ) -> None:
        """Revoke all user sessions after password change (STUB).

        STUB: Logs sessions would be revoked. Future: Revoke via SessionProtocol.

        Args:
            event: UserPasswordChangeSucceeded event with user_id.

        Session Revocation Logic (Future):
            1. Fetch all active sessions for user_id from Redis/PostgreSQL
            2. Mark each session as revoked (add JTI to blacklist)
            3. Set TTL on blacklist entries (match JWT expiry)
            4. On next request: Check if JWT JTI is in blacklist
            5. If blacklisted: Return 401 Unauthorized (force re-login)

        Implementation Approaches (Future):

            Approach 1: Redis Blacklist (Recommended)
                - Store: SET user:{user_id}:revoked_sessions → {jti, jti, ...}
                - Check: SISMEMBER user:{user_id}:revoked_sessions {jti}
                - TTL: Set to JWT expiry (auto-cleanup)
                - Pros: Fast (O(1) lookup), automatic expiry
                - Cons: Requires Redis

            Approach 2: PostgreSQL Table
                - Store: CREATE TABLE revoked_sessions (jti, user_id, revoked_at)
                - Check: SELECT EXISTS(SELECT 1 FROM revoked_sessions WHERE jti = ?)
                - Cleanup: Periodic job to delete expired entries
                - Pros: No Redis dependency
                - Cons: Slower (database query per request)

            Approach 3: JWT Claims (Not Recommended)
                - Store: Add "pwd_changed_at" claim to JWT
                - Check: If JWT issued_at < user.password_changed_at → Invalid
                - Pros: No storage needed
                - Cons: Leaks password change timestamp, less flexible

        Security Notes:
            - CRITICAL: All sessions MUST be revoked immediately
            - User inconvenience acceptable (security > convenience)
            - Applies to password changes initiated by user OR admin
            - Session revocation is SYNCHRONOUS (don't fail-open here)
            - Future: Consider notifying user of device logout via push notification

        Example Future Implementation:
            >>> session_service = get_session_service()
            >>> result = await session_service.revoke_all_user_sessions(
            ...     user_id=event.user_id,
            ...     reason="password_changed",
            ... )
            >>> match result:
            ...     case Success(revoked_count):
            ...         logger.info("sessions_revoked", count=revoked_count)
            ...     case Failure(error):
            ...         logger.error("session_revocation_failed", error=str(error))
        """
        self._logger.info(
            "sessions_would_be_revoked",
            user_id=str(event.user_id),
            event_id=str(event.event_id),
            reason="password_changed",
            initiated_by=event.initiated_by,
            security_impact="All user sessions will be revoked. User must re-login on all devices.",
            # Future: Call SessionProtocol.revoke_all_user_sessions()
            note="STUB: Replace with SessionProtocol.revoke_all_user_sessions() when session service ready",
        )
