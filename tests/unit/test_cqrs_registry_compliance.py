"""CQRS Registry Compliance Tests.

Self-enforcing tests that fail if the registry is incomplete or inconsistent.
Follows the Registry Pattern architecture established in domain events and route metadata.

Test categories:
1. Completeness - All commands/queries registered
2. Handler compliance - All handlers have handle() method
3. Naming conventions - Commands imperative, queries interrogative
4. Category consistency - Categories match actual use cases
5. Statistics - Registry counts match expectations

Reference:
    - docs/architecture/registry.md
    - docs/architecture/cqrs-registry.md
"""

from src.application.cqrs import (
    CachePolicy,
    CQRSCategory,
    COMMAND_REGISTRY,
    QUERY_REGISTRY,
    get_all_commands,
    get_all_queries,
    get_command_metadata,
    get_commands_by_category,
    get_commands_emitting_events,
    get_queries_by_category,
    get_query_metadata,
    get_statistics,
    validate_registry_consistency,
)
from src.application.cqrs.metadata import get_handler_factory_name


class TestRegistryCompleteness:
    """Verify all commands and queries are registered."""

    def test_command_registry_not_empty(self) -> None:
        """COMMAND_REGISTRY must have entries."""
        assert len(COMMAND_REGISTRY) > 0, "COMMAND_REGISTRY is empty"

    def test_query_registry_not_empty(self) -> None:
        """QUERY_REGISTRY must have entries."""
        assert len(QUERY_REGISTRY) > 0, "QUERY_REGISTRY is empty"

    def test_no_duplicate_commands(self) -> None:
        """No duplicate command classes in registry."""
        command_classes = [meta.command_class for meta in COMMAND_REGISTRY]
        duplicates = [cmd for cmd in command_classes if command_classes.count(cmd) > 1]
        assert not duplicates, f"Duplicate commands: {duplicates}"

    def test_no_duplicate_queries(self) -> None:
        """No duplicate query classes in registry."""
        query_classes = [meta.query_class for meta in QUERY_REGISTRY]
        duplicates = [qry for qry in query_classes if query_classes.count(qry) > 1]
        assert not duplicates, f"Duplicate queries: {duplicates}"

    def test_command_count_matches_get_all_commands(self) -> None:
        """Registry length matches get_all_commands() helper.

        Auto-discovery: count derived from registry itself.
        """
        registry_count = len(COMMAND_REGISTRY)
        helper_count = len(get_all_commands())
        assert registry_count == helper_count, (
            f"Registry count ({registry_count}) != get_all_commands() ({helper_count})"
        )
        # Sanity check: registry is not empty
        assert registry_count > 0, "COMMAND_REGISTRY is empty"

    def test_query_count_matches_get_all_queries(self) -> None:
        """Registry length matches get_all_queries() helper.

        Auto-discovery: count derived from registry itself.
        """
        registry_count = len(QUERY_REGISTRY)
        helper_count = len(get_all_queries())
        assert registry_count == helper_count, (
            f"Registry count ({registry_count}) != get_all_queries() ({helper_count})"
        )
        # Sanity check: registry is not empty
        assert registry_count > 0, "QUERY_REGISTRY is empty"


class TestHandlerCompliance:
    """Verify handlers conform to CQRS patterns."""

    def test_all_command_handlers_have_handle_method(self) -> None:
        """All command handlers must implement handle()."""
        missing = []
        for meta in COMMAND_REGISTRY:
            if not hasattr(meta.handler_class, "handle"):
                missing.append(meta.handler_class.__name__)

        assert not missing, f"Missing handle() method: {missing}"

    def test_all_query_handlers_have_handle_method(self) -> None:
        """All query handlers must implement handle()."""
        missing = []
        for meta in QUERY_REGISTRY:
            if not hasattr(meta.handler_class, "handle"):
                missing.append(meta.handler_class.__name__)

        assert not missing, f"Missing handle() method: {missing}"

    def test_handlers_are_classes(self) -> None:
        """Handlers must be class types, not instances."""
        for cmd_meta in COMMAND_REGISTRY:
            assert isinstance(cmd_meta.handler_class, type), (
                f"{cmd_meta.handler_class} is not a class"
            )

        for qry_meta in QUERY_REGISTRY:
            assert isinstance(qry_meta.handler_class, type), (
                f"{qry_meta.handler_class} is not a class"
            )

    def test_commands_are_dataclasses(self) -> None:
        """Commands should be dataclasses (frozen, kw_only)."""
        from dataclasses import is_dataclass

        for meta in COMMAND_REGISTRY:
            assert is_dataclass(meta.command_class), (
                f"{meta.command_class.__name__} is not a dataclass"
            )

    def test_queries_are_dataclasses(self) -> None:
        """Queries should be dataclasses (frozen, kw_only)."""
        from dataclasses import is_dataclass

        for meta in QUERY_REGISTRY:
            assert is_dataclass(meta.query_class), (
                f"{meta.query_class.__name__} is not a dataclass"
            )


