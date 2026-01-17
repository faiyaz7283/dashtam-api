"""Unit tests for handler_factory module.

Tests the automatic dependency injection system for CQRS handlers.
This module is critical infrastructure - it replaces ~1321 lines of
manual factory functions.

Test Strategy:
- Unit tests with mocked dependencies
- Test each function in isolation
- Cover error paths and edge cases
- Verify FastAPI integration patterns
"""

import pytest
from typing import Protocol
from unittest.mock import MagicMock, patch

from src.core.container.handler_factory import (
    REPOSITORY_TYPES,
    SINGLETON_TYPES,
    analyze_handler_dependencies,
    clear_handler_factory_cache,
    create_handler,
    get_all_handler_factories,
    get_supported_dependencies,
    get_type_name,
    handler_factory,
)


# =============================================================================
# Test Fixtures - Mock Handler Classes
# =============================================================================


class MockUserRepository(Protocol):
    """Mock repository protocol for testing."""

    async def find_by_id(self, user_id: str) -> dict[str, str] | None: ...


class MockEventBusProtocol(Protocol):
    """Mock event bus protocol for testing."""

    async def publish(self, event: object) -> None: ...


class SimpleHandler:
    """Handler with no dependencies."""

    def __init__(self) -> None:
        pass

    async def handle(self, cmd: object) -> str:
        return "success"


class SingleDependencyHandler:
    """Handler with one repository dependency."""

    def __init__(self, user_repo: "MockUserRepository") -> None:
        self._user_repo = user_repo

    async def handle(self, cmd: object) -> str:
        return "success"


class MultipleDependencyHandler:
    """Handler with multiple dependencies."""

    def __init__(
        self,
        user_repo: "MockUserRepository",
        event_bus: "MockEventBusProtocol",
    ) -> None:
        self._user_repo = user_repo
        self._event_bus = event_bus

    async def handle(self, cmd: object) -> str:
        return "success"


class OptionalDependencyHandler:
    """Handler with optional dependency."""

    def __init__(
        self,
        user_repo: "MockUserRepository",
        optional_service: "MockEventBusProtocol | None" = None,
    ) -> None:
        self._user_repo = user_repo
        self._optional = optional_service

    async def handle(self, cmd: object) -> str:
        return "success"


# =============================================================================
# Test get_type_name
# =============================================================================


@pytest.mark.unit
class TestGetTypeName:
    """Tests for get_type_name() function."""

    def test_extracts_name_from_class(self) -> None:
        """Should extract class name from type."""

        class MyClass:
            pass

        result = get_type_name(MyClass)
        assert result == "MyClass"

    def test_extracts_name_from_string_annotation(self) -> None:
        """Should handle string forward references."""
        result = get_type_name("MyModule.MyClass")
        assert result == "MyClass"

    def test_handles_none(self) -> None:
        """Should handle None annotation."""
        result = get_type_name(None)
        assert result == "None"

    def test_handles_optional_type(self) -> None:
        """Should extract inner type from Optional."""
        from typing import Optional

        # Optional[str] is Union[str, None]
        result = get_type_name(Optional[str])
        assert result == "str"

    def test_handles_union_with_none(self) -> None:
        """Should extract first non-None type from Union."""
        # Using modern syntax
        from typing import Union

        result = get_type_name(Union[int, None])
        assert result == "int"


# =============================================================================
# Test analyze_handler_dependencies
# =============================================================================


@pytest.mark.unit
class TestAnalyzeHandlerDependencies:
    """Tests for analyze_handler_dependencies() function."""

    def test_returns_empty_for_no_dependencies(self) -> None:
        """Handler with no __init__ params returns empty dict."""
        deps = analyze_handler_dependencies(SimpleHandler)
        assert deps == {}

    def test_extracts_single_dependency(self) -> None:
        """Should extract single dependency with type info."""
        deps = analyze_handler_dependencies(SingleDependencyHandler)

        assert "user_repo" in deps
        assert deps["user_repo"]["type_name"] == "MockUserRepository"
        assert deps["user_repo"]["is_optional"] is False

    def test_extracts_multiple_dependencies(self) -> None:
        """Should extract all dependencies."""
        deps = analyze_handler_dependencies(MultipleDependencyHandler)

        assert len(deps) == 2
        assert "user_repo" in deps
        assert "event_bus" in deps

    def test_identifies_optional_dependencies(self) -> None:
        """Should mark Optional types as optional."""
        deps = analyze_handler_dependencies(OptionalDependencyHandler)

        assert "user_repo" in deps
        assert deps["user_repo"]["is_optional"] is False

        assert "optional_service" in deps
        assert deps["optional_service"]["is_optional"] is True


