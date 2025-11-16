"""Infrastructure-specific error codes.

These are internal codes for tracking infrastructure failures.
They are mapped to domain ErrorCode when flowing to domain layer.

Categories:
- Database errors (DATABASE_*)
- Cache errors (CACHE_*)
- External service errors (EXTERNAL_SERVICE_*)
- Provider errors (PROVIDER_*)
"""

from enum import Enum


class InfrastructureErrorCode(Enum):
    """Infrastructure-specific error codes.

    These are internal codes for tracking infrastructure failures.
    They are mapped to domain ErrorCode when flowing to domain layer.
    """

    # Database errors
    DATABASE_CONNECTION_FAILED = "database_connection_failed"
    DATABASE_TIMEOUT = "database_timeout"
    DATABASE_CONSTRAINT_VIOLATION = "database_constraint_violation"
    DATABASE_CONFLICT = "database_conflict"
    DATABASE_DATA_ERROR = "database_data_error"
    DATABASE_ERROR = "database_error"
    DATABASE_UNKNOWN_ERROR = "database_unknown_error"

    # Cache errors
    CACHE_CONNECTION_ERROR = "cache_connection_error"
    CACHE_TIMEOUT = "cache_timeout"
    CACHE_GET_ERROR = "cache_get_error"
    CACHE_SET_ERROR = "cache_set_error"
    CACHE_DELETE_ERROR = "cache_delete_error"

    # External service errors
    EXTERNAL_SERVICE_UNAVAILABLE = "external_service_unavailable"
    EXTERNAL_SERVICE_TIMEOUT = "external_service_timeout"
    EXTERNAL_SERVICE_ERROR = "external_service_error"

    # Provider errors
    PROVIDER_CONNECTION_FAILED = "provider_connection_failed"
    PROVIDER_AUTH_REQUIRED = "provider_auth_required"
    PROVIDER_RATE_LIMITED = "provider_rate_limited"
