# mypy: disable-error-code="arg-type"
"""Centralized dependency injection container.

Provides both application-scoped singletons and request-scoped dependencies
for use across all architectural layers.

Architecture:
    - Application-scoped: @lru_cache() decorated functions (singletons)
    - Request-scoped: Generator functions with yield (per-request)

Reference:
    See docs/architecture/dependency-injection-architecture.md for complete
    patterns and usage examples.
"""

from functools import lru_cache
from typing import AsyncGenerator, TYPE_CHECKING

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import get_settings, settings
from src.infrastructure.persistence.database import Database

# ============================================================================
# Type-Checking Only Imports (Circular Import Prevention)
# ============================================================================
# These imports are ONLY executed during type checking (mypy, pyright), NOT at runtime.
#
# Why?
#   - Prevents circular import deadlocks (Container → Adapter → Container → ...)
#   - Type checkers need to see Protocol types for validation
#   - Runtime doesn't need these imports (factories import adapters internally)
#
# How it works:
#   - TYPE_CHECKING = True during static analysis (mypy)
#   - TYPE_CHECKING = False during runtime (python execution)
#   - Return type annotations use string quotes: "AuditProtocol" (forward reference)
#   - Actual imports happen inside factory functions (deferred until needed)
#
# Example:
#   def get_audit() -> "AuditProtocol":  # ← String annotation (not evaluated at runtime)
#       from src.infrastructure.audit.postgres_adapter import PostgresAuditAdapter  # ← Runtime import
#       return PostgresAuditAdapter(...)
#
# Without TYPE_CHECKING guard:
#   - Would cause circular imports if adapter imports from container
#   - Example: Container imports Adapter → Adapter imports get_logger → Container (deadlock!)
#
# With TYPE_CHECKING guard:
#   - Type checkers see the Protocol types for validation
#   - Runtime skips these imports entirely (no circular dependency)
#   - Imports happen lazily inside functions when actually needed
#
# Reference:
#   - PEP 563 (Postponed Evaluation of Annotations)
#   - Python typing docs: https://docs.python.org/3/library/typing.html#typing.TYPE_CHECKING
# ============================================================================
if TYPE_CHECKING:
    from src.domain.protocols.audit_protocol import AuditProtocol
    from src.domain.protocols.cache_protocol import CacheProtocol
    from src.domain.protocols.email_protocol import EmailProtocol
    from src.domain.protocols.event_bus_protocol import EventBusProtocol
    from src.domain.protocols.logger_protocol import LoggerProtocol
    from src.domain.protocols.password_hashing_protocol import PasswordHashingProtocol
    from src.domain.protocols.rate_limit_protocol import RateLimitProtocol
    from src.domain.protocols.secrets_protocol import SecretsProtocol
    from src.domain.protocols.token_generation_protocol import TokenGenerationProtocol
    from src.domain.protocols.authorization_protocol import AuthorizationProtocol

    # Casbin types
    from casbin import AsyncEnforcer

    # Repository types
    from src.infrastructure.persistence.repositories import UserRepository
    from src.infrastructure.persistence.repositories import (
        ProviderConnectionRepository,
    )
    from src.infrastructure.persistence.repositories import AccountRepository

    # Handler types
    from src.application.commands.handlers.register_user_handler import (
        RegisterUserHandler,
    )
    from src.application.commands.handlers.authenticate_user_handler import (
        AuthenticateUserHandler,
    )
    from src.application.commands.handlers.generate_auth_tokens_handler import (
        GenerateAuthTokensHandler,
    )
    from src.application.commands.handlers.create_session_handler import (
        CreateSessionHandler,
    )
    from src.application.commands.handlers.logout_user_handler import LogoutUserHandler
    from src.application.commands.handlers.refresh_access_token_handler import (
        RefreshAccessTokenHandler,
    )
    from src.application.commands.handlers.verify_email_handler import (
        VerifyEmailHandler,
    )
    from src.application.commands.handlers.request_password_reset_handler import (
        RequestPasswordResetHandler,
    )
    from src.application.commands.handlers.confirm_password_reset_handler import (
        ConfirmPasswordResetHandler,
    )
    from src.application.commands.handlers.revoke_session_handler import (
        RevokeSessionHandler,
    )
    from src.application.commands.handlers.revoke_all_sessions_handler import (
        RevokeAllSessionsHandler,
    )
    from src.application.queries.handlers.list_sessions_handler import (
        ListSessionsHandler,
    )
    from src.application.queries.handlers.get_session_handler import GetSessionHandler

    # Token rotation handlers
    from src.application.commands.handlers.trigger_global_rotation_handler import (
        TriggerGlobalTokenRotationHandler,
    )
    from src.application.commands.handlers.trigger_user_rotation_handler import (
        TriggerUserTokenRotationHandler,
    )


# ============================================================================
# Module-Level State (Enforcer Singleton)
# ============================================================================

