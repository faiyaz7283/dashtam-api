"""Create session handler.

Flow:
1. Enrich device info from user agent
2. Enrich location from IP address
3. Check session limit for user tier
4. Evict oldest session if at limit
5. Create session in database
6. Cache session for fast lookups
7. Publish SessionCreated event
8. Return session ID

Architecture:
- Application layer ONLY imports from domain layer (entities, protocols, events)
- NO infrastructure imports (repositories are injected via protocols)
- Handler orchestrates business logic without knowing persistence details
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from src.application.commands.session_commands import CreateSession
from src.core.result import Failure, Result, Success
from src.domain.events.session_events import (
    SessionCreatedEvent,
    SessionEvictedEvent,
)
from src.domain.protocols.event_bus_protocol import EventBusProtocol
from src.domain.protocols.session_cache import SessionCache
from src.domain.protocols.session_enricher import DeviceEnricher, LocationEnricher
from src.domain.protocols.session_repository import SessionData, SessionRepository
from src.domain.protocols.user_repository import UserRepository


# Default session lifetime (30 days)
DEFAULT_SESSION_LIFETIME_DAYS = 30


class CreateSessionError:
    """Create session error reasons."""

    USER_NOT_FOUND = "user_not_found"
    SESSION_LIMIT_EXCEEDED = "session_limit_exceeded"
    EVICTION_FAILED = "eviction_failed"


@dataclass
class CreateSessionResponse:
    """Response data for successful session creation."""

    session_id: UUID
    device_info: str | None
    location: str | None
    expires_at: datetime


class CreateSessionHandler:
    """Handler for session creation command.

    Orchestrates:
    - Device and location enrichment
    - Session limit enforcement (per user tier)
    - Session persistence (database + cache)
    - Domain event publishing
    """

    def __init__(
        self,
        session_repo: SessionRepository,
        session_cache: SessionCache,
        user_repo: UserRepository,
        device_enricher: DeviceEnricher,
        location_enricher: LocationEnricher,
        event_bus: EventBusProtocol,
    ) -> None:
        """Initialize create session handler with dependencies.

        Args:
            session_repo: Session repository for persistence.
            session_cache: Session cache for fast lookups.
            user_repo: User repository to check session tier.
            device_enricher: Device info enricher.
            location_enricher: Location enricher.
            event_bus: Event bus for publishing domain events.
        """
        self._session_repo = session_repo
        self._session_cache = session_cache
        self._user_repo = user_repo
        self._device_enricher = device_enricher
        self._location_enricher = location_enricher
        self._event_bus = event_bus

    async def handle(self, cmd: CreateSession) -> Result[CreateSessionResponse, str]:
        """Handle create session command.

        Args:
            cmd: CreateSession command with user_id, ip_address, user_agent.

        Returns:
            Success(CreateSessionResponse) with session details.
            Failure(error_message) on failure.

        Side Effects:
            - May evict oldest session if at limit (publishes SessionEvictedEvent).
            - Creates session in database.
            - Caches session in Redis.
            - Publishes SessionCreatedEvent.
        """
        # Step 1: Get user to check session tier
        user = await self._user_repo.find_by_id(cmd.user_id)
        if user is None:
            return Failure(error=CreateSessionError.USER_NOT_FOUND)

        # Step 2: Enrich device info
        device_result = await self._device_enricher.enrich(cmd.user_agent or "")
        device_info = device_result.device_info

        # Step 3: Enrich location
        location_result = await self._location_enricher.enrich(cmd.ip_address or "")
        location = location_result.location

        # Step 4: Check session limit
        max_sessions = user.get_max_sessions()
        if max_sessions is not None:
            active_count = await self._session_repo.count_active_sessions(cmd.user_id)

            if active_count >= max_sessions:
                # Evict oldest session (FIFO)
                evict_result = await self._evict_oldest_session(
                    user_id=cmd.user_id,
                    reason="session_limit_exceeded",
                )
                if not evict_result:
                    return Failure(error=CreateSessionError.EVICTION_FAILED)

        # Step 5: Create session
        session_id = uuid4()
        now = datetime.now(UTC)
        expires_at = cmd.expires_at or (
            now + timedelta(days=DEFAULT_SESSION_LIFETIME_DAYS)
        )

        session_data = SessionData(
            id=session_id,
            user_id=cmd.user_id,
            device_info=device_info,
            user_agent=cmd.user_agent,
            ip_address=cmd.ip_address,
            location=location,
            created_at=now,
            last_activity_at=now,
            expires_at=expires_at,
            is_revoked=False,
            is_trusted=False,
            refresh_token_id=cmd.refresh_token_id,
            last_ip_address=cmd.ip_address,
            suspicious_activity_count=0,
        )

        # Step 6: Save to database
        await self._session_repo.save(session_data)

        # Step 7: Cache session
        await self._session_cache.set(session_data)

        # Step 8: Publish event
        await self._event_bus.publish(
            SessionCreatedEvent(
                event_id=uuid4(),
                occurred_at=now,
                session_id=session_id,
                user_id=cmd.user_id,
                device_info=device_info,
                ip_address=cmd.ip_address,
                location=location,
            )
        )

        # Step 9: Return success
        return Success(
            value=CreateSessionResponse(
                session_id=session_id,
                device_info=device_info,
                location=location,
                expires_at=expires_at,
            )
        )

    async def _evict_oldest_session(
        self,
        user_id: UUID,
        reason: str,
    ) -> bool:
        """Evict the oldest active session for a user.

        Args:
            user_id: User identifier.
            reason: Eviction reason for audit.

        Returns:
            True if session evicted, False if no session to evict.
        """
        oldest = await self._session_repo.get_oldest_active_session(user_id)
        if oldest is None:
            return True  # No sessions to evict, OK to proceed

        # Revoke the oldest session
        now = datetime.now(UTC)
        oldest.is_revoked = True
        oldest.revoked_at = now
        oldest.revoked_reason = reason

        await self._session_repo.save(oldest)

        # Remove from cache
        await self._session_cache.delete(oldest.id)
        await self._session_cache.remove_user_session(user_id, oldest.id)

        # Publish eviction event
        await self._event_bus.publish(
            SessionEvictedEvent(
                event_id=uuid4(),
                occurred_at=now,
                session_id=oldest.id,
                user_id=user_id,
                reason=reason,
                device_info=oldest.device_info,
            )
        )

        return True
