# Token Rotation Implementation Guide

Comprehensive implementation guide for Approach 3 (Hybrid Global + Per-User Token Versioning) with SOLID principles and enterprise-grade security.

---

## Overview

This guide provides step-by-step instructions for implementing token breach rotation using the hybrid approach (Approach 3). The implementation adds global and per-user token versioning to the existing JWT authentication system, enabling both targeted and system-wide token rotation for security incidents.

### What You'll Learn

- How to extend database models with token versioning fields (SOLID: Open-Closed Principle)
- How to create Alembic migrations for schema changes
- How to implement token rotation services following SOLID principles
- How to add API endpoints for token rotation management
- How to test token rotation scenarios comprehensively
- How to maintain backward compatibility during rollout

### When to Use This Guide

Use this guide when:

- Implementing token breach rotation for JWT authentication system
- Adding emergency global token rotation capability
- Enhancing security posture with token versioning
- Responding to security audit requirements (SOC 2, PCI-DSS)

### Architecture Decision Record (ADR)

**Decision**: Approach 3 (Hybrid Global + Per-User Versioning)

**Rationale**: See [Token Breach Rotation Research](../../research/token-breach-rotation-research.md) for comprehensive analysis.

**Key Benefits**:

- Handles both targeted (per-user) and system-wide (global) breaches
- Industry standard (Auth0, Okta pattern)
- Audit trail for compliance
- Grace period support for distributed systems

## Prerequisites

Before starting, ensure you have:

- [ ] Development environment running (`make dev-up`)
- [ ] Understanding of existing JWT authentication system
- [ ] Familiarity with Alembic migrations
- [ ] Read the [Token Breach Rotation Research](../../research/token-breach-rotation-research.md)

**Required Tools:**

- Docker Desktop with Docker Compose v2
- Python 3.13+ with UV package manager
- PostgreSQL 17.6+ (containerized)
- Make for workflow commands

**Required Knowledge:**

- SQLModel and SQLAlchemy ORM patterns
- Async Python (async/await, AsyncSession)
- FastAPI routing and dependency injection
- SOLID principles (especially SRP, OCP, DIP)
- Database migrations with Alembic

## Step-by-Step Instructions

### Phase 1: Database Schema Changes

Add token versioning fields to database models and create migration.

#### Step 1.1: Create Security Config Model

Create new model for global security configuration.

**File**: `src/models/security_config.py`

```python

"""Global security configuration model.

This module defines the SecurityConfig singleton model which stores
system-wide security parameters, including global token version for
emergency rotation scenarios.
"""

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlmodel import Field, Column
from sqlalchemy import String, Integer, DateTime, Text
from pydantic import field_validator

from src.models.base import DashtamBase


class SecurityConfig(DashtamBase, table=True):
    """Global security configuration singleton.

    Stores system-wide security settings including the global minimum
    token version for emergency rotation scenarios (e.g., encryption
    key compromise, database breach).

    This table should contain exactly one row at all times.

    Attributes:
        global_min_token_version: Minimum token version accepted globally.
        updated_at: When global version was last updated.
        updated_by: Who initiated the global rotation (admin identifier).
        reason: Why global rotation was performed (audit trail).
    """

    __tablename__ = "security_config"

    global_min_token_version: int = Field(
        default=1,
        sa_column=Column(Integer, nullable=False),
        description="Minimum token version accepted globally",
    )
    updated_at: datetime = Field(
        sa_type=DateTime(timezone=True),
        nullable=False,
        description="When global version was last updated",
    )
    updated_by: Optional[str] = Field(
        default=None,
        sa_column=Column(String(255), nullable=True),
        description="Who initiated the global rotation",
    )
    reason: Optional[str] = Field(
        default=None,
        sa_column=Column(Text, nullable=True),
        description="Why global rotation was performed",
    )

    @field_validator("updated_at", mode="before")
    @classmethod
    def ensure_timezone_aware(cls, v: Optional[datetime]) -> Optional[datetime]:
        """Ensure datetime fields are timezone-aware (UTC)."""
        if v is None:
            return None
        if v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v.astimezone(timezone.utc)
```

**What This Does:**

- Creates singleton table for global security configuration
- Stores audit trail (who, when, why) for compliance
- Follows existing model patterns (DashtamBase, timezone-aware datetimes)

**SOLID Principles Applied:**

- **Single Responsibility**: Model only represents security configuration data
- **Open-Closed**: Can add new security fields without modifying existing code

#### Step 1.2: Update User Model

Add per-user token versioning field.

**File**: `src/models/user.py`

Add field to `User` class:

```python
# After line 103 (after is_active field)

# Token rotation (per-user version)
min_token_version: int = Field(
    default=1,
    sa_column=Column(Integer, nullable=False, server_default="1"),
    description="Minimum token version for this user (rotation)",
)
```

**What This Does:**

- Adds per-user token versioning capability
- Defaults to version 1 for new users
- Server default ensures database consistency

#### Step 1.3: Update RefreshToken Model

Add both version fields to track token lifecycle.

**File**: `src/models/auth.py`

Add fields to `RefreshToken` class:

```python
# After line 115 (after is_trusted_device field)

# Token versioning (hybrid approach)
token_version: int = Field(
    default=1,
    sa_column=Column(Integer, nullable=False, server_default="1", index=True),
    description="User's token version at issuance time",
)
global_version_at_issuance: int = Field(
    default=1,
    sa_column=Column(Integer, nullable=False, server_default="1", index=True),
    description="Global token version at issuance time",
)
```

**What This Does:**

- Captures both user and global versions when token is created
- Indexed for fast validation queries
- Immutable after creation (represents state at issuance)

**SOLID Principles Applied:**

- **Open-Closed**: Extended model without modifying existing fields
- **Interface Segregation**: Token versioning is separate concern

#### Step 1.4: Create Alembic Migration

Generate and review migration for schema changes.

```bash
# Generate migration
make migrate-create MESSAGE="add_token_versioning_hybrid_approach"

# Review generated migration
cat src/alembic/versions/[timestamp]_add_token_versioning_hybrid_approach.py
```

**Expected Migration Content:**

