# Continuity — gated production releases

## Current deployment boundaries

- `staging` pushes run the test-gated Night Observatory GitHub Pages workflow.
- `main` is protected; production changes require a reviewed `staging` → `main` PR.
- The Cloudflare Pages production project must use Git integration, with **production branch `main`**, automatic production deploys enabled, and **preview branches None**.
- This release-preparation milestone **does not** change Cloudflare settings or publish application features to production.

## Production build contract

Set Cloudflare Pages build settings (when preparing the first production readiness PR):

- **Root directory:** repository root (unset)
- **Framework:** None
- **Build command:** `python3 scripts/build_production_site.py --output dist/production`
- **Build output directory:** `dist/production`

The builder reads `deploy/production-release.json`:

- `"mode": "holding"` (default): output exactly `deploy/production/index.html` into the build directory.
- `"mode": "synthetic-preview"` (future explicitly approved release): publish the public-safe synthetic Night Observatory preview through the same allowlisted builder as staging.
- Any unsupported mode, missing source, network API, unsafe assets, unexpected content, or pre-existing nonempty output fails the build.

The PR workflow **Validate production release** enforces `staging` as the PR source, runs JS and Python tests, and builds/verifies the production artifact. Once GitHub records a successful PR check, configure `main` ruleset to **require that status check** before merging.

Do not switch the release mode merely to test CI. The first readiness PR should keep `holding` and preserve the same public holding page. Separately approve any change to `synthetic-preview` mode; it is publicly accessible, even with a noindex meta tag.

No real user accounts, Supabase config, OAuth tokens, backend services, or Hugging Face inference are included in either static release mode. A later full application production release will require a separately reviewed build policy, credentials configuration, access-control review, and user approval.

## Expected workflow after setup

1. Develop and validate a milestone on a feature branch.
2. Promote to `staging` (automatic GitHub Pages build/deployment).
3. Review the live staging build.
4. Open a `staging` → `main` PR, and wait for required production checks.
5. Merge the approved PR. Cloudflare Pages Git integration builds the versioned production release mode from `main` automatically.

Never push directly to `main`, force-push either release branch, or publish the whole `frontend/` directory without a separate security review.