# =============================================================================
# Test Dependency Type Mappings
# =============================================================================


@pytest.mark.unit
class TestDependencyMappings:
    """Tests for dependency type mappings."""

    def test_repository_types_not_empty(self) -> None:
        """REPOSITORY_TYPES should have entries."""
        assert len(REPOSITORY_TYPES) > 0
        assert "UserRepository" in REPOSITORY_TYPES

    def test_singleton_types_not_empty(self) -> None:
        """SINGLETON_TYPES should have entries."""
        assert len(SINGLETON_TYPES) > 0
        assert "EventBusProtocol" in SINGLETON_TYPES

    def test_get_supported_dependencies_returns_both(self) -> None:
        """get_supported_dependencies() should return both lists."""
        result = get_supported_dependencies()

        assert "repositories" in result
        assert "singletons" in result
        assert len(result["repositories"]) > 0
        assert len(result["singletons"]) > 0


# =============================================================================
# Test create_handler
# =============================================================================


@pytest.mark.unit
class TestCreateHandler:
    """Tests for create_handler() function."""

    @pytest.fixture
    def mock_session(self) -> MagicMock:
        """Create mock database session."""
        return MagicMock()

    @pytest.mark.asyncio
    async def test_creates_handler_with_no_deps(
        self,
        mock_session: MagicMock,
    ) -> None:
        """Should create handler without dependencies."""
        handler = await create_handler(SimpleHandler, mock_session)

        assert isinstance(handler, SimpleHandler)

    @pytest.mark.asyncio
    async def test_creates_handler_with_override(
        self,
        mock_session: MagicMock,
    ) -> None:
        """Should use provided overrides."""
        mock_repo = MagicMock()

        handler = await create_handler(
            SingleDependencyHandler,
            mock_session,
            user_repo=mock_repo,
        )

        assert isinstance(handler, SingleDependencyHandler)
        assert handler._user_repo is mock_repo

    @pytest.mark.asyncio
    async def test_resolves_optional_as_none_if_unknown(
        self,
        mock_session: MagicMock,
    ) -> None:
        """Optional dependencies resolve to None if unknown type."""
        # Create handler with custom optional type that's not in mappings
        handler = await create_handler(
            OptionalDependencyHandler,
            mock_session,
            user_repo=MagicMock(),  # Provide required dep
        )

        assert isinstance(handler, OptionalDependencyHandler)
        # Optional unknown type should be None
        assert handler._optional is None

    @pytest.mark.asyncio
    async def test_raises_for_unknown_required_dependency(
        self,
        mock_session: MagicMock,
    ) -> None:
        """Should raise ValueError for unknown required type."""
        # Define a handler with an unresolvable dependency type
        # The type name "UnknownServiceXYZ" won't match any known repository or singleton

        class UnknownDependencyHandler:
            # Using a custom class as type that won't be in REPOSITORY_TYPES or SINGLETON_TYPES
            class UnknownServiceXYZ:
                pass

            def __init__(self, unknown_service: UnknownServiceXYZ) -> None:
                self._unknown = unknown_service

        with pytest.raises(ValueError, match="Cannot resolve dependency"):
            await create_handler(UnknownDependencyHandler, mock_session)


# =============================================================================
# Test Real Handler Integration
# =============================================================================


@pytest.mark.unit
class TestRealHandlerIntegration:
    """Tests with actual Dashtam handlers."""

    @pytest.fixture
    def mock_session(self) -> MagicMock:
        """Create mock database session."""
        return MagicMock()

    def test_analyze_register_user_handler(self) -> None:
        """Analyze actual RegisterUserHandler dependencies."""
        from src.application.commands.handlers.register_user_handler import (
            RegisterUserHandler,
        )

        deps = analyze_handler_dependencies(RegisterUserHandler)

        # Should have multiple dependencies
        assert len(deps) >= 3

        # Should include common dependencies
        dep_types = {d["type_name"] for d in deps.values()}
        assert "UserRepository" in dep_types
        assert "PasswordHashingProtocol" in dep_types
        assert "EventBusProtocol" in dep_types

    @pytest.mark.asyncio
    async def test_create_register_user_handler_with_mocks(
        self,
        mock_session: MagicMock,
    ) -> None:
        """Create RegisterUserHandler with mock dependencies."""
        from src.application.commands.handlers.register_user_handler import (
            RegisterUserHandler,
        )

        # Provide all required mocks
        mock_deps = {
            "user_repo": MagicMock(),
            "password_service": MagicMock(),
            "event_bus": MagicMock(),
            "email_verification_repo": MagicMock(),
            "email_service": MagicMock(),
            "encryption_service": MagicMock(),
        }

        handler = await create_handler(
            RegisterUserHandler,
            mock_session,
            **mock_deps,
        )

        assert isinstance(handler, RegisterUserHandler)

    @pytest.mark.asyncio
    async def test_create_handler_auto_resolves_repositories(
        self,
        mock_session: MagicMock,
    ) -> None:
        """Auto-resolve repository and session service dependencies."""
        from src.application.queries.handlers.get_account_handler import (
            GetAccountHandler,
        )

        # Mock container functions to avoid real infrastructure
        with (
            patch(
                "src.core.container.handler_factory._get_repository_instance"
            ) as mock_repo_fn,
            patch(
                "src.core.container.handler_factory._get_singleton_instance"
            ) as mock_singleton_fn,
            patch(
                "src.core.container.handler_factory._get_session_service_instance"
            ) as mock_session_service_fn,
        ):
            mock_repo_fn.return_value = MagicMock()
            mock_singleton_fn.return_value = MagicMock()
            mock_session_service_fn.return_value = MagicMock()

            handler = await create_handler(GetAccountHandler, mock_session)

            assert isinstance(handler, GetAccountHandler)
            # GetAccountHandler now uses OwnershipVerifier (session service)
            assert mock_session_service_fn.called


