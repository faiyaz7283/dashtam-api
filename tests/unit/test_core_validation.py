"""Unit tests for core validation functions.

Tests cover:
- validate_not_empty: null, empty string, whitespace
- validate_email: valid, invalid formats
- validate_min_length: boundary cases
- validate_max_length: boundary cases
- Result type returns (Success/Failure)

Architecture:
- Unit tests for pure validation functions
- No mocking required (pure functions)
- Test all error paths and edge cases
"""

import pytest

from src.core.enums import ErrorCode
from src.core.result import Failure, Success
from src.core.validation import (
    validate_email,
    validate_max_length,
    validate_min_length,
    validate_not_empty,
)


@pytest.mark.unit
class TestValidateNotEmpty:
    """Test validate_not_empty function."""

    def test_validate_not_empty_with_valid_string(self):
        """Test validation passes with non-empty string."""
        result = validate_not_empty("hello", "test_field")

        assert isinstance(result, Success)
        assert result.value == "hello"

    def test_validate_not_empty_fails_with_none(self):
        """Test validation fails with None value."""
        result = validate_not_empty(None, "test_field")

        assert isinstance(result, Failure)
        assert result.error.code == ErrorCode.VALIDATION_FAILED
        assert "test_field cannot be empty" in result.error.message

    def test_validate_not_empty_fails_with_empty_string(self):
        """Test validation fails with empty string."""
        result = validate_not_empty("", "test_field")

        assert isinstance(result, Failure)
        assert "test_field cannot be empty" in result.error.message

    def test_validate_not_empty_fails_with_whitespace(self):
        """Test validation fails with whitespace only."""
        result = validate_not_empty("   ", "test_field")

        assert isinstance(result, Failure)
        assert "test_field cannot be empty" in result.error.message

    def test_validate_not_empty_with_non_string_value(self):
        """Test validation passes with non-string value (e.g., number)."""
        result = validate_not_empty(123, "test_field")

        assert isinstance(result, Success)
        assert result.value == 123


@pytest.mark.unit
class TestValidateEmail:
    """Test validate_email function."""

    def test_validate_email_with_valid_format(self):
        """Test validation passes with valid email."""
        result = validate_email("user@example.com")

        assert isinstance(result, Success)
        assert result.value == "user@example.com"

    def test_validate_email_with_subdomain(self):
        """Test validation passes with subdomain email."""
        result = validate_email("user@mail.example.com")

        assert isinstance(result, Success)

    def test_validate_email_with_plus_sign(self):
        """Test validation passes with plus sign in email."""
        result = validate_email("user+tag@example.com")

        assert isinstance(result, Success)

    def test_validate_email_fails_without_at_sign(self):
        """Test validation fails without @ sign."""
        result = validate_email("userexample.com")

        assert isinstance(result, Failure)
        assert result.error.code == ErrorCode.INVALID_EMAIL
        assert "Invalid email format" in result.error.message

    def test_validate_email_fails_without_domain(self):
        """Test validation fails without domain."""
        result = validate_email("user@")

        assert isinstance(result, Failure)

    def test_validate_email_fails_without_tld(self):
        """Test validation fails without TLD."""
        result = validate_email("user@example")

        assert isinstance(result, Failure)

    def test_validate_email_fails_with_spaces(self):
        """Test validation fails with spaces."""
        result = validate_email("user @example.com")

        assert isinstance(result, Failure)


@pytest.mark.unit
class TestValidateMinLength:
    """Test validate_min_length function."""

    def test_validate_min_length_passes_exact_length(self):
        """Test validation passes with exact minimum length."""
        result = validate_min_length("hello", 5, "password")

        assert isinstance(result, Success)
        assert result.value == "hello"

    def test_validate_min_length_passes_longer(self):
        """Test validation passes with longer than minimum."""
        result = validate_min_length("hello world", 5, "password")

        assert isinstance(result, Success)

    def test_validate_min_length_fails_shorter(self):
        """Test validation fails with shorter than minimum."""
        result = validate_min_length("hi", 5, "password")

        assert isinstance(result, Failure)
        assert result.error.code == ErrorCode.VALIDATION_FAILED
        assert "password must be at least 5 characters" in result.error.message

    def test_validate_min_length_fails_empty_string(self):
        """Test validation fails with empty string."""
        result = validate_min_length("", 1, "field")

        assert isinstance(result, Failure)


@pytest.mark.unit
class TestValidateMaxLength:
    """Test validate_max_length function."""

    def test_validate_max_length_passes_exact_length(self):
        """Test validation passes with exact maximum length."""
        result = validate_max_length("hello", 5, "username")

        assert isinstance(result, Success)
        assert result.value == "hello"

    def test_validate_max_length_passes_shorter(self):
        """Test validation passes with shorter than maximum."""
        result = validate_max_length("hi", 5, "username")

        assert isinstance(result, Success)

    def test_validate_max_length_fails_longer(self):
        """Test validation fails with longer than maximum."""
        result = validate_max_length("hello world", 5, "username")

        assert isinstance(result, Failure)
        assert result.error.code == ErrorCode.VALIDATION_FAILED
        assert "username must be at most 5 characters" in result.error.message

    def test_validate_max_length_passes_empty_string(self):
        """Test validation passes with empty string (zero length)."""
        result = validate_max_length("", 10, "field")

        assert isinstance(result, Success)
