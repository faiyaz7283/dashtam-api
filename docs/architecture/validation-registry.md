# Validation Rules Registry Architecture

## Overview

### Purpose

The **Validation Rules Registry** is a metadata-driven catalog that serves as the single source of truth for all validation rules in Dashtam. It follows the **Registry Pattern** established by the Domain Events Registry, Provider Registry, and Rate Limit Registry.

**Key Benefits**:

- **Single source of truth** - All validation rules cataloged in one place
- **Self-documenting** - Metadata includes descriptions, examples, constraints
- **Self-enforcing** - Compliance tests fail if registry incomplete
- **Zero drift** - Can't add validator without registry entry
- **Easy discovery** - Helper functions for accessing rules

### Problem Statement

**Before Registry Pattern**:

- **Centralized validators** (Good ✅): 4 Annotated types in `src/domain/types.py` with 4 validators in `src/domain/validators.py`
- **No catalog** (Gap ⚠️): No central place to see all validation rules
- **No metadata** (Gap ⚠️): Rules lack descriptions, examples, documentation
- **No tests** (Gap ⚠️): No validation that validators are complete
- **Manual discovery** (Gap ⚠️): Must grep codebase to find validators

**The Gap**: Without a registry, developers must manually search for validation rules, lack examples, and have no automated way to ensure validators are properly documented and tested.

### Solution

**With Registry Pattern**:

```python
# src/domain/validators/registry.py - Single source of truth
VALIDATION_RULES_REGISTRY: dict[str, ValidationRuleMetadata] = {
    "email": ValidationRuleMetadata(
        rule_name="email",
        validator_function=validate_email,
        field_constraints={"min_length": 5, "max_length": 255},
        description="Email address with format validation and lowercase normalization",
        examples=["user@example.com", "test.user@domain.co.uk"],
        category=ValidationCategory.AUTHENTICATION,
    ),
    # ... 3 more rules
}
```

**Benefits**:

- ✅ All 4 validation rules cataloged with complete metadata
- ✅ 18 self-enforcing compliance tests
- ✅ Helper functions for easy access (`get_validation_rule`, `get_rules_by_category`)
- ✅ 100% coverage for validation registry module
- ✅ Zero drift - tests fail if metadata incomplete

---

## Architecture Components

### 1. ValidationRuleMetadata (Dataclass)

**Purpose**: Immutable metadata container for a single validation rule.

**Location**: `src/domain/validators/registry.py`

**Structure**:

```python
@dataclass(frozen=True, kw_only=True)
class ValidationRuleMetadata:
    """Metadata for a single validation rule.
    
    Attributes:
        rule_name: Unique identifier (e.g., 'email', 'password').
        validator_function: Callable that validates input and returns validated value.
        field_constraints: Pydantic Field constraints (min_length, max_length, pattern).
        description: Human-readable description of validation requirements.
        examples: List of valid example values.
        category: Category for grouping (AUTHENTICATION, API_PARAMETERS, etc.).
    """
    rule_name: str
    validator_function: Callable[[str], str]
    field_constraints: dict[str, int | str]
    description: str
    examples: list[str]
    category: ValidationCategory
```

**Key Properties**:

- **Immutable** (`frozen=True`) - Prevents accidental modification
- **Type-safe** - All fields have type hints
- **Self-documenting** - Description and examples included
- **Callable validator** - Function reference for actual validation

### 2. ValidationCategory (Enum)

**Purpose**: Categorize validation rules by their domain purpose.

**Location**: `src/domain/validators/registry.py`

**Structure**:

```python
class ValidationCategory(str, Enum):
    """Categories for validation rules."""
    AUTHENTICATION = "authentication"  # Email, Password, Tokens
    API_PARAMETERS = "api_parameters"  # UUIDs, booleans, filters (future)
    PROVIDER_DATA = "provider_data"    # Provider-specific validation (future)
    DOMAIN_VALUES = "domain_values"    # Money, dates, etc. (future)
```

**Current Usage**:

- **AUTHENTICATION**: All 4 current rules (email, password, verification_token, refresh_token)
- **API_PARAMETERS**: Reserved for future (Query/Path parameter validation)
- **PROVIDER_DATA**: Reserved for future (Provider-specific validation)
- **DOMAIN_VALUES**: Reserved for future (Money, DateRange validation)

