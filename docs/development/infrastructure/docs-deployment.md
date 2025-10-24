# Documentation Deployment

Automated deployment of MkDocs documentation to GitHub Pages using GitHub Actions.

---

## Overview

The Dashtam documentation is automatically built and deployed to GitHub Pages whenever changes are pushed to the development branch. This ensures the public documentation always reflects the current development state.

### Key Features

- **Automated Deployment**: Push to development branch triggers automatic build and deployment
- **GitHub Pages Hosting**: Free, reliable hosting for public documentation
- **Build Validation**: Strict mode ensures no warnings or errors in production docs
- **UV-Powered Builds**: Fast, deterministic builds with dependency caching
- **Manual Trigger**: Option to manually deploy via GitHub Actions UI

## Purpose

This infrastructure automates documentation deployment to eliminate manual publishing steps, ensure documentation stays in sync with code, and provide a reliable public URL for project documentation. It replaces manual `mkdocs gh-deploy` commands with a fully automated CI/CD pipeline.

## Components

### Component 1: GitHub Actions Workflow

**Purpose:** Automates building and deploying MkDocs site to GitHub Pages

**Technology:** GitHub Actions, Python 3.13, UV 0.8.22

**Dependencies:**

- MkDocs 1.6.1+
- MkDocs Material theme
- MkDocs Mermaid2 plugin
- MkDocstrings plugin

**File Location:** `.github/workflows/docs.yml`

### Component 2: GitHub Pages

**Purpose:** Hosts the built static documentation site

**Technology:** GitHub Pages (static site hosting)

**Dependencies:**

- GitHub repository with Pages enabled
- `gh-pages` branch (auto-created)

**URL:** `https://faiyazhaider.github.io/Dashtam/`

### Component 3: MkDocs Build System

**Purpose:** Generates static HTML site from markdown documentation

**Technology:** MkDocs with Material theme

**Dependencies:**

- Python 3.13
- Project dependencies in `pyproject.toml`

## Configuration

### Environment Variables

No environment variables required. All configuration is in repository files.

### Configuration Files

**File:** `.github/workflows/docs.yml`

```yaml
name: Documentation

on:
  push:
    branches:
      - development  # Deploy from development (pre-v1.0)
    paths:
      - 'docs/**'
      - 'mkdocs.yml'
      - '.github/workflows/docs.yml'
  workflow_dispatch:  # Manual trigger option
```

**Purpose:** Defines when and how documentation is built and deployed

**File:** `mkdocs.yml`

```yaml
site_name: Dashtam Documentation
site_url: https://faiyazhaider.github.io/Dashtam/
repo_url: https://github.com/faiyazhaider/Dashtam
```

**Purpose:** MkDocs configuration for site generation

### Ports and Services

| Service | Port | Protocol | Purpose |
|---------|------|----------|---------|
| GitHub Pages | 443 | HTTPS | Public documentation hosting |
| Local Preview | 8001 | HTTP | Development preview server |

## Setup Instructions

### Prerequisites

- [x] GitHub repository with documentation in `docs/`
- [x] MkDocs configuration in `mkdocs.yml`
- [x] Dependencies in `pyproject.toml`
- [ ] GitHub Pages enabled (one-time setup below)

### Installation Steps

#### Step 1: Enable GitHub Pages

Navigate to repository settings:

```bash
# Open in browser
https://github.com/faiyazhaider/Dashtam/settings/pages
```

Configuration:

1. **Source:** Select "GitHub Actions"
2. **Branch:** No branch selection needed (workflow handles deployment)
3. **Save changes**

**Verification:**

Visit the deployment URL after first workflow run:

```bash
# Expected: Documentation site loads
https://faiyazhaider.github.io/Dashtam/
```

#### Step 2: Configure Workflow Permissions

Repository settings are already configured in workflow file:

```yaml
permissions:
  contents: read    # Read repository content
  pages: write      # Deploy to GitHub Pages
  id-token: write   # OIDC authentication
```

No manual action required.

**Verification:**

Check workflow runs:

```bash
# GitHub Actions tab
https://github.com/faiyazhaider/Dashtam/actions/workflows/docs.yml
```

#### Step 3: Push Documentation Changes

Make any change to documentation:

```bash
# Edit any doc file
vim docs/index.md

# Commit and push to development
git add docs/index.md
git commit -m "docs: trigger deployment test"
git push origin development
```

**Verification:**

Check workflow status:

```bash
# Should see "Documentation" workflow running
# Green checkmark = success, Red X = failed
```

## Operation

### Starting the System

Documentation deployment is automatic. No manual start required.

**Trigger conditions:**

1. Push to `development` branch
2. Changes in: `docs/**`, `mkdocs.yml`, or `.github/workflows/docs.yml`
3. Manual workflow dispatch

