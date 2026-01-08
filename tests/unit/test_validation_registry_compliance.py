"""Validation registry compliance tests (F8.4).

Self-enforcing validation tests that verify VALIDATION_RULES_REGISTRY completeness.
These tests fail if:
- Rules are missing required metadata
- Validators are not callable or don't work correctly
- Field constraints are invalid
- Examples don't pass validation

Similar to F8.1 Provider Registry and F8.3 Rate Limit Registry, this ensures
the validation rules registry remains complete and prevents drift.

Pattern: Registry Pattern with self-enforcing compliance tests.
"""

from typing import Any, cast
import pytest

from src.domain.validators import (
    VALIDATION_RULES_REGISTRY,
    ValidationCategory,
    get_all_validation_rules,
    get_rules_by_category,
    get_statistics,
    get_validation_rule,
)


# =============================================================================
# Test Class 1: Registry Completeness
# =============================================================================


class TestValidationRegistryCompleteness:
    """Verify all validation rules have complete and valid metadata."""

    def test_all_rules_have_validator_functions(self):
        """Every rule must have a callable validator function."""
        for rule_name, rule in VALIDATION_RULES_REGISTRY.items():
            assert callable(rule.validator_function), (
                f"Rule '{rule_name}' has non-callable validator_function: "
                f"{rule.validator_function}"
            )

    def test_all_rules_have_field_constraints(self):
        """Every rule must have field_constraints dict (can be empty)."""
        for rule_name, rule in VALIDATION_RULES_REGISTRY.items():
            assert isinstance(rule.field_constraints, dict), (
                f"Rule '{rule_name}' has invalid field_constraints: "
                f"{type(rule.field_constraints).__name__}. Must be dict."
            )

    def test_all_rules_have_descriptions(self):
        """Every rule must have non-empty description."""
        for rule_name, rule in VALIDATION_RULES_REGISTRY.items():
            assert rule.description and rule.description.strip(), (
                f"Rule '{rule_name}' has empty description. "
                "Descriptions are required for documentation."
            )

    def test_all_rules_have_examples(self):
        """Every rule must have at least one example."""
        for rule_name, rule in VALIDATION_RULES_REGISTRY.items():
            assert rule.examples and len(rule.examples) > 0, (
                f"Rule '{rule_name}' has no examples. "
                "At least one valid example is required."
            )

    def test_all_rules_have_valid_categories(self):
        """Every rule must have a valid ValidationCategory enum value."""
        valid_categories = set(ValidationCategory)
        for rule_name, rule in VALIDATION_RULES_REGISTRY.items():
            assert rule.category in valid_categories, (
                f"Rule '{rule_name}' has invalid category: {rule.category}. "
                f"Must be one of: {[c.value for c in valid_categories]}"
            )

    def test_rule_names_are_unique(self):
        """Registry keys (rule names) must be unique."""
        rule_names = list(VALIDATION_RULES_REGISTRY.keys())
        duplicates = [name for name in set(rule_names) if rule_names.count(name) > 1]

        assert not duplicates, (
            f"Duplicate rule names found: {duplicates}. "
            "Each rule must have a unique name."
        )

    def test_rule_names_follow_convention(self):
        """Rule names should use snake_case convention."""
        for rule_name in VALIDATION_RULES_REGISTRY.keys():
            assert (
                rule_name.islower()
                and "_" in rule_name
                or len(rule_name.split("_")) == 1
            ), (
                f"Rule name '{rule_name}' doesn't follow snake_case convention. "
                "Use lowercase with underscores (e.g., 'email', 'refresh_token')."
            )

    def test_field_constraints_are_valid_pydantic_args(self):
        """Field constraints should be valid Pydantic Field arguments."""
        valid_constraint_keys = {
            "min_length",
            "max_length",
            "pattern",
            "gt",
            "ge",
            "lt",
            "le",
            "multiple_of",
        }

        for rule_name, rule in VALIDATION_RULES_REGISTRY.items():
            for key in rule.field_constraints.keys():
                assert key in valid_constraint_keys, (
                    f"Rule '{rule_name}' has invalid constraint '{key}'. "
                    f"Valid keys: {valid_constraint_keys}"
                )


