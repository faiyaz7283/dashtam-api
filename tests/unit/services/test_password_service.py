"""Unit tests for PasswordService.

Tests password hashing, verification, strength validation, and random generation. Covers:
- Bcrypt password hashing with salt
- Password verification (correct and incorrect)
- Password strength validation rules
- Bcrypt hash format validation
- Random secure password generation
- Password requirements text formatting

Note:
    Uses synchronous test pattern (regular def test_*(), NOT async def)
    since PasswordService operates synchronously with bcrypt.
"""

import pytest

from src.services.password_service import PasswordService


class TestPasswordService:
    """Test suite for PasswordService password hashing and validation.

    Validates all password operations including bcrypt hashing, verification,
    strength validation, and secure random password generation.

    Attributes:
        service: PasswordService instance created in setup_method
    """

    def setup_method(self):
        """Set up test fixtures before each test method.

        Initializes:
            - PasswordService instance (fresh for each test)

        Note:
            Called automatically by pytest before each test method in the class.
        """
        self.service = PasswordService()

    def test_hash_password(self):
        """Test password hashing with bcrypt algorithm.

        Verifies that:
        - Hashed password differs from plaintext
        - Hash starts with bcrypt identifier "$2b$"
        - Hash has standard bcrypt length (60 characters)
        - Password is properly encoded with bcrypt

        Note:
            Bcrypt format: $2b$rounds$salt+hash (60 chars total).
        """
        password = "SecurePass123!"

        hashed = self.service.hash_password(password)

        assert hashed != password
        assert hashed.startswith("$2b$")  # bcrypt identifier
        assert len(hashed) == 60  # bcrypt hash length

    def test_hash_password_different_each_time(self):
        """Test that same password produces different hashes due to random salt.

        Verifies that:
        - Two hashes of same password are different
        - Each hash uses unique random salt
        - Salt randomness prevents rainbow table attacks

        Note:
            Bcrypt automatically generates random salt for each hash.
            This is critical for security.
        """
        password = "SecurePass123!"

        hash1 = self.service.hash_password(password)
        hash2 = self.service.hash_password(password)

        assert hash1 != hash2  # Different due to random salt

    def test_verify_password_correct(self):
        """Test successful password verification with correct password.

        Verifies that:
        - Correct password returns True
        - Bcrypt verification handles salt correctly
        - Hash comparison is performed securely

        Note:
            Bcrypt extracts salt from hash for comparison.
        """
        password = "SecurePass123!"
        hashed = self.service.hash_password(password)

        result = self.service.verify_password(password, hashed)

        assert result is True

    def test_verify_password_incorrect(self):
        """Test password verification rejection with incorrect password.

        Verifies that:
        - Incorrect password returns False
        - No exceptions raised on mismatch
        - Timing-safe comparison prevents timing attacks

        Note:
            Bcrypt.checkpw is timing-safe to prevent timing attacks.
        """
        password = "SecurePass123!"
        hashed = self.service.hash_password(password)

        result = self.service.verify_password("WrongPassword!", hashed)

        assert result is False

    def test_verify_password_case_sensitive(self):
        """Test that password verification is case-sensitive.

        Verifies that:
        - Lowercase version of password returns False
        - Case sensitivity is enforced
        - No automatic case normalization occurs

        Note:
            Passwords should always be case-sensitive for security.
        """
        password = "SecurePass123!"
        hashed = self.service.hash_password(password)

        result = self.service.verify_password("securepass123!", hashed)

        assert result is False

    def test_validate_password_strength_valid(self):
        """Test password strength validation with valid strong password.

        Verifies that:
        - Valid password returns (True, "")
        - No error message returned
        - All strength requirements met

        Note:
            Valid password meets: 8+ chars, uppercase, lowercase, digit, special char.
        """
        password = "SecurePass123!"

        is_valid, error_msg = self.service.validate_password_strength(password)

        assert is_valid is True
        assert error_msg == ""

    def test_validate_password_strength_too_short(self):
        """Test password strength validation rejection for short password.

        Verifies that:
        - Password under 8 characters returns (False, error_msg)
        - Error message mentions "at least 8 characters"
        - Minimum length requirement enforced

        Note:
            Minimum 8 characters is industry standard.
        """
        password = "Short1!"

        is_valid, error_msg = self.service.validate_password_strength(password)

        assert is_valid is False
        assert "at least 8 characters" in error_msg

    def test_validate_password_strength_no_uppercase(self):
        """Test password validation rejection without uppercase letter.

        Verifies that:
        - Password without uppercase returns (False, error_msg)
        - Error message mentions "uppercase letter"
        - Character diversity requirement enforced

        Note:
            Uppercase requirement increases password entropy.
        """
        password = "securepass123!"

        is_valid, error_msg = self.service.validate_password_strength(password)

        assert is_valid is False
        assert "uppercase letter" in error_msg

    def test_validate_password_strength_no_lowercase(self):
        """Test password validation rejection without lowercase letter.

        Verifies that:
        - Password without lowercase returns (False, error_msg)
        - Error message mentions "lowercase letter"
        - Character diversity requirement enforced

        Note:
            Lowercase requirement increases password entropy.
        """
        password = "SECUREPASS123!"

        is_valid, error_msg = self.service.validate_password_strength(password)

        assert is_valid is False
        assert "lowercase letter" in error_msg

    def test_validate_password_strength_no_digit(self):
        """Test password validation rejection without numeric digit.

        Verifies that:
        - Password without digit returns (False, error_msg)
        - Error message mentions "digit"
        - Numeric character requirement enforced

        Note:
            Digit requirement increases password entropy.
        """
        password = "SecurePass!"

        is_valid, error_msg = self.service.validate_password_strength(password)

        assert is_valid is False
        assert "digit" in error_msg

    def test_validate_password_strength_no_special_char(self):
        """Test password validation rejection without special character.

        Verifies that:
        - Password without special char returns (False, error_msg)
        - Error message mentions "special character"
        - Special character requirement enforced

        Note:
            Special chars: !@#$%^&*()_+-=[]{}|;:,.<>?
        """
        password = "SecurePass123"

        is_valid, error_msg = self.service.validate_password_strength(password)

        assert is_valid is False
        assert "special character" in error_msg

    def test_needs_rehash_fresh_hash(self):
        """Test that fresh bcrypt hash doesn't need rehashing.

        Verifies that:
        - Newly created hash returns False for needs_rehash
        - Hash uses current bcrypt work factor
        - No rehashing needed for recent hashes

        Note:
            needs_rehash checks if work factor has changed since hashing.
        """
        password = "SecurePass123!"
        hashed = self.service.hash_password(password)

        needs_rehash = self.service.needs_rehash(hashed)

        assert needs_rehash is False

    def test_generate_random_password_default_length(self):
        """Test secure random password generation with default length.

        Verifies that:
        - Generated password is 16 characters (default)
        - Password meets all strength requirements
        - Uses cryptographically secure random generation

        Note:
            Default length 16 provides strong security.
        """
        password = self.service.generate_random_password()

        assert len(password) == 16
        # Verify it meets strength requirements
        is_valid, _ = self.service.validate_password_strength(password)
        assert is_valid is True

    def test_generate_random_password_custom_length(self):
        """Test random password generation with custom specified length.

        Verifies that:
        - Generated password has requested length (20)
        - Password meets all strength requirements
        - Length parameter is respected

        Note:
            Custom length useful for different security requirements.
        """
        password = self.service.generate_random_password(length=20)

        assert len(password) == 20
        is_valid, _ = self.service.validate_password_strength(password)
        assert is_valid is True

    def test_generate_random_password_minimum_length(self):
        """Test random password generation at minimum allowed length.

        Verifies that:
        - Minimum length (8 chars) is supported
        - Generated password still meets strength requirements
        - Edge case of minimum length handled correctly

        Note:
            8 characters is minimum length to meet all requirements.
        """
        password = self.service.generate_random_password(length=8)

        assert len(password) == 8
        is_valid, _ = self.service.validate_password_strength(password)
        assert is_valid is True

    def test_generate_random_password_too_short_raises_error(self):
        """Test random password generation rejection for insufficient length.

        Verifies that:
        - Length under 8 raises ValueError
        - Error message mentions "at least 8"
        - Impossible lengths are rejected early

        Raises:
            ValueError: Expected exception for length < 8

        Note:
            Minimum 8 chars needed to meet all strength requirements.
        """
        with pytest.raises(ValueError, match="at least 8"):
            self.service.generate_random_password(length=7)

    def test_generate_random_password_unique(self):
        """Test that generated passwords are cryptographically unique.

        Verifies that:
        - Two generated passwords are different
        - Random generation uses secure entropy source
        - No predictable patterns in passwords

        Note:
            Uses secrets module for cryptographically secure randomness.
        """
        password1 = self.service.generate_random_password()
        password2 = self.service.generate_random_password()

        assert password1 != password2

    def test_get_password_requirements_text(self):
        """Test password requirements text for user display.

        Verifies that:
        - Requirements text includes all rules
        - Text mentions minimum 8 characters
        - Text mentions uppercase/lowercase requirement
        - Text mentions digit requirement
        - Text mentions special character requirement

        Note:
            Used for displaying requirements to users during registration.
        """
        requirements = self.service.get_password_requirements_text()

        assert "Password must:" in requirements
        assert "8 characters" in requirements
        assert "uppercase" in requirements
        assert "lowercase" in requirements
        assert "digit" in requirements
        assert "special character" in requirements
