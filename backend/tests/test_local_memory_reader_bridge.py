import unittest
from types import SimpleNamespace
from unittest.mock import patch

from backend.memory.supabase_reader import (
    _base_url,
    fetch_project_context,
)
from backend.memory.local_staging_boundary import LOCAL_SUPABASE_URL

PROJECT_ID = "00000000-0000-4000-8000-000000000001"
LOCAL_KEY = "sb_publishable_testonly"
HOSTED = "https://example.supabase.co"


class StopBeforeNetwork(Exception):
    pass


class LocalMemoryReaderBridgeTests(unittest.TestCase):
    def test_local_reader_disabled_by_default(self):
        with self.assertRaises(ValueError):
            _base_url(LOCAL_SUPABASE_URL)

    def test_explicit_local_reader_allowed(self):
        self.assertEqual(
            _base_url(
                LOCAL_SUPABASE_URL,
                allow_local_memory=True,
                publishable_key=LOCAL_KEY,
            ),
            LOCAL_SUPABASE_URL,
        )

    def test_local_mode_rejects_hosted_endpoint(self):
        with self.assertRaises(ValueError):
            _base_url(
                HOSTED,
                allow_local_memory=True,
                publishable_key=LOCAL_KEY,
            )

    def test_hosted_reader_unchanged(self):
        self.assertEqual(_base_url(HOSTED), HOSTED)

    def test_reader_forwards_local_mode_to_auth(self):
        with patch(
            "backend.memory.supabase_reader.verify_access_token",
            side_effect=StopBeforeNetwork,
        ) as verify:
            with self.assertRaises(StopBeforeNetwork):
                fetch_project_context(
                    "Bearer synthetic-only",
                    supabase_url=LOCAL_SUPABASE_URL,
                    publishable_key=LOCAL_KEY,
                    project_id=PROJECT_ID,
                    allow_local_memory=True,
                )

        self.assertTrue(
            verify.call_args.kwargs["allow_local_memory"]
        )

    def test_route_forwards_local_mode(self):
        from backend.auth import server

        settings = SimpleNamespace(
            auth_ready=True,
            allow_local_memory=True,
            supabase_url=LOCAL_SUPABASE_URL,
            supabase_publishable_key=LOCAL_KEY,
        )

        with (
            patch.object(server, "config", settings),
            patch.object(
                server,
                "fetch_project_context",
                return_value={"project": {"id": PROJECT_ID}},
            ) as read,
        ):
            response = server.app.test_client().get(
                f"/memory/projects/{PROJECT_ID}/context",
                headers={
                    "Authorization": "Bearer synthetic-only",
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            read.call_args.kwargs["allow_local_memory"]
        )


if __name__ == "__main__":
    unittest.main()
