"""F1C candidate snapshot regressions: all synthetic, local, no DB/network."""
import json
import unittest
from dataclasses import replace
from datetime import datetime, timezone
from unittest.mock import Mock

from backend.intelligence.router import ModelRouter
from backend.intelligence.reviewed import ReviewedExtraction, extract_with_review
from backend.intelligence.evidence_snapshot import build_candidate_snapshot


TEXT = ("Fictional test: On October 16, 2026, the team approved the rover "
        "dashboard wireframe. Alex agreed to prepare an updated telemetry "
        "mockup by October 23, 2026.")
DECISION_QUOTE = "On October 16, 2026, the team approved the rover dashboard wireframe"
ACTION_QUOTE = "Alex agreed to prepare an updated telemetry mockup by October 23, 2026"
OBSERVED = datetime(2026, 10, 16, 22, 0, tzinfo=timezone.utc)


class EvidenceSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.source = {
            "source_type": "upload", "title": "Fictional Mars Rover Project Update",
            "extracted_text": TEXT,
            "occurred_at": datetime(2026, 10, 16, 12, tzinfo=timezone.utc),
            "sender": "excluded@example.com", "secret": "DO_NOT_COPY",
        }
        self.output = {
            "events": [{"event_type": "decision", "title": "Wireframe approved",
                        "body": "The team approved the wireframe.",
                        "person": "the team", "event_date": "2026-10-16",
                        "evidence_quote": DECISION_QUOTE, "requires_response": False,
                        "confidence": 0.95}],
            "actions": [{"title": "Prepare telemetry mockup", "assignee": "Alex",
                         "due_date": "2026-10-23", "status": "not_started",
                         "backlog": False, "confidence": .9,
                         "evidence_quote": ACTION_QUOTE}],
        }
        self.provider = Mock()
        self.provider.name = "synthetic-mock"
        self.provider.infer.return_value = self.output
        self.reviewed = extract_with_review(
            ModelRouter(self.provider), self.source, source_id="fake-source-01",
            remote_approved=True, synthetic_test=True)

    def make(self, reviewed=None, **kw):
        return build_candidate_snapshot(reviewed or self.reviewed,
                                        observed_at=OBSERVED, **kw)

    def test_both_claims_present_and_unverified(self):
        s = self.make()
        self.assertEqual(s["snapshot_type"], "unverified_extraction_candidates")
        self.assertEqual(len(s["events"]), 1)
        self.assertEqual(len(s["actions"]), 1)
        for row in s["events"] + s["actions"]:
            self.assertEqual(row["verification_state"], "needs_review")

    def test_reports_two_exact_reviewed_anchors(self):
        s = self.make()
        for row in s["events"] + s["actions"]:
            a = row["source_anchor"]
            self.assertEqual(a["quote"], TEXT[a["start"]:a["end"]])
            self.assertEqual(a["field"], "extracted_text")
            self.assertEqual(a["source_id"], "fake-source-01")

    def test_source_timestamp_is_not_event_time(self):
        s = self.make()
        self.assertEqual(s["source"]["reported_at"], "2026-10-16T12:00:00+00:00")
        self.assertEqual(s["events"][0]["event_date_claim"], "2026-10-16")
        self.assertFalse(s["events"][0]["event_time_verified"])
        self.assertFalse(s["events"][0]["date_claim_verified"])
        self.assertNotIn("12:00", json.dumps(s["events"]))

    def test_action_not_promoted_to_completed(self):
        a = self.make()["actions"][0]
        self.assertEqual(a["status_claim"], "not_started")
        self.assertFalse(a["status_verified"])
        self.assertFalse(a["due_date_verified"])

    def test_role_claim_retains_review_flag(self):
        s = self.make()
        self.assertIn("person_role_not_verified", s["events"][0]["review_flags"])
        self.assertIn("assignee_role_not_verified", s["actions"][0]["review_flags"])

    def test_does_not_copy_sender_or_secret_metadata(self):
        payload = json.dumps(self.make())
        self.assertNotIn("excluded@example.com", payload)
        self.assertNotIn("DO_NOT_COPY", payload)

    def test_continuity_identity_not_guessed(self):
        self.assertIsNone(self.make()["continuity_id"])
        self.assertEqual(self.make(continuity_id="continuity-alpha")["continuity_id"], "continuity-alpha")

    def test_invalid_continuity_id_refused(self):
        with self.assertRaises(ValueError):
            self.make(continuity_id="  ")

    def test_timezone_aware_snapshot_clock_required(self):
        with self.assertRaises(ValueError):
            build_candidate_snapshot(self.reviewed, observed_at=datetime(2026, 10, 16, 22))

    def test_canonical_json_and_no_datetime_objects(self):
        json.dumps(self.make(), allow_nan=False)

    def test_candidate_ids_are_stable_across_snapshot_times(self):
        a = self.make()
        b = build_candidate_snapshot(self.reviewed,
                                      observed_at=datetime(2026, 10, 17, tzinfo=timezone.utc))
        self.assertEqual(a["events"][0]["candidate_id"], b["events"][0]["candidate_id"])
        self.assertNotEqual(a["observed_at"], b["observed_at"])

    def test_candidate_ids_are_different_for_different_claims(self):
        s = self.make()
        self.assertNotEqual(s["events"][0]["candidate_id"], s["actions"][0]["candidate_id"])

    def test_offline_fallback_does_not_create_fake_anchors(self):
        reviewed = extract_with_review(ModelRouter(), self.source, source_id="fake-source-01")
        s = self.make(reviewed)
        self.assertTrue(s["inference"]["fallback_used"])
        self.assertIsNone(s["events"][0]["source_anchor"])
        self.assertEqual(s["events"][0]["evidence_state"], "unanchored")

    def test_cannot_promote_review_as_verified(self):
        item = replace(self.reviewed.review.items[0], verification_state="verified")
        report = replace(self.reviewed.review, items=(item, self.reviewed.review.items[1]))
        with self.assertRaises(ValueError):
            self.make(ReviewedExtraction(self.reviewed.inference, report))

    def test_cannot_drop_candidate_from_review(self):
        report = replace(self.reviewed.review, items=self.reviewed.review.items[:1])
        with self.assertRaises(ValueError):
            self.make(ReviewedExtraction(self.reviewed.inference, report))

    def test_no_network_calls_during_snapshot(self):
        before = repr(self.reviewed)
        self.make()
        self.assertEqual(before, repr(self.reviewed))
        self.provider.infer.assert_called_once()


if __name__ == "__main__":
    unittest.main()
