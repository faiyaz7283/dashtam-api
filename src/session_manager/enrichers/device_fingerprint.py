"""Device fingerprint enricher stub for session manager.

This is a STUB implementation that demonstrates the enricher interface.
Applications should implement their own device fingerprinting enricher based
on their chosen approach (user-agents library, ua-parser, custom regex, etc.).

Example Application Implementation:
    ```python
    from src.session_manager.enrichers.base import SessionEnricher
    from src.session_manager.models.base import SessionBase

    class MyDeviceFingerprintEnricher(SessionEnricher):
        def __init__(self, parser):
            # Application provides its own User-Agent parser
            self.parser = parser

        async def enrich(self, session: SessionBase) -> SessionBase:
            if session.user_agent:
                parsed = self.parser.parse(session.user_agent)
                # Update device_info with parsed results
                session.device_info = f"{parsed.browser} on {parsed.os}"
            return session
    ```

Why This Is A Stub:
- User-Agent parsing approaches vary (user-agents, ua-parser, regex)
- Each has different dependencies, accuracy, and performance
- Applications choose their approach
- Package cannot assume a specific parser
"""

import logging

from src.session_manager.enrichers.base import SessionEnricher
from src.session_manager.models.base import SessionBase

logger = logging.getLogger(__name__)


class DeviceFingerprintEnricher(SessionEnricher):
    """STUB: Device fingerprint enricher (no-op implementation).

    This stub enricher does nothing and returns sessions unchanged.
    Applications should implement their own device fingerprinting enricher
    based on their chosen User-Agent parsing approach.

    Why Stub?
    - User-Agent parsing libraries vary (user-agents, ua-parser, etc.)
    - Each has different accuracy, dependencies, and performance
    - Cannot assume which approach application uses
    - Package remains parser-agnostic

    Application Implementation:
        Applications should create their own enricher that:
        1. Accepts their User-Agent parser in __init__
        2. Parses session.user_agent to extract device info
        3. Populates session.device_info field (e.g., "Chrome on macOS")
        4. Handles errors gracefully (fail-safe)

    Example:
        >>> # Application creates custom enricher with their parser
        >>> from myapp.utils import UserAgentParser
        >>>
        >>> class MyDeviceFingerprintEnricher(SessionEnricher):
        ...     def __init__(self, parser: UserAgentParser):
        ...         self.parser = parser
        ...
        ...     async def enrich(self, session: SessionBase) -> SessionBase:
        ...         if session.user_agent:
        ...             result = self.parser.parse(session.user_agent)
        ...             session.device_info = f"{result.browser} on {result.os}"
        ...         return session
    """

    def __init__(self, fail_silently: bool = True):
        """Initialize stub device fingerprint enricher.

        Args:
            fail_silently: If True, errors don't raise exceptions (recommended)
        """
        self.fail_silently = fail_silently

    async def enrich(self, session: SessionBase) -> SessionBase:
        """STUB: Returns session unchanged (no device parsing).

        Applications should override this method with real implementation.

        Args:
            session: Session to enrich

        Returns:
            Session unchanged (stub does nothing)
        """
        logger.debug(
            "DeviceFingerprintEnricher is a stub - no device parsing performed. "
            "Application should implement custom enricher with their parser."
        )
        return session
