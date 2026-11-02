import importlib.util
import tempfile
import unittest
from pathlib import Path

script = (
    Path(__file__).resolve().parents[1]
    / 'build_staging_app.py'
)

spec = importlib.util.spec_from_file_location(
    'continuity_staging_builder', script
)

builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)

STAGING_REF = 's' * 20
PROD_REF = 'p' * 20

STAGING_KEY = 'sb_publishable_StagingFixture123456'
PROD_KEY = 'sb_publishable_ProductionFixture123456'


class StagingAppBuildTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

        self.repo = Path(self.tmp.name) / 'repo'
        self.frontend = self.repo / 'frontend'

        for name in builder.CSS | builder.JS:
            path = self.frontend / name
            path.parent.mkdir(
                parents=True, exist_ok=True
            )
            path.write_text(
                '/* reviewed fixture */\n',
                encoding='utf-8'
            )

        config = self.frontend / builder.CONFIG
        config.parent.mkdir(
            parents=True, exist_ok=True
        )

        config.write_text(
            "window.SUPABASE_CONFIG = {\n"
            f"  url: 'https://{PROD_REF}.supabase.co',\n"
            f"  publishableKey: '{PROD_KEY}',\n"
            "  oauthBaseUrl: 'http://localhost:8080'\n"
            "};\n",
            encoding='utf-8'
        )

        for page in builder.PAGES:
            if page == 'reset-password.html':
                includes = {
                    'assets/js/reset-password.js',
                    builder.CONFIG,
                }
            else:
                includes = builder.ASSETS - {
                    'assets/js/reset-password.js'
                }

            tags = []

            for relative in sorted(includes):
                if relative in builder.CSS:
                    tags.append(
                        '<link rel="stylesheet" '
                        f'href="{relative}">'
                    )
                else:
                    tags.append(
                        f'<script src="{relative}"></script>'
                    )

            tags.append(
                f'<script src="{builder.ALLOWED_CDN}">'
                '</script>'
            )

            (self.frontend / page).write_text(
                '<html><head>'
                + ''.join(tags)
                + '</head><body></body></html>',
                encoding='utf-8'
            )

        self.env = {
            'CONTINUITY_STAGING_SUPABASE_PROJECT_REF':
                STAGING_REF,
            'CONTINUITY_STAGING_SUPABASE_URL':
                f'https://{STAGING_REF}.supabase.co',
            'CONTINUITY_STAGING_SUPABASE_PUBLISHABLE_KEY':
                STAGING_KEY,
        }

        self.output = Path(self.tmp.name) / 'build'

    def test_allowlisted_bundle_and_generated_config(self):
        builder.build(
            self.repo, self.output, self.env
        )

        files = {
            p.relative_to(self.output).as_posix()
            for p in self.output.rglob('*')
            if p.is_file()
        }

        self.assertEqual(
            files,
            builder.ASSETS | builder.PAGES | {'.nojekyll'}
        )

        config = (
            self.output / builder.CONFIG
        ).read_text()

        self.assertIn(STAGING_KEY, config)
        self.assertIn('"oauthBaseUrl":""', config)
        self.assertNotIn(PROD_KEY, config)
        self.assertNotIn(PROD_REF, config)

    def test_missing_settings_fail_closed(self):
        with self.assertRaises(ValueError):
            builder.build(
                self.repo, self.output, {}
            )

        self.assertFalse(self.output.exists())

    def test_production_url_and_key_are_rejected(self):
        wrong = dict(self.env)
        wrong[
            'CONTINUITY_STAGING_SUPABASE_PROJECT_REF'
        ] = PROD_REF

        wrong[
            'CONTINUITY_STAGING_SUPABASE_URL'
        ] = f'https://{PROD_REF}.supabase.co'

        with self.assertRaises(ValueError):
            builder.build(
                self.repo, self.output, wrong
            )

        wrong = dict(self.env)
        wrong[
            'CONTINUITY_STAGING_SUPABASE_PUBLISHABLE_KEY'
        ] = PROD_KEY

        with self.assertRaises(ValueError):
            builder.build(
                self.repo, self.output, wrong
            )

        self.assertFalse(self.output.exists())

    def test_secret_keys_and_unreviewed_oauth_are_rejected(self):
        wrong = dict(self.env)

        wrong[
            'CONTINUITY_STAGING_SUPABASE_PUBLISHABLE_KEY'
        ] = 'sb_secret_ExampleSecretValue123'

        with self.assertRaises(ValueError):
            builder.build(
                self.repo, self.output, wrong
            )

        wrong = dict(self.env)
        wrong[
            'CONTINUITY_STAGING_OAUTH_BASE_URL'
        ] = 'https://example.net'

        with self.assertRaises(ValueError):
            builder.build(
                self.repo, self.output, wrong
            )

        self.assertFalse(self.output.exists())

    def test_unreviewed_assets_and_dynamic_imports_fail(self):
        page = self.frontend / 'index.html'

        page.write_text(
            page.read_text().replace(
                '</body>',
                '<script src="assets/js/unknown.js">'
                '</script></body>'
            )
        )

        with self.assertRaises(ValueError):
            builder.build(
                self.repo, self.output, self.env
            )

        page.write_text(
            page.read_text().replace(
                '<script src="assets/js/unknown.js">'
                '</script>',
                ''
            )
        )

        source = (
            self.frontend / 'assets/js/auth.js'
        )
        source.write_text(
            'import("./unreviewed.js");'
        )

        with self.assertRaises(ValueError):
            builder.build(
                self.repo, self.output, self.env
            )

        self.assertFalse(self.output.exists())

    def test_nonempty_output_is_never_overwritten(self):
        self.output.mkdir()

        sentinel = self.output / 'keep.txt'
        sentinel.write_text('sentinel')

        with self.assertRaises(ValueError):
            builder.build(
                self.repo, self.output, self.env
            )

        self.assertEqual(
            sentinel.read_text(), 'sentinel'
        )


if __name__ == '__main__':
    unittest.main()
