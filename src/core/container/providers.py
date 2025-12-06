"""Provider dependency factory.

Factory for creating financial provider adapters based on slug.
Currently supports Charles Schwab; extensible for future providers.

Reference:
    See docs/architecture/provider-integration-architecture.md for complete
    provider patterns and integration details.
"""

from typing import TYPE_CHECKING

from src.core.config import settings

if TYPE_CHECKING:
    from src.domain.protocols.provider_protocol import ProviderProtocol


# ============================================================================
# Provider Factory (Application-Scoped)
# ============================================================================


def get_provider(slug: str) -> "ProviderProtocol":
    """Get financial provider adapter by slug.

    Factory function that returns the correct provider implementation
    based on the provider slug. Follows Composition Root pattern.

    Currently supported providers:
        - 'schwab': Charles Schwab (OAuth, Trader API)

    Future providers (not yet implemented):
        - 'plaid': Plaid (aggregator)
        - 'yodlee': Yodlee (aggregator)

    Args:
        slug: Provider identifier (e.g., 'schwab', 'plaid').

    Returns:
        Provider adapter implementing ProviderProtocol.

    Raises:
        ValueError: If provider slug is unknown or provider not configured.

    Usage:
        # Application Layer (command handlers)
        from src.core.container import get_provider
        provider = get_provider("schwab")
        result = await provider.exchange_code_for_tokens(auth_code)

        # Presentation Layer (FastAPI Depends)
        # Use a dependency that calls this factory with the slug parameter

    Reference:
        - docs/architecture/provider-integration-architecture.md
    """
    match slug:
        case "schwab":
            from src.infrastructure.providers.schwab import SchwabProvider

            # Validate required settings
            if not settings.schwab_api_key or not settings.schwab_api_secret:
                raise ValueError(
                    f"Provider '{slug}' not configured. "
                    "Set SCHWAB_API_KEY and SCHWAB_API_SECRET in environment."
                )

            return SchwabProvider(settings=settings)

        # Future providers:
        # case "plaid":
        #     from src.infrastructure.providers.plaid import PlaidProvider
        #     return PlaidProvider(settings=settings)

        case _:
            raise ValueError(f"Unknown provider: {slug}. Supported: 'schwab'")
