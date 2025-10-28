"""IP address geolocation service using MaxMind GeoLite2.

This service converts IP addresses to user-friendly location strings
for session management. Uses local MaxMind GeoLite2 database for
fast, privacy-focused lookups (no external API calls).

Performance:
- Local lookups: <1ms
- No rate limits
- No network dependency

Privacy:
- No external API calls
- City-level precision only
- Optional IP anonymization (mask last octet)

License:
- GeoLite2 database: CC BY-SA 4.0
- Requires MaxMind account (free)
- Cannot redistribute database file
"""

import logging
from pathlib import Path

import geoip2.database
from geoip2.errors import AddressNotFoundError

logger = logging.getLogger(__name__)


class GeolocationService:
    """IP address geolocation using MaxMind GeoLite2."""

    def __init__(self, db_path: Path | str):
        """Initialize geolocation service with GeoLite2 database.

        Args:
            db_path: Path to GeoLite2-City.mmdb file

        Raises:
            FileNotFoundError: If database file not found
        """
        self.db_path = Path(db_path)

        if not self.db_path.exists():
            logger.warning(
                f"GeoLite2 database not found at {self.db_path}. "
                "IP geolocation will return 'Unknown Location'. "
                "Download database: scripts/download_geolite2.sh"
            )
            self.reader = None
        else:
            self.reader = geoip2.database.Reader(str(self.db_path))
            logger.info(f"GeoLite2 database loaded from {self.db_path}")

    def get_location(self, ip_address: str) -> str:
        """Convert IP address to user-friendly location string.

        Args:
            ip_address: IPv4 or IPv6 address (e.g., '8.8.8.8', '2001:4860:4860::8888')

        Returns:
            Location string (e.g., 'San Francisco, USA', 'London, United Kingdom')
            Returns 'Unknown Location' if lookup fails or database missing

        Examples:
            >>> geo = GeolocationService('/path/to/GeoLite2-City.mmdb')
            >>> geo.get_location('8.8.8.8')
            'Mountain View, United States'
            >>> geo.get_location('invalid')
            'Unknown Location'
        """
        if self.reader is None:
            return "Unknown Location"

        try:
            response = self.reader.city(ip_address)

            # Extract city and country
            city = response.city.name or "Unknown City"
            country = response.country.name or "Unknown Country"

            return f"{city}, {country}"

        except AddressNotFoundError:
            # IP not in database (private IP, localhost, etc.)
            logger.debug(f"IP address not found in GeoLite2: {ip_address}")
            return "Unknown Location"

        except ValueError as e:
            # Invalid IP address format
            logger.warning(f"Invalid IP address format: {ip_address} - {e}")
            return "Unknown Location"

        except Exception as e:
            # Unexpected error
            logger.error(f"Geolocation lookup failed for {ip_address}: {e}")
            return "Unknown Location"

    def anonymize_ip(self, ip_address: str) -> str:
        """Anonymize IP address for privacy (mask last octet).

        Args:
            ip_address: IPv4 address (e.g., '192.168.1.100')

        Returns:
            Anonymized IP (e.g., '192.168.1.0')

        Examples:
            >>> geo.anonymize_ip('192.168.1.100')
            '192.168.1.0'
            >>> geo.anonymize_ip('2001:4860:4860::8888')
            '2001:4860:4860::'
        """
        try:
            if ":" in ip_address:
                # IPv6: mask last 16 bits
                parts = ip_address.split(":")
                return ":".join(parts[:-1]) + ":"
            else:
                # IPv4: mask last octet
                parts = ip_address.split(".")
                return ".".join(parts[:3]) + ".0"
        except Exception as e:
            logger.warning(f"IP anonymization failed for {ip_address}: {e}")
            return ip_address

    def __del__(self):
        """Close database reader on cleanup."""
        if self.reader:
            self.reader.close()


# Singleton instance (lazy initialization)
_geolocation_service: GeolocationService | None = None


def get_geolocation_service(db_path: Path | str | None = None) -> GeolocationService:
    """Get singleton GeolocationService instance.

    Args:
        db_path: Path to GeoLite2 database (only used on first call)

    Returns:
        GeolocationService instance
    """
    global _geolocation_service

    if _geolocation_service is None:
        if db_path is None:
            from src.core.config import settings

            db_path = settings.GEOLITE2_DB_PATH

        _geolocation_service = GeolocationService(db_path)

    return _geolocation_service
