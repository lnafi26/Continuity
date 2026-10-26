"""Write one natural "what happened" sentence per project (Stage 7, Haiku 4.5).

Given a project's recent events (type, title, body, person), asks a cheap model
for a single concise sentence a busy professional can read in a catch-up
digest -- prioritizing decisions and any differing opinions/disagreements over
routine meetings or notes. Falls back to a deterministic join when no API key
is set or a call fails, so the digest is never blocked waiting on the LLM.
"""

from __future__ import annotations

DEFAULT_SUMMARY_MODEL = "claude-haiku-4-5"

_SYSTEM = (
    "You write one concise, natural sentence summarizing recent project "
    "activity for a busy professional's catch-up digest. Reply with ONLY the "
    "sentence -- no preamble, no quotes, no bullet points."
)

_MAX_EVENTS = 12


def _prompt(project_name: str, events: list[dict]) -> str:
    lines = []
    for e in events[:_MAX_EVENTS]:
        who = f" -- {e.get('person')}" if e.get("person") else ""
        body = f": {e.get('body')}" if e.get("body") else ""
        lines.append(f"  [{e.get('event_type', 'note')}] {e.get('title', '')}{body}{who}")
    items = "\n".join(lines) or "  (no items)"
    return (
        f"Project: {project_name}\n"
        f"Recent items (most recent first):\n{items}\n\n"
        "Write one natural sentence (max ~30 words) summarizing what happened. "
        "Prioritize decisions and any differing opinions or disagreements "
        "mentioned over routine meetings or notes. Do not list items; write "
        "connected prose, as if telling a colleague what they missed."
    )


def _fallback(events: list[dict]) -> str:
    """Deterministic sentence used when the LLM is unavailable or fails."""
    if not events:
        return "No recent activity."
    by_type: dict[str, list[dict]] = {}
    for e in events:
        by_type.setdefault(e.get("event_type", "note"), []).append(e)
    order = ["decision", "deadline", "meeting", "email", "file", "status", "note"]
    clauses = []
    for etype in order:
        group = by_type.get(etype)
        if not group:
            continue
        if etype in ("decision", "deadline"):
            titles = " and ".join(f'"{g.get("title", "")}"' for g in group[:2])
            extra = f" (+{len(group) - 2} more)" if len(group) > 2 else ""
            clauses.append(f"{etype} on {titles}{extra}")
        else:
            plural = "s" if len(group) > 1 else ""
            clauses.append(f"{len(group)} {etype}{plural}")
    if not clauses:
        return events[0].get("title", "New activity")
    if len(clauses) == 1:
        sentence = clauses[0]
    else:
        last = clauses.pop()
        sentence = ", ".join(clauses) + f", and {last}"
    return sentence[0].upper() + sentence[1:] + "."


def summarize(
    project_name: str,
    events: list[dict],
    *,
    api_key: str | None,
    model: str = DEFAULT_SUMMARY_MODEL,
) -> str:
    """Return one sentence summarizing a project's recent events. Never raises."""
    if not events:
        return "No recent activity."
    if not api_key:
        return _fallback(events)
    try:
        import anthropic

        client = anthropic.Anthropic(api_key=api_key)
        resp = client.messages.create(
            model=model,
            max_tokens=120,
            system=_SYSTEM,
            messages=[{"role": "user", "content": _prompt(project_name, events)}],
        )
        text = "".join(
            block.text for block in resp.content
            if getattr(block, "type", None) == "text"
        ).strip()
        return text or _fallback(events)
    except Exception:  # noqa: BLE001 - fall back rather than block the digest
        return _fallback(events)
