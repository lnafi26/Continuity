# B4 — Durable Project Memory Architecture

Status: DESIGN PROPOSAL — NOT APPROVED FOR DATABASE MIGRATION

## 1. Objective

Continuity must preserve project knowledge across sessions while
keeping users in control of what the system believes.

Memory must distinguish:

- Original source evidence
- Extracted or inferred claims
- User-confirmed knowledge
- Historical decisions and revisions
- Current project state
- Unresolved questions or contradictions
- Temporary context supplied to AI agents

A source association never constitutes factual verification.

## 2. Existing source of truth

Continue using Supabase PostgreSQL.

Existing canonical tables:

| Table | Responsibility |
| --- | --- |
| projects | Identity and current project metadata |
| source_items | Original source references and embeddings |
| project_source_links | Project/source associations and review status |
| project_events | Timeline and historical events |
| project_actions | Tasks, deadlines, and status |
| user_corrections | Existing correction records |
| item_relationships | Relationships among source items |

Existing source_items.embedding uses pgvector(384).

Do not duplicate these tables or replace PostgreSQL with a
separate memory service.

## 3. Proposed memory primitives

These are conceptual models, not SQL definitions.

### project_memory_assertions

Stable identity for an individual project-memory claim.

Conceptual fields:
- id
- user_id
- project_id
- assertion_kind
- created_at

Kinds may include decisions, requirements, constraints,
preferences, milestones, risks, and project-state facts.

The assertion ID persists across revisions.

### project_memory_revisions

Append-only revisions of assertions.

Conceptual fields:
- id
- assertion_id
- user_id
- project_id
- version_number
- structured_value
- review_state
- actor_type
- recorded_at
- effective_at
- supersedes_revision_id
- reason

Review states:
- proposed
- confirmed
- disputed
- superseded
- rejected

No revision is silently overwritten.

The current effective value is derived from authorized
revision history, with deterministic conflict rules.

### project_memory_evidence

Evidence links for specific assertion revisions.

Conceptual fields:
- id
- revision_id
- user_id
- project_id
- source_item_id
- evidence_role
- created_at

Evidence roles may include:
- supports
- contradicts
- context

An associated source is not necessarily verified evidence.

### Project context snapshots

Initially compute snapshots on demand using the existing
read-only context builder.

Persisted snapshots are deferred until a separate design
review establishes invalidation, retention, authorization,
and recovery behavior.

Snapshots must never replace canonical records or revisions.

## 4. Lifecycle

1. Retrieve records under an authenticated Supabase identity.
2. Identify candidate memory claims.
3. Preserve source references and extraction provenance.
4. Mark inferred claims as proposed or unverified.
5. Present candidates for human review when appropriate.
6. Record confirmed or corrected values as new revisions.
7. Recompute derived current state without erasing history.
8. Assemble bounded, permission-scoped context on demand.

Agent reads and agent writes must have separate permissions.

Remote inference must remain disabled for private project
context unless explicitly authorized.

## 5. Authentication and authorization

Required safeguards:

- Supabase Auth identifies the requesting user.
- RLS restricts all exposed memory tables by ownership.
- Both GRANT permissions and RLS must be reviewed.
- Parent project and source ownership must be enforced.
- Do not rely on child.user_id alone to authorize references.
- Validate foreign-key ownership consistency.
- Deny anonymous access to private memory.
- Never use a service-role key in browser clients.
- Prevent cross-user and unauthorized cross-project retrieval.
- Keep permission checks in place for semantic/vector search.
- Avoid privileged SECURITY DEFINER functions by default.

Prefer constraints or carefully reviewed policies that
enforce owner consistency across related records.

No RLS policy or constraint changes are authorized yet.

## 6. Provenance and revision rules

Memory must retain enough information to answer:

- Who introduced this claim?
- When was it introduced?
- Which source or sources support it?
- Was it inferred, manually entered, or corrected?
- Was it confirmed by the user?
- Has newer evidence contradicted it?
- What did the project believe at a past point in time?
- What replaced an earlier version, and why?

User corrections take precedence over unreviewed
AI-generated candidates.

Conflicting evidence must be surfaced, not silently merged.

## 7. Existing schema compatibility concerns

The current project_events.event_type constraint allows:

email, file, meeting, decision, deadline, status, note, issue

