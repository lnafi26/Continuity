"""Stage 5 orchestrator: Group & Link to Projects.

Builds project clusters from the Stage 4 relationship graph, uses the
Continuity model router to name + summarize them, creates AI projects, and links
their items via project_source_links (match_method='ai', review_status='pending').

`run` is incremental by default: items already linked to a project (any
match_method) are never re-clustered, re-summarized, or moved. A newly
synced item that relates strongly to something already in an existing
project is linked straight there (score-only, no LLM call, no new project).
Only items with no strong tie to an existing project get clustered into
brand-new ones, same as the original full-build behavior. `--reset` is
still available for a full rebuild -- it deletes every AI-origin project
(and, by cascade, their events/actions/links) and reclusters everything
from scratch; use it when you want to redo naming/grouping wholesale, not
for routine "a new email came in" runs.

  preview  cluster only, show what run would do (no writes, no LLM cost)
  run      link matches to existing projects, then name+create new ones
           for the rest                          [--reset] [--min-size N]
  status   AI project / link counts
  show     list AI projects with linked-item counts

Commands:
  python3 backend/grouping/group.py preview --user-id <uuid>
  python3 backend/grouping/group.py run --user-id <uuid>
  python3 backend/grouping/group.py run --user-id <uuid> --reset   # full rebuild
  python3 backend/grouping/group.py status --user-id <uuid>
  python3 backend/grouping/group.py show --user-id <uuid>
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "auth"))

import clustering
import config as config_mod
import grouping_repo as repo

# Standalone stage scripts don't automatically have the repository root on sys.path.
REPO_ROOT = HERE.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
from backend.intelligence import ModelRouter

# A small palette for AI-created project cards.
_PALETTE = [
    ("#4263eb", "#eef2ff"), ("#0ca678", "#e6fcf5"), ("#f76707", "#fff4e6"),
    ("#ae3ec9", "#f8f0fc"), ("#e64980", "#fff0f6"), ("#1c7ed6", "#e7f5ff"),
    ("#f59f00", "#fff9db"), ("#37b24d", "#ebfbee"),
]


def _resolve_user_id(cfg, explicit: str | None) -> str | None:
    user_id = (explicit or cfg.default_test_user_id or "").strip()
    if not user_id or user_id == "00000000-0000-0000-0000-000000000000":
        return None
    return user_id


def _member_initials(items) -> list[str]:
    seen: list[str] = []
    for item in items:
        people = list(item.participants or [])
        if item.sender:
            people.append(item.sender)
        for email in people:
            local = (email or "").split("@")[0]
            initials = "".join(part[:1] for part in local.replace(".", " ").split()[:2]).upper()
            if initials and initials not in seen:
                seen.append(initials)
            if len(seen) >= 5:
                return seen
    return seen


def _find_existing_matches(all_items, edges, linked):
    """For every unlinked item, the best-scoring existing project it connects
    to (if any), via an edge to an item that's already linked there. Pure --
    no writes, so both `preview` and `run` can share it."""
    matches = {}
    for item_id in all_items:
        if item_id in linked:
            continue
        best_project_id, best_score = None, 0.0
        for a, b, score in edges:
            other = b if a == item_id else (a if b == item_id else None)
            if other is None:
                continue
            other_project = linked.get(other)
            if other_project and score > best_score:
                best_project_id, best_score = other_project, score
        if best_project_id:
            matches[item_id] = (best_project_id, best_score)
    return matches


def cmd_preview(args, cfg) -> int:
    user_id = _resolve_user_id(cfg, args.user_id)
    if not user_id:
        print("Need a user. Pass --user-id or set DEFAULT_TEST_USER_ID.")
        return 1

    linked = repo.fetch_linked_items(cfg.database_url, user_id)
    all_items = repo.fetch_included(cfg.database_url, user_id)
    edges = repo.fetch_edges(cfg.database_url, user_id, args.threshold)

    matches = _find_existing_matches(all_items, edges, linked)
    if matches:
        print(f"{len(matches)} item(s) would attach to an existing project "
              f"(no new projects, no LLM calls):")
        for item_id, (project_id, score) in matches.items():
            m = all_items[item_id]
            print(f"     - [{m.source_type}] {(m.title or '(no title)')[:60]} "
                  f"-> project {project_id} (score {score:.2f})")
        print()

    items = {
        iid: all_items[iid] for iid in all_items
        if iid not in linked and iid not in matches
    }
    remaining_edges = [(a, b, s) for a, b, s in edges if a in items and b in items]
    components = clustering.connected_components(list(items), remaining_edges, args.threshold)
    clusters = [c for c in components if len(c) >= args.min_size]
    if not clusters:
        if not matches:
            print(f"No clusters of size >= {args.min_size} at threshold {args.threshold}.")
        return 0
    print(f"{len(clusters)} new cluster(s) of size >= {args.min_size} "
          f"(threshold {args.threshold}); no writes, no LLM calls:\n")
    for i, member_ids in enumerate(clusters, 1):
        members = [items[mid] for mid in member_ids]
        cohesion = clustering.cluster_cohesion(set(member_ids), remaining_edges)
        print(f"  Cluster {i}: {len(members)} items, cohesion {cohesion:.2f}")
        for m in members[:6]:
            print(f"     - [{m.source_type}] {(m.title or '(no title)')[:60]}")
        if len(members) > 6:
            print(f"     ... and {len(members) - 6} more")
    return 0


def cmd_run(args, cfg) -> int:
    user_id = _resolve_user_id(cfg, args.user_id)
    if not user_id:
        print("Need a user. Pass --user-id or set DEFAULT_TEST_USER_ID.")
        return 1

    existing = repo.ai_projects_exist(cfg.database_url, user_id)
    if args.reset and existing:
        removed = repo.delete_ai_projects(cfg.database_url, user_id)
        print(f"Reset: removed {removed} AI project(s) and their links.")

    # Incremental by default: items already linked to a project (by any
    # match_method -- AI, rule, or manual) are never re-clustered or moved.
    # --reset clears links above, so this is empty on a full rebuild.
    linked = repo.fetch_linked_items(cfg.database_url, user_id)

    all_items = repo.fetch_included(cfg.database_url, user_id)
    edges = repo.fetch_edges(cfg.database_url, user_id, args.threshold)

    # ---- Step 1: attach already-unlinked items to an existing project when
    # they're strongly related to something already in it. No LLM call --
    # the relationship score alone decides it, same "deterministic/structural
    # signal first" spirit as everywhere else in the pipeline. ----
    matches = _find_existing_matches(all_items, edges, linked)
    for item_id, (project_id, score) in matches.items():
        repo.link_item(
            cfg.database_url, user_id, project_id, item_id,
            confidence=score,
            explanation=f"Linked to an existing project via item "
                        f"relationship (score {score:.2f}).",
        )
    if matches:
        print(f"Linked {len(matches)} item(s) to existing project(s) "
              f"(no new projects, no LLM calls).")

    # ---- Step 2: cluster whatever's left -- items with no strong tie to an
    # existing project -- into brand-new projects. Exactly the original
    # clustering logic, just scoped to the remaining unlinked items so
    # existing projects/events/actions are never touched. ----
    items = {
        iid: all_items[iid] for iid in all_items
        if iid not in linked and iid not in matches
    }
    remaining_edges = [(a, b, s) for a, b, s in edges if a in items and b in items]
    components = clustering.connected_components(list(items), remaining_edges, args.threshold)
    clusters = [c for c in components if len(c) >= args.min_size]
    if not clusters:
        if not matches:
            print(f"No clusters of size >= {args.min_size} to group.")
        return 0

    router = ModelRouter()
    print(f"Naming {len(clusters)} cluster(s) via offline model router "
          "(no external inference calls).")

    created = 0
    for idx, member_ids in enumerate(clusters):
        members = [items[mid] for mid in member_ids]
        cohesion = clustering.cluster_cohesion(set(member_ids), edges)
        item_dicts = [
            {
                "source_type": m.source_type, "title": m.title,
                "sender": m.sender, "occurred_at": str(m.occurred_at or ""),
                "excerpt": m.excerpt,
            }
            for m in members
        ]
        naming_result = router.run("project_naming", {"items": item_dicts})
        named = naming_result.data
        color, soft = _PALETTE[idx % len(_PALETTE)]
        project_id = repo.create_project(
            cfg.database_url, user_id,
            name=named["name"], symbol=named["symbol"], summary=named["summary"],
            color=color, soft_color=soft, members=_member_initials(members),
            category=named.get("category", "project"),
        )
        # Link confidence blends structural cohesion with naming coherence.
        confidence = round(min(1.0, 0.5 * cohesion + 0.5 * named["coherence"]), 4)
        explanation = (
            f"Grouped by semantic + deterministic similarity "
            f"(cohesion {cohesion:.2f}, naming coherence {named['coherence']:.2f}, "
            f"provider {naming_result.provider})."
        )
        for m in members:
            repo.link_item(
                cfg.database_url, user_id, project_id, m.id,
                confidence=confidence, explanation=explanation,
            )
        created += 1
        print(f"  + {named['symbol']} {named['name']}  "
              f"({len(members)} items, confidence {confidence:.2f})")

    print(f"\nCreated {created} AI project(s).")
    return 0


def cmd_status(args, cfg) -> int:
    user_id = _resolve_user_id(cfg, args.user_id)
    if not user_id:
        print("Need a user. Pass --user-id or set DEFAULT_TEST_USER_ID.")
        return 1
    counts = repo.progress(cfg.database_url, user_id)
    print("Stage 5 grouping progress")
    print("-" * 34)
    print(f"  AI projects:     {counts['ai_projects']}")
    print(f"  AI links:        {counts['ai_links']}")
    print(f"  included items:  {counts['included_items']}")
    return 0


def cmd_show(args, cfg) -> int:
    user_id = _resolve_user_id(cfg, args.user_id)
    if not user_id:
        print("Need a user. Pass --user-id or set DEFAULT_TEST_USER_ID.")
        return 1
    rows = repo.list_ai_projects(cfg.database_url, user_id)
    if not rows:
        print("No AI projects yet. Run `group.py run` first.")
        return 0
    print(f"AI projects ({len(rows)}):\n")
    for name, symbol, summary, items, avg_conf in rows:
        print(f"  {symbol}  {name}  ({items} items, avg confidence {avg_conf})")
        if summary:
            print(f"        {summary[:100]}")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Stage 5 Group & Link to Projects.")
    sub = parser.add_subparsers(dest="command", required=True)
    for name, help_text in [
        ("preview", "Cluster only (no writes, no LLM calls)."),
        ("run", "Name clusters and write projects + links."),
        ("status", "AI project / link counts."),
        ("show", "List AI projects."),
    ]:
        p = sub.add_parser(name, help=help_text)
        p.add_argument("--user-id", dest="user_id", default=None)
        if name in ("preview", "run"):
            p.add_argument("--threshold", type=float, default=0.5,
                           help="Min combined_score for an edge to connect items.")
            p.add_argument("--min-size", dest="min_size", type=int, default=2,
                           help="Minimum cluster size to become a project.")
        if name == "run":
            p.add_argument("--reset", action="store_true",
                           help="Full rebuild: delete every AI-origin project "
                                "(and their events/actions/links) and recluster "
                                "everything from scratch. Not needed for normal "
                                "incremental runs.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    cfg = config_mod.load_config()
    return {
        "preview": cmd_preview,
        "run": cmd_run,
        "status": cmd_status,
        "show": cmd_show,
    }[args.command](args, cfg)


if __name__ == "__main__":
    raise SystemExit(main())
