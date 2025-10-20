# [Issue Title] - Troubleshooting Guide

[2-3 paragraph summary of the issue, investigation, and resolution. Include key findings and final solution.]

---

## Table of Contents

- [Initial Problem](#initial-problem)
- [Investigation Steps](#investigation-steps)
- [Root Cause Analysis](#root-cause-analysis)
- [Solution Implementation](#solution-implementation)
- [Verification](#verification)
- [Lessons Learned](#lessons-learned)
- [Future Improvements](#future-improvements)
- [References](#references)
- [Document Information](#document-information)

---

## Initial Problem

### Symptoms

[Describe observable symptoms of the problem]

**Environment:** [Where the issue occurred - Dev/Test/CI/Production]

```bash
# Error messages, stack traces, or logs
[paste relevant error output]
```

**Working Environments:** [List environments where issue did NOT occur]

### Expected Behavior

[What should have happened]

### Actual Behavior

[What actually happened]

### Impact

- **Severity:** Critical | High | Medium | Low
- **Affected Components:** [List affected systems/features]
- **User Impact:** [How users were affected]

## Investigation Steps

Document each investigation attempt chronologically. For each step, include:

- **Hypothesis**: What you thought was wrong
- **Investigation**: What you tested/checked
- **Findings**: What you discovered
- **Result**: ✅ Issue found | ❌ Not the cause | 🔍 Partial insight

### Step 1: [Investigation Area]

**Hypothesis:** [What you suspected]

**Investigation:**

[Describe what you tested or checked]

```bash
# Commands or code used to investigate
[commands here]
```

**Findings:**

[What you discovered]

**Result:** ❌ | ✅ | 🔍

### Step 2: [Next Investigation Area]

**Hypothesis:** [Next theory]

**Investigation:**

[What you tested]

**Findings:**

[Discoveries]

**Result:** ❌ | ✅ | 🔍

[Repeat for each investigation step]

## Root Cause Analysis

### Primary Cause

**Problem:**

[Detailed explanation of the root cause]

```python
# Code snippet showing the problematic pattern
[code here]
```

**Why This Happens:**

[Technical explanation of why the problem occurs]

**Impact:**

[How this cause created the observed symptoms]

### Contributing Factors

**Factor 1: [Name]**

[Description of contributing factor]

**Factor 2: [Name]**

[Description of contributing factor]

## Solution Implementation

### Approach

[High-level description of the solution strategy]

### Changes Made

#### Change 1: [Component/File]

**Before:**

```python
# Original code
[code here]
```

**After:**

```python
# Fixed code
[code here]
```

**Rationale:**

[Why this change fixes the issue]

#### Change 2: [Component/File]

**Before:**

```python
# Original code
```

**After:**

```python
# Fixed code
```

**Rationale:**

[Explanation]

[Repeat for all changes]

### Implementation Steps

1. **Step 1**: [Action taken]

   ```bash
   # Commands executed
   ```

2. **Step 2**: [Next action]

   ```bash
   # Commands executed
   ```

[Continue for all steps]

## Verification

### Test Results

**Before Fix:**

```bash
# Test output showing failures
[output here]
```

**After Fix:**

```bash
# Test output showing success
[output here]
```

### Verification Steps

1. **Test in original failing environment**

   ```bash
   # Verification commands
   ```

   **Result:** ✅ Passing

2. **Test in all other environments**

   ```bash
   # Additional verification
   ```

   **Result:** ✅ Passing

### Regression Testing

[Describe any additional testing performed to ensure no regressions]

## Lessons Learned

### Technical Insights

1. **[Key Learning 1]**

   [What we learned about the technology/system]

2. **[Key Learning 2]**

   [Another technical insight]

### Process Improvements

1. **[Improvement 1]**

   [How we can prevent similar issues]

2. **[Improvement 2]**

   [Another preventive measure]

### Best Practices

[List of best practices derived from this experience]

- Best practice 1
- Best practice 2
- Best practice 3

## Future Improvements

### Short-Term Actions

1. **[Action 1]**

   **Timeline:** [When to implement]

   **Owner:** [Responsible party]

2. **[Action 2]**

   **Timeline:** [When to implement]

   **Owner:** [Responsible party]

### Long-Term Improvements

1. **[Improvement 1]**

   [Description and rationale]

2. **[Improvement 2]**

   [Description and rationale]

### Monitoring & Prevention

[Describe monitoring or automated checks to prevent recurrence]

```bash
# Example monitoring commands or checks
[commands here]
```

## References

**Related Documentation:**

- [Related Doc 1](../path/to/doc1.md)
- [Related Doc 2](../path/to/doc2.md)

**External Resources:**

- [External Resource 1](https://example.com) - Description
- [External Resource 2](https://example.com) - Description

**Related Issues:**

- GitHub Issue #XX - [Issue title]
- GitHub PR #YY - [PR title]

---

## Document Information

**Template:** [troubleshooting-template.md](troubleshooting-template.md)
**Created:** YYYY-MM-DD
**Last Updated:** YYYY-MM-DD
