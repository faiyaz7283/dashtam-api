"""Encryption protocol for provider credentials.

Defines the port for encryption/decryption operations. Infrastructure
layer implements this protocol to provide AES-256-GCM encryption.

Architecture:
    - Domain layer protocol (port)
    - Infrastructure adapter: src/infrastructure/providers/encryption_service.py
    - Used by sync handlers to decrypt provider credentials

Reference:
    - docs/architecture/hexagonal.md
    - docs/architecture/provider-integration-architecture.md
"""

from dataclasses import dataclass
from typing import Any, Protocol

from src.core.result import Result
from src.core.errors import DomainError


# =============================================================================
# Encryption Error Types (Domain Layer)
# =============================================================================


@dataclass(frozen=True, slots=True, kw_only=True)
class EncryptionError(DomainError):
    """Base encryption error.

    Used when encryption or decryption fails.
    Does NOT inherit from Exception - used in Result types.
    """

    pass


@dataclass(frozen=True, slots=True, kw_only=True)
class EncryptionKeyError(EncryptionError):
    """Invalid encryption key.

    Occurs when key doesn't meet requirements (wrong length, etc.).
    """

    pass


@dataclass(frozen=True, slots=True, kw_only=True)
class DecryptionError(EncryptionError):
    """Decryption failure.

    Occurs when:
    - Wrong encryption key
    - Data has been tampered with
    - Invalid encrypted data format
    """

    pass


@dataclass(frozen=True, slots=True, kw_only=True)
class SerializationError(EncryptionError):
    """Serialization/deserialization failure.

    Occurs when data cannot be serialized to JSON
    or decrypted data cannot be parsed as JSON.
    """

    pass


# =============================================================================
# Encryption Protocol (Port)
# =============================================================================


class EncryptionProtocol(Protocol):
    """Protocol for encryption/decryption operations.

    Abstracts the encryption service used by application layer handlers.
    Infrastructure layer provides concrete implementation.

    Example:
        class SyncAccountsHandler:
            def __init__(
                self,
                encryption_service: EncryptionProtocol,
                ...
            ) -> None:
                self._encryption = encryption_service

            async def handle(self, cmd: SyncAccounts) -> Result[...]:
                result = self._encryption.decrypt(encrypted_data)
                ...
    """

    def encrypt(self, data: dict[str, Any]) -> Result[bytes, EncryptionError]:
        """Encrypt credentials dictionary to bytes.

        Args:
            data: Credentials dictionary to encrypt. Must be JSON-serializable.

        Returns:
            Success(bytes) with encrypted data.
            Failure(EncryptionError) if encryption fails.
        """
        ...

    def decrypt(self, encrypted: bytes) -> Result[dict[str, Any], EncryptionError]:
        """Decrypt bytes back to credentials dictionary.

        Args:
            encrypted: Encrypted bytes from encrypt().

        Returns:
            Success(dict) with original credentials dictionary.
            Failure(DecryptionError) if decryption fails.
        """
        ...
