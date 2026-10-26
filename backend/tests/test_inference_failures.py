"""R0.1: no-network fault-injection tests for inference failure isolation."""
import unittest
from unittest.mock import Mock, patch

from backend.intelligence.router import InferenceUnavailableError, ModelRouter

ITEM = {
    "title": "Fictional moon dashboard",
    "source_type": "upload",
    "extracted_text": "Design review planned for later.",
    "secret": "SYNTHETIC_PRIVATE_PAYLOAD_DO_NOT_LEAK",
}
PAYLOAD = {"items": [ITEM]}
SECRET = "SYNTHETIC_TOKEN_DO_NOT_LEAK"


class InferenceFailureBoundaryTests(unittest.TestCase):
    def test_timeout_uses_fallback_and_safe_reason(self):
        provider = Mock(name="hosted")
        provider.infer.side_effect = TimeoutError(f"Timeout: {SECRET}")
        result = ModelRouter(provider).run("project_naming", PAYLOAD)
        self.assertTrue(result.fallback_used)
        self.assertEqual(result.provider, "offline")
        self.assertEqual(result.reason, "primary_failed_validation_or_execution")
        self.assertNotIn(SECRET, str(result))
        self.assertNotIn(ITEM["secret"], str(result))

    def test_network_error_falls_back(self):
        provider = Mock(name="hosted")
        provider.infer.side_effect = ConnectionError("network unavailable")
        result = ModelRouter(provider).run("project_naming", PAYLOAD)
        self.assertTrue(result.fallback_used)

    def test_bad_provider_shape_falls_back(self):
        provider = Mock(name="hosted")
        provider.infer.return_value = "unexpected string"
        result = ModelRouter(provider).run("project_naming", PAYLOAD)
        self.assertTrue(result.fallback_used)

    def test_normal_offline_still_works(self):
        result = ModelRouter().run("project_naming", PAYLOAD)
        self.assertEqual(result.provider, "offline")
        self.assertEqual(result.reason, "no_primary_provider")

    @patch("backend.intelligence.router.OfflineProvider.infer")
    def test_offline_failure_is_typed_and_redacted(self, offline):
        offline.side_effect = RuntimeError(f"DB failure: {SECRET}")
        with self.assertRaises(InferenceUnavailableError) as caught:
            ModelRouter().run("project_naming", PAYLOAD)
        error = caught.exception
        self.assertEqual(error.code, "inference_unavailable")
        self.assertEqual(error.task, "project_naming")
        self.assertFalse(error.primary_configured)
        self.assertNotIn(SECRET, str(error))
        self.assertNotIn(ITEM["secret"], str(error.to_dict()))
        self.assertEqual(error.to_dict()["code"], "inference_unavailable")
        self.assertEqual(error.to_dict()["task"], "project_naming")

    @patch("backend.intelligence.router.OfflineProvider.infer")
    def test_double_failure_is_typed_not_success(self, offline):
        offline.side_effect = RuntimeError(f"Offline failure {SECRET}")
        provider = Mock(name="hosted")
        provider.infer.side_effect = TimeoutError("hosted failed")
        with self.assertRaises(InferenceUnavailableError) as caught:
            ModelRouter(provider).run("project_naming", PAYLOAD)
        self.assertTrue(caught.exception.primary_configured)
        self.assertEqual(caught.exception.code, "inference_unavailable")
        provider.infer.assert_called_once()
        offline.assert_called_once()

    @patch("backend.intelligence.router.OfflineProvider.infer")
    def test_offline_malformed_result_has_typed_failure(self, offline):
        offline.return_value = {"name": ""}
        with self.assertRaises(InferenceUnavailableError):
            ModelRouter().run("project_naming", PAYLOAD)

    @patch("backend.intelligence.router.OfflineProvider.infer")
    def test_successful_primary_never_invokes_offline(self, offline):
        provider = Mock(name="hosted")
        provider.name = "synthetic-provider"
        provider.infer.return_value = {"name": "Fictional Mission", "summary": "Synthetic"}
        result = ModelRouter(provider).run("project_naming", PAYLOAD)
        self.assertFalse(result.fallback_used)
        self.assertEqual(result.provider, "synthetic-provider")
        offline.assert_not_called()

    @patch("backend.intelligence.router.OfflineProvider.infer")
    def test_bad_input_rejected_before_either_provider(self, offline):
        provider = Mock(name="hosted")
        with self.assertRaises(ValueError):
            ModelRouter(provider).run("event_extraction", {"item": "bad item"})
        provider.infer.assert_not_called()
        offline.assert_not_called()

    def test_first_request_can_fail_and_next_request_recovers(self):
        provider = Mock(name="hosted")
        provider.name = "synthetic-provider"
        provider.infer.side_effect = [
            TimeoutError("first request failed"),
            {"name": "Recovered", "summary": "Healthy provider"},
        ]
        router = ModelRouter(provider)
        first = router.run("project_naming", PAYLOAD)
        second = router.run("project_naming", PAYLOAD)
        self.assertTrue(first.fallback_used)
        self.assertFalse(second.fallback_used)
        self.assertEqual(second.data["name"], "Recovered")
        self.assertEqual(provider.infer.call_count, 2)


if __name__ == "__main__":
    unittest.main()
