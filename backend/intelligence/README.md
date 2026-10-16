# Continuity inference boundary (Phase 3A)

`ModelRouter()` **defaults to offline-only** and makes no HTTP calls. It wraps
existing deterministic behavior from the inherited code:

| Task | Payload | Result data |
| ---- | ------- | ----------- |
| `project_naming` | `{"items": [source_item_dict, ...]}` | name, summary, symbol, category, coherence |
| `event_extraction` | `{"item": source_item_dict}` | `events`, `actions` (Python date/datetime values may appear) |
| `digest_summary` | `{"project_name": str, "events": [event_dict, ...]}` | `summary` |

```python
from backend.intelligence import ModelRouter
router = ModelRouter()
result = router.run("project_naming", {"items": [{"title": "Website kickoff"}]})
print(result.provider, result.data["name"])
```

A future opt-in provider must implement `name` and
`infer(task: str, payload: dict) -> dict`. The router normalizes results and
falls back to deterministic implementations if the provider raises or returns
invalid structure. It does **not** validate factual grounding of arbitrary
model-generated content: that requires separate provenance and review tests.

**Scope:** This phase introduces only the interface. It does not change any
existing pipeline stage, enable Claude, call Hugging Face, or send source data
to external services. The old work-only relevance filter is not connected to
this router and must be redesigned before enabling ingestion. Live or remote
providers must be explicitly configured with scoped permissions and privacy
controls. Do not turn on `CONTINUITY_ENABLE_LEGACY_PIPELINE` for this phase.
