"""R0.2: simulated DB failures and isolated source processing (no I/O)."""
import importlib.util
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[2]
USER = "synthetic-user"
PROJECT = "synthetic-project"
ITEM = "synthetic-item"
EVENT = {
    "event_type": "note", "title": "Test note", "body": "Fictional input",
    "person": "", "event_date": None, "requires_response": False,
    "confidence": 0.5,
}
ACTION = {
    "title": "Test work", "assignee": "Alex", "due_date": None,
    "status": "not_started", "backlog": False, "confidence": 0.4,
}


def load_repo():
    spec = importlib.util.spec_from_file_location(
        "r02_extract_repo", ROOT / "backend/extract/extract_repo.py"
    )
    module = importlib.util.module_from_spec(spec)
    # dataclasses need the module visible during class construction.
    import sys
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class AtomicExtractionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.repo = load_repo()

    def setUp(self):
        self.db = MagicMock()
        self.connection = self.db.return_value.__enter__.return_value
        self.cursor = self.connection.cursor.return_value.__enter__.return_value
        self.cursor.fetchone.side_effect = [(None,), (False,)]
        self.cursor.rowcount = 1
        self.patcher = patch.object(self.repo.psycopg, "connect", self.db)
        self.patcher.start()
        self.addCleanup(self.patcher.stop)

    def write(self, events=None, actions=None):
        return self.repo.write_extraction_atomic(
            "synthetic-db", USER, PROJECT, ITEM,
            events=[EVENT] if events is None else events,
            actions=[ACTION] if actions is None else actions,
            color="#123456",
        )

    def statements(self):
        return [c.args[0].strip().lower() for c in self.cursor.execute.call_args_list]

    def test_single_connection_and_completion_last(self):
        self.assertTrue(self.write())
        self.db.assert_called_once_with("synthetic-db")
        sql = self.statements()
        self.assertIn("for update of si", sql[0])
        self.assertTrue(sql[-1].startswith("update public.source_items"))
        self.assertEqual(sum("insert into public.project_events" in s for s in sql), 1)
        self.assertEqual(sum("insert into public.project_actions" in s for s in sql), 1)
        self.assertLess(next(i for i,s in enumerate(sql) if "insert into public.project_actions" in s), len(sql)-1)
        self.assertEqual(self.cursor.execute.call_args.args[1], (ITEM, USER))

    def test_already_processed_source_skipped_without_mutations(self):
        self.cursor.fetchone.side_effect = [("some-timestamp",)]
        self.assertFalse(self.write())
        self.assertEqual(len(self.statements()), 1)

    def test_missing_source_link_cannot_write(self):
        self.cursor.fetchone.side_effect = [None]
        with self.assertRaises(ValueError):
            self.write()
        self.assertEqual(len(self.statements()), 1)

    def test_user_edits_block_rewrite_without_mutations(self):
        self.cursor.fetchone.side_effect = [(None,), (True,)]
        with self.assertRaises(self.repo.ExtractionWriteConflict):
            self.write()
        self.assertEqual(len(self.statements()), 2)

    def test_previous_unedited_rows_cleaned_before_insert(self):
        self.write()
        sql = self.statements()
        deletes = [i for i, s in enumerate(sql) if s.startswith("delete from public.")]
        insert_idx = [i for i, s in enumerate(sql) if "insert into public." in s]
        self.assertEqual(len(deletes), 2)
        self.assertTrue(all(d < min(insert_idx) for d in deletes))
        self.assertTrue(all("user_edited = false" in sql[d] for d in deletes))

    def test_failure_mid_write_not_marked_processed(self):
        def exec_effect(statement, params):
            if "insert into public.project_actions" in statement:
                raise RuntimeError("SECRET_SYNTHETIC_FAULT")
        self.cursor.execute.side_effect = exec_effect
        with self.assertRaises(RuntimeError):
            self.write()
        self.assertFalse(any(s.startswith("update public.source_items") for s in self.statements()))
        # psycopg connection context receives an exception and rolls back.
        self.assertIsNotNone(self.db.return_value.__exit__.call_args.args[0])

    def test_marker_failure_raises_instead_of_success(self):
        def exec_effect(statement, params):
            if statement.strip().lower().startswith("update public.source_items"):
                self.cursor.rowcount = 0
        self.cursor.execute.side_effect = exec_effect
        with self.assertRaises(RuntimeError):
            self.write()
        self.assertIsNotNone(self.db.return_value.__exit__.call_args.args[0])

    def test_invalid_generated_rows_rejected_before_database(self):
        with self.assertRaises(ValueError):
            self.write(events=["invalid"])
        self.db.assert_not_called()


class StageIsolationTests(unittest.TestCase):
    def test_first_source_failure_does_not_skip_second_source(self):
        spec = importlib.util.spec_from_file_location(
            "r02_extract_stage", ROOT / "backend/extract/extract.py"
        )
        import sys
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        sys.path.insert(0, str(ROOT / "backend/extract"))
        spec.loader.exec_module(module)
        def item(i):
            return SimpleNamespace(
                id=i, project_id=PROJECT, title="Synthetic source", source_type="upload",
                sender=None, participants=[], occurred_at=None,
                extracted_text="Synthetic source text", color="#123456",
            )
        args = SimpleNamespace(user_id=USER, reset=False, limit=3)
        cfg = SimpleNamespace(database_url="mocked")
        with patch.object(module, "extract_repo") as repo:
            repo.fetch_queue.return_value = [item("failed"), item("succeeded")]
            repo.write_extraction_atomic.side_effect = [RuntimeError("SENSITIVE_UNEXPECTED_DB_ERROR"), True]
            with patch.object(module, "ModelRouter") as router_cls:
                router_cls.return_value.run.return_value.data = {"events": [EVENT], "actions": []}
                from io import StringIO
                from contextlib import redirect_stdout
                out = StringIO()
                with redirect_stdout(out):
                    exit_code = module.cmd_run(args, cfg)
        self.assertEqual(exit_code, 1)
        self.assertEqual(repo.write_extraction_atomic.call_count, 2)
        self.assertIn("1 committed item(s)", out.getvalue())
        self.assertIn("1 failed", out.getvalue())
        self.assertNotIn("SENSITIVE_UNEXPECTED_DB_ERROR", out.getvalue())


if __name__ == "__main__":
    unittest.main()
