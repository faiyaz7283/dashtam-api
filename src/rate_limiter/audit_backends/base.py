"""Audit Backend Interface for Rate Limiting.

This module defines the abstract interface for rate limit violation audit logging.

Architecture:
    - Strategy Pattern: Multiple audit backends can be implemented
    - Dependency Inversion: Services depend on abstraction, not concrete implementations
    - Open/Closed Principle: New backends can be added without modifying existing code
    - Single Responsibility: Each backend handles one audit destination

Example Usage:
    >>> from src.rate_limiter.audit_backends.base import AuditBackend
    >>> from src.rate_limiter.audit_backends.database import DatabaseAuditBackend
    >>>
    >>> # Inject backend via dependency injection
    >>> backend: AuditBackend = DatabaseAuditBackend(db_session)
    >>> await backend.log_violation(
    ...     user_id=uuid.uuid4(),
    ...     ip_address="192.168.1.1",
    ...     endpoint="/api/v1/providers",
    ...     rule_name="provider_list",
    ...     limit=100,
    ...     window_seconds=60,
    ...     violation_count=1
    ... )
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional
from uuid import UUID


class AuditBackend(ABC):
    """Abstract interface for rate limit violation audit logging.

    This interface defines the contract that all audit backends must implement.
    Backends can log to database, file, external service, or multiple destinations.

    Design Principles:
        - SOLID: Strategy Pattern (Open/Closed, Dependency Inversion)
        - DRY: Single source of truth for audit interface
        - Testability: Easy to mock for testing
        - Extensibility: New backends without changing existing code

    Implementations:
        - DatabaseAuditBackend: Logs to PostgreSQL (src.rate_limiter.audit_backends.database)
        - Future: FileAuditBackend, SyslogAuditBackend, etc.

    Example:
        >>> class MyCustomBackend(AuditBackend):
        ...     async def log_violation(self, **kwargs):
        ...         # Custom implementation
        ...         pass
    """

    @abstractmethod
    async def log_violation(
        self,
        ip_address: str,
        endpoint: str,
        rule_name: str,
        limit: int,
        window_seconds: int,
        violation_count: int,
        user_id: Optional[UUID] = None,
        timestamp: Optional[datetime] = None,
    ) -> None:
        """Log a rate limit violation.

        Records when a client exceeds rate limits for security analysis,
        monitoring, and compliance.

        Args:
            ip_address: Client IP address (IPv4 or IPv6)
            endpoint: API endpoint that was rate limited (e.g., "/api/v1/auth/login")
            rule_name: Name of the rate limit rule violated (e.g., "auth_login")
            limit: Maximum requests allowed in the window
            window_seconds: Time window for the limit (in seconds)
            violation_count: How many requests exceeded the limit (typically 1)
            user_id: Optional user ID if request was authenticated
            timestamp: Optional custom timestamp (defaults to current UTC time)

        Returns:
            None

        Raises:
            Exception: Implementation-specific exceptions (e.g., database errors)

        Example:
            >>> await backend.log_violation(
            ...     ip_address="192.168.1.1",
            ...     endpoint="/api/v1/auth/login",
            ...     rule_name="auth_login",
            ...     limit=5,
            ...     window_seconds=60,
            ...     violation_count=1,
            ...     user_id=uuid.uuid4()
            ... )

        Notes:
            - Implementations should handle errors gracefully (fail-open for audit)
            - Timestamp defaults to current UTC time if not provided
            - user_id is optional for unauthenticated requests
        """
        pass
