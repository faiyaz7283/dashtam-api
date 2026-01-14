"""CQRS Registry - Single Source of Truth for Commands and Queries.

This registry catalogs ALL commands and queries in the system with their metadata.
Used for:
- Container auto-wiring (automated handler factory generation)
- Validation tests (verify no drift between commands/handlers)
- Documentation generation (always accurate)
- Gap detection (missing handlers, result DTOs, etc.)

Architecture:
- Application layer (commands/queries are use cases)
- Imported by container for automated wiring
- Verified by tests to catch drift

Adding new commands/queries:
1. Define command/query dataclass in appropriate *_commands.py/*_queries.py file
2. Create handler class in handlers/ directory
3. Add entry to COMMAND_REGISTRY or QUERY_REGISTRY below
4. Run tests - they'll tell you what's missing

Reference:
    - docs/architecture/registry.md
    - docs/architecture/cqrs-registry.md
"""

from src.application.cqrs.metadata import (
    CachePolicy,
    CommandMetadata,
    CQRSCategory,
    QueryMetadata,
)

# ═══════════════════════════════════════════════════════════════════════════
# Import all commands
# ═══════════════════════════════════════════════════════════════════════════
from src.application.commands.auth_commands import (
    AuthenticateUser,
    ConfirmPasswordReset,
    LogoutUser,
    RefreshAccessToken,
    RegisterUser,
    RequestPasswordReset,
    VerifyEmail,
)
from src.application.commands.import_commands import ImportFromFile
from src.application.commands.provider_commands import (
    ConnectProvider,
    DisconnectProvider,
    RefreshProviderTokens,
)
from src.application.commands.rotation_commands import (
    TriggerGlobalTokenRotation,
    TriggerUserTokenRotation,
)
from src.application.commands.session_commands import (
    CreateSession,
    LinkRefreshTokenToSession,
    RecordProviderAccess,
    RevokeAllUserSessions,
    RevokeSession,
    UpdateSessionActivity,
)
from src.application.commands.sync_commands import (
    SyncAccounts,
    SyncHoldings,
    SyncTransactions,
)
from src.application.commands.token_commands import GenerateAuthTokens

# ═══════════════════════════════════════════════════════════════════════════
# Import all command handlers
# ═══════════════════════════════════════════════════════════════════════════
from src.application.commands.handlers.authenticate_user_handler import (
    AuthenticateUserHandler,
)
from src.application.commands.handlers.confirm_password_reset_handler import (
    ConfirmPasswordResetHandler,
)
from src.application.commands.handlers.connect_provider_handler import (
    ConnectProviderHandler,
)
from src.application.commands.handlers.create_session_handler import (
    CreateSessionHandler,
)
from src.application.commands.handlers.disconnect_provider_handler import (
    DisconnectProviderHandler,
)
from src.application.commands.handlers.generate_auth_tokens_handler import (
    GenerateAuthTokensHandler,
)
from src.application.commands.handlers.import_from_file_handler import (
    ImportFromFileHandler,
)
from src.application.commands.handlers.logout_user_handler import LogoutUserHandler
from src.application.commands.handlers.refresh_access_token_handler import (
    RefreshAccessTokenHandler,
)
from src.application.commands.handlers.refresh_provider_tokens_handler import (
    RefreshProviderTokensHandler,
)
from src.application.commands.handlers.register_user_handler import RegisterUserHandler
from src.application.commands.handlers.request_password_reset_handler import (
    RequestPasswordResetHandler,
)
from src.application.commands.handlers.revoke_all_sessions_handler import (
    RevokeAllSessionsHandler,
)
from src.application.commands.handlers.revoke_session_handler import (
    RevokeSessionHandler,
)
from src.application.commands.handlers.sync_accounts_handler import SyncAccountsHandler
from src.application.commands.handlers.sync_holdings_handler import SyncHoldingsHandler
from src.application.commands.handlers.sync_transactions_handler import (
    SyncTransactionsHandler,
)
from src.application.commands.handlers.trigger_global_rotation_handler import (
    TriggerGlobalTokenRotationHandler,
)
from src.application.commands.handlers.trigger_user_rotation_handler import (
    TriggerUserTokenRotationHandler,
)
from src.application.commands.handlers.verify_email_handler import VerifyEmailHandler

