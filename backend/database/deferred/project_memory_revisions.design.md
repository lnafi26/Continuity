# Project Continuity — Deferred revision storage design (B4)

**Status: DESIGN REVIEW ONLY. NOT APPROVED FOR EXECUTION.**

This document describes a possible durable model for the existing `backend/memory/revisions.py` projection contract. It is not a production migration, not a local migration, and not permission to modify Supabase. The existing memory endpoint remains an ephemeral, bounded, authenticated read of project events and actions. The synthetic revision viewer remains disconnected from user data.

## Candidate tables and ownership

| Table | Purpose | Authorization boundary |
| --- | --- | --- |
| `project_memory_assertions` | Identity and creation time of a project-scoped assertion | Composite FK `(user_id, project_id)` to `projects` |
| `project_memory_revisions` | Append-only proposed, confirmed, disputed, or rejected revision records | Composite FK `(user_id, project_id, assertion_id)` to assertions and scoped self-FK to the predecessor |
| `project_memory_revision_evidence` | Role-labeled source references, not factual verification | Scoped revision FK, owner-scoped `source_items` FK, and project-linked `project_source_links` FK |

All three candidate tables have explicit `REVOKE ALL` for `PUBLIC`, `anon`, and `authenticated`; only owner-scoped `SELECT` is granted to `authenticated`, with RLS and a parent-project ownership check. No client-facing write policies, public mutator functions, or service-role browser use are proposed. A server-side privileged role would still bypass RLS if granted access; never treat RLS as an authorization boundary for privileged operations.

## Compatibility with the existing Python projector

The model is designed around `project_memory_at(assertion, revisions, evidence, *, as_of)` in `backend/memory/revisions.py`. Each revision has a sequential `version_number`, scoped `supersedes_revision_id`, review state, actor type, structured value, and distinct recorded/effective timestamps. Evidence has a source ID and a role of `supports`, `contradicts`, or `context`. A source link never proves a claim. The projector derives current/superseded states from confirmed revisions and time; it does not mutate inputs or persist them.

**Do not synthesize revisions for existing project events or tasks.** Existing project records are not automatically assertions, and no backfill is authorized.

## Mandatory review blockers before any SQL is executed

1. **Live/local schema inspection:** Verify exact column types, existing composite unique indexes, RLS grants, ownership integrity, and legacy rows. The audit only provided a keyword inventory; it did not include complete DDL. Obtain a read-only migration review and then test against an isolated, disposable local database, never against the preserved QA stack initially.
2. **Trusted write path:** There is no implementation for creating assertions, revisions, or evidence. No direct browser insert is allowed. A future authenticated, transactional API must derive `user_id`, `actor_type`, `confirmed_by`, `confirmed_at`, and `recorded_at` from trusted context. A row shape CHECK alone cannot prove that a human clicked Confirm; a server/service role bypasses RLS and requires explicit authorization checks.
3. **Sequential and temporal invariants:** A FK ensures the predecessor belongs to the same assertion, but cannot alone enforce `predecessor.version_number = new.version_number - 1`, nondecreasing `recorded_at`, existence only after assertion creation, evidence creation after revision recording, effective-time semantics, or concurrency ordering. Enforce these under a serialized/locked transaction and test rollback and concurrency. Do not weaken `project_memory_at` validation.
4. **Deletion, privacy, and retention:** The draft deliberately uses `ON DELETE RESTRICT` for evidence-to-source references. Decide whether users may unlink/delete source items or projects, how evidence history is handled after deletion, and what privacy/erasure obligations apply. The chosen actions must not silently destroy revision provenance or permanently obstruct legitimate account deletion. Review cascades and restrictive references together before implementation.
5. **Authorization and Data API exposure:** Decide whether revision tables belong in `public` with owner-only `SELECT` or an unexposed internal schema with authenticated API projections. Confirm the Data API grants and run RLS cross-account tests with two independent users. Future reader must authenticate the bearer token, check project ownership and bounded pagination, return an explicit completeness flag, and never reveal unreviewed private source bodies.
6. **Approval gates:** Keep this SQL under `backend/database/deferred/`; do not move it to `supabase/migrations/`, change `scripts/check_supabase_integration_gate.py`, or use `supabase db push`, `db reset`, migration-up, or hosted deployment without separate explicit authorization. Only after the design is approved and tested should a reviewed migration be generated through the CLI (consult installed CLI's `--help` first).

## Next implementation stage

Build a **synthetic repository integration test** that maps stored-row-shaped fictional inputs to the existing projector and verifies invalid ownership, missing parents, invalid predecessor chains, and unverifiable source references fail closed. Only after the design blockers are settled should storage and live revision retrieval be considered.
