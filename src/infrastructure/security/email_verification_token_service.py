"""Email verification token service.

This service handles generation of email verification tokens.

Architecture:
    - Infrastructure service (no protocol needed)
    - Used by application handlers directly
    - Tokens stored in plain text (already unguessable)

Token Strategy:
    - 32-byte random hex string (64 characters)
    - 24-hour expiration
    - One-time use (marked as used_at)
    - 2^256 possibilities (unguessable)

Reference:
    - docs/architecture/authentication-architecture.md (Lines 307-336)
"""

import secrets
from datetime import UTC, datetime, timedelta

from src.core.constants import TOKEN_BYTES


class EmailVerificationTokenService:
    """Email verification token generation service.

    Generates unguessable tokens for email verification links.
    Tokens are stored in plain text (already cryptographically secure).

    Usage:
        # Application handler uses directly
        service = EmailVerificationTokenService(expiration_hours=24)

        # Generate token
        token = service.generate_token()

        # Store in database
        await email_verification_repo.save(
            user_id=user_id,
            token=token,
            expires_at=service.calculate_expiration(),
        )

        # Send in email (URL built using settings.verification_url_base)
        # Note: Actual endpoint is POST /api/v1/auth/verify-email with token in body
        # This URL is for GET request that redirects/renders form
        verification_url = f"{settings.verification_url_base}/api/v1/auth/verify-email?token={token}"
    """

    def __init__(self, expiration_hours: int = 24) -> None:
        """Initialize email verification token service.

        Args:
            expiration_hours: Token expiration in hours (default: 24).

        Note:
            24 hours gives users reasonable time to verify email.
        """
        self._expiration_hours = expiration_hours

    def generate_token(self) -> str:
        """Generate email verification token.

        Returns:
            64-character hex string (32 bytes of entropy).

        Example:
            >>> service = EmailVerificationTokenService()
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
            Expiration datetime (UTC) based on configured expiration_hours.

        Example:
            >>> service = EmailVerificationTokenService(expiration_hours=24)
            >>> expires_at = service.calculate_expiration()
            >>> # ~24 hours from now

        Note:
            - Always returns UTC timestamp
            - Add configured hours to current time
        """
        return datetime.now(UTC) + timedelta(hours=self._expiration_hours)
