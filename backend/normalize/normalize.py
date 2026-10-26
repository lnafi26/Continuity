"""Stage 2 orchestrator: Extract & Normalize.

Consumes the Stage 1 work queue (pending rows where normalized_at IS NULL),
cleans each row's text (strip HTML boilerplate, quoted replies, signatures),
normalizes participants/sender, finalizes a <=2000 char text_excerpt, and stamps
normalized_at. Idempotent: only un-normalized rows are picked up.

Commands:
  python3 backend/normalize/normalize.py run                 # normalize the queue
  python3 backend/normalize/normalize.py run --limit 50 --user-id <uuid>
  python3 backend/normalize/normalize.py status              # progress counts
  python3 backend/normalize/normalize.py preview [--limit 3] # dry-run, no writes
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "auth"))

import config as config_mod
import normalize_repo
import text_cleaning as tc


def _resolve_user_id(cfg, explicit: str | None) -> str | None:
    user_id = (explicit or cfg.default_test_user_id or "").strip()
    if not user_id or user_id == "00000000-0000-0000-0000-000000000000":
        return None
    return user_id


def cmd_run(args, cfg) -> int:
    cfg.require_complete()
    user_id = _resolve_user_id(cfg, args.user_id)
    items = normalize_repo.fetch_pending(cfg.database_url, user_id, limit=args.limit)
    if not items:
        print("Nothing to normalize. Queue is empty.")
        return 0

    done = failed = 0
    for item in items:
        try:
            cleaned = tc.clean_body(item.source_type, item.extracted_text)
            normalize_repo.save_normalized(
                cfg.database_url,
                item.id,
                extracted_text=cleaned,
                text_excerpt=tc.make_excerpt(cleaned),
                sender=tc.normalize_sender(item.sender),
                participants=tc.normalize_participants(item.participants),
            )
            done += 1
        except Exception as error:  # noqa: BLE001 - record and continue
            failed += 1
            normalize_repo.mark_failed(cfg.database_url, item.id, str(error))
            print(f"  failed id={item.id}: {error}")

    print(f"Normalized {done} item(s); {failed} failed.")
    counts = normalize_repo.progress(cfg.database_url, user_id)
    print(f"Queue now: {counts}")
    return 0 if failed == 0 else 1


def cmd_status(args, cfg) -> int:
    cfg.require_complete()
    user_id = _resolve_user_id(cfg, args.user_id)
    counts = normalize_repo.progress(cfg.database_url, user_id)
    print("Stage 2 normalization progress")
    print("-" * 34)
    print(f"  normalized:     {counts['normalized']}")
    print(f"  not normalized: {counts['not_normalized']}")
    print(f"  failed:         {counts['failed']}")
    print(f"  total:          {counts['total']}")
    return 0


def cmd_preview(args, cfg) -> int:
    """Dry run: show before/after cleaning for a few rows without writing."""
    cfg.require_complete()
    user_id = _resolve_user_id(cfg, args.user_id)
    items = normalize_repo.fetch_pending(cfg.database_url, user_id, limit=args.limit)
    if not items:
        print("Nothing pending to preview.")
        return 0
    for item in items:
        cleaned = tc.clean_body(item.source_type, item.extracted_text)
        raw = (item.extracted_text or "").strip()
        print(f"\n=== [{item.source_type}] {item.title[:70]!r} (id={item.id}) ===")
        print(f"  raw     ({len(raw)} chars): {raw[:200]!r}")
        print(f"  cleaned ({len(cleaned)} chars): {cleaned[:200]!r}")
    print("\n(preview only - no rows were modified)")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Stage 2 Extract & Normalize.")
    sub = parser.add_subparsers(dest="command", required=True)

    p_run = sub.add_parser("run", help="Normalize pending rows.")
    p_run.add_argument("--user-id", dest="user_id", default=None)
    p_run.add_argument("--limit", type=int, default=200, help="Max rows this pass.")

    p_status = sub.add_parser("status", help="Show normalization counts.")
    p_status.add_argument("--user-id", dest="user_id", default=None)

    p_preview = sub.add_parser("preview", help="Dry-run before/after (no writes).")
    p_preview.add_argument("--user-id", dest="user_id", default=None)
    p_preview.add_argument("--limit", type=int, default=3)

    return parser.parse_args()


def main() -> int:
    args = parse_args()
    cfg = config_mod.load_config()
    if args.command == "run":
        return cmd_run(args, cfg)
    if args.command == "status":
        return cmd_status(args, cfg)
    if args.command == "preview":
        return cmd_preview(args, cfg)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
