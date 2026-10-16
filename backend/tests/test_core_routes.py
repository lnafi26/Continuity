"""Core Flask routes work without optional Google/DB/Claude credentials."""

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'auth'))
import server  # noqa: E402
from config import Config  # noqa: E402

ID = '7fbd542e-4cab-48fa-988d-23f68faac503'
TOKEN = {'Authorization': 'Bearer synthetic-unit-test'}


def auth_only_config():
    return Config(
        google_client_id='', google_client_secret='',
        redirect_uri='http://localhost:8766/auth/google/callback',
        token_encryption_key='', database_url='',
        default_test_user_id='', supabase_url='https://example.supabase.co',
        supabase_publishable_key='sb_publishable_synthetic',
        missing=['GOOGLE_CLIENT_ID', 'GOOGLE_CLIENT_SECRET',
                 'TOKEN_ENCRYPTION_KEY', 'SUPABASE_DATABASE_URL'],
    )


class CoreRoutesTests(unittest.TestCase):
    def setUp(self):
        self.client = server.app.test_client()
        self.cfg = auth_only_config()

    def test_health_is_ready_without_google(self):
        with patch.object(server, 'config', self.cfg):
            response = self.client.get('/health')
        self.assertEqual(response.status_code, 200)
        self.assertIn('auth_ready: True', response.get_data(as_text=True))
        self.assertIn('google_integration_ready: False', response.get_data(as_text=True))

    @patch.object(server, 'verify_access_token', return_value=ID)
    def test_session_uses_token_verifier_without_db(self, verify):
        with patch.object(server, 'config', self.cfg):
            response = self.client.get('/auth/session', headers=TOKEN)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, {'ok': True, 'user_id': ID})
        self.assertEqual(verify.call_args.kwargs['supabase_url'], self.cfg.supabase_url)
        self.assertEqual(verify.call_args.kwargs['publishable_key'], self.cfg.supabase_publishable_key)

    def test_session_without_token_is_unauthorized(self):
        with patch.object(server, 'config', self.cfg):
            response = self.client.get('/auth/session')
        self.assertEqual(response.status_code, 401)

    @patch.object(server.connections_repo, 'list_connections')
    @patch.object(server, 'verify_access_token', return_value=ID)
    def test_connections_unconfigured_does_not_query_database(self, verify, list_connections):
        with patch.object(server, 'config', self.cfg):
            response = self.client.get('/connections', headers=TOKEN)
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json['error'], 'Database connection not configured.')
        list_connections.assert_not_called()

    @patch.object(server.subprocess, 'run')
    @patch.object(server, 'verify_access_token', return_value=ID)
    def test_pipeline_disabled_does_not_spawn_processes(self, verify, run):
        with patch.object(server, 'config', self.cfg):
            response = self.client.post('/pipeline/run', headers=TOKEN, json={})
        self.assertEqual(response.status_code, 503)
        run.assert_not_called()

    @patch.object(server, '_build_flow')
    @patch.object(server, 'verify_access_token', return_value=ID)
    def test_google_unconfigured_does_not_start_oauth(self, verify, flow):
        with patch.object(server, 'config', self.cfg):
            response = self.client.post('/auth/google/start', headers=TOKEN, json={'providers': 'gmail'})
        self.assertEqual(response.status_code, 503)
        flow.assert_not_called()


if __name__ == '__main__':
    unittest.main()