### Stopping the System

To temporarily disable automatic deployments:

#### Option 1: Disable workflow

```bash
# Navigate to Actions → Documentation → ... → Disable workflow
```

#### Option 2: Remove trigger paths

Edit `.github/workflows/docs.yml`:

```yaml
on:
  workflow_dispatch:  # Only manual trigger, no automatic
```

### Restarting

Re-enable workflow:

```bash
# Actions → Documentation → ... → Enable workflow
```

Or trigger manual deployment:

```bash
# Actions → Documentation → Run workflow → Select branch → Run
```

### Checking Status

**Current deployment status:**

```bash
# Visit GitHub Actions
https://github.com/faiyazhaider/Dashtam/actions/workflows/docs.yml
```

**Expected Output:**

- Green checkmark: Deployed successfully
- Yellow circle: Build in progress
- Red X: Build or deployment failed

**Live site status:**

```bash
# Visit deployment URL
https://faiyazhaider.github.io/Dashtam/
```

## Monitoring

### Health Checks

**Check deployment status:**

```bash
# GitHub CLI (if installed)
gh workflow view docs.yml

# Or visit Actions tab in browser
```

**Check live site:**

```bash
# HTTP status check
curl -I https://faiyazhaider.github.io/Dashtam/
```

**Expected:** HTTP 200 OK

### Metrics to Monitor

- **Build Time**: 30-60 seconds (cached), 2-3 minutes (first build)
- **Deployment Success Rate**: Should be 100% if local builds pass
- **Workflow Runs**: Check for repeated failures
- **Pages Build Status**: Settings → Pages → View deployments

### Logs

**Location:** GitHub Actions workflow logs

**Viewing Logs:**

```bash
# Via GitHub UI
Actions → Documentation → Select workflow run → Build Documentation

# Via GitHub CLI
gh run list --workflow=docs.yml
gh run view <run-id> --log
```

**Key log sections:**

- Install dependencies
- Build documentation (`mkdocs build --strict --verbose`)
- Upload artifact
- Deploy to Pages

## Troubleshooting

### Issue 1: Build Fails with Warnings

**Symptoms:**

- Workflow fails at "Build documentation" step
- Error: "WARNING" treated as error
- Local build works but CI fails

**Diagnosis:**

```bash
# Run strict build locally
make docs-build

# Or manually
docker compose -f compose/docker-compose.dev.yml exec app uv run mkdocs build --strict
```

**Solution:**

Fix all warnings before pushing:

```bash
# Check for warnings
make docs-build

# Common issues:
# - Broken links
# - Missing files
# - Invalid Mermaid syntax
# - Unrecognized relative links
```

### Issue 2: Deployment Succeeds but Site Shows Old Content

**Symptoms:**

- Workflow shows green checkmark
- Visited site still shows old content
- Recent changes not visible

**Diagnosis:**

Check GitHub Pages deployment timestamp:

```bash
# Settings → Pages → View deployments
# Compare timestamp with recent commits
```

**Solution:**

```bash
# 1. Wait 5-10 minutes for propagation

# 2. Hard refresh browser
# Mac: Cmd + Shift + R
# Windows/Linux: Ctrl + Shift + R

# 3. Clear browser cache completely

# 4. Try incognito/private window

# 5. If still not working, check deployment logs
```

### Issue 3: Workflow Not Triggering

**Symptoms:**

- Pushed changes to development
- No workflow run appears in Actions tab
- Documentation not updating

**Diagnosis:**

```bash
# Check if changes are in trigger paths
git diff HEAD~1 --name-only

# Workflow triggers on:
# - docs/**
# - mkdocs.yml
# - .github/workflows/docs.yml
```

**Solution:**

```bash
# If changes outside trigger paths:
# Option 1: Manually trigger workflow
Actions → Documentation → Run workflow

# Option 2: Touch a doc file
touch docs/index.md
git add docs/index.md
git commit -m "docs: trigger deployment"
git push origin development
```

### Issue 4: Permission Denied Errors

**Symptoms:**

- Build succeeds
- Deploy step fails
- Error: "Permission denied" or "403 Forbidden"

**Diagnosis:**

Check workflow permissions:

```bash
# Verify in .github/workflows/docs.yml:
permissions:
  contents: read
  pages: write
  id-token: write
```

**Solution:**

```bash
# Permissions should be correctly set in workflow file
# If still failing, check repository settings:
Settings → Actions → General → Workflow permissions
# Ensure "Read and write permissions" is enabled
```

### Issue 5: UV Dependency Installation Fails

**Symptoms:**

- Workflow fails at "Install dependencies" step
- Error: "Package not found" or "Lock file out of sync"

**Diagnosis:**

```bash
# Check if uv.lock is committed
git ls-files uv.lock

# Verify dependencies locally
uv sync --frozen --no-dev
```

