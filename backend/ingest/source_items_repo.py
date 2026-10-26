"""Write and inspect `source_items` rows produced by Stage 1 ingestion.

Stage 1 upserts one row per Gmail message / Calendar event with
`processing_status = 'pending'`. Those pending rows are the queue that Stage 2
(extract & normalize) consumes. Idempotency comes from the
`unique (connection_id, external_id)` constraint: re-syncing the same item
updates its row instead of creating a duplicate.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import psycopg


@dataclass
class SourceItem:
    connection_id: str
    user_id: str
    source_type: str          # 'gmail' | 'google_calendar'
    external_id: str
    title: str = ""
    text_excerpt: str = ""
    extracted_text: str | None = None
    sender: str | None = None
    participants: list[str] = field(default_factory=list)
    external_thread_id: str | None = None
    mime_type: str | None = None
    source_url: str | None = None
    occurred_at: Any = None   # timezone-aware datetime or None
    ends_at: Any = None
    location: str | None = None


def upsert_source_item(database_url: str, item: SourceItem) -> bool:
    """Insert or update one source item. Returns True if a new row was inserted.

    On conflict the content fields are refreshed and the row is re-queued
    (`processing_status = 'pending'`) so a changed message/event is reprocessed.
    """
    excerpt = (item.text_excerpt or "")[:2000]
    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                insert into public.source_items
                    (user_id, connection_id, source_type, external_id,
                     external_thread_id, title, text_excerpt, extracted_text,
                     sender, participants, mime_type, source_url,
                     occurred_at, ends_at, location, processing_status, updated_at)
                values
                    (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                     'pending', now())
                on conflict (connection_id, external_id) do update set
                    external_thread_id = excluded.external_thread_id,
                    title = excluded.title,
                    text_excerpt = excluded.text_excerpt,
                    extracted_text = excluded.extracted_text,
                    sender = excluded.sender,
                    participants = excluded.participants,
                    mime_type = excluded.mime_type,
                    source_url = excluded.source_url,
                    occurred_at = excluded.occurred_at,
                    ends_at = excluded.ends_at,
                    location = excluded.location,
                    processing_status = 'pending',
                    processing_error = null,
                    normalized_at = null,
                    content_hash = null,
                    include_in_grouping = true,
                    exclusion_reason = null,
                    deduped_at = null,
                    embedding = null,
                    embedded_at = null,
                    extracted_at = null,
                    updated_at = now()
                returning (xmax = 0) as inserted
                """,
                (
                    item.user_id,
                    item.connection_id,
                    item.source_type,
                    item.external_id,
                    item.external_thread_id,
                    item.title,
                    excerpt,
                    item.extracted_text,
                    item.sender,
                    item.participants,
                    item.mime_type,
                    item.source_url,
                    item.occurred_at,
                    item.ends_at,
                    item.location,
                ),
            )
            return bool(cursor.fetchone()[0])


def counts_by_status(database_url: str, connection_id: str) -> dict[str, int]:
    """Return {processing_status: count} for one connection's source items."""
    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                select processing_status, count(*)
                from public.source_items
                where connection_id = %s
                group by processing_status
                """,
                (connection_id,),
            )
            return {row[0]: row[1] for row in cursor.fetchall()}


def recent_items(
    database_url: str, connection_id: str, limit: int = 5
) -> list[tuple]:
    """Return a few recent items (title, occurred_at, sender) for spot-checking."""
    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                select title, occurred_at, sender
                from public.source_items
                where connection_id = %s
                order by occurred_at desc nulls last
                limit %s
                """,
                (connection_id, limit),
            )
            return cursor.fetchall()
