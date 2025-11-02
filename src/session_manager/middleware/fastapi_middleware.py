"""FastAPI middleware adapter for session manager.

This module provides FastAPI-specific integration for the session manager
package. It adds SessionManagerService to the request state and provides
a dependency function for endpoint injection.

This is a FRAMEWORK ADAPTER - specific to FastAPI. Other frameworks
(Django, Flask) would have their own adapter modules.

Usage:
    from fastapi import FastAPI
    from src.session_manager.middleware.fastapi_middleware import (
        SessionManagerMiddleware,
        get_session_manager,
    )
    from src.session_manager.factory import get_session_manager as create_manager
    from src.models.session import Session
    from src.core.database import get_session

    # Create session manager instance
    async def create_session_manager():
        db_session = await anext(get_session())
        return create_manager(
            session_model=Session,
            config=SessionConfig(),
            db_session=db_session,
        )

    # Add middleware to FastAPI app
    app = FastAPI()
    app.add_middleware(
        SessionManagerMiddleware,
        session_manager_factory=create_session_manager,
    )

    # Use in endpoints
    @app.get("/sessions")
    async def list_sessions(
        current_user: User = Depends(get_current_user),
        session_manager: SessionManagerService = Depends(get_session_manager),
    ):
        sessions = await session_manager.list_sessions(current_user.id)
        return sessions
"""

import logging
from typing import Awaitable, Callable, Optional

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from src.session_manager.service import SessionManagerService

logger = logging.getLogger(__name__)


class SessionManagerMiddleware(BaseHTTPMiddleware):
    """FastAPI middleware that adds SessionManagerService to request state.

    This middleware instantiates a SessionManagerService for each request
    and attaches it to request.state.session_manager. This allows endpoints
    to access the session manager via dependency injection.

    Attributes:
        session_manager_factory: Async factory function that creates
            SessionManagerService instances

    Example:
        >>> from fastapi import FastAPI
        >>> from src.session_manager.middleware.fastapi_middleware import (
        ...     SessionManagerMiddleware,
        ... )
        >>>
        >>> app = FastAPI()
        >>> app.add_middleware(
        ...     SessionManagerMiddleware,
        ...     session_manager_factory=create_session_manager,
        ... )

    Note:
        The factory function is called for each request. For performance,
        consider caching the manager instance if all requests share the
        same configuration (depends on your application architecture).
    """

    def __init__(
        self,
        app,
        session_manager_factory: Callable[[], Awaitable[SessionManagerService]],
    ):
        """Initialize middleware with session manager factory.

        Args:
            app: FastAPI application instance
            session_manager_factory: Async factory function that creates
                SessionManagerService instances. Called for each request.

        Example:
            >>> async def create_manager():
            ...     db_session = await anext(get_session())
            ...     return get_session_manager(
            ...         session_model=Session,
            ...         config=SessionConfig(),
            ...         db_session=db_session,
            ...     )
            >>>
            >>> app.add_middleware(
            ...     SessionManagerMiddleware,
            ...     session_manager_factory=create_manager,
            ... )
        """
        super().__init__(app)
        self.session_manager_factory = session_manager_factory

    async def dispatch(self, request: Request, call_next):
        """Process request and add session manager to request state.

        Args:
            request: FastAPI Request object
            call_next: Next middleware/endpoint in chain

        Returns:
            Response from downstream middleware/endpoint
        """
        try:
            # Create session manager instance for this request
            session_manager = await self.session_manager_factory()

            # Attach to request state
            request.state.session_manager = session_manager

            logger.debug("SessionManager attached to request state")

        except Exception as e:
            # Log error but don't block request
            # Endpoints can handle missing session manager gracefully
            logger.error(
                f"Failed to create SessionManager for request: {e}",
                exc_info=True,
            )
            request.state.session_manager = None

        # Continue request processing
        response = await call_next(request)
        return response


# Dependency function for endpoint injection


def get_session_manager(request: Request) -> Optional[SessionManagerService]:
    """Dependency function to inject SessionManagerService into endpoints.

    Extracts SessionManagerService from request.state (added by middleware).

    Args:
        request: FastAPI Request object

    Returns:
        SessionManagerService instance, or None if middleware not configured

    Raises:
        RuntimeError: If middleware not configured (session_manager not in state)

    Example:
        >>> from fastapi import Depends
        >>> from src.session_manager.middleware.fastapi_middleware import (
        ...     get_session_manager,
        ... )
        >>>
        >>> @app.get("/sessions")
        >>> async def list_sessions(
        ...     current_user: User = Depends(get_current_user),
        ...     session_manager: SessionManagerService = Depends(get_session_manager),
        ... ):
        ...     sessions = await session_manager.list_sessions(current_user.id)
        ...     return sessions

    Note:
        This dependency assumes SessionManagerMiddleware is configured.
        If middleware is missing, this will raise RuntimeError.
    """
    session_manager = getattr(request.state, "session_manager", None)

    if session_manager is None:
        raise RuntimeError(
            "SessionManager not found in request state. "
            "Did you forget to add SessionManagerMiddleware?"
        )

    return session_manager


# Optional: Dependency that returns None instead of raising


def get_session_manager_optional(
    request: Request,
) -> Optional[SessionManagerService]:
    """Optional dependency that returns None if session manager not available.

    Use this instead of get_session_manager() when session manager is optional.

    Args:
        request: FastAPI Request object

    Returns:
        SessionManagerService instance, or None if not available

    Example:
        >>> @app.get("/health")
        >>> async def health_check(
        ...     session_manager: Optional[SessionManagerService] = Depends(
        ...         get_session_manager_optional
        ...     ),
        ... ):
        ...     return {
        ...         "status": "healthy",
        ...         "session_manager": session_manager is not None,
        ...     }
    """
    return getattr(request.state, "session_manager", None)
