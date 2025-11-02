"""No-op audit backend - does nothing.

Useful for testing and development when audit logging is not needed.
Default backend if no audit configured.
"""

from typing import Any, Dict

from ..models.base import SessionBase
from .base import SessionAuditBackend


class NoOpAuditBackend(SessionAuditBackend):
    """No-op audit backend.

    Does nothing - all methods are no-ops.

    Use Cases:
        - Testing (don't want audit noise)
        - Development (audit not needed yet)
        - Default fallback (if app doesn't configure audit)

    Example:
        ```python
        # Default audit backend
        audit = NoOpAuditBackend()

        # Or explicitly in factory
        session_manager = get_session_manager(
            audit_type="noop",  # No audit logging
            ...
        )
        ```
    """

    async def log_session_created(
        self, session: SessionBase, context: Dict[str, Any]
    ) -> None:
        """No-op: Do nothing.

        Args:
            session: Newly created session (ignored)
            context: Additional context (ignored)
        """
        pass

    async def log_session_revoked(
        self, session_id: str, reason: str, context: Dict[str, Any]
    ) -> None:
        """No-op: Do nothing.

        Args:
            session_id: Revoked session ID (ignored)
            reason: Revocation reason (ignored)
            context: Who revoked it, from where (ignored)
        """
        pass

    async def log_session_accessed(
        self, session_id: str, context: Dict[str, Any]
    ) -> None:
        """No-op: Do nothing.

        Args:
            session_id: Accessed session ID (ignored)
            context: Access metadata (ignored)
        """
        pass

    async def log_suspicious_activity(
        self, session_id: str, event: str, context: Dict[str, Any]
    ) -> None:
        """No-op: Do nothing.

        Args:
            session_id: Session involved (ignored)
            event: Suspicious event type (ignored)
            context: Event details (ignored)
        """
        pass
