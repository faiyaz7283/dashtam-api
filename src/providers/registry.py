"""Provider registry system for managing available financial providers.

This module implements a self-registering provider system where each provider
class automatically registers itself when imported. The registry serves as the
single source of truth for which providers are available in the system.

The registry is application-level (runtime) and works in conjunction with the
database which stores user-specific provider instances.
"""

from typing import Dict, Type, Optional, List
from src.providers.base import BaseProvider, ProviderType


class ProviderRegistry:
    """Central registry for all available financial providers.

    This registry maintains a mapping of provider keys to their implementation
    classes and metadata. Providers register themselves using the @register_provider
    decorator when their modules are imported.

    The registry serves as the bridge between:
    - Database records (which store provider_key as strings)
    - Provider classes (actual implementation)
    """

    _providers: Dict[str, Type[BaseProvider]] = {}
    _provider_metadata: Dict[str, dict] = {}

    @classmethod
    def register(
        cls,
        key: str,
        provider_class: Type[BaseProvider],
        name: str,
        provider_type: ProviderType,
        description: str = "",
        icon_url: Optional[str] = None,
        supported_features: Optional[List[str]] = None,
    ) -> None:
        """Register a provider in the system.

        This method is called automatically by the @register_provider decorator
        when a provider class is defined.

        Args:
            key: Unique identifier for the provider (e.g., 'schwab').
            provider_class: The provider implementation class.
            name: Official name of the institution (e.g., 'Charles Schwab').
            provider_type: Category of provider (brokerage, banking, etc.).
            description: Brief description of the provider.
            icon_url: Path to provider's icon/logo.
            supported_features: List of features this provider supports.

        Raises:
            ValueError: If a provider with the same key is already registered.
        """
        if key in cls._providers:
            raise ValueError(f"Provider '{key}' is already registered")

        cls._providers[key] = provider_class
        cls._provider_metadata[key] = {
            "key": key,
            "name": name,
            "provider_type": provider_type.value
            if isinstance(provider_type, ProviderType)
            else provider_type,
            "description": description,
            "icon_url": icon_url,
            "supported_features": supported_features or [],
            "is_configured": cls._check_provider_configuration(provider_class),
        }

    @classmethod
    def _check_provider_configuration(cls, provider_class: Type[BaseProvider]) -> bool:
        """Check if a provider has necessary configuration.

        Creates a temporary instance to check if the provider has required
        API credentials configured.

        Args:
            provider_class: The provider class to check.

        Returns:
            True if provider is properly configured, False otherwise.
        """
        try:
            instance = provider_class()
            return instance.is_configured
        except Exception:
            return False

    @classmethod
    def get_provider_class(cls, key: str) -> Type[BaseProvider]:
        """Get a provider implementation class by key.

        Args:
            key: The provider key (e.g., 'schwab').

        Returns:
            The provider implementation class.

        Raises:
            ValueError: If provider key is not registered.
        """
        if key not in cls._providers:
            available = ", ".join(cls._providers.keys())
            raise ValueError(
                f"Provider '{key}' not found. Available providers: {available}"
            )
        return cls._providers[key]

    @classmethod
    def create_provider_instance(cls, key: str) -> BaseProvider:
        """Create an instance of a provider by key.

        Args:
            key: The provider key (e.g., 'schwab').

        Returns:
            An instance of the provider class.

        Raises:
            ValueError: If provider key is not registered.
        """
        provider_class = cls.get_provider_class(key)
        return provider_class()

    @classmethod
    def get_available_providers(cls) -> Dict[str, dict]:
        """Get all available providers and their metadata.

        Returns:
            Dictionary mapping provider keys to their metadata.
        """
        return cls._provider_metadata.copy()

    @classmethod
    def get_configured_providers(cls) -> Dict[str, dict]:
        """Get only providers that are properly configured.

        Returns:
            Dictionary of providers that have necessary API credentials.
        """
        return {
            key: metadata
            for key, metadata in cls._provider_metadata.items()
            if metadata["is_configured"]
        }

    @classmethod
    def is_provider_available(cls, key: str) -> bool:
        """Check if a provider is registered and available.

        Args:
            key: The provider key to check.

        Returns:
            True if provider is registered, False otherwise.
        """
        return key in cls._providers

    @classmethod
    def is_provider_configured(cls, key: str) -> bool:
        """Check if a provider is properly configured.

        Args:
            key: The provider key to check.

        Returns:
            True if provider is configured, False otherwise.
        """
        if key not in cls._provider_metadata:
            return False
        return cls._provider_metadata[key]["is_configured"]

    @classmethod
    def get_provider_metadata(cls, key: str) -> dict:
        """Get metadata for a specific provider.

        Args:
            key: The provider key.

        Returns:
            Dictionary containing provider metadata.

        Raises:
            ValueError: If provider key is not registered.
        """
        if key not in cls._provider_metadata:
            raise ValueError(f"Provider '{key}' not found")
        return cls._provider_metadata[key].copy()

    @classmethod
    def get_providers_by_type(cls, provider_type: ProviderType) -> Dict[str, dict]:
        """Get all providers of a specific type.

        Args:
            provider_type: The type of providers to retrieve.

        Returns:
            Dictionary of providers matching the specified type.
        """
        return {
            key: metadata
            for key, metadata in cls._provider_metadata.items()
            if metadata["provider_type"] == provider_type.value
        }

    @classmethod
    def clear_registry(cls) -> None:
        """Clear the registry (mainly for testing).

        Warning: This removes all registered providers. Only use in tests.
        """
        cls._providers.clear()
        cls._provider_metadata.clear()


def register_provider(
    key: str,
    name: str,
    provider_type: ProviderType,
    description: str = "",
    icon_url: Optional[str] = None,
    supported_features: Optional[List[str]] = None,
):
    """Decorator to register a provider class.

    This decorator should be applied to provider classes to automatically
    register them in the ProviderRegistry when the module is imported.

    Args:
        key: Unique identifier for the provider (e.g., 'schwab').
        name: Official name of the institution (e.g., 'Charles Schwab').
        provider_type: Category of provider.
        description: Brief description of the provider.
        icon_url: Path to provider's icon/logo.
        supported_features: List of features this provider supports.

    Returns:
        The decorated class unchanged.

    Example:
        >>> @register_provider(
        ...     key="schwab",
        ...     name="Charles Schwab",
        ...     provider_type=ProviderType.BROKERAGE
        ... )
        ... class SchwabProvider(BaseProvider):
        ...     pass
    """

    def decorator(provider_class: Type[BaseProvider]) -> Type[BaseProvider]:
        """Inner decorator function that performs the registration.

        Args:
            provider_class: The provider class to register.

        Returns:
            The unmodified provider class.
        """
        ProviderRegistry.register(
            key=key,
            provider_class=provider_class,
            name=name,
            provider_type=provider_type,
            description=description,
            icon_url=icon_url,
            supported_features=supported_features,
        )
        return provider_class

    return decorator
