# Project Continuity — persistent relationship schema staging checklist

**Status:** Deferred SQL draft and offline structural tests. This checkpoint
has **not** executed SQL against PostgreSQL, Supabase staging, or production.

## Before generating an official migration

1. Inspect the draft at `backend/database/deferred/project_record_relationships.draft.sql`
   alongside `docs/architecture/continuity-record-relationship-persistence.md`.
2. Confirm the target PostgreSQL version supports `NULLS NOT DISTINCT` and
   that the canonical tables have the reviewed `user_id`, `project_id`, and ID types.
3. After isolated database validation, create an official migration with the
   installed Supabase CLI's **`supabase migration new`** workflow. Do not
   manually guess migration naming or apply this deferred file to production.
4. Review Supabase Data API grants separately from RLS. Ensure `anon` has no
   access; `authenticated` has only column-limited INSERT, SELECT, DELETE.

## Must-run integration/security tests in an isolated database

- Two authenticated identities: A cannot read/delete B's relationships, nor
  insert a relation that references B's project, event, or action.
- A cannot point to another project owned by A (each endpoint must belong to
  the same `user_id` **and** `project_id` as the relationship).
- Insert with no token fails; anonymous SELECT returns no records.
- Authenticated clients cannot submit or update `confirmed_by`, `confirmed_at`,
  `state`, `id`, or `user_id` through the Data API; server defaults populate
  the proof actor and timestamp on an intentional INSERT.
- The database rejects event+action simultaneously on one side, missing typed
  endpoints, event-to-same-event and action-to-same-action links, duplicate
  same-kind endpoint pairs, unsupported kinds, and empty statements.
- Deleting an event/action or project cascades the corresponding relationships;
  deleting a relationship must not delete either endpoint.
- No frontend client call is permitted to mark a relationship confirmed
  without an explicit user action. Session switching/sign-out clears caches.
- Test SQL advisor warnings, post-migration `GRANT`s, RLS policies, and
  unauthorized mutations with two separately authenticated test accounts.

## Scope and limitations

This is a user-confirmed-only first slice. Source-evidence proof remains
unsupported in database persistence until an accepted-evidence review model
is designed. Client-side validators remain defense in depth, **not** database
access control. Do not wire this draft into the dashboard until staging tests
and a separately authorized database migration pass.