```python
"""add_token_versioning_hybrid_approach

Revision ID: [generated_id]
Revises: [previous_revision]
Create Date: [timestamp]
"""
from alembic import op
import sqlalchemy as sa


def upgrade():
    # Create security_config table
    op.create_table(
        'security_config',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('global_min_token_version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_by', sa.String(length=255), nullable=True),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at_model', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Add min_token_version to users
    op.add_column('users', sa.Column('min_token_version', sa.Integer(), nullable=False, server_default='1'))
    op.create_index(op.f('ix_users_min_token_version'), 'users', ['id', 'min_token_version'], unique=False)
    
    # Add version fields to refresh_tokens
    op.add_column('refresh_tokens', sa.Column('token_version', sa.Integer(), nullable=False, server_default='1'))
    op.add_column('refresh_tokens', sa.Column('global_version_at_issuance', sa.Integer(), nullable=False, server_default='1'))
    op.create_index(op.f('ix_refresh_tokens_version'), 'refresh_tokens', ['user_id', 'token_version'], unique=False)
    op.create_index(op.f('ix_refresh_tokens_global_version'), 'refresh_tokens', ['global_version_at_issuance'], unique=False)
    
    # Insert initial security_config row (singleton)
    op.execute("""
        INSERT INTO security_config (id, global_min_token_version, updated_at, created_at, updated_at_model)
        VALUES (gen_random_uuid(), 1, NOW(), NOW(), NOW())
    """)


def downgrade():
    # Remove indexes
    op.drop_index(op.f('ix_refresh_tokens_global_version'), table_name='refresh_tokens')
    op.drop_index(op.f('ix_refresh_tokens_version'), table_name='refresh_tokens')
    op.drop_index(op.f('ix_users_min_token_version'), table_name='users')
    
    # Remove columns
    op.drop_column('refresh_tokens', 'global_version_at_issuance')
    op.drop_column('refresh_tokens', 'token_version')
    op.drop_column('users', 'min_token_version')
    
    # Drop security_config table
    op.drop_table('security_config')
```

#### Step 1.5: Run Migration

Apply migration to development database.

```bash
# Apply migration
make migrate-up

# Verify migration
make migrate-history
```

**Expected Output:**

```text
INFO  [alembic.runtime.migration] Running upgrade ... -> [new_revision], add_token_versioning_hybrid_approach
```

**Verification:**

```bash
# Check table structure
docker compose -f compose/docker-compose.dev.yml exec postgres psql -U dashtam -d dashtam -c "\d security_config"
docker compose -f compose/docker-compose.dev.yml exec postgres psql -U dashtam -d dashtam -c "\d users" | grep min_token_version
docker compose -f compose/docker-compose.dev.yml exec postgres psql -U dashtam -d dashtam -c "\d refresh_tokens" | grep version
```

### Phase 2: Token Rotation Service Layer

Implement service layer for token rotation following SOLID principles.

#### Step 2.1: Create Token Rotation Service (Core Logic)

**SOLID Principle**: Single Responsibility - Service handles only token rotation logic.

**File**: `src/services/token_rotation_service.py`

