"""Token generation protocol for domain layer.

This protocol defines the interface for JWT access token generation and validation.
Infrastructure layer provides concrete implementations (JWT, future alternatives).

Architecture:
    - Domain defines protocol (port)
    - Infrastructure implements adapter (JWTService)
    - No framework dependencies in domain

Token Strategy:
    - Access tokens: Short-lived JWT (15 minutes)
    - Refresh tokens: Long-lived opaque tokens (handled separately)
    - Stateless validation (no database lookup)

Reference:
    - docs/architecture/authentication-architecture.md (Lines 131-173)
"""

from typing import Protocol
from uuid import UUID

from src.core.result import Result


class TokenGenerationProtocol(Protocol):
    """JWT access token generation and validation interface.

    Implementations:
        - JWTService: HMAC-SHA256 with 15-minute expiration (production)
        - MockTokenService: Testing stub (future)

    Usage:
        # Domain/Application layer depends on protocol
        def __init__(self, token_service: TokenGenerationProtocol):
            self.token_service = token_service

        # Generate access token
        token = self.token_service.generate_access_token(
            user_id=user_id,
            email=user.email,
            roles=["user"],
            session_id=session_id,
        )

        # Validate access token
        result = self.token_service.validate_access_token(token)
        match result:
            case Success(value=payload):
                user_id = payload["sub"]
            case Failure(error=error):
                # Invalid or expired token
                pass
    """

    def generate_access_token(
        self,
        user_id: UUID,
        email: str,
        roles: list[str],
        session_id: UUID | None = None,
    ) -> str:
        """Generate JWT access token.

        Args:
            user_id: User's unique identifier (stored in 'sub' claim).
            email: User's email address.
            roles: List of user roles (e.g., ["user"], ["admin"]).
            session_id: Optional session ID (F1.3 integration).

        Returns:
            JWT access token string (3 parts: header.payload.signature).

        Example:
            >>> token = service.generate_access_token(
            ...     user_id=uuid4(),
            ...     email="user@example.com",
            ...     roles=["user"],
            ...     session_id=uuid4(),
            ... )
            >>> # eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

        Note:
            - Token expires in 15 minutes (configured in settings)
            - Includes iat (issued at) and exp (expires at) timestamps
            - Includes jti (JWT ID) for unique identification
            - Cannot be revoked (expires naturally)
        """
        ...

    def validate_access_token(
        self, token: str
    ) -> Result[dict[str, str | int | list[str]], str]:
        """Validate JWT access token and extract payload.

        Args:
            token: JWT access token string to validate.

        Returns:
            Result with payload dict if valid, or error string if invalid.

            Payload structure:
                {
                    "sub": "user_id_uuid",
                    "email": "user@example.com",
                    "roles": ["user"],
                    "iat": 1700000000,
                    "exp": 1700000900,
                    "jti": "unique_jwt_id",
                    "session_id": "session_id_uuid" (optional)
                }

        Example:
            >>> result = service.validate_access_token(token)
            >>> match result:
            ...     case Success(value=payload):
            ...         user_id = UUID(payload["sub"])
            ...         email = payload["email"]
            ...     case Failure(error=error):
            ...         # Token invalid, expired, or malformed
            ...         return 401 Unauthorized

        Note:
            - Validates signature (prevents tampering)
            - Validates expiration (rejects expired tokens)
            - Returns Failure for malformed tokens (no exceptions)
            - Stateless validation (no database lookup)
        """
        ...