### 3. VALIDATION_RULES_REGISTRY (Constant)

**Purpose**: The registry itself - single source of truth for all validation rules.

**Location**: `src/domain/validators/registry.py`

**Structure**:

```python
VALIDATION_RULES_REGISTRY: dict[str, ValidationRuleMetadata] = {
    "email": ValidationRuleMetadata(...),
    "password": ValidationRuleMetadata(...),
    "verification_token": ValidationRuleMetadata(...),
    "refresh_token": ValidationRuleMetadata(...),
}
```

**Key Properties**:

- **Dictionary keyed by rule_name** - Fast O(1) lookup
- **Complete metadata** - Every rule has all 6 required fields
- **Immutable entries** - Metadata objects are frozen dataclasses
- **Self-validating** - Compliance tests enforce completeness

### 4. Helper Functions

**Purpose**: Convenient access to registry data.

**Location**: `src/domain/validators/registry.py`

#### get_validation_rule()

```python
def get_validation_rule(rule_name: str) -> ValidationRuleMetadata | None:
    """Get validation rule metadata by name.
    
    Args:
        rule_name: Name of the validation rule (e.g., 'email').
    
    Returns:
        ValidationRuleMetadata if found, None otherwise.
    
    Example:
        >>> rule = get_validation_rule("email")
        >>> if rule:
        ...     validated = rule.validator_function("user@example.com")
    """
    return VALIDATION_RULES_REGISTRY.get(rule_name)
```

#### get_all_validation_rules()

```python
def get_all_validation_rules() -> list[ValidationRuleMetadata]:
    """Get all validation rules in the registry.
    
    Returns:
        List of all ValidationRuleMetadata objects.
    
    Example:
        >>> all_rules = get_all_validation_rules()
        >>> print(f"Total rules: {len(all_rules)}")
    """
    return list(VALIDATION_RULES_REGISTRY.values())
```

#### get_rules_by_category()

```python
def get_rules_by_category(category: ValidationCategory) -> list[ValidationRuleMetadata]:
    """Get all validation rules in a specific category.
    
    Args:
        category: Category to filter by.
    
    Returns:
        List of ValidationRuleMetadata objects in the category.
    
    Example:
        >>> auth_rules = get_rules_by_category(ValidationCategory.AUTHENTICATION)
        >>> print(f"Auth rules: {len(auth_rules)}")
    """
    return [r for r in VALIDATION_RULES_REGISTRY.values() if r.category == category]
```

#### get_statistics()

```python
def get_statistics() -> dict[str, int | dict[str, int]]:
    """Get registry statistics.
    
    Returns:
        Dictionary with:
        - total_rules: Total number of rules
        - by_category: Count of rules per category
    
    Example:
        >>> stats = get_statistics()
        >>> print(f"Total: {stats['total_rules']}")
        >>> print(f"Auth: {stats['by_category']['authentication']}")
    """
    # Implementation counts rules by category
```

---

## Current Validation Rules

### Complete Registry (4 Rules)

All rules are in the **AUTHENTICATION** category.

#### 1. email

**Rule Name**: `email`

**Validator Function**: `validate_email(v: str) -> str`

**Field Constraints**:

- `min_length`: 5
- `max_length`: 255

**Description**: Email address with format validation and lowercase normalization

**Examples**:

- `user@example.com`
- `test.user@domain.co.uk`

**Validation Logic**:

- Matches regex: `^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$`
- Converts to lowercase
- Raises `ValueError` if format invalid

**Usage**:

```python
from src.domain.types import Email

# In Pydantic models
class UserCreate(BaseModel):
    email: Email  # Auto-validates with constraints + validator
```

#### 2. password

**Rule Name**: `password`

**Validator Function**: `validate_strong_password(v: str) -> str`

**Field Constraints**:

- `min_length`: 8
- `max_length`: 128

**Description**: Strong password: 8+ chars, uppercase, lowercase, digit, special char

**Examples**:

- `SecurePass123!`
- `MyP@ssw0rd2024`

**Validation Logic**:

- Minimum 8 characters
- At least 1 uppercase letter
- At least 1 lowercase letter
- At least 1 digit
- At least 1 special character
- Raises `ValueError` if requirements not met

