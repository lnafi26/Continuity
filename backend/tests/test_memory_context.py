import unittest

from backend.memory.context import build_project_context


USER = "synthetic-user"
PROJECT = "fictional-project"


def fixture():
    project = {
        "id": PROJECT,
        "user_id": USER,
        "name": "Fictional Lunar Observatory",
        "summary": "Imaginary moon-base dashboard.",
        "origin": "user",
    }

    events = [{
        "id": 1,
        "user_id": USER,
        "project_id": PROJECT,
        "event_type": "decision",
        "title": "Prototype approved",
        "event_date": "2026-10-30T12:00:00Z",
        "source_item_id": "fictional-source",
        "user_edited": False,
    }]

    actions = [{
        "id": 2,
        "user_id": USER,
        "project_id": PROJECT,
        "title": "Build fictional dashboard",
        "status": "not_started",
        "completed": False,
    }]

    links = [{
        "user_id": USER,
        "project_id": PROJECT,
        "source_item_id": "fictional-source",
        "review_status": "confirmed",
    }]

    return project, events, actions, links


def snapshot(*args):
    return build_project_context(
        *args, as_of="2026-10-31T12:00:00Z"
    )


class MemoryContextTests(unittest.TestCase):

    def test_project_history_and_actions(self):
        result = snapshot(*fixture())
        self.assertEqual(result["counts"]["events"], 1)
        self.assertEqual(result["counts"]["open_actions"], 1)
        self.assertFalse(result["persisted"])
        self.assertEqual(
            result["kind"], "derived_read_only"
        )

    def test_confirmed_link_does_not_verify_claim(self):
        result = snapshot(*fixture())
        event = result["recent_events"][0]
        self.assertEqual(
            event["source_link_status"], "confirmed"
        )
        self.assertEqual(
            event["evidence_verification"], "not_verified"
        )

    def test_reject_cross_user_event(self):
        project, events, actions, links = fixture()
        events[0]["user_id"] = "another-user"

        with self.assertRaises(PermissionError):
            snapshot(project, events, actions, links)

    def test_reject_cross_project_action(self):
        project, events, actions, links = fixture()
        actions[0]["project_id"] = "different-project"

        with self.assertRaises(PermissionError):
            snapshot(project, events, actions, links)

    def test_completed_actions_excluded(self):
        project, events, actions, links = fixture()
        actions[0]["completed"] = True
        result = snapshot(project, events, actions, links)
        self.assertEqual(result["counts"]["open_actions"], 0)

    def test_timezone_required(self):
        with self.assertRaises(ValueError):
            build_project_context(
                *fixture(), as_of="2026-10-31T12:00:00"
            )


    def test_events_sorted_newest_first(self):
        project, events, actions, links = fixture()
        older = dict(events[0])
        older["id"] = 99
        older["event_date"] = "2026-10-20T12:00:00Z"
        events.insert(0, older)

        result = snapshot(project, events, actions, links)
        self.assertEqual(
            [row["id"] for row in result["recent_events"]],
            ["1", "99"]
        )

    def test_unlinked_event_remains_unverified(self):
        project, events, actions, links = fixture()
        result = snapshot(project, events, actions, [])

        event = result["recent_events"][0]
        self.assertEqual(
            event["source_link_status"], "unlinked"
        )
        self.assertEqual(
            event["evidence_verification"], "not_verified"
        )

    def test_missing_project_owner_rejected(self):
        project, events, actions, links = fixture()
        del project["user_id"]

        with self.assertRaises(ValueError):
            snapshot(project, events, actions, links)

    def test_builder_does_not_modify_input_records(self):
        import copy

        records = fixture()
        before = copy.deepcopy(records)

        snapshot(*records)
        self.assertEqual(records, before)


if __name__ == "__main__":
    unittest.main()
