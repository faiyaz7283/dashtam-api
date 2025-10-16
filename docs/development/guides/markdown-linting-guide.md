# Markdown Linting and Formatting Guide

**Comprehensive approach to maintaining high-quality Markdown documentation:**

**Last Updated:** 2025-10-12  
**Status:** Recommendation - Ready for Implementation  
**Priority:** P3 (Quality of Life)

---

## 📖 Table of Contents

- [Overview](#overview)
  - [The Challenge](#the-challenge)
- [Current State Analysis](#current-state-analysis)
  - [Documentation Inventory](#documentation-inventory)
  - [Risk Areas for Auto-Formatting](#risk-areas-for-auto-formatting)
- [Recommended Approach](#recommended-approach)
  - [Strategy: "Lint First, Format Carefully"](#strategy-lint-first-format-carefully)
  - [Core Principles](#core-principles)
- [Tool Selection](#tool-selection)
  - [Recommended Tools](#recommended-tools)
    - [1. **markdownlint-cli2** (Primary Linter)](#1-markdownlint-cli2-primary-linter)
    - [2. **remark-cli with remark-lint** (Alternative/Supplementary)](#2-remark-cli-with-remark-lint-alternativesupplementary)
    - [3. **prettier** (Formatting Only)](#3-prettier-formatting-only)
- [Configuration](#configuration)
  - [markdownlint Configuration](#markdownlint-configuration)
  - [Ignore Patterns](#ignore-patterns)
  - [File-Specific Overrides](#file-specific-overrides)
- [Workflow Integration](#workflow-integration)
  - [Makefile Commands](#makefile-commands)
  - [Pre-Commit Hook (Optional)](#pre-commit-hook-optional)
  - [VS Code Integration](#vs-code-integration)
- [Risk Mitigation](#risk-mitigation)
  - [Visual Testing Protocol](#visual-testing-protocol)
  - [Safe Formatting Guidelines](#safe-formatting-guidelines)
  - [Rollback Plan](#rollback-plan)
- [Phased Rollout](#phased-rollout)
  - [Phase 1: Linting Only ✅ Recommended Start](#phase-1-linting-only--recommended-start)
  - [Phase 2: Manual Fixes](#phase-2-manual-fixes)
  - [Phase 3: CI/CD Integration](#phase-3-cicd-integration)
  - [Phase 4: Gradual Enforcement](#phase-4-gradual-enforcement)
- [Maintenance](#maintenance)
  - [Regular Tasks](#regular-tasks)
  - [Common Issues and Solutions](#common-issues-and-solutions)
- [Recommendations Summary](#recommendations-summary)
  - [✅ **Recommended Immediate Actions**](#-recommended-immediate-actions)
  - [❌ **NOT Recommended**](#-not-recommended)
  - [🎯 **Success Metrics**](#-success-metrics)
- [Integration with Existing Workflow](#integration-with-existing-workflow)
  - [Add to WARP.md](#add-to-warpmd)
  - [Add to Phase Completion Workflow](#add-to-phase-completion-workflow)
- [Conclusion](#conclusion)
- [See Also](#see-also)

---

## Overview

### The Challenge

**Current Situation:**

- 67 Markdown files across the project
- Markdownlint warnings throughout documentation
- No automated validation or formatting
- Inconsistent styling across files
- Risk of visual presentation issues with auto-formatting

**Goals:**

- Maintain consistent Markdown quality
- Catch common mistakes early
- Enable automated validation in CI/CD
- Preserve visual presentation integrity
- Minimize manual intervention

---

## Current State Analysis

### Documentation Inventory

```bash
# Total Markdown files: 67
docs/                    # Main documentation directory
├── api-flows/          # API flow examples (critical - must preserve formatting)
├── development/        # Developer documentation
│   ├── architecture/   # Architecture docs (tables, diagrams)
│   ├── guides/         # Implementation guides (code blocks, commands)
│   ├── infrastructure/ # Setup guides (commands, configurations)
│   └── testing/        # Testing documentation
├── research/           # Research notes and decisions
└── README.md           # Project documentation index
```

### Risk Areas for Auto-Formatting

**High-Risk Files** (require careful handling):

1. **API flow examples** (`docs/api-flows/`) - cURL commands with specific formatting
2. **Code examples** - Inline code blocks with specific line breaks
3. **Tables** - Complex tables with alignment requirements
4. **Mermaid diagrams** - Syntax-sensitive diagram code
5. **WARP.md** - Project rules file with specific formatting
6. **Session journals** - Timestamped entries with specific structure

**Low-Risk Files** (safe for auto-formatting):

- README files
- Simple guides without complex code
- Text-heavy documentation
- Research notes

---

## Recommended Approach

### Strategy: "Lint First, Format Carefully"

**Phase-based approach with progressive automation:**

```text
Phase 1: Linting Only (Non-Destructive)
   ↓
Phase 2: Manual Fixes with Guidelines  
   ↓
Phase 3: Selective Auto-Formatting (Low-Risk Files)
   ↓
Phase 4: CI/CD Integration (Validation Only)
   ↓
Phase 5: Gradual Expansion (As Confidence Grows)
```

### Core Principles

1. ✅ **Lint Everything, Format Selectively**
   - Run linters on all files to identify issues
   - Auto-format only low-risk files
   - Manual review for high-risk files

2. ✅ **Non-Destructive by Default**
   - Start with `--check` mode (validation only)
   - Never auto-fix in CI/CD initially
   - Require manual approval for formatting

3. ✅ **Progressive Enhancement**
   - Begin with critical warnings only
   - Gradually enable more rules
   - Build confidence over time

4. ✅ **Visual Testing Protocol**
   - Render preview before/after formatting
   - Test in both GitHub markdown and MkDocs (when implemented)
   - Manual verification for critical documentation

---

## Tool Selection

### Recommended Tools

#### 1. **markdownlint-cli2** (Primary Linter)

**Why Choose This?**

- Fast, modern, and actively maintained
- Highly configurable (enable/disable rules per file)
- Supports `.markdownlint.jsonc` for comments in config
- Compatible with VS Code extension
- Can use `.markdownlintignore` for exceptions

**No Installation Required:**

Dashtam uses a one-off Node.js container approach (no project dependencies needed).

**Usage via Makefile (Recommended):**

```bash
# Check all files (non-destructive)
make lint-md

# Check specific file
make lint-md-file FILE="docs/README.md"

# Check specific directory pattern
make lint-md-file FILE="docs/development/**/*.md"

# Auto-fix issues (with confirmation prompt)
make lint-md-fix
```

**Direct Docker Usage:**

```bash
# Check all files
docker run --rm -v $(PWD):/workspace:ro -w /workspace node:24-alpine \
  npx markdownlint-cli2 "**/*.md" "#node_modules"

# Check specific file
docker run --rm -v $(PWD):/workspace:ro -w /workspace node:24-alpine \
  npx markdownlint-cli2 "docs/README.md"
```

#### 2. **remark-cli with remark-lint** (Alternative/Supplementary)

**Why Consider This?**

- More sophisticated formatting capabilities
- Pluggable architecture (fine-grained control)
- Better for complex transformations
- Can preserve intentional formatting

**When to Use:**

- As a second opinion for complex files
- For advanced formatting needs
- When markdownlint rules are too strict

#### 3. **prettier** (Formatting Only)

**Why Be Cautious?**

- ⚠️ Opinionated formatting (may break presentation)
- ⚠️ Limited Markdown-specific configuration
- ⚠️ May reformat code blocks unexpectedly

**Recommendation:** **NOT recommended** for Dashtam initially due to risk of breaking formatting in API flows and code examples.

---

## Configuration

### markdownlint Configuration

Create `.markdownlint.jsonc` in project root:

```jsonc
{
  "$schema": "https://raw.githubusercontent.com/DavidAnson/markdownlint/main/schema/markdownlint-config-schema.json",
  
  // Default: all rules enabled
  "default": true,
  
  // Disable or customize specific rules
  
  // MD013: Line length (disabled - we have long lines in code examples)
  "MD013": false,
  
  // MD024: Multiple headings with same content (disabled - acceptable in our docs)
  "MD024": {
    "siblings_only": true  // Only flag if same level siblings have duplicate text
  },
  
  // MD033: Inline HTML (allow - needed for custom formatting)
  "MD033": false,
  
  // MD034: Bare URLs (disabled - acceptable in certain contexts)
  "MD034": false,
  
  // MD041: First line should be top-level heading (disabled - some files have frontmatter)
  "MD041": false,
  
  // MD046: Code block style (enforce fenced code blocks)
  "MD046": {
    "style": "fenced"
  },
  
  // MD048: Code fence style (enforce backticks)
  "MD048": {
    "style": "backtick"
  },
  
  // MD049: Emphasis style (enforce asterisks)
  "MD049": {
    "style": "asterisk"
  },
  
  // MD050: Strong style (enforce asterisks)
  "MD050": {
    "style": "asterisk"
  }
}
```

### Ignore Patterns

Create `.markdownlintignore`:

```gitignore
# Node modules and dependencies
node_modules/

# Build outputs
site/
build/
dist/

# Archived documentation (may have old formatting)
docs/research/archived/**/*.md

# Auto-generated files
CHANGELOG.md

# External documentation
vendor/
```

### File-Specific Overrides

For files that need special handling, use inline comments:

```markdown
<!-- markdownlint-disable MD013 -->
This line can be very long and won't trigger the line length warning.

<!-- markdownlint-disable-next-line MD034 -->
https://this-bare-url-is-ok.com

<!-- markdownlint-disable-file MD024 -->
<!-- Disables rule for entire file - place at top -->
```

---

## Workflow Integration

### Makefile Commands

The project Makefile already includes these commands (no changes needed):

```makefile
# Markdown linting commands (uses one-off Node.js container)
MARKDOWN_LINT_IMAGE := node:24-alpine
MARKDOWN_LINT_CMD := npx markdownlint-cli2

lint-md:  ## Check all Markdown files for linting issues
  @echo "🔍 Linting markdown files..."
  @docker run --rm \
    -v $(PWD):/workspace:ro \
    -w /workspace \
    $(MARKDOWN_LINT_IMAGE) \
    $(MARKDOWN_LINT_CMD) "**/*.md" "#node_modules"

lint-md-fix:  ## Fix auto-fixable Markdown issues (with confirmation)
  @echo "⚠️  WARNING: This will modify markdown files!"
  @read -p "Continue? (yes/no): " confirm; \
  if [ "$$confirm" = "yes" ]; then \
    docker run --rm \
      -v $(PWD):/workspace \
      -w /workspace \
      $(MARKDOWN_LINT_IMAGE) \
      $(MARKDOWN_LINT_CMD) --fix "**/*.md" "#node_modules"; \
  fi

lint-md-file:  ## Lint specific file(s) - Usage: make lint-md-file FILE="path/to/file.md"
  @docker run --rm \
    -v $(PWD):/workspace:ro \
    -w /workspace \
    $(MARKDOWN_LINT_IMAGE) \
    $(MARKDOWN_LINT_CMD) "$(FILE)"

md-check: lint-md  ## Alias for lint-md
```

### Pre-Commit Hook (Optional)

Create `.git/hooks/pre-commit`:

```bash
#!/bin/sh
# Markdown linting pre-commit hook

# Only check staged .md files
STAGED_MD_FILES=$(git diff --cached --name-only --diff-filter=ACM | grep '\.md$')

if [ -n "$STAGED_MD_FILES" ]; then
    echo "Running markdownlint on staged Markdown files..."
    
    # Run markdownlint using one-off container (check only, no auto-fix)
    docker run --rm \
        -v $(PWD):/workspace:ro \
        -w /workspace \
        node:24-alpine \
        npx markdownlint-cli2 $STAGED_MD_FILES
    
    if [ $? -ne 0 ]; then
        echo "❌ Markdown linting failed. Please fix issues before committing."
        echo "Run 'make lint-md' to see all issues."
        exit 1
    fi
    
    echo "✅ Markdown linting passed"
fi

exit 0
```

Make executable:

```bash
chmod +x .git/hooks/pre-commit
```

### VS Code Integration

Add to `.vscode/settings.json`:

```json
{
  "markdownlint.config": {
    "extends": ".markdownlint.jsonc"
  },
  "markdownlint.run": "onType",
  "[markdown]": {
    "editor.formatOnSave": false,  // Don't auto-format markdown
    "editor.codeActionsOnSave": {
      "source.fixAll.markdownlint": false  // Don't auto-fix on save
    }
  }
}
```

**Recommended VS Code Extension:** `DavidAnson.vscode-markdownlint`

---

## Risk Mitigation

### Visual Testing Protocol

**Before committing formatted Markdown:**

1. **Preview in GitHub:**

   ```bash
   # Create a test branch
   git checkout -b test/markdown-formatting
   
   # Format a single file
   make lint-md-fix  # Or lint specific file with make lint-md-file FILE="..."
   
   # Commit and push
   git add docs/path/to/file.md
   git commit -m "test: markdown formatting"
   git push origin test/markdown-formatting
   
   # View on GitHub to verify rendering
   # Delete branch after verification
   ```

2. **Preview Locally with MkDocs** (when implemented):

   ```bash
   make docs-serve
   # Navigate to affected pages
   ```

3. **Diff Review:**

   ```bash
   # Before formatting
   git diff docs/path/to/file.md
   
   # Review EVERY change carefully
   # Look for:
   # - Broken links
   # - Reformatted code blocks
   # - Changed table alignment
   # - Modified list indentation
   ```

### Safe Formatting Guidelines

**Always Safe:**

- Fixing trailing whitespace
- Consistent heading styles
- Consistent list markers
- Fixing line breaks at end of file

**Requires Review:**

- Table reformatting
- List indentation changes
- Code block language tags
- Link reference reformatting

**Never Auto-Fix:**

- API flow documentation (`docs/api-flows/`)
- WARP.md (critical project rules)
- Session journals (`~/ai_dev_sessions/Dashtam/`)
- Files with complex Mermaid diagrams

### Rollback Plan

If formatting breaks something:

```bash
# Revert specific file
git checkout HEAD -- docs/path/to/file.md

# Revert entire commit
git revert <commit-hash>

# Force push if already pushed (use carefully)
git push --force-with-lease origin development
```

---

## Phased Rollout

### Phase 1: Linting Only ✅ Recommended Start

**Goal:** Identify issues without making changes

**Actions:**

1. ✅ Add markdownlint-cli2 to dev dependencies
2. ✅ Create `.markdownlint.jsonc` configuration
3. ✅ Create `.markdownlintignore`
4. ✅ Add `make lint-md` command
5. ✅ Run `make lint-md` to see current state
6. ✅ Document common issues and patterns

**Success Criteria:**

- Linting runs without errors on command
- Team understands common warnings
- No files modified yet

---

### Phase 2: Manual Fixes

**Goal:** Fix critical issues manually with careful review

**Actions:**

1. ✅ Fix critical warnings in high-value files:
   - README.md (root)
   - docs/README.md
   - Key architecture documents
2. ✅ Use `--fix` only on low-risk files
3. ✅ Manual review of every change
4. ✅ Test rendering on GitHub after each fix
5. ✅ Document any issues encountered

**Priority Order:**

1. Root README.md
2. docs/README.md
3. Architecture documents
4. Implementation guides (excluding API flows)
5. Testing documentation

**Success Criteria:**

- Critical documentation has no warnings
- No visual presentation issues
- Team comfortable with linting workflow

---

### Phase 3: CI/CD Integration

**Goal:** Automated validation in pull requests

**Actions:**

1. ✅ Add markdownlint check to GitHub Actions
2. ✅ Run in "check only" mode (no auto-fix)
3. ✅ Make it non-blocking initially (warning only)
4. ✅ Collect feedback from team

**GitHub Actions Workflow:**

Create `.github/workflows/markdown-lint.yml`:

```yaml
name: Markdown Lint

on:
  pull_request:
    paths:
      - '**.md'
      - '.markdownlint.jsonc'
      - '.github/workflows/markdown-lint.yml'

jobs:
  markdownlint:
    runs-on: ubuntu-latest
    
    steps:
      - name: Checkout code
        uses: actions/checkout@v4
      
      - name: Setup Node.js
        uses: actions/setup-node@v4
        with:
          node-version: '20'
      
      - name: Install markdownlint-cli2
        run: npm install -g markdownlint-cli2
      
      - name: Run markdownlint
        run: markdownlint-cli2 "**/*.md"
        continue-on-error: true  # Non-blocking initially
      
      - name: Comment on PR (if warnings)
        if: failure()
        uses: actions/github-script@v7
        with:
          script: |
            github.rest.issues.createComment({
              issue_number: context.issue.number,
              owner: context.repo.owner,
              repo: context.repo.repo,
              body: '⚠️ Markdown linting found some issues. Please review and
                     fix before merging.'
            })
```

**Success Criteria:**

- CI runs successfully
- Warnings visible in PR checks
- No blocking of legitimate PRs

---

### Phase 4: Gradual Enforcement

**Goal:** Make linting required for new/modified files

**Actions:**

1. ✅ Change CI workflow to blocking (required check)
2. ✅ Update CONTRIBUTING.md with markdown guidelines
3. ✅ Add linting to PR template checklist
4. ✅ Gradually fix remaining warnings

**PR Template Addition:**

```markdown
## Markdown Quality

- [ ] Markdown files pass linting (`make lint-md`)
- [ ] Visual presentation verified (preview on GitHub)
- [ ] No broken links or formatting issues
```

**Success Criteria:**

- New PRs consistently pass markdown linting
- Documentation quality improves
- Team comfortable with workflow

---

## Maintenance

### Regular Tasks

**Regularly:**

- Review any new markdownlint warnings
- Update `.markdownlintignore` if needed
- Check for markdownlint-cli2 updates
- Review and update `.markdownlint.jsonc` rules
- Evaluate if any disabled rules can be enabled
- Check for new best practices

**Per PR:**

- Run `make lint-md` before submitting
- Review markdown diff carefully
- Test rendering for significant changes

### Common Issues and Solutions

**Issue:** Line too long (MD013)

```markdown
<!-- Solution 1: Disable rule for that line -->
<!-- markdownlint-disable-next-line MD013 -->
This is a very long line that needs to stay on one line for formatting reasons.

<!-- Solution 2: Break long URLs -->
[link text][ref]

[ref]: https://very-long-url.com/path/to/resource
```

**Issue:** Multiple headings with same content (MD024)

```markdown
<!-- Solution: Make headings more specific -->
## Authentication (Bad)
## Authentication Flow (Good)
## Authentication API (Good)
```

**Issue:** Bare URL without angle brackets (MD034)

```markdown
<!-- Bad -->
https://example.com

<!-- Good -->
<https://example.com>

<!-- Or -->
[https://example.com](https://example.com)
```

---

## Recommendations Summary

### ✅ **Recommended Immediate Actions**

1. **Start with Phase 1** (Linting Only)
   - Zero risk, high visibility into issues
   - Add markdownlint-cli2 as dev dependency
   - Create configuration files
   - Run `make lint-md` to assess current state

2. **Document Findings**
   - Create list of common warnings
   - Identify high-risk files (don't auto-format)
   - Prioritize which warnings to fix first

3. **Manual Fixes First**
   - Fix critical documentation manually
   - Build confidence and understanding
   - Learn which rules are most valuable

4. **CI/CD Integration Later**
   - Only after team is comfortable
   - Start with non-blocking warnings
   - Gradually make it required

### ❌ **NOT Recommended**

1. **Don't use Prettier for Markdown** (initially)
   - Too opinionated
   - Risk of breaking formatting
   - Limited configuration options

2. **Don't auto-fix everything**
   - High risk of visual presentation issues
   - Manual review is essential
   - Start with low-risk files only

3. **Don't make it blocking immediately**
   - Team needs time to adapt
   - May block legitimate PRs
   - Start with warnings only

### 🎯 **Success Metrics**

- **Quality:** Consistent markdown formatting across all docs
- **Velocity:** No significant slowdown in PR review process
- **Safety:** Zero visual presentation issues from formatting
- **Adoption:** Team comfortable running `make lint-md` before commits

---

## Integration with Existing Workflow

### Add to WARP.md

Under "## Coding Standards" section, add:

```markdown
### Markdown Documentation Standards

- **Linting Required:** All Markdown files must pass `make lint-md`
- **No Auto-Formatting:** Do not use auto-fix on high-risk files (API flows, WARP.md)
- **Visual Testing:** Preview changes on GitHub before committing
- **Configuration:** Follow rules in `.markdownlint.jsonc`
- **See:** [Markdown Linting Guide](docs/development/guides/markdown-linting-guide.md)
```

### Add to Phase Completion Workflow

Under "Before Committing" section in WARP.md:

```markdown
# Lint markdown files (if documentation changes)
make lint-md

# Visual check (for documentation PRs)
# Preview on GitHub to verify rendering
```

---

## Conclusion

**Recommended Approach:** **Progressive, Safety-First Implementation**

1. ✅ **Start:** Linting only (validation, no changes)
2. ✅ **Then:** Manual fixes with careful review
3. ✅ **Later:** Selective auto-formatting on low-risk files
4. ✅ **Finally:** CI/CD integration as confidence grows

**Key Principle:** **"Trust but Verify"**

- Lint everything to catch issues
- Fix carefully with manual review
- Test visual presentation always
- Automate only when safe

**Rollout:**

Progressive implementation through phases, with benefits visible from Phase 1 onward.

---

**Last Updated:** 2025-10-12  
**Document Owner:** Development Team  
**Status:** Ready for Phase 1 Implementation  
**Next Review:** After Phase 1 completion

## See Also

- [Docstring Standards Guide](docstring-standards.md) - Python documentation standards
- [Documentation Implementation Guide](documentation-implementation-guide.md) - MkDocs setup
- WARP.md - Project coding standards

---

## Document Information

**Category:** Guide
**Created:** 2025-10-11
**Last Updated:** 2025-10-15
**Difficulty Level:** Intermediate
**Target Audience:** Developers, documentation maintainers, DevOps engineers
**Prerequisites:** Basic Markdown knowledge, Docker familiarity
**Related Documents:** [Docstring Standards Guide](docstring-standards.md), [Documentation Implementation Guide](documentation-implementation-guide.md)
