"""Unit tests for AuditAction enum.

Tests cover:
- Enum value types and formats
- Enum membership and iteration
- Serialization to string
- String comparison
- All 32 audit actions are defined
- Edge cases

Architecture:
- Unit tests with no external dependencies
- Tests enum behavior and string serialization
"""

import pytest

from src.domain.enums import AuditAction


@pytest.mark.unit
class TestAuditActionEnumValues:
    """Test AuditAction enum values and types."""

    def test_all_values_are_strings(self):
        """Test all enum values are strings (str Enum)."""
        for action in AuditAction:
            assert isinstance(action.value, str)
            # Enum members should also be string instances
            assert isinstance(action, str)

    def test_values_are_snake_case(self):
        """Test all enum values use snake_case format."""
        for action in AuditAction:
            value = action.value
            # Should contain only lowercase letters, numbers, underscores
            assert value.islower()
            assert all(c.isalnum() or c == "_" for c in value)
            # Should not start or end with underscore
            assert not value.startswith("_")
            assert not value.endswith("_")

    def test_enum_has_sufficient_coverage(self):
        """Test AuditAction enum covers all registered events.

        This test dynamically verifies AuditAction has at least as many
        entries as required by EVENT_REGISTRY. No hardcoded counts.

        For detailed compliance verification, see:
        tests/unit/test_domain_events_registry_compliance.py::TestAuditActionCompliance
        """
        from src.domain.events.registry import EVENT_REGISTRY

        # Count events requiring audit (each needs an AuditAction)
        events_requiring_audit = sum(1 for m in EVENT_REGISTRY if m.requires_audit)

        # AuditAction should have at least this many entries
        # (may have more for non-event actions like admin operations)
        actual_count = len(list(AuditAction))

        assert actual_count >= events_requiring_audit, (
            f"AuditAction enum has {actual_count} entries but "
            f"EVENT_REGISTRY requires at least {events_requiring_audit}"
        )

    def test_enum_membership(self):
        """Test enum membership checks work correctly."""
        # Positive cases - enum members (using ATTEMPT/OUTCOME pattern)
        assert AuditAction.USER_LOGIN_ATTEMPTED in AuditAction
        assert AuditAction.USER_LOGIN_SUCCESS in AuditAction
        assert AuditAction.USER_LOGOUT in AuditAction
        assert AuditAction.DATA_VIEWED in AuditAction

        # Negative case - string value IS a member (str Enum behavior)
        assert "user_login_attempted" in AuditAction
        assert "invalid_action" not in AuditAction

    def test_enum_iteration(self):
        """Test enum can be iterated over."""
        actions = list(AuditAction)
        assert len(actions) > 0
        assert all(isinstance(action, AuditAction) for action in actions)

    def test_enum_comparison(self):
        """Test enum values can be compared."""
        # Same enum values are equal
        assert AuditAction.USER_LOGIN_ATTEMPTED == AuditAction.USER_LOGIN_ATTEMPTED

        # Different enum values are not equal
        assert AuditAction.USER_LOGIN_ATTEMPTED != AuditAction.USER_LOGOUT  # type: ignore[comparison-overlap]

        # Enum value equals its string value
        assert AuditAction.USER_LOGIN_ATTEMPTED.value == "user_login_attempted"
        assert AuditAction.DATA_VIEWED.value == "data_viewed"


@pytest.mark.unit
class TestAuditActionCategories:
    """Test AuditAction categories are complete."""

    def test_authentication_actions_exist(self):
        """Test all authentication actions are defined (ATTEMPT/OUTCOME pattern)."""
        auth_actions = [
            # Login flow
            AuditAction.USER_LOGIN_ATTEMPTED,
            AuditAction.USER_LOGIN_SUCCESS,
            AuditAction.USER_LOGIN_FAILED,
            # Registration flow
            AuditAction.USER_REGISTRATION_ATTEMPTED,
            AuditAction.USER_REGISTERED,
            AuditAction.USER_REGISTRATION_FAILED,
            # Logout (completed event)
            AuditAction.USER_LOGOUT,
            # Password changes
            AuditAction.USER_PASSWORD_CHANGED,
            AuditAction.USER_PASSWORD_RESET_REQUESTED,
            AuditAction.USER_PASSWORD_RESET_COMPLETED,
            # Verification
            AuditAction.USER_EMAIL_VERIFIED,
            # MFA
            AuditAction.USER_MFA_ENABLED,
            AuditAction.USER_MFA_DISABLED,
        ]

        for action in auth_actions:
            assert action in AuditAction

    def test_authorization_actions_exist(self):
        """Test all authorization actions are defined."""
        authz_actions = [
            AuditAction.ACCESS_GRANTED,
            AuditAction.ACCESS_DENIED,
            AuditAction.PERMISSION_CHANGED,
            AuditAction.ROLE_ASSIGNED,
            AuditAction.ROLE_REVOKED,
        ]

        for action in authz_actions:
            assert action in AuditAction

    def test_data_operations_actions_exist(self):
        """Test all data operation actions are defined."""
        data_actions = [
            AuditAction.DATA_VIEWED,
            AuditAction.DATA_EXPORTED,
            AuditAction.DATA_DELETED,
            AuditAction.DATA_MODIFIED,
        ]

        for action in data_actions:
            assert action in AuditAction

    def test_administrative_actions_exist(self):
        """Test all administrative actions are defined."""
        admin_actions = [
            AuditAction.ADMIN_USER_CREATED,
            AuditAction.ADMIN_USER_DELETED,
            AuditAction.ADMIN_USER_SUSPENDED,
            AuditAction.ADMIN_CONFIG_CHANGED,
            AuditAction.ADMIN_BACKUP_CREATED,
        ]

        for action in admin_actions:
            assert action in AuditAction

    def test_provider_actions_exist(self):
        """Test all provider actions are defined."""
        provider_actions = [
            AuditAction.PROVIDER_CONNECTED,
            AuditAction.PROVIDER_DISCONNECTED,
            AuditAction.PROVIDER_TOKEN_REFRESHED,
            AuditAction.PROVIDER_TOKEN_REFRESH_FAILED,
            AuditAction.PROVIDER_DATA_SYNCED,
            AuditAction.PROVIDER_ACCOUNT_VIEWED,
            AuditAction.PROVIDER_TRANSACTION_VIEWED,
        ]

        for action in provider_actions:
            assert action in AuditAction


