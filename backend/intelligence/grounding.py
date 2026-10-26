"""Offline, non-authoritative source-grounding review for model extraction.

Phase F1A: annotate model-produced event/action candidates with exact, local
source spans and review flags. NEVER promotes an AI claim to a verified fact,
never writes to a database, and never performs network requests.

An anchored quotation proves only that the quoted TEXT occurs in the source;
it does not prove that the model's paraphrase, role assignment, status, or
conclusion is entailed by that text. Human/source-aware verification is a
separate future step.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from datetime import date, datetime
from typing import Any, Mapping

_WORDS = re.compile(r"[A-Za-z][A-Za-z'-]{2,}")
# Conservative signal, not an automatic classification rule.
_DECISION = re.compile(r"\b(?:approved?|decided?|selected|authorized|signed\s+off)\b", re.I)
_STOP = frozenset({
    "the", "and", "but", "for", "with", "from", "that", "this", "were", "was",
    "are", "has", "have", "had", "into", "about", "during", "after", "before",
    "will", "who", "when", "where", "which", "their", "them", "they", "our",
    "its", "his", "her", "not", "yet", "did", "does", "been", "being", "also",
    "upon", "under", "over", "then", "than", "only", "each", "while", "would",
    "should", "could", "can", "all", "one", "two", "three", "update", "updated",
})


@dataclass(frozen=True)
class SourceSpan:
    source_id: str
    field: str  # 'title' or 'extracted_text'
    start: int  # half-open character offsets into the original field
    end: int
    quote: str


@dataclass(frozen=True)
class ReviewItem:
    kind: str  # 'event' or 'action'
    index: int
    label: str
    anchor: SourceSpan | None
    flags: tuple[str, ...]
    evidence_state: str  # 'anchored' or 'unanchored'
    verification_state: str = "needs_review"  # NEVER auto-verified in F1A


@dataclass(frozen=True)
class GroundingReport:
    source_id: str
    source_type: str
    reported_at: str | None
    items: tuple[ReviewItem, ...]
    assessment: str = "preliminary_not_factual_verification"

    def to_dict(self) -> dict[str, Any]:
        """Stable JSON-serializable shape for future UI and agent snapshots."""
        return asdict(self)


def _find_span(source_id: str, fields: Mapping[str, str], quote: Any) -> SourceSpan | None:
    # Exact substring match; do not silently convert paraphrases into citations.
    if not isinstance(quote, str) or len(quote.strip()) < 14 or len(quote.split()) < 3:
        return None
    for field in ("extracted_text", "title"):
        original = fields[field]
        start = original.find(quote)
        if start != -1:
            return SourceSpan(source_id, field, start, start + len(quote), quote)
    return None


def _content_terms(value: str) -> set[str]:
    return {w.lower() for w in _WORDS.findall(value) if w.lower() not in _STOP}


def _novel_terms(body: str, source_text: str) -> list[str]:
    """Only a review signal: synonyms/paraphrases can cause false positives."""
    return sorted(_content_terms(body) - _content_terms(source_text))


def _date_in_quote(value: Any, quote: str) -> bool:
    if isinstance(value, datetime):
        value = value.date()
    elif isinstance(value, str):
        try:
            value = date.fromisoformat(value[:10])
        except ValueError:
            return False
    if not isinstance(value, date):
        return False
    forms = (value.isoformat(), f"{value.strftime('%B')} {value.day}, {value.year}",
             f"{value.strftime('%b')} {value.day}, {value.year}",
             f"{value.month}/{value.day}/{value.year}")
    return any(form.casefold() in quote.casefold() for form in forms)


def _possible_decision(event: Mapping[str, Any], source_text: str) -> bool:
    title = event.get("title", "")
    return (isinstance(title, str) and bool(_DECISION.search(title))
            and bool(_DECISION.search(source_text))
            and event.get("event_type") != "decision")


def review_extraction(
    source_item: Mapping[str, Any],
    extraction: Mapping[str, Any],
    *,
    source_id: str,
) -> GroundingReport:
    """Review extracted event/action candidates against exactly one source.

    Models may optionally return `evidence_quote` per event/action, containing
    *verbatim* source text. Missing quotes stay unanchored. Even with a matching
    quote, ALL model-produced claims remain `needs_review` in this phase.

    No mutation, API calls, database writes, implicit source IDs, or approval.
    Do not treat the synthetic_test flag as an actual privacy control.
    """
    if not isinstance(source_id, str) or not source_id.strip():
        raise ValueError("An explicit source_id is required for provenance.")
    if not isinstance(source_item, Mapping) or not isinstance(extraction, Mapping):
        raise ValueError("Source and extraction must be mappings.")
    fields: dict[str, str] = {}
    for name in ("title", "extracted_text"):
        value = source_item.get(name, "")
        if value is not None and not isinstance(value, str):
            raise ValueError(f"Source {name} must be text.")
        fields[name] = value or ""
    source_text = "\n".join(fields.values())
    result: list[ReviewItem] = []
    for kind, key in (("event", "events"), ("action", "actions")):
        entries = extraction.get(key, [])
        if not isinstance(entries, list) or any(not isinstance(it, Mapping) for it in entries):
            raise ValueError(f"{key} must be a list of objects.")
        for index, entry in enumerate(entries):
            raw_quote = entry.get("evidence_quote")
            anchor = _find_span(source_id, fields, raw_quote)
            flags: list[str] = []
            if anchor is None:
                flags.append("missing_evidence_quote" if not raw_quote else "unmatched_evidence_quote")
            if kind == "event":
                if _possible_decision(entry, source_text):
                    flags.append("possible_decision_misclassification")
                body = entry.get("body", "")
                if isinstance(body, str) and _novel_terms(body, source_text):
                    flags.append("paraphrase_has_new_terms")
                # 'Alex' appearing elsewhere in the message does not establish
                # that Alex made the particular decision described by this event.
                if entry.get("person"):
                    flags.append("person_role_not_verified")
                label = entry.get("title", "")
            else:
                if entry.get("assignee"):
                    flags.append("assignee_role_not_verified")
                due = entry.get("due_date")
                if due and not (anchor and _date_in_quote(due, anchor.quote)):
                    flags.append("due_date_needs_evidence_review")
                label = entry.get("title", "")
            if not isinstance(label, str):
                label = ""
            result.append(ReviewItem(
                kind=kind, index=index, label=label[:200], anchor=anchor,
                flags=tuple(flags),
                evidence_state="anchored" if anchor is not None else "unanchored",
            ))
    occurred = source_item.get("occurred_at")
    if isinstance(occurred, (date, datetime)):
        reported_at = occurred.isoformat()
    elif isinstance(occurred, str):
        reported_at = occurred[:50]
    else:
        reported_at = None
    typ = source_item.get("source_type", "unknown")
    return GroundingReport(
        source_id=source_id.strip(),
        source_type=typ if isinstance(typ, str) else "unknown",
        reported_at=reported_at,
        items=tuple(result),
    )
