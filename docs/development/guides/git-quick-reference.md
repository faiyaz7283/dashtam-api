# Git Quick Reference - Dashtam

## Table of Contents

- [🌳 Branch Overview](#-branch-overview)
- [🚀 Daily Workflow](#-daily-workflow)
  - [Start New Feature](#start-new-feature)
  - [Make Changes](#make-changes)
  - [Finish Feature](#finish-feature)
- [🐛 Bug Fix Workflow](#-bug-fix-workflow)
- [📦 Release Workflow](#-release-workflow)
  - [Start Release](#start-release)
  - [Finish Release (after PR merged)](#finish-release-after-pr-merged)
- [🚨 Hotfix Workflow](#-hotfix-workflow)
  - [Start Hotfix](#start-hotfix)
  - [Finish Hotfix (after PR merged)](#finish-hotfix-after-pr-merged)
- [📝 Commit Message Format](#-commit-message-format)
  - [Types](#types)
  - [Examples](#examples)
  - [Breaking Changes](#breaking-changes)
- [🛠️ Make Commands](#️-make-commands)
  - [Git Flow](#git-flow)
  - [Testing & Quality](#testing--quality)
- [🔄 Common Git Commands](#-common-git-commands)
  - [Sync & Update](#sync--update)
  - [Status & History](#status--history)
  - [Stashing](#stashing)
  - [Branch Management](#branch-management)
  - [Undoing Changes](#undoing-changes)
- [🔒 Branch Protection Requirements](#-branch-protection-requirements)
- [🔄 GitHub CLI PR Management](#-github-cli-pr-management)
  - [Creating Pull Requests](#creating-pull-requests)
  - [Viewing PRs](#viewing-prs)
  - [Reviewing PRs](#reviewing-prs)
  - [Merging PRs](#merging-prs)
- [📋 Pull Request Checklist](#-pull-request-checklist)
- [🎯 Semantic Versioning](#-semantic-versioning)
- [🚦 Workflow Decision Tree](#-workflow-decision-tree)
- [⚠️ Important Rules](#️-important-rules)
- [🆘 Emergency Procedures](#-emergency-procedures)
  - [Revert Last Commit (not pushed)](#revert-last-commit-not-pushed)
  - [Revert Pushed Commit (safe)](#revert-pushed-commit-safe)
  - [Accidentally Committed to Wrong Branch](#accidentally-committed-to-wrong-branch)
  - [Merge Conflict](#merge-conflict)
- [📚 Resources](#-resources)
- [💡 Pro Tips](#-pro-tips)

**One-page cheat sheet for common Git Flow operations:**

---

## 🌳 Branch Overview

```text
main (production)               ← v1.2.0, v1.1.1 (tags)
  ├── development (integration) ← default branch
  │   ├── feature/my-feature
  │   └── fix/my-bug-fix
  ├── release/v1.2.0            ← preparing release
  └── hotfix/v1.1.1             ← emergency fix
```

---

## 🚀 Daily Workflow

### Start New Feature

```bash
make git-feature
# Or manually:
git checkout development
git pull origin development
git checkout -b feature/feature-name
```

### Make Changes

```bash
# Make your changes
git add .
git commit -m "feat(scope): description"
```

### Finish Feature

```bash
make git-finish
# This will:
# 1. Run all tests
# 2. Run linting
# 3. Push to remote
# 4. Show PR creation link
```

---

## 🐛 Bug Fix Workflow

```bash
make git-fix                              # Create fix branch
# Make fixes
git commit -m "fix(scope): description"   # Commit
make git-finish                           # Push & create PR
```

---

## 📦 Release Workflow

### Start Release

```bash
make git-release-start                    # Enter version: 1.2.0
# Update pyproject.toml
# Update CHANGELOG.md
git commit -m "chore: bump version to 1.2.0"
git commit -m "docs: update changelog for v1.2.0"
make test                                 # Final testing
git push -u origin release/v1.2.0
# Create PR to main
```

### Finish Release (after PR merged)

```bash
make git-release-finish VERSION=1.2.0
# This will:
# 1. Tag v1.2.0 on main
# 2. Merge back to development
# 3. Clean up release branch
```

---

## 🚨 Hotfix Workflow

### Start Hotfix

```bash
make git-hotfix-start                     # Enter version: 1.1.1
# Fix critical issue ONLY
git commit -m "fix(critical): description"
# Update version and CHANGELOG
make test                                 # Test thoroughly
git push -u origin hotfix/v1.1.1
# Create URGENT PR to main
```

### Finish Hotfix (after PR merged)

```bash
make git-hotfix-finish VERSION=1.1.1
# Deploy immediately!
```

---

## 📝 Commit Message Format

```text
<type>(<scope>): <subject>

<body>

<footer>
```

### Types

- `feat:` New feature (minor version bump)
- `fix:` Bug fix (patch version bump)
- `docs:` Documentation only
- `test:` Tests
- `refactor:` Code refactoring
- `chore:` Maintenance
- `perf:` Performance
- `ci:` CI/CD changes

### Examples

```bash
feat(api): add account listing endpoint
fix(auth): prevent race condition in token refresh
docs: update API documentation
test(integration): add OAuth flow tests
chore(deps): update FastAPI to 0.110.0
```

### Breaking Changes

```bash
feat(api)!: change authentication structure

BREAKING CHANGE: Auth endpoint moved to /api/v1/auth
```

---

## 🛠️ Make Commands

### Git Flow

```bash
make git-status                        # Show Git status
make git-sync                          # Sync with development
make git-feature                       # Create feature branch
make git-fix                           # Create fix branch
make git-finish                        # Finish & push branch
make git-release-start                 # Start release
make git-release-finish VERSION=X.Y.Z
make git-hotfix-start                  # Start hotfix
make git-hotfix-finish VERSION=X.Y.Z
make git-cleanup                       # Clean merged branches
make git-branch-protection            # Setup branch protection
```

### Testing & Quality

```bash
make test                # All tests with coverage
make test-unit           # Unit tests only
make test-integration    # Integration tests only
make lint                # Run linting
make format              # Format code
```

---

## 🔄 Common Git Commands

### Sync & Update

```bash
git fetch origin                          # Fetch updates
git pull origin development               # Pull development
git rebase origin/development             # Rebase on development
```

### Status & History

```bash
git status                                # Current status
git log --oneline --graph -10             # Recent commits
git diff                                  # Unstaged changes
git diff --staged                         # Staged changes
```

### Stashing

```bash
git stash                                 # Stash changes
git stash list                            # List stashes
git stash pop                             # Apply & remove stash
```

### Branch Management

```bash
git branch                                # List local branches
git branch -a                             # List all branches
git branch -d feature/name                # Delete local branch
git push origin --delete feature/name     # Delete remote branch
```

### Undoing Changes

```bash
git checkout -- file.py                   # Discard file changes
git reset HEAD file.py                    # Unstage file
git reset --soft HEAD~1                   # Undo commit (keep changes)
git reset --hard HEAD~1                   # Undo commit (discard changes)
git revert <commit-hash>                  # Safe revert (creates new commit)
```

---

## 🔒 Branch Protection Requirements

**Both `main` and `development` are protected:**

✅ Required status checks:

- `Test Suite / Run Tests` must pass
- `Code Quality / lint` must pass

✅ Pull request requirements:

- At least 1 approval required
- All conversations must be resolved
- Branch must be up to date

✅ Restrictions:

- No direct commits
- No force pushes
- No branch deletion

---

## 🔄 GitHub CLI PR Management

### Creating Pull Requests

```bash
# Interactive PR creation
gh pr create

# Quick PR creation inline
gh pr create --base development --title "feat: my feature" --body "Description"

# Quick PR creation temporary file
gh pr create --base development --title "feat: my feature" --body-file /tmp/pr_description.md

# With reviewers and labels
gh pr create --base development --reviewer user1 --label enhancement

# Draft PR
gh pr create --base development --draft --title "WIP: my feature"
```

### Viewing PRs

```bash
# View PR in browser
gh pr view 16 --web

# View PR details
gh pr view 16

# Check PR status
gh pr view 16 --json mergeable,mergeStateStatus

# List all open PRs
gh pr list
```

### Reviewing PRs

```bash
# Approve PR
gh pr review 16 --approve --body "LGTM!"

# Request changes
gh pr review 16 --request-changes --body "Please fix X"

# Comment only
gh pr review 16 --comment --body "Minor suggestion"
```

### Merging PRs

```bash
# Squash merge (recommended)
gh pr merge 16 --squash --delete-branch

# Merge commit (preserve history)
gh pr merge 16 --merge --delete-branch

# Rebase merge
gh pr merge 16 --rebase --delete-branch

# Admin merge (bypass protection)
gh pr merge 16 --squash --delete-branch --admin

# Auto-merge when checks pass
gh pr merge 16 --squash --auto --delete-branch
```

**Merge Options:**

- `--squash` - Combine all commits into one (clean history)
- `--merge` - Create merge commit (preserve feature commits)
- `--rebase` - Linear history
- `--delete-branch` - Auto-delete branch after merge ✅
- `--admin` - Bypass branch protection rules
- `--auto` - Merge automatically when checks pass

**Merge State Status:**

- `CLEAN` ✅ Ready to merge
- `BLOCKED` ❌ Missing approvals or failing checks
- `BEHIND` ⚠️ Branch needs update
- `UNSTABLE` ⚠️ Checks failing
- `DRAFT` 📝 PR is draft

---

## 📋 Pull Request Checklist

Before creating PR:

- [ ] All tests pass (`make test`)
- [ ] Linting passes (`make lint`)
- [ ] Code is formatted (`make format`)
- [ ] Documentation updated
- [ ] Commit messages follow conventions
- [ ] Branch is up to date with development

PR Description Template:

```markdown
## Description
[Brief description]

## Type of Change
- [ ] New feature
- [ ] Bug fix
- [ ] Breaking change
- [ ] Documentation

## Testing
- [ ] Unit tests pass
- [ ] Integration tests pass
- [ ] All tests pass (`make test`)
- [ ] Linting passes (`make lint`)

## Related Issues
Closes #XX
```

---

## 🎯 Semantic Versioning

```text
vMAJOR.MINOR.PATCH

v1.2.3
│ │ │
│ │ └─ Patch: Bug fixes (backwards compatible)
│ └─── Minor: New features (backwards compatible)
└───── Major: Breaking changes (not backwards compatible)
```

**Examples:**

- `v1.0.0` → Initial release
- `v1.1.0` → New feature added
- `v1.1.1` → Bug fix
- `v2.0.0` → Breaking change

---

## 🚦 Workflow Decision Tree

```text
Need to work on something?
│
├─ New feature? → make git-feature
├─ Bug fix? → make git-fix
├─ Ready to release? → make git-release-start
└─ Production is broken? → make git-hotfix-start

Work complete?
│
├─ Feature/Fix done? → make git-finish → Create PR → Merge
├─ Release ready? → make git-release-finish VERSION=X.Y.Z
└─ Hotfix deployed? → make git-hotfix-finish VERSION=X.Y.Z
```

---

## ⚠️ Important Rules

❌ **NEVER:**

- Commit directly to `main` or `development`
- Force push to shared branches
- Commit secrets or sensitive data
- Mix multiple unrelated changes in one commit
- Skip running tests before pushing

✅ **ALWAYS:**

- Create feature/fix branch for changes
- Write meaningful commit messages
- Run tests before pushing (`make test`)
- Run linting before pushing (`make lint`)
- Keep branches short-lived (< 1 week)
- Delete branches after merging
- Update documentation with code changes

---

## 🆘 Emergency Procedures

### Revert Last Commit (not pushed)

```bash
git reset --soft HEAD~1        # Keep changes
git reset --hard HEAD~1        # Discard changes
```

### Revert Pushed Commit (safe)

```bash
git revert <commit-hash>       # Creates new commit
git push origin <branch>
```

### Accidentally Committed to Wrong Branch

```bash
git branch feature/correct-branch    # Create branch with current commits
git reset --hard origin/development  # Reset current branch
git checkout feature/correct-branch  # Switch to correct branch
```

### Merge Conflict

```bash
git status                     # See conflicted files
# Edit files, resolve conflicts (remove markers)
git add <resolved-files>
git rebase --continue          # If rebasing
# or
git merge --continue           # If merging
```

---

## 📚 Resources

- **Full Guide:** [Git Workflow Guide](./git-workflow.md)
- **Project Rules:** [WARP.md](../../../WARP.md)
- **Conventional Commits:** https://www.conventionalcommits.org/
- **Semantic Versioning:** https://semver.org/
- **Git Flow:** https://danielkummer.github.io/git-flow-cheatsheet/

---

## 💡 Pro Tips

1. **Use make commands** - They include safeguards and run tests automatically
2. **Commit often** - Small, focused commits are easier to review and revert
3. **Pull before push** - Always sync with development before pushing
4. **Review your own PR** - Check the diff on GitHub before requesting reviews
5. **Keep branches current** - Regularly rebase on development to avoid conflicts
6. **Clean up regularly** - Run `make git-cleanup` to remove merged branches
7. **Use descriptive branch names** - `feature/account-api` not `feature/stuff`
8. **Write good commit messages** - Future you will thank current you

---

---

## Document Information

**Category:** Guide
**Created:** 2025-10-03
**Last Updated:** 2025-10-15
**Difficulty Level:** Beginner
**Target Audience:** Developers, new contributors, anyone needing quick Git reference
**Prerequisites:** Basic command line knowledge
**Related Documents:** [Git Workflow Guide](git-workflow.md)
