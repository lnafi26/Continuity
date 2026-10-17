# Continuity

**Evidence-backed, continuously updated project context for people and AI assistants.**

Continuity is an in-development platform for organizing conversations, source documents, development activity, decisions, open actions, and changes over time into distinct, interconnected **continuities**. It is intended to help both people and authorized AI agents understand what happened, what is happening now, what remains uncertain, and what needs attention next.

Continuity is **not production-ready**. Much of the application is still an inherited prototype being refactored and secured. The repository began as a fork of ThreadLinePMA; older `docs/` and pipeline modules retain historical context and must not be mistaken for the current product specification.

## Current state (October 2026)

| Area | Status |
| --- | --- |
| Supabase schema and owner-scoped row-level security | Initial migration written; development Supabase project initialized |
| Supabase account registration, login, and backend session verification | Implemented and locally tested |
| Local Flask backend with optional integrations decoupled | Implemented; core authentication can start without Google, database access, or model-provider credentials |
| Provider-independent `ModelRouter` | Implemented; offline-only by default |
| Hosted Hugging Face inference gateway | Private **staging** Space; tested using fictional data and explicit approval |
| Project naming, event/action extraction, and digest summarization | Synthetic hosted smoke tests completed; extraction still requires review |
| Source quotations and grounding-review helpers | Implemented; exact quotes may be anchored, but claims are **not automatically verified** |
| Evidence-candidate snapshots | Under development; local work in progress, not deployed or integrated into ingestion |
| Live ChatGPT or GitHub synchronization | Not yet implemented |
| Production agent context API / Timeline Canvas | Planned, not implemented |

The inherited `frontend/` contains placeholder project content. Do not interpret demonstration entries as actual user project data or as evidence that synchronization is operating.

## Design and safety principles

- **Active context, not just archives:** Capture current state, milestones, unresolved questions, blockers, and next actions alongside history.
- **Source-grounded history:** Keep source identifiers, timestamps, quotations, and review flags; distinguish proposals, decisions, implementation, testing, and deployment.
- **Human and agent access:** Plan read-only, authenticated, permission-scoped context retrieval first. Agent writes and background actions require separate authorization and audit controls.
- **Graceful failure:** Preserve the ability to inspect existing information when individual providers, network calls, or ingestion jobs fail; isolate failures and report freshness.
- **Privacy by default:** No automatic remote processing of real inboxes, client records, or conversations during the current staging phase. Fictional, manually approved test data only.
- **No invented confirmation:** A matching quotation proves that text occurs in a source, not that the model's conclusion is true.

## Repository layout

```text
backend/
  auth/            Flask API, Supabase authentication, optional Google OAuth
  intelligence/    ModelRouter, offline/hosted adapters, source review
  ingest/          Inherited Gmail/Calendar sync modules (not enabled)
  normalize/       Inherited source normalization
  dedupe/          Inherited work-only relevance filter; requires redesign
  embed/           Inherited semantic grouping primitives
  grouping/        Project grouping and naming
  extract/         Event/action extraction
  digest/          Project summaries
  tests/           Automated no-network and mocked integration tests
frontend/          Browser UI and Supabase login (includes placeholder data)
supabase/migrations/  Versioned initial schema
demo_data/         Synthetic fixtures; historical pipeline demonstrations
docs/              Architecture, older stage guides, security/review notes
```

## Local development

Requires Python 3, the packages in `backend/requirements.txt`, and a configured Supabase project if testing sign-in or authenticated API routes.

From the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r backend/requirements.txt
```

Copy `backend/.env.example` to `backend/.env` and configure the **minimum auth settings**:

```text
SUPABASE_URL=https://YOUR_PROJECT_REF.supabase.co
SUPABASE_PUBLISHABLE_KEY=sb_publishable_YOUR_KEY
CONTINUITY_ENABLE_LEGACY_PIPELINE=false
OAUTH_SERVER_PORT=8766
```

A Supabase **publishable key** is designed for browser use; **database passwords, provider access tokens, OAuth client secrets, and service-role keys are not**. Keep secrets in ignored local environment files or an external secret manager, never in frontend JavaScript or Git history.

The initial migration is stored at `supabase/migrations/20261016000000_initial_schema.sql`. The current development database had its initial schema applied manually; do **not** blindly re-run the migration against a populated database or assume migration-history tracking is reconciled.

Start the services in separate terminals:

```bash
# Backend — reads its port from backend/.env (8766 in the example)
python backend/auth/server.py

# Static frontend
python -m http.server 8000 --directory frontend
```

Open `http://localhost:8000`. Ensure `frontend/config/supabase-config.js` has the expected browser-safe project URL, publishable key, and `oauthBaseUrl` matching the local backend. Keep sensitive credentials out of this file.

**Important:** The inherited Google/Claude pipeline is disabled by default. Do not enable `CONTINUITY_ENABLE_LEGACY_PIPELINE`; the old work-only filtering, consent, error-recovery, and persistence paths require redesign before they can process real user data safely. The existing "Scan for updates" workflow is therefore **not** an available end-to-end production feature.

## Tests

```bash
python -m unittest discover -s backend/tests -p 'test_*.py' -v
git diff --check
```

Tests cover authentication, offline inference fallback, staging request guards, review and grounding, and pipeline isolation. Some hosted checks have been performed manually using fictional Mars rover data; automated tests are primarily local and mocked. Passing tests **do not** imply production readiness or complete fact verification.

## Private staging inference

`backend/intelligence/space_staging.py` connects to a separately deployed **private Hugging Face staging Space**, but makes no requests by default. A request needs explicit provider enablement and per-item approval, with a separate private-Space read token and Continuity service token. The staging gateway holds its own Hugging Face inference token. Do not paste tokens into code, issue reports, or chat.

`backend/intelligence/reviewed.py` can combine a normalized inference result with a local evidence review. Exact quote offsets and warning flags remain preliminary; records stay `needs_review`. Staging is **synthetic-only** at this stage. Production inference is not deployed.

See `backend/intelligence/SPACE_STAGING.md`, `docs/F1A_EVIDENCE_REVIEW.md`, and `docs/F1B_QUOTE_TRANSPORT.md`.

## Roadmap (high level)

1. Strengthen source-grounded extraction, review, evidence records, and resilience/error handling.
2. Import ChatGPT exports and reconstruct conversations into distinct project histories with source references.
3. Add read-only GitHub integration for commits, pull requests, issues, releases, and CI status.
4. Reconcile multiple sources, sync incrementally, and expose permission-scoped context snapshots to humans and agents.
5. Extend authorized connectors (email, calendar, and others), with durable sync and failure recovery.
6. Build the interactive **Timeline Canvas**: move and inspect distinct continuities and their contextual relationships without changing historical facts.
7. Prepare Cloudflare deployment, operational monitoring, security review, and user-access controls. `continuity.app` is a preferred domain, **not** a confirmed registration or active deployment.

This roadmap describes **intent**, not implementation. Historical stage documentation in `docs/` and `demo_data/` may include outdated ThreadLinePMA workflows, models, defaults, and schema references; treat them as legacy reference material during the ongoing migration.

## Development and attribution

Continuity is an ongoing rearchitecture of an inherited ThreadLinePMA prototype, with a broader focus on evidence-backed context for both people and AI agents. Before a public product launch or redistribution of inherited code/assets, verify the upstream project's applicable license and permissions.
