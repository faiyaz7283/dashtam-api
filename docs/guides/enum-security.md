# Enum Security Guidelines

Security considerations and best practices for managing domain enums in Dashtam.

---

## Overview

Domain enums (TransactionType, TransactionSubtype, AssetType, etc.) are **critical financial primitives**. They define the vocabulary of our financial data model and directly impact:

- Financial calculations
- Audit trails
- Compliance reporting
- Business logic routing
- Data integrity

**Key Principle**: Enums are hardcoded in Python files, which means developers can modify them. This guide documents the security implications and defense strategies.

---

## Security Symptoms (Attack Vectors)

### Symptom 1: Malicious Enum Addition

**Description**: Developer adds suspicious types to bypass business logic or hide transactions.

**Example**:

```python
# Malicious addition to TransactionSubtype
class TransactionSubtype(str, Enum):
    # ... legitimate values ...
    ADMIN_OVERRIDE = "admin_override"  # Bypass validation
    HIDDEN_TRANSFER = "hidden_transfer"  # Hide from reports
    SECRET_WITHDRAWAL = "secret_withdrawal"  # Evade audit
```

**Impact**:

- Could bypass audit trails
- Hide fraudulent transactions
- Manipulate financial reporting
- Evade compliance checks
- Create untraceable money movements

**Real-World Risk**: High - This is the most likely attack vector

---

### Symptom 2: Enum Value Modification

**Description**: Changing the string value of an existing enum to flip its meaning.

**Example**:

```python
# Before (correct)
WITHDRAWAL = "withdrawal"

# After (malicious)
WITHDRAWAL = "deposit"  # Flips transaction direction!
```

**Impact**:

- **CRITICAL** - Flips financial direction
- All withdrawals become deposits in reports
- Catastrophic for accounting reconciliation
- Could enable theft through balance manipulation
- Breaks historical data integrity

**Real-World Risk**: Critical - Would be caught quickly but causes immediate damage

---

### Symptom 3: Helper Method Manipulation

**Description**: Altering classification logic to hide or misclassify transactions.

**Example**:

```python
@classmethod
def security_related(cls) -> list["TransactionType"]:
    # Malicious: exclude TRADE to hide trading activity
    return [cls.INCOME]  # TRADE removed!
```

**Impact**:

- Hide transactions from security-related queries
- Break compliance reports (e.g., Form 1099 reporting)
- Evade tax reporting requirements
- Misclassify transactions in analytics

**Real-World Risk**: Medium - Subtle and harder to detect

---

### Symptom 4: Enum Count/Coverage Manipulation

**Description**: Removing or commenting out legitimate enum values.

**Example**:

```python
class TransactionSubtype(str, Enum):
    BUY = "buy"
    SELL = "sell"
    # SHORT_SELL = "short_sell"  # Commented out to hide short sales
```

**Impact**:

- Breaks existing transactions (database references invalid enum)
- Forces use of fallback values (e.g., UNKNOWN)
- Obscures specific transaction types
- Data quality degradation

**Real-World Risk**: Low - Causes immediate failures, easy to detect

---

## Remedies (Defense in Depth)

### Layer 1: Code Review Process (PRIMARY DEFENSE)

**Required for ALL enum changes.**

#### GitHub CODEOWNERS

```yaml
# .github/CODEOWNERS
# Enum changes require security team approval
src/domain/enums/*.py @security-team @senior-engineers @compliance-team
alembic/versions/*enum*.py @security-team @compliance-team
```

#### Branch Protection Rules

```yaml
# GitHub/GitLab branch protection
branch_protection:
  required_reviews: 2  # Minimum 2 approvals
  require_security_review: true  # For domain/enums/* changes
  dismiss_stale_reviews: true  # Re-review after new commits
  require_code_owner_review: true  # CODEOWNERS must approve
  restrict_push: true  # No direct commits to main/development
```

**Process**:

1. Developer creates PR with enum changes
2. Automated checks run (see Layer 2)
3. Two senior engineers review
4. Security team member reviews
5. Compliance team reviews (if financial impact)
6. All checks pass → merge allowed

**Protection Level**: High - Human oversight catches malicious intent

---

### Layer 2: Automated Validation (CI/CD)

**Automated checks run on every commit/PR.**

#### Pre-commit Hook

```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: enum-audit
        name: Audit Enum Changes
        entry: python scripts/audit_enum_changes.py
        language: python
        files: ^src/domain/enums/.*\.py$
        pass_filenames: true
```

#### Audit Script

