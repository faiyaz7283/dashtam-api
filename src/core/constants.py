"""Centralized constants for internal implementation details.

This module contains constants that are internal implementation details,
NOT environment-specific configuration. For environment-specific settings,
use `src/core/config.py` instead.

Categories:
- Token lengths: Fixed sizes for cryptographic tokens and keys
- Timeouts: Default timeouts for external service calls
- Prefixes: Standard protocol prefixes
- Limits: Truncation and safety limits

Reference:
    - docs/architecture/configuration.md (to be added)
    - WARP.md Section 0 (Established Configuration Pattern)

Example:
    >>> from src.core.constants import TOKEN_BYTES, BEARER_PREFIX
    >>> token = secrets.token_bytes(TOKEN_BYTES)
    >>> header = f"{BEARER_PREFIX}{access_token}"
"""

# =============================================================================
# Token and Key Lengths
# =============================================================================

TOKEN_BYTES: int = 32
"""Number of bytes for secure token generation (32 bytes = 256 bits)."""

TOKEN_HEX_LENGTH: int = 64
"""Length of hex-encoded token string (TOKEN_BYTES * 2)."""

AES_KEY_LENGTH: int = 32
"""AES-256 encryption key length in bytes."""

BCRYPT_ROUNDS_DEFAULT: int = 12
"""Default bcrypt work factor (cost parameter)."""


# =============================================================================
# Timeouts
# =============================================================================

PROVIDER_TIMEOUT_DEFAULT: float = 30.0
"""Default timeout for external provider API calls in seconds."""


# =============================================================================
# Prefixes
# =============================================================================

BEARER_PREFIX: str = "Bearer "
"""HTTP Authorization header prefix for Bearer tokens."""


# =============================================================================
# Response Limits
# =============================================================================

RESPONSE_BODY_MAX_LENGTH: int = 500
"""Maximum length for response body in error messages (truncation limit)."""


# =============================================================================
# SSE (Server-Sent Events)
# =============================================================================

SSE_HEARTBEAT_INTERVAL_SECONDS: int = 30
"""Interval between SSE heartbeat comments to detect stale connections."""

SSE_RETRY_INTERVAL_MS: int = 3000
"""Client reconnection interval hint (milliseconds)."""

SSE_CHANNEL_PREFIX: str = "sse"
"""Redis channel prefix for SSE pub/sub."""

SSE_RETENTION_MAX_LEN_DEFAULT: int = 1000
"""Default max events per user in Redis Stream retention."""

SSE_RETENTION_TTL_DEFAULT: int = 3600
"""Default TTL for retained events (seconds)."""
