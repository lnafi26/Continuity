# R0.2 — Atomic per-source extraction (first job reliability increment)

Scope: inherited **disabled** extraction stage's output writer only. No change
activates Gmail, Calendar, model providers, the legacy `/pipeline/run` route,
or the future reviewed/evidence-backed persistence workflow.

- One `psycopg.connect` context/transaction per source item: lock an authorized
  linked source row, check completion, check for user edits, clean up existing
  unedited partial AI output, insert normalized events and actions, then stamp
  `extracted_at` and `processing_status` in the **same transaction**.
- A failed SQL statement or marker update rolls the entire transaction back.
  A retry may safely regenerate the same item; an already-completed source is
  skipped under lock rather than duplicated.
- If user-edited output exists on a pending source, abort rather than silently
  overwrite/copy/duplicate it. This requires a future reconciliation workflow.
- The stage isolates one failed item, returns nonzero for any failures, and
  prints no raw exception messages; subsequent items are attempted.
- No external calls, live DB connections or writes occur in the regression
  tests; one fake transaction ensures the intended order and failure paths.

Limitations: the disabled inherited stage still writes metadata-derived events
without Evidence Engine review. Do not activate it for real data. This does not
implement durable job IDs, per-item error/audit records, operational metrics,
backoff/retries, globally exactly-once processing, stale-lock recovery, or
user-scoped reviewed snapshots. Multi-stage pipeline dependency handling and
future persisted candidate approval remain separate R0 milestones.

Run: `python -m unittest discover -s backend/tests -p 'test_*.py' -v`
