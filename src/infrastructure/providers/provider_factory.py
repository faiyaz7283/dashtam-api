"""Provider Factory Implementation.

Concrete implementation of ProviderFactoryProtocol that resolves
provider adapters at runtime based on slug. Delegates to existing
get_provider() function from container.

Architecture:
- Infrastructure layer implementation
- Implements ProviderFactoryProtocol from domain
- Used as app-scoped singleton via get_provider_factory()

Reference:
    - docs/architecture/provider-integration-architecture.md
    - docs/architecture/dependency-injection.md
"""

from src.core.config import settings
from src.domain.protocols.provider_protocol import ProviderProtocol
from src.domain.providers.registry import (
    PROVIDER_REGISTRY,
    get_provider_metadata,
)


class ProviderFactory:
    """Concrete provider factory implementation.

    Provides runtime resolution of provider adapters by slug.
    Validates configuration before instantiating providers.

    Example:
        >>> factory = ProviderFactory()
        >>> provider = factory.get_provider("schwab")
        >>> result = await provider.fetch_accounts(credentials)
    """

    def get_provider(self, slug: str) -> ProviderProtocol:
        """Get provider adapter by slug.

        Args:
            slug: Provider identifier (e.g., 'schwab', 'alpaca', 'chase_file').

        Returns:
            Provider adapter implementing ProviderProtocol.

        Raises:
            ValueError: If provider slug is unknown or not configured.
        """
        # Lookup metadata from registry
        metadata = get_provider_metadata(slug)
        if not metadata:
            supported = ", ".join([p.slug for p in PROVIDER_REGISTRY])
            raise ValueError(f"Unknown provider: {slug}. Supported: {supported}")

        # Validate required settings (registry-driven)
        if metadata.required_settings:
            for setting_name in metadata.required_settings:
                if not getattr(settings, setting_name, None):
                    required = ", ".join(metadata.required_settings)
                    raise ValueError(
                        f"Provider '{slug}' not configured. Required settings: {required}"
                    )

        # Lazy import and instantiate (avoid circular imports)
        match slug:
            case "schwab":
                from src.infrastructure.providers.schwab import SchwabProvider

                return SchwabProvider(settings=settings)

            case "alpaca":
                from src.infrastructure.providers.alpaca import AlpacaProvider

                return AlpacaProvider(settings=settings)

            case "chase_file":
                from src.infrastructure.providers.chase import ChaseFileProvider

                return ChaseFileProvider()

            case _:
                raise ValueError(
                    f"Provider '{slug}' in registry but no factory defined. "
                    "This is a bug - please report to maintainers."
                )

    def supports(self, slug: str) -> bool:
        """Check if provider slug is supported.

        Args:
            slug: Provider identifier to check.

        Returns:
            True if provider is supported and configured.
        """
        metadata = get_provider_metadata(slug)
        if not metadata:
            return False

        # Check if required settings are present
        if metadata.required_settings:
            for setting_name in metadata.required_settings:
                if not getattr(settings, setting_name, None):
                    return False

        return True

    def list_supported(self) -> list[str]:
        """List all supported provider slugs.

        Returns:
            List of supported provider slugs that are configured.
        """
        return [p.slug for p in PROVIDER_REGISTRY if self.supports(p.slug)]
