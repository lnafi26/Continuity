# Backend Workflow Architecture

## Purpose

Let an authorized user connect **Gmail** and **Google Calendar**, then answer
one question automatically every time they open the app: **"What did I miss?"**
— since their last login, or across an explicit out-of-office window they
declare (e.g. "I was out Aug 10–14").

The system turns scattered messages and events into **projects**, **timelines**,
and **action items** so the user never has to scroll their inbox or calendar to
reconstruct what happened while they were away. The catch-up moment is the
primary product surface; the always-current project workspace underneath it is
the mechanism that makes that catch-up possible — not the pitch itself.

Concretely, once a user is logged in and has integrated Gmail / Google Calendar,
the app should:

- Scan emails and calendar events continuously (Stages 0–6), independent of
  when the user is actually looking.
- Group semantically related items into the same project — using deterministic
  rules first (same sender, shared project name/keywords, thread, participants,
  time window) and an LLM second for meaning-based relationships across
  messages that are **not** necessarily in the same thread.
- Reconstruct a project **timeline**: progress by day, most recent action
  items, and who the conversations were with.
- On open, compute what changed **since the user's last catch-up checkpoint**
  (login-based by default, or a manually declared OOO window) and present it as
  one project-grouped digest — decisions and differing opinions first, then new
  actions/deadlines, then everything else — instead of a flat, chronological
  re-read of everything that happened.

This document defines the backend **stages** that carry data from a connected
account to the dashboard. The stages follow the pipeline recommended in
`Formatted_AI_Project_Memory_Four_Phase_Planning_Guide.txt` (Phase 2):

> ingestion → extraction/normalization → relationship detection → project
> grouping → event/action extraction → timeline generation → user review →
> dashboard

and are aligned with the existing Supabase schema in
`backend/database/supabase_queries.json`.

## Guiding principles (from Phase 2)

- **Deterministic first, LLM second.** Use sender, participants, thread IDs,
  timestamps, and explicit project names to pre-filter; use embeddings + LLM
  only to decide semantic relationships the rules cannot.
- **Everything stays source-linked.** Every event, action, and match keeps a
  `source_item_id` and a `source_url` so the user can open the original.
- **Every AI decision carries a confidence and an explanation** (`confidence`,
  `explanation` columns) and is presented for review before it is trusted.
- **User corrections are captured as feedback** (`user_corrections`) and used
  for evaluation before changing model behavior — never applied silently.
- **Gmail is added first, Google Calendar second**, because Gmail supplies
  content, participants, timestamps, threads, and attachments in one source.
- **Catch-up is checkpoint-anchored, not a fixed report.** Every read the user
  sees on open is relative to "since you last checked" (default) or an
  explicit OOO window they declare — never a static daily digest they have to
  remember to open. Viewing a project's catch-up digest advances the
  checkpoint; nothing is deleted or hidden, it just moves from "new" to
  "recent" in the full timeline.
- **AI proposes, the user verifies — for the past and for what's next.** The
  same pattern covers both directions: reconstructing what happened
  (confidence + explanation, corrected via Stage 8) and drafting what the user
  now owes people (a queue of reviewable drafts, never auto-sent). Nothing the
  AI produces is presented as final without an easy way to confirm or fix it.

---

## Stage map

| # | Stage | Reads | Writes | Main tech |
|---|-------|-------|--------|-----------|
| 0 | Connect & authorize | user request | `source_connections` | Google OAuth 2.0 |
| 1 | Ingest / sync | `source_connections` | raw payloads (queue) | Gmail API, Calendar API |
| 2 | Extract & normalize | raw payloads | `source_items` (`pending`) | parsers, MIME/text extraction |
| 3 | Clean & deduplicate | `source_items` | `source_items` (`processing`) | rules, hashing |
| 4 | Embed & detect relationships | `source_items` | vector store + candidates | embeddings, similarity |
| 5 | Group & link to projects | candidates | `projects`, `project_source_links` | rules + LLM |
| 6 | Extract events & actions | `source_items`, links | `project_events` (+`requires_response`), `project_actions` (+`status`,`backlog`) | LLM extraction |
| 7 | Assemble timeline & catch-up digest | events, actions, links, checkpoint | dashboard read models (incl. board) | SQL queries |
| 8 | User review & feedback | dashboard edits, drafts | `user_corrections`, `project_drafts`, updates | app + RLS |
| 9 | Scheduling, retry, errors | all of the above | status columns | worker/cron |
| 10 | Draft generation ("Clear my plate") | Stage 7 digest output | `project_drafts` | LLM generation |

