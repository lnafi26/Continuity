# R0.3A — Durable processing job ledger (not yet wired into processing)

**Current status: backend-only building block, not deployed.** Do not apply the
new migration to the existing Supabase database until separately reviewed and
authorized. Do not enable `CONTINUITY_ENABLE_LEGACY_PIPELINE`.

## Intended behavior

- A job is scoped to one owner and one source item (only `extract` stage for now).
- `enqueue_extraction` inserts only when the source is owned and not extracted;
  a uniqueness constraint rejects duplicate schedules. Reprocessing content
  revisions still needs a revision-aware design before enabling execution.
- `claim_next` uses `FOR UPDATE SKIP LOCKED` plus a random lease token, tracks
  attempts, and recovers jobs abandoned beyond their lease deadline.
- `mark_succeeded` or `mark_failed` accepts only the current unexpired claim.
  A stale worker cannot claim success in the ledger.
- Failure codes come from a fixed allowlist; raw exception messages, source
  text, prompts, emails, or authentication information are **never recorded**.
- Failed jobs wait at least 30 seconds between attempts, with exponential
  backoff. The maximum attempt count is 6, then failure is terminal pending
  a future explicitly authorized reset.
- Status lookups are scoped by owner, and the database applies a composite
  source owner foreign key. The table has RLS enabled but no browser grants.

## Lifecycle

`queued` → `running` → `succeeded` (only after successful work)

`running` → `retry_wait` (transient failure / expired lease) → `running`

`running` → `failed` (retry attempts exhausted; intervention required)

## Important limits / integration prerequisites

The functions do not currently run automatically, persist jobs, or access a
real database until an authorized caller invokes them and the migration has
been applied. R0.3B must integrate with atomic extraction, ensure database writes
are also fenced by current job lease, reconcile the case of a successful
extraction commit followed by an interrupted job acknowledgement, establish
source-version semantics, and add live PostgreSQL integration/concurrency tests.

No automatic retries of Gmail, Google, or Hugging Face operations are enabled.
No frontend UI, background worker, dashboard endpoint, or API endpoint exists.
`get_status` is only a backend function, not permissioned HTTP access.

## Verify locally (no network or DB)

`python -m unittest discover -s backend/tests -p 'test_*.py' -v`

The tests mock psycopg and inspect query restrictions/claims, so they cannot
prove live PostgreSQL transaction or concurrency behavior. Do not confuse them
with production readiness.
