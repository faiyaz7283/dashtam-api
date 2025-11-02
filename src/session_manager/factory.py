"""Session manager factory for dependency injection.

This module provides the factory function to create fully-configured
SessionManagerService instances with all dependencies wired together.

The factory follows the Dependency Injection pattern, accepting all external
dependencies (database session, cache client, models) from the application,
and wiring them with the appropriate package implementations.

Usage:
    from src.session_manager.factory import get_session_manager
    from src.models.session import Session
    from src.models.session_audit import SessionAuditLog
    from src.core.database import get_session

    db_session = await anext(get_session())
    manager = get_session_manager(
        session_model=Session,
        audit_model=SessionAuditLog,
        config=SessionConfig(),
        db_session=db_session,
    )
"""

import logging
from typing import Any, List, Optional, Protocol, Type

from sqlalchemy.ext.asyncio import AsyncSession

from src.session_manager.audit.base import SessionAuditBackend
from src.session_manager.audit.database import DatabaseAuditBackend
from src.session_manager.audit.logger import LoggerAuditBackend
from src.session_manager.audit.noop import NoOpAuditBackend
from src.session_manager.backends.base import SessionBackend
from src.session_manager.backends.database_backend import DatabaseSessionBackend
from src.session_manager.backends.jwt_backend import JWTSessionBackend
from src.session_manager.enrichers.base import SessionEnricher
from src.session_manager.models.base import SessionBase
from src.session_manager.models.config import SessionConfig
from src.session_manager.service import SessionManagerService
from src.session_manager.storage.base import SessionStorage
from src.session_manager.storage.cache import CacheSessionStorage
from src.session_manager.storage.database import DatabaseSessionStorage
from src.session_manager.storage.memory import MemorySessionStorage


class CacheClient(Protocol):
    """Protocol for cache clients (Redis, Memcached, etc.).

    Defines the minimal interface required for cache storage.
    Any cache client implementing these methods can be used.
    """

    async def get(self, key: str) -> Optional[bytes]:
        """Retrieve value from cache."""
        ...

    async def set(self, key: str, value: bytes, ttl: Optional[int] = None) -> None:
        """Store value in cache with optional TTL (seconds)."""
        ...

    async def delete(self, key: str) -> None:
        """Delete value from cache."""
        ...


def get_session_manager(
    session_model: Type[SessionBase],
    config: SessionConfig,
    db_session: Optional[AsyncSession] = None,
    cache_client: Optional[CacheClient] = None,
    audit_model: Optional[Type[Any]] = None,
    logger: Optional[logging.Logger] = None,
    enrichers: Optional[List[SessionEnricher]] = None,
) -> SessionManagerService:
    """Create configured SessionManagerService instance.

    Factory function that wires all session manager components together
    based on configuration. Follows Dependency Injection pattern.

    Args:
        session_model: Application's concrete Session model (implements SessionBase)
        config: Session manager configuration
        db_session: Database session (required for "database" storage/audit)
        cache_client: Cache client (required for "cache" storage)
        audit_model: Application's audit model (required for "database" audit)
        logger: Logger instance (optional, uses default if not provided)
        enrichers: Optional list of session enrichers (geolocation, device, etc.)

    Returns:
        Fully configured SessionManagerService instance

    Raises:
        ValueError: If required dependencies are missing for chosen config

    Example:
        >>> from src.session_manager.factory import get_session_manager
        >>> from src.session_manager.models.config import SessionConfig
        >>> from src.models.session import Session
        >>>
        >>> manager = get_session_manager(
        ...     session_model=Session,
        ...     config=SessionConfig(storage_type="memory"),
        ... )

    Example with database storage:
        >>> manager = get_session_manager(
        ...     session_model=Session,
        ...     config=SessionConfig(storage_type="database"),
        ...     db_session=db_session,
        ... )

    Example with full configuration:
        >>> manager = get_session_manager(
        ...     session_model=Session,
        ...     audit_model=SessionAuditLog,
        ...     config=SessionConfig(
        ...         storage_type="database",
        ...         audit_type="database",
        ...     ),
        ...     db_session=db_session,
        ...     enrichers=[GeolocationEnricher(), DeviceFingerprintEnricher()],
        ... )
    """
    # Create backend
    backend = _create_backend(
        config=config,
        session_model=session_model,
        db_session=db_session,
    )

    # Create storage
    storage = _create_storage(
        config=config,
        session_model=session_model,
        db_session=db_session,
        cache_client=cache_client,
    )

    # Create audit backend
    audit = _create_audit_backend(
        config=config,
        db_session=db_session,
        audit_model=audit_model,
        logger=logger,
    )

    # Use provided enrichers or empty list
    enrichers = enrichers or []

    # Create and return service
    return SessionManagerService(
        backend=backend,
        storage=storage,
        audit=audit,
        enrichers=enrichers,
    )


