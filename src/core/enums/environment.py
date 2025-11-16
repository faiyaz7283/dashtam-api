"""Application environment types.

Defines the different runtime environments for Dashtam application.
Used by Settings to determine environment-specific behavior.

Environments:
- DEVELOPMENT: Local development with hot reload, debug mode
- TESTING: Automated test execution with isolated database
- CI: Continuous integration environment (GitHub Actions)
- PRODUCTION: Production deployment with full security
"""

from enum import Enum


class Environment(str, Enum):
    """Application environment types."""

    DEVELOPMENT = "development"
    TESTING = "testing"
    CI = "ci"
    PRODUCTION = "production"