# =============================================================================
# Test handler_factory FastAPI Integration
# =============================================================================


@pytest.mark.unit
class TestHandlerFactory:
    """Tests for handler_factory() FastAPI dependency generator."""

    def setup_method(self) -> None:
        """Clear cache before each test."""
        clear_handler_factory_cache()

    def test_returns_callable(self) -> None:
        """handler_factory should return a callable."""
        factory = handler_factory(SimpleHandler)
        assert callable(factory)

    def test_caches_factory_function(self) -> None:
        """Same handler should return same factory."""
        factory1 = handler_factory(SimpleHandler)
        factory2 = handler_factory(SimpleHandler)

        assert factory1 is factory2

    def test_different_handlers_get_different_factories(self) -> None:
        """Different handlers should get different factories."""
        factory1 = handler_factory(SimpleHandler)
        factory2 = handler_factory(SingleDependencyHandler)

        assert factory1 is not factory2

    def test_factory_has_descriptive_name(self) -> None:
        """Factory should have handler-based name."""
        factory = handler_factory(SimpleHandler)

        assert "simplehandler" in factory.__name__.lower()

    def test_factory_has_docstring(self) -> None:
        """Factory should have documentation."""
        factory = handler_factory(SimpleHandler)

        assert factory.__doc__ is not None
        assert "SimpleHandler" in factory.__doc__

    def test_clear_cache_removes_all_entries(self) -> None:
        """clear_handler_factory_cache should remove all cached factories."""
        # Create some factories
        _ = handler_factory(SimpleHandler)
        _ = handler_factory(SingleDependencyHandler)

        # Clear cache
        clear_handler_factory_cache()

        # New factory should be different instance
        from src.core.container.handler_factory import _handler_factory_cache

        assert len(_handler_factory_cache) == 0


# =============================================================================
# Test get_all_handler_factories
# =============================================================================


@pytest.mark.unit
class TestGetAllHandlerFactories:
    """Tests for get_all_handler_factories() registry integration."""

    def setup_method(self) -> None:
        """Clear cache before each test."""
        clear_handler_factory_cache()

    def test_returns_dict_of_factories(self) -> None:
        """Should return dict mapping handler names to factories."""
        factories = get_all_handler_factories()

        assert isinstance(factories, dict)
        assert len(factories) > 0

    def test_includes_all_registered_handlers(self) -> None:
        """Should include factories for all CQRS registry handlers."""
        from src.application.cqrs.computed_views import get_all_handler_classes

        factories = get_all_handler_factories()
        handler_classes = get_all_handler_classes()

        # Should have factory for each handler
        for handler_class in handler_classes:
            assert handler_class.__name__ in factories

    def test_factory_values_are_callable(self) -> None:
        """All factory values should be callable."""
        factories = get_all_handler_factories()

        for name, factory in factories.items():
            assert callable(factory), f"Factory for {name} is not callable"


# =============================================================================
# Test Repository Instance Creation
# =============================================================================


