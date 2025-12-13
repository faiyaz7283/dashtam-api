"""Session enricher protocol for device and location enrichment.

This module defines the port (interface) for session metadata enrichment.
Enrichers parse user agents and resolve IP addresses to locations.

Reference:
    - docs/architecture/session-management-architecture.md
"""

from dataclasses import dataclass
from typing import Protocol


@dataclass(slots=True, kw_only=True)
class DeviceEnrichmentResult:
    """Result of device information enrichment.

    Contains parsed device details from user agent string.

    Attributes:
        device_info: Human-readable device info ("Chrome on macOS").
        browser: Browser name ("Chrome", "Firefox", "Safari").
        browser_version: Browser version ("120.0.1").
        os: Operating system ("macOS", "Windows", "Android").
        os_version: OS version ("14.2", "11").
        device_type: Device category ("desktop", "mobile", "tablet").
        is_bot: Whether user agent appears to be a bot.
    """

    device_info: str | None = None
    browser: str | None = None
    browser_version: str | None = None
    os: str | None = None
    os_version: str | None = None
    device_type: str | None = None
    is_bot: bool = False


@dataclass(slots=True, kw_only=True)
class LocationEnrichmentResult:
    """Result of location enrichment from IP address.

    Contains geographic information resolved from IP.

    Attributes:
        location: Human-readable location ("New York, US").
        city: City name.
        region: State/province.
        country: Country name.
        country_code: ISO country code ("US", "CA").
        latitude: Latitude coordinate.
        longitude: Longitude coordinate.
        timezone: Timezone identifier ("America/New_York").
    """

    location: str | None = None
    city: str | None = None
    region: str | None = None
    country: str | None = None
    country_code: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    timezone: str | None = None


class DeviceEnricher(Protocol):
    """Device enricher protocol (port) for user agent parsing.

    Parses user agent strings to extract device information.
    Implementation uses libraries like user-agents.

    Behavior:
        - Fail-open: Returns empty result on errors
        - Non-blocking: Should complete quickly (<10ms)
        - Best-effort: Unknown agents return partial data

    Example:
        >>> class UserAgentDeviceEnricher:
        ...     async def enrich(self, user_agent: str) -> DeviceEnrichmentResult:
        ...         # Parse user agent with user-agents library
        ...         ...
    """

    async def enrich(self, user_agent: str) -> DeviceEnrichmentResult:
        """Parse user agent string to extract device information.

        Args:
            user_agent: Raw user agent string from HTTP header.

        Returns:
            DeviceEnrichmentResult with parsed device info.
            Returns empty result (all None) on parse failure.
        """
        ...


class LocationEnricher(Protocol):
    """Location enricher protocol (port) for IP geolocation.

    Resolves IP addresses to geographic locations.
    Implementation uses databases like IP2Location or MaxMind.

    Behavior:
        - Fail-open: Returns empty result on errors
        - Async-friendly: May involve I/O (database lookup)
        - Best-effort: Private IPs return empty data

    Example:
        >>> class IP2LocationEnricher:
        ...     async def enrich(self, ip_address: str) -> LocationEnrichmentResult:
        ...         # Look up IP in IP2Location database
        ...         ...
    """

    async def enrich(self, ip_address: str) -> LocationEnrichmentResult:
        """Resolve IP address to geographic location.

        Args:
            ip_address: Client IP address (IPv4 or IPv6).

        Returns:
            LocationEnrichmentResult with location data.
            Returns empty result (all None) for private IPs or on failure.
        """
        ...
