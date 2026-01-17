"""Tests for src/core/constants.py.

Verifies that centralized constants have correct values and types.
These constants are used across the codebase for token generation,
encryption, timeouts, and API prefixes.

Reference:
    - src/core/constants.py
"""

from src.core.constants import (
    AES_KEY_LENGTH,
    BCRYPT_ROUNDS_DEFAULT,
    BEARER_PREFIX,
    PROVIDER_TIMEOUT_DEFAULT,
    RESPONSE_BODY_MAX_LENGTH,
    TOKEN_BYTES,
    TOKEN_HEX_LENGTH,
)


class TestTokenConstants:
    """Tests for token generation constants."""

    def test_token_bytes_value(self) -> None:
        """TOKEN_BYTES should be 32 (256 bits of entropy)."""
        assert TOKEN_BYTES == 32

    def test_token_bytes_type(self) -> None:
        """TOKEN_BYTES should be an integer."""
        assert isinstance(TOKEN_BYTES, int)

    def test_token_hex_length_value(self) -> None:
        """TOKEN_HEX_LENGTH should be 64 (32 bytes * 2 hex chars)."""
        assert TOKEN_HEX_LENGTH == 64

    def test_token_hex_length_is_double_bytes(self) -> None:
        """TOKEN_HEX_LENGTH should be exactly 2x TOKEN_BYTES."""
        assert TOKEN_HEX_LENGTH == TOKEN_BYTES * 2


class TestEncryptionConstants:
    """Tests for encryption-related constants."""

    def test_aes_key_length_value(self) -> None:
        """AES_KEY_LENGTH should be 32 (256 bits for AES-256)."""
        assert AES_KEY_LENGTH == 32

    def test_bcrypt_rounds_default_value(self) -> None:
        """BCRYPT_ROUNDS_DEFAULT should be 12 (~300ms hashing time)."""
        assert BCRYPT_ROUNDS_DEFAULT == 12

    def test_bcrypt_rounds_in_valid_range(self) -> None:
        """BCRYPT_ROUNDS_DEFAULT should be in safe range (4-31)."""
        assert 4 <= BCRYPT_ROUNDS_DEFAULT <= 31


class TestProviderConstants:
    """Tests for provider API constants."""

    def test_provider_timeout_default_value(self) -> None:
        """PROVIDER_TIMEOUT_DEFAULT should be 30.0 seconds."""
        assert PROVIDER_TIMEOUT_DEFAULT == 30.0

    def test_provider_timeout_is_float(self) -> None:
        """PROVIDER_TIMEOUT_DEFAULT should be a float."""
        assert isinstance(PROVIDER_TIMEOUT_DEFAULT, float)


class TestApiConstants:
    """Tests for API-related constants."""

    def test_bearer_prefix_value(self) -> None:
        """BEARER_PREFIX should be 'Bearer ' with trailing space."""
        assert BEARER_PREFIX == "Bearer "

    def test_bearer_prefix_ends_with_space(self) -> None:
        """BEARER_PREFIX must end with a space for proper concatenation."""
        assert BEARER_PREFIX.endswith(" ")

    def test_response_body_max_length_value(self) -> None:
        """RESPONSE_BODY_MAX_LENGTH should be 500 characters."""
        assert RESPONSE_BODY_MAX_LENGTH == 500

    def test_response_body_max_length_is_positive(self) -> None:
        """RESPONSE_BODY_MAX_LENGTH should be positive."""
        assert RESPONSE_BODY_MAX_LENGTH > 0
