"""Database access for Stage 2 (extract & normalize).

Reads the Stage 1 work queue -- pending rows not yet normalized -- and writes
back the cleaned text, normalized participants/sender, and a `normalized_at`
stamp. Marks a row 'failed' if cleaning raises.
"""

from __future__ import annotations

from dataclasses import dataclass

import psycopg


@dataclass
class PendingItem:
    id: int | str
    source_type: str
    title: str
    extracted_text: str | None
    sender: str | None
    participants: list[str]


def fetch_pending(
    database_url: str,
    user_id: str | None = None,
    limit: int = 200,
) -> list[PendingItem]:
    """Return pending rows that still need normalization (normalized_at IS NULL)."""
    where = ["processing_status = 'pending'", "normalized_at is null"]
    params: list = []
    if user_id:
        where.append("user_id = %s")
        params.append(user_id)
    params.append(limit)
    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                select id, source_type, title, extracted_text, sender, participants
                from public.source_items
                where {" and ".join(where)}
                order by created_at
                limit %s
                """,
                params,
            )
            rows = cursor.fetchall()
    return [
        PendingItem(
            id=row[0],
            source_type=row[1],
            title=row[2] or "",
            extracted_text=row[3],
            sender=row[4],
            participants=row[5] or [],
        )
        for row in rows
    ]


def save_normalized(
    database_url: str,
    item_id: int | str,
    *,
    extracted_text: str,
    text_excerpt: str,
    sender: str | None,
    participants: list[str],
) -> None:
    """Persist cleaned fields and stamp normalized_at."""
    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                update public.source_items
                set extracted_text = %s,
                    text_excerpt = %s,
                    sender = %s,
                    participants = %s,
                    normalized_at = now(),
                    processing_error = null,
                    updated_at = now()
                where id = %s
                """,
                (extracted_text, text_excerpt[:2000], sender, participants, item_id),
            )


def mark_failed(database_url: str, item_id: int | str, error: str) -> None:
    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                update public.source_items
                set processing_status = 'failed',
                    processing_error = %s,
                    updated_at = now()
                where id = %s
                """,
                (error[:500], item_id),
            )


def progress(database_url: str, user_id: str | None = None) -> dict[str, int]:
    """Return {normalized, not_normalized, failed, total} across source items."""
    where = ""
    params: list = []
    if user_id:
        where = "where user_id = %s"
        params.append(user_id)
    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                select
                    count(*) filter (where normalized_at is not null) as normalized,
                    count(*) filter (where normalized_at is null
                                       and processing_status = 'pending') as not_normalized,
                    count(*) filter (where processing_status = 'failed') as failed,
                    count(*) as total
                from public.source_items
                {where}
                """,
                params,
            )
            row = cursor.fetchone()
    return {
        "normalized": row[0],
        "not_normalized": row[1],
        "failed": row[2],
        "total": row[3],
    }
