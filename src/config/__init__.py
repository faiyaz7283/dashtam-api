"""Application configuration package.

This package contains Dashtam-specific configuration modules that use
generic components from other packages.

Modules:
    rate_limits: Rate limit rules for API endpoints (uses src/rate_limiter)
"""

from src.config.rate_limits import (
    RATE_LIMIT_RULES,
    get_rate_limit_rule,
    has_rate_limit,
    get_all_rate_limit_rules,
    get_enabled_rate_limit_rules,
)

__all__ = [
    "RATE_LIMIT_RULES",
    "get_rate_limit_rule",
    "has_rate_limit",
    "get_all_rate_limit_rules",
    "get_enabled_rate_limit_rules",
]
