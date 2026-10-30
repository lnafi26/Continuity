# B1 — Supabase privilege hardening

Applied: 2026-10-30

Supabase project: Continuity

## Change

The reviewed SQL in `b1_privileges.review.sql` was applied
manually through the Supabase connection.

- Revoked TRUNCATE, TRIGGER and REFERENCES privileges from
  anon and authenticated on nine application tables.
- Revoked client EXECUTE privileges on handle_new_user()
  and rls_auto_enable().
- Preserved authenticated CRUD privileges.
- Preserved the existing RLS policies and internal triggers.

## Verified after application

- Both client roles have no TRUNCATE, TRIGGER or REFERENCES
  permissions on the nine reviewed application tables.
- Authenticated CRUD privileges remain available.
- Both privileged functions deny client EXECUTE access.
- Their database triggers remain enabled.
- All ten application tables retain RLS.
- Profile, project and event row counts were unchanged.
- Supabase's privileged-function execution warnings cleared.

## Outstanding work

- Reconcile the pre-existing database with migration history.
- Do not automatically execute the deferred processing_jobs
  migration.
- Review cross-record ownership constraints and policies.
- Review leaked-password protection in Auth settings.
- Retain source_secrets as backend-only; it intentionally
  has no client RLS policies or data-access grants.

This file is an audit record, not a migration-history entry.

No production website deployment was performed.
