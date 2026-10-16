"""Opt-in Continuity staging Space adapter (synthetic data only).

Routes task requests to the fixed, private staging FastAPI Space. Its response
is normalized by ModelRouter; this adapter deliberately does not modify the
existing pipeline defaults. Two independent credentials are required:
Hugging Face private-Space access and Continuity service authentication.
"""
from __future__ import annotations

import json
import math
from datetime import date, datetime
from typing import Any

import requests

STAGING_ENDPOINT = "https://lnafi-continuity-inference-staging.hf.space/v1/infer"
TASKS = frozenset({"project_naming", "event_extraction", "digest_summary"})
MAX_REQUEST_BYTES = 8192  # Must fit staging gateway's limit.
MAX_RESPONSE_BYTES = 40000


def _text(value: Any, limit: int) -> str:
    if isinstance(value, str):
        return value[:limit]
    if isinstance(value, (date, datetime)):
        return value.isoformat()[:limit]
    return ""


def _minimize(task: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Create a field allowlist matching the *Space's* input schema.

    Do not send user IDs, email addresses, participants, URLs, or arbitrary
    source metadata. Titles/bodies may still contain sensitive information.
    """
    if task == "project_naming":
        items = payload.get("items")
        if not isinstance(items, list) or not items or any(not isinstance(x, dict) for x in items):
            raise ValueError("Project naming requires nonempty item dictionaries.")
        return {"items": [
            {"title": _text(it.get("title"), 120), "excerpt": _text(it.get("excerpt"), 700)}
            for it in items[:12]
        ]}
    if task == "event_extraction":
        item = payload.get("item")
        if not isinstance(item, dict):
            raise ValueError("Event extraction requires an item dictionary.")
        # The Space sanitizes `extracted_text` into its upstream `body` field.
        return {"item": {
            "source_type": _text(item.get("source_type"), 40),
            "title": _text(item.get("title"), 160),
            "occurred_at": _text(item.get("occurred_at"), 40),
            "extracted_text": _text(item.get("extracted_text"), 1200),
        }}
    if task == "digest_summary":
        events = payload.get("events")
        if not isinstance(events, list) or any(not isinstance(x, dict) for x in events):
            raise ValueError("Digest summary requires event dictionaries.")
        return {
            "project_name": _text(payload.get("project_name"), 120),
            "events": [
                {
                    "event_type": _text(ev.get("event_type"), 30),
                    "title": _text(ev.get("title"), 160),
                    "body": _text(ev.get("body"), 250),
                }
                for ev in events[:12]
            ],
        }
    raise ValueError("Unsupported inference task.")


class StagingSpaceProvider:
    """Private staging Space inference, disabled unless explicitly opted in.

    Construct with enabled=True and supply remote_approved=True AND
    synthetic_test=True on the individual ModelRouter.run payload. No user
    content should be sent until separate, production-ready consent controls.
    """

    name = "huggingface-space-staging"

    def __init__(self, *, hf_access_token: str = "", service_token: str = "",
                 enabled: bool = False, timeout_seconds: float = 60):
        if (not isinstance(timeout_seconds, (int, float))
                or not math.isfinite(timeout_seconds)
                or not 1 <= timeout_seconds <= 90):
            raise ValueError("Timeout must be between 1 and 90 seconds.")
        self._hf_access_token = hf_access_token
        self._service_token = service_token
        self.enabled = enabled
        self.timeout_seconds = timeout_seconds

    def preview_request(self, task: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Return the EXACT JSON body sent on approval, but never credentials.

        Local-only: no network, no secret checks, and no model calls.
        """
        if task not in TASKS or not isinstance(payload, dict):
            raise ValueError("Invalid staging inference request.")
        body = {
            "task": task,
            "payload": _minimize(task, payload),
            "remote_approved": True,
            "synthetic_test": True,
        }
        if len(json.dumps(body, ensure_ascii=False).encode("utf-8")) > MAX_REQUEST_BYTES:
            raise ValueError("Inference request exceeds staging size limit.")
        return body

    def infer(self, task: str, payload: dict[str, Any]) -> dict[str, Any]:
        if not self.enabled:
            raise PermissionError("Remote staging inference disabled.")
        if not isinstance(payload, dict) or payload.get("remote_approved") is not True:
            raise PermissionError("Remote inference was not approved for this item.")
        if payload.get("synthetic_test") is not True:
            raise PermissionError("Staging accepts explicitly marked synthetic tests only.")
        if not isinstance(self._hf_access_token, str) or not self._hf_access_token.startswith("hf_"):
            raise ValueError("Missing Hugging Face private-Space access token.")
        if not isinstance(self._service_token, str) or len(self._service_token) < 32:
            raise ValueError("Missing Continuity staging service token.")
        body = self.preview_request(task, payload)
        response = requests.post(
            STAGING_ENDPOINT,
            headers={
                "Authorization": f"Bearer {self._hf_access_token}",
                "X-Continuity-Service-Token": self._service_token,
                "Content-Type": "application/json",
            },
            json=body,
            timeout=self.timeout_seconds,
            allow_redirects=False,
        )
        if response.status_code != 200 or len(response.content) > MAX_RESPONSE_BYTES:
            raise RuntimeError("Staging inference unavailable or rejected.")
        try:
            result = response.json()
            if (
                not isinstance(result, dict)
                or result.get("ok") is not True
                or result.get("environment") != "staging"
                or result.get("provider") != "huggingface"
                or result.get("task") != task
                or not isinstance(result.get("result"), dict)
            ):
                raise ValueError("Unexpected inference response.")
            return result["result"]
        except (ValueError, TypeError):
            raise ValueError("Staging inference returned invalid structured output.") from None
