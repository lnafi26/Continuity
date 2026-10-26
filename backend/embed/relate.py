"""Stage 4 orchestrator: Embed & detect relationships.

  embed   -> embed included, deduplicated rows into source_items.embedding
  relate  -> score candidate pairs (semantic KNN + deterministic) into
             item_relationships
  status  -> embedded count + relationship count
  show    -> print the top candidate pairs

Commands:
  python3 backend/embed/relate.py embed  --user-id <uuid>
  python3 backend/embed/relate.py relate --user-id <uuid> [--reset] [--k 5] [--threshold 0.45]
  python3 backend/embed/relate.py status --user-id <uuid>
  python3 backend/embed/relate.py show   --user-id <uuid> [--limit 20]
"""

from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from itertools import combinations
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "auth"))

import config as config_mod
import deterministic
import embed_repo
import embeddings
import relationships_repo as rr


def _resolve_user_id(cfg, explicit: str | None) -> str | None:
    user_id = (explicit or cfg.default_test_user_id or "").strip()
    if not user_id or user_id == "00000000-0000-0000-0000-000000000000":
        return None
    return user_id


def _item_dict(info) -> dict:
    return {
        "thread": info.thread,
        "sender": info.sender,
        "participants": info.participants,
        "title": info.title,
        "occurred_at": info.occurred_at,
    }


def cmd_embed(args, cfg) -> int:
    cfg.require_complete()
    user_id = _resolve_user_id(cfg, args.user_id)
    rows = embed_repo.fetch_to_embed(cfg.database_url, user_id, limit=args.limit)
    if not rows:
        print("Nothing to embed. All included items already have embeddings.")
        return 0
    print(f"Embedding {len(rows)} item(s) with {embeddings.MODEL_NAME} ...")
    inputs = [embeddings.build_embedding_input(r.title, r.extracted_text) for r in rows]
    vectors = embeddings.embed_texts(inputs)
    for row, vector in zip(rows, vectors):
        embed_repo.save_embedding(cfg.database_url, row.id, vector)
    print(f"Embedded and stored {len(rows)} item(s).")
    return 0


def cmd_relate(args, cfg) -> int:
    cfg.require_complete()
    user_id = _resolve_user_id(cfg, args.user_id)
    if not user_id:
        print("relate needs a user. Pass --user-id or set DEFAULT_TEST_USER_ID.")
        return 1

    items = rr.fetch_included_items(cfg.database_url, user_id)
    if len(items) < 2:
        print(f"Only {len(items)} embedded item(s); need at least 2 to relate.")
        return 0

    if args.reset:
        rr.clear_for_user(cfg.database_url, user_id)

    by_id = {it.id: it for it in items}
    sim_by_pair: dict[tuple[str, str], float] = {}

    def canon(a: str, b: str) -> tuple[str, str]:
        return tuple(sorted([a, b]))  # type: ignore[return-value]

    # Semantic candidates: each item's nearest neighbours.
    candidates: set[tuple[str, str]] = set()
    for it in items:
        for neighbor_id, sim in rr.knn(cfg.database_url, user_id, it.id, k=args.k):
            if neighbor_id in by_id:
                pair = canon(it.id, neighbor_id)
                candidates.add(pair)
                sim_by_pair[pair] = max(sim_by_pair.get(pair, -1.0), sim)

    # Structural candidates: items sharing an email thread (may be semantically
    # distant yet clearly related).
    threads = defaultdict(list)
    for it in items:
        if it.thread:
            threads[it.thread].append(it.id)
    for ids in threads.values():
        for a, b in combinations(ids, 2):
            candidates.add(canon(a, b))

    stored = 0
    for a_id, b_id in candidates:
        a, b = by_id[a_id], by_id[b_id]
        det_score, signals = deterministic.signals_between(_item_dict(a), _item_dict(b))
        pair = canon(a_id, b_id)
        semantic = sim_by_pair.get(pair)
        if semantic is None:
            semantic = rr.pair_similarity(cfg.database_url, a_id, b_id)
        combined = deterministic.combine(semantic, det_score, signals)

        if combined >= args.threshold or signals["same_thread"]:
            rr.upsert_relationship(
                cfg.database_url, user_id, a_id, b_id,
                semantic=semantic, deterministic=det_score,
                combined=combined, signals=signals,
            )
            stored += 1

    print(f"Evaluated {len(candidates)} candidate pair(s); "
          f"stored {stored} above threshold {args.threshold} (or same-thread).")
    return 0


def cmd_status(args, cfg) -> int:
    cfg.require_complete()
    user_id = _resolve_user_id(cfg, args.user_id)
    to_embed = len(embed_repo.fetch_to_embed(cfg.database_url, user_id, limit=100000))
    embedded = len(rr.fetch_included_items(cfg.database_url, user_id))
    pairs = rr.count_relationships(cfg.database_url, user_id)
    print("Stage 4 embed & relationships")
    print("-" * 34)
    print(f"  embedded items:      {embedded}")
    print(f"  awaiting embedding:  {to_embed}")
    print(f"  relationship pairs:  {pairs}")
    return 0


def cmd_show(args, cfg) -> int:
    cfg.require_complete()
    user_id = _resolve_user_id(cfg, args.user_id)
    rows = rr.top_relationships(cfg.database_url, user_id, limit=args.limit)
    if not rows:
        print("No relationships yet. Run `embed` then `relate` first.")
        return 0
    print(f"Top {len(rows)} candidate relationships (by combined score):\n")
    for combined, semantic, det, signals, title_a, title_b in rows:
        flags = []
        if signals.get("same_thread"):
            flags.append("thread")
        if signals.get("shared_sender"):
            flags.append("sender")
        if signals.get("participant_overlap"):
            flags.append(f"ppl={signals['participant_overlap']}")
        if signals.get("keyword_overlap"):
            flags.append(f"kw={signals['keyword_overlap']}")
        flag_str = ", ".join(flags) or "semantic-only"
        print(f"  {float(combined):.3f}  (sem {float(semantic):.2f} / det {float(det):.2f})  [{flag_str}]")
        print(f"        {(title_a or '(untitled)')[:52]!r}")
        print(f"        {(title_b or '(untitled)')[:52]!r}")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Stage 4 Embed & detect relationships.")
    sub = parser.add_subparsers(dest="command", required=True)

    p_embed = sub.add_parser("embed", help="Embed included items into pgvector.")
    p_embed.add_argument("--user-id", dest="user_id", default=None)
    p_embed.add_argument("--limit", type=int, default=1000)

    p_relate = sub.add_parser("relate", help="Score candidate relationships.")
    p_relate.add_argument("--user-id", dest="user_id", default=None)
    p_relate.add_argument("--reset", action="store_true", help="Delete existing pairs first.")
    p_relate.add_argument("--k", type=int, default=5, help="Nearest neighbours per item.")
    p_relate.add_argument("--threshold", type=float, default=0.45, help="Min combined score to store.")

    p_status = sub.add_parser("status", help="Embedded + relationship counts.")
    p_status.add_argument("--user-id", dest="user_id", default=None)

    p_show = sub.add_parser("show", help="Print top candidate relationships.")
    p_show.add_argument("--user-id", dest="user_id", default=None)
    p_show.add_argument("--limit", type=int, default=20)

    return parser.parse_args()


def main() -> int:
    args = parse_args()
    cfg = config_mod.load_config()
    return {
        "embed": cmd_embed,
        "relate": cmd_relate,
        "status": cmd_status,
        "show": cmd_show,
    }[args.command](args, cfg)


if __name__ == "__main__":
    raise SystemExit(main())
