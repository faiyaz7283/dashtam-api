"""Refresh token service.

This service handles generation and validation of opaque refresh tokens.

Architecture:
    - Infrastructure service (no protocol needed - not a domain boundary)
    - Used by application handlers directly
    - Tokens stored hashed in database (via repository)

Token Strategy:
    - Opaque tokens (NOT JWT)
    - 32-byte random string (urlsafe base64)
    - Hashed with bcrypt before storage
    - 30-day expiration
    - Rotated on every use

Reference:
    - docs/architecture/authentication-architecture.md (Lines 174-231)
"""

import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID

import bcrypt


class RefreshTokenService:
    """Refresh token generation and validation service.

    Generates opaque refresh tokens for long-lived authentication.
    Tokens are hashed before database storage for security.

    Usage:
        # Application handler uses directly
        service = RefreshTokenService(expiration_days=30)

        # Generate token
        token, token_hash = service.generate_token()

        # Store token_hash in database, return token to user
        await refresh_token_repo.save(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=datetime.now(UTC) + timedelta(days=30),
        )

        # Later: Verify token from user
        is_valid = service.verify_token(provided_token, stored_hash)
    """

    def __init__(self, expiration_days: int = 30) -> None:
        """Initialize refresh token service.

        Args:
            expiration_days: Token expiration in days (default: 30).

        Note:
            Expiration is tracked in database, not in token itself.
        """
        self._expiration_days = expiration_days

    def generate_token(self) -> tuple[str, str]:
        """Generate refresh token and its hash.

        Returns:
            Tuple of (token, token_hash):
                - token: Plain token to return to user (urlsafe base64)
                - token_hash: Bcrypt hash to store in database

        Example:
            >>> service = RefreshTokenService()
            >>> token, token_hash = service.generate_token()
            >>> len(token)  # ~43 characters
            43
            >>> token_hash.startswith("$2b$")  # Bcrypt format
            True

        Note:
            - Token is 32 bytes = 256 bits of entropy
            - Each generation produces unique token
            - Token hash is bcrypt with cost factor 12
            - Store token_hash in database, return token to user
        """
        # Generate cryptographically secure random token
        # 32 bytes = 256 bits of entropy
        token = secrets.token_urlsafe(32)

        # Hash token with bcrypt before storage
        # Cost factor 12 = ~250ms (same as passwords)
        token_hash = bcrypt.hashpw(token.encode("utf-8"), bcrypt.gensalt(rounds=12))

        # Return as strings (bcrypt returns bytes)
        return token, token_hash.decode("utf-8")

    def verify_token(self, token: str, token_hash: str) -> bool:
        """Verify token against stored hash.

        Args:
            token: Plain token from user request.
            token_hash: Bcrypt hash from database.

        Returns:
            True if token matches hash, False otherwise.

        Example:
            >>> service = RefreshTokenService()
            >>> token, token_hash = service.generate_token()
            >>> service.verify_token(token, token_hash)
            True
            >>> service.verify_token("wrong_token", token_hash)
            False

        Note:
            - Constant-time comparison (prevents timing attacks)
            - Returns False for invalid hash format (no exceptions)
            - Does NOT check expiration (repository handles that)
        """
        try:
            # bcrypt.checkpw does constant-time comparison
            return bcrypt.checkpw(token.encode("utf-8"), token_hash.encode("utf-8"))
        except (ValueError, AttributeError):
            # Invalid hash format or encoding error
            return False

    def calculate_expiration(self) -> datetime:
        """Calculate expiration timestamp for new token.

        Returns:
            Expiration datetime (UTC) based on configured expiration_days.

        Example:
            >>> service = RefreshTokenService(expiration_days=30)
            >>> expires_at = service.calculate_expiration()
            >>> # ~30 days from now

        Note:
            - Always returns UTC timestamp
            - Add configured days to current time
        """
        return datetime.now(UTC) + timedelta(days=self._expiration_days)
