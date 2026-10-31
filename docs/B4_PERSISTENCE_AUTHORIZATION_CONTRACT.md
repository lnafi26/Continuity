# B4.3 — Persistent Memory & Authorization Contract

Status: DESIGN PROPOSAL — NO MIGRATION AUTHORIZED

Parent specification:
`docs/B4_DURABLE_MEMORY_ARCHITECTURE.md`

## 1. Objective

Translate Continuity's synthetic memory revision prototype
into a proposed PostgreSQL persistence and authorization model.

This document does not authorize database modifications,
new write endpoints, production rollout, or inference.

Supabase PostgreSQL remains the canonical database.

## 2. Proposed persistence model

### project_memory_assertions

One stable identity per project-memory claim.

Candidate attributes:

- id: UUID primary key
- user_id: UUID, non-null
- project_id: UUID, non-null
- assertion_kind: constrained text
- created_at: server-generated timestamp

An assertion's identity remains stable across revisions.

### project_memory_revisions

Append-only record of changes to an assertion.

Candidate attributes:

- id: UUID primary key
- assertion_id: UUID, non-null
- user_id: UUID, non-null
- project_id: UUID, non-null
- version_number: positive integer
- structured_value: JSONB
- review_state: constrained text
- actor_type: constrained text
- recorded_at: server-generated timestamp
- effective_at: timezone-aware timestamp
- supersedes_revision_id: nullable UUID
- reason: nullable text
- idempotency_key: nullable unique request identifier

A revision's original contents and review state
must not be silently modified.

Supersession is derived from authorized revision history.

### project_memory_evidence

Evidence attribution for a specific revision.

Candidate attributes:

- id: UUID primary key
- revision_id: UUID, non-null
- user_id: UUID, non-null
- project_id: UUID, non-null
- source_item_id: UUID, non-null
- evidence_role: supports / contradicts / context
- created_at: server-generated timestamp

An evidence association is not proof of a factual claim.

The source's review status and factual verification status
must remain separate concepts.

## 3. Cross-record ownership invariants

Every memory record must be consistently associated with
the authenticated owner.

Proposed constraints:

- Projects have a unique `(id, user_id)` pair.
- Assertions reference projects using
  `(project_id, user_id)`.
- Assertions have a unique `(id, user_id, project_id)` key.
- Revisions reference assertions using
  `(assertion_id, user_id, project_id)`.
- Revisions have a unique `(id, user_id, project_id)` key.
- Evidence references revisions using
  `(revision_id, user_id, project_id)`.
- Source references must preserve source ownership.
- Evidence should reference a project-associated source,
  not merely an arbitrary source belonging to the user.

Evaluate composite references to `project_source_links`
using `(project_id, source_item_id, user_id)`.

The required supporting unique constraints, on-delete
behavior, and implications for existing tables must be
reviewed before creating a migration.

An ordinary foreign key to a record ID alone does not
guarantee ownership consistency.

## 4. Authenticated read contract

- Verify the user's Supabase session.
- Enforce user and project ownership.
- Enable RLS for every exposed memory table.
- Deny anonymous access to private project memory.
- Review GRANT permissions separately from RLS.
- Keep queries bounded and project-scoped.
- Avoid privileged reads and service-role bypass.
- Apply equivalent authorization to vector retrieval.
- Return explicit incomplete or partial-history metadata.

The existing B3 read-only API remains unchanged until
a separate integration phase is authorized.

## 5. Human confirmation and writes

A client-supplied `actor_type = user` is not evidence
that a person approved an action.

Proposed write boundary:

1. An authenticated user explicitly submits an action.
2. The trusted write boundary verifies identity.
3. The boundary validates target project ownership.
4. It verifies that the user authorized this revision.
5. It checks version/concurrency expectations.
6. It assigns authoritative server-side metadata.
7. It appends the revision transactionally.
8. It returns a versioned confirmation.

AI-generated candidates may be proposed, but may not
silently become human-confirmed memory.

Prevent direct client writes from bypassing this boundary.

The choice of restricted database role, controlled
transactional endpoint, and permitted database operations
requires separate security review.

Do not assume a user JWT alone proves UI-level approval.

Do not introduce service-role bypass or SECURITY DEFINER
functions without a separate explicit design review.

## 6. Concurrency and atomicity

Candidate invariants:

- Unique `(assertion_id, version_number)`.
- An incoming edit states its expected base revision.
- Only one new head may succeed per base revision.
- Stale writes fail with a conflict response.
- Writes are atomic and retry-safe.
- Idempotency prevents duplicate confirmations.
- A revision references a valid predecessor belonging
  to the same assertion.
