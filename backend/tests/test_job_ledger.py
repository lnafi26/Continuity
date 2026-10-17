"""R0.3A: no-network, no-database unit tests for durable job boundaries."""
from __future__ import annotations

import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

from backend.jobs import ledger

OWNER = "7fbd542e-4cab-48fa-988d-23f68faac503"
OTHER = "c9965aaf-371f-41c6-9778-80ea678b14b4"
SOURCE = "54715de6-4131-4ed0-8147-c6810996ad57"
JOB = "1fe4dbac-0276-4d14-bb2a-38ccbb7e5ea6"
TOKEN = "5a8e3f7c-2bf4-4944-8dfc-37333f57f3b1"


def harness(fetches):
    connection = MagicMock()
    connection.__enter__.return_value = connection
    cursor = MagicMock()
    cursor.__enter__.return_value = cursor
    connection.cursor.return_value = cursor
    cursor.fetchone.side_effect = fetches
    return connection, cursor


class JobLedgerTests(unittest.TestCase):
    @patch.object(ledger.psycopg, "connect")
    def test_enqueue_validates_source_owner_not_extracted_and_deduplicates(self, connect):
        con, cur = harness([(JOB,)])
        connect.return_value = con
        actual = ledger.enqueue_extraction("not-real-db", user_id=OWNER,
                                            source_item_id=SOURCE)
        self.assertEqual(actual, JOB)
        query = cur.execute.call_args.args[0].lower()
        self.assertIn("si.user_id = %s", query)
        self.assertIn("si.extracted_at is null", query)
        self.assertIn("on conflict (user_id, source_item_id, stage) do nothing", query)
        self.assertEqual(cur.execute.call_args.args[1], ("extract", 3, SOURCE, OWNER))

    @patch.object(ledger.psycopg, "connect")
    def test_enqueue_existing_or_unowned_does_not_insert(self, connect):
        con, _ = harness([None])
        connect.return_value = con
        self.assertIsNone(ledger.enqueue_extraction("db", user_id=OWNER,
                                                     source_item_id=SOURCE))

    @patch.object(ledger.psycopg, "connect")
    def test_bad_id_or_max_attempts_rejected_before_connection(self, connect):
        for kwargs in (
            {"user_id": "not-uuid", "source_item_id": SOURCE},
            {"user_id": OWNER, "source_item_id": "not-uuid"},
            {"user_id": OWNER, "source_item_id": SOURCE, "max_attempts": True},
            {"user_id": OWNER, "source_item_id": SOURCE, "max_attempts": 7},
        ):
            with self.assertRaises(ValueError):
                ledger.enqueue_extraction("db", **kwargs)
        connect.assert_not_called()

    @patch.object(ledger.psycopg, "connect")
    def test_claim_recovers_expired_and_locks_next_job(self, connect):
        con, cur = harness([(JOB, SOURCE, 2)])
        connect.return_value = con
        c = ledger.claim_next("db", user_id=OWNER)
        self.assertEqual(c.job_id, JOB)
        self.assertEqual(c.source_item_id, SOURCE)
        self.assertEqual(c.attempt, 2)
        self.assertEqual(c.user_id, OWNER)
        self.assertEqual(len(c.lease_token), 36)
        self.assertEqual(cur.execute.call_count, 2)
        recover = cur.execute.call_args_list[0].args[0].lower()
        claim = cur.execute.call_args_list[1].args[0].lower()
        self.assertIn("lease_until <= now()", recover)
        self.assertIn("last_error_code = 'lease_expired'", recover)
        self.assertIn("when attempts >= max_attempts", recover)
        self.assertIn("for update skip locked", claim)
        self.assertIn("attempts < max_attempts", claim)
        self.assertIn("retry_at <= now()", claim)
        self.assertIn("attempts = attempts + 1", claim)
        self.assertIn("lease_token = %s::uuid", claim)
        self.assertIn("where user_id = %s", claim)

    @patch.object(ledger.psycopg, "connect")
    def test_no_available_job_returns_none(self, connect):
        con, _ = harness([None]);connect.return_value = con
        self.assertIsNone(ledger.claim_next("db", user_id=OWNER))

    @patch.object(ledger.psycopg, "connect")
    def test_invalid_lease_duration_does_not_connect(self, connect):
        for n in (0, 29, 901, True):
            with self.assertRaises(ValueError):
                ledger.claim_next("db", user_id=OWNER, lease_seconds=n)
        connect.assert_not_called()

    @patch.object(ledger.psycopg, "connect")
    def test_completion_requires_unexpired_token_and_owner(self, connect):
        con, cur = harness([(JOB,)])
        connect.return_value = con
        claim = ledger.JobClaim(JOB, OWNER, SOURCE, TOKEN, 1)
        ledger.mark_succeeded("db", claim)
        sql, params = cur.execute.call_args.args
        self.assertIn("lease_until > now()", sql)
        self.assertIn("lease_token = %s", sql)
        self.assertIn("status = 'running'", sql)
        self.assertIn("finished_at = now()", sql)
        self.assertEqual(params, (JOB, OWNER, "extract", TOKEN))

    @patch.object(ledger.psycopg, "connect")
    def test_old_claim_cannot_report_success(self, connect):
        con, _ = harness([None]);connect.return_value = con
        with self.assertRaises(ledger.JobLeaseLostError) as err:
            ledger.mark_succeeded("db", ledger.JobClaim(JOB, OWNER, SOURCE, TOKEN, 1))
        self.assertNotIn(SOURCE, str(err.exception))

    @patch.object(ledger.psycopg, "connect")
    def test_failure_uses_allowed_code_bounded_retry_and_lease(self, connect):
        con, cur = harness([("retry_wait",)]);connect.return_value = con
        claim = ledger.JobClaim(JOB, OWNER, SOURCE, TOKEN, 1)
        self.assertEqual(ledger.mark_failed("db", claim, error_code="inference_unavailable"),
                         "retry_wait")
        sql, params = cur.execute.call_args.args
        self.assertIn("least(3600, 30 * power(2, attempts - 1))", sql)
        self.assertIn("when attempts >= max_attempts", sql)
        self.assertIn("lease_until > now()", sql)
        self.assertEqual(params, ("inference_unavailable", JOB, OWNER, "extract", TOKEN))

    @patch.object(ledger.psycopg, "connect")
    def test_invalid_error_never_goes_to_database(self, connect):
        claim = ledger.JobClaim(JOB, OWNER, SOURCE, TOKEN, 1)
        for bad in ("access_token=VERY_SECRET", "RuntimeError: private body", [], None):
            with self.assertRaises(ValueError):
                ledger.mark_failed("db", claim, error_code=bad)
        connect.assert_not_called()

    @patch.object(ledger.psycopg, "connect")
    def test_old_claim_cannot_report_failure(self, connect):
        con, _ = harness([None]);connect.return_value = con
        with self.assertRaises(ledger.JobLeaseLostError):
            ledger.mark_failed("db", ledger.JobClaim(JOB, OWNER, SOURCE, TOKEN, 1),
                               error_code="processing_failed")

    @patch.object(ledger.psycopg, "connect")
    def test_status_is_owner_scoped_and_source_free(self, connect):
        when = datetime(2026, 10, 16, tzinfo=timezone.utc)
        con, cur = harness([(JOB, "extract", "retry_wait", 1, 3, "processing_failed", when, when)])
        connect.return_value = con
        item = ledger.get_status("db", user_id=OWNER, job_id=JOB)
        self.assertEqual(item["status"], "retry_wait")
        self.assertEqual(item["attempts"], 1)
        self.assertNotIn("source_item_id", item)
        self.assertNotIn("lease_token", item)
        self.assertEqual(cur.execute.call_args.args[1], (JOB, OWNER))

    @patch.object(ledger.psycopg, "connect")
    def test_missing_job_returns_none(self, connect):
        con, _ = harness([None]);connect.return_value = con
        self.assertIsNone(ledger.get_status("db", user_id=OTHER, job_id=JOB))

    def test_schema_owner_constraint_backend_only_and_no_raw_exception(self):
        sql = (Path(__file__).resolve().parents[2] /
               "supabase/migrations/20261017000000_processing_jobs.sql").read_text()
        normalized = sql.lower()
        self.assertIn("foreign key (source_item_id, user_id)", normalized)
        self.assertIn("enable row level security", normalized)
        self.assertIn("revoke all privileges", normalized)
        self.assertNotIn("create policy", normalized)
        self.assertNotIn("error_message", normalized)
        self.assertNotIn("source_text", normalized)
        self.assertIn("last_error_code text check", normalized)


if __name__ == "__main__":
    unittest.main()
