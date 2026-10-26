# R0.6 — Worker Storage Failure Hardening

## Status

Implemented and locally validated.
Not deployed or enabled for unattended processing.

## Changes

- Added WorkerStorageUnavailableError.
- PostgreSQL errors during job claiming are sanitized.
- PostgreSQL errors during failure reporting are sanitized.
- Storage failures do not falsely report job success.
- Expired job leases remain recoverable through the ledger.

## Validation

- 187 automated tests passed.
- Simulated claim failure correctly raised a sanitized error.
- Simulated failure-reporting outage raised a sanitized error.
- Disposable PostgreSQL was paused and resumed successfully.
- The interrupted worker reported storage unavailability.
- An existing completed job retained its status and attempt count.

## Remaining limitations

- No background scheduler or automatic polling.
- No lease heartbeat or renewal.
- No source revision-aware reprocessing.
- No production database authorization design.
- No guaranteed exactly-once external side effects.
- The inherited unfenced extraction path remains available.
- Infrastructure failures outside the covered PostgreSQL
  boundaries may still propagate.

## Safety

Keep CONTINUITY_ENABLE_LEGACY_PIPELINE=false.

Do not deploy workers, connect real user data, or apply
pending migrations to live Supabase without explicit approval.
