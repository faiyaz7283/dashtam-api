"""Encryption service for secure storage of sensitive data.

This module provides encryption and decryption functionality for storing
sensitive data like OAuth tokens. It uses Fernet (symmetric encryption)
from the cryptography library, which provides authenticated encryption
with AES 128 in CBC mode.

The encryption key is derived from the application's SECRET_KEY or can be
configured separately for production environments.
"""

import base64
import logging
import os
from typing import Optional

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from src.core.config import settings

logger = logging.getLogger(__name__)


class EncryptionService:
    """Service for encrypting and decrypting sensitive data.

    This service provides a simple interface for encrypting strings
    (like OAuth tokens) before storing them in the database and
    decrypting them when needed.

    The encryption key is derived from the application's SECRET_KEY
    or can be set via ENCRYPTION_KEY environment variable.
    """

    _instance: Optional["EncryptionService"] = None
    _cipher: Optional[Fernet] = None

    def __new__(cls) -> "EncryptionService":
        """Singleton pattern to ensure one encryption service instance."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialize the encryption service with a cipher."""
        if self._cipher is None:
            self._cipher = self._create_cipher()

    def _create_cipher(self) -> Fernet:
        """Create a Fernet cipher for encryption/decryption.

        The cipher uses either:
        1. ENCRYPTION_KEY from environment (if set)
        2. Derived key from SECRET_KEY (for development)

        Returns:
            Fernet cipher instance.
        """
        # Check for explicit encryption key
        encryption_key = os.getenv("ENCRYPTION_KEY")

        if encryption_key:
            # Use provided encryption key
            try:
                # Ensure it's properly formatted
                if not encryption_key.startswith("gAAAAA"):
                    # If it's not a Fernet key, try to use it as is
                    encryption_key = base64.urlsafe_b64encode(
                        encryption_key.encode()[:32].ljust(32, b"0")
                    )
                else:
                    encryption_key = encryption_key.encode()

                cipher = Fernet(encryption_key)
                logger.info("Using provided ENCRYPTION_KEY")
                return cipher
            except Exception as e:
                logger.warning(f"Invalid ENCRYPTION_KEY, generating new one: {e}")

        # Derive key from SECRET_KEY for development
        if hasattr(settings, "SECRET_KEY"):
            # Use PBKDF2 to derive a key from the secret
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=b"dashtam-token-salt",  # Fixed salt for consistency
                iterations=100000,
            )
            key = base64.urlsafe_b64encode(kdf.derive(settings.SECRET_KEY.encode()))
            logger.info("Using key derived from SECRET_KEY")
            return Fernet(key)

        # Generate a new key if nothing else is available
        key = Fernet.generate_key()
        logger.warning(
            "Generated new encryption key. Set ENCRYPTION_KEY in production!"
        )
        logger.debug(f"Generated key: {key.decode()}")
        return Fernet(key)

    def encrypt(self, plaintext: str) -> str:
        """Encrypt a string value.

        Args:
            plaintext: The string to encrypt.

        Returns:
            Base64-encoded encrypted string.

        Raises:
            Exception: If encryption fails.
        """
        if not plaintext:
            return ""

        try:
            encrypted_bytes = self._cipher.encrypt(plaintext.encode())
            return encrypted_bytes.decode("utf-8")
        except Exception as e:
            logger.error(f"Encryption failed: {e}")
            raise Exception("Failed to encrypt data") from e

    def decrypt(self, ciphertext: str) -> str:
        """Decrypt an encrypted string.

        Args:
            ciphertext: The encrypted string to decrypt.

        Returns:
            The original plaintext string.

        Raises:
            Exception: If decryption fails.
        """
        if not ciphertext:
            return ""

        try:
            decrypted_bytes = self._cipher.decrypt(ciphertext.encode())
            return decrypted_bytes.decode("utf-8")
        except Exception as e:
            logger.error(f"Decryption failed: {e}")
            raise Exception("Failed to decrypt data") from e

    def encrypt_dict(self, data: dict) -> dict:
        """Encrypt all string values in a dictionary.

        Useful for encrypting multiple tokens at once.

        Args:
            data: Dictionary with string values to encrypt.

        Returns:
            Dictionary with encrypted values.
        """
        encrypted = {}
        for key, value in data.items():
            if isinstance(value, str):
                encrypted[key] = self.encrypt(value)
            else:
                encrypted[key] = value
        return encrypted

    def decrypt_dict(self, data: dict) -> dict:
        """Decrypt all string values in a dictionary.

        Args:
            data: Dictionary with encrypted string values.

        Returns:
            Dictionary with decrypted values.
        """
        decrypted = {}
        for key, value in data.items():
            if isinstance(value, str) and value:
                try:
                    decrypted[key] = self.decrypt(value)
                except Exception:
                    # If decryption fails, keep original value
                    decrypted[key] = value
            else:
                decrypted[key] = value
        return decrypted

    def is_encrypted(self, value: str) -> bool:
        """Check if a string appears to be encrypted.

        This is a heuristic check based on Fernet token format.

        Args:
            value: String to check.

        Returns:
            True if the string appears to be encrypted.
        """
        if not value:
            return False

        # Fernet tokens start with "gAAAAA"
        if value.startswith("gAAAAA"):
            return True

        # Try to decrypt - if it fails, it's not encrypted
        try:
            self.decrypt(value)
            return True
        except Exception:
            return False

    @classmethod
    def get_instance(cls) -> "EncryptionService":
        """Get the singleton instance of the encryption service.

        Returns:
            The encryption service instance.
        """
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance


# Convenience functions for direct use
_encryption_service = None


def get_encryption_service() -> EncryptionService:
    """Get the global encryption service instance.

    Returns:
        The encryption service singleton.
    """
    global _encryption_service
    if _encryption_service is None:
        _encryption_service = EncryptionService()
    return _encryption_service


def encrypt_token(token: str) -> str:
    """Convenience function to encrypt a token.

    Args:
        token: The token to encrypt.

    Returns:
        Encrypted token string.
    """
    service = get_encryption_service()
    return service.encrypt(token)


def decrypt_token(encrypted_token: str) -> str:
    """Convenience function to decrypt a token.

    Args:
        encrypted_token: The encrypted token.

    Returns:
        Decrypted token string.
    """
    service = get_encryption_service()
    return service.decrypt(encrypted_token)