**Usage**:

```python
from src.domain.types import Password

class UserCreate(BaseModel):
    password: Password  # Enforces strong password requirements
```

#### 3. verification_token

**Rule Name**: `verification_token`

**Validator Function**: `validate_token_format(v: str) -> str`

**Field Constraints**:

- `min_length`: 16
- `max_length`: 128
- `pattern`: `^[a-fA-F0-9]+$`

**Description**: Email verification or password reset token (hexadecimal string)

**Examples**:

- `abc123def456789fedcba`
- `0123456789abcdef`

**Validation Logic**:

- Must be hexadecimal string (a-f, A-F, 0-9)
- Between 16 and 128 characters
- Raises `ValueError` if non-hex characters found

**Usage**:

```python
from src.domain.types import VerificationToken

class EmailVerification(BaseModel):
    token: VerificationToken
```

#### 4. refresh_token

**Rule Name**: `refresh_token`

**Validator Function**: `validate_refresh_token_format(v: str) -> str`

**Field Constraints**:

- `min_length`: 16
- `max_length`: 256
- `pattern`: `^[A-Za-z0-9_-]+$`

**Description**: Opaque refresh token for JWT refresh flow (urlsafe base64)

**Examples**:

- `dGhpcyBpcyBhIHJhbmRvbSB0b2tlbg`
- `YW5vdGhlcl90b2tlbl9leGFtcGxl`

**Validation Logic**:

- Must be urlsafe base64 format (A-Z, a-z, 0-9, _, -)
- Between 16 and 256 characters
- Raises `ValueError` if invalid characters found

**Usage**:

```python
from src.domain.types import RefreshToken

class TokenRefreshRequest(BaseModel):
    refresh_token: RefreshToken
```

---

## Self-Enforcing Compliance Tests

### Test Architecture

**Location**: `tests/unit/test_validation_registry_compliance.py`

**Total Tests**: 18 tests across 4 test classes

**Purpose**: Ensure `VALIDATION_RULES_REGISTRY` remains complete and prevents drift.

### Test Class 1: Registry Completeness (8 tests)

**Purpose**: Verify all rules have complete and valid metadata.

#### test_all_rules_have_validator_functions()

**Verifies**: Every rule has a callable `validator_function`.

**Fails if**: Any rule's `validator_function` is not callable.

**Example Failure**:

```text
Rule 'email' has non-callable validator_function: None
```

#### test_all_rules_have_field_constraints()

**Verifies**: Every rule has `field_constraints` dict (can be empty).

**Fails if**: Any rule's `field_constraints` is not a dict.

#### test_all_rules_have_descriptions()

**Verifies**: Every rule has non-empty description.

**Fails if**: Any rule has empty or whitespace-only description.

#### test_all_rules_have_examples()

**Verifies**: Every rule has at least one example.

**Fails if**: Any rule has empty `examples` list.

#### test_all_rules_have_valid_categories()

**Verifies**: Every rule has a valid `ValidationCategory` enum value.

**Fails if**: Any rule's category is not in `ValidationCategory` enum.

#### test_rule_names_are_unique()

**Verifies**: Registry keys (rule names) are unique.

**Fails if**: Duplicate rule names found.

#### test_rule_names_follow_convention()

**Verifies**: Rule names use snake_case convention.

**Fails if**: Rule names have uppercase or invalid characters.

**Valid Examples**: `email`, `password`, `refresh_token`

#### test_field_constraints_are_valid_pydantic_args()

**Verifies**: Field constraints use valid Pydantic Field arguments.

**Valid Keys**: `min_length`, `max_length`, `pattern`, `gt`, `ge`, `lt`, `le`, `multiple_of`

**Fails if**: Any constraint key not in valid set.

### Test Class 2: Validator Functions (4 tests)

**Purpose**: Verify validator functions work correctly.

#### test_all_validators_are_callable()

**Verifies**: All validator functions are callable.

#### test_validators_raise_value_error_on_invalid()

**Verifies**: Validators raise `ValueError` for invalid input.

**Test Cases**:

- `email`: `"not-an-email"` → raises `ValueError`
- `password`: `"weak"` → raises `ValueError`
- `verification_token`: `"not-hex!"` → raises `ValueError`
- `refresh_token`: `"invalid chars!"` → raises `ValueError`