# ═══════════════════════════════════════════════════════════════════════════
# Import all queries
# ═══════════════════════════════════════════════════════════════════════════
from src.application.queries.account_queries import (
    GetAccount,
    ListAccountsByConnection,
    ListAccountsByUser,
)
from src.application.queries.balance_snapshot_queries import (
    GetBalanceHistory,
    GetLatestBalanceSnapshots,
    GetUserBalanceHistory,
    ListBalanceSnapshotsByAccount,
)
from src.application.queries.holding_queries import (
    GetHolding,
    ListHoldingsByAccount,
    ListHoldingsByUser,
)
from src.application.queries.provider_queries import (
    GetProviderConnection,
    ListProviderConnections,
)
from src.application.queries.session_queries import (
    GetSession,
    ListUserSessions,
)
from src.application.queries.transaction_queries import (
    GetTransaction,
    ListSecurityTransactions,
    ListTransactionsByAccount,
    ListTransactionsByDateRange,
)

# ═══════════════════════════════════════════════════════════════════════════
# Import all query handlers
# ═══════════════════════════════════════════════════════════════════════════
from src.application.queries.handlers.get_account_handler import GetAccountHandler
from src.application.queries.handlers.list_accounts_handler import (
    ListAccountsByConnectionHandler,
    ListAccountsByUserHandler,
)
from src.application.queries.handlers.balance_snapshot_handlers import (
    GetBalanceHistoryHandler,
    GetLatestBalanceSnapshotsHandler,
    GetUserBalanceHistoryHandler,
    ListBalanceSnapshotsByAccountHandler,
)
from src.application.queries.handlers.get_provider_handler import (
    GetProviderConnectionHandler,
)
from src.application.queries.handlers.list_providers_handler import (
    ListProviderConnectionsHandler,
)
from src.application.queries.handlers.get_session_handler import GetSessionHandler
from src.application.queries.handlers.list_sessions_handler import ListSessionsHandler
from src.application.queries.handlers.get_transaction_handler import (
    GetTransactionHandler,
)
from src.application.queries.handlers.list_transactions_handler import (
    ListTransactionsByAccountHandler,
    ListTransactionsByDateRangeHandler,
    ListSecurityTransactionsHandler,
)
from src.application.queries.handlers.get_holding_handler import GetHoldingHandler
from src.application.queries.handlers.list_holdings_handler import (
    ListHoldingsByAccountHandler,
    ListHoldingsByUserHandler,
)

# ═══════════════════════════════════════════════════════════════════════════
# Import DTOs (for commands with result_dto_class)
# ═══════════════════════════════════════════════════════════════════════════
from src.application.dtos import (
    AuthenticatedUser,
    AuthTokens,
    GlobalRotationResult,
    ImportResult,
    SyncAccountsResult,
    SyncHoldingsResult,
    SyncTransactionsResult,
    UserRotationResult,
)


# ═══════════════════════════════════════════════════════════════════════════
# COMMAND REGISTRY - Single Source of Truth (23 commands)
# ═══════════════════════════════════════════════════════════════════════════

