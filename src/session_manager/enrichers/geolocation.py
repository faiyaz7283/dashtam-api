"""Geolocation enricher stub for session manager.

This is a STUB implementation that demonstrates the enricher interface.
Applications should implement their own geolocation enricher based on their
chosen geolocation provider (MaxMind, ipapi.co, IP2Location, etc.).

Example Application Implementation:
    ```python
    from src.session_manager.enrichers.base import SessionEnricher
    from src.session_manager.models.base import SessionBase

    class MyGeolocationEnricher(SessionEnricher):
        def __init__(self, geolocation_client):
            # Application provides its own geolocation client
            self.client = geolocation_client

        async def enrich(self, session: SessionBase) -> SessionBase:
            if session.ip_address:
                location = await self.client.lookup(session.ip_address)
                session.location = location
            return session
    ```

Why This Is A Stub:
- Geolocation providers vary (MaxMind, ipapi, ipstack, IP2Location)
- Each has different APIs, licensing, and performance
- Applications choose their provider
- Package cannot assume a specific provider
"""

import logging

from src.session_manager.enrichers.base import SessionEnricher
from src.session_manager.models.base import SessionBase

logger = logging.getLogger(__name__)


class GeolocationEnricher(SessionEnricher):
    """STUB: Geolocation enricher (no-op implementation).

    This stub enricher does nothing and returns sessions unchanged.
    Applications should implement their own geolocation enricher
    based on their chosen geolocation provider.

    Why Stub?
    - Geolocation providers vary (MaxMind, ipapi.co, ipstack, etc.)
    - Each provider has different APIs and licensing
    - Cannot assume which provider application uses
    - Package remains provider-agnostic

    Application Implementation:
        Applications should create their own enricher that:
        1. Accepts their geolocation client in __init__
        2. Looks up location from session.ip_address
        3. Populates session.location field
        4. Handles errors gracefully (fail-safe)

    Example:
        >>> # Application creates custom enricher with their provider
        >>> from myapp.services import GeolocationClient
        >>>
        >>> class MyGeolocationEnricher(SessionEnricher):
        ...     def __init__(self, client: GeolocationClient):
        ...         self.client = client
        ...
        ...     async def enrich(self, session: SessionBase) -> SessionBase:
        ...         if session.ip_address:
        ...             location = self.client.lookup(session.ip_address)
        ...             session.location = location
        ...         return session
    """

    def __init__(self, fail_silently: bool = True):
        """Initialize stub geolocation enricher.

        Args:
            fail_silently: If True, errors don't raise exceptions (recommended)
        """
        self.fail_silently = fail_silently

    async def enrich(self, session: SessionBase) -> SessionBase:
        """STUB: Returns session unchanged (no geolocation lookup).

        Applications should override this method with real implementation.

        Args:
            session: Session to enrich

        Returns:
            Session unchanged (stub does nothing)
        """
        logger.debug(
            "GeolocationEnricher is a stub - no geolocation performed. "
            "Application should implement custom enricher with their provider."
        )
        return session
