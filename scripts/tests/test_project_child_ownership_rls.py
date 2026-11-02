import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MIGRATION = (
    ROOT / "supabase/migrations/"
    "20261102163151_enforce_child_project_ownership.sql"
)

class ChildProjectOwnershipTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sql = MIGRATION.read_text(encoding="utf-8")

    def test_two_restrictive_policies(self):
        names = re.findall(
            r"(?im)^CREATE POLICY (\w+)$", self.sql
        )
        self.assertEqual(set(names), {
            "project_events_parent_owner_guard",
            "project_actions_parent_owner_guard",
        })
        self.assertEqual(self.sql.count("AS RESTRICTIVE"), 2)

    def test_both_parent_ownership_checks(self):
        self.assertEqual(
            self.sql.count("p.user_id = (SELECT auth.uid())"), 4
        )
        for table in ("project_events", "project_actions"):
            self.assertEqual(
                self.sql.count(f"p.id = {table}.project_id"), 2
            )

    def test_ownership_preflight(self):
        for child in ("e", "a"):
            self.assertIn(
                f"{child}.user_id IS DISTINCT FROM p.user_id",
                self.sql
            )

    def test_no_privilege_broadening(self):
        self.assertEqual(self.sql.count("WITH CHECK ("), 2)
        self.assertNotRegex(
            self.sql,
            r"(?im)^\s*(?:GRANT|REVOKE|DROP POLICY)\b"
        )
        self.assertNotIn("cat > ", self.sql)
        self.assertNotIn("python3 - ", self.sql)

if __name__ == "__main__":
    unittest.main()
