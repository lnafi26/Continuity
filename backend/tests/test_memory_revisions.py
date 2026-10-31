"""Synthetic B4 versioned memory tests; no database or network."""

import copy
import unittest

from backend.memory.revisions import project_memory_at

USER = "synthetic-user"
PROJECT = "fictional-project"
ASSERTION = "fictional-assertion"


def sample():
    assertion = {
        "id": ASSERTION,
        "user_id": USER,
        "project_id": PROJECT,
        "created_at": "2026-10-29T09:00:00Z",
    }

    revisions = []

    versions = [
        (
            "confirmed", "user",
            "2026-10-29T10:00:00Z",
            "Initial fictional decision",
        ),
        (
            "proposed", "agent",
            "2026-10-30T10:00:00Z",
            "Unreviewed alternative",
        ),
        (
            "confirmed", "user",
            "2026-10-31T10:00:00Z",
            "Corrected fictional decision",
        ),
    ]

    for version, (
        state, actor, recorded, value
    ) in enumerate(versions, 1):

        revisions.append({
            "id": f"revision-{version}",
            "assertion_id": ASSERTION,
            "user_id": USER,
            "project_id": PROJECT,
            "version_number": version,
            "review_state": state,
            "actor_type": actor,
            "recorded_at": recorded,
            "effective_at": recorded,
            "structured_value": {
                "decision": value,
            },
            "supersedes_revision_id": (
                f"revision-{version-1}"
                if version > 1 else None
            ),
        })

    evidence = [
        {
            "user_id": USER,
            "project_id": PROJECT,
            "revision_id": "revision-1",
            "source_item_id": "fictional-source-1",
            "evidence_role": "supports",
            "created_at": "2026-10-29T11:00:00Z",
        },
        {
            "user_id": USER,
            "project_id": PROJECT,
            "revision_id": "revision-3",
            "source_item_id": "fictional-source-2",
            "evidence_role": "contradicts",
            "created_at": "2026-10-31T11:00:00Z",
        },
    ]

    return assertion, revisions, evidence


def snapshot(*args, at="2026-10-31T12:00:00Z"):
    return project_memory_at(*args, as_of=at)


