# Deferred database work

The processing-jobs SQL was originally stored under
`supabase/migrations/` and explicitly marked as undeployed.

It has been moved here unchanged, outside Supabase's
automatic migration discovery path.

Do not execute it until the processing pipeline and
source-revision semantics have been reviewed.

## Migration baseline status

- The original initial schema exists in Supabase.
- The initial schema is recorded as applied remotely:
  `20261016000000`.
- B1 privilege hardening was applied manually and verified.
- Its reviewed migration is recorded as applied remotely:
  `20261030212002`.
- Both migration versions are reconciled between local and
  remote history; neither was replayed during reconciliation.
- The `processing_jobs` migration remains deferred and must
  not be applied without separate authorization.

Do not enable automated GitHub database deployments yet.
