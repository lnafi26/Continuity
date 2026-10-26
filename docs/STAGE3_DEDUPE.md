# Stage 3 — Clean & Deduplicate

This stage decides which normalized rows proceed to AI grouping. It implements
the Stage 3 spec in [Architecture.md](Architecture.md).

## What it does

For each normalized row still queued (`normalized_at` set, `deduped_at IS NULL`),
it records a decision:

- `include_in_grouping = true` → clean, unique item ready for Stage 4.
- `include_in_grouping = false` with an `exclusion_reason` → **kept and
  retrievable**, but held out of grouping:
  - `noise` — newsletter / automated notification (per-row rule).
  - `recurring_instance` — an extra instance of a recurring calendar series.
  - `duplicate` — same `content_hash` as an earlier kept item.

Every processed row also gets a `content_hash` and a `deduped_at` stamp.

## Decision logic

1. **Noise** (highest precedence): sender contains fragments like `noreply`,
   `newsletter`, `notifications`, `alerts`, `mailer`, `jobalerts`, … or the body
   contains phrases like `unsubscribe`, `view in browser`, `manage your
   preferences`.
2. **Recurring collapse**: calendar rows sharing
   `(connection_id, external_thread_id)` are one series; the earliest instance
   is kept, the rest become `recurring_instance`.
3. **Content-hash duplicates**: rows with the same
   `sha256(source_type + title + cleaned_text)` collapse to the earliest
   representative; the rest become `duplicate`. Empty-text items hash to `None`
   and are never falsely deduplicated.

Precedence when several apply: **noise > recurring_instance > duplicate**.

## Components

| File | Role |
|------|------|
| `backend/dedupe/classification.py` | Pure: `content_hash`, `is_noise` |
| `backend/dedupe/dedupe_repo.py` | Fetch queue / apply decision / counts |
| `backend/dedupe/dedupe.py` | Orchestrator CLI (`run` / `preview` / `status`) |

Schema: `add_source_items_dedupe_fields` in
`backend/database/supabase_queries.json` (adds `content_hash`,
`include_in_grouping`, `exclusion_reason`, `deduped_at` + queue indexes).

## Setup

```bash
python3 backend/database/supabase_connections.py --title add_source_items_dedupe_fields
```

## Commands

```bash
# Dry-run the decisions (no writes)
python3 backend/dedupe/dedupe.py preview --user-id <uuid>

# Apply decisions
python3 backend/dedupe/dedupe.py run --user-id <uuid>

# Counts (queued / included / excluded by reason)
python3 backend/dedupe/dedupe.py status --user-id <uuid>
```

## Seeing the results

```sql
-- The included set that feeds Stage 4 (with cleaned text)
select source_type, occurred_at, sender, title, left(text_excerpt,200) as excerpt
from public.source_items
where user_id = '<uuid>' and deduped_at is not null and include_in_grouping
order by occurred_at desc nulls last;

-- Why things were excluded
select exclusion_reason, source_type, sender, title
from public.source_items
where user_id = '<uuid>' and include_in_grouping = false
order by exclusion_reason;
```

## Idempotency & re-processing

- Only rows with `deduped_at IS NULL` are picked up; re-running is a no-op once
  the queue is empty.
- Re-ingesting a changed item (Stage 1) resets `content_hash`,
  `include_in_grouping`, `exclusion_reason`, and `deduped_at`, so it re-runs the
  whole pipeline.

## Tuning

Noise rules are deliberately simple heuristics in `classification.py`. If a real
project email is misflagged as `noise`, or a newsletter slips through, adjust
`_NOISE_SENDER_FRAGMENTS` / `_NOISE_BODY_PHRASES`. Because excluded rows are kept
(not deleted), re-running after re-ingest re-evaluates them.

## Note on `processing_status`

Architecture mentions setting `processing_status = 'processing'` while a worker
owns a row. This MVP keeps the marker-column approach (`deduped_at`) for stage
progress and defers true ownership/locking to the concurrent-worker design in
Stage 9. Single-process runs don't need it.

## Next stage

**Stage 4 — Embed & detect relationships**: over the `include_in_grouping`
set, combine deterministic signals (shared thread, participants, keywords, time
windows) with embeddings (pgvector) to produce scored candidate relationships.
