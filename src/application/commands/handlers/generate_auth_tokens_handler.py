"""Generate auth tokens handler.

Single responsibility: Generate JWT access token and opaque refresh token.
Does NOT authenticate users or create sessions (CQRS separation).

Flow:
1. Generate JWT access token (15 minutes)
2. Generate opaque refresh token (30 days)
3. Persist refresh token hash to database
4. Return tokens to caller

Architecture:
- Application layer ONLY imports from domain layer (entities, protocols, events)
- NO infrastructure imports (services are injected via protocols)
- Handler orchestrates token generation without knowing implementation details
"""

from src.application.commands.token_commands import AuthTokens, GenerateAuthTokens
from src.core.result import Result, Success
from src.domain.protocols import (
    RefreshTokenRepository,
    SecurityConfigRepository,
    TokenGenerationProtocol,
)
from src.domain.protocols.refresh_token_service_protocol import (
    RefreshTokenServiceProtocol,
)


class GenerateAuthTokensHandler:
    """Handler for auth token generation command.

    Single responsibility: Generate and persist authentication tokens.
    Called after successful authentication and session creation.

    Follows hexagonal architecture:
    - Application layer (this handler)
    - Domain layer (protocols for token services)
    - Infrastructure layer (JWT service, refresh token service via DI)
    """

    def __init__(
        self,
        token_service: TokenGenerationProtocol,
        refresh_token_service: RefreshTokenServiceProtocol,
        refresh_token_repo: RefreshTokenRepository,
        security_config_repo: SecurityConfigRepository,
    ) -> None:
        """Initialize token generation handler with dependencies.

        Args:
            token_service: JWT access token generation service.
            refresh_token_service: Opaque refresh token generation service.
            refresh_token_repo: Refresh token repository for persistence.
            security_config_repo: Security config repository for token versioning.
        """
        self._token_service = token_service
        self._refresh_token_service = refresh_token_service
        self._refresh_token_repo = refresh_token_repo
        self._security_config_repo = security_config_repo

    async def handle(self, cmd: GenerateAuthTokens) -> Result[AuthTokens, str]:
        """Handle auth token generation command.

        Args:
            cmd: GenerateAuthTokens command with user_id, email, roles, session_id.

        Returns:
            Success(AuthTokens) with access_token and refresh_token.

        Side Effects:
            - Persists refresh token hash to database.
        """
        # Step 1: Generate JWT access token
        access_token = self._token_service.generate_access_token(
            user_id=cmd.user_id,
            email=cmd.email,
            roles=cmd.roles,
            session_id=cmd.session_id,
        )

        # Step 2: Generate opaque refresh token
        refresh_token, token_hash = self._refresh_token_service.generate_token()

        # Step 3: Calculate expiration
        expires_at = self._refresh_token_service.calculate_expiration()

        # Step 4: Get current security config for token versioning
        security_config = await self._security_config_repo.get_or_create_default()

        # Step 5: Persist refresh token to database with version info
        await self._refresh_token_repo.save(
            user_id=cmd.user_id,
            token_hash=token_hash,
            session_id=cmd.session_id,
            expires_at=expires_at,
            token_version=security_config.global_min_token_version,
            global_version_at_issuance=security_config.global_min_token_version,
        )

        # Step 6: Return tokens
        return Success(
            value=AuthTokens(
                access_token=access_token,
                refresh_token=refresh_token,
            )
        )
