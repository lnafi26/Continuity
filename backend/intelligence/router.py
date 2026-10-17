"""Provider-independent task router, initially offline-only.

Model providers implement ``infer(task, payload) -> dict``. No provider is
configured by default; this module never starts network requests itself.
Existing deterministic fallbacks are reused rather than reimplemented.

The router is intentionally NOT connected to the inherited Claude pipeline
or Flask routes yet. That integration comes after adapter tests and privacy
controls have been reviewed.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol

from backend.digest import summarizer
from backend.extract import extractor
from backend.grouping import llm_namer

SUPPORTED_TASKS = frozenset({
    "project_naming", "event_extraction", "digest_summary"
})
CATEGORIES = frozenset({
    "project", "meeting_series", "training", "conference", "interview", "admin"
})


class InferenceProvider(Protocol):
    """Interface for future local Ollama/Hugging Face model adapters."""

    name: str

    def infer(self, task: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Return a JSON-style value for the requested task."""


@dataclass(frozen=True)
class RouterResult:
    data: dict[str, Any]
    provider: str
    fallback_used: bool
    reason: str | None = None


class OfflineProvider:
    """Existing deterministic behaviors, with no network or API key usage."""

    name = "offline"

    def infer(self, task: str, payload: dict[str, Any]) -> dict[str, Any]:
        if task == "project_naming":
            return llm_namer.keyword_name(payload["items"])
        if task == "event_extraction":
            return extractor.extract(payload["item"], api_key=None)
        if task == "digest_summary":
            return {
                "summary": summarizer.summarize(
                    payload["project_name"], payload["events"], api_key=None
                )
            }
        raise ValueError(f"Unsupported inference task: {task}")


