# Project Continuity — persistent project-record relationships (design checkpoint)

**Status:** schema design, not an applied migration. No live data change is authorized by this document.

## Confirmed live schema (November 1, 2026)

The connected Continuity Supabase project contains `projects`, `project_events`,
`project_actions` and `item_relationships`. There is no dedicated persisted table
for event/action dependency, handoff, divergence, or convergence. RLS is enabled
on the existing tables. `item_relationships` is a semantic *source-item* score
and must not be used as evidence of a causal project-record connection.

## Proposed persistence boundary

A dedicated `project_record_relationships` table with server-generated ID,
`user_id`, `project_id`, `kind`, `state`, `statement`, typed endpoint columns
(`from_event_id`, `from_action_id`, `to_event_id`, `to_action_id`), and server-owned
confirmation information. Both endpoint pairs have **exactly one** non-null ID.
Four kinds are permitted: dependency, handoff, divergence, convergence.

The first supported proof path should be **explicit user confirmation** only.
Source-evidence relationships need a separate accepted-evidence linkage and
review trail; arbitrary source-item similarity or user-supplied evidence IDs
must never automatically confirm causation.

## Security invariants to enforce in the database, not only JavaScript

1. Enable RLS and explicitly grant the minimum required privileges; revoke
   grants to `anon` and unnecessary update privileges from `authenticated`.
2. Require `auth.uid() = user_id`, with a server-established confirmation actor
   and timestamp. Do not accept arbitrary `confirmed_by`/`confirmed_at` claims
   as evidence of confirmation. Consider column-limited INSERT grants or a
   tightly scoped SECURITY INVOKER RPC for server-created proof metadata.
3. Enforce **same user AND same project** for each endpoint by composite foreign
   keys referencing `(user_id, project_id, id)` uniqueness on the event/action
   tables; also verify that `(id, user_id)` identifies an owned project.
4. Disallow self-relationships, missing endpoints, unrecognized kinds and
   unauthorized writes. Deletion and project/event/task cascade behavior must
   be tested; avoid duplicate logical links.
5. Avoid broad `FOR ALL` policies for this new table. Use explicit operations,
   validate owner scope on INSERT (`WITH CHECK`), and use user-scoped SELECT and
   DELETE policies. No unrestricted UPDATE of confirmation or endpoints.
6. Run tests for cross-account references, forged confirmation metadata,
   missing RLS/grants, unauthenticated access and data deletion behavior.

## Client-side integration (not enabled yet)

`continuity-relationship-data-boundary.js` is a pure, read-only shape adapter
for **future RLS-filtered rows**. It never authenticates or fetches data. The
existing `continuity-record-relationships.js` validator and visual bridge must
still classify the resulting bundle. The current dashboard does **not yet**
forward `project.user_id` or fetch relationship rows; no live connections are
expected at this checkpoint. Wire the boundary only after the server schema,
policies, metadata, and integration tests pass.

## Delivery sequence

1. Review and stage SQL migration locally using the Supabase CLI's supported
   migration creation workflow; do not apply to production.
2. Validate against an isolated local/staging Supabase database and verify RLS
   with multiple distinct authenticated identities.
3. Add authenticated relationship fetch to the same session-bound dashboard
   loading lifecycle, including sign-out/account-switch cleanup and errors.
4. Forward `user_id` from the authoritative authenticated project row, pass
   only RLS-verified relationship rows through the adapter, and verify that
   Canvas/Inspector/Navigator remain empty without confirmed relationships.
5. Add intentional creation and removal UI only after end-to-end verification.