#### test_validators_return_correct_type()

**Verifies**: Validators return `str` (or appropriate type).

**Test Cases**:

- `email`: `"user@example.com"` → returns `str`
- `password`: `"SecurePass123!"` → returns `str`
- `verification_token`: `"abc123def456"` → returns `str`
- `refresh_token`: `"dGhpcyBpcyBh"` → returns `str`

#### test_validators_handle_edge_cases()

**Verifies**: Validators handle edge cases (empty strings, None).

**Test Cases**:

- Empty string `""` → raises `ValueError` for all validators

### Test Class 3: Type Consistency (3 tests)

**Purpose**: Verify consistency between registry and actual usage.

#### test_domain_types_use_registry_validators()

**Verifies**: `src/domain/types.py` uses same validator functions as registry.

**Checks**:

- `Email` uses `validate_email` (same function as `VALIDATION_RULES_REGISTRY["email"]`)
- `Password` uses `validate_strong_password`
- `VerificationToken` uses `validate_token_format`
- `RefreshToken` uses `validate_refresh_token_format`

#### test_no_duplicate_validator_logic()

**Verifies**: Each validator function is used exactly once.

**Fails if**: Multiple rules use the same validator function.

#### test_examples_pass_validation()

**Verifies**: All examples in metadata pass their validators.

**Fails if**: Any example raises `ValueError` when validated.

### Test Class 4: Statistics (3 tests)

**Purpose**: Snapshot tests for current registry state.

#### test_registry_has_minimum_rules()

**Verifies**: Registry has at least 4 rules (current implementation).

**Fails if**: Rule count drops below 4 (indicates rules were removed).

#### test_category_distribution()

**Verifies**: AUTHENTICATION category has at least 4 rules.

**Fails if**: Category counts don't match expected distribution.

#### test_all_existing_types_covered()

**Verifies**: All 4 critical rules exist (`email`, `password`, `verification_token`, `refresh_token`).

**Fails if**: Any critical rule missing from registry.

---

## Integration Examples

### Example 1: Using Registry in Documentation

```python
from src.domain.validators.registry import get_all_validation_rules

# Generate documentation from registry
def generate_validation_docs():
    """Auto-generate validation documentation from registry."""
    rules = get_all_validation_rules()
    
    for rule in rules:
        print(f"## {rule.rule_name}")
        print(f"**Description**: {rule.description}")
        print(f"**Constraints**: {rule.field_constraints}")
        print(f"**Examples**: {', '.join(rule.examples)}")
        print()
```

### Example 2: Using Registry for API Documentation

```python
from src.domain.validators.registry import get_validation_rule

def get_field_schema(rule_name: str) -> dict:
    """Generate OpenAPI schema from registry metadata."""
    rule = get_validation_rule(rule_name)
    if not rule:
        raise ValueError(f"Unknown validation rule: {rule_name}")
    
    schema = {
        "type": "string",
        "description": rule.description,
        "example": rule.examples[0] if rule.examples else None,
    }
    
    # Add Pydantic Field constraints to schema
    if "min_length" in rule.field_constraints:
        schema["minLength"] = rule.field_constraints["min_length"]
    if "max_length" in rule.field_constraints:
        schema["maxLength"] = rule.field_constraints["max_length"]
    if "pattern" in rule.field_constraints:
        schema["pattern"] = rule.field_constraints["pattern"]
    
    return schema
```

### Example 3: Using Registry for Testing

```python
from src.domain.validators.registry import get_rules_by_category, ValidationCategory

def test_all_auth_validators_work():
    """Test all authentication validators with their examples."""
    auth_rules = get_rules_by_category(ValidationCategory.AUTHENTICATION)
    
    for rule in auth_rules:
        for example in rule.examples:
            # Each example should pass validation
            result = rule.validator_function(example)
            assert isinstance(result, str)
            assert result  # Non-empty
```

### Example 4: Using Registry for Monitoring

```python
from src.domain.validators.registry import get_statistics

def log_registry_stats():
    """Log validation registry statistics for monitoring."""
    stats = get_statistics()
    
    logger.info(
        "validation_registry_stats",
        total_rules=stats["total_rules"],
        by_category=stats["by_category"],
    )
```

