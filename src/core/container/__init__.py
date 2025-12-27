"""Container module - Centralized dependency injection.

This module re-exports all factory functions from submodules to preserve
backward compatibility. All existing imports continue to work:

    from src.core.container import get_cache, get_user_repository, ...

The container is organized into modules by domain:
- infrastructure: Core services (cache, db, logging, etc.)
- events: Event bus and subscriptions
- repositories: Repository factories
- auth_handlers: Authentication handler factories
- provider_handlers: Provider handler factories
- data_handlers: Account/transaction handler factories
- providers: Financial provider adapter factory
- authorization: Casbin RBAC

Reference:
    See docs/architecture/dependency-injection-architecture.md for complete
    patterns and usage examples.
"""

# Infrastructure services
from src.core.container.infrastructure import (
    get_audit,
    get_audit_session,
    get_cache,
    get_database,
    get_db_session,
    get_email_service,
    get_encryption_service,
    get_logger,
    get_password_service,
    get_rate_limit,
    get_secrets,
    get_token_service,
)

# Event bus
from src.core.container.events import get_event_bus

# Repositories
from src.core.container.repositories import (
    get_account_repository,
    get_provider_connection_repository,
    get_provider_repository,
    get_transaction_repository,
    get_user_repository,
)

# Auth handlers
from src.core.container.auth_handlers import (
    get_authenticate_user_handler,
    get_confirm_password_reset_handler,
    get_create_session_handler,
    get_generate_auth_tokens_handler,
    get_get_session_handler,
    get_list_sessions_handler,
    get_logout_user_handler,
    get_refresh_token_handler,
    get_register_user_handler,
    get_request_password_reset_handler,
    get_revoke_all_sessions_handler,
    get_revoke_session_handler,
    get_trigger_global_rotation_handler,
    get_trigger_user_rotation_handler,
    get_verify_email_handler,
)

# Provider handlers
from src.core.container.provider_handlers import (
    get_connect_provider_handler,
    get_disconnect_provider_handler,
    get_get_provider_connection_handler,
    get_list_provider_connections_handler,
    get_refresh_provider_tokens_handler,
)

# Data handlers (accounts, holdings, transactions, imports)
from src.core.container.data_handlers import (
    get_get_account_handler,
    get_get_transaction_handler,
    get_import_from_file_handler,
    get_list_accounts_by_connection_handler,
    get_list_accounts_by_user_handler,
    get_list_holdings_by_account_handler,
    get_list_holdings_by_user_handler,
    get_list_security_transactions_handler,
    get_list_transactions_by_account_handler,
    get_list_transactions_by_date_range_handler,
    get_sync_accounts_handler,
    get_sync_holdings_handler,
    get_sync_transactions_handler,
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
    # Events
    "get_event_bus",
    # Repositories
    "get_user_repository",
    "get_provider_connection_repository",
    "get_provider_repository",
    "get_account_repository",
    "get_transaction_repository",
    # Auth handlers
    "get_register_user_handler",
    "get_authenticate_user_handler",
    "get_generate_auth_tokens_handler",
    "get_create_session_handler",
    "get_logout_user_handler",
    "get_refresh_token_handler",
    "get_verify_email_handler",
    "get_request_password_reset_handler",
    "get_confirm_password_reset_handler",
    "get_list_sessions_handler",
    "get_get_session_handler",
    "get_revoke_session_handler",
    "get_revoke_all_sessions_handler",
    "get_trigger_global_rotation_handler",
    "get_trigger_user_rotation_handler",
    # Provider handlers
    "get_connect_provider_handler",
    "get_disconnect_provider_handler",
    "get_refresh_provider_tokens_handler",
    "get_get_provider_connection_handler",
    "get_list_provider_connections_handler",
    # Data handlers
    "get_get_account_handler",
    "get_list_accounts_by_connection_handler",
    "get_list_accounts_by_user_handler",
    "get_list_holdings_by_account_handler",
    "get_list_holdings_by_user_handler",
    "get_get_transaction_handler",
    "get_list_transactions_by_account_handler",
    "get_list_transactions_by_date_range_handler",
    "get_list_security_transactions_handler",
    "get_sync_accounts_handler",
    "get_sync_holdings_handler",
    "get_sync_transactions_handler",
    "get_import_from_file_handler",
    # Providers
    "get_provider",
    "is_oauth_provider",
    # Authorization
    "init_enforcer",
    "get_enforcer",
    "get_authorization",
]