- Conflicting writes never silently overwrite history.

The transaction implementation and locking strategy
must be validated in isolated concurrency tests.

## 7. Temporal semantics

Continuity must distinguish:

- `recorded_at`: when the system learned something.
- `effective_at`: when the recorded change applies.

Two historical questions require different answers:

**What did Continuity know on October 1?**

Only revisions recorded by October 1 are eligible.

**What does Continuity now believe was true on October 1?**

Later-recorded corrections may inform the answer,
but must retain their later recording timestamps.

The current in-memory prototype primarily implements
the first question.

Full bitemporal retrieval requires further design.

Future-effective revisions must not become current early.

The order of concurrent confirmations, backdated
revisions, explicit revocations, and overlapping effective
periods requires a deterministic conflict policy.

## 8. Corrections, disputes, and revocations

Separate:

- Proposing an alternative
- Confirming a new value
- Disputing an existing value
- Rejecting a candidate
- Revoking an earlier confirmation
- Deleting private information

A rejected proposal is not a revocation.

A dispute alone does not establish a new fact.

Explicit revocation semantics must be designed before
persistent memory writes are enabled.

Existing `user_corrections` records must be reviewed for
compatibility; don't create parallel correction histories
without a reconciliation plan.

## 9. Retention, privacy, and deletion

Append-only means ordinary revisions preserve history.

It must not prevent lawful or user-authorized erasure.

Requirements:

- Define source and derived-data retention periods.
- Define project deletion cascades.
- Define deletion of linked sources and embeddings.
- Prevent erased information resurfacing from caches,
  summaries, snapshots, indexes, or agent context.
- Support redaction and permanent deletion as distinct
  operations.
- Avoid storing secrets and authentication tokens.
- Specify audit metadata retained after content deletion.
- Review backup retention and restoration implications.

No retention schedule is approved yet.

## 10. Retrieval scalability

The current B3 context reader uses bounded snapshots.

Persistent memory retrieval must specify:

- Stable cursor-based pagination
- Per-project scoping
- Deterministic ordering
- A complete-history retrieval mode
- Snapshot and page consistency
- Explicit truncation metadata
- Indexes supporting common filters
- Controlled token budgets for AI context
- No assumption that absent records do not exist

Derived summaries must not replace the underlying
canonical revision history.

## 11. Existing schema reconciliation

Before writing SQL:

- Review `projects` ownership constraints.
- Review `source_items` and associated connections.
- Review `project_source_links` ownership and status.
- Review `project_events` event-type constraints.
- Review `user_corrections` correction-type constraints.
- Review existing RLS, grants, and foreign keys.
- Review existing ON DELETE CASCADE and SET NULL rules.
- Confirm compatibility with B3's read-only context API.

B3's fictional `milestone` and `update` event labels
do not currently match the live `project_events`
constraint and must not be inserted without review.

## 12. Required security tests

Before authorization of any migration or write endpoint:

- Anonymous and unauthenticated write denial
- Cross-user assertion and revision rejection
- Cross-project reference rejection
- Cross-user source/evidence rejection
- Fake human-approval rejection
- Stale revision/write conflict rejection
- Duplicate request idempotency
- Transaction rollback on partial failure
- Future-effective revision handling
- Backdated correction handling
- Explicit revocation semantics
- User/project/source deletion behavior
- RLS and direct Data API access attempts
- No service-role or browser secret exposure
- No unauthorized inference or ingestion

Test these in an isolated database environment first.

## 13. Decision gates

B4.3A: This persistence contract — design only.

B4.3B: Finalize ownership and controlled-write strategy.

B4.3C: Finalize temporal, revocation, and deletion policies.

B4.4: Proposed migration and isolated database testing,
requiring explicit authorization.

B4.5: Authenticated write integration, requiring separate
approval.

Production inference, automatic database migrations,
legacy ingestion, and automatic production deployment
remain disabled.

This document authorizes no database mutation.

## 14. B4.3B controlled-write threat model

Status: PROPOSED DESIGN, NOT IMPLEMENTED.

### 14.1 Trust boundaries

Continuity distinguishes these actors:

| Actor | Intended permissions |
| --- | --- |
| Anonymous visitor | No private memory access |
| Authenticated project owner | Read authorized memory; explicitly request changes |
| Read-only AI agent | Receive approved bounded context; no writes |
| Proposal-capable AI agent | Submit candidate changes to a review queue |
| Human approval interface | Present exact changes and collect explicit decisions |
| Trusted application backend | Verify identity, authorization, and request integrity |
| Restricted persistence component | Execute narrowly authorized atomic operations |

