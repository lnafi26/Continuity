"""Database access for candidate relationships (Stage 4, relationship half).

Provides the included items (with deterministic fields), pgvector nearest-
neighbour search, pairwise similarity, and upserts into item_relationships.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

import psycopg


@dataclass
class ItemInfo:
    id: str
    title: str
    sender: str | None
    participants: list[str]
    thread: str | None
    occurred_at: object  # tz-aware datetime or None


def fetch_included_items(
    database_url: str, user_id: str | None = None
) -> list[ItemInfo]:
    """Included, embedded items with the fields deterministic signals need."""
    where = [
        "include_in_grouping = true",
        "deduped_at is not null",
        "embedding is not null",
    ]
    params: list = []
    if user_id:
        where.append("user_id = %s")
        params.append(user_id)
    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                select id, title, sender, participants,
                       external_thread_id, occurred_at
                from public.source_items
                where {" and ".join(where)}
                order by created_at
                """,
                params,
            )
            rows = cursor.fetchall()
    return [
        ItemInfo(
            id=str(r[0]),
            title=r[1] or "",
            sender=r[2],
            participants=r[3] or [],
            thread=r[4],
            occurred_at=r[5],
        )
        for r in rows
    ]


def knn(
    database_url: str, user_id: str, item_id: str, k: int = 5
) -> list[tuple[str, float]]:
    """Return the k nearest included items to item_id as (id, cosine_similarity)."""
    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                select id,
                       1 - (embedding <=> (select embedding from public.source_items
                                           where id = %(item)s)) as similarity
                from public.source_items
                where user_id = %(user)s
                  and include_in_grouping = true
                  and deduped_at is not null
                  and embedding is not null
                  and id <> %(item)s
                order by embedding <=> (select embedding from public.source_items
                                        where id = %(item)s)
                limit %(k)s
                """,
                {"item": item_id, "user": user_id, "k": k},
            )
            return [(str(r[0]), float(r[1])) for r in cursor.fetchall()]


def pair_similarity(database_url: str, a_id: str, b_id: str) -> float:
    """Cosine similarity between two specific items' embeddings."""
    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                select 1 - (a.embedding <=> b.embedding)
                from public.source_items a, public.source_items b
                where a.id = %s and b.id = %s
                """,
                (a_id, b_id),
            )
            row = cursor.fetchone()
    return float(row[0]) if row and row[0] is not None else 0.0


def clear_for_user(database_url: str, user_id: str) -> None:
    """Delete existing relationships for a user (used by relate --reset)."""
    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "delete from public.item_relationships where user_id = %s", (user_id,)
            )


def upsert_relationship(
    database_url: str,
    user_id: str,
    a_id: str,
    b_id: str,
    *,
    semantic: float,
    deterministic: float,
    combined: float,
    signals: dict,
) -> None:
    """Insert/update one undirected pair, stored canonically (min id first)."""
    src, rel = sorted([str(a_id), str(b_id)])
    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                insert into public.item_relationships
                    (user_id, source_item_id, related_item_id,
                     semantic_score, deterministic_score, combined_score, signals)
                values (%s, %s, %s, %s, %s, %s, %s)
                on conflict (source_item_id, related_item_id) do update set
                    semantic_score = excluded.semantic_score,
                    deterministic_score = excluded.deterministic_score,
                    combined_score = excluded.combined_score,
                    signals = excluded.signals
                """,
                (
                    user_id, src, rel,
                    round(semantic, 5), round(deterministic, 5), round(combined, 5),
                    json.dumps(signals),
                ),
            )


def top_relationships(
    database_url: str, user_id: str | None, limit: int = 20
) -> list[tuple]:
    """Return top pairs by combined_score with both titles, for display."""
    user_filter = "where r.user_id = %s" if user_id else ""
    params: list = [user_id] if user_id else []
    params.append(limit)
    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                select r.combined_score, r.semantic_score, r.deterministic_score,
                       r.signals, a.title, b.title
                from public.item_relationships r
                join public.source_items a on a.id = r.source_item_id
                join public.source_items b on b.id = r.related_item_id
                {user_filter}
                order by r.combined_score desc
                limit %s
                """,
                params,
            )
            return cursor.fetchall()


def count_relationships(database_url: str, user_id: str | None = None) -> int:
    user_filter = "where user_id = %s" if user_id else ""
    params = [user_id] if user_id else []
    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                f"select count(*) from public.item_relationships {user_filter}",
                params,
            )
            return cursor.fetchone()[0]
