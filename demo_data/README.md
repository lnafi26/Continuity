# Demo data — reusable synthetic dataset

A self-contained, **work-only** Gmail + Calendar dataset for exercising the whole
ThreadLinePMA pipeline without connecting a real Google account or storing any
personal information.

## What's in it

`synthetic_dataset.json` is fictional and limited to **work** content:

- **Projects / discussions** — a "Payments service migration" email thread with a
  proposed plan, a teammate's differing opinion, and a decision + action items.
- **Manager weekly 1:1** — a recurring calendar event plus an agenda email.
- **Q3 roadmap** — a review-request thread with a differing-opinion reply, and a
  planning meeting.
- **Interview panel** — you're on a hiring panel (a work task), with a scheduling
  email and the panel meeting.
- **Work training** — an Advanced SQL training enrollment email + session event.
- **Conference** — an internal engineering summit schedule email + keynote event.
- **One noise item** — a subscription blog digest, kept so you can confirm the
  Stage 3 noise filter still excludes non-actionable mail.

It deliberately **excludes** job applications, job alerts, and personal events
(doctor visits, errands, shopping, etc.).

Dates are **relative** (`days_ago` / `days_from_now`), converted to concrete
timestamps at load time, so the dashboard always looks current — recent activity
in the last week and several upcoming events (including one today).

## Where it's injected

`load_demo_data.py` writes each fixture through
`backend/ingest/source_items_repo.upsert_source_item()` — the **exact** function
Stage 1 (ingest/sync) uses for real Gmail/Calendar data. So everything from
Stage 2 onward runs identically on demo rows and real rows. It first upserts two
synthetic `source_connections` (gmail + google_calendar, account
`testxu495@acmecorp.com`) so the FK/CHECK constraints are satisfied.

## Setup (one time)

1. **Create the auth user.** In the Supabase dashboard → **Authentication → Users**,
   add a user with email **`testxu495@gmail.com`** (any password). The loader
   resolves this email to its `auth.users.id` and owns the data under it.
2. Make sure `backend/.env` has `SUPABASE_DATABASE_URL` set (already required by
   the rest of the backend).

## Load the data

From the project root (`ai_project_management_tool/`):

```bash
# Load under testxu495@gmail.com (default)
python3 demo_data/load_demo_data.py

# Preview without writing
python3 demo_data/load_demo_data.py --dry-run

# Wipe previously-loaded demo rows, then reload fresh
python3 demo_data/load_demo_data.py --reset

# Just remove the demo rows
python3 demo_data/load_demo_data.py --reset-only

# Load under a different existing auth user
python3 demo_data/load_demo_data.py --email you@example.com
```

The loader prints the resolved `user_id` — **copy it**; every pipeline stage below
is scoped with `--user-id <that id>`.

## Run the pipeline (scoped to the demo user)

Replace `<UID>` with the id printed by the loader.

```bash
# Stage 2 — normalize
python3 backend/normalize/normalize.py run --user-id <UID>

# Stage 3 — clean & dedupe + work-only filter (LLM work-gate runs by default;
# needs ANTHROPIC_API_KEY. Add --no-gate for the cheap deterministic filter only)
python3 backend/dedupe/dedupe.py run --user-id <UID>

# Stage 4 — embed, then detect relationships
python3 backend/embed/relate.py embed  --user-id <UID>
python3 backend/embed/relate.py relate --user-id <UID> --reset

# Stage 5 — group & name projects (uses Claude Sonnet 5)
python3 backend/grouping/group.py run --user-id <UID> --reset

# Stage 6 — extract events & actions (uses Claude Haiku 4.5)
python3 backend/extract/extract.py run --user-id <UID> --reset

# Stage 7 — precompute the catch-up digest's per-project summary (Haiku 4.5).
# Run this after Stage 6 (and again any time new events land) -- the
# dashboard only reads projects.catchup_summary, it never generates it live.
python3 backend/digest/summarize.py run --user-id <UID>
```

Each stage has `status` (and most have `preview`) subcommands for spot-checking,
e.g. `python3 backend/extract/extract.py status --user-id <UID>`.

## View it

Sign in to the frontend as `testxu495@gmail.com`. The dashboard reads the
projects, events, and actions produced above for that user.

## Re-running / idempotency

Loading is idempotent on `(connection_id, external_id)` — re-running updates rows
in place and re-queues them (`processing_status = 'pending'`, marker columns
reset), so you can re-run the loader and the pipeline any number of times. Use
`--reset` on the loader (and `--reset` on Stages 4–6) for a completely clean pass.