An AI proposal cannot itself authorize a confirmed revision.

An authenticated browser session proves account identity,
not that a person personally reviewed a specific change.

The browser must not expose privileged database credentials.

The boundary must remain effective if a client directly calls
the API without using the intended application interface.

### 14.2 Proposed confirmation workflow

1. An agent or user creates an unconfirmed candidate.
2. The backend stores or temporarily holds the candidate
   with a stable identifier and immutable content digest.
3. The user receives a clearly labeled comparison showing
   the existing claim, proposed value, sources, and effects.
4. The user explicitly approves or rejects the proposal.
5. The backend authenticates the requester and checks
   project ownership and current revision version.
6. The backend validates a one-use approval challenge
   bound to the exact candidate, project, user session,
   intended operation, and expiry.
7. The trusted persistence component atomically verifies
   concurrency and appends the authorized revision.
8. The backend records the decision outcome and returns
   the committed revision identifier.

Approval challenges must be single-use, short-lived,
server-generated, and checked against server-side state.

A content digest detects a changed proposal between
presentation and submission; it does not independently
prove human presence.

For particularly sensitive operations, evaluate explicit
step-up user verification before persistence.

Agents must not receive approval credentials, backend
write credentials, or unrestricted authenticated browser
automation privileges.

A compromised browser or agent with equivalent control
of the user's session may still impersonate a UI action.
Stronger assurance requires an independently protected
approval factor or surface.

Do not describe a normal confirmation click as a
cryptographic human-presence guarantee.

### 14.3 Data API privilege boundary

Candidate strategy:

- Authenticate application users through Supabase Auth.
- Allow only approved memory reads through user-scoped RLS.
- Do not grant general browser-facing INSERT, UPDATE,
  DELETE, or TRUNCATE privileges on memory revision tables.
- Do not expose unrestricted memory mutation RPCs.
- Avoid application use of the Supabase service-role key.
- Do not permit public or authenticated callers to execute
  a privileged SECURITY DEFINER write function.
- Do not treat a caller-supplied actor_type as authoritative.

The trusted write mechanism is not yet selected.

Before implementation, compare:

A. A backend-only restricted PostgreSQL role, without
   BYPASSRLS, using a transaction-bound authenticated
   subject context that untrusted callers cannot set.

B. A narrowly granted SECURITY INVOKER transactional
   routine, accessible only through an independently
   protected backend identity and not directly through
   the public Data API.

For both approaches, demonstrate that the database
actually enforces the authenticated principal's identity.
Do not rely on a freely supplied user_id parameter.

A database role or session-setting design must be
tested for spoofing and connection-pool context leakage.

The implementation must prove that ordinary users
cannot directly bypass the approval workflow with
table writes or RPC execution.

Neither candidate is authorized for deployment yet.

### 14.4 Composite ownership and source integrity

The proposed ownership graph is:

Project (user_id)
  -> Assertion (project_id, user_id)
     -> Revision (assertion_id, project_id, user_id)
        -> Evidence (revision_id, project_id, user_id)
           -> Source item (source_item_id, user_id)

Candidate composite foreign keys must ensure:

- A revision cannot reference another user's assertion.
- Evidence cannot reference another user's revision.
- Evidence cannot attach a different project's revision.
- Evidence cannot reference another user's source item.
- An asserted project must exist and belong to the owner.

Existing project_source_links connect sources to projects,
but their review state may be pending, confirmed, or
rejected.

An evidence reference must record the state of the
project-source association when attribution occurs.

Consider validating an eligible association transactionally
rather than making all historical evidence depend on a
mutable project_source_links row.

Otherwise deleting or changing the source association
could unexpectedly erase evidence or distort history.

Do not assume a confirmed source association verifies
the underlying factual claim.

Cross-record consistency requires both structural
database constraints and authorization tests.

### 14.5 Transaction boundary and concurrency

An authorized revision write must:

- Validate the expected current revision.
- Reject a stale expected revision with a conflict.
- Reject unauthorized project and source references.
- Allocate a unique sequential version atomically.
- Enforce a valid predecessor relationship.
- Use server-assigned immutable identity and timestamps.
- Reject duplicate or replayed approval challenges.
- Deduplicate safe retries with an idempotency key.
- Commit revisions and evidence changes atomically.
- Roll back all partial changes on failure.

The exact locking and transaction mechanism remains
pending isolated-database evaluation.

### 14.6 Minimum negative security tests

Before enabling persistence, prove rejection of:

