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
    from src.domain.protocols.rate_limit_protocol import RateLimitProtocol
    from src.domain.protocols.secrets_protocol import SecretsProtocol
    from src.domain.protocols.token_generation_protocol import TokenGenerationProtocol
    from src.infrastructure.providers.encryption_service import EncryptionService


# ============================================================================
# Application-Scoped Dependencies (Singletons)
# ============================================================================


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

    result = EncryptionService.create(settings.encryption_key)

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

    Returns JWTService with HMAC-SHA256 and 15-minute expiration.
    Service instance is shared across entire application.

    Returns:
        Token generation service implementing TokenGenerationProtocol.

    Reference:
        - docs/architecture/authentication-architecture.md (Lines 131-173)
    """
    from src.infrastructure.security import JWTService

    return JWTService(
        secret_key=settings.secret_key,
        expiration_minutes=15,
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
