"""Balance snapshot domain errors.

Defines balance snapshot-specific error constants for validation
and state management.

Architecture:
    - Domain layer errors (no infrastructure dependencies)
    - Used in Result types (railway-oriented programming)
    - Never raised as exceptions (return Failure(error) instead)

Usage:
    from src.domain.errors import BalanceSnapshotError
    from src.core.result import Failure

    if not balance:
        return Failure(BalanceSnapshotError.INVALID_BALANCE)

Reference:
    - docs/architecture/balance-tracking-architecture.md
"""


class BalanceSnapshotError:
    """Balance snapshot error constants.

    Used in Result types for balance snapshot operation failures.
    These are NOT exceptions - they are error value constants
    used in railway-oriented programming pattern.

    Error Categories:
        - Validation errors: INVALID_BALANCE, INVALID_CURRENCY
        - Query errors: SNAPSHOT_NOT_FOUND
    """

    # -------------------------------------------------------------------------
    # Validation Errors
    # -------------------------------------------------------------------------

    INVALID_BALANCE = "Balance cannot be None"
    """Balance value is required for snapshot."""

    INVALID_CURRENCY = "Invalid ISO 4217 currency code"
    """Currency must be a valid 3-letter ISO 4217 code."""

    CURRENCY_MISMATCH = "Balance currency must match account currency"
    """Balance currency must be consistent with account."""

    # -------------------------------------------------------------------------
    # Query Errors
    # -------------------------------------------------------------------------

    SNAPSHOT_NOT_FOUND = "Balance snapshot not found"
    """Balance snapshot with given ID does not exist."""

    ACCOUNT_NOT_FOUND = "Account not found for snapshot"
    """Account associated with snapshot does not exist."""

    # -------------------------------------------------------------------------
    # Time Range Errors
    # -------------------------------------------------------------------------

    INVALID_DATE_RANGE = "Start date must be before end date"
    """Date range query has invalid bounds."""

    DATE_RANGE_TOO_LARGE = "Date range exceeds maximum allowed period"
    """Requested date range is too large for query."""
