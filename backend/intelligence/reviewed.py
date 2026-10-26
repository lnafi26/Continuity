"""F1B: local source-grounded review orchestration, with no database writes.

Returns normalized model output and a separate evidence review. This intentionally
never upgrades extracted claims to verified facts. Remote inference remains
synthetic-only and opt-in; the helper forces the offline router unless both
approval flags are explicitly true. No credentials or provider configurations
are persisted here.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from backend.intelligence.grounding import GroundingReport, review_extraction
from backend.intelligence.router import ModelRouter, RouterResult


@dataclass(frozen=True)
class ReviewedExtraction:
    inference: RouterResult
    review: GroundingReport


def extract_with_review(
    router: ModelRouter,
    source_item: Mapping[str, Any],
    *,
    source_id: str,
    remote_approved: bool = False,
    synthetic_test: bool = False,
) -> ReviewedExtraction:
    """Extract candidates and locally review verbatim source quotation anchors.

    Not a database writer or an agent endpoint. Set both booleans explicitly
    ONLY after manually previewing a genuinely fictional staging payload.
    """
    if not isinstance(source_id, str) or not source_id.strip():
        raise ValueError("An explicit source_id is required.")
    if not isinstance(source_item, Mapping):
        raise ValueError("source_item must be a mapping.")
    if not isinstance(router, ModelRouter):
        raise TypeError("router must be a ModelRouter.")
    for field in ("title", "extracted_text"):
        value = source_item.get(field)
        if value is not None and not isinstance(value, str):
            raise ValueError(f"{field} must be text.")

    payload = {"item": dict(source_item)}
    if remote_approved is True and synthetic_test is True:
        # Minimize even before invoking a provider. User IDs, sender addresses,
        # arbitrary metadata and private fields are never required for this
        # synthetic extraction task. The staging adapter minimizes again.
        payload["item"] = {
            field: source_item.get(field)
            for field in ("source_type", "title", "occurred_at", "extracted_text")
        }
        payload.update({"remote_approved": True, "synthetic_test": True})
        result = router.run("event_extraction", payload)
    else:
        # No primary provider may be contacted in unapproved code paths, even
        # if a caller supplied a custom network provider with weak controls.
        result = ModelRouter().run("event_extraction", payload)
    report = review_extraction(source_item, result.data, source_id=source_id)
    return ReviewedExtraction(inference=result, review=report)