```python
# scripts/audit_enum_changes.py
"""Validate enum changes don't introduce security issues."""

import re
import sys
from pathlib import Path

APPROVED_PATTERN = re.compile(r'^[A-Z_]+\s*=\s*"[a-z_]+"')
FORBIDDEN_KEYWORDS = [
    "admin", "override", "bypass", "hidden", "secret",
    "test", "debug", "temp", "hack", "backdoor"
]

def audit_enum_file(filepath: str) -> list[str]:
    """Return list of security concerns.
    
    Args:
        filepath: Path to enum file to audit.
        
    Returns:
        List of security concern messages (empty if clean).
    """
    concerns = []
    
    with open(filepath) as f:
        content = f.read()
        lines = content.split("\n")
        
        for line_num, line in enumerate(lines, 1):
            # Check for forbidden keywords
            for keyword in FORBIDDEN_KEYWORDS:
                if keyword in line.lower() and "=" in line:
                    concerns.append(
                        f"{filepath}:{line_num}: "
                        f"Forbidden keyword '{keyword}' in enum definition"
                    )
            
            # Validate enum value format (variable = "value")
            stripped = line.strip()
            if "=" in stripped and "Enum" not in stripped and stripped:
                if not stripped.startswith("#"):
                    # Check format: UPPERCASE = "lowercase"
                    if not APPROVED_PATTERN.match(stripped):
                        if not stripped.startswith("@") and "def " not in stripped:
                            concerns.append(
                                f"{filepath}:{line_num}: "
                                f"Invalid enum format: {stripped}"
                            )
    
    return concerns

if __name__ == "__main__":
    all_concerns = []
    for filepath in sys.argv[1:]:
        concerns = audit_enum_file(filepath)
        all_concerns.extend(concerns)
    
    if all_concerns:
        print("🚨 SECURITY CONCERNS DETECTED:\n")
        for concern in all_concerns:
            print(f"  - {concern}")
        sys.exit(1)
    
    print("✅ Enum security check passed")
    sys.exit(0)
```

#### CI Pipeline Check

```yaml
# .github/workflows/security.yml
name: Security Checks
on: [pull_request]

jobs:
  enum-security:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
        with:
          fetch-depth: 0  # Full history for diff
      
      - name: Check Enum Changes
        run: |
          # Detect enum file changes
          ENUM_CHANGES=$(git diff origin/main --name-only | grep "src/domain/enums/" || true)
          
          if [ -n "$ENUM_CHANGES" ]; then
            echo "⚠️  ENUM CHANGES DETECTED - Security review required"
            echo "Changed files:"
            echo "$ENUM_CHANGES"
            
            # Run audit script
            python scripts/audit_enum_changes.py $ENUM_CHANGES
            
            # Notify security team (if Slack webhook configured)
            if [ -n "$SLACK_WEBHOOK" ]; then
              curl -X POST $SLACK_WEBHOOK \
                -H 'Content-Type: application/json' \
                -d "{\"text\": \"🔒 Enum changes in PR #${{ github.event.pull_request.number }} - Review required\"}"
            fi
          else
            echo "✅ No enum changes detected"
          fi
      
      - name: Run Enum Security Tests
        run: |
          pytest tests/unit/test_domain_enum_security.py --strict -v
```

**Protection Level**: Medium - Catches obvious issues, flags for review

---

### Layer 3: Database Constraints (RUNTIME DEFENSE)

**PostgreSQL CHECK constraints enforce valid values at database level.**

#### Migration Example

```python
# alembic/versions/xxx_transaction_constraints.py
"""Add CHECK constraints for transaction enums.

Revision ID: xxx
Revises: yyy
Create Date: 2025-11-30 12:00:00.000000
"""

from alembic import op

def upgrade():
    """Add CHECK constraints for enum integrity."""
    
    # TransactionType constraint
    op.execute("""
        ALTER TABLE transactions
        ADD CONSTRAINT transactions_type_check
        CHECK (transaction_type IN (
            'trade', 'transfer', 'income', 'fee', 'other'
        ));
    """)
    
    # TransactionSubtype constraint (all 24 values)
    op.execute("""
        ALTER TABLE transactions
        ADD CONSTRAINT transactions_subtype_check
        CHECK (subtype IN (
            -- TRADE (7)
            'buy', 'sell', 'short_sell', 'buy_to_cover',
            'exercise', 'assignment', 'expiration',
            -- TRANSFER (7)
            'deposit', 'withdrawal', 'wire_in', 'wire_out',
            'transfer_in', 'transfer_out', 'internal',
            -- INCOME (4)
            'dividend', 'interest', 'capital_gain', 'distribution',
            -- FEE (4)
            'commission', 'account_fee', 'margin_interest', 'other_fee',
            -- OTHER (3)
            'adjustment', 'journal', 'unknown'
        ));
    """)
    
    # AssetType constraint (optional field)
    op.execute("""
        ALTER TABLE transactions
        ADD CONSTRAINT transactions_asset_type_check
        CHECK (
            asset_type IS NULL OR
            asset_type IN (
                'equity', 'etf', 'option', 'mutual_fund',
                'fixed_income', 'futures', 'cryptocurrency',
                'cash_equivalent', 'other'
            )
        );
    """)

def downgrade():
    """Remove CHECK constraints."""
    op.execute("ALTER TABLE transactions DROP CONSTRAINT transactions_type_check;")
    op.execute("ALTER TABLE transactions DROP CONSTRAINT transactions_subtype_check;")
    op.execute("ALTER TABLE transactions DROP CONSTRAINT transactions_asset_type_check;")
```