def _validated_payload(task: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    """Reject programmer errors before any provider sees project information."""
    if task not in SUPPORTED_TASKS:
        raise ValueError(f"Unsupported inference task: {task}")
    if not isinstance(payload, Mapping):
        raise ValueError("Inference payload must be a mapping.")
    data = dict(payload)
    if task == "project_naming":
        items = data.get("items")
        if not isinstance(items, list) or any(not isinstance(x, dict) for x in items):
            raise ValueError("project_naming requires a list of item dictionaries.")
    elif task == "event_extraction":
        if not isinstance(data.get("item"), dict):
            raise ValueError("event_extraction requires an item dictionary.")
    elif task == "digest_summary":
        if not isinstance(data.get("project_name"), str):
            raise ValueError("digest_summary requires a project_name string.")
        events = data.get("events")
        if not isinstance(events, list) or any(not isinstance(x, dict) for x in events):
            raise ValueError("digest_summary requires a list of event dictionaries.")
    return data


def _normalize_result(task: str, value: Any, payload: dict[str, Any]) -> dict[str, Any]:
    """Validate provider output before exposing it to project/database code."""
    if not isinstance(value, dict):
        raise ValueError("Provider returned a non-object response.")
    if task == "project_naming":
        name = value.get("name")
        if not isinstance(name, str) or not name.strip():
            raise ValueError("Project name missing or invalid.")
        summary = value.get("summary", "")
        if not isinstance(summary, str):
            raise ValueError("Project summary must be text.")
        coherence = value.get("coherence", 0.5)
        try:
            coherence = float(coherence)
        except (ValueError, TypeError) as exc:
            raise ValueError("Invalid coherence score.") from exc
        if not math.isfinite(coherence):
            raise ValueError("Non-finite coherence score.")
        category = value.get("category", "project")
        category = category if isinstance(category, str) and category in CATEGORIES else "project"
        symbol = value.get("symbol")
        if not isinstance(symbol, str) or not symbol.strip():
            symbol = name[0]
        return {
            "name": name.strip()[:60],
            "summary": summary.strip()[:500],
            "symbol": symbol.strip()[:1].upper(),
            "category": category,
            "coherence": max(0.0, min(1.0, coherence)),
        }
    if task == "event_extraction":
        events, actions = value.get("events"), value.get("actions")
        if (
            not isinstance(events, list)
            or not isinstance(actions, list)
            or any(not isinstance(x, dict) for x in events + actions)
        ):
            raise ValueError("Events and actions must be arrays of objects.")
        # Reuse the existing field/date/status validator for external model
        # output. The offline fallback is already normalized by extractor.
        if not events:
            raise ValueError("An event is required for a source item.")
        normalized = extractor._normalize(value, payload["item"])
        # F1B: preserve *optional* verbatim evidence quotations after the legacy
        # event/action normalizer removes fields it does not recognize. Quotes
        # must stay unmodified: stripping or clipping would forge source spans.
        # This transports a claim of evidence; it does NOT verify that claim.
        if not isinstance(normalized, dict):
            raise ValueError("Invalid normalized extraction.")
        for key in ("events", "actions"):
            candidates = value[key][:4]
            if key == "actions":
                # The normalizer discards actions with empty titles. Align with
                # its rule, rather than attaching an earlier action's quote to
                # a different action after filtering.
                candidates = [x for x in candidates if str(x.get("title", "")).strip()]
            output = normalized.get(key)
            if not isinstance(output, list) or len(output) != len(candidates):
                continue  # Ambiguous mapping: do not attach evidence.
            for raw, row in zip(candidates, output):
                if not isinstance(row, dict):
                    continue
                expected_title = (str(raw.get("title", "")).strip() or "(untitled)")[:200]
                if row.get("title") != expected_title:
                    # Length alone does not establish correspondence if a
                    # different normalizer reorders the candidates.
                    continue
                quote = raw.get("evidence_quote")
                if isinstance(quote, str) and 14 <= len(quote) <= 500 and len(quote.split()) >= 3:
                    row["evidence_quote"] = quote
        return normalized
    if task == "digest_summary":
        summary = value.get("summary")
        if not isinstance(summary, str) or not summary.strip():
            raise ValueError("Summary is missing or invalid.")
        return {"summary": summary.strip()[:500]}
    raise ValueError(f"Unsupported inference task: {task}")


class InferenceUnavailableError(RuntimeError):
    """Safe, structured failure when neither provider can produce an answer.

    Caller-facing diagnostics intentionally never include the source payload,
    credentials, third-party response body, or raw exception message.
    Rejected programmer input still raises ValueError before inference starts.
    """

    code = "inference_unavailable"

    def __init__(self, task: str, *, primary_configured: bool):
        self.task = task
        self.primary_configured = primary_configured
        super().__init__("Inference could not be completed; no result was produced.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": str(self),
            "task": self.task,
            "primary_configured": self.primary_configured,
        }


class ModelRouter:
    """Opt-in provider with deterministic fallback and explicit provenance.

    Passing no primary provider guarantees no model service is contacted.
    Provider errors never silently create a project or delete source data.
    """

    def __init__(self, primary: InferenceProvider | None = None):
        self.primary = primary
        self.offline = OfflineProvider()

    def run(self, task: str, payload: Mapping[str, Any]) -> RouterResult:
        data = _validated_payload(task, payload)
        if self.primary is not None:
            try:
                output = self.primary.infer(task, data)
                normalized = _normalize_result(task, output, data)
                return RouterResult(normalized, self.primary.name, False)
            except Exception:  # Fail closed on model output, not on source retention.
                reason = "primary_failed_validation_or_execution"
        else:
            reason = "no_primary_provider"
        try:
            output = self.offline.infer(task, data)
            normalized = _normalize_result(task, output, data)
        except Exception:
            # No fabricated success, no raw exception details crossing the
            # boundary. Source retention / retry policy is owned by the caller.
            raise InferenceUnavailableError(
                task, primary_configured=self.primary is not None
            ) from None
        return RouterResult(normalized, self.offline.name, True, reason)
