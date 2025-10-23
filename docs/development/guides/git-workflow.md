# Git Workflow Guide

A comprehensive guide to Dashtam's Git Flow branching strategy, semantic versioning, and collaborative development practices.

---

## Table of Contents

- [Overview](#overview)
  - [What You'll Learn](#what-youll-learn)
  - [When to Use This Guide](#when-to-use-this-guide)
- [Prerequisites](#prerequisites)
- [Step-by-Step Instructions](#step-by-step-instructions)
  - [Step 1: Understanding Git Flow Branches](#step-1-understanding-git-flow-branches)
  - [Step 2: Applying Semantic Versioning](#step-2-applying-semantic-versioning)
  - [Step 3: Writing Conventional Commit Messages](#step-3-writing-conventional-commit-messages)
  - [Step 4: Creating Feature and Fix Branches](#step-4-creating-feature-and-fix-branches)
  - [Step 5: Creating and Managing Pull Requests](#step-5-creating-and-managing-pull-requests)
  - [Step 6: Creating Releases](#step-6-creating-releases)
  - [Step 7: Handling Emergency Hotfixes](#step-7-handling-emergency-hotfixes)
- [Examples](#examples)
  - [Example 1: Starting a New Feature](#example-1-starting-a-new-feature)
  - [Example 2: Fixing a Bug](#example-2-fixing-a-bug)
  - [Example 3: Creating a Release](#example-3-creating-a-release)
  - [Example 4: Emergency Hotfix](#example-4-emergency-hotfix)
- [Verification](#verification)
  - [Check 1: Branch Protection is Active](#check-1-branch-protection-is-active)
  - [Check 2: Pull Request Requirements](#check-2-pull-request-requirements)
  - [Check 3: Semantic Versioning Tags](#check-3-semantic-versioning-tags)
- [Troubleshooting](#troubleshooting)
  - [Issue 1: "Your branch is behind"](#issue-1-your-branch-is-behind)
  - [Issue 2: "Your branch has diverged"](#issue-2-your-branch-has-diverged)
  - [Issue 3: "Merge conflict"](#issue-3-merge-conflict)
  - [Issue 4: "Accidentally committed to wrong branch"](#issue-4-accidentally-committed-to-wrong-branch)
  - [Issue 5: "Need to undo last commit"](#issue-5-need-to-undo-last-commit)
- [Best Practices](#best-practices)
  - [General Guidelines](#general-guidelines)
  - [Commit Hygiene](#commit-hygiene)
  - [Branch Hygiene](#branch-hygiene)
  - [Collaboration Tips](#collaboration-tips)
  - [Security Considerations](#security-considerations)
- [Common Mistakes to Avoid](#common-mistakes-to-avoid)
- [Next Steps](#next-steps)
- [References](#references)
  - [Documentation](#documentation)
  - [Tools](#tools)
  - [Internal Resources](#internal-resources)
- [Document Information](#document-information)

---

## Overview

Dashtam uses **Git Flow** as our branching model, which provides a robust framework for managing releases, features, and hotfixes. Combined with **Semantic Versioning** and **Conventional Commits**, this ensures our codebase remains organized, traceable, and production-ready.

### What You'll Learn

- How to use Git Flow branching strategy with `main`, `development`, and supporting branches
- Semantic versioning principles and how to apply them
- Conventional commit message format for automated changelog generation
- Complete workflows for features, fixes, releases, and hotfixes
- Pull request process with branch protection and code review
- Common Git commands and troubleshooting techniques
- Branch protection setup for secure collaborative development

### When to Use This Guide

Use this guide when you need to:

- Start a new feature or bug fix branch
- Create a release or hotfix
- Understand the Git Flow workflow and branching strategy
- Learn proper commit message conventions
- Set up branch protection rules
- Troubleshoot common Git issues
- Review Git command reference for daily operations

## Prerequisites

Before using this Git workflow, ensure you have:

- [ ] Git installed (version 2.23 or higher)
- [ ] GitHub account with repository access
- [ ] GitHub CLI (`gh`) installed (recommended)
- [ ] Basic knowledge of Git commands (clone, commit, push, pull)
- [ ] Understanding of branching concepts
- [ ] Write access to the Dashtam repository

**Required Tools:**

- Git - Version 2.23+ (for `git switch` support)
- GitHub CLI - Latest version recommended
- Text editor or IDE

**Required Knowledge:**

- Familiarity with basic Git operations
- Understanding of pull requests and code review
- Basic command-line skills

## Step-by-Step Instructions

### Step 1: Understanding Git Flow Branches

Dashtam uses Git Flow with a clear branch hierarchy. All development work flows through specific branch types, each with a defined purpose and lifecycle.

**Branch Hierarchy:**

```text
main (production)
  ├── development (integration)
  │   ├── feature/oauth-integration
  │   ├── feature/account-api
  │   └── fix/token-encryption-bug
  ├── release/v1.2.0 (prepared release)
  └── hotfix/v1.1.1 (emergency fix)
```

**Branch Overview:**

| Branch | Purpose | Protected | Lifetime | Deploy Target |
|--------|---------|-----------|----------|---------------|
| `main` | Production-ready code | ✅ Yes | Permanent | Production |
| `development` | Integration branch | ✅ Yes | Permanent | Staging/Dev |
| `feature/*` | New features | ❌ No | Temporary | N/A |
| `fix/*` | Bug fixes | ❌ No | Temporary | N/A |
| `release/*` | Release preparation | ✅ Yes | Temporary | Staging |
| `hotfix/*` | Emergency fixes | ✅ Yes | Temporary | Production |

**Branch Details:**

**1. `main` Branch:**

- **Purpose:** Production-ready code only
- ✅ Always deployable to production
- ✅ Protected (no direct commits)
- ✅ Requires PR with approvals
- ✅ All tests must pass
- ✅ Tagged with version numbers (e.g., `v1.2.0`)
- **Receives merges from:** `release/*` and `hotfix/*` branches

**2. `development` Branch:**

- **Purpose:** Integration branch for ongoing development
- ✅ Protected (no direct commits)
- ✅ Requires PR with approvals
- ✅ All tests must pass
- ✅ Always ahead of `main` (contains unreleased features)
- **Receives merges from:** `feature/*`, `fix/*`, and `hotfix/*` branches

**3. `feature/*` Branches:**

- **Purpose:** Develop new features
- **Naming:** `feature/short-description` (e.g., `feature/account-listing-api`)
- **Lifecycle:** Branch from `development`, merge back to `development`
- Delete after merge

**4. `fix/*` Branches:**

- **Purpose:** Fix bugs in development
- **Naming:** `fix/short-description` (e.g., `fix/token-encryption-error`)
- **Lifecycle:** Same as feature branches

**5. `release/*` Branches:**

- **Purpose:** Prepare a new release
- **Naming:** `release/vX.Y.Z` (e.g., `release/v1.2.0`)
- **Lifecycle:** Branch from `development`, merge to `main` and back to `development`
- Delete after release

**6. `hotfix/*` Branches:**

- **Purpose:** Emergency fixes for production
- **Naming:** `hotfix/vX.Y.Z` or `hotfix/critical-issue`
- **Lifecycle:** Branch from `main`, merge to `main` and `development`
- Delete after hotfix

**What This Does:** Understanding the branch hierarchy ensures all team members follow consistent workflows, preventing conflicts and maintaining code quality across all environments.

### Step 2: Applying Semantic Versioning

Dashtam follows [Semantic Versioning 2.0.0](https://semver.org/) with the format `vMAJOR.MINOR.PATCH`.

**Version Format: `vX.Y.Z`**

- **MAJOR** (X): Breaking changes, incompatible API changes
- **MINOR** (Y): New features, backward-compatible functionality
- **PATCH** (Z): Bug fixes, backward-compatible patches

**Version Examples:**

```text
v1.0.0  → Initial stable release
v1.1.0  → Added account listing API (new feature)
v1.1.1  → Fixed token refresh bug (bug fix)
v1.2.0  → Added transaction endpoints (new feature)
v2.0.0  → Changed OAuth flow (breaking change)
```

**Pre-release Versions:**

For development and testing:

- `v1.2.0-alpha.1` - Alpha release (unstable, internal testing)
- `v1.2.0-beta.1` - Beta release (feature-complete, external testing)
- `v1.2.0-rc.1` - Release candidate (production-ready, final testing)

**When to Increment:**

1. **MAJOR version** when you make incompatible API changes
2. **MINOR version** when you add functionality in a backward-compatible manner
3. **PATCH version** when you make backward-compatible bug fixes

**What This Does:** Semantic versioning provides clear communication about the scope of changes in each release, allowing users and developers to understand compatibility and impact at a glance.

### Step 3: Writing Conventional Commit Messages

We use **Conventional Commits** for automated changelog generation and semantic versioning.

**Commit Format:**

```text
<type>(<scope>): <subject>

<body>

<footer>
```

**Commit Types:**

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

**Breaking Changes:**

Use `BREAKING CHANGE:` in footer or `!` after type:

```bash
# Method 1: Footer
feat(api)!: change authentication endpoint structure

BREAKING CHANGE: Auth endpoint moved from /auth to /api/v1/auth

# Method 2: Exclamation mark
feat!: redesign OAuth flow
```

**Commit Examples:**

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
```

**Commit Message Rules:**

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

**What This Does:** Conventional commits enable automated changelog generation, simplify code review, and provide clear history for debugging and understanding project evolution.

### Step 4: Creating Feature and Fix Branches

Create feature branches for new functionality and fix branches for bug fixes.

**Creating a Feature Branch:**

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

# 5. Keep branch updated with development
git fetch origin
git rebase origin/development

# 6. Push to remote
git push -u origin feature/transaction-api
```

**Creating a Fix Branch:**

```bash
# 1. Create fix branch from development
git checkout development
git pull origin development
git checkout -b fix/token-refresh-error

# 2. Fix the bug and add tests
git add src/services/token_service.py tests/test_token_service.py
git commit -m "fix(auth): prevent race condition in token refresh"

# 3. Push and prepare for PR
git push -u origin fix/token-refresh-error
```

**Important Notes:**

- ⚠️ Always branch from `development`, not `main`
- ⚠️ Keep branches short-lived (complete within 1 week)
- ⚠️ Update your branch regularly with `git rebase origin/development`
- ℹ️ Use descriptive branch names that explain the work

**What This Does:** Isolating work in dedicated branches prevents conflicts, enables parallel development, and makes code review manageable.

### Step 5: Creating and Managing Pull Requests

Pull requests are the gateway to merging code into protected branches.

**Creating a Pull Request:**

1. **Push your branch** to GitHub:

   ```bash
   git push -u origin feature/your-feature
   ```

2. **Create PR on GitHub** (via web UI):
   - Navigate to repository
   - Click "Pull requests" → "New pull request"
   - Select base branch (`development` for features/fixes)
   - Select your feature branch
   - Click "Create pull request"

3. **Or use GitHub CLI** (recommended):

   ```bash
   # Interactive PR creation
   gh pr create

   # Create PR with details
   gh pr create \
     --base development \
     --title "feat(api): Add transaction filtering API" \
     --body "Detailed description..."

   # Create draft PR for work in progress
   gh pr create --base development --draft --title "WIP: New feature"
   ```

**PR Description Template:**

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

## Checklist
- [x] Code follows project style guidelines
- [x] Self-review completed
- [x] Comments added for complex logic
- [x] Documentation updated
- [x] No new warnings generated
- [x] Tests added/updated
- [x] All tests passing
```

**Addressing Review Feedback:**

```bash
# Make requested changes
git add .
git commit -m "refactor: address PR feedback on error handling"

# Push updates (PR automatically updates)
git push origin feature/your-feature
```

**Merging Pull Requests:**

```bash
# After approval and checks pass
gh pr merge 16 --squash --delete-branch

# Merge options:
# --squash   : Squash all commits (recommended for most PRs)
# --merge    : Create merge commit (preserves feature history)
# --rebase   : Rebase and merge (linear history)
# --admin    : Bypass branch protection (admin only)
```

**What This Does:** The PR process ensures code review, automated testing, and team collaboration before changes reach production.

### Step 6: Creating Releases

Releases prepare stable versions for production deployment.

**Release Workflow:**

```bash
# 1. Ensure development is stable
make test  # All tests pass
make lint  # No linting errors

# 2. Create release branch
git checkout development
git pull origin development
git checkout -b release/v1.4.0

# 3. Update version numbers
# Edit: pyproject.toml, src/__init__.py, docs/conf.py

# 4. Update CHANGELOG.md
git add .
git commit -m "chore: bump version to 1.4.0"
git commit -m "docs: update changelog for v1.4.0"

# 5. Final testing
make test
make lint

# 6. Push release branch
git push -u origin release/v1.4.0

# 7. Create PR to main, get approval and merge

# 8. After merge, tag release on main
git checkout main
git pull origin main
git tag -a v1.4.0 -m "Release version 1.4.0"
git push origin v1.4.0

# 9. Merge back to development
git checkout development
git merge --no-ff main
git push origin development

# 10. Cleanup
git branch -d release/v1.4.0
git push origin --delete release/v1.4.0
```

**CHANGELOG Format:**

```text
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
```

**What This Does:** The release process creates a stable checkpoint, documents changes, and enables controlled production deployments.

### Step 7: Handling Emergency Hotfixes

Hotfixes address critical production issues requiring immediate deployment.

**When to Create a Hotfix:**

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

**Hotfix Workflow:**

```bash
# 1. Create hotfix from main (production)
git checkout main
git pull origin main
git checkout -b hotfix/v1.3.1

# 2. Fix the issue QUICKLY (focus on specific problem)
git add src/ tests/
git commit -m "fix(critical): resolve database connection timeout"

# 3. Update version (patch increment: v1.3.0 → v1.3.1)
git commit -m "chore: bump version to 1.3.1"

# 4. Update CHANGELOG
git add CHANGELOG.md
git commit -m "docs: add hotfix v1.3.1 to changelog"

# 5. Test thoroughly
make test
make lint

# 6. Create PR to main (expedited review)
# Title: "HOTFIX v1.3.1: Critical database timeout"

# 7. After approval and merge, tag immediately
git checkout main
git pull origin main
git tag -a v1.3.1 -m "Hotfix v1.3.1: Database connection timeout"
git push origin main v1.3.1

# 8. Merge to development
git checkout development
git pull origin development
git merge --no-ff main
git push origin development

# 9. Cleanup
git branch -d hotfix/v1.3.1
git push origin --delete hotfix/v1.3.1

# 10. Deploy to production ASAP
```

**Important Notes:**

- ⚠️ **Speed is critical** - Focus only on the specific issue
- ⚠️ **No refactoring** - Don't add features or improve code
- ⚠️ **Test thoroughly** - Despite urgency, ensure fix is correct
- ℹ️ **Communicate** - Alert team about hotfix in progress

**What This Does:** The hotfix process enables rapid response to production issues while maintaining code quality and change tracking.

## Examples

### Example 1: Starting a New Feature

**Scenario:** You need to build a new transaction listing API with filtering capabilities.

```bash
# 1. Ensure you're up to date
git checkout development
git pull origin development

# 2. Create feature branch
git checkout -b feature/transaction-api

# 3. Work on the feature incrementally
# Edit files, write tests

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
gh pr create --base development \
  --title "feat(api): Add transaction listing and filtering API" \
  --body "Full PR description..."

# 8. Address review feedback
git add .
git commit -m "refactor(api): address PR feedback on validation"
git push origin feature/transaction-api

# 9. After PR is merged
git checkout development
git pull origin development
git branch -d feature/transaction-api
```

**Result:** Feature successfully developed, reviewed, tested, and merged into development.

### Example 2: Fixing a Bug

**Scenario:** There's a race condition in token refresh causing intermittent authentication failures.

```bash
# 1. Create fix branch from development
git checkout development
git pull origin development
git checkout -b fix/token-refresh-error

# 2. Investigate and fix the bug
# Debug, identify root cause, implement fix

# 3. Add tests to prevent regression
# Write unit tests that expose the race condition

# 4. Commit the fix
git add src/services/token_service.py tests/test_token_service.py
git commit -m "fix(auth): prevent race condition in token refresh"

# 5. Push and create PR
git push -u origin fix/token-refresh-error
gh pr create --base development \
  --title "fix(auth): Prevent race condition in token refresh" \
  --body "Fixes #123..."

# 6. After merge, cleanup
git checkout development
git pull origin development
git branch -d fix/token-refresh-error
```

**Result:** Bug fixed with regression tests, merged to development, will be included in next release.

### Example 3: Creating a Release

**Scenario:** Development branch has accumulated enough features and fixes for version 1.3.0 release.

```bash
# 1. Create release branch from development
git checkout development
git pull origin development
git checkout -b release/v1.3.0

# 2. Update version numbers
# Edit: pyproject.toml, __version__.py, etc.
git add .
git commit -m "chore: bump version to 1.3.0"

# 3. Update CHANGELOG.md with release notes
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

**Result:** Version 1.3.0 tagged on main, deployed to production, changes merged back to development.

### Example 4: Emergency Hotfix

**Scenario:** Production is leaking API keys in error logs - critical security issue requiring immediate fix.

```bash
# 1. Create hotfix from main (production code)
git checkout main
git pull origin main
git checkout -b hotfix/v1.2.1

# 2. Fix the critical issue QUICKLY
git add src/core/security.py
git commit -m "fix(security): prevent API key exposure in logs"

# 3. Update version (patch increment)
git commit -m "chore: bump version to 1.2.1"

# 4. Update CHANGELOG
git add CHANGELOG.md
git commit -m "docs: add hotfix v1.2.1 to changelog"

# 5. Test fix thoroughly
make test
make lint

# 6. Create expedited PR to main
gh pr create --base main \
  --title "HOTFIX v1.2.1: Security patch for API key exposure" \
  --body "Critical security fix..." \
  --label "hotfix,security"

# 7. After approval, merge to main
git checkout main
git merge --no-ff hotfix/v1.2.1
git tag -a v1.2.1 -m "Hotfix v1.2.1: Security patch for API key exposure"
git push origin main --tags

# 8. Merge to development
git checkout development
git merge --no-ff hotfix/v1.2.1
git push origin development

# 9. Cleanup
git branch -d hotfix/v1.2.1
git push origin --delete hotfix/v1.2.1

# 10. Immediate production deployment
```

**Result:** Critical security vulnerability patched, deployed to production within hours, changes propagated to development.

## Verification

How to verify your Git workflow is properly configured and functioning.

### Check 1: Branch Protection is Active

**Verify branch protection rules are enforced:**

```bash
# Check protection status for main
gh api repos/faiyaz7283/Dashtam/branches/main/protection \
  | jq '.required_pull_request_reviews.required_approving_review_count'

# Expected: 1 (requires 1 approval)

# Check required status checks
gh api repos/faiyaz7283/Dashtam/branches/main/protection \
  | jq '.required_status_checks.contexts'

# Expected: ["Test Suite / Run Tests", "Code Quality / lint"]
```

**Expected Result:** Branch protection is active with required approvals and status checks.

### Check 2: Pull Request Requirements

**Verify PR meets merge requirements:**

```bash
# Check PR mergeable status
gh pr view 16 --json mergeable,mergeStateStatus

# Expected output:
{
  "mergeable": "MERGEABLE",
  "mergeStateStatus": "CLEAN"  # Ready to merge
}

# Possible states:
# - CLEAN: Ready to merge
# - BLOCKED: Missing approvals or failing checks
# - BEHIND: Branch needs update
# - UNSTABLE: Checks failing
```

**Expected Result:** PR shows "CLEAN" status when all requirements are met.

### Check 3: Semantic Versioning Tags

**Verify tags follow semantic versioning:**

```bash
# List recent tags
git tag -l "v*" | tail -10

# Expected format: v1.2.3, v2.0.0, v1.4.0-beta.1

# Check tag exists on main
git checkout main
git pull origin main
git describe --tags

# Expected: v1.2.0 or similar semantic version
```

**Expected Result:** All version tags follow `vMAJOR.MINOR.PATCH` format and exist on main branch.

## Troubleshooting

### Issue 1: "Your branch is behind"

**Symptoms:**

- Git warns branch is behind remote
- Push is rejected

**Cause:** Remote branch has commits your local branch doesn't have.

**Solution:**

```bash
# Pull changes from remote
git pull origin development

# If you have local commits, use rebase
git pull --rebase origin development
```

### Issue 2: "Your branch has diverged"

**Symptoms:**

- Local and remote branches have different commits
- Cannot push or pull cleanly

**Cause:** Both local and remote have commits the other doesn't have.

**Solution:**

```bash
# Solution 1: Rebase (preferred - creates linear history)
git fetch origin
git rebase origin/development

# Solution 2: Merge (creates merge commit)
git pull origin development

# After resolving, push with force-with-lease (safer than --force)
git push --force-with-lease origin feature/your-branch
```

### Issue 3: "Merge conflict"

**Symptoms:**

- Git reports conflicts during merge/rebase
- Files contain conflict markers (`<<<<<<<`, `=======`, `>>>>>>>`)

**Cause:** Same lines were changed differently in both branches.

**Solution:**

```bash
# 1. Identify conflicted files
git status

# 2. Open files and resolve conflicts
# Look for conflict markers:
# <<<<<<< HEAD
# your changes
# =======
# their changes
# >>>>>>> branch-name

# 3. Edit files to keep desired changes, remove markers

# 4. Mark as resolved
git add <resolved-file>

# 5. Complete merge/rebase
git rebase --continue  # If rebasing
git merge --continue   # If merging

# Or abort if needed
git rebase --abort
git merge --abort
```

### Issue 4: "Accidentally committed to wrong branch"

**Symptoms:**

- Commits made directly to `main` or `development`
- Commits on wrong feature branch

**Cause:** Forgot to create/switch to correct branch before committing.

**Solution:**

```bash
# Move commits to new branch
git branch feature/correct-branch  # Create branch with current commits
git reset --hard origin/development  # Reset current branch
git checkout feature/correct-branch  # Switch to correct branch

# Commits are now on correct branch
```

### Issue 5: "Need to undo last commit"

**Symptoms:**

- Committed wrong changes
- Need to modify last commit

**Cause:** Premature commit or mistake in committed changes.

**Solution:**

```bash
# Keep changes but undo commit (can re-commit)
git reset --soft HEAD~1

# Discard changes and undo commit (permanent)
git reset --hard HEAD~1

# Amend last commit (add more changes or fix message)
git add .
git commit --amend --no-edit  # Keep message
git commit --amend -m "New message"  # Change message
```

## Best Practices

Follow these best practices for optimal Git workflow results.

### General Guidelines

✅ **DO:**

- Commit early and often with meaningful messages
- Keep commits small and focused on single concerns
- Write clear commit messages following Conventional Commits
- Pull before you push to avoid conflicts
- Test locally before committing (run tests and linting)
- Use feature branches for all work (never commit to main/development)
- Keep branches short-lived (complete within 1 week)
- Delete branches after merging to keep repository clean
- Update your branch regularly from development
- Review your own PR before requesting team reviews
- Respond to review feedback promptly

❌ **DON'T:**

- Commit directly to main or development (always use PRs)
- Force push to shared branches (use `--force-with-lease` if needed)
- Commit incomplete work to shared branches
- Mix multiple unrelated changes in one commit
- Commit secrets or sensitive data (use .gitignore)
- Ignore merge conflicts (resolve them properly)
- Leave branches unmerged for weeks
- Push broken code (test first)
- Commit generated files (build artifacts, logs, **pycache**)
- Use `git add .` blindly without reviewing changes

### Commit Hygiene

**Review changes before committing:**

```bash
# See what changed
git diff

# Interactive staging (review each change)
git add -p

# Commit specific files only
git add src/specific_file.py tests/test_specific.py
git commit -m "feat: add specific feature"
```

**Use .gitignore effectively:**

```bash
# Add common patterns to .gitignore
cat >> .gitignore << EOF
**pycache**/
*.pyc
.env
.venv/
coverage.xml
test-results.xml
*.log
.DS_Store
node_modules/
dist/
build/
EOF
```

### Branch Hygiene

**Keep branches updated:**

```bash
# Regularly update your feature branch
git checkout feature/my-feature
git fetch origin
git rebase origin/development

# Squash commits before merging (if needed)
git rebase -i origin/development

# Clean up merged branches locally
git branch --merged | grep -v "\*\|main\|development" | xargs -n 1 git branch -d

# Clean up deleted remote branches
git fetch --prune
```

### Collaboration Tips

1. **Communicate:** Let team know about long-running branches or blockers
2. **Small PRs:** Keep PRs focused and reviewable (< 400 lines changed)
3. **Self-review:** Review your own PR first, check diff thoroughly
4. **Link issues:** Reference issues in commits (`Closes #42`) and PRs
5. **Document:** Update documentation with code changes
6. **Test:** All PRs must have tests - no exceptions

### Security Considerations

**Never commit secrets:**

```bash
# Ensure .env files are ignored
echo ".env" >> .gitignore
echo ".env.*" >> .gitignore

# If you accidentally commit a secret
git filter-branch --force --index-filter \
  "git rm --cached --ignore-unmatch path/to/secret" \
  --prune-empty --tag-name-filter cat -- --all

# Better: Use tools like git-secrets or pre-commit hooks
```

## Common Mistakes to Avoid

- ❌ **Forgetting to switch branches** - Always check `git branch` before committing
- ❌ **Not testing before pushing** - Run `make test` and `make lint` first
- ❌ **Vague commit messages** - Be specific: "Fix OAuth token refresh race condition" not "Fix bug"
- ❌ **Committing merge conflicts** - Resolve conflicts completely, remove all markers
- ❌ **Force pushing to shared branches** - Use `--force-with-lease` and only on your own branches

## Next Steps

After mastering this Git workflow, consider:

- [ ] Set up Git aliases for common commands (e.g., `git co` for checkout)
- [ ] Configure Git hooks for automated linting and testing
- [ ] Learn interactive rebase (`git rebase -i`) for cleaning commit history
- [ ] Explore Git bisect for finding commits that introduced bugs
- [ ] Set up GPG signing for verified commits
- [ ] Review [Git Quick Reference](git-quick-reference.md) for command cheat sheet
- [ ] Study the [Testing Guide](../../development/guides/testing-guide.md) for test workflow
- [ ] Read [WARP.md](../../../WARP.md) for complete project rules

## References

### Documentation

- [Git Official Documentation](https://git-scm.com/doc) - Complete Git reference
- [Git Flow Cheatsheet](https://danielkummer.github.io/git-flow-cheatsheet/) - Visual workflow guide
- [Conventional Commits](https://www.conventionalcommits.org/) - Commit message specification
- [Semantic Versioning](https://semver.org/) - Versioning specification

### Tools

- [GitHub CLI (gh)](https://cli.github.com/) - Command-line GitHub operations
- [Git Flow Extension](https://github.com/nvie/gitflow) - Git Flow commands
- [Commitizen](https://github.com/commitizen/cz-cli) - Interactive commit message tool

### Internal Resources

- [Git Quick Reference](git-quick-reference.md) - One-page command cheat sheet
- [Testing Guide](../../development/guides/testing-guide.md) - Test workflow and strategies
- [Development Setup](../infrastructure/docker-compose-guide.md) - Docker environment setup
- [WARP.md](../../../WARP.md) - Project rules and conventions

---

## Document Information

**Template:** [guide-template.md](../../templates/guide-template.md)
**Created:** 2025-10-03
**Last Updated:** 2025-10-20
