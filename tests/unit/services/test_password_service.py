"""Unit tests for PasswordService.

Tests password hashing, verification, strength validation, and random generation.
"""

import pytest

from src.services.password_service import PasswordService


class TestPasswordService:
    """Test suite for PasswordService."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = PasswordService()

    def test_hash_password(self):
        """Test password hashing creates bcrypt hash."""
        password = "SecurePass123!"

        hashed = self.service.hash_password(password)

        assert hashed != password
        assert hashed.startswith("$2b$")  # bcrypt identifier
        assert len(hashed) == 60  # bcrypt hash length

    def test_hash_password_different_each_time(self):
        """Test that same password creates different hashes (salt)."""
        password = "SecurePass123!"

        hash1 = self.service.hash_password(password)
        hash2 = self.service.hash_password(password)

        assert hash1 != hash2  # Different due to random salt

    def test_verify_password_correct(self):
        """Test password verification with correct password."""
        password = "SecurePass123!"
        hashed = self.service.hash_password(password)

        result = self.service.verify_password(password, hashed)

        assert result is True

    def test_verify_password_incorrect(self):
        """Test password verification with incorrect password."""
        password = "SecurePass123!"
        hashed = self.service.hash_password(password)

        result = self.service.verify_password("WrongPassword!", hashed)

        assert result is False

    def test_verify_password_case_sensitive(self):
        """Test password verification is case sensitive."""
        password = "SecurePass123!"
        hashed = self.service.hash_password(password)

        result = self.service.verify_password("securepass123!", hashed)

        assert result is False

    def test_validate_password_strength_valid(self):
        """Test password strength validation with valid password."""
        password = "SecurePass123!"

        is_valid, error_msg = self.service.validate_password_strength(password)

        assert is_valid is True
        assert error_msg == ""

    def test_validate_password_strength_too_short(self):
        """Test password validation fails if too short."""
        password = "Short1!"

        is_valid, error_msg = self.service.validate_password_strength(password)

        assert is_valid is False
        assert "at least 8 characters" in error_msg

    def test_validate_password_strength_no_uppercase(self):
        """Test password validation fails without uppercase letter."""
        password = "securepass123!"

        is_valid, error_msg = self.service.validate_password_strength(password)

        assert is_valid is False
        assert "uppercase letter" in error_msg

    def test_validate_password_strength_no_lowercase(self):
        """Test password validation fails without lowercase letter."""
        password = "SECUREPASS123!"

        is_valid, error_msg = self.service.validate_password_strength(password)

        assert is_valid is False
        assert "lowercase letter" in error_msg

    def test_validate_password_strength_no_digit(self):
        """Test password validation fails without digit."""
        password = "SecurePass!"

        is_valid, error_msg = self.service.validate_password_strength(password)

        assert is_valid is False
        assert "digit" in error_msg

    def test_validate_password_strength_no_special_char(self):
        """Test password validation fails without special character."""
        password = "SecurePass123"

        is_valid, error_msg = self.service.validate_password_strength(password)

        assert is_valid is False
        assert "special character" in error_msg

    def test_needs_rehash_fresh_hash(self):
        """Test needs_rehash returns False for fresh hash."""
        password = "SecurePass123!"
        hashed = self.service.hash_password(password)

        needs_rehash = self.service.needs_rehash(hashed)

        assert needs_rehash is False

    def test_generate_random_password_default_length(self):
        """Test random password generation with default length."""
        password = self.service.generate_random_password()

        assert len(password) == 16
        # Verify it meets strength requirements
        is_valid, _ = self.service.validate_password_strength(password)
        assert is_valid is True

    def test_generate_random_password_custom_length(self):
        """Test random password generation with custom length."""
        password = self.service.generate_random_password(length=20)

        assert len(password) == 20
        is_valid, _ = self.service.validate_password_strength(password)
        assert is_valid is True

    def test_generate_random_password_minimum_length(self):
        """Test random password generation with minimum length."""
        password = self.service.generate_random_password(length=8)

        assert len(password) == 8
        is_valid, _ = self.service.validate_password_strength(password)
        assert is_valid is True

    def test_generate_random_password_too_short_raises_error(self):
        """Test random password generation fails if length too short."""
        with pytest.raises(ValueError, match="at least 8"):
            self.service.generate_random_password(length=7)

    def test_generate_random_password_unique(self):
        """Test that random passwords are unique."""
        password1 = self.service.generate_random_password()
        password2 = self.service.generate_random_password()

        assert password1 != password2

    def test_get_password_requirements_text(self):
        """Test password requirements text formatting."""
        requirements = self.service.get_password_requirements_text()

        assert "Password must:" in requirements
        assert "8 characters" in requirements
        assert "uppercase" in requirements
        assert "lowercase" in requirements
        assert "digit" in requirements
        assert "special character" in requirements
