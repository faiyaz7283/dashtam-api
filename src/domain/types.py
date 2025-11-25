"""Annotated types with centralized validation (DRY principle).

Define validation once, use everywhere.
All custom types use Pydantic's Annotated with Field constraints and AfterValidator.

Usage:
    from src.domain.types import Email, Password, VerificationToken

    class RegisterUser:
        email: Email  # Validation included!
        password: Password  # Validation included!

Reference:
    - clean-slate-reference.md §1.5 (Annotated Types)
    - development-checklist.md §9 (Modern Python Patterns)
    - development-checklist.md §10b (DRY Principle)
"""

from typing import Annotated

from pydantic import AfterValidator, Field

from src.domain.validators import (
    validate_email,
    validate_refresh_token_format,
    validate_strong_password,
    validate_token_format,
)

# ============================================================================
# Authentication Types
# ============================================================================

Email = Annotated[
    str,
    Field(
        min_length=5,
        max_length=255,
        description="Email address",
        examples=["user@example.com"],
    ),
    AfterValidator(validate_email),
]
"""Email address with validation and normalization.

Validation:
- Format: standard email pattern (user@domain.tld)
- Normalized to lowercase

Examples:
    >>> from pydantic import BaseModel
    >>> class UserCreate(BaseModel):
    ...     email: Email
    >>> user = UserCreate(email="User@Example.COM")
    >>> user.email
    'user@example.com'
"""

Password = Annotated[
    str,
    Field(
        min_length=8,
        max_length=128,
        description="Password with strength requirements",
        examples=["SecurePass123!"],
    ),
    AfterValidator(validate_strong_password),
]
"""Password with strength validation.

Requirements:
- At least 8 characters
- At least one uppercase letter
- At least one lowercase letter
- At least one digit
- At least one special character (!@#$%^&*(),.?":{}|<>)

Examples:
    >>> from pydantic import BaseModel
    >>> class LoginRequest(BaseModel):
    ...     password: Password
    >>> req = LoginRequest(password="SecurePass123!")
    >>> # Valid password
"""

VerificationToken = Annotated[
    str,
    Field(
        min_length=16,
        max_length=128,
        description="Email verification or password reset token (hex)",
        pattern=r"^[a-fA-F0-9]+$",
        examples=["abc123def456789"],
    ),
    AfterValidator(validate_token_format),
]
"""Email verification or password reset token.

Format:
- Hexadecimal string (32-byte hex = 64 characters typically)
- Used for email verification and password reset flows

Examples:
    >>> from pydantic import BaseModel
    >>> class VerifyEmailRequest(BaseModel):
    ...     token: VerificationToken
    >>> req = VerifyEmailRequest(token="abc123def456")
    >>> # Valid hex token
"""

RefreshToken = Annotated[
    str,
    Field(
        min_length=16,
        max_length=256,
        description="Opaque refresh token (urlsafe base64)",
        pattern=r"^[A-Za-z0-9_-]+$",
        examples=["dGhpcyBpcyBhIHJhbmRvbSB0b2tlbg"],
    ),
    AfterValidator(validate_refresh_token_format),
]
"""Opaque refresh token for JWT refresh flow.

Format:
- urlsafe base64 encoded (32-byte random)
- Used for token rotation and session management

Examples:
    >>> from pydantic import BaseModel
    >>> class RefreshRequest(BaseModel):
    ...     refresh_token: RefreshToken
    >>> req = RefreshRequest(refresh_token="dGhpcyBpcyBh")
    >>> # Valid refresh token
"""
