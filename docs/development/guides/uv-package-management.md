# Modern UV Package Management Guide

A comprehensive guide for using UV (version 0.8.22+) as the modern Python package manager in Dashtam, covering installation, workflows, Docker integration, and best practices.

---

## Table of Contents

- [Overview](#overview)
  - [What You'll Learn](#what-youll-learn)
  - [When to Use This Guide](#when-to-use-this-guide)
  - [Why UV](#why-uv)
  - [Core Concepts](#core-concepts)
- [Prerequisites](#prerequisites)
- [Step-by-Step Instructions](#step-by-step-instructions)
  - [Step 1: Install UV](#step-1-install-uv)
  - [Step 2: Initialize Project](#step-2-initialize-project)
  - [Step 3: Manage Dependencies](#step-3-manage-dependencies)
  - [Step 4: Sync Environment](#step-4-sync-environment)
  - [Step 5: Run Commands](#step-5-run-commands)
  - [Step 6: Integrate with Docker](#step-6-integrate-with-docker)
- [Examples](#examples)
  - [Example 1: Adding New Dependency in Dashtam](#example-1-adding-new-dependency-in-dashtam)
  - [Example 2: After Pulling Changes](#example-2-after-pulling-changes)
  - [Example 3: Upgrading Dependencies](#example-3-upgrading-dependencies)
  - [Example 4: Docker Multi-Stage Build](#example-4-docker-multi-stage-build)
  - [Example 5: Migration from pip](#example-5-migration-from-pip)
- [Verification](#verification)
  - [Check 1: UV Installation](#check-1-uv-installation)
  - [Check 2: Dependencies Installed](#check-2-dependencies-installed)
  - [Check 3: Environment Synced](#check-3-environment-synced)
- [Troubleshooting](#troubleshooting)
  - [Issue 1: No module named package](#issue-1-no-module-named-package)
  - [Issue 2: uv command not found](#issue-2-uv-command-not-found)
  - [Issue 3: Environment Out of Sync](#issue-3-environment-out-of-sync)
  - [Issue 4: Dependency Conflicts](#issue-4-dependency-conflicts)
- [Best Practices](#best-practices)
  - [Command Usage](#command-usage)
  - [Version Control](#version-control)
  - [Docker Integration](#docker-integration)
  - [Performance Optimization](#performance-optimization)
  - [Common Mistakes to Avoid](#common-mistakes-to-avoid)
  - [Quick Command Cheat Sheet](#quick-command-cheat-sheet)
- [Next Steps](#next-steps)
- [References](#references)
- [Document Information](#document-information)

---

## Overview

UV is an extremely fast Python package manager and resolver, written in Rust. It's designed as a drop-in replacement for pip, pip-tools, poetry, and other Python package management tools.

### What You'll Learn

- How to install and configure UV in Docker and on host machines
- Modern Python dependency management with UV project mode
- Adding, removing, and upgrading dependencies
- Syncing environments after pulling changes
- Docker integration with official UV images
- Migrating from pip or poetry to UV
- Troubleshooting common UV issues

### When to Use This Guide

Use this guide when:

- Setting up Dashtam development environment
- Adding new Python dependencies to the project
- Updating existing dependencies
- Troubleshooting dependency installation issues
- Migrating from pip or poetry
- Optimizing Docker builds with UV

### Why UV

- **10-100x faster** than pip for package installation
- **Deterministic resolution** with lockfiles (reproducible builds)
- **Modern Python workflow** following PEP 621 standards
- **Docker-optimized** with official container images
- **Universal resolver** handles complex dependency scenarios
- **No separate tools needed** (replaces pip, poetry, pipenv)

### Core Concepts

UV distinguishes between two modes:

**Project Management Mode** (Modern - Dashtam uses this):

- Uses `uv add`, `uv sync`, `uv lock` commands
- Manages dependencies in `pyproject.toml` and `uv.lock`
- Creates and manages virtual environments automatically
- For applications with modern Python project structure

**Package Management Mode** (Legacy):

- Uses `uv pip` commands (pip-compatible interface)
- For one-off package installations
- Compatible with `requirements.txt`
- Use only when absolutely necessary for legacy compatibility

## Prerequisites

Before using this guide, ensure you have:

- [ ] Docker Desktop installed (for containerized development)
- [ ] Basic understanding of Python package management
- [ ] Access to Dashtam repository
- [ ] Terminal access to development environment

**Required Tools:**

- Docker Desktop - Latest version (for containerized UV)
- Python 3.13 - Required version for Dashtam
- UV 0.8.22+ - Latest version recommended

**Required Knowledge:**

- Basic command line usage
- Understanding of Python virtual environments
- Familiarity with dependency management concepts
- Basic Docker commands

## Step-by-Step Instructions

### Step 1: Install UV

Choose installation method based on your environment.

**In Docker (Recommended for Dashtam):**

```dockerfile
# Use official UV image with Python 3.13
FROM ghcr.io/astral-sh/uv:0.8.22-python3.13-trixie-slim AS base

# Set UV environment variables
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    PATH="/app/.venv/bin:$PATH"
```

**On Host Machine (macOS):**

```bash
# Via Homebrew (recommended)
brew install uv

# Via curl
curl -LsSf https://astral.sh/uv/install.sh | sh

# Verify installation
uv --version
```

**What This Does:**

- Downloads and installs UV binary
- Sets up UV in system PATH
- Enables modern Python package management

### Step 2: Initialize Project

Initialize UV project structure for new or existing projects.

**For New Projects:**

```bash
# Create new project with pyproject.toml
uv init --app --name myproject --python 3.13

# What gets created:
# - pyproject.toml (project configuration)
# - .python-version (Python version pinning)
# - src/myproject/ (source directory)
```

**For Existing Projects (Like Dashtam):**

```bash
# Initialize in existing directory
uv init --app --name dashtam --python 3.13 --no-readme

# Add existing dependencies from requirements.txt
uv add --requirements requirements.txt
uv add --dev --requirements requirements-dev.txt
```

**Important Notes:**

- `--app` flag indicates application (not a library)
- `--python 3.13` sets Python version requirement
- `--no-readme` skips README.md creation if already exists

### Step 3: Manage Dependencies

Add, remove, and update project dependencies.

**Adding Production Dependencies:**

```bash
# Add latest version
uv add boto3

# Add specific version
uv add "boto3==1.40.45"

# Add with version constraints
uv add "boto3>=1.40.0,<2.0.0"

# Add multiple packages
uv add boto3 requests httpx

# Add from requirements.txt
uv add --requirements requirements.txt
```

**Adding Development Dependencies:**

```bash
# Add dev tools
uv add --dev pytest pytest-cov ruff

# Add from requirements-dev.txt
uv add --dev --requirements requirements-dev.txt
```

**Removing Dependencies:**

```bash
# Remove package
uv remove boto3

# Remove multiple packages
uv remove boto3 requests

# Remove dev dependency
uv remove --dev pytest
```

**What Happens When Adding:**

1. UV resolves all dependencies
2. Updates `pyproject.toml` with new dependency
3. Updates `uv.lock` with exact resolved versions
4. Installs package into `.venv` immediately
5. Compiles bytecode for faster imports

### Step 4: Sync Environment

Keep your environment synchronized with project dependencies.

**Basic Sync:**

```bash
# Sync with lockfile (install/update/remove as needed)
uv sync

# Sync only production dependencies
uv sync --no-dev

# Force reinstall all packages
uv sync --reinstall
```

**When to Sync:**

- After pulling changes from git
- After switching branches with different dependencies
- After manually editing `pyproject.toml`
- When virtual environment seems corrupted
- After team member updates dependencies

### Step 5: Run Commands

Execute Python scripts and commands with project dependencies.

**Running Scripts:**

```bash
# Run Python script
uv run python script.py

# Run module
uv run -m pytest

# Run installed CLI tool
uv run uvicorn src.main:app --reload

# Run with specific Python version
uv run --python 3.13 python script.py
```

**Benefits of uv run:**

- Ensures correct virtual environment is active
- No manual venv activation needed
- Consistent across all environments
- Works in CI/CD without modifications

### Step 6: Integrate with Docker

Configure Docker to use UV for fast, deterministic builds.

**Basic Docker Configuration:**

```dockerfile
# Use official UV image
FROM ghcr.io/astral-sh/uv:0.8.22-python3.13-trixie-slim AS base

# Set UV environment
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# Copy project files (lockfile first for caching)
COPY pyproject.toml uv.lock ./

# Sync dependencies
RUN uv sync --no-dev

# Copy application code
COPY . .

# Run application
CMD ["uv", "run", "uvicorn", "src.main:app", "--host", "0.0.0.0"]
```

**Layer Caching Optimization:**

```dockerfile
# Good: Copy lockfile first
COPY pyproject.toml uv.lock ./
RUN uv sync --no-dev
COPY . .

# Bad: Invalidates cache on any code change
COPY . .
RUN uv sync --no-dev
```

## Examples

### Example 1: Adding New Dependency in Dashtam

Complete workflow for adding a new package in containerized development.

**Scenario:** Add boto3 for AWS SES integration

```bash
# 1. Add package in Docker container
docker compose -f compose/docker-compose.dev.yml exec app uv add boto3

# 2. Verify installation
docker compose -f compose/docker-compose.dev.yml exec app \
  python -c "import boto3; print(boto3.__version__)"

# 3. Check what was updated
git status
# Shows: pyproject.toml and uv.lock modified

# 4. Commit changes
git add pyproject.toml uv.lock
git commit -m "feat(deps): add boto3 for AWS SES integration"
```

**What Gets Updated:**

- `pyproject.toml`: Adds `boto3>=1.40.0` to dependencies
- `uv.lock`: Locks boto3 and all its dependencies with exact versions
- `.venv/`: Package installed immediately

### Example 2: After Pulling Changes

Sync your environment after teammate adds dependencies.

**Scenario:** Pull branch with new dependencies

```bash
# 1. Pull changes
git pull origin feature/new-dependencies

# 2. Check what changed
git diff HEAD@{1} -- pyproject.toml uv.lock

# 3. Sync environment
docker compose -f compose/docker-compose.dev.yml exec app uv sync

# 4. Verify everything works
docker compose -f compose/docker-compose.dev.yml exec app uv run pytest
```

**Expected Output:**

```text
Resolved 50 packages in 1.2s
Installed 5 packages in 500ms
```

### Example 3: Upgrading Dependencies

Update packages to latest compatible versions.

**Scenario:** Update FastAPI to latest version

```bash
# 1. Update specific package
docker compose -f compose/docker-compose.dev.yml exec app \
  uv lock --upgrade-package fastapi

# 2. Apply updates
docker compose -f compose/docker-compose.dev.yml exec app uv sync

# 3. Test application
docker compose -f compose/docker-compose.dev.yml exec app uv run pytest

# 4. If tests pass, commit
git add uv.lock
git commit -m "chore(deps): upgrade fastapi to latest version"
```

**Update All Packages:**

```bash
# Update all to latest compatible versions
docker compose -f compose/docker-compose.dev.yml exec app \
  uv lock --upgrade

docker compose -f compose/docker-compose.dev.yml exec app uv sync
```

### Example 4: Docker Multi-Stage Build

Optimize Docker image size with multi-stage builds.

**Complete Multi-Stage Dockerfile:**

```dockerfile
# syntax=docker/dockerfile:1

# Base stage with UV
FROM ghcr.io/astral-sh/uv:0.8.22-python3.13-trixie-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

# Builder stage
FROM base AS builder

WORKDIR /app

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install production dependencies only
RUN uv sync --no-dev --frozen

# Production stage
FROM python:3.13-slim AS production

# Create non-root user
RUN useradd -m -u 1000 appuser

WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder --chown=appuser:appuser /app/.venv /app/.venv

# Copy application code
COPY --chown=appuser:appuser . .

# Set PATH to use venv
ENV PATH="/app/.venv/bin:$PATH"

USER appuser

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Result:** Production image ~200MB smaller than development image.

### Example 5: Migration from pip

Migrate existing pip-based project to UV.

**Scenario:** Convert Dashtam from pip to UV

```bash
# 1. Initialize UV project
uv init --app --name dashtam --python 3.13

# 2. Add all dependencies
uv add --requirements requirements.txt
uv add --dev --requirements requirements-dev.txt

# 3. Verify lockfile created
ls -la uv.lock

# 4. Test in clean environment
docker compose -f compose/docker-compose.test.yml up --build

# 5. If successful, commit UV files
git add pyproject.toml uv.lock
git commit -m "build: migrate from pip to UV package management"

# 6. (Optional) Keep requirements.txt for compatibility
uv pip compile pyproject.toml -o requirements.txt
```

## Verification

### Check 1: UV Installation

Verify UV is properly installed and accessible.

```bash
# Check UV version
uv --version
# Expected: uv 0.8.22 or higher

# Check UV in Docker
docker compose -f compose/docker-compose.dev.yml exec app uv --version

# Check UV configuration
uv config list
```

**Expected Result:** UV version displays without errors.

### Check 2: Dependencies Installed

Verify all dependencies are properly installed.

```bash
# Show dependency tree
uv tree

# Check specific package
uv tree --package fastapi

# List installed packages
uv pip list

# In Docker
docker compose -f compose/docker-compose.dev.yml exec app uv tree
```

**Expected Result:** All dependencies listed with correct versions.

### Check 3: Environment Synced

Verify environment matches lockfile.

```bash
# Validate lockfile
uv lock --check

# Show what would change (dry run)
uv sync --dry-run

# Verify by running tests
uv run pytest
```

**Expected Result:** "Environment is already synced" or tests pass successfully.

## Troubleshooting

### Issue 1: No module named package

**Symptoms:**

- ImportError when running Python code
- Module not found errors in tests
- Application crashes on import

**Cause:** Package not installed or virtual environment not synced.

**Solution:**

```bash
# Sync environment with lockfile
uv sync

# Or add package if genuinely missing
uv add package-name

# Force reinstall if corrupted
uv sync --reinstall
```

### Issue 2: uv command not found

**Symptoms:**

- "uv: command not found" error
- Commands fail in Docker container
- UV not available in PATH

**Cause:** UV not installed or not in PATH.

**Solution:**

```bash
# Check if UV exists in Docker
docker compose -f compose/docker-compose.dev.yml exec app which uv

# If missing, rebuild container
docker compose -f compose/docker-compose.dev.yml build --no-cache

# On host machine, reinstall UV
brew install uv  # macOS
curl -LsSf https://astral.sh/uv/install.sh | sh  # Linux/Unix
```

### Issue 3: Environment Out of Sync

**Symptoms:**

- Different versions than expected
- Import errors after pulling changes
- Lockfile and installed packages mismatch

**Cause:** Environment not synced after lockfile changes.

**Solution:**

```bash
# Force re-sync
uv sync --reinstall

# Or recreate virtual environment
rm -rf .venv
uv venv
uv sync

# In Docker, rebuild
docker compose -f compose/docker-compose.dev.yml up --build
```

### Issue 4: Dependency Conflicts

**Symptoms:**

- UV cannot resolve compatible versions
- Conflicting version requirements
- Resolution fails with error messages

**Cause:** Incompatible version constraints in dependencies.

**Solution:**

```bash
# Check conflict details
uv add package-name --verbose

# Loosen version constraints in pyproject.toml
# Change: "package==1.0.0"
# To: "package>=1.0.0,<2.0.0"

# Exclude problematic versions
uv add "package>=1.0.0,!=1.5.0"

# Update lockfile
uv lock
```

## Best Practices

### Command Usage

**Always Use Modern Commands:**

- Use `uv add` for adding dependencies (not `uv pip install`)
- Use `uv remove` for removing dependencies
- Use `uv sync` after pulling changes
- Use `uv run` to execute commands with project dependencies
- Use `uv lock` to update lockfile without installing

**Avoid Legacy Commands:**

- Avoid `uv pip install` (use `uv add` instead)
- Avoid `uv pip uninstall` (use `uv remove` instead)
- Never mix UV with pip/poetry in same project

### Version Control

**Always Commit:**

- Commit `pyproject.toml` (project configuration)
- Commit `uv.lock` (exact dependency versions)
- Commit `.python-version` (Python version pinning)

**Never Commit:**

- Never commit `.venv/` directory
- Never commit `__pycache__/` directories
- Never commit `.uv/` cache directory

**Handling Merge Conflicts:**

```bash
# When uv.lock has conflicts
git checkout --theirs uv.lock  # Or --ours
uv lock  # Regenerate lockfile
uv sync  # Test resolution
```

### Docker Integration

**Layer Caching Best Practices:**

```dockerfile
# Copy lockfile first (rarely changes)
COPY pyproject.toml uv.lock ./
RUN uv sync --no-dev

# Copy code last (changes frequently)
COPY . .
```

**Multi-Stage Optimization:**

- Use builder stage for dependency installation
- Copy only `.venv` to production stage
- Use `--frozen` flag for deterministic builds
- Set `UV_COMPILE_BYTECODE=1` for faster startup

### Performance Optimization

**UV Caching:**

```bash
# Show cache location
uv cache dir

# Show cache size
uv cache size

# Clean cache (rarely needed)
uv cache clean
```

**Parallel Installation:**

- UV automatically parallelizes installations
- No configuration needed
- Significantly faster than pip

**Bytecode Compilation:**

```dockerfile
# Enable in Docker for faster imports
ENV UV_COMPILE_BYTECODE=1
```

### Common Mistakes to Avoid

**Don't Do These:**

- Don't use `uv pip install` in modern projects (use `uv add`)
- Don't edit `uv.lock` manually (always regenerate with `uv lock`)
- Don't commit `.venv/` directory to git
- Don't mix UV with pip/poetry in same project
- Don't ignore lockfile merge conflicts (resolve carefully)
- Don't use `pip` inside UV-managed projects

**Do These Instead:**

- Use `uv add` for all dependency additions
- Let UV manage `uv.lock` automatically
- Add `.venv/` to `.gitignore`
- Choose one tool (UV) and stick with it
- Resolve lockfile conflicts then regenerate
- Use UV commands exclusively

### Quick Command Cheat Sheet

**Common Commands:**

```bash
# Dependency Management
uv add package              # Add dependency
uv add --dev package        # Add dev dependency
uv remove package           # Remove dependency
uv sync                     # Sync environment with lockfile
uv lock                     # Update lockfile
uv lock --upgrade           # Upgrade all packages

# Running Code
uv run python script.py     # Run script
uv run -m pytest            # Run module
uv run uvicorn app:main     # Run server

# Information
uv tree                     # Show dependency tree
uv pip list                 # List installed packages
uv --version                # Show UV version
```

**Docker Commands (Dashtam-Specific):**

```bash
# Add dependency in container
docker compose -f compose/docker-compose.dev.yml exec app uv add package

# Sync environment
docker compose -f compose/docker-compose.dev.yml exec app uv sync

# Run tests
docker compose -f compose/docker-compose.dev.yml exec app uv run pytest

# Show dependencies
docker compose -f compose/docker-compose.dev.yml exec app uv tree
```

## Next Steps

After mastering UV package management, consider:

- [ ] Review [Docker Refactoring Implementation Guide](docker-refactoring-implementation.md)
- [ ] Set up automated dependency updates with Dependabot
- [ ] Configure pre-commit hooks for lockfile validation
- [ ] Implement dependency security scanning
- [ ] Explore UV workspaces for monorepo projects
- [ ] Set up UV caching in CI/CD pipeline
- [ ] Document project-specific UV workflows
- [ ] Train team members on UV best practices

## References

- [UV Documentation](https://docs.astral.sh/uv/) - Official UV documentation
- [UV GitHub Repository](https://github.com/astral-sh/uv) - Source code and issues
- [PEP 621](https://peps.python.org/pep-0621/) - Project metadata standard
- [Dashtam Docker Configuration](../../docker/Dockerfile) - Project Dockerfile
- [Dashtam WARP.md](../../../WARP.md) - Project rules for UV usage
- [Docker Best Practices](https://docs.docker.com/develop/dev-best-practices/) - Docker optimization

---

## Document Information

**Template:** [guide-template.md](../../templates/guide-template.md)
**Created:** 2025-10-04
**Last Updated:** 2025-10-20
