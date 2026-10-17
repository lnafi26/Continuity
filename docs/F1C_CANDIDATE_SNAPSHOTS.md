# Phase F1C — Candidate evidence snapshot (read-only, local)

**Why:** Continuity is intended to be living memory for people and AI agents, not
just a retrospective timeline. The first shared representation must explicitly
separate observed source text, AI interpretation, and current verified facts.

`build_candidate_snapshot(reviewed, observed_at=aware_datetime, continuity_id=None)`
consumes only the output of F1B `extract_with_review(...)` and produces a
JSON-serializable dictionary. It makes **no model calls, database writes, or
network requests**. It is NOT an authenticated agent API, a synchronization
engine, or a permission layer. The pipeline defaults remain offline.

## Reading a record

- `source.id`, `source.type`, `source.reported_at` identify the underlying item,
  *not* the event's occurrence time.
- `observed_at` is when the snapshot was assembled, supplied by the caller.
- `source_anchor` includes the exact matched text and half-open source offsets,
  or null when no precise quote could be matched.
- `verification_state=needs_review` remains mandatory, whether anchored or not.
- `event_date_claim` is **date-only**. The extractor previously reused the
  source's time-of-day in some cases; this snapshot explicitly refuses to
  promote such timestamps to verified event times.
- `status_claim`, `actor_claim`, `assignee_claim` and deadlines are AI claims,
  never confirmed project status or agent instructions.
- `continuity_id` is supplied explicitly or null, never inferred by filename,
  source type or overlapping terminology.
- `candidate_id` is a repeatable identifier for **this candidate shape** only;
  it is not yet a canonical event ID or source deduplication key.

## Example (offline)

```python
from datetime import datetime, timezone
from backend.intelligence import ModelRouter
from backend.intelligence.reviewed import extract_with_review
from backend.intelligence.evidence_snapshot import build_candidate_snapshot

item = {"source_type": "upload", "title": "Fictional example",
        "extracted_text": "Example status update.", "occurred_at": None}
reviewed = extract_with_review(ModelRouter(), item, source_id="fictional-001")
snapshot = build_candidate_snapshot(reviewed, observed_at=datetime.now(timezone.utc))
# Review candidate records; NEVER treat these as verified decisions.
```

## Scope and limitations

This is a **schema and display prototype**, not durable storage. Before any
real-data use or agent retrieval, implement per-user / per-source authorization,
source retention controls, consent, append-only observation history, full claim
reconciliation, project identity resolution, and correction/retraction paths.
The extractor and grounding heuristic are not semantic fact checkers. Access
control must protect the exact quotations and any original source text.

## Tests

```bash
python -m unittest discover -s backend/tests -p 'test_*.py' -v
git diff --check
git status --short
```

16 new tests; expected total is 114 (98 existing + 16 new). Do not commit
until this passes in the actual Continuity environment.
