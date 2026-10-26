# R0.1 — Inference failure boundary (first increment)

Scope: `backend/intelligence/router.py` only, with no database, frontend,
network or Hugging Face Space changes. Fault-injection tests are local-only.

## Invariants

1. An invalid task or malformed caller payload is a `ValueError` before any provider call.
2. A failing primary provider causes a deterministic offline fallback. The
   existing `RouterResult.reason` stays `primary_failed_validation_or_execution`.
3. If **both** the primary and the offline fallback fail (or the offline fallback
   alone fails), the router raises `InferenceUnavailableError`. It **must not**
   fabricate events, declare a successful inference, or silently swallow the error.
4. `InferenceUnavailableError.to_dict()` contains safe fixed metadata (`code`,
   `message`, `task`, `primary_configured`), **never** exception messages, source
   text, payloads or provider credentials. This object is not yet a public API.
5. A single failure must not poison a reusable router: a later successful request
   must still work.

This does **not** yet provide retry queues, timeouts for arbitrary providers,
user-facing API error conversion, circuit breakers, database atomicity, job
checkpoints, production monitoring, or whole-app failure containment.

Next increments: define uniform HTTP/API error envelopes with distinct
transient/persistent failures, then durable and idempotent job checkpoints and
component-level frontend recovery. Keep the inherited pipeline disabled.

Test: `python -m unittest discover -s backend/tests -p 'test_*.py' -v`.
Expected full repository total after this patch: **124 tests**, if the
previous 114 tests are unchanged.
