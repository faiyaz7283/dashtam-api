"""Base secrets adapter with shared functionality.

Provides common implementation of get_secret_json() to avoid duplication
across EnvAdapter and AWSAdapter.

Pattern: Composition over inheritance - adapters can inherit or delegate.
"""

import json
from typing import Any

from src.core.enums import ErrorCode
from src.core.result import Failure, Result, Success
from src.domain.errors import SecretsError


class BaseSecretsAdapter:
    """Base adapter with shared secrets functionality.

    Provides shared implementation of get_secret_json() that delegates
    to the concrete adapter's get_secret() method.

    Subclasses must implement:
        - get_secret(secret_path: str) -> Result[str, SecretsError]
        - refresh_cache() -> None
    """

    def get_secret(self, secret_path: str) -> Result[str, SecretsError]:
        """Get secret value (must be implemented by subclass).

        Args:
            secret_path: Path to secret.

        Returns:
            Result with secret value or SecretsError.
        """
        raise NotImplementedError("Subclass must implement get_secret()")

    def get_secret_json(self, secret_path: str) -> Result[dict[str, Any], SecretsError]:
        """Get secret as parsed JSON dictionary.

        Shared implementation that:
        1. Calls subclass's get_secret() to fetch value
        2. Parses JSON
        3. Returns parsed dict or error

        Args:
            secret_path: Path to JSON-formatted secret.

        Returns:
            Success(parsed_dict) if valid JSON (dict[str, Any]).
            Failure(SecretsError) if not found, access denied, or invalid JSON.

        Example:
            >>> adapter = EnvAdapter()  # or AWSAdapter()
            >>> result = adapter.get_secret_json("config/json")
            >>> # Success({"key": "value"})
        """
        result = self.get_secret(secret_path)

        match result:
            case Success(value=secret_value):
                try:
                    return Success(value=json.loads(secret_value))
                except json.JSONDecodeError:
                    return Failure(
                        error=SecretsError(
                            code=ErrorCode.SECRET_INVALID_JSON,
                            message=f"Secret is not valid JSON: {secret_path}",
                        )
                    )
            case Failure(error=error):
                return Failure(error=error)

    def refresh_cache(self) -> None:
        """Clear cache (must be implemented by subclass).

        Implementation depends on adapter strategy:
        - EnvAdapter: no-op (env vars always fresh)
        - AWSAdapter: clear in-memory cache
        """
        raise NotImplementedError("Subclass must implement refresh_cache()")
