"""Validation Rules Registry (F8.4).

Single source of truth for all validation rules with self-enforcing compliance tests.

This registry follows the same architectural pattern as:
- F7.7: Domain Events Registry (metadata-driven, auto-wiring)
- F8.1: Provider Registry (single source of truth, 100% coverage)
- F8.3: Rate Limit Registry Compliance (self-enforcing validation)

Pattern: Registry Pattern with metadata catalog and helper functions.

Reference:
    - docs/architecture/validation-registry-architecture.md
    - docs/architecture/registry-pattern-architecture.md
"""

from dataclasses import dataclass
from enum import Enum
from typing import Callable

from src.domain.validators.functions import (
    validate_email,
    validate_refresh_token_format,
    validate_strong_password,
    validate_token_format,
)


class ValidationCategory(str, Enum):
    """Categories for validation rules.

    Used to group validators by their domain purpose.
    """

    AUTHENTICATION = "authentication"  # Email, Password, Tokens
    API_PARAMETERS = "api_parameters"  # UUIDs, booleans, filters (future)
    PROVIDER_DATA = "provider_data"  # Provider-specific validation (future)
    DOMAIN_VALUES = "domain_values"  # Money, dates, etc. (future)


@dataclass(frozen=True, kw_only=True)
class ValidationRuleMetadata:
    """Metadata for a single validation rule.

    Contains all information needed to use a validator: function, constraints,
    documentation, and examples.

    Attributes:
        rule_name: Unique identifier for the rule (e.g., 'email', 'password').
        validator_function: Callable that validates input and returns validated value.
        field_constraints: Pydantic Field constraints (min_length, max_length, pattern).
        description: Human-readable description of validation requirements.
        examples: List of valid example values.
        category: Category for grouping (AUTHENTICATION, API_PARAMETERS, etc.).

    Example:
        >>> metadata = ValidationRuleMetadata(
        ...     rule_name="email",
        ...     validator_function=validate_email,
        ...     field_constraints={"min_length": 5, "max_length": 255},
        ...     description="Email address with format validation",
        ...     examples=["user@example.com"],
        ...     category=ValidationCategory.AUTHENTICATION,
        ... )
    """

    rule_name: str
    validator_function: Callable[[str], str]
    field_constraints: dict[str, int | str]
    description: str
    examples: list[str]
    category: ValidationCategory


# =============================================================================
# Validation Rules Registry
# =============================================================================

VALIDATION_RULES_REGISTRY: dict[str, ValidationRuleMetadata] = {
    "email": ValidationRuleMetadata(
        rule_name="email",
        validator_function=validate_email,
        field_constraints={
            "min_length": 5,
            "max_length": 255,
        },
        description="Email address with format validation and lowercase normalization",
        examples=["user@example.com", "test.user@domain.co.uk"],
        category=ValidationCategory.AUTHENTICATION,
    ),
    "password": ValidationRuleMetadata(
        rule_name="password",
        validator_function=validate_strong_password,
        field_constraints={
            "min_length": 8,
            "max_length": 128,
        },
        description="Strong password: 8+ chars, uppercase, lowercase, digit, special char",
        examples=["SecurePass123!", "MyP@ssw0rd2024"],
        category=ValidationCategory.AUTHENTICATION,
    ),
    "verification_token": ValidationRuleMetadata(
        rule_name="verification_token",
        validator_function=validate_token_format,
        field_constraints={
            "min_length": 16,
            "max_length": 128,
            "pattern": r"^[a-fA-F0-9]+$",
        },
        description="Email verification or password reset token (hexadecimal string)",
        examples=["abc123def456789fedcba", "0123456789abcdef"],
        category=ValidationCategory.AUTHENTICATION,
    ),
    "refresh_token": ValidationRuleMetadata(
        rule_name="refresh_token",
        validator_function=validate_refresh_token_format,
        field_constraints={
            "min_length": 16,
            "max_length": 256,
            "pattern": r"^[A-Za-z0-9_-]+$",
        },
        description="Opaque refresh token for JWT refresh flow (urlsafe base64)",
        examples=["dGhpcyBpcyBhIHJhbmRvbSB0b2tlbg", "YW5vdGhlcl90b2tlbl9leGFtcGxl"],
        category=ValidationCategory.AUTHENTICATION,
    ),
}


# =============================================================================
# Helper Functions
# =============================================================================


def get_validation_rule(rule_name: str) -> ValidationRuleMetadata | None:
    """Get validation rule metadata by name.

    Args:
        rule_name: Name of the validation rule (e.g., 'email', 'password').

    Returns:
        ValidationRuleMetadata if found, None otherwise.

    Example:
        >>> rule = get_validation_rule("email")
        >>> if rule:
        ...     validated = rule.validator_function("user@example.com")
    """
    return VALIDATION_RULES_REGISTRY.get(rule_name)


def get_all_validation_rules() -> list[ValidationRuleMetadata]:
    """Get all validation rules in the registry.

    Returns:
        List of all ValidationRuleMetadata objects.

    Example:
        >>> all_rules = get_all_validation_rules()
        >>> print(f"Total rules: {len(all_rules)}")
    """
    return list(VALIDATION_RULES_REGISTRY.values())


def get_rules_by_category(category: ValidationCategory) -> list[ValidationRuleMetadata]:
    """Get all validation rules in a specific category.

    Args:
        category: Category to filter by (AUTHENTICATION, API_PARAMETERS, etc.).

    Returns:
        List of ValidationRuleMetadata objects in the category.

    Example:
        >>> auth_rules = get_rules_by_category(ValidationCategory.AUTHENTICATION)
        >>> print(f"Auth rules: {len(auth_rules)}")
    """
    return [
        rule for rule in VALIDATION_RULES_REGISTRY.values() if rule.category == category
    ]


def get_statistics() -> dict[str, int | dict[str, int]]:
    """Get registry statistics.

    Returns:
        Dictionary with:
        - total_rules: Total number of rules
        - by_category: Count of rules per category

    Example:
        >>> stats = get_statistics()
        >>> print(f"Total: {stats['total_rules']}")
        >>> print(f"Auth: {stats['by_category'][`'authentication'`]}")
    """
    rules = list(VALIDATION_RULES_REGISTRY.values())
    category_counts: dict[str, int] = {}

    for rule in rules:
        category_key = rule.category.value
        category_counts[category_key] = category_counts.get(category_key, 0) + 1

    return {
        "total_rules": len(rules),
        "by_category": category_counts,
    }
