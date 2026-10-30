import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import check_supabase_integration_gate as gate


class B2IntegrationGateTests(unittest.TestCase):

    def test_approved_manifest(self):
        actual = tuple(sorted(
            p.name
            for p in (ROOT / "supabase/migrations").glob("*.sql")
        ))
        self.assertEqual(actual, gate.APPROVED)

    def test_deferred_migration_blocks_integration(self):
        main = (
            "20261016000000_initial_schema.sql",
            gate.DEFERRED,
        )
        self.assertTrue(gate.assess(main, gate.APPROVED))

    def test_missing_b1_migration_blocks_integration(self):
        main = ("20261016000000_initial_schema.sql",)
        self.assertTrue(gate.assess(main, gate.APPROVED))

    def test_aligned_manifests_pass(self):
        self.assertEqual(
            gate.assess(gate.APPROVED, gate.APPROVED),
            [],
        )

    def test_no_automatic_database_mutation_workflows(self):
        workflows = ROOT / ".github/workflows"

        forbidden = re.compile(
            r"\bsupabase\s+(?:db\s+(?:push|reset)|"
            r"migration\s+up)\b",
            re.IGNORECASE,
        )

        for path in workflows.glob("*.yml"):
            with self.subTest(workflow=path.name):
                self.assertIsNone(
                    forbidden.search(path.read_text())
                )


if __name__ == "__main__":
    unittest.main()