# =============================================================================
# Test Class 2: Validator Functions
# =============================================================================


class TestValidationRuleValidatorFunctions:
    """Verify validator functions work correctly."""

    def test_all_validators_are_callable(self):
        """All validator functions must be callable."""
        for rule_name, rule in VALIDATION_RULES_REGISTRY.items():
            assert callable(rule.validator_function), (
                f"Validator for '{rule_name}' is not callable: "
                f"{rule.validator_function}"
            )

    def test_validators_raise_value_error_on_invalid(self):
        """Validators must raise ValueError for invalid input."""
        # Test with known invalid inputs for each rule
        invalid_inputs = {
            "email": "not-an-email",
            "password": "weak",
            "verification_token": "not-hex!",
            "refresh_token": "invalid chars!",
        }

        for rule_name, invalid_input in invalid_inputs.items():
            rule = VALIDATION_RULES_REGISTRY[rule_name]
            with pytest.raises(ValueError, match=".*"):
                rule.validator_function(invalid_input)

    def test_validators_return_correct_type(self):
        """Validators should return str (or appropriate type)."""
        # Test with known valid inputs
        valid_inputs = {
            "email": "user@example.com",
            "password": "SecurePass123!",
            "verification_token": "abc123def456",
            "refresh_token": "dGhpcyBpcyBh",
        }

        for rule_name, valid_input in valid_inputs.items():
            rule = VALIDATION_RULES_REGISTRY[rule_name]
            result = rule.validator_function(valid_input)
            assert isinstance(result, str), (
                f"Validator for '{rule_name}' returned {type(result).__name__}, "
                "expected str"
            )

    def test_validators_handle_edge_cases(self):
        """Validators should handle edge cases appropriately."""
        # Empty string should fail for all validators
        for rule_name, rule in VALIDATION_RULES_REGISTRY.items():
            with pytest.raises(ValueError):
                rule.validator_function("")


# =============================================================================
# Test Class 3: Type Consistency
# =============================================================================


class TestValidationRuleTypeConsistency:
    """Verify consistency between registry and actual usage."""

    def test_domain_types_use_registry_validators(self):
        """src/domain/types.py should use validators from registry."""
        # This is a documentation test - verify that domain/types.py imports
        # from the same validator functions as the registry
        from src.domain.validators import (
            validate_email,
            validate_refresh_token_format,
            validate_strong_password,
            validate_token_format,
        )

        # Verify Email uses validate_email (same function as registry)
        email_rule = VALIDATION_RULES_REGISTRY["email"]
        assert email_rule.validator_function == validate_email

        # Verify Password uses validate_strong_password
        password_rule = VALIDATION_RULES_REGISTRY["password"]
        assert password_rule.validator_function == validate_strong_password

        # Verify tokens
        token_rule = VALIDATION_RULES_REGISTRY["verification_token"]
        assert token_rule.validator_function == validate_token_format

        refresh_rule = VALIDATION_RULES_REGISTRY["refresh_token"]
        assert refresh_rule.validator_function == validate_refresh_token_format

    def test_no_duplicate_validator_logic(self):
        """Validator functions should not be duplicated."""
        # Check that each validator function is used exactly once
        validator_functions = [
            rule.validator_function for rule in VALIDATION_RULES_REGISTRY.values()
        ]

        # All validator functions should be unique
        unique_validators = set(validator_functions)
        assert len(unique_validators) == len(validator_functions), (
            f"Found {len(validator_functions) - len(unique_validators)} duplicate "
            "validator functions. Each validator should be unique."
        )

    def test_examples_pass_validation(self):
        """All examples in metadata must pass their validators."""
        for rule_name, rule in VALIDATION_RULES_REGISTRY.items():
            for example in rule.examples:
                try:
                    result = rule.validator_function(example)
                    assert isinstance(result, str), (
                        f"Example '{example}' for rule '{rule_name}' validation "
                        f"returned {type(result).__name__}, expected str"
                    )
                except ValueError as e:
                    pytest.fail(
                        f"Example '{example}' for rule '{rule_name}' failed validation: {e}"
                    )


