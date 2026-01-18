"""Container module - Centralized dependency injection.

This module re-exports factory functions from submodules.

    from src.core.container import get_cache, get_user_repository, ...

The container is organized into modules by domain:
- infrastructure: Core services (cache, db, logging, etc.)
- events: Event bus and subscriptions
- repositories: Repository factories
- handler_factory: Auto-wired handler dependency injection
- providers: Financial provider adapter factory
- authorization: Casbin RBAC

Handler Factory:
    All CQRS handlers use handler_factory() for auto-wired dependency injection:

        from src.core.container.handler_factory import handler_factory
        from src.application.commands.handlers.register_user_handler import (
            RegisterUserHandler,
        )

        # In router:
        handler: RegisterUserHandler = Depends(handler_factory(RegisterUserHandler))

        # In tests:
        app.dependency_overrides[handler_factory(RegisterUserHandler)] = (
            lambda: mock_handler
        )

Reference:
    See docs/architecture/dependency-injection.md for complete
    patterns and usage examples.
"""

# Infrastructure services
from src.core.container.infrastructure import (
    get_audit,
    get_audit_session,
    get_cache,
    get_cache_keys,
    get_cache_metrics,
    get_database,
    get_db_session,
    get_device_enricher,
    get_email_service,
    get_encryption_service,
    get_location_enricher,
    get_logger,
    get_password_reset_token_service,
    get_password_service,
    get_provider_connection_cache,
    get_provider_factory,
    get_rate_limit,
    get_refresh_token_service,
    get_secrets,
    get_session_cache,
    get_token_service,
)

# Event bus
from src.core.container.events import get_event_bus

# SSE (Server-Sent Events)
from src.core.container.sse import get_sse_publisher, get_sse_subscriber

# Repositories
from src.core.container.repositories import (
    get_account_repository,
    get_provider_connection_repository,
    get_provider_repository,
    get_transaction_repository,
    get_user_repository,
)

# Handler factory (auto-wired DI for CQRS handlers)
from src.core.container.handler_factory import (
    handler_factory,
    create_handler,
    analyze_handler_dependencies,
    get_supported_dependencies,
)

# Provider factory
from src.core.container.providers import get_provider, is_oauth_provider

# Authorization (Casbin RBAC)
from src.core.container.authorization import (
    get_authorization,
    get_enforcer,
    init_enforcer,
)

__all__ = [
    # Infrastructure
    "get_cache",
    "get_cache_keys",
    "get_cache_metrics",
    "get_secrets",
    "get_encryption_service",
    "get_database",
    "get_db_session",
    "get_audit_session",
    "get_audit",
    "get_password_service",
    "get_token_service",
    "get_email_service",
    "get_rate_limit",
    "get_logger",
    "get_session_cache",
    "get_provider_connection_cache",
    "get_device_enricher",
    "get_location_enricher",
    "get_refresh_token_service",
    "get_password_reset_token_service",
    "get_provider_factory",
    # Events
    "get_event_bus",
    # SSE
    "get_sse_publisher",
    "get_sse_subscriber",
    # Repositories
    "get_user_repository",
    "get_provider_connection_repository",
    "get_provider_repository",
    "get_account_repository",
    "get_transaction_repository",
    # Handler factory
    "handler_factory",
    "create_handler",
    "analyze_handler_dependencies",
    "get_supported_dependencies",
    # Providers
    "get_provider",
    "is_oauth_provider",
    # Authorization
    "init_enforcer",
    "get_enforcer",
    "get_authorization",
]
