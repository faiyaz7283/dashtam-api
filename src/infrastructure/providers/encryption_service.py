"""Encryption service for provider credentials.

Provides AES-256-GCM encryption for secure storage of OAuth tokens
and other sensitive provider credentials.

Security Properties:
    - Confidentiality: Only holder of key can decrypt
    - Integrity: Tampering is detected via GCM authentication tag
    - Uniqueness: Random IV per encryption prevents pattern analysis

Architecture:
    - Infrastructure adapter (catches cryptography exceptions)
    - Returns Result types (railway-oriented programming)
    - Uses domain error codes (ErrorCode enum)

Reference:
    - docs/architecture/provider-integration-architecture.md
    - docs/architecture/error-handling-architecture.md
"""

import json
import os
from typing import Any

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from src.core.enums import ErrorCode
from src.core.result import Failure, Result, Success

# Import error types from domain protocol (single source of truth)
from src.domain.protocols.encryption_protocol import (
    DecryptionError,
    EncryptionError,
    EncryptionKeyError,
    SerializationError,
)

# Re-export error types for backward compatibility
__all__ = [
    "DecryptionError",
    "EncryptionError",
    "EncryptionKeyError",
    "EncryptionService",
    "SerializationError",
]


# =============================================================================
# Encryption Service
# =============================================================================


