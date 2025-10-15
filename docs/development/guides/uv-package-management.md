# Modern UV Package Management Guide

**Document Purpose:** Comprehensive guide for using UV (version 0.8.22+) as the modern Python package manager in Dashtam.

**Last Updated:** 2025-10-04  
**UV Version:** 0.8.22+  
**Status:** Active Standard

---

## Overview

UV is an extremely fast Python package manager and resolver, written in Rust. It's designed as a drop-in replacement for pip, pip-tools, poetry, and other Python package management tools.

**Why UV?**

- ⚡ **10-100x faster** than pip
- 🔒 **Deterministic resolution** with lockfiles
- 🎯 **Modern Python workflow** (replaces pip, poetry, pipenv)
- 🐳 **Docker-optimized** with official container images
- 📦 **Universal resolver** handles all dependency scenarios

---

## Core Concepts

### Project vs Package Management

UV distinguishes between two modes:

1. **Project Management** (`uv add`, `uv sync`, `uv lock`)
   - For applications with `pyproject.toml`
   - Manages project dependencies in a lockfile
   - Creates and manages virtual environments

2. **Package Management** (`uv pip`)
   - Legacy pip-compatible interface
   - For one-off package installations
   - Compatible with `requirements.txt`

**Dashtam uses Project Management mode** - this is the modern approach.

---

## Installation

### In Docker (Recommended for Dashtam)

```dockerfile
# Use official UV image with Python 3.13
FROM ghcr.io/astral-sh/uv:0.8.22-python3.13-trixie-slim AS base

# Set UV environment variables
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    PATH="/app/.venv/bin:$PATH"
```

### On Host Machine (macOS)

```bash
# Via Homebrew (recommended for macOS)
brew install uv

# Via curl
curl -LsSf https://astral.sh/uv/install.sh | sh

# Via pip (not recommended - defeats the purpose!)
pip install uv
```

---

## Command Reference

### Project Initialization

#### Initialize New Project

```bash
# Create new project with pyproject.toml
uv init --app --name myproject --python 3.13

# Initialize in existing directory
uv init --app --name dashtam --python 3.13 --no-readme
```

**Options:**

- `--app`: Create an application (not a library)
- `--name`: Project name
- `--python`: Python version requirement
- `--no-readme`: Skip README.md creation

### Adding Dependencies

#### Add Production Dependencies

```bash
# Add single package (latest version)
uv add boto3

# Add specific version
uv add "boto3==1.40.45"

# Add with version constraint
uv add "boto3>=1.40.0,<2.0.0"

# Add multiple packages
uv add boto3 requests httpx

# Add from requirements.txt
uv add --requirements requirements.txt
```

#### Add Development Dependencies

```bash
# Add dev dependencies
uv add --dev pytest pytest-cov ruff

# Add from requirements-dev.txt
uv add --dev --requirements requirements-dev.txt
```

#### Add Optional Dependencies

```bash
# Add to specific extras group
uv add --optional docs sphinx sphinx-rtd-theme

# Add to dependency group
uv add --group test pytest pytest-asyncio
```

**Key Points:**

- ✅ **Use `uv add`** - NOT `uv pip install`
- ✅ Updates `pyproject.toml` and `uv.lock` automatically
- ✅ Installs immediately into virtual environment
- ✅ Resolves dependencies intelligently

### Removing Dependencies

```bash
# Remove package
uv remove boto3

# Remove multiple packages
uv remove boto3 requests

# Remove dev dependency
uv remove --dev pytest
```

### Syncing Environment

```bash
# Sync environment with lockfile (install/update/remove as needed)
uv sync

# Sync only production dependencies (no dev)
uv sync --no-dev

# Force reinstall all packages
uv sync --reinstall

# Sync without installing project itself
uv sync --no-install-project
```

**When to use `uv sync`:**

- After pulling changes from git
- After modifying `pyproject.toml` manually
- After switching branches with different dependencies
- When virtual environment is corrupted

### Lockfile Management

