"""Deterministic relationship signals for Stage 4 (pure functions).

Cheap, high-precision signals that two items belong to the same project: shared
email thread, shared sender, overlapping participants, shared title keywords, and
closeness in time. These are combined with semantic (embedding) similarity to
score candidate relationships -- deterministic matches raise confidence.
"""

from __future__ import annotations

import re
from datetime import datetime

_STOPWORDS = {
    "the", "and", "for", "with", "your", "you", "our", "are", "was", "this",
    "that", "from", "have", "has", "will", "can", "not", "but", "all", "any",
    "get", "new", "out", "now", "into", "about", "re", "fwd", "fw", "please",
    "week", "meeting", "update", "updates", "call", "hi", "hello", "thanks",
}
_TOKEN_RE = re.compile(r"[a-z0-9]{4,}")

# Weights for the deterministic score (summed then clamped to <= 1.0).
_W_THREAD = 0.50
_W_SENDER = 0.15
_W_PARTICIPANTS = 0.25
_W_KEYWORDS = 0.20
_W_TIME = 0.10
_TIME_WINDOW_DAYS = 7.0


def participant_set(sender: str | None, participants: list[str] | None) -> set[str]:
    people = {p.strip().lower() for p in (participants or []) if p and p.strip()}
    if sender and sender.strip():
        people.add(sender.strip().lower())
    return people


def title_keywords(title: str | None) -> set[str]:
    tokens = _TOKEN_RE.findall((title or "").lower())
    return {t for t in tokens if t not in _STOPWORDS}


def _jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _days_apart(a: datetime | None, b: datetime | None) -> float | None:
    if a is None or b is None:
        return None
    return abs((a - b).total_seconds()) / 86400.0


def signals_between(a: dict, b: dict) -> tuple[float, dict]:
    """Score the deterministic relationship between two items.

    Each item dict has: thread, sender, participants, title, occurred_at.
    Returns (deterministic_score in [0,1], signals dict).
    """
    same_thread = bool(
        a.get("thread") and b.get("thread") and a["thread"] == b["thread"]
    )
    shared_sender = bool(
        a.get("sender") and b.get("sender")
        and a["sender"].lower() == b["sender"].lower()
    )
    participant_overlap = _jaccard(
        participant_set(a.get("sender"), a.get("participants")),
        participant_set(b.get("sender"), b.get("participants")),
    )
    keyword_overlap = _jaccard(
        title_keywords(a.get("title")), title_keywords(b.get("title"))
    )
    days = _days_apart(a.get("occurred_at"), b.get("occurred_at"))
    time_proximity = 0.0
    if days is not None and days <= _TIME_WINDOW_DAYS:
        time_proximity = 1.0 - (days / _TIME_WINDOW_DAYS)

    score = (
        (_W_THREAD if same_thread else 0.0)
        + (_W_SENDER if shared_sender else 0.0)
        + _W_PARTICIPANTS * participant_overlap
        + _W_KEYWORDS * keyword_overlap
        + _W_TIME * time_proximity
    )
    score = min(1.0, score)

    signals = {
        "same_thread": same_thread,
        "shared_sender": shared_sender,
        "participant_overlap": round(participant_overlap, 3),
        "keyword_overlap": round(keyword_overlap, 3),
        "days_apart": round(days, 2) if days is not None else None,
    }
    return score, signals


def combine(semantic: float, deterministic: float, signals: dict) -> float:
    """Blend semantic + deterministic into a final combined score in [0,1].

    Cosine can be slightly negative for unrelated text; floor it at 0. A shared
    thread is a strong structural link, so it raises the floor.
    """
    sem = max(0.0, semantic)
    combined = 0.6 * sem + 0.4 * deterministic
    if signals.get("same_thread"):
        combined = max(combined, 0.85)
    return round(min(1.0, combined), 5)
