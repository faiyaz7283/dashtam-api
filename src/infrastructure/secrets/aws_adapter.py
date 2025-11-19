"""AWS Secrets Manager adapter for production secrets.

Implements SecretsProtocol using AWS Secrets Manager with in-memory caching.

File: aws_adapter.py → class AWSAdapter (PEP 8 naming)
"""

from src.core.enums import ErrorCode
from src.core.result import Failure, Result, Success
from src.domain.errors import SecretsError
from src.infrastructure.secrets.base_adapter import BaseSecretsAdapter


class AWSAdapter(BaseSecretsAdapter):
    """Production secrets from AWS Secrets Manager.

    Features:
        - In-memory caching (reduce API calls, cost savings)
        - Hierarchical naming: /dashtam/{env}/{category}/{name}
        - Automatic retry with exponential backoff (boto3 default)

    Caching Strategy:
        - Cache secrets in memory to reduce AWS API calls
        - Cost: $0.05 per 10,000 API calls
        - Without cache: ~100,000 calls/month = $0.50
        - With cache: ~1,000 calls/month (startup only) = $0.005
        - Savings: 99% reduction in API costs
    """

    def __init__(self, environment: str, region: str = "us-east-1") -> None:
        """Initialize AWS Secrets Manager client.

        Args:
            environment: 'staging' or 'production'.
            region: AWS region for secrets (default: us-east-1).

        Raises:
            ImportError: If boto3 not installed.
        """
        try:
            import boto3
        except ImportError as e:
            raise ImportError(
                "boto3 required for AWS Secrets Manager. Install with: uv add boto3"
            ) from e

        self.client = boto3.client("secretsmanager", region_name=region)
        self.environment = environment
        self._cache: dict[str, str] = {}

    def get_secret(self, secret_path: str) -> Result[str, SecretsError]:
        """Get secret from AWS Secrets Manager.

        Args:
            secret_path: Path like 'database/url' or 'schwab/api_key'.

        Returns:
            Success(secret_value) if found in AWS.
            Failure(SecretsError) if not found or access denied.

        Example:
            >>> adapter = AWSAdapter(environment="production")
            >>> result = adapter.get_secret("database/url")
            >>> # Fetches from: /dashtam/production/database/url
            >>> # Success("postgresql://...")
        """
        secret_id = f"/dashtam/{self.environment}/{secret_path}"

        # Check cache first
        if secret_id in self._cache:
            return Success(value=self._cache[secret_id])

        try:
            response = self.client.get_secret_value(SecretId=secret_id)
            secret_value = response["SecretString"]

            # Cache for future calls
            self._cache[secret_id] = secret_value
            return Success(value=secret_value)

        except self.client.exceptions.ResourceNotFoundException:
            return Failure(
                error=SecretsError(
                    code=ErrorCode.SECRET_NOT_FOUND,
                    message=f"Secret not found in AWS: {secret_id}",
                )
            )
        except Exception as e:
            return Failure(
                error=SecretsError(
                    code=ErrorCode.SECRET_ACCESS_DENIED,
                    message=f"Failed to access AWS secret: {secret_id}",
                    details={"error": str(e)},
                )
            )

    # get_secret_json() inherited from BaseSecretsAdapter

    def refresh_cache(self) -> None:
        """Clear cache to force reload on next access.

        Call this after rotating secrets in AWS console or Terraform.
        Next get_secret() call will fetch fresh value from AWS.

        Example:
            >>> adapter = AWSAdapter(environment="production")
            >>> adapter.refresh_cache()  # Clear cache
            >>> result = adapter.get_secret("database/password")
            >>> # Fetches fresh from AWS
        """
        self._cache.clear()
