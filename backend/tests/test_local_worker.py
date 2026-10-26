"""R0.4: Controlled extraction worker regression tests.

All database-facing operations are mocked.
No PostgreSQL, external inference, or production services.
"""

import unittest
from unittest.mock import patch

from backend.jobs.ledger import JobClaim
from backend.jobs.extraction_worker import process_one_claim_local


DB = (
    "postgresql://continuity_test:continuity_test_only"
    "@127.0.0.1:55432/continuity_test"
)

CLAIM = JobClaim(
    job_id="0c27afd5-7364-4846-a93e-b97f044ac5d0",
    user_id="7fbd542e-4cab-48fa-988d-23f68faac503",
    source_item_id="54715de6-4131-4ed0-8147-c6810996ad57",
    lease_token="21a51e0e-fbf3-41b4-a2d8-8e245c822af1",
    attempt=1,
)

PREPARED = {
    "project_id": "35550b67-9e96-4968-9537-9852ff15436a",
    "color": "#4263eb",
    "events": [{"title": "Synthetic event"}],
    "actions": [],
}


class LocalWorkerTests(unittest.TestCase):

    def setUp(self):
        reader_patch = patch(
            "backend.jobs.extraction_worker.prepare_claimed_extraction"
        )
        writer_patch = patch(
            "backend.jobs.extraction_worker.write_extraction_with_claim_atomic"
        )

        self.prepare = reader_patch.start()
        self.write = writer_patch.start()

        self.addCleanup(reader_patch.stop)
        self.addCleanup(writer_patch.stop)

        self.prepare.return_value = PREPARED
        self.write.return_value = True

    def test_valid_local_worker_calls_fenced_writer(self):
        result = process_one_claim_local(DB, CLAIM)

        self.assertTrue(result)
        self.prepare.assert_called_once_with(DB, CLAIM)

        self.write.assert_called_once_with(
            DB,
            CLAIM,
            PREPARED["project_id"],
            events=PREPARED["events"],
            actions=PREPARED["actions"],
            color=PREPARED["color"],
        )

    def test_nonlocal_databases_rejected_before_processing(self):
        invalid_urls = [
            DB.replace("127.0.0.1", "db.example.test"),
            DB.replace("127.0.0.1", "localhost"),
            DB.replace("55432", "5432"),
            DB.replace("/continuity_test", "/production"),
            DB.replace("://continuity_test:", "://other_user:"),
            DB + "?hostaddr=127.0.0.1",
            DB + "?service=unexpected",
        ]

        for url in invalid_urls:
            with self.subTest(url=url):
                with self.assertRaises(ValueError):
                    process_one_claim_local(url, CLAIM)

        self.prepare.assert_not_called()
        self.write.assert_not_called()

    def test_preparation_failure_never_writes(self):
        self.prepare.side_effect = RuntimeError(
            "Synthetic preparation failure"
        )

        with self.assertRaises(RuntimeError):
            process_one_claim_local(DB, CLAIM)

        self.write.assert_not_called()

    def test_database_write_failure_is_not_success(self):
        self.write.side_effect = RuntimeError(
            "Synthetic transaction failure"
        )

        with self.assertRaises(RuntimeError):
            process_one_claim_local(DB, CLAIM)

        self.prepare.assert_called_once_with(DB, CLAIM)
        self.write.assert_called_once()

    def test_writer_result_is_not_falsified(self):
        self.write.return_value = False

        result = process_one_claim_local(DB, CLAIM)

        self.assertFalse(result)
        self.write.assert_called_once()


if __name__ == "__main__":
    unittest.main()
