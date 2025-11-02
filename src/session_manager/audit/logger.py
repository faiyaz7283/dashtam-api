"""Logger audit backend - concrete implementation using Python stdlib.

Uses Python's built-in logging module. App configures handlers to control
where logs go (files, syslog, CloudWatch, Datadog, etc.).
"""

import logging
from typing import Any, Dict

from ..models.base import SessionBase
from .base import SessionAuditBackend


class LoggerAuditBackend(SessionAuditBackend):
    """Audit backend using Python's stdlib logging.

    This is a CONCRETE implementation (no abstraction needed).

    App configures logging handlers to control where logs go:
    - Files (FileHandler)
    - Syslog (SysLogHandler)
    - Cloud services (CloudWatch, Stackdriver, etc.)
    - Aggregators (Datadog, Splunk, Elasticsearch, etc.)
    - JSON structured logging (python-json-logger)

    Why Concrete (not abstract):
        - Python logging is a universal standard
        - stdlib module (no external dependencies)
        - Handlers provide the abstraction (not this class)
        - Similar to MemorySessionStorage (concrete)

    Example Configuration (Dashtam):
        ```python
        import logging
        from pythonjsonlogger import jsonlogger

        # Configure JSON logging to file
        logger = logging.getLogger("session_manager.audit")
        handler = logging.FileHandler("/var/log/session_audit.log")
        formatter = jsonlogger.JsonFormatter()
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)

        # Use logger backend
        audit = LoggerAuditBackend(logger_name="session_manager.audit")
        ```

    Example (CloudWatch):
        ```python
        from watchtower import CloudWatchLogHandler

        logger = logging.getLogger("session_manager.audit")
        handler = CloudWatchLogHandler(log_group="/aws/session-manager")
        logger.addHandler(handler)

        # Same interface!
        audit = LoggerAuditBackend(logger_name="session_manager.audit")
        ```
    """

    def __init__(self, logger_name: str = "session_manager.audit"):
        """Initialize with logger name.

        Args:
            logger_name: Logger name (app configures handlers for this logger)
        """
        self.logger = logging.getLogger(logger_name)

    async def log_session_created(
        self, session: SessionBase, context: Dict[str, Any]
    ) -> None:
        """Log session creation event.

        Args:
            session: Newly created session
            context: Additional context
        """
        self.logger.info(
            "Session created",
            extra={
                "event_type": "session_created",
                "session_id": str(session.id),
                "user_id": session.user_id,
                "ip_address": session.ip_address,
                "device_info": session.device_info,
                "location": session.location,
                "created_at": session.created_at.isoformat()
                if session.created_at
                else None,
                **context,
            },
        )

    async def log_session_revoked(
        self, session_id: str, reason: str, context: Dict[str, Any]
    ) -> None:
        """Log session revocation event.

        Args:
            session_id: Revoked session ID
            reason: Revocation reason
            context: Who revoked it, from where
        """
        self.logger.warning(
            "Session revoked",
            extra={
                "event_type": "session_revoked",
                "session_id": session_id,
                "reason": reason,
                **context,
            },
        )

    async def log_session_accessed(
        self, session_id: str, context: Dict[str, Any]
    ) -> None:
        """Log session access event (optional, high-security scenarios).

        Args:
            session_id: Accessed session ID
            context: Access metadata
        """
        self.logger.debug(
            "Session accessed",
            extra={
                "event_type": "session_accessed",
                "session_id": session_id,
                **context,
            },
        )

    async def log_suspicious_activity(
        self, session_id: str, event: str, context: Dict[str, Any]
    ) -> None:
        """Log suspicious activity detected.

        Args:
            session_id: Session involved
            event: Suspicious event type
            context: Event details
        """
        self.logger.error(
            f"Suspicious activity: {event}",
            extra={
                "event_type": "suspicious_activity",
                "session_id": session_id,
                "suspicious_event": event,
                **context,
            },
        )