**Impact**: Even if code enum is modified, database **rejects invalid values at runtime**.

**Protection Level**: High - Last line of defense, prevents data corruption

---

### Layer 4: Enum Integrity Tests (REGRESSION DEFENSE)

**Frozen tests verify enums haven't been tampered with.**

```python
# tests/unit/test_domain_enum_security.py
"""Security tests for enum integrity.

These tests verify that domain enums maintain their approved values
and haven't been tampered with by unauthorized changes.

CRITICAL: These tests must ALWAYS pass. Do not modify without
security team approval and architectural review.
"""

import pytest
from src.domain.enums import (
    TransactionType,
    TransactionSubtype,
    TransactionStatus,
    AssetType,
)


class TestEnumIntegrity:
    """Verify enums haven't been tampered with."""
    
    def test_transaction_type_frozen_values(self):
        """Ensure TransactionType has ONLY approved values.
        
        ANY change to this test requires:
        - Architecture Decision Record (ADR)
        - Security team approval
        - Compliance team sign-off
        """
        approved = {"trade", "transfer", "income", "fee", "other"}
        actual = {t.value for t in TransactionType}
        
        assert actual == approved, (
            f"🚨 SECURITY ALERT: TransactionType values changed!\n"
            f"Unauthorized additions: {actual - approved}\n"
            f"Missing values: {approved - actual}\n"
            f"This requires security review and ADR approval."
        )
    
    def test_transaction_subtype_frozen_values(self):
        """Ensure TransactionSubtype has ONLY approved values."""
        approved = {
            # TRADE (7)
            "buy", "sell", "short_sell", "buy_to_cover",
            "exercise", "assignment", "expiration",
            # TRANSFER (7)
            "deposit", "withdrawal", "wire_in", "wire_out",
            "transfer_in", "transfer_out", "internal",
            # INCOME (4)
            "dividend", "interest", "capital_gain", "distribution",
            # FEE (4)
            "commission", "account_fee", "margin_interest", "other_fee",
            # OTHER (3)
            "adjustment", "journal", "unknown",
        }
        actual = {s.value for s in TransactionSubtype}
        
        assert actual == approved, (
            f"🚨 SECURITY ALERT: TransactionSubtype values changed!\n"
            f"Unauthorized additions: {actual - approved}\n"
            f"Missing values: {approved - actual}\n"
            f"Count: Expected 24, got {len(actual)}"
        )
    
    def test_asset_type_frozen_values(self):
        """Ensure AssetType has ONLY approved values."""
        approved = {
            "equity", "etf", "option", "mutual_fund",
            "fixed_income", "futures", "cryptocurrency",
            "cash_equivalent", "other"
        }
        actual = {a.value for a in AssetType}
        
        assert actual == approved, (
            f"🚨 SECURITY ALERT: AssetType values changed!\n"
            f"Unauthorized additions: {actual - approved}\n"
            f"Missing values: {approved - actual}"
        )
    
    def test_transaction_status_frozen_values(self):
        """Ensure TransactionStatus has ONLY approved values."""
        approved = {"pending", "settled", "failed", "cancelled"}
        actual = {s.value for s in TransactionStatus}
        
        assert actual == approved, (
            f"🚨 SECURITY ALERT: TransactionStatus values changed!\n"
            f"Unauthorized additions: {actual - approved}\n"
            f"Missing values: {approved - actual}"
        )
    
    def test_no_suspicious_enum_values(self):
        """Check for suspicious enum value names.
        
        Forbidden keywords indicate potential security bypass attempts.
        """
        forbidden_keywords = [
            "admin", "override", "bypass", "hidden", "secret",
            "test", "debug", "temp", "hack", "backdoor"
        ]
        
        all_values = (
            [t.value for t in TransactionType] +
            [s.value for s in TransactionSubtype] +
            [a.value for a in AssetType] +
            [s.value for s in TransactionStatus]
        )
        
        violations = []
        for value in all_values:
            for keyword in forbidden_keywords:
                if keyword in value.lower():
                    violations.append((value, keyword))
        
        assert not violations, (
            f"🚨 SECURITY ALERT: Suspicious keywords found!\n" +
            "\n".join(
                f"  - '{value}' contains forbidden keyword '{kw}'"
                for value, kw in violations
            )
        )
    
    def test_enum_value_immutability(self):
        """Ensure enum values match their variable names semantically.
        
        This catches attacks where the enum value is changed:
        WITHDRAWAL = "deposit"  # Would fail this test
        """
        # Critical mappings that must never change
        assert TransactionSubtype.BUY == "buy"
        assert TransactionSubtype.SELL == "sell"
        assert TransactionSubtype.WITHDRAWAL == "withdrawal"
        assert TransactionSubtype.DEPOSIT == "deposit"
        assert TransactionType.TRADE == "trade"
        assert TransactionType.TRANSFER == "transfer"
        assert TransactionType.INCOME == "income"
        assert TransactionType.FEE == "fee"
    
    def test_enum_count_stability(self):
        """Verify enum counts remain stable.
        
        Prevents silent removal of enum values.
        """
        assert len(TransactionType) == 5, \
            f"TransactionType count changed: expected 5, got {len(TransactionType)}"
        
        assert len(TransactionSubtype) == 24, \
            f"TransactionSubtype count changed: expected 24, got {len(TransactionSubtype)}"
        
        assert len(AssetType) == 9, \
            f"AssetType count changed: expected 9, got {len(AssetType)}"
        
        assert len(TransactionStatus) == 4, \
            f"TransactionStatus count changed: expected 4, got {len(TransactionStatus)}"
```

