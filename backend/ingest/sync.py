"""Stage 1 orchestrator: Ingest / Synchronize Gmail + Google Calendar.

Drives one sync pass per active connection:

  1. Load the connection's fresh credentials (refresh token if needed).
  2. Run the provider's sync (incremental via stored cursor, else backfill).
  3. On success, persist the new cursor + last_synced_at (only after the batch
     is safely in source_items). On failure, record status + last_error and
     keep the old cursor.

Commands:
  python3 backend/ingest/sync.py run                       # all active connections
  python3 backend/ingest/sync.py run --provider gmail
  python3 backend/ingest/sync.py run --full --max 25       # force backfill
  python3 backend/ingest/sync.py status                    # cursors + item counts
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Reuse the Stage 0 modules (config, connections, tokens, credentials) plus the
# Stage 1 ingest modules, regardless of the caller's working directory.
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "auth"))

import calendar_sync
import config as config_mod
import connections_repo
import credentials
import gmail_sync
import source_items_repo
from token_store import TokenStore, TokenStoreError

SYNCERS = {"gmail": gmail_sync, "google_calendar": calendar_sync}


def _resolve_user_id(cfg, explicit: str | None) -> str | None:
    user_id = (explicit or cfg.default_test_user_id or "").strip()
    if not user_id or user_id == "00000000-0000-0000-0000-000000000000":
        return None
    return user_id


def _active_connections(cfg, user_id, provider):
    rows = connections_repo.list_connections(cfg.database_url, user_id)
    rows = [c for c in rows if c.status in ("active", "expired", "error")]
    if provider:
        rows = [c for c in rows if c.provider == provider]
    return rows


def cmd_run(args, cfg) -> int:
    cfg.require_complete()
    user_id = _resolve_user_id(cfg, args.user_id)
    connections = _active_connections(cfg, user_id, args.provider)
    if not connections:
        print("No connections to sync. Connect an account first (Stage 0).")
        return 1

    store = TokenStore(cfg.token_encryption_key, cfg.database_url)
    all_ok = True

    for conn in connections:
        syncer = SYNCERS.get(conn.provider)
        print(f"\n[{conn.provider}] {conn.account_email}")
        if syncer is None:
            print(f"  skip: no syncer for provider '{conn.provider}'")
            continue
        try:
            creds = credentials.get_fresh_credentials(store, conn.id, conn.user_id)
        except (TokenStoreError, RuntimeError) as error:
            all_ok = False
            connections_repo.set_status(cfg.database_url, conn.id, "expired", str(error)[:500])
            print(f"  auth FAILED -> {error}")
            print("  status: expired (reconnect needed)")
            continue

        try:
            extra = {"query": args.query} if conn.provider == "gmail" else {}
            summary = syncer.sync(
                cfg.database_url, conn, creds.token,
                cursor=conn.sync_cursor,
                force_full=args.full,
                days=args.days,
                max_items=args.max,
                **extra,
            )
            # Advance the cursor only after the batch is safely stored.
            connections_repo.update_sync_state(
                cfg.database_url, conn.id, summary.get("new_cursor")
            )
            extras = f", skipped {summary['skipped']}" if "skipped" in summary else ""
            print(f"  {summary['mode']}: inserted {summary['inserted']}, "
                  f"updated {summary['updated']}{extras}")
            print(f"  cursor -> {summary.get('new_cursor')}  (last_synced_at stamped)")
        except Exception as error:  # noqa: BLE001 - record and continue
            all_ok = False
            connections_repo.set_status(cfg.database_url, conn.id, "error", str(error)[:500])
            print(f"  sync FAILED -> {error}")
            print("  status: error (cursor kept)")

    print("\n" + ("SYNC OK" if all_ok else "SYNC COMPLETED WITH ERRORS"))
    return 0 if all_ok else 1


def cmd_status(args, cfg) -> int:
    cfg.require_complete()
    user_id = _resolve_user_id(cfg, args.user_id)
    connections = connections_repo.list_connections(cfg.database_url, user_id)
    if not connections:
        print("No connections.")
        return 0
    for conn in connections:
        counts = source_items_repo.counts_by_status(cfg.database_url, conn.id)
        total = sum(counts.values())
        print(f"\n[{conn.provider}] {conn.account_email}  status={conn.status}")
        print(f"  last_synced_at: {conn.last_synced_at or '(never)'}")
        print(f"  sync_cursor:    {conn.sync_cursor or '(none - next run backfills)'}")
        if conn.last_error:
            print(f"  last_error:     {conn.last_error}")
        print(f"  source_items:   {total} total  {dict(counts)}")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Stage 1 Ingest / Synchronize.")
    sub = parser.add_subparsers(dest="command", required=True)

    p_run = sub.add_parser("run", help="Sync active connections into source_items.")
    p_run.add_argument("--provider", choices=list(SYNCERS), default=None)
    p_run.add_argument("--user-id", dest="user_id", default=None)
    p_run.add_argument("--full", action="store_true", help="Force a backfill (ignore cursor).")
    p_run.add_argument("--days", type=int, default=30, help="Backfill window in days.")
    p_run.add_argument("--max", type=int, default=50, help="Max items per connection.")
    p_run.add_argument("--query", default=None,
                       help="Gmail search string for a targeted backfill "
                            "(e.g. 'from:codepath.org newer_than:180d'). Gmail only.")

    p_status = sub.add_parser("status", help="Show cursors, timestamps, and item counts.")
    p_status.add_argument("--user-id", dest="user_id", default=None)

    return parser.parse_args()


def main() -> int:
    args = parse_args()
    cfg = config_mod.load_config()
    if args.command == "run":
        return cmd_run(args, cfg)
    if args.command == "status":
        return cmd_status(args, cfg)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
