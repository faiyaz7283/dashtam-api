"""Security config repository protocol for persistence abstraction.

This module defines the port (interface) for security config persistence.
Infrastructure layer implements the adapter.

Reference:
    - docs/architecture/token-breach-rotation-architecture.md
"""

from datetime import datetime
from typing import Protocol

from src.domain.entities.security_config import SecurityConfig


class SecurityConfigRepository(Protocol):
    """Security config repository protocol (port) for persistence.

    Defines the interface for security config storage operations.
    Infrastructure layer provides the adapter implementation.

    This follows hexagonal architecture: domain defines ports,
    infrastructure implements adapters.

    Note:
        SecurityConfig is a singleton table (only one row with id=1).
        The get() method returns None if not initialized.

    Example:
        >>> class PostgresSecurityConfigRepository:
        ...     async def get(self) -> SecurityConfig | None:
        ...         # Fetch from PostgreSQL
        ...         ...
        ...
        >>> # PostgresSecurityConfigRepository implements SecurityConfigRepository
        >>> # via structural typing (no inheritance needed)
    """

    async def get(self) -> SecurityConfig | None:
        """Get the security configuration.

        Returns the singleton security config row.

        Returns:
            SecurityConfig if exists, None if not initialized.
        """
        ...

    async def get_or_create_default(self) -> SecurityConfig:
        """Get security config or create with defaults.

        Ensures the singleton config row exists.
        Creates with default values if missing.

        Returns:
            SecurityConfig: The singleton configuration.

        Default values:
            - global_min_token_version: 1
            - grace_period_seconds: 300 (5 minutes)
        """
        ...

    async def update_global_version(
        self,
        new_version: int,
        reason: str,
        rotation_time: datetime,
    ) -> SecurityConfig:
        """Update global minimum token version.

        Used to trigger global token rotation (invalidate all tokens
        with version below new_version).

        Args:
            new_version: New global minimum token version.
            reason: Reason for rotation (for audit trail).
            rotation_time: When rotation was triggered.

        Returns:
            Updated SecurityConfig.

        Raises:
            ValueError: If new_version <= current version.
        """
        ...

    async def update_grace_period(
        self,
        grace_period_seconds: int,
    ) -> SecurityConfig:
        """Update grace period for token rotation.

        Args:
            grace_period_seconds: New grace period in seconds.

        Returns:
            Updated SecurityConfig.

        Raises:
            ValueError: If grace_period_seconds < 0.
        """
        ...