---

## Stage 0 — Connect & authorize

**Goal:** obtain and store per-user permission to read Gmail and Calendar.

- User initiates OAuth from the dashboard; request read-only scopes
  (`gmail.readonly`, `calendar.readonly` / `calendar.events.readonly`).
- Store **non-secret** connection metadata in `source_connections`
  (`provider`, `provider_account_id`, `account_email`, `status`).
- Store OAuth **refresh/access tokens as secrets in the backend only**
  (never in the browser or in `source_connections`), keyed by connection id.
- Set `status = 'active'`; on token failure set `'expired'` / `'error'` and
  surface a reconnect prompt.

**Done when:** an `active` row exists per connected provider for the user.
See "Live demo strategy" below for how Stage 0 is exercised safely in front of
an audience. Scopes stay read-only even with "Clear my plate" (Stage 10) —
drafts are generated and reviewed, never auto-sent, so no `gmail.send` scope
is ever requested.

## Stage 1 — Ingest / sync

**Goal:** pull new and changed items from each connected account, incrementally.

- **Gmail:** first run does a bounded backfill (e.g. last N days); later runs use
  the Gmail **History API** with the stored `sync_cursor` (historyId) to fetch
  only deltas. Capture message id, thread id, headers, body, attachments.
- **Google Calendar:** use `syncToken` (also stored in `sync_cursor`) for
  incremental sync; capture event id, title, description, attendees,
  start/end times, location, and recurrence.
- Persist `last_synced_at`; advance `sync_cursor` only after a batch is safely
  handed to Stage 2. On sync error, record `last_error` and keep the old cursor.

**Done when:** raw payloads for new/changed items are queued for normalization.

## Stage 2 — Extract & normalize

**Goal:** turn heterogeneous payloads into one uniform row shape.

- Write one `source_items` row per message/event with
  `processing_status = 'pending'`:
  - Gmail → `source_type = 'gmail'`, fill `sender`, `participants`,
    `external_thread_id`, `occurred_at`, attachment refs.
  - Calendar → `source_type = 'google_calendar'`, fill `participants`
    (attendees), `occurred_at`/`ends_at`, `location`.
- Extract plain text into `extracted_text`; strip signatures, quoted reply
  chains, and HTML boilerplate. Store a short `text_excerpt` (≤ 2000 chars).
- Preserve `external_id` + `source_url` for source-linking and idempotency
  (the `unique (connection_id, external_id)` constraint prevents duplicates).

**Done when:** every ingested item is a normalized `source_items` row.

## Stage 3 — Clean & deduplicate

**Goal:** avoid double-counting and reduce noise before AI work.

- Set `processing_status = 'processing'` while a worker owns the row.
- Deduplicate forwarded/quoted email history and re-synced items by
  `(connection_id, external_id)` and by content hash of `extracted_text`.
- Collapse recurring calendar events into a series with instances so a weekly
  standup does not create dozens of unrelated timeline entries.
- Drop obvious non-project noise (newsletters, automated notifications) via
  simple rules; keep them retrievable but out of grouping by default.

**Done when:** clean, de-duplicated text is ready for embedding.

## Stage 4 — Embed & detect relationships

**Goal:** find which items are candidates for the same project.

- **Deterministic signals first** (cheap, high-precision):
  same `external_thread_id`, overlapping `participants`/`sender`, shared
  explicit project name/keyword, close `occurred_at` windows.
