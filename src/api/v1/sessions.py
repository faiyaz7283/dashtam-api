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
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, status

from src.api.dependencies import (
    get_current_user,
    get_client_ip,
    get_current_session_id,
    get_session_manager,
    get_user_agent,
)
from src.core.fingerprinting import format_device_info
from src.models.user import User
from src.schemas.session import (
    SessionListResponse,
    SessionInfoResponse,
    RevokeSessionResponse,
    BulkRevokeResponse,
)
from src.session_manager.models.filters import SessionFilters
from src.session_manager.service import SessionManagerService

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
    current_user: User = Depends(get_current_user),
    current_session_id: Optional[str] = Depends(get_current_session_id),
    session_manager: SessionManagerService = Depends(get_session_manager),
):
    """List all active sessions for authenticated user.

    Rate limit: 10 requests per minute per user.

    Uses pluggable session_manager package (SOLID + Strategy Pattern).
    """
    # List active sessions using session_manager
    # SessionFilters(active_only=True) returns only non-revoked, non-expired sessions
    sessions = await session_manager.list_sessions(
        user_id=str(current_user.id),
        filters=SessionFilters(active_only=True),
    )

    # Convert to response schema
    session_responses = [
        SessionInfoResponse(
            id=session.id,
            device_info=session.device_info or "Unknown Device",
            location=session.location or "Unknown Location",
            ip_address=session.ip_address,
            last_activity=session.last_activity,
            created_at=session.created_at,
            is_current=(str(session.id) == current_session_id),
            is_trusted=session.is_trusted,
        )
        for session in sessions
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
    - Invalidates token in cache (immediate blacklist)
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
    current_user: User = Depends(get_current_user),
    current_session_id: Optional[str] = Depends(get_current_session_id),
    session_manager: SessionManagerService = Depends(get_session_manager),
    ip_address: Optional[str] = Depends(get_client_ip),
    user_agent: Optional[str] = Depends(get_user_agent),
):
    """Revoke specific session (logout from device).

    Rate limit: 20 requests per minute per user.

    Uses pluggable session_manager package (SOLID + Strategy Pattern).
    """
    from fastapi import HTTPException

    # Prevent revoking current session (use logout endpoint instead)
    if str(session_id) == current_session_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot revoke current session. Use /api/v1/auth/logout endpoint instead.",
        )

    # Verify session exists and belongs to current user
    session = await session_manager.get_session(str(session_id))
    if not session or str(session.user_id) != str(current_user.id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found or not owned by user",
        )

    # Revoke session with audit context
    revoked = await session_manager.revoke_session(
        session_id=str(session_id),
        reason="User revoked via API",
        context={
            "revoked_by_user_id": str(current_user.id),
            "revoked_by_ip": ip_address,
            "revoked_by_device": format_device_info(user_agent)
            if user_agent
            else "Unknown",
        },
    )

    if not revoked:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to revoke session",
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
    current_user: User = Depends(get_current_user),
    current_session_id: Optional[str] = Depends(get_current_session_id),
    session_manager: SessionManagerService = Depends(get_session_manager),
):
    """Revoke all sessions except current.

    Rate limit: 5 requests per hour per user.

    Uses pluggable session_manager package (SOLID + Strategy Pattern).
    """
    # Revoke all sessions except current using session_manager
    # except_session_id keeps current session active
    revoked_count = await session_manager.revoke_all_user_sessions(
        user_id=str(current_user.id),
        reason="User revoked all other sessions via API",
        except_session_id=current_session_id,
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
    session_manager: SessionManagerService = Depends(get_session_manager),
    ip_address: Optional[str] = Depends(get_client_ip),
    user_agent: Optional[str] = Depends(get_user_agent),
):
    """Revoke all sessions (nuclear option).

    Rate limit: 3 requests per hour per user.

    Uses pluggable session_manager package (SOLID + Strategy Pattern).
    """
    # Revoke ALL sessions (including current) using session_manager
    # No except_session_id parameter = revoke everything
    revoked_count = await session_manager.revoke_all_user_sessions(
        user_id=str(current_user.id),
        reason="User revoked all sessions (nuclear option) via API",
        except_session_id=None,  # Explicit: revoke ALL sessions
    )

    return BulkRevokeResponse(
        message="All sessions revoked successfully. You have been logged out.",
        revoked_count=revoked_count,
    )
