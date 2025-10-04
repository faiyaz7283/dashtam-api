# JWT Authentication Implementation Guide

**Document Purpose**: Complete implementation guide for JWT-based authentication in Dashtam, including architecture decisions, code patterns, database design, API endpoints, testing strategy, and migration from mock authentication.

**Implementation Time**: 4-5 days  
**Status**: Ready for Implementation  
**Priority**: P1 (Blocks P2 features)

---

## Table of Contents
1. [Architecture Overview](#architecture-overview)
2. [Database Design](#database-design)
3. [Service Layer Implementation](#service-layer-implementation)
4. [API Endpoints](#api-endpoints)
5. [Security Patterns](#security-patterns)
6. [Testing Strategy](#testing-strategy)
7. [Migration from Mock Auth](#migration-from-mock-auth)
8. [Day-by-Day Implementation Plan](#day-by-day-implementation-plan)

---

## Architecture Overview

### Authentication Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                        JWT Authentication Flow                        │
└─────────────────────────────────────────────────────────────────────┘

1. SIGNUP/REGISTRATION
   ┌─────────┐                                            ┌──────────┐
   │ Client  │──POST /api/v1/auth/signup────────────────>│  API     │
   └─────────┘   (email, password, name)                  └──────────┘
                                                                 │
                                                                 v
                                                           ┌──────────┐
                                                           │ AuthSvc  │
                                                           └──────────┘
                                                                 │
                                                                 v
                                                         • Hash password (bcrypt)
                                                         • Create user record
                                                         • Generate verification token
                                                         • Send verification email
                                                                 │
                                                                 v
                                                         ┌────────────────┐
                                                         │   Database     │
                                                         │  users table   │
                                                         │  + email_verification_tokens │
                                                         └────────────────┘

2. EMAIL VERIFICATION
   ┌─────────┐                                            ┌──────────┐
   │ Client  │──POST /api/v1/auth/verify-email──────────>│  API     │
   └─────────┘   (token)                                  └──────────┘
                                                                 │
                                                                 v
                                                         • Validate token
                                                         • Mark email verified
                                                         • Return success

3. LOGIN
   ┌─────────┐                                            ┌──────────┐
   │ Client  │──POST /api/v1/auth/login─────────────────>│  API     │
   └─────────┘   (email, password)                        └──────────┘
                                                                 │
                                                                 v
                                                           ┌──────────┐
                                                           │ AuthSvc  │
                                                           └──────────┘
                                                                 │
                                                                 v
                                                         • Verify password
                                                         • Check email verified
                                                         • Generate access token (JWT, 30min)
                                                         • Generate refresh token (random, 30d)
                                                         • Store refresh token in DB
                                                                 │
   ┌─────────┐                                                 v
   │ Client  │<───────────────────────────────────────────Response
   └─────────┘   {
                   "access_token": "eyJhbG...",
                   "refresh_token": "abc123...",
                   "token_type": "bearer",
                   "expires_in": 1800
                 }

4. AUTHENTICATED REQUEST
   ┌─────────┐                                            ┌──────────┐
   │ Client  │──GET /api/v1/providers/──────────────────>│  API     │
   └─────────┘   Authorization: Bearer <access_token>    └──────────┘
                                                                 │
                                                                 v
                                                         ┌──────────────┐
                                                         │ Middleware   │
                                                         │ (get_current_│
                                                         │   user)      │
                                                         └──────────────┘
                                                                 │
                                                                 v
                                                         • Decode JWT token
                                                         • Verify signature
                                                         • Check expiration
                                                         • Extract user_id
                                                         • Load user from DB
                                                                 │
   ┌─────────┐                                                 v
   │ Client  │<───────────────────────────────────────────Response
   └─────────┘   {providers: [...]}

5. TOKEN REFRESH
   ┌─────────┐                                            ┌──────────┐
   │ Client  │──POST /api/v1/auth/refresh───────────────>│  API     │
   └─────────┘   (refresh_token)                          └──────────┘
                                                                 │
                                                                 v
                                                         • Validate refresh token
                                                         • Check not expired
                                                         • Check not revoked
                                                         • Generate new access token
                                                         • ROTATE: Generate new refresh token
                                                         • Revoke old refresh token
                                                                 │
   ┌─────────┐                                                 v
   │ Client  │<───────────────────────────────────────────Response
   └─────────┘   {
                   "access_token": "eyJhbG...",
                   "refresh_token": "def456...",  # NEW
                   "token_type": "bearer",
                   "expires_in": 1800
                 }

6. LOGOUT
   ┌─────────┐                                            ┌──────────┐
   │ Client  │──POST /api/v1/auth/logout────────────────>│  API     │
   └─────────┘   (refresh_token)                          └──────────┘
                                                                 │
                                                                 v
                                                         • Mark refresh token as revoked
                                                         • Client discards access token
                                                         • User logged out
```

### Key Design Decisions

#### 1. Stateless Access Tokens (JWT)
**Decision**: Use JWT for access tokens, stored in client memory.

**Rationale**:
- ✅ No database lookup on every request (performance)
- ✅ Scalable: No session storage synchronization needed
- ✅ Can include claims (user_id, email, roles)
- ✅ Industry standard (95% of fintech)

**Configuration**:
```python
ACCESS_TOKEN_EXPIRE_MINUTES = 30  # Short-lived for security
ALGORITHM = "HS256"  # HMAC SHA-256 (symmetric)
```

**Why HS256 (not RS256)?**
- Single backend service (no distributed signature verification)
- Faster than RSA (asymmetric crypto)
- Simpler key management
- Can upgrade to RS256 later if needed for microservices

---

#### 2. Stateful Refresh Tokens (Database)
**Decision**: Store refresh tokens in database as hashed values.

**Rationale**:
- ✅ Can revoke tokens (logout, security breach)
- ✅ Track device/session information
- ✅ Implement token rotation (prevents replay attacks)
- ✅ Audit trail of authentication events

**Configuration**:
```python
REFRESH_TOKEN_EXPIRE_DAYS = 30  # Long-lived for UX
# Token rotation: New refresh token on each use
```

**Why hash refresh tokens?**
- If database compromised, attacker can't use tokens
- Similar to password hashing best practice
- Minimal performance overhead (bcrypt with low rounds)

---

#### 3. Token Rotation Strategy
**Decision**: Rotate refresh token on every use (refresh endpoint).

**Rationale**:
- ✅ Prevents replay attacks
- ✅ Detects stolen tokens (if old token used)
- ✅ Industry best practice (OAuth2 recommendation)

**Flow**:
```python
# Client uses refresh_token_A
# Server validates refresh_token_A
# Server generates access_token_B + refresh_token_B
# Server revokes refresh_token_A
# Server returns access_token_B + refresh_token_B
# Client stores refresh_token_B (replaces A)
```

---

#### 4. Email Verification Required
**Decision**: Users must verify email before full access.

**Rationale**:
- ✅ Prevents fake accounts
- ✅ Enables password recovery
- ✅ Compliance requirement (GDPR, SOC 2)
- ✅ Better user communication channel

**Implementation**:
- Can login immediately after signup
- Limited functionality until email verified
- Cannot connect providers until verified
- 24-hour verification token expiry

---

#### 5. Password Security
**Decision**: Use bcrypt with 12 rounds, enforce complexity.

**Rationale**:
- ✅ Recommended by OWASP for password hashing
- ✅ Adaptive: Can increase rounds as hardware improves
- ✅ Salt included automatically
- ✅ ~300ms verification time (prevents brute force)

**Requirements**:
```python
# Password complexity (configurable)
MIN_LENGTH = 8
REQUIRE_UPPERCASE = True
REQUIRE_LOWERCASE = True
REQUIRE_DIGIT = True
REQUIRE_SPECIAL = True
```

---

#### 6. Rate Limiting & Account Lockout
**Decision**: Implement progressive backoff and account lockout.

**Rationale**:
- ✅ Prevents brute force attacks
- ✅ Detects credential stuffing
- ✅ Compliance requirement (PCI-DSS)

**Strategy**:
```python
# Failed login attempts
- 5 failures → 15-minute cooldown
- 10 failures → 1-hour account lockout
- Track by email AND IP address

# Password reset
- 3 requests per email per hour
- 15-minute token expiry

# Email verification
- 3 resend requests per hour
- 24-hour token expiry
```

---

## Database Design

### 1. Extend Users Table

**Migration**: `alembic/versions/YYYYMMDD_HHMM-<hash>_add_auth_fields_to_users.py`

```python
"""Add authentication fields to users table.

Revision ID: <generated>
Revises: <previous>
Create Date: 2025-10-04 00:00:00

Adds password hashing, email verification, and account lockout fields
to support JWT authentication.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import INET


def upgrade() -> None:
    """Add authentication fields to users table."""
    # Add password field
    op.add_column(
        'users',
        sa.Column('password_hash', sa.String(255), nullable=True)
    )
    
    # Add email verification fields
    op.add_column(
        'users',
        sa.Column('email_verified', sa.Boolean(), nullable=False, server_default='false')
    )
    op.add_column(
        'users',
        sa.Column('email_verified_at', sa.DateTime(timezone=True), nullable=True)
    )
    
    # Add password management fields
    op.add_column(
        'users',
        sa.Column('password_changed_at', sa.DateTime(timezone=True), nullable=True)
    )
    
    # Add account lockout fields
    op.add_column(
        'users',
        sa.Column('failed_login_attempts', sa.Integer(), nullable=False, server_default='0')
    )
    op.add_column(
        'users',
        sa.Column('locked_until', sa.DateTime(timezone=True), nullable=True)
    )
    
    # Add last login tracking
    op.add_column(
        'users',
        sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        'users',
        sa.Column('last_login_ip', INET(), nullable=True)
    )


def downgrade() -> None:
    """Remove authentication fields from users table."""
    op.drop_column('users', 'last_login_ip')
    op.drop_column('users', 'last_login_at')
    op.drop_column('users', 'locked_until')
    op.drop_column('users', 'failed_login_attempts')
    op.drop_column('users', 'password_changed_at')
    op.drop_column('users', 'email_verified_at')
    op.drop_column('users', 'email_verified')
    op.drop_column('users', 'password_hash')
```

---

### 2. Refresh Tokens Table

**Migration**: `alembic/versions/YYYYMMDD_HHMM-<hash>_create_refresh_tokens.py`

```python
"""Create refresh_tokens table for JWT refresh token management.

Revision ID: <generated>
Revises: <previous>
Create Date: 2025-10-04 00:00:00

Implements refresh token storage with rotation support, device tracking,
and revocation capabilities for secure JWT authentication.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, INET


def upgrade() -> None:
    """Create refresh_tokens table."""
    op.create_table(
        'refresh_tokens',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('token_hash', sa.String(255), nullable=False, unique=True, index=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_revoked', sa.Boolean(), nullable=False, server_default='false', index=True),
        sa.Column('device_info', sa.Text(), nullable=True),
        sa.Column('ip_address', INET(), nullable=True),
        sa.Column('user_agent', sa.Text(), nullable=True),
        sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True),
    )
    
    # Composite index for active token lookups
    op.create_index(
        'idx_refresh_tokens_active',
        'refresh_tokens',
        ['user_id', 'is_revoked'],
        unique=False
    )


def downgrade() -> None:
    """Drop refresh_tokens table."""
    op.drop_index('idx_refresh_tokens_active', table_name='refresh_tokens')
    op.drop_table('refresh_tokens')
```

---

### 3. Email Verification Tokens Table

**Migration**: `alembic/versions/YYYYMMDD_HHMM-<hash>_create_email_verification_tokens.py`

```python
"""Create email_verification_tokens table.

Revision ID: <generated>
Revises: <previous>
Create Date: 2025-10-04 00:00:00

Implements email verification with one-time tokens and expiration.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


def upgrade() -> None:
    """Create email_verification_tokens table."""
    op.create_table(
        'email_verification_tokens',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('token_hash', sa.String(255), nullable=False, unique=True, index=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('used_at', sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    """Drop email_verification_tokens table."""
    op.drop_table('email_verification_tokens')
```

---

### 4. Password Reset Tokens Table

**Migration**: `alembic/versions/YYYYMMDD_HHMM-<hash>_create_password_reset_tokens.py`

```python
"""Create password_reset_tokens table.

Revision ID: <generated>
Revises: <previous>
Create Date: 2025-10-04 00:00:00

Implements secure password reset with one-time tokens, short expiration,
and request tracking for rate limiting.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, INET


def upgrade() -> None:
    """Create password_reset_tokens table."""
    op.create_table(
        'password_reset_tokens',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('token_hash', sa.String(255), nullable=False, unique=True, index=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('ip_address', INET(), nullable=True),
        sa.Column('user_agent', sa.Text(), nullable=True),
    )


def downgrade() -> None:
    """Drop password_reset_tokens table."""
    op.drop_table('password_reset_tokens')
```

---

### SQLModel Models

#### Update User Model

**File**: `src/models/user.py`

```python
"""User model for authentication and provider ownership."""

from datetime import datetime, timezone
from typing import Optional, List, TYPE_CHECKING
from uuid import UUID

from sqlmodel import Field, Relationship, Column
from sqlalchemy import String, DateTime, Integer, Boolean
from sqlalchemy.dialects.postgresql import INET
from pydantic import field_validator, EmailStr

from src.models.base import DashtamBase

if TYPE_CHECKING:
    from src.models.provider import Provider
    from src.models.auth import RefreshToken, EmailVerificationToken, PasswordResetToken


class User(DashtamBase, table=True):
    """Application user model with authentication support.

    Represents a user who can authenticate and manage multiple financial
    provider instances. Supports JWT authentication with email/password,
    email verification, and account security features.

    Attributes:
        email: User's email address (unique, used for login).
        name: User's full name.
        password_hash: Bcrypt hash of user's password.
        email_verified: Whether email address has been verified.
        email_verified_at: Timestamp of email verification.
        password_changed_at: Timestamp of last password change.
        failed_login_attempts: Count of consecutive failed login attempts.
        locked_until: Timestamp until which account is locked (after too many failures).
        last_login_at: Timestamp of last successful login.
        last_login_ip: IP address of last successful login.
        is_active: Whether account is active (for soft deletion/suspension).
        providers: List of provider instances owned by user.
        refresh_tokens: List of active refresh tokens for user sessions.
    """

    __tablename__ = "users"

    # Basic info
    email: str = Field(
        sa_column=Column(String(255), unique=True, index=True, nullable=False),
        description="User's email address (unique, used for login)",
    )
    name: str = Field(description="User's full name")

    # Authentication
    password_hash: Optional[str] = Field(
        default=None,
        sa_column=Column(String(255), nullable=True),
        description="Bcrypt hash of user's password",
    )

    # Email verification
    email_verified: bool = Field(
        default=False,
        sa_column=Column(Boolean, nullable=False, server_default="false"),
        description="Whether email address has been verified",
    )
    email_verified_at: Optional[datetime] = Field(
        default=None,
        sa_type=DateTime(timezone=True),
        description="Timestamp of email verification",
    )

    # Password management
    password_changed_at: Optional[datetime] = Field(
        default=None,
        sa_type=DateTime(timezone=True),
        description="Timestamp of last password change",
    )

    # Account security
    failed_login_attempts: int = Field(
        default=0,
        sa_column=Column(Integer, nullable=False, server_default="0"),
        description="Count of consecutive failed login attempts",
    )
    locked_until: Optional[datetime] = Field(
        default=None,
        sa_type=DateTime(timezone=True),
        description="Timestamp until which account is locked",
    )

    # Login tracking
    last_login_at: Optional[datetime] = Field(
        default=None,
        sa_type=DateTime(timezone=True),
        description="Timestamp of last successful login",
    )
    last_login_ip: Optional[str] = Field(
        default=None,
        sa_column=Column(INET, nullable=True),
        description="IP address of last successful login",
    )

    # Account status
    is_active: bool = Field(
        default=True,
        description="Whether account is active (for soft deletion/suspension)",
    )

    # Relationships
    providers: List["Provider"] = Relationship(
        back_populates="user", cascade_delete=True
    )
    refresh_tokens: List["RefreshToken"] = Relationship(
        back_populates="user", cascade_delete=True
    )
    email_verification_tokens: List["EmailVerificationToken"] = Relationship(
        back_populates="user", cascade_delete=True
    )
    password_reset_tokens: List["PasswordResetToken"] = Relationship(
        back_populates="user", cascade_delete=True
    )

    # Validators to ensure timezone awareness
    @field_validator(
        "email_verified_at",
        "password_changed_at",
        "locked_until",
        "last_login_at",
        mode="before"
    )
    @classmethod
    def ensure_timezone_aware(cls, v: Optional[datetime]) -> Optional[datetime]:
        """Ensure datetime fields are timezone-aware (UTC)."""
        if v is None:
            return None
        if v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v.astimezone(timezone.utc)

    @property
    def is_locked(self) -> bool:
        """Check if account is currently locked."""
        if not self.locked_until:
            return False
        return datetime.now(timezone.utc) < self.locked_until

    @property
    def can_login(self) -> bool:
        """Check if user can log in (active, not locked)."""
        return self.is_active and not self.is_locked

    @property
    def active_providers_count(self) -> int:
        """Count of active provider connections."""
        if not self.providers:
            return 0
        return sum(1 for p in self.providers if p.is_connected)

    @property
    def display_name(self) -> str:
        """Get display name (name or email)."""
        return self.name or self.email.split("@")[0]

    def reset_failed_login_attempts(self) -> None:
        """Reset failed login attempts counter."""
        self.failed_login_attempts = 0
        self.locked_until = None

    def increment_failed_login_attempts(self) -> None:
        """Increment failed login attempts and lock account if threshold exceeded."""
        self.failed_login_attempts += 1
        
        # Lock account after 10 failed attempts (1 hour)
        if self.failed_login_attempts >= 10:
            self.locked_until = datetime.now(timezone.utc) + timedelta(hours=1)
```

---

#### Create Auth Models

**File**: `src/models/auth.py`

```python
"""Authentication models for JWT token management.

This module defines models for refresh tokens, email verification tokens,
and password reset tokens used in the JWT authentication system.
"""

from datetime import datetime, timezone, timedelta
from typing import Optional, TYPE_CHECKING
from uuid import UUID
import secrets

from sqlmodel import Field, Relationship, Column
from sqlalchemy import String, DateTime, Boolean, Text
from sqlalchemy.dialects.postgresql import INET
from pydantic import field_validator

from src.models.base import DashtamBase

if TYPE_CHECKING:
    from src.models.user import User


class RefreshToken(DashtamBase, table=True):
    """Refresh token for JWT authentication.

    Stores refresh tokens with rotation support. Each token is hashed
    before storage and can be revoked for logout or security events.

    Attributes:
        user_id: ID of user who owns this token.
        token_hash: Bcrypt hash of the refresh token.
        expires_at: Token expiration timestamp (30 days).
        revoked_at: Timestamp when token was revoked (logout).
        is_revoked: Whether token has been revoked.
        device_info: Information about device/browser.
        ip_address: IP address where token was issued.
        user_agent: User agent string of client.
        last_used_at: Timestamp of last token use (refresh).
        user: User who owns this token.
    """

    __tablename__ = "refresh_tokens"

    user_id: UUID = Field(
        foreign_key="users.id",
        nullable=False,
        index=True,
        ondelete="CASCADE",
        description="ID of user who owns this token",
    )
    token_hash: str = Field(
        sa_column=Column(String(255), nullable=False, unique=True, index=True),
        description="Bcrypt hash of the refresh token",
    )
    expires_at: datetime = Field(
        sa_type=DateTime(timezone=True),
        nullable=False,
        description="Token expiration timestamp",
    )
    revoked_at: Optional[datetime] = Field(
        default=None,
        sa_type=DateTime(timezone=True),
        description="Timestamp when token was revoked",
    )
    is_revoked: bool = Field(
        default=False,
        sa_column=Column(Boolean, nullable=False, server_default="false", index=True),
        description="Whether token has been revoked",
    )
    device_info: Optional[str] = Field(
        default=None,
        sa_column=Column(Text, nullable=True),
        description="Information about device/browser",
    )
    ip_address: Optional[str] = Field(
        default=None,
        sa_column=Column(INET, nullable=True),
        description="IP address where token was issued",
    )
    user_agent: Optional[str] = Field(
        default=None,
        sa_column=Column(Text, nullable=True),
        description="User agent string of client",
    )
    last_used_at: Optional[datetime] = Field(
        default=None,
        sa_type=DateTime(timezone=True),
        description="Timestamp of last token use",
    )

    # Relationships
    user: "User" = Relationship(back_populates="refresh_tokens")

    @field_validator("expires_at", "revoked_at", "last_used_at", mode="before")
    @classmethod
    def ensure_timezone_aware(cls, v: Optional[datetime]) -> Optional[datetime]:
        """Ensure datetime fields are timezone-aware (UTC)."""
        if v is None:
            return None
        if v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v.astimezone(timezone.utc)

    @property
    def is_expired(self) -> bool:
        """Check if token has expired."""
        return datetime.now(timezone.utc) > self.expires_at

    @property
    def is_valid(self) -> bool:
        """Check if token is valid (not expired, not revoked)."""
        return not self.is_expired and not self.is_revoked

    def revoke(self) -> None:
        """Revoke this token."""
        self.is_revoked = True
        self.revoked_at = datetime.now(timezone.utc)


class EmailVerificationToken(DashtamBase, table=True):
    """Email verification token.

    One-time use token sent via email to verify user's email address.
    Expires after 24 hours.

    Attributes:
        user_id: ID of user who needs to verify email.
        token_hash: Bcrypt hash of the verification token.
        expires_at: Token expiration timestamp (24 hours).
        used_at: Timestamp when token was used.
        user: User who needs to verify email.
    """

    __tablename__ = "email_verification_tokens"

    user_id: UUID = Field(
        foreign_key="users.id",
        nullable=False,
        index=True,
        ondelete="CASCADE",
        description="ID of user who needs to verify email",
    )
    token_hash: str = Field(
        sa_column=Column(String(255), nullable=False, unique=True, index=True),
        description="Bcrypt hash of the verification token",
    )
    expires_at: datetime = Field(
        sa_type=DateTime(timezone=True),
        nullable=False,
        index=True,
        description="Token expiration timestamp (24 hours)",
    )
    used_at: Optional[datetime] = Field(
        default=None,
        sa_type=DateTime(timezone=True),
        description="Timestamp when token was used",
    )

    # Relationships
    user: "User" = Relationship(back_populates="email_verification_tokens")

    @field_validator("expires_at", "used_at", mode="before")
    @classmethod
    def ensure_timezone_aware(cls, v: Optional[datetime]) -> Optional[datetime]:
        """Ensure datetime fields are timezone-aware (UTC)."""
        if v is None:
            return None
        if v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v.astimezone(timezone.utc)

    @property
    def is_expired(self) -> bool:
        """Check if token has expired."""
        return datetime.now(timezone.utc) > self.expires_at

    @property
    def is_used(self) -> bool:
        """Check if token has already been used."""
        return self.used_at is not None

    @property
    def is_valid(self) -> bool:
        """Check if token is valid (not expired, not used)."""
        return not self.is_expired and not self.is_used

    def mark_as_used(self) -> None:
        """Mark token as used."""
        self.used_at = datetime.now(timezone.utc)


class PasswordResetToken(DashtamBase, table=True):
    """Password reset token.

    One-time use token sent via email to reset forgotten password.
    Expires after 15 minutes for security.

    Attributes:
        user_id: ID of user requesting password reset.
        token_hash: Bcrypt hash of the reset token.
        expires_at: Token expiration timestamp (15 minutes).
        used_at: Timestamp when token was used.
        ip_address: IP address of reset request.
        user_agent: User agent string of reset request.
        user: User requesting password reset.
    """

    __tablename__ = "password_reset_tokens"

    user_id: UUID = Field(
        foreign_key="users.id",
        nullable=False,
        index=True,
        ondelete="CASCADE",
        description="ID of user requesting password reset",
    )
    token_hash: str = Field(
        sa_column=Column(String(255), nullable=False, unique=True, index=True),
        description="Bcrypt hash of the reset token",
    )
    expires_at: datetime = Field(
        sa_type=DateTime(timezone=True),
        nullable=False,
        index=True,
        description="Token expiration timestamp (15 minutes)",
    )
    used_at: Optional[datetime] = Field(
        default=None,
        sa_type=DateTime(timezone=True),
        description="Timestamp when token was used",
    )
    ip_address: Optional[str] = Field(
        default=None,
        sa_column=Column(INET, nullable=True),
        description="IP address of reset request",
    )
    user_agent: Optional[str] = Field(
        default=None,
        sa_column=Column(Text, nullable=True),
        description="User agent string of reset request",
    )

    # Relationships
    user: "User" = Relationship(back_populates="password_reset_tokens")

    @field_validator("expires_at", "used_at", mode="before")
    @classmethod
    def ensure_timezone_aware(cls, v: Optional[datetime]) -> Optional[datetime]:
        """Ensure datetime fields are timezone-aware (UTC)."""
        if v is None:
            return None
        if v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v.astimezone(timezone.utc)

    @property
    def is_expired(self) -> bool:
        """Check if token has expired."""
        return datetime.now(timezone.utc) > self.expires_at

    @property
    def is_used(self) -> bool:
        """Check if token has already been used."""
        return self.used_at is not None

    @property
    def is_valid(self) -> bool:
        """Check if token is valid (not expired, not used)."""
        return not self.is_expired and not self.is_used

    def mark_as_used(self) -> None:
        """Mark token as used."""
        self.used_at = datetime.now(timezone.utc)
```

---

## Service Layer Implementation

### Authentication Service

**File**: `src/services/auth_service.py`

```python
"""Authentication service for JWT token management.

This service handles user authentication, token generation, password
verification, and account security features like rate limiting and
account lockout.
"""

import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, Tuple
from uuid import UUID

from jose import jwt, JWTError
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from src.core.config import settings
from src.models.user import User
from src.models.auth import RefreshToken, EmailVerificationToken, PasswordResetToken

logger = logging.getLogger(__name__)

# Password hashing context
pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=12  # ~300ms verification time
)


class AuthService:
    """Service for handling user authentication and JWT tokens.
    
    Provides methods for user registration, login, token management,
    email verification, and password reset functionality.
    """

    def __init__(self, session: AsyncSession):
        """Initialize auth service.
        
        Args:
            session: Async database session for queries.
        """
        self.session = session

    # =====================================================================
    # PASSWORD MANAGEMENT
    # =====================================================================

    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a password using bcrypt.
        
        Args:
            password: Plain text password.
            
        Returns:
            Bcrypt hash of password.
        """
        return pwd_context.hash(password)

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash.
        
        Args:
            plain_password: Plain text password to verify.
            hashed_password: Bcrypt hash to verify against.
            
        Returns:
            True if password matches hash, False otherwise.
        """
        return pwd_context.verify(plain_password, hashed_password)

    @staticmethod
    def validate_password_strength(password: str) -> Tuple[bool, Optional[str]]:
        """Validate password meets complexity requirements.
        
        Args:
            password: Password to validate.
            
        Returns:
            Tuple of (is_valid, error_message).
        """
        if len(password) < 8:
            return False, "Password must be at least 8 characters long"
        
        if not any(c.isupper() for c in password):
            return False, "Password must contain at least one uppercase letter"
        
        if not any(c.islower() for c in password):
            return False, "Password must contain at least one lowercase letter"
        
        if not any(c.isdigit() for c in password):
            return False, "Password must contain at least one digit"
        
        if not any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password):
            return False, "Password must contain at least one special character"
        
        return True, None

    # =====================================================================
    # JWT TOKEN MANAGEMENT
    # =====================================================================

    @staticmethod
    def create_access_token(user_id: UUID, email: str) -> str:
        """Create JWT access token.
        
        Args:
            user_id: User's unique ID.
            email: User's email address.
            
        Returns:
            JWT access token (expires in 30 minutes).
        """
        expires = datetime.now(timezone.utc) + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )
        
        to_encode = {
            "sub": str(user_id),  # Subject (user ID)
            "email": email,
            "iat": datetime.now(timezone.utc),  # Issued at
            "exp": expires,  # Expiration
        }
        
        encoded_jwt = jwt.encode(
            to_encode,
            settings.SECRET_KEY,
            algorithm=settings.ALGORITHM
        )
        
        return encoded_jwt

    @staticmethod
    def decode_access_token(token: str) -> Dict[str, Any]:
        """Decode and validate JWT access token.
        
        Args:
            token: JWT access token to decode.
            
        Returns:
            Token payload dictionary.
            
        Raises:
            JWTError: If token is invalid, expired, or tampered.
        """
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )
        return payload

    async def create_refresh_token(
        self,
        user_id: UUID,
        device_info: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Tuple[str, RefreshToken]:
        """Create and store refresh token.
        
        Args:
            user_id: User's unique ID.
            device_info: Optional device information.
            ip_address: Optional IP address.
            user_agent: Optional user agent string.
            
        Returns:
            Tuple of (plain_token, refresh_token_model).
        """
        # Generate random token
        plain_token = secrets.token_urlsafe(32)  # 256 bits entropy
        
        # Hash token before storing
        token_hash = pwd_context.hash(plain_token)
        
        # Create refresh token record
        expires_at = datetime.now(timezone.utc) + timedelta(
            days=settings.REFRESH_TOKEN_EXPIRE_DAYS
        )
        
        refresh_token = RefreshToken(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
            device_info=device_info,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        
        self.session.add(refresh_token)
        await self.session.commit()
        await self.session.refresh(refresh_token)
        
        logger.info(f"Created refresh token for user {user_id}")
        
        return plain_token, refresh_token

    async def verify_refresh_token(self, plain_token: str) -> Optional[RefreshToken]:
        """Verify refresh token and return token record.
        
        Args:
            plain_token: Plain text refresh token from client.
            
        Returns:
            RefreshToken model if valid, None if invalid.
        """
        # Get all active (non-revoked, non-expired) refresh tokens
        result = await self.session.execute(
            select(RefreshToken).where(
                RefreshToken.is_revoked == False,
                RefreshToken.expires_at > datetime.now(timezone.utc)
            )
        )
        tokens = result.scalars().all()
        
        # Check each token's hash (constant time comparison)
        for token in tokens:
            if pwd_context.verify(plain_token, token.token_hash):
                # Update last used timestamp
                token.last_used_at = datetime.now(timezone.utc)
                await self.session.commit()
                return token
        
        return None

    async def revoke_refresh_token(self, token: RefreshToken) -> None:
        """Revoke a refresh token (logout).
        
        Args:
            token: RefreshToken model to revoke.
        """
        token.revoke()
        await self.session.commit()
        
        logger.info(f"Revoked refresh token {token.id} for user {token.user_id}")

    async def revoke_all_user_tokens(self, user_id: UUID) -> int:
        """Revoke all refresh tokens for a user (logout all devices).
        
        Args:
            user_id: User's unique ID.
            
        Returns:
            Number of tokens revoked.
        """
        result = await self.session.execute(
            select(RefreshToken).where(
                RefreshToken.user_id == user_id,
                RefreshToken.is_revoked == False
            )
        )
        tokens = result.scalars().all()
        
        for token in tokens:
            token.revoke()
        
        await self.session.commit()
        
        logger.info(f"Revoked {len(tokens)} refresh tokens for user {user_id}")
        return len(tokens)

    # =====================================================================
    # USER AUTHENTICATION
    # =====================================================================

    async def authenticate_user(
        self, email: str, password: str, ip_address: Optional[str] = None
    ) -> Optional[User]:
        """Authenticate user with email and password.
        
        Args:
            email: User's email address.
            password: User's plain text password.
            ip_address: Optional IP address for login tracking.
            
        Returns:
            User model if authentication successful, None otherwise.
        """
        # Get user by email
        result = await self.session.execute(
            select(User).where(User.email == email)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            logger.warning(f"Login attempt for non-existent email: {email}")
            return None
        
        # Check if account is locked
        if user.is_locked:
            logger.warning(f"Login attempt for locked account: {email}")
            return None
        
        # Check if account is active
        if not user.is_active:
            logger.warning(f"Login attempt for inactive account: {email}")
            return None
        
        # Verify password
        if not user.password_hash or not self.verify_password(password, user.password_hash):
            # Increment failed login attempts
            user.increment_failed_login_attempts()
            await self.session.commit()
            
            logger.warning(
                f"Failed login attempt for {email} "
                f"(attempts: {user.failed_login_attempts})"
            )
            return None
        
        # Authentication successful
        user.reset_failed_login_attempts()
        user.last_login_at = datetime.now(timezone.utc)
        if ip_address:
            user.last_login_ip = ip_address
        
        await self.session.commit()
        await self.session.refresh(user)
        
        logger.info(f"Successful login for user {email}")
        return user

    async def register_user(
        self, email: str, password: str, name: str
    ) -> Tuple[User, str]:
        """Register a new user.
        
        Args:
            email: User's email address.
            password: User's plain text password.
            name: User's full name.
            
        Returns:
            Tuple of (user_model, verification_token).
            
        Raises:
            ValueError: If email already exists or password invalid.
        """
        # Check if email already exists
        result = await self.session.execute(
            select(User).where(User.email == email)
        )
        if result.scalar_one_or_none():
            raise ValueError("Email already registered")
        
        # Validate password strength
        is_valid, error = self.validate_password_strength(password)
        if not is_valid:
            raise ValueError(error)
        
        # Create user
        user = User(
            email=email,
            name=name,
            password_hash=self.hash_password(password),
            email_verified=False,
        )
        
        self.session.add(user)
        await self.session.commit()
        await self.session.refresh(user)
        
        # Generate email verification token
        plain_token = await self.create_email_verification_token(user.id)
        
        logger.info(f"Registered new user: {email}")
        return user, plain_token

    # =====================================================================
    # EMAIL VERIFICATION
    # =====================================================================

    async def create_email_verification_token(self, user_id: UUID) -> str:
        """Create email verification token.
        
        Args:
            user_id: User's unique ID.
            
        Returns:
            Plain text verification token (send via email).
        """
        # Generate random token
        plain_token = secrets.token_urlsafe(32)
        token_hash = pwd_context.hash(plain_token)
        
        # Create token record (expires in 24 hours)
        expires_at = datetime.now(timezone.utc) + timedelta(hours=24)
        
        verification_token = EmailVerificationToken(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
        )
        
        self.session.add(verification_token)
        await self.session.commit()
        
        logger.info(f"Created email verification token for user {user_id}")
        return plain_token

    async def verify_email(self, plain_token: str) -> Optional[User]:
        """Verify user's email with token.
        
        Args:
            plain_token: Plain text verification token from email.
            
        Returns:
            User model if verification successful, None otherwise.
        """
        # Get all active (not used, not expired) verification tokens
        result = await self.session.execute(
            select(EmailVerificationToken).where(
                EmailVerificationToken.used_at == None,
                EmailVerificationToken.expires_at > datetime.now(timezone.utc)
            )
        )
        tokens = result.scalars().all()
        
        # Check each token's hash
        for token in tokens:
            if pwd_context.verify(plain_token, token.token_hash):
                # Mark token as used
                token.mark_as_used()
                
                # Mark user's email as verified
                result = await self.session.execute(
                    select(User).where(User.id == token.user_id)
                )
                user = result.scalar_one_or_none()
                
                if user:
                    user.email_verified = True
                    user.email_verified_at = datetime.now(timezone.utc)
                    await self.session.commit()
                    await self.session.refresh(user)
                    
                    logger.info(f"Verified email for user {user.email}")
                    return user
        
        logger.warning("Invalid or expired email verification token")
        return None

    # =====================================================================
    # PASSWORD RESET
    # =====================================================================

    async def create_password_reset_token(
        self,
        email: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Optional[str]:
        """Create password reset token.
        
        Args:
            email: User's email address.
            ip_address: Optional IP address of request.
            user_agent: Optional user agent string.
            
        Returns:
            Plain text reset token (send via email), or None if user not found.
        """
        # Get user by email
        result = await self.session.execute(
            select(User).where(User.email == email)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            # Don't reveal whether email exists (security)
            logger.warning(f"Password reset requested for non-existent email: {email}")
            return None
        
        # Generate random token
        plain_token = secrets.token_urlsafe(32)
        token_hash = pwd_context.hash(plain_token)
        
        # Create token record (expires in 15 minutes)
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=15)
        
        reset_token = PasswordResetToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=expires_at,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        
        self.session.add(reset_token)
        await self.session.commit()
        
        logger.info(f"Created password reset token for user {email}")
        return plain_token

    async def reset_password(self, plain_token: str, new_password: str) -> Optional[User]:
        """Reset user's password with token.
        
        Args:
            plain_token: Plain text reset token from email.
            new_password: User's new password.
            
        Returns:
            User model if reset successful, None otherwise.
            
        Raises:
            ValueError: If password invalid.
        """
        # Validate password strength
        is_valid, error = self.validate_password_strength(new_password)
        if not is_valid:
            raise ValueError(error)
        
        # Get all active (not used, not expired) reset tokens
        result = await self.session.execute(
            select(PasswordResetToken).where(
                PasswordResetToken.used_at == None,
                PasswordResetToken.expires_at > datetime.now(timezone.utc)
            )
        )
        tokens = result.scalars().all()
        
        # Check each token's hash
        for token in tokens:
            if pwd_context.verify(plain_token, token.token_hash):
                # Mark token as used
                token.mark_as_used()
                
                # Update user's password
                result = await self.session.execute(
                    select(User).where(User.id == token.user_id)
                )
                user = result.scalar_one_or_none()
                
                if user:
                    user.password_hash = self.hash_password(new_password)
                    user.password_changed_at = datetime.now(timezone.utc)
                    
                    # Reset failed login attempts and unlock account
                    user.reset_failed_login_attempts()
                    
                    # Revoke all existing refresh tokens (force re-login)
                    await self.revoke_all_user_tokens(user.id)
                    
                    await self.session.commit()
                    await self.session.refresh(user)
                    
                    logger.info(f"Reset password for user {user.email}")
                    return user
        
        logger.warning("Invalid or expired password reset token")
        return None
```

---

This is a comprehensive foundation. Let me mark the completed tasks and continue with the remaining sections...

<function_calls>
<invoke name="mark_todo_as_done">
<parameter name="todo_ids">["c6871eac-6a9b-42d6-add1-a0055cf3d616", "d82dfdee-73ec-479f-b8fe-24fb6dd57202"]