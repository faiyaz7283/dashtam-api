"""Validators package exports.

Exports:
    - Validator functions (from functions.py)
    - Registry components (from registry.py)
"""

# Validator functions (backward compatibility)
from src.domain.validators.functions import (
    validate_email,
    validate_refresh_token_format,
    validate_strong_password,
    validate_token_format,
)

# Registry components (new in F8.4)
from src.domain.validators.registry import (
    VALIDATION_RULES_REGISTRY,
    ValidationCategory,
    ValidationRuleMetadata,
    get_all_validation_rules,
    get_rules_by_category,
    get_statistics,
    get_validation_rule,
)

__all__ = [
    # Validator functions
    "validate_email",
    "validate_strong_password",
    "validate_token_format",
    "validate_refresh_token_format",
    # Registry
    "VALIDATION_RULES_REGISTRY",
    "ValidationRuleMetadata",
    "ValidationCategory",
    "get_validation_rule",
    "get_all_validation_rules",
    "get_rules_by_category",
    "get_statistics",
]