---

## Adding New Validation Rules

### Step-by-Step Guide

#### Step 1: Create Validator Function

**Location**: `src/domain/validators/functions.py`

```python
def validate_phone_number(v: str) -> str:
    """Validate phone number format (E.164).
    
    Args:
        v: Phone number string (e.g., '+12345678901').
    
    Returns:
        Validated phone number string.
    
    Raises:
        ValueError: If phone number format is invalid.
    """
    import re
    
    # E.164 format: +[country code][number] (max 15 digits)
    pattern = r"^\+[1-9]\d{1,14}$"
    
    if not re.match(pattern, v):
        raise ValueError(
            f"Invalid phone number format: {v}. "
            "Must be E.164 format (e.g., +12345678901)"
        )
    
    return v
```

#### Step 2: Add to Registry

**Location**: `src/domain/validators/registry.py`

```python
# Import new validator
from src.domain.validators.functions import validate_phone_number

# Add to VALIDATION_RULES_REGISTRY
VALIDATION_RULES_REGISTRY: dict[str, ValidationRuleMetadata] = {
    # ... existing rules ...
    "phone_number": ValidationRuleMetadata(
        rule_name="phone_number",
        validator_function=validate_phone_number,
        field_constraints={
            "min_length": 8,
            "max_length": 16,
            "pattern": r"^\+[1-9]\d{1,14}$",
        },
        description="Phone number in E.164 format (+country code + number)",
        examples=["+12345678901", "+442071234567"],
        category=ValidationCategory.AUTHENTICATION,  # or appropriate category
    ),
}
```

#### Step 3: Export from \_\_init\_\_.py

**Location**: `src/domain/validators/__init__.py`

```python
# Add to imports
from src.domain.validators.functions import (
    validate_email,
    validate_phone_number,  # NEW
    # ... other validators
)

# Add to __all__
__all__ = [
    "validate_email",
    "validate_phone_number",  # NEW
    # ... rest of exports
]
```

#### Step 4: Create Annotated Type (Optional)

**Location**: `src/domain/types.py`

```python
from pydantic import AfterValidator, Field
from typing import Annotated

from src.domain.validators import validate_phone_number

PhoneNumber = Annotated[
    str,
    Field(min_length=8, max_length=16, pattern=r"^\+[1-9]\d{1,14}$"),
    AfterValidator(validate_phone_number),
]
```

#### Step 5: Run Tests

**Tests will tell you what's missing**:

```bash
make test
```

**Expected Results**:

- ✅ `test_all_rules_have_validator_functions()` - Passes (function is callable)
- ✅ `test_all_rules_have_field_constraints()` - Passes (constraints dict present)
- ✅ `test_all_rules_have_descriptions()` - Passes (description provided)
- ✅ `test_all_rules_have_examples()` - Passes (examples provided)
- ✅ `test_examples_pass_validation()` - Passes (examples valid)
- ✅ `test_registry_has_minimum_rules()` - Passes (5 rules now)

#### Step 6: Update Snapshot Test (If Needed)

If you changed category distribution or added first rule in new category:

**Location**: `tests/unit/test_validation_registry_compliance.py`

```python
def test_category_distribution(self):
    """Update expected counts if you added rules to new category."""
    stats = get_statistics()
    by_category = stats["by_category"]
    
    assert "authentication" in by_category
    assert by_category["authentication"] >= 5  # Was 4, now 5
```

---

## Testing Strategy

### Coverage Targets

- **Overall**: 88%+ (Dashtam target maintained)
- **Validation Registry Module**: 100% achieved

**Achieved Coverage**:

```text
src/domain/validators/registry.py    100%    (206/206 statements)
tests/unit/test_validation_registry_compliance.py    100%    (334/334 statements)
```

### Test Execution

```bash
# Run all validation tests
pytest tests/unit/test_validation_registry_compliance.py -v

# Run specific test class
pytest tests/unit/test_validation_registry_compliance.py::TestValidationRegistryCompleteness -v

# Run with coverage
pytest tests/unit/test_validation_registry_compliance.py --cov=src/domain/validators/registry --cov-report=term-missing
```

### Continuous Integration

**GitHub Actions** (`.github/workflows/test.yml`):

