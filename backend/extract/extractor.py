"""Extract timeline events and action items from one item (Stage 6, Haiku 4.5).

Given a single source item (email or calendar event) with its project context,
asks a cheap model for a small set of typed timeline events and actionable
to-dos. Normalizes the result (event types, dates, persons) so the caller can
insert directly. Falls back to a single metadata-derived event when no API key
is set or a call fails, so extraction never blocks the pipeline.
"""

from __future__ import annotations

import json
import re
from datetime import date, datetime, timezone

DEFAULT_EXTRACT_MODEL = "claude-haiku-4-5"

_EVENT_TYPES = {"email", "file", "meeting", "decision", "deadline", "status", "note", "issue"}
_ACTION_STATUSES = {"not_started", "in_progress", "completed"}

_SYSTEM = (
    "You extract structured timeline events and action items from a single work "
    "item (an email or a calendar event). Reply with ONLY a JSON object, no prose."
)


def _prompt(item: dict) -> str:
    return (
        "Item:\n"
        f"  type: {item.get('source_type')}\n"
        f"  subject/title: {item.get('title') or '(none)'}\n"
        f"  from: {item.get('sender') or '(unknown)'}\n"
        f"  participants: {', '.join(item.get('participants') or []) or '(none)'}\n"
        f"  date: {item.get('occurred_at') or '(unknown)'}\n"
        f"  body: {(item.get('extracted_text') or '')[:1200]}\n\n"
        "Return a JSON object:\n"
        '{\n'
        '  "events": [ {"event_type": one of '
        "email|file|meeting|decision|deadline|status|note|issue -- use 'issue' "
        "for a blocker, risk, disagreement/differing opinion, or problem raised "
        "(not yet resolved into a decision); use 'decision' only once something "
        "was actually decided, "
        '"title": short, "body": one sentence, "person": name or email or "", '
        '"event_date": "YYYY-MM-DD" -- the date this actually happens/happened, '
        "which can differ from the item's own date (e.g. a meeting mentioned "
        "inside an email, or a deadline computed from one); use the item's own "
        'date if this coincides with it, or null if truly unknown, '
        '"event_time": "HH:MM" in 24-hour time ONLY if a specific time is '
        'stated in the text (e.g. "2pm" -> "14:00"), else null -- never guess one, '
        '"requires_response": true only if this item genuinely needs a reply '
        'or response from the recipient personally (not an FYI, notification, '
        'or something already resolved), else false, '
        '"confidence": 0.0-1.0} ],\n'
        '  "actions": [ {"title": an imperative task the recipient should do, '
        '"assignee": name or email or "", "due_date": "YYYY-MM-DD" or null, '
        '"status": one of not_started|in_progress|completed -- infer from the '
        'text: explicit completion language means completed, explicit '
        'ongoing/in-flight language means in_progress, otherwise not_started, '
        '"backlog": true if this is a suggested-but-not-urgent action with no '
        'explicit owner or due date, else false, '
        '"confidence": 0.0-1.0} ]\n'
        "}\n\n"
        "Rules: events summarize what happened; actions are things to do next. "
        "Always include at least one event describing this item. If there is "
        "nothing to act on, use an empty actions list. At most 4 events and 4 "
        "actions. Use the item's date and sender when a date or person is not "
        "otherwise stated. Be conservative with requires_response -- when in "
        "doubt, false."
    )


def _parse_time_of_day(value) -> tuple[int, int] | None:
    """Parse an "HH:MM" string the model gave because the text actually
    stated a time. Returns None for anything else -- we never guess."""
    if not isinstance(value, str):
        return None
    try:
        hh, mm = value.strip()[:5].split(":")
        hour, minute = int(hh), int(mm)
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return hour, minute
    except (ValueError, TypeError):
        pass
    return None


