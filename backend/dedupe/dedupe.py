"""Stage 3 orchestrator: Clean & Deduplicate.

Consumes normalized rows (normalized_at set, deduped_at NULL) and decides, for
each, whether it proceeds to AI grouping. Excluded rows are kept and retrievable
but flagged out of grouping with a reason:

  - noise               newsletters / automated notifications (per-row rule)
  - off_topic           not work (personal/entertainment/job-alert) per LLM gate
  - recurring_instance  extra instances of a recurring calendar series
  - duplicate           same content_hash as an earlier kept item

Precedence when several apply: (noise | off_topic) > recurring_instance >
duplicate. One representative per recurring series / duplicate group stays
included. The work-gate runs by default; pass --no-gate for the cheap
deterministic filter only.

Commands:
  python3 backend/dedupe/dedupe.py run       [--user-id <uuid>] [--limit N]
  python3 backend/dedupe/dedupe.py preview    [--user-id <uuid>] [--limit N]
  python3 backend/dedupe/dedupe.py status     [--user-id <uuid>]
"""

from __future__ import annotations

import argparse
import os
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "auth"))

import classification as cl
import config as config_mod
import dedupe_repo
import relevance_gate


def _resolve_user_id(cfg, explicit: str | None) -> str | None:
    user_id = (explicit or cfg.default_test_user_id or "").strip()
    if not user_id or user_id == "00000000-0000-0000-0000-000000000000":
        return None
    return user_id


def _rep_key(row):
    """Sort key to choose a group's representative: earliest occurrence wins."""
    if row.occurred_at is not None:
        return (0, row.occurred_at, str(row.id))
    return (1, row.created_at, str(row.id))


def decide(rows, forced_exclusions: dict | None = None) -> tuple[dict, dict]:
    """Compute per-row (hash, reason). Returns (hash_by_id, reason_by_id).

    reason_by_id only contains excluded rows; absence means included.
    `forced_exclusions` maps id -> reason ('noise' | 'off_topic') already decided
    by the classification step; these take precedence over recurring/duplicate.
    """
    forced = forced_exclusions or {}
    hash_by_id: dict = {}
    reason_by_id: dict = {}

    # 1) Pre-decided exclusions: deterministic noise + LLM off_topic (highest).
    for row in rows:
        hash_by_id[row.id] = cl.content_hash(
            row.source_type, row.title, row.extracted_text
        )
        if row.id in forced:
            reason_by_id[row.id] = forced[row.id]

    # 2) Collapse recurring calendar series (keep one representative).
    series = defaultdict(list)
    for row in rows:
        if row.source_type == "google_calendar" and row.external_thread_id:
            series[(row.connection_id, row.external_thread_id)].append(row)
    for group in series.values():
        if len(group) < 2:
            continue
        rep = min(group, key=_rep_key)
        for row in group:
            if row.id != rep.id and row.id not in reason_by_id:
                reason_by_id[row.id] = "recurring_instance"

    # 3) Content-hash duplicates (keep the earliest representative).
    by_hash = defaultdict(list)
    for row in rows:
        h = hash_by_id.get(row.id)
        if h:
            by_hash[h].append(row)
    for group in by_hash.values():
        if len(group) < 2:
            continue
        rep = min(group, key=_rep_key)
        for row in group:
            if row.id != rep.id and row.id not in reason_by_id:
                reason_by_id[row.id] = "duplicate"

    return hash_by_id, reason_by_id


def _classify_exclusions(rows, use_gate: bool) -> dict:
    """Return {id: reason} for items excluded before recurring/duplicate.

    Two layers:
      * Deterministic noise (cheap, always on): obvious bulk/automated mail is
        excluded as 'noise' without an LLM call.
      * Work-gate (LLM, on by default): every remaining item is classified
        work-vs-not-work; non-work items are excluded as 'off_topic'. This is
        what enforces "work-only", since personal mail from a real person is not
        'noise' but still isn't work.
    """
    forced: dict = {}
    for row in rows:
        if cl.is_noise(row.sender, row.title, row.extracted_text):
            forced[row.id] = "noise"

    if not use_gate:
        return forced

    api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if not api_key or api_key.endswith("REPLACE_ME"):
        print("Work-gate skipped: no ANTHROPIC_API_KEY set. "
              "Deterministic noise filter only -- personal/off-topic mail may "
              "pass through. Re-run with a key (or --no-gate to silence this).")
        return forced

    model = os.getenv("ANTHROPIC_GATE_MODEL", relevance_gate.DEFAULT_GATE_MODEL).strip()
    candidates = [r for r in rows if r.id not in forced]
    if not candidates:
        return forced
    print(f"Work-gate: classifying {len(candidates)} item(s) work-vs-not-work "
          f"with {model} ...")
    off_topic = 0
    for row in candidates:
        if not relevance_gate.is_work_related(
            row.sender, row.title, row.extracted_text, api_key=api_key, model=model
        ):
            forced[row.id] = "off_topic"
            off_topic += 1
    print(f"Work-gate: excluded {off_topic} of {len(candidates)} as off-topic "
          f"(not work).")
    return forced