class TestNamingConventions:
    """Verify naming follows CQRS patterns."""

    def test_command_names_are_imperative(self) -> None:
        """Commands should have imperative names (verbs).

        Pattern: VerbNoun (e.g., RegisterUser, CreateSession)
        """
        imperative_prefixes = (
            "Register",
            "Authenticate",
            "Verify",
            "Refresh",
            "Request",
            "Confirm",
            "Logout",
            "Create",
            "Revoke",
            "Link",
            "Record",
            "Update",
            "Generate",
            "Trigger",
            "Connect",
            "Disconnect",
            "Sync",
            "Import",
        )

        for meta in COMMAND_REGISTRY:
            name = meta.command_class.__name__
            assert any(name.startswith(prefix) for prefix in imperative_prefixes), (
                f"Command {name} should start with imperative verb"
            )

    def test_query_names_are_interrogative(self) -> None:
        """Queries should have interrogative names (questions).

        Pattern: Get* or List* (e.g., GetAccount, ListAccountsByUser)
        """
        interrogative_prefixes = ("Get", "List")

        for meta in QUERY_REGISTRY:
            name = meta.query_class.__name__
            assert any(name.startswith(prefix) for prefix in interrogative_prefixes), (
                f"Query {name} should start with Get/List"
            )

    def test_handler_names_match_commands(self) -> None:
        """Handler class names should match command names.

        Pattern: CommandName + Handler (e.g., RegisterUser -> RegisterUserHandler)
        """
        exceptions = {
            # These use a shared handler for multiple commands
            "LinkRefreshTokenToSession",
            "RecordProviderAccess",
            "UpdateSessionActivity",
            # Handler named RevokeAllSessionsHandler (not RevokeAllUserSessionsHandler)
            "RevokeAllUserSessions",
        }

        for meta in COMMAND_REGISTRY:
            cmd_name = meta.command_class.__name__
            if cmd_name in exceptions:
                continue
            expected_handler_name = f"{cmd_name}Handler"
            actual_handler_name = meta.handler_class.__name__
            assert actual_handler_name == expected_handler_name, (
                f"Expected handler {expected_handler_name}, got {actual_handler_name}"
            )


class TestCategoryConsistency:
    """Verify category assignments are consistent."""

    def test_all_categories_have_commands(self) -> None:
        """Each category should have at least one command."""
        categories_with_commands = {meta.category for meta in COMMAND_REGISTRY}

        # All categories should be used except those with no commands
        expected_categories = {
            CQRSCategory.AUTH,
            CQRSCategory.SESSION,
            CQRSCategory.TOKEN,
            CQRSCategory.PROVIDER,
            CQRSCategory.DATA_SYNC,
            CQRSCategory.IMPORT,
        }

        assert categories_with_commands == expected_categories, (
            f"Category mismatch. Expected {expected_categories}, got {categories_with_commands}"
        )

    def test_auth_category_has_expected_commands(self) -> None:
        """AUTH category should have authentication-related commands."""
        auth_commands = get_commands_by_category(CQRSCategory.AUTH)
        auth_names = {meta.command_class.__name__ for meta in auth_commands}

        expected = {
            "RegisterUser",
            "AuthenticateUser",
            "VerifyEmail",
            "RefreshAccessToken",
            "RequestPasswordReset",
            "ConfirmPasswordReset",
            "LogoutUser",
        }

        assert auth_names == expected, (
            f"AUTH category mismatch: {auth_names} != {expected}"
        )

    def test_session_category_has_expected_commands(self) -> None:
        """SESSION category should have session-related commands."""
        session_commands = get_commands_by_category(CQRSCategory.SESSION)
        session_names = {meta.command_class.__name__ for meta in session_commands}

        expected = {
            "CreateSession",
            "RevokeSession",
            "RevokeAllUserSessions",
            "LinkRefreshTokenToSession",
            "RecordProviderAccess",
            "UpdateSessionActivity",
        }

        assert session_names == expected, (
            f"SESSION category mismatch: {session_names} != {expected}"
        )

    def test_data_sync_queries_are_majority(self) -> None:
        """DATA_SYNC should have the most queries (accounts, transactions, etc.).

        Auto-discovery: compare DATA_SYNC count to other categories.
        """
        data_sync_queries = get_queries_by_category(CQRSCategory.DATA_SYNC)
        other_categories = [
            CQRSCategory.SESSION,
            CQRSCategory.PROVIDER,
        ]

        for category in other_categories:
            other_count = len(get_queries_by_category(category))
            assert len(data_sync_queries) > other_count, (
                f"DATA_SYNC ({len(data_sync_queries)}) should have more queries "
                f"than {category.value} ({other_count})"
            )


