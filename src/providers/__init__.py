"""Provider module initialization and registration.

This module imports all available provider implementations, which triggers
their self-registration via the @register_provider decorator. This ensures
that the ProviderRegistry is populated with all available providers when
the application starts.

To add a new provider:
1. Create the provider class in its own file (e.g., chase.py)
2. Apply the @register_provider decorator
3. Import it here

The import order doesn't matter as each provider registers itself independently.
"""

# Import base components
from src.providers.base import BaseProvider, ProviderType

# Import the registry
from src.providers.registry import ProviderRegistry, register_provider

# Import all provider implementations to trigger registration
# Each import causes the @register_provider decorator to run
from src.providers.schwab import SchwabProvider

# Future providers will be imported here as they're built:
# from src.providers.chase import ChaseProvider
# from src.providers.plaid import PlaidProvider
# from src.providers.fidelity import FidelityProvider

# Export the main components for easy access
__all__ = [
    "BaseProvider",
    "ProviderType",
    "ProviderRegistry",
    "register_provider",
    "SchwabProvider",
]

# Log available providers on module load (for debugging)
import logging

logger = logging.getLogger(__name__)


def list_available_providers():
    """Log all available providers for debugging."""
    providers = ProviderRegistry.get_available_providers()
    if providers:
        logger.info(f"Available providers: {list(providers.keys())}")
        for key, metadata in providers.items():
            logger.debug(
                f"  {key}: {metadata['name']} "
                f"({metadata['provider_type']}) "
                f"- Configured: {metadata['is_configured']}"
            )
    else:
        logger.warning("No providers registered!")


# Only log in debug mode to avoid noise
if logger.isEnabledFor(logging.DEBUG):
    list_available_providers()
