"""Synthetic-only persisted-row-shape validation; no DB or network."""
import copy
import unittest

from backend.memory.revision_row_adapter import project_synthetic_rows

USER = "11111111-1111-4111-8111-111111111111"
OTHER = "22222222-2222-4222-8222-222222222222"
PROJECT = "33333333-3333-4333-8333-333333333333"
OTHER_PROJECT = "44444444-4444-4444-8444-444444444444"
ASSERTION = "55555555-5555-4555-8555-555555555555"
SOURCES = (
    "66666666-6666-4666-8666-666666666666",
    "77777777-7777-4777-8777-777777777777",
)


def fixture():
    assertion = dict(
        id=ASSERTION, user_id=USER, project_id=PROJECT,
        created_at="2026-10-29T09:00:00Z",
    )
    versions = (
        ("confirmed", "user", "2026-10-29T10:00:00Z", "Original"),
        ("proposed", "agent", "2026-10-30T10:00:00Z", "Proposal"),
        ("confirmed", "user", "2026-10-31T10:00:00Z", "Correction"),
    )
    revisions = []
    for i, (state, actor, when, content) in enumerate(versions, 1):
        revisions.append(dict(
            id=f"revision-{i}", user_id=USER, project_id=PROJECT,
            assertion_id=ASSERTION, version_number=i,
            supersedes_revision_id=f"revision-{i-1}" if i > 1 else None,
            review_state=state, actor_type=actor,
            confirmed_by=USER if state == "confirmed" else None,
            confirmed_at=when if state == "confirmed" else None,
            structured_value={"decision": content},
            recorded_at=when, effective_at=when,
        ))
    evidence = [dict(
        user_id=USER, project_id=PROJECT, assertion_id=ASSERTION,
        revision_id="revision-1", source_item_id=SOURCES[0],
        evidence_role="supports", created_at="2026-10-29T11:00:00Z",
    ), dict(
        user_id=USER, project_id=PROJECT, assertion_id=ASSERTION,
        revision_id="revision-3", source_item_id=SOURCES[1],
        evidence_role="contradicts", created_at="2026-10-31T11:00:00Z",
    )]
    links = [dict(user_id=USER, project_id=PROJECT, source_item_id=s)
             for s in SOURCES]
    return assertion, revisions, evidence, links


def snapshot(assertion, revisions, evidence, links, *, at="2026-11-01T00:00:00Z"):
    return project_synthetic_rows(
        assertion, revisions, evidence, links,
        authenticated_user_id=USER, project_id=PROJECT, as_of=at,
    )


