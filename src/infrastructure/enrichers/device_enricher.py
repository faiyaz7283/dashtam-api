"""Device enricher implementation using user-agents library.

Parses user agent strings to extract device, browser, and OS information.
Implements DeviceEnricher protocol with fail-open behavior.

Reference:
    - docs/architecture/session-management-architecture.md
"""

import logging

from user_agents import parse as parse_user_agent  # type: ignore[import-untyped]
from user_agents.parsers import UserAgent  # type: ignore[import-untyped]

from src.domain.protocols.session_enricher import DeviceEnrichmentResult


logger = logging.getLogger(__name__)


class UserAgentDeviceEnricher:
    """Device enricher using the user-agents library.

    Parses user agent strings using the well-maintained user-agents library
    which provides accurate browser, OS, and device detection.

    Implements DeviceEnricher protocol (structural typing).

    Behavior:
        - Fail-open: Returns empty result on parse errors
        - Non-blocking: Pure string parsing (<1ms)
        - Best-effort: Unknown agents return partial data
    """

    async def enrich(self, user_agent: str) -> DeviceEnrichmentResult:
        """Parse user agent string to extract device information.

        Args:
            user_agent: Raw user agent string from HTTP header.

        Returns:
            DeviceEnrichmentResult with parsed device info.
            Returns empty result (all None) on parse failure.
        """
        if not user_agent:
            return DeviceEnrichmentResult()

        try:
            ua: UserAgent = parse_user_agent(user_agent)

            # Extract browser info
            browser = ua.browser.family if ua.browser.family else None
            browser_version = (
                ua.browser.version_string if ua.browser.version_string else None
            )

            # Extract OS info
            os_name = ua.os.family if ua.os.family else None
            os_version = ua.os.version_string if ua.os.version_string else None

            # Determine device type
            device_type = self._determine_device_type(ua)

            # Check if bot
            is_bot = ua.is_bot

            # Build human-readable device info
            device_info = self._build_device_info(browser, os_name)

            return DeviceEnrichmentResult(
                device_info=device_info,
                browser=browser,
                browser_version=browser_version,
                os=os_name,
                os_version=os_version,
                device_type=device_type,
                is_bot=is_bot,
            )

        except Exception as e:
            logger.warning(
                "Failed to parse user agent",
                extra={"user_agent": user_agent[:100], "error": str(e)},
            )
            return DeviceEnrichmentResult()

    def _determine_device_type(self, ua: UserAgent) -> str:
        """Determine device type from parsed user agent.

        Args:
            ua: Parsed UserAgent object.

        Returns:
            Device type: "mobile", "tablet", "pc", or "other".
        """
        if ua.is_mobile:
            return "mobile"
        if ua.is_tablet:
            return "tablet"
        if ua.is_pc:
            return "desktop"
        return "other"

    def _build_device_info(
        self,
        browser: str | None,
        os_name: str | None,
    ) -> str | None:
        """Build human-readable device info string.

        Args:
            browser: Browser name.
            os_name: OS name.

        Returns:
            Human-readable string like "Chrome on Mac OS X", or None.
        """
        if browser and os_name:
            return f"{browser} on {os_name}"
        if browser:
            return browser
        if os_name:
            return f"Unknown browser on {os_name}"
        return None