- **Semantic signals second:** compute an embedding of `extracted_text`, store
  it in a vector store (Supabase `pgvector`), and retrieve nearest neighbors.
- Combine both into scored **candidate pairs/clusters**. Deterministic matches
  raise confidence; embeddings catch related items that use different wording
  or live in separate threads/tools (messages need not be in one thread).

**Done when:** each item has a ranked set of candidate relationships + scores.

## Stage 5 — Group & link to projects

**Goal:** assign items to a project, creating projects as needed.

- Cluster candidates into project groups. For ambiguous clusters, ask the LLM
  to confirm/split and to **name and summarize** the project.
- Upsert into `projects`; link each item via `project_source_links` with:
  - `match_method` = `rule` | `ai` | `manual`,
  - `confidence` (0–1) and a short `explanation`,
  - `review_status = 'pending'` for AI/rule matches.
- **Multi-project items:** allowed — write multiple `project_source_links`
  rows (per Phase 1: "update the information in both project lists").
- Low-confidence links are still written but flagged for Stage 8 review.

**Done when:** every processed item links to at least one project with a score.

## Stage 6 — Extract events & actions

**Goal:** populate the timeline and the task list.

- For each item (with project context), run LLM extraction to produce:
  - `project_events` rows typed as `email` / `file` / `meeting` / `decision`
    / `deadline` / `status` / `note`, each with `event_date`, `title`, `body`,
    `person`, `confidence`, and its `source_item_id`. `event_date` + `person`
    are what drive "progress by day" and "who we talked with".
  - `project_actions` rows with `title`, `assignee`, `due_date`, `completed`,
    `confidence`, and `source_item_id` — the "most recent action items".
- Set `source_items.processing_status = 'processed'`.
- Keep `user_edited = false` so later re-processing knows it may overwrite
  AI-generated (but not user-edited) rows.

**Schema additions required for the board and "Clear my plate" (Stage 10):**

- `project_actions.status` — enum `not_started` | `in_progress` | `completed`,
  replacing the current boolean `completed` (kept as a derived/legacy alias
  during migration). Inferred from reply activity, due-date proximity, and
  explicit completion language — the same extraction pass, a richer output.
  The dashboard's board (Stage 7) only ever *shows* two of the three values
  as distinct columns (In Progress, Completed) plus the separate `backlog`
  flag — a freshly-extracted `not_started` row folds into the In Progress
  column until a user or later signal moves it. The column value stays in
  the database either way; this is a display grouping, not a schema change.
- `project_actions.backlog boolean default false` — AI-suggested-but-not-urgent
  items, feeding the board's third column.
