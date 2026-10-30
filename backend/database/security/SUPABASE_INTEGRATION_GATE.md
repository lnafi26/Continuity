# Continuity — Supabase integration safety gate

Status: NOT AUTHORIZED FOR AUTOMATIC DATABASE DEPLOYMENT.

The linked Supabase project currently has two migration
versions recorded as applied:

- 20261016000000_initial_schema
- 20261030212002_continuity_b1_privilege_hardening

The GitHub staging branch contains those two migrations.

The GitHub main branch still contains the deferred
20261017000000_processing_jobs.sql migration and does
not yet have the reconciled B1 migration.

Do not enable the Supabase "Deploy to production" option
while this mismatch exists.

Integration constraints:

- Preserve main and its production holding release.
- Do not run supabase db push, db reset, or migration up.
- Do not apply the deferred processing_jobs migration.
- Do not introduce database write credentials into CI.
- Keep automatic branching disabled pending separate approval.
- Keep the Hugging Face inference staging Space separate.
- Use working directory "." when integration is eventually
  authorized, because supabase/ is at the repository root.

Before reviewing integration readiness, fetch origin/main
and origin/staging, then run:

    python3 scripts/check_supabase_integration_gate.py

A passing migration preflight is necessary but not sufficient
authorization for deployment.

GitHub Actions checks cannot prevent an independently
configured Supabase native integration from running.
Its deployment settings must also be reviewed explicitly.
