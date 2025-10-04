"""Pydantic schemas for API request/response validation.

This package contains all Pydantic models used for:
- Request validation (input from clients)
- Response serialization (output to clients)
- OpenAPI documentation generation
- Type safety across the API layer

Organization:
- auth.py: Authentication and user management schemas
- provider.py: Provider management schemas
- common.py: Shared/common schemas used across modules
"""

# Import will be done lazily to avoid circular imports at module load time
# Users should import directly from submodules:
#   from src.schemas.auth import LoginRequest
#   from src.schemas.provider import ProviderTypeInfo
#   from src.schemas.common import MessageResponse

__all__ = [
    # Schemas are exported from their respective modules
    "auth",
    "provider",
    "common",
]
