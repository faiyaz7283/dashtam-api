"""Password service for hashing, verification, and validation.

This service handles all password-related operations including:
- Hashing passwords using bcrypt
- Verifying passwords against hashes
- Validating password strength
- Generating secure random passwords

Note: This service is synchronous (uses `def` instead of `async def`)
because password hashing is CPU-bound and bcrypt is a synchronous library.
See docs/development/architecture/async-vs-sync-patterns.md for details.
"""

import re
import secrets
import string
from typing import Tuple

import bcrypt

from src.core.config import get_settings


class PasswordService:
    """Service for password operations using bcrypt.

    This service provides secure password hashing and verification using
    bcrypt with configurable rounds. All methods are synchronous because
    bcrypt is CPU-bound and passlib is a synchronous library.

    Attributes:
        pwd_context: Passlib CryptContext configured with bcrypt
        min_length: Minimum password length (default: 8)
        require_uppercase: Whether uppercase letter is required (default: True)
        require_lowercase: Whether lowercase letter is required (default: True)
        require_digit: Whether digit is required (default: True)
        require_special: Whether special character is required (default: True)
    """

    def __init__(self):
        """Initialize password service with bcrypt configuration.

        Bcrypt rounds are loaded from config (default: 12).
        Higher rounds = more secure but slower (exponential).
        - 10 rounds: ~100ms
        - 12 rounds: ~300ms (recommended)
        - 14 rounds: ~1200ms
        """
        settings = get_settings()
        self.bcrypt_rounds = getattr(settings, "BCRYPT_ROUNDS", 12)

        # Password strength requirements
        self.min_length = 8
        self.require_uppercase = True
        self.require_lowercase = True
        self.require_digit = True
        self.require_special = True

        # Special characters allowed in passwords
        self.special_chars = "!@#$%^&*()_+-=[]{}|;:,.<>?"

    def hash_password(self, password: str) -> str:
        """Hash a password using bcrypt.

        This operation is CPU-intensive (~300ms with 12 rounds) but
        synchronous. It can be called directly from async code without
        blocking the event loop improperly.

        Note: Bcrypt has a 72-byte maximum password length. Passwords are
        automatically truncated to 72 bytes before hashing. This is safe
        because 72 bytes provides sufficient entropy.

        Args:
            password: Plain text password to hash

        Returns:
            Hashed password string (includes salt and algorithm info)

        Example:
            >>> service = PasswordService()
            >>> hashed = service.hash_password("SecurePass123!")
            >>> hashed.startswith("$2b$")
            True
        """
        # Bcrypt has a 72-byte limit, truncate if needed
        # This is safe as 72 bytes provides sufficient entropy
        password_bytes = password.encode("utf-8")[:72]
        salt = bcrypt.gensalt(rounds=self.bcrypt_rounds)
        hashed = bcrypt.hashpw(password_bytes, salt)
        return hashed.decode("utf-8")

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash.

        Uses constant-time comparison to prevent timing attacks.

        Note: Bcrypt has a 72-byte maximum password length. Passwords are
        automatically truncated to 72 bytes before verification to match
        the hashing behavior.

        Args:
            plain_password: Plain text password to verify
            hashed_password: Hashed password to compare against

        Returns:
            True if password matches, False otherwise

        Example:
            >>> service = PasswordService()
            >>> hashed = service.hash_password("SecurePass123!")
            >>> service.verify_password("SecurePass123!", hashed)
            True
            >>> service.verify_password("WrongPassword", hashed)
            False
        """
        # Truncate to 72 bytes to match hashing behavior
        password_bytes = plain_password.encode("utf-8")[:72]
        hashed_bytes = hashed_password.encode("utf-8")
        return bcrypt.checkpw(password_bytes, hashed_bytes)

    def validate_password_strength(self, password: str) -> Tuple[bool, str]:
        """Validate password meets strength requirements.

        Requirements (all must be met):
        - Minimum length (default: 8 characters)
        - At least one uppercase letter
        - At least one lowercase letter
        - At least one digit
        - At least one special character

        Args:
            password: Password to validate

        Returns:
            Tuple of (is_valid: bool, error_message: str)
            If valid, error_message is empty string
            If invalid, error_message describes the issue

        Example:
            >>> service = PasswordService()
            >>> valid, msg = service.validate_password_strength("weak")
            >>> valid
            False
            >>> msg
            'Password must be at least 8 characters long'

            >>> valid, msg = service.validate_password_strength("SecurePass123!")
            >>> valid
            True
            >>> msg
            ''
        """
        # Check minimum length
        if len(password) < self.min_length:
            return False, f"Password must be at least {self.min_length} characters long"

        # Check for uppercase letter
        if self.require_uppercase and not re.search(r"[A-Z]", password):
            return False, "Password must contain at least one uppercase letter"

        # Check for lowercase letter
        if self.require_lowercase and not re.search(r"[a-z]", password):
            return False, "Password must contain at least one lowercase letter"

        # Check for digit
        if self.require_digit and not re.search(r"\d", password):
            return False, "Password must contain at least one digit"

        # Check for special character
        if self.require_special:
            special_char_pattern = f"[{re.escape(self.special_chars)}]"
            if not re.search(special_char_pattern, password):
                return (
                    False,
                    f"Password must contain at least one special character ({self.special_chars})",
                )

        return True, ""

    def needs_rehash(self, hashed_password: str) -> bool:
        """Check if a password hash needs to be updated.

        This happens when:
        - The bcrypt rounds configuration has changed
        - The hashing algorithm has been deprecated
        - The hash format is outdated

        If this returns True, you should re-hash the password
        with the current settings after successful login.

        Args:
            hashed_password: Existing password hash to check

        Returns:
            True if hash should be regenerated, False otherwise

        Example:
            >>> service = PasswordService()
            >>> hashed = service.hash_password("SecurePass123!")
            >>> service.needs_rehash(hashed)
            False
        """
        # Extract the number of rounds from the bcrypt hash
        # Format: $2b$12$...
        try:
            parts = hashed_password.split("$")
            if len(parts) >= 3 and parts[1] in ("2a", "2b", "2y"):
                current_rounds = int(parts[2])
                return current_rounds != self.bcrypt_rounds
        except (ValueError, IndexError):
            pass
        return False

    def generate_random_password(self, length: int = 16) -> str:
        """Generate a cryptographically secure random password.

        Useful for:
        - Temporary passwords during account creation
        - Password reset flows
        - Testing

        The generated password will meet all strength requirements.

        Args:
            length: Length of password to generate (default: 16)
                   Must be >= min_length (8)

        Returns:
            Randomly generated password meeting all requirements

        Raises:
            ValueError: If length < min_length

        Example:
            >>> service = PasswordService()
            >>> password = service.generate_random_password(16)
            >>> len(password)
            16
            >>> service.validate_password_strength(password)[0]
            True
        """
        if length < self.min_length:
            raise ValueError(
                f"Password length must be at least {self.min_length}, got {length}"
            )

        # Character sets
        uppercase = string.ascii_uppercase
        lowercase = string.ascii_lowercase
        digits = string.digits
        special = self.special_chars

        # Ensure at least one character from each required set
        password_chars = []

        if self.require_uppercase:
            password_chars.append(secrets.choice(uppercase))
        if self.require_lowercase:
            password_chars.append(secrets.choice(lowercase))
        if self.require_digit:
            password_chars.append(secrets.choice(digits))
        if self.require_special:
            password_chars.append(secrets.choice(special))

        # Fill remaining length with random characters from all sets
        all_chars = uppercase + lowercase + digits + special
        remaining_length = length - len(password_chars)
        password_chars.extend(
            secrets.choice(all_chars) for _ in range(remaining_length)
        )

        # Shuffle to avoid predictable patterns
        # Use secrets.SystemRandom for cryptographically secure shuffle
        rng = secrets.SystemRandom()
        rng.shuffle(password_chars)

        password = "".join(password_chars)

        # Verify the generated password meets requirements
        # (should always pass, but defensive programming)
        is_valid, error_msg = self.validate_password_strength(password)
        if not is_valid:
            # Recursively try again (should never happen)
            return self.generate_random_password(length)

        return password

    def get_password_requirements_text(self) -> str:
        """Get human-readable password requirements.

        Useful for displaying requirements to users during
        registration or password change flows.

        Returns:
            Formatted string describing password requirements

        Example:
            >>> service = PasswordService()
            >>> print(service.get_password_requirements_text())
            Password must:
            - Be at least 8 characters long
            - Contain at least one uppercase letter
            - Contain at least one lowercase letter
            - Contain at least one digit
            - Contain at least one special character (!@#$%^&*()_+-=[]{}|;:,.<>?)
        """
        requirements = ["Password must:"]
        requirements.append(f"- Be at least {self.min_length} characters long")

        if self.require_uppercase:
            requirements.append("- Contain at least one uppercase letter")
        if self.require_lowercase:
            requirements.append("- Contain at least one lowercase letter")
        if self.require_digit:
            requirements.append("- Contain at least one digit")
        if self.require_special:
            requirements.append(
                f"- Contain at least one special character ({self.special_chars})"
            )

        return "\n".join(requirements)
