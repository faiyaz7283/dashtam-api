"""Schwab provider package.

Implements ProviderProtocol for Charles Schwab integration.

Usage:
    from src.infrastructure.providers.schwab import SchwabProvider

    provider = SchwabProvider(client_id="...", client_secret="...")
    result = await provider.exchange_code_for_tokens(auth_code)
"""

from src.infrastructure.providers.schwab.schwab_provider import SchwabProvider

__all__ = ["SchwabProvider"]
