import re
import unittest
from pathlib import Path


SQL_FILE = (
    Path(__file__).resolve().parents[1]
    / "database"
    / "security"
    / "b1_privileges.review.sql"
)

EXPECTED_TABLES = {
    "public.profiles",
    "public.projects",
    "public.source_connections",
    "public.source_items",
    "public.project_source_links",
    "public.project_events",
    "public.project_actions",
    "public.user_corrections",
    "public.item_relationships",
}


class B1PrivilegePlanTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        text = SQL_FILE.read_text()
        cls.sql = "\n".join(
            line.split("--", 1)[0]
            for line in text.splitlines()
        )

    def test_exact_client_table_scope(self):
        match = re.search(
            r"REVOKE\s+TRUNCATE,\s*TRIGGER,\s*REFERENCES"
            r"\s+ON\s+TABLE\s+(.*?)\s+FROM\s+anon,"
            r"\s*authenticated\s*;",
            self.sql,
            re.IGNORECASE | re.DOTALL,
        )
        self.assertIsNotNone(match)

        tables = {
            value.strip()
            for value in match.group(1).split(",")
        }
        self.assertEqual(tables, EXPECTED_TABLES)

    def test_privileged_functions_restricted(self):
        for name in ("handle_new_user", "rls_auto_enable"):
            expected = (
                f"REVOKE EXECUTE ON FUNCTION public.{name}()"
                "\nFROM PUBLIC, anon, authenticated;"
            )
            self.assertIn(expected, self.sql)

    def test_only_approved_operations(self):
        self.assertRegex(self.sql, r"\bBEGIN\s*;")
        self.assertRegex(self.sql, r"\bCOMMIT\s*;")

        self.assertEqual(
            len(re.findall(r"\bREVOKE\b", self.sql)), 3
        )

        self.assertNotRegex(
            self.sql,
            r"\b(DROP|ALTER|CREATE|INSERT|UPDATE|DELETE|GRANT)"
            r"\b",
        )


if __name__ == "__main__":
    unittest.main()
