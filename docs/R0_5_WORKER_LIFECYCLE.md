# R0.5 — Controlled Worker Lifecycle

## Status

Implemented and validated locally using synthetic data.

Not deployed. No background worker or scheduler enabled.

## Components

### backend/jobs/one_shot.py

Provides `run_one_local(database_url, user_id=...)`.

The function:

1. Validates the disposable Docker database destination.
2. Claims at most one eligible extraction job.
3. Invokes the R0.4 offline extraction workflow.
4. Commits through the R0.3C lease-fenced writer.
5. Reports failures using approved diagnostic codes.
6. Schedules bounded retries through the job ledger.
7. Returns a sanitized result without source contents.

### backend/jobs/extraction_worker.py

Provides the shared local database guard and
the manually invoked extraction processor.

## Verified behavior

- Successful automatic job claiming and completion.
- Offline extraction with atomic PostgreSQL writes.
- Automatic failure reporting.
- Scheduled retry eligibility.
- Successful recovery on a subsequent invocation.
- Maximum retry exhaustion and terminal failure.
- No duplicate extraction output in recovery tests.
- Rejection of expired or invalid worker leases.

## Automated testing

185 unit and regression tests passed.

Additional PostgreSQL integration tests were executed
against synthetic records in Docker.

## Current limitations

- No background scheduling or unattended polling.
- Retries require another explicit worker invocation.
- No lease heartbeat or automatic renewal.
- No source revision-aware reprocessing.
- No automated resolution of user-edited conflicts.
- No production database authentication design.
- No production deployment or real-data validation.
- The inherited unfenced extraction path still exists.
- Database fencing does not guarantee exactly-once
  execution of external side effects.
- Unexpected infrastructure failures during claiming
  or failure reporting may still propagate to callers.

## Safety requirements

Keep CONTINUITY_ENABLE_LEGACY_PIPELINE=false.

Do not apply pending migrations to live Supabase,
enable production processing, or connect real user data
without separate review and explicit authorization.
