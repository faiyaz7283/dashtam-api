"""Session management API endpoints.

Provides user-facing session control:
- List all active sessions
- Revoke specific session
- Revoke all other sessions
- Revoke all sessions (including current)

Security:
- JWT authentication required
- Users can only manage their own sessions
- Rate limiting applied (see RateLimitConfig)
- Audit logging for all operations

REST Compliance:
- Resource-oriented URLs (/api/v1/auth/sessions)
- Proper HTTP methods (GET, DELETE)
- Standard status codes (200, 400, 404)
- No inline Pydantic schemas
"""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_current_user
from src.core.database import get_session
from src.core.fingerprinting import format_device_info
from src.models.user import User
from src.schemas.session import (
    SessionListResponse,
    SessionInfoResponse,
    RevokeSessionResponse,
    BulkRevokeResponse,
)
from src.services.session_management_service import SessionManagementService
from src.services.geolocation_service import get_geolocation_service
from src.services.jwt_service import JWTService

router = APIRouter(prefix="/auth/sessions", tags=["sessions"])
logger = logging.getLogger(__name__)


@router.get(
    "",
    response_model=SessionListResponse,
    status_code=status.HTTP_200_OK,
    summary="List all active sessions",
    description="""
    List all active sessions (devices) for the authenticated user.
    
    Returns:
    - Device information (browser, OS)
    - Location (city, country from IP)
    - Last activity timestamp
    - Current session indicator
    - Trusted device flag
    
    Sessions are sorted by last activity (most recent first).
    """,
    responses={
        200: {"description": "List of active sessions"},
        401: {"description": "Not authenticated"},
        429: {"description": "Rate limit exceeded (10 requests/minute)"},
    },
)
async def list_sessions(
    request: Request,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """List all active sessions for authenticated user.

    Rate limit: 10 requests per minute per user.
    """
    # Initialize services
    geo_service = get_geolocation_service()
    mgmt_service = SessionManagementService(session, geo_service)
    jwt_service = JWTService()

    # Extract current session ID from JWT (jti claim)
    auth_header = request.headers.get("Authorization", "")
    token = auth_header.replace("Bearer ", "")

    try:
        payload = jwt_service.decode_token(token)
        current_token_id = UUID(payload.get("jti")) if payload.get("jti") else None
    except Exception:
        current_token_id = None

    # List sessions
    sessions = await mgmt_service.list_sessions(
        user_id=current_user.id, current_token_id=current_token_id
    )

    # Convert to response schema
    session_responses = [
        SessionInfoResponse(
            id=s.id,
            device_info=s.device_info,
            location=s.location,
            ip_address=s.ip_address,  # Optional: hide for privacy
            last_activity=s.last_activity,
            created_at=s.created_at,
            is_current=s.is_current,
            is_trusted=s.is_trusted,
        )
        for s in sessions
    ]

    return SessionListResponse(
        sessions=session_responses, total_count=len(session_responses)
    )


@router.delete(
    "/{session_id}",
    response_model=RevokeSessionResponse,
    status_code=status.HTTP_200_OK,
    summary="Revoke specific session",
    description="""
    Revoke a specific session (logout from device).
    
    Cannot revoke current session (use logout endpoint instead).
    Session is immediately revoked (no delay).
    
    Security:
    - Creates audit log entry
    - Invalidates token in Redis cache
    - Sends email alert if revoked from different device/IP
    """,
    responses={
        200: {"description": "Session revoked successfully"},
        400: {"description": "Cannot revoke current session"},
        401: {"description": "Not authenticated"},
        404: {"description": "Session not found or not owned by user"},
        429: {"description": "Rate limit exceeded (20 requests/minute)"},
    },
)
async def revoke_session(
    session_id: UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Revoke specific session (logout from device).

    Rate limit: 20 requests per minute per user.
    """
    # Initialize services
    geo_service = get_geolocation_service()
    mgmt_service = SessionManagementService(session, geo_service)
    jwt_service = JWTService()

    # Extract current session ID from JWT
    auth_header = request.headers.get("Authorization", "")
    token = auth_header.replace("Bearer ", "")

    try:
        payload = jwt_service.decode_token(token)
        current_token_id = UUID(payload.get("jti")) if payload.get("jti") else None
    except Exception:
        current_token_id = None

    # Get revocation context
    revoked_by_ip = request.client.host if request.client else "unknown"
    revoked_by_device = format_device_info(request.headers.get("user-agent", ""))

    # Revoke session
    await mgmt_service.revoke_session(
        user_id=current_user.id,
        session_id=session_id,
        current_session_id=current_token_id,
        revoked_by_ip=revoked_by_ip,
        revoked_by_device=revoked_by_device,
    )

    return RevokeSessionResponse(
        message="Session revoked successfully", revoked_session_id=session_id
    )


@router.delete(
    "/others/revoke",
    response_model=BulkRevokeResponse,
    status_code=status.HTTP_200_OK,
    summary="Revoke all other sessions",
    description="""
    Revoke all sessions except the current one (keep current, logout from all others).
    
    Use cases:
    - User suspects account compromise
    - User lost device (quick response)
    - User wants single-device access
    
    Current session remains active.
    """,
    responses={
        200: {"description": "All other sessions revoked"},
        401: {"description": "Not authenticated"},
        429: {"description": "Rate limit exceeded (5 requests/hour)"},
    },
)
async def revoke_other_sessions(
    request: Request,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Revoke all sessions except current.

    Rate limit: 5 requests per hour per user.
    """
    # Initialize services
    geo_service = get_geolocation_service()
    mgmt_service = SessionManagementService(session, geo_service)
    jwt_service = JWTService()

    # Extract current session ID from JWT
    auth_header = request.headers.get("Authorization", "")
    token = auth_header.replace("Bearer ", "")

    try:
        payload = jwt_service.decode_token(token)
        current_token_id = UUID(payload.get("jti")) if payload.get("jti") else None
    except Exception:
        current_token_id = None

    # Revoke other sessions
    revoked_count = await mgmt_service.revoke_other_sessions(
        user_id=current_user.id, current_session_id=current_token_id
    )

    return BulkRevokeResponse(
        message="All other sessions revoked successfully", revoked_count=revoked_count
    )


@router.delete(
    "/all/revoke",
    response_model=BulkRevokeResponse,
    status_code=status.HTTP_200_OK,
    summary="Revoke all sessions (including current)",
    description="""
    Revoke ALL sessions including current (nuclear option).
    
    User will be logged out immediately.
    
    Use cases:
    - User confirms account breach
    - User wants to reset all sessions
    - Admin-initiated logout
    """,
    responses={
        200: {"description": "All sessions revoked (user logged out)"},
        401: {"description": "Not authenticated"},
        429: {"description": "Rate limit exceeded (3 requests/hour)"},
    },
)
async def revoke_all_sessions(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Revoke all sessions (nuclear option).

    Rate limit: 3 requests per hour per user.
    """
    # Initialize services
    geo_service = get_geolocation_service()
    mgmt_service = SessionManagementService(session, geo_service)

    # Revoke all sessions
    revoked_count = await mgmt_service.revoke_all_sessions(current_user.id)

    return BulkRevokeResponse(
        message="All sessions revoked successfully. You have been logged out.",
        revoked_count=revoked_count,
    )