```python
"""Token rotation service for breach response.

This service handles token versioning and rotation for both per-user
and global security events. Implements hybrid token rotation strategy
(Approach 3) with audit trail and grace period support.

Architecture:
- Single Responsibility: Only handles token rotation logic
- Dependency Injection: Accepts AsyncSession, not coupled to database
- Strategy Pattern: Supports both user and global rotation strategies
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Literal
from uuid import UUID
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select, func
from sqlalchemy import update

from src.models.user import User
from src.models.auth import RefreshToken
from src.models.security_config import SecurityConfig

logger = logging.getLogger(__name__)


@dataclass
class TokenRotationResult:
    """Result of token rotation operation.
    
    Attributes:
        rotation_type: Type of rotation ('USER' or 'GLOBAL')
        user_id: User ID (for USER rotation, None for GLOBAL)
        old_version: Previous version number
        new_version: New version number
        tokens_revoked: Number of tokens revoked
        users_affected: Number of users affected (GLOBAL only)
        reason: Why rotation was performed
        initiated_by: Who initiated rotation (GLOBAL only)
        grace_period_minutes: Grace period before full revocation
    """
    rotation_type: Literal["USER", "GLOBAL"]
    old_version: int
    new_version: int
    tokens_revoked: int
    reason: str
    user_id: Optional[UUID] = None
    users_affected: Optional[int] = None
    initiated_by: Optional[str] = None
    grace_period_minutes: Optional[int] = None


class TokenRotationService:
    """Service for token versioning and rotation.
    
    Implements hybrid token rotation strategy with both per-user and
    global rotation capabilities. Follows SOLID principles:
    
    - Single Responsibility: Only token rotation logic
    - Open-Closed: Extendable rotation strategies
    - Liskov Substitution: Works with any AsyncSession implementation
    - Interface Segregation: Minimal public API
    - Dependency Inversion: Depends on abstractions (AsyncSession)
    
    Example:
        >>> service = TokenRotationService(session)
        >>> result = await service.rotate_user_tokens(
        ...     user_id=uuid,
        ...     reason="Password changed"
        ... )
        >>> print(f"Revoked {result.tokens_revoked} tokens")
    """
    
    def __init__(self, session: AsyncSession):
        """Initialize service with database session.
        
        Args:
            session: Async database session for queries
        """
        self.session = session
    
    async def get_security_config(self) -> SecurityConfig:
        """Get global security configuration singleton.
        
        Returns:
            SecurityConfig singleton instance
            
        Raises:
            RuntimeError: If security_config table is empty (should never happen)
        """
        result = await self.session.execute(select(SecurityConfig))
        config = result.scalar_one_or_none()
        
        if not config:
            # This should never happen (migration inserts row)
            raise RuntimeError("security_config table is empty (database corruption?)")
        
        return config
    
    async def rotate_user_tokens(
        self,
        user_id: UUID,
        reason: str
    ) -> TokenRotationResult:
        """Rotate all tokens for a specific user (targeted rotation).
        
        Use cases:
        - Password change
        - User requests logout from all devices
        - Suspicious activity detected for user
        - User-specific security event
        
        Algorithm:
        1. Get max token version currently in use by user
        2. Set user's min_token_version to max + 1
        3. Mark all tokens below new minimum as revoked
        
        Args:
            user_id: UUID of user whose tokens to rotate
            reason: Human-readable reason for rotation (audit trail)
            
        Returns:
            TokenRotationResult with rotation details
            
        Example:
            >>> result = await service.rotate_user_tokens(
            ...     user_id=uuid.UUID("..."),
            ...     reason="Password changed by user"
            ... )
            >>> print(f"Version {result.old_version} → {result.new_version}")
        """
        # Get user's current minimum version
        result = await self.session.execute(
            select(User.min_token_version).where(User.id == user_id)
        )
        old_version = result.scalar_one()
        
        # Get max token version currently in use (0 if no tokens)
        result = await self.session.execute(
            select(func.max(RefreshToken.token_version))
            .where(RefreshToken.user_id == user_id)
        )
        max_version = result.scalar() or 0
        
        # New minimum is max + 1 (invalidates all existing tokens)
        new_min_version = max(old_version, max_version) + 1
        
        # Update user's minimum version
        await self.session.execute(
            update(User)
            .where(User.id == user_id)
            .values(min_token_version=new_min_version)
        )
        
        # Revoke all tokens below new minimum
        result = await self.session.execute(
            update(RefreshToken)
            .where(
                RefreshToken.user_id == user_id,
                RefreshToken.token_version < new_min_version,
                ~RefreshToken.is_revoked
            )
            .values(
                is_revoked=True,
                revoked_at=datetime.now(timezone.utc)
            )
            .returning(RefreshToken.id)
        )
        revoked_tokens = result.scalars().all()
        
        await self.session.commit()
        
        logger.info(
            f"USER token rotation: user_id={user_id}, "
            f"version {old_version} → {new_min_version}, "
            f"revoked {len(revoked_tokens)} tokens, "
            f"reason='{reason}'"
        )
        
        return TokenRotationResult(
            rotation_type="USER",
            user_id=user_id,
            old_version=old_version,
            new_version=new_min_version,
            tokens_revoked=len(revoked_tokens),
            reason=reason
        )
    
    async def rotate_all_tokens_global(
        self,
        reason: str,
        initiated_by: str,
        grace_period_minutes: int = 15
    ) -> TokenRotationResult:
        """Rotate ALL tokens system-wide (nuclear option for major breaches).
        
        Use cases:
        - Encryption key compromise
        - Database breach requiring mass logout
        - Critical security vulnerability discovered
        - Regulatory compliance requirement
        
        Algorithm:
        1. Increment global_min_token_version by 1
        2. Count affected tokens and users (for reporting)
        3. Mark all old tokens as revoked (with grace period)
        4. Log critical security event with full audit trail
        
        Args:
            reason: Why global rotation was initiated (audit trail)
            initiated_by: Who initiated (e.g., "ADMIN:john@example.com")
            grace_period_minutes: Minutes before full revocation (default 15)
            
        Returns:
            TokenRotationResult with global rotation details
            
        Example:
            >>> result = await service.rotate_all_tokens_global(
            ...     reason="Encryption key rotated",
            ...     initiated_by="ADMIN:security@example.com",
            ...     grace_period_minutes=15
            ... )
            >>> print(f"Affected {result.users_affected} users")
        
        Warning:
            This is a nuclear option. All users will be logged out.
            Use only for genuine security emergencies.
        """
        # Get current global configuration
        config = await self.get_security_config()
        old_version = config.global_min_token_version
        new_version = old_version + 1
        
        # Update global minimum version
        await self.session.execute(
            update(SecurityConfig)
            .values(
                global_min_token_version=new_version,
                updated_at=datetime.now(timezone.utc),
                updated_by=initiated_by,
                reason=reason
            )
        )
        
        # Count tokens that will be invalidated
        result = await self.session.execute(
            select(func.count(RefreshToken.id))
            .where(
                RefreshToken.global_version_at_issuance < new_version,
                ~RefreshToken.is_revoked
            )
        )
        affected_tokens = result.scalar()
        
        # Count affected users
        result = await self.session.execute(
            select(func.count(func.distinct(RefreshToken.user_id)))
            .where(
                RefreshToken.global_version_at_issuance < new_version,
                ~RefreshToken.is_revoked
            )
        )
        affected_users = result.scalar()
        
        # Mark all old tokens as revoked (with grace period)
        revocation_time = datetime.now(timezone.utc) + timedelta(minutes=grace_period_minutes)
        await self.session.execute(
            update(RefreshToken)
            .where(
                RefreshToken.global_version_at_issuance < new_version,
                ~RefreshToken.is_revoked
            )
            .values(
                is_revoked=True,
                revoked_at=revocation_time  # Delayed revocation
            )
        )
        
        await self.session.commit()
        
        # Log critical security event
        logger.critical(
            f"GLOBAL TOKEN ROTATION: version {old_version} → {new_version}. "
            f"Reason: {reason}. Initiated by: {initiated_by}. "
            f"Affected: {affected_users} users, {affected_tokens} tokens. "
            f"Grace period: {grace_period_minutes} minutes."
        )
        
        return TokenRotationResult(
            rotation_type="GLOBAL",
            old_version=old_version,
            new_version=new_version,
            tokens_revoked=affected_tokens,
            users_affected=affected_users,
            reason=reason,
            initiated_by=initiated_by,
            grace_period_minutes=grace_period_minutes
        )
```

**What This Does:**

- Implements both user and global rotation strategies
- Includes comprehensive audit logging
- Supports grace period for distributed systems
- Returns structured results for API responses

**SOLID Principles Applied:**

- **Single Responsibility**: Only token rotation logic (no auth, no token generation)
- **Open-Closed**: Can add new rotation strategies without modifying existing code
- **Liskov Substitution**: Works with any AsyncSession implementation
- **Interface Segregation**: Clean public API (2 methods)
- **Dependency Inversion**: Depends on AsyncSession abstraction, not concrete database

#### Step 2.2: Update AuthService for Token Validation

