"""Provider Factory Protocol - Abstract factory for provider adapters.

This protocol defines the interface for creating provider adapters at runtime
based on provider slug. Used by handlers that need to resolve providers
dynamically (e.g., sync handlers that discover provider from connection).

Architecture:
- Domain layer protocol (no infrastructure imports)
- Implemented by ProviderFactory in infrastructure/providers
- Enables auto-wiring of handlers that need provider resolution

Usage:
    class SyncAccountsHandler:
        def __init__(self, ..., provider_factory: ProviderFactoryProtocol):
            self._provider_factory = provider_factory

        async def handle(self, cmd: SyncAccounts):
            connection = await self._connection_repo.find_by_id(cmd.connection_id)
            provider = self._provider_factory.get_provider(connection.provider_slug)
            # ... use provider

Reference:
    - docs/architecture/provider-integration-architecture.md
    - docs/architecture/dependency-injection.md
"""

from typing import Protocol

from src.domain.protocols.provider_protocol import ProviderProtocol


class ProviderFactoryProtocol(Protocol):
    """Protocol for provider adapter factory.

    Provides runtime resolution of provider adapters by slug.
    This enables handlers to be auto-wired without knowing the
    specific provider at construction time.

    Example:
        >>> factory: ProviderFactoryProtocol = ...
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
        ...

    def supports(self, slug: str) -> bool:
        """Check if provider slug is supported.

        Args:
            slug: Provider identifier to check.

        Returns:
            True if provider is supported and configured.
        """
        ...

    def list_supported(self) -> list[str]:
        """List all supported provider slugs.

        Returns:
            List of supported provider slugs.
        """
        ...