class MemoryRevisionRowAdapterTests(unittest.TestCase):
    def test_projects_database_shaped_revisions(self):
        projection = snapshot(*fixture())
        self.assertEqual(projection["kind"], "synthetic_revision_projection")
        self.assertIs(projection["persisted"], False)
        self.assertEqual(projection["current_confirmed"]["id"], "revision-3")
        self.assertEqual(projection["visible_revisions"][0]["derived_state"], "superseded")
        self.assertTrue(projection["has_current_contradictory_evidence"])
        self.assertTrue(all(e["evidence_verification"] == "not_verified"
                            for e in projection["evidence"]))

    def test_pending_proposal_cannot_override_confirmation(self):
        assertion, revisions, evidence, links = fixture()
        result = snapshot(assertion, revisions[:2], evidence[:1], links,
                          at="2026-10-30T12:00:00Z")
        self.assertEqual(result["current_confirmed"]["id"], "revision-1")
        self.assertEqual(result["open_review_revision_ids"], ["revision-2"])

    def test_rejects_foreign_assertion(self):
        assertion, revisions, evidence, links = fixture()
        assertion["user_id"] = OTHER
        with self.assertRaises(PermissionError):
            snapshot(assertion, revisions, evidence, links)

    def test_rejects_foreign_project(self):
        assertion, revisions, evidence, links = fixture()
        assertion["project_id"] = OTHER_PROJECT
        with self.assertRaises(PermissionError):
            snapshot(assertion, revisions, evidence, links)

    def test_rejects_foreign_revision(self):
        assertion, revisions, evidence, links = fixture()
        revisions[0]["user_id"] = OTHER
        with self.assertRaises(PermissionError):
            snapshot(assertion, revisions, evidence, links)

    def test_rejects_revision_from_another_assertion(self):
        assertion, revisions, evidence, links = fixture()
        revisions[0]["assertion_id"] = "another-assertion"
        with self.assertRaises(PermissionError):
            snapshot(assertion, revisions, evidence, links)

    def test_rejects_foreign_evidence(self):
        assertion, revisions, evidence, links = fixture()
        evidence[0]["project_id"] = OTHER_PROJECT
        with self.assertRaises(PermissionError):
            snapshot(assertion, revisions, evidence, links)

    def test_rejects_foreign_source_link(self):
        assertion, revisions, evidence, links = fixture()
        links[0]["user_id"] = OTHER
        with self.assertRaises(PermissionError):
            snapshot(assertion, revisions, evidence, links)

    def test_missing_source_link_rejected(self):
        assertion, revisions, evidence, links = fixture()
        with self.assertRaises(PermissionError):
            snapshot(assertion, revisions, evidence, links[1:])

    def test_mismatched_evidence_assertion_rejected(self):
        assertion, revisions, evidence, links = fixture()
        evidence[0]["assertion_id"] = "another-assertion"
        with self.assertRaises(PermissionError):
            snapshot(assertion, revisions, evidence, links)

    def test_forged_confirmation_actor_rejected(self):
        assertion, revisions, evidence, links = fixture()
        revisions[0]["actor_type"] = "agent"
        with self.assertRaises(PermissionError):
            snapshot(assertion, revisions, evidence, links)

    def test_forged_confirmation_identity_rejected(self):
        assertion, revisions, evidence, links = fixture()
        revisions[0]["confirmed_by"] = OTHER
        with self.assertRaises(PermissionError):
            snapshot(assertion, revisions, evidence, links)

    def test_absent_confirmation_timestamp_rejected(self):
        assertion, revisions, evidence, links = fixture()
        revisions[0]["confirmed_at"] = None
        with self.assertRaises(ValueError):
            snapshot(assertion, revisions, evidence, links)

    def test_unconfirmed_row_cannot_claim_human_confirmation(self):
        assertion, revisions, evidence, links = fixture()
        revisions[1]["confirmed_by"] = USER
        with self.assertRaises(ValueError):
            snapshot(assertion, revisions, evidence, links)

    def test_confirmation_cannot_postdate_recorded_time(self):
        assertion, revisions, evidence, links = fixture()
        revisions[0]["confirmed_at"] = "2026-10-30T11:00:00Z"
        with self.assertRaises(ValueError):
            snapshot(assertion, revisions, evidence, links)

    def test_invalid_predecessor_chain_rejected_by_projector(self):
        assertion, revisions, evidence, links = fixture()
        revisions[2]["supersedes_revision_id"] = "revision-1"
        with self.assertRaises(ValueError):
            snapshot(assertion, revisions, evidence, links)

    def test_orphan_evidence_rejected_by_projector(self):
        assertion, revisions, evidence, links = fixture()
        evidence[0]["revision_id"] = "unknown-revision"
        with self.assertRaises(ValueError):
            snapshot(assertion, revisions, evidence, links)

    def test_original_input_data_is_not_mutated(self):
        args = fixture()
        original = copy.deepcopy(args)
        result = snapshot(*args)
        result["visible_revisions"][0]["structured_value"]["decision"] = "Changed"
        self.assertEqual(args, original)

    def test_snapshot_hides_future_records(self):
        assertion, revisions, evidence, links = fixture()
        result = snapshot(assertion, revisions, evidence, links,
                          at="2026-10-29T12:00:00Z")
        self.assertEqual(len(result["visible_revisions"]), 1)
        self.assertEqual(result["current_confirmed"]["id"], "revision-1")

    def test_revision_row_limit_fails_closed(self):
        assertion, revisions, evidence, links = fixture()
        with self.assertRaises(ValueError):
            snapshot(assertion, revisions * 35, evidence, links)

    def test_evidence_row_limit_fails_closed(self):
        assertion, revisions, evidence, links = fixture()
        with self.assertRaises(ValueError):
            snapshot(assertion, revisions, evidence * 101, links)

    def test_repository_adapter_does_not_change_sql_or_gates(self):
        from pathlib import Path
        root = Path(__file__).resolve().parents[2]
        self.assertTrue((root/'backend/database/deferred/project_memory_revisions.review.sql').is_file())
        self.assertEqual(len(list((root/'supabase/migrations').glob('*.sql'))), 4)
        self.assertNotIn('revision_row_adapter', (root/'scripts/check_supabase_integration_gate.py').read_text())


if __name__ == '__main__':
    unittest.main()