Modify AuthService to validate tokens against version numbers.

**File**: `src/services/auth_service.py`

Add validation method:

```python
# Add at end of AuthService class

async def _validate_token_versions(
    self,
    token: RefreshToken,
    user: User
) -> tuple[bool, Optional[str]]:
    """Validate token against both global and per-user versions.
    
    Two-level validation:
    1. Global version check (for system-wide breaches)
    2. Per-user version check (for user-specific events)
    
    Both checks must pass for token to be valid.
    
    Args:
        token: RefreshToken to validate
        user: User who owns the token
        
    Returns:
        Tuple of (is_valid, failure_reason)
        
    Example:
        >>> is_valid, reason = await service._validate_token_versions(token, user)
        >>> if not is_valid:
        ...     raise HTTPException(status_code=401, detail=reason)
    """
    # Get current global version
    from src.models.security_config import SecurityConfig
    result = await self.session.execute(select(SecurityConfig))
    config = result.scalar_one()
    
    # Check global version (rare, extreme breach)
    if token.global_version_at_issuance < config.global_min_token_version:
        logger.security(
            f"Token failed global version check: "
            f"token_global_v{token.global_version_at_issuance} < "
            f"required_v{config.global_min_token_version}, "
            f"token_id={token.id}"
        )
        return False, "GLOBAL_TOKEN_VERSION_TOO_OLD"
    
    # Check per-user version (common, targeted rotation)
    if token.token_version < user.min_token_version:
        logger.info(
            f"Token failed user version check: "
            f"token_v{token.token_version} < "
            f"min_v{user.min_token_version}, "
            f"user_id={user.id}"
        )
        return False, "USER_TOKEN_VERSION_TOO_OLD"
    
    return True, None
```

Update `refresh_access_token` method to include version validation:

```python
# Find refresh_access_token method, add version check after existing validations

# ... existing code ...

# NEW: Validate token versions (after existing validations)
is_valid, failure_reason = await self._validate_token_versions(token, user)
if not is_valid:
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=f"Token has been rotated: {failure_reason}"
    )

# ... rest of existing code ...
```

Update `_create_refresh_token` method to capture versions:

```python
# Find _create_refresh_token method, update token creation

# Get current versions
from src.models.security_config import SecurityConfig
result = await self.session.execute(select(SecurityConfig))
config = result.scalar_one()

# Create token with both version numbers
token = RefreshToken(
    user_id=user_id,
    token_hash=token_hash,
    token_version=user.min_token_version,  # User's current version
    global_version_at_issuance=config.global_min_token_version,  # Global version
    expires_at=expires_at,
    ip_address=ip_address,
    user_agent=user_agent,
    device_info=device_info,
    location=location,
    fingerprint=fingerprint
)
```

**What This Does:**

- Integrates version validation into existing auth flow
- Minimal changes to existing code (Open-Closed Principle)
- Captures versions at token creation time

### Phase 3: API Endpoints

Add REST API endpoints for token rotation management.

#### Step 3.1: Create Token Rotation Schemas

**SOLID Principle**: Interface Segregation - Separate request/response schemas.

**File**: `src/schemas/token_rotation.py`

```python
"""Schemas for token rotation API endpoints.

Request and response models for token rotation operations.
Follows REST API design principles with clean separation.
"""

from datetime import datetime
from typing import Optional, Literal
from uuid import UUID

from pydantic import BaseModel, Field


# Request Schemas

class RotateUserTokensRequest(BaseModel):
    """Request to rotate tokens for specific user."""
    
    reason: str = Field(
        ...,
        min_length=10,
        max_length=500,
        description="Why tokens are being rotated (audit trail)",
        examples=["Password changed by user", "Suspicious activity detected"]
    )


class RotateGlobalTokensRequest(BaseModel):
    """Request to rotate all tokens system-wide (emergency)."""
    
    reason: str = Field(
        ...,
        min_length=20,
        max_length=1000,
        description="Detailed reason for global rotation (audit trail)",
        examples=["Encryption key compromised", "Database breach detected"]
    )
    grace_period_minutes: int = Field(
        default=15,
        ge=0,
        le=60,
        description="Minutes before full revocation (0-60)",
    )


# Response Schemas

class TokenRotationResponse(BaseModel):
    """Response from token rotation operation."""
    
    rotation_type: Literal["USER", "GLOBAL"] = Field(
        description="Type of rotation performed"
    )
    user_id: Optional[UUID] = Field(
        default=None,
        description="User ID (for USER rotation)"
    )
    old_version: int = Field(
        description="Previous version number"
    )
    new_version: int = Field(
        description="New version number"
    )
    tokens_revoked: int = Field(
        description="Number of tokens revoked"
    )
    users_affected: Optional[int] = Field(
        default=None,
        description="Number of users affected (GLOBAL only)"
    )
    reason: str = Field(
        description="Why rotation was performed"
    )
    initiated_by: Optional[str] = Field(
        default=None,
        description="Who initiated rotation (GLOBAL only)"
    )
    grace_period_minutes: Optional[int] = Field(
        default=None,
        description="Grace period before full revocation (GLOBAL only)"
    )
    rotated_at: datetime = Field(
        description="When rotation was performed (UTC)"
    )
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "rotation_type": "USER",
                    "user_id": "123e4567-e89b-12d3-a456-426614174000",
                    "old_version": 1,
                    "new_version": 2,
                    "tokens_revoked": 3,
                    "reason": "Password changed by user",
                    "rotated_at": "2025-10-29T22:00:00Z"
                }
            ]
        }
    }


class SecurityConfigResponse(BaseModel):
    """Current global security configuration."""
    
    global_min_token_version: int = Field(
        description="Current global minimum token version"
    )
    last_updated_at: datetime = Field(
        description="When global version was last updated (UTC)"
    )
    last_updated_by: Optional[str] = Field(
        default=None,
        description="Who last updated global version"
    )
    last_rotation_reason: Optional[str] = Field(
        default=None,
        description="Reason for last global rotation"
    )
```

**What This Does:**

- Defines clean request/response contracts
- Includes validation rules and examples
- Follows REST API schema patterns

