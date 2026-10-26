"""Database access for embedding included items (Stage 4, embedding half).

Reads the included, deduplicated rows that still need an embedding, and writes
the 384-dim vector back into source_items.embedding (pgvector).
"""

from __future__ import annotations

from dataclasses import dataclass

import psycopg


@dataclass
class EmbedRow:
    id: str
    title: str
    extracted_text: str | None


def fetch_to_embed(
    database_url: str, user_id: str | None = None, limit: int = 1000
) -> list[EmbedRow]:
    """Included, deduplicated rows without an embedding yet."""
    where = [
        "include_in_grouping = true",
        "deduped_at is not null",
        "embedding is null",
    ]
    params: list = []
    if user_id:
        where.append("user_id = %s")
        params.append(user_id)
    params.append(limit)
    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                select id, title, extracted_text
                from public.source_items
                where {" and ".join(where)}
                order by created_at
                limit %s
                """,
                params,
            )
            rows = cursor.fetchall()
    return [EmbedRow(id=str(r[0]), title=r[1] or "", extracted_text=r[2]) for r in rows]


def _vector_literal(vector: list[float]) -> str:
    """Format a Python list as a pgvector text literal: [0.1,0.2,...]."""
    return "[" + ",".join(f"{x:.7f}" for x in vector) + "]"


def save_embedding(database_url: str, item_id: str, vector: list[float]) -> None:
    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                update public.source_items
                set embedding = %s::extensions.vector,
                    embedded_at = now(),
                    updated_at = now()
                where id = %s
                """,
                (_vector_literal(vector), item_id),
            )
