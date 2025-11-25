"""UserRepository - SQLAlchemy implementation of UserRepository protocol.

Adapter for hexagonal architecture.
Maps between domain User entities and database UserModel.
"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.user import User
from src.infrastructure.persistence.models.user import User as UserModel


class UserRepository:
    """SQLAlchemy implementation of UserRepository protocol.

    This is an adapter that implements the UserRepository port.
    It handles the mapping between domain User entities and database UserModel.

    This class does NOT inherit from UserRepository protocol (Protocol uses structural typing).

    Attributes:
        session: SQLAlchemy async session for database operations.

    Example:
        >>> async with get_session() as session:
        ...     repo = UserRepository(session)
        ...     user = await repo.find_by_email("user@example.com")
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository with database session.

        Args:
            session: SQLAlchemy async session.
        """
        self.session = session

    async def find_by_id(self, user_id: UUID) -> User | None:
        """Find user by ID.

        Args:
            user_id: User's unique identifier.

        Returns:
            Domain User entity if found, None otherwise.
        """
        stmt = select(UserModel).where(UserModel.id == user_id)
        result = await self.session.execute(stmt)
        user_model = result.scalar_one_or_none()

        if user_model is None:
            return None

        return self._to_domain(user_model)

    async def find_by_email(self, email: str) -> User | None:
        """Find user by email address.

        Email comparison is case-insensitive using PostgreSQL ILIKE.

        Args:
            email: User's email address (case-insensitive).

        Returns:
            Domain User entity if found, None otherwise.
        """
        stmt = select(UserModel).where(UserModel.email.ilike(email))
        result = await self.session.execute(stmt)
        user_model = result.scalar_one_or_none()

        if user_model is None:
            return None

        return self._to_domain(user_model)

    async def save(self, user: User) -> None:
        """Create new user in database.

        Args:
            user: Domain User entity to persist.

        Raises:
            IntegrityError: If email already exists (caught by SQLAlchemy).
        """
        user_model = self._to_model(user)
        self.session.add(user_model)
        await self.session.commit()
        await self.session.refresh(user_model)

    async def update(self, user: User) -> None:
        """Update existing user in database.

        Args:
            user: Domain User entity with updated fields.

        Raises:
            NoResultFound: If user doesn't exist (caught by SQLAlchemy).
        """
        stmt = select(UserModel).where(UserModel.id == user.id)
        result = await self.session.execute(stmt)
        user_model = result.scalar_one()

        # Update fields from domain entity
        user_model.email = user.email
        user_model.password_hash = user.password_hash
        user_model.is_verified = user.is_verified
        user_model.is_active = user.is_active
        user_model.failed_login_attempts = user.failed_login_attempts
        user_model.locked_until = user.locked_until
        user_model.updated_at = user.updated_at

        await self.session.commit()
        await self.session.refresh(user_model)

    async def delete(self, user_id: UUID) -> None:
        """Delete user (soft delete - sets is_active=False).

        Args:
            user_id: User's unique identifier.

        Raises:
            NoResultFound: If user doesn't exist (caught by SQLAlchemy).
        """
        stmt = select(UserModel).where(UserModel.id == user_id)
        result = await self.session.execute(stmt)
        user_model = result.scalar_one()

        # Soft delete
        user_model.is_active = False

        await self.session.commit()
        await self.session.refresh(user_model)

    async def exists_by_email(self, email: str) -> bool:
        """Check if user with email exists.

        Args:
            email: Email address to check (case-insensitive).

        Returns:
            True if user exists, False otherwise.
        """
        stmt = select(UserModel.id).where(UserModel.email.ilike(email))
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none() is not None

    def _to_domain(self, user_model: UserModel) -> User:
        """Convert database model to domain entity.

        Args:
            user_model: SQLAlchemy UserModel instance.

        Returns:
            Domain User entity.
        """
        return User(
            id=user_model.id,
            email=user_model.email,
            password_hash=user_model.password_hash,
            is_verified=user_model.is_verified,
            is_active=user_model.is_active,
            failed_login_attempts=user_model.failed_login_attempts,
            locked_until=user_model.locked_until,
            created_at=user_model.created_at,
            updated_at=user_model.updated_at,
        )

    def _to_model(self, user: User) -> UserModel:
        """Convert domain entity to database model.

        Args:
            user: Domain User entity.

        Returns:
            SQLAlchemy UserModel instance.
        """
        return UserModel(
            id=user.id,
            email=user.email,
            password_hash=user.password_hash,
            is_verified=user.is_verified,
            is_active=user.is_active,
            failed_login_attempts=user.failed_login_attempts,
            locked_until=user.locked_until,
            created_at=user.created_at,
            updated_at=user.updated_at,
        )
