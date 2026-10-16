"""Regression tests for authenticated Continuity Flask API endpoints.

Requires lightweight backend auth dependencies, but no live Supabase,
Google account, database, or model API keys.
"""
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'auth'))
import server  # noqa: E402
from supabase_auth import AuthenticationError  # noqa: E402

VERIFIED_ID = '7fbd542e-4cab-48fa-988d-23f68faac503'
OTHER_ID = '45987c3a-bc3d-4dd1-a47c-01c2b7337df3'
HEADER = {'Authorization': 'Bearer test-access-token'}


class ProtectedRouteTests(unittest.TestCase):
    def setUp(self):
        self.client = server.app.test_client()
        server._pending.clear()

    @patch.object(server.connections_repo, 'list_connections')
    def test_connections_rejects_unauthenticated_requests(self, list_connections):
        response = self.client.get('/connections?user_id=' + OTHER_ID)
        self.assertEqual(response.status_code, 401)
        list_connections.assert_not_called()

    @patch.object(server.subprocess, 'run')
    def test_pipeline_rejects_unauthenticated_requests(self, run):
        response = self.client.post('/pipeline/run', json={'user_id': OTHER_ID})
        self.assertEqual(response.status_code, 401)
        run.assert_not_called()

    @patch.object(server, '_build_flow')
    def test_google_start_requires_post_and_authenticated_session(self, build_flow):
        self.assertEqual(self.client.get('/auth/google/start?user_id=' + OTHER_ID).status_code, 405)
        response = self.client.post('/auth/google/start', json={'providers': 'gmail', 'user_id': OTHER_ID})
        self.assertEqual(response.status_code, 401)
        build_flow.assert_not_called()

    @patch.object(server.connections_repo, 'list_connections', return_value=[])
    @patch.object(server, 'verify_access_token', return_value=VERIFIED_ID)
    def test_connections_uses_verified_identity(self, verify, list_connections):
        with patch.object(server, 'config', Mock(is_complete=True)):
            response = self.client.get(
                '/connections?user_id=' + OTHER_ID,
                headers=HEADER
            )
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(list_connections.call_args.args[1], VERIFIED_ID)
        self.assertTrue(verify.called)

    @patch.object(server.subprocess, 'run')
    @patch.object(server, 'verify_access_token', return_value=VERIFIED_ID)
    def test_pipeline_uses_verified_identity_even_when_body_spoofed(self, verify, run):
        run.return_value = Mock(returncode=0, stdout='ok', stderr='')
        with patch.object(server, 'config', Mock(is_complete=True)), \
             patch.object(server, 'PIPELINE_STEPS', [('sync', ['worker.py'])]):
            response = self.client.post('/pipeline/run', headers=HEADER,
                                        json={'user_id': OTHER_ID})
        self.assertEqual(response.status_code, 200)
        args = run.call_args.args[0]
        self.assertIn(VERIFIED_ID, args)
        self.assertNotIn(OTHER_ID, args)

    @patch.object(server, 'verify_access_token', return_value=VERIFIED_ID)
    @patch.object(server, '_build_flow')
    def test_google_oauth_start_binds_state_to_verified_user(self, build_flow, verify):
        flow = Mock(code_verifier='verifier-123')
        flow.authorization_url.return_value = ('https://accounts.google.com/o/oauth2/auth?state=test', 'test')
        build_flow.return_value = flow
        fake_config = Mock(is_complete=True)
        fake_config.scopes_for.return_value = ['openid']
        with patch.object(server, 'config', fake_config):
            response = self.client.post('/auth/google/start', headers={
                **HEADER, 'Origin': 'http://localhost:8000'}, json={
                'providers': 'gmail',
                'user_id': OTHER_ID,
                'return_to': 'http://localhost:8000/',
            })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['authorization_url'], flow.authorization_url.return_value[0])
        self.assertEqual(len(server._pending), 1)
        record = next(iter(server._pending.values()))
        self.assertEqual(record['user_id'], VERIFIED_ID)
        self.assertEqual(record['return_to'], 'http://localhost:8000/')
        self.assertIn('Authorization', response.headers['Access-Control-Allow-Headers'])
        self.assertEqual(response.headers['Access-Control-Allow-Origin'], 'http://localhost:8000')

    def test_oauth_redirect_rejects_untrusted_origin(self):
        for candidate in (
            'https://ai-project-management-tool.huairuxu.workers.dev/',
            'http://localhost:8000.attacker.example/',
            'http://localhost:8000@attacker.example/',
            'http://localhost:9000/',
            'javascript:alert(1)',
        ):
            with self.subTest(candidate=candidate):
                self.assertIsNone(server._safe_return_to(candidate))
        self.assertEqual(server._safe_return_to('http://localhost:8000/'), 'http://localhost:8000/')

    @patch.object(server.subprocess, 'run')
    @patch.object(server, 'verify_access_token', side_effect=AuthenticationError('Invalid or expired session.'))
    def test_expired_token_rejects_pipeline(self, verify, run):
        response = self.client.post('/pipeline/run', headers=HEADER, json={})
        self.assertEqual(response.status_code, 401)
        run.assert_not_called()


if __name__ == '__main__':
    unittest.main()
