import unittest
from copy import deepcopy

from backend.memory.record_association import (
    prepare_record_association,
)

USER = "11111111-1111-4111-8111-111111111111"
OTHER = "22222222-2222-4222-8222-222222222222"
PROJECT = "33333333-3333-4333-8333-333333333333"
ASSERTION = "44444444-4444-4444-8444-444444444444"


class RecordAssociationTests(unittest.TestCase):
    def setUp(self):
        self.record = {
            "id": 1,
            "user_id": USER,
            "project_id": PROJECT,
            "title": "Review Canvas visualization",
        }
        self.assertion = {
            "id": ASSERTION,
            "user_id": USER,
            "project_id": PROJECT,
        }

    def prepare(self, **updates):
        args = {
            "user_id": USER,
            "project_id": PROJECT,
            "record_kind": "action",
            "record_id": "1",
            "record": self.record,
            "assertion": self.assertion,
        }
        args.update(updates)
        return prepare_record_association(**args)

    def test_explicit_action_association(self):
        before = deepcopy((self.record, self.assertion))
        result = self.prepare()

        self.assertEqual(result["record_id"], "1")
        self.assertEqual(result["record_kind"], "action")
        self.assertEqual(result["assertion_id"], ASSERTION)
        self.assertFalse(result["persisted"])
        self.assertFalse(result["confirmed"])
        self.assertEqual(
            (self.record, self.assertion), before
        )

    def test_event_association(self):
        result = self.prepare(record_kind="event")
        self.assertEqual(result["record_kind"], "event")

    def test_bigint_maximum(self):
        value = "9223372036854775807"
        self.record["id"] = int(value)
        self.assertEqual(
            self.prepare(record_id=value)["record_id"], value
        )

    def test_rejects_invalid_record_id(self):
        for value in (
            "0", "-1", "01", "1.0", "1e3", "",
            "9223372036854775808",
            ASSERTION, True, None, 1.5
        ):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    self.prepare(record_id=value)

    def test_rejects_invalid_record_kind(self):
        for kind in ("task", "project", "", None):
            with self.subTest(kind=kind):
                with self.assertRaises(ValueError):
                    self.prepare(record_kind=kind)

    def test_rejects_cross_user_record(self):
        self.record["user_id"] = OTHER
        with self.assertRaises(PermissionError):
            self.prepare()

    def test_rejects_cross_project_record(self):
        self.record["project_id"] = OTHER
        with self.assertRaises(PermissionError):
            self.prepare()

    def test_rejects_cross_user_assertion(self):
        self.assertion["user_id"] = OTHER
        with self.assertRaises(PermissionError):
            self.prepare()

    def test_rejects_cross_project_assertion(self):
        self.assertion["project_id"] = OTHER
        with self.assertRaises(PermissionError):
            self.prepare()

    def test_rejects_record_identity_mismatch(self):
        self.record["id"] = 2
        with self.assertRaises(PermissionError):
            self.prepare()

    def test_rejects_invalid_assertion_identity(self):
        self.assertion["id"] = "1"
        with self.assertRaises(ValueError):
            self.prepare()

    def test_duplicate_titles_never_select_other_record(self):
        self.record["title"] = "Same title"
        with self.assertRaises(PermissionError):
            self.prepare(record_id="2")

    def test_requires_explicit_record_and_assertion(self):
        with self.assertRaises(TypeError):
            self.prepare(record=None)
        with self.assertRaises(TypeError):
            self.prepare(assertion=None)


if __name__ == "__main__":
    unittest.main()
