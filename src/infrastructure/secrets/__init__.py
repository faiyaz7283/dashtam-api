"""Secrets infrastructure package.

This package provides secrets management adapters implementing SecretsProtocol.
All secrets dependencies are managed through src.core.container.

Architecture:
- BaseSecretsAdapter: Shared functionality (get_secret_json implementation)
- EnvAdapter: Local development (.env files) - inherits from BaseSecretsAdapter
- AWSAdapter: Production (AWS Secrets Manager with caching) - inherits from BaseSecretsAdapter
- Use src.core.container.get_secrets() for dependency injection

Multi-Tier Strategy:
- Local Development: .env files (SECRETS_BACKEND=env)
- Production: AWS Secrets Manager (SECRETS_BACKEND=aws)
- Testing: Mocked adapters (hardcoded test values)

Security:
- Read-only protocol (apps cannot modify secrets)
- Caching in adapters (reduce API costs)
- Secret naming: /dashtam/{env}/{category}/{name}
"""

from src.infrastructure.secrets.aws_adapter import AWSAdapter
from src.infrastructure.secrets.base_adapter import BaseSecretsAdapter
from src.infrastructure.secrets.env_adapter import EnvAdapter

__all__ = [
    "BaseSecretsAdapter",
    "EnvAdapter",
    "AWSAdapter",
]
