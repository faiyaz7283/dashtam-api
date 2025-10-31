"""Authentication and user management Pydantic schemas.

This module contains request/response schemas for JWT authentication endpoints,
including registration, login, token management, password reset, and user profile.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator


class RegisterRequest(BaseModel):
    """Request to register a new user account.

    Attributes:
        email: User's email address (must be valid and unique).
        password: User's password (must meet strength requirements).
        name: User's full name.
    """

    email: EmailStr = Field(..., description="User's email address")
    password: str = Field(
        ...,
        description="User's password (min 8 chars, 1 uppercase, 1 lowercase, 1 digit, 1 special)",
        min_length=8,
        max_length=128,
    )
    name: str = Field(..., description="User's full name", min_length=1, max_length=100)

    model_config = {
        "json_schema_extra": {
            "example": {
                "email": "john.doe@example.com",
                "password": "SecurePass123!",
                "name": "John Doe",
            }
        }
    }


class LoginRequest(BaseModel):
    """Request to log in to an existing account.

    Attributes:
        email: User's email address.
        password: User's password.
    """

    email: EmailStr = Field(..., description="User's email address")
    password: str = Field(..., description="User's password", min_length=1)

    model_config = {
        "json_schema_extra": {
            "example": {"email": "john.doe@example.com", "password": "SecurePass123!"}
        }
    }


class TokenResponse(BaseModel):
    """Response containing JWT tokens.

    Attributes:
        access_token: Short-lived JWT access token (30 min).
        refresh_token: Long-lived JWT refresh token (30 days).
        token_type: Token type (always "bearer").
        expires_in: Access token expiration time in seconds.
    """

    access_token: str = Field(..., description="JWT access token")
    refresh_token: str = Field(..., description="JWT refresh token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(
        default=1800, description="Access token expiration in seconds"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "token_type": "bearer",
                "expires_in": 1800,
            }
        }
    }


class UserResponse(BaseModel):
    """Response containing user profile information.

    Attributes:
        id: User's unique identifier.
        email: User's email address.
        name: User's full name.
        email_verified: Whether email has been verified.
        is_active: Whether account is active.
        created_at: Account creation timestamp.
        last_login_at: Last login timestamp.
    """

    id: UUID = Field(..., description="User's unique identifier")
    email: str = Field(..., description="User's email address")
    name: Optional[str] = Field(default=None, description="User's full name")
    email_verified: bool = Field(default=False, description="Email verification status")
    is_active: bool = Field(default=True, description="Account active status")
    created_at: datetime = Field(..., description="Account creation timestamp")
    last_login_at: Optional[datetime] = Field(
        default=None, description="Last login timestamp"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "email": "john.doe@example.com",
                "name": "John Doe",
                "email_verified": True,
                "is_active": True,
                "created_at": "2025-10-04T20:00:00Z",
                "last_login_at": "2025-10-04T20:30:00Z",
            }
        }
    }


class LoginResponse(BaseModel):
    """Response after successful login.

    Combines token information with user profile.

    Attributes:
        access_token: JWT access token.
        refresh_token: JWT refresh token.
        token_type: Token type (always "bearer").
        expires_in: Access token expiration in seconds.
        user: User profile information.
    """

    access_token: str = Field(..., description="JWT access token")
    refresh_token: str = Field(..., description="JWT refresh token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(default=1800, description="Expiration in seconds")
    user: UserResponse = Field(..., description="User profile information")

    model_config = {
        "json_schema_extra": {
            "example": {
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "token_type": "bearer",
                "expires_in": 1800,
                "user": {
                    "id": "123e4567-e89b-12d3-a456-426614174000",
                    "email": "john.doe@example.com",
                    "name": "John Doe",
                    "email_verified": True,
                    "is_active": True,
                    "created_at": "2025-10-04T20:00:00Z",
                    "last_login_at": "2025-10-04T20:30:00Z",
                },
            }
        }
    }


class RefreshTokenRequest(BaseModel):
    """Request to refresh access token.

    Attributes:
        refresh_token: Valid refresh token from previous login.
    """

    refresh_token: str = Field(..., description="JWT refresh token", min_length=1)

    model_config = {
        "json_schema_extra": {
            "example": {"refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."}
        }
    }


class EmailVerificationRequest(BaseModel):
    """Request to verify email address.

    Attributes:
        token: Email verification token from email.
    """

    token: str = Field(
        ..., description="Email verification token from email", min_length=1
    )

    model_config = {"json_schema_extra": {"example": {"token": "abc123def456ghi789"}}}


class ChangePasswordRequest(BaseModel):
    """Request to change password while authenticated.

    User must provide current password for verification before
    setting new password. This triggers automatic token rotation
    to log out all other devices for security.

    Attributes:
        current_password: Current password for verification.
        new_password: New password (must meet strength requirements).
    """

    current_password: str = Field(
        ..., description="Current password for verification", min_length=1
    )
    new_password: str = Field(
        ...,
        description="New password (min 8 chars, 1 uppercase, 1 lowercase, 1 digit, 1 special)",
        min_length=8,
        max_length=128,
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "current_password": "OldSecurePass123!",
                "new_password": "NewSecurePass456!",
            }
        }
    }


class PasswordResetRequest(BaseModel):
    """Request to initiate password reset flow.

    Attributes:
        email: User's email address to send reset link.
    """

    email: EmailStr = Field(
        ..., description="Email address to send password reset link"
    )

    model_config = {"json_schema_extra": {"example": {"email": "john.doe@example.com"}}}


class PasswordResetConfirm(BaseModel):
    """Request to confirm password reset with new password.

    Attributes:
        token: Password reset token from email.
        new_password: New password (must meet strength requirements).
    """

    token: str = Field(..., description="Password reset token from email", min_length=1)
    new_password: str = Field(
        ...,
        description="New password (min 8 chars, 1 uppercase, 1 lowercase, 1 digit, 1 special)",
        min_length=8,
        max_length=128,
    )

    model_config = {
        "json_schema_extra": {
            "example": {"token": "xyz789abc123def456", "new_password": "NewSecure123!"}
        }
    }


class UpdateUserRequest(BaseModel):
    """Request to update user profile.

    All fields are optional - only provided fields will be updated.

    Attributes:
        name: Updated full name.
        email: Updated email address (requires re-verification).
    """

    name: Optional[str] = Field(
        default=None, description="Updated full name", min_length=1, max_length=100
    )
    email: Optional[EmailStr] = Field(
        default=None, description="Updated email (requires re-verification)"
    )

    @field_validator("name")
    @classmethod
    def validate_name_not_empty(cls, v: Optional[str]) -> Optional[str]:
        """Ensure name is not just whitespace if provided."""
        if v is not None and not v.strip():
            raise ValueError("Name cannot be empty or just whitespace")
        return v.strip() if v else v

    model_config = {
        "json_schema_extra": {
            "example": {"name": "Jane Doe", "email": "jane.doe@example.com"}
        }
    }


class CreatePasswordResetRequest(BaseModel):
    """Request to create a password reset (resource-oriented).

    Attributes:
        email: Email address to send reset link to.
    """

    email: EmailStr = Field(
        ..., description="Email address to send password reset link"
    )

    model_config = {"json_schema_extra": {"example": {"email": "john.doe@example.com"}}}


class VerifyResetTokenResponse(BaseModel):
    """Response for password reset token verification.

    Attributes:
        valid: Whether the token is valid.
        email: Email address associated with token (only if valid).
        expires_at: Token expiration timestamp (only if valid).
    """

    valid: bool = Field(..., description="Whether the token is valid")
    email: Optional[str] = Field(
        default=None, description="Email address associated with token"
    )
    expires_at: Optional[str] = Field(
        default=None, description="Token expiration timestamp (ISO 8601)"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "valid": True,
                "email": "john.doe@example.com",
                "expires_at": "2025-10-05T12:00:00Z",
            }
        }
    }


class CompletePasswordResetRequest(BaseModel):
    """Request to complete password reset (resource-oriented).

    Attributes:
        new_password: New password meeting strength requirements.
    """

    new_password: str = Field(
        ...,
        description="New password (min 8 chars, 1 uppercase, 1 lowercase, 1 digit, 1 special)",
        min_length=8,
        max_length=128,
    )

    model_config = {"json_schema_extra": {"example": {"new_password": "NewSecure123!"}}}


class MessageResponse(BaseModel):
    """Generic message response for auth operations.

    Used for operations like registration, logout, password reset request, etc.

    Attributes:
        message: Human-readable success or status message.
    """

    message: str = Field(..., description="Success or status message", min_length=1)

    model_config = {
        "json_schema_extra": {
            "example": {"message": "Registration successful. Please check your email."}
        }
    }
