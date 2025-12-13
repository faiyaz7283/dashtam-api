"""Session enrichers infrastructure package.

Provides implementations for device and location enrichment protocols.

Enrichers:
    - UserAgentDeviceEnricher: Parses user agent strings (uses user-agents library)
    - IPLocationEnricher: IP geolocation (stub - extend with GeoIP service)
"""

from src.infrastructure.enrichers.device_enricher import UserAgentDeviceEnricher
from src.infrastructure.enrichers.location_enricher import IPLocationEnricher

__all__ = [
    "IPLocationEnricher",
    "UserAgentDeviceEnricher",
]
