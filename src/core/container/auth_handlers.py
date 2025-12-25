"""Authentication handler dependency factories.

Request-scoped handler instances for authentication operations:
- User registration, login, logout
- Token refresh, email verification
- Password reset (request and confirm)
- Session management (list, get, revoke)
- Token rotation (global and per-user)

Reference:
    See docs/architecture/authentication-architecture.md for complete
    authentication flow documentation.
"""

from typing import TYPE_CHECKING

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.core.container.events import get_event_bus
from src.core.container.infrastructure import (
    get_cache,
    get_cache_keys,
    get_cache_metrics,
    get_db_session,
    get_email_service,
    get_logger,
    get_password_service,
    get_token_service,
)

if TYPE_CHECKING:
    from src.application.commands.handlers.authenticate_user_handler import (
        AuthenticateUserHandler,
    )
    from src.application.commands.handlers.confirm_password_reset_handler import (
        ConfirmPasswordResetHandler,
    )
    from src.application.commands.handlers.create_session_handler import (
        CreateSessionHandler,
    )
    from src.application.commands.handlers.generate_auth_tokens_handler import (
        GenerateAuthTokensHandler,
    )
    from src.application.commands.handlers.logout_user_handler import LogoutUserHandler
    from src.application.commands.handlers.refresh_access_token_handler import (
        RefreshAccessTokenHandler,
    )
    from src.application.commands.handlers.register_user_handler import (
        RegisterUserHandler,
    )
    from src.application.commands.handlers.request_password_reset_handler import (
        RequestPasswordResetHandler,
    )
    from src.application.commands.handlers.revoke_all_sessions_handler import (
        RevokeAllSessionsHandler,
    )
    from src.application.commands.handlers.revoke_session_handler import (
        RevokeSessionHandler,
    )
    from src.application.commands.handlers.trigger_global_rotation_handler import (
        TriggerGlobalTokenRotationHandler,
    )
    from src.application.commands.handlers.trigger_user_rotation_handler import (
        TriggerUserTokenRotationHandler,
    )
    from src.application.commands.handlers.verify_email_handler import (
        VerifyEmailHandler,
    )
    from src.application.queries.handlers.get_session_handler import GetSessionHandler
    from src.application.queries.handlers.list_sessions_handler import (
        ListSessionsHandler,
    )


# ============================================================================
# Authentication Handler Factories
# ============================================================================


async def get_register_user_handler(
    session: AsyncSession = Depends(get_db_session),
) -> "RegisterUserHandler":
    """Get RegisterUser command handler (request-scoped).

    Creates new handler instance per request with all required dependencies:
    - UserRepository (request-scoped, uses session)
    - EmailVerificationTokenRepository (request-scoped, uses session)
    - BcryptPasswordService (app-scoped singleton)
    - EventBus (app-scoped singleton)

    Returns:
        RegisterUserHandler instance.

    Usage:
        # Presentation Layer (FastAPI endpoint)
        from fastapi import Depends
        from src.application.commands.handlers.register_user_handler import (
            RegisterUserHandler,
        )

        @router.post("/users")
        async def create_user(
            handler: RegisterUserHandler = Depends(get_register_user_handler)
        ):
            result = await handler.handle(command)

    Reference:
        - docs/architecture/authentication-architecture.md (Lines 250-278)
    """
    from src.application.commands.handlers.register_user_handler import (
        RegisterUserHandler,
    )
    from src.infrastructure.persistence.repositories import (
        EmailVerificationTokenRepository,
        UserRepository,
    )

    # Create repositories with session
    user_repo = UserRepository(session=session)
    verification_token_repo = EmailVerificationTokenRepository(session=session)

    # Get application-scoped singletons
    password_service = get_password_service()
    event_bus = get_event_bus()

    return RegisterUserHandler(
        user_repo=user_repo,
        verification_token_repo=verification_token_repo,
        password_service=password_service,
        event_bus=event_bus,
    )


