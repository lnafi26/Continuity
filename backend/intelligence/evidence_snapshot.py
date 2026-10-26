"""F1C: local, read-only candidate evidence snapshot for people and agents.

Consumes an already-reviewed extraction; it does NOT authenticate users, expose
an API, persist records, or promote AI claims to verified facts. Agent access
must later enforce per-source and per-project authorization separately.

Snapshot dates are deliberate: reported_at belongs to the original source,
observed_at is when this snapshot was assembled, and a claimed event date is
never falsely presented as a verified event timestamp.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from datetime import date, datetime
from typing import Any

from backend.intelligence.reviewed import ReviewedExtraction

SCHEMA_VERSION = "0.1"


def _date_only(value: Any) -> str | None:
    """Retain an extracted *date claim* without inferring an event time."""
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, str):
        try:
            return date.fromisoformat(value[:10]).isoformat()
        except ValueError:
            return None
    return None


def _candidate_id(source_id: str, kind: str, index: int, title: str,
                  quote: str | None) -> str:
    # Stable across repeated snapshots of identical candidates; NOT a globally
    # stable event identifier. Deduplication/revisions come in a later phase.
    serialized = json.dumps([source_id, kind, index, title, quote],
                            ensure_ascii=False, separators=(",", ":"))
    return "cand_" + hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:20]


def build_candidate_snapshot(
    reviewed: ReviewedExtraction,
    *,
    observed_at: datetime,
    continuity_id: str | None = None,
) -> dict[str, Any]:
    """Build a JSON-ready, candidate-only view with explicit source provenance.

    Never claims an item was executed, verified, or deployed. Retains evidence
    text and offsets only when review_extraction already matched the substring.
    Does not perform I/O, model calls, or modify its inputs.
    """
    if not isinstance(reviewed, ReviewedExtraction):
        raise TypeError("Pass a ReviewedExtraction from extract_with_review.")
    if not isinstance(observed_at, datetime) or observed_at.tzinfo is None or observed_at.utcoffset() is None:
        raise ValueError("observed_at must be a timezone-aware datetime.")
    if continuity_id is not None and (not isinstance(continuity_id, str) or not continuity_id.strip()):
        raise ValueError("continuity_id must be a nonempty string or None.")
    report, inference = reviewed.review, reviewed.inference
    if not isinstance(report.source_id, str) or not report.source_id.strip():
        raise ValueError("Reviewed report is missing source provenance.")
    if not isinstance(inference.data, dict):
        raise ValueError("Inference result must be a mapping of events and actions.")
    events, actions = inference.data.get("events"), inference.data.get("actions")
    if (not isinstance(events, list) or not isinstance(actions, list)
            or any(not isinstance(it, dict) for it in events + actions)):
        raise ValueError("Reviewed extraction has invalid event/action data.")
    by_kind = {"event": events, "action": actions}
    snapshot = {
        "schema_version": SCHEMA_VERSION,
        "snapshot_type": "unverified_extraction_candidates",
        "continuity_id": continuity_id.strip() if continuity_id is not None else None,
        "observed_at": observed_at.isoformat(),
        "source": {"id": report.source_id, "type": report.source_type,
                   "reported_at": report.reported_at},
        "inference": {"provider": inference.provider,
                      "fallback_used": inference.fallback_used,
                      "reason": inference.reason},
        "verification_state": "needs_review",
        "events": [],
        "actions": [],
    }
    seen = set()
    for item in report.items:
        if item.kind not in by_kind or not isinstance(item.index, int) or isinstance(item.index, bool):
            raise ValueError("Unexpected grounding-review item.")
        rows = by_kind[item.kind]
        key = (item.kind, item.index)
        if item.index < 0 or item.index >= len(rows) or key in seen:
            raise ValueError("Grounding review does not match extraction.")
        seen.add(key)
        raw = rows[item.index]
        if raw.get("title") != item.label or item.verification_state != "needs_review":
            raise ValueError("Grounding review and normalized output disagree.")
        anchor = None
        if item.anchor is not None:
            if (item.anchor.source_id != report.source_id
                    or item.anchor.field not in ("title", "extracted_text")
                    or item.anchor.start < 0 or item.anchor.end <= item.anchor.start
                    or item.anchor.end - item.anchor.start != len(item.anchor.quote)):
                raise ValueError("Invalid source anchor.")
            anchor = asdict(item.anchor)
        evidence_quote = item.anchor.quote if item.anchor is not None else None
        record = {
            "candidate_id": _candidate_id(report.source_id, item.kind, item.index,
                                          item.label, evidence_quote),
            "title": item.label,
            "verification_state": "needs_review",
            "evidence_state": item.evidence_state,
            "source_anchor": anchor,
            "review_flags": list(item.flags),
        }
        if item.kind == "event":
            record.update({
                "event_type_claim": raw.get("event_type"),
                "body_claim": raw.get("body", ""),
                "actor_claim": raw.get("person") or None,
                "event_date_claim": _date_only(raw.get("event_date")),
                "event_time_verified": False,
                "date_claim_verified": False,
                "requires_response_claim": raw.get("requires_response"),
            })
            snapshot["events"].append(record)
        else:
            record.update({
                "assignee_claim": raw.get("assignee"),
                "due_date_claim": _date_only(raw.get("due_date")),
                "status_claim": raw.get("status"),
                "status_verified": False,
                "due_date_verified": False,
                "backlog_claim": raw.get("backlog"),
            })
            snapshot["actions"].append(record)
    if len(seen) != len(events) + len(actions):
        raise ValueError("Grounding review did not cover all extracted candidates.")
    return snapshot