def cmd_run(args, cfg) -> int:
    cfg.require_complete()
    user_id = _resolve_user_id(cfg, args.user_id)
    rows = dedupe_repo.fetch_queue(cfg.database_url, user_id, limit=args.limit)
    if not rows:
        print("Nothing to deduplicate. Queue is empty.")
        return 0

    forced = _classify_exclusions(rows, use_gate=not args.no_gate)
    hash_by_id, reason_by_id = decide(rows, forced_exclusions=forced)
    tally = {"included": 0, "noise": 0, "off_topic": 0,
             "recurring_instance": 0, "duplicate": 0}
    for row in rows:
        reason = reason_by_id.get(row.id)
        dedupe_repo.apply_decision(
            cfg.database_url,
            row.id,
            content_hash=hash_by_id.get(row.id),
            include_in_grouping=reason is None,
            exclusion_reason=reason,
        )
        tally[reason or "included"] += 1

    print(f"Processed {len(rows)} row(s):")
    print(f"  included (ready for grouping): {tally['included']}")
    print(f"  excluded - noise:              {tally['noise']}")
    print(f"  excluded - off_topic (not work): {tally['off_topic']}")
    print(f"  excluded - recurring_instance: {tally['recurring_instance']}")
    print(f"  excluded - duplicate:          {tally['duplicate']}")
    return 0


def cmd_preview(args, cfg) -> int:
    """Dry run: show the decision for each queued row without writing."""
    cfg.require_complete()
    user_id = _resolve_user_id(cfg, args.user_id)
    rows = dedupe_repo.fetch_queue(cfg.database_url, user_id, limit=args.limit)
    if not rows:
        print("Nothing pending to preview.")
        return 0
    forced = _classify_exclusions(rows, use_gate=not args.no_gate)
    _, reason_by_id = decide(rows, forced_exclusions=forced)
    for row in rows:
        reason = reason_by_id.get(row.id) or "INCLUDE"
        who = row.sender or "(no sender)"
        print(f"  {reason:<18} [{row.source_type}] {who:<34} {row.title[:44]!r}")
    print("\n(preview only - no rows were modified)")
    return 0


def cmd_status(args, cfg) -> int:
    cfg.require_complete()
    user_id = _resolve_user_id(cfg, args.user_id)
    counts = dedupe_repo.progress(cfg.database_url, user_id)
    print("Stage 3 dedupe/clean progress")
    print("-" * 34)
    print(f"  queued (not yet deduped): {counts['queued']}")
    print(f"  included for grouping:    {counts['included']}")
    print(f"  excluded - duplicate:     {counts['duplicate']}")
    print(f"  excluded - recurring:     {counts['recurring_instance']}")
    print(f"  excluded - noise:         {counts['noise']}")
    print(f"  excluded - off_topic:     {counts['off_topic']}")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Stage 3 Clean & Deduplicate.")
    sub = parser.add_subparsers(dest="command", required=True)
    for name, help_text in [
        ("run", "Apply dedupe/clean decisions to the queue."),
        ("preview", "Dry-run the decisions (no writes)."),
        ("status", "Show dedupe counts."),
    ]:
        p = sub.add_parser(name, help=help_text)
        p.add_argument("--user-id", dest="user_id", default=None)
        if name in ("run", "preview"):
            p.add_argument("--limit", type=int, default=1000)
            p.add_argument("--no-gate", dest="no_gate", action="store_true",
                           help="Disable the LLM work-gate and use only the "
                                "deterministic noise filter (faster/free, but "
                                "personal/off-topic mail may pass through).")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    cfg = config_mod.load_config()
    return {
        "run": cmd_run,
        "preview": cmd_preview,
        "status": cmd_status,
    }[args.command](args, cfg)


if __name__ == "__main__":
    raise SystemExit(main())
