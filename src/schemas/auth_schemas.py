"""Authentication request/response schemas.

Pydantic models for API request validation and response serialization.
Kept separate from domain entities - these are HTTP-layer concerns.

RESTful Endpoints (100% resource-based):
    POST   /api/v1/users                    - Create user (registration)
    POST   /api/v1/sessions                 - Create session (login)
    DELETE /api/v1/sessions/current         - Delete session (logout)
    POST   /api/v1/tokens                   - Create tokens (refresh)
    POST   /api/v1/email-verifications      - Create verification (verify email)
    POST   /api/v1/password-reset-tokens    - Create reset token (request)
    POST   /api/v1/password-resets          - Create reset (execute)
"""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


# =============================================================================
# Registration
# =============================================================================


class UserCreateRequest(BaseModel):
    """Request schema for user creation (registration).

    POST /api/v1/users
    Returns: 201 Created
    """

    email: EmailStr = Field(
        ...,
        description="User's email address",
        examples=["user@example.com"],
    )
    password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="Password (8-128 chars, mixed case, number, special char)",
        examples=["SecurePass123!"],
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "email": "user@example.com",
                "password": "SecurePass123!",
            }
        }
    )


class UserCreateResponse(BaseModel):
    """Response schema for user creation (201 Created).

    Returns created user resource.
    User must verify email before creating a session (login).
    """

    id: UUID = Field(..., description="Created user's ID")
    email: str = Field(..., description="User's email address")
    message: str = Field(
        default="Registration successful. Please check your email to verify your account.",
        description="Success message",
    )


# =============================================================================
# Login
# =============================================================================


class SessionCreateRequest(BaseModel):
    """Request schema for session creation (login).

    POST /api/v1/sessions
    Returns: 201 Created
    """

    email: EmailStr = Field(
        ...,
        description="User's email address",
        examples=["user@example.com"],
    )
    password: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="User's password",
        examples=["SecurePass123!"],
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "email": "user@example.com",
                "password": "SecurePass123!",
            }
        }
    )


class SessionCreateResponse(BaseModel):
    """Response schema for session creation (201 Created).

    Returns session tokens (JWT access + opaque refresh).
    """

    access_token: str = Field(..., description="JWT access token (15 min expiry)")
    refresh_token: str = Field(..., description="Opaque refresh token (30 day expiry)")
    token_type: str = Field(
        default="bearer", description="Token type for Authorization header"
    )
    expires_in: int = Field(
        default=900, description="Access token expiration in seconds"
    )


# =============================================================================
# Logout
# =============================================================================


class SessionDeleteRequest(BaseModel):
    """Request schema for session deletion (logout).

    DELETE /api/v1/sessions/current
    Returns: 204 No Content

    Note: Requires Authorization header with JWT.
    """

    refresh_token: str = Field(
        ...,
        min_length=1,
        description="Refresh token to revoke",
    )


# Note: DELETE returns 204 No Content (no response body)


# =============================================================================
# Token Refresh
# =============================================================================


class TokenCreateRequest(BaseModel):
    """Request schema for token creation (refresh).

    POST /api/v1/tokens
    Returns: 201 Created
    """

    refresh_token: str = Field(
        ...,
        min_length=1,
        description="Current refresh token",
    )


class TokenCreateResponse(BaseModel):
    """Response schema for token creation (201 Created).

    Returns new tokens (rotation: old refresh token invalidated).
    """

    access_token: str = Field(..., description="New JWT access token")
    refresh_token: str = Field(..., description="New refresh token (rotated)")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(
        default=900, description="Access token expiration in seconds"
    )


# =============================================================================
# Email Verification
# =============================================================================


class EmailVerificationCreateRequest(BaseModel):
    """Request schema for email verification creation.

    POST /api/v1/email-verifications
    Returns: 201 Created
    """

    token: str = Field(
        ...,
        min_length=64,
        max_length=64,
        description="64-character hex verification token from email",
    )


class EmailVerificationCreateResponse(BaseModel):
    """Response schema for email verification (201 Created)."""

    message: str = Field(
        default="Email verified successfully. You can now create a session.",
        description="Success message",
    )


# =============================================================================
# Password Reset Request
# =============================================================================


class PasswordResetTokenCreateRequest(BaseModel):
    """Request schema for password reset token creation.

    POST /api/v1/password-reset-tokens
    Returns: 201 Created (always, to prevent user enumeration)
    """

    email: EmailStr = Field(
        ...,
        description="Email address for password reset",
        examples=["user@example.com"],
    )


class PasswordResetTokenCreateResponse(BaseModel):
    """Response schema for password reset token (201 Created).

    Always returns success to prevent user enumeration.
    """

    message: str = Field(
        default="If an account with that email exists, a password reset link has been sent.",
        description="Success message (always same to prevent enumeration)",
    )


# =============================================================================
# Password Reset Confirm
# =============================================================================


class PasswordResetCreateRequest(BaseModel):
    """Request schema for password reset execution.

    POST /api/v1/password-resets
    Returns: 201 Created
    """

    token: str = Field(
        ...,
        min_length=64,
        max_length=64,
        description="64-character hex reset token from email",
    )
    new_password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="New password (8-128 chars, mixed case, number, special char)",
        examples=["NewSecurePass456!"],
    )


class PasswordResetCreateResponse(BaseModel):
    """Response schema for password reset (201 Created)."""

    message: str = Field(
        default="Password has been reset successfully. Please create a new session.",
        description="Success message",
    )
