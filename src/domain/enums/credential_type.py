"""Authentication mechanism types for provider credentials.

Defines the type of credential stored, used by infrastructure layer
to route to the correct credential handler for encryption/decryption
and token refresh operations.

The domain layer treats credentials as opaque blobs - this enum
provides a hint to infrastructure about how to process them.

Reference:
    - docs/architecture/provider-domain-model.md

Usage:
    from src.domain.enums import CredentialType

    credentials = ProviderCredentials(
        encrypted_data=encrypted_blob,
        credential_type=CredentialType.OAUTH2,
        expires_at=expires_at,
    )
"""

from enum import Enum


class CredentialType(str, Enum):
    """Authentication mechanism type for provider credentials.

    Used by infrastructure layer to determine how to:
    - Encrypt/decrypt credential data
    - Refresh expiring credentials
    - Validate credential format

    The domain layer is authentication-agnostic - it only stores
    this type as a routing hint for infrastructure.

    String Enum:
        Inherits from str for easy serialization and database storage.
        Values are lowercase for consistency.
    """

    OAUTH2 = "oauth2"
    """OAuth 2.0 authentication.

    Used by most brokerages (Schwab, Fidelity, etc.).

    Credential data typically includes:
        - access_token
        - refresh_token
        - token_type
        - expires_in
        - scope
    """

    API_KEY = "api_key"
    """Simple API key authentication.

    Used by some data providers with static credentials.

    Credential data typically includes:
        - api_key
        - api_secret (optional)
    """

    LINK_TOKEN = "link_token"
    """Plaid-style link tokens.

    Used by aggregators like Plaid that use a linking flow.

    Credential data typically includes:
        - access_token
        - item_id
        - institution_id
    """

    CERTIFICATE = "certificate"
    """mTLS certificate-based authentication.

    Used by providers requiring mutual TLS.

    Credential data typically includes:
        - client_certificate
        - private_key
        - certificate_chain
    """

    CUSTOM = "custom"
    """Provider-specific custom authentication.

    Fallback for providers with unique auth mechanisms.
    Infrastructure must handle on a per-provider basis.
    """

    @classmethod
    def values(cls) -> list[str]:
        """Get all credential type values as strings.

        Returns:
            list[str]: List of credential type values.
        """
        return [cred_type.value for cred_type in cls]

    @classmethod
    def is_valid(cls, value: str) -> bool:
        """Check if a string is a valid credential type.

        Args:
            value: String to check.

        Returns:
            bool: True if value is a valid credential type.
        """
        return value in cls.values()

    @classmethod
    def supports_refresh(cls) -> list["CredentialType"]:
        """Get credential types that support automatic refresh.

        Returns:
            list[CredentialType]: Types with refresh capability.
        """
        return [cls.OAUTH2, cls.LINK_TOKEN]

    @classmethod
    def never_expires(cls) -> list["CredentialType"]:
        """Get credential types that typically don't expire.

        Returns:
            list[CredentialType]: Types without expiration.
        """
        return [cls.API_KEY, cls.CERTIFICATE]
