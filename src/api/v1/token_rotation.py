"""Token management API endpoints (RESTful design).

Resource-oriented endpoints for managing user tokens and security configuration.
Follows REST principles: tokens are resources that can be deleted (revoked).

Design rationale:
- DELETE /users/{id}/tokens: Revoke all tokens for a user (resource deletion)
- DELETE /tokens: Revoke all tokens system-wide (admin only, nuclear option)
- GET /security/config: View security configuration (read-only)

Previous design (/token-rotation/) was action-oriented (non-RESTful).
This refactoring maintains 100% REST compliance.
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
    SecurityConfigResponse,
)
from src.api.dependencies import get_current_user
from src.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Token Management"])


@router.delete(
    "/users/{user_id}/tokens",
    response_model=TokenRotationResponse,
    status_code=status.HTTP_200_OK,
    summary="Revoke all tokens for a user",
    description="""Revoke all refresh tokens for a user (logout from all devices).
    
    Use cases:
    - Password changed (automatic)
    - User requests logout from all devices
    - Suspicious activity detected
    - Security incident response
    
    Authorization: Users can only revoke their own tokens (or use /auth/me/tokens).
    Future: Admin role can revoke any user's tokens.
    """,
)
async def revoke_user_tokens(
    user_id: str,
    request: RotateUserTokensRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> TokenRotationResponse:
    """Revoke all tokens for a specific user.

    RESTful design: DELETE operation on tokens resource.
    Implementation: Increments user's token version (invalidates all existing tokens).

    Use cases:
    - Password changed
    - User requests logout from all devices
    - Suspicious activity detected

    Authorization:
    - Users can only revoke their own tokens
    - Future: Admin role can revoke any user's tokens

    Args:
        user_id: UUID of user whose tokens to revoke.
        request: Revocation request with reason.
        current_user: Currently authenticated user.
        session: Database session.

    Returns:
        TokenRotationResponse with revocation details.

    Raises:
        HTTPException: If user_id invalid, unauthorized, or revocation fails.
    """
    from uuid import UUID

    try:
        target_user_id = UUID(user_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid user ID format"
        )

    # Authorization: User can only rotate their own tokens
    # (Future: Add admin role check to allow admins to rotate any user)
    if current_user.id != target_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only rotate your own tokens",
        )

    # Rotate tokens
    service = TokenRotationService(session)
    result = await service.rotate_user_tokens(
        user_id=target_user_id, reason=request.reason
    )

    return TokenRotationResponse(
        rotation_type=result.rotation_type,
        user_id=result.user_id,
        old_version=result.old_version,
        new_version=result.new_version,
        tokens_revoked=result.tokens_revoked,
        reason=result.reason,
        rotated_at=datetime.now(timezone.utc),
    )


@router.delete(
    "/tokens",
    response_model=TokenRotationResponse,
    status_code=status.HTTP_200_OK,
    summary="Revoke ALL tokens system-wide (nuclear option)",
    description="""Emergency: Revoke all refresh tokens for all users.
    
    Use cases:
    - Encryption key compromise
    - Database breach
    - Critical security vulnerability discovered
    
    WARNING: ALL users will be logged out immediately. Use only for emergencies.
    
    Authorization: Requires admin role (future implementation).
    Current: Any authenticated user (dev/testing only).
    """,
)
async def revoke_all_tokens(
    request: RotateGlobalTokensRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> TokenRotationResponse:
    """Revoke ALL tokens system-wide (nuclear option).

    RESTful design: DELETE operation on global tokens resource.
    Implementation: Increments global token version (invalidates all tokens).

    Use cases:
    - Encryption key compromise
    - Database breach
    - Critical security vulnerability

    WARNING: All users will be logged out. Use only for emergencies.

    Authorization:
    - Future: Requires admin role with MFA
    - Current: Any authenticated user (dev/testing only)

    Args:
        request: Global revocation request with reason and grace period.
        current_user: Currently authenticated user.
        session: Database session.

    Returns:
        TokenRotationResponse with global revocation details.

    Raises:
        HTTPException: If revocation fails.
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
        grace_period_minutes=request.grace_period_minutes,
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
        rotated_at=datetime.now(timezone.utc),
    )


@router.get(
    "/security/config",
    response_model=SecurityConfigResponse,
    status_code=status.HTTP_200_OK,
    summary="Get security configuration",
    description="""View current token security configuration and version.
    
    Returns:
    - Current global token version
    - Last rotation timestamp
    - Who initiated last rotation
    - Rotation reason
    
    Useful for:
    - Security auditing
    - Monitoring token rotation history
    - Debugging token validation issues
    """,
)
async def get_security_config(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> SecurityConfigResponse:
    """Get current security configuration.

    RESTful design: GET operation on security config resource (read-only).

    Returns current global token version and rotation history.
    Useful for security auditing and monitoring.

    Args:
        current_user: Currently authenticated user.
        session: Database session.

    Returns:
        SecurityConfigResponse with current configuration.

    Raises:
        HTTPException: If configuration retrieval fails.
    """
    service = TokenRotationService(session)
    config = await service.get_security_config()

    return SecurityConfigResponse(
        global_min_token_version=config.global_min_token_version,
        last_updated_at=config.updated_at,
        last_updated_by=config.updated_by,
        last_rotation_reason=config.reason,
    )
