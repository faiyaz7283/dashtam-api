"""API Route Registry - Single Source of Truth for all routes.

This module contains ROUTE_REGISTRY, the authoritative list of all API endpoints.
The registry is used to generate FastAPI routes, rate limit rules, auth dependencies,
and OpenAPI metadata at application startup.

Registry structure:
    - 37 total endpoints across 13 resource categories
    - Each entry is a RouteMetadata instance with complete specification
    - Handlers reference actual functions from router modules
    - Auth policies explicitly declared (PUBLIC, AUTHENTICATED, ADMIN, MANUAL_AUTH)
    - Rate limit policies assigned based on endpoint sensitivity

Usage:
    from src.presentation.routers.api.v1.routes.registry import ROUTE_REGISTRY
    from src.presentation.routers.api.v1.routes.generator import register_routes_from_registry

    router = APIRouter(prefix="/api/v1")
    register_routes_from_registry(router, ROUTE_REGISTRY)

Reference:
    - docs/architecture/registry-pattern-architecture.md
"""

from src.presentation.routers.api.v1.routes.metadata import (
    AuthLevel,
    AuthPolicy,
    ErrorSpec,
    HTTPMethod,
    IdempotencyLevel,
    RateLimitPolicy,
    RouteMetadata,
)

# Import handlers from router modules
from src.presentation.routers.api.v1.accounts import (
    get_account,
    list_accounts,
    list_accounts_by_connection,
    sync_accounts,
)
from src.presentation.routers.api.v1.admin.token_rotation import (
    create_global_rotation,
    create_user_rotation,
    get_security_config,
)
from src.presentation.routers.api.v1.balance_snapshots import (
    get_balance_history,
    get_latest_snapshots,
    list_balance_snapshots,
)
from src.presentation.routers.api.v1.email_verifications import (
    create_email_verification,
)
from src.presentation.routers.api.v1.holdings import (
    list_holdings,
    list_holdings_by_account,
    sync_holdings,
)
from src.presentation.routers.api.v1.imports import (
    import_from_file,
    list_supported_formats,
)
from src.presentation.routers.api.v1.password_resets import (
    create_password_reset,
    create_password_reset_token,
)
from src.presentation.routers.api.v1.providers import (
    disconnect_provider,
    get_provider_connection,
    initiate_connection,
    list_providers,
    oauth_callback,
    refresh_provider_tokens,
    update_provider,
)
from src.presentation.routers.api.v1.sessions import (
    create_session,
    delete_current_session,
    get_session,
    list_sessions,
    revoke_all_sessions,
    revoke_session,
)
from src.presentation.routers.api.v1.tokens import create_tokens
from src.presentation.routers.api.v1.transactions import (
    get_transaction,
    list_transactions_by_account,
    sync_transactions,
)
from src.presentation.routers.api.v1.events import get_events
from src.presentation.routers.api.v1.users import create_user
from src.schemas.account_schemas import (
    AccountListResponse,
    AccountResponse,
    SyncAccountsResponse,
)
from src.schemas.auth_schemas import (
    EmailVerificationCreateResponse,
    PasswordResetCreateResponse,
    PasswordResetTokenCreateResponse,
    SessionCreateResponse,
    TokenCreateResponse,
    UserCreateResponse,
)
from src.schemas.balance_snapshot_schemas import (
    BalanceHistoryResponse,
    LatestSnapshotsResponse,
)
from src.schemas.holding_schemas import HoldingListResponse, SyncHoldingsResponse
from src.schemas.import_schemas import ImportResponse, SupportedFormatsResponse
from src.schemas.provider_schemas import (
    AuthorizationUrlResponse,
    ProviderConnectionListResponse,
    ProviderConnectionResponse,
    TokenRefreshResponse,
)
from src.schemas.rotation_schemas import (
    GlobalRotationResponse,
    SecurityConfigResponse,
    UserRotationResponse,
)
from src.schemas.session_schemas import (
    SessionListResponse,
    SessionResponse,
    SessionRevokeAllResponse,
)
from src.schemas.transaction_schemas import (
    SyncTransactionsResponse,
    TransactionListResponse,
    TransactionResponse,
)

# =============================================================================
# ROUTE_REGISTRY - Single Source of Truth
# =============================================================================