**SOLID Principles Applied:**

- **Interface Segregation**: Separate schemas for different operations
- **Single Responsibility**: Each schema has one purpose

#### Step 3.2: Create Token Rotation Router

**File**: `src/api/token_rotation.py`

```python
"""Token rotation API endpoints.

REST API endpoints for managing token rotation for security incidents.
Requires admin authentication (future: implement admin role check).
"""

import logging
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_session
from src.services.token_rotation_service import TokenRotationService
from src.schemas.token_rotation import (
    RotateUserTokensRequest,
    RotateGlobalTokensRequest,
    TokenRotationResponse,
    SecurityConfigResponse
)
from src.api.dependencies import get_current_user
from src.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/token-rotation", tags=["Token Rotation"])


@router.post(
    "/users/{user_id}",
    response_model=TokenRotationResponse,
    status_code=status.HTTP_200_OK,
    summary="Rotate tokens for specific user",
    description="Revokes all refresh tokens for a user (password change, suspicious activity)"
)
async def rotate_user_tokens(
    user_id: str,
    request: RotateUserTokensRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)]
) -> TokenRotationResponse:
    """Rotate all tokens for specific user.
    
    Use cases:
    - Password changed
    - User requests logout from all devices
    - Suspicious activity detected
    
    Only the user themselves or an admin can rotate their tokens.
    """
    from uuid import UUID
    
    try:
        target_user_id = UUID(user_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user ID format"
        )
    
    # Authorization: User can only rotate their own tokens
    # (Future: Add admin role check to allow admins to rotate any user)
    if current_user.id != target_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only rotate your own tokens"
        )
    
    # Rotate tokens
    service = TokenRotationService(session)
    result = await service.rotate_user_tokens(
        user_id=target_user_id,
        reason=request.reason
    )
    
    return TokenRotationResponse(
        rotation_type=result.rotation_type,
        user_id=result.user_id,
        old_version=result.old_version,
        new_version=result.new_version,
        tokens_revoked=result.tokens_revoked,
        reason=result.reason,
        rotated_at=datetime.now(timezone.utc)
    )


@router.post(
    "/global",
    response_model=TokenRotationResponse,
    status_code=status.HTTP_200_OK,
    summary="Rotate ALL tokens system-wide (emergency)",
    description="Nuclear option: Revokes all refresh tokens (encryption key breach, database breach)"
)
async def rotate_global_tokens(
    request: RotateGlobalTokensRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)]
) -> TokenRotationResponse:
    """Rotate ALL tokens system-wide (emergency only).
    
    Use cases:
    - Encryption key compromise
    - Database breach
    - Critical security vulnerability
    
    WARNING: All users will be logged out. Use only for emergencies.
    
    Future: Require admin role with elevated privileges.
    """
    # Future: Add admin role check
    # For now, any authenticated user can trigger (dev/testing only)
    # In production, this would require:
    # - Admin role
    # - Multi-factor authentication
    # - Audit logging
    # - Possibly confirmation step
    
    logger.warning(
        f"Global token rotation initiated by user_id={current_user.id}, "
        f"reason='{request.reason}'"
    )
    
    # Rotate all tokens
    service = TokenRotationService(session)
    result = await service.rotate_all_tokens_global(
        reason=request.reason,
        initiated_by=f"USER:{current_user.email}",
        grace_period_minutes=request.grace_period_minutes
    )
    
    return TokenRotationResponse(
        rotation_type=result.rotation_type,
        old_version=result.old_version,
        new_version=result.new_version,
        tokens_revoked=result.tokens_revoked,
        users_affected=result.users_affected,
        reason=result.reason,
        initiated_by=result.initiated_by,
        grace_period_minutes=result.grace_period_minutes,
        rotated_at=datetime.now(timezone.utc)
    )


@router.get(
    "/security-config",
    response_model=SecurityConfigResponse,
    status_code=status.HTTP_200_OK,
    summary="Get current global security configuration",
    description="View current global token version and rotation history"
)
async def get_security_config(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)]
) -> SecurityConfigResponse:
    """Get current global security configuration.
    
    Shows current global minimum token version and last rotation details.
    """
    service = TokenRotationService(session)
    config = await service.get_security_config()
    
    return SecurityConfigResponse(
        global_min_token_version=config.global_min_token_version,
        last_updated_at=config.updated_at,
        last_updated_by=config.updated_by,
        last_rotation_reason=config.reason
    )
```

**What This Does:**

- Adds 3 REST endpoints for token rotation
- Includes authorization checks (user can rotate own tokens)
- Comprehensive logging and error handling
- Future-proof for admin role implementation

**SOLID Principles Applied:**

- **Dependency Inversion**: Depends on TokenRotationService abstraction
- **Single Responsibility**: Router only handles HTTP concerns
- **Open-Closed**: Can add new endpoints without modifying service

#### Step 3.3: Register Router in Main App

**File**: `src/main.py`

```python
# Add import
from src.api import token_rotation

# Register router (add with other routers)
app.include_router(token_rotation.router)
```

### Phase 4: Testing

Comprehensive test coverage for token rotation functionality.

#### Step 4.1: Unit Tests for TokenRotationService

**File**: `tests/unit/services/test_token_rotation_service.py`

