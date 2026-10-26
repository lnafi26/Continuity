# F1A — source-grounding review (offline, no writes)

## Purpose

Continuity must support active work by both humans and AI agents while retaining
context that is backed by identifiable source material. An AI's output should
not be silently converted into a confirmed fact just because its JSON is valid.

`backend/intelligence/grounding.py` is the **first isolated review step**, not
a full fact-checking engine. It **does not** change `ModelRouter`, live ingestion,
Hugging Face staging, Supabase schema, or the legacy pipeline. It makes no API
requests or DB writes.

`review_extraction(source_item, model_result, source_id="<source item's stable ID>")`
returns a `GroundingReport` containing one record per event/action:

- Source identity and original report timestamp, if present.
- An optional `SourceSpan` with **verbatim** `evidence_quote` and source offsets.
- Signals for missing/fabricated quotes, possible decision misclassification,
  unverified actor/assignee attribution, missing deadline support, and novel
  wording in a generated event body.
- `verification_state="needs_review"` **always**. A matching quote is an
  anchor to inspect, **not** automatic factual verification.

The backend's current Space contract does not request `evidence_quote`. So all
existing Space extraction outputs will initially be **unanchored**. That is
intentional: the code refuses to invent citations. Future model-output schema
changes should ask for exact spans and still verify them locally.

### Local regression test

```bash
python -m unittest backend.tests.test_grounding -v
python -m unittest discover -s backend/tests -p "test_*.py" -v
git diff --check
```

All tests use synthetic material and perform no network requests.

## Known limitations and next steps

This is **not semantic entailment checking**. Novel-word detection is a crude
flag for human/agent review, not a rejection algorithm. An exact quote may
support an occurrence of text without supporting the model's broader
interpretation. Classification mismatch checks can both miss errors and flag
valid content. A source timestamp is not the event's actual timestamp.

Next: add quote requirements to structured hosted inference outputs; implement
claim-specific provenance, decisions vs intentions vs executed work, immutable
revisions, user-confirmation states, and safe persistence behind owner RLS.
For agent retrieval, make a future read-only, authenticated context snapshot
that identifies freshness, last observed change, evidence links, blockers,
next actions, and unverified claims separately. Do not silently grant agents
write access to project memory or individual source permissions.

Never run real project content through the synthetic-only staging service.