# =============================================================================
# Test Class 4: Registry Statistics and Helper Functions
# =============================================================================


class TestValidationRegistryStatistics:
    """Snapshot tests for current registry state and helper functions."""

    def test_registry_has_minimum_rules(self):
        """Registry should have at least 4 rules (as of F8.4 implementation)."""
        rule_count = len(VALIDATION_RULES_REGISTRY)
        assert rule_count >= 4, (
            f"Registry has only {rule_count} rules. "
            "Expected at least 4 (email, password, verification_token, refresh_token). "
            "If rules were removed, update this test."
        )

    def test_category_distribution(self):
        """Verify category distribution matches expected patterns."""
        stats: dict[str, Any] = get_statistics()
        by_category = cast(dict[str, int], stats["by_category"])

        # As of F8.4, all 4 rules are AUTHENTICATION
        assert "authentication" in by_category, "No AUTHENTICATION rules found"
        assert by_category["authentication"] >= 4, (
            f"Expected at least 4 AUTHENTICATION rules, found {by_category.get('authentication', 0)}"
        )

    def test_all_existing_types_covered(self):
        """Verify all existing Annotated types from domain/types.py are in registry."""
        critical_rules = ["email", "password", "verification_token", "refresh_token"]

        missing_rules = [
            rule_name
            for rule_name in critical_rules
            if rule_name not in VALIDATION_RULES_REGISTRY
        ]

        assert not missing_rules, (
            f"Critical rules missing from registry: {missing_rules}. "
            "These must be in the registry to match domain/types.py"
        )

    def test_get_validation_rule_helper(self):
        """Test get_validation_rule() helper function."""
        # Should return rule for valid name
        email_rule = get_validation_rule("email")
        assert email_rule is not None, "get_validation_rule('email') returned None"
        assert email_rule.rule_name == "email"

        # Should return None for invalid name
        invalid_rule = get_validation_rule("nonexistent_rule")
        assert invalid_rule is None, (
            "get_validation_rule() should return None for invalid names"
        )

    def test_get_all_validation_rules_helper(self):
        """Test get_all_validation_rules() helper function."""
        all_rules = get_all_validation_rules()
        assert len(all_rules) == len(VALIDATION_RULES_REGISTRY), (
            "get_all_validation_rules() count doesn't match registry"
        )
        assert all(hasattr(rule, "rule_name") for rule in all_rules), (
            "get_all_validation_rules() returned invalid objects"
        )

    def test_get_rules_by_category_helper(self):
        """Test get_rules_by_category() helper function."""
        auth_rules = get_rules_by_category(ValidationCategory.AUTHENTICATION)
        assert len(auth_rules) >= 4, (
            f"Expected at least 4 AUTHENTICATION rules, found {len(auth_rules)}"
        )
        assert all(
            rule.category == ValidationCategory.AUTHENTICATION for rule in auth_rules
        ), "get_rules_by_category() returned rules with wrong category"

    def test_get_statistics_helper(self):
        """Test get_statistics() helper function."""
        stats = get_statistics()

        # Should have expected keys
        assert "total_rules" in stats, "stats missing 'total_rules'"
        assert "by_category" in stats, "stats missing 'by_category'"

        # Total should match registry
        assert stats["total_rules"] == len(VALIDATION_RULES_REGISTRY), (
            "stats['total_rules'] doesn't match registry count"
        )

        # by_category should be dict
        assert isinstance(stats["by_category"], dict), (
            "stats['by_category'] should be dict"
        )