**CI Enforcement**:

```bash
# Must pass on every commit
pytest tests/unit/test_domain_enum_security.py --strict -v
```

**Protection Level**: High - Detects tampering immediately

---

### Layer 5: Audit Logging (DETECTION)

**Track who changed what and when.**

#### Git Audit Script

```python
# scripts/generate_enum_audit_report.py
"""Generate audit report of enum changes.

Usage:
    python scripts/generate_enum_audit_report.py
    python scripts/generate_enum_audit_report.py --since="2025-01-01"
"""

import subprocess
import sys
from datetime import datetime

def audit_enum_history(since_date: str | None = None):
    """Report all enum changes with author/date.
    
    Args:
        since_date: Optional date filter (YYYY-MM-DD format).
    """
    cmd = [
        "git", "log",
        "--follow",
        "--pretty=format:%H|%an|%ae|%ad|%s",
        "--date=iso",
        "--", "src/domain/enums/"
    ]
    
    if since_date:
        cmd.insert(2, f"--since={since_date}")
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    print("=" * 80)
    print("ENUM CHANGE AUDIT REPORT")
    print(f"Generated: {datetime.now().isoformat()}")
    if since_date:
        print(f"Filtered since: {since_date}")
    print("=" * 80)
    print()
    
    if not result.stdout:
        print("No enum changes found.")
        return
    
    for line in result.stdout.split("\n"):
        if not line:
            continue
            
        parts = line.split("|")
        if len(parts) != 5:
            continue
            
        commit, author, email, date, message = parts
        
        print(f"Commit:  {commit[:8]}")
        print(f"Author:  {author} <{email}>")
        print(f"Date:    {date}")
        print(f"Message: {message}")
        print()
        
        # Show file changes
        diff_cmd = ["git", "show", "--stat", commit, "--", "src/domain/enums/"]
        diff_result = subprocess.run(diff_cmd, capture_output=True, text=True)
        print(diff_result.stdout)
        print("-" * 80)
        print()

if __name__ == "__main__":
    since = None
    if len(sys.argv) > 1 and sys.argv[1].startswith("--since="):
        since = sys.argv[1].split("=")[1]
    
    audit_enum_history(since)
```

**Usage**:

```bash
# Full audit history
python scripts/generate_enum_audit_report.py

# Changes since specific date
python scripts/generate_enum_audit_report.py --since="2025-01-01"
```

**Protection Level**: Medium - Post-incident forensics and compliance

---

### Layer 6: Governance & Documentation (ORGANIZATIONAL)

#### Architecture Decision Record (ADR)

