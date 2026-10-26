"""R0.3C-A: no-network mocked-DB tests for lease-fenced extraction writer.

These tests cover SQL call ordering and guarded failure states; they do NOT
prove live PostgreSQL transactions. A separate Docker test is required.
"""
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from backend.jobs.ledger import JobClaim, JobLeaseLostError

ROOT = Path(__file__).resolve().parents[2]
USER = "7fbd542e-4cab-48fa-988d-23f68faac503"
SOURCE = "54715de6-4131-4ed0-8147-c6810996ad57"
PROJECT = "f72f4074-a812-4947-bd99-c9c4ace4cb1b"
JOB = "1fe4dbac-0276-4d14-bb2a-38ccbb7e5ea6"
TOKEN = "5a8e3f7c-2bf4-4944-8dfc-37333f57f3b1"
EVENT = {
    "event_type": "note", "title": "Synthetic item", "body": "Fictional",
    "person": "", "event_date": None, "requires_response": None,
    "confidence": 0.4,
}
ACTION = {
    "title": "Synthetic follow-up", "assignee": None, "due_date": None,
    "status": "not_started", "backlog": False, "confidence": 0.5,
}


def load_repo():
    spec = importlib.util.spec_from_file_location(
        "r03c_extract_repo", ROOT / "backend/extract/extract_repo.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class FencedExtractionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.repo = load_repo()

    def setUp(self):
        self.connect = MagicMock()
        self.con = self.connect.return_value.__enter__.return_value
        self.cur = self.con.cursor.return_value.__enter__.return_value
        self.cur.fetchone.side_effect = [(JOB,), (None,), (False,), (JOB,)]
        self.cur.rowcount = 1
        self.patch = patch.object(self.repo.psycopg, "connect", self.connect)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.claim = JobClaim(JOB, USER, SOURCE, TOKEN, 1)

    def run_write(self, claim=None, *, events=None, actions=None):
        return self.repo.write_extraction_with_claim_atomic(
            "isolated-db", self.claim if claim is None else claim, PROJECT,
            events=[EVENT] if events is None else events,
            actions=[ACTION] if actions is None else actions,
            color="#123456",
        )

    def sql(self):
        return [c.args[0].strip().lower() for c in self.cur.execute.call_args_list]

    def test_valid_claim_locks_job_first_and_acknowledges_last(self):
        self.assertTrue(self.run_write())
        sql = self.sql()
        self.assertIn("from public.processing_jobs j", sql[0])
        self.assertIn("for update of j", sql[0])
        self.assertIn("clock_timestamp()", sql[0])
        self.assertIn("for update of si", sql[1])
        self.assertIn("update public.source_items", sql[-2])
        self.assertIn("update public.processing_jobs", sql[-1])
        self.assertIn("lease_until > clock_timestamp()", sql[-1])
        self.assertEqual(self.cur.execute.call_args.args[1],
                         (JOB, USER, SOURCE, "extract", TOKEN, 1))
        self.connect.assert_called_once_with("isolated-db")

    def test_lost_lease_cannot_touch_source(self):
        self.cur.fetchone.side_effect = [None]
        with self.assertRaises(JobLeaseLostError):
            self.run_write()
        self.assertEqual(len(self.sql()), 1)
        self.assertIn("processing_jobs", self.sql()[0])
        self.assertIsNotNone(self.connect.return_value.__exit__.call_args.args[0])

    def test_claim_from_another_user_rejected_before_database(self):
        bad = JobClaim(JOB, "c9965aaf-371f-41c6-9778-80ea678b14b4", SOURCE, TOKEN, 1)
        with self.assertRaises(JobLeaseLostError):
            self.repo.write_extraction_atomic(
                "isolated-db", USER, PROJECT, SOURCE,
                events=[EVENT], actions=[], color="#123456", job_claim=bad)
        self.connect.assert_not_called()

    def test_claim_from_another_source_rejected_before_database(self):
        bad = JobClaim(JOB, USER, "8f857d92-29e8-498f-9790-dead15ca7dcb", TOKEN, 1)
        with self.assertRaises(JobLeaseLostError):
            self.repo.write_extraction_atomic(
                "isolated-db", USER, PROJECT, SOURCE,
                events=[EVENT], actions=[], color="#123456", job_claim=bad)
        self.connect.assert_not_called()

    def test_boolean_attempt_rejected(self):
        bad = JobClaim(JOB, USER, SOURCE, TOKEN, True)
        with self.assertRaises(JobLeaseLostError):
            self.run_write(bad)
        self.connect.assert_not_called()

    def test_no_claim_rejected_by_explicit_entrypoint(self):
        with self.assertRaises(ValueError):
            self.run_write("not-a-claim")
        self.connect.assert_not_called()

    def test_already_processed_source_cannot_ack_job(self):
        self.cur.fetchone.side_effect = [(JOB,), ("extracted_at",)]
        with self.assertRaises(JobLeaseLostError):
            self.run_write()
        self.assertEqual(len(self.sql()), 2)
        self.assertFalse(any("update public.processing_jobs" in s for s in self.sql()))

    def test_source_link_missing_cannot_modify_output(self):
        self.cur.fetchone.side_effect = [(JOB,), None]
        with self.assertRaises(ValueError):
            self.run_write()
        self.assertEqual(len(self.sql()), 2)

    def test_manual_edits_block_output(self):
        self.cur.fetchone.side_effect = [(JOB,), (None,), (True,)]
        with self.assertRaises(self.repo.ExtractionWriteConflict):
            self.run_write()
        self.assertEqual(len(self.sql()), 3)

    def test_insert_error_rolls_back_and_does_not_ack(self):
        def error(sql, params):
            if "insert into public.project_actions" in sql:
                raise RuntimeError("SYNTHETIC_PRIVATE_SECRET")
        self.cur.execute.side_effect = error
        with self.assertRaises(RuntimeError):
            self.run_write()
        self.assertFalse(any("update public.processing_jobs" in s for s in self.sql()))
        self.assertIsNotNone(self.connect.return_value.__exit__.call_args.args[0])

    def test_ack_failure_rolls_back_output(self):
        self.cur.fetchone.side_effect = [(JOB,), (None,), (False,), None]
        with self.assertRaises(JobLeaseLostError):
            self.run_write()
        self.assertIn("update public.processing_jobs", self.sql()[-1])
        self.assertTrue(any("insert into public.project_events" in s for s in self.sql()))
        self.assertIsNotNone(self.connect.return_value.__exit__.call_args.args[0])

    def test_missing_or_malformed_generated_rows_rejected_before_connection(self):
        with self.assertRaises(ValueError):
            self.run_write(events=["not an object"])
        self.connect.assert_not_called()


if __name__ == "__main__":
    unittest.main()
