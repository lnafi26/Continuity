"""Load the reusable synthetic WORK-ONLY dataset into `source_items`.

This injects fixtures at the exact point where real Gmail/Calendar data enters
the backend: `source_items_repo.upsert_source_item()` — the same write path
Stage 1 (ingest/sync) uses. Everything downstream (Stage 2 normalize, Stage 3
dedupe/noise, Stage 4 embed, Stage 5 group, Stage 6 extract) then runs
unchanged against the demo rows.

What it does:
  1. Resolve the auth user by email (default: testxu495@gmail.com).
  2. Upsert two synthetic `source_connections` (gmail + google_calendar) so the
     FK / CHECK constraints on `source_items` are satisfied.
  3. Map each fixture in synthetic_dataset.json to a `SourceItem` and upsert it,
     converting the relative `days_ago` / `days_from_now` offsets into concrete
     timezone-aware timestamps at load time.

Usage:
  python3 demo_data/load_demo_data.py                 # load under testxu495@gmail.com
  python3 demo_data/load_demo_data.py --email you@x   # load under a different user
  python3 demo_data/load_demo_data.py --reset         # delete demo rows, then load
  python3 demo_data/load_demo_data.py --reset-only     # delete demo rows, don't load
  python3 demo_data/load_demo_data.py --dry-run       # print what would load

After loading, run the pipeline scoped to the same user, e.g.:
  python3 backend/dedupe/normalize.py --user-id <id>
  ... etc (see demo_data/README.md).
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from pathlib import Path

import psycopg

# Make the backend package importable without installing it.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from auth import config as auth_config  # noqa: E402
from auth import connections_repo  # noqa: E402
from ingest.source_items_repo import SourceItem, upsert_source_item  # noqa: E402

DATASET_PATH = Path(__file__).resolve().parent / "synthetic_dataset.json"

# Stable identifiers so the loader is idempotent and --reset can find its rows.
DEMO_ACCOUNT_ID = "demo-testxu495"
DEMO_GMAIL_EMAIL = "testxu495@acmecorp.com"


@dataclass
class DemoConnections:
    gmail_id: str
    calendar_id: str


def _load_dataset() -> dict:
    with DATASET_PATH.open() as handle:
        return json.load(handle)


def _resolve_user_id(database_url: str, email: str) -> str:
    """Look up the Supabase auth user id for an email address."""
    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "select id from auth.users where lower(email) = lower(%s)",
                (email,),
            )
            row = cursor.fetchone()
    if not row:
        raise SystemExit(
            f"No auth user found for {email!r}. Create the user in the Supabase "
            f"dashboard (Authentication → Users) first, then re-run."
        )
    return str(row[0])


def _ensure_connections(database_url: str, user_id: str) -> DemoConnections:
    """Create/refresh the two synthetic connections the source_items rows need."""
    gmail_id = connections_repo.upsert_connection(
        database_url,
        user_id=user_id,
        provider="gmail",
        provider_account_id=DEMO_ACCOUNT_ID,
        account_email=DEMO_GMAIL_EMAIL,
    )
    calendar_id = connections_repo.upsert_connection(
        database_url,
        user_id=user_id,
        provider="google_calendar",
        provider_account_id=DEMO_ACCOUNT_ID,
        account_email=DEMO_GMAIL_EMAIL,
    )
    return DemoConnections(gmail_id=gmail_id, calendar_id=calendar_id)


def _email_occurred_at(now: datetime, days_ago: int) -> datetime:
    """A plausible mid-morning-ish timestamp `days_ago` days back."""
    return now - timedelta(days=days_ago)


def _event_times(
    today: datetime, days_from_now: int, start_hour: int, duration_min: int
) -> tuple[datetime, datetime]:
    """Concrete start/end for a calendar event relative to today."""
    day = (today + timedelta(days=days_from_now)).date()
    start = datetime.combine(day, time(hour=start_hour), tzinfo=timezone.utc)
    end = start + timedelta(minutes=duration_min)
    return start, end


def _to_gmail_item(msg: dict, conn: DemoConnections, user_id: str, now: datetime) -> SourceItem:
    body = msg.get("body", "")
    return SourceItem(
        connection_id=conn.gmail_id,
        user_id=user_id,
        source_type="gmail",
        external_id=msg["id"],
        title=msg.get("subject", ""),
        text_excerpt=body,
        extracted_text=body,
        sender=msg.get("from"),
        participants=msg.get("to", []),
        external_thread_id=msg.get("thread_id"),
        mime_type="text/plain",
        source_url=None,
        occurred_at=_email_occurred_at(now, int(msg.get("days_ago", 0))),
    )


def _to_calendar_item(ev: dict, conn: DemoConnections, user_id: str, today: datetime) -> SourceItem:
    start, end = _event_times(
        today,
        int(ev.get("days_from_now", 0)),
        int(ev.get("start_hour", 9)),
        int(ev.get("duration_min", 60)),
    )
    description = ev.get("description", "")
    return SourceItem(
        connection_id=conn.calendar_id,
        user_id=user_id,
        source_type="google_calendar",
        external_id=ev["id"],
        title=ev.get("summary", ""),
        text_excerpt=description,
        extracted_text=description,
        sender=ev.get("organizer"),
        participants=ev.get("attendees", []),
        external_thread_id=ev.get("recurring_id"),
        mime_type=None,
        source_url=None,
        occurred_at=start,
        ends_at=end,
        location=ev.get("location"),
    )


def _reset_demo_rows(database_url: str, conn: DemoConnections) -> int:
    """Delete previously-loaded demo source_items (by connection). Returns count.

    Downstream rows (project_events/actions, links, embeddings) are removed by
    the pipeline's own purge query; this only clears the demo's ingested items so
    a fresh load starts clean. Connections are kept and reused.
    """
    deleted = 0
    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "delete from public.source_items where connection_id in (%s, %s)",
                (conn.gmail_id, conn.calendar_id),
            )
            deleted = cursor.rowcount
        connection.commit()
    return deleted


def main() -> None:
    parser = argparse.ArgumentParser(description="Load synthetic demo data into source_items.")
    parser.add_argument("--email", default="testxu495@gmail.com", help="Auth user email to load under.")
    parser.add_argument("--reset", action="store_true", help="Delete demo rows before loading.")
    parser.add_argument("--reset-only", action="store_true", help="Delete demo rows and exit.")
    parser.add_argument("--dry-run", action="store_true", help="Print planned rows without writing.")
    args = parser.parse_args()

    cfg = auth_config.load_config()
    if not cfg.database_url:
        raise SystemExit("SUPABASE_DATABASE_URL is not set in backend/.env")

    dataset = _load_dataset()
    now = datetime.now(timezone.utc)
    today = now

    user_id = _resolve_user_id(cfg.database_url, args.email)
    print(f"User {args.email} -> {user_id}")

    if args.dry_run:
        # Stay read-only: use placeholder connection ids, don't touch the DB.
        conn = DemoConnections(gmail_id="<gmail-conn>", calendar_id="<calendar-conn>")
    else:
        conn = _ensure_connections(cfg.database_url, user_id)
        print(f"Connections: gmail={conn.gmail_id} calendar={conn.calendar_id}")

    if (args.reset or args.reset_only) and not args.dry_run:
        removed = _reset_demo_rows(cfg.database_url, conn)
        print(f"Reset: deleted {removed} existing demo source_items")
        if args.reset_only:
            return

    gmail_items = [
        _to_gmail_item(m, conn, user_id, now) for m in dataset.get("gmail_messages", [])
    ]
    calendar_items = [
        _to_calendar_item(e, conn, user_id, today) for e in dataset.get("calendar_events", [])
    ]

    if args.dry_run:
        for item in gmail_items + calendar_items:
            when = item.occurred_at.isoformat() if item.occurred_at else "-"
            print(f"  [{item.source_type}] {item.external_id} @ {when} :: {item.title}")
        print(f"Dry run: {len(gmail_items)} emails + {len(calendar_items)} events (not written).")
        return

    inserted = updated = 0
    for item in gmail_items + calendar_items:
        if upsert_source_item(cfg.database_url, item):
            inserted += 1
        else:
            updated += 1

    print(
        f"Loaded {len(gmail_items)} emails + {len(calendar_items)} events "
        f"({inserted} inserted, {updated} updated) under {args.email}."
    )
    print("Next: run the pipeline scoped to this user (see demo_data/README.md).")


if __name__ == "__main__":
    main()