- `project_events.requires_response boolean` — an explicit, LLM-judged signal
  ("does this item genuinely need a reply from the user"), not a naive
  last-sender heuristic. This replaces today's client-side `statWaiting`
  guess and is what Stage 10 uses to decide which threads get a reply draft —
  a false positive here (drafting a reply to something that didn't need one)
  is a worse failure than missing an event/action, so this stays LLM-judged
  rather than rule-based, consistent with the deterministic-first/LLM-second
  principle (the deterministic layer still pre-filters obvious non-candidates,
  e.g. an event the user is not a participant/recipient on).

**Done when:** the project has timeline events and action items — including
status, backlog, and response-required signals — all source-linked.

## Stage 7 — Assemble timeline & catch-up digest (dashboard read)

**Goal:** serve two read models off the same underlying data — the always-on
project timeline, and a checkpoint-scoped catch-up digest that is the app's
**primary entry point** on login.

- **Checkpoint:** each user has a `last_catchup_at` timestamp
  (`profiles.last_catchup_at`, new column). It defaults to their previous
  `auth.users.last_sign_in_at` on first use, then advances only when the user
  views/dismisses the digest — **not on every login** — so checking in twice in
  one day doesn't erase what's genuinely new between those checks.
- **OOO override:** the user can declare an explicit window ("I was out Aug
  10–14") for one session instead of the stored checkpoint. This does not move
  the stored checkpoint unless the user confirms "mark as caught up" (Stage 8).
- **Delta query:** for `occurred_at >= checkpoint` (falling back to
  `created_at` for items without a natural occurrence time), pull events and
  actions already produced by Stages 5–6, grouped by project. No new
  extraction — this is purely a filtered read over existing data.
- **Ranking within the digest**, per project: (1) decisions and differing
  opinions, (2) new/changed action items assigned to the user, (3) upcoming
  meetings pulled forward from the window, (4) everything else. This reuses
  `project_events.event_type` and `project_actions` as already extracted in
  Stage 6.
- **Full timeline** (unscoped "Needs attention / Recent activity / Upcoming"
  views) stays available for anyone who wants to browse rather than catch up —
  the digest is the front door, not the only door.
- **Project page is the verify/correct surface, not the digest.** The
  Overview digest is glance-and-navigate only — clicking a project card takes
  the user to that project's full page, which is where Stage 8's
  confirm/edit/reject controls actually live (summary, timeline events,
  action items). This keeps the catch-up scroll fast and read-only while
  still putting every correction one click away.
- **Board read model:** the same `project_actions` grouped by `status` +
  `backlog` (Stage 6) instead of by time — three columns, In Progress /
  Completed / Backlog (no separate Not Started column; see the Stage 6 note
  above on how `not_started` rows are grouped). A pure read grouping; no new
  extraction. Filterable by project (multi-select) and by due-date range,
  purely client-side over the same read. A project page's action list links
  out to this same board pre-filtered to just that project ("See action
  items by due dates").
- **Status changes stay in sync across both surfaces in the same session.**
  Changing an action's status from the project page's status control, or by
  dragging its card on the board, updates the other surface's in-memory copy
  immediately — no reload needed. This is a same-tab/same-session
  convenience over shared client state, not a realtime subscription; a
  change made in one browser tab is not pushed to another tab or user.
- **Feeds Stage 10:** the digest's "waiting on you" list
  (`project_events.requires_response = true` with no later outbound reply),
  "new decision" list, and backlog items are exactly the input set Stage 10
  turns into draft replies/recaps/next-steps.
- Every entry links back to its `source_url` for one-click verification.

**Done when:** opening the app renders a project-grouped "what changed since
you were last here" digest without re-running the pipeline, and viewing it
advances the user's checkpoint.

## Stage 8 — User review & correction feedback

**Goal:** let users trust and correct the output; capture that as signal.

- User actions map to `user_corrections.correction_type`:
  `confirm_match`, `reject_match`, `move_project`, `edit_event`, `edit_action`,
  `edit_project`.
- On confirm/reject, update `project_source_links.review_status`.
- On edit, update the `project_events` / `project_actions` / `projects` row
  and set `user_edited = true` (not applicable to `projects`) so
  re-processing will not overwrite it.
- Store `previous_value` / `corrected_value` as JSONB for evaluation. Use these
  to measure accuracy and tune rules/prompts **before** changing behavior
  automatically (Phase 2 principle).
- `mark_caught_up` is a dedicated correction type that advances
  `profiles.last_catchup_at` to now (or to the end of a declared OOO window).
  It is the only correction type that doesn't touch `project_events` /
  `project_actions` — it moves the Stage 7 checkpoint, not project content.
- The "✓ looks right / ✎ fix" verify-in-place UI lives on the project page
  (see Stage 7) and covers everything Stage 5–6 generates about that
  project, each as its own inline confirm/edit affordance rather than a
  separate review screen:
  - **Project summary** (Stage 5) — `confirm_match` / `edit_project`.
  - **Timeline events** — `confirm_match` / `edit_event`, and editing covers
    both the event's title and its AI-generated summary (`body`) in one form.
  - **Action items** — `confirm_match` / `edit_action` for title and due
    date, plus `edit_action` for status/backlog (the same correction a board
    drag makes, just made from a dropdown here instead). `reject_match`
    additionally covers "this AI-suggested action item isn't actually
    needed" — unlike its original project-match-only scope, this deletes the
    `project_actions` row after capturing its prior state on the correction,
    rather than only flipping a review flag.
  - Edits are collected through a real multi-field dialog (title and/or
    summary/due-date together where relevant), not a bare browser prompt —
    each field commits together on Save, and the dialog only closes once the
    write actually succeeds.
  - The project page's action list is filterable by status (In Progress /
    Completed / Backlog, multi-select, default hides Completed); none of
    this filtering touches the underlying data, same as the board's filters.
- Three new correction types for the Stage 10 drafts queue: `edit_draft`
  (user rewrites before sending, stored like other corrections for
  evaluation), `dismiss_draft` (not relevant, drop it), and `mark_draft_sent`
  (user sent it outside the app; stops it from resurfacing). These touch the
  new `project_drafts` table (Stage 10), not `project_events`/`project_actions`.

**Done when:** corrections are persisted and protected from being overwritten.

## Stage 9 — Scheduling, retry & error handling (cross-cutting)

**Goal:** keep the pipeline reliable and current.

- **Scheduling:** periodic incremental sync per active connection (Stage 1);
  optional Gmail push (Pub/Sub) later.
- **Idempotency:** all stages are safe to re-run — keyed by `external_id`,
  content hash, and `processing_status`.
- **Retry:** transient API/model failures back off and retry; on repeated
  failure set `source_items.processing_status = 'failed'` +
  `processing_error`, or `source_connections.status = 'error'` + `last_error`.
- **Isolation:** a single bad item never blocks the batch; failures are
  quarantined and surfaced, not silently dropped.
- Stage 10's draft generation gets the same guarantees: it's triggered
  on-demand (not scheduled), is idempotent per input event/action set, and a
  failed draft for one project is isolated and surfaced — it never blocks
  drafts for the user's other projects.

**Done when:** failures are visible, recoverable, and non-blocking.

## Stage 10 — Draft generation ("Clear my plate")

**Goal:** turn the digest's "things the user now owes someone" into a queue of
reviewable drafts, on demand — the outbound half of catch-up.

- **Trigger:** user-initiated, from the catch-up digest (Stage 7), not
  scheduled — this runs against a checkpoint's worth of data once, not
  continuously.
- **Inputs**, all already produced by Stages 5–7, no new extraction over raw
  source text:
  - Threads with `project_events.requires_response = true` and no later
    outbound reply → **reply drafts**.
  - Projects with a new `decision`-typed event since checkpoint → **status
    recap drafts** for a manager/team, explicitly incorporating any
    differing-opinion events on the same project.
  - `project_actions` with `backlog = true` the user chooses to act on →
    **next-step write-up drafts**.
- **Output:** one `project_drafts` row per item — `draft_type`
  (`reply` | `recap` | `next_step`), `project_id`, `source_item_id` (the
  thread being replied to, if a reply), `body`, `based_on` (JSONB array of the
  `project_events`/`project_actions` ids used — same source-linking principle
  as every other stage), `confidence`, `explanation`, `status`
  (`pending` | `edited` | `dismissed` | `sent_ack`).
- **Never auto-sent.** The user reviews/edits every draft and sends it
  themselves outside the app (Stage 0's read-only scopes are never exceeded);
  `mark_draft_sent` (Stage 8) just stops it resurfacing.

**Done when:** every item the digest flagged as owed to someone has a
reviewable, source-linked draft, and none are sent without the user's action.

---

## MVP sequencing (what to build first)

Aligned with Phase 3 ("add one integration first; Gmail is the strongest
initial candidate"):

1. **Stages 2–8 on uploaded/exported email first** — validate normalization,
   grouping, extraction, timeline, and review with no live auth.
2. **Add Stage 0–1 for Gmail** once the core pipeline passes evaluation.
3. **Add Google Calendar** to enrich meetings and dates.
4. **Defer** Slack/Discord and images/audio until the text workflow is reliable.

## Live demo strategy

A real inbox rarely has enough work-related content to demo well, and running
live OAuth in front of an audience is fragile on its own: Google flags the app
unverified, and Stage 0's consent screen only succeeds for accounts already
added as test users (the `access_denied` failure mode). The strategy is to make
the "live" part of the demo genuinely real, on a controlled account, rather
than either faking it or risking OAuth against an unregistered account on
stage:

- **Present on a real Gmail/Calendar account already registered as an OAuth
  test user.** Run Stage 0 end-to-end at least once before presenting so
  `invalid_grant` / PKCE / insecure-transport issues are caught in rehearsal,
  not live.
- **Seed that account's real inbox and calendar ahead of time** with genuine
  work-only emails and events — sent and created for real, not injected at the
  `source_items` level. Reuse the content beats from
  `demo_data/synthetic_dataset.json` (a project thread with a decision and a
  differing opinion, a recurring manager 1:1, a roadmap debate, an interview
  panel, work training, a conference), since that content is already shaped to
  pass the Stage 3 work-only filter cleanly.
- **On stage, run Stage 0 and Stage 1 for real:** click Connect, approve the
  real consent screen, and let the Gmail History API / Calendar `syncToken`
  pull the seeded messages and events live. This also makes the strongest
  version of the catch-up story (Stage 7), since it genuinely is the first
  time this account's data has been ingested.
- **Run Stages 2–6 live** (a few seconds — local embeddings + Haiku extraction)
  so the audience watches grouping and extraction happen on freshly-synced
  real data, then land on the resulting catch-up digest.
- **Keep the synthetic `testxu495@gmail.com` account as a fallback.** If live
  OAuth or sync fails during the actual talk, switch to the pre-loaded demo
  account (see `demo_data/README.md`) rather than troubleshooting live.

## Data model reference

Backing tables (see `backend/database/supabase_queries.json`):
`source_connections`, `source_items`, `projects`, `project_source_links`,
`project_events`, `project_actions`, `user_corrections`, `profiles` — all
user-scoped and protected by Row Level Security.

Schema additions needed for the catch-up + board + "Clear my plate" features
(none touch Stages 0–5 or their tables):

- `profiles.last_catchup_at` (Stage 7) — each user's catch-up checkpoint.
- `project_actions.status` (Stage 6) — enum `not_started` | `in_progress` |
  `completed`, replacing today's boolean `completed` (kept as a legacy alias
  during migration) — drives the board columns (In Progress / Completed;
  `not_started` displays under In Progress — see Stage 6).
- `project_actions.backlog boolean default false` (Stage 6) — the board's
  third column.
- `user_corrections.correction_type` gained `edit_project` (Stage 8) so a
  correction can target the `projects` table itself (the AI-generated
  summary), not just `project_events` / `project_actions`.
- `project_events.requires_response boolean` (Stage 6) — explicit,
  LLM-judged "does this need a reply" signal; replaces the client-side
  `statWaiting` heuristic and is what Stage 10 keys off of.
- **New table `project_drafts`** (Stage 10) — `draft_type`, `project_id`,
  `source_item_id`, `body`, `based_on` (JSONB, source-linking the events/
  actions a draft was generated from), `confidence`, `explanation`, `status`
  (`pending`/`edited`/`dismissed`/`sent_ack`). User-scoped, RLS-protected like
  every other table.

No changes to `source_connections`, `source_items`, `projects`, or
`project_source_links` — Stages 0–5 are untouched by any of this.

## What the users should be able to do
When they logged in, they will see the home page
👋 Welcome back
Catch up on what you missed
Since: August 13, 5:00 PM
Catch Me Up

Or Are able to set up in their home page:
Catch me up from [Aug 13] to [Today]

The users should be able to connect to the interface with gmail or Google Calendar, and see what they've missed from the last time they logged in or between a certain time range, and once the information/event is pulled and populated, they should be able to:
- See the events/project conversation they've missed in a timeline (with a brief summary of what happened underneath the event title, who's involved in the conversation) (at max display 5 items at a time, if more events are included in this timeline, the panel should be scrollable, list from most recent to less recent), when you click on each event, it shows up a page with more details - open actions summaried from the item, the message or calendar event original details, and showing the complete thread of this event/project with other other related events
- Another section — **the Task Board** — is where the tool categorizes action items into three columns: **In Progress, Completed, Backlog** (suggested items from the conversation, but not urgent, that can be kept in backlog). There is no separate "not started" column; a freshly-extracted action defaults into In Progress until it's moved (see Stage 6/7). The AI populates and moves cards automatically from Stage 6 signals — the user's job is to glance and correct, not to maintain the board. Drag-and-drop is kept, but as a correction (Stage 8 `edit_action`, sets `user_edited = true`) rather than the primary interaction, so it doesn't turn into a manually-managed Trello board. Each card also shows its project and due date (if any) as small tags, and clicking a card (as opposed to dragging it) opens that project's page instead.
  - Schema: `project_actions.status` + `.backlog` — now specified in Stage 6 and the data model reference below.
  - **Board filters:** by project (a multi-select dropdown, not one control per project, so it scales as projects are added) and by due-date range. Purely client-side over the same board read — no new query per filter change.
  - **The same status control exists on the project page**, next to each action item, as a three-option dropdown (In Progress / Completed / Backlog) — the identical `edit_action` correction as a board drag, just reachable without leaving the project. A change from either surface updates the other's in-memory state immediately within the same session (see Stage 7).
  - The project page's action list can itself be filtered by status, and carries a "See action items by due dates" link that jumps to the Task Board pre-filtered to just that project — the board is where the due-date filter actually lives.
  - Collaboration (adding other users to see the same items) is cut. Everything today is single-user RLS derived from that user's own inbox; sharing needs a permissions model that doesn't exist and conflicts with the "your data stays yours" privacy pitch. A read-only share link for one project's digest is the lightweight version if this is wanted later.

- **Verify and correct on the project page, not inline in the digest scroll.**
  The Overview digest itself is glance-and-navigate only; clicking a project
  card takes the user to that project's full page, which is where every
  correction actually happens. There, each AI-generated piece of content
  carries its own "✓ looks right" / "✎ fix" pair: the project summary, each
  timeline event (title + generated summary together), and each action item
  (title + due date together, plus a separate status control and a "not
  needed" removal). Every field carrying a `confidence` and an `explanation`
  (per the guiding principles) is corrigible this way. Maps to Stage 8's
  `confirm_match` / `edit_event` / `edit_action` / `edit_project` /
  `reject_match` corrections — no new architecture beyond `edit_project`
  (added so the project summary itself is correctable), just an explicit UI
  moment for something the pipeline already tracks. Edits are made through a
  small dialog, not a bare browser prompt, so multi-field corrections (e.g.
  title + summary) commit together.

- **"Clear my plate"** — the outbound half of catch-up, and the more
  defensible version of "let AI do new work." Not a generic drafting
  assistant (that's a crowded category, and it usually implies write/send
  access this app doesn't have). Instead, one action at the end of the
  catch-up flow turns the digest into a **queue of reviewable drafts**, each
  generated from cross-project memory rather than a blank compose box:
  - A reply draft for every thread where someone is waiting on the user
    (the existing "Waiting" metric) — built from the *whole project's*
    history, not just the last message: what got decided, who disagreed,
    what's actually owed.
  - A status recap for a manager/team for every project with a new decision
    — drawing on the explicit decision + differing-opinion extraction
    (Stage 6), which a single-thread compose tool has no concept of.
  - A next-step write-up for any backlog item the user wants to act on.

  The user reviews, edits, and sends each draft themselves — this stays
  read-only (no `gmail.send` scope needed) and is the same "AI proposes, user
  verifies" pattern as verification above, just pointed at outbound work
  instead of inbound review. This is deliberately scoped to *things the
  catch-up flow already identified the user owes someone* — not open-ended
  composition — because that scoping is what only this pipeline's
  cross-project, decision-aware memory can do well.

