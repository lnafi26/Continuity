"""Offline transaction contract tests; no database connection."""

import json
import unittest

from datetime import datetime, timezone
from uuid import UUID

from backend.memory.revision_pg_repository import revision_transaction
from backend.memory.revision_write_service import (
    UserRevisionIntent,
    RevisionConflict,
    append_user_revision,
)

USER = "11111111-1111-4111-8111-111111111111"
OTHER = "22222222-2222-4222-8222-222222222222"
PROJECT = "33333333-3333-4333-8333-333333333333"
ASSERTION = "44444444-4444-4444-8444-444444444444"
SOURCE = "55555555-5555-4555-8555-555555555555"

CREATED = datetime(2026, 11, 1, tzinfo=timezone.utc)
NOW = datetime(2026, 11, 17, tzinfo=timezone.utc)


class FakeDatabase:
    def __init__(self):
        self.revisions = []
        self.evidence = []
        self.connections = []
        self.calls = []
        self.fail_evidence = False
        self.autocommit = False

    def connect(self):
        conn = FakeConnection(self)
        self.connections.append(conn)
        return conn


class FakeConnection:
    def __init__(self, db):
        self.db = db
        self.autocommit = db.autocommit
        self.pending_revisions = []
        self.pending_evidence = []
        self.closed = False
        self.rolled_back = False

    def cursor(self):
        return FakeCursor(self)

    def commit(self):
        self.db.revisions.extend(self.pending_revisions)
        self.db.evidence.extend(self.pending_evidence)
        self.db.calls.append("commit")

    def rollback(self):
        self.pending_revisions.clear()
        self.pending_evidence.clear()
        self.rolled_back = True
        self.db.calls.append("rollback")

    def close(self):
        self.closed = True
        self.db.calls.append("close_connection")


class FakeCursor:
    def __init__(self, connection):
        self.conn = connection
        self.next = None

    def execute(self, sql, params):
        assert type(params) is tuple
        assert sql.count("%s") == len(params)
        db = self.conn.db

        if "FROM public.project_memory_assertions" in sql:
            db.calls.append("lock_assertion")
            assert "FOR UPDATE" in sql
            self.next = (
                (
                    UUID(ASSERTION),
                    UUID(USER),
                    UUID(PROJECT),
                    CREATED,
                )
                if params == (USER, PROJECT, ASSERTION)
                else None
            )

        elif "FROM public.project_memory_revisions" in sql:
            db.calls.append("latest_revision")
            assert "ORDER BY version_number DESC LIMIT 1" in sql
            rows = db.revisions
            self.next = (
                (
                    UUID(rows[-1][0]),
                    UUID(rows[-1][1]),
                    UUID(rows[-1][2]),
                    UUID(rows[-1][3]),
                    rows[-1][4],
                    rows[-1][11],
                )
                if rows else None
            )

        elif "FROM public.project_source_links" in sql:
            db.calls.append("lock_source_link")
            assert "FOR KEY SHARE OF l, s" in sql
            self.next = (
                (UUID(USER), UUID(PROJECT), UUID(SOURCE))
                if params == (USER, PROJECT, SOURCE)
                else None
            )

        elif "INSERT INTO public.project_memory_revisions" in sql:
            db.calls.append("insert_revision")
            assert "%s::jsonb" in sql
            assert json.loads(params[10])["decision"] == "Proceed"
            self.conn.pending_revisions.append(params)

        elif "INSERT INTO public.project_memory_revision_evidence" in sql:
            db.calls.append("insert_evidence")
            if db.fail_evidence:
                raise RuntimeError("Simulated evidence write failure")
            self.conn.pending_evidence.append(params)

        else:
            raise AssertionError("Unexpected SQL statement.")

    def fetchone(self):
        return self.next

    def close(self):
        self.conn.db.calls.append("close_cursor")