class TestMetadataConsistency:
    """Verify metadata fields are consistent."""

    def test_result_dto_consistency(self) -> None:
        """If has_result_dto is True, result_dto_class must be set."""
        for meta in COMMAND_REGISTRY:
            if meta.has_result_dto:
                assert meta.result_dto_class is not None, (
                    f"{meta.command_class.__name__} has_result_dto=True but no result_dto_class"
                )

    def test_no_result_dto_without_flag(self) -> None:
        """If has_result_dto is False, result_dto_class must be None."""
        for meta in COMMAND_REGISTRY:
            if not meta.has_result_dto:
                assert meta.result_dto_class is None, (
                    f"{meta.command_class.__name__} has_result_dto=False but has result_dto_class"
                )

    def test_event_emitting_commands_majority(self) -> None:
        """Most commands should emit events.

        Auto-discovery: verify emitting > non-emitting.
        """
        emitting_count = len(get_commands_emitting_events())
        total_count = len(COMMAND_REGISTRY)
        non_emitting_count = total_count - emitting_count

        # Majority (>50%) should emit events
        assert emitting_count > non_emitting_count, (
            f"Event-emitting commands ({emitting_count}) should be majority. "
            f"Non-emitting: {non_emitting_count}"
        )

    def test_transaction_requiring_commands_majority(self) -> None:
        """Most commands should require transactions.

        Auto-discovery: verify majority requires transactions.
        """
        requiring = sum(1 for meta in COMMAND_REGISTRY if meta.requires_transaction)
        total = len(COMMAND_REGISTRY)
        not_requiring = total - requiring

        # Majority should require transactions
        assert requiring > not_requiring, (
            f"Transaction-requiring commands ({requiring}) should be majority. "
            f"Not requiring: {not_requiring}"
        )

    def test_paginated_queries_have_list_prefix(self) -> None:
        """Paginated queries should be list operations."""
        for meta in QUERY_REGISTRY:
            if meta.is_paginated:
                name = meta.query_class.__name__
                assert name.startswith("List"), (
                    f"Paginated query {name} should start with 'List'"
                )


class TestHelperFunctions:
    """Verify helper functions work correctly."""

    def test_get_all_commands_returns_classes(self) -> None:
        """get_all_commands() should return command classes."""
        commands = get_all_commands()
        assert all(isinstance(cmd, type) for cmd in commands)
        assert len(commands) == len(COMMAND_REGISTRY)

    def test_get_all_queries_returns_classes(self) -> None:
        """get_all_queries() should return query classes."""
        queries = get_all_queries()
        assert all(isinstance(qry, type) for qry in queries)
        assert len(queries) == len(QUERY_REGISTRY)

    def test_get_command_metadata_finds_command(self) -> None:
        """get_command_metadata() should find registered commands."""
        from src.application.commands.auth_commands import RegisterUser

        meta = get_command_metadata(RegisterUser)
        assert meta is not None
        assert meta.command_class == RegisterUser
        assert meta.category == CQRSCategory.AUTH

    def test_get_command_metadata_returns_none_for_unknown(self) -> None:
        """get_command_metadata() should return None for unknown commands."""

        class FakeCommand:
            pass

        meta = get_command_metadata(FakeCommand)
        assert meta is None

    def test_get_query_metadata_finds_query(self) -> None:
        """get_query_metadata() should find registered queries."""
        from src.application.queries.account_queries import GetAccount

        meta = get_query_metadata(GetAccount)
        assert meta is not None
        assert meta.query_class == GetAccount
        assert meta.category == CQRSCategory.DATA_SYNC

    def test_get_statistics_returns_expected_keys(self) -> None:
        """get_statistics() should return expected keys."""
        stats = get_statistics()

        expected_keys = {
            "total_commands",
            "total_queries",
            "total_operations",
            "commands_by_category",
            "queries_by_category",
            "commands_with_result_dto",
            "commands_emitting_events",
            "commands_requiring_transaction",
            "paginated_queries",
            "queries_by_cache_policy",
        }

        assert set(stats.keys()) == expected_keys

    def test_validate_registry_consistency_passes(self) -> None:
        """validate_registry_consistency() should return no errors."""
        errors = validate_registry_consistency()
        assert errors == [], f"Registry validation errors: {errors}"


