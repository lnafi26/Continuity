"""Database access for Stage 6 (extract events & actions).

Reads the items that are linked to a project but not yet extracted, inserts the
extracted project_events / project_actions, and marks the item extracted. AI
rows carry user_edited=false so a re-run can clear them without touching rows a
user has edited.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import psycopg


@dataclass
class ExtractItem:
    id: str
    project_id: str
    source_type: str
    title: str
    sender: str | None
    participants: list[str] = field(default_factory=list)
    occurred_at: object = None
    extracted_text: str | None = None
    color: str = "#4263eb"


def fetch_queue(database_url: str, user_id: str, limit: int = 500) -> list[ExtractItem]:
    """Linked items not yet extracted (one row per item, highest-confidence link)."""
    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                select distinct on (si.id)
                    si.id, l.project_id, si.source_type, si.title, si.sender,
                    si.participants, si.occurred_at, si.extracted_text, p.color
                from public.source_items si
                join public.project_source_links l on l.source_item_id = si.id
                join public.projects p on p.id = l.project_id
                where si.user_id = %s and si.extracted_at is null
                order by si.id, l.confidence desc nulls last
                limit %s
                """,
                (user_id, limit),
            )
            rows = cursor.fetchall()
    return [
        ExtractItem(
            id=str(r[0]), project_id=str(r[1]), source_type=r[2],
            title=r[3] or "", sender=r[4], participants=r[5] or [],
            occurred_at=r[6], extracted_text=r[7], color=r[8] or "#4263eb",
        )
        for r in rows
    ]


def insert_event(database_url, user_id, project_id, source_item_id, event, color) -> None:
    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                insert into public.project_events
                    (user_id, project_id, source_item_id, event_type, title,
                     body, person, event_date, requires_response, confidence,
                     user_edited, color)
                values (%s, %s, %s, %s, %s, %s, %s, coalesce(%s, now()), %s, %s, false, %s)
                """,
                (user_id, project_id, source_item_id, event["event_type"],
                 event["title"], event["body"], event["person"],
                 event["event_date"], event.get("requires_response"),
                 round(event["confidence"], 4), color),
            )


def insert_action(database_url, user_id, project_id, source_item_id, action, color) -> None:
    # `completed` is kept as a derived legacy alias of `status` (Architecture
    # Stage 6) so anything still reading the old boolean stays correct.
    status = action.get("status") or "not_started"
    completed = status == "completed"
    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                insert into public.project_actions
                    (user_id, project_id, source_item_id, title, assignee,
                     due_date, status, backlog, completed, confidence,
                     user_edited, color)
                values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, false, %s)
                """,
                (user_id, project_id, source_item_id, action["title"],
                 action["assignee"], action["due_date"], status,
                 bool(action.get("backlog", False)), completed,
                 round(action["confidence"], 4), color),
            )


