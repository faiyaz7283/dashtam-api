"""Application-level session manager factory.

This module provides the app-specific factory function that wires the
session_manager package with Dashtam's concrete models and configuration.

This follows the Adapter pattern - the session_manager package is generic,
and this module adapts it to work with Dashtam's specific models and config.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from src.models.session import Session
from src.models.session_audit import SessionAuditLog
from src.session_manager.factory import get_session_manager
from src.session_manager.models.config import SessionConfig
from src.session_manager.service import SessionManagerService


async def get_session_manager_service(
    db_session: AsyncSession,
) -> SessionManagerService:
    """Create SessionManagerService configured for Dashtam application.

    This factory function wires the session_manager package with:
    - Dashtam's RefreshToken model (via SessionAdapter)
    - Dashtam's SessionAuditLog model (via SessionAuditAdapter)
    - Production-ready configuration (database storage + audit)

    Args:
        db_session: Database session for storage and audit operations

    Returns:
        Fully configured SessionManagerService instance

    Usage:
        from src.core.database import get_session

        db_session = await anext(get_session())
        session_manager = await get_session_manager_service(db_session)

        # Now use session_manager for all session operations
        sessions = await session_manager.list_sessions(user_id="...")

    Note:
        This function is async because it may need to initialize enrichers
        or other async components in the future. Currently, it's a simple
        wrapper but keeping it async provides forward compatibility.
    """
    # Production configuration: database storage + database audit
    config = SessionConfig(
        storage_type="database",
        backend_type="database",
        audit_type="database",
    )

    # Wire session_manager with Dashtam's models
    return get_session_manager(
        session_model=Session,  # Session adapter (wraps RefreshToken)
        audit_model=SessionAuditLog,  # Session audit log model
        config=config,
        db_session=db_session,
    )
