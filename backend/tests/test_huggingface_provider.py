"""No-network tests for Hugging Face adapter and offline router fallback."""

import json
import unittest
from unittest.mock import Mock, patch

from backend.intelligence import ModelRouter
from backend.intelligence.huggingface import ENDPOINT, HuggingFaceProvider

MODEL = "example-org/example-model"
TOKEN = "hf_synthetic_not_real"


class HuggingFaceAdapterTests(unittest.TestCase):
    def setUp(self):
        self.provider = HuggingFaceProvider(model=MODEL, token=TOKEN)
        self.item = {
            "source_type": "gmail", "title": "Portfolio website kickoff",
            "sender": "private-person@example.com", "participants": ["person@example.com"],
            "extracted_text": "Please review the wireframe.",
            "occurred_at": "2026-10-16T12:00:00Z",
            "source_url": "https://secret.example/private", "secret": "DO_NOT_SEND",
        }
        self.named = {"items": [self.item]}

    @patch("backend.intelligence.huggingface.requests.post")
    def test_disabled_by_default_is_offline_and_never_calls_network(self, post):
        r = ModelRouter(self.provider).run("project_naming", {**self.named, "remote_approved": True})
        self.assertEqual(r.provider, "offline")
        self.assertTrue(r.fallback_used)
        post.assert_not_called()

    @patch("backend.intelligence.huggingface.requests.post")
    def test_enabled_without_item_approval_is_offline(self, post):
        self.provider.enabled = True
        r = ModelRouter(self.provider).run("project_naming", self.named)
        self.assertEqual(r.provider, "offline")
        post.assert_not_called()

    @patch("backend.intelligence.huggingface.requests.post")
    def test_missing_token_is_offline(self, post):
        provider = HuggingFaceProvider(model=MODEL, enabled=True)
        r = ModelRouter(provider).run("project_naming", {**self.named, "remote_approved": True})
        self.assertEqual(r.provider, "offline")
        post.assert_not_called()

    def test_rejects_insecure_or_url_like_model_names(self):
        for bad in ("", "https://evil.example/model", "just-a-name", "../../etc/passwd", "/model"):
            with self.subTest(model=bad), self.assertRaises(ValueError):
                HuggingFaceProvider(model=bad)

    def test_preview_excludes_metadata_and_credentials_without_io(self):
        preview = self.provider.preview_request("event_extraction", {"item": self.item})
        serial = json.dumps(preview)
        self.assertIn("Please review the wireframe", serial)
        for private in ("private-person@example.com", "person@example.com", "DO_NOT_SEND", TOKEN, "secret.example"):
            self.assertNotIn(private, serial)
        self.assertEqual(preview["model"], MODEL)

    def test_preview_caps_body_and_drops_other_fields(self):
        big = {**self.item, "extracted_text": "X" * 5000}
        preview = self.provider.preview_request("event_extraction", {"item": big})
        data = json.loads(preview["messages"][1]["content"])
        self.assertEqual(len(data["item"]["body"]), 1200)
        self.assertNotIn("source_url", data["item"])

    @patch("backend.intelligence.huggingface.requests.post")
    def test_approved_naming_calls_fixed_endpoint_and_router_normalizes(self, post):
        self.provider.enabled = True
        post.return_value = Mock(
            status_code=200, content=b"short response",
            **{"json.return_value": {"choices": [{"message": {"content": json.dumps({
                "name": "Portfolio Project", "summary": "A website refresh",
                "symbol": "p", "category": "project", "coherence": 0.83,
            })}}]}}
        )
        r = ModelRouter(self.provider).run("project_naming", {**self.named, "remote_approved": True})
        self.assertEqual(r.provider, "huggingface")
        self.assertFalse(r.fallback_used)
        self.assertEqual(r.data["symbol"], "P")
        args, kwargs = post.call_args
        self.assertEqual(args, (ENDPOINT,))
        self.assertFalse(kwargs["allow_redirects"])
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer " + TOKEN)
        self.assertNotIn("remote_approved", json.dumps(kwargs["json"]))

    @patch("backend.intelligence.huggingface.requests.post")
    def test_provider_http_failure_falls_back_without_sensitive_error(self, post):
        self.provider.enabled = True
        post.return_value = Mock(status_code=429)
        r = ModelRouter(self.provider).run("project_naming", {**self.named, "remote_approved": True})
        self.assertEqual(r.provider, "offline")
        self.assertEqual(r.reason, "primary_failed_validation_or_execution")

    @patch("backend.intelligence.huggingface.requests.post")
    def test_non_json_model_response_falls_back(self, post):
        self.provider.enabled = True
        post.return_value = Mock(status_code=200, content=b"small", **{
            "json.return_value": {"choices": [{"message": {"content": "Not JSON"}}]}
        })
        r = ModelRouter(self.provider).run("project_naming", {**self.named, "remote_approved": True})
        self.assertEqual(r.provider, "offline")

    @patch("backend.intelligence.huggingface.requests.post")
    def test_valid_summary_is_used(self, post):
        self.provider.enabled = True
        post.return_value = Mock(status_code=200, content=b"small", **{
            "json.return_value": {"choices": [{"message": {"content": '{"summary":"Approved wireframe."}'}}]}
        })
        r = ModelRouter(self.provider).run("digest_summary", {
            "project_name": "Website", "events": [{"title": "Approve wireframe", "event_type": "decision"}],
            "remote_approved": True,
        })
        self.assertEqual(r.data["summary"], "Approved wireframe.")
        self.assertFalse(r.fallback_used)

    @patch("backend.intelligence.huggingface.requests.post")
    def test_invalid_extracted_events_fall_back(self, post):
        self.provider.enabled = True
        post.return_value = Mock(status_code=200, content=b"small", **{
            "json.return_value": {"choices": [{"message": {"content": '{"events":["fake"],"actions":[]}'}}]}
        })
        r = ModelRouter(self.provider).run("event_extraction", {"item": self.item, "remote_approved": True})
        self.assertEqual(r.provider, "offline")
        self.assertEqual(r.data["actions"], [])

    @patch("backend.intelligence.huggingface.requests.post")
    def test_oversize_response_falls_back(self, post):
        self.provider.enabled = True
        post.return_value = Mock(status_code=200, content=b"X" * 40001)
        r = ModelRouter(self.provider).run("project_naming", {**self.named, "remote_approved": True})
        self.assertEqual(r.provider, "offline")


if __name__ == "__main__":
    unittest.main()
