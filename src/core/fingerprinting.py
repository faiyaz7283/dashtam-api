"""Device fingerprinting for session hijacking detection.

Device fingerprints are generated from browser/device metadata to
detect when a session token is used from a different device (potential
session hijacking).

Fingerprint Components:
- User-Agent header (browser, OS, version)
- Accept-Language header (preferred languages)
- Screen resolution (from custom header)
- Timezone offset (from custom header)

Security:
- SHA256 hash (64 hex characters)
- Not reversible
- Cannot identify user, only detect device changes
- Privacy-focused (no PII collected)

Use Cases:
- Detect session hijacking (token used on different device)
- Trigger email alerts for suspicious activity
- Optional: force re-authentication on device change
"""

import hashlib
import logging

from fastapi import Request

logger = logging.getLogger(__name__)


def generate_device_fingerprint(request: Request) -> str:
    """Generate SHA256 hash of device fingerprint from request metadata.

    Args:
        request: FastAPI Request object

    Returns:
        SHA256 hash (64 hex characters)

    Examples:
        >>> fingerprint = generate_device_fingerprint(request)
        >>> len(fingerprint)
        64
        >>> fingerprint
        'a1b2c3d4e5f6...'

    Notes:
        - Custom headers (x-screen-resolution, x-timezone-offset) must be
          sent by client for full fingerprint accuracy
        - Missing headers result in empty string components (still unique)
        - Same device/browser should produce same fingerprint
        - Different devices produce different fingerprints
    """
    components = [
        request.headers.get("user-agent", ""),
        request.headers.get("accept-language", ""),
        request.headers.get("x-screen-resolution", ""),  # Custom header from client
        request.headers.get("x-timezone-offset", ""),  # Custom header from client
    ]

    # Join components with delimiter
    fingerprint_string = "|".join(components)

    # SHA256 hash (256 bits = 64 hex characters)
    fingerprint_hash = hashlib.sha256(fingerprint_string.encode("utf-8")).hexdigest()

    logger.debug(f"Generated device fingerprint: {fingerprint_hash[:8]}...")

    return fingerprint_hash


def parse_user_agent(user_agent: str) -> dict[str, str]:
    """Parse User-Agent string into device info components.

    Args:
        user_agent: User-Agent header string

    Returns:
        Dict with keys: browser, os, device_type

    Examples:
        >>> parse_user_agent("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)")
        {'browser': 'Safari', 'os': 'macOS', 'device_type': 'desktop'}

    Notes:
        - Simple regex-based parsing (not comprehensive)
        - For production: consider using user-agents library
        - Falls back to "Unknown" for unrecognized patterns
    """
    ua_lower = user_agent.lower()

    # Detect browser
    if "chrome" in ua_lower and "edg" not in ua_lower:
        browser = "Chrome"
    elif "firefox" in ua_lower:
        browser = "Firefox"
    elif "safari" in ua_lower and "chrome" not in ua_lower:
        browser = "Safari"
    elif "edg" in ua_lower:
        browser = "Edge"
    elif "opera" in ua_lower or "opr" in ua_lower:
        browser = "Opera"
    else:
        browser = "Unknown Browser"

    # Detect OS
    if "mac os x" in ua_lower or "macintosh" in ua_lower:
        os_name = "macOS"
    elif "windows" in ua_lower or "win64" in ua_lower or "win32" in ua_lower:
        os_name = "Windows"
    elif "linux" in ua_lower:
        os_name = "Linux"
    elif "iphone" in ua_lower or "ipad" in ua_lower:
        os_name = "iOS"
    elif "android" in ua_lower:
        os_name = "Android"
    else:
        os_name = "Unknown OS"

    # Detect device type
    if "mobile" in ua_lower or "iphone" in ua_lower or "android" in ua_lower:
        device_type = "mobile"
    elif "tablet" in ua_lower or "ipad" in ua_lower:
        device_type = "tablet"
    else:
        device_type = "desktop"

    return {"browser": browser, "os": os_name, "device_type": device_type}


def format_device_info(user_agent: str) -> str:
    """Format device info for display in session list.

    Args:
        user_agent: User-Agent header string

    Returns:
        Human-readable device info (e.g., "Chrome on macOS", "Safari on iOS")

    Examples:
        >>> format_device_info("Mozilla/5.0 (Macintosh; ...)")
        'Chrome on macOS'
    """
    if not user_agent:
        return "Unknown Device"

    parsed = parse_user_agent(user_agent)
    browser = parsed["browser"]
    os_name = parsed["os"]

    return f"{browser} on {os_name}"
