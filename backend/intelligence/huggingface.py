"""Opt-in Hugging Face Inference Providers adapter for Continuity.

Not selected by ModelRouter() or by any existing pipeline stage. No request
is made unless BOTH the instance is enabled and the individual task payload
contains ``remote_approved is True``. Errors are intentionally sanitized;
ModelRouter catches them and uses its existing offline fallback.
"""

from __future__ import annotations

import json
import re
from typing import Any

import requests

ENDPOINT = "https://router.huggingface.co/v1/chat/completions"
# Accept Hugging Face Hub model IDs plus an optional explicit provider suffix.
_MODEL_RE = re.compile(r"\A[A-Za-z0-9][\w.-]*/[A-Za-z0-9][\w.-]*(?::[A-Za-z0-9][\w.-]*)?\Z")
MAX_REPLY_CHARS = 40_000
MAX_EXCERPT_CHARS = 700
MAX_SOURCE_BODY_CHARS = 1200
MAX_EVENTS = 12
MAX_NAMING_ITEMS = 12

_SYSTEM = {
    "project_naming": (
        "You label groups of related projects and activities, including personal, "
        "educational and professional contexts. Use the provided evidence only. "
        "Return ONLY a JSON object with keys name, summary, symbol, category, "
        "coherence. category must be one of project, meeting_series, training, "
        "conference, interview, admin. coherence is a number between 0 and 1. "
        "Do not invent project details."
    ),
    "event_extraction": (
        "Extract events and explicit action items from the provided source. "
        "Use only statements grounded in the source; do not invent assignments "
        "or deadlines. Return ONLY a JSON object with arrays events and actions. "
        "An event has event_type, title, body, person, event_date, event_time, "
        "requires_response, confidence. An action has title, assignee, "
        "due_date, status, backlog, confidence. At most four of each. "
        "Use an empty actions array when nothing actionable is stated."
    ),
    "digest_summary": (
        "Write a concise factual recap of the provided project events. "
        "Emphasize decisions, issues and deadlines where supported. "
        "Do not invent information. Return ONLY a JSON object with one key, summary."
    ),
}
_LIMITS = {"project_naming": 300, "event_extraction": 850, "digest_summary": 180}


def _clip(value: Any, size: int) -> str:
    """Bound material sent remotely, without serializing arbitrary objects."""
    return value[:size] if isinstance(value, str) else ""


def _build_task_data(task: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Allowlist only fields the remote task genuinely needs.

    Emails, participants, arbitrary source metadata, credentials and IDs are
    excluded. Text supplied in title/body may still contain sensitive data;
    approval and local preview remain mandatory for remote use.
    """
    if task == "project_naming":
        items = payload.get("items", [])
        if not isinstance(items, list) or any(not isinstance(x, dict) for x in items):
            raise ValueError("Invalid project naming items.")
        return {"items": [{
            "title": _clip(it.get("title"), 120),
            "excerpt": _clip(it.get("excerpt"), MAX_EXCERPT_CHARS),
        } for it in items[:MAX_NAMING_ITEMS]]}
    if task == "event_extraction":
        item = payload.get("item")
        if not isinstance(item, dict):
            raise ValueError("Invalid event item.")
        return {"item": {
            "source_type": _clip(item.get("source_type"), 40),
            "title": _clip(item.get("title"), 160),
            "occurred_at": str(item.get("occurred_at") or "")[:40],
            "body": _clip(item.get("extracted_text"), MAX_SOURCE_BODY_CHARS),
        }}
    if task == "digest_summary":
        events = payload.get("events", [])
        if not isinstance(events, list) or any(not isinstance(x, dict) for x in events):
            raise ValueError("Invalid events list.")
        return {
            "project_name": _clip(payload.get("project_name"), 120),
            "events": [{
                "type": _clip(ev.get("event_type"), 30),
                "title": _clip(ev.get("title"), 160),
                "body": _clip(ev.get("body"), 250),
            } for ev in events[:MAX_EVENTS]],
        }
    raise ValueError("Unknown inference task.")


class HuggingFaceProvider:
    """InferenceProvider implementation with two independent opt-in gates.

    Use ``ModelRouter(HuggingFaceProvider(...))`` only in a deliberate call
    site. Ordinary pipeline stages continue to instantiate ``ModelRouter()``.
    """

    name = "huggingface"

    def __init__(self, *, model: str, token: str = "", enabled: bool = False,
                 timeout_seconds: float = 25.0):
        if not isinstance(model, str) or len(model) > 160 or not _MODEL_RE.fullmatch(model):
            raise ValueError("Use an explicit Hugging Face Hub model ID (org/model).")
        if not isinstance(timeout_seconds, (int, float)) or not 1 <= timeout_seconds <= 90:
            raise ValueError("timeout_seconds must be between 1 and 90.")
        self.model = model
        self._token = token
        self.enabled = enabled
        self.timeout_seconds = timeout_seconds

    def preview_request(self, task: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Show exactly what would be sent, minus authentication credentials.

        Local-only preview. Does not require approval and never performs I/O.
        Review this content before granting payload-level approval.
        """
        if task not in _SYSTEM:
            raise ValueError("Unknown inference task.")
        safe_data = _build_task_data(task, payload)
        return {
            "model": self.model,
            "messages": [
                {"role": "system", "content": _SYSTEM[task]},
                {"role": "user", "content": json.dumps(safe_data, ensure_ascii=False)},
            ],
            "stream": False,
            "temperature": 0.1,
            "max_tokens": _LIMITS[task],
        }

    def infer(self, task: str, payload: dict[str, Any]) -> dict[str, Any]:
        # Block *before* even preparing a prompt unless both gates are true.
        if not self.enabled:
            raise PermissionError("Hugging Face remote inference is disabled.")
        if not isinstance(payload, dict) or payload.get("remote_approved") is not True:
            raise PermissionError("This item has not been approved for remote inference.")
        if not isinstance(self._token, str) or not self._token.startswith("hf_"):
            raise ValueError("Missing valid-format Hugging Face token.")

        request_body = self.preview_request(task, payload)
        # Fixed HTTPS origin, no user-provided URL, no redirects, bounded wait.
        response = requests.post(
            ENDPOINT,
            json=request_body,
            headers={
                "Authorization": f"Bearer {self._token}",
                "Content-Type": "application/json",
            },
            timeout=self.timeout_seconds,
            allow_redirects=False,
        )
        if response.status_code != 200:
            raise RuntimeError("Hugging Face inference returned a non-200 status.")
        if len(response.content) > MAX_REPLY_CHARS:
            raise ValueError("Hugging Face response exceeded the size limit.")
        try:
            envelope = response.json()
            content = envelope["choices"][0]["message"]["content"]
            if not isinstance(content, str) or len(content) > MAX_REPLY_CHARS:
                raise ValueError("Invalid model completion.")
            result = json.loads(content)
            if not isinstance(result, dict):
                raise ValueError("Model completion was not a JSON object.")
            return result
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            # Never include provider response bodies or secrets in errors.
            raise ValueError("Model completion was not valid task JSON.") from exc
