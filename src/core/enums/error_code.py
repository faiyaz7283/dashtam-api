"""Domain-level error codes (machine-readable).

Error codes follow ENTITY_ACTION_REASON naming convention.
Used with Result types for railway-oriented programming.

Categories:
- Validation errors (INVALID_*, VALIDATION_*)
- Resource errors (*_NOT_FOUND)
- Conflict errors (*_ALREADY_EXISTS, *_CONFLICT)
- Authentication errors (INVALID_CREDENTIALS, TOKEN_*)
- Authorization errors (PERMISSION_*, ACCOUNT_LOCKED)
- Business rule violations (INSUFFICIENT_*, *_LIMIT_EXCEEDED)
- Secrets management errors (SECRET_*)
"""

from enum import Enum


class ErrorCode(Enum):
    """Domain-level error codes (machine-readable).

    Error codes follow ENTITY_ACTION_REASON naming convention.
    """

    # Validation errors
    INVALID_EMAIL = "invalid_email"
    INVALID_PASSWORD = "invalid_password"
    PASSWORD_TOO_WEAK = "password_too_weak"
    INVALID_PHONE_NUMBER = "invalid_phone_number"
    INVALID_DATE_RANGE = "invalid_date_range"
    VALIDATION_FAILED = "validation_failed"

    # Resource errors
    USER_NOT_FOUND = "user_not_found"
    ACCOUNT_NOT_FOUND = "account_not_found"
    TRANSACTION_NOT_FOUND = "transaction_not_found"
    PROVIDER_NOT_FOUND = "provider_not_found"
    RESOURCE_NOT_FOUND = "resource_not_found"

    # Conflict errors
    USER_ALREADY_EXISTS = "user_already_exists"
    EMAIL_ALREADY_EXISTS = "email_already_exists"
    ACCOUNT_ALREADY_LINKED = "account_already_linked"
    RESOURCE_CONFLICT = "resource_conflict"

    # Authentication errors
    INVALID_CREDENTIALS = "invalid_credentials"
    TOKEN_EXPIRED = "token_expired"
    TOKEN_INVALID = "token_invalid"
    EMAIL_NOT_VERIFIED = "email_not_verified"
    AUTHENTICATION_FAILED = "authentication_failed"

    # Authorization errors
    PERMISSION_DENIED = "permission_denied"
    RESOURCE_NOT_OWNED = "resource_not_owned"
    ACCOUNT_LOCKED = "account_locked"
    AUTHORIZATION_FAILED = "authorization_failed"

    # Business rule violations
    INSUFFICIENT_BALANCE = "insufficient_balance"
    TRANSFER_LIMIT_EXCEEDED = "transfer_limit_exceeded"
    INVALID_TRANSACTION_TYPE = "invalid_transaction_type"

    # Secrets management errors
    SECRET_NOT_FOUND = "secret_not_found"
    SECRET_ACCESS_DENIED = "secret_access_denied"
    SECRET_INVALID_JSON = "secret_invalid_json"

    # Audit trail errors
    AUDIT_RECORD_FAILED = "audit_record_failed"
    AUDIT_QUERY_FAILED = "audit_query_failed"

    # Rate limit errors
    RATE_LIMIT_CHECK_FAILED = "rate_limit_check_failed"
    RATE_LIMIT_RESET_FAILED = "rate_limit_reset_failed"

    # Encryption errors
    ENCRYPTION_KEY_INVALID = "encryption_key_invalid"
    ENCRYPTION_FAILED = "encryption_failed"
    DECRYPTION_FAILED = "decryption_failed"
    INVALID_INPUT = "invalid_input"

    # Provider errors
    PROVIDER_AUTHENTICATION_FAILED = "provider_authentication_failed"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    PROVIDER_RATE_LIMITED = "provider_rate_limited"
    PROVIDER_CREDENTIAL_INVALID = "provider_credential_invalid"