```markdown
# ADR-015: Enum Change Process

## Status
Approved

## Context
Domain enums (TransactionType, TransactionSubtype, AssetType, TransactionStatus)
are critical financial primitives that define the vocabulary of our financial
data model.

Unauthorized or careless changes could:
- Compromise audit trails
- Break financial calculations
- Violate compliance requirements
- Enable fraud or theft
- Corrupt historical data

## Decision
ALL enum changes require the following approval process:

### Required Approvals
1. **Architecture Review** - Document WHY the change is needed
2. **Security Team** - Verify no security implications
3. **Compliance Team** - Verify no regulatory impact
4. **Database Migration Plan** - How will existing data be handled?
5. **Rollback Procedure** - How to undo if issues arise?

### Required Documentation
- Update architecture document (`docs/architecture/transaction.md`)
- Update frozen tests (`tests/unit/test_domain_enum_security.py`)
- Create database migration with CHECK constraint update
- Document in ADR (this file)

### Approval Timeline
- Minimum 48-hour review period
- All reviewers must explicitly approve
- Changes merged only after all checks pass

## Consequences
**Positive:**
- Higher confidence in financial data integrity
- Clear audit trail for regulators
- Reduced risk of fraud or data corruption
- Explicit review catches issues early

**Negative:**
- Slower enum changes (intentional friction)
- More process overhead
- Cannot make emergency enum changes without approvals

## Alternatives Considered
1. **Database-driven enums** - Rejected: Loses type safety, adds runtime complexity
2. **No restrictions** - Rejected: Too risky for financial primitives
3. **Single approver** - Rejected: Single point of failure

## Notes
This is intentionally heavyweight because enums are financial primitives.
For user-configurable data (tags, categories), use database tables instead.

**Created**: 2025-11-30
**Last Updated**: 2025-11-30
**Reviewers**: Security Team, Compliance Team, Engineering Leadership
```

**Protection Level**: High - Organizational commitment to security

---

## Summary: Defense in Depth Strategy

| Layer | Defense Mechanism | Protection Level | When Active |
|-------|-------------------|------------------|-------------|
| 1 | Code Review (CODEOWNERS) | 🔴 High | Before merge |
| 2 | CI/CD Automation | 🟡 Medium | During PR |
| 3 | Database Constraints | 🔴 High | Runtime |
| 4 | Frozen Tests | 🔴 High | Every commit |
| 5 | Audit Logging | 🟡 Medium | Post-incident |
| 6 | Governance (ADR) | 🔴 High | Organization-wide |

**Key Principle**: No single point of failure. Malicious changes must bypass **multiple independent defenses**.

---

## Legitimate Enum Change Process

### Step 1: Identify Need

Example: New provider (Fidelity) returns "STOCK_SPLIT" transaction type.

### Step 2: Research & Map

- Does it map to existing subtype? (e.g., `ADJUSTMENT`)
- Or is it truly new? (requires new `STOCK_SPLIT` subtype)

### Step 3: Create ADR

Document the WHY and business justification.

### Step 4: Update Code

```python
# src/domain/enums/transaction_subtype.py
class TransactionSubtype(str, Enum):
    # ... existing ...
    STOCK_SPLIT = "stock_split"  # NEW - Fidelity integration
```

### Step 5: Update Tests

```python
# tests/unit/test_domain_enum_security.py
def test_transaction_subtype_frozen_values(self):
    approved = {
        # ... existing 24 values ...
        "stock_split",  # NEW
    }
    # Update count assertion: 24 → 25
```

### Step 6: Create Migration

```python
# alembic/versions/xxx_add_stock_split.py
def upgrade():
    op.execute("""
        ALTER TABLE transactions DROP CONSTRAINT transactions_subtype_check;
        ALTER TABLE transactions ADD CONSTRAINT transactions_subtype_check
        CHECK (subtype IN (
            -- ... all existing values ...
            'stock_split'  -- NEW
        ));
    """)
```

### Step 7: Update Documentation

Update architecture doc with new subtype and count.

### Step 8: Submit PR

- Security team reviews
- Compliance team reviews
- 2+ senior engineers review
- All CI checks pass
- Merge approved

---

## Monitoring & Alerts

### Recommended Alerts

1. **Enum File Changes**: Slack/email notification on PR
2. **Test Failures**: Immediate alert if frozen tests fail
3. **Database Constraint Violations**: Runtime alerts if invalid enum attempted
4. **Audit Review**: Monthly review of enum change audit log

---

## References

- Architecture: `docs/architecture/transaction.md`
- Import Guidelines: `docs/guides/imports.md`

---

**Created**: 2025-11-30 | **Last Updated**: 2025-11-30