```bash
# Update lockfile without installing
uv lock

# Update specific package to latest version
uv lock --upgrade-package boto3

# Update all packages to latest compatible versions
uv lock --upgrade
```

### Running Commands

```bash
# Run Python script with project dependencies
uv run python script.py

# Run module
uv run -m pytest

# Run installed tool
uv run uvicorn src.main:app --reload

# Run with specific Python version
uv run --python 3.13 python script.py
```

**Benefits of `uv run`:**

- Ensures correct virtual environment is used
- No need to activate venv manually
- Consistent across all environments

### Virtual Environment Management

```bash
# Create virtual environment
uv venv

# Create with specific Python version
uv venv --python 3.13

# Create in custom location
uv venv .venv

# Activate (manual - not usually needed with `uv run`)
source .venv/bin/activate  # Unix
.venv\Scripts\activate     # Windows
```

### Legacy pip Interface

```bash
# Only use when absolutely necessary for legacy compatibility
uv pip install package-name
uv pip uninstall package-name
uv pip list
uv pip freeze
```

**⚠️ Warning:** Avoid `uv pip` commands in modern projects. Use `uv add` instead.

---

## Dashtam Workflow

### Adding New Dependency

**Scenario:** You need to add a new package (e.g., `boto3`)

```bash
# 1. Add package using modern UV command
docker compose -f docker-compose.dev.yml exec app uv add boto3

# Alternative: Add with version constraint
docker compose -f docker-compose.dev.yml exec app uv add "boto3>=1.40.0"

# 2. Verify installation
docker compose -f docker-compose.dev.yml exec app python -c "import boto3; print(boto3.__version__)"

# 3. Commit changes (pyproject.toml and uv.lock updated automatically)
git add pyproject.toml uv.lock
git commit -m "Add boto3 for AWS SES integration"
```

**What Happens:**

1. UV resolves dependencies
2. Updates `pyproject.toml` with new dependency
3. Updates `uv.lock` with resolved versions
4. Installs package into `.venv`
5. Compiles bytecode for faster imports

### After Pulling Changes

**Scenario:** Teammate added dependencies, you pulled their branch

```bash
# Sync your environment with the updated lockfile
docker compose -f docker-compose.dev.yml exec app uv sync

# Verify everything works
docker compose -f docker-compose.dev.yml exec app uv run pytest
```

### Upgrading Dependencies

**Scenario:** Update to latest compatible versions

```bash
# Update specific package
docker compose -f docker-compose.dev.yml exec app uv lock --upgrade-package fastapi

# Update all packages
docker compose -f docker-compose.dev.yml exec app uv lock --upgrade

# Apply updates
docker compose -f docker-compose.dev.yml exec app uv sync
```

### Development Dependencies

**Scenario:** Add testing or development tools

```bash
# Add dev dependencies
docker compose -f docker-compose.dev.yml exec app uv add --dev pytest pytest-asyncio pytest-cov

# Add linting tools
docker compose -f docker-compose.dev.yml exec app uv add --dev ruff black mypy
```

### Checking What's Installed

```bash
# Show dependency tree
docker compose -f docker-compose.dev.yml exec app uv tree

# Show installed packages (legacy)
docker compose -f docker-compose.dev.yml exec app uv pip list
```

---

## Docker Integration

### Multi-Stage Dockerfile with UV

```dockerfile
# syntax=docker/dockerfile:1

FROM ghcr.io/astral-sh/uv:0.8.22-python3.13-trixie-slim AS base

# Set UV environment
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# Development stage
FROM base AS development

# Copy project files
COPY pyproject.toml uv.lock* ./
COPY requirements*.txt ./

# Initialize project if needed
RUN if [ ! -f "pyproject.toml" ]; then \
        uv init --app --name dashtam --python 3.13 --no-readme; \
    fi

# Add dependencies from requirements.txt (migration phase)
RUN uv add --requirements requirements.txt && \
    uv add --dev --requirements requirements-dev.txt

# Copy application code
COPY . .

# Sync environment
RUN uv sync

# Run with uv
CMD ["uv", "run", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
```