# Casbin enforcer instance (initialized at startup)
_enforcer: "AsyncEnforcer | None" = None


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
    # Import here to avoid circular dependency
    from redis.asyncio import ConnectionPool, Redis
    from src.infrastructure.cache.redis_adapter import RedisAdapter

    # Create Redis client with connection pooling
    pool = ConnectionPool.from_url(
        settings.redis_url,
        max_connections=50,
        decode_responses=False,  # RedisAdapter handles decoding
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

    # Create and return RedisAdapter
    # mypy limitation: CacheError is subtype of DomainError (correct by LSP),
    # but mypy doesn't recognize this in Protocol return type covariance
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
    # Import here to avoid circular dependency
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

    Usage:
        # Presentation Layer (FastAPI endpoint)
        from fastapi import Depends
        from src.domain.protocols import AuditProtocol

        @router.post("/users")
        async def create_user(
            audit: AuditProtocol = Depends(get_audit),
        ):
            # Step 1: Record ATTEMPT first
            await audit.record(
                action=AuditAction.USER_REGISTRATION_ATTEMPTED,
                user_id=None,
                resource_type="user",
            )
            # Step 2: Business logic
            # ... create user ...
            # Step 3: Record SUCCESS after business commit
            await audit.record(
                action=AuditAction.USER_REGISTERED,
                user_id=user_id,
                resource_type="user",
            )

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

    Returns correct adapter based on database type:
        - PostgreSQL: PostgresAuditAdapter
        - MySQL: MySQLAuditAdapter (future)
        - SQLite: SQLiteAuditAdapter (future/testing)

    Args:
        audit_session: Independent database session for audit operations.
            Injected via Depends(get_audit_session).

    Returns:
        Audit adapter implementing AuditProtocol.

    Usage:
        # Presentation Layer (FastAPI endpoint)
        from fastapi import Depends
        from sqlalchemy.ext.asyncio import AsyncSession
        from src.domain.protocols import AuditProtocol

        @router.post("/users")
        async def create_user(
            session: AsyncSession = Depends(get_db_session),  # Business logic
            audit: AuditProtocol = Depends(get_audit),  # Separate audit session
        ):
            # Step 1: Record ATTEMPT (persists even if business fails)
            await audit.record(
                action=AuditAction.USER_REGISTRATION_ATTEMPTED,
                user_id=None,
                resource_type="user",
                ip_address=request.client.host,
            )
            # Step 2: Business logic creates user and commits
            # ... session.add(user), session.commit() ...
            # Step 3: Record SUCCESS after business commit
            await audit.record(
                action=AuditAction.USER_REGISTERED,
                user_id=user_id,
                resource_type="user",
                ip_address=request.client.host,
            )

    See Also:
        docs/architecture/audit-trail-architecture.md Section 5.2
        for complete audit session architecture and compliance impact.
    """
    # Import here to avoid circular dependency
    from src.infrastructure.audit.postgres_adapter import PostgresAuditAdapter

    # For now, always return PostgreSQL adapter
    # In future, detect database type from settings.database_url
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

    Usage:
        # Application Layer (direct use)
        from src.core.container import get_password_service
        password_service = get_password_service()
        password_hash = password_service.hash_password("SecurePass123!")

        # Presentation Layer (FastAPI Depends)
        from fastapi import Depends
        from src.domain.protocols import PasswordHashingProtocol

        @router.post("/users")
        async def create_user(
            password_service: PasswordHashingProtocol = Depends(get_password_service)
        ):
            password_hash = password_service.hash_password(data.password)

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

    Usage:
        # Application Layer (direct use)
        from src.core.container import get_token_service
        token_service = get_token_service()
        token = token_service.generate_access_token(
            user_id=user_id,
            email=user.email,
            roles=["user"],
        )

        # Presentation Layer (FastAPI Depends)
        from fastapi import Depends
        from src.domain.protocols import TokenGenerationProtocol

        @router.post("/auth/login")
        async def login(
            token_service: TokenGenerationProtocol = Depends(get_token_service)
        ):
            token = token_service.generate_access_token(...)

    Reference:
        - docs/architecture/authentication-architecture.md (Lines 131-173)
    """
    from src.infrastructure.security import JWTService

    return JWTService(
        secret_key=settings.secret_key,
        expiration_minutes=15,  # 15 minutes per auth architecture (not settings default)
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

    Usage:
        # Application Layer (direct use)
        email_service = get_email_service()
        await email_service.send_verification_email(
            to_email="user@example.com",
            verification_url="https://app.com/verify?token=abc123",
        )

        # Presentation Layer (FastAPI Depends)
        from fastapi import Depends
        email_service: EmailProtocol = Depends(get_email_service)

    Reference:
        - docs/architecture/authentication-architecture.md (Lines 272-278)
    """
    # Import here to avoid circular dependency
    from src.infrastructure.email import StubEmailService

    env = (
        settings.environment.value
        if hasattr(settings.environment, "value")
        else str(settings.environment)
    )

    if env == "production":
        # Future: AWS SES implementation
        # from src.infrastructure.email import AWSEmailService
        # return AWSEmailService(region=settings.aws_region)
        #
        # For now, use stub even in production (upgrade later)
        return StubEmailService(logger=get_logger())
    else:
        # Development, testing, CI: Use stub
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

    Usage:
        # Application Layer (direct use)
        rate_limit = get_rate_limit()
        result = await rate_limit.is_allowed(
            endpoint="POST /api/v1/sessions",
            identifier="192.168.1.1",
        )

        # Presentation Layer (FastAPI Depends)
        from fastapi import Depends
        from src.domain.protocols import RateLimitProtocol

        @router.post("/login")
        async def login(
            rate_limit: RateLimitProtocol = Depends(get_rate_limit)
        ):
            result = await rate_limit.is_allowed(...)

    Reference:
        - docs/architecture/rate-limit-architecture.md
    """
    # Import here to avoid circular dependency
    from redis.asyncio import ConnectionPool, Redis

    from src.infrastructure.rate_limit import (
        RATE_LIMIT_RULES,
        RedisStorage,
        TokenBucketAdapter,
    )

    # Create Redis client with same connection pool settings as cache
    # (separate pool for rate limiting to avoid interference)
    pool = ConnectionPool.from_url(
        settings.redis_url,
        max_connections=20,  # Fewer connections than cache (rate limit is simpler)
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

    # Create storage and adapter
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
def get_logger() -> "LoggerProtocol":  # noqa: F821
    """Return the application-scoped logger singleton.

    Adapter selection is centralized here (composition root):
    - development: ConsoleAdapter (human-readable)
    - testing/ci: ConsoleAdapter (JSON)
    - production: CloudWatchAdapter (AWS CloudWatch)

    Returns:
        LoggerProtocol: Logger instance implementing the protocol.
    """
    from datetime import datetime, UTC
    from socket import gethostname

    env = (
        settings.environment.value
        if hasattr(settings.environment, "value")
        else str(settings.environment)
    )

    if env == "production":
        # Lazily import to avoid hard dependency when not in production
        from src.infrastructure.logging.cloudwatch_adapter import CloudWatchAdapter

        log_group = f"/dashtam/{env}/app"
        log_stream = f"{gethostname()}/{datetime.now(UTC).date().isoformat()}"
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
# Domain Events (Application-Scoped)
# ============================================================================


@lru_cache()
def get_event_bus() -> "EventBusProtocol":  # noqa: F821
    """Get event bus singleton (app-scoped).

    Container owns factory logic - decides which adapter based on EVENT_BUS_TYPE.
    This follows the Composition Root pattern (industry best practice).

    Returns correct adapter based on EVENT_BUS_TYPE environment variable:
        - 'in-memory': InMemoryEventBus (MVP, single-server)
        - 'rabbitmq': RabbitMQEventBus (future, distributed)
        - 'kafka': KafkaEventBus (future, high-volume)

    Event handlers are registered at startup (ALL 27 subscriptions):
        - LoggingEventHandler: 12 events (all authentication events)
        - AuditEventHandler: 12 events (all authentication events)
        - EmailEventHandler: 2 SUCCEEDED events (registration, password change)
        - SessionEventHandler: 1 SUCCEEDED event (password change)

    Returns:
        Event bus implementing EventBusProtocol.

    Usage:
        # Application Layer (direct use)
        event_bus = get_event_bus()
        await event_bus.publish(UserRegistrationSucceeded(...))

        # Presentation Layer (FastAPI Depends)
        from fastapi import Depends
        event_bus: EventBusProtocol = Depends(get_event_bus)

    Reference:
        - docs/architecture/domain-events-architecture.md
        - docs/architecture/dependency-injection-architecture.md
    """
    # Import here to avoid circular dependency
    import os
    from src.infrastructure.events.in_memory_event_bus import InMemoryEventBus
    from src.infrastructure.events.handlers.logging_event_handler import (
        LoggingEventHandler,
    )
    from src.infrastructure.events.handlers.audit_event_handler import AuditEventHandler
    from src.infrastructure.events.handlers.email_event_handler import EmailEventHandler
    from src.infrastructure.events.handlers.session_event_handler import (
        SessionEventHandler,
    )
    from src.domain.events.auth_events import (
        UserRegistrationAttempted,
        UserRegistrationSucceeded,
        UserRegistrationFailed,
        UserPasswordChangeAttempted,
        UserPasswordChangeSucceeded,
        UserPasswordChangeFailed,
    )
    from src.domain.events.provider_events import (
        ProviderConnectionAttempted,
        ProviderConnectionSucceeded,
        ProviderConnectionFailed,
        ProviderTokenRefreshAttempted,
        ProviderTokenRefreshSucceeded,
        ProviderTokenRefreshFailed,
    )

    event_bus_type = os.getenv("EVENT_BUS_TYPE", "in-memory")

    if event_bus_type == "in-memory":
        # Create InMemoryEventBus with logger
        event_bus = InMemoryEventBus(logger=get_logger())
    # elif event_bus_type == "rabbitmq":
    #     # Future: RabbitMQ adapter
    #     from src.infrastructure.events.rabbitmq_event_bus import RabbitMQEventBus
    #
    #     event_bus = RabbitMQEventBus(url=os.getenv("RABBITMQ_URL"))
    # elif event_bus_type == "kafka":
    #     # Future: Kafka adapter
    #     from src.infrastructure.events.kafka_event_bus import KafkaEventBus
    #
    #     event_bus = KafkaEventBus(brokers=os.getenv("KAFKA_BROKERS"))
    else:
        raise ValueError(
            f"Unsupported EVENT_BUS_TYPE: {event_bus_type}. "
            f"Supported: 'in-memory' (rabbitmq and kafka: future)"
        )

    # Create event handlers
    logging_handler = LoggingEventHandler(logger=get_logger())

    # Audit handler uses database session from event bus (if provided).
    # Pass both database (fallback) and event_bus (preferred session source).
    # This prevents "Event loop is closed" errors in tests by avoiding
    # session creation inside event handlers.
    audit_handler = AuditEventHandler(database=get_database(), event_bus=event_bus)

    email_handler = EmailEventHandler(logger=get_logger(), settings=get_settings())
    session_handler = SessionEventHandler(logger=get_logger())

    # =========================================================================
    # Subscribe ALL handlers to events (27 subscriptions total)
    # =========================================================================
    # NOTE: mypy shows arg-type errors because handler signatures are more specific
    # (e.g., Callable[[UserRegistrationAttempted], Awaitable[None]]) than the
    # EventHandler type alias (Callable[[DomainEvent], Awaitable[None]]). This is
    # correct by contravariance principle - handlers accepting specific events can
    # safely handle the base type. Runtime behavior is sound, so we suppress mypy
    # at file level (first line of this file).

    # User Registration Events (3 events × 2 handlers = 6 subscriptions)
    event_bus.subscribe(
        UserRegistrationAttempted, logging_handler.handle_user_registration_attempted
    )
    event_bus.subscribe(
        UserRegistrationAttempted, audit_handler.handle_user_registration_attempted
    )

    event_bus.subscribe(
        UserRegistrationSucceeded, logging_handler.handle_user_registration_succeeded
    )
    event_bus.subscribe(
        UserRegistrationSucceeded, audit_handler.handle_user_registration_succeeded
    )
    event_bus.subscribe(
        UserRegistrationSucceeded, email_handler.handle_user_registration_succeeded
    )  # +1 email

    event_bus.subscribe(
        UserRegistrationFailed, logging_handler.handle_user_registration_failed
    )
    event_bus.subscribe(
        UserRegistrationFailed, audit_handler.handle_user_registration_failed
    )

    # User Password Change Events (3 events × 2 handlers + email + session = 9 subscriptions)
    event_bus.subscribe(
        UserPasswordChangeAttempted,
        logging_handler.handle_user_password_change_attempted,
    )
    event_bus.subscribe(
        UserPasswordChangeAttempted, audit_handler.handle_user_password_change_attempted
    )

    event_bus.subscribe(
        UserPasswordChangeSucceeded,
        logging_handler.handle_user_password_change_succeeded,
    )
    event_bus.subscribe(
        UserPasswordChangeSucceeded, audit_handler.handle_user_password_change_succeeded
    )
    event_bus.subscribe(
        UserPasswordChangeSucceeded, email_handler.handle_user_password_change_succeeded
    )  # +1 email
    event_bus.subscribe(
        UserPasswordChangeSucceeded,
        session_handler.handle_user_password_change_succeeded,
    )  # +1 session

    event_bus.subscribe(
        UserPasswordChangeFailed, logging_handler.handle_user_password_change_failed
    )
    event_bus.subscribe(
        UserPasswordChangeFailed, audit_handler.handle_user_password_change_failed
    )

    # Provider Connection Events (3 events × 2 handlers = 6 subscriptions)
    event_bus.subscribe(
        ProviderConnectionAttempted,
        logging_handler.handle_provider_connection_attempted,
    )
    event_bus.subscribe(
        ProviderConnectionAttempted, audit_handler.handle_provider_connection_attempted
    )

    event_bus.subscribe(
        ProviderConnectionSucceeded,
        logging_handler.handle_provider_connection_succeeded,
    )
    event_bus.subscribe(
        ProviderConnectionSucceeded, audit_handler.handle_provider_connection_succeeded
    )

    event_bus.subscribe(
        ProviderConnectionFailed, logging_handler.handle_provider_connection_failed
    )
    event_bus.subscribe(
        ProviderConnectionFailed, audit_handler.handle_provider_connection_failed
    )

    # Provider Token Refresh Events (3 events × 2 handlers = 6 subscriptions)
    event_bus.subscribe(
        ProviderTokenRefreshAttempted,
        logging_handler.handle_provider_token_refresh_attempted,
    )
    event_bus.subscribe(
        ProviderTokenRefreshAttempted,
        audit_handler.handle_provider_token_refresh_attempted,
    )

    event_bus.subscribe(
        ProviderTokenRefreshSucceeded,
        logging_handler.handle_provider_token_refresh_succeeded,
    )
    event_bus.subscribe(
        ProviderTokenRefreshSucceeded,
        audit_handler.handle_provider_token_refresh_succeeded,
    )

    event_bus.subscribe(
        ProviderTokenRefreshFailed, logging_handler.handle_provider_token_refresh_failed
    )
    event_bus.subscribe(
        ProviderTokenRefreshFailed, audit_handler.handle_provider_token_refresh_failed
    )

    return event_bus


# ============================================================================
# Repository Factories (Request-Scoped)
# ============================================================================


async def get_user_repository(
    session: AsyncSession = Depends(get_db_session),
) -> "UserRepository":
    """Get user repository (request-scoped).

    Creates new repository instance per request with database session.
    Repository provides CRUD operations for User domain entities.

    Args:
        session: Database session for request duration.
            Injected via Depends(get_db_session).

    Returns:
        UserRepository instance.

    Usage:
        # Application Layer (command handlers)
        from src.core.container import get_user_repository
        user_repo = await anext(get_user_repository())
        user = await user_repo.find_by_email("user@example.com")

        # Presentation Layer (FastAPI Depends)
        from fastapi import Depends
        from src.infrastructure.persistence.repositories import UserRepository

        @router.post("/users")
        async def create_user(
            user_repo: UserRepository = Depends(get_user_repository)
        ):
            await user_repo.save(user)

    Reference:
        - docs/architecture/authentication-architecture.md (Lines 589-593)
    """
    from src.infrastructure.persistence.repositories import UserRepository

    return UserRepository(session=session)


async def get_provider_connection_repository(
    session: AsyncSession = Depends(get_db_session),
) -> "ProviderConnectionRepository":
    """Get provider connection repository (request-scoped).

    Creates new repository instance per request with database session.
    Repository provides CRUD operations for ProviderConnection domain entities.

    Args:
        session: Database session for request duration.
            Injected via Depends(get_db_session).

    Returns:
        ProviderConnectionRepository instance.

    Usage:
        # Application Layer (command handlers)
        from src.core.container import get_provider_connection_repository
        conn_repo = await anext(get_provider_connection_repository())
        conn = await conn_repo.find_by_id(connection_id)

        # Presentation Layer (FastAPI Depends)
        from fastapi import Depends
        from src.infrastructure.persistence.repositories import ProviderConnectionRepository

        @router.get("/providers/connections/{id}")
        async def get_connection(
            conn_repo: ProviderConnectionRepository = Depends(get_provider_connection_repository)
        ):
            return await conn_repo.find_by_id(id)

    Reference:
        - docs/architecture/repository-pattern.md
    """
    from src.infrastructure.persistence.repositories import (
        ProviderConnectionRepository,
    )

    return ProviderConnectionRepository(session=session)


async def get_account_repository(
    session: AsyncSession = Depends(get_db_session),
) -> "AccountRepository":
    """Get account repository (request-scoped).

    Creates new repository instance per request with database session.
    Repository provides CRUD operations for Account domain entities.

    Args:
        session: Database session for request duration.
            Injected via Depends(get_db_session).

    Returns:
        AccountRepository instance.

    Usage:
        # Application Layer (command handlers)
        from src.core.container import get_account_repository
        account_repo = await anext(get_account_repository())
        account = await repo.find_by_id(account_id)

        # Presentation Layer (FastAPI Depends)
        from fastapi import Depends
        from src.infrastructure.persistence.repositories import AccountRepository

        @router.get("/accounts/{id}")
        async def get_account(
            account_repo: AccountRepository = Depends(get_account_repository)
        ):
            return await account_repo.find_by_id(id)

    Reference:
        - docs/architecture/repository-pattern.md
    """
    from src.infrastructure.persistence.repositories import AccountRepository

    return AccountRepository(session=session)


# ============================================================================
# Handler Factories (Request-Scoped) - Add as needed
# ============================================================================


async def get_register_user_handler(
    session: AsyncSession = Depends(get_db_session),
) -> "RegisterUserHandler":
    """Get RegisterUser command handler (request-scoped).

    Creates new handler instance per request with all required dependencies:
    - UserRepository (request-scoped, uses session)
    - EmailVerificationTokenRepository (request-scoped, uses session)
    - BcryptPasswordService (app-scoped singleton)
    - EventBus (app-scoped singleton)

    Returns:
        RegisterUserHandler instance.

    Usage:
        # Presentation Layer (FastAPI endpoint)
        from fastapi import Depends
        from src.application.commands.handlers.register_user_handler import (
            RegisterUserHandler,
        )

        @router.post("/users")
        async def create_user(
            handler: RegisterUserHandler = Depends(get_register_user_handler)
        ):
            result = await handler.handle(command)

    Reference:
        - docs/architecture/authentication-architecture.md (Lines 250-278)
    """
    from src.application.commands.handlers.register_user_handler import (
        RegisterUserHandler,
    )
    from src.infrastructure.persistence.repositories import (
        UserRepository,
        EmailVerificationTokenRepository,
    )

    # Create repositories with session
    user_repo = UserRepository(session=session)
    verification_token_repo = EmailVerificationTokenRepository(session=session)

    # Get application-scoped singletons
    password_service = get_password_service()
    event_bus = get_event_bus()

    return RegisterUserHandler(
        user_repo=user_repo,
        verification_token_repo=verification_token_repo,
        password_service=password_service,
        event_bus=event_bus,
    )


async def get_authenticate_user_handler(
    session: AsyncSession = Depends(get_db_session),
) -> "AuthenticateUserHandler":
    """Get AuthenticateUser command handler (request-scoped).

    Single responsibility: Verify user credentials.
    Part of 3-handler login orchestration (authenticate → session → tokens).

    Returns:
        AuthenticateUserHandler instance.
    """
    from src.application.commands.handlers.authenticate_user_handler import (
        AuthenticateUserHandler,
    )
    from src.infrastructure.persistence.repositories import UserRepository

    user_repo = UserRepository(session=session)
    password_service = get_password_service()
    event_bus = get_event_bus()

    return AuthenticateUserHandler(
        user_repo=user_repo,
        password_service=password_service,
        event_bus=event_bus,
    )


async def get_generate_auth_tokens_handler(
    session: AsyncSession = Depends(get_db_session),
) -> "GenerateAuthTokensHandler":
    """Get GenerateAuthTokens command handler (request-scoped).

    Single responsibility: Generate JWT + refresh token.
    Part of 3-handler login orchestration (authenticate → session → tokens).

    Returns:
        GenerateAuthTokensHandler instance.
    """
    from src.application.commands.handlers.generate_auth_tokens_handler import (
        GenerateAuthTokensHandler,
    )
    from src.infrastructure.persistence.repositories import (
        RefreshTokenRepository,
        SecurityConfigRepository,
    )
    from src.infrastructure.security.refresh_token_service import RefreshTokenService

    refresh_token_repo = RefreshTokenRepository(session=session)
    security_config_repo = SecurityConfigRepository(session=session)
    token_service = get_token_service()
    refresh_token_service = RefreshTokenService()

    return GenerateAuthTokensHandler(
        token_service=token_service,
        refresh_token_service=refresh_token_service,
        refresh_token_repo=refresh_token_repo,
        security_config_repo=security_config_repo,
    )


async def get_create_session_handler(
    session: AsyncSession = Depends(get_db_session),
) -> "CreateSessionHandler":
    """Get CreateSession command handler (request-scoped).

    Single responsibility: Create session with device/location enrichment.
    Part of 3-handler login orchestration (authenticate → session → tokens).

    Returns:
        CreateSessionHandler instance.
    """
    from src.application.commands.handlers.create_session_handler import (
        CreateSessionHandler,
    )
    from src.infrastructure.persistence.repositories import (
        SessionRepository,
        UserRepository,
    )
    from src.infrastructure.cache import RedisSessionCache
    from src.infrastructure.enrichers.device_enricher import UserAgentDeviceEnricher
    from src.infrastructure.enrichers.location_enricher import IPLocationEnricher

    session_repo = SessionRepository(session=session)
    user_repo = UserRepository(session=session)
    session_cache = RedisSessionCache(redis_adapter=get_cache())
    device_enricher = UserAgentDeviceEnricher()
    location_enricher = IPLocationEnricher()
    event_bus = get_event_bus()

    return CreateSessionHandler(
        session_repo=session_repo,
        session_cache=session_cache,
        user_repo=user_repo,
        device_enricher=device_enricher,
        location_enricher=location_enricher,
        event_bus=event_bus,
    )


async def get_logout_user_handler(
    session: AsyncSession = Depends(get_db_session),
) -> "LogoutUserHandler":
    """Get LogoutUser command handler (request-scoped).

    Returns:
        LogoutUserHandler instance.
    """
    from src.application.commands.handlers.logout_user_handler import LogoutUserHandler
    from src.infrastructure.persistence.repositories import RefreshTokenRepository
    from src.infrastructure.security.refresh_token_service import RefreshTokenService

    refresh_token_repo = RefreshTokenRepository(session=session)
    refresh_token_service = RefreshTokenService()
    event_bus = get_event_bus()

    return LogoutUserHandler(
        refresh_token_repo=refresh_token_repo,
        refresh_token_service=refresh_token_service,
        event_bus=event_bus,
    )


async def get_refresh_token_handler(
    session: AsyncSession = Depends(get_db_session),
) -> "RefreshAccessTokenHandler":
    """Get RefreshAccessToken command handler (request-scoped).

    Returns:
        RefreshAccessTokenHandler instance.
    """
    from src.application.commands.handlers.refresh_access_token_handler import (
        RefreshAccessTokenHandler,
    )
    from src.infrastructure.persistence.repositories import (
        UserRepository,
        RefreshTokenRepository,
        SecurityConfigRepository,
    )
    from src.infrastructure.security.refresh_token_service import RefreshTokenService

    user_repo = UserRepository(session=session)
    refresh_token_repo = RefreshTokenRepository(session=session)
    security_config_repo = SecurityConfigRepository(session=session)
    token_service = get_token_service()
    refresh_token_service = RefreshTokenService()
    event_bus = get_event_bus()

    return RefreshAccessTokenHandler(
        user_repo=user_repo,
        refresh_token_repo=refresh_token_repo,
        security_config_repo=security_config_repo,
        token_service=token_service,
        refresh_token_service=refresh_token_service,
        event_bus=event_bus,
    )


async def get_verify_email_handler(
    session: AsyncSession = Depends(get_db_session),
) -> "VerifyEmailHandler":
    """Get VerifyEmail command handler (request-scoped).

    Returns:
        VerifyEmailHandler instance.
    """
    from src.application.commands.handlers.verify_email_handler import (
        VerifyEmailHandler,
    )
    from src.infrastructure.persistence.repositories import (
        UserRepository,
        EmailVerificationTokenRepository,
    )

    user_repo = UserRepository(session=session)
    verification_token_repo = EmailVerificationTokenRepository(session=session)
    event_bus = get_event_bus()

    return VerifyEmailHandler(
        user_repo=user_repo,
        verification_token_repo=verification_token_repo,
        event_bus=event_bus,
    )


async def get_request_password_reset_handler(
    session: AsyncSession = Depends(get_db_session),
) -> "RequestPasswordResetHandler":
    """Get RequestPasswordReset command handler (request-scoped).

    Returns:
        RequestPasswordResetHandler instance.
    """
    from src.application.commands.handlers.request_password_reset_handler import (
        RequestPasswordResetHandler,
    )
    from src.infrastructure.persistence.repositories import (
        UserRepository,
        PasswordResetTokenRepository,
    )
    from src.infrastructure.security.password_reset_token_service import (
        PasswordResetTokenService,
    )

    user_repo = UserRepository(session=session)
    password_reset_repo = PasswordResetTokenRepository(session=session)
    token_service = PasswordResetTokenService()
    email_service = get_email_service()
    event_bus = get_event_bus()

    return RequestPasswordResetHandler(
        user_repo=user_repo,
        password_reset_repo=password_reset_repo,
        token_service=token_service,
        email_service=email_service,
        event_bus=event_bus,
        verification_url_base=settings.verification_url_base,
    )


async def get_confirm_password_reset_handler(
    session: AsyncSession = Depends(get_db_session),
) -> "ConfirmPasswordResetHandler":
    """Get ConfirmPasswordReset command handler (request-scoped).

    Returns:
        ConfirmPasswordResetHandler instance.
    """
    from src.application.commands.handlers.confirm_password_reset_handler import (
        ConfirmPasswordResetHandler,
    )
    from src.infrastructure.persistence.repositories import (
        UserRepository,
        PasswordResetTokenRepository,
        RefreshTokenRepository,
    )

    user_repo = UserRepository(session=session)
    password_reset_repo = PasswordResetTokenRepository(session=session)
    refresh_token_repo = RefreshTokenRepository(session=session)
    password_service = get_password_service()
    email_service = get_email_service()
    event_bus = get_event_bus()

    return ConfirmPasswordResetHandler(
        user_repo=user_repo,
        password_reset_repo=password_reset_repo,
        refresh_token_repo=refresh_token_repo,
        password_service=password_service,
        email_service=email_service,
        event_bus=event_bus,
    )


# ============================================================================
# Session Management Handler Factories
# ============================================================================


async def get_list_sessions_handler(
    session: AsyncSession = Depends(get_db_session),
) -> "ListSessionsHandler":
    """Get ListSessions query handler (request-scoped).

    Returns:
        ListSessionsHandler instance.
    """
    from src.application.queries.handlers.list_sessions_handler import (
        ListSessionsHandler,
    )
    from src.infrastructure.persistence.repositories import SessionRepository

    session_repo = SessionRepository(session=session)

    return ListSessionsHandler(
        session_repo=session_repo,
    )


async def get_get_session_handler(
    session: AsyncSession = Depends(get_db_session),
) -> "GetSessionHandler":
    """Get GetSession query handler (request-scoped).

    Returns:
        GetSessionHandler instance.
    """
    from src.application.queries.handlers.get_session_handler import GetSessionHandler
    from src.infrastructure.persistence.repositories import SessionRepository
    from src.infrastructure.cache import RedisSessionCache

    session_repo = SessionRepository(session=session)
    session_cache = RedisSessionCache(redis_adapter=get_cache())

    return GetSessionHandler(
        session_repo=session_repo,
        session_cache=session_cache,
    )


async def get_revoke_session_handler(
    session: AsyncSession = Depends(get_db_session),
) -> "RevokeSessionHandler":
    """Get RevokeSession command handler (request-scoped).

    Returns:
        RevokeSessionHandler instance.
    """
    from src.application.commands.handlers.revoke_session_handler import (
        RevokeSessionHandler,
    )
    from src.infrastructure.persistence.repositories import SessionRepository
    from src.infrastructure.cache import RedisSessionCache

    session_repo = SessionRepository(session=session)
    session_cache = RedisSessionCache(redis_adapter=get_cache())
    event_bus = get_event_bus()

    return RevokeSessionHandler(
        session_repo=session_repo,
        session_cache=session_cache,
        event_bus=event_bus,
    )


async def get_revoke_all_sessions_handler(
    session: AsyncSession = Depends(get_db_session),
) -> "RevokeAllSessionsHandler":
    """Get RevokeAllSessions command handler (request-scoped).

    Returns:
        RevokeAllSessionsHandler instance.
    """
    from src.application.commands.handlers.revoke_all_sessions_handler import (
        RevokeAllSessionsHandler,
    )
    from src.infrastructure.persistence.repositories import SessionRepository
    from src.infrastructure.cache import RedisSessionCache

    session_repo = SessionRepository(session=session)
    session_cache = RedisSessionCache(redis_adapter=get_cache())
    event_bus = get_event_bus()

    return RevokeAllSessionsHandler(
        session_repo=session_repo,
        session_cache=session_cache,
        event_bus=event_bus,
    )


# ============================================================================
# Token Rotation Handler Factories
# ============================================================================


async def get_trigger_global_rotation_handler(
    session: AsyncSession = Depends(get_db_session),
) -> "TriggerGlobalTokenRotationHandler":
    """Get TriggerGlobalTokenRotation command handler (request-scoped).

    Admin-only operation for global token rotation.

    Returns:
        TriggerGlobalTokenRotationHandler instance.
    """
    from src.application.commands.handlers.trigger_global_rotation_handler import (
        TriggerGlobalTokenRotationHandler,
    )
    from src.infrastructure.persistence.repositories import SecurityConfigRepository

    security_config_repo = SecurityConfigRepository(session=session)
    event_bus = get_event_bus()

    return TriggerGlobalTokenRotationHandler(
        security_config_repo=security_config_repo,
        event_bus=event_bus,
    )


async def get_trigger_user_rotation_handler(
    session: AsyncSession = Depends(get_db_session),
) -> "TriggerUserTokenRotationHandler":
    """Get TriggerUserTokenRotation command handler (request-scoped).

    Per-user token rotation (password change, log out everywhere).

    Returns:
        TriggerUserTokenRotationHandler instance.
    """
    from src.application.commands.handlers.trigger_user_rotation_handler import (
        TriggerUserTokenRotationHandler,
    )
    from src.infrastructure.persistence.repositories import UserRepository

    user_repo = UserRepository(session=session)
    event_bus = get_event_bus()

    return TriggerUserTokenRotationHandler(
        user_repo=user_repo,
        event_bus=event_bus,
    )


# ============================================================================
# Authorization (Casbin RBAC)
# ============================================================================


async def init_enforcer() -> "AsyncEnforcer":
    """Initialize Casbin AsyncEnforcer at application startup.

    Creates enforcer with:
    - Model config from infrastructure/authorization/model.conf
    - PostgreSQL adapter for persistent policy storage

    MUST be called during FastAPI lifespan startup.
    Enforcer is app-scoped singleton (stored in _enforcer module variable).

    Returns:
        Initialized AsyncEnforcer instance.

    Raises:
        RuntimeError: If enforcer is already initialized.

    Reference:
        - docs/architecture/authorization-architecture.md
    """
    global _enforcer

    if _enforcer is not None:
        raise RuntimeError("Enforcer already initialized")

    import os

    import casbin
    from casbin_async_sqlalchemy_adapter import Adapter as CasbinSQLAdapter

    # Model config path (relative to src/)
    model_path = os.path.join(
        os.path.dirname(__file__),
        "..",
        "infrastructure",
        "authorization",
        "model.conf",
    )

    # Create PostgreSQL adapter for policy storage
    adapter = CasbinSQLAdapter(settings.database_url)

    # Create async enforcer
    _enforcer = casbin.AsyncEnforcer(model_path, adapter)

    # Load policies from database
    await _enforcer.load_policy()

    get_logger().info(
        "casbin_enforcer_initialized",
        model_path=model_path,
    )

    return _enforcer


def get_enforcer() -> "AsyncEnforcer":
    """Get Casbin AsyncEnforcer singleton.

    MUST be called after init_enforcer() during startup.

    Returns:
        The initialized enforcer.

    Raises:
        RuntimeError: If called before init_enforcer().
    """
    if _enforcer is None:
        raise RuntimeError(
            "Enforcer not initialized. Call init_enforcer() during startup."
        )
    return _enforcer


async def get_authorization(
    audit: "AuditProtocol" = Depends(get_audit),
) -> "AuthorizationProtocol":
    """Get authorization adapter (request-scoped).

    Creates CasbinAdapter with:
    - App-scoped enforcer (pre-initialized at startup)
    - Request-scoped audit (for per-request audit logging)
    - App-scoped cache, event_bus, logger

    Args:
        audit: Request-scoped audit adapter for logging authorization checks.

    Returns:
        CasbinAdapter implementing AuthorizationProtocol.

    Usage:
        # Presentation Layer (FastAPI endpoint)
        from fastapi import Depends
        from src.domain.protocols import AuthorizationProtocol

        @router.get("/accounts")
        async def list_accounts(
            auth: AuthorizationProtocol = Depends(get_authorization),
            user: User = Depends(get_current_user),
        ):
            if not await auth.check_permission(user.id, "accounts", "read"):
                raise HTTPException(403, "Permission denied")
            ...

    Reference:
        - docs/architecture/authorization-architecture.md
    """
    from src.infrastructure.authorization.casbin_adapter import CasbinAdapter

    return CasbinAdapter(
        enforcer=get_enforcer(),
        cache=get_cache(),
        audit=audit,
        event_bus=get_event_bus(),
        logger=get_logger(),
    )
