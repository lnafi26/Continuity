"""Offline and injection tests for the model-independent task router."""

import unittest
from datetime import datetime, timezone
from unittest.mock import Mock

from backend.intelligence import ModelRouter, OfflineProvider


class ModelRouterTests(unittest.TestCase):
    def setUp(self):
        self.router = ModelRouter()
        self.item = {
            "source_type": "gmail",
            "title": "Client website deployment",
            "sender": "client@example.com",
            "occurred_at": datetime(2026, 10, 16, 12, 0, tzinfo=timezone.utc),
            "extracted_text": "Website ready for review.",
        }

    def test_offline_project_naming_reuses_keyword_fallback(self):
        result = self.router.run("project_naming", {"items": [self.item]})
        self.assertEqual(result.provider, "offline")
        self.assertTrue(result.fallback_used)
        self.assertIn("Website", result.data["name"])
        self.assertEqual(result.data["category"], "project")
        self.assertEqual(result.data["coherence"], 0.5)

    def test_offline_event_extraction_preserves_source_date(self):
        result = self.router.run("event_extraction", {"item": self.item})
        self.assertEqual(result.data["actions"], [])
        self.assertEqual(result.data["events"][0]["event_date"], self.item["occurred_at"])
        self.assertIsNone(result.data["events"][0]["requires_response"])

    def test_offline_summary(self):
        result = self.router.run("digest_summary", {
            "project_name": "Website",
            "events": [{"event_type": "meeting", "title": "Review"}],
        })
        self.assertEqual(result.data["summary"], "1 meeting.")

    def test_empty_event_summary(self):
        result = self.router.run("digest_summary", {"project_name": "Website", "events": []})
        self.assertEqual(result.data["summary"], "No recent activity.")

    def test_primary_provider_receives_expected_task_and_payload(self):
        provider = Mock(name="synthetic")
        provider.name = "test-provider"
        provider.infer.return_value = {"name": "Project ABC", "summary": "Test", "category": "project", "coherence": 0.8}
        result = ModelRouter(provider).run("project_naming", {"items": [self.item]})
        self.assertEqual(result.provider, "test-provider")
        self.assertFalse(result.fallback_used)
        self.assertEqual(result.data["name"], "Project ABC")
        provider.infer.assert_called_once()
        self.assertEqual(provider.infer.call_args.args[0], "project_naming")

    def test_provider_failure_uses_offline_fallback(self):
        provider = Mock()
        provider.infer.side_effect = RuntimeError("model offline")
        result = ModelRouter(provider).run("project_naming", {"items": [self.item]})
        self.assertEqual(result.provider, "offline")
        self.assertTrue(result.fallback_used)
        self.assertEqual(result.reason, "primary_failed_validation_or_execution")

    def test_invalid_output_uses_fallback(self):
        provider = Mock()
        provider.infer.return_value = {"name": "", "summary": "not usable"}
        result = ModelRouter(provider).run("project_naming", {"items": [self.item]})
        self.assertTrue(result.fallback_used)

    def test_nonfinite_score_uses_fallback(self):
        provider = Mock()
        provider.infer.return_value = {"name": "ABC", "coherence": float("nan")}
        result = ModelRouter(provider).run("project_naming", {"items": [self.item]})
        self.assertTrue(result.fallback_used)

    def test_valid_primary_output_is_normalized(self):
        provider = Mock()
        provider.name = "mock-provider"
        provider.infer.return_value = {
            "name": "  A Test Project  ", "summary": "Done", "symbol": "q",
            "category": "not-a-category", "coherence": 5,
        }
        result = ModelRouter(provider).run("project_naming", {"items": [self.item]})
        self.assertEqual(result.data["name"], "A Test Project")
        self.assertEqual(result.data["symbol"], "Q")
        self.assertEqual(result.data["category"], "project")
        self.assertEqual(result.data["coherence"], 1)

    def test_primary_summary_is_capped(self):
        provider = Mock()
        provider.name = "mock-provider"
        provider.infer.return_value = {"summary": "a" * 800}
        result = ModelRouter(provider).run("digest_summary", {"project_name": "P", "events": []})
        self.assertEqual(len(result.data["summary"]), 500)

    def test_invalid_event_payload_falls_back(self):
        provider = Mock()
        provider.infer.return_value = {"events": ["oops"], "actions": []}
        result = ModelRouter(provider).run("event_extraction", {"item": self.item})
        self.assertTrue(result.fallback_used)
        self.assertEqual(len(result.data["events"]), 1)

    def test_malformed_input_rejected_before_primary_invocation(self):
        provider = Mock()
        with self.assertRaises(ValueError):
            ModelRouter(provider).run("event_extraction", {"item": "not a dict"})
        provider.infer.assert_not_called()

    def test_unknown_task_rejected(self):
        with self.assertRaises(ValueError):
            self.router.run("arbitrary_task", {})

    def test_offline_provider_has_no_secret_or_network_config(self):
        self.assertEqual(OfflineProvider().name, "offline")
        self.assertIsNone(self.router.primary)


if __name__ == "__main__":
    unittest.main()