- All 18 compliance tests run on every PR
- Tests fail if registry incomplete
- Can't merge until tests pass
- **Zero drift enforcement**

---

## Design Decisions

### Why Metadata-Driven Registry?

**Rationale**: Follows established pattern from Domain Events Registry, Provider Registry, and Rate Limit Registry.

**Benefits**:

- Single source of truth
- Self-documenting (descriptions, examples)
- Self-enforcing (tests validate completeness)
- Easy to extend (add metadata fields)

**Alternative Considered**: Decorator-based registration

**Rejected Because**: Less explicit, harder to test, no central catalog to review.

### Why dict Instead of list?

**Rationale**: Fast O(1) lookup by rule name.

**Benefits**:

- `get_validation_rule("email")` is O(1)
- Natural key-value relationship
- Enforces unique rule names

**Alternative Considered**: List of metadata objects

**Rejected Because**: O(n) lookup, no uniqueness enforcement, less ergonomic.

### Why Separate Validator Functions?

**Rationale**: Keep validation logic separate from registry metadata.

**Benefits**:

- Validators can be tested independently
- Registry is pure metadata (no logic)
- Validators can be imported directly if needed
- Follows single responsibility principle

**Alternative Considered**: Inline lambdas in registry

**Rejected Because**: Harder to test, less readable, no docstrings.

### Why ValidationCategory Enum?

**Rationale**: Type-safe categorization with IDE autocomplete.

**Benefits**:

