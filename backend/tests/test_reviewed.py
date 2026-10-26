"""F1B: quote transport, mapping safety, and no-network review orchestration."""
import unittest
from datetime import date, datetime, timezone
from unittest.mock import Mock, patch

from backend.intelligence import ModelRouter
from backend.intelligence.reviewed import extract_with_review


BODY = (
    "Fictional test: On October 16, 2026, the team approved the rover "
    "dashboard wireframe. Alex agreed to prepare an updated telemetry "
    "mockup by October 23, 2026."
)
EVENT_QUOTE = "the team approved the rover dashboard wireframe"
ACTION_QUOTE = "Alex agreed to prepare an updated telemetry mockup by October 23, 2026."
ITEM = {"source_type": "upload", "title": "Mars Demo", "extracted_text": BODY,
        "occurred_at": datetime(2026, 10, 16, 12, tzinfo=timezone.utc)}


def provider():
    p = Mock()
    p.name = "synthetic-fake-provider"
    p.infer.return_value = {
        "events": [{"event_type": "decision", "title": "Wireframe approved",
                    "body": "The team approved the rover dashboard wireframe.",
                    "person": "", "event_date": "2026-10-16",
                    "evidence_quote": EVENT_QUOTE}],
        "actions": [{"title": "Prepare updated telemetry mockup", "assignee": "Alex",
                     "due_date": "2026-10-23", "status": "not_started",
                     "evidence_quote": ACTION_QUOTE}],
    }
    return p


