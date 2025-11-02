"""Session enricher abstract interface.

This module defines the SessionEnricher interface for adding
metadata to sessions (geolocation, device parsing, etc.).
"""

from abc import ABC, abstractmethod

from ..models.base import SessionBase


class SessionEnricher(ABC):
    """Abstract interface for session enrichers.

    Enrichers add metadata to sessions (decorator pattern).
    Enrichers are optional and injected via dependency injection.

    Design Pattern:
        - Decorator Pattern: Enhance sessions with additional data
        - Open-Closed: Add new enrichers without modifying interface
        - Optional: Enrichers are not required for core functionality

    Implementations:
        - GeolocationEnricher: IP → city/country
        - DeviceFingerprintEnricher: User-Agent → browser/OS
        - CustomEnricher: Application-specific enrichment

    Usage:
        ```python
        enrichers = [
            GeolocationEnricher(),
            DeviceFingerprintEnricher()
        ]

        # Service applies enrichers in order
        for enricher in enrichers:
            session = await enricher.enrich(session)
        ```

    Performance Note:
        Enrichers may call external APIs (geoip, device parser).
        Consider timeout/retry strategies and fail-safe behavior.
    """

    @abstractmethod
    async def enrich(self, session: SessionBase) -> SessionBase:
        """Enrich session with additional metadata.

        Args:
            session: Session to enrich

        Returns:
            Enriched session (modified in-place or new instance)

        Note:
            Should fail gracefully - missing enrichment is acceptable.
            Don't let enrichment failures block session creation.

        Example:
            ```python
            async def enrich(self, session: SessionBase) -> SessionBase:
                try:
                    location = await self.geoip_service.lookup(session.ip_address)
                    session.location = f"{location.city}, {location.country}"
                except Exception as e:
                    logger.warning(f"Geolocation enrichment failed: {e}")
                    # Continue without location data
                return session
            ```
        """
        pass
