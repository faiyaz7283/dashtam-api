"""Email value object with validation.

Immutable value object that validates email format.
"""

from dataclasses import dataclass

from email_validator import EmailNotValidError, validate_email


@dataclass(frozen=True)
class Email:
    """Email value object with format validation.

    Immutable value object that ensures email addresses are valid.
    Uses email-validator library for RFC-compliant validation.

    Attributes:
        value: The email address string (validated, lowercase)

    Raises:
        ValueError: If email format is invalid

    Example:
        >>> email = Email("user@example.com")
        >>> str(email)
        'user@example.com'
        >>> Email("invalid")
        Traceback (most recent call last):
        ...
        ValueError: Invalid email: ...
    """

    value: str

    def __post_init__(self) -> None:
        """Validate email format after initialization.

        Uses email-validator library for comprehensive validation.
        Converts email to lowercase for case-insensitive comparison.

        Raises:
            ValueError: If email format is invalid.
        """
        try:
            # Validate email format (no deliverability check for performance)
            validated = validate_email(self.value, check_deliverability=False)
            # Store normalized (lowercase) email
            # Use object.__setattr__ because dataclass is frozen
            object.__setattr__(self, "value", validated.normalized)
        except EmailNotValidError as e:
            raise ValueError(f"Invalid email: {e}") from e

    def __str__(self) -> str:
        """Return email address as string.

        Returns:
            str: The email address.
        """
        return self.value

    def __repr__(self) -> str:
        """Return repr for debugging.

        Returns:
            str: String representation of Email object.
        """
        return f"Email('{self.value}')"
