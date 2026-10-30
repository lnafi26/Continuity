import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

MIGRATIONS = ROOT / "supabase" / "migrations"
DEFERRED = (
    ROOT / "backend" / "database" / "deferred"
    / "20261017000000_processing_jobs.sql"
)


class B2MigrationSafetyTests(unittest.TestCase):
    def test_only_initial_migration_is_discoverable(self):
        filenames = sorted(
            file.name for file in MIGRATIONS.glob("*.sql")
        )
        self.assertEqual(
            filenames,
            ["20261016000000_initial_schema.sql"],
        )

    def test_processing_jobs_is_preserved_and_deferred(self):
        self.assertTrue(DEFERRED.is_file())
        sql = DEFERRED.read_text()
        self.assertIn("DO NOT apply", sql)
        self.assertIn(
            "CREATE TABLE public.processing_jobs", sql
        )

    def test_b1_audit_is_not_an_automatic_migration(self):
        record = (
            ROOT / "backend" / "database" / "security"
            / "b1_privileges.review.sql"
        )
        self.assertTrue(record.is_file())
        self.assertIn("NOT an automatic migration",
                      record.read_text())


if __name__ == "__main__":
    unittest.main()
