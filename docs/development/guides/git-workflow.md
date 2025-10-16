# Git Workflow Guide

## Table of Contents

- [Overview](#overview)
  - [Key Principles](#key-principles)
- [Branching Strategy (Git Flow)](#branching-strategy-git-flow)
  - [Branch Hierarchy](#branch-hierarchy)
  - [Branch Overview](#branch-overview)
- [Semantic Versioning](#semantic-versioning)
  - [Version Format: `vX.Y.Z`](#version-format-vxyz)
  - [Examples](#examples)
  - [Pre-release Versions](#pre-release-versions)
- [Branch Types](#branch-types)
  - [1. `main` Branch](#1-main-branch)
  - [2. `development` Branch](#2-development-branch)
  - [3. `feature/*` Branches](#3-feature-branches)
  - [4. `fix/*` Branches](#4-fix-branches)
  - [5. `release/*` Branches](#5-release-branches)
  - [6. `hotfix/*` Branches](#6-hotfix-branches)
- [Commit Message Conventions](#commit-message-conventions)
  - [Format](#format)
  - [Types](#types)
  - [Breaking Changes](#breaking-changes)
  - [Examples](#examples-1)
  - [Commit Message Rules](#commit-message-rules)
- [Workflow Examples](#workflow-examples)
  - [Example 1: Starting a New Feature](#example-1-starting-a-new-feature)
  - [Example 2: Fixing a Bug](#example-2-fixing-a-bug)
  - [Example 3: Creating a Release](#example-3-creating-a-release)
  - [Example 4: Emergency Hotfix](#example-4-emergency-hotfix)
- [Pull Request Process](#pull-request-process)
  - [Creating a Pull Request](#creating-a-pull-request)
  - [Reviewing a Pull Request](#reviewing-a-pull-request)
  - [Addressing Review Feedback](#addressing-review-feedback)
  - [Creating Pull Requests with GitHub CLI](#creating-pull-requests-with-github-cli)
  - [Merging Pull Requests](#merging-pull-requests)
- [Branch Protection Rules](#branch-protection-rules)
  - [Required Protection Settings](#required-protection-settings)
    - [For `main` Branch](#for-main-branch)
    - [For `development` Branch](#for-development-branch)
  - [Setting Up Branch Protection (GitHub CLI)](#setting-up-branch-protection-github-cli)
  - [Setting Up via GitHub Web UI](#setting-up-via-github-web-ui)
- [Release Process](#release-process)
  - [Standard Release Workflow](#standard-release-workflow)
  - [Automated Release with GitHub Actions](#automated-release-with-github-actions)
- [Hotfix Process](#hotfix-process)
  - [When to Create a Hotfix](#when-to-create-a-hotfix)
  - [Hotfix Workflow](#hotfix-workflow)
- [Common Commands Reference](#common-commands-reference)
  - [Daily Operations](#daily-operations)
  - [Undoing Changes](#undoing-changes)
  - [Branch Management](#branch-management)
  - [Viewing History](#viewing-history)
  - [Stashing Changes](#stashing-changes)
  - [Rebasing and Merging](#rebasing-and-merging)
  - [Resolving Conflicts](#resolving-conflicts)
  - [Tags](#tags)
- [Best Practices](#best-practices)
  - [General Guidelines](#general-guidelines)
  - [Commit Hygiene](#commit-hygiene)
  - [Branch Hygiene](#branch-hygiene)
  - [Collaboration Tips](#collaboration-tips)
  - [Security Considerations](#security-considerations)
- [Troubleshooting](#troubleshooting)
  - [Common Issues](#common-issues)
    - ["Your branch is behind"](#your-branch-is-behind)
    - ["Your branch has diverged"](#your-branch-has-diverged)
    - ["Merge conflict"](#merge-conflict)
    - ["Accidentally committed to wrong branch"](#accidentally-committed-to-wrong-branch)
    - ["Need to undo last commit"](#need-to-undo-last-commit)
- [Additional Resources](#additional-resources)
  - [Documentation](#documentation)
  - [Tools](#tools)
  - [Internal Resources](#internal-resources)
- [Questions or Issues?](#questions-or-issues)

---

## Overview

Dashtam uses **Git Flow** as our branching model, which provides a robust framework for managing releases, features, and hotfixes. Combined with **Semantic Versioning** and **Conventional Commits**, this ensures our codebase remains organized, traceable, and production-ready.

### Key Principles

- ✅ **All work happens in feature branches** - Never commit directly to `main` or `development`
- ✅ **Tests must pass** - All PRs require passing CI tests before merge
- ✅ **Code review required** - At least one approval needed for PRs to protected branches
- ✅ **Semantic versioning** - Clear version numbers that convey meaning
- ✅ **Conventional commits** - Structured commit messages for automated changelog generation

---

## Branching Strategy (Git Flow)

### Branch Hierarchy

```text
main (production)
  ├── development (integration)
  │   ├── feature/oauth-integration
  │   ├── feature/account-api
  │   └── fix/token-encryption-bug
  ├── release/v1.2.0 (prepared release)
  └── hotfix/v1.1.1 (emergency fix)
```

### Branch Overview

| Branch | Purpose | Protected | Lifetime | Deploy Target |
|--------|---------|-----------|----------|---------------|
| `main` | Production-ready code | ✅ Yes | Permanent | Production |
| `development` | Integration branch | ✅ Yes | Permanent | Staging/Dev |
| `feature/*` | New features | ❌ No | Temporary | N/A |
| `fix/*` | Bug fixes | ❌ No | Temporary | N/A |
| `release/*` | Release preparation | ✅ Yes | Temporary | Staging |
| `hotfix/*` | Emergency fixes | ✅ Yes | Temporary | Production |

---

## Semantic Versioning

We follow [Semantic Versioning 2.0.0](https://semver.org/): `MAJOR.MINOR.PATCH`

### Version Format: `vX.Y.Z`

- **MAJOR** (X): Breaking changes, incompatible API changes
- **MINOR** (Y): New features, backward-compatible functionality
- **PATCH** (Z): Bug fixes, backward-compatible patches

### Examples

```text
v1.0.0  → Initial stable release
v1.1.0  → Added account listing API (new feature)
v1.1.1  → Fixed token refresh bug (bug fix)
v1.2.0  → Added transaction endpoints (new feature)
v2.0.0  → Changed OAuth flow (breaking change)
```

### Pre-release Versions

For development and testing:

- `v1.2.0-alpha.1` - Alpha release (unstable, internal testing)
- `v1.2.0-beta.1` - Beta release (feature-complete, external testing)
- `v1.2.0-rc.1` - Release candidate (production-ready, final testing)

---

## Branch Types

### 1. `main` Branch

**Purpose:** Production-ready code only

**Rules:**

- ✅ Always deployable to production
- ✅ Protected (no direct commits)
- ✅ Requires PR with approvals
- ✅ All tests must pass
- ✅ Tagged with version numbers (e.g., `v1.2.0`)

**Receives merges from:**

- `release/*` branches (new releases)
- `hotfix/*` branches (emergency fixes)

### 2. `development` Branch

**Purpose:** Integration branch for ongoing development

**Rules:**

- ✅ Protected (no direct commits)
- ✅ Requires PR with approvals
- ✅ All tests must pass
- ✅ Always ahead of `main` (contains unreleased features)

**Receives merges from:**

- `feature/*` branches (new features)
- `fix/*` branches (bug fixes)
- `hotfix/*` branches (after production deployment)

### 3. `feature/*` Branches

**Purpose:** Develop new features

**Naming Convention:** `feature/short-description`

**Examples:**

```bash
feature/account-listing-api
feature/oauth-plaid-integration
feature/dashboard-ui
feature/transaction-sync
```

**Lifecycle:**

```bash
# Create from development
git checkout development
git pull origin development
git checkout -b feature/account-listing-api

# Work on feature, commit regularly
git add .
git commit -m "feat: add account model and repository"

# Push to remote
git push -u origin feature/account-listing-api

# Create PR to development
# After merge, delete branch
git branch -d feature/account-listing-api
git push origin --delete feature/account-listing-api
```

### 4. `fix/*` Branches

**Purpose:** Fix bugs in development

**Naming Convention:** `fix/short-description`

**Examples:**

```text
fix/token-encryption-error
fix/database-connection-leak
fix/oauth-callback-timeout
fix/test-isolation-issue
```

**Lifecycle:** Same as feature branches (branch from and merge to `development`)

### 5. `release/*` Branches

**Purpose:** Prepare a new release

**Naming Convention:** `release/vX.Y.Z`

**Examples:**

```text
release/v1.2.0
release/v2.0.0
release/v1.3.0-beta.1
```

**When to Create:**

- When `development` has enough features for a release
- When you want to freeze features and focus on stabilization

**Lifecycle:**

```bash
# Create from development
git checkout development
git pull origin development
git checkout -b release/v1.2.0

# Update version numbers
# - Update pyproject.toml or version file
# - Update CHANGELOG.md
git add .
git commit -m "chore: bump version to 1.2.0"

# Bug fixes only (no new features!)
git commit -m "fix: resolve OAuth timeout issue"

# When ready, merge to main
git checkout main
git merge --no-ff release/v1.2.0
git tag -a v1.2.0 -m "Release version 1.2.0"
git push origin main --tags

# Also merge back to development
git checkout development
git merge --no-ff release/v1.2.0
git push origin development

# Delete release branch
git branch -d release/v1.2.0
git push origin --delete release/v1.2.0
```

### 6. `hotfix/*` Branches

**Purpose:** Emergency fixes for production

**Naming Convention:** `hotfix/vX.Y.Z` or `hotfix/critical-issue`

**Examples:**

```text
hotfix/v1.1.1
hotfix/security-token-leak
hotfix/critical-db-error
```

**When to Create:**

- Critical bug in production
- Security vulnerability
- Data loss risk
- System downtime

**Lifecycle:**

```bash
# Create from main (production)
git checkout main
git pull origin main
git checkout -b hotfix/v1.1.1

# Fix the critical issue
git commit -m "fix: prevent token leak in error logs"

# Update version (patch increment)
git commit -m "chore: bump version to 1.1.1"

# Merge to main
git checkout main
git merge --no-ff hotfix/v1.1.1
git tag -a v1.1.1 -m "Hotfix: Security token leak"
git push origin main --tags

# Merge to development
git checkout development
git merge --no-ff hotfix/v1.1.1
git push origin development

# Delete hotfix branch
git branch -d hotfix/v1.1.1
git push origin --delete hotfix/v1.1.1
```

---

## Commit Message Conventions

We use **Conventional Commits** for automated changelog generation and semantic versioning.

### Format

```text
<type>(<scope>): <subject>

<body>

<footer>
```

### Types

| Type | Purpose | Version Impact | Example |
|------|---------|----------------|---------|
| `feat` | New feature | Minor | `feat(api): add account listing endpoint` |
| `fix` | Bug fix | Patch | `fix(auth): resolve OAuth timeout` |
| `docs` | Documentation | None | `docs: update API documentation` |
| `style` | Code style (formatting) | None | `style: format with black` |
| `refactor` | Code refactoring | None | `refactor(db): simplify query logic` |
| `test` | Add/update tests | None | `test: add unit tests for encryption` |
| `chore` | Maintenance | None | `chore: update dependencies` |
| `perf` | Performance improvement | Patch | `perf(db): add index on user_id` |
| `ci` | CI/CD changes | None | `ci: add test coverage reporting` |
| `build` | Build system changes | None | `build: update Docker base image` |
| `revert` | Revert previous commit | Varies | `revert: "feat: add broken feature"` |

### Breaking Changes

Use `BREAKING CHANGE:` in footer or `!` after type:

```bash
# Method 1: Footer
feat(api)!: change authentication endpoint structure

BREAKING CHANGE: Auth endpoint moved from /auth to /api/v1/auth

# Method 2: Exclamation mark
feat!: redesign OAuth flow
```

### Examples

```bash
# Simple feature
feat(providers): add Plaid provider support

# Bug fix with scope
fix(token): prevent encryption key rotation during refresh

# Documentation
docs(api): add examples for account endpoints

# Test addition
test(integration): add OAuth flow integration tests

# Chore with body
chore(deps): update FastAPI to 0.110.0

Update FastAPI and dependencies to latest versions
for security patches and new features.

# Breaking change
feat(api)!: restructure response format

BREAKING CHANGE: All API responses now wrapped in data envelope
Clients must update to access response.data instead of response

# Multiple types in one commit (discouraged, but if needed)
feat(auth): add OAuth provider registry
test(auth): add registry unit tests
```

### Commit Message Rules

✅ **DO:**

- Use present tense ("add feature" not "added feature")
- Use imperative mood ("move cursor to" not "moves cursor to")
- Keep subject line under 72 characters
- Capitalize the subject line
- Don't end subject line with period
- Separate subject from body with blank line
- Wrap body at 72 characters
- Reference issues and PRs in footer

❌ **DON'T:**

- Write vague messages like "fix bug" or "update code"
- Mix multiple unrelated changes in one commit
- Commit incomplete work to shared branches
- Use past tense
- Include implementation details in subject

---

## Workflow Examples

### Example 1: Starting a New Feature

```bash
# 1. Ensure you're up to date
git checkout development
git pull origin development

# 2. Create feature branch
git checkout -b feature/transaction-api

# 3. Work on the feature
# Edit files, write tests, etc.

# 4. Commit changes (multiple commits OK)
git add src/api/transactions.py tests/test_transactions.py
git commit -m "feat(api): add transaction model and schema"

git add src/services/transaction_service.py
git commit -m "feat(api): add transaction service with filtering"

git add tests/test_transaction_service.py
git commit -m "test(api): add transaction service unit tests"

# 5. Keep branch updated with development
git fetch origin
git rebase origin/development

# 6. Push to remote
git push -u origin feature/transaction-api

# 7. Create Pull Request on GitHub
# - Title: "feat(api): Add transaction listing and filtering API"
# - Description: Explain the feature, link to issues, add screenshots
# - Request reviews

# 8. Address review feedback
git add .
git commit -m "refactor(api): address PR feedback on validation"
git push origin feature/transaction-api

# 9. After PR is merged
git checkout development
git pull origin development
git branch -d feature/transaction-api
```

### Example 2: Fixing a Bug

```bash
# 1. Create fix branch from development
git checkout development
git pull origin development
git checkout -b fix/token-refresh-error

# 2. Fix the bug
# Edit files, add tests

# 3. Commit the fix
git add src/services/token_service.py tests/test_token_service.py
git commit -m "fix(auth): prevent race condition in token refresh"

# 4. Push and create PR
git push -u origin fix/token-refresh-error

# 5. After merge, cleanup
git checkout development
git pull origin development
git branch -d fix/token-refresh-error
```

### Example 3: Creating a Release

```bash
# 1. Create release branch from development
git checkout development
git pull origin development
git checkout -b release/v1.3.0

# 2. Update version numbers
# Edit pyproject.toml, __version__.py, etc.
git add .
git commit -m "chore: bump version to 1.3.0"

# 3. Update CHANGELOG.md
# Add release notes, breaking changes, new features
git add CHANGELOG.md
git commit -m "docs: update changelog for v1.3.0"

# 4. Fix any last-minute bugs (no new features!)
git commit -m "fix: resolve edge case in account sync"

# 5. Merge to main
git checkout main
git pull origin main
git merge --no-ff release/v1.3.0

# 6. Tag the release
git tag -a v1.3.0 -m "Release version 1.3.0

New Features:
- Transaction API with filtering
- Account balance tracking
- Plaid provider integration

Bug Fixes:
- Fixed token refresh race condition
- Resolved database connection leak
"

# 7. Push main and tags
git push origin main
git push origin v1.3.0

# 8. Merge back to development
git checkout development
git merge --no-ff release/v1.3.0
git push origin development

# 9. Cleanup
git branch -d release/v1.3.0
git push origin --delete release/v1.3.0

# 10. Deploy to production (via CI/CD)
```

### Example 4: Emergency Hotfix

```bash
# 1. Create hotfix from main
git checkout main
git pull origin main
git checkout -b hotfix/v1.2.1

# 2. Fix the critical issue quickly
git add src/core/security.py
git commit -m "fix(security): prevent API key exposure in logs"

# 3. Update version
git commit -m "chore: bump version to 1.2.1"

# 4. Update CHANGELOG
git add CHANGELOG.md
git commit -m "docs: add hotfix v1.2.1 to changelog"

# 5. Merge to main
git checkout main
git merge --no-ff hotfix/v1.2.1
git tag -a v1.2.1 -m "Hotfix v1.2.1: Security patch for API key exposure"
git push origin main --tags

# 6. Merge to development
git checkout development
git merge --no-ff hotfix/v1.2.1
git push origin development

# 7. Cleanup
git branch -d hotfix/v1.2.1
git push origin --delete hotfix/v1.2.1

# 8. Immediate production deployment
```

---

## Pull Request Process

### Creating a Pull Request

1. **Push your branch** to GitHub:

   ```bash
   git push -u origin feature/your-feature
   ```

2. **Create PR on GitHub:**
   - Navigate to repository
   - Click "Pull requests" → "New pull request"
   - Select base branch (`development` for features/fixes)
   - Select your feature branch
   - Click "Create pull request"

3. **Write a good PR description:**

   ```markdown
   ## Description
   Add transaction listing API with filtering capabilities
   
   ## Type of Change
   - [x] New feature
   - [ ] Bug fix
   - [ ] Breaking change
   - [ ] Documentation update
   
   ## Changes Made
   - Added Transaction model and schema
   - Implemented transaction service with filtering
   - Added API endpoints for listing transactions
   - Added comprehensive unit and integration tests
   
   ## Testing
   - [x] Unit tests pass (`make test-unit`)
   - [x] Integration tests pass (`make test-integration`)
   - [x] All tests pass (`make test`)
   - [x] Linting passes (`make lint`)
   - [x] Manual testing completed
   
   ## Related Issues
   Closes #42
   Related to #38
   
   ## Screenshots (if applicable)
   [Add screenshots of UI changes]
   
   ## Checklist
   - [x] Code follows project style guidelines
   - [x] Self-review completed
   - [x] Comments added for complex logic
   - [x] Documentation updated
   - [x] No new warnings generated
   - [x] Tests added/updated
   - [x] All tests passing
   ```

4. **Request reviews** from team members

5. **Wait for CI checks** to pass (automated tests)

### Reviewing a Pull Request

**As a Reviewer:**

✅ **Check:**

- Code quality and readability
- Tests coverage and quality
- Documentation updates
- No security vulnerabilities
- Follows project conventions
- Breaking changes clearly documented

✅ **Review Types:**

- **Approve:** Code is good to merge
- **Request changes:** Issues need to be addressed
- **Comment:** Feedback without blocking merge

✅ **Best Practices:**

- Be constructive and kind
- Explain the "why" behind suggestions
- Distinguish between blocking and non-blocking feedback
- Test the code locally if needed

### Addressing Review Feedback

```bash
# Make requested changes
git add .
git commit -m "refactor: address PR feedback on error handling"

# Push updates
git push origin feature/your-feature

# PR automatically updates
# Request re-review if needed
```

### Creating Pull Requests with GitHub CLI

**Using `gh` CLI** (recommended):

```bash
# Basic PR creation (interactive prompts)
gh pr create

# Create PR with all details in one command
gh pr create \
  --base development \
  --title "feat(api): Add transaction filtering API" \
  --body "Full description here..."

# Create PR from template file
gh pr create --base development --title "My Feature" --body-file PR_TEMPLATE.md

# Create draft PR (for work in progress)
gh pr create --base development --draft --title "WIP: New feature"

# Assign reviewers and labels
gh pr create \
  --base development \
  --reviewer username1,username2 \
  --label "enhancement,needs-review"
```

**Example: Comprehensive PR Creation:**

```bash
# After pushing your feature branch
git push -u origin feature/password-reset-session-revocation

# Create detailed PR
gh pr create --base development --title "feat(security): Password reset with automatic session revocation" --body "
## Description
Implements automatic session revocation on password reset for enhanced security.
When a user resets their password, all active refresh tokens are revoked.

## Type of Change
- [x] New feature
- [x] Security enhancement
- [x] Documentation update

## Testing
- [x] Unit tests pass
- [x] Integration tests pass
- [x] All tests pass (305 tests, 77% coverage)
- [x] Linting passes
- [x] Code formatting passes

## Related Issues
Closes #42
Related to #38
"
```

**Viewing and Managing PRs:**

```bash
# View PR in browser
gh pr view 16 --web

# View PR details in terminal
gh pr view 16

# Check PR status and checks
gh pr view 16 --json statusCheckRollup

# List all open PRs
gh pr list

# List PRs by status
gh pr list --state open
gh pr list --state closed

# Review PR
gh pr review 16 --approve --body "LGTM! Great work."
gh pr review 16 --request-changes --body "Please address X, Y, Z"
gh pr review 16 --comment --body "Minor feedback: consider..."
```

### Merging Pull Requests

**Merge Options:**

1. **Merge commit** (preferred for features):
   - Preserves complete history
   - Shows when feature was merged
   - Use for `feature/*` → `development`

2. **Squash and merge** (for small fixes):
   - Combines all commits into one
   - Cleaner history
   - Use for small bug fixes with many commits

3. **Rebase and merge** (use sparingly):
   - Linear history
   - Can complicate history if not careful

**Merging with GitHub CLI:**

```bash
# Basic merge (uses repository default merge method)
gh pr merge 16

# Squash merge (recommended for most PRs)
gh pr merge 16 --squash --delete-branch

# Merge commit (preserves all commits)
gh pr merge 16 --merge --delete-branch

# Rebase merge (linear history)
gh pr merge 16 --rebase --delete-branch

# Admin merge (bypass branch protection)
gh pr merge 16 --squash --delete-branch --admin

# Auto-merge when checks pass
gh pr merge 16 --squash --auto --delete-branch
```

**Merge Command Options Explained:**

| Option | Description | Use Case |
|--------|-------------|----------|
| `--squash` | Squash all commits into one | Clean history, most PRs |
| `--merge` | Create merge commit | Preserve feature history |
| `--rebase` | Rebase and merge | Linear history |
| `--delete-branch` | Delete branch after merge | Cleanup (recommended) |
| `--admin` | Bypass branch protection | Admin emergency merge |
| `--auto` | Auto-merge when checks pass | CI-dependent merge |
| `--body "text"` | Custom merge commit message | Override default |

**Branch Protection and PR Merging:**

```bash
# Check if PR is mergeable
gh pr view 16 --json mergeable,mergeStateStatus

# Example output:
{
  "mergeable": "MERGEABLE",
  "mergeStateStatus": "BLOCKED"  # Requires approval or checks
}
```

**Merge State Status:**

- `CLEAN` - Ready to merge
- `BLOCKED` - Cannot merge (missing approvals or failing checks)
- `BEHIND` - Branch needs to be updated
- `UNSTABLE` - Checks failing
- `DRAFT` - PR is in draft state

**Common Merge Scenarios:**

**Scenario 1: Feature PR to Development (Standard):**

```bash
# After all checks pass and approval received
gh pr merge 16 --squash --delete-branch
```

**Scenario 2: Self-Approval Required (Admin):**

```bash
# Review your own PR for documentation
gh pr review 16 --approve --body "Self-approval: All tests passing, security enhancement thoroughly tested."

# Then merge
gh pr merge 16 --squash --delete-branch
```

**Scenario 3: Bypass Review (Admin Emergency):**

```bash
# Use --admin flag to bypass branch protection
gh pr merge 16 --squash --delete-branch --admin
```

**Scenario 4: Release PR to Main:**

```bash
# Use merge commit to preserve release history
gh pr merge 42 --merge --delete-branch

# Tag the release
git checkout main
git pull origin main
git tag -a v1.4.0 -m "Release version 1.4.0"
git push origin v1.4.0
```

**Scenario 5: Hotfix PR (Urgent):**

```bash
# Squash merge to main
gh pr merge 99 --squash --delete-branch --admin

# Tag immediately
git checkout main
git pull origin main
git tag -a v1.3.1 -m "Hotfix v1.3.1: Critical security patch"
git push origin v1.3.1

# Merge back to development
git checkout development
git pull origin development
git merge --no-ff main
git push origin development
```

**Customizing Merge Commit Message:**

```bash
# Squash merge with custom commit message
gh pr merge 16 --squash --delete-branch --body "feat(security): Password reset with automatic session revocation (#16)

* Core: AuthService.reset_password() revokes all active refresh tokens
* Security: Forces logout on all devices for breach response
* Testing: 10 new unit tests, 305 total tests passing
* Coverage: 77% overall (+0.85%), Services 86.81% (+2.78%)
* Docs: Architecture, API flows, and improvement guide updated
* CI: Fixed lint job to use modern UV sync commands

Follows Pattern A (JWT Access + Opaque Refresh) security model.
Comprehensive test coverage ensures reliable behavior."
```

**After Merge:**

```bash
# Update local development branch
git checkout development
git pull origin development

# Delete local feature branch
git branch -d feature/your-feature

# Verify branch was deleted remotely (if --delete-branch used)
git fetch --prune
```

---

## Branch Protection Rules

### Required Protection Settings

#### For `main` Branch

```yaml
Settings → Branches → Branch protection rules → Add rule

Branch name pattern: main

✅ Require a pull request before merging
  ✅ Require approvals: 1
  ✅ Dismiss stale pull request approvals when new commits are pushed
  ✅ Require review from Code Owners (optional)

✅ Require status checks to pass before merging
  ✅ Require branches to be up to date before merging
  Required status checks:
    - Test Suite / Run Tests
    - Code Quality / lint

✅ Require conversation resolution before merging

✅ Require linear history (optional)

✅ Do not allow bypassing the above settings
  ❌ Allow force pushes
  ❌ Allow deletions
```

#### For `development` Branch

```yaml
Branch name pattern: development

✅ Require a pull request before merging
  ✅ Require approvals: 1

✅ Require status checks to pass before merging
  ✅ Require branches to be up to date before merging
  Required status checks:
    - Test Suite / Run Tests
    - Code Quality / lint

✅ Require conversation resolution before merging

❌ Require linear history
❌ Do not allow bypassing the above settings (can allow for admins)
❌ Allow force pushes
❌ Allow deletions
```

### Setting Up Branch Protection (GitHub CLI)

```bash
# Protect main branch
gh api repos/faiyaz7283/Dashtam/branches/main/protection \
  --method PUT \
  --field required_status_checks[strict]=true \
  --field required_status_checks[contexts][]=Test Suite / Run Tests \
  --field required_status_checks[contexts][]=Code Quality / lint \
  --field required_pull_request_reviews[required_approving_review_count]=1 \
  --field required_pull_request_reviews[dismiss_stale_reviews]=true \
  --field enforce_admins=true \
  --field restrictions=null

# Protect development branch
gh api repos/faiyaz7283/Dashtam/branches/development/protection \
  --method PUT \
  --field required_status_checks[strict]=true \
  --field required_status_checks[contexts][]=Test Suite / Run Tests \
  --field required_status_checks[contexts][]=Code Quality / lint \
  --field required_pull_request_reviews[required_approving_review_count]=1 \
  --field required_pull_request_reviews[dismiss_stale_reviews]=true \
  --field enforce_admins=false \
  --field restrictions=null
```

### Setting Up via GitHub Web UI

1. Go to: `Settings` → `Branches` → `Add branch protection rule`
2. Enter branch name pattern: `main` or `development`
3. Enable required settings as shown above
4. Click "Create" or "Save changes"

---

## Release Process

### Standard Release Workflow

```bash
# 1. Ensure development is stable
make test  # All tests pass
make lint  # No linting errors

# 2. Create release branch
git checkout development
git pull origin development
git checkout -b release/v1.4.0

# 3. Version bump
# Update version in:
# - pyproject.toml
# - src/__init__.py or src/__version__.py
# - docs/conf.py (if using Sphinx)

# 4. Update CHANGELOG.md
cat > CHANGELOG_ADDITION.md << 'EOF'
## [1.4.0] - 2024-01-15

### Added
- Transaction filtering by date range
- Account balance tracking
- Plaid provider integration

### Changed
- Improved OAuth token refresh logic
- Updated Docker base images to Python 3.13

### Fixed
- Fixed race condition in token refresh
- Resolved database connection leak

### Security
- Updated cryptography library to patch CVE-2024-XXXX
EOF

# 5. Commit version changes
git add .
git commit -m "chore: bump version to 1.4.0"
git commit -m "docs: update changelog for v1.4.0"

# 6. Final testing
make test
make lint

# 7. Push release branch
git push -u origin release/v1.4.0

# 8. Create PR to main
# Title: "Release v1.4.0"
# Get approval and merge

# 9. After merge, tag release on main
git checkout main
git pull origin main
git tag -a v1.4.0 -m "Release version 1.4.0"
git push origin v1.4.0

# 10. Merge back to development
git checkout development
git merge --no-ff main
git push origin development

# 11. Cleanup
git branch -d release/v1.4.0
git push origin --delete release/v1.4.0

# 12. GitHub Release
# Create release on GitHub from tag v1.4.0
# Copy changelog content
# Add any binaries or assets
```

### Automated Release with GitHub Actions

Create `.github/workflows/release.yml`:

```yaml
name: Release

on:
  push:
    tags:
      - 'v*'

jobs:
  release:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Create Release
        uses: actions/create-release@v1
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        with:
          tag_name: ${{ github.ref }}
          release_name: Release ${{ github.ref }}
          draft: false
          prerelease: false
```

---

## Hotfix Process

### When to Create a Hotfix

**Create hotfix if:**

- ❌ Critical production bug
- ❌ Security vulnerability
- ❌ Data loss or corruption
- ❌ Service downtime
- ❌ Performance degradation affecting users

**Don't create hotfix if:**

- ✅ Minor UI glitch (can wait for regular release)
- ✅ Non-critical bug (can wait for regular release)
- ✅ Feature request (definitely not a hotfix)

### Hotfix Workflow

```bash
# 1. Create hotfix from main
git checkout main
git pull origin main
git checkout -b hotfix/v1.3.1

# 2. Fix the issue QUICKLY
# Focus on the specific problem
# Don't refactor or add features

# 3. Add tests for the fix
git add src/ tests/
git commit -m "fix(critical): resolve database connection timeout"

# 4. Update version (patch increment)
# v1.3.0 → v1.3.1
git commit -m "chore: bump version to 1.3.1"

# 5. Update CHANGELOG
git add CHANGELOG.md
git commit -m "docs: add hotfix v1.3.1 to changelog"

# 6. Test thoroughly
make test
make lint

# 7. Create PR to main (expedited review)
# Title: "HOTFIX v1.3.1: Critical database timeout"
# Mark as urgent

# 8. After approval and merge
git checkout main
git pull origin main
git tag -a v1.3.1 -m "Hotfix v1.3.1: Database connection timeout"
git push origin main v1.3.1

# 9. Merge to development
git checkout development
git pull origin development
git merge --no-ff main
git push origin development

# 10. Cleanup
git branch -d hotfix/v1.3.1
git push origin --delete hotfix/v1.3.1

# 11. Deploy to production ASAP
```

---

## Common Commands Reference

### Daily Operations

```bash
# Check current status
git status
git branch
git log --oneline --graph --decorate --all -10

# Update local branches
git fetch origin
git checkout development
git pull origin development

# Start new feature
git checkout -b feature/my-feature

# Commit changes
git add .
git status  # Review what you're committing
git commit -m "feat: add new feature"

# Push changes
git push -u origin feature/my-feature

# Keep branch updated
git fetch origin
git rebase origin/development

# Switch branches
git checkout development
git checkout feature/my-feature
```

### Undoing Changes

```bash
# Discard local changes (not staged)
git checkout -- <file>
git restore <file>

# Unstage files
git reset HEAD <file>
git restore --staged <file>

# Undo last commit (keep changes)
git reset --soft HEAD~1

# Undo last commit (discard changes)
git reset --hard HEAD~1

# Amend last commit
git add .
git commit --amend --no-edit

# Revert a commit (safe for shared branches)
git revert <commit-hash>
```

### Branch Management

```bash
# List branches
git branch                    # Local branches
git branch -r                 # Remote branches
git branch -a                 # All branches

# Delete branch
git branch -d feature/done    # Safe delete (merged only)
git branch -D feature/done    # Force delete
git push origin --delete feature/done  # Delete remote

# Rename branch
git branch -m old-name new-name

# Clean up deleted remote branches
git fetch --prune
git remote prune origin
```

### Viewing History

```bash
# View commit history
git log
git log --oneline
git log --graph --oneline --all

# View changes
git diff                      # Unstaged changes
git diff --staged             # Staged changes
git diff development          # Compare with development

# View file history
git log -p <file>
git blame <file>

# Find commits
git log --grep="feature"      # Search commit messages
git log --author="John"       # Filter by author
git log --since="2 weeks ago" # Time-based filter
```

### Stashing Changes

```bash
# Stash current changes
git stash
git stash save "work in progress on feature X"

# List stashes
git stash list

# Apply stash
git stash apply               # Keep stash
git stash pop                 # Apply and remove stash

# Drop stash
git stash drop stash@{0}

# Clear all stashes
git stash clear
```

### Rebasing and Merging

```bash
# Rebase current branch on development
git fetch origin
git rebase origin/development

# Interactive rebase (clean up commits)
git rebase -i HEAD~3

# Merge branch
git checkout development
git merge --no-ff feature/my-feature

# Abort rebase
git rebase --abort

# Continue after conflict resolution
git rebase --continue
```

### Resolving Conflicts

```bash
# When conflict occurs
# 1. View conflicted files
git status

# 2. Open files and resolve conflicts
# Look for conflict markers:
# <<<<<<< HEAD
# your changes
# =======
# their changes
# >>>>>>> branch-name

# 3. Mark as resolved
git add <resolved-file>

# 4. Continue
git rebase --continue  # If rebasing
git merge --continue   # If merging

# Or abort
git rebase --abort
git merge --abort
```

### Tags

```bash
# List tags
git tag
git tag -l "v1.*"

# Create tag
git tag v1.0.0
git tag -a v1.0.0 -m "Version 1.0.0"

# Push tags
git push origin v1.0.0
git push origin --tags  # Push all tags

# Delete tag
git tag -d v1.0.0                    # Local
git push origin --delete v1.0.0     # Remote

# Checkout tag
git checkout v1.0.0
```

---

## Best Practices

### General Guidelines

✅ **DO:**

- Commit early and often with meaningful messages
- Keep commits small and focused
- Write clear commit messages following conventions
- Pull before you push
- Test before committing
- Use feature branches for all work
- Keep branches short-lived (< 1 week)
- Delete branches after merging
- Update your branch regularly from development
- Review your own PR before requesting reviews
- Respond to review feedback promptly

❌ **DON'T:**

- Commit directly to main or development
- Force push to shared branches
- Commit incomplete work
- Mix multiple unrelated changes in one commit
- Commit secrets or sensitive data
- Ignore merge conflicts
- Leave branches unmerged for weeks
- Push broken code
- Commit generated files (build artifacts, logs)
- Use `git add .` blindly without reviewing

### Commit Hygiene

```bash
# Review changes before committing
git diff
git add -p  # Interactive staging

# Commit specific files
git add src/specific_file.py tests/test_specific.py
git commit -m "feat: add specific feature"

# Use .gitignore effectively
cat >> .gitignore << EOF
__pycache__/
*.pyc
.env
.venv/
coverage.xml
test-results.xml
*.log
.DS_Store
EOF
```

### Branch Hygiene

```bash
# Keep branches updated
git checkout feature/my-feature
git fetch origin
git rebase origin/development

# Squash commits before merging (if needed)
git rebase -i origin/development

# Clean up merged branches
git branch --merged | grep -v "\*\|main\|development" | xargs -n 1 git branch -d
```

### Collaboration Tips

1. **Communicate:** Let team know about long-running branches
2. **Small PRs:** Keep PRs focused and reviewable (< 400 lines)
3. **Self-review:** Review your own PR first
4. **Link issues:** Reference issues in commits and PRs
5. **Document:** Update docs with code changes
6. **Test:** All PRs must have tests

### Security Considerations

```bash
# Never commit secrets
# Use .env files (add to .gitignore)
echo ".env" >> .gitignore

# If you accidentally commit a secret
git filter-branch --force --index-filter \
  "git rm --cached --ignore-unmatch path/to/secret" \
  --prune-empty --tag-name-filter cat -- --all

# Better: Use tools like git-secrets
# Or BFG Repo-Cleaner for large-scale cleanup
```

---

## Troubleshooting

### Common Issues

#### "Your branch is behind"

```bash
# Solution: Pull changes
git pull origin development
```

#### "Your branch has diverged"

```bash
# Solution 1: Rebase (preferred)
git fetch origin
git rebase origin/development

# Solution 2: Merge
git pull origin development
```

#### "Merge conflict"

```bash
# 1. Identify conflicts
git status

# 2. Open and resolve conflicts
# Edit files, remove conflict markers

# 3. Mark as resolved
git add <file>

# 4. Complete merge/rebase
git rebase --continue
# or
git merge --continue
```

#### "Accidentally committed to wrong branch"

```bash
# Move commits to new branch
git branch feature/correct-branch
git reset --hard origin/development
git checkout feature/correct-branch
```

#### "Need to undo last commit"

```bash
# Keep changes
git reset --soft HEAD~1

# Discard changes
git reset --hard HEAD~1
```

---

## Additional Resources

### Documentation

- [Git Official Documentation](https://git-scm.com/doc)
- [Git Flow Cheatsheet](https://danielkummer.github.io/git-flow-cheatsheet/)
- [Conventional Commits](https://www.conventionalcommits.org/)
- [Semantic Versioning](https://semver.org/)

### Tools

- [GitHub CLI (gh)](https://cli.github.com/)
- [Git Flow Extension](https://github.com/nvie/gitflow)
- [Commitizen](https://github.com/commitizen/cz-cli) - Interactive commit message tool

### Internal Resources

- [Testing Guide](../../tests/TESTING_GUIDE.md)
- [Development Setup](../infrastructure/docker-compose-guide.md)
- [WARP.md](../../../WARP.md) - Project rules and conventions

---

## Questions or Issues?

If you have questions about the Git workflow:

1. Check this guide first
2. Review the [WARP.md](../../../WARP.md) project rules
3. Ask in the team chat
4. Open a discussion on GitHub

---

---

## Document Information

**Category:** Guide
**Created:** 2025-10-03
**Last Updated:** 2025-10-15
**Difficulty Level:** Intermediate
**Target Audience:** Developers, contributors, maintainers
**Prerequisites:** Basic Git knowledge, GitHub account access
