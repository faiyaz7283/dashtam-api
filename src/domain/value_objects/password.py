"""Password value object with complexity validation.

Immutable value object that validates password complexity requirements.
"""

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Password:
    """Password value object with complexity validation.

    Immutable value object that ensures passwords meet security requirements.

    Password Requirements:
        - At least 8 characters
        - At least one uppercase letter
        - At least one lowercase letter
        - At least one digit
        - At least one special character

    Attributes:
        value: The password string (validated)

    Raises:
        ValueError: If password does not meet complexity requirements

    Example:
        >>> password = Password("SecurePass123!")
        >>> str(password)
        'SecurePass123!'
        >>> Password("weak")
        Traceback (most recent call last):
        ...
        ValueError: Password must be at least 8 characters
    """

    value: str

    def __post_init__(self) -> None:
        """Validate password complexity after initialization.

        Raises:
            ValueError: If password does not meet requirements.
        """
        self._validate()

    def _validate(self) -> None:
        """Validate password complexity requirements.

        Requirements:
            - At least 8 characters
            - At least one uppercase letter
            - At least one lowercase letter
            - At least one digit
            - At least one special character

        Raises:
            ValueError: If any requirement is not met.
        """
        if len(self.value) < 8:
            raise ValueError("Password must be at least 8 characters")

        if not re.search(r"[A-Z]", self.value):
            raise ValueError("Password must contain uppercase letter")

        if not re.search(r"[a-z]", self.value):
            raise ValueError("Password must contain lowercase letter")

        if not re.search(r"\d", self.value):
            raise ValueError("Password must contain digit")

        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', self.value):
            raise ValueError("Password must contain special character")

    def __str__(self) -> str:
        """Return masked password for security.

        Returns:
            str: Masked password (asterisks).

        Note:
            Never return plaintext password in logs or output.
        """
        return "*" * len(self.value)

    def __repr__(self) -> str:
        """Return repr for debugging (masked).

        Returns:
            str: Masked representation.
        """
        return f"Password('{'*' * len(self.value)}')"