**Solution:**

```bash
# Regenerate lock file
uv lock

# Commit updated lock file
git add uv.lock
git commit -m "chore: update uv.lock"
git push origin development
```

## Maintenance

### Regular Tasks

**Weekly:**

- Monitor deployment success rate in Actions tab
- Check for failed workflow runs
- Review deployment times (should be consistent)

**Monthly:**

- Review and update dependencies (UV, Python, GitHub Actions)
- Check GitHub Pages quota and usage
- Verify all documentation links still work

**Quarterly:**

- Review workflow efficiency and optimization opportunities
- Update documentation about deployment process
- Test manual deployment process

### Dependency Updates

**Update GitHub Actions:**

```yaml
# .github/workflows/docs.yml
- uses: actions/checkout@v4  # Check for newer versions
- uses: actions/setup-python@v5
- uses: astral-sh/setup-uv@v4
- uses: actions/upload-pages-artifact@v3
- uses: actions/deploy-pages@v4
```

**Update Python Dependencies:**

```bash
# Update MkDocs and plugins
docker compose -f compose/docker-compose.dev.yml exec app uv add mkdocs@latest
docker compose -f compose/docker-compose.dev.yml exec app uv add mkdocs-material@latest

# Test locally
make docs-build

# Commit updated dependencies
git add pyproject.toml uv.lock
git commit -m "chore: update mkdocs dependencies"
```

### Backup and Recovery

**Backup Strategy:**

Documentation source is in git repository (already backed up). Deployed site can be regenerated anytime from source.

**Recovery Process:**

If deployment fails completely:

```bash
# 1. Local build and manual deploy
make docs-build

# 2. Push to gh-pages branch manually (emergency only)
git clone --branch gh-pages https://github.com/faiyazhaider/Dashtam.git /tmp/gh-pages
cp -r site/* /tmp/gh-pages/
cd /tmp/gh-pages
git add .
git commit -m "Emergency manual deployment"
git push origin gh-pages
```

## Security

### Access Control

- **Read Access**: Public (documentation is public)
- **Write Access**: GitHub Actions workflow only
- **Manual Deployment**: Repository maintainers via workflow_dispatch

### Secrets Management

No secrets required. Workflow uses OIDC (OpenID Connect) for secure authentication:

```yaml
permissions:
  id-token: write  # OIDC token for deployment
```

Benefits:

- No personal access tokens needed
- No secrets to rotate
- GitHub manages credentials automatically
- Tokens are short-lived and scoped

### Branch Protection

Recommended settings for `development` branch:

- Require status check: "Documentation / Build Documentation"
- Prevents merging broken documentation
- Ensures all docs pass strict validation

## Performance Optimization

### Build Time Optimization

**Current Performance:**

- First build: 2-3 minutes (dependency installation)
- Cached builds: 30-60 seconds (UV caching enabled)

**Optimization Strategies:**

1. **UV Caching** (Already enabled):

```yaml
- uses: astral-sh/setup-uv@v4
  with:
    enable-cache: true  # Caches dependencies between runs
```

1. **Conditional Deployment**:

```yaml
paths:
  - 'docs/**'  # Only deploy when docs change
```

1. **Parallel Jobs** (Not needed - single job is fast enough)

### Content Delivery Optimization

GitHub Pages automatically provides:

- Global CDN distribution
- HTTPS by default
- Gzip compression
- Browser caching headers

No additional optimization needed.

## References

### Documentation

- [MkDocs Documentation](https://www.mkdocs.org/)
- [MkDocs Material Theme](https://squidfunk.github.io/mkdocs-material/)
- [GitHub Pages Documentation](https://docs.github.com/en/pages)
- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [UV Package Manager](https://docs.astral.sh/uv/)

### Related Project Documentation

- [MkDocs Local Setup](../../guides/mkdocs-setup.md)
- [GitHub Workflow Guide](../../guides/git-workflow.md)
- [CI/CD Overview](ci-cd.md)
- [Markdown Standards](../../guides/markdown-linting-guide.md)

### External Resources

- [GitHub Actions: Deploy Pages](https://github.com/actions/deploy-pages)
- [GitHub Pages Custom Domains](https://docs.github.com/en/pages/configuring-a-custom-domain-for-your-github-pages-site)
- [MkDocs Plugins](https://github.com/mkdocs/mkdocs/wiki/MkDocs-Plugins)

---

## Document Information

**Template:** infrastructure-template.md (located in docs/templates/)

**Created:** 2025-10-24

**Last Updated:** 2025-10-24

**Status:** Active

**Maintainer:** Faiyaz Haider

**Related Documentation:**

- [Docker Setup](docker-setup.md)
- [Database Migrations](database-migrations.md)
- [CI/CD Pipeline](ci-cd.md)
