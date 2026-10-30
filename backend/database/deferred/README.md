# Deferred database work

The processing-jobs SQL was originally stored under
`supabase/migrations/` and explicitly marked as undeployed.

It has been moved here unchanged, outside Supabase's
automatic migration discovery path.

Do not execute it until the processing pipeline and
source-revision semantics have been reviewed.

## Migration baseline status

- The original initial schema exists in Supabase.
- Supabase has no recorded project migration history.
- B1 privilege hardening was applied manually and verified.
- The initial migration must not be replayed against the
  existing database.
- A future versioned migration must represent B1 privileges
  for new database environments.
- Migration reconciliation requires separate verification.

Do not enable automated GitHub database deployments yet.