class MemoryRevisionsTests(unittest.TestCase):

    def test_latest_human_confirmation_wins(self):
        result = snapshot(*sample())

        self.assertEqual(
            result["current_confirmed"]["version_number"], 3
        )
        self.assertEqual(
            result["current_confirmed"]["structured_value"][
                "decision"
            ],
            "Corrected fictional decision",
        )
        self.assertFalse(result["persisted"])

    def test_unreviewed_proposal_does_not_override(self):
        result = snapshot(
            *sample(), at="2026-10-30T12:00:00Z"
        )

        self.assertEqual(
            result["current_confirmed"]["version_number"], 1
        )
        self.assertEqual(
            result["open_review_revision_ids"],
            ["revision-2"],
        )

    def test_historical_projection_hides_future(self):
        result = snapshot(
            *sample(), at="2026-10-29T12:00:00Z"
        )

        self.assertEqual(
            len(result["visible_revisions"]), 1
        )
        self.assertEqual(
            len(result["evidence"]), 1
        )
        self.assertFalse(
            result["has_contradictory_evidence"]
        )

    def test_contradictory_evidence_remains_unverified(self):
        result = snapshot(*sample())

        self.assertTrue(
            result["has_contradictory_evidence"]
        )
        self.assertEqual(
            {item["role"] for item in result["evidence"]},
            {"supports", "contradicts"},
        )
        self.assertTrue(all(
            item["evidence_verification"] == "not_verified"
            for item in result["evidence"]
        ))

    def test_cross_project_revision_rejected(self):
        assertion, revisions, evidence = sample()
        revisions[1]["project_id"] = "other-project"

        with self.assertRaises(PermissionError):
            snapshot(assertion, revisions, evidence)

    def test_cross_user_evidence_rejected(self):
        assertion, revisions, evidence = sample()
        evidence[0]["user_id"] = "other-user"

        with self.assertRaises(PermissionError):
            snapshot(assertion, revisions, evidence)

    def test_orphan_evidence_rejected(self):
        assertion, revisions, evidence = sample()
        evidence[0]["revision_id"] = "missing"

        with self.assertRaises(ValueError):
            snapshot(assertion, revisions, evidence)

    def test_agent_cannot_confirm(self):
        assertion, revisions, evidence = sample()
        revisions[2]["actor_type"] = "agent"

        with self.assertRaises(PermissionError):
            snapshot(assertion, revisions, evidence)

    def test_version_chain_required(self):
        assertion, revisions, evidence = sample()
        revisions[2][
            "supersedes_revision_id"
        ] = "revision-1"

        with self.assertRaises(ValueError):
            snapshot(assertion, revisions, evidence)

    def test_timezone_required(self):
        with self.assertRaises(ValueError):
            snapshot(
                *sample(),
                at="2026-10-31T12:00:00",
            )

    def test_does_not_mutate_inputs_or_outputs(self):
        records = sample()
        original = copy.deepcopy(records)

        result = snapshot(*records)
        result["current_confirmed"][
            "structured_value"
        ]["decision"] = "tampered"

        self.assertEqual(records, original)

    def test_rejects_time_before_assertion_creation(self):
        with self.assertRaises(ValueError):
            snapshot(
                *sample(),
                at="2026-10-28T12:00:00Z",
            )

    def test_dispute_does_not_change_confirmation(self):
        assertion, revisions, evidence = sample()
        revisions[2]["review_state"] = "disputed"

        result = snapshot(
            assertion, revisions, evidence
        )

        self.assertEqual(
            result["current_confirmed"]["version_number"], 1
        )
        self.assertEqual(
            result["open_review_revision_ids"],
            ["revision-2", "revision-3"],
        )


    def test_confirmed_supersession_is_derived(self):
        result = snapshot(*sample())

        self.assertEqual(
            [
                row["derived_state"]
                for row in result["visible_revisions"]
            ],
            ["superseded", "proposed", "current"],
        )

        self.assertEqual(
            result["visible_revisions"][0]["review_state"],
            "confirmed",
        )

    def test_future_effective_confirmation_waits(self):
        assertion, revisions, evidence = sample()

        revisions[2]["effective_at"] = (
            "2026-11-02T12:00:00Z"
        )

        before = snapshot(
            assertion, revisions, evidence,
            at="2026-10-31T12:00:00Z",
        )

        self.assertEqual(
            before["current_confirmed"]["version_number"],
            1,
        )
        self.assertEqual(
            before["visible_revisions"][2]["derived_state"],
            "not_yet_effective",
        )

        after = snapshot(
            assertion, revisions, evidence,
            at="2026-11-03T12:00:00Z",
        )

        self.assertEqual(
            after["current_confirmed"]["version_number"],
            3,
        )

    def test_backdated_correction_not_known_early(self):
        assertion, revisions, evidence = sample()

        revisions[2]["effective_at"] = (
            "2026-10-29T10:00:00Z"
        )

        result = snapshot(
            assertion, revisions, evidence,
            at="2026-10-30T12:00:00Z",
        )

        self.assertEqual(
            len(result["visible_revisions"]), 2
        )
        self.assertEqual(
            result["current_confirmed"]["version_number"],
            1,
        )

    def test_old_revision_conflict_not_current_conflict(self):
        assertion, revisions, evidence = sample()

        evidence[1]["revision_id"] = "revision-1"

        result = snapshot(
            assertion, revisions, evidence
        )

        self.assertTrue(
            result["has_contradictory_evidence"]
        )
        self.assertFalse(
            result["has_current_contradictory_evidence"]
        )

    def test_current_revision_conflict_is_visible(self):
        result = snapshot(*sample())

        self.assertTrue(
            result["has_contradictory_evidence"]
        )
        self.assertTrue(
            result["has_current_contradictory_evidence"]
        )

    def test_revision_cannot_predate_assertion(self):
        assertion, revisions, evidence = sample()

        revisions[0]["recorded_at"] = (
            "2026-10-28T10:00:00Z"
        )

        with self.assertRaises(ValueError):
            snapshot(assertion, revisions, evidence)

    def test_evidence_link_cannot_predate_revision(self):
        assertion, revisions, evidence = sample()

        evidence[1]["created_at"] = (
            "2026-10-30T11:00:00Z"
        )

        with self.assertRaises(ValueError):
            snapshot(assertion, revisions, evidence)


if __name__ == "__main__":
    unittest.main()
