"""Authentication domain errors for User Authentication.

Defines authentication-specific error types for token validation,
user authentication, and authorization failures.

Architecture:
    - Domain layer errors (no infrastructure dependencies)
    - Used in Result types (railway-oriented programming)
    - Never raised as exceptions (return Failure(error) instead)

Usage:
    from src.domain.errors import AuthenticationError
    from src.core.result import Failure

    result = token_service.validate_access_token(token)
    match result:
        case Success(payload):
            # Process valid token
            ...
        case Failure(AuthenticationError.INVALID_TOKEN):
            # Handle invalid token
            ...

Reference:
    - docs/architecture/authentication-architecture.md
"""


class AuthenticationError:
    """Authentication error constants.

    Used in Result types for authentication failures.
    These are NOT exceptions - they are error value constants
    used in railway-oriented programming pattern.

    Error Categories:
        - Token errors: INVALID_TOKEN, EXPIRED_TOKEN, MALFORMED_TOKEN
        - Credential errors: INVALID_CREDENTIALS, EMAIL_NOT_VERIFIED
        - Session errors: SESSION_EXPIRED, SESSION_REVOKED

    Example:
        # Token validation
        def validate_token(token: str) -> Result[dict, str]:
            if not token:
                return Failure(AuthenticationError.INVALID_TOKEN)
            if expired:
                return Failure(AuthenticationError.EXPIRED_TOKEN)
            return Success(payload)

        # Login validation
        def login(email: str, password: str) -> Result[User, str]:
            user = find_by_email(email)
            if not user or not verify_password(password):
                return Failure(AuthenticationError.INVALID_CREDENTIALS)
            if not user.is_verified:
                return Failure(AuthenticationError.EMAIL_NOT_VERIFIED)
            return Success(user)
    """

    # Token validation errors
    INVALID_TOKEN = "Invalid token"
    EXPIRED_TOKEN = "Token expired"
    MALFORMED_TOKEN = "Malformed token"

    # Credential validation errors
    INVALID_CREDENTIALS = "Invalid email or password"
    EMAIL_NOT_VERIFIED = "Email not verified"

    # Session errors
    SESSION_EXPIRED = "Session expired"
    SESSION_REVOKED = "Session revoked"

    # Authorization errors
    INSUFFICIENT_PERMISSIONS = "Insufficient permissions"
    ACCOUNT_LOCKED = "Account locked"
