"""Environment variables adapter for local development secrets.

Implements SecretsProtocol using environment variables from .env files.

File: env_adapter.py → class EnvAdapter (PEP 8 naming)
"""

import os

from src.core.enums import ErrorCode
from src.core.result import Failure, Result, Success
from src.domain.errors import SecretsError
from src.infrastructure.secrets.base_adapter import BaseSecretsAdapter


class EnvAdapter(BaseSecretsAdapter):
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

    # get_secret_json() inherited from BaseSecretsAdapter

    def refresh_cache(self) -> None:
        """Clear cache (no-op for environment variables).

        Environment variables are always fresh from the process environment.
        """
        pass
