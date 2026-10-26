"""Pure text-cleaning functions for Stage 2 (extract & normalize).

Strips HTML boilerplate, quoted reply chains, and signatures from raw message
bodies, and normalizes whitespace and participant lists. No I/O and no DB
access -- every function takes text/lists and returns cleaned text/lists, so it
is trivially unit-testable.
"""

from __future__ import annotations

import html
import re

# Markers that begin a quoted reply / forwarded block. Matched against the whole
# body; everything from the earliest match onward is dropped.
_REPLY_MARKERS = [
    # Gmail-style: "On Mon, Aug 4, 2025 at 3:00 PM John Doe <j@x.com> wrote:"
    re.compile(r"\n?On\s.{0,300}?\swrote:", re.IGNORECASE | re.DOTALL),
    # Outlook: "-----Original Message-----"
    re.compile(r"\n-{2,}\s*Original Message\s*-{2,}", re.IGNORECASE),
    # Outlook header block: "From: ...\nSent: ..." or "From: ...\nDate: ..."
    re.compile(r"\nFrom:\s.{0,200}?\n(?:Sent|Date):\s", re.IGNORECASE | re.DOTALL),
]

# A line that, once seen, marks the start of a signature (drop it and after).
_SIGNATURE_MARKERS = [
    re.compile(r"^--\s*$"),                       # RFC 3676 "-- " delimiter
    re.compile(r"^Sent from my ", re.IGNORECASE), # phone auto-signatures
    re.compile(r"^Get Outlook for ", re.IGNORECASE),
]

_EMAIL_RE = re.compile(r"[\w.\-+]+@[\w.\-]+\.\w+")


def strip_html(text: str) -> str:
    """Remove script/style blocks and tags, then unescape entities.

    Block-level and <br> tags become newlines first, so line-based signature and
    quoted-reply detection still works on HTML email.
    """
    if "<" not in text or ">" not in text:
        return text
    text = re.sub(r"(?is)<(script|style).*?</\1>", " ", text)
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?i)</(p|div|tr|li|h[1-6])\s*>", "\n", text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    return html.unescape(text)


def strip_quoted_replies(text: str) -> str:
    """Cut the body at the first quoted-reply marker and drop '>' quoted lines."""
    cut = len(text)
    for pattern in _REPLY_MARKERS:
        match = pattern.search(text)
        if match and match.start() < cut:
            cut = match.start()
    text = text[:cut]
    kept = [line for line in text.splitlines() if not line.lstrip().startswith(">")]
    return "\n".join(kept)


def strip_signature(text: str) -> str:
    """Drop everything from the first signature marker onward."""
    lines = text.splitlines()
    out: list[str] = []
    for line in lines:
        stripped = line.strip()
        if any(marker.match(stripped) for marker in _SIGNATURE_MARKERS):
            break
        out.append(line)
    return "\n".join(out)


def normalize_whitespace(text: str) -> str:
    """Normalize newlines, collapse runs of spaces/blank lines, trim edges."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = "\n".join(line.strip() for line in text.split("\n"))
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def clean_email_body(raw: str | None) -> str:
    """Full cleaning pipeline for an email body."""
    text = strip_html(raw or "")
    text = strip_quoted_replies(text)
    text = strip_signature(text)
    return normalize_whitespace(text)


def clean_calendar_description(raw: str | None) -> str:
    """Clean a calendar event description (strip Google Meet boilerplate block)."""
    text = strip_html(raw or "")
    # Google Calendar wraps video-conference details in a "-::~:~::~..." block.
    marker = text.find("-::~")
    if marker != -1:
        text = text[:marker]
    return normalize_whitespace(text)


def clean_body(source_type: str, raw: str | None) -> str:
    """Dispatch to the right cleaner by source type."""
    if source_type == "google_calendar":
        return clean_calendar_description(raw)
    return clean_email_body(raw)


def normalize_participants(values: list[str] | None) -> list[str]:
    """Lowercase, trim, and de-duplicate participant emails, preserving order."""
    seen: list[str] = []
    for value in values or []:
        email = (value or "").strip().lower()
        if email and email not in seen:
            seen.append(email)
    return seen


def normalize_sender(value: str | None) -> str | None:
    """Return a lowercased email address for the sender, or the trimmed value."""
    if not value:
        return None
    found = _EMAIL_RE.findall(value)
    if found:
        return found[0].lower()
    return value.strip() or None


def make_excerpt(text: str, limit: int = 2000) -> str:
    """Bounded text_excerpt (Architecture: <= 2000 chars)."""
    return (text or "")[:limit]