def _parse_date(date_value, time_value, fallback) -> object:
    """Combine the LLM's date with a time-of-day, preferring (in order):
      1. An explicit time the model gave, because the text actually stated
         one ("2pm" -> "14:00").
      2. The source item's own time-of-day, but ONLY when the model's date
         agrees with the source's calendar day -- in that case the event
         genuinely is the source item, so its precise timestamp is known,
         not guessed.
      3. Noon UTC, when the model's date is a *different* day than the
         source and no time was stated -- we genuinely don't know the time
         on that other day, so a neutral placeholder beats either midnight
         UTC (which rolls back to the *previous* day once the frontend
         formats it in any negative-UTC-offset timezone, silently shifting
         the event a day earlier than it happened) or borrowing the
         source's time (misleading whenever the event happens at a
         different time than when the message was created, e.g. an email
         sent at midnight about a meeting "Thursday at 2pm").
    """
    if isinstance(date_value, str):
        try:
            d = date.fromisoformat(date_value[:10])
        except ValueError:
            return fallback
        explicit = _parse_time_of_day(time_value)
        if explicit:
            hour, minute = explicit
        elif isinstance(fallback, datetime) and (d.year, d.month, d.day) == (
            fallback.year, fallback.month, fallback.day,
        ):
            hour, minute = fallback.hour, fallback.minute
        else:
            hour, minute = 12, 0
        return datetime(d.year, d.month, d.day, hour, minute, tzinfo=timezone.utc)
    return fallback


def _parse_due(value):
    if isinstance(value, str):
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None
    return None


def _clamp01(value) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return 0.5


def _parse_bool(value) -> bool | None:
    """Parse a tri-state boolean: True/False, or None if unrecognized/missing."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        v = value.strip().lower()
        if v in ("true", "yes", "1"):
            return True
        if v in ("false", "no", "0"):
            return False
    return None


def _parse_status(value) -> str:
    v = str(value or "").strip().lower()
    return v if v in _ACTION_STATUSES else "not_started"


def _extract_json(text: str) -> dict | None:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                return None
    return None


def _fallback(item: dict) -> dict:
    kind = "meeting" if item.get("source_type") == "google_calendar" else "email"
    return {
        "events": [{
            "event_type": kind,
            "title": (item.get("title") or "(untitled)")[:200],
            "body": "",
            "person": item.get("sender") or "",
            "event_date": item.get("occurred_at"),
            # No LLM call happened, so this is genuinely unclassified rather
            # than a guessed False -- Stage 7/10 treat None as "not yet judged".
            "requires_response": None,
            "confidence": 0.4,
        }],
        "actions": [],
    }


def _normalize(data: dict, item: dict) -> dict:
    occurred = item.get("occurred_at")
    events = []
    for ev in (data.get("events") or [])[:4]:
        etype = str(ev.get("event_type", "note")).lower().strip()
        if etype not in _EVENT_TYPES:
            etype = "note"
        events.append({
            "event_type": etype,
            "title": (str(ev.get("title", "")).strip() or "(untitled)")[:200],
            "body": str(ev.get("body", "")).strip()[:1000],
            "person": str(ev.get("person", "")).strip()[:200]
                      or (item.get("sender") or ""),
            "event_date": _parse_date(ev.get("event_date"), ev.get("event_time"), occurred),
            "requires_response": _parse_bool(ev.get("requires_response")),
            "confidence": _clamp01(ev.get("confidence", 0.6)),
        })
    if not events:  # always keep at least one event
        events = _fallback(item)["events"]

    actions = []
    for ac in (data.get("actions") or [])[:4]:
        title = str(ac.get("title", "")).strip()
        if not title:
            continue
        actions.append({
            "title": title[:200],
            "assignee": str(ac.get("assignee", "")).strip()[:200] or None,
            "due_date": _parse_due(ac.get("due_date")),
            "status": _parse_status(ac.get("status")),
            "backlog": bool(_parse_bool(ac.get("backlog")) or False),
            "confidence": _clamp01(ac.get("confidence", 0.6)),
        })
    return {"events": events, "actions": actions}


def extract(item: dict, *, api_key: str | None, model: str = DEFAULT_EXTRACT_MODEL) -> dict:
    """Return {events: [...], actions: [...]} for one item. Never raises."""
    if not api_key:
        return _normalize(_fallback(item), item)
    try:
        import anthropic

        client = anthropic.Anthropic(api_key=api_key)
        resp = client.messages.create(
            model=model,
            max_tokens=800,
            system=_SYSTEM,
            messages=[{"role": "user", "content": _prompt(item)}],
        )
        text = "".join(
            block.text for block in resp.content
            if getattr(block, "type", None) == "text"
        )
        data = _extract_json(text)
        if not data:
            return _normalize(_fallback(item), item)
        return _normalize(data, item)
    except Exception:  # noqa: BLE001 - fall back rather than fail the stage
        return _normalize(_fallback(item), item)
