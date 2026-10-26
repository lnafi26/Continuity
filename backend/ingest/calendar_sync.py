"""Google Calendar ingestion for Stage 1.

First run: a bounded backfill of recent + upcoming events, capturing the
`nextSyncToken`. Later runs: an incremental sync using that token, which returns
only changed events. Each event becomes a `source_items` row
(source_type='google_calendar', processing_status='pending'). Uses the Calendar
REST API directly with the connection's access token.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import requests

from source_items_repo import SourceItem, upsert_source_item

API = "https://www.googleapis.com/calendar/v3/calendars/primary/events"


class CalendarSyncError(RuntimeError):
    pass


class _SyncTokenGone(Exception):
    """The stored syncToken is invalid (HTTP 410); a full resync is required."""


def _get(access_token: str, params: dict) -> dict:
    resp = requests.get(
        API,
        headers={"Authorization": f"Bearer {access_token}"},
        params=params,
        timeout=30,
    )
    if resp.status_code == 410:
        raise _SyncTokenGone()
    resp.raise_for_status()
    return resp.json()


def _parse_when(value: dict | None):
    """Parse an event start/end object into a timezone-aware datetime."""
    if not value:
        return None
    if value.get("dateTime"):
        raw = value["dateTime"].replace("Z", "+00:00")
        return datetime.fromisoformat(raw)
    if value.get("date"):  # all-day event
        return datetime.fromisoformat(value["date"]).replace(tzinfo=timezone.utc)
    return None


def _event_to_item(connection, event: dict) -> SourceItem:
    attendees = [
        a.get("email")
        for a in event.get("attendees", []) or []
        if a.get("email")
    ]
    organizer = (event.get("organizer") or {}).get("email")
    description = (event.get("description") or "").strip()
    summary = event.get("summary") or "(no title)"

    return SourceItem(
        connection_id=connection.id,
        user_id=connection.user_id,
        source_type="google_calendar",
        external_id=event["id"],
        external_thread_id=event.get("recurringEventId"),
        title=summary,
        text_excerpt=description[:2000],
        extracted_text=description or None,
        sender=organizer,
        participants=attendees,
        mime_type=None,
        source_url=event.get("htmlLink"),
        occurred_at=_parse_when(event.get("start")),
        ends_at=_parse_when(event.get("end")),
        location=event.get("location"),
    )


def _page_through(database_url, connection, access_token, base_params, max_items):
    inserted = updated = skipped = 0
    new_cursor = None
    page_token = None
    while inserted + updated + skipped < max_items:
        params = dict(base_params)
        if page_token:
            params["pageToken"] = page_token
        page = _get(access_token, params)

        for event in page.get("items", []):
            # Cancelled events arrive on incremental syncs; skip them for the MVP.
            if event.get("status") == "cancelled" or not event.get("id"):
                skipped += 1
                continue
            item = _event_to_item(connection, event)
            if upsert_source_item(database_url, item):
                inserted += 1
            else:
                updated += 1

        new_cursor = page.get("nextSyncToken") or new_cursor
        page_token = page.get("nextPageToken")
        if not page_token:
            break
    return inserted, updated, skipped, new_cursor


def sync(
    database_url: str,
    connection,
    access_token: str,
    *,
    cursor: str | None,
    force_full: bool = False,
    days: int = 30,
    max_items: int = 50,
) -> dict:
    """Run one Calendar sync pass. Returns a summary including the new syncToken."""
    # Try incremental first when we have a token; on 410 fall back to backfill.
    if cursor and not force_full:
        try:
            inserted, updated, skipped, new_cursor = _page_through(
                database_url, connection, access_token,
                {"syncToken": cursor, "maxResults": 100},
                max_items,
            )
            return {
                "provider": "google_calendar",
                "mode": "incremental",
                "inserted": inserted,
                "updated": updated,
                "skipped": skipped,
                "new_cursor": new_cursor,
            }
        except _SyncTokenGone:
            mode = "backfill (token expired)"
    else:
        mode = "backfill"

    time_min = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    inserted, updated, skipped, new_cursor = _page_through(
        database_url, connection, access_token,
        {
            "singleEvents": "true",
            "orderBy": "startTime",
            "timeMin": time_min,
            "maxResults": 100,
        },
        max_items,
    )
    return {
        "provider": "google_calendar",
        "mode": mode,
        "inserted": inserted,
        "updated": updated,
        "skipped": skipped,
        "new_cursor": new_cursor,
    }