@pytest.mark.unit
class TestAuditActionSerialization:
    """Test AuditAction serialization and deserialization."""

    def test_enum_to_string(self):
        """Test enum value (not str()) equals string."""
        # str Enum: enum.value is the string, str(enum) is repr
        assert AuditAction.USER_LOGIN_ATTEMPTED.value == "user_login_attempted"
        assert AuditAction.DATA_VIEWED.value == "data_viewed"
        assert AuditAction.PROVIDER_CONNECTED.value == "provider_connected"

    def test_enum_value_access(self):
        """Test enum .value property returns string."""
        assert AuditAction.USER_LOGIN_ATTEMPTED.value == "user_login_attempted"
        assert AuditAction.DATA_VIEWED.value == "data_viewed"
        assert AuditAction.PROVIDER_CONNECTED.value == "provider_connected"

    def test_enum_from_string(self):
        """Test creating enum from string value."""
        # Valid values
        assert AuditAction("user_login_attempted") == AuditAction.USER_LOGIN_ATTEMPTED
        assert AuditAction("data_viewed") == AuditAction.DATA_VIEWED
        assert AuditAction("provider_connected") == AuditAction.PROVIDER_CONNECTED

    def test_enum_from_invalid_string_raises_error(self):
        """Test creating enum from invalid string raises ValueError."""
        with pytest.raises(ValueError):
            AuditAction("invalid_action")

        with pytest.raises(ValueError):
            AuditAction("USER_LOGIN_ATTEMPTED")  # Wrong case

        with pytest.raises(ValueError):
            AuditAction("")  # Empty string

    def test_enum_json_serializable(self):
        """Test enum can be serialized to JSON (as string)."""
        import json

        # Enum value is a string, so JSON serialization should work
        data = {"action": AuditAction.USER_LOGIN_ATTEMPTED.value}
        json_str = json.dumps(data)

        assert json_str == '{"action": "user_login_attempted"}'

        # Deserialize and verify
        parsed = json.loads(json_str)
        assert parsed["action"] == "user_login_attempted"
        assert AuditAction(parsed["action"]) == AuditAction.USER_LOGIN_ATTEMPTED


@pytest.mark.unit
class TestAuditActionEdgeCases:
    """Test AuditAction edge cases and error conditions."""

    def test_enum_name_property(self):
        """Test enum .name property returns member name."""
        assert AuditAction.USER_LOGIN_ATTEMPTED.name == "USER_LOGIN_ATTEMPTED"
        assert AuditAction.DATA_VIEWED.name == "DATA_VIEWED"
        assert AuditAction.PROVIDER_CONNECTED.name == "PROVIDER_CONNECTED"

    def test_enum_repr(self):
        """Test enum __repr__ includes both name and value."""
        repr_str = repr(AuditAction.USER_LOGIN_ATTEMPTED)
        assert "AuditAction" in repr_str
        assert "USER_LOGIN_ATTEMPTED" in repr_str

    def test_enum_hash(self):
        """Test enum values are hashable (can be used as dict keys)."""
        # Create dict with enum keys
        audit_counts = {
            AuditAction.USER_LOGIN_ATTEMPTED: 10,
            AuditAction.USER_LOGOUT: 5,
            AuditAction.DATA_VIEWED: 20,
        }

        assert audit_counts[AuditAction.USER_LOGIN_ATTEMPTED] == 10
        assert audit_counts[AuditAction.USER_LOGOUT] == 5
        assert audit_counts[AuditAction.DATA_VIEWED] == 20

    def test_enum_in_set(self):
        """Test enum values can be added to sets."""
        actions = {
            AuditAction.USER_LOGIN_ATTEMPTED,
            AuditAction.USER_LOGOUT,
            AuditAction.USER_LOGIN_ATTEMPTED,  # Duplicate should be ignored
        }

        assert len(actions) == 2
        assert AuditAction.USER_LOGIN_ATTEMPTED in actions
        assert AuditAction.USER_LOGOUT in actions

    def test_enum_comparison_with_string(self):
        """Test enum can be compared with string values."""
        # String comparison works because AuditAction is str Enum
        assert AuditAction.USER_LOGIN_ATTEMPTED.value == "user_login_attempted"
        assert AuditAction.DATA_VIEWED.value == "data_viewed"

        # Not equal to different strings
        assert AuditAction.USER_LOGIN_ATTEMPTED.value != "user_logout"  # type: ignore[comparison-overlap]
        assert AuditAction.DATA_VIEWED.value != "DATA_VIEWED"  # type: ignore[comparison-overlap]

    def test_enum_boolean_context(self):
        """Test enum values are truthy."""
        # All enum values should be truthy
        for action in AuditAction:
            assert action  # Should be truthy
            assert bool(action) is True