### Best Practices for Docker

1. **Copy lockfile first** for better caching:

   ```dockerfile
   COPY pyproject.toml uv.lock* ./
   ```

2. **Use multi-stage builds** for smaller production images:

   ```dockerfile
   FROM base AS builder
   RUN uv sync --no-dev
   
   FROM python:3.13-slim AS production
   COPY --from=builder /app/.venv /app/.venv
   ```

3. **Set UV environment variables** for optimal performance:

   ```dockerfile
   ENV UV_COMPILE_BYTECODE=1 \
       UV_LINK_MODE=copy
   ```

---

## Configuration Files

### pyproject.toml

UV uses `pyproject.toml` for project configuration (PEP 621 standard).

```toml
[project]
name = "dashtam"
version = "0.1.0"
description = "Financial data aggregation platform"
requires-python = ">=3.13"
dependencies = [
    "fastapi>=0.100.0",
    "uvicorn[standard]>=0.23.0",
    "sqlmodel>=0.0.18",
    "boto3>=1.40.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
    "pytest-cov>=4.1.0",
    "ruff>=0.5.0",
]

[tool.uv]
dev-dependencies = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
]

[tool.uv.sources]
# Optional: specify package sources
# mypackage = { git = "https://github.com/user/repo.git" }
```

### uv.lock

**DO NOT EDIT MANUALLY** - Generated and managed by UV.

- Contains exact resolved versions
- Platform-specific hashes for security
- Ensures reproducible installations
- Should be committed to git

### .gitignore

```gitignore
# Python
__pycache__/
*.py[cod]
*$py.class
*.so

# Virtual environments
.venv/
venv/
ENV/
env/

# UV cache
.uv/

# Don't ignore lockfile!
# uv.lock  ❌ DO NOT ADD THIS
```

---

## Migration from pip/poetry

### From pip + requirements.txt

```bash
# 1. Initialize UV project
uv init --app --name dashtam --python 3.13

# 2. Add all dependencies from requirements.txt
uv add --requirements requirements.txt
uv add --dev --requirements requirements-dev.txt

# 3. Generate lockfile
uv lock

# 4. Verify everything works
uv sync
uv run pytest

# 5. (Optional) Keep requirements.txt for legacy compatibility
uv pip compile pyproject.toml -o requirements.txt
```

### From poetry

```bash
# 1. Export poetry dependencies
poetry export -f requirements.txt --output requirements.txt

# 2. Initialize UV project
uv init --app --name dashtam --python 3.13

# 3. Add dependencies
uv add --requirements requirements.txt

# 4. Remove poetry files
rm poetry.lock pyproject.toml  # Backup first!
```

---

## Troubleshooting

### Common Issues

#### "No module named 'package'"

**Problem:** Package not installed in virtual environment

**Solution:**

```bash
# Sync environment with lockfile
uv sync

# Or add package if missing
uv add package-name
```

#### "uv: command not found"

**Problem:** UV not available in Docker container

**Solution:**

```bash
# Check UV installation
docker compose -f docker-compose.dev.yml exec app which uv

# If missing, rebuild container
docker compose -f docker-compose.dev.yml build --no-cache
```

#### Environment out of sync

**Problem:** Lockfile and installed packages don't match

**Solution:**

```bash
# Force re-sync
uv sync --reinstall

# Or recreate virtual environment
rm -rf .venv
uv venv
uv sync
```

#### Dependency conflicts

**Problem:** UV can't resolve compatible versions

**Solution:**

```bash
# Try loosening version constraints in pyproject.toml
# Change: "package==1.0.0"
# To: "package>=1.0.0"

# Or exclude problematic versions
uv add "package>=1.0.0,!=1.5.0"
```

### Debug Commands

```bash
# Show UV version
uv --version

# Show UV configuration
uv config list

# Show dependency tree
uv tree

# Show why a package is installed
uv tree --package boto3 --invert

# Show locked versions
uv pip list

# Validate lockfile
uv lock --check
```

