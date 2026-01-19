# mypy: disable-error-code="arg-type"
"""Infrastructure dependency factories.

Application-scoped singletons for core infrastructure services:
- Cache (Redis)
- Secrets (env/AWS)
- Encryption (AES-256-GCM)
- Database (PostgreSQL)
- Password hashing (bcrypt)
- Token generation (JWT)
- Email (stub/AWS SES)
- Rate limiting (token bucket)
- Logging (console/CloudWatch)

Reference:
    See docs/architecture/dependency-injection-architecture.md for complete
    patterns and usage examples.
"""

from functools import lru_cache
from typing import TYPE_CHECKING, AsyncGenerator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.infrastructure.persistence.database import Database

if TYPE_CHECKING:
    from src.domain.protocols.audit_protocol import AuditProtocol
    from src.domain.protocols.cache_protocol import CacheProtocol
    from src.domain.protocols.email_protocol import EmailProtocol
    from src.domain.protocols.logger_protocol import LoggerProtocol
    from src.domain.protocols.password_hashing_protocol import PasswordHashingProtocol
    from src.domain.protocols.password_reset_token_service_protocol import (
        PasswordResetTokenServiceProtocol,
    )
    from src.domain.protocols.provider_factory_protocol import ProviderFactoryProtocol
    from src.domain.protocols.rate_limit_protocol import RateLimitProtocol
    from src.domain.protocols.refresh_token_service_protocol import (
        RefreshTokenServiceProtocol,
    )
    from src.domain.protocols.secrets_protocol import SecretsProtocol
    from src.domain.protocols.session_cache_protocol import SessionCache
    from src.domain.protocols.session_enricher_protocol import (
        DeviceEnricher,
        LocationEnricher,
    )
    from src.domain.protocols.token_generation_protocol import TokenGenerationProtocol
    from src.domain.protocols.provider_connection_cache_protocol import (
        ProviderConnectionCache,
    )
    from src.infrastructure.cache.cache_keys import CacheKeys
    from src.infrastructure.cache.cache_metrics import CacheMetrics
    from src.infrastructure.jobs.monitor import JobsMonitor
    from src.infrastructure.providers.encryption_service import EncryptionService


# ============================================================================
# Application-Scoped Dependencies (Singletons)
# ============================================================================


@lru_cache()
def get_cache_keys() -> "CacheKeys":
    """Get cache keys utility singleton (app-scoped).

    Returns CacheKeys instance for consistent cache key construction.
    Uses configurable prefix from settings.

    Returns:
        CacheKeys utility for key construction.

    Usage:
        # Application Layer (direct use)
        keys = get_cache_keys()
        cache_key = keys.user(user_id)

        # Presentation Layer (FastAPI Depends)
        from fastapi import Depends
        keys: CacheKeys = Depends(get_cache_keys)
    """
    from src.infrastructure.cache.cache_keys import CacheKeys

    return CacheKeys(prefix=settings.cache_key_prefix)


@lru_cache()
def get_cache_metrics() -> "CacheMetrics":
    """Get cache metrics singleton (app-scoped).

    Returns CacheMetrics instance for tracking cache hit/miss/error rates.
    Metrics are in-memory and thread-safe.

    Returns:
        CacheMetrics instance for metrics tracking.

    Usage:
        # Application Layer (direct use)
        metrics = get_cache_metrics()
        metrics.record_hit("user")
        stats = metrics.get_stats("user")

        # Presentation Layer (FastAPI Depends)
        from fastapi import Depends
        metrics: CacheMetrics = Depends(get_cache_metrics)
    """
    from src.infrastructure.cache.cache_metrics import CacheMetrics

    return CacheMetrics()