async def get_authenticate_user_handler(
    session: AsyncSession = Depends(get_db_session),
) -> "AuthenticateUserHandler":
    """Get AuthenticateUser command handler (request-scoped).

    Single responsibility: Verify user credentials.
    Part of 3-handler login orchestration (authenticate → session → tokens).

    Returns:
        AuthenticateUserHandler instance.
    """
    from src.application.commands.handlers.authenticate_user_handler import (
        AuthenticateUserHandler,
    )
    from src.infrastructure.persistence.repositories import UserRepository

    user_repo = UserRepository(session=session)
    password_service = get_password_service()
    event_bus = get_event_bus()

    return AuthenticateUserHandler(
        user_repo=user_repo,
        password_service=password_service,
        event_bus=event_bus,
    )


async def get_generate_auth_tokens_handler(
    session: AsyncSession = Depends(get_db_session),
) -> "GenerateAuthTokensHandler":
    """Get GenerateAuthTokens command handler (request-scoped).

    Single responsibility: Generate JWT + refresh token.
    Part of 3-handler login orchestration (authenticate → session → tokens).

    Returns:
        GenerateAuthTokensHandler instance.
    """
    from src.application.commands.handlers.generate_auth_tokens_handler import (
        GenerateAuthTokensHandler,
    )
    from src.infrastructure.persistence.repositories import (
        RefreshTokenRepository,
        SecurityConfigRepository,
    )
    from src.infrastructure.security.refresh_token_service import RefreshTokenService

    refresh_token_repo = RefreshTokenRepository(session=session)
    security_config_repo = SecurityConfigRepository(
        session=session,
        cache=get_cache(),
        cache_keys=get_cache_keys(),
    )
    token_service = get_token_service()
    refresh_token_service = RefreshTokenService()

    return GenerateAuthTokensHandler(
        token_service=token_service,
        refresh_token_service=refresh_token_service,
        refresh_token_repo=refresh_token_repo,
        security_config_repo=security_config_repo,
    )


async def get_create_session_handler(
    session: AsyncSession = Depends(get_db_session),
) -> "CreateSessionHandler":
    """Get CreateSession command handler (request-scoped).

    Single responsibility: Create session with device/location enrichment.
    Part of 3-handler login orchestration (authenticate → session → tokens).

    Returns:
        CreateSessionHandler instance.
    """
    from src.application.commands.handlers.create_session_handler import (
        CreateSessionHandler,
    )
    from src.infrastructure.cache import RedisSessionCache
    from src.infrastructure.enrichers.device_enricher import UserAgentDeviceEnricher
    from src.infrastructure.enrichers.location_enricher import IPLocationEnricher
    from src.infrastructure.persistence.repositories import (
        SessionRepository,
        UserRepository,
    )

    session_repo = SessionRepository(session=session)
    user_repo = UserRepository(session=session)
    session_cache = RedisSessionCache(cache=get_cache())
    logger = get_logger()
    device_enricher = UserAgentDeviceEnricher(logger=logger)
    location_enricher = IPLocationEnricher(logger=logger)
    event_bus = get_event_bus()

    return CreateSessionHandler(
        session_repo=session_repo,
        session_cache=session_cache,
        user_repo=user_repo,
        device_enricher=device_enricher,
        location_enricher=location_enricher,
        event_bus=event_bus,
    )


async def get_logout_user_handler(
    session: AsyncSession = Depends(get_db_session),
) -> "LogoutUserHandler":
    """Get LogoutUser command handler (request-scoped).

    Returns:
        LogoutUserHandler instance.
    """
    from src.application.commands.handlers.logout_user_handler import LogoutUserHandler
    from src.infrastructure.persistence.repositories import RefreshTokenRepository
    from src.infrastructure.security.refresh_token_service import RefreshTokenService

    refresh_token_repo = RefreshTokenRepository(session=session)
    refresh_token_service = RefreshTokenService()
    event_bus = get_event_bus()

    return LogoutUserHandler(
        refresh_token_repo=refresh_token_repo,
        refresh_token_service=refresh_token_service,
        event_bus=event_bus,
    )