- Type-safe (can't use invalid category)
- IDE autocomplete
- Easy to add categories
- Consistent with Provider Registry (ProviderCategory) and Domain Events Registry (EventCategory)

**Alternative Considered**: String categories

**Rejected Because**: Typo-prone, no type safety, no IDE support.

### Why field_constraints as dict?

**Rationale**: Flexible structure for Pydantic Field arguments.

**Benefits**:

- Can add any Pydantic Field constraint
- Easy to extend (new constraint types)
- Self-documenting (constraint names are keys)

**Alternative Considered**: Separate fields for each constraint type

**Rejected Because**: Rigid structure, hard to extend, verbose.

---

## Registry Pattern Consistency

### Comparison with Other Registries

This implementation follows the same pattern as three other Dashtam registries:

#### Domain Events Registry

**Similarities**:

- ✅ Metadata dataclass (`EventMetadata` → `ValidationRuleMetadata`)
- ✅ Category enum (`EventCategory` → `ValidationCategory`)
- ✅ Registry constant (`EVENT_REGISTRY` → `VALIDATION_RULES_REGISTRY`)
- ✅ Helper functions (`get_event_metadata` → `get_validation_rule`)
- ✅ Self-enforcing compliance tests (18 tests each)

**Differences**:

- Domain Events: List registry (order matters for auto-wiring)
- Validation Rules: Dict registry (fast lookup by name)
- Domain Events: Auto-wiring in container
- Validation Rules: No wiring (validators are pure functions)

#### Provider Registry

**Similarities**:

- ✅ Dict-based registry (keyed by enum)
- ✅ Category enum for grouping
- ✅ Helper functions for filtering
- ✅ 100% coverage target
- ✅ Self-enforcing compliance tests

**Differences**:

- Provider Registry: Keys are `Provider` enum values
- Validation Rules: Keys are string rule names
- Provider Registry: 19 compliance tests
- Validation Rules: 18 compliance tests

#### Rate Limit Registry

**Similarities**:

- ✅ Dict-based registry (keyed by endpoint pattern)
- ✅ 23 self-enforcing compliance tests
- ✅ Completeness, Consistency, Statistics test classes
- ✅ Helper functions for access

**Differences**:

- Rate Limit: Rules are infrastructure config
- Validation Rules: Rules are domain validators
- Rate Limit: Uses `RateLimitRule` value object
- Validation Rules: Uses `ValidationRuleMetadata` dataclass

### Architectural Consistency

**All 4 registries follow**:

1. **Single source of truth** - One file contains all metadata
2. **Metadata-driven** - Dataclass with type-safe fields
3. **Self-enforcing** - Compliance tests fail if incomplete
4. **Helper functions** - Easy access to registry data
5. **100% coverage target** - Complete test coverage
6. **Documentation** - Architecture doc for each registry

**Pattern Reference**: `docs/architecture/registry.md`

---

## Future Enhancements

### Phase 2: API Parameter Validators (Future)

**Goal**: Add validators for common API parameter types.

**Candidates**:

- `uuid`: UUID format validation
- `boolean_filter`: Boolean query parameters
- `optional_string`: Nullable string filters
- `date_range`: Date range validation
- `pagination_offset`: Non-negative integer

**Registry Entry Example**:

```python
"uuid": ValidationRuleMetadata(
    rule_name="uuid",
    validator_function=validate_uuid_format,
    field_constraints={
        "pattern": r"^[a-f0-9]{8}-[a-f0-9]{4}-4[a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12}$",
    },
    description="UUID v4 format validation",
    examples=["550e8400-e29b-41d4-a716-446655440000"],
    category=ValidationCategory.API_PARAMETERS,
),
```

### Phase 3: Provider Data Validators (Future)

**Goal**: Add validators for provider-specific data formats.

**Candidates**:

- `provider_account_id`: Provider account identifier format
- `cusip`: CUSIP security identifier (9 chars)
- `isin`: ISIN security identifier (12 chars)
- `ticker_symbol`: Stock ticker symbol (1-5 uppercase letters)

### Phase 4: Domain Value Validators (Future)

**Goal**: Add validators for domain value objects.

**Candidates**:

- `money_amount`: Decimal precision validation
- `currency_code`: ISO 4217 currency code (3 uppercase letters)
- `date_iso8601`: ISO 8601 date format
- `timezone`: Valid timezone identifier

---

## Troubleshooting

### Test Failure: "Rule has non-callable validator_function"

**Cause**: `validator_function` field is not callable.

**Solution**: Check that you imported the function correctly:

```python
# ❌ Wrong: Calling the function
validator_function=validate_email("test")  # Returns str, not callable

# ✅ Correct: Function reference
validator_function=validate_email  # Function itself
```

### Test Failure: "Rule has empty description"

**Cause**: `description` field is empty or whitespace-only.

**Solution**: Provide meaningful description:

```python
# ❌ Wrong
description=""

# ✅ Correct
description="Email address with format validation and lowercase normalization"
```

### Test Failure: "Rule has no examples"

**Cause**: `examples` list is empty.

**Solution**: Provide at least one valid example:

```python
# ❌ Wrong
examples=[]

# ✅ Correct
examples=["user@example.com", "test@domain.co.uk"]
```

### Test Failure: "Example failed validation"

**Cause**: Example in metadata doesn't pass its own validator.

**Solution**: Test your examples before adding to registry:

```python
# Test manually first
example = "user@example.com"
try:
    result = validate_email(example)
    print(f"Valid: {result}")
except ValueError as e:
    print(f"Invalid: {e}")
```

### ImportError: "cannot import name 'validate_xyz'"

**Cause**: New validator not exported from `__init__.py`.

**Solution**: Add to exports:

```python
# src/domain/validators/__init__.py
from src.domain.validators.functions import (
    validate_email,
    validate_xyz,  # ADD THIS
)

__all__ = [
    "validate_email",
    "validate_xyz",  # ADD THIS
]
```

---

## References

### Related Dashtam Registries

- **Domain Events Registry** - `docs/architecture/domain-events.md` (Section 5.1)
- **Provider Registry** - `docs/architecture/provider-registry.md`
- **Rate Limit Registry** - `docs/architecture/rate-limit.md` (Section 5)

### Registry Pattern Documentation

- **Registry Pattern Theory** - `docs/architecture/registry.md`
- **Implementation Guide** - `docs/architecture/registry.md` (Section: Implementation Guide)
- **Best Practices** - `docs/architecture/registry.md` (Section: Best Practices)

### Implementation Files

- **Registry**: `src/domain/validators/registry.py`
- **Validators**: `src/domain/validators/functions.py`
- **Exports**: `src/domain/validators/__init__.py`
- **Compliance Tests**: `tests/unit/test_validation_registry_compliance.py`

### Development Workflow

- **Feature Development Checklist** - `~/references/starter/development-checklist.md`
- **Feature Roadmap** - `~/references/starter/dashtam-feature-roadmap.md`

---

**Created**: 2025-12-31 | **Last Updated**: 2025-12-31