---

## Performance Tips

### Caching

UV automatically caches downloaded packages:

```bash
# Show cache location
uv cache dir

# Show cache size
uv cache size

# Clean cache (rarely needed)
uv cache clean
```

### Docker Layer Caching

```dockerfile
# ✅ GOOD: Copy lockfile first for better caching
COPY pyproject.toml uv.lock ./
RUN uv sync --no-dev
COPY . .

# ❌ BAD: Invalidates cache on any code change
COPY . .
RUN uv sync --no-dev
```

### Parallel Installation

UV automatically parallelizes installations - no configuration needed!

---

## Best Practices

### ✅ DO

- Use `uv add` for adding dependencies
- Commit `uv.lock` to version control
- Use `uv sync` after pulling changes
- Use `uv run` to run commands with project dependencies
- Keep `pyproject.toml` organized and documented
- Use version constraints (`>=`, `<`, `!=`) appropriately
- Test in clean environment before deploying

### ❌ DON'T

- Use `uv pip install` in modern projects (legacy only)
- Edit `uv.lock` manually
- Commit `.venv/` directory
- Mix UV with other package managers (pip, poetry) in same project
- Use `pip` inside UV-managed projects
- Ignore lockfile merge conflicts (resolve carefully!)

---

## Comparison with Other Tools

| Feature | UV | pip | poetry | pipenv |
|---------|-----|-----|--------|--------|
| **Speed** | ⚡⚡⚡⚡⚡ | ⚡ | ⚡⚡ | ⚡⚡ |
| **Lockfile** | ✅ | ❌ | ✅ | ✅ |
| **Resolver** | ✅ Fast | ❌ Slow | ✅ Slow | ✅ Very Slow |
| **Docker Support** | ✅ Official images | ⚠️ Manual | ⚠️ Manual | ⚠️ Manual |
| **PEP 621 Support** | ✅ | ❌ | ⚠️ Partial | ❌ |
| **Ease of Use** | ⚡⚡⚡⚡⚡ | ⚡⚡⚡ | ⚡⚡⚡⚡ | ⚡⚡⚡ |

---

## References

- [UV Documentation](https://docs.astral.sh/uv/)
- [UV GitHub Repository](https://github.com/astral-sh/uv)
- [PEP 621 - Storing project metadata in pyproject.toml](https://peps.python.org/pep-0621/)
- [Dashtam Docker Configuration](../../docker/Dockerfile)

---

## Changelog

| Date | Change | Author |
|------|--------|--------|
| 2025-10-04 | Initial comprehensive UV guide created | Dashtam Team |
| 2025-10-04 | Added Docker integration examples | Dashtam Team |
| 2025-10-04 | Added troubleshooting section | Dashtam Team |

---

## Quick Command Cheat Sheet

```bash
# Common Commands
uv add package              # Add dependency
uv add --dev package        # Add dev dependency
uv remove package           # Remove dependency
uv sync                     # Sync environment with lockfile
uv lock                     # Update lockfile
uv run python script.py     # Run with project dependencies
uv tree                     # Show dependency tree

# Docker Commands (Dashtam-specific)
docker compose -f docker-compose.dev.yml exec app uv add package
docker compose -f docker-compose.dev.yml exec app uv sync
docker compose -f docker-compose.dev.yml exec app uv run pytest
docker compose -f docker-compose.dev.yml exec app uv tree
```

---

**Remember:** UV is designed to be fast and intuitive. When in doubt, `uv --help` or `uv <command> --help` provides excellent inline documentation!

---

## Document Information

**Category:** Guide
**Created:** 2025-10-04
**Last Updated:** 2025-10-15
**Difficulty Level:** Intermediate
**Target Audience:** Developers, DevOps engineers, Python package managers
**Prerequisites:** Basic Python knowledge, Docker familiarity
**Related Documents:** [Docker Setup Guide](../infrastructure/docker-setup.md)
