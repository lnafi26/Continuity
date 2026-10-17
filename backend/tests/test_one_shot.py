"""R0.5: Single-job worker lifecycle regression tests.

Database operations and extraction are mocked.
No live services, PostgreSQL writes, or inference calls.
"""

import unittest
from unittest.mock import patch

from backend.extract.extract_repo import ExtractionWriteConflict
from backend.intelligence.router import InferenceUnavailableError
from backend.jobs.ledger import JobClaim, JobLeaseLostError
from backend.jobs.one_shot import run_one_local


DB = (
    "postgresql://continuity_test:continuity_test_only"
    "@127.0.0.1:55432/continuity_test"
)

USER = "7fbd542e-4cab-48fa-988d-23f68faac503"

CLAIM = JobClaim(
    job_id="0c27afd5-7364-4846-a93e-b97f044ac5d0",
    user_id=USER,
    source_item_id="54715de6-4131-4ed0-8147-c6810996ad57",
    lease_token="21a51e0e-fbf3-41b4-a2d8-8e245c822af1",
    attempt=1,
)


class OneShotWorkerTests(unittest.TestCase):

    def setUp(self):
        self.claim = patch(
            "backend.jobs.one_shot.claim_next"
        ).start()
        self.process = patch(
            "backend.jobs.one_shot.process_one_claim_local"
        ).start()
        self.fail = patch(
            "backend.jobs.one_shot.mark_failed"
        ).start()

        self.addCleanup(patch.stopall)

        self.claim.return_value = CLAIM
        self.process.return_value = True
        self.fail.return_value = "retry_wait"

    def run_worker(self):
        return run_one_local(DB, user_id=USER)

    def test_nonlocal_database_rejected_before_claim(self):
        invalid = DB.replace(
            "127.0.0.1", "production.example.test"
        )

        with self.assertRaises(ValueError):
            run_one_local(invalid, user_id=USER)

        self.claim.assert_not_called()
        self.process.assert_not_called()
        self.fail.assert_not_called()

    def test_empty_queue_does_not_process(self):
        self.claim.return_value = None

        result = self.run_worker()

        self.assertEqual(
            result,
            {"status": "no_eligible_job", "job_id": None},
        )
        self.process.assert_not_called()
        self.fail.assert_not_called()

    def test_successful_job(self):
        result = self.run_worker()

        self.assertEqual(result["status"], "succeeded")
        self.assertEqual(result["job_id"], CLAIM.job_id)

        self.claim.assert_called_once_with(
            DB, user_id=USER, lease_seconds=180
        )
        self.process.assert_called_once_with(DB, CLAIM)
        self.fail.assert_not_called()

    def test_inference_failure_schedules_retry(self):
        self.process.side_effect = InferenceUnavailableError(
            "event_extraction",
            primary_configured=False,
        )

        result = self.run_worker()

        self.assertEqual(result["status"], "retry_wait")
        self.assertEqual(
            result["error_code"], "inference_unavailable"
        )
        self.fail.assert_called_once_with(
            DB, CLAIM, error_code="inference_unavailable"
        )

    def test_manual_edit_conflict_categorized(self):
        self.process.side_effect = ExtractionWriteConflict(
            "Synthetic edited output"
        )

        result = self.run_worker()

        self.assertEqual(
            result["error_code"], "user_edit_conflict"
        )
        self.fail.assert_called_once_with(
            DB, CLAIM, error_code="user_edit_conflict"
        )

    def test_unexpected_failure_redacted(self):
        self.process.side_effect = RuntimeError(
            "SYNTHETIC_PRIVATE_EXCEPTION_DETAIL"
        )

        result = self.run_worker()

        self.assertEqual(result["status"], "retry_wait")
        self.assertEqual(
            result["error_code"], "processing_failed"
        )
        self.assertNotIn(
            "SYNTHETIC_PRIVATE_EXCEPTION_DETAIL",
            str(result),
        )
        self.fail.assert_called_once_with(
            DB, CLAIM, error_code="processing_failed"
        )

    def test_false_write_result_not_success(self):
        self.process.return_value = False

        result = self.run_worker()

        self.assertEqual(result["status"], "retry_wait")
        self.assertEqual(
            result["error_code"], "processing_failed"
        )
        self.fail.assert_called_once()

    def test_lost_lease_does_not_report_failure(self):
        self.process.side_effect = JobLeaseLostError()

        result = self.run_worker()

        self.assertEqual(result["status"], "lease_lost")
        self.assertEqual(result["job_id"], CLAIM.job_id)
        self.fail.assert_not_called()

    def test_lease_lost_while_reporting_failure(self):
        self.process.side_effect = RuntimeError(
            "Synthetic processing error"
        )
        self.fail.side_effect = JobLeaseLostError()

        result = self.run_worker()

        self.assertEqual(result["status"], "lease_lost")
        self.assertEqual(result["job_id"], CLAIM.job_id)
        self.fail.assert_called_once()


if __name__ == "__main__":
    unittest.main()