@lru_cache()
def get_cache() -> "CacheProtocol":
    """Get cache client singleton (app-scoped).

    Returns RedisAdapter with connection pooling.
    Connection pool is shared across entire application.

    Returns:
        Cache client implementing CacheProtocol.

    Usage:
        # Application Layer (direct use)
        cache = get_cache()
        await cache.set("key", "value")

        # Presentation Layer (FastAPI Depends)
        from fastapi import Depends
        cache: CacheProtocol = Depends(get_cache)
    """
    from redis.asyncio import ConnectionPool, Redis

    from src.infrastructure.cache.redis_adapter import RedisAdapter

    pool = ConnectionPool.from_url(
        settings.redis_url,
        max_connections=50,
        decode_responses=False,
        socket_connect_timeout=5,
        socket_timeout=5,
        retry_on_timeout=True,
        socket_keepalive=True,
        socket_keepalive_options={
            1: 1,  # TCP_KEEPIDLE
            2: 1,  # TCP_KEEPINTVL
            3: 5,  # TCP_KEEPCNT
        },
    )
    redis_client = Redis(connection_pool=pool)
    return RedisAdapter(redis_client=redis_client)  # type: ignore[return-value]


@lru_cache()
def get_secrets() -> "SecretsProtocol":
    """Get secrets manager singleton (app-scoped).

    Container owns factory logic - decides which adapter based on SECRETS_BACKEND.
    This follows the Composition Root pattern (industry best practice).

    Returns correct adapter based on SECRETS_BACKEND environment variable:
        - 'env': EnvAdapter (local development)
        - 'aws': AWSAdapter (production)

    Returns:
        Secrets manager implementing SecretsProtocol.

    Raises:
        ValueError: If SECRETS_BACKEND is unsupported or required env vars missing.

    Usage:
        # Application Layer (direct use)
        secrets = get_secrets()
        db_url = secrets.get_secret("database/url")

        # Presentation Layer (FastAPI Depends)
        from fastapi import Depends
        secrets: SecretsProtocol = Depends(get_secrets)
    """
    import os

    backend = os.getenv("SECRETS_BACKEND", "env")

    if backend == "aws":
        from src.infrastructure.secrets.aws_adapter import AWSAdapter

        region = os.getenv("AWS_REGION", "us-east-1")
        return AWSAdapter(environment=settings.environment, region=region)

    elif backend == "env":
        from src.infrastructure.secrets.env_adapter import EnvAdapter

        return EnvAdapter()

    else:
        raise ValueError(
            f"Unsupported SECRETS_BACKEND: {backend}. Supported: 'env', 'aws'"
        )


@lru_cache()
def get_encryption_service() -> "EncryptionService":
    """Get encryption service singleton (app-scoped).

    Returns EncryptionService for encrypting/decrypting provider credentials.
    Uses settings.encryption_key for AES-256-GCM encryption.

    Returns:
        EncryptionService instance.

    Raises:
        RuntimeError: If encryption key is invalid.

    Usage:
        # Application Layer (direct use)
        encryption = get_encryption_service()
        result = encryption.encrypt({"access_token": "..."})

        # Presentation Layer (FastAPI Depends)
        from fastapi import Depends
        encryption: EncryptionService = Depends(get_encryption_service)
    """
    from src.core.result import Failure, Success
    from src.infrastructure.providers.encryption_service import EncryptionService

    # Convert string key to bytes (UTF-8 encoding)
    key_bytes = settings.encryption_key.encode("utf-8")
    result = EncryptionService.create(key_bytes)

    match result:
        case Success(value=service):
            return service
        case Failure(error=err):
            raise RuntimeError(
                f"Failed to initialize encryption service: {err.message}"
            )


@lru_cache()
def get_database() -> Database:
    """Get database manager singleton (app-scoped).

    Returns Database instance with connection pool.
    Use get_db_session() for per-request sessions.

    Returns:
        Database manager instance.

    Note:
        This is rarely used directly. Prefer get_db_session() for sessions.

    Usage:
        # Application Layer (direct use)
        db = get_database()

        # Presentation Layer - use get_db_session() instead
    """
    return Database(
        database_url=settings.database_url,
        echo=settings.db_echo,
    )


