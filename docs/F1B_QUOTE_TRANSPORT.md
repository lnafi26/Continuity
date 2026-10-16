# Phase F1B — Evidence quote transport and local review

This patch transports optional **verbatim** `evidence_quote` fields through
`ModelRouter`'s extraction normalization and adds `extract_with_review(...)` for
local evidence review. All records remain **needs_review**, including records
with exact source spans. Quotes are never proof that a model claim is entailed.

The existing staging Space does not yet ask models to produce `evidence_quote`.
That change is a separate deployment step, after local tests. Until then,
model results without quotes remain unanchored. Do not fabricate anchors.

`extract_with_review(ModelRouter(), item, source_id="synthetic-id")` is offline.
To deliberately use an opted-in staging provider with **fictional data only**,
first preview the `StagingSpaceProvider` payload and then set BOTH
`remote_approved=True` and `synthetic_test=True`; the provider additionally
requires its private access token and service token. The helper never writes to
Supabase. It does not enable ingestion, web routes, or agent write access.

The existing `backend/extract/extract.py` Stage 6 remains offline, and
`CONTINUITY_ENABLE_LEGACY_PIPELINE` remains disabled by default.

Quotes are only transported with their original text, with an upper length
bound; title and body are still independent model-generated claims. The
`GroundingReport` attaches offsets when the quotation exists *verbatim* in the
source. It flags missing/unmatched quotes, unsupported new wording, and other
anomalies. It does **not** independently verify classification, roles, dates,
or content semantics.

## Run locally from the repository root

```bash
python -m unittest discover -s backend/tests -p 'test_*.py' -v
git diff --check
git status --short
```

Expected total after Phase F1B: 98 tests (82 before + 16 new).
Do not commit until full suite runs clean. The changes are limited to
`backend/intelligence/router.py`, `backend/intelligence/reviewed.py`,
`backend/tests/test_reviewed.py`, and this document.
