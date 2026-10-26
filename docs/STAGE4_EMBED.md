# Stage 4 — Embed & Detect Relationships

This stage finds which included items are candidates for the same project, by
combining deterministic signals with semantic similarity. It implements the
Stage 4 spec in [Architecture.md](Architecture.md).

## What it produces

- An **embedding** (384-dim, pgvector) on each included, deduplicated
  `source_items` row.
- Scored **candidate pairs** in `item_relationships`
  (`semantic_score`, `deterministic_score`, `combined_score`, `signals`).

## How scoring works

**Deterministic signals** (cheap, high-precision) between two items:

| Signal | Weight | Meaning |
|--------|--------|---------|
| `same_thread` | 0.50 | shared `external_thread_id` |
| `shared_sender` | 0.15 | same sender address |
| `participant_overlap` | ×0.25 | Jaccard of participants (incl. sender) |
| `keyword_overlap` | ×0.20 | Jaccard of significant title tokens |
| `time_proximity` | ×0.10 | within a 7-day window, scaled by closeness |

**Semantic signal**: cosine similarity of the local `all-MiniLM-L6-v2`
embeddings, retrieved as nearest neighbours via the pgvector HNSW index.

**Combined** = `0.6 · max(0, semantic) + 0.4 · deterministic`, with a shared
thread raising the floor to `0.85` (a strong structural link).

A pair is stored when `combined ≥ threshold` (default `0.45`) **or** it shares a
thread. Pairs are stored canonically (smaller id first), so each undirected pair
appears once.

### Candidate generation
- **Semantic**: each item's top-`k` (default 5) nearest neighbours.
- **Structural**: all pairs within a shared email thread (may be semantically
  distant yet clearly related).

This means semantic similarity can catch relationships the deterministic layer
misses — e.g. two identical-title calendar events with empty descriptions (whose
`content_hash` is `None`, so Stage 3 can't dedupe them) still link at `sem 1.00`.

## Components

| File | Role |
|------|------|
| `backend/embed/embeddings.py` | Local model wrapper (lazy load) |
| `backend/embed/deterministic.py` | Pure signal functions + `combine()` |
| `backend/embed/embed_repo.py` | Fetch to-embed / save embedding |
| `backend/embed/relationships_repo.py` | KNN, pair similarity, upsert pairs |
| `backend/embed/relate.py` | Orchestrator CLI |

Schema: `add_embeddings_and_relationships` (pgvector extension, `embedding` +
`embedded_at` columns, `item_relationships` table).

## Setup

```bash
python3 -m pip install -r backend/requirements.txt   # pulls sentence-transformers + torch
python3 backend/database/supabase_connections.py --title add_embeddings_and_relationships
```
If `create extension vector` fails, enable it once via **Supabase → Database →
Extensions → "vector" → Enable**, then re-run the migration.

## Commands

```bash
python3 backend/embed/relate.py embed  --user-id <uuid>              # embed included items
python3 backend/embed/relate.py relate --user-id <uuid> --reset     # score candidate pairs
python3 backend/embed/relate.py show   --user-id <uuid> --limit 20  # top pairs + signals
python3 backend/embed/relate.py status --user-id <uuid>             # counts
```

`relate` flags: `--reset` (clear existing pairs), `--k` (neighbours per item,
default 5), `--threshold` (min combined score, default 0.45).

## Tuning

- Too many weak pairs → raise `--threshold` (e.g. `0.55`).
- Too few → lower it (e.g. `0.35`) or raise `--k`.
- Signal weights live in `deterministic.py` (`_W_*`). Calendar-heavy data has
  short titles and empty bodies, so semantic + keyword/participant signals carry
  more weight than the body text.

## Idempotency & re-processing

- `embed` only embeds rows with `embedding IS NULL`.
- `relate --reset` recomputes cleanly; without `--reset` it upserts (updates
  scores for existing pairs).
- Re-ingesting a changed item (Stage 1) clears its `embedding`/`embedded_at`, so
  it is re-embedded and re-related.

## Next stage

**Stage 5 — Group & link to projects**: cluster these scored pairs into project
groups, use the LLM to name/summarize each project, and write
`project_source_links` (with `match_method`, `confidence`, `review_status`).
