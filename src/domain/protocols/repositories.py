"""Repository protocols (ports) for domain layer.

This module defines the repository interfaces that the domain layer
needs. These are protocols (ports) that will be implemented by
the infrastructure layer (adapters).

Following hexagonal architecture:
- Domain defines what it needs (protocols/ports)
- Infrastructure provides implementations (adapters)
- Domain has no knowledge of how data is stored
"""

from typing import Protocol, TypeVar
from uuid import UUID

# Generic type for entities
T = TypeVar("T")


class BaseRepository(Protocol[T]):
    """Base repository protocol defining common operations.

    This is a generic protocol that all repositories should implement.
    It defines the basic CRUD operations that domain entities need.

    The infrastructure layer will provide concrete implementations
    that work with specific databases (PostgreSQL, MongoDB, etc.)
    """

    async def save(self, entity: T) -> None:
        """Save an entity to the repository.

        Args:
            entity: The domain entity to save.
        """
        ...

    async def find_by_id(self, entity_id: UUID) -> T | None:
        """Find an entity by its ID.

        Args:
            entity_id: The UUID of the entity to find.

        Returns:
            The entity if found, None otherwise.
        """
        ...

    async def delete(self, entity: T) -> None:
        """Delete an entity from the repository.

        Args:
            entity: The entity to delete.
        """
        ...

    async def exists(self, entity_id: UUID) -> bool:
        """Check if an entity exists.

        Args:
            entity_id: The UUID of the entity to check.

        Returns:
            True if the entity exists, False otherwise.
        """
        ...