COMMAND_REGISTRY: list[CommandMetadata] = [
    # ═══════════════════════════════════════════════════════════════════════
    # Authentication Commands (7 commands)
    # ═══════════════════════════════════════════════════════════════════════
    CommandMetadata(
        command_class=RegisterUser,
        handler_class=RegisterUserHandler,
        category=CQRSCategory.AUTH,
        has_result_dto=False,  # Returns UUID
        emits_events=True,
        requires_transaction=True,
        description="Register new user account with email verification",
    ),
    CommandMetadata(
        command_class=AuthenticateUser,
        handler_class=AuthenticateUserHandler,
        category=CQRSCategory.AUTH,
        has_result_dto=True,
        result_dto_class=AuthenticatedUser,
        emits_events=True,
        requires_transaction=True,
        description="Authenticate user credentials (no session/tokens)",
    ),
    CommandMetadata(
        command_class=VerifyEmail,
        handler_class=VerifyEmailHandler,
        category=CQRSCategory.AUTH,
        has_result_dto=False,  # Returns None
        emits_events=True,
        requires_transaction=True,
        description="Verify user email address with token",
    ),
    CommandMetadata(
        command_class=RefreshAccessToken,
        handler_class=RefreshAccessTokenHandler,
        category=CQRSCategory.AUTH,
        has_result_dto=True,
        result_dto_class=AuthTokens,
        emits_events=True,
        requires_transaction=True,
        description="Refresh access token using refresh token",
    ),
    CommandMetadata(
        command_class=RequestPasswordReset,
        handler_class=RequestPasswordResetHandler,
        category=CQRSCategory.AUTH,
        has_result_dto=False,  # Returns None (always succeeds publicly)
        emits_events=True,
        requires_transaction=True,
        description="Request password reset email",
    ),
    CommandMetadata(
        command_class=ConfirmPasswordReset,
        handler_class=ConfirmPasswordResetHandler,
        category=CQRSCategory.AUTH,
        has_result_dto=False,  # Returns None
        emits_events=True,
        requires_transaction=True,
        description="Confirm password reset with token and new password",
    ),
    CommandMetadata(
        command_class=LogoutUser,
        handler_class=LogoutUserHandler,
        category=CQRSCategory.AUTH,
        has_result_dto=False,  # Returns None
        emits_events=True,
        requires_transaction=True,
        description="Logout user and revoke refresh token",
    ),
    # ═══════════════════════════════════════════════════════════════════════
    # Session Commands (6 commands)
    # ═══════════════════════════════════════════════════════════════════════
    CommandMetadata(
        command_class=CreateSession,
        handler_class=CreateSessionHandler,
        category=CQRSCategory.SESSION,
        has_result_dto=False,  # Returns UUID (session_id)
        emits_events=True,
        requires_transaction=True,
        description="Create new session with device/location enrichment",
    ),
    CommandMetadata(
        command_class=RevokeSession,
        handler_class=RevokeSessionHandler,
        category=CQRSCategory.SESSION,
        has_result_dto=False,  # Returns None
        emits_events=True,
        requires_transaction=True,
        description="Revoke a specific session",
    ),
    CommandMetadata(
        command_class=RevokeAllUserSessions,
        handler_class=RevokeAllSessionsHandler,
        category=CQRSCategory.SESSION,
        has_result_dto=False,  # Returns int (count)
        emits_events=True,
        requires_transaction=True,
        description="Revoke all sessions for a user (logout everywhere)",
    ),
    # Note: The following 3 session commands don't have dedicated handlers
    # They are internal operations typically handled inline or via session service
    CommandMetadata(
        command_class=LinkRefreshTokenToSession,
        handler_class=CreateSessionHandler,  # Handled inline in CreateSessionHandler
        category=CQRSCategory.SESSION,
        has_result_dto=False,
        emits_events=False,  # Internal operation, no events
        requires_transaction=True,
        description="Link refresh token to session after token generation",
    ),
    CommandMetadata(
        command_class=RecordProviderAccess,
        handler_class=CreateSessionHandler,  # Handled inline or via session service
        category=CQRSCategory.SESSION,
        has_result_dto=False,
        emits_events=True,  # SessionProviderAccessEvent
        requires_transaction=False,  # Can be async/deferred
        description="Record provider access in session for audit",
    ),
    CommandMetadata(
        command_class=UpdateSessionActivity,
        handler_class=CreateSessionHandler,  # Handled inline or via session service
        category=CQRSCategory.SESSION,
        has_result_dto=False,
        emits_events=False,  # Lightweight, no events
        requires_transaction=False,  # Cache update only
        description="Update session last activity timestamp",
    ),
    # ═══════════════════════════════════════════════════════════════════════
    # Token Commands (3 commands)
    # ═══════════════════════════════════════════════════════════════════════
    CommandMetadata(
        command_class=GenerateAuthTokens,
        handler_class=GenerateAuthTokensHandler,
        category=CQRSCategory.TOKEN,
        has_result_dto=True,
        result_dto_class=AuthTokens,
        emits_events=False,  # No events for token generation
        requires_transaction=True,
        description="Generate JWT access token and opaque refresh token",
    ),
    CommandMetadata(
        command_class=TriggerGlobalTokenRotation,
        handler_class=TriggerGlobalTokenRotationHandler,
        category=CQRSCategory.TOKEN,
        has_result_dto=True,
        result_dto_class=GlobalRotationResult,
        emits_events=True,
        requires_transaction=True,
        description="Trigger global token rotation (admin operation)",
    ),
    CommandMetadata(
        command_class=TriggerUserTokenRotation,
        handler_class=TriggerUserTokenRotationHandler,
        category=CQRSCategory.TOKEN,
        has_result_dto=True,
        result_dto_class=UserRotationResult,
        emits_events=True,
        requires_transaction=True,
        description="Trigger per-user token rotation (password change, logout everywhere)",
    ),
    # ═══════════════════════════════════════════════════════════════════════
    # Provider Commands (3 commands)
    # ═══════════════════════════════════════════════════════════════════════
    CommandMetadata(
        command_class=ConnectProvider,
        handler_class=ConnectProviderHandler,
        category=CQRSCategory.PROVIDER,
        has_result_dto=False,  # Returns UUID (connection_id)
        emits_events=True,
        requires_transaction=True,
        description="Connect user to financial provider",
    ),
    CommandMetadata(
        command_class=DisconnectProvider,
        handler_class=DisconnectProviderHandler,
        category=CQRSCategory.PROVIDER,
        has_result_dto=False,  # Returns None
        emits_events=True,
        requires_transaction=True,
        description="Disconnect user from financial provider",
    ),
    CommandMetadata(
        command_class=RefreshProviderTokens,
        handler_class=RefreshProviderTokensHandler,
        category=CQRSCategory.PROVIDER,
        has_result_dto=False,  # Returns None
        emits_events=True,
        requires_transaction=True,
        description="Refresh provider credentials after OAuth token refresh",
    ),
    # ═══════════════════════════════════════════════════════════════════════
    # Data Sync Commands (3 commands)
    # ═══════════════════════════════════════════════════════════════════════
    CommandMetadata(
        command_class=SyncAccounts,
        handler_class=SyncAccountsHandler,
        category=CQRSCategory.DATA_SYNC,
        has_result_dto=True,
        result_dto_class=SyncAccountsResult,
        emits_events=True,
        requires_transaction=True,
        description="Sync accounts from provider connection",
    ),
    CommandMetadata(
        command_class=SyncTransactions,
        handler_class=SyncTransactionsHandler,
        category=CQRSCategory.DATA_SYNC,
        has_result_dto=True,
        result_dto_class=SyncTransactionsResult,
        emits_events=True,
        requires_transaction=True,
        description="Sync transactions from provider connection",
    ),
    CommandMetadata(
        command_class=SyncHoldings,
        handler_class=SyncHoldingsHandler,
        category=CQRSCategory.DATA_SYNC,
        has_result_dto=True,
        result_dto_class=SyncHoldingsResult,
        emits_events=True,
        requires_transaction=True,
        description="Sync holdings from provider connection",
    ),
    # ═══════════════════════════════════════════════════════════════════════
    # Import Commands (1 command)
    # ═══════════════════════════════════════════════════════════════════════
    CommandMetadata(
        command_class=ImportFromFile,
        handler_class=ImportFromFileHandler,
        category=CQRSCategory.IMPORT,
        has_result_dto=True,
        result_dto_class=ImportResult,
        emits_events=True,
        requires_transaction=True,
        description="Import financial data from file (QFX, OFX, CSV)",
    ),
]


