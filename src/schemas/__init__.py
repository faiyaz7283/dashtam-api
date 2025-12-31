"""Request/response schemas for API endpoints.

All Pydantic models for HTTP request validation and response serialization.
Schemas are kept separate from domain entities (HTTP-layer concerns only).

Usage:
    from src.schemas import UserCreateRequest, SessionCreateResponse
"""

from src.schemas.auth_schemas import (
    # User (registration)
    UserCreateRequest,
    UserCreateResponse,
    # Session (login/logout)
    SessionCreateRequest,
    SessionCreateResponse,
    SessionDeleteRequest,
    # Token (refresh)
    TokenCreateRequest,
    TokenCreateResponse,
    # Email verification
    EmailVerificationCreateRequest,
    EmailVerificationCreateResponse,
    # Password reset
    PasswordResetTokenCreateRequest,
    PasswordResetTokenCreateResponse,
    PasswordResetCreateRequest,
    PasswordResetCreateResponse,
)
from src.schemas.session_schemas import (
    SessionListResponse,
    SessionResponse,
    SessionRevokeAllRequest,
    SessionRevokeAllResponse,
    SessionRevokeRequest,
)

__all__ = [
    # User
    "UserCreateRequest",
    "UserCreateResponse",
    # Session (login/logout)
    "SessionCreateRequest",
    "SessionCreateResponse",
    "SessionDeleteRequest",
    # Session management
    "SessionListResponse",
    "SessionResponse",
    "SessionRevokeAllRequest",
    "SessionRevokeAllResponse",
    "SessionRevokeRequest",
    # Token
    "TokenCreateRequest",
    "TokenCreateResponse",
    # Email verification
    "EmailVerificationCreateRequest",
    "EmailVerificationCreateResponse",
    # Password reset
    "PasswordResetTokenCreateRequest",
    "PasswordResetTokenCreateResponse",
    "PasswordResetCreateRequest",
    "PasswordResetCreateResponse",
]
