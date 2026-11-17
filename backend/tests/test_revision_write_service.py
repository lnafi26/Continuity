"""Offline revision transaction tests. No SQL or network."""

import copy
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import unittest

from backend.memory.revision_write_service import (
    RevisionConflict,
    UserRevisionIntent,
    append_user_revision,
)

USER = "11111111-1111-4111-8111-111111111111"
OTHER = "22222222-2222-4222-8222-222222222222"
PROJECT = "33333333-3333-4333-8333-333333333333"
ASSERTION = "44444444-4444-4444-8444-444444444444"
SOURCE = "55555555-5555-4555-8555-555555555555"

CREATED = datetime(2026, 11, 1, tzinfo=timezone.utc)
NOW = datetime(2026, 11, 17, tzinfo=timezone.utc)


class FakeTransaction:
    def __init__(self):
        self.assertion = dict(
            id=ASSERTION,
            user_id=USER,
            project_id=PROJECT,
            created_at=CREATED,
        )
        self.head = None
        self.revisions = []
        self.evidence = []
        self.source_owner = USER
        self.fail_evidence = False
        self.calls = []

    @contextmanager
    def transaction(self):
        snapshot = copy.deepcopy(
            (self.head, self.revisions, self.evidence)
        )
        try:
            yield self
        except Exception:
            self.head, self.revisions, self.evidence = snapshot
            raise

    def lock_assertion(self, **scope):
        self.calls.append("lock_assertion")
        return (
            dict(self.assertion)
            if all(
                self.assertion[
                    "id" if k == "assertion_id" else k
                ] == v
                for k, v in scope.items()
            )
            else None
        )

    def latest_revision(self, **scope):
        self.calls.append("latest_revision")
        assert (
            self.calls.index("lock_assertion")
            < self.calls.index("latest_revision")
        )
        return copy.deepcopy(self.head)

    def lock_source_link(self, **scope):
        self.calls.append("lock_source_link")
        if (
            scope["user_id"] != self.source_owner
            or scope["source_item_id"] != SOURCE
        ):
            return None
        return dict(scope)

    def insert_revision(self, row):
        self.calls.append("insert_revision")
        self.revisions.append(copy.deepcopy(row))
        self.head = copy.deepcopy(row)

    def insert_evidence(self, row):
        self.calls.append("insert_evidence")
        if self.fail_evidence:
            raise RuntimeError("Simulated evidence write failure")
        self.evidence.append(copy.deepcopy(row))


def intent(action="propose", head=None, evidence=(), value=None):
    return UserRevisionIntent(
        PROJECT,
        ASSERTION,
        head,
        action,
        {"decision": "Proceed"} if value is None else value,
        NOW,
        evidence,
    )


class RevisionWriteServiceTests(unittest.TestCase):
    def setUp(self):
        self.db = FakeTransaction()

    def apply(self, request, user=USER, clock=lambda: NOW):
        return append_user_revision(
            verified_user_id=user,
            intent=request,
            transaction_factory=self.db.transaction,
            clock=clock,
        )

    def test_initial_proposal_and_sequential_confirmation(self):
        first = self.apply(intent())
        self.assertEqual(
            (first["version_number"], first["review_state"]),
            (1, "proposed"),
        )
        self.assertIsNone(first["confirmed_by"])

        second = self.apply(
            intent("confirm", head=first["id"])
        )
        self.assertEqual(second["version_number"], 2)
        self.assertEqual(
            second["supersedes_revision_id"],
            first["id"],
        )
        self.assertEqual(
            (
                second["actor_type"],
                second["confirmed_by"],
                second["confirmed_at"],
            ),
            ("user", USER, NOW),
        )
        self.assertEqual(len(self.db.revisions), 2)

    def test_stale_head_conflict_does_not_append(self):
        self.apply(intent())
        with self.assertRaises(RevisionConflict):
            self.apply(intent("confirm"))
        self.assertEqual(len(self.db.revisions), 1)

    def test_user_cannot_write_other_users_assertion(self):
        with self.assertRaises(PermissionError):
            self.apply(intent("confirm"), user=OTHER)
        self.assertEqual(self.db.revisions, [])

    def test_link_scoped_before_revision_write(self):
        self.db.source_owner = OTHER
        with self.assertRaises(PermissionError):
            self.apply(
                intent(evidence=((SOURCE, "supports"),))
            )
        self.assertEqual(self.db.revisions, [])

    def test_evidence_failure_rolls_back_all_changes(self):
        self.db.fail_evidence = True
        with self.assertRaises(RuntimeError):
            self.apply(
                intent(evidence=((SOURCE, "context"),))
            )
        self.assertEqual(
            (
                self.db.revisions,
                self.db.evidence,
                self.db.head,
            ),
            ([], [], None),
        )

    def test_evidence_and_revision_share_transaction(self):
        row = self.apply(
            intent(evidence=(
                (SOURCE, "supports"),
                (SOURCE, "context"),
            ))
        )
        self.assertEqual(len(self.db.evidence), 2)
        self.assertTrue(all(
            e["revision_id"] == row["id"]
            for e in self.db.evidence
        ))

    def test_rejects_invalid_or_oversized_values(self):
        for value in (
            {"a": float("nan")},
            {"a": set()},
            {"a": "x" * 20000},
        ):
            with self.assertRaises(ValueError):
                self.apply(intent(value=value))
        self.assertEqual(self.db.revisions, [])

    def test_rejects_duplicate_or_invalid_evidence_roles(self):
        for entries in (
            ((SOURCE, "supports"), (SOURCE, "supports")),
            ((SOURCE, "verified"),),
        ):
            with self.assertRaises(ValueError):
                self.apply(intent(evidence=entries))

    def test_rejects_untrusted_action(self):
        with self.assertRaises(ValueError):
            self.apply(intent(action="system-confirm"))

    def test_rejects_inconsistent_recording_time(self):
        with self.assertRaises(ValueError):
            self.apply(
                intent(),
                clock=lambda: CREATED - timedelta(seconds=1),
            )

    def test_rejects_foreign_revision_head(self):
        self.db.head = dict(
            id=SOURCE,
            user_id=OTHER,
            project_id=PROJECT,
            assertion_id=ASSERTION,
            version_number=1,
            recorded_at=CREATED,
        )
        with self.assertRaises(PermissionError):
            self.apply(intent(head=SOURCE))


if __name__ == "__main__":
    unittest.main()
