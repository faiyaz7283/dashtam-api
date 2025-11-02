"""Session audit backend abstract interface.

This module defines the SessionAuditBackend interface for tracking
session operations (security monitoring, compliance, forensics).
"""

from abc import ABC, abstractmethod
from typing import Any, Dict

from ..models.base import SessionBase


class SessionAuditBackend(ABC):
    """Abstract audit backend for session operations.

    Tracks all session lifecycle events for security monitoring,
    compliance (audit trails), and forensics (incident investigation).

    Design Pattern:
        - Single Responsibility: Only concerns audit logging
        - Interface Segregation: Minimal focused interface
        - Open-Closed: Add new audit backends without changing interface

    Implementations:
        - DatabaseAuditBackend: Persistent, queryable (app provides model)
        - LoggerAuditBackend: Python logging (concrete - stdlib)
        - NoOpAuditBackend: No-op for testing
        - MetricsAuditBackend: Prometheus/StatsD metrics (optional)
    """

    @abstractmethod
    async def log_session_created(
        self, session: SessionBase, context: Dict[str, Any]
    ) -> None:
        """Log session creation event.

        Args:
            session: Newly created session
            context: Additional context (IP, device, location, etc.)

        Examples:
            context = {
                "device": "Mozilla/5.0...",
                "ip": "192.168.1.1",
                "location": "New York, US"
            }
        """
        pass

    @abstractmethod
    async def log_session_revoked(
        self, session_id: str, reason: str, context: Dict[str, Any]
    ) -> None:
        """Log session revocation event.

        Args:
            session_id: Revoked session ID
            reason: Revocation reason ("user_logout", "suspicious_activity", etc.)
            context: Who revoked it, from where

        Examples:
            context = {
                "revoked_by": "user",
                "ip": "192.168.1.1",
                "endpoint": "/api/v1/auth/logout"
            }
        """
        pass

    @abstractmethod
    async def log_session_accessed(
        self, session_id: str, context: Dict[str, Any]
    ) -> None:
        """Log session access event (optional, high-security scenarios).

        Args:
            session_id: Accessed session ID
            context: Access metadata (endpoint, operation, IP)

        Note:
            This is optional and may be verbose. Use for high-security applications.

        Examples:
            context = {
                "endpoint": "/api/v1/providers",
                "method": "GET",
                "ip": "192.168.1.1"
            }
        """
        pass

    @abstractmethod
    async def log_suspicious_activity(
        self, session_id: str, event: str, context: Dict[str, Any]
    ) -> None:
        """Log suspicious activity detected.

        Args:
            session_id: Session involved
            event: Suspicious event type ("multiple_ips", "unusual_location", etc.)
            context: Event details

        Examples:
            context = {
                "event": "multiple_ips",
                "previous_ip": "192.168.1.1",
                "current_ip": "10.0.0.1",
                "time_diff_seconds": 60
            }
        """
        pass
