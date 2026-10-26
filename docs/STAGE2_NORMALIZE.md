# Stage 2 — Extract & Normalize (clean the ingested text)

This stage turns the raw rows written by Stage 1 into clean, uniform text ready
for relationship detection. It implements the Stage 2 spec in
[Architecture.md](Architecture.md).

## What it does

For each `source_items` row still on the queue (`processing_status = 'pending'`
and `normalized_at IS NULL`) it:

- Strips **HTML boilerplate**, **quoted reply chains**, and **signatures** from
  the body.
- Normalizes whitespace, and lowercases/de-duplicates `participants` + `sender`.
- Writes the cleaned text back to `extracted_text`, refreshes a bounded
  `text_excerpt` (≤ 2000 chars), and stamps `normalized_at = now()`.

> **Scope.** Stage 2 only *cleans text*. Removing duplicates, collapsing
> recurring meetings, and dropping newsletter/noise rows is **Stage 3**
> (clean & deduplicate). So a newsletter gets cleaned here but is not filtered
> out until Stage 3.

## The `normalized_at` marker

Rather than overload the 4-value `processing_status`, Stage 2 uses a nullable
`normalized_at` timestamp as its per-stage marker:

- `NULL` → still needs normalization (the work queue).
- set → normalized; downstream stages can rely on clean text.

Re-ingesting a changed item (Stage 1) resets `normalized_at` to `NULL`, so the
updated content is automatically re-normalized. This makes the pass idempotent:
re-running only touches un-normalized rows.

## Components

| File | Role |
|------|------|
| `backend/normalize/text_cleaning.py` | Pure cleaning functions (no I/O) |
| `backend/normalize/normalize_repo.py` | Fetch queue / save cleaned / mark failed / counts |
| `backend/normalize/normalize.py` | Orchestrator CLI (`run` / `status` / `preview`) |

Schema: `add_source_items_normalized_at` in
`backend/database/supabase_queries.json` (adds the column + a work-queue index).

## Cleaning rules (heuristics)

- **HTML**: `<br>` and block tags → newlines; script/style and all tags removed;
  entities unescaped.
- **Quoted replies**: cut at the first of `On … wrote:`,
  `-----Original Message-----`, or an Outlook `From:/Sent:` header block; drop
  lines beginning with `>`.
- **Signatures**: cut at the RFC `-- ` delimiter, `Sent from my …`, or
  `Get Outlook for …`.
- **Calendar**: strip the Google Meet `-::~:~::…` boilerplate block.

These are deliberately conservative to avoid deleting real content; refine as you
see misses on real data.

## Setup

Apply the migration once (adds the marker column):
```bash
python3 backend/database/supabase_connections.py --title add_source_items_normalized_at
```
> Apply this **before** the next `sync.py run`, because Stage 1's upsert now
> references `normalized_at`.

## Commands

```bash
# Dry run: show raw vs cleaned for a few rows, no writes
python3 backend/normalize/normalize.py preview --user-id <uuid> --limit 3

# Normalize the pending queue
python3 backend/normalize/normalize.py run --user-id <uuid>

# Progress counts
python3 backend/normalize/normalize.py status --user-id <uuid>
```

## Testing

1. **Preview** a few rows and eyeball the cleaning quality.
2. **Run** — expect `Normalized N item(s); 0 failed` and a queue summary with
   `not_normalized: 0`.
3. **Idempotency** — re-run `run`: `Nothing to normalize. Queue is empty.`
4. **Browser** — in Supabase, the `text_excerpt` shows cleaned text and
   `normalized_at` is set:
   ```sql
   select source_type, title, left(text_excerpt, 120) as excerpt, normalized_at
   from public.source_items
   where user_id = '<uuid>' and normalized_at is not null
   order by updated_at desc;
   ```

## Status & error handling

- Success: cleaned fields written, `normalized_at` stamped, `processing_error`
  cleared.
- Cleaning error (rare, since functions are pure text ops): row set to
  `processing_status = 'failed'` with `processing_error`; the pass continues.

## Next stage

**Stage 3 — Clean & deduplicate**: set `processing_status = 'processing'` while
owned, drop duplicate/forwarded content by content hash, collapse recurring
calendar events, and filter obvious non-project noise (newsletters, automated
notifications) so only meaningful items reach embedding/grouping.
