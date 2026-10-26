# Continuity private staging Space adapter — Phase 3C.3

The `StagingSpaceProvider` uses the already-running, private staging Space:
`https://lnafi-continuity-inference-staging.hf.space/v1/infer`.
It is **not enabled or registered in existing pipeline stages**. This module
makes no requests unless deliberately instantiated with `enabled=True`, and
an individual `ModelRouter.run` payload has both `remote_approved=True` and
`synthetic_test=True`. The staging gateway itself enforces these flags too.

Access requires **two different credentials**: a Hugging Face access token for
the private Space, and the Space's separate `CONTINUITY_SERVICE_TOKEN`.
Do not mix these with the staging Space's HF inference token.

```
from backend.intelligence import ModelRouter
from backend.intelligence.space_staging import StagingSpaceProvider

provider = StagingSpaceProvider()  # OFF by default, no credentials
router = ModelRouter(provider)
```

`provider.preview_request(task, payload)` creates the exact JSON body before
network access, filtering the fields to match the **staging gateway's schema**.
It drops sender/participant/email/URL/ID metadata, clips title/excerpt/text,
and enforces an 8 KB request bound. Text fields may still contain identifying
information: review previews manually. The `synthetic_test` flag alone does
not prove content is fictional. Never use real client, job, health, or inbox
material in this staging phase.

The router normalizes the Space's JSON, including limiting project symbols to
one uppercase letter, and falls back to local deterministic results on HTTP,
validation, or provider errors. This is *not* factual grounding validation.

No Supabase connection, Gmail ingestion, database write, or production deployment
is performed by the adapter or its unit tests. Existing pipeline `ModelRouter()`
instances stay offline. Leave `CONTINUITY_ENABLE_LEGACY_PIPELINE=false`.
