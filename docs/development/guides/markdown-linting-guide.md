# Markdown Linting and Formatting Guide

Comprehensive guide to maintaining consistent, high-quality Markdown documentation using markdownlint-cli2 with automated validation and safe formatting practices.

---

## Table of Contents

- [Overview](#overview)
  - [What You'll Learn](#what-youll-learn)
  - [When to Use This Guide](#when-to-use-this-guide)
- [Prerequisites](#prerequisites)
- [Step-by-Step Instructions](#step-by-step-instructions)
  - [Step 1: Understand the Linting Strategy](#step-1-understand-the-linting-strategy)
  - [Step 2: Configure markdownlint](#step-2-configure-markdownlint)
  - [Step 3: Run Markdown Linting](#step-3-run-markdown-linting)
  - [Step 4: Fix Common Issues](#step-4-fix-common-issues)
  - [Step 5: Use Auto-Fix Carefully](#step-5-use-auto-fix-carefully)
  - [Step 6: Integrate into Workflow](#step-6-integrate-into-workflow)
- [Examples](#examples)
  - [Example 1: Linting Single File](#example-1-linting-single-file)
  - [Example 2: Fixing Common Violations](#example-2-fixing-common-violations)
  - [Example 3: VS Code Integration](#example-3-vs-code-integration)
  - [Example 4: Pre-Commit Hook](#example-4-pre-commit-hook)
  - [Example 5: GitHub Actions CI](#example-5-github-actions-ci)
- [Verification](#verification)
  - [Check 1: Linting Passes](#check-1-linting-passes)
  - [Check 2: Visual Presentation Preserved](#check-2-visual-presentation-preserved)
- [Troubleshooting](#troubleshooting)
  - [Issue 1: Line Too Long (MD013)](#issue-1-line-too-long-md013)
  - [Issue 2: Multiple Headings Same Content (MD024)](#issue-2-multiple-headings-same-content-md024)
  - [Issue 3: Bare URL Without Brackets (MD034)](#issue-3-bare-url-without-brackets-md034)
  - [Issue 4: Formatting Breaks Visual Presentation](#issue-4-formatting-breaks-visual-presentation)
- [Best Practices](#best-practices)
  - [Common Mistakes to Avoid](#common-mistakes-to-avoid)
- [Next Steps](#next-steps)
- [References](#references)
- [Document Information](#document-information)

---

## Overview

This guide provides a phased approach to implementing markdown linting in Dashtam using markdownlint-cli2. The strategy prioritizes safety and gradual adoption, ensuring documentation quality improves without breaking existing formatting.

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

### What You'll Learn

- How to run markdown linting using Makefile commands
- Understanding and fixing common markdown violations
- Configuration of markdownlint rules and ignore patterns
- Safe auto-formatting practices for high-risk files
- Integrating linting into development workflow and CI/CD
- Visual verification workflow and rollback safety
- Tool selection and comparison (markdownlint-cli2, remark, prettier)
- Phased rollout strategy for team adoption

### When to Use This Guide

Use this guide when:

- Creating or editing markdown documentation
- Setting up markdown linting for the first time
- Troubleshooting markdown linting errors
- Integrating linting into CI/CD pipeline
- Reviewing pull requests with documentation changes
- Establishing documentation quality standards
- Training team members on markdown best practices

## Prerequisites

Before starting, ensure you have:

- [ ] Docker Desktop installed and running
- [ ] Dashtam development environment set up
- [ ] Access to project Makefile commands
- [ ] Understanding of markdown syntax
- [ ] Familiarity with git workflow

**Required Tools:**

- Docker - For running markdownlint-cli2 in isolated container
- Make - For executing linting commands
- Git - For version control and PR reviews
- Node.js 20+ (via Docker, no local install needed)

**Required Knowledge:**

- Basic markdown syntax and formatting
- Command line operations
- Git branching and pull requests
- Visual diff review techniques
- Understanding of risk classification for files

## Step-by-Step Instructions

### Step 1: Understand the Linting Strategy

Dashtam follows a **"Lint First, Format Carefully"** strategy with phased rollout:

**Phase-based approach:**

```text
Phase 1: Linting Only (Non-Destructive)
   ↓
Phase 2: Manual Fixes with Guidelines
   ↓
Phase 3: CI/CD Integration (Validation Only)
   ↓
Phase 4: Gradual Enforcement
```

**Core Principles:**

1. **Lint Everything, Format Selectively** - Run linters on all files, but auto-format only low-risk files
2. **Non-Destructive by Default** - Start with validation only, never auto-fix in CI/CD initially
3. **Progressive Enhancement** - Begin with critical warnings, gradually enable more rules
4. **Visual Testing Protocol** - Always verify rendering after formatting

**Risk Classification:**

**High-Risk Files** (manual fixes only):

- API flow examples (`docs/api-flows/`) - cURL commands with specific formatting
- WARP.md - Critical project rules
- Session journals (`~/ai_dev_sessions/Dashtam/`) - Timestamped entries
- Complex Mermaid diagrams - Syntax-sensitive
- Tables with specific alignment

**Low-Risk Files** (safe for auto-format):

- README files
- Simple guides without complex code
- Text-heavy documentation
- Research notes

**Documentation Inventory:**

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

### Step 2: Configure markdownlint

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

**File-Specific Overrides:**

Use inline comments for special handling:

```markdown
<!-- markdownlint-disable MD013 -->
This line can be very long and won't trigger the line length warning.

<!-- markdownlint-disable-next-line MD034 -->
https://this-bare-url-is-ok.com

<!-- markdownlint-disable-file MD024 -->
<!-- Disables rule for entire file - place at top -->
```

### Step 3: Run Markdown Linting

Use Makefile commands to check markdown files:

```bash
# Check all markdown files (read-only, no changes)
make lint-md

# Check specific file
make lint-md-file FILE="docs/development/guides/my-guide.md"

# Check directory pattern
make lint-md-file FILE="docs/development/**/*.md"
```

**What This Does:** Runs markdownlint-cli2 in a one-off Node.js Docker container, validating all markdown files against configured rules without making changes.

**Direct Docker Usage** (alternative):

```bash
# Check all files
docker run --rm -v $(PWD):/workspace:ro -w /workspace node:24-alpine \
  npx markdownlint-cli2 "**/*.md" "#node_modules"

# Check specific file
docker run --rm -v $(PWD):/workspace:ro -w /workspace node:24-alpine \
  npx markdownlint-cli2 "docs/README.md"
```

**Expected Output:**

```text
🔍 Linting markdown files...
docs/README.md:45 MD022/blanks-around-headings Headings should be surrounded by blank lines
docs/guide.md:120 MD032/blanks-around-lists Lists should be surrounded by blank lines
```

### Step 4: Fix Common Issues

Address violations manually or selectively auto-fix low-risk files:

**Manual Fix Example:**

```markdown
<!-- BEFORE (MD022 violation) -->
Some text here.
## Heading
More text here.

<!-- AFTER (fixed) -->
Some text here.

## Heading

More text here.
```

**Common Fixes:**

- **MD022** - Add blank lines before and after headings
- **MD032** - Add blank lines before and after lists
- **MD031** - Add blank lines before and after code blocks
- **MD040** - Add language identifier to code blocks

**Safe Formatting Guidelines:**

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

### Step 5: Use Auto-Fix Carefully

Only use auto-fix on verified low-risk files:

```bash
# Auto-fix with confirmation prompt
make lint-md-fix

# Prompt will ask:
# ⚠️  WARNING: This will modify markdown files!
# Continue? (yes/no):
```

**Important Notes:**

- ⚠️ Always review changes with `git diff` before committing
- ⚠️ Test rendering on GitHub after auto-fix
- ⚠️ Never auto-fix API flows, WARP.md, or session journals
- ⚠️ Keep rollback plan ready (`git checkout -- <file>`)

**Visual Testing Protocol:**

1. **Preview in GitHub:**

   ```bash
   # Create a test branch
   git checkout -b test/markdown-formatting
   
   # Format a single file
   make lint-md-fix
   
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

**Rollback Plan:**

If formatting breaks something:

```bash
# Revert specific file
git checkout HEAD -- docs/path/to/file.md

# Revert entire commit
git revert <commit-hash>

# Force push if already pushed (use carefully)
git push --force-with-lease origin development
```

### Step 6: Integrate into Workflow

Add linting to your development workflow:

**Before Committing:**

```bash
# Lint documentation changes
make lint-md

# Fix violations manually or with auto-fix (carefully)
make lint-md-fix

# Verify changes
git diff docs/

# Commit
git add docs/
git commit -m "docs: fix markdown linting violations"
```

**In Pull Requests:**

- Run `make lint-md` before submitting PR
- Review markdown diff carefully
- Test rendering for significant changes
- Address CI/CD linting failures

**Add to WARP.md Phase Completion Workflow:**

```markdown
# Lint markdown files (if documentation changes)
make lint-md

# Visual check (for documentation PRs)
# Preview on GitHub to verify rendering
```

## Examples

### Example 1: Linting Single File

Check a specific markdown file for violations:

```bash
make lint-md-file FILE="docs/development/guides/testing-guide.md"
```

**Result:**

```text
docs/development/guides/testing-guide.md:15 MD022/blanks-around-headings
docs/development/guides/testing-guide.md:45 MD032/blanks-around-lists
docs/development/guides/testing-guide.md:120 MD040/fenced-code-language
```

### Example 2: Fixing Common Violations

Fix violations found in linting:

**MD040 - Missing Code Language:**

<!-- BEFORE -->

```text
echo "Hello"
```

<!-- AFTER -->

```bash
echo "Hello"
```

**MD032 - Lists Without Blank Lines:**

```markdown
<!-- BEFORE -->
Paragraph before list.
- Item 1
- Item 2
Paragraph after list.

<!-- AFTER -->
Paragraph before list.

- Item 1
- Item 2

Paragraph after list.
```

### Example 3: VS Code Integration

Configure VS Code for real-time markdown linting:

Create `.vscode/settings.json`:

```json
{
  "markdownlint.config": {
    "extends": ".markdownlint.jsonc"
  },
  "markdownlint.run": "onType",
  "[markdown]": {
    "editor.formatOnSave": false,
    "editor.codeActionsOnSave": {
      "source.fixAll.markdownlint": false
    }
  }
}
```

Install extension: `DavidAnson.vscode-markdownlint`

### Example 4: Pre-Commit Hook

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

### Example 5: GitHub Actions CI

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
              body: '⚠️ Markdown linting found some issues. Please review and fix before merging.'
            })
```

## Verification

How to verify markdown linting is working correctly:

### Check 1: Linting Passes

```bash
# All files should pass linting
make lint-md
# Expected: Exit code 0 (no errors)

# Specific file should pass
make lint-md-file FILE="docs/README.md"
# Expected: No violations reported
```

### Check 2: Visual Presentation Preserved

After fixing violations or auto-formatting:

1. **Git diff review:**

   ```bash
   git diff docs/path/to/file.md
   # Verify no unexpected changes to content
   ```

2. **GitHub preview:**

   - Push to test branch
   - View on GitHub to verify rendering
   - Check tables, code blocks, lists render correctly

3. **Local preview** (if MkDocs implemented):

   ```bash
   make docs-serve
   # Navigate to affected pages
   ```

## Troubleshooting

### Issue 1: Line Too Long (MD013)

**Symptoms:**

- Warning: Line exceeds maximum length

**Cause:** Line length rule enabled (disabled in Dashtam by default)

**Solution:**

```markdown
<!-- Solution 1: Disable for specific line -->
<!-- markdownlint-disable-next-line MD013 -->
This is a very long line that needs to stay on one line.

<!-- Solution 2: Break long URLs -->
[link text][ref]

[ref]: https://very-long-url.com/path/to/resource
```

### Issue 2: Multiple Headings Same Content (MD024)

**Symptoms:**

- Warning: Multiple headings with the same content

**Cause:** Duplicate heading text at same level

**Solution:**

```markdown
<!-- BAD -->
## Authentication
## Authentication

<!-- GOOD -->
## Authentication Flow
## Authentication API
```

### Issue 3: Bare URL Without Brackets (MD034)

**Symptoms:**

- Warning: Bare URL without angle brackets

**Cause:** URL not wrapped in brackets or link syntax

**Solution:**

```markdown
<!-- BAD -->
https://example.com

<!-- GOOD Option 1 -->
<https://example.com>

<!-- GOOD Option 2 -->
[https://example.com](https://example.com)
```

### Issue 4: Formatting Breaks Visual Presentation

**Symptoms:**

- Tables misaligned after formatting
- Code blocks reformatted incorrectly
- List indentation changed

**Cause:** Auto-fix applied to high-risk file

**Solution:**

```bash
# Rollback changes
git checkout HEAD -- docs/path/to/file.md

# Fix manually instead of auto-fix
# Edit file directly, then verify with lint
make lint-md-file FILE="docs/path/to/file.md"
```

## Best Practices

Follow these best practices for markdown quality:

- ✅ **Run linting before commit** - Always check with `make lint-md`
- ✅ **Fix violations manually for high-risk files** - API flows, WARP.md, diagrams
- ✅ **Use auto-fix only for low-risk files** - READMEs, simple guides
- ✅ **Review diffs carefully** - Check every change before committing
- ✅ **Test rendering after changes** - Preview on GitHub
- ✅ **Commit configuration changes** - Include `.markdownlint.jsonc` updates
- ✅ **Use inline comments for exceptions** - Document why rules are disabled
- ✅ **Keep configuration documented** - Explain rule choices in config
- ✅ **Follow phased rollout** - Start lint-only, gradually add enforcement
- ✅ **Maintain team documentation** - Keep markdown standards current

**Phased Rollout Strategy:**

Phase 1: Linting Only (Recommended Start)

- Add markdownlint-cli2, create `.markdownlint.jsonc` and `.markdownlintignore`
- Add `make lint-md` commands
- Run `make lint-md` to assess current state
- Document common issues and patterns

Phase 2: Manual Fixes

- Fix critical warnings in high-value files (README.md, key architecture docs)
- Use `--fix` only on low-risk files
- Manual review of every change
- Test rendering on GitHub after each fix

Phase 3: CI/CD Integration

- Add markdownlint check to GitHub Actions
- Run in "check only" mode (no auto-fix)
- Make it non-blocking initially (warning only)
- Collect feedback from team

Phase 4: Gradual Enforcement

- Change CI workflow to blocking (required check)
- Update CONTRIBUTING.md with markdown guidelines
- Add linting to PR template checklist
- Gradually fix remaining warnings

**Regular Maintenance Tasks:**

- Review any new markdownlint warnings
- Update `.markdownlintignore` if needed
- Check for markdownlint-cli2 updates
- Review and update `.markdownlint.jsonc` rules
- Evaluate if any disabled rules can be enabled
- Check for new best practices

**Per PR Tasks:**

- Run `make lint-md` before submitting
- Review markdown diff carefully
- Test rendering for significant changes

### Common Mistakes to Avoid

- ❌ **Auto-fixing everything** - High risk of breaking formatting
- ❌ **Ignoring linting failures** - Address violations promptly
- ❌ **Using Prettier for markdown** - Too opinionated, breaks formatting in Dashtam
- ❌ **Editing configuration manually without testing** - Always verify with `make lint-md`
- ❌ **Committing without review** - Always diff and verify changes
- ❌ **Skipping visual testing** - Preview changes on GitHub before merging
- ❌ **Making CI blocking immediately** - Team needs time to adapt
- ❌ **Using deprecated tools** - Stick with markdownlint-cli2

**Tool Comparison:**

**markdownlint-cli2 (Recommended):**

- Fast, modern, actively maintained
- Highly configurable (`.markdownlint.jsonc`)
- Works in Docker one-off container
- No project dependencies needed

**remark-cli with remark-lint (Alternative):**

- More sophisticated formatting
- Pluggable architecture
- Use for complex transformations
- When markdownlint rules too strict

**prettier (NOT Recommended):**

- ⚠️ Opinionated formatting (may break presentation)
- ⚠️ Limited Markdown-specific configuration
- ⚠️ May reformat code blocks unexpectedly

## Next Steps

After mastering markdown linting, consider:

- [ ] Set up pre-commit hooks for automatic linting
- [ ] Integrate linting into CI/CD pipeline (Phase 3)
- [ ] Enable additional markdownlint rules gradually
- [ ] Document project-specific markdown conventions
- [ ] Train team on markdown linting workflow
- [ ] Review and update `.markdownlint.jsonc` configuration periodically
- [ ] Explore MkDocs for local preview capabilities
- [ ] Consider badge in README showing lint status
- [ ] Add markdown quality metrics to team dashboard
- [ ] Schedule periodic documentation quality audits

**Success Metrics:**

- **Quality:** Consistent markdown formatting across all docs
- **Velocity:** No significant slowdown in PR review process
- **Safety:** Zero visual presentation issues from formatting
- **Adoption:** Team comfortable running `make lint-md` before commits

**Integration with WARP.md:**

Add to "Coding Standards" section:

```markdown
### Markdown Documentation Standards

- **Linting Required:** All Markdown files must pass `make lint-md`
- **No Auto-Formatting:** Do not use auto-fix on high-risk files (API flows, WARP.md)
- **Visual Testing:** Preview changes on GitHub before committing
- **Configuration:** Follow rules in `.markdownlint.jsonc`
- **See:** [Markdown Linting Guide](docs/development/guides/markdown-linting-guide.md)
```

## References

- [markdownlint-cli2 Documentation](https://github.com/DavidAnson/markdownlint-cli2) - Official tool documentation
- [markdownlint Rules](https://github.com/DavidAnson/markdownlint/blob/main/doc/Rules.md) - Complete rule reference
- [Mermaid Diagram Standards](mermaid-diagram-standards.md) - Diagram creation guidelines
- [Documentation Template System](../../templates/README.md) - Template usage guide
- `WARP.md` (project root) - Project coding standards and markdown quality rules
- [Docstring Standards Guide](docstring-standards.md) - Python documentation standards
- [Documentation Implementation Guide](documentation-implementation-guide.md) - MkDocs setup

---

## Document Information

**Template:** [guide-template.md](../../templates/guide-template.md)
**Created:** 2025-10-11
**Last Updated:** 2025-10-20
