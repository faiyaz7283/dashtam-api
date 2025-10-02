# GitHub Actions Setup Guide

## ✅ Automated Setup (Already Done)

The following files are already configured and committed:

- ✅ `.github/workflows/test.yml` - Main workflow file
- ✅ `docker-compose.ci.yml` - CI environment configuration  
- ✅ `.env.ci.example` - CI environment variables template
- ✅ `.env.ci` - Actual CI environment file

## 🚀 Quick Start (2 Steps)

### Step 1: Push Your Code

```bash
cd /Users/faiyazhaider/Dashtam

# Check what will be committed
git status

# Add all changes
git add .

# Commit with descriptive message
git commit -m "feat: add CI/CD infrastructure with GitHub Actions"

# Push to GitHub
git push origin main  # or your branch name (develop, feature/ci-cd, etc.)
```

### Step 2: Watch It Run!

1. Go to your GitHub repo
2. Click the **"Actions"** tab
3. You'll see your workflow running automatically
4. Click on the running workflow to see live logs

**That's it!** No manual GitHub configuration needed.

---

## 🔍 What Happens Automatically

When you push code, GitHub Actions will:

1. **Detect the workflow** (`.github/workflows/test.yml`)
2. **Spin up Ubuntu runner** (free, provided by GitHub)
3. **Run two jobs in parallel:**
   - **Test Job:** Build and run full test suite via `docker-compose.ci.yml`
   - **Lint Job:** Check code quality with ruff
4. **Report results:**
   - ✅ Green checkmark if all pass
   - ❌ Red X if anything fails
   - 📊 Detailed logs for debugging

---

## 🎯 Triggers

Your workflow runs automatically on:

✅ **Push to `main` branch**
✅ **Push to `develop` branch**  
✅ **Pull requests to `main` or `develop`**

You can customize triggers in `.github/workflows/test.yml`:

```yaml
on:
  push:
    branches: [ main, develop, feature/* ]  # Add more branches
  pull_request:
    branches: [ main, develop ]
  schedule:
    - cron: '0 0 * * 0'  # Weekly on Sunday
```

---

## 🛡️ Branch Protection (Recommended)

Prevent merging broken code:

### Steps:

1. **Go to repo Settings**
2. **Branches** → **Add rule**
3. **Branch name pattern:** `main`
4. **Enable:**
   - ✅ Require status checks to pass before merging
   - ✅ Require branches to be up to date before merging
   - ✅ Select: "Run Tests" and "Code Quality"
5. **Save changes**

Now PRs must pass tests before merging!

---

## 📊 Codecov Integration (Optional)

### What is Codecov?

A service that shows:
- Which code lines are tested vs untested
- Coverage trends over time
- PR comments with coverage changes
- Coverage badges for README

### Free For:
- ✅ Public repositories (unlimited)
- ✅ Open source projects
- ✅ Private repos (limited free tier)

### Setup (5 minutes):

#### 1. Sign Up

Go to [codecov.io](https://codecov.io) and sign up with GitHub

#### 2. Enable Repository

- Click "Add Repository"
- Find and enable `Dashtam`
- Codecov will show you a token

#### 3. Add Token to GitHub

```bash
# Your token looks like: a1b2c3d4-e5f6-7890-abcd-ef1234567890
```

1. Go to GitHub repo → **Settings**
2. **Secrets and variables** → **Actions**
3. **New repository secret**
4. Name: `CODECOV_TOKEN`
5. Value: Paste your token
6. Click **Add secret**

#### 4. Push Code

Next push will automatically upload coverage to Codecov!

#### 5. Add Badge to README (Optional)

Codecov provides a badge URL:

```markdown
[![codecov](https://codecov.io/gh/YOUR_USERNAME/Dashtam/branch/main/graph/badge.svg)](https://codecov.io/gh/YOUR_USERNAME/Dashtam)
```

### Skip Codecov?

**Totally fine!** Your CI still works without it:
- Tests run ✅
- Coverage generated ✅  
- Reports in CI artifacts ✅

To disable Codecov upload, comment out in `.github/workflows/test.yml`:

```yaml
# - name: Upload coverage to Codecov
#   uses: codecov/codecov-action@v4
#   ...
```

---

## 🧪 Local Testing (Before Pushing)

Test your CI locally before pushing:

```bash
# Run exactly what GitHub Actions will run
make ci-test

# If it passes locally, it will pass in GitHub Actions!
```

---

## 📈 Viewing Results

### In GitHub:

**Actions Tab:**
- See all workflow runs
- Click on a run to see detailed logs
- Download artifacts (coverage reports)

**Pull Requests:**
- Status checks show at bottom of PR
- Required checks must pass before merge

**README Badge (Optional):**

Add to your README.md:

```markdown
![Tests](https://github.com/YOUR_USERNAME/Dashtam/workflows/Test%20Suite/badge.svg)
```

---

## 🐛 Troubleshooting

### Workflow Not Running?

1. **Check file location:** Must be `.github/workflows/test.yml`
2. **Check YAML syntax:** Indentation matters!
3. **Check GitHub Actions is enabled:** Repo Settings → Actions

### Tests Failing in CI but Pass Locally?

1. **Check .env.ci file:** Make sure it's committed
2. **Check Docker cache:** CI rebuilds from scratch
3. **Check logs:** Actions tab → Click failed run → View logs

### Need Help?

1. Check [GitHub Actions docs](https://docs.github.com/en/actions)
2. View workflow logs in Actions tab
3. Run `make ci-test` locally to debug

---

## 🎯 Next Steps After Setup

Once GitHub Actions is running:

1. ✅ **Watch first run** complete successfully
2. ✅ **Enable branch protection** on main
3. ✅ **Add status badge** to README
4. ✅ Optional: Set up Codecov for coverage tracking
5. ✅ Optional: Add more workflows (deployment, releases, etc.)

---

## 📋 Checklist

Before pushing:

- [ ] `.github/workflows/test.yml` exists
- [ ] `.env.ci.example` exists  
- [ ] `.env.ci` exists
- [ ] `docker-compose.ci.yml` exists
- [ ] `make ci-test` works locally
- [ ] Code committed
- [ ] Ready to push!

After pushing:

- [ ] Go to Actions tab
- [ ] Watch workflow run
- [ ] Check results
- [ ] Optional: Set up branch protection
- [ ] Optional: Set up Codecov
- [ ] Optional: Add badges to README

---

**🎉 Your CI/CD is ready to go! Just push and watch it work!**
