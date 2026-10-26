"""Stage 7 orchestrator: precompute the catch-up digest's per-project summary.

For each project with events newer than its last summary (or none yet),
uses the Continuity model router for a concise sentence and writes it
to projects.catchup_summary. Run this after Stage 6 extraction so the digest
has a fresh sentence ready -- the dashboard only ever reads it, never
generates it live.

  preview  dry-run: print what would be generated (LLM calls, no writes)
  run      generate and write summaries for projects that need one
  status   summarized / missing counts

Commands:
  python3 backend/digest/summarize.py preview --user-id <uuid>
  python3 backend/digest/summarize.py run --user-id <uuid>
  python3 backend/digest/summarize.py status --user-id <uuid>
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "auth"))

import config as config_mod
import summarize_repo

REPO_ROOT = HERE.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
from backend.intelligence import ModelRouter


def _resolve_user_id(cfg, explicit: str | None) -> str | None:
    user_id = (explicit or cfg.default_test_user_id or "").strip()
    if not user_id or user_id == "00000000-0000-0000-0000-000000000000":
        return None
    return user_id


def cmd_run(args, cfg) -> int:
    user_id = _resolve_user_id(cfg, args.user_id)
    if not user_id:
        print("Need a user. Pass --user-id or set DEFAULT_TEST_USER_ID.")
        return 1
    targets = summarize_repo.fetch_projects_needing_summary(cfg.database_url, user_id)
    if not targets:
        print("Nothing to summarize. All projects are up to date.")
        return 0

    router = ModelRouter()
    print(f"Summarizing {len(targets)} project(s) via offline model router "
          "(no external inference calls).")

    for t in targets:
        events = summarize_repo.fetch_recent_events(cfg.database_url, t.id)
        sentence = router.run("digest_summary", {
            "project_name": t.name, "events": events,
        }).data["summary"]
        summarize_repo.update_summary(cfg.database_url, t.id, sentence)
        print(f"  [{t.name}] {sentence}")

    print(f"\nSummarized {len(targets)} project(s).")
    return 0


def cmd_preview(args, cfg) -> int:
    user_id = _resolve_user_id(cfg, args.user_id)
    if not user_id:
        print("Need a user. Pass --user-id or set DEFAULT_TEST_USER_ID.")
        return 1
    targets = summarize_repo.fetch_projects_needing_summary(cfg.database_url, user_id)
    if not targets:
        print("Nothing pending to preview.")
        return 0
    router = ModelRouter()
    print(f"Dry-run of {len(targets)} project(s) "
          "(offline deterministic summary); no writes or external inference calls:\n")
    for t in targets:
        events = summarize_repo.fetch_recent_events(cfg.database_url, t.id)
        sentence = router.run("digest_summary", {
            "project_name": t.name, "events": events,
        }).data["summary"]
        print(f"[{t.name}] ({len(events)} recent event(s))\n  {sentence}\n")
    print("(preview only - no rows were modified)")
    return 0


def cmd_status(args, cfg) -> int:
    user_id = _resolve_user_id(cfg, args.user_id)
    if not user_id:
        print("Need a user. Pass --user-id or set DEFAULT_TEST_USER_ID.")
        return 1
    counts = summarize_repo.progress(cfg.database_url, user_id)
    print("Stage 7 digest summary progress")
    print("-" * 34)
    print(f"  summarized: {counts['summarized']}")
    print(f"  missing:    {counts['missing']}")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Stage 7 precompute digest summaries.")
    sub = parser.add_subparsers(dest="command", required=True)
    for name, help_text in [
        ("preview", "Dry-run summarization for projects that need it (LLM calls, no writes)."),
        ("run", "Generate and write summaries for projects that need one."),
        ("status", "Summarized / missing counts."),
    ]:
        p = sub.add_parser(name, help=help_text)
        p.add_argument("--user-id", dest="user_id", default=None)
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
