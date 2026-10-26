# Stage 5 — Group & Link to Projects

This stage turns the candidate relationships from Stage 4 into actual named
**projects** and links each item to them. It implements the Stage 5 spec in
[Architecture.md](Architecture.md) and is the first stage whose output the
dashboard renders directly.

## What it produces

- **`projects`** rows (`origin = 'ai'`), one per cluster, each with a
  Claude-generated `name`, `summary`, and `symbol`.
- **`project_source_links`** rows joining items to their project
  (`match_method = 'ai'`, `confidence`, `explanation`, `review_status = 'pending'`).

## How it works

1. **Cluster** — connected components of the Stage 4 relationship graph
   (`item_relationships` edges with `combined_score >= threshold`). Each
   component is a candidate project; isolated items are singletons.
2. **Name** — for each cluster (size >= `--min-size`, default 2), send the item
   titles/senders/excerpts to **Claude Sonnet 5** and get back
   `{name, summary, symbol, coherence}`. Falls back to a keyword-derived name if
   the API key is missing or a call fails.
3. **Link** — upsert the project and write a `project_source_links` row per
   item. `confidence` blends structural cohesion (avg edge score) with the LLM's
   coherence; all links are `review_status = 'pending'` for Stage 8.

## Components

| File | Role |
|------|------|
| `backend/grouping/clustering.py` | Pure: connected components + cohesion |
| `backend/grouping/llm_namer.py` | Claude naming + keyword fallback |
| `backend/grouping/grouping_repo.py` | Fetch included/edges; create projects; link |
| `backend/grouping/group.py` | Orchestrator CLI (`preview`/`run`/`status`/`show`) |

Schema: `add_projects_origin` adds `projects.origin` so AI re-runs can reset
only AI-created projects. `projects` and `project_source_links` already existed.

## Setup

```bash
python3 -m pip install -r backend/requirements.txt   # adds anthropic
python3 backend/database/supabase_connections.py --title add_projects_origin
```
Set `ANTHROPIC_API_KEY` (and optionally `ANTHROPIC_MODEL=claude-sonnet-5`) in
`backend/.env`.

## Commands

```bash
python3 backend/grouping/group.py preview --user-id <uuid>            # cluster only, free
python3 backend/grouping/group.py run --user-id <uuid> --reset       # name + write (LLM)
python3 backend/grouping/group.py status --user-id <uuid>
python3 backend/grouping/group.py show --user-id <uuid>
```

`run`/`preview` flags: `--threshold` (edge score to connect, default 0.5),
`--min-size` (min cluster size, default 2). `run --reset` deletes existing AI
projects (cascades their links) before rebuilding; user-created projects
(`origin='user'`) are never touched.

## Cost

At ~40 included items the naming calls total a few cents on Sonnet 5. It scales
with the number of clusters, not raw items, and only re-runs on `--reset`.

## The Stage 3 work-only filter (layered)

Stage 5 is only as good as what Stage 3 lets through. Stage 3 keeps **work**
content only — projects, tasks, meetings, conferences, work training, project
discussions, and interviews the person attends/conducts — and drops everything
else. It has three layers, cheapest first:

1. **Deterministic noise rule** (`is_noise` in `classification.py`) — obvious
   bulk/automated mail (newsletters, `no-reply@`, marketing, `unsubscribe`) is
   excluded as `noise` without an LLM call. Free.
2. **Allowlist + work-actionable phrases** (`_ALLOWLIST_FRAGMENTS`,
   `_RELEVANCE_PHRASES`) — your own work senders/domains (add them here) and
   generic work cues like "action required" / "please review" skip the noise
   rule so they reach the work-gate rather than being auto-dropped. Free.
3. **LLM work-gate** (`relevance_gate.py`, Haiku 4.5) — runs **by default** on
   every non-noise item and classifies it work-vs-not-work; non-work items
   (personal errands, entertainment, job alerts, application confirmations) are
   excluded as `off_topic`. This is the layer that enforces work-only, since
   personal mail from a real person isn't "noise". It fails **open** (a call
   error keeps the item) so genuine work is never lost to a transient failure.
   Needs `ANTHROPIC_API_KEY`; pass `dedupe.py run --no-gate` to disable it and
   use the deterministic filter alone.

Add your own work senders/phrases to `classification.py`.

## Design decisions (per Architecture.md)

- **`--min-size 2`** by default so lone one-off items don't each become a
  trivial project. Architecture says "every item links to at least one project";
  pass `--min-size 1` for full coverage.
- **Idempotent re-runs** via `origin='ai'` + `--reset`.
- **Graceful degradation** — no API key or a failed call falls back to
  keyword-based names rather than failing the stage.
- **Everything is `review_status='pending'`** and source-linked, ready for
  Stage 8 review.

## Seeing the result

```sql
select p.symbol, p.name, p.summary, count(l.id) as items,
       round(avg(l.confidence),3) as avg_conf
from public.projects p
left join public.project_source_links l on l.project_id = p.id
where p.user_id = '<uuid>' and p.origin = 'ai'
group by p.id order by items desc;
```
These AI projects are exactly what the dashboard's project grid reads, so they
appear in the frontend for the signed-in user.

## Next stage

**Stage 6 — Extract events & actions**: for each linked item, extract timeline
`project_events` (email/file/meeting/decision/deadline/status) and
`project_actions` (title/assignee/due_date), source-linked and confidence-scored
— populating each project's timeline and "needs your attention" list.