@pytest.mark.unit
class TestRepositoryInstanceCreation:
    """Tests for _get_repository_instance() function."""

    @pytest.fixture
    def mock_session(self) -> MagicMock:
        """Create mock database session."""
        return MagicMock()

    def test_creates_user_repository(self, mock_session: MagicMock) -> None:
        """Should create UserRepository with session."""
        from src.core.container.handler_factory import _get_repository_instance

        repo = _get_repository_instance("UserRepository", mock_session)

        from src.infrastructure.persistence.repositories import UserRepository

        assert isinstance(repo, UserRepository)

    def test_creates_account_repository(self, mock_session: MagicMock) -> None:
        """Should create AccountRepository with session."""
        from src.core.container.handler_factory import _get_repository_instance

        repo = _get_repository_instance("AccountRepository", mock_session)

        from src.infrastructure.persistence.repositories import AccountRepository

        assert isinstance(repo, AccountRepository)

    def test_raises_for_unknown_repository(self, mock_session: MagicMock) -> None:
        """Should raise ValueError for unknown repository type."""
        from src.core.container.handler_factory import _get_repository_instance

        with pytest.raises(ValueError, match="Unknown repository type"):
            _get_repository_instance("FakeRepository", mock_session)

    def test_security_config_repo_gets_cache_deps(
        self,
        mock_session: MagicMock,
    ) -> None:
        """SecurityConfigRepository should get cache dependencies."""
        from src.core.container.handler_factory import _get_repository_instance

        with (
            patch("src.core.container.infrastructure.get_cache") as mock_cache,
            patch("src.core.container.infrastructure.get_cache_keys") as mock_keys,
        ):
            mock_cache.return_value = MagicMock()
            mock_keys.return_value = MagicMock()

            repo = _get_repository_instance("SecurityConfigRepository", mock_session)

            from src.infrastructure.persistence.repositories.security_config_repository import (
                SecurityConfigRepository,
            )

            assert isinstance(repo, SecurityConfigRepository)


# =============================================================================
# Test Singleton Instance Creation
# =============================================================================


@pytest.mark.unit
class TestSingletonInstanceCreation:
    """Tests for _get_singleton_instance() function."""

    def test_gets_event_bus(self) -> None:
        """Should get EventBus singleton."""
        from src.core.container.handler_factory import _get_singleton_instance

        with patch("src.core.container.events.get_event_bus") as mock_get_bus:
            mock_bus = MagicMock()
            mock_get_bus.return_value = mock_bus

            result = _get_singleton_instance("EventBusProtocol")

            assert result is mock_bus
            mock_get_bus.assert_called_once()

    def test_gets_password_service(self) -> None:
        """Should get PasswordService singleton."""
        from src.core.container.handler_factory import _get_singleton_instance

        with patch(
            "src.core.container.infrastructure.get_password_service"
        ) as mock_get:
            mock_service = MagicMock()
            mock_get.return_value = mock_service

            result = _get_singleton_instance("PasswordHashingProtocol")

            assert result is mock_service
            mock_get.assert_called_once()

    def test_raises_for_unknown_singleton(self) -> None:
        """Should raise ValueError for unknown singleton type."""
        from src.core.container.handler_factory import _get_singleton_instance

        with pytest.raises(ValueError, match="Unknown singleton type"):
            _get_singleton_instance("FakeSingleton")

    def test_supports_protocol_suffix_types(self) -> None:
        """Should support both X and XProtocol naming."""
        from src.core.container.handler_factory import _get_singleton_instance

        # Both EncryptionProtocol and EncryptionService should work
        with patch(
            "src.core.container.infrastructure.get_encryption_service"
        ) as mock_get:
            mock_service = MagicMock()
            mock_get.return_value = mock_service

            result1 = _get_singleton_instance("EncryptionProtocol")
            result2 = _get_singleton_instance("EncryptionService")

            assert result1 is mock_service
            assert result2 is mock_service


# =============================================================================
# Test Type Detection Helpers
# =============================================================================


@pytest.mark.unit
class TestTypeDetectionHelpers:
    """Tests for _is_repository_type and _is_singleton_type."""

    def test_detects_repository_by_name(self) -> None:
        """Should detect known repository types."""
        from src.core.container.handler_factory import _is_repository_type

        assert _is_repository_type("UserRepository") is True
        assert _is_repository_type("AccountRepository") is True
        assert _is_repository_type("EventBusProtocol") is False

    def test_detects_repository_by_suffix(self) -> None:
        """Should detect types ending in 'Repository'."""
        from src.core.container.handler_factory import _is_repository_type

        assert _is_repository_type("CustomRepository") is True

    def test_detects_singleton_by_name(self) -> None:
        """Should detect known singleton types."""
        from src.core.container.handler_factory import _is_singleton_type

        assert _is_singleton_type("EventBusProtocol") is True
        assert _is_singleton_type("CacheProtocol") is True
        assert _is_singleton_type("UserRepository") is False

    def test_detects_singleton_by_suffix(self) -> None:
        """Should detect types ending in 'Protocol'."""
        from src.core.container.handler_factory import _is_singleton_type

        assert _is_singleton_type("CustomProtocol") is True