class RevisionPgRepositoryTests(unittest.TestCase):
    def setUp(self):
        self.db = FakeDatabase()

    def test_scoped_sql_and_transaction_order(self):
        with revision_transaction(self.db.connect) as tx:
            assertion = tx.lock_assertion(
                user_id=USER,
                project_id=PROJECT,
                assertion_id=ASSERTION,
            )
            self.assertEqual(assertion["id"], ASSERTION)

            self.assertIsNone(tx.latest_revision(
                user_id=USER,
                project_id=PROJECT,
                assertion_id=ASSERTION,
            ))

            link = tx.lock_source_link(
                user_id=USER,
                project_id=PROJECT,
                source_item_id=SOURCE,
            )
            self.assertEqual(link["source_item_id"], SOURCE)

            tx.insert_revision(dict(
                id=SOURCE,
                user_id=USER,
                project_id=PROJECT,
                assertion_id=ASSERTION,
                version_number=1,
                supersedes_revision_id=None,
                review_state="confirmed",
                actor_type="user",
                confirmed_by=USER,
                confirmed_at=NOW,
                structured_value={"decision": "Proceed"},
                recorded_at=NOW,
                effective_at=NOW,
            ))

            tx.insert_evidence(dict(
                id=SOURCE,
                user_id=USER,
                project_id=PROJECT,
                assertion_id=ASSERTION,
                revision_id=SOURCE,
                source_item_id=SOURCE,
                evidence_role="supports",
                created_at=NOW,
            ))

        self.assertEqual(len(self.db.revisions), 1)
        self.assertEqual(len(self.db.evidence), 1)

        self.assertEqual(self.db.calls, [
            "lock_assertion",
            "latest_revision",
            "lock_source_link",
            "insert_revision",
            "insert_evidence",
            "commit",
            "close_cursor",
            "close_connection",
        ])

    def test_database_failure_rolls_back_everything(self):
        self.db.fail_evidence = True

        with self.assertRaises(RuntimeError):
            with revision_transaction(self.db.connect) as tx:
                tx.insert_revision(dict(
                    id=SOURCE,
                    user_id=USER,
                    project_id=PROJECT,
                    assertion_id=ASSERTION,
                    version_number=1,
                    supersedes_revision_id=None,
                    review_state="confirmed",
                    actor_type="user",
                    confirmed_by=USER,
                    confirmed_at=NOW,
                    structured_value={"decision": "Proceed"},
                    recorded_at=NOW,
                    effective_at=NOW,
                ))

                tx.insert_evidence(dict(
                    id=SOURCE,
                    user_id=USER,
                    project_id=PROJECT,
                    assertion_id=ASSERTION,
                    revision_id=SOURCE,
                    source_item_id=SOURCE,
                    evidence_role="supports",
                    created_at=NOW,
                ))

        self.assertEqual(self.db.revisions, [])
        self.assertTrue(self.db.connections[0].rolled_back)
        self.assertTrue(self.db.connections[0].closed)

    def test_wrong_owner_cannot_find_assertion(self):
        with revision_transaction(self.db.connect) as tx:
            self.assertIsNone(tx.lock_assertion(
                user_id=OTHER,
                project_id=PROJECT,
                assertion_id=ASSERTION,
            ))

    def _apply(self, action="propose", expected=None, evidence=False):
        return append_user_revision(
            verified_user_id=USER,
            intent=UserRevisionIntent(
                project_id=PROJECT,
                assertion_id=ASSERTION,
                expected_head_id=expected,
                action=action,
                structured_value={"decision": "Proceed"},
                effective_at=NOW,
                evidence=((SOURCE, "supports"),) if evidence else (),
            ),
            transaction_factory=lambda: revision_transaction(
                self.db.connect
            ),
            clock=lambda: NOW,
        )

    def test_service_creates_ordered_revisions(self):
        first = self._apply()
        second = self._apply(
            "confirm",
            first["id"],
            evidence=True,
        )

        self.assertEqual(
            (first["version_number"], second["version_number"]),
            (1, 2),
        )
        self.assertEqual(
            second["supersedes_revision_id"],
            first["id"],
        )
        self.assertEqual(second["confirmed_by"], USER)
        self.assertEqual(len(self.db.revisions), 2)
        self.assertEqual(len(self.db.evidence), 1)
        self.assertTrue(all(
            conn.closed for conn in self.db.connections
        ))

    def test_stale_revision_rejected_and_rolled_back(self):
        self._apply()

        with self.assertRaises(RevisionConflict):
            self._apply("confirm", None)

        self.assertEqual(len(self.db.revisions), 1)
        self.assertTrue(self.db.connections[-1].rolled_back)

    def test_evidence_failure_rolls_back_user_action(self):
        self.db.fail_evidence = True

        with self.assertRaises(RuntimeError):
            self._apply(evidence=True)

        self.assertEqual(self.db.revisions, [])
        self.assertEqual(self.db.evidence, [])
        self.assertTrue(self.db.connections[-1].rolled_back)

    def test_refuses_autocommit_connections(self):
        self.db.autocommit = True

        with self.assertRaises(ValueError):
            with revision_transaction(self.db.connect):
                pass

        self.assertTrue(self.db.connections[0].closed)


if __name__ == "__main__":
    unittest.main()
