"""Pure, local regressions for source citations and untrusted model extraction."""
import json
import unittest
from datetime import date, datetime, timezone

from backend.intelligence.grounding import review_extraction


class GroundingTests(unittest.TestCase):
    def setUp(self):
        self.source = {
            "source_type": "upload",
            "title": "Fictional Mars Rover Project Update",
            "extracted_text": (
                "Fictional test: On October 16, 2026, the team approved the rover "
                "dashboard wireframe. Alex agreed to prepare an updated telemetry "
                "mockup by October 23, 2026."
            ),
            "occurred_at": datetime(2026, 10, 16, 12, tzinfo=timezone.utc),
        }
        self.output = {
            "events": [{
                "event_type": "note",
                "title": "Rover Dashboard Wireframe Approved",
                "body": "The team approved the rover dashboard wireframe during the project review on October 16, 2026.",
                "person": "Alex",
                "event_date": datetime(2026, 10, 16, 12, tzinfo=timezone.utc),
            }],
            "actions": [{"title": "Prepare Updated Telemetry Mockup", "assignee": "Alex",
                         "due_date": date(2026, 10, 23)}],
        }

    def evaluate(self, output=None, source=None, source_id="fictional-mars-001"):
        return review_extraction(source or self.source, output or self.output, source_id=source_id)

    def test_live_anomaly_classification_is_flagged(self):
        item = self.evaluate().items[0]
        self.assertIn("possible_decision_misclassification", item.flags)
        self.assertEqual(item.verification_state, "needs_review")

    def test_invented_review_setting_is_not_promoted(self):
        item = self.evaluate().items[0]
        self.assertIn("paraphrase_has_new_terms", item.flags)
        self.assertIn("missing_evidence_quote", item.flags)
        self.assertIsNone(item.anchor)

    def test_decision_person_not_assumed_from_action_owner(self):
        item = self.evaluate().items[0]
        self.assertIn("person_role_not_verified", item.flags)

    def test_missing_action_quote_does_not_confirm_due_date(self):
        item = self.evaluate().items[1]
        self.assertIn("due_date_needs_evidence_review", item.flags)

    def test_exact_quote_creates_precise_offsets(self):
        quote = "the team approved the rover dashboard wireframe"
        output = {"events": [{"title": "Approved", "event_type": "decision", "evidence_quote": quote}], "actions": []}
        item = self.evaluate(output).items[0]
        self.assertEqual(item.evidence_state, "anchored")
        self.assertEqual(item.anchor.field, "extracted_text")
        self.assertEqual(self.source["extracted_text"][item.anchor.start:item.anchor.end], quote)
        self.assertEqual(item.anchor.source_id, "fictional-mars-001")

    def test_anchor_does_not_mean_verified(self):
        output = {"events": [{"title": "Approved", "event_type": "decision",
                              "body": "Invented deployment", "evidence_quote":
                              "the team approved the rover dashboard wireframe"}], "actions": []}
        record = self.evaluate(output).items[0]
        self.assertEqual(record.evidence_state, "anchored")
        self.assertEqual(record.verification_state, "needs_review")
        self.assertIn("paraphrase_has_new_terms", record.flags)

    def test_fabricated_quote_is_not_anchored(self):
        output = {"events": [{"title": "Launched", "event_type": "decision",
                              "evidence_quote": "Project successfully deployed to production"}], "actions": []}
        record = self.evaluate(output).items[0]
        self.assertEqual(record.evidence_state, "unanchored")
        self.assertIn("unmatched_evidence_quote", record.flags)

    def test_short_generic_quote_is_not_evidence(self):
        output = {"events": [{"title": "Approved", "evidence_quote": "Alex"}], "actions": []}
        self.assertIsNone(self.evaluate(output).items[0].anchor)

    def test_action_due_date_quoted(self):
        quote = "Alex agreed to prepare an updated telemetry mockup by October 23, 2026."
        output = {"events": [], "actions": [{"title": "Prepare mockup", "due_date": date(2026, 10, 23),
                    "assignee": "Alex", "evidence_quote": quote}]}
        record = self.evaluate(output).items[0]
        self.assertEqual(record.evidence_state, "anchored")
        self.assertNotIn("due_date_needs_evidence_review", record.flags)
        self.assertIn("assignee_role_not_verified", record.flags)

    def test_due_date_not_in_quote_is_flagged(self):
        output = {"events": [], "actions": [{"title": "Prepare mockup", "due_date": "2026-11-23",
                    "evidence_quote": "Alex agreed to prepare an updated telemetry mockup by October 23, 2026."}]}
        record = self.evaluate(output).items[0]
        self.assertIn("due_date_needs_evidence_review", record.flags)

    def test_title_anchor_uses_correct_field(self):
        source = {**self.source, "title": "Fictional Mars Rover Project Update"}
        output = {"events": [{"title": "Update", "evidence_quote": "Fictional Mars Rover Project Update"}], "actions": []}
        self.assertEqual(self.evaluate(output, source).items[0].anchor.field, "title")

    def test_no_network_or_mutation(self):
        before = repr(self.output), repr(self.source)
        self.evaluate()
        self.assertEqual((repr(self.output), repr(self.source)), before)

    def test_json_serializable_for_later_agent_api(self):
        result = self.evaluate().to_dict()
        self.assertEqual(result["assessment"], "preliminary_not_factual_verification")
        self.assertEqual(result["source_id"], "fictional-mars-001")
        self.assertEqual(len(result["items"]), 2)
        json.dumps(result)

    def test_source_id_required(self):
        with self.assertRaises(ValueError):
            self.evaluate(source_id="")

    def test_bad_extraction_shape_rejected(self):
        with self.assertRaises(ValueError):
            self.evaluate({"events": "not-list"})

    def test_no_date_in_source_does_not_invent_one(self):
        source = {"source_type": "upload", "title": "Test", "extracted_text": "Hello"}
        report = self.evaluate({"events": [], "actions": []}, source)
        self.assertIsNone(report.reported_at)


if __name__ == "__main__":
    unittest.main()
