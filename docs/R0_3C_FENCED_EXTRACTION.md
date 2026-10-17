# R0.3C-A — Lease-fenced extraction, opt-in writer (not deployed)

**Status: new backend write path, no workers or API endpoints connected.**
Do not enable `CONTINUITY_ENABLE_LEGACY_PIPELINE` or apply migrations to live Supabase.

## What changed

The pre-existing `write_extraction_atomic` continues to serve the inherited,
disabled legacy stage. A distinct `write_extraction_with_claim_atomic` entrypoint
requires a `JobClaim` and uses the same event/action insertion transaction,
protected by a live lease in `public.processing_jobs`.

When the fenced entrypoint is called, it:

1. Validates the provided claim's user/source identity and attempt.
2. Locks the matching **job row first**, requiring running state, matching
   source and owner, token and attempt, and an unexpired lease using
   `clock_timestamp()` (not the transaction's frozen `now()`).
3. Locks the authorized, linked source row and checks it is unprocessed.
4. Rejects an extraction if user-edited events/actions already exist.
5. Replaces unedited generated rows and marks the source processed.
6. Updates the same claimed job to `succeeded` **inside the same transaction**,
   again requiring the lease to be valid at the time of acknowledgement.

Any exception—including the final lease check—rolls back extracted rows, the
processed marker, **and** the job acknowledgement together. No raw source
payloads or exception messages are written to the ledger.

## Limitations and next work

- This does not launch workers, ingest real data, or create any jobs.
- The old writer remains available to the disabled legacy extraction stage;
  do not enable it or allow it to compete with the new job workers.
- Separate **real PostgreSQL tests** are required to prove rollback behavior,
  lease reclaims, and concurrency. The supplied unit tests mock psycopg.
- Job claim longevity/heartbeat, source revision-aware requeueing and manual
  conflict-resolution workflows are NOT yet implemented.
- Not a universal exactly-once guarantee for external effects. The fence
  controls only database work within this transaction.

Run local no-network regression suite:

`python -m unittest discover -s backend/tests -p 'test_*.py' -v`