# ═══════════════════════════════════════════════════════════════════════════
# QUERY REGISTRY - Single Source of Truth (18 queries)
# ═══════════════════════════════════════════════════════════════════════════

QUERY_REGISTRY: list[QueryMetadata] = [
    # ═══════════════════════════════════════════════════════════════════════
    # Session Queries (2 queries)
    # ═══════════════════════════════════════════════════════════════════════
    QueryMetadata(
        query_class=GetSession,
        handler_class=GetSessionHandler,
        category=CQRSCategory.SESSION,
        is_paginated=False,
        cache_policy=CachePolicy.SHORT,  # Session data can be cached briefly
        description="Get a single session by ID",
    ),
    QueryMetadata(
        query_class=ListUserSessions,
        handler_class=ListSessionsHandler,
        category=CQRSCategory.SESSION,
        is_paginated=False,  # Limited by session limit (typically 5-10)
        cache_policy=CachePolicy.SHORT,
        description="List all sessions for a user",
    ),
    # ═══════════════════════════════════════════════════════════════════════
    # Provider Queries (2 queries)
    # ═══════════════════════════════════════════════════════════════════════
    QueryMetadata(
        query_class=GetProviderConnection,
        handler_class=GetProviderConnectionHandler,
        category=CQRSCategory.PROVIDER,
        is_paginated=False,
        cache_policy=CachePolicy.SHORT,
        description="Get a single provider connection by ID",
    ),
    QueryMetadata(
        query_class=ListProviderConnections,
        handler_class=ListProviderConnectionsHandler,
        category=CQRSCategory.PROVIDER,
        is_paginated=False,  # Limited number of connections per user
        cache_policy=CachePolicy.SHORT,
        description="List all provider connections for a user",
    ),
    # ═══════════════════════════════════════════════════════════════════════
    # Account Queries (3 queries)
    # ═══════════════════════════════════════════════════════════════════════
    QueryMetadata(
        query_class=GetAccount,
        handler_class=GetAccountHandler,
        category=CQRSCategory.DATA_SYNC,
        is_paginated=False,
        cache_policy=CachePolicy.SHORT,
        description="Get a single account by ID",
    ),
    QueryMetadata(
        query_class=ListAccountsByConnection,
        handler_class=ListAccountsByConnectionHandler,
        category=CQRSCategory.DATA_SYNC,
        is_paginated=False,  # Limited accounts per connection
        cache_policy=CachePolicy.SHORT,
        description="List all accounts for a provider connection",
    ),
    QueryMetadata(
        query_class=ListAccountsByUser,
        handler_class=ListAccountsByUserHandler,
        category=CQRSCategory.DATA_SYNC,
        is_paginated=False,  # Moderate number of accounts per user
        cache_policy=CachePolicy.SHORT,
        description="List all accounts for a user across all connections",
    ),
    # ═══════════════════════════════════════════════════════════════════════
    # Transaction Queries (4 queries)
    # ═══════════════════════════════════════════════════════════════════════
    QueryMetadata(
        query_class=GetTransaction,
        handler_class=GetTransactionHandler,
        category=CQRSCategory.DATA_SYNC,
        is_paginated=False,
        cache_policy=CachePolicy.MEDIUM,  # Transactions are immutable
        description="Get a single transaction by ID",
    ),
    QueryMetadata(
        query_class=ListTransactionsByAccount,
        handler_class=ListTransactionsByAccountHandler,
        category=CQRSCategory.DATA_SYNC,
        is_paginated=True,  # Large number of transactions
        cache_policy=CachePolicy.SHORT,
        description="List transactions for an account with pagination",
    ),
    QueryMetadata(
        query_class=ListTransactionsByDateRange,
        handler_class=ListTransactionsByDateRangeHandler,
        category=CQRSCategory.DATA_SYNC,
        is_paginated=False,  # Bounded by date range
        cache_policy=CachePolicy.MEDIUM,  # Historical data rarely changes
        description="List transactions within a date range",
    ),
    QueryMetadata(
        query_class=ListSecurityTransactions,
        handler_class=ListSecurityTransactionsHandler,
        category=CQRSCategory.DATA_SYNC,
        is_paginated=True,  # Can have many trades for a symbol
        cache_policy=CachePolicy.SHORT,
        description="List transactions for a specific security/symbol",
    ),
    # ═══════════════════════════════════════════════════════════════════════
    # Balance Snapshot Queries (4 queries)
    # ═══════════════════════════════════════════════════════════════════════
    QueryMetadata(
        query_class=GetBalanceHistory,
        handler_class=GetBalanceHistoryHandler,
        category=CQRSCategory.DATA_SYNC,
        is_paginated=False,  # Bounded by date range
        cache_policy=CachePolicy.MEDIUM,  # Historical data
        description="Get balance history for an account within date range",
    ),
    QueryMetadata(
        query_class=GetLatestBalanceSnapshots,
        handler_class=GetLatestBalanceSnapshotsHandler,
        category=CQRSCategory.DATA_SYNC,
        is_paginated=False,  # One per account
        cache_policy=CachePolicy.SHORT,  # Frequently accessed
        description="Get latest balance snapshot for each user account",
    ),
    QueryMetadata(
        query_class=GetUserBalanceHistory,
        handler_class=GetUserBalanceHistoryHandler,
        category=CQRSCategory.DATA_SYNC,
        is_paginated=False,  # Bounded by date range
        cache_policy=CachePolicy.MEDIUM,  # Historical data
        description="Get aggregate balance history across all user accounts",
    ),
    QueryMetadata(
        query_class=ListBalanceSnapshotsByAccount,
        handler_class=ListBalanceSnapshotsByAccountHandler,
        category=CQRSCategory.DATA_SYNC,
        is_paginated=False,  # Limited by optional limit param
        cache_policy=CachePolicy.SHORT,
        description="List balance snapshots for a specific account",
    ),
    # ═══════════════════════════════════════════════════════════════════════
    # Holding Queries (3 queries)
    # ═══════════════════════════════════════════════════════════════════════
    QueryMetadata(
        query_class=GetHolding,
        handler_class=GetHoldingHandler,
        category=CQRSCategory.DATA_SYNC,
        is_paginated=False,
        cache_policy=CachePolicy.SHORT,
        description="Get a single holding by ID",
    ),
    QueryMetadata(
        query_class=ListHoldingsByAccount,
        handler_class=ListHoldingsByAccountHandler,
        category=CQRSCategory.DATA_SYNC,
        is_paginated=False,  # Limited positions per account
        cache_policy=CachePolicy.SHORT,
        description="List all holdings for an account",
    ),
    QueryMetadata(
        query_class=ListHoldingsByUser,
        handler_class=ListHoldingsByUserHandler,
        category=CQRSCategory.DATA_SYNC,
        is_paginated=False,  # Moderate number of holdings per user
        cache_policy=CachePolicy.SHORT,
        description="List all holdings for a user across all accounts",
    ),
]