async def get_refresh_token_handler(
    session: AsyncSession = Depends(get_db_session),
) -> "RefreshAccessTokenHandler":
    """Get RefreshAccessToken command handler (request-scoped).

    Returns:
        RefreshAccessTokenHandler instance with cache support.
    """
    from src.application.commands.handlers.refresh_access_token_handler import (
        RefreshAccessTokenHandler,
    )
    from src.infrastructure.persistence.repositories import (
        RefreshTokenRepository,
        SecurityConfigRepository,
        UserRepository,
    )
    from src.infrastructure.security.refresh_token_service import RefreshTokenService

    user_repo = UserRepository(session=session)
    refresh_token_repo = RefreshTokenRepository(session=session)
    security_config_repo = SecurityConfigRepository(
        session=session,
        cache=get_cache(),
        cache_keys=get_cache_keys(),
    )
    token_service = get_token_service()
    refresh_token_service = RefreshTokenService()
    event_bus = get_event_bus()

    # Phase 7: Security config cache (MEDIUM priority optimization)
    cache = get_cache()
    cache_keys = get_cache_keys()
    cache_metrics = get_cache_metrics()

    return RefreshAccessTokenHandler(
        user_repo=user_repo,
        refresh_token_repo=refresh_token_repo,
        security_config_repo=security_config_repo,
        token_service=token_service,
        refresh_token_service=refresh_token_service,
        event_bus=event_bus,
        cache=cache,
        cache_keys=cache_keys,
        cache_metrics=cache_metrics,
        cache_ttl=settings.cache_security_ttl,
    )


async def get_verify_email_handler(
    session: AsyncSession = Depends(get_db_session),
) -> "VerifyEmailHandler":
    """Get VerifyEmail command handler (request-scoped).

    Returns:
        VerifyEmailHandler instance.
    """
    from src.application.commands.handlers.verify_email_handler import (
        VerifyEmailHandler,
    )
    from src.infrastructure.persistence.repositories import (
        EmailVerificationTokenRepository,
        UserRepository,
    )

    user_repo = UserRepository(session=session)
    verification_token_repo = EmailVerificationTokenRepository(session=session)
    event_bus = get_event_bus()

    return VerifyEmailHandler(
        user_repo=user_repo,
        verification_token_repo=verification_token_repo,
        event_bus=event_bus,
    )


async def get_request_password_reset_handler(
    session: AsyncSession = Depends(get_db_session),
) -> "RequestPasswordResetHandler":
    """Get RequestPasswordReset command handler (request-scoped).

    Returns:
        RequestPasswordResetHandler instance.
    """
    from src.application.commands.handlers.request_password_reset_handler import (
        RequestPasswordResetHandler,
    )
    from src.infrastructure.persistence.repositories import (
        PasswordResetTokenRepository,
        UserRepository,
    )
    from src.infrastructure.security.password_reset_token_service import (
        PasswordResetTokenService,
    )

    user_repo = UserRepository(session=session)
    password_reset_repo = PasswordResetTokenRepository(session=session)
    token_service = PasswordResetTokenService()
    email_service = get_email_service()
    event_bus = get_event_bus()

    return RequestPasswordResetHandler(
        user_repo=user_repo,
        password_reset_repo=password_reset_repo,
        token_service=token_service,
        email_service=email_service,
        event_bus=event_bus,
        verification_url_base=settings.verification_url_base,
    )


async def get_confirm_password_reset_handler(
    session: AsyncSession = Depends(get_db_session),
) -> "ConfirmPasswordResetHandler":
    """Get ConfirmPasswordReset command handler (request-scoped).

    Returns:
        ConfirmPasswordResetHandler instance.
    """
    from src.application.commands.handlers.confirm_password_reset_handler import (
        ConfirmPasswordResetHandler,
    )
    from src.infrastructure.persistence.repositories import (
        PasswordResetTokenRepository,
        RefreshTokenRepository,
        UserRepository,
    )

    user_repo = UserRepository(session=session)
    password_reset_repo = PasswordResetTokenRepository(session=session)
    refresh_token_repo = RefreshTokenRepository(session=session)
    password_service = get_password_service()
    email_service = get_email_service()
    event_bus = get_event_bus()

    return ConfirmPasswordResetHandler(
        user_repo=user_repo,
        password_reset_repo=password_reset_repo,
        refresh_token_repo=refresh_token_repo,
        password_service=password_service,
        email_service=email_service,
        event_bus=event_bus,
    )


# ============================================================================
# Session Management Handler Factories
# ============================================================================


