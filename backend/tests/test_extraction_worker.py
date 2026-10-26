"""R0.4: Offline extraction preparation regression tests.

Synthetic data and mocked database access only.
"""

import unittest
from unittest.mock import patch, MagicMock
from types import SimpleNamespace

from backend.jobs.ledger import JobClaim, JobLeaseLostError
from backend.jobs.extraction_worker import prepare_claimed_extraction
from backend.intelligence.router import InferenceUnavailableError


DB = "synthetic-database"

CLAIM = JobClaim(
    job_id="0c27afd5-7364-4846-a93e-b97f044ac5d0",
    user_id="7fbd542e-4cab-48fa-988d-23f68faac503",
    source_item_id="54715de6-4131-4ed0-8147-c6810996ad57",
    lease_token="21a51e0e-fbf3-41b4-a2d8-8e245c822af1",
    attempt=1,
)

ITEM = {
    "source_type": "upload",
    "title": "Fictional milestone",
    "sender": None,
    "participants": [],
    "occurred_at": None,
    "extracted_text": "The fictional team completed its prototype.",
}

SOURCE = {
    "project_id": "35550b67-9e96-4968-9537-9852ff15436a",
    "color": "#4263eb",
    "item": ITEM,
}


class ExtractionPreparationTests(unittest.TestCase):

    @patch("backend.jobs.extraction_worker.ModelRouter")
    @patch("backend.jobs.extraction_worker.fetch_claimed_source")
    def test_preparation_returns_candidates(self, reader, router_cls):
        reader.return_value = SOURCE
        router_cls.return_value.run.return_value = SimpleNamespace(
            provider="offline",
            data={"events": [{"title": "Test event"}], "actions": []},
        )

        result = prepare_claimed_extraction(DB, CLAIM)

        reader.assert_called_once_with(DB, CLAIM)
        router_cls.assert_called_once_with()
        router_cls.return_value.run.assert_called_once_with(
            "event_extraction", {"item": ITEM}
        )

        self.assertEqual(result["project_id"], SOURCE["project_id"])
        self.assertEqual(result["color"], "#4263eb")
        self.assertEqual(len(result["events"]), 1)
        self.assertEqual(result["actions"], [])

    @patch("backend.jobs.extraction_worker.fetch_claimed_source")
    def test_real_offline_router_generates_event(self, reader):
        reader.return_value = SOURCE

        result = prepare_claimed_extraction(DB, CLAIM)

        self.assertGreaterEqual(len(result["events"]), 1)
        self.assertIsInstance(result["actions"], list)

    @patch("backend.jobs.extraction_worker.ModelRouter")
    @patch("backend.jobs.extraction_worker.fetch_claimed_source")
    def test_invalid_lease_blocks_inference(self, reader, router_cls):
        reader.side_effect = JobLeaseLostError()

        with self.assertRaises(JobLeaseLostError):
            prepare_claimed_extraction(DB, CLAIM)

        router_cls.assert_not_called()

    @patch("backend.jobs.extraction_worker.ModelRouter")
    @patch("backend.jobs.extraction_worker.fetch_claimed_source")
    def test_inference_failure_is_not_silent(self, reader, router_cls):
        reader.return_value = SOURCE
        router_cls.return_value.run.side_effect = (
            InferenceUnavailableError(
                "event_extraction", primary_configured=False
            )
        )

        with self.assertRaises(InferenceUnavailableError):
            prepare_claimed_extraction(DB, CLAIM)

    @patch("backend.jobs.extraction_worker.ModelRouter")
    @patch("backend.jobs.extraction_worker.fetch_claimed_source")
    def test_non_offline_provider_rejected(self, reader, router_cls):
        reader.return_value = SOURCE
        router_cls.return_value.run.return_value = SimpleNamespace(
            provider="unexpected_external_provider",
            data={"events": [], "actions": []},
        )

        with self.assertRaises(RuntimeError):
            prepare_claimed_extraction(DB, CLAIM)


if __name__ == "__main__":
    unittest.main()
