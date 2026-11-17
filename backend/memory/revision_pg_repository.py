"""B4.5 PostgreSQL transaction adapter for revision_write_service.

No credentials, connections or automatic execution exist here.
A future trusted API must supply a fresh connection and verified identity.
Not activated until the reviewed migration and privacy policy are approved.
"""

from contextlib import contextmanager
import json


def _record(row, names):
    if row is None:
        return None
    if len(row) != len(names):
        raise ValueError("Unexpected revision database row shape.")

    result = dict(zip(names, row))
    for key in (
        "id", "user_id", "project_id",
        "assertion_id", "source_item_id",
    ):
        if key in result:
            result[key] = str(result[key])
    return result


class RevisionPostgresTransaction:
    """One cursor within one caller-owned transaction."""

    def __init__(self, cursor):
        self._cursor = cursor

    def _select(self, sql, values, columns):
        self._cursor.execute(sql, values)
        return _record(self._cursor.fetchone(), columns)

    def lock_assertion(self, *, user_id, project_id, assertion_id):
        # Every writer must lock this assertion before reading its head.
        return self._select(
            """SELECT id, user_id, project_id, created_at
               FROM public.project_memory_assertions
               WHERE user_id = %s AND project_id = %s AND id = %s
               FOR UPDATE""",
            (user_id, project_id, assertion_id),
            ("id", "user_id", "project_id", "created_at"),
        )

    def latest_revision(self, *, user_id, project_id, assertion_id):
        return self._select(
            """SELECT id, user_id, project_id, assertion_id,
                      version_number, recorded_at
               FROM public.project_memory_revisions
               WHERE user_id = %s AND project_id = %s
                 AND assertion_id = %s
               ORDER BY version_number DESC LIMIT 1""",
            (user_id, project_id, assertion_id),
            (
                "id", "user_id", "project_id", "assertion_id",
                "version_number", "recorded_at",
            ),
        )

    def lock_source_link(self, *, user_id, project_id, source_item_id):
        # Lock linked references, never read private source bodies.
        return self._select(
            """SELECT l.user_id, l.project_id, l.source_item_id
               FROM public.project_source_links AS l
               JOIN public.source_items AS s
                 ON s.id = l.source_item_id
                AND s.user_id = l.user_id
               WHERE l.user_id = %s AND l.project_id = %s
                 AND l.source_item_id = %s
               FOR KEY SHARE OF l, s""",
            (user_id, project_id, source_item_id),
            ("user_id", "project_id", "source_item_id"),
        )

    def insert_revision(self, row):
        self._cursor.execute(
            """INSERT INTO public.project_memory_revisions
                (id, user_id, project_id, assertion_id,
                 version_number, supersedes_revision_id,
                 review_state, actor_type, confirmed_by,
                 confirmed_at, structured_value,
                 recorded_at, effective_at)
               VALUES (%s, %s, %s, %s, %s, %s, %s,
                       %s, %s, %s, %s::jsonb, %s, %s)""",
            (
                row["id"],
                row["user_id"],
                row["project_id"],
                row["assertion_id"],
                row["version_number"],
                row["supersedes_revision_id"],
                row["review_state"],
                row["actor_type"],
                row["confirmed_by"],
                row["confirmed_at"],
                json.dumps(
                    row["structured_value"],
                    allow_nan=False,
                ),
                row["recorded_at"],
                row["effective_at"],
            ),
        )

    def insert_evidence(self, row):
        self._cursor.execute(
            """INSERT INTO public.project_memory_revision_evidence
                (id, user_id, project_id, assertion_id,
                 revision_id, source_item_id,
                 evidence_role, created_at)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
            (
                row["id"],
                row["user_id"],
                row["project_id"],
                row["assertion_id"],
                row["revision_id"],
                row["source_item_id"],
                row["evidence_role"],
                row["created_at"],
            ),
        )


@contextmanager
def revision_transaction(connection_factory):
    """Commit on success; roll back on failure; always close.

    Connection factory must create a fresh non-autocommit session.
    The trusted API remains responsible for authentication.
    """

    if not callable(connection_factory):
        raise TypeError("Trusted connection factory required.")

    connection = connection_factory()

    try:
        if getattr(connection, "autocommit", None) is not False:
            raise ValueError(
                "Revision writes require autocommit=False."
            )

        cursor = connection.cursor()

        try:
            try:
                yield RevisionPostgresTransaction(cursor)
                connection.commit()
            except BaseException:
                connection.rollback()
                raise
        finally:
            cursor.close()
    finally:
        connection.close()
