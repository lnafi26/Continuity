"""Regression tests for the fail-closed Cloudflare production build."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

SCRIPT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_DIR))

from build_production_site import build, read_mode, MODES  # noqa: E402

REPO = SCRIPT_DIR.parent


class ProductionReleaseTests(unittest.TestCase):
    def test_reviewed_release_mode_is_allowlisted(self):
        self.assertIn(read_mode(REPO), MODES)

    def test_holding_build_contains_only_approved_page(self):
        with tempfile.TemporaryDirectory() as scratch:
            output = Path(scratch) / "public"
            mode = build(REPO, output, mode="holding")
            self.assertEqual(mode, "holding")
            self.assertEqual(sorted(p.name for p in output.iterdir()), ["index.html"])
            self.assertEqual((output / "index.html").read_bytes(),
                             (REPO / "deploy/production/index.html").read_bytes())

    def test_synthetic_mode_reuses_safe_staging_builder(self):
        with tempfile.TemporaryDirectory() as scratch:
            output = Path(scratch) / "public"
            self.assertEqual(build(REPO, output, mode="synthetic-preview"), "synthetic-preview")
            self.assertTrue((output / ".nojekyll").exists())
            self.assertTrue((output / "assets/js/night-observatory-selection.js").exists())
            self.assertFalse((output / "assets/js/auth.js").exists())
            self.assertFalse((output / "config/supabase-config.js").exists())
            self.assertEqual(len([p for p in output.rglob("*") if p.is_file()]), 28)

    def test_refuses_reusing_nonempty_output(self):
        with tempfile.TemporaryDirectory() as scratch:
            output = Path(scratch) / "public"
            output.mkdir()
            (output / "keep.txt").write_text("must not overwrite")
            with self.assertRaises(ValueError):
                build(REPO, output)
            self.assertEqual((output / "keep.txt").read_text(), "must not overwrite")

    def test_rejects_unknown_mode(self):
        with tempfile.TemporaryDirectory() as scratch:
            with self.assertRaises(ValueError):
                build(REPO, Path(scratch) / "public", mode="frontend")

    def test_rejects_invalid_config(self):
        with tempfile.TemporaryDirectory() as scratch:
            repo = Path(scratch)
            config = repo / "deploy/production-release.json"
            config.parent.mkdir()
            config.write_text(json.dumps({"schema_version": 1, "mode": "frontend"}))
            with self.assertRaises(ValueError):
                read_mode(repo)
            config.write_text(json.dumps({"schema_version": 1, "mode": "holding", "secret": "x"}))
            with self.assertRaises(ValueError):
                read_mode(repo)


if __name__ == "__main__":
    unittest.main()
