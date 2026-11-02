# Continuity — Environment and Release Roadmap

**Status: PLANNED — not configured, deployed, or approved.**
**Roadmap priority:** Complete environment isolation and release controls **before** promoting the new Canvas and relationship functionality to the public production site.
**Planning checkpoint:** November 1, 2026; local feature implementation at `22f24d5`.

## Target environments

| Concern | Development and QA | Staging | Production |
| --- | --- | --- | --- |
| Frontend | Local browser preview | GitHub Pages (`lnafi26.github.io/Continuity/` is a *proposed* URL; verify before configuration) | Existing Cloudflare Pages-hosted Continuity site |
| Source / release | Protected local feature branches and tests | Dedicated staging branch or CI deployment workflow | Approved production release branch / deployment workflow (exact source branch to audit and decide) |
| Database and Auth | Disposable local Supabase | Separate hosted Supabase **staging** project with synthetic QA identities/data | Existing production Supabase project, with production user data |
| AI inference | Approved offline/local or explicitly isolated tests | Private Hugging Face Space `lnafi/Continuity-Inference-Staging`, connected only behind a secure server-side gateway | Separate production inference only when independently reviewed and authorized |
| Data | Local and disposable | Fictional/synthetic test records only | Real data under production access rules |

A public GitHub Pages staging site is **not private**. It must never expose Supabase service-role keys, Hugging Face tokens, client secrets, or confidential records. Public browser-facing keys alone do not grant access: enforce RLS, least privilege, and correct auth configuration. Any private staging inference requests must pass through an authenticated server-side proxy; do not call a private Space directly with a secret embedded in JavaScript.

## Required milestones and acceptance gates

### E1 — Inventory and freeze boundaries (pending)

- [ ] Verify the actual GitHub Pages and Cloudflare Pages repository/branch/build settings before changing either deployment.
- [ ] Audit current production Supabase usage, Auth redirect URLs, OAuth settings, allowed origins, domain configuration and schema migration history **read-only**.
- [ ] Record current production release, rollback route, and environment ownership. Keep the hosted project untouched during the audit.

### E2 — Provision isolated staging (pending; requires separate authorization)

- [ ] Configure GitHub Pages from a designated staging branch/workflow, ensuring `/Continuity/` base paths, assets and auth callbacks function as intended.
- [ ] Provision an entirely separate staging Supabase project; apply reviewed migrations **to staging only**; enforce RLS and environment-specific Auth redirect URLs.
- [ ] Use fabricated staging identities, events, tasks, relationships and sample sources only; prohibit production data copies.
- [ ] Connect the existing **private** `lnafi/Continuity-Inference-Staging` Space through a secure, approval-gated backend. Keep provider tokens server-side; do not enable inference automatically.

### E3 — Automated verification and review gates (pending)

- [ ] Require JavaScript/frontend regressions, migration/schema checks, authentication and RLS/API isolation checks, and browser QA for staging changes.
- [ ] Verify sign-in/sign-out, A/B account isolation, relationship create/cancel/delete, refresh persistence, and Inspector/Canvas navigation on staging.
- [ ] Exercise staging failure modes (missing/invalid data, unavailable inference, stale sessions, network interruption) and confirm that existing histories remain viewable without fabricated connections.
- [ ] Verify staging deploys never trigger a Cloudflare production deploy and cannot access production database credentials.

### E4 — Manual production promotion (pending; **not authorized**)

- [ ] Choose and document production release branch/tag strategy, protection rules and explicit approval gate.
- [ ] Review the production migration plan, migration-history reconciliation, rollback strategy, backups, secret handling and data protections **before** any production SQL execution.
- [ ] Deploy to Cloudflare Pages only after a reviewed staging release and explicit owner approval; separately authorize any production database migration.
- [ ] Independently review and authorize a production Hugging Face inference service; the staging Space must not silently become production.
- [ ] Complete production smoke checks and record release/rollback details without automatically promoting the next staging commit.

## Delivery order and boundaries

1. Continue local Canvas refinement and browser QA on feature branches.
2. Establish E1–E3 so **GitHub Pages is the ongoing staging environment** with a wholly isolated backend.
3. Keep **Cloudflare Pages as the production environment**, updated only through the E4 manually approved release procedure.

**Do not** push, merge, trigger Pages builds, modify the hosted Supabase database, activate production inference, or deploy as part of writing this roadmap. This document describes an intended architecture, not a claim that these services have been configured.