async def get_list_sessions_handler(
    session: AsyncSession = Depends(get_db_session),
) -> "ListSessionsHandler":
    """Get ListSessions query handler (request-scoped).

    Returns:
        ListSessionsHandler instance.
    """
    from src.application.queries.handlers.list_sessions_handler import (
        ListSessionsHandler,
    )
    from src.infrastructure.persistence.repositories import SessionRepository

    session_repo = SessionRepository(session=session)

    return ListSessionsHandler(
        session_repo=session_repo,
    )


async def get_get_session_handler(
    session: AsyncSession = Depends(get_db_session),
) -> "GetSessionHandler":
    """Get GetSession query handler (request-scoped).

    Returns:
        GetSessionHandler instance.
    """
    from src.application.queries.handlers.get_session_handler import GetSessionHandler
    from src.infrastructure.cache import RedisSessionCache
    from src.infrastructure.persistence.repositories import SessionRepository

    session_repo = SessionRepository(session=session)
    session_cache = RedisSessionCache(cache=get_cache())

    return GetSessionHandler(
        session_repo=session_repo,
        session_cache=session_cache,
    )


async def get_revoke_session_handler(
    session: AsyncSession = Depends(get_db_session),
) -> "RevokeSessionHandler":
    """Get RevokeSession command handler (request-scoped).

    Returns:
        RevokeSessionHandler instance.
    """
    from src.application.commands.handlers.revoke_session_handler import (
        RevokeSessionHandler,
    )
    from src.infrastructure.cache import RedisSessionCache
    from src.infrastructure.persistence.repositories import SessionRepository

    session_repo = SessionRepository(session=session)
    session_cache = RedisSessionCache(cache=get_cache())
    event_bus = get_event_bus()

    return RevokeSessionHandler(
        session_repo=session_repo,
        session_cache=session_cache,
        event_bus=event_bus,
    )


async def get_revoke_all_sessions_handler(
    session: AsyncSession = Depends(get_db_session),
) -> "RevokeAllSessionsHandler":
    """Get RevokeAllSessions command handler (request-scoped).

    Returns:
        RevokeAllSessionsHandler instance.
    """
    from src.application.commands.handlers.revoke_all_sessions_handler import (
        RevokeAllSessionsHandler,
    )
    from src.infrastructure.cache import RedisSessionCache
    from src.infrastructure.persistence.repositories import SessionRepository

    session_repo = SessionRepository(session=session)
    session_cache = RedisSessionCache(cache=get_cache())
    event_bus = get_event_bus()

    return RevokeAllSessionsHandler(
        session_repo=session_repo,
        session_cache=session_cache,
        event_bus=event_bus,
    )


# ============================================================================
# Token Rotation Handler Factories
# ============================================================================


async def get_trigger_global_rotation_handler(
    session: AsyncSession = Depends(get_db_session),
) -> "TriggerGlobalTokenRotationHandler":
    """Get TriggerGlobalTokenRotation command handler (request-scoped).

    Admin-only operation for global token rotation.

    Returns:
        TriggerGlobalTokenRotationHandler instance.
    """
    from src.application.commands.handlers.trigger_global_rotation_handler import (
        TriggerGlobalTokenRotationHandler,
    )
    from src.infrastructure.persistence.repositories import SecurityConfigRepository

    security_config_repo = SecurityConfigRepository(
        session=session,
        cache=get_cache(),
        cache_keys=get_cache_keys(),
    )
    event_bus = get_event_bus()

    return TriggerGlobalTokenRotationHandler(
        security_config_repo=security_config_repo,
        event_bus=event_bus,
    )


async def get_trigger_user_rotation_handler(
    session: AsyncSession = Depends(get_db_session),
) -> "TriggerUserTokenRotationHandler":
    """Get TriggerUserTokenRotation command handler (request-scoped).

    Per-user token rotation (password change, log out everywhere).

    Returns:
        TriggerUserTokenRotationHandler instance.
    """
    from src.application.commands.handlers.trigger_user_rotation_handler import (
        TriggerUserTokenRotationHandler,
    )
    from src.infrastructure.persistence.repositories import UserRepository

    user_repo = UserRepository(session=session)
    event_bus = get_event_bus()

    return TriggerUserTokenRotationHandler(
        user_repo=user_repo,
        event_bus=event_bus,
    )