1. Anonymous revision writes.
2. Direct Data API writes by an ordinary user.
3. Unrestricted RPC calls by an ordinary user.
4. Agent-generated human confirmation metadata.
5. Stolen or reused approval challenges.
6. Approval submitted for different content.
7. Approval submitted for another project.
8. Cross-user and cross-project evidence references.
9. Unauthorized source associations.
10. Concurrent commits against the same base revision.
11. Partial writes that would leave orphan records.
12. Connection-pool identity-context leakage.
13. Deletion that unexpectedly retains private content.

A successful UI demonstration alone is insufficient
to establish write-path security.

### 14.7 References and status

Supabase guidance to review before implementation:

- https://supabase.com/docs/guides/database/postgres/row-level-security
- https://supabase.com/docs/guides/api/securing-your-api

B4.3B defines a proposed security contract only.

No new grants, policies, tables, functions, triggers,
endpoints, or database roles are authorized.

No persistent-memory write mechanism has been selected.

## 15. B4.3C revocation and retention contract

Status: PROPOSED DESIGN — NOT IMPLEMENTED OR APPROVED
FOR PERSISTENT STORAGE.

### 15.1 Memory lifecycle operations

Continuity must distinguish these operations:

| Operation | Meaning |
| --- | --- |
| Propose | Suggest a candidate memory |
| Confirm | Explicitly approve a value |
| Correct | Confirm a replacement value |
| Dispute | Challenge an existing claim |
| Reject | Decline an unconfirmed proposal |
| Revoke | Withdraw a previously confirmed claim |
| Archive | Hide inactive content without erasure |
| Redact | Remove protected content from selected records |
| Delete | Erase designated content and its derivatives |

These operations are not interchangeable.

In particular:

- Rejecting a proposal does not revoke a confirmation.
- Disputing a claim does not automatically invalidate it.
- Archiving is not deletion.
- Redaction is not necessarily complete erasure.
- Deletion must not be implemented as an ordinary
  invisible revision while retaining private content.

### 15.2 Explicit revocation

A confirmed claim may later be withdrawn.

Proposed behavior:

1. The user explicitly requests revocation.
2. The backend authenticates and authorizes the action.
3. The request identifies the current revision being revoked.
4. The backend verifies the expected current head.
5. The system records an authorized revocation operation.
6. The current effective state becomes revoked.
7. Historical revisions remain available unless erased.
8. A later confirmation may establish a new current state.

The revocation operation should identify its target,
reason if supplied, actor, recorded time, and effective time.

The exact schema is not selected.

Revocation must not silently reactivate an older
confirmation.

Example:

- V1: Confirmed — Use framework A.
- V2: Confirmed — Use framework B.
- V3: Revocation of V2's active decision.

After V3, the system must not simply reinstate V1.

The current projection should indicate an explicit
revocation or absence of an active decision.

The existing B4.2 prototype does not implement this
operation and must not be described as revocation-aware.

### 15.3 Conflicting claims

Conflicts may exist between:

- Two source documents
- User statements at different times
- A human confirmation and new evidence
- Multiple agents' proposed claims
- Concurrent human edits
- Conflicting project requirements
- Current state and historical state

A conflict record should preserve:

- Affected assertion and revision identities
- Supporting and contradicting source references
- Review status
- Detection time
- Resolution time, if resolved
- User-authorized resolution, if supplied

Contradictory evidence does not independently determine
which claim is true.

The default behavior is to surface unresolved conflicts,
not automatically select a winner.

A new source may trigger review but must not silently
overwrite an existing confirmed decision.

### 15.4 Historical queries and bitemporal semantics

Memory retrieval should eventually support:

A. Knowledge as known then:
   Use the recorded-time cutoff to exclude claims
   learned later.

B. Current understanding of the past:
   Use today's available knowledge while evaluating
   the historical effective-time interval.

A past-effective correction recorded today may affect
query B but must not rewrite query A.

For revocations, distinguish:

- When the revocation was recorded
- When it became effective
- Which revision it withdrew
- Whether the revocation was later superseded

Future-effective records must not apply prematurely.

An explicit policy for overlapping effective intervals,
late-arriving evidence, and retroactive revocation is
required before implementing full bitemporal retrieval.

### 15.5 Data deletion model

Proposed deletion scopes:

**Individual assertion**

Remove the designated assertion's private contents,
its revisions, source-specific evidence as appropriate,
and derivative projections.

**Source item**

Remove the original content, extracted text, stored file,
embedding, and any derivative copies or source excerpts.

Preserve remaining project knowledge only if it has
an independent authorized basis and does not reproduce
the deleted source's protected content.

**Entire project**

Remove the project's memory, events, actions, source
associations, cached summaries, and project-specific
derived representations.

