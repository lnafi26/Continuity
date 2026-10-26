# R0.4 — Controlled Offline Extraction

## Status

Manually invoked extraction workflow implemented and tested.
Not deployed or enabled for production.

## Components

- `backend/jobs/source_reader.py`
  - Retrieves the source for an active leased job.
  - Checks job identity, ownership, attempt, token, and expiration.
  - Confirms ownership of the source, link, and project.

- `backend/jobs/extraction_worker.py`
  - `prepare_claimed_extraction()` retrieves the authorized source
    and generates candidates through the offline ModelRouter.
  - `process_one_claim_local()` commits those candidates through
    the R0.3C lease-fenced extraction writer.
  - Database writes are restricted to the disposable local
    PostgreSQL test endpoint.

## Successful processing sequence

1. An external caller enqueues and claims a job.
2. The source reader validates the active claim.
3. The offline router prepares extraction candidates.
4. The fenced writer revalidates the lease.
5. Events, actions, source completion, and job success
   are committed in one PostgreSQL transaction.

## Validation

- 176 automated regression tests passed.
- Authorized source retrieval tested against PostgreSQL.
- Invalid lease tokens and incorrect ownership rejected.
- Offline preparation produced candidates without writes.
- End-to-end synthetic extraction completed successfully.
- Earlier R0.3C tests verified rollback and lease expiration.

## Outstanding limitations

- No automatic worker loop or scheduler.
- No automatic failure reporting from process_one_claim_local().
- No heartbeat or lease renewal for long-running inference.
- No source revision/version fencing.
- No automatic conflict resolution for user-edited outputs.
- The inherited unfenced extraction path remains available,
  but the legacy processing pipeline must stay disabled.
- The localhost database guard is a development restriction,
  not a substitute for production authorization.
- No universal exactly-once guarantee for external effects.

## Safety boundary

Do not enable the legacy pipeline, connect real user data,
apply the job migration to live Supabase, or deploy this worker
without separate review and explicit authorization.