def mark_extracted(database_url: str, item_id: str) -> None:
    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                update public.source_items
                set extracted_at = now(),
                    processing_status = 'processed',
                    updated_at = now()
                where id = %s
                """,
                (item_id,),
            )



class ExtractionWriteConflict(RuntimeError):
    """Pending source has user-edited output requiring manual reconciliation."""


def write_extraction_atomic(
    database_url: str,
    user_id: str,
    project_id: str,
    source_item_id: str,
    *,
    events: list[dict],
    actions: list[dict],
    color: str,
) -> bool:
    """Commit one source's generated rows AND processed marker atomically.

    Returns False if another worker has already extracted this source. A row
    lock serializes concurrent attempts; an exception causes psycopg's connection
    context manager to roll back all statements. No model work is done here.

    This intentionally rejects pending sources with user-edited events/actions
    rather than duplicating or overwriting those edits. A requeued source with
    only unedited AI rows can safely replace previous partial generated output.
    """
    if not isinstance(events, list) or not isinstance(actions, list):
        raise ValueError("Events and actions must be lists.")
    if any(not isinstance(x, dict) for x in events + actions):
        raise ValueError("Events and actions must contain objects.")
    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                select si.extracted_at
                from public.source_items si
                join public.project_source_links l
                  on l.source_item_id = si.id and l.user_id = %s
                where si.id = %s and si.user_id = %s and l.project_id = %s
                for update of si
                """,
                (user_id, source_item_id, user_id, project_id),
            )
            source_row = cursor.fetchone()
            if source_row is None:
                raise ValueError("No authorized source-project link exists.")
            if source_row[0] is not None:
                return False

            cursor.execute(
                """
                select (
                    exists (select 1 from public.project_events
                            where user_id = %s and source_item_id = %s
                              and user_edited = true)
                    or exists (select 1 from public.project_actions
                               where user_id = %s and source_item_id = %s
                                 and user_edited = true)
                )
                """,
                (user_id, source_item_id, user_id, source_item_id),
            )
            edited_row = cursor.fetchone()
            if edited_row is None:
                raise RuntimeError("Unable to check existing corrections.")
            if edited_row[0]:
                raise ExtractionWriteConflict(
                    "Source has user-edited outputs and requires review."
                )

            # Replace any *unedited* partial output left by the former writer
            # or a legitimate requeue. All deletes and inserts roll back together.
            for table in ("project_events", "project_actions"):
                cursor.execute(
                    f"delete from public.{table} "
                    "where user_id = %s and source_item_id = %s "
                    "and user_edited = false",
                    (user_id, source_item_id),
                )

            for ev in events:
                cursor.execute(
                    """
                    insert into public.project_events
                        (user_id, project_id, source_item_id, event_type, title,
                         body, person, event_date, requires_response, confidence,
                         user_edited, color)
                    values (%s, %s, %s, %s, %s, %s, %s,
                            coalesce(%s, now()), %s, %s, false, %s)
                    """,
                    (user_id, project_id, source_item_id, ev["event_type"],
                     ev["title"], ev["body"], ev["person"],
                     ev["event_date"], ev.get("requires_response"),
                     round(ev["confidence"], 4), color),
                )

            for ac in actions:
                status = ac.get("status") or "not_started"
                cursor.execute(
                    """
                    insert into public.project_actions
                        (user_id, project_id, source_item_id, title, assignee,
                         due_date, status, backlog, completed, confidence,
                         user_edited, color)
                    values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, false, %s)
                    """,
                    (user_id, project_id, source_item_id, ac["title"],
                     ac["assignee"], ac["due_date"], status,
                     bool(ac.get("backlog", False)), status == "completed",
                     round(ac["confidence"], 4), color),
                )

            # Only stamp success after EVERY generated row was inserted. The
            # transaction also guards the stamp against independent failure.
            cursor.execute(
                """
                update public.source_items
                set extracted_at = now(), processing_status = 'processed',
                    processing_error = null, updated_at = now()
                where id = %s and user_id = %s and extracted_at is null
                """,
                (source_item_id, user_id),
            )
            if cursor.rowcount != 1:
                raise RuntimeError("Source completion marker was not updated.")
    return True


def reset(database_url: str, user_id: str) -> dict:
    """Delete AI-generated (not user-edited) events/actions and re-queue items."""
    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "delete from public.project_events "
                "where user_id = %s and user_edited = false",
                (user_id,),
            )
            events = cursor.rowcount
            cursor.execute(
                "delete from public.project_actions "
                "where user_id = %s and user_edited = false",
                (user_id,),
            )
            actions = cursor.rowcount
            cursor.execute(
                """
                update public.source_items
                set extracted_at = null
                where user_id = %s
                  and id in (select source_item_id from public.project_source_links
                             where user_id = %s)
                """,
                (user_id, user_id),
            )
            requeued = cursor.rowcount
    return {"events_deleted": events, "actions_deleted": actions, "requeued": requeued}


def status_breakdown(database_url: str, user_id: str) -> dict:
    """Board + response counts for this user -- a quick smoke test after extraction."""
    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                select
                    count(*) filter (where status = 'not_started'),
                    count(*) filter (where status = 'in_progress'),
                    count(*) filter (where status = 'completed'),
                    count(*) filter (where backlog)
                from public.project_actions
                where user_id = %s
                """,
                (user_id,),
            )
            a = cursor.fetchone()
            cursor.execute(
                """
                select
                    count(*) filter (where requires_response is true),
                    count(*) filter (where requires_response is false),
                    count(*) filter (where requires_response is null)
                from public.project_events
                where user_id = %s
                """,
                (user_id,),
            )
            e = cursor.fetchone()
    return {
        "not_started": a[0], "in_progress": a[1], "completed": a[2], "backlog": a[3],
        "requires_response": e[0], "no_response_needed": e[1], "not_yet_classified": e[2],
    }


def progress(database_url: str, user_id: str) -> dict:
    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                select
                    (select count(*) from public.project_events
                       where user_id = %(u)s) as events,
                    (select count(*) from public.project_actions
                       where user_id = %(u)s) as actions,
                    (select count(*) from public.source_items si
                       join public.project_source_links l on l.source_item_id = si.id
                       where si.user_id = %(u)s and si.extracted_at is null) as queued
                """,
                {"u": user_id},
            )
            row = cursor.fetchone()
    return {"events": row[0], "actions": row[1], "queued": row[2]}
