"""Database access for Stage 7 digest summaries (projects.catchup_summary).

Reads projects that have events newer than their last summary (or no summary
yet), pulls each project's recent events, and writes back the generated
sentence + timestamp. Precomputed here so the dashboard never makes a live LLM
call at page load.
"""

from __future__ import annotations

from dataclasses import dataclass

import psycopg


@dataclass
class ProjectTarget:
    id: str
    name: str


def fetch_projects_needing_summary(database_url: str, user_id: str) -> list[ProjectTarget]:
    """Projects with an event newer than catchup_summary_at (or none yet)."""
    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                select distinct p.id, p.name
                from public.projects p
                join public.project_events e on e.project_id = p.id
                where p.user_id = %(u)s
                  and (p.catchup_summary_at is null
                       or e.event_date > p.catchup_summary_at
                       or e.created_at > p.catchup_summary_at)
                order by p.name
                """,
                {"u": user_id},
            )
            rows = cursor.fetchall()
    return [ProjectTarget(id=str(r[0]), name=r[1]) for r in rows]


def fetch_recent_events(database_url: str, project_id: str, limit: int = 12) -> list[dict]:
    """A project's most recent events (type, title, body, person), newest first."""
    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                select event_type, title, body, person
                from public.project_events
                where project_id = %s
                order by event_date desc
                limit %s
                """,
                (project_id, limit),
            )
            rows = cursor.fetchall()
    return [
        {"event_type": r[0], "title": r[1], "body": r[2] or "", "person": r[3] or ""}
        for r in rows
    ]


def update_summary(database_url: str, project_id: str, summary: str) -> None:
    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                update public.projects
                set catchup_summary = %s,
                    catchup_summary_at = now(),
                    updated_at = now()
                where id = %s
                """,
                (summary, project_id),
            )


def progress(database_url: str, user_id: str) -> dict:
    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                select
                    count(*) filter (where catchup_summary is not null) as summarized,
                    count(*) filter (where catchup_summary is null) as missing
                from public.projects
                where user_id = %s
                """,
                (user_id,),
            )
            row = cursor.fetchone()
    return {"summarized": row[0], "missing": row[1]}
