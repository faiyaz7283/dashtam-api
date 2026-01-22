"""JWT token service (adapter).

This service implements the TokenGenerationProtocol using PyJWT with HMAC-SHA256.

Architecture:
    - Implements TokenGenerationProtocol (no inheritance required)
    - Structural typing via Protocol
    - Injected via dependency container

Security:
    - HMAC-SHA256 (HS256) algorithm
    - 256-bit secret key minimum
    - 15-minute token expiration
    - Unique JWT ID (jti) for tracking

Performance:
    - Stateless validation (no database lookup)
    - Fast generation and validation (~1ms)
    - No external service dependencies

Reference:
    - docs/architecture/authentication-architecture.md (Lines 131-173)
"""

from datetime import UTC, datetime, timedelta
from uuid import UUID
from uuid_extensions import uuid7

import jwt
from jwt.exceptions import InvalidTokenError

from src.core.result import Failure, Result, Success
from src.domain.errors import AuthenticationError


class JWTService:
    """JWT token generation and validation service.

    Implements access token generation and validation using HMAC-SHA256.
    This is the production token service implementation.

    Usage:
        # Via dependency injection
        from src.core.container import get_token_service
        from src.domain.protocols import TokenGenerationProtocol

        token_service: TokenGenerationProtocol = get_token_service()

        # Generate token
        token = token_service.generate_access_token(
            user_id=user_id,
            email=user.email,
            roles=["user"],
            session_id=session_id,
        )

        # Validate token
        result = token_service.validate_access_token(token)
    """

    def __init__(self, secret_key: str, expiration_minutes: int = 15) -> None:
        """Initialize JWT service.

        Args:
            secret_key: Secret key for HMAC-SHA256 signing.
                MUST be at least 256 bits (32 bytes) for security.
            expiration_minutes: Token expiration in minutes (default: 15).

        Raises:
            ValueError: If secret_key is too short (< 32 bytes).

        Note:
            Secret key should come from settings/secrets manager, NEVER hardcoded.
        """
        if len(secret_key) < 32:
            msg = "JWT secret key must be at least 32 bytes (256 bits)"
            raise ValueError(msg)

        self._secret_key = secret_key
        self._expiration_minutes = expiration_minutes
        self._algorithm = "HS256"  # HMAC-SHA256

    def generate_access_token(
        self,
        user_id: UUID,
        email: str,
        roles: list[str],
        session_id: UUID | None = None,
    ) -> str:
        """Generate JWT access token.

        Args:
            user_id: User's unique identifier.
            email: User's email address.
            roles: List of user roles.
            session_id: Optional session ID (F1.3 integration).

        Returns:
            JWT access token string.

        Example:
            >>> service = JWTService(secret_key="x" * 32)
            >>> token = service.generate_access_token(
            ...     user_id=uuid7(),
            ...     email="user@example.com",
            ...     roles=["user"],
            ... )
            >>> len(token.split("."))
            3

        Note:
            - JWT format: header.payload.signature
            - Each generation creates unique jti (JWT ID)
            - Token is self-contained (no database needed)
        """
        now = datetime.now(UTC)
        expires_at = now + timedelta(minutes=self._expiration_minutes)

        payload = {
            "sub": str(user_id),  # Subject (user ID)
            "email": email,
            "roles": roles,
            "iat": int(now.timestamp()),  # Issued at
            "exp": int(expires_at.timestamp()),  # Expires at
            "jti": str(uuid7()),  # JWT ID (unique identifier)
        }

        # Add optional session_id if provided
        if session_id is not None:
            payload["session_id"] = str(session_id)

        # Generate JWT token
        # jwt.encode returns str in python-jose, but type hints say Any
        token: str = jwt.encode(payload, self._secret_key, algorithm=self._algorithm)
        return token

    def validate_access_token(
        self, token: str
    ) -> Result[dict[str, str | int | list[str]], str]:
        """Validate JWT access token and extract payload.

        Args:
            token: JWT access token string to validate.

        Returns:
            Result with payload dict if valid, or error string if invalid.

        Example:
            >>> service = JWTService(secret_key="x" * 32)
            >>> token = service.generate_access_token(
            ...     user_id=uuid7(),
            ...     email="user@example.com",
            ...     roles=["user"],
            ... )
            >>> result = service.validate_access_token(token)
            >>> match result:
            ...     case Success(value=payload):
            ...         assert "sub" in payload
            ...         assert "email" in payload
            ...     case Failure(error=error):
            ...         pass

        Note:
            - Validates signature (prevents tampering)
            - Validates expiration automatically
            - Returns Failure (not exceptions) for invalid tokens
            - Stateless (no database lookup)
        """
        try:
            # Decode and validate JWT
            # PyJWT automatically validates:
            # - Signature (using secret_key)
            # - Expiration (exp claim)
            payload: dict[str, str | int | list[str]] = jwt.decode(
                token, self._secret_key, algorithms=[self._algorithm]
            )

            return Success(value=payload)

        except InvalidTokenError:
            # Token is invalid, expired, or malformed
            # Return error constant (no exceptions in domain)
            return Failure(error=AuthenticationError.INVALID_TOKEN)
