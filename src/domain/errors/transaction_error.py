"""Transaction domain errors.

Defines error constants for transaction validation and business logic failures.

Architecture:
    - Domain layer errors (no infrastructure dependencies)
    - Used in Result types (railway-oriented programming)
    - Never raised as exceptions (return Failure(error) instead)

Usage:
    from src.domain.errors import TransactionError
    from src.core.result import Failure

    if amount <= 0:
        return Failure(TransactionError.INVALID_AMOUNT)

Reference:
    - docs/architecture/transaction-domain-model.md
"""


class TransactionError:
    """Transaction error constants.

    Used in Result types for transaction operation failures.
    These are NOT exceptions - they are error value constants
    used in railway-oriented programming pattern.

    Error Categories:
        - Validation errors: INVALID_AMOUNT, INVALID_PROVIDER_TRANSACTION_ID, INVALID_TRANSACTION_DATE
        - Security errors: MISSING_SECURITY_SYMBOL, MISSING_QUANTITY, INVALID_QUANTITY, MISSING_UNIT_PRICE, MISSING_ASSET_TYPE
        - Status errors: TRANSACTION_NOT_FOUND, TRANSACTION_ALREADY_SETTLED, DUPLICATE_PROVIDER_TRANSACTION
    """

    # -------------------------------------------------------------------------
    # Validation Errors
    # -------------------------------------------------------------------------

    INVALID_AMOUNT = "Invalid transaction amount"
    """Transaction amount is invalid.

    Used when:
    - Amount is zero or negative (except for specific transaction types)
    - Amount currency doesn't match account currency
    - Amount precision exceeds acceptable limits
    """

    INVALID_PROVIDER_TRANSACTION_ID = "Invalid provider transaction ID"
    """Provider transaction ID is invalid or missing.

    Used when:
    - provider_transaction_id is empty
    - provider_transaction_id format is invalid for provider
    - Duplicate provider_transaction_id for same account
    """

    INVALID_TRANSACTION_DATE = "Invalid transaction date"
    """Transaction date is invalid.

    Used when:
    - transaction_date is in the future
    - transaction_date is before account creation
    - settlement_date is before transaction_date
    """

    # -------------------------------------------------------------------------
    # Security/Trade Validation Errors
    # -------------------------------------------------------------------------

    MISSING_SECURITY_SYMBOL = "Missing security symbol"
    """Security symbol is missing for trade transaction.

    Used when:
    - TransactionType is TRADE and subtype requires symbol (BUY, SELL, etc.)
    - symbol field is None or empty
    """

    MISSING_QUANTITY = "Missing quantity"
    """Quantity is missing for trade transaction.

    Used when:
    - TransactionType is TRADE and subtype requires quantity
    - quantity field is None
    """

    INVALID_QUANTITY = "Invalid quantity"
    """Quantity value is invalid.

    Used when:
    - quantity is zero or negative
    - quantity precision exceeds acceptable limits (typically 8 decimals)
    """

    MISSING_UNIT_PRICE = "Missing unit price"
    """Unit price is missing for trade transaction.

    Used when:
    - TransactionType is TRADE and subtype requires unit_price
    - unit_price field is None
    """

    MISSING_ASSET_TYPE = "Missing asset type"
    """Asset type is missing for trade transaction.

    Used when:
    - TransactionType is TRADE
    - asset_type field is None
    """

    # -------------------------------------------------------------------------
    # Status/Lifecycle Errors
    # -------------------------------------------------------------------------

    TRANSACTION_NOT_FOUND = "Transaction not found"
    """Transaction does not exist.

    Used when:
    - Transaction ID not found in repository
    - Provider transaction ID not found for account
    """

    TRANSACTION_ALREADY_SETTLED = "Transaction already settled"
    """Transaction is already settled and cannot be modified.

    Used when:
    - Attempting to update a transaction with status SETTLED
    - Attempting to cancel a settled transaction (use reversal instead)
    """

    DUPLICATE_PROVIDER_TRANSACTION = "Duplicate provider transaction"
    """Provider transaction already exists for this account.

    Used when:
    - Attempting to save transaction with duplicate provider_transaction_id
    - Same provider_transaction_id already exists for the account

    This prevents duplicate transaction imports during sync operations.
    """
