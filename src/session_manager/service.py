"""Session manager service - orchestrator for complete session lifecycle.

This is the main entry point for session management. It coordinates:
- Backend (domain logic)
- Storage (persistence)
- Audit (logging)
- Enrichers (optional metadata)
"""

from typing import List, Optional

from .audit.base import SessionAuditBackend
from .audit.noop import NoOpAuditBackend
from .backends.base import SessionBackend
from .enrichers.base import SessionEnricher
from .models.base import SessionBase
from .models.filters import SessionFilters
from .storage.base import SessionStorage


class SessionManagerService:
    """Session manager service - orchestrator.

    Coordinates backend, storage, audit, and enrichers to provide
    complete session management functionality.

    This is the "real implementation" that wires everything together.

    Design Pattern:
        - Facade Pattern: Simple interface to complex subsystem
        - Dependency Injection: All dependencies injected
        - Strategy Pattern: Pluggable backend/storage/audit
        - Decorator Pattern: Optional enrichers

    Flow:
        1. Backend creates session domain object
        2. Enrichers add metadata (optional)
        3. Storage persists session
        4. Audit logs event

    Example:
        ```python
        # Wire components together
        backend = JWTSessionBackend(session_ttl_days=30)
        storage = DatabaseSessionStorage(db_session, Session)
        audit = LoggerAuditBackend()

        # Create service
        service = SessionManagerService(
            backend=backend,
            storage=storage,
            audit=audit
        )

        # Use service
        session = await service.create_session(
            user_id="user123",
            device_info="Mozilla/5.0...",
            ip_address="192.168.1.1"
        )
        ```
    """

    def __init__(
        self,
        backend: SessionBackend,
        storage: SessionStorage,
        audit: Optional[SessionAuditBackend] = None,
        enrichers: Optional[List[SessionEnricher]] = None,
    ):
        """Initialize session manager service.

        Args:
            backend: Session backend (JWT, database, custom)
            storage: Session storage (database, cache, memory)
            audit: Optional audit backend (defaults to NoOp)
            enrichers: Optional list of enrichers (geolocation, device, etc.)
        """
        self.backend = backend
        self.storage = storage
        self.audit = audit or NoOpAuditBackend()
        self.enrichers = enrichers or []

    async def create_session(
        self,
        user_id: str,
        device_info: str,
        ip_address: str,
        user_agent: Optional[str] = None,
        **metadata,
    ) -> SessionBase:
        """Create new session (complete flow).

        Args:
            user_id: User identifier
            device_info: Device/browser information
            ip_address: Client IP address
            user_agent: Full user agent string
            **metadata: Additional metadata

        Returns:
            Created session

        Flow:
            1. Backend creates session domain object
            2. Enrichers add metadata (location, device type)
            3. Storage persists session
            4. Audit logs creation event
        """
        # 1. Backend creates domain object
        session = await self.backend.create_session(
            user_id=user_id,
            device_info=device_info,
            ip_address=ip_address,
            user_agent=user_agent,
            **metadata,
        )

        # 2. Enrich session with metadata (optional)
        for enricher in self.enrichers:
            try:
                session = await enricher.enrich(session)
            except Exception:
                # Enrichment failures are non-critical
                # Log but don't block session creation
                pass

        # 3. Storage persists session
        await self.storage.save_session(session)

        # 4. Audit logs event
        await self.audit.log_session_created(
            session,
            context={
                "device": device_info,
                "ip": ip_address,
                "user_agent": user_agent,
            },
        )

        return session

    async def get_session(self, session_id: str) -> Optional[SessionBase]:
        """Get session by ID.

        Args:
            session_id: Session identifier

        Returns:
            Session or None if not found
        """
        return await self.storage.get_session(session_id)

    async def validate_session(self, session_id: str) -> bool:
        """Validate session is active and valid.

        Args:
            session_id: Session identifier

        Returns:
            True if valid, False otherwise
        """
        session = await self.storage.get_session(session_id)
        if not session:
            return False

        return await self.backend.validate_session(session)

    async def list_sessions(
        self, user_id: str, filters: Optional[SessionFilters] = None
    ) -> List[SessionBase]:
        """List sessions for user with optional filters.

        Args:
            user_id: User identifier
            filters: Optional filters (active_only, device_type, etc.)

        Returns:
            List of sessions
        """
        return await self.storage.list_sessions(user_id, filters)

    async def revoke_session(
        self, session_id: str, reason: str, context: Optional[dict] = None
    ) -> bool:
        """Revoke session (complete flow).

        Args:
            session_id: Session to revoke
            reason: Revocation reason
            context: Optional context (who revoked, from where)

        Returns:
            True if revoked, False if not found

        Flow:
            1. Storage fetches session
            2. Backend validates
            3. Storage revokes (updates)
            4. Audit logs revocation
        """
        # 1. Fetch session
        session = await self.storage.get_session(session_id)
        if not session:
            return False

        # 2. Backend validation (optional)
        # Could add business rules here

        # 3. Storage revokes
        revoked = await self.storage.revoke_session(session_id, reason)

        # 4. Audit logs event
        if revoked:
            await self.audit.log_session_revoked(
                session_id, reason, context=context or {}
            )

        return revoked

    async def delete_session(self, session_id: str) -> bool:
        """Permanently delete session.

        Args:
            session_id: Session to delete

        Returns:
            True if deleted, False if not found
        """
        return await self.storage.delete_session(session_id)

    async def revoke_all_user_sessions(
        self, user_id: str, reason: str, except_session_id: Optional[str] = None
    ) -> int:
        """Revoke all sessions for user.

        Args:
            user_id: User identifier
            reason: Revocation reason
            except_session_id: Optional session to keep active

        Returns:
            Number of sessions revoked

        Use Cases:
            - User logout from all devices
            - Security breach response
            - Password change (revoke all except current)
        """
        sessions = await self.storage.list_sessions(user_id)
        revoked_count = 0

        for session in sessions:
            if except_session_id and str(session.id) == except_session_id:
                continue

            if await self.revoke_session(str(session.id), reason):
                revoked_count += 1

        return revoked_count

    async def log_suspicious_activity(
        self, session_id: str, event: str, context: dict
    ) -> None:
        """Log suspicious activity for session.

        Args:
            session_id: Session involved
            event: Suspicious event type
            context: Event details
        """
        await self.audit.log_suspicious_activity(session_id, event, context)
