"""Secrets management protocol (port) for hexagonal architecture.

This protocol defines what the domain needs from a secrets management system.
Infrastructure layer provides concrete implementations (adapters).

Protocol Pattern:
    - Domain defines the PORT (this protocol)
    - Infrastructure implements ADAPTERS (EnvAdapter, AWSAdapter, VaultAdapter)
    - Application uses protocol (backend-agnostic)
"""

from typing import Protocol

from src.domain.errors import SecretsError
from src.core.result import Result


class SecretsProtocol(Protocol):
    """Protocol for secrets management systems.

    Applications are READ-ONLY consumers of secrets.
    Secret provisioning is an admin operation (Terraform, AWS CLI, web console).

    Implementations:
        - EnvAdapter: Local development (.env files)
        - AWSAdapter: Production (AWS Secrets Manager)
        - VaultAdapter: Alternative (HashiCorp Vault)
    """

    def get_secret(self, secret_path: str) -> Result[str, SecretsError]:
        """Get single secret value.

        Args:
            secret_path: Path like 'database/url' or 'schwab/api_key'.

        Returns:
            Success(secret_value) if found.
            Failure(SecretsError) if not found or access denied.
        """
        ...

    def get_secret_json(self, secret_path: str) -> Result[dict[str, str], SecretsError]:
        """Get secret as parsed JSON dictionary.

        Args:
            secret_path: Path to JSON-formatted secret.

        Returns:
            Success(parsed_json) if valid JSON.
            Failure(SecretsError) if not found, access denied, or invalid JSON.
        """
        ...

    def refresh_cache(self) -> None:
        """Clear cached secrets to reload after rotation.

        Call this after rotating secrets in backend system.
        Next get_secret() call will fetch fresh value.
        """
        ...