# ============================================================================
# Request-Scoped Dependencies (Per-Request)
# ============================================================================


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Get database session (request-scoped).

    Creates new session per request with automatic transaction management:
        - Commits on success
        - Rolls back on exception
        - Always closes session

    Yields:
        Database session for request duration.

    Usage:
        # Presentation Layer (FastAPI endpoint)
        from fastapi import Depends
        from sqlalchemy.ext.asyncio import AsyncSession

        @router.post("/users")
        async def create_user(
            session: AsyncSession = Depends(get_db_session)
        ):
            # Use session
            ...
    """
    db = get_database()
    async with db.get_session() as session:
        yield session


async def get_audit_session() -> AsyncGenerator[AsyncSession, None]:
    """Get audit session (request-scoped, independent lifecycle).

    Creates separate session ONLY for audit logging with immediate commits
    to ensure audit logs persist regardless of request outcome.

    CRITICAL: Audit logs MUST persist even when business transactions fail
    (PCI-DSS 10.2.4, SOC 2 CC6.1, GDPR Article 30 requirements).

    Separate from get_db_session() to prevent audit logs from being lost
    when business transactions roll back.

    Yields:
        Database session for audit operations only.

    See Also:
        docs/architecture/audit-trail-architecture.md Section 5.2
        for complete audit session architecture.
    """
    db = get_database()
    async with db.get_session() as session:
        yield session


async def get_audit(
    audit_session: AsyncSession = Depends(get_audit_session),
) -> "AuditProtocol":
    """Get audit trail adapter (request-scoped with separate session).

    Creates audit adapter instance per request with SEPARATE audit session
    that commits immediately to ensure durability.

    CRITICAL: Uses get_audit_session() (NOT get_db_session()) to ensure
    audit logs persist even when business transactions fail.

    Args:
        audit_session: Independent database session for audit operations.
            Injected via Depends(get_audit_session).

    Returns:
        Audit adapter implementing AuditProtocol.

    See Also:
        docs/architecture/audit-trail-architecture.md Section 5.2
        for complete audit session architecture and compliance impact.
    """
    from src.infrastructure.audit.postgres_adapter import PostgresAuditAdapter

    return PostgresAuditAdapter(session=audit_session)


# ============================================================================
# Security Services (Application-Scoped)
# ============================================================================


@lru_cache()
def get_password_service() -> "PasswordHashingProtocol":
    """Get password hashing service singleton (app-scoped).

    Returns BcryptPasswordService with cost factor 12 (~250ms per hash).
    Service instance is shared across entire application.

    Returns:
        Password hashing service implementing PasswordHashingProtocol.

    Reference:
        - docs/architecture/authentication-architecture.md (Lines 853-875)
    """
    from src.infrastructure.security import BcryptPasswordService

    return BcryptPasswordService(cost_factor=12)


@lru_cache()
def get_token_service() -> "TokenGenerationProtocol":
    """Get JWT token service singleton (app-scoped).

    Returns JWTService with HMAC-SHA256 and configurable expiration.
    Service instance is shared across entire application.

    Configuration:
        - access_token_expire_minutes: Configurable via settings (default: 30)
        - For stricter security, reduce to 15 minutes via environment variable

    Returns:
        Token generation service implementing TokenGenerationProtocol.

    Reference:
        - docs/architecture/authentication-architecture.md (Lines 131-173)
        - F6.5 Security Audit Item 2: Config/Container alignment
    """
    from src.infrastructure.security import JWTService

    return JWTService(
        secret_key=settings.secret_key,
        expiration_minutes=settings.access_token_expire_minutes,
    )


# ============================================================================
# Email Service (Application-Scoped)
# ============================================================================


@lru_cache()
def get_email_service() -> "EmailProtocol":
    """Get email service singleton (app-scoped).

    Container owns factory logic - decides which adapter based on ENVIRONMENT.
    This follows the Composition Root pattern (industry best practice).

    Returns correct adapter based on environment:
        - development/testing/ci: StubEmailService (logs to console)
        - production: AWSEmailService (real AWS SES)

    Returns:
        Email service implementing EmailProtocol.

    Reference:
        - docs/architecture/authentication-architecture.md (Lines 272-278)
    """
    from src.infrastructure.email import StubEmailService

    env = (
        settings.environment.value
        if hasattr(settings.environment, "value")
        else str(settings.environment)
    )

    if env == "production":
        # Future: AWS SES implementation
        return StubEmailService(logger=get_logger())
    else:
        return StubEmailService(logger=get_logger())


# ============================================================================
# Rate Limiting (Application-Scoped)
# ============================================================================


@lru_cache()
def get_rate_limit() -> "RateLimitProtocol":
    """Get rate limiter singleton (app-scoped).

    Creates TokenBucketAdapter with:
    - RedisStorage for atomic token bucket operations
    - Centralized rules configuration from RATE_LIMIT_RULES
    - Event bus for domain event publishing
    - Logger for structured logging

    Fail-Open Design:
        All rate limit operations return allowed=True on infrastructure
        failures. Rate limiting should NEVER cause denial of service.

    Returns:
        Rate limiter implementing RateLimitProtocol.

    Reference:
        - docs/architecture/rate-limit-architecture.md
    """
    from redis.asyncio import ConnectionPool, Redis

    from src.infrastructure.rate_limit import (
        RATE_LIMIT_RULES,
        RedisStorage,
        TokenBucketAdapter,
    )

    # Avoid circular import - import get_event_bus here
    from src.core.container.events import get_event_bus

    pool = ConnectionPool.from_url(
        settings.redis_url,
        max_connections=20,
        decode_responses=False,
        socket_connect_timeout=5,
        socket_timeout=5,
        retry_on_timeout=True,
        socket_keepalive=True,
        socket_keepalive_options={
            1: 1,
            2: 1,
            3: 5,
        },
    )
    redis_client = Redis(connection_pool=pool)

    storage = RedisStorage(redis_client=redis_client)

    return TokenBucketAdapter(
        storage=storage,
        rules=RATE_LIMIT_RULES,
        event_bus=get_event_bus(),
        logger=get_logger(),
    )


# ============================================================================
# Logging (Application-Scoped)
# ============================================================================


@lru_cache()
def get_logger() -> "LoggerProtocol":
    """Return the application-scoped logger singleton.

    Adapter selection is centralized here (composition root):
    - development: ConsoleAdapter (human-readable)
    - testing/ci: ConsoleAdapter (JSON)
    - production: CloudWatchAdapter (AWS CloudWatch)

    Returns:
        LoggerProtocol: Logger instance implementing the protocol.
    """
    from datetime import UTC, datetime
    from socket import gethostname

    env = (
        settings.environment.value
        if hasattr(settings.environment, "value")
        else str(settings.environment)
    )

    # Use settings.instance_id if set, otherwise fall back to hostname
    instance_id = settings.instance_id or gethostname()

    if env == "production":
        from src.infrastructure.logging.cloudwatch_adapter import CloudWatchAdapter

        log_group = f"/dashtam/{env}/app"
        log_stream = f"{instance_id}/{datetime.now(UTC).date().isoformat()}"
        return CloudWatchAdapter(
            log_group=log_group,
            log_stream=log_stream,
            region=settings.aws_region,
        )
    else:
        from src.infrastructure.logging.console_adapter import ConsoleAdapter

        use_json = env in {"testing", "ci"}
        return ConsoleAdapter(use_json=use_json)


# ============================================================================
# Session & Cache Infrastructure (Application-Scoped)
# ============================================================================


@lru_cache()
def get_session_cache() -> "SessionCache":
    """Get session cache singleton (app-scoped).

    Returns RedisSessionCache for session storage with user indexing.
    Uses shared Redis connection pool.

    Returns:
        Session cache implementing SessionCache protocol.
    """
    from src.infrastructure.cache import RedisSessionCache

    return RedisSessionCache(cache=get_cache())


@lru_cache()
def get_provider_connection_cache() -> "ProviderConnectionCache":
    """Get provider connection cache singleton (app-scoped).

    Returns RedisProviderConnectionCache for connection storage.
    Uses shared Redis connection pool.

    Returns:
        Provider connection cache implementing ProviderConnectionCache protocol.
    """
    from src.infrastructure.cache import RedisProviderConnectionCache

    return RedisProviderConnectionCache(cache=get_cache())


# ============================================================================
# Enrichers (Application-Scoped)
# ============================================================================


@lru_cache()
def get_device_enricher() -> "DeviceEnricher":
    """Get device enricher singleton (app-scoped).

    Returns UserAgentDeviceEnricher for parsing user agent strings.

    Returns:
        Device enricher implementing DeviceEnricher protocol.
    """
    from src.infrastructure.enrichers.device_enricher import UserAgentDeviceEnricher

    return UserAgentDeviceEnricher(logger=get_logger())


@lru_cache()
def get_location_enricher() -> "LocationEnricher":
    """Get location enricher singleton (app-scoped).

    Returns IPLocationEnricher for IP geolocation.

    Returns:
        Location enricher implementing LocationEnricher protocol.
    """
    from src.infrastructure.enrichers.location_enricher import IPLocationEnricher

    return IPLocationEnricher(logger=get_logger())


# ============================================================================
# Token Services (Application-Scoped)
# ============================================================================


@lru_cache()
def get_refresh_token_service() -> "RefreshTokenServiceProtocol":
    """Get refresh token service singleton (app-scoped).

    Returns RefreshTokenService for generating and verifying refresh tokens.

    Returns:
        Refresh token service implementing RefreshTokenServiceProtocol.
    """
    from src.infrastructure.security.refresh_token_service import RefreshTokenService

    return RefreshTokenService()


@lru_cache()
def get_password_reset_token_service() -> "PasswordResetTokenServiceProtocol":
    """Get password reset token service singleton (app-scoped).

    Returns PasswordResetTokenService for generating password reset tokens.

    Returns:
        Password reset token service implementing PasswordResetTokenServiceProtocol.
    """
    from src.infrastructure.security.password_reset_token_service import (
        PasswordResetTokenService,
    )

    return PasswordResetTokenService()


# ============================================================================
# Provider Factory (Application-Scoped)
# ============================================================================


@lru_cache()
def get_provider_factory() -> "ProviderFactoryProtocol":
    """Get provider factory singleton (app-scoped).

    Returns ProviderFactory for runtime provider resolution.
    Used by handlers that need to resolve providers dynamically.

    Returns:
        Provider factory implementing ProviderFactoryProtocol.
    """
    from src.infrastructure.providers.provider_factory import ProviderFactory

    return ProviderFactory()


# ============================================================================
# Background Jobs Monitor (Application-Scoped)
# ============================================================================


@lru_cache()
def get_jobs_monitor() -> "JobsMonitor":
    """Get background jobs monitor singleton (app-scoped).

    Returns JobsMonitor for querying the dashtam-jobs background worker service.
    Uses JOBS_REDIS_URL if configured, otherwise falls back to main REDIS_URL.

    The jobs monitor allows the API to check job queue health and status
    without depending on dashtam-jobs code.

    Returns:
        JobsMonitor instance for job queue monitoring.

    Usage:
        # Application Layer (direct use)
        monitor = get_jobs_monitor()
        health = await monitor.check_health()

        # Presentation Layer (FastAPI Depends)
        from fastapi import Depends
        monitor: JobsMonitor = Depends(get_jobs_monitor)
    """
    from redis.asyncio import ConnectionPool, Redis

    from src.infrastructure.jobs.monitor import JobsMonitor

    # Use dedicated jobs Redis URL if configured, otherwise fall back to main Redis
    redis_url = settings.jobs_redis_url or settings.redis_url

    pool = ConnectionPool.from_url(
        redis_url,
        max_connections=10,  # Fewer connections needed for monitoring
        decode_responses=False,
        socket_connect_timeout=5,
        socket_timeout=5,
        retry_on_timeout=True,
    )
    redis_client = Redis(connection_pool=pool)

    return JobsMonitor(
        redis_client=redis_client,
        queue_name=settings.jobs_queue_name,
    )
