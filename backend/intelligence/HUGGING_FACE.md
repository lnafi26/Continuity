# Hugging Face Inference Providers adapter — Phase 3C

This adapter is **not connected to Continuity's live ingestion pipeline**.
`ModelRouter()` still runs completely offline. No remote inference occurs
from installing or importing this file.

## Security model

Two explicit approvals are needed to send source-derived text to Hugging Face:

1. Construct `HuggingFaceProvider` with `enabled=True` (disabled by default).
2. Include `remote_approved: True` in the specific task payload. **Do not**
   automatically approve all items or infer approval from login/session state.

`preview_request(task, payload)` creates the exact JSON request body locally,
without sending anything or including the HF token. It drops metadata such as
sender, participants, source URL and arbitrary fields. **Titles, excerpts and
bodies can still contain private information.** Inspect the preview and use
only invented, nonsensitive examples during development.

The adapter sends a request only to the fixed HTTPS endpoint
`https://router.huggingface.co/v1/chat/completions`, refuses redirects, enforces
input/output length caps and a timeout, and returns JSON data to `ModelRouter`.
The router validates result shape and returns deterministic offline output on
network or model failures. It does not fact-check generated statements; add
source-grounded validation before automatically writing remote results to DB.

The adapter uses the existing `requests` dependency. There are no Hugging Face
SDK dependencies and no new environment variables or secrets required to
install or run the unit tests.

## Local-only smoke preview (no token, no remote calls)

Run this from the repository root:

```python
from backend.intelligence.huggingface import HuggingFaceProvider

hf = HuggingFaceProvider(model="example-org/example-model")
preview = hf.preview_request("project_naming", {
    "items": [{"title": "Synthetic website redesign", "excerpt": "Prototype approved"}]
})
print(preview)
```

When ready for a deliberate, synthetic-data live test, create a narrowly scoped
Hugging Face access token with Inference Providers permission. Keep it only in
local ignored configuration or a secret manager. Never commit, paste, or print
it. Choose a currently supported model/provider from Hugging Face's Inference
Providers catalog (not every model supports chat or reliable JSON outputs),
and review provider billing and privacy policies first.

For now **do not wire this adapter into Flask, enable legacy ingestion, or run
against client emails**. Later milestones will include a per-source consent UI,
permission scoping, remote inference budget controls, and provenance tracking.
