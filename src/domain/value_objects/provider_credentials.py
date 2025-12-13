"""Authentication-agnostic encrypted credentials value object.

Immutable value object that stores encrypted credential data as an
opaque blob. The domain layer has no knowledge of the credential
format - infrastructure layer handles encryption/decryption based
on the credential_type hint.

Reference:
    - docs/architecture/provider-domain-model.md

Usage:
    from src.domain.value_objects import ProviderCredentials
    from src.domain.enums import CredentialType

    credentials = ProviderCredentials(
        encrypted_data=encrypted_blob,
        credential_type=CredentialType.OAUTH2,
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )

    if credentials.is_expired():
        # Need to refresh or re-authenticate
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from src.domain.enums.credential_type import CredentialType


@dataclass(frozen=True)
class ProviderCredentials:
    """Authentication-agnostic encrypted credentials.

    Stores encrypted credential data as an opaque blob. The domain layer
    treats this as a black box - only the infrastructure layer understands
    the internal format based on credential_type.

    This design supports multiple authentication mechanisms (OAuth2, API keys,
    link tokens, certificates) without domain layer changes.

    Attributes:
        encrypted_data: Encrypted credential blob (opaque to domain).
        credential_type: Type hint for infrastructure to route handling.
        expires_at: When credentials expire (None = never expires).

    Immutability:
        Frozen dataclass ensures credentials cannot be modified after creation.
        To update credentials, create a new ProviderCredentials instance.

    Security:
        - Domain never sees raw credentials
        - Encryption/decryption happens at infrastructure layer
        - Credentials excluded from logging and events

    Example:
        >>> from datetime import UTC, datetime, timedelta
        >>> creds = ProviderCredentials(
        ...     encrypted_data=b"encrypted_oauth_tokens",
        ...     credential_type=CredentialType.OAUTH2,
        ...     expires_at=datetime.now(UTC) + timedelta(hours=1),
        ... )
        >>> creds.is_expired()
        False
    """

    encrypted_data: bytes
    credential_type: CredentialType
    expires_at: datetime | None = None

    def __post_init__(self) -> None:
        """Validate credentials after initialization.

        Raises:
            ValueError: If encrypted_data is empty or invalid.
        """
        if not self.encrypted_data:
            raise ValueError("encrypted_data cannot be empty")

        if not isinstance(self.encrypted_data, bytes):
            raise ValueError("encrypted_data must be bytes")

        if not isinstance(self.credential_type, CredentialType):
            raise ValueError("credential_type must be a CredentialType enum")

        # Ensure expires_at is timezone-aware if provided
        if self.expires_at is not None:
            if self.expires_at.tzinfo is None:
                raise ValueError("expires_at must be timezone-aware")

    def is_expired(self) -> bool:
        """Check if credentials have expired.

        Returns:
            bool: True if credentials are past expiration time.
                  False if no expiration set or not yet expired.
        """
        if self.expires_at is None:
            return False
        return datetime.now(UTC) >= self.expires_at

    def is_expiring_soon(self, threshold: timedelta = timedelta(minutes=5)) -> bool:
        """Check if credentials will expire within threshold.

        Useful for proactive refresh before expiration.

        Args:
            threshold: Time window to check. Defaults to 5 minutes.

        Returns:
            bool: True if credentials will expire within threshold.
                  False if no expiration set or expiration is further out.
        """
        if self.expires_at is None:
            return False
        return datetime.now(UTC) >= (self.expires_at - threshold)

    def time_until_expiry(self) -> timedelta | None:
        """Get time remaining until credentials expire.

        Returns:
            timedelta | None: Time until expiration, or None if no expiration.
                              Returns zero timedelta if already expired.
        """
        if self.expires_at is None:
            return None

        remaining = self.expires_at - datetime.now(UTC)
        if remaining.total_seconds() < 0:
            return timedelta(seconds=0)
        return remaining

    def supports_refresh(self) -> bool:
        """Check if credential type supports automatic refresh.

        Returns:
            bool: True if credentials can be refreshed without user action.
        """
        return self.credential_type in CredentialType.supports_refresh()

    def __repr__(self) -> str:
        """Return repr for debugging.

        Note: Does NOT include encrypted_data for security.

        Returns:
            str: String representation without sensitive data.
        """
        expires_str = self.expires_at.isoformat() if self.expires_at else "None"
        return (
            f"ProviderCredentials("
            f"credential_type={self.credential_type.value}, "
            f"expires_at={expires_str}, "
            f"encrypted_data=<{len(self.encrypted_data)} bytes>)"
        )

    def __str__(self) -> str:
        """Return string representation.

        Note: Does NOT include encrypted_data for security.

        Returns:
            str: Human-readable string without sensitive data.
        """
        status = "expired" if self.is_expired() else "valid"
        return f"ProviderCredentials({self.credential_type.value}, {status})"
