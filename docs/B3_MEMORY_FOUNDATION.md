# B3 — Continuity Memory Foundation

Status: local read-only prototype, not deployed.

## Existing canonical database

Use Supabase PostgreSQL as the source of truth:

- `projects`: project identity and current description
- `source_items`: original source references and embeddings
- `project_source_links`: association and match-review status
- `project_events`: chronological events and decisions
- `project_actions`: outstanding and completed work
- `user_corrections`: user-directed corrections
- `item_relationships`: semantic and deterministic relationships

Existing `source_items.embedding` uses pgvector(384).

## Memory principles

1. Preserve source evidence separately from interpretations.
2. Do not treat confirmed source associations as verified claims.
3. Preserve historical records rather than silently overwriting them.
4. Track context freshness and retrieval scope.
5. Support future versioned project-state snapshots.
6. Require authenticated ownership enforcement and RLS.
7. Never send private project content to remote inference by default.
8. Keep agent memory retrieval read-only until separately authorized.

## Current implementation

`backend/memory/context.py` assembles temporary snapshots from
already-authorized records. It performs no database access.

The caller must enforce identity and ownership before fetching
records; the builder's ownership checks are defense in depth,
not a substitute for database authorization.

The prototype does not create durable memory, verify source claims,
or expose an API.

## B3.7 authenticated read-only retrieval

The local Flask backend now defines:

`GET /memory/projects/<project_id>/context`

This route:

- Requires a Supabase-authenticated end-user bearer token.
- Uses the user's token with the publishable API key.
- Relies on database RLS and explicitly scopes project queries.
- Retrieves at most 20 rows from each collection.
- Labels returned context as bounded and potentially incomplete.
- Returns no-store responses and sanitized errors.
- Performs no database writes or remote inference.

The HTTP endpoint is not connected to the frontend and the
Flask backend has not been deployed by the static Pages workflow.
All B3.7 retrieval tests are mocked; a live end-user retrieval
test is still required before claiming end-to-end readiness.

## Planned durable memory

A separately reviewed migration may introduce versioned,
source-linked memory assertions and context snapshots.

The design must define provenance, human confirmation,
supersession, deletion, retention, per-user authorization,
and cross-project visibility before applying schema changes.

No migration, database write, or remote inference is authorized
by this document.