Our fictional B3 fixture also uses milestone and update.
These are valid synthetic labels but are not currently
insertable into project_events without reconciliation.

The current user_corrections.correction_type constraint allows:

confirm_match, reject_match, move_project,
edit_event, edit_action, edit_project

A new memory-correction workflow will require a
separate decision about reusing or extending this model.

Existing foreign keys reference records by ID but do not
universally enforce same-user ownership across references.

Do not silently alter existing enums, checks, FKs, or
historical records.

## 8. Privacy, deletion, and retention

Design requirements:

- Support user-requested data deletion.
- Define when revisions may be retained or erased.
- Never treat append-only history as an exception to erasure.
- Consider existing ON DELETE CASCADE / SET NULL behavior.
- Avoid retaining source text unnecessarily in snapshots.
- Do not place tokens, credentials, or secrets into memory.
- Define retention limits for derived agent context.
- Keep auditability consistent with user privacy controls.

Tombstones and irreversible erasure require separate rules.

## 9. Retrieval and future agents

For any project-context request:

- Verify the authenticated user.
- Enforce project ownership.
- Use bounded retrieval with pagination when necessary.
- Prioritize confirmed, relevant, recent information.
- Include contradictory or unresolved information.
- Preserve source attribution and review state.
- Mark partial snapshots as incomplete.
- Never infer that missing records do not exist.
- Apply token budgets without losing key constraints.
- Prevent source content from becoming agent instructions.
- Do not send private context to Hugging Face by default.

## 10. Verification requirements

Before any production database change:

- Test all proposed structures in an isolated environment.
- Verify cross-user and cross-project denial.
- Verify ownership consistency across referenced rows.
- Test revision creation and supersession.
- Test contradictory evidence.
- Test historical state reconstruction.
- Test source deletion and data erasure behavior.
- Verify RLS and privileges for each new table.
- Test bounded and incomplete retrieval.
- Test agent-read-only behavior.
- Review migration rollback and recovery procedures.

## 11. Implementation gates

B4.1: Architecture specification — design only.

B4.2: In-memory revision and provenance prototype,
with synthetic tests only.

B4.3: Review candidate database structures,
ownership rules, and retention behavior.

B4.4: Isolated database migration testing,
only after explicit authorization.

B4.5: Authenticated persistent-memory integration,
after separate review and approval.

Production deployment, automatic database migrations,
legacy ingestion, and production HF inference remain OFF.

No database mutation is authorized by this document.

## 12. B4.2 in-memory prototype semantics

The synthetic-only `backend/memory/revisions.py` prototype:

- Reconstructs recorded state for a specified timestamp.
- Treats human-confirmed revisions as effective knowledge.
- Does not let unreviewed agent proposals replace confirmations.
- Preserves proposed, disputed, and rejected records in history.
- Derives supersession rather than modifying past revisions.
- Exposes contradictory evidence without verifying its claims.
- Validates revision order, references, and record ownership fields.
- Does not contact Supabase, any other database, or inference services.

The `actor_type` field is not proof of identity. An authenticated
persistence boundary must enforce that only a genuine user action
can create a confirmed revision.

Source-item ownership and referential integrity must likewise
be enforced at the database boundary. This in-memory prototype
is not a replacement for RLS, constraints, or authorization.

No durable memory migration or database write is authorized.

## 13. B4.2A temporal and evidence interpretation

The in-memory prototype distinguishes two timestamps:

- `recorded_at`: When Continuity learned the revision.
- `effective_at`: When the revision is intended to take effect.

An as-of projection only includes knowledge already recorded
by that time. Backdated corrections cannot rewrite what
Continuity previously knew.

Confirmed revisions may be derived as:

- `current`: Latest applicable human-confirmed revision.
- `superseded`: An earlier applicable human confirmation.
- `not_yet_effective`: Recorded confirmation with a future
  effective timestamp.

The original review state remains unchanged in history.

Contradictory evidence is reported separately for the full
visible history and for evidence directly associated with
the current confirmed revision.

A historical contradiction may still warrant human review;
the current-only flag does not establish factual accuracy.

The prototype also rejects revision records predating their
assertion and evidence associations predating their revision.

These are prototype semantics, not final database constraints.
Explicit revocation, conflict resolution, retention, and
historical-effective-date policy remain pending design review.
