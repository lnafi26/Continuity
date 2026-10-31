"""No-network regression tests for the authenticated memory API."""

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(
    0,
    str(Path(__file__).resolve().parents[1] / "auth"),
)

import server

from config import Config
from backend.auth.supabase_auth import (
    AuthenticationError,
    AuthenticationUnavailable,
)
from backend.memory.supabase_reader import MemoryReadUnavailable


PROJECT = "81c7e765-ea89-4519-91fc-c7aaaf8cc802"
PATH = f"/memory/projects/{PROJECT}/context"
TOKEN = {"Authorization": "Bearer synthetic-session"}


def test_config(ready=True):
    return Config(
        google_client_id="",
        google_client_secret="",
        redirect_uri="http://localhost:8766/auth/google/callback",
        token_encryption_key="",
        database_url="",
        default_test_user_id="",
        supabase_url=(
            "https://example.supabase.co"
            if ready else ""
        ),
        supabase_publishable_key=(
            "sb_publishable_synthetic"
            if ready else ""
        ),
    )


class MemoryRoutesTests(unittest.TestCase):

    def setUp(self):
        self.client = server.app.test_client()

    def request_with_reader(self, result=None, error=None):
        with (
            patch.object(server, "config", test_config()),
            patch.object(
                server,
                "fetch_project_context",
                return_value=result,
                side_effect=error,
            ) as reader,
        ):
            response = self.client.get(
                PATH, headers=TOKEN
            )
        return response, reader

    def test_success_returns_read_only_context(self):
        context = {
            "kind": "derived_read_only",
            "persisted": False,
            "counts": {"events": 1},
        }

        response, reader = self.request_with_reader(
            result=context
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json["ok"])
        self.assertEqual(
            response.json["context"], context
        )

        reader.assert_called_once_with(
            TOKEN["Authorization"],
            supabase_url="https://example.supabase.co",
            publishable_key="sb_publishable_synthetic",
            project_id=PROJECT,
        )

        self.assertIn(
            "no-store",
            response.headers["Cache-Control"],
        )

    def test_invalid_session_returns_401(self):
        response, _ = self.request_with_reader(
            error=AuthenticationError("Synthetic invalid session")
        )
        self.assertEqual(response.status_code, 401)
        self.assertNotIn(
            "Synthetic invalid session",
            response.get_data(as_text=True),
        )

    def test_auth_service_failure_returns_503(self):
        response, _ = self.request_with_reader(
            error=AuthenticationUnavailable("Synthetic outage")
        )
        self.assertEqual(response.status_code, 503)

    def test_inaccessible_project_returns_404(self):
        response, _ = self.request_with_reader(
            error=LookupError("Synthetic missing project")
        )
        self.assertEqual(response.status_code, 404)

    def test_ownership_mismatch_returns_404(self):
        response, _ = self.request_with_reader(
            error=PermissionError("Synthetic ownership mismatch")
        )
        self.assertEqual(response.status_code, 404)

    def test_invalid_project_id_returns_400(self):
        response, _ = self.request_with_reader(
            error=ValueError("Invalid project identity")
        )
        self.assertEqual(response.status_code, 400)

    def test_database_failure_returns_503(self):
        response, _ = self.request_with_reader(
            error=MemoryReadUnavailable("Synthetic provider detail")
        )
        self.assertEqual(response.status_code, 503)
        self.assertNotIn(
            "Synthetic provider detail",
            response.get_data(as_text=True),
        )

    def test_unconfigured_auth_never_reads(self):
        with (
            patch.object(server, "config", test_config(False)),
            patch.object(server, "fetch_project_context") as reader,
        ):
            response = self.client.get(PATH, headers=TOKEN)

        self.assertEqual(response.status_code, 503)
        reader.assert_not_called()

    def test_post_is_not_allowed(self):
        with patch.object(server, "fetch_project_context") as reader:
            response = self.client.post(PATH, headers=TOKEN)

        self.assertEqual(response.status_code, 405)
        reader.assert_not_called()

    def test_untrusted_origin_not_authorized(self):
        with (
            patch.object(server, "config", test_config()),
            patch.object(
                server,
                "fetch_project_context",
                return_value={"persisted": False},
            ),
        ):
            response = self.client.get(
                PATH,
                headers={
                    **TOKEN,
                    "Origin": "https://untrusted.example",
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertNotIn(
            "Access-Control-Allow-Origin",
            response.headers,
        )
        self.assertIn(
            "no-store",
            response.headers["Cache-Control"],
        )


    def test_missing_bearer_never_contacts_supabase(self):
        with (
            patch.object(server, "config", test_config()),
            patch(
                "backend.memory.supabase_reader.requests.get"
            ) as get,
        ):
            response = self.client.get(PATH)

        self.assertEqual(response.status_code, 401)
        get.assert_not_called()


if __name__ == "__main__":
    unittest.main()
