"""Unit tests for backend auth verification; no live credentials needed."""

import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "auth"))
from supabase_auth import (  # noqa: E402
    AuthenticationError,
    AuthenticationUnavailable,
    verify_access_token,
)

SUPABASE_URL = "https://example.supabase.co"
PUBLISHABLE_KEY = "sb_publishable_test"
USER_ID = "7fbd542e-4cab-48fa-988d-23f68faac503"


class VerifyAccessTokenTests(unittest.TestCase):
    def verify(self, header="Bearer valid-session", **kwargs):
        return verify_access_token(
            header,
            supabase_url=kwargs.get("supabase_url", SUPABASE_URL),
            publishable_key=kwargs.get("publishable_key", PUBLISHABLE_KEY),
        )

    @patch("supabase_auth.requests.get")
    def test_valid_supabase_session_returns_verified_uuid(self, get):
        get.return_value = Mock(status_code=200)
        get.return_value.json.return_value = {"id": USER_ID, "email": "test@example.com"}
        self.assertEqual(self.verify(), USER_ID)
        url = get.call_args.args[0]
        headers = get.call_args.kwargs["headers"]
        self.assertEqual(url, "https://example.supabase.co/auth/v1/user")
        self.assertEqual(headers["apikey"], PUBLISHABLE_KEY)
        self.assertEqual(headers["Authorization"], "Bearer valid-session")
        self.assertFalse(get.call_args.kwargs["allow_redirects"])

    @patch("supabase_auth.requests.get")
    def test_missing_header_rejected_without_network(self, get):
        for header in (None, "", "Basic abc", "Bearer", "Bearer ", "Bearer a b"):
            with self.subTest(header=header), self.assertRaises(AuthenticationError):
                self.verify(header)
        get.assert_not_called()

    @patch("supabase_auth.requests.get")
    def test_expired_or_invalid_token_rejected(self, get):
        for status in (400, 401, 403):
            get.return_value = Mock(status_code=status)
            with self.subTest(status=status), self.assertRaises(AuthenticationError):
                self.verify()

    @patch("supabase_auth.requests.get")
    def test_auth_service_errors_fail_closed(self, get):
        for status in (302, 429, 500, 503):
            get.return_value = Mock(status_code=status)
            with self.subTest(status=status), self.assertRaises(AuthenticationUnavailable):
                self.verify()

    @patch("supabase_auth.requests.get")
    def test_bad_user_payload_fails_closed(self, get):
        get.return_value = Mock(status_code=200)
        for response in ({}, [], {"id": "not-a-uuid"}, {"id": None}):
            get.return_value.json.return_value = response
            with self.subTest(response=response), self.assertRaises(AuthenticationUnavailable):
                self.verify()

    @patch("supabase_auth.requests.get")
    def test_network_failure_fails_closed(self, get):
        import requests
        get.side_effect = requests.Timeout("timed out")
        with self.assertRaises(AuthenticationUnavailable):
            self.verify()

    @patch("supabase_auth.requests.get")
    def test_invalid_supabase_config_fails_closed(self, get):
        for bad_url in ("http://example.supabase.co", "https://example.supabase.co/evil", "", "https://user@example.com"):
            with self.subTest(bad_url=bad_url), self.assertRaises(AuthenticationUnavailable):
                self.verify(supabase_url=bad_url)
        with self.assertRaises(AuthenticationUnavailable):
            self.verify(publishable_key="")
        get.assert_not_called()


if __name__ == "__main__":
    unittest.main()
