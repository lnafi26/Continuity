# Stage 1 — Ingest / Synchronize (Gmail + Google Calendar)

This stage pulls new and changed items from each **active** connection (created
in Stage 0) into `source_items`, incrementally. It implements the Stage 1 spec
in [Architecture.md](Architecture.md).

## What it produces

One **`source_items`** row per Gmail message / Calendar event, with
`processing_status = 'pending'`. Those pending rows are the queue that Stage 2
(extract & normalize) will consume.

> **Design note.** Architecture Stage 1 describes "raw payloads queued for
> normalization" and Stage 2 writes `source_items`. To avoid a second raw table
> (and the storage overhead SUPABASE.md warns against), Stage 1 writes the
> `source_items` rows directly with `processing_status = 'pending'` — the
> pending rows *are* the queue. Stage 2 cleans/normalizes them in place.

## How incremental sync works

| Provider | First run | Later runs | Cursor stored in |
|----------|-----------|------------|------------------|
| Gmail | Backfill last N days (`newer_than:Nd`) | **History API** (`messageAdded` since historyId) | `source_connections.sync_cursor` |
| Calendar | Backfill recent/upcoming events | **syncToken** (changed events only) | `source_connections.sync_cursor` |

The cursor is advanced **only after** a batch is safely written to
`source_items`, so it never skips unprocessed items. If Gmail's historyId is too
old (HTTP 404) or Calendar's syncToken is invalid (HTTP 410), the sync
automatically falls back to a full backfill.

## Components

| File | Role |
|------|------|
| `backend/ingest/source_items_repo.py` | Idempotent upsert into `source_items` + counts |
| `backend/ingest/gmail_sync.py` | Gmail backfill + History API (REST) |
| `backend/ingest/calendar_sync.py` | Calendar backfill + syncToken (REST) |
| `backend/ingest/sync.py` | Orchestrator CLI (`run` / `status`) |
| `backend/auth/credentials.py` | Shared: fresh access token per connection (refresh + persist) |

No new dependencies or tables — it reuses the Stage 0 config, token store, and
`source_items` (already in the schema).

## Prerequisites

- Stage 0 complete: at least one connection with `status = 'active'`
  (verify with `python3 backend/auth/verify.py list`).

## Commands

```bash
# Sync every active connection for the default test user
python3 backend/ingest/sync.py run

# Scope to one provider / user, force a backfill, cap items
python3 backend/ingest/sync.py run --provider gmail --user-id <uuid> --full --max 25

# Inspect cursors, timestamps, and item counts (read-only)
python3 backend/ingest/sync.py status --user-id <uuid>
```

`run` flags: `--provider {gmail,google_calendar}`, `--user-id`, `--full` (ignore
cursor and backfill), `--days N` (backfill window, default 30), `--max N` (cap
per connection, default 50).

## Testing

1. **First run — backfill + cursor persistence**
   ```bash
   python3 backend/ingest/sync.py run --user-id <uuid> --full --max 15
   ```
   Each connection prints `backfill: inserted …, updated …` and
   `cursor -> <value> (last_synced_at stamped)`.

2. **Confirm state was saved**
   ```bash
   python3 backend/ingest/sync.py status --user-id <uuid>
   ```
   Both connections now show a real `sync_cursor` and a `last_synced_at`.

3. **Second run — incremental**
   ```bash
   python3 backend/ingest/sync.py run --user-id <uuid> --max 15
   ```
   Mode flips to `incremental`; with no new mail/events it inserts `0`.

4. **Idempotency** — re-running a backfill shows `inserted 0, updated N`; the row
   count does not grow (guaranteed by `unique (connection_id, external_id)`).

### See the rows in a browser
Supabase → SQL Editor:
```sql
select source_type, title, sender, occurred_at, processing_status, source_url
from public.source_items
where user_id = '<uuid>'
order by created_at desc;
```

## Status & error handling

- Success: `source_connections` → `status = 'active'`, `last_error = null`,
  cursor + `last_synced_at` updated.
- Expired/again token failure: `status = 'expired'` with `last_error` (reconnect
  via Stage 0).
- Sync/API failure: `status = 'error'` with `last_error`; the **cursor is kept**
  so the next run retries the same delta rather than skipping it.
- A single failing connection does not stop the others (each is independent).

## What Stage 1 intentionally does NOT do

- No cleaning of signatures/quoted replies, no dedupe beyond identity, no
  semantic grouping — those are Stage 2 (normalize) and Stage 3+ (clean, group).
- Cancelled calendar events are skipped for the MVP (not deleted from
  `source_items`).
- Attachments are not downloaded (only metadata/text is captured), per the
  Free-tier storage guidance in SUPABASE.md.

## Next stage

**Stage 2 — Extract & normalize**: consume `processing_status = 'pending'`
rows, strip signatures/quoted text/HTML boilerplate, finalize `text_excerpt`,
and mark them ready for relationship detection.