```python
"""Unit tests for TokenRotationService.

Tests token rotation logic in isolation with mocked database.
"""

import pytest
from datetime import datetime, timezone, timedelta
from uuid import uuid4

from src.services.token_rotation_service import TokenRotationService


@pytest.mark.asyncio
class TestTokenRotationService:
    """Unit tests for TokenRotationService."""
    
    async def test_rotate_user_tokens_basic(
        self,
        async_session,
        sample_user,
        sample_refresh_token
    ):
        """Test basic user token rotation."""
        service = TokenRotationService(async_session)
        
        # Initial state: user has min_token_version=1, token has version=1
        assert sample_user.min_token_version == 1
        assert sample_refresh_token.token_version == 1
        assert not sample_refresh_token.is_revoked
        
        # Rotate tokens
        result = await service.rotate_user_tokens(
            user_id=sample_user.id,
            reason="Test rotation"
        )
        
        # Verify result
        assert result.rotation_type == "USER"
        assert result.user_id == sample_user.id
        assert result.old_version == 1
        assert result.new_version == 2
        assert result.tokens_revoked == 1
        assert result.reason == "Test rotation"
        
        # Verify database state
        await async_session.refresh(sample_user)
        await async_session.refresh(sample_refresh_token)
        
        assert sample_user.min_token_version == 2
        assert sample_refresh_token.is_revoked
        assert sample_refresh_token.revoked_at is not None
    
    async def test_rotate_user_tokens_multiple_tokens(
        self,
        async_session,
        sample_user
    ):
        """Test rotating user with multiple active tokens."""
        from src.models.auth import RefreshToken
        
        # Create 3 tokens for user
        tokens = []
        for i in range(3):
            token = RefreshToken(
                user_id=sample_user.id,
                token_hash=f"hash_{i}",
                token_version=1,
                global_version_at_issuance=1,
                expires_at=datetime.now(timezone.utc) + timedelta(days=30)
            )
            async_session.add(token)
            tokens.append(token)
        
        await async_session.commit()
        
        # Rotate tokens
        service = TokenRotationService(async_session)
        result = await service.rotate_user_tokens(
            user_id=sample_user.id,
            reason="Multiple tokens test"
        )
        
        # Verify all 3 tokens revoked
        assert result.tokens_revoked == 3
        
        for token in tokens:
            await async_session.refresh(token)
            assert token.is_revoked
    
    async def test_rotate_global_tokens(
        self,
        async_session,
        sample_users_with_tokens  # Fixture: 3 users with 2 tokens each
    ):
        """Test global token rotation."""
        service = TokenRotationService(async_session)
        
        # Get initial config
        config = await service.get_security_config()
        old_global_version = config.global_min_token_version
        
        # Rotate globally
        result = await service.rotate_all_tokens_global(
            reason="Test global rotation",
            initiated_by="ADMIN:test@example.com",
            grace_period_minutes=10
        )
        
        # Verify result
        assert result.rotation_type == "GLOBAL"
        assert result.old_version == old_global_version
        assert result.new_version == old_global_version + 1
        assert result.tokens_revoked == 6  # 3 users * 2 tokens
        assert result.users_affected == 3
        assert result.initiated_by == "ADMIN:test@example.com"
        assert result.grace_period_minutes == 10
        
        # Verify global config updated
        config = await service.get_security_config()
        assert config.global_min_token_version == old_global_version + 1
        assert config.updated_by == "ADMIN:test@example.com"
        assert config.reason == "Test global rotation"
    
    async def test_rotate_user_tokens_idempotent(
        self,
        async_session,
        sample_user,
        sample_refresh_token
    ):
        """Test that rotating twice doesn't double-revoke."""
        service = TokenRotationService(async_session)
        
        # First rotation
        result1 = await service.rotate_user_tokens(
            user_id=sample_user.id,
            reason="First rotation"
        )
        assert result1.tokens_revoked == 1
        assert result1.new_version == 2
        
        # Second rotation (token already revoked)
        result2 = await service.rotate_user_tokens(
            user_id=sample_user.id,
            reason="Second rotation"
        )
        assert result2.tokens_revoked == 0  # No new tokens to revoke
        assert result2.new_version == 3  # Version still increments
```

**Test Coverage:**

- Basic user rotation
- Multiple tokens per user
- Global rotation affecting all users
- Idempotent rotation (safe to call multiple times)
- Grace period behavior

#### Step 4.2: Integration Tests for Token Validation

**File**: `tests/integration/test_token_rotation_integration.py`

```python
"""Integration tests for token rotation with auth flow.

Tests full token rotation workflow including validation in auth flow.
"""

import pytest
from datetime import datetime, timezone, timedelta
from fastapi import status


@pytest.mark.asyncio
class TestTokenRotationIntegration:
    """Integration tests for token rotation with authentication."""
    
    async def test_token_invalid_after_user_rotation(
        self,
        async_session,
        sample_user,
        auth_service
    ):
        """Test that tokens become invalid after user rotation."""
        from src.services.token_rotation_service import TokenRotationService
        
        # Login to get tokens
        access_token, refresh_token, _ = await auth_service.login(
            email=sample_user.email,
            password="ValidPassword123!"
        )
        
        # Verify token works
        new_access = await auth_service.refresh_access_token(refresh_token)
        assert new_access is not None
        
        # Rotate user's tokens
        rotation_service = TokenRotationService(async_session)
        result = await rotation_service.rotate_user_tokens(
            user_id=sample_user.id,
            reason="Test rotation"
        )
        assert result.tokens_revoked == 1
        
        # Try to use old refresh token (should fail)
        with pytest.raises(Exception) as exc_info:
            await auth_service.refresh_access_token(refresh_token)
        
        assert "rotated" in str(exc_info.value).lower()
    
    async def test_token_invalid_after_global_rotation(
        self,
        async_session,
        sample_users_with_tokens,
        auth_service
    ):
        """Test that all tokens become invalid after global rotation."""
        from src.services.token_rotation_service import TokenRotationService
        
        # Get refresh tokens for all users
        refresh_tokens = []
        for user in sample_users_with_tokens:
            _, refresh_token, _ = await auth_service.login(
                email=user.email,
                password="ValidPassword123!"
            )
            refresh_tokens.append(refresh_token)
        
        # Rotate globally
        rotation_service = TokenRotationService(async_session)
        result = await rotation_service.rotate_all_tokens_global(
            reason="Test global rotation",
            initiated_by="ADMIN:test@example.com"
        )
        assert result.users_affected == len(sample_users_with_tokens)
        
        # Try to use all old tokens (should all fail)
        for refresh_token in refresh_tokens:
            with pytest.raises(Exception) as exc_info:
                await auth_service.refresh_access_token(refresh_token)
            
            assert "rotated" in str(exc_info.value).lower()
    
    async def test_new_tokens_valid_after_rotation(
        self,
        async_session,
        sample_user,
        auth_service
    ):
        """Test that new tokens issued after rotation are valid."""
        from src.services.token_rotation_service import TokenRotationService
        
        # Rotate user's tokens
        rotation_service = TokenRotationService(async_session)
        await rotation_service.rotate_user_tokens(
            user_id=sample_user.id,
            reason="Test rotation"
        )
        
        # Login again (new token with new version)
        _, new_refresh_token, _ = await auth_service.login(
            email=sample_user.email,
            password="ValidPassword123!"
        )
        
        # New token should work
        new_access = await auth_service.refresh_access_token(new_refresh_token)
        assert new_access is not None
```

