"""No-network regression tests for the private staging Space bridge."""
import json
import unittest
from unittest.mock import Mock, patch

from backend.intelligence import ModelRouter
from backend.intelligence.space_staging import STAGING_ENDPOINT, StagingSpaceProvider

HF_TOKEN = "hf_fake_test_read_token"
SERVICE_TOKEN = "synthetic-test-secret-0123456789abcdefghijklmnopqrstuvwxyz"
ITEM = {
    "title": "Mars Rover Mission Dashboard",
    "excerpt": "Fictional mission planning and telemetry charts",
    "sender": "private@example.com",
    "secret": "DO_NOT_SEND",
}
NAMING = {"items": [ITEM], "remote_approved": True, "synthetic_test": True}


def provider(**kwargs):
    return StagingSpaceProvider(
        hf_access_token=HF_TOKEN, service_token=SERVICE_TOKEN, **kwargs
    )


def response(task="project_naming", data=None):
    if data is None:
        data = {
            "name": "Mars Rover Mission Dashboard", "symbol": "rover-dashboard",
            "category": "project", "coherence": 1.0,
            "summary": "A fictional rover telemetry dashboard.",
        }
    return Mock(status_code=200, content=b"small JSON", **{
        "json.return_value": {
            "ok": True, "environment": "staging", "provider": "huggingface",
            "task": task, "result": data,
        }
    })


class StagingSpaceProviderTests(unittest.TestCase):
    @patch("backend.intelligence.space_staging.requests.post")
    def test_default_is_disabled_and_offline(self, post):
        result = ModelRouter(provider()).run("project_naming", NAMING)
        self.assertEqual(result.provider, "offline")
        post.assert_not_called()

    @patch("backend.intelligence.space_staging.requests.post")
    def test_approval_required(self, post):
        result = ModelRouter(provider(enabled=True)).run(
            "project_naming", {"items": [ITEM], "synthetic_test": True}
        )
        self.assertTrue(result.fallback_used)
        post.assert_not_called()

    @patch("backend.intelligence.space_staging.requests.post")
    def test_synthetic_flag_required(self, post):
        result = ModelRouter(provider(enabled=True)).run(
            "project_naming", {"items": [ITEM], "remote_approved": True}
        )
        self.assertTrue(result.fallback_used)
        post.assert_not_called()

    @patch("backend.intelligence.space_staging.requests.post")
    def test_private_space_token_required(self, post):
        p = StagingSpaceProvider(service_token=SERVICE_TOKEN, enabled=True)
        self.assertTrue(ModelRouter(p).run("project_naming", NAMING).fallback_used)
        post.assert_not_called()

    @patch("backend.intelligence.space_staging.requests.post")
    def test_service_token_required(self, post):
        p = StagingSpaceProvider(hf_access_token=HF_TOKEN, enabled=True)
        self.assertTrue(ModelRouter(p).run("project_naming", NAMING).fallback_used)
        post.assert_not_called()

    def test_preview_strips_metadata_and_tokens(self):
        preview = provider().preview_request("project_naming", NAMING)
        text = json.dumps(preview)
        self.assertIn("Mars Rover", text)
        for forbidden in ("private@example.com", "DO_NOT_SEND", HF_TOKEN, SERVICE_TOKEN):
            self.assertNotIn(forbidden, text)
        self.assertEqual(preview["payload"]["items"][0]["title"], ITEM["title"])

    def test_event_body_uses_gateway_field_name(self):
        preview = provider().preview_request("event_extraction", {"item": {
            "title": "Test", "extracted_text": "A" * 2000, "email": "private@example.com",
        }})
        item = preview["payload"]["item"]
        self.assertEqual(len(item["extracted_text"]), 1200)
        self.assertNotIn("body", item)
        self.assertNotIn("email", item)

    def test_digest_uses_gateway_event_type_field_name(self):
        preview = provider().preview_request("digest_summary", {
            "project_name": "Mars", "events": [{"event_type": "decision", "title": "Approved"}]
        })
        self.assertEqual(preview["payload"]["events"][0]["event_type"], "decision")
        self.assertNotIn("type", preview["payload"]["events"][0])

    @patch("backend.intelligence.space_staging.requests.post")
    def test_realistic_response_normalized_by_router(self, post):
        post.return_value = response()
        result = ModelRouter(provider(enabled=True)).run("project_naming", NAMING)
        self.assertFalse(result.fallback_used)
        self.assertEqual(result.provider, "huggingface-space-staging")
        self.assertEqual(result.data["symbol"], "R")
        self.assertEqual(result.data["name"], "Mars Rover Mission Dashboard")
        args, kwargs = post.call_args
        self.assertEqual(args, (STAGING_ENDPOINT,))
        self.assertFalse(kwargs["allow_redirects"])
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer " + HF_TOKEN)
        self.assertEqual(kwargs["headers"]["X-Continuity-Service-Token"], SERVICE_TOKEN)
        self.assertEqual(set(kwargs["json"]), {"task", "payload", "remote_approved", "synthetic_test"})

    @patch("backend.intelligence.space_staging.requests.post")
    def test_http_failure_falls_back_offline(self, post):
        post.return_value = Mock(status_code=429, content=b"")
        result = ModelRouter(provider(enabled=True)).run("project_naming", NAMING)
        self.assertTrue(result.fallback_used)
        self.assertEqual(result.reason, "primary_failed_validation_or_execution")

    @patch("backend.intelligence.space_staging.requests.post")
    def test_invalid_envelope_falls_back(self, post):
        post.return_value = response(task="digest_summary")
        result = ModelRouter(provider(enabled=True)).run("project_naming", NAMING)
        self.assertTrue(result.fallback_used)

    @patch("backend.intelligence.space_staging.requests.post")
    def test_oversize_request_never_calls_space(self, post):
        big = {"items": [{"title": "X" * 140, "excerpt": "Y" * 900} for _ in range(12)],
               "remote_approved": True, "synthetic_test": True}
        result = ModelRouter(provider(enabled=True)).run("project_naming", big)
        self.assertTrue(result.fallback_used)
        post.assert_not_called()


if __name__ == "__main__":
    unittest.main()
