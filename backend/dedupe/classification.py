"""Pure helpers for Stage 3 (clean & deduplicate).

Content hashing (for duplicate detection) and simple noise rules (newsletters,
automated notifications). No I/O -- takes text/fields, returns values -- so it
is unit-testable in isolation.
"""

from __future__ import annotations

import hashlib

# Sender fragments that signal automated / bulk mail rather than project work.
_NOISE_SENDER_FRAGMENTS = (
    "noreply", "no-reply", "no_reply", "donotreply", "do-not-reply",
    "newsletter", "notifications", "notification", "notify",
    "alerts", "alert@", "mailer-daemon", "mailer", "bounce",
    "marketing", "promo", "jobalerts", "automated", "updates@",
)

# Body phrases typical of newsletters / bulk mail.
_NOISE_BODY_PHRASES = (
    "unsubscribe",
    "view in browser",
    "view this email in your browser",
    "manage your preferences",
    "update your preferences",
    "you are receiving this",
    "you're receiving this",
)

# Allowlist: senders/subjects that must be KEPT past the deterministic noise
# rule even if they look automated (e.g. a "no-reply@" address from a WORK
# system you rely on -- your ticketing tool, CI, HR portal). Matched as a
# lowercased substring against sender + subject + body. Add your own work
# senders/domains here. Note: passing this layer only means the item skips the
# cheap noise rule; the work-gate (Stage 3 LLM) still decides work-vs-personal.
_ALLOWLIST_FRAGMENTS: tuple[str, ...] = (
    # e.g. "jira", "@acmecorp.com", "workday", "confluence"
)

# High-precision phrases that signal a genuine, actionable WORK item for the
# recipient (a task/deadline/meeting to act on). If one appears, the item skips
# the cheap noise rule and is instead handed to the work-gate. Kept generic and
# work-flavoured -- job-application/job-alert phrasing was removed on purpose so
# recruiter blasts and application confirmations are not auto-admitted.
_RELEVANCE_PHRASES = (
    "action required",
    "next steps",
    "please complete",
    "please submit",
    "please review",
    "respond by",
    "you have been invited",
    "you're invited",
)


def content_hash(source_type: str, title: str | None, text: str | None) -> str | None:
    """Stable hash of an item's meaningful content, or None if there's no text.

    Returns None when the cleaned text is empty so that empty-bodied items (many
    calendar events) are not falsely deduplicated against each other.
    """
    body = (text or "").strip()
    if not body:
        return None
    key = "\n".join([source_type or "", (title or "").strip(), body])
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def is_noise(sender: str | None, title: str | None, text: str | None) -> bool:
    """True if the item looks like a newsletter / automated notification.

    An allowlist match (known-good sender/subject) always wins, so a program you
    care about is kept even when it mails from a 'no-reply@' address.
    """
    sender_l = (sender or "").lower()
    combined = f"{sender_l}\n{title or ''}\n{text or ''}".lower()
    # Free keep layer: known senders, or a high-precision actionable phrase.
    if any(fragment in combined for fragment in _ALLOWLIST_FRAGMENTS):
        return False
    if any(phrase in combined for phrase in _RELEVANCE_PHRASES):
        return False
    if any(fragment in sender_l for fragment in _NOISE_SENDER_FRAGMENTS):
        return True
    body_l = f"{title or ''}\n{text or ''}".lower()
    return any(phrase in body_l for phrase in _NOISE_BODY_PHRASES)
