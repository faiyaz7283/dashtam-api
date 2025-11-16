"""Environment variables adapter for local development secrets.

Implements SecretsProtocol using environment variables from .env files.

File: env_adapter.py → class EnvAdapter (PEP 8 naming)
"""

import json
import os

from src.core.enums import ErrorCode
from src.core.result import Failure, Result, Success
from src.domain.errors import SecretsError


class EnvAdapter:
    """Local development secrets from .env files.

    Converts secret paths to environment variable names:
        - 'database/url' → DATABASE_URL
        - 'schwab/api_key' → SCHWAB_API_KEY

    Benefits:
        - No external dependencies
        - Works offline
        - Fast (no network calls)
        - Familiar to developers (.env files)
    """

    def __init__(self) -> None:
        """Initialize environment adapter.

        No configuration needed - reads from process environment.
        """
        pass

    def get_secret(self, secret_path: str) -> Result[str, SecretsError]:
        """Get secret from environment variable.

        Args:
            secret_path: Path like 'database/url' or 'schwab/api_key'.

        Returns:
            Success(secret_value) if env var exists.
            Failure(SecretsError) with SECRET_NOT_FOUND if env var not set.

        Example:
            >>> adapter = EnvAdapter()
            >>> result = adapter.get_secret("database/url")
            >>> # If DATABASE_URL env var exists:
            >>> # Success("postgresql://...")
            >>> # If not:
            >>> # Failure(SecretsError(code=SECRET_NOT_FOUND, ...))
        """
        env_var_name = secret_path.replace("/", "_").upper()
        secret_value = os.getenv(env_var_name)

        if secret_value is None:
            return Failure(
                error=SecretsError(
                    code=ErrorCode.SECRET_NOT_FOUND,
                    message=f"Environment variable not found: {env_var_name}",
                    details={"secret_path": secret_path},
                )
            )

        return Success(value=secret_value)

    def get_secret_json(self, secret_path: str) -> Result[dict[str, str], SecretsError]:
        """Get secret as parsed JSON dictionary.

        Args:
            secret_path: Path to JSON-formatted secret.

        Returns:
            Success(parsed_dict) if env var exists and is valid JSON.
            Failure(SecretsError) if not found or invalid JSON.

        Example:
            >>> adapter = EnvAdapter()
            >>> # If CONFIG_JSON='{"key": "value"}'
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
        """Clear cache (no-op for environment variables).

        Environment variables are always fresh from the process environment.
        """
        pass