Shared source records require separate ownership and
reference analysis before removal.

**Account deletion**

Cover all account-associated project memory and
derived data, subject to documented retention obligations.

These are intended scopes, not implemented operations.

### 15.6 Deletion execution requirements

An eventual deletion workflow must:

1. Authenticate and authorize the request.
2. Clearly identify the requested deletion scope.
3. Stop new processing for affected data.
4. Prevent affected data from appearing in new reads.
5. Locate canonical and derived copies.
6. Apply appropriately authorized deletion operations.
7. Invalidate caches, summaries, and search indexes.
8. Remove affected vectors and storage objects.
9. Prevent background jobs from recreating deleted data.
10. Record a privacy-preserving operation outcome.
11. Verify removal from live authorized retrieval.
12. Document backup and restoration limitations.

Partial failures must be tracked and safely retried.

No system should claim complete erasure based only on
a successful SQL DELETE response.

### 15.7 Append-only history and erasure

Append-only revision history applies to ordinary
project edits, corrections, and supersession.

It does not prohibit separately authorized erasure.

A privacy deletion operation may permanently remove
revision content, original evidence, or entire records.

Any retained audit marker must be minimized and must
not contain deleted content or reversible references
without an independently justified retention basis.

The design must state when a redacted historical
timeline is incomplete because information was erased.

Deleted private material must not be reconstructed
from older revision payloads.

### 15.8 Existing database relationships

The current schema has existing deletion behavior:

- Projects reference authenticated users.
- Project events and actions reference projects.
- Project-source associations reference projects
  and source items.
- Some event/action source references use SET NULL.
- Several project/source relationships use CASCADE.

Those existing behaviors require migration-specific
verification before creating memory references.

CASCADE alone does not remove all external files,
embeddings, caches, exports, or derived summaries.

Source ownership and cross-project associations need
special care when one source supports multiple projects.

### 15.9 Backups, restoration, and retention

The eventual service must document:

- Retention of live project records
- Retention of ordinary revision history
- Temporary processing data
- Cache and context expiration
- Deleted-file handling
- Backup and point-in-time recovery retention
- Operational and security log retention
- Restoration and deletion replay procedures

Provider backup retention must be verified against
the project's actual Supabase configuration.

A deletion from the live database may remain in
retained backups until those backups expire.

Restoring a backup must not reintroduce data already
subject to an authorized deletion request.

A deletion ledger or equivalent restoration safeguard
may be needed, but any retained identifiers must be
privacy-reviewed.

Do not promise immediate deletion of immutable backups
without verified provider support.

No concrete retention durations have been approved.

### 15.10 Agent context and derived memory

Memory provided to an AI agent must be permission-scoped.

Requirements:

- Do not make persistent project data globally available
  to unrelated agents or users.
- Do not treat retrieved source text as instructions.
- Expire temporary context according to documented rules.
- Do not reuse erased evidence in future prompts.
- Prevent background embedding or summarization jobs
  from regenerating deleted content.
- Preserve uncertainty and provenance in summaries.
- Require separate authorization before sharing private
  project content with external inference services.

The Hugging Face staging Space remains outside the
persistent memory write path.

Production inference is not authorized.

### 15.11 Tests required before persistence

Required scenarios:

1. Revoke current confirmation without restoring older V1.
2. Reject an unconfirmed candidate without revoking V1.
3. Dispute a claim without silently replacing its value.
4. Create a new confirmation after revocation.
5. Reject stale concurrent revocation attempts.
6. Keep historical recorded-time queries accurate.
7. Support retroactive effective-time queries.
8. Preserve unresolved contradictory evidence.
9. Delete an assertion and its derivative copies.
10. Delete a source and invalidate its embeddings.
11. Delete a project without leaking its history.
12. Handle shared sources across multiple projects.
13. Verify deletion despite failed background jobs.
14. Prevent deleted content from returning after restore.
15. Test RLS against unauthorized deletion requests.
16. Verify that agent context no longer contains erased
    information after cache invalidation.

These must be exercised against an isolated test
database before enabling durable writes.

### 15.12 Remaining design decisions

Still requiring separate implementation review:

- Revocation schema and transaction semantics
- Late-effective and overlapping-revision policy
- Deletion cascade strategy for new memory tables
- Source preservation across shared projects
- Auditable deletion without retaining erased content
- Backup restoration and retention guarantees
- Legal or operational retention exceptions, if any
- Database role and approved write transaction mechanism

The implementation must not claim these decisions are
already enforced by the B4.2 in-memory prototype.

B4.3C remains documentation only.

No database migration, memory write API, retention job,
or deletion workflow is authorized by this document.
