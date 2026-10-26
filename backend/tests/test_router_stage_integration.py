"""Phase 3B: the inherited stage entrypoints must use Continuity's offline router.

Database methods are mocked: no Supabase, Gmail, Google, Claude, or inference
service is contacted. The legacy pipeline must remain disabled.
"""
from __future__ import annotations

import importlib.util
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
USER_ID = "7fbd542e-4cab-48fa-988d-23f68faac503"


def load_stage(name: str, relative: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class StageRouterIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.group = load_stage("continuity_group_stage", "backend/grouping/group.py")
        cls.extract = load_stage("continuity_extract_stage", "backend/extract/extract.py")
        cls.digest = load_stage("continuity_digest_stage", "backend/digest/summarize.py")

    def test_group_run_names_clusters_offline(self):
        stage = self.group
        def item(i, title):
            return SimpleNamespace(
                id=i, title=title, source_type="upload", sender="dev@example.com",
                participants=[], occurred_at=None, excerpt="", color="#4263eb"
            )
        args = SimpleNamespace(user_id=USER_ID, reset=False, threshold=0.5, min_size=2)
        cfg = SimpleNamespace(database_url="mocked")
        with patch.object(stage, "repo") as repo, patch.object(stage, "clustering") as clustering:
            repo.ai_projects_exist.return_value = False
            repo.fetch_linked_items.return_value = {}
            repo.fetch_included.return_value = {
                "a": item("a", "Client website kickoff"),
                "b": item("b", "Client website redesign"),
            }
            repo.fetch_edges.return_value = [("a", "b", 0.9)]
            clustering.connected_components.return_value = [["a", "b"]]
            clustering.cluster_cohesion.return_value = 0.9
            repo.create_project.return_value = "project-test"
            self.assertEqual(stage.cmd_run(args, cfg), 0)
            self.assertIn("Website", repo.create_project.call_args.kwargs["name"])
            self.assertEqual(repo.link_item.call_count, 2)
            self.assertIn("provider offline", repo.link_item.call_args.kwargs["explanation"])

    def test_extract_run_writes_metadata_event_and_no_invented_actions(self):
        stage = self.extract
        it = SimpleNamespace(
            id="item-1", project_id="project-test", title="Website update",
            source_type="gmail", sender="team@example.com", participants=[],
            occurred_at=datetime(2026, 10, 15, 15, 0, tzinfo=timezone.utc),
            extracted_text="Status update", color="#4263eb",
        )
        args = SimpleNamespace(user_id=USER_ID, reset=False, limit=3)
        cfg = SimpleNamespace(database_url="mocked")
        with patch.object(stage, "extract_repo") as repo:
            repo.fetch_queue.return_value = [it]
            self.assertEqual(stage.cmd_run(args, cfg), 0)
            repo.write_extraction_atomic.assert_called_once()
            call = repo.write_extraction_atomic.call_args
            self.assertEqual(call.args[:4], ("mocked", USER_ID, "project-test", "item-1"))
            self.assertEqual(call.kwargs["events"][0]["title"], "Website update")
            self.assertEqual(call.kwargs["actions"], [])
            repo.insert_event.assert_not_called()
            repo.insert_action.assert_not_called()
            repo.mark_extracted.assert_not_called()

    def test_digest_run_writes_deterministic_summary(self):
        stage = self.digest
        cfg = SimpleNamespace(database_url="mocked")
        args = SimpleNamespace(user_id=USER_ID)
        events = [{"event_type": "decision", "title": "Approve wireframe", "person": "Designer"}]
        target = SimpleNamespace(id="project-test", name="Website Refresh")
        with patch.object(stage, "summarize_repo") as repo:
            repo.fetch_projects_needing_summary.return_value = [target]
            repo.fetch_recent_events.return_value = events
            self.assertEqual(stage.cmd_run(args, cfg), 0)
            repo.update_summary.assert_called_once()
            self.assertIn("Approve wireframe", repo.update_summary.call_args.args[2])

    def test_extraction_preview_never_writes(self):
        stage = self.extract
        cfg = SimpleNamespace(database_url="mocked")
        args = SimpleNamespace(user_id=USER_ID, limit=3)
        it = SimpleNamespace(
            id="item-1", project_id="project-test", title="Preview",
            source_type="gmail", sender="dev@example.com", participants=[],
            occurred_at=None, extracted_text="", color="#4263eb",
        )
        with patch.object(stage, "extract_repo") as repo:
            repo.fetch_queue.return_value = [it]
            self.assertEqual(stage.cmd_preview(args, cfg), 0)
            repo.insert_event.assert_not_called()
            repo.insert_action.assert_not_called()
            repo.mark_extracted.assert_not_called()


if __name__ == "__main__":
    unittest.main()