class EncryptionService:
    """AES-256-GCM encryption service for provider credentials.

    Encrypts and decrypts credential dictionaries (containing access tokens,
    refresh tokens, etc.) to/from bytes for secure database storage.

    Format:
        Encrypted bytes = IV (12 bytes) || ciphertext || auth_tag (16 bytes)

    Usage:
        >>> from src.core.config import get_settings
        >>> service = EncryptionService.create(get_settings().encryption_key)
        >>> match service:
        ...     case Success(svc):
        ...         # Encrypt credentials
        ...         result = svc.encrypt({"access_token": "abc123"})
        ...     case Failure(error):
        ...         # Handle invalid key
        ...         ...

    Thread Safety:
        This service is thread-safe. The AESGCM instance can be used
        concurrently from multiple threads.

    Reference:
        - NIST SP 800-38D (GCM specification)
        - docs/architecture/provider-integration-architecture.md
    """

    IV_SIZE = 12  # 96 bits - NIST recommended for GCM
    MIN_ENCRYPTED_SIZE = 12 + 16  # IV + auth tag

    def __init__(self, aesgcm: AESGCM) -> None:
        """Initialize with pre-validated AESGCM instance.

        Use EncryptionService.create() factory instead of direct construction.

        Args:
            aesgcm: Pre-initialized AESGCM cipher instance.
        """
        self._aesgcm = aesgcm

    @classmethod
    def create(cls, key: bytes) -> Result["EncryptionService", EncryptionKeyError]:
        """Create encryption service with validated key.

        Factory method that validates the encryption key and returns
        a Result type.

        Args:
            key: 32-byte (256-bit) encryption key.

        Returns:
            Success(EncryptionService) if key is valid.
            Failure(EncryptionKeyError) if key is invalid.

        Example:
            >>> key = os.urandom(32)
            >>> match EncryptionService.create(key):
            ...     case Success(service):
            ...         # Use service
            ...     case Failure(error):
            ...         logger.error(f"Invalid key: {error.message}")
        """
        if len(key) != 32:
            return Failure(
                error=EncryptionKeyError(
                    code=ErrorCode.ENCRYPTION_KEY_INVALID,
                    message=(
                        f"Encryption key must be exactly 32 bytes (256 bits), "
                        f"got {len(key)} bytes"
                    ),
                    details={"expected_length": "32", "actual_length": str(len(key))},
                )
            )

        try:
            aesgcm = AESGCM(key)
            return Success(value=cls(aesgcm))
        except Exception as e:
            return Failure(
                error=EncryptionKeyError(
                    code=ErrorCode.ENCRYPTION_KEY_INVALID,
                    message=f"Failed to initialize encryption: {e}",
                )
            )

    def encrypt(self, data: dict[str, Any]) -> Result[bytes, EncryptionError]:
        """Encrypt credentials dictionary to bytes.

        Serializes the dictionary to JSON, then encrypts using AES-256-GCM
        with a random IV. The IV is prepended to the ciphertext.

        Args:
            data: Credentials dictionary to encrypt. Must be JSON-serializable.
                Typically contains access_token, refresh_token, etc.

        Returns:
            Success(bytes) with encrypted data in format:
                IV (12 bytes) || ciphertext || auth_tag (16 bytes)
            Failure(SerializationError) if data cannot be serialized.
            Failure(EncryptionError) if encryption fails.

        Example:
            >>> credentials = {
            ...     "access_token": "abc123",
            ...     "refresh_token": "xyz789",
            ... }
            >>> match service.encrypt(credentials):
            ...     case Success(encrypted):
            ...         # Store encrypted bytes in database
            ...     case Failure(error):
            ...         # Handle error
        """
        # Serialize to JSON
        try:
            plaintext = json.dumps(data, separators=(",", ":")).encode("utf-8")
        except (TypeError, ValueError) as e:
            return Failure(
                error=SerializationError(
                    code=ErrorCode.INVALID_INPUT,
                    message=f"Failed to serialize credentials to JSON: {e}",
                )
            )

        # Generate random IV and encrypt
        try:
            iv = os.urandom(self.IV_SIZE)
            ciphertext = self._aesgcm.encrypt(iv, plaintext, associated_data=None)
            return Success(value=iv + ciphertext)
        except Exception as e:
            return Failure(
                error=EncryptionError(
                    code=ErrorCode.ENCRYPTION_FAILED,
                    message=f"Encryption failed: {e}",
                )
            )

    def decrypt(self, encrypted: bytes) -> Result[dict[str, Any], EncryptionError]:
        """Decrypt bytes back to credentials dictionary.

        Extracts the IV from the first 12 bytes, then decrypts the remaining
        ciphertext using AES-256-GCM.

        Args:
            encrypted: Encrypted bytes from encrypt().

        Returns:
            Success(dict) with original credentials dictionary.
            Failure(DecryptionError) if decryption fails (wrong key, tampered).
            Failure(SerializationError) if decrypted data is not valid JSON.

        Example:
            >>> match service.decrypt(encrypted_bytes):
            ...     case Success(credentials):
            ...         access_token = credentials["access_token"]
            ...     case Failure(error):
            ...         # Handle error - may need user to re-authenticate
        """
        # Validate minimum size
        if len(encrypted) < self.MIN_ENCRYPTED_SIZE:
            return Failure(
                error=DecryptionError(
                    code=ErrorCode.INVALID_INPUT,
                    message=(
                        f"Encrypted data too short: {len(encrypted)} bytes "
                        f"(minimum {self.MIN_ENCRYPTED_SIZE} bytes)"
                    ),
                    details={
                        "actual_length": str(len(encrypted)),
                        "minimum_length": str(self.MIN_ENCRYPTED_SIZE),
                    },
                )
            )

        # Extract IV and ciphertext
        iv = encrypted[: self.IV_SIZE]
        ciphertext = encrypted[self.IV_SIZE :]

        # Decrypt
        try:
            plaintext = self._aesgcm.decrypt(iv, ciphertext, associated_data=None)
        except Exception:
            # AESGCM raises InvalidTag if authentication fails
            return Failure(
                error=DecryptionError(
                    code=ErrorCode.DECRYPTION_FAILED,
                    message="Failed to decrypt credentials: invalid key or tampered data",
                )
            )

        # Deserialize JSON
        try:
            return Success(value=json.loads(plaintext.decode("utf-8")))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            return Failure(
                error=SerializationError(
                    code=ErrorCode.INVALID_INPUT,
                    message=f"Failed to deserialize decrypted credentials: {e}",
                )
            )
