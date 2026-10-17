"""R0.4: authorization and read-only source retrieval tests.

All database operations are mocked. No live services are contacted.
"""

import unittest
from dataclasses import replace
from unittest.mock import patch

from backend.jobs.ledger import JobClaim, JobLeaseLostError
from backend.jobs.source_reader import fetch_claimed_source


DB = "synthetic-database"

CLAIM = JobClaim(
    job_id="0c27afd5-7364-4846-a93e-b97f044ac5d0",
    user_id="7fbd542e-4cab-48fa-988d-23f68faac503",
    source_item_id="54715de6-4131-4ed0-8147-c6810996ad57",
    lease_token="21a51e0e-fbf3-41b4-a2d8-8e245c822af1",
    attempt=1,
)

PROJECT = "35550b67-9e96-4968-9537-9852ff15436a"


class SourceReaderTests(unittest.TestCase):

    def setUp(self):
        patcher = patch(
            "backend.jobs.source_reader.psycopg.connect"
        )
        self.connect = patcher.start()
        self.addCleanup(patcher.stop)

        connection = (
            self.connect.return_value.__enter__.return_value
        )
        self.cursor = (
            connection.cursor.return_value.__enter__.return_value
        )

        self.cursor.fetchone.return_value = (
            PROJECT,
            "#4263eb",
            "upload",
            "Fictional milestone",
            None,
            ["Alex", "Sam"],
            None,
            "The fictional project reached its milestone.",
        )

    def test_authorized_source_returns_expected_data(self):
        data = fetch_claimed_source(DB, CLAIM)

        self.assertEqual(data["project_id"], PROJECT)
        self.assertEqual(data["color"], "#4263eb")
        self.assertEqual(
            data["item"]["title"], "Fictional milestone"
        )
        self.assertEqual(
            data["item"]["participants"], ["Alex", "Sam"]
        )
        self.connect.assert_called_once_with(DB)

    def test_query_checks_every_authorization_boundary(self):
        fetch_claimed_source(DB, CLAIM)

        self.cursor.execute.assert_called_once()
        sql, params = self.cursor.execute.call_args.args
        sql = " ".join(sql.lower().split())

        for expected in (
            "j.source_item_id = %s",
            "j.user_id = %s",
            "j.stage = %s",
            "j.status = 'running'",
            "j.lease_token = %s",
            "j.attempts = %s",
            "j.lease_until > clock_timestamp()",
            "si.user_id = j.user_id",
            "l.user_id = j.user_id",
            "p.user_id = j.user_id",
            "si.extracted_at is null",
        ):
            self.assertIn(expected, sql)

        self.assertTrue(sql.startswith("select"))
        self.assertEqual(len(params), 6)
        self.assertEqual(params[0], CLAIM.job_id)
        self.assertEqual(params[1], CLAIM.user_id)
        self.assertEqual(params[2], CLAIM.source_item_id)
        self.assertEqual(params[4], CLAIM.lease_token)
        self.assertEqual(params[5], CLAIM.attempt)

    def test_missing_or_unavailable_source_rejected(self):
        self.cursor.fetchone.return_value = None

        with self.assertRaises(JobLeaseLostError):
            fetch_claimed_source(DB, CLAIM)

    def test_invalid_attempt_rejected_before_connection(self):
        for attempt in (0, -1, True, "1"):
            with self.subTest(attempt=attempt):
                invalid = replace(CLAIM, attempt=attempt)

                with self.assertRaises(JobLeaseLostError):
                    fetch_claimed_source(DB, invalid)

        self.connect.assert_not_called()

    def test_malformed_identifiers_rejected(self):
        for field in (
            "job_id",
            "user_id",
            "source_item_id",
            "lease_token",
        ):
            with self.subTest(field=field):
                invalid = replace(CLAIM, **{field: "invalid"})

                with self.assertRaises(ValueError):
                    fetch_claimed_source(DB, invalid)

        self.connect.assert_not_called()

    def test_missing_claim_rejected(self):
        with self.assertRaises(ValueError):
            fetch_claimed_source(DB, None)

        self.connect.assert_not_called()

    def test_empty_metadata_gets_safe_defaults(self):
        self.cursor.fetchone.return_value = (
            PROJECT, None, "upload", "Test",
            None, None, None, None,
        )

        data = fetch_claimed_source(DB, CLAIM)

        self.assertEqual(data["color"], "#4263eb")
        self.assertEqual(data["item"]["participants"], [])
        self.assertIsNone(data["item"]["extracted_text"])


if __name__ == "__main__":
    unittest.main()