def _create_backend(
    config: SessionConfig,
    session_model: Type[SessionBase],
    db_session: Optional[AsyncSession],
) -> SessionBackend:
    """Create session backend based on configuration.

    Args:
        config: Session manager configuration
        session_model: Application's concrete Session model
        db_session: Database session (required for "database" backend)

    Returns:
        Configured SessionBackend instance

    Raises:
        ValueError: If backend_type is invalid or required dependencies missing
    """
    if config.backend_type == "jwt":
        return JWTSessionBackend(
            session_model=session_model,
            session_ttl_days=config.session_ttl.days,
        )
    elif config.backend_type == "database":
        if db_session is None:
            raise ValueError("db_session is required for 'database' backend")
        return DatabaseSessionBackend(
            session_model=session_model,
            db_session=db_session,
            session_ttl_days=config.session_ttl.days,
        )
    else:
        raise ValueError(
            f"Invalid backend_type: {config.backend_type}. Must be 'jwt' or 'database'"
        )


def _create_storage(
    config: SessionConfig,
    session_model: Type[SessionBase],
    db_session: Optional[AsyncSession],
    cache_client: Optional[CacheClient],
) -> SessionStorage:
    """Create storage backend based on configuration.

    Args:
        config: Session manager configuration
        session_model: Application's concrete Session model
        db_session: Database session (required for "database" storage)
        cache_client: Cache client (required for "cache" storage)

    Returns:
        Configured SessionStorage instance

    Raises:
        ValueError: If storage_type is invalid or required dependencies missing
    """
    if config.storage_type == "database":
        if db_session is None:
            raise ValueError("db_session is required for 'database' storage")
        return DatabaseSessionStorage(
            session_model=session_model,
            db_session=db_session,
        )
    elif config.storage_type == "cache":
        if cache_client is None:
            raise ValueError("cache_client is required for 'cache' storage")
        return CacheSessionStorage(
            session_model=session_model,
            cache_client=cache_client,
            ttl=int(config.session_ttl.total_seconds()),
        )
    elif config.storage_type == "memory":
        return MemorySessionStorage()
    else:
        raise ValueError(
            f"Invalid storage_type: {config.storage_type}. "
            f"Must be 'database', 'cache', or 'memory'"
        )


def _create_audit_backend(
    config: SessionConfig,
    db_session: Optional[AsyncSession],
    audit_model: Optional[Type[Any]],
    logger: Optional[logging.Logger],
) -> SessionAuditBackend:
    """Create audit backend based on configuration.

    Args:
        config: Session manager configuration
        db_session: Database session (required for "database" audit)
        audit_model: Application's audit model (required for "database" audit)
        logger: Logger instance (optional, uses default if not provided)

    Returns:
        Configured SessionAuditBackend instance

    Raises:
        ValueError: If audit_type is invalid or required dependencies missing
    """
    if config.audit_type == "database":
        if db_session is None:
            raise ValueError("db_session is required for 'database' audit")
        if audit_model is None:
            raise ValueError("audit_model is required for 'database' audit")
        return DatabaseAuditBackend(
            audit_model=audit_model,
            db_session=db_session,
        )
    elif config.audit_type == "logger":
        # LoggerAuditBackend takes logger_name, not logger instance
        logger_name = "session_manager.audit"
        return LoggerAuditBackend(logger_name=logger_name)
    elif config.audit_type == "noop":
        return NoOpAuditBackend()
    elif config.audit_type == "metrics":
        # Metrics backend requires external metrics client
        # For now, fall back to NoOp (application can implement custom)
        logging.warning("Metrics audit backend not implemented, using NoOp")
        return NoOpAuditBackend()
    else:
        raise ValueError(
            f"Invalid audit_type: {config.audit_type}. "
            f"Must be 'database', 'logger', 'noop', or 'metrics'"
        )


# Convenience functions for common scenarios


def get_session_manager_for_testing(
    session_model: Type[SessionBase],
) -> SessionManagerService:
    """Create session manager for testing (memory storage, no audit).

    Convenience function for test setup. Uses in-memory storage and
    no-op audit backend for fast, isolated tests.

    Args:
        session_model: Application's concrete Session model

    Returns:
        SessionManagerService configured for testing

    Example:
        >>> from src.models.session import Session
        >>> manager = get_session_manager_for_testing(Session)
    """
    from src.session_manager.models.config import TESTING_CONFIG

    return get_session_manager(
        session_model=session_model,
        config=TESTING_CONFIG,
    )


def get_session_manager_for_development(
    session_model: Type[SessionBase],
    db_session: Optional[AsyncSession] = None,
) -> SessionManagerService:
    """Create session manager for development.

    Convenience function for development setup. Uses memory storage
    by default (fast), with logger audit for visibility.

    Args:
        session_model: Application's concrete Session model
        db_session: Optional database session (if testing with real DB)

    Returns:
        SessionManagerService configured for development

    Example:
        >>> from src.models.session import Session
        >>> manager = get_session_manager_for_development(Session)
    """
    from src.session_manager.models.config import DEVELOPMENT_CONFIG

    return get_session_manager(
        session_model=session_model,
        config=DEVELOPMENT_CONFIG,
        db_session=db_session,
    )
