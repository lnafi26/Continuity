# Continuity — deployment environments

## Initial deployment foundations (not a product release)

- **Production**: Cloudflare Pages, GitHub `main`, build output `deploy/production`.
  Only a public-safe holding page is published. No Supabase, OAuth, or backend calls.
- **Staging**: GitHub Pages, GitHub Actions workflow `continuity-staging-pages.yml`
  stored on the repository default branch `update`. It manually checks out
  branch `staging` and publishes **only** `deploy/staging`.
  Only a public-safe holding page is published.
- **Development**: `feat/model-router`, locally served frontend.
  The locally committed C1 changes are **not** promoted or pushed by this setup.

## Manual setup in dashboards

1. GitHub repository **Settings > Pages**: set **Source: GitHub Actions**.
2. On the **Actions** tab, select **Deploy Continuity Staging** and click
   **Run workflow** from the default `update` branch.
3. Cloudflare **Workers & Pages > Create > Pages > Connect to Git**:
   connect `lnafi26/Continuity` with production branch `main`, no framework,
   root directory unset/repository root, build command `exit 0`, and
   build output directory `deploy/production`.
4. In Cloudflare **Settings > Builds > Branch control**, verify production
   is `main` and disable automatic preview deployments for other branches.

Do not change Cloudflare build output to `frontend` or deploy the inherited
application until a separate security/privacy review and explicit authorization.
Before functional staging, create isolated or synthetic-data configuration.

Cloudflare Pages and GitHub Pages publicly serve the uploaded artifact.
A `noindex` tag is not access control.
