"""Database access for Stage 5 (group & link to projects).

Reads the included items and their candidate relationships, creates AI projects,
and links items to them via project_source_links. AI projects carry
origin='ai' so a re-run can reset just those (leaving user-created projects
untouched).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import psycopg


@dataclass
class GroupItem:
    id: str
    source_type: str
    title: str
    sender: str | None
    participants: list[str] = field(default_factory=list)
    occurred_at: object = None
    excerpt: str = ""


def fetch_included(database_url: str, user_id: str) -> dict[str, GroupItem]:
    """Included, deduplicated items eligible for grouping, keyed by id."""
    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                select id, source_type, title, sender, participants,
                       occurred_at, text_excerpt
                from public.source_items
                where user_id = %s
                  and include_in_grouping = true
                  and deduped_at is not null
                order by created_at
                """,
                (user_id,),
            )
            rows = cursor.fetchall()
    return {
        str(r[0]): GroupItem(
            id=str(r[0]),
            source_type=r[1],
            title=r[2] or "",
            sender=r[3],
            participants=r[4] or [],
            occurred_at=r[5],
            excerpt=r[6] or "",
        )
        for r in rows
    }


def fetch_edges(
    database_url: str, user_id: str, min_score: float
) -> list[tuple[str, str, float]]:
    """Candidate relationship pairs at or above min_score."""
    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                select source_item_id, related_item_id, combined_score
                from public.item_relationships
                where user_id = %s and combined_score >= %s
                """,
                (user_id, min_score),
            )
            return [(str(a), str(b), float(s)) for a, b, s in cursor.fetchall()]


def fetch_linked_items(database_url: str, user_id: str) -> dict[str, str]:
    """source_item_id -> project_id for every item already linked to any
    project (any match_method) -- what an incremental run must not re-cluster."""
    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                select source_item_id, project_id
                from public.project_source_links
                where user_id = %s
                """,
                (user_id,),
            )
            return {str(item_id): str(project_id) for item_id, project_id in cursor.fetchall()}


def ai_projects_exist(database_url: str, user_id: str) -> int:
    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "select count(*) from public.projects "
                "where user_id = %s and origin = 'ai'",
                (user_id,),
            )
            return cursor.fetchone()[0]


def delete_ai_projects(database_url: str, user_id: str) -> int:
    """Delete AI-created projects (cascades to their project_source_links)."""
    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "delete from public.projects "
                "where user_id = %s and origin = 'ai'",
                (user_id,),
            )
            return cursor.rowcount


def create_project(
    database_url: str,
    user_id: str,
    *,
    name: str,
    symbol: str,
    summary: str,
    color: str,
    soft_color: str,
    members: list[str],
    category: str = "project",
) -> str:
    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                insert into public.projects
                    (user_id, name, symbol, summary, color, soft_color,
                     members, category, origin, updated_at)
                values (%s, %s, %s, %s, %s, %s, %s, %s, 'ai', now())
                returning id
                """,
                (user_id, name, symbol, summary, color, soft_color, members, category),
            )
            return str(cursor.fetchone()[0])


def link_item(
    database_url: str,
    user_id: str,
    project_id: str,
    source_item_id: str,
    *,
    confidence: float,
    explanation: str,
) -> None:
    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                insert into public.project_source_links
                    (user_id, project_id, source_item_id, match_method,
                     confidence, explanation, review_status)
                values (%s, %s, %s, 'ai', %s, %s, 'pending')
                on conflict (project_id, source_item_id) do update
                    set confidence = excluded.confidence,
                        explanation = excluded.explanation,
                        review_status = 'pending'
                """,
                (user_id, project_id, source_item_id, round(confidence, 4), explanation),
            )


def list_ai_projects(database_url: str, user_id: str) -> list[tuple]:
    """AI projects with their linked item counts, for display."""
    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                select p.name, p.symbol, p.summary,
                       count(l.id) as items,
                       round(avg(l.confidence), 3) as avg_conf
                from public.projects p
                left join public.project_source_links l on l.project_id = p.id
                where p.user_id = %s and p.origin = 'ai'
                group by p.id, p.name, p.symbol, p.summary
                order by items desc
                """,
                (user_id,),
            )
            return cursor.fetchall()


def progress(database_url: str, user_id: str) -> dict:
    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                select
                    (select count(*) from public.projects
                       where user_id = %(u)s and origin = 'ai') as ai_projects,
                    (select count(*) from public.project_source_links
                       where user_id = %(u)s and match_method = 'ai') as ai_links,
                    (select count(*) from public.source_items
                       where user_id = %(u)s and include_in_grouping
                         and deduped_at is not null) as included_items
                """,
                {"u": user_id},
            )
            row = cursor.fetchone()
    return {
        "ai_projects": row[0],
        "ai_links": row[1],
        "included_items": row[2],
    }
