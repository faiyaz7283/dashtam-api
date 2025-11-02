"""Session manager factory wiring for Dashtam application.

This module wires the session_manager package with Dashtam-specific models,
database session, and cache client. It provides a dependency injection function
to get configured SessionManagerService instances.

Configuration:
    - Backend: JWTSessionBackend (JWT-based sessions)
    - Storage: DatabaseSessionStorage (uses RefreshToken table via Session adapter)
    - Audit: LoggerAuditBackend (Python logging) - can switch to DatabaseAuditBackend
    - Enrichers: None for now (can add geolocation, device fingerprinting later)

Usage:
    ```python
    # In FastAPI endpoint
    session_manager = Depends(get_session_manager)

    # List user sessions
    sessions = await session_manager.list_sessions(
        user_id=str(current_user.id)
    )
    ```
"""

from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from src.models.session import Session
from src.models.session_audit import SessionAuditLog
from src.session_manager.backends.jwt_backend import JWTSessionBackend
from src.session_manager.storage.database import DatabaseSessionStorage
from src.session_manager.audit.logger import LoggerAuditBackend
from src.session_manager.audit.database import DatabaseAuditBackend
from src.session_manager.service import SessionManagerService
from src.core.config import get_settings
from src.core.cache import CacheBackend


def get_session_manager(
    db_session: AsyncSession,
    cache: Optional[CacheBackend] = None,
    use_database_audit: bool = False,
) -> SessionManagerService:
    """Get configured SessionManagerService instance.

    Factory function that wires session_manager package components with
    Dashtam-specific implementations.

    Args:
        db_session: Database session for storage operations
        cache: Cache backend for token blacklist (defaults to singleton)
        use_database_audit: Use database audit backend instead of logger

    Returns:
        Configured SessionManagerService ready to use

    Example:
        ```python
        from fastapi import Depends
        from src.core.database import get_session
        from src.core.session import get_session_manager

        @router.get("/sessions")
        async def list_sessions(
            current_user: User = Depends(get_current_user),
            db_session: AsyncSession = Depends(get_session),
        ):
            session_manager = get_session_manager(db_session)
            sessions = await session_manager.list_sessions(
                user_id=str(current_user.id)
            )
            return sessions
        ```

    Configuration:
        - Backend: JWTSessionBackend (30-day TTL from settings)
        - Storage: DatabaseSessionStorage (RefreshToken via Session adapter)
        - Audit: LoggerAuditBackend or DatabaseAuditBackend
        - Enrichers: None (can be added later)

    Note:
        This function creates a NEW service instance each time.
        For FastAPI, use this in Depends() to get request-scoped instances.
    """
    settings = get_settings()

    # 1. Configure Backend (JWT-based sessions)
    backend = JWTSessionBackend(
        session_model=Session,
        session_ttl_days=settings.REFRESH_TOKEN_EXPIRE_DAYS,  # 30 days
    )

    # 2. Configure Storage (Database using RefreshToken via Session adapter)
    storage = DatabaseSessionStorage(
        db_session=db_session,
        session_model=Session,
    )

    # 3. Configure Audit (Logger or Database)
    if use_database_audit:
        audit = DatabaseAuditBackend(
            db_session=db_session,
            audit_model=SessionAuditLog,
        )
    else:
        audit = LoggerAuditBackend()

    # 4. Configure Enrichers (None for now, can add later)
    # enrichers = [
    #     GeolocationEnricher(geo_service),
    #     DeviceFingerprintEnricher(),
    # ]

    # 5. Wire everything together
    service = SessionManagerService(
        backend=backend,
        storage=storage,
        audit=audit,
        enrichers=None,  # Can add enrichers later
    )

    return service


# Convenience function for FastAPI dependency injection
async def get_session_manager_dependency(
    db_session: AsyncSession,
) -> SessionManagerService:
    """FastAPI dependency for SessionManagerService.

    This is a convenience wrapper that can be used directly in Depends().
    It uses logger audit backend by default.

    Args:
        db_session: Database session (injected by FastAPI)

    Returns:
        Configured SessionManagerService

    Example:
        ```python
        from fastapi import Depends

        @router.get("/sessions")
        async def list_sessions(
            current_user: User = Depends(get_current_user),
            session_manager: SessionManagerService = Depends(get_session_manager_dependency),
        ):
            sessions = await session_manager.list_sessions(
                user_id=str(current_user.id)
            )
            return sessions
        ```
    """
    return get_session_manager(db_session=db_session)