class TestHandlerFactoryNames:
    """Verify handler factory name computation."""

    def test_command_handler_factory_names(self) -> None:
        """get_handler_factory_name() should compute correct names."""
        from src.application.commands.auth_commands import RegisterUser

        meta = get_command_metadata(RegisterUser)
        assert meta is not None

        factory_name = get_handler_factory_name(meta)
        assert factory_name == "get_register_user_handler"

    def test_query_handler_factory_names(self) -> None:
        """get_handler_factory_name() should compute correct names for queries."""
        from src.application.queries.account_queries import ListAccountsByUser

        meta = get_query_metadata(ListAccountsByUser)
        assert meta is not None

        factory_name = get_handler_factory_name(meta)
        assert factory_name == "get_list_accounts_by_user_handler"


class TestStatistics:
    """Verify registry statistics are accurate."""

    def test_total_operations_count(self) -> None:
        """Total operations should be commands + queries."""
        stats = get_statistics()
        total_ops = stats["total_operations"]
        total_cmds = stats["total_commands"]
        total_qrys = stats["total_queries"]
        assert isinstance(total_ops, int)
        assert isinstance(total_cmds, int)
        assert isinstance(total_qrys, int)
        assert total_ops == total_cmds + total_qrys

    def test_commands_by_category_sums_to_total(self) -> None:
        """Sum of commands by category should equal total."""
        stats = get_statistics()
        by_category = stats["commands_by_category"]
        total_cmds = stats["total_commands"]
        assert isinstance(by_category, dict)
        assert isinstance(total_cmds, int)
        category_sum = sum(by_category.values())
        assert category_sum == total_cmds

    def test_queries_by_category_sums_to_total(self) -> None:
        """Sum of queries by category should equal total."""
        stats = get_statistics()
        by_category = stats["queries_by_category"]
        total_qrys = stats["total_queries"]
        assert isinstance(by_category, dict)
        assert isinstance(total_qrys, int)
        category_sum = sum(by_category.values())
        assert category_sum == total_qrys

    def test_cache_policy_distribution(self) -> None:
        """All queries should have cache policy set."""
        stats = get_statistics()
        by_cache = stats["queries_by_cache_policy"]
        total_qrys = stats["total_queries"]
        assert isinstance(by_cache, dict)
        assert isinstance(total_qrys, int)
        cache_sum = sum(by_cache.values())
        assert cache_sum == total_qrys


class TestFutureProofing:
    """Tests that catch common mistakes when adding new commands/queries."""

    def test_handler_class_not_command_class(self) -> None:
        """Handler should not be the same as command class."""
        for meta in COMMAND_REGISTRY:
            assert meta.handler_class != meta.command_class, (
                f"{meta.command_class.__name__} handler_class is command_class"
            )

    def test_handler_class_not_query_class(self) -> None:
        """Handler should not be the same as query class."""
        for meta in QUERY_REGISTRY:
            assert meta.handler_class != meta.query_class, (
                f"{meta.query_class.__name__} handler_class is query_class"
            )

    def test_all_categories_are_enum_values(self) -> None:
        """All categories should be valid CQRSCategory enum values."""
        for cmd_meta in COMMAND_REGISTRY:
            assert isinstance(cmd_meta.category, CQRSCategory), (
                f"{cmd_meta.command_class.__name__} category is not CQRSCategory"
            )

        for qry_meta in QUERY_REGISTRY:
            assert isinstance(qry_meta.category, CQRSCategory), (
                f"{qry_meta.query_class.__name__} category is not CQRSCategory"
            )

    def test_all_cache_policies_are_enum_values(self) -> None:
        """All cache policies should be valid CachePolicy enum values."""
        for meta in QUERY_REGISTRY:
            assert isinstance(meta.cache_policy, CachePolicy), (
                f"{meta.query_class.__name__} cache_policy is not CachePolicy"
            )
