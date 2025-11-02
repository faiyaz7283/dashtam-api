"""Session manager configuration models.

This module provides type-safe configuration models for the session manager
package, including session TTLs, storage options, and audit configuration.

Configuration can be provided via:
- Direct instantiation (for testing)
- Environment variables (production)
- Application settings (framework integration)
"""

from dataclasses import dataclass
from datetime import timedelta
from typing import Literal, Optional


@dataclass
class SessionConfig:
    """Session manager configuration.

    Provides all configuration options for the session manager package,
    including session lifecycle, storage, audit, and security settings.

    Attributes:
        session_ttl: Session time-to-live (default: 30 days)
        inactive_ttl: Inactive session timeout (default: 7 days)
        max_sessions_per_user: Maximum concurrent sessions per user (default: 5)
        backend_type: Session backend strategy ("jwt", "database")
        storage_type: Storage backend ("database", "cache", "memory")
        audit_type: Audit backend ("database", "logger", "noop", "metrics")
        enable_enrichment: Enable session enrichment (location, device)
        trust_forwarded_ip: Trust X-Forwarded-For headers
        require_user_agent: Require User-Agent header

    Example:
        >>> config = SessionConfig(
        ...     session_ttl=timedelta(days=30),
        ...     storage_type="database",
        ...     audit_type="logger",
        ... )
        >>> print(config.session_ttl.days)
        30
    """

    # Session lifecycle
    session_ttl: timedelta = timedelta(days=30)
    inactive_ttl: timedelta = timedelta(days=7)
    max_sessions_per_user: int = 5

    # Backend configuration
    backend_type: Literal["jwt", "database"] = "jwt"
    storage_type: Literal["database", "cache", "memory"] = "database"
    audit_type: Literal["database", "logger", "noop", "metrics"] = "logger"

    # Enrichment configuration
    enable_enrichment: bool = True  # Enable geolocation/device enrichers

    # Security configuration
    trust_forwarded_ip: bool = False  # Trust X-Forwarded-For (use with caution)
    require_user_agent: bool = True  # Require User-Agent header

    def __post_init__(self) -> None:
        """Validate configuration after initialization.

        Raises:
            ValueError: If configuration is invalid
        """
        if self.session_ttl <= timedelta(0):
            raise ValueError("session_ttl must be positive")
        if self.inactive_ttl <= timedelta(0):
            raise ValueError("inactive_ttl must be positive")
        if self.max_sessions_per_user < 1:
            raise ValueError("max_sessions_per_user must be at least 1")


@dataclass
class StorageConfig:
    """Storage backend configuration.

    Provides storage-specific configuration options (TTLs, connection pools, etc.).

    Attributes:
        cache_ttl: Cache entry TTL for cache storage (default: 30 days)
        cache_key_prefix: Prefix for cache keys (default: "session:")
        database_pool_size: Database connection pool size (default: 10)
        enable_cache_fallback: Enable cache fallback for database storage

    Example:
        >>> config = StorageConfig(
        ...     cache_ttl=timedelta(days=30),
        ...     cache_key_prefix="app:session:",
        ... )
    """

    # Cache storage configuration
    cache_ttl: timedelta = timedelta(days=30)
    cache_key_prefix: str = "session:"

    # Database storage configuration
    database_pool_size: int = 10

    # Hybrid storage (database + cache)
    enable_cache_fallback: bool = False


@dataclass
class AuditConfig:
    """Audit backend configuration.

    Provides audit-specific configuration options (retention, sampling, etc.).

    Attributes:
        retention_days: Audit log retention period (default: 90 days)
        sample_rate: Sampling rate for high-volume events (1.0 = 100%)
        log_level: Logging level for logger backend ("DEBUG", "INFO", "WARNING")
        enable_metrics: Enable metrics collection (for metrics backend)

    Example:
        >>> config = AuditConfig(
        ...     retention_days=90,
        ...     sample_rate=1.0,
        ...     log_level="INFO",
        ... )
    """

    # Retention configuration
    retention_days: int = 90

    # Sampling configuration (for high-volume apps)
    sample_rate: float = 1.0  # 1.0 = 100% (no sampling)

    # Logger backend configuration
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    # Metrics backend configuration
    enable_metrics: bool = False

    def __post_init__(self) -> None:
        """Validate configuration after initialization.

        Raises:
            ValueError: If configuration is invalid
        """
        if self.retention_days < 1:
            raise ValueError("retention_days must be at least 1")
        if not 0.0 <= self.sample_rate <= 1.0:
            raise ValueError("sample_rate must be between 0.0 and 1.0")


@dataclass
class EnricherConfig:
    """Session enricher configuration.

    Provides enricher-specific configuration options (geolocation API keys, etc.).

    Attributes:
        enable_geolocation: Enable IP geolocation enrichment
        geolocation_provider: Geolocation provider ("ipapi", "maxmind", "ipstack")
        geolocation_api_key: API key for geolocation provider
        enable_device_fingerprint: Enable device fingerprinting
        device_parser: Device parser library ("user-agents", "ua-parser")

    Example:
        >>> config = EnricherConfig(
        ...     enable_geolocation=True,
        ...     geolocation_provider="ipapi",
        ... )
    """

    # Geolocation enrichment
    enable_geolocation: bool = False
    geolocation_provider: Optional[Literal["ipapi", "maxmind", "ipstack"]] = None
    geolocation_api_key: Optional[str] = None

    # Device fingerprint enrichment
    enable_device_fingerprint: bool = False
    device_parser: Literal["user-agents", "ua-parser"] = "user-agents"


# Default configurations for common scenarios

DEFAULT_CONFIG = SessionConfig(
    session_ttl=timedelta(days=30),
    storage_type="database",
    audit_type="logger",
)

DEVELOPMENT_CONFIG = SessionConfig(
    session_ttl=timedelta(days=7),  # Shorter TTL for dev
    storage_type="memory",  # Fast in-memory storage
    audit_type="logger",  # Console logging
    enable_enrichment=False,  # Skip enrichment in dev
)

PRODUCTION_CONFIG = SessionConfig(
    session_ttl=timedelta(days=30),
    storage_type="database",
    audit_type="database",  # Persistent audit logs
    enable_enrichment=True,  # Full enrichment in prod
)

TESTING_CONFIG = SessionConfig(
    session_ttl=timedelta(minutes=5),  # Short TTL for tests
    storage_type="memory",  # Isolated in-memory storage
    audit_type="noop",  # No audit noise in tests
    enable_enrichment=False,  # Skip enrichment in tests
)
