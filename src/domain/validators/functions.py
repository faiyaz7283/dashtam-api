"""Centralized validation functions (DRY principle).

All validation logic defined once, reused everywhere via Annotated types.
Validators are pure functions that raise ValueError on validation failure.

As of F8.4, all validators are cataloged in the Validation Rules Registry
(src/domain/validators/registry.py) with complete metadata.

Reference:
    - docs/architecture/validation-registry-architecture.md (F8.4)
    - docs/architecture/registry-pattern-architecture.md
    - clean-slate-reference.md §1.5 (Annotated Types)
"""

import re


def validate_email(v: str) -> str:
    """Validate email format.

    Uses email-validator library pattern for consistency with Email value object.

    Args:
        v: Email address to validate.

    Returns:
        Normalized email (lowercase).

    Raises:
        ValueError: If email format is invalid.

    Example:
        >>> validate_email("User@Example.COM")
        'user@example.com'
        >>> validate_email("invalid")
        ValueError: Invalid email format
    """
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    if not re.match(pattern, v):
        raise ValueError(f"Invalid email format: {v}")
    return v.lower()  # Normalize to lowercase


def validate_strong_password(v: str) -> str:
    """Validate password strength.

    Requirements match Password value object validation.

    Args:
        v: Password to validate.

    Returns:
        Password unchanged (validation only).

    Raises:
        ValueError: If password doesn't meet requirements.

    Example:
        >>> validate_strong_password("SecurePass123!")
        'SecurePass123!'
        >>> validate_strong_password("weak")
        ValueError: Password must be at least 8 characters
    """
    if len(v) < 8:
        raise ValueError("Password must be at least 8 characters")
    if not any(c.isupper() for c in v):
        raise ValueError("Password must contain uppercase letter")
    if not any(c.islower() for c in v):
        raise ValueError("Password must contain lowercase letter")
    if not any(c.isdigit() for c in v):
        raise ValueError("Password must contain digit")
    if not any(c in '!@#$%^&*(),.?":{}|<>' for c in v):
        raise ValueError("Password must contain special character")
    return v


def validate_token_format(v: str) -> str:
    """Validate token format (hex string).

    Used for email verification and password reset tokens.

    Args:
        v: Token string to validate.

    Returns:
        Token unchanged (validation only).

    Raises:
        ValueError: If token format is invalid.

    Example:
        >>> validate_token_format("abc123def456")
        'abc123def456'
        >>> validate_token_format("not-hex!")
        ValueError: Token must be hexadecimal
    """
    if not v:
        raise ValueError("Token cannot be empty")
    if not re.match(r"^[a-fA-F0-9]+$", v):
        raise ValueError("Token must be hexadecimal")
    return v


def validate_refresh_token_format(v: str) -> str:
    """Validate refresh token format (urlsafe base64).

    Used for opaque refresh tokens.

    Args:
        v: Refresh token to validate.

    Returns:
        Token unchanged (validation only).

    Raises:
        ValueError: If token format is invalid.

    Example:
        >>> validate_refresh_token_format("dGhpcyBpcyBh")
        'dGhpcyBpcyBh'
        >>> validate_refresh_token_format("")
        ValueError: Refresh token cannot be empty
    """
    if not v:
        raise ValueError("Refresh token cannot be empty")
    # urlsafe base64 uses A-Z, a-z, 0-9, -, _
    if not re.match(r"^[A-Za-z0-9_-]+$", v):
        raise ValueError("Invalid refresh token format")
    return v
