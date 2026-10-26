"""Gmail ingestion for Stage 1.

First run: a bounded backfill of recent messages (last N days). Later runs: the
Gmail History API using the stored historyId cursor to fetch only new messages.
Each message becomes a `source_items` row (source_type='gmail',
processing_status='pending'). Uses the Gmail REST API directly with the
connection's access token, so no extra client library is required.
"""

from __future__ import annotations

import base64
import re
from datetime import datetime, timezone

import requests

from source_items_repo import SourceItem, upsert_source_item

API = "https://gmail.googleapis.com/gmail/v1/users/me"
_EMAIL_RE = re.compile(r"[\w.\-+]+@[\w.\-]+\.\w+")


class GmailSyncError(RuntimeError):
    pass


def _get(access_token: str, path: str, params: dict | None = None) -> dict:
    resp = requests.get(
        f"{API}{path}",
        headers={"Authorization": f"Bearer {access_token}"},
        params=params or {},
        timeout=30,
    )
    if resp.status_code == 404:
        raise _HistoryGone()
    resp.raise_for_status()
    return resp.json()


class _HistoryGone(Exception):
    """startHistoryId is too old; a full backfill is required."""


def _header(headers: list[dict], name: str) -> str:
    lname = name.lower()
    for h in headers:
        if h.get("name", "").lower() == lname:
            return h.get("value", "")
    return ""


def _emails(value: str) -> list[str]:
    return _EMAIL_RE.findall(value or "")


def _decode_part(data: str) -> str:
    if not data:
        return ""
    try:
        return base64.urlsafe_b64decode(data.encode("utf-8")).decode(
            "utf-8", errors="replace"
        )
    except Exception:  # noqa: BLE001 - tolerate malformed parts
        return ""


def _plain_text(payload: dict) -> str:
    """Walk a Gmail payload tree and return the best plain-text body."""
    mime = payload.get("mimeType", "")
    body = payload.get("body", {})
    if mime == "text/plain" and body.get("data"):
        return _decode_part(body["data"])
    for part in payload.get("parts", []) or []:
        text = _plain_text(part)
        if text:
            return text
    # Fall back to stripped HTML if no text/plain part exists.
    if mime == "text/html" and body.get("data"):
        html = _decode_part(body["data"])
        return re.sub(r"<[^>]+>", " ", html)
    return ""


def _message_to_item(connection, message: dict) -> SourceItem:
    payload = message.get("payload", {})
    headers = payload.get("headers", [])
    subject = _header(headers, "Subject")
    from_value = _header(headers, "From")
    to_value = _header(headers, "To")
    cc_value = _header(headers, "Cc")

    participants = []
    for value in (from_value, to_value, cc_value):
        for email in _emails(value):
            if email not in participants:
                participants.append(email)

    occurred_at = None
    internal = message.get("internalDate")
    if internal:
        occurred_at = datetime.fromtimestamp(int(internal) / 1000, tz=timezone.utc)

    body = _plain_text(payload).strip()
    snippet = message.get("snippet", "")
    excerpt = (body or snippet)[:2000]

    return SourceItem(
        connection_id=connection.id,
        user_id=connection.user_id,
        source_type="gmail",
        external_id=message["id"],
        external_thread_id=message.get("threadId"),
        title=subject,
        text_excerpt=excerpt,
        extracted_text=body or snippet or None,
        sender=(_emails(from_value) or [from_value or None])[0],
        participants=participants,
        mime_type="text/plain",
        source_url=f"https://mail.google.com/mail/u/0/#all/{message['id']}",
        occurred_at=occurred_at,
    )


def _fetch_and_store(database_url, connection, access_token, message_ids) -> tuple[int, int]:
    inserted = updated = 0
    for message_id in message_ids:
        message = _get(access_token, f"/messages/{message_id}", {"format": "full"})
        item = _message_to_item(connection, message)
        if upsert_source_item(database_url, item):
            inserted += 1
        else:
            updated += 1
    return inserted, updated


def _backfill(
    database_url, connection, access_token, days, max_items, query=None
) -> tuple[int, int, str]:
    """List recent message ids, store them, and return the new history cursor.

    When `query` is given it is used as the Gmail search (e.g.
    "from:codepath.org newer_than:180d"); otherwise the default recent-window
    query is used.
    """
    # Capture the mailbox historyId now; anything after it is caught next run.
    profile = _get(access_token, "/profile")
    new_cursor = str(profile.get("historyId", ""))

    search = query.strip() if query and query.strip() else f"newer_than:{days}d"
    ids: list[str] = []
    page_token = None
    while len(ids) < max_items:
        params = {
            "q": search,
            "maxResults": min(100, max_items - len(ids)),
        }
        if page_token:
            params["pageToken"] = page_token
        page = _get(access_token, "/messages", params)
        ids.extend(m["id"] for m in page.get("messages", []))
        page_token = page.get("nextPageToken")
        if not page_token:
            break

    inserted, updated = _fetch_and_store(database_url, connection, access_token, ids[:max_items])
    return inserted, updated, new_cursor


def _incremental(database_url, connection, access_token, cursor, max_items) -> tuple[int, int, str]:
    """Use the History API to fetch only messages added since the cursor."""
    ids: list[str] = []
    page_token = None
    new_cursor = cursor
    while len(ids) < max_items:
        params = {"startHistoryId": cursor, "historyTypes": "messageAdded"}
        if page_token:
            params["pageToken"] = page_token
        page = _get(access_token, "/history", params)
        new_cursor = str(page.get("historyId", new_cursor))
        for record in page.get("history", []):
            for added in record.get("messagesAdded", []):
                mid = added.get("message", {}).get("id")
                if mid and mid not in ids:
                    ids.append(mid)
        page_token = page.get("nextPageToken")
        if not page_token:
            break

    inserted, updated = _fetch_and_store(database_url, connection, access_token, ids[:max_items])
    return inserted, updated, new_cursor


def sync(
    database_url: str,
    connection,
    access_token: str,
    *,
    cursor: str | None,
    force_full: bool = False,
    days: int = 30,
    max_items: int = 50,
    query: str | None = None,
) -> dict:
    """Run one Gmail sync pass. Returns a summary dict including the new cursor.

    Falls back to a full backfill if there is no cursor, if forced, or if the
    stored historyId is too old for the History API. A `query` forces a backfill
    with that Gmail search string (incremental history sync can't be filtered).
    """
    if cursor and not force_full and not query:
        try:
            inserted, updated, new_cursor = _incremental(
                database_url, connection, access_token, cursor, max_items
            )
            mode = "incremental"
        except _HistoryGone:
            inserted, updated, new_cursor = _backfill(
                database_url, connection, access_token, days, max_items, query
            )
            mode = "backfill (history expired)"
    else:
        inserted, updated, new_cursor = _backfill(
            database_url, connection, access_token, days, max_items, query
        )
        mode = "backfill (query)" if query else "backfill"

    return {
        "provider": "gmail",
        "mode": mode,
        "inserted": inserted,
        "updated": updated,
        "new_cursor": new_cursor,
    }
