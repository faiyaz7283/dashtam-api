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
    SecurityConfigResponse,
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
    description="Revokes all refresh tokens for a user (password change, suspicious activity)",
)
async def rotate_user_tokens(
    user_id: str,
    request: RotateUserTokensRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> TokenRotationResponse:
    """Rotate all tokens for specific user.

    Use cases:
    - Password changed
    - User requests logout from all devices
    - Suspicious activity detected

    Only the user themselves or an admin can rotate their tokens.

    Args:
        user_id: UUID of user whose tokens to rotate.
        request: Rotation request with reason.
        current_user: Currently authenticated user.
        session: Database session.

    Returns:
        TokenRotationResponse with rotation details.

    Raises:
        HTTPException: If user_id invalid, unauthorized, or rotation fails.
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


@router.post(
    "/global",
    response_model=TokenRotationResponse,
    status_code=status.HTTP_200_OK,
    summary="Rotate ALL tokens system-wide (emergency)",
    description="Nuclear option: Revokes all refresh tokens (encryption key breach, database breach)",
)
async def rotate_global_tokens(
    request: RotateGlobalTokensRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> TokenRotationResponse:
    """Rotate ALL tokens system-wide (emergency only).

    Use cases:
    - Encryption key compromise
    - Database breach
    - Critical security vulnerability

    WARNING: All users will be logged out. Use only for emergencies.

    Future: Require admin role with elevated privileges.

    Args:
        request: Global rotation request with reason and grace period.
        current_user: Currently authenticated user.
        session: Database session.

    Returns:
        TokenRotationResponse with global rotation details.

    Raises:
        HTTPException: If rotation fails.
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
    "/security-config",
    response_model=SecurityConfigResponse,
    status_code=status.HTTP_200_OK,
    summary="Get current global security configuration",
    description="View current global token version and rotation history",
)
async def get_security_config(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> SecurityConfigResponse:
    """Get current global security configuration.

    Shows current global minimum token version and last rotation details.

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
