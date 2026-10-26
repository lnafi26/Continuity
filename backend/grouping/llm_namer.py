"""Name and summarize a project cluster with the Claude API (Sonnet 5).

Given the items in one cluster, asks Claude for a short project name, a
one-sentence summary, a single-letter symbol, and a coherence score (how
strongly the items belong to one project). Falls back to a keyword-derived name
when no API key is set or the call fails, so Stage 5 still runs offline.
"""

from __future__ import annotations

import json
import re
from collections import Counter

DEFAULT_MODEL = "claude-sonnet-5"

_SYSTEM = (
    "You organize scattered work items (emails and calendar events) into "
    "projects. Given a set of related items, produce a concise project name and "
    "a one-sentence summary. Reply with ONLY a JSON object, no prose."
)

# Fixed category set for the digest's tag pills (Stage 7). 'project' is the
# generic default and deliberately not shown as a tag in the UI -- only the
# more specific categories are, so tags stay informative rather than noisy.
_CATEGORIES = (
    "project", "meeting_series", "training", "conference", "interview", "admin",
)

# Stopwords for the offline keyword fallback.
_STOP = {
    "the", "and", "for", "with", "your", "you", "our", "re", "fwd", "fw",
    "update", "meeting", "call", "session", "week", "reminder", "invitation",
    "new", "get", "this", "that", "from", "about",
}
_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9]{2,}")


def _extract_json(text: str) -> dict | None:
    """Pull the first JSON object out of a model response."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
    return None


def keyword_name(items: list[dict]) -> dict:
    """Offline fallback: derive a name from the most common title keywords."""
    counter: Counter = Counter()
    for item in items:
        for token in _TOKEN_RE.findall((item.get("title") or "").lower()):
            if token not in _STOP:
                counter[token] += 1
    top = [word.capitalize() for word, _ in counter.most_common(3)]
    name = " ".join(top) if top else "Untitled Project"
    symbol = (name[:1] or "P").upper()
    return {
        "name": name[:60],
        "summary": f"Auto-grouped from {len(items)} related item(s).",
        "symbol": symbol,
        "coherence": 0.5,
        # Without the LLM there's no reliable way to classify the domain, so
        # this stays generic rather than guessing from keywords.
        "category": "project",
    }


def _build_prompt(items: list[dict]) -> str:
    lines = []
    for item in items[:20]:  # cap prompt size
        lines.append(
            f"- [{item.get('source_type', '?')}] "
            f"{(item.get('title') or '(no title)')[:90]} "
            f"| from {item.get('sender') or '?'} "
            f"| {item.get('occurred_at') or '?'} "
            f"| {(item.get('excerpt') or '')[:160]}"
        )
    categories = ", ".join(_CATEGORIES)
    return (
        "These items appear to belong to one project:\n"
        + "\n".join(lines)
        + "\n\nReturn a JSON object with keys:\n"
        '  "name": a concise project name (<= 6 words),\n'
        '  "summary": one sentence describing the project,\n'
        '  "symbol": a single uppercase letter,\n'
        f'  "category": one of {categories} -- pick "meeting_series" for '
        'recurring 1:1s/standing meetings, "training" for courses/workshops, '
        '"conference" for summits/external events, "interview" for hiring/'
        'candidate panels, "admin" for administrative items, and "project" '
        "for everything else (the default),\n"
        '  "coherence": a number 0.0-1.0 for how strongly these items belong '
        "to a single project."
    )


def name_project(
    items: list[dict],
    *,
    api_key: str | None,
    model: str = DEFAULT_MODEL,
) -> dict:
    """Return {name, summary, symbol, coherence}. Never raises."""
    if not api_key:
        return keyword_name(items)
    try:
        import anthropic

        client = anthropic.Anthropic(api_key=api_key)
        resp = client.messages.create(
            model=model,
            max_tokens=400,
            system=_SYSTEM,
            messages=[{"role": "user", "content": _build_prompt(items)}],
        )
        text = "".join(
            block.text for block in resp.content
            if getattr(block, "type", None) == "text"
        )
        data = _extract_json(text)
        if not data or "name" not in data:
            return keyword_name(items)
        category = str(data.get("category", "")).strip().lower()
        if category not in _CATEGORIES:
            category = "project"
        return {
            "name": str(data.get("name", "")).strip()[:60] or "Untitled Project",
            "summary": str(data.get("summary", "")).strip()[:500],
            "symbol": (str(data.get("symbol", "")).strip()[:1] or "P").upper(),
            "category": category,
            "coherence": _clamp01(data.get("coherence", 0.5)),
        }
    except Exception:  # noqa: BLE001 - fall back rather than fail the stage
        return keyword_name(items)


def _clamp01(value) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return 0.5
