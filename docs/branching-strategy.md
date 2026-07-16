# Enterprise Branching Strategy

## Branch Structure

```
main (production)
  ├── develop (integration)
  │     ├── feature/AUTH-001-fix-redis-otp
  │     ├── feature/TOUR-002-real-images
  │     └── feature/PAY-003-razorpay-integration
  ├── release/1.1.0 (release candidate)
  ├── hotfix/FIX-critical-cors-issue
  └── Tags: v1.0.0, v1.1.0, ...
```

## Branch Rules

| Branch | Purpose | Deploys To | Protection |
|--------|---------|-----------|-----------|
| `main` | Production-ready code | ECS + CloudFront (production) | PR required, 1 approval, CI must pass |
| `develop` | Integration branch | Staging (if available) | PR required, CI must pass |
| `feature/*` | New features | None (local only) | No protection |
| `release/*` | Release candidates | Pre-production testing | PR to main required |
| `hotfix/*` | Critical production fixes | Direct to main (fast-track) | 1 approval, CI must pass |

## Workflow

### Feature Development
```bash
# Start feature
git checkout develop
git pull origin develop
git checkout -b feature/TOUR-005-buyer-chat-improvements

# Work on feature...
git add -A && git commit -m "feat(tour): improve Priya chat response UX"

# Push and create PR → develop
git push -u origin feature/TOUR-005-buyer-chat-improvements
# Create PR: feature/TOUR-005 → develop
```

### Release Process
```bash
# Create release branch from develop
git checkout develop
git pull origin develop
git checkout -b release/1.1.0

# Final testing, version bump
# Create PR: release/1.1.0 → main
# After merge → tag
git tag v1.1.0
git push origin v1.1.0

# Merge back to develop
git checkout develop
git merge main
git push origin develop
```

### Hotfix (Production emergency)
```bash
git checkout main
git checkout -b hotfix/FIX-cors-blocking-login
# Fix the issue
git commit -m "fix: CORS blocking login from new domain"
# Create PR: hotfix/FIX-cors → main (fast-track, 1 approval)
# After merge → tag patch version
git tag v1.0.1
```

## Naming Conventions

| Type | Pattern | Example |
|------|---------|---------|
| Feature | `feature/<TICKET>-<description>` | `feature/AUTH-001-fix-redis-timeout` |
| Bugfix | `bugfix/<TICKET>-<description>` | `bugfix/DASH-012-stats-cache-stale` |
| Hotfix | `hotfix/<TICKET>-<description>` | `hotfix/FIX-otp-500-error` |
| Release | `release/<version>` | `release/1.1.0` |

## Commit Message Format

```
<type>(<scope>): <description>

Types: feat, fix, docs, style, refactor, test, chore
Scopes: auth, tour, dash, admin, billing, infra, ci
```

Examples:
```
feat(tour): add real project images to tour viewer
fix(auth): handle Redis timeout gracefully in OTP request
docs(api): update Swagger descriptions for billing endpoints
chore(ci): add caching to GitHub Actions workflow
```

## CI/CD Pipeline

```
PR to develop:
  → Lint + Type Check
  → Run Backend Tests (183 tests)
  → Build Frontend (type check)
  → ❌ Block merge if any fail

Merge to main:
  → All above +
  → Build Docker image → Push to ECR
  → Deploy to ECS (force new deployment)
  → Build Frontend → S3 sync → CloudFront invalidation
  → Slack/Discord notification
```

## Setting Up Branch Protection (GitHub)

Go to: Repository → Settings → Branches → Add rule

**For `main`:**
- ✅ Require pull request before merging
- ✅ Require approvals: 1
- ✅ Require status checks: `test-backend`, `test-frontend`
- ✅ Require branches to be up to date
- ✅ Do not allow bypassing

**For `develop`:**
- ✅ Require pull request before merging
- ✅ Require status checks: `test-backend`, `test-frontend`
