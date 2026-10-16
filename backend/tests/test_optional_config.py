"""Core auth readiness is independent of optional Google, DB and Claude."""

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'auth'))
from config import Config, load_config  # noqa: E402


class OptionalConfigurationTests(unittest.TestCase):
    def test_core_auth_only_can_start(self):
        with patch.dict('os.environ', {
            'SUPABASE_URL': 'https://example.supabase.co',
            'SUPABASE_PUBLISHABLE_KEY': 'sb_publishable_synthetic',
            'OAUTH_SERVER_PORT': '8766',
        }, clear=True):
            cfg = load_config()
        self.assertTrue(cfg.auth_ready)
        self.assertFalse(cfg.database_ready)
        self.assertFalse(cfg.oauth_ready)
        self.assertFalse(cfg.pipeline_ready)
        self.assertEqual(cfg.port, 8766)

    def test_missing_supabase_keys_reported(self):
        with patch.dict('os.environ', {}, clear=True):
            cfg = load_config()
        self.assertFalse(cfg.auth_ready)
        self.assertIn('SUPABASE_URL', cfg.auth_missing)
        self.assertIn('SUPABASE_PUBLISHABLE_KEY', cfg.auth_missing)

    def test_legacy_pipeline_is_opt_in(self):
        cfg = Config(
            google_client_id='test', google_client_secret='test',
            redirect_uri='http://localhost:8766/auth/google/callback',
            token_encryption_key='test', database_url='postgresql://localhost/test',
            default_test_user_id='', supabase_url='https://example.supabase.co',
            supabase_publishable_key='sb_publishable_synthetic', missing=[],
        )
        self.assertTrue(cfg.oauth_ready)
        self.assertFalse(cfg.pipeline_ready)
        cfg.pipeline_enabled = True
        self.assertTrue(cfg.pipeline_ready)


if __name__ == '__main__':
    unittest.main()
