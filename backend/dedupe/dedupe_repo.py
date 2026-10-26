"""Database access for Stage 3 (clean & deduplicate).

Reads normalized rows not yet deduplicated and writes back the dedupe decision:
content_hash, include_in_grouping, exclusion_reason, and a deduped_at stamp.
"""

from __future__ import annotations

from dataclasses import dataclass

import psycopg


@dataclass
class Stage3Row:
    id: int | str
    connection_id: str
    source_type: str
    external_thread_id: str | None
    title: str
    extracted_text: str | None
    sender: str | None
    occurred_at: object          # tz-aware datetime or None
    created_at: object


def fetch_queue(
    database_url: str,
    user_id: str | None = None,
    limit: int = 1000,
) -> list[Stage3Row]:
    """Return normalized rows still awaiting Stage 3 (deduped_at IS NULL)."""
    where = [
        "processing_status = 'pending'",
        "normalized_at is not null",
        "deduped_at is null",
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
                select id, connection_id, source_type, external_thread_id,
                       title, extracted_text, sender, occurred_at, created_at
                from public.source_items
                where {" and ".join(where)}
                order by created_at
                limit %s
                """,
                params,
            )
            rows = cursor.fetchall()
    return [
        Stage3Row(
            id=row[0],
            connection_id=str(row[1]) if row[1] is not None else None,
            source_type=row[2],
            external_thread_id=row[3],
            title=row[4] or "",
            extracted_text=row[5],
            sender=row[6],
            occurred_at=row[7],
            created_at=row[8],
        )
        for row in rows
    ]


def apply_decision(
    database_url: str,
    item_id: int | str,
    *,
    content_hash: str | None,
    include_in_grouping: bool,
    exclusion_reason: str | None,
) -> None:
    """Persist a Stage 3 decision and stamp deduped_at."""
    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                update public.source_items
                set content_hash = %s,
                    include_in_grouping = %s,
                    exclusion_reason = %s,
                    deduped_at = now(),
                    updated_at = now()
                where id = %s
                """,
                (content_hash, include_in_grouping, exclusion_reason, item_id),
            )


def progress(database_url: str, user_id: str | None = None) -> dict:
    """Return counts: queued, included, and excluded broken down by reason."""
    user_filter = "and user_id = %s" if user_id else ""
    params: list = [user_id] if user_id else []
    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                select
                    count(*) filter (
                        where processing_status = 'pending'
                          and normalized_at is not null
                          and deduped_at is null
                    ) as queued,
                    count(*) filter (
                        where deduped_at is not null and include_in_grouping
                    ) as included,
                    count(*) filter (
                        where deduped_at is not null and exclusion_reason = 'duplicate'
                    ) as duplicate,
                    count(*) filter (
                        where deduped_at is not null and exclusion_reason = 'recurring_instance'
                    ) as recurring_instance,
                    count(*) filter (
                        where deduped_at is not null and exclusion_reason = 'noise'
                    ) as noise,
                    count(*) filter (
                        where deduped_at is not null and exclusion_reason = 'off_topic'
                    ) as off_topic
                from public.source_items
                where true {user_filter}
                """,
                params,
            )
            row = cursor.fetchone()
    return {
        "queued": row[0],
        "included": row[1],
        "duplicate": row[2],
        "recurring_instance": row[3],
        "noise": row[4],
        "off_topic": row[5],
    }