ROUTE_REGISTRY: list[RouteMetadata] = [
    # =========================================================================
    # Users Resource (1 endpoint)
    # =========================================================================
    RouteMetadata(
        method=HTTPMethod.POST,
        path="/users",
        handler=create_user,
        resource="users",
        tags=["Users"],
        summary="Create user",
        description="Register a new user account. Sends verification email.",
        operation_id="create_user",
        response_model=UserCreateResponse,
        status_code=201,
        errors=[
            ErrorSpec(status=400, description="Validation error"),
            ErrorSpec(status=409, description="Email already registered"),
        ],
        idempotency=IdempotencyLevel.NON_IDEMPOTENT,
        auth_policy=AuthPolicy(level=AuthLevel.PUBLIC),
        rate_limit_policy=RateLimitPolicy.AUTH_REGISTER,
    ),
    # =========================================================================
    # Sessions Resource (6 endpoints)
    # =========================================================================
    # MANUAL_AUTH: Sessions endpoints handle authentication manually with custom
    # 401/403 error mapping and token/session validation logic. They use
    # _extract_user_id_from_token helper instead of AuthenticatedUser dependency.
    RouteMetadata(
        method=HTTPMethod.POST,
        path="/sessions",
        handler=create_session,
        resource="sessions",
        tags=["Sessions"],
        summary="Create session",
        description="Authenticate user and create a new session with tokens.",
        operation_id="create_session",
        response_model=SessionCreateResponse,
        status_code=201,
        errors=[
            ErrorSpec(status=400, description="Invalid credentials"),
            ErrorSpec(status=401, description="Authentication failed"),
            ErrorSpec(status=403, description="Account locked or not verified"),
        ],
        idempotency=IdempotencyLevel.NON_IDEMPOTENT,
        auth_policy=AuthPolicy(
            level=AuthLevel.MANUAL_AUTH,
            rationale="Custom 401/403 mapping for credential validation and account status",
        ),
        rate_limit_policy=RateLimitPolicy.AUTH_LOGIN,
    ),
    RouteMetadata(
        method=HTTPMethod.DELETE,
        path="/sessions/current",
        handler=delete_current_session,
        resource="sessions",
        tags=["Sessions"],
        summary="Delete current session",
        description="Logout by revoking the refresh token for current session.",
        operation_id="delete_current_session",
        response_model=None,
        status_code=204,
        errors=[
            ErrorSpec(status=401, description="Not authenticated"),
        ],
        idempotency=IdempotencyLevel.IDEMPOTENT,
        auth_policy=AuthPolicy(
            level=AuthLevel.MANUAL_AUTH,
            rationale="Requires token extraction for session revocation",
        ),
        rate_limit_policy=RateLimitPolicy.API_WRITE,
    ),
    RouteMetadata(
        method=HTTPMethod.GET,
        path="/sessions",
        handler=list_sessions,
        resource="sessions",
        tags=["Sessions"],
        summary="List sessions",
        description="Get all sessions for the current user.",
        operation_id="list_sessions",
        response_model=SessionListResponse,
        status_code=200,
        errors=[
            ErrorSpec(status=401, description="Not authenticated"),
        ],
        idempotency=IdempotencyLevel.SAFE,
        auth_policy=AuthPolicy(
            level=AuthLevel.MANUAL_AUTH,
            rationale="Requires user_id and session_id extraction for filtering",
        ),
        rate_limit_policy=RateLimitPolicy.API_READ,
    ),
    RouteMetadata(
        method=HTTPMethod.GET,
        path="/sessions/{session_id}",
        handler=get_session,
        resource="sessions",
        tags=["Sessions"],
        summary="Get session",
        description="Get details of a specific session.",
        operation_id="get_session",
        response_model=SessionResponse,
        status_code=200,
        errors=[
            ErrorSpec(status=401, description="Not authenticated"),
            ErrorSpec(status=404, description="Session not found"),
        ],
        idempotency=IdempotencyLevel.SAFE,
        auth_policy=AuthPolicy(
            level=AuthLevel.MANUAL_AUTH,
            rationale="Requires ownership verification via token parsing",
        ),
        rate_limit_policy=RateLimitPolicy.API_READ,
    ),
    RouteMetadata(
        method=HTTPMethod.DELETE,
        path="/sessions/{session_id}",
        handler=revoke_session,
        resource="sessions",
        tags=["Sessions"],
        summary="Revoke session",
        description="Revoke a specific session (logout that device).",
        operation_id="revoke_session",
        response_model=None,
        status_code=204,
        errors=[
            ErrorSpec(status=401, description="Not authenticated"),
            ErrorSpec(status=404, description="Session not found"),
        ],
        idempotency=IdempotencyLevel.IDEMPOTENT,
        auth_policy=AuthPolicy(
            level=AuthLevel.MANUAL_AUTH,
            rationale="Requires ownership verification for security",
        ),
        rate_limit_policy=RateLimitPolicy.API_WRITE,
    ),
    RouteMetadata(
        method=HTTPMethod.DELETE,
        path="/sessions",
        handler=revoke_all_sessions,
        resource="sessions",
        tags=["Sessions"],
        summary="Revoke all sessions",
        description="Revoke all sessions except the current one (logout everywhere else).",
        operation_id="revoke_all_sessions",
        response_model=SessionRevokeAllResponse,
        status_code=200,
        errors=[
            ErrorSpec(status=401, description="Not authenticated"),
        ],
        idempotency=IdempotencyLevel.IDEMPOTENT,
        auth_policy=AuthPolicy(
            level=AuthLevel.MANUAL_AUTH,
            rationale="Requires current session_id to exclude from revocation",
        ),
        rate_limit_policy=RateLimitPolicy.API_WRITE,
    ),
    # =========================================================================
    # Tokens Resource (1 endpoint)
    # =========================================================================
    RouteMetadata(
        method=HTTPMethod.POST,
        path="/tokens",
        handler=create_tokens,
        resource="tokens",
        tags=["Tokens"],
        summary="Create tokens",
        description="Refresh access token using refresh token. Implements token rotation.",
        operation_id="create_tokens",
        response_model=TokenCreateResponse,
        status_code=201,
        errors=[
            ErrorSpec(status=400, description="Invalid token"),
            ErrorSpec(status=401, description="Token expired or revoked"),
        ],
        idempotency=IdempotencyLevel.NON_IDEMPOTENT,
        auth_policy=AuthPolicy(level=AuthLevel.PUBLIC),
        rate_limit_policy=RateLimitPolicy.AUTH_TOKEN_REFRESH,
    ),
    # =========================================================================
    # Email Verifications Resource (1 endpoint)
    # =========================================================================
    RouteMetadata(
        method=HTTPMethod.POST,
        path="/email-verifications",
        handler=create_email_verification,
        resource="email_verifications",
        tags=["Email Verifications"],
        summary="Create email verification",
        description="Verify user's email address using verification token from email.",
        operation_id="create_email_verification",
        response_model=EmailVerificationCreateResponse,
        status_code=201,
        errors=[
            ErrorSpec(status=400, description="Invalid or expired token"),
            ErrorSpec(status=404, description="Token not found"),
        ],
        idempotency=IdempotencyLevel.NON_IDEMPOTENT,
        auth_policy=AuthPolicy(level=AuthLevel.PUBLIC),
        rate_limit_policy=RateLimitPolicy.AUTH_PASSWORD_RESET,
    ),
    # =========================================================================
    # Password Reset Tokens Resource (1 endpoint)
    # =========================================================================
    RouteMetadata(
        method=HTTPMethod.POST,
        path="/password-reset-tokens",
        handler=create_password_reset_token,
        resource="password_reset_tokens",
        tags=["Password Reset Tokens"],
        summary="Create password reset token",
        description="Request a password reset. Always returns success to prevent user enumeration.",
        operation_id="create_password_reset_token",
        response_model=PasswordResetTokenCreateResponse,
        status_code=201,
        errors=[],
        idempotency=IdempotencyLevel.NON_IDEMPOTENT,
        auth_policy=AuthPolicy(level=AuthLevel.PUBLIC),
        rate_limit_policy=RateLimitPolicy.AUTH_PASSWORD_RESET,
    ),
    # =========================================================================
    # Password Resets Resource (1 endpoint)
    # =========================================================================
    RouteMetadata(
        method=HTTPMethod.POST,
        path="/password-resets",
        handler=create_password_reset,
        resource="password_resets",
        tags=["Password Resets"],
        summary="Create password reset",
        description="Reset password using token from email. Revokes all sessions.",
        operation_id="create_password_reset",
        response_model=PasswordResetCreateResponse,
        status_code=201,
        errors=[
            ErrorSpec(status=400, description="Invalid or expired token"),
            ErrorSpec(status=404, description="Token not found"),
        ],
        idempotency=IdempotencyLevel.NON_IDEMPOTENT,
        auth_policy=AuthPolicy(level=AuthLevel.PUBLIC),
        rate_limit_policy=RateLimitPolicy.AUTH_PASSWORD_RESET,
    ),
    # =========================================================================
    # Providers Resource (6 endpoints)
    # =========================================================================
    RouteMetadata(
        method=HTTPMethod.GET,
        path="/providers",
        handler=list_providers,
        resource="providers",
        tags=["Providers"],
        summary="List provider connections",
        description="List all provider connections for the authenticated user.",
        operation_id="list_providers",
        response_model=ProviderConnectionListResponse,
        status_code=200,
        errors=[],
        idempotency=IdempotencyLevel.SAFE,
        auth_policy=AuthPolicy(level=AuthLevel.AUTHENTICATED),
        rate_limit_policy=RateLimitPolicy.API_READ,
    ),
    RouteMetadata(
        method=HTTPMethod.GET,
        path="/providers/{connection_id}",
        handler=get_provider_connection,
        resource="providers",
        tags=["Providers"],
        summary="Get provider connection",
        description="Get details of a specific provider connection.",
        operation_id="get_provider_connection",
        response_model=ProviderConnectionResponse,
        status_code=200,
        errors=[
            ErrorSpec(status=404, description="Connection not found"),
            ErrorSpec(
                status=403, description="Not authorized to access this connection"
            ),
        ],
        idempotency=IdempotencyLevel.SAFE,
        auth_policy=AuthPolicy(level=AuthLevel.AUTHENTICATED),
        rate_limit_policy=RateLimitPolicy.API_READ,
    ),
    RouteMetadata(
        method=HTTPMethod.POST,
        path="/providers",
        handler=initiate_connection,
        resource="providers",
        tags=["Providers"],
        summary="Initiate provider connection",
        description="Start OAuth flow to connect a financial provider.",
        operation_id="initiate_provider_connection",
        response_model=AuthorizationUrlResponse,
        status_code=201,
        errors=[
            ErrorSpec(status=404, description="Provider not supported"),
        ],
        idempotency=IdempotencyLevel.NON_IDEMPOTENT,
        auth_policy=AuthPolicy(level=AuthLevel.AUTHENTICATED),
        rate_limit_policy=RateLimitPolicy.PROVIDER_CONNECT,
    ),
    RouteMetadata(
        method=HTTPMethod.POST,
        path="/providers/callback",
        handler=oauth_callback,
        resource="providers",
        tags=["Providers"],
        summary="Complete OAuth callback",
        description="Complete OAuth flow after user consent. Called by frontend after redirect.",
        operation_id="oauth_callback",
        response_model=ProviderConnectionResponse,
        status_code=201,
        errors=[
            ErrorSpec(status=400, description="Invalid or expired state"),
            ErrorSpec(status=502, description="Provider authentication failed"),
        ],
        idempotency=IdempotencyLevel.NON_IDEMPOTENT,
        auth_policy=AuthPolicy(level=AuthLevel.PUBLIC),
        rate_limit_policy=RateLimitPolicy.PROVIDER_CONNECT,
    ),
    RouteMetadata(
        method=HTTPMethod.PATCH,
        path="/providers/{connection_id}",
        handler=update_provider,
        resource="providers",
        tags=["Providers"],
        summary="Update provider connection",
        description="Update connection properties (currently only alias).",
        operation_id="update_provider_connection",
        response_model=ProviderConnectionResponse,
        status_code=200,
        errors=[
            ErrorSpec(status=404, description="Connection not found"),
            ErrorSpec(
                status=403, description="Not authorized to update this connection"
            ),
        ],
        idempotency=IdempotencyLevel.NON_IDEMPOTENT,
        auth_policy=AuthPolicy(level=AuthLevel.AUTHENTICATED),
        rate_limit_policy=RateLimitPolicy.API_WRITE,
    ),
    RouteMetadata(
        method=HTTPMethod.DELETE,
        path="/providers/{connection_id}",
        handler=disconnect_provider,
        resource="providers",
        tags=["Providers"],
        summary="Disconnect provider",
        description="Disconnect and remove a provider connection.",
        operation_id="disconnect_provider",
        response_model=None,
        status_code=204,
        errors=[
            ErrorSpec(status=404, description="Connection not found"),
            ErrorSpec(
                status=403, description="Not authorized to disconnect this connection"
            ),
        ],
        idempotency=IdempotencyLevel.IDEMPOTENT,
        auth_policy=AuthPolicy(level=AuthLevel.AUTHENTICATED),
        rate_limit_policy=RateLimitPolicy.API_WRITE,
    ),
    RouteMetadata(
        method=HTTPMethod.POST,
        path="/providers/{connection_id}/token-refreshes",
        handler=refresh_provider_tokens,
        resource="providers",
        tags=["Providers"],
        summary="Refresh provider tokens",
        description="Refresh OAuth tokens for a provider connection.",
        operation_id="refresh_provider_tokens",
        response_model=TokenRefreshResponse,
        status_code=201,
        errors=[
            ErrorSpec(status=404, description="Connection not found"),
            ErrorSpec(
                status=403, description="Not authorized or connection not active"
            ),
            ErrorSpec(status=502, description="Provider token refresh failed"),
        ],
        idempotency=IdempotencyLevel.NON_IDEMPOTENT,
        auth_policy=AuthPolicy(level=AuthLevel.AUTHENTICATED),
        rate_limit_policy=RateLimitPolicy.PROVIDER_SYNC,
    ),
    # =========================================================================
    # Accounts Resource (3 endpoints)
    # =========================================================================
    RouteMetadata(
        method=HTTPMethod.GET,
        path="/accounts",
        handler=list_accounts,
        resource="accounts",
        tags=["Accounts"],
        summary="List accounts",
        description="List all accounts for the authenticated user across all connections.",
        operation_id="list_accounts",
        response_model=AccountListResponse,
        status_code=200,
        errors=[],
        idempotency=IdempotencyLevel.SAFE,
        auth_policy=AuthPolicy(level=AuthLevel.AUTHENTICATED),
        rate_limit_policy=RateLimitPolicy.API_READ,
    ),
    RouteMetadata(
        method=HTTPMethod.GET,
        path="/accounts/{account_id}",
        handler=get_account,
        resource="accounts",
        tags=["Accounts"],
        summary="Get account",
        description="Get details of a specific account.",
        operation_id="get_account",
        response_model=AccountResponse,
        status_code=200,
        errors=[
            ErrorSpec(status=404, description="Account not found"),
            ErrorSpec(status=403, description="Not authorized to access this account"),
        ],
        idempotency=IdempotencyLevel.SAFE,
        auth_policy=AuthPolicy(level=AuthLevel.AUTHENTICATED),
        rate_limit_policy=RateLimitPolicy.API_READ,
    ),
    RouteMetadata(
        method=HTTPMethod.POST,
        path="/accounts/syncs",
        handler=sync_accounts,
        resource="accounts",
        tags=["Accounts"],
        summary="Sync accounts",
        description="Sync accounts from a provider connection.",
        operation_id="sync_accounts",
        response_model=SyncAccountsResponse,
        status_code=201,
        errors=[
            ErrorSpec(status=404, description="Connection not found"),
            ErrorSpec(status=403, description="Not authorized to sync this connection"),
            ErrorSpec(status=429, description="Sync rate limit exceeded"),
        ],
        idempotency=IdempotencyLevel.NON_IDEMPOTENT,
        auth_policy=AuthPolicy(level=AuthLevel.AUTHENTICATED),
        rate_limit_policy=RateLimitPolicy.PROVIDER_SYNC,
    ),
    # =========================================================================
    # Transactions Resource (2 endpoints)
    # =========================================================================
    RouteMetadata(
        method=HTTPMethod.GET,
        path="/transactions/{transaction_id}",
        handler=get_transaction,
        resource="transactions",
        tags=["Transactions"],
        summary="Get transaction",
        description="Get details of a specific transaction.",
        operation_id="get_transaction",
        response_model=TransactionResponse,
        status_code=200,
        errors=[
            ErrorSpec(status=404, description="Transaction not found"),
            ErrorSpec(
                status=403, description="Not authorized to access this transaction"
            ),
        ],
        idempotency=IdempotencyLevel.SAFE,
        auth_policy=AuthPolicy(level=AuthLevel.AUTHENTICATED),
        rate_limit_policy=RateLimitPolicy.API_READ,
    ),
    RouteMetadata(
        method=HTTPMethod.POST,
        path="/transactions/syncs",
        handler=sync_transactions,
        resource="transactions",
        tags=["Transactions"],
        summary="Sync transactions",
        description="Sync transactions from a provider connection.",
        operation_id="sync_transactions",
        response_model=SyncTransactionsResponse,
        status_code=201,
        errors=[
            ErrorSpec(status=404, description="Connection or account not found"),
            ErrorSpec(status=403, description="Not authorized to sync"),
            ErrorSpec(status=429, description="Sync rate limit exceeded"),
        ],
        idempotency=IdempotencyLevel.NON_IDEMPOTENT,
        auth_policy=AuthPolicy(level=AuthLevel.AUTHENTICATED),
        rate_limit_policy=RateLimitPolicy.PROVIDER_SYNC,
    ),
    # =========================================================================
    # Holdings Resource (2 endpoints)
    # =========================================================================
    RouteMetadata(
        method=HTTPMethod.GET,
        path="/holdings",
        handler=list_holdings,
        resource="holdings",
        tags=["Holdings"],
        summary="List holdings",
        description="List all holdings for the authenticated user across all accounts.",
        operation_id="list_holdings",
        response_model=HoldingListResponse,
        status_code=200,
        errors=[],
        idempotency=IdempotencyLevel.SAFE,
        auth_policy=AuthPolicy(level=AuthLevel.AUTHENTICATED),
        rate_limit_policy=RateLimitPolicy.API_READ,
    ),
    RouteMetadata(
        method=HTTPMethod.POST,
        path="/accounts/{account_id}/holdings/syncs",
        handler=sync_holdings,
        resource="holdings",
        tags=["Accounts"],
        summary="Sync holdings",
        description="Sync holdings from provider for a specific account.",
        operation_id="sync_holdings",
        response_model=SyncHoldingsResponse,
        status_code=201,
        errors=[
            ErrorSpec(status=404, description="Account not found"),
            ErrorSpec(status=403, description="Not authorized to sync this account"),
            ErrorSpec(status=429, description="Sync rate limit exceeded"),
        ],
        idempotency=IdempotencyLevel.NON_IDEMPOTENT,
        auth_policy=AuthPolicy(level=AuthLevel.AUTHENTICATED),
        rate_limit_policy=RateLimitPolicy.PROVIDER_SYNC,
    ),
    # =========================================================================
    # Balance Snapshots Resource (3 endpoints)
    # =========================================================================
    RouteMetadata(
        method=HTTPMethod.GET,
        path="/balance-snapshots",
        handler=get_latest_snapshots,
        resource="balance_snapshots",
        tags=["Balance Snapshots"],
        summary="Get latest balance snapshots",
        description="Get the most recent balance snapshot for each of user's accounts.",
        operation_id="get_latest_balance_snapshots",
        response_model=LatestSnapshotsResponse,
        status_code=200,
        errors=[],
        idempotency=IdempotencyLevel.SAFE,
        auth_policy=AuthPolicy(level=AuthLevel.AUTHENTICATED),
        rate_limit_policy=RateLimitPolicy.API_READ,
    ),
    RouteMetadata(
        method=HTTPMethod.GET,
        path="/accounts/{account_id}/balance-history",
        handler=get_balance_history,
        resource="balance_snapshots",
        tags=["Accounts"],
        summary="Get balance history",
        description="Get balance history for an account within a date range.",
        operation_id="get_balance_history",
        response_model=BalanceHistoryResponse,
        status_code=200,
        errors=[
            ErrorSpec(status=404, description="Account not found"),
            ErrorSpec(status=403, description="Not authorized to access this account"),
            ErrorSpec(status=400, description="Invalid date range"),
        ],
        idempotency=IdempotencyLevel.SAFE,
        auth_policy=AuthPolicy(level=AuthLevel.AUTHENTICATED),
        rate_limit_policy=RateLimitPolicy.API_READ,
    ),
    RouteMetadata(
        method=HTTPMethod.GET,
        path="/accounts/{account_id}/balance-snapshots",
        handler=list_balance_snapshots,
        resource="balance_snapshots",
        tags=["Accounts"],
        summary="List balance snapshots",
        description="List recent balance snapshots for an account.",
        operation_id="list_balance_snapshots",
        response_model=BalanceHistoryResponse,
        status_code=200,
        errors=[
            ErrorSpec(status=404, description="Account not found"),
            ErrorSpec(status=403, description="Not authorized to access this account"),
        ],
        idempotency=IdempotencyLevel.SAFE,
        auth_policy=AuthPolicy(level=AuthLevel.AUTHENTICATED),
        rate_limit_policy=RateLimitPolicy.API_READ,
    ),
    # =========================================================================
    # Imports Resource (2 endpoints)
    # =========================================================================
    RouteMetadata(
        method=HTTPMethod.POST,
        path="/imports",
        handler=import_from_file,
        resource="imports",
        tags=["Imports"],
        summary="Import from file",
        description="Import financial data from an uploaded file (QFX, OFX).",
        operation_id="import_from_file",
        response_model=ImportResponse,
        status_code=201,
        errors=[
            ErrorSpec(status=400, description="Invalid file or format"),
            ErrorSpec(status=415, description="Unsupported file format"),
        ],
        idempotency=IdempotencyLevel.NON_IDEMPOTENT,
        auth_policy=AuthPolicy(level=AuthLevel.AUTHENTICATED),
        rate_limit_policy=RateLimitPolicy.API_WRITE,
    ),
    RouteMetadata(
        method=HTTPMethod.GET,
        path="/imports/formats",
        handler=list_supported_formats,
        resource="imports",
        tags=["Imports"],
        summary="List supported formats",
        description="List file formats supported for import.",
        operation_id="list_supported_formats",
        response_model=SupportedFormatsResponse,
        status_code=200,
        errors=[],
        idempotency=IdempotencyLevel.SAFE,
        auth_policy=AuthPolicy(level=AuthLevel.PUBLIC),
        rate_limit_policy=RateLimitPolicy.API_READ,
    ),
    # =========================================================================
    # Admin Resource (3 endpoints)
    # =========================================================================
    RouteMetadata(
        method=HTTPMethod.POST,
        path="/admin/security/rotations",
        handler=create_global_rotation,
        resource="admin",
        tags=["Token Rotation"],
        summary="Trigger global token rotation",
        description="Admin-only. Increments global minimum token version, invalidating all existing refresh tokens.",
        operation_id="create_global_rotation",
        response_model=GlobalRotationResponse,
        status_code=201,
        errors=[
            ErrorSpec(status=401, description="Not authenticated"),
            ErrorSpec(status=403, description="Not authorized (admin only)"),
            ErrorSpec(status=500, description="Rotation failed"),
        ],
        idempotency=IdempotencyLevel.NON_IDEMPOTENT,
        auth_policy=AuthPolicy(level=AuthLevel.ADMIN, role="admin"),
        rate_limit_policy=RateLimitPolicy.API_WRITE,
    ),
    RouteMetadata(
        method=HTTPMethod.POST,
        path="/admin/users/{user_id}/rotations",
        handler=create_user_rotation,
        resource="admin",
        tags=["Token Rotation"],
        summary="Trigger per-user token rotation",
        description="Admin-only. Increments user's minimum token version, invalidating only that user's tokens.",
        operation_id="create_user_rotation",
        response_model=UserRotationResponse,
        status_code=201,
        errors=[
            ErrorSpec(status=401, description="Not authenticated"),
            ErrorSpec(status=403, description="Not authorized (admin only)"),
            ErrorSpec(status=404, description="User not found"),
            ErrorSpec(status=500, description="Rotation failed"),
        ],
        idempotency=IdempotencyLevel.NON_IDEMPOTENT,
        auth_policy=AuthPolicy(level=AuthLevel.ADMIN, role="admin"),
        rate_limit_policy=RateLimitPolicy.API_WRITE,
    ),
    RouteMetadata(
        method=HTTPMethod.GET,
        path="/admin/security/config",
        handler=get_security_config,
        resource="admin",
        tags=["Token Rotation"],
        summary="Get security configuration",
        description="Admin-only. Retrieve current security configuration including token version.",
        operation_id="get_security_config",
        response_model=SecurityConfigResponse,
        status_code=200,
        errors=[
            ErrorSpec(status=401, description="Not authenticated"),
            ErrorSpec(status=403, description="Not authorized (admin only)"),
        ],
        idempotency=IdempotencyLevel.SAFE,
        auth_policy=AuthPolicy(level=AuthLevel.ADMIN, role="admin"),
        rate_limit_policy=RateLimitPolicy.API_READ,
    ),
    # =========================================================================
    # Nested Resource Routes (4 endpoints)
    # =========================================================================
    RouteMetadata(
        method=HTTPMethod.GET,
        path="/providers/{connection_id}/accounts",
        handler=list_accounts_by_connection,
        resource="accounts",
        tags=["Providers"],
        summary="List accounts for connection",
        description="List all accounts for a specific provider connection.",
        operation_id="list_accounts_by_connection",
        response_model=AccountListResponse,
        status_code=200,
        errors=[
            ErrorSpec(status=404, description="Connection not found"),
            ErrorSpec(
                status=403, description="Not authorized to access this connection"
            ),
        ],
        idempotency=IdempotencyLevel.SAFE,
        auth_policy=AuthPolicy(level=AuthLevel.AUTHENTICATED),
        rate_limit_policy=RateLimitPolicy.API_READ,
    ),
    RouteMetadata(
        method=HTTPMethod.GET,
        path="/accounts/{account_id}/transactions",
        handler=list_transactions_by_account,
        resource="transactions",
        tags=["Accounts"],
        summary="List transactions for account",
        description="List transactions for a specific account with pagination and filters.",
        operation_id="list_transactions_by_account",
        response_model=TransactionListResponse,
        status_code=200,
        errors=[
            ErrorSpec(status=404, description="Account not found"),
            ErrorSpec(status=403, description="Not authorized to access this account"),
        ],
        idempotency=IdempotencyLevel.SAFE,
        auth_policy=AuthPolicy(level=AuthLevel.AUTHENTICATED),
        rate_limit_policy=RateLimitPolicy.API_READ,
    ),
    RouteMetadata(
        method=HTTPMethod.GET,
        path="/accounts/{account_id}/holdings",
        handler=list_holdings_by_account,
        resource="holdings",
        tags=["Accounts"],
        summary="List holdings for account",
        description="List all holdings for a specific account.",
        operation_id="list_holdings_by_account",
        response_model=HoldingListResponse,
        status_code=200,
        errors=[
            ErrorSpec(status=404, description="Account not found"),
            ErrorSpec(status=403, description="Not authorized to access this account"),
        ],
        idempotency=IdempotencyLevel.SAFE,
        auth_policy=AuthPolicy(level=AuthLevel.AUTHENTICATED),
        rate_limit_policy=RateLimitPolicy.API_READ,
    ),
    # =========================================================================
    # Events Resource (1 endpoint - SSE)
    # =========================================================================
    RouteMetadata(
        method=HTTPMethod.GET,
        path="/events",
        handler=get_events,
        resource="events",
        tags=["Events"],
        summary="Subscribe to events (SSE)",
        description="Server-Sent Events stream for real-time updates. Requires authenticated user.",
        operation_id="get_events",
        response_model=None,  # StreamingResponse
        status_code=200,
        errors=[
            ErrorSpec(status=401, description="Not authenticated"),
        ],
        idempotency=IdempotencyLevel.SAFE,
        auth_policy=AuthPolicy(level=AuthLevel.AUTHENTICATED),
        rate_limit_policy=RateLimitPolicy.SSE_STREAM,
    ),
]
