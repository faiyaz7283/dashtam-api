"""Account domain errors.

Defines account-specific error constants for validation, money operations,
and state management.

Architecture:
    - Domain layer errors (no infrastructure dependencies)
    - Used in Result types (railway-oriented programming)
    - Never raised as exceptions (return Failure(error) instead)

Usage:
    from src.domain.errors import AccountError
    from src.core.result import Failure

    if not name:
        return Failure(AccountError.INVALID_ACCOUNT_NAME)

Reference:
    - docs/architecture/account-domain-model.md
"""


class AccountError:
    """Account error constants.

    Used in Result types for account operation failures.
    These are NOT exceptions - they are error value constants
    used in railway-oriented programming pattern.

    Error Categories:
        - Validation errors: INVALID_ACCOUNT_NAME, INVALID_CURRENCY
        - Money errors: CURRENCY_MISMATCH, INVALID_AMOUNT
        - State errors: ACCOUNT_INACTIVE
    """

    # -------------------------------------------------------------------------
    # Validation Errors
    # -------------------------------------------------------------------------

    INVALID_ACCOUNT_NAME = "Account name cannot be empty"
    """Account name is required for display purposes."""

    INVALID_CURRENCY = "Invalid ISO 4217 currency code"
    """Currency must be a valid 3-letter ISO 4217 code."""

    INVALID_PROVIDER_ACCOUNT_ID = "Provider account ID cannot be empty"
    """Provider's unique account identifier is required for sync."""

    INVALID_ACCOUNT_NUMBER = "Account number mask cannot be empty"
    """Masked account number is required for display."""

    # -------------------------------------------------------------------------
    # Money Errors
    # -------------------------------------------------------------------------

    CURRENCY_MISMATCH = "Cannot perform operation on different currencies"
    """Arithmetic operations require same currency."""

    INVALID_AMOUNT = "Amount must be a valid Decimal"
    """Balance amount must be a valid decimal number."""

    NEGATIVE_BALANCE_NOT_ALLOWED = "Balance cannot be negative for this account type"
    """Some account types cannot have negative balances."""

    # -------------------------------------------------------------------------
    # State Errors
    # -------------------------------------------------------------------------

    ACCOUNT_INACTIVE = "Account is not active"
    """Account has been deactivated and cannot be modified."""

    ACCOUNT_NOT_FOUND = "Account not found"
    """Account with given ID does not exist."""

    # -------------------------------------------------------------------------
    # Sync Errors
    # -------------------------------------------------------------------------

    SYNC_FAILED = "Account sync failed"
    """Failed to sync account data from provider."""

    CONNECTION_REQUIRED = "Account must be associated with a connection"
    """Account requires a valid provider connection."""
