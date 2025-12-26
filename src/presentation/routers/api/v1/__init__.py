"""API v1 routers.

RESTful resource-based endpoints following strict REST compliance.
All endpoints use resource nouns, not action verbs.

Resources:
    /api/v1/users                  - User management
    /api/v1/sessions               - Session management (login/logout)
    /api/v1/tokens                 - Token management (refresh)
    /api/v1/email-verifications    - Email verification
    /api/v1/password-reset-tokens  - Password reset token requests
    /api/v1/password-resets        - Password reset execution
    /api/v1/providers              - Provider connection management
    /api/v1/accounts               - Account management
    /api/v1/transactions           - Transaction management
    /api/v1/holdings               - Holdings management
    /api/v1/balance-snapshots      - Balance snapshot management

Admin Resources:
    /api/v1/admin/security/rotations     - Global token rotation
    /api/v1/admin/security/config        - Security configuration
    /api/v1/admin/users/{id}/rotations   - Per-user token rotation
"""

from fastapi import APIRouter

from src.presentation.routers.api.v1.accounts import (
    provider_accounts_router,
    router as accounts_router,
)
from src.presentation.routers.api.v1.admin import admin_router
from src.presentation.routers.api.v1.email_verifications import (
    router as email_verifications_router,
)
from src.presentation.routers.api.v1.password_resets import (
    password_reset_tokens_router,
    password_resets_router,
)
from src.presentation.routers.api.v1.providers import router as providers_router
from src.presentation.routers.api.v1.sessions import router as sessions_router
from src.presentation.routers.api.v1.tokens import router as tokens_router
from src.presentation.routers.api.v1.transactions import (
    account_transactions_router,
    router as transactions_router,
)
from src.presentation.routers.api.v1.holdings import (
    account_holdings_router,
    router as holdings_router,
)
from src.presentation.routers.api.v1.balance_snapshots import (
    account_balance_router,
    router as balance_snapshots_router,
)
from src.presentation.routers.api.v1.users import router as users_router

# Create combined v1 router
v1_router = APIRouter(prefix="/api/v1")

# Include all resource routers
v1_router.include_router(users_router)
v1_router.include_router(sessions_router)
v1_router.include_router(tokens_router)
v1_router.include_router(email_verifications_router)
v1_router.include_router(password_reset_tokens_router)
v1_router.include_router(password_resets_router)

# Include Phase 5 routers (providers, accounts, transactions)
v1_router.include_router(providers_router)
v1_router.include_router(accounts_router)
v1_router.include_router(transactions_router)

# Include Phase 7 routers (holdings)
v1_router.include_router(holdings_router)

# Include Phase 8 routers (balance snapshots)
v1_router.include_router(balance_snapshots_router)

# Include nested resource routers
# GET /api/v1/providers/{id}/accounts - List accounts for a provider connection
v1_router.include_router(provider_accounts_router)
# GET /api/v1/accounts/{id}/transactions - List transactions for an account
v1_router.include_router(account_transactions_router)
# GET /api/v1/accounts/{id}/holdings - List holdings for an account
# POST /api/v1/accounts/{id}/holdings/syncs - Sync holdings for an account
v1_router.include_router(account_holdings_router)
# GET /api/v1/accounts/{id}/balance-history - Get balance history for account
# GET /api/v1/accounts/{id}/balance-snapshots - List balance snapshots for account
v1_router.include_router(account_balance_router)

# Include admin routers
v1_router.include_router(admin_router)

# Export individual routers for testing
__all__ = [
    "v1_router",
    "users_router",
    "sessions_router",
    "tokens_router",
    "email_verifications_router",
    "password_reset_tokens_router",
    "password_resets_router",
    "providers_router",
    "accounts_router",
    "transactions_router",
    "holdings_router",
    "balance_snapshots_router",
    "provider_accounts_router",
    "account_transactions_router",
    "account_holdings_router",
    "account_balance_router",
    "admin_router",
]
