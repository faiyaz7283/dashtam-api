"""Provider connection domain errors.

Defines provider connection-specific error constants for state transitions,
validation, and connection management.

Architecture:
    - Domain layer errors (no infrastructure dependencies)
    - Used in Result types (railway-oriented programming)
    - Never raised as exceptions (return Failure(error) instead)

Usage:
    from src.domain.errors import ProviderConnectionError
    from src.core.result import Failure

    result = connection.mark_connected(credentials)
    match result:
        case Success(_):
            # Connection activated
            ...
        case Failure(ProviderConnectionError.INVALID_STATE_TRANSITION):
            # Handle invalid transition
            ...

Reference:
    - docs/architecture/provider-domain-model.md
"""


class ProviderConnectionError:
    """Provider connection error constants.

    Used in Result types for connection operation failures.
    These are NOT exceptions - they are error value constants
    used in railway-oriented programming pattern.

    Error Categories:
        - State transition errors: INVALID_STATE_TRANSITION
        - Validation errors: INVALID_CREDENTIALS, INVALID_PROVIDER_SLUG
        - Status errors: NOT_CONNECTED, CREDENTIALS_EXPIRED
    """

    # State transition errors
    INVALID_STATE_TRANSITION = "Invalid state transition"
    CANNOT_TRANSITION_TO_ACTIVE = "Cannot transition to ACTIVE from current state"
    CANNOT_TRANSITION_TO_EXPIRED = "Cannot transition to EXPIRED, must be ACTIVE"
    CANNOT_TRANSITION_TO_REVOKED = "Cannot transition to REVOKED, must be ACTIVE"
    CANNOT_TRANSITION_TO_FAILED = "Cannot transition to FAILED, must be PENDING"

    # Validation errors
    CREDENTIALS_REQUIRED = "Credentials are required"
    INVALID_CREDENTIALS = "Invalid credentials"
    INVALID_PROVIDER_SLUG = "Invalid provider slug"
    INVALID_ALIAS = "Alias exceeds maximum length"

    # Status errors
    NOT_CONNECTED = "Connection is not active"
    CREDENTIALS_EXPIRED = "Credentials have expired"
    CONNECTION_DISCONNECTED = "Connection has been disconnected"

    # Consistency errors
    ACTIVE_WITHOUT_CREDENTIALS = "ACTIVE connection must have credentials"
