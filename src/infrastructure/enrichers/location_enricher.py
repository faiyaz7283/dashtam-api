"""Location enricher implementation for IP geolocation.

Resolves IP addresses to geographic locations using MaxMind GeoIP2.

Implementation:
    - Uses GeoLite2-City database for city-level geolocation
    - Fail-open: Returns empty result on any errors
    - Private IPs: Returns empty (no meaningful location)
    - TODO: F7.3 - Automate monthly database updates via background jobs

Reference:
    - docs/architecture/session-management-architecture.md
    - MaxMind GeoIP2: https://dev.maxmind.com/geoip/docs/databases/city-and-country
"""

import ipaddress
from pathlib import Path

import geoip2.database
import geoip2.errors

from src.core.config import settings
from src.domain.protocols.logger_protocol import LoggerProtocol
from src.domain.protocols.session_enricher_protocol import LocationEnrichmentResult


class IPLocationEnricher:
    """Location enricher for IP geolocation using MaxMind GeoIP2.

    Uses GeoLite2-City database to resolve IP addresses to geographic locations.
    Database is updated monthly (manual for now, automated in F7.3).

    Implements LocationEnricher protocol (structural typing).

    Behavior:
        - Fail-open: Returns empty result on errors (never blocks session creation)
        - Private IPs: Always return empty (no meaningful location data)
        - Best-effort: Unknown IPs return empty data
        - Lazy loading: Database reader initialized on first use

    Args:
        db_path: Path to GeoLite2-City.mmdb file. If None, geolocation is disabled.
    """

    def __init__(
        self,
        logger: LoggerProtocol,
        db_path: str | None = None,
    ) -> None:
        """Initialize location enricher.

        Args:
            logger: Logger for error/debug messages.
            db_path: Path to GeoIP2 database file. Defaults to settings.geoip_db_path.
        """
        self._logger = logger
        self._db_path = db_path or settings.geoip_db_path
        self._reader: geoip2.database.Reader | None = None

    async def enrich(self, ip_address: str) -> LocationEnrichmentResult:
        """Resolve IP address to geographic location using GeoIP2.

        Args:
            ip_address: Client IP address (IPv4 or IPv6).

        Returns:
            LocationEnrichmentResult with location data.
            Returns empty result for:
            - Private/reserved IPs (no meaningful location)
            - Database not configured or missing
            - IP not found in database
            - Any lookup errors (fail-open)
        """
        if not ip_address:
            return LocationEnrichmentResult()

        try:
            # Check if private/reserved IP (no lookup needed)
            if self._is_private_ip(ip_address):
                return LocationEnrichmentResult()

            # Check if database is configured
            if not self._db_path:
                self._logger.debug(
                    "GeoIP database not configured (geoip_db_path is None)"
                )
                return LocationEnrichmentResult()

            # Lazy load database reader
            if self._reader is None:
                self._init_reader()

            # If reader still None (init failed), return empty
            if self._reader is None:
                return LocationEnrichmentResult()

            # Lookup IP in GeoIP2 database
            response = self._reader.city(ip_address)

            # Extract location data (all fields optional in GeoIP2)
            city = response.city.name if response.city.name else None
            country_code = (
                response.country.iso_code if response.country.iso_code else None
            )
            latitude = (
                response.location.latitude if response.location.latitude else None
            )
            longitude = (
                response.location.longitude if response.location.longitude else None
            )

            # Format location string: "City, CC" or "CC" if no city
            location = None
            if city and country_code:
                location = f"{city}, {country_code}"
            elif country_code:
                location = country_code

            return LocationEnrichmentResult(
                location=location,
                city=city,
                country_code=country_code,
                latitude=latitude,
                longitude=longitude,
            )

        except geoip2.errors.AddressNotFoundError:
            # IP not in database (common for some IP ranges)
            self._logger.debug(
                "IP not found in GeoIP database",
                ip_address=ip_address,
            )
            return LocationEnrichmentResult()

        except Exception as e:
            # Any other error: fail-open (log warning, return empty)
            self._logger.warning(
                "Failed to enrich IP location",
                ip_address=ip_address,
                error=str(e),
            )
            return LocationEnrichmentResult()

    def _init_reader(self) -> None:
        """Initialize GeoIP2 database reader (lazy loading).

        Called on first use. If initialization fails, logs warning and sets
        reader to None (geolocation disabled).
        """
        try:
            if not self._db_path:
                return

            db_file = Path(self._db_path)
            if not db_file.exists():
                self._logger.warning(
                    "GeoIP database file not found",
                    db_path=self._db_path,
                )
                return

            self._reader = geoip2.database.Reader(str(db_file))
            self._logger.info(
                "GeoIP database loaded successfully",
                db_path=self._db_path,
            )

        except Exception as e:
            self._logger.warning(
                "Failed to initialize GeoIP database",
                db_path=self._db_path,
                error=str(e),
            )
            self._reader = None

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