**Test Coverage:**

- Token invalidation after user rotation
- Token invalidation after global rotation
- New tokens work after rotation
- Integration with existing auth flow

#### Step 4.3: API Endpoint Tests

**File**: `tests/api/test_token_rotation_endpoints.py`

```python
"""API tests for token rotation endpoints.

Tests REST API endpoints for token rotation management.
"""

import pytest
from fastapi import status


@pytest.mark.asyncio
class TestTokenRotationEndpoints:
    """API tests for token rotation endpoints."""
    
    async def test_rotate_user_tokens_success(
        self,
        client,
        sample_user,
        auth_headers
    ):
        """Test successful user token rotation."""
        response = await client.post(
            f"/api/v1/token-rotation/users/{sample_user.id}",
            json={"reason": "Testing user rotation endpoint"},
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["rotation_type"] == "USER"
        assert data["user_id"] == str(sample_user.id)
        assert data["new_version"] > data["old_version"]
        assert data["tokens_revoked"] >= 0
        assert data["reason"] == "Testing user rotation endpoint"
    
    async def test_rotate_user_tokens_forbidden(
        self,
        client,
        sample_user,
        other_user,
        auth_headers
    ):
        """Test that users cannot rotate other users' tokens."""
        response = await client.post(
            f"/api/v1/token-rotation/users/{other_user.id}",
            json={"reason": "Trying to rotate someone else's tokens"},
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_403_FORBIDDEN
    
    async def test_rotate_global_tokens_success(
        self,
        client,
        auth_headers
    ):
        """Test successful global token rotation."""
        response = await client.post(
            "/api/v1/token-rotation/global",
            json={
                "reason": "Testing global rotation endpoint for security incident",
                "grace_period_minutes": 10
            },
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["rotation_type"] == "GLOBAL"
        assert data["new_version"] > data["old_version"]
        assert data["users_affected"] is not None
        assert data["grace_period_minutes"] == 10
    
    async def test_get_security_config_success(
        self,
        client,
        auth_headers
    ):
        """Test retrieving global security configuration."""
        response = await client.get(
            "/api/v1/token-rotation/security-config",
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "global_min_token_version" in data
        assert "last_updated_at" in data
        assert data["global_min_token_version"] >= 1
    
    async def test_rotate_user_tokens_unauthenticated(
        self,
        client,
        sample_user
    ):
        """Test that unauthenticated requests are rejected."""
        response = await client.post(
            f"/api/v1/token-rotation/users/{sample_user.id}",
            json={"reason": "Testing without auth"}
        )
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
```

**Test Coverage:**

- Successful user rotation
- Authorization checks (users can only rotate own tokens)
- Successful global rotation
- Security config retrieval
- Unauthenticated request rejection

## Examples

### Example 1: User Changes Password (Per-User Rotation)

**Scenario**: User changes their password and wants to logout all other devices.

```bash
# User authenticates
curl -X POST https://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "OldPassword123!"
  }'

# Response includes access_token
export ACCESS_TOKEN="eyJ..."

# User changes password (triggers automatic token rotation)
# OR manually rotate tokens
curl -X POST https://localhost:8000/api/v1/token-rotation/users/[user-id] \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "reason": "Password changed - logout all devices"
  }'

# Response
{
  "rotation_type": "USER",
  "user_id": "123e4567-e89b-12d3-a456-426614174000",
  "old_version": 1,
  "new_version": 2,
  "tokens_revoked": 3,
  "reason": "Password changed - logout all devices",
  "rotated_at": "2025-10-29T22:00:00Z"
}
```

**Result**: All 3 of user's active sessions are logged out. New login required.

### Example 2: Global Rotation (Emergency)

**Scenario**: Database breach detected, rotate ALL tokens immediately.

```bash
# Admin authenticates
curl -X POST https://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@example.com",
    "password": "AdminPassword123!"
  }'

export ADMIN_TOKEN="eyJ..."

# Trigger global rotation
curl -X POST https://localhost:8000/api/v1/token-rotation/global \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "reason": "Database breach detected - emergency global token rotation per security incident response plan",
    "grace_period_minutes": 15
  }'

# Response
{
  "rotation_type": "GLOBAL",
  "old_version": 1,
  "new_version": 2,
  "tokens_revoked": 1247,
  "users_affected": 423,
  "reason": "Database breach detected - emergency global token rotation per security incident response plan",
  "initiated_by": "USER:admin@example.com",
  "grace_period_minutes": 15,
  "rotated_at": "2025-10-29T22:00:00Z"
}
```

**Result**: All 423 users (1247 active sessions) will be logged out after 15-minute grace period.

## Verification

How to verify implementation works correctly:

### Check 1: Database Schema

Verify all version fields exist.

```bash
# Check security_config table
docker compose -f compose/docker-compose.dev.yml exec postgres \
  psql -U dashtam -d dashtam -c "SELECT * FROM security_config;"

# Check users.min_token_version
docker compose -f compose/docker-compose.dev.yml exec postgres \
  psql -U dashtam -d dashtam -c "SELECT id, email, min_token_version FROM users LIMIT 5;"

# Check refresh_tokens version fields
docker compose -f compose/docker-compose.dev.yml exec postgres \
  psql -U dashtam -d dashtam -c "SELECT id, user_id, token_version, global_version_at_issuance, is_revoked FROM refresh_tokens LIMIT 5;"
```

**Expected Result**: All tables exist with correct columns and indexes.

### Check 2: Token Validation

Test that old tokens are rejected after rotation.

