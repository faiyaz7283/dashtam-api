"""Location enricher implementation for IP geolocation.

Resolves IP addresses to geographic locations.
Currently a stub implementation - extend with MaxMind GeoIP2 or similar service.

Reference:
    - docs/architecture/session-management-architecture.md
"""

import ipaddress
import logging

from src.domain.protocols.session_enricher_protocol import LocationEnrichmentResult


logger = logging.getLogger(__name__)


class IPLocationEnricher:
    """Location enricher for IP geolocation.

    Currently returns empty results for all IPs.
    To enable geolocation, integrate with:
    - MaxMind GeoIP2 (recommended, requires license)
    - IP2Location
    - ipinfo.io API

    Implements LocationEnricher protocol (structural typing).

    Behavior:
        - Fail-open: Returns empty result on errors
        - Private IPs: Always return empty (no location data)
        - Best-effort: Unknown IPs return empty data
    """

    async def enrich(self, ip_address: str) -> LocationEnrichmentResult:
        """Resolve IP address to geographic location.

        Args:
            ip_address: Client IP address (IPv4 or IPv6).

        Returns:
            LocationEnrichmentResult with location data.
            Returns empty result for private IPs or when geolocation unavailable.
        """
        if not ip_address:
            return LocationEnrichmentResult()

        try:
            # Check if private/reserved IP
            if self._is_private_ip(ip_address):
                return LocationEnrichmentResult()

            # TODO: Integrate with geolocation service
            # For now, return empty result
            # Future implementation example:
            #
            # response = await self._geoip_client.lookup(ip_address)
            # return LocationEnrichmentResult(
            #     location=f"{response.city}, {response.country_code}",
            #     city=response.city,
            #     region=response.region,
            #     country=response.country,
            #     country_code=response.country_code,
            #     latitude=response.latitude,
            #     longitude=response.longitude,
            #     timezone=response.timezone,
            # )

            return LocationEnrichmentResult()

        except Exception as e:
            logger.warning(
                "Failed to enrich IP location",
                extra={"ip_address": ip_address, "error": str(e)},
            )
            return LocationEnrichmentResult()

    def _is_private_ip(self, ip_address: str) -> bool:
        """Check if IP address is private/reserved.

        Private IPs have no meaningful geographic location.

        Args:
            ip_address: IP address string.

        Returns:
            True if private/reserved, False if public.
        """
        try:
            ip = ipaddress.ip_address(ip_address)
            return (
                ip.is_private
                or ip.is_loopback
                or ip.is_reserved
                or ip.is_link_local
                or ip.is_multicast
            )
        except ValueError:
            # Invalid IP address format
            return True
