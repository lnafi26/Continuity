# Stage 6 — Extract Events & Actions

This stage fills each project's timeline and to-do list. For every item linked to
a project (Stage 5), it uses the LLM to extract typed timeline **events** and
actionable **to-dos**, all source-linked. It implements the Stage 6 spec in
[Architecture.md](Architecture.md).

## What it produces

- **`project_events`** rows: `event_type` (email / file / meeting / decision /
  deadline / status / note), `title`, `body`, `person`, `event_date`,
  `confidence`, `source_item_id`. `event_date` + `person` drive "progress by
  day" and "who we talked with".
- **`project_actions`** rows: `title`, `assignee`, `due_date`, `completed`,
  `confidence`, `source_item_id` — the "needs your attention" list.

All AI rows carry `user_edited = false`, so a re-run can clear and regenerate
them without touching rows a user has edited.

## How it works

1. **Queue** — items with a `project_source_link` and `extracted_at IS NULL`
   (one row per item, highest-confidence link).
2. **Extract** — for each item, send its metadata + cleaned body to **Haiku 4.5**
   and get `{events: [...], actions: [...]}`. The result is normalized: event
   types clamped to the enum, dates parsed (falling back to the item's date),
   `person` defaulting to the sender, confidence clamped to 0–1, empty actions
   dropped. Always keeps at least one event describing the item.
3. **Write** — insert the events/actions (colored to match the project), then set
   the item `extracted_at = now()` and `processing_status = 'processed'`.

## Components

| File | Role |
|------|------|
| `backend/extract/extractor.py` | Haiku extraction + normalization + metadata fallback |
| `backend/extract/extract_repo.py` | Fetch queue, insert events/actions, mark, reset |
| `backend/extract/extract.py` | Orchestrator CLI (`preview` / `run` / `status`) |

Schema: `add_source_items_extracted_at` adds the `extracted_at` marker.
`project_events` / `project_actions` already existed.

## Setup

```bash
python3 backend/database/supabase_connections.py --title add_source_items_extracted_at
```
`ANTHROPIC_API_KEY` must be set; `ANTHROPIC_EXTRACT_MODEL` defaults to
`claude-haiku-4-5`.

## Commands

```bash
python3 backend/extract/extract.py preview --user-id <uuid> --limit 3   # dry-run (LLM, no writes)
python3 backend/extract/extract.py run --user-id <uuid>                 # extract the queue
python3 backend/extract/extract.py run --user-id <uuid> --reset         # rebuild AI rows
python3 backend/extract/extract.py status --user-id <uuid>
python3 backend/database/supabase_connections.py --title check_extract_progress
```

## Cost

Haiku 4.5, one call per linked item (~15–30 items) — a few cents per full run.
Only items with `extracted_at IS NULL` are processed, so re-runs are free no-ops
until something changes.

## Idempotency & re-processing

- The `extracted_at` marker is the queue signal; a completed item is skipped.
- **Re-ingest** (Stage 1) clears `extracted_at`, so a changed item is re-extracted.
- **After re-grouping** (`group.py run --reset`), run `extract.py run --reset`:
  it deletes AI-generated events/actions (`user_edited = false`) and re-queues
  the linked items, then re-extracts. Rows a user edited (`user_edited = true`)
  are preserved.

## Graceful fallback

No API key or a failed call yields a single metadata-derived event per item
(a `meeting` for calendar, an `email` for mail) and no actions — so the stage
never blocks the pipeline.

## Seeing the result

```sql
select p.name, e.event_type, e.title, e.event_date, e.person
from public.project_events e join public.projects p on p.id = e.project_id
where e.user_id = '<uuid>' order by e.event_date desc limit 20;

select p.name, a.title, a.due_date, a.assignee, a.completed
from public.project_actions a join public.projects p on p.id = a.project_id
where a.user_id = '<uuid>' order by a.due_date nulls last limit 20;
```
These are exactly what the dashboard's timeline and "Needs your attention" list
read.

## Next stage

**Stage 7 — Assemble timeline (dashboard read)**: serve each project's
summary, participants, timeline (by day), open vs. done actions, next deadline,
and a confidence indicator to the frontend — every entry linking back to its
`source_url`. Most of this is the browser reading what Stages 0–6 have written.
