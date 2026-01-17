"""Password reset token service.

This service handles generation of password reset tokens.

Architecture:
    - Infrastructure service (no protocol needed)
    - Used by application handlers directly
    - Tokens stored in plain text (already unguessable)

Token Strategy:
    - 32-byte random hex string (64 characters)
    - 15-minute expiration (security vs UX)
    - One-time use (marked as used_at)
    - Very short-lived (security-sensitive operation)

Reference:
    - docs/architecture/authentication-architecture.md (Lines 425-442)
"""

import secrets
from datetime import UTC, datetime, timedelta

from src.core.constants import TOKEN_BYTES


class PasswordResetTokenService:
    """Password reset token generation service.

    Generates unguessable tokens for password reset links.
    Very short-lived (15 minutes) for security.

    Usage:
        # Application handler uses directly
        service = PasswordResetTokenService(expiration_minutes=15)

        # Generate token
        token = service.generate_token()

        # Store in database
        await password_reset_repo.save(
            user_id=user_id,
            token=token,
            expires_at=service.calculate_expiration(),
            ip_address=request.client.host,
            user_agent=request.headers.get("User-Agent"),
        )

        # Send in email (URL built using settings.verification_url_base)
        # Note: Actual endpoint is POST /api/v1/auth/password-reset/confirm with token in body
        # This URL is for GET request that redirects/renders form
        reset_url = f"{settings.verification_url_base}/api/v1/auth/password-reset/confirm?token={token}"
    """

    def __init__(self, expiration_minutes: int = 15) -> None:
        """Initialize password reset token service.

        Args:
            expiration_minutes: Token expiration in minutes (default: 15).

        Note:
            15 minutes balances security (short window) with UX (enough time).
            Password reset is security-sensitive, so very short expiration.
        """
        self._expiration_minutes = expiration_minutes

    def generate_token(self) -> str:
        """Generate password reset token.

        Returns:
            64-character hex string (32 bytes of entropy).

        Example:
            >>> service = PasswordResetTokenService()
            >>> token = service.generate_token()
            >>> len(token)
            64
            >>> all(c in '0123456789abcdef' for c in token)
            True

        Note:
            - Token is 32 bytes = 256 bits of entropy
            - 2^256 possibilities (unguessable)
            - No hashing needed (already cryptographically secure)
            - Each generation produces unique token
        """
        # Generate 32-byte random hex string
        # Returns 64 hex characters (each byte = 2 hex chars)
        return secrets.token_hex(TOKEN_BYTES)

    def calculate_expiration(self) -> datetime:
        """Calculate expiration timestamp for new token.

        Returns:
            Expiration datetime (UTC) based on configured expiration_minutes.

        Example:
            >>> service = PasswordResetTokenService(expiration_minutes=15)
            >>> expires_at = service.calculate_expiration()
            >>> # ~15 minutes from now

        Note:
            - Always returns UTC timestamp
            - Add configured minutes to current time
            - Very short expiration for security
        """
        return datetime.now(UTC) + timedelta(minutes=self._expiration_minutes)
