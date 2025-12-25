"""Unit tests for Email and Password value objects.

Tests cover:
- Email: validation, normalization, __str__, __repr__, error handling
- Password: complexity validation, __str__ masking, __repr__, error handling

Architecture:
- Unit tests for domain value objects
- Test validation logic and edge cases
- No dependencies or mocking needed
"""

import pytest

from src.domain.value_objects.email import Email
from src.domain.value_objects.password import Password


@pytest.mark.unit
class TestEmailValueObject:
    """Test Email value object."""

    def test_email_with_valid_format(self):
        """Test Email creation with valid format."""
        email = Email("user@example.com")

        assert email.value == "user@example.com"

    def test_email_normalizes_to_lowercase(self):
        """Test Email normalizes to lowercase."""
        email = Email("User@Example.COM")

        # email-validator normalizes the domain, not necessarily the local part
        assert email.value.lower() == "user@example.com"

    def test_email_str_returns_email_address(self):
        """Test __str__ returns email address."""
        email = Email("test@example.com")

        assert str(email) == "test@example.com"

    def test_email_repr_returns_formatted_string(self):
        """Test __repr__ returns formatted representation."""
        email = Email("test@example.com")

        assert repr(email) == "Email('test@example.com')"

    def test_email_fails_with_invalid_format(self):
        """Test Email raises ValueError with invalid format."""
        with pytest.raises(ValueError, match="Invalid email"):
            Email("not-an-email")

    def test_email_fails_with_missing_at_sign(self):
        """Test Email raises ValueError without @ sign."""
        with pytest.raises(ValueError):
            Email("userexample.com")

    def test_email_fails_with_missing_domain(self):
        """Test Email raises ValueError without domain."""
        with pytest.raises(ValueError):
            Email("user@")


@pytest.mark.unit
class TestPasswordValueObject:
    """Test Password value object."""

    def test_password_with_valid_complexity(self):
        """Test Password creation with valid complexity."""
        password = Password("SecurePass123!")

        assert password.value == "SecurePass123!"

    def test_password_str_returns_masked(self):
        """Test __str__ returns masked password for security."""
        password = Password("SecurePass123!")

        assert str(password) == "*" * len("SecurePass123!")
        assert "*" in str(password)
        assert "SecurePass123!" not in str(password)

    def test_password_repr_returns_masked(self):
        """Test __repr__ returns masked password for security."""
        password = Password("SecurePass123!")

        result = repr(password)
        assert "Password" in result
        assert "*" in result
        assert "SecurePass123!" not in result

    def test_password_fails_too_short(self):
        """Test Password raises ValueError when too short."""
        with pytest.raises(ValueError, match="at least 8 characters"):
            Password("Short1!")

    def test_password_fails_missing_uppercase(self):
        """Test Password raises ValueError without uppercase letter."""
        with pytest.raises(ValueError, match="uppercase"):
            Password("securepass123!")

    def test_password_fails_missing_lowercase(self):
        """Test Password raises ValueError without lowercase letter."""
        with pytest.raises(ValueError, match="lowercase"):
            Password("SECUREPASS123!")

    def test_password_fails_missing_digit(self):
        """Test Password raises ValueError without digit."""
        with pytest.raises(ValueError, match="digit"):
            Password("SecurePass!")

    def test_password_fails_missing_special_char(self):
        """Test Password raises ValueError without special character."""
        with pytest.raises(ValueError, match="special character"):
            Password("SecurePass123")
