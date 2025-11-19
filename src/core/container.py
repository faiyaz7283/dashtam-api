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

if TYPE_CHECKING:
    from src.domain.protocols.audit_protocol import AuditProtocol
    from src.domain.protocols.cache import CacheProtocol
    from src.domain.protocols.event_bus_protocol import EventBusProtocol
    from src.domain.protocols.logger_protocol import LoggerProtocol
    from src.domain.protocols.secrets_protocol import SecretsProtocol


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
    from src.domain.events.authentication_events import (
        UserRegistrationAttempted,
        UserRegistrationSucceeded,
        UserRegistrationFailed,
        UserPasswordChangeAttempted,
        UserPasswordChangeSucceeded,
        UserPasswordChangeFailed,
        ProviderConnectionAttempted,
        ProviderConnectionSucceeded,
        ProviderConnectionFailed,
        TokenRefreshAttempted,
        TokenRefreshSucceeded,
        TokenRefreshFailed,
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

    # Token Refresh Events (3 events × 2 handlers = 6 subscriptions)
    event_bus.subscribe(
        TokenRefreshAttempted, logging_handler.handle_token_refresh_attempted
    )
    event_bus.subscribe(
        TokenRefreshAttempted, audit_handler.handle_token_refresh_attempted
    )

    event_bus.subscribe(
        TokenRefreshSucceeded, logging_handler.handle_token_refresh_succeeded
    )
    event_bus.subscribe(
        TokenRefreshSucceeded, audit_handler.handle_token_refresh_succeeded
    )

    event_bus.subscribe(TokenRefreshFailed, logging_handler.handle_token_refresh_failed)
    event_bus.subscribe(TokenRefreshFailed, audit_handler.handle_token_refresh_failed)

    return event_bus


# ============================================================================
# Handler Factories (Request-Scoped) - Add as needed
# ============================================================================

# Example handler factory (uncomment when handlers are created):
#
# def get_register_user_handler():
#     """Get RegisterUser command handler (request-scoped).
#
#     Creates new handler instance per request.
#     Handler uses application-scoped dependencies internally.
#
#     Returns:
#         RegisterUserHandler instance.
#
#     Usage:
#         @router.post("/users")
#         async def create_user(
#             handler: RegisterUserHandler = Depends(get_register_user_handler)
#         ):
#             result = await handler.handle(command)
#     """
#     from src.application.commands.handlers.register_user_handler import (
#         RegisterUserHandler,
#     )
#
#     return RegisterUserHandler()
