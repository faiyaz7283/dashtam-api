"""UserRepository protocol for user persistence.

Port (interface) for hexagonal architecture.
Infrastructure layer implements this protocol.
"""

from typing import Protocol
from uuid import UUID

from src.domain.entities.user import User


class UserRepository(Protocol):
    """User repository protocol (port).

    Defines the interface for user persistence operations.
    Infrastructure layer provides concrete implementation.

    This is a Protocol (not ABC) for structural typing.
    Implementations don't need to inherit from this.

    Methods:
        find_by_id: Retrieve user by ID
        find_by_email: Retrieve user by email
        save: Create new user
        update: Update existing user
        delete: Delete user (soft delete)

    Example Implementation:
        >>> class UserRepository:
        ...     async def find_by_email(self, email: str) -> User | None:
        ...         # Database logic here
        ...         pass
    """

    async def find_by_id(self, user_id: UUID) -> User | None:
        """Find user by ID.

        Args:
            user_id: User's unique identifier.

        Returns:
            User if found, None otherwise.

        Example:
            >>> user = await repo.find_by_id(uuid4())
            >>> if user:
            ...     print(user.email)
        """
        ...

    async def find_by_email(self, email: str) -> User | None:
        """Find user by email address.

        Email comparison should be case-insensitive.

        Args:
            email: User's email address (case-insensitive).

        Returns:
            User if found, None otherwise.

        Example:
            >>> user = await repo.find_by_email("user@example.com")
            >>> if user:
            ...     print(user.id)
        """
        ...

    async def save(self, user: User) -> None:
        """Create new user in database.

        Args:
            user: User entity to persist.

        Raises:
            ConflictError: If email already exists.
            DatabaseError: If database operation fails.

        Example:
            >>> user = User(id=uuid4(), email="new@example.com", ...)
            >>> await repo.save(user)
        """
        ...

    async def update(self, user: User) -> None:
        """Update existing user in database.

        Args:
            user: User entity with updated fields.

        Raises:
            NotFoundError: If user doesn't exist.
            DatabaseError: If database operation fails.

        Example:
            >>> user.failed_login_attempts = 0
            >>> await repo.update(user)
        """
        ...

    async def delete(self, user_id: UUID) -> None:
        """Delete user (soft delete - sets is_active=False).

        Args:
            user_id: User's unique identifier.

        Raises:
            NotFoundError: If user doesn't exist.
            DatabaseError: If database operation fails.

        Note:
            This is a soft delete. User remains in database but is_active=False.

        Example:
            >>> await repo.delete(user_id)
        """
        ...

    async def exists_by_email(self, email: str) -> bool:
        """Check if user with email exists.

        Convenience method to check for duplicates before creation.

        Args:
            email: Email address to check (case-insensitive).

        Returns:
            True if user exists, False otherwise.

        Example:
            >>> if await repo.exists_by_email("user@example.com"):
            ...     raise ConflictError("Email already exists")
        """
        ...

    async def update_password(self, user_id: UUID, password_hash: str) -> None:
        """Update user's password hash.

        Atomic operation that only updates the password field.
        Used for password reset and password change flows.

        Args:
            user_id: User's unique identifier.
            password_hash: New bcrypt password hash.

        Raises:
            NotFoundError: If user doesn't exist.
            DatabaseError: If database operation fails.

        Example:
            >>> await repo.update_password(user_id, new_hash)
        """
        ...

    async def verify_email(self, user_id: UUID) -> None:
        """Mark user's email as verified.

        Atomic operation that sets is_verified=True.
        Used for email verification flow.

        Args:
            user_id: User's unique identifier.

        Raises:
            NotFoundError: If user doesn't exist.
            DatabaseError: If database operation fails.

        Example:
            >>> await repo.verify_email(user_id)
        """
        ...