class F1BTests(unittest.TestCase):
    @staticmethod
    def normalize_that_drops_extra_fields(value, item):
        # Simulates the current extractor._normalize() intentionally dropping
        # anything outside the fixed schema (including evidence_quote).
        return {
            "events": [{k: v for k, v in x.items() if k != "evidence_quote"}
                       for x in value["events"][:4]],
            "actions": [{k: v for k, v in x.items() if k != "evidence_quote"}
                        for x in value["actions"][:4] if str(x.get("title", "")).strip()],
        }

    def run_mock(self, p):
        with patch("backend.intelligence.router.extractor._normalize", self.normalize_that_drops_extra_fields):
            return extract_with_review(ModelRouter(p), ITEM, source_id="synthetic-001",
                                       remote_approved=True, synthetic_test=True)

    def test_quotes_survive_normalization(self):
        result = self.run_mock(provider())
        self.assertEqual(result.inference.data["events"][0]["evidence_quote"], EVENT_QUOTE)
        self.assertEqual(result.inference.data["actions"][0]["evidence_quote"], ACTION_QUOTE)

    def test_report_anchors_both_excerpts_with_exact_spans(self):
        result = self.run_mock(provider())
        self.assertEqual([i.evidence_state for i in result.review.items], ["anchored", "anchored"])
        for record in result.review.items:
            self.assertEqual(BODY[record.anchor.start:record.anchor.end], record.anchor.quote)
            self.assertEqual(record.verification_state, "needs_review")

    def test_report_never_verifies_claims_from_matching_quotes(self):
        result = self.run_mock(provider())
        self.assertTrue(all(x.verification_state == "needs_review" for x in result.review.items))

    def test_disabled_by_default_uses_offline_even_with_custom_primary(self):
        p = provider()
        result = extract_with_review(ModelRouter(p), ITEM, source_id="synthetic-001")
        p.infer.assert_not_called()
        self.assertEqual(result.inference.provider, "offline")
        self.assertTrue(result.inference.fallback_used)

    def test_approved_payload_does_not_expose_arbitrary_metadata(self):
        p = provider()
        item = {**ITEM, "sender": "private@example.com", "user_id": "private-id",
                "api_key": "do-not-transmit"}
        with patch("backend.intelligence.router.extractor._normalize", self.normalize_that_drops_extra_fields):
            extract_with_review(ModelRouter(p), item, source_id="synthetic-001",
                                remote_approved=True, synthetic_test=True)
        passed_item = p.infer.call_args.args[1]["item"]
        self.assertEqual(set(passed_item), {"source_type", "title", "occurred_at", "extracted_text"})
        self.assertNotIn("sender", passed_item)

    def test_only_one_flag_is_not_enough(self):
        for flags in ({"remote_approved": True}, {"synthetic_test": True}):
            with self.subTest(flags=flags):
                p = provider()
                result = extract_with_review(ModelRouter(p), ITEM,
                                             source_id="synthetic-001", **flags)
                p.infer.assert_not_called()
                self.assertEqual(result.inference.provider, "offline")

    def test_invalid_source_id_rejected_before_inference(self):
        p = provider()
        with self.assertRaises(ValueError):
            extract_with_review(ModelRouter(p), ITEM, source_id=" ",
                                remote_approved=True, synthetic_test=True)
        p.infer.assert_not_called()

    def test_invalid_source_text_rejected_before_inference(self):
        p = provider()
        with self.assertRaises(ValueError):
            extract_with_review(ModelRouter(p), {**ITEM, "extracted_text": []},
                                source_id="synthetic-001", remote_approved=True,
                                synthetic_test=True)
        p.infer.assert_not_called()

    def test_missing_quote_stays_unanchored(self):
        p = provider()
        for item in p.infer.return_value["events"]:
            item.pop("evidence_quote")
        result = self.run_mock(p)
        self.assertEqual(result.review.items[0].evidence_state, "unanchored")
        self.assertIn("missing_evidence_quote", result.review.items[0].flags)

    def test_fabricated_quote_not_anchored(self):
        p = provider()
        p.infer.return_value["events"][0]["evidence_quote"] = "fictional approval during a project review"
        result = self.run_mock(p)
        self.assertEqual(result.review.items[0].evidence_state, "unanchored")
        self.assertIn("unmatched_evidence_quote", result.review.items[0].flags)

    def test_non_string_quote_not_carried(self):
        p = provider()
        p.infer.return_value["events"][0]["evidence_quote"] = 42
        result = self.run_mock(p)
        self.assertNotIn("evidence_quote", result.inference.data["events"][0])

    def test_mismatched_normalized_order_cannot_steal_quote(self):
        p = provider()
        def wrongly_reordered(value, _item):
            events = [{k: v for k, v in x.items() if k != "evidence_quote"}
                      for x in value["events"]]
            events[0]["title"] = "Different event"
            return {"events": events, "actions": []}
        with patch("backend.intelligence.router.extractor._normalize", wrongly_reordered):
            result = ModelRouter(p).run("event_extraction", {"item": ITEM})
        self.assertNotIn("evidence_quote", result.data["events"][0])

    def test_too_long_quote_not_carried(self):
        p = provider()
        p.infer.return_value["events"][0]["evidence_quote"] = "a " * 300
        result = self.run_mock(p)
        self.assertNotIn("evidence_quote", result.inference.data["events"][0])

    def test_filtered_action_does_not_steal_quote(self):
        p = provider()
        p.infer.return_value["actions"].insert(0, {"title": "  ", "evidence_quote": EVENT_QUOTE})
        result = self.run_mock(p)
        self.assertEqual(result.inference.data["actions"][0]["evidence_quote"], ACTION_QUOTE)

    def test_unsupported_body_remains_needs_review_even_with_anchor(self):
        p = provider()
        p.infer.return_value["events"][0]["body"] = "Invented production deployment"
        result = self.run_mock(p)
        self.assertIn("paraphrase_has_new_terms", result.review.items[0].flags)
        self.assertEqual(result.review.items[0].verification_state, "needs_review")

    def test_fallback_does_not_invent_evidence_quotes(self):
        p = provider()
        p.infer.side_effect = RuntimeError("synthetic failure")
        result = self.run_mock(p)
        self.assertEqual(result.inference.provider, "offline")
        self.assertTrue(result.inference.fallback_used)
        self.assertIsNone(result.review.items[0].anchor)


if __name__ == "__main__":
    unittest.main()
