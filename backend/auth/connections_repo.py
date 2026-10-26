"""Read/write the non-secret `source_connections` metadata.

Only connection metadata lives here (provider, account, status, sync cursor).
The tokens themselves are handled separately by token_store.py. This module
uses the direct Postgres connection, so it sets `user_id` explicitly rather
than relying on the `auth.uid()` default used by browser clients.
"""

from __future__ import annotations

from dataclasses import dataclass

import psycopg


@dataclass
class Connection:
    id: str
    user_id: str
    provider: str
    provider_account_id: str
    account_email: str
    status: str
    sync_cursor: str | None
    last_synced_at: str | None
    last_error: str | None


def upsert_connection(
    database_url: str,
    *,
    user_id: str,
    provider: str,
    provider_account_id: str,
    account_email: str,
    status: str = "active",
) -> str:
    """Create or update one connection row and return its id.

    Idempotent on (user_id, provider, provider_account_id) -- reconnecting the
    same Google account for the same provider updates the existing row rather
    than creating a duplicate.
    """
    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                insert into public.source_connections
                    (user_id, provider, provider_account_id, account_email,
                     status, last_error, updated_at)
                values (%s, %s, %s, %s, %s, null, now())
                on conflict (user_id, provider, provider_account_id) do update
                    set account_email = excluded.account_email,
                        status = excluded.status,
                        last_error = null,
                        updated_at = now()
                returning id
                """,
                (user_id, provider, provider_account_id, account_email, status),
            )
            return str(cursor.fetchone()[0])


def set_status(
    database_url: str,
    connection_id: str,
    status: str,
    last_error: str | None = None,
) -> None:
    """Update a connection's status lifecycle (active/expired/error/disconnected)."""
    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                update public.source_connections
                set status = %s, last_error = %s, updated_at = now()
                where id = %s
                """,
                (status, last_error, connection_id),
            )


def list_connections(
    database_url: str, user_id: str | None = None
) -> list[Connection]:
    """List connections, optionally scoped to one user."""
    where = "where user_id = %s" if user_id else ""
    params = (user_id,) if user_id else ()
    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                select id, user_id, provider, provider_account_id,
                       account_email, status, sync_cursor, last_synced_at, last_error
                from public.source_connections
                {where}
                order by provider, created_at
                """,
                params,
            )
            rows = cursor.fetchall()
    return [
        Connection(
            id=str(row[0]),
            user_id=str(row[1]),
            provider=row[2],
            provider_account_id=row[3],
            account_email=row[4],
            status=row[5],
            sync_cursor=row[6],
            last_synced_at=str(row[7]) if row[7] else None,
            last_error=row[8],
        )
        for row in rows
    ]


def update_sync_state(
    database_url: str, connection_id: str, sync_cursor: str | None
) -> None:
    """Persist a new sync cursor and stamp last_synced_at after a successful pass.

    Called only once a batch has been safely written to source_items, so the
    cursor never advances past unprocessed items (Architecture Stage 1).
    """
    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                update public.source_connections
                set sync_cursor = %s,
                    last_synced_at = now(),
                    last_error = null,
                    status = 'active',
                    updated_at = now()
                where id = %s
                """,
                (sync_cursor, connection_id),
            )
