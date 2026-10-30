import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

MIGRATIONS = ROOT / "supabase" / "migrations"
DEFERRED = (
    ROOT / "backend" / "database" / "deferred"
    / "20261017000000_processing_jobs.sql"
)


class B2MigrationSafetyTests(unittest.TestCase):
    def test_only_reviewed_migrations_are_discoverable(self):
        filenames = sorted(
            file.name for file in MIGRATIONS.glob("*.sql")
        )
        self.assertEqual(len(filenames), 2)
        self.assertEqual(
            filenames[0],
            "20261016000000_initial_schema.sql",
        )
        self.assertRegex(
            filenames[1],
            r"^\d{14}_continuity_b1_privilege_hardening\.sql$",
        )

    def test_b1_migration_matches_applied_security_sql(self):
        migrations = list(
            MIGRATIONS.glob(
                "*_continuity_b1_privilege_hardening.sql"
            )
        )
        self.assertEqual(len(migrations), 1)

        reviewed = (
            ROOT / "backend" / "database" / "security"
            / "b1_privileges.review.sql"
        ).read_text()

        generated = migrations[0].read_text()

        original = 'REVOKE EXECUTE ON FUNCTION public.rls_auto_enable()\nFROM PUBLIC, anon, authenticated;'
        guarded = "-- Optional function: absent from the initial schema.\nDO $b1_optional_rls$\nBEGIN\n    IF to_regprocedure('public.rls_auto_enable()') IS NOT NULL THEN\n        EXECUTE 'REVOKE EXECUTE ON FUNCTION public.rls_auto_enable() FROM PUBLIC, anon, authenticated';\n    END IF;\nEND;\n$b1_optional_rls$;"
        reviewed_body = reviewed.split("\nBEGIN;\n", 1)[1]
        generated_body = generated.split("\nBEGIN;\n", 1)[1]
        self.assertEqual(reviewed_body.count(original), 1)
        self.assertEqual(
            generated_body,
            reviewed_body.replace(original, guarded, 1),
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
