"""Stage 6 orchestrator: Extract Events & Actions.

For each item linked to a project but not yet extracted, uses the
Continuity model router to derive timeline events and actions for project_events /
project_actions (AI rows, user_edited=false). Marks the item extracted.

  preview  dry-run: show what would be extracted for a few items (LLM calls, no writes)
  run      extract the queue and write events/actions        [--reset] [--limit N]
  status   event / action / queue counts

Commands:
  python3 backend/extract/extract.py preview --user-id <uuid> --limit 3
  python3 backend/extract/extract.py run --user-id <uuid>
  python3 backend/extract/extract.py status --user-id <uuid>
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "auth"))

import config as config_mod
import extract_repo

REPO_ROOT = HERE.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
from backend.intelligence import ModelRouter


def _resolve_user_id(cfg, explicit: str | None) -> str | None:
    user_id = (explicit or cfg.default_test_user_id or "").strip()
    if not user_id or user_id == "00000000-0000-0000-0000-000000000000":
        return None
    return user_id


def _item_dict(it) -> dict:
    return {
        "source_type": it.source_type, "title": it.title, "sender": it.sender,
        "participants": it.participants, "occurred_at": it.occurred_at,
        "extracted_text": it.extracted_text,
    }


def cmd_run(args, cfg) -> int:
    user_id = _resolve_user_id(cfg, args.user_id)
    if not user_id:
        print("Need a user. Pass --user-id or set DEFAULT_TEST_USER_ID.")
        return 1

    if args.reset:
        r = extract_repo.reset(cfg.database_url, user_id)
        print(f"Reset: deleted {r['events_deleted']} event(s), "
              f"{r['actions_deleted']} action(s); re-queued {r['requeued']} item(s).")

    items = extract_repo.fetch_queue(cfg.database_url, user_id, limit=args.limit)
    if not items:
        print("Nothing to extract. Queue is empty.")
        return 0

    router = ModelRouter()
    print(f"Extracting {len(items)} item(s) via offline model router "
          "(metadata-derived events; no external inference calls).")

    ev_total = ac_total = 0
    for it in items:
        result = router.run("event_extraction", {"item": _item_dict(it)}).data
        for ev in result["events"]:
            extract_repo.insert_event(cfg.database_url, user_id, it.project_id, it.id, ev, it.color)
        for ac in result["actions"]:
            extract_repo.insert_action(cfg.database_url, user_id, it.project_id, it.id, ac, it.color)
        extract_repo.mark_extracted(cfg.database_url, it.id)
        ev_total += len(result["events"])
        ac_total += len(result["actions"])

    print(f"Extracted {ev_total} event(s) and {ac_total} action(s) "
          f"from {len(items)} item(s).")
    return 0


def cmd_preview(args, cfg) -> int:
    user_id = _resolve_user_id(cfg, args.user_id)
    if not user_id:
        print("Need a user. Pass --user-id or set DEFAULT_TEST_USER_ID.")
        return 1
    items = extract_repo.fetch_queue(cfg.database_url, user_id, limit=args.limit)
    if not items:
        print("Nothing pending to preview.")
        return 0
    router = ModelRouter()
    print(f"Dry-run of {len(items)} item(s) "
          "(offline metadata fallback); no writes or external inference calls:\n")
    for it in items:
        result = router.run("event_extraction", {"item": _item_dict(it)}).data
        print(f"[{it.source_type}] {(it.title or '(untitled)')[:70]}")
        for ev in result["events"]:
            rr = ev.get("requires_response")
            rr_label = "needs reply" if rr else ("no reply needed" if rr is False else "unclassified")
            print(f"   event  ({ev['event_type']}, {ev['confidence']:.2f}, {rr_label}) "
                  f"{ev['title'][:60]}")
        for ac in result["actions"]:
            due = ac["due_date"] or "no date"
            tag = ac["status"] + (", backlog" if ac["backlog"] else "")
            print(f"   action ({ac['confidence']:.2f}, due {due}, {tag}) {ac['title'][:60]}")
    print("\n(preview only - no rows were modified)")
    return 0


def cmd_status(args, cfg) -> int:
    user_id = _resolve_user_id(cfg, args.user_id)
    if not user_id:
        print("Need a user. Pass --user-id or set DEFAULT_TEST_USER_ID.")
        return 1
    counts = extract_repo.progress(cfg.database_url, user_id)
    print("Stage 6 extract progress")
    print("-" * 34)
    print(f"  timeline events:  {counts['events']}")
    print(f"  action items:     {counts['actions']}")
    print(f"  queued (linked, not extracted): {counts['queued']}")

    board = extract_repo.status_breakdown(cfg.database_url, user_id)
    print("\nBoard (project_actions.status / backlog)")
    print(f"  not_started: {board['not_started']}   in_progress: {board['in_progress']}   "
          f"completed: {board['completed']}   backlog: {board['backlog']}")
    print("Waiting list (project_events.requires_response)")
    print(f"  requires_response: {board['requires_response']}   "
          f"no_response_needed: {board['no_response_needed']}   "
          f"not_yet_classified: {board['not_yet_classified']}")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Stage 6 Extract Events & Actions.")
    sub = parser.add_subparsers(dest="command", required=True)
    for name, help_text in [
        ("preview", "Dry-run extraction for a few items (LLM calls, no writes)."),
        ("run", "Extract the queue and write events/actions."),
        ("status", "Event / action / queue counts."),
    ]:
        p = sub.add_parser(name, help=help_text)
        p.add_argument("--user-id", dest="user_id", default=None)
        if name == "preview":
            p.add_argument("--limit", type=int, default=3)
        if name == "run":
            p.add_argument("--limit", type=int, default=500)
            p.add_argument("--reset", action="store_true",
                           help="Delete AI-generated events/actions and re-extract.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    cfg = config_mod.load_config()
    return {
        "preview": cmd_preview,
        "run": cmd_run,
        "status": cmd_status,
    }[args.command](args, cfg)


if __name__ == "__main__":
    raise SystemExit(main())