```bash
# Create user and get token
curl -k -X POST https://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "ValidPassword123!",
    "name": "Test User"
  }'

# Verify email (check logs for token)
# Login
TOKENS=$(curl -k -X POST https://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "ValidPassword123!"
  }')

ACCESS_TOKEN=$(echo $TOKENS | jq -r '.access_token')
REFRESH_TOKEN=$(echo $TOKENS | jq -r '.refresh_token')

# Verify token works
curl -k -X POST https://localhost:8000/api/v1/auth/refresh \
  -H "Content-Type: application/json" \
  -d "{\"refresh_token\": \"$REFRESH_TOKEN\"}"

# Rotate tokens
curl -k -X POST https://localhost:8000/api/v1/token-rotation/users/[user-id] \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"reason": "Testing token rotation"}'

# Try old token (should fail)
curl -k -X POST https://localhost:8000/api/v1/auth/refresh \
  -H "Content-Type: application/json" \
  -d "{\"refresh_token\": \"$REFRESH_TOKEN\"}"
```

**Expected Result**: First refresh succeeds, second refresh fails with "Token has been rotated" error.

### Check 3: Test Suite

Run all tests to verify comprehensive coverage.

```bash
# Run all tests
make test

# Run only token rotation tests
docker compose -f compose/docker-compose.test.yml exec app \
  uv run pytest tests/unit/services/test_token_rotation_service.py -v

docker compose -f compose/docker-compose.test.yml exec app \
  uv run pytest tests/integration/test_token_rotation_integration.py -v

docker compose -f compose/docker-compose.test.yml exec app \
  uv run pytest tests/api/test_token_rotation_endpoints.py -v
```

**Expected Result**: All tests pass, coverage >= 85% for new code.

## Troubleshooting

### Issue 1: Migration Fails with "column already exists"

**Symptoms:**

- Alembic migration fails
- Error: "column 'min_token_version' of relation 'users' already exists"

**Cause:** Migration was partially applied or run twice.

**Solution:**

```bash
# Check current migration state
make migrate-history

# If migration is marked as applied, downgrade
make migrate-down

# Re-run migration
make migrate-up

# If problem persists, manually check database
docker compose -f compose/docker-compose.dev.yml exec postgres \
  psql -U dashtam -d dashtam -c "\d users" | grep token_version
```

### Issue 2: SecurityConfig Table Empty

**Symptoms:**

- API returns 500 error: "security_config table is empty"
- TokenRotationService raises RuntimeError

**Cause:** Initial row was not inserted during migration.

**Solution:**

```bash
# Manually insert initial row
docker compose -f compose/docker-compose.dev.yml exec postgres \
  psql -U dashtam -d dashtam -c "
    INSERT INTO security_config (id, global_min_token_version, updated_at, created_at, updated_at_model)
    VALUES (gen_random_uuid(), 1, NOW(), NOW(), NOW())
    ON CONFLICT DO NOTHING;
  "

# Verify
docker compose -f compose/docker-compose.dev.yml exec postgres \
  psql -U dashtam -d dashtam -c "SELECT * FROM security_config;"
```

### Issue 3: Tokens Not Being Invalidated

**Symptoms:**

- User rotates tokens but old tokens still work
- Token validation not checking versions

**Cause:** AuthService not calling `_validate_token_versions` method.

**Solution:**

Verify `refresh_access_token` method includes version validation:

```python
# In refresh_access_token method, after existing validations

# Validate token versions
is_valid, failure_reason = await self._validate_token_versions(token, user)
if not is_valid:
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=f"Token has been rotated: {failure_reason}"
    )
```

## Best Practices

Follow these best practices for optimal results:

- ✅ **Always provide descriptive reason**: Audit trail is critical for compliance
- ✅ **Use grace period for global rotation**: Prevents abrupt service disruption (15 min recommended)
- ✅ **Test in staging first**: Never test global rotation in production
- ✅ **Monitor after rotation**: Check logs for user impact and errors
- ✅ **Automate password change rotation**: Trigger user rotation on password change
- ✅ **Document security incidents**: Keep detailed records of rotation events
- ✅ **Set up alerts**: Monitor global rotation attempts (should be rare)
- ✅ **Regular rotation drills**: Test global rotation in staging quarterly

## Common Mistakes to Avoid

- ❌ **Using global rotation casually**: Global rotation is nuclear option, use sparingly
- ❌ **Skipping grace period**: Always allow 10-15 minutes for in-flight requests
- ❌ **Forgetting to test**: Always test rotation before deploying
- ❌ **No monitoring**: Set up alerts for rotation events
- ❌ **Vague rotation reason**: Audit trail requires detailed explanations
- ❌ **Manual token version management**: Let service handle versioning logic
- ❌ **Bypassing authorization**: Enforce "users can only rotate own tokens" rule

## Next Steps

After completing this implementation, consider:

- [ ] Implement admin role check for global rotation (restrict to admins only)
- [ ] Add email notifications for security events (rotation alerts)
- [ ] Set up monitoring dashboards (track rotation frequency, user impact)
- [ ] Create runbook for security incident response
- [ ] Add token rotation to password reset flow (automatic rotation)
- [ ] Implement multi-factor authentication before global rotation
- [ ] Add confirmation step for global rotation (requires typing reason twice)
- [ ] Create audit report endpoint (view rotation history)

## References

- [Token Breach Rotation Research](../../research/token-breach-rotation-research.md) - Comprehensive analysis and decision rationale
- [JWT Authentication Architecture](../architecture/jwt-authentication.md) - Existing auth system overview
- [RESTful API Design](../architecture/restful-api-design.md) - REST API principles followed
- [Testing Guide](../guides/testing-guide.md) - Testing strategy and patterns
- [Alembic Documentation](https://alembic.sqlalchemy.org/) - Database migrations
- [Auth0 Token Rotation](https://auth0.com/docs/secure/tokens/refresh-tokens/refresh-token-rotation) - Industry patterns
- [OWASP Token Management](https://cheatsheetseries.owasp.org/cheatsheets/JSON_Web_Token_for_Java_Cheat_Sheet.html) - Security best practices

---

## Document Information

**Template:** [guide-template.md](../../templates/guide-template.md)
**Created:** 2025-10-29
**Last Updated:** 2025-10-29
