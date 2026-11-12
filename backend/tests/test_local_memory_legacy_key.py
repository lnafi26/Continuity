import base64
import json
import unittest
from unittest.mock import patch

from backend.auth.supabase_auth import AuthenticationError
from backend.memory.supabase_reader import fetch_project_context
from backend.memory.local_staging_boundary import LOCAL_SUPABASE_URL

PROJECT = "00000000-0000-4000-8000-000000000001"


def legacy_key(role):
    payload = base64.urlsafe_b64encode(
        json.dumps({"role": role}).encode()
    ).decode().rstrip("=")
    return f"e30.{payload}.synthetic-signature"


class LegacyLocalMemoryKeyTests(unittest.TestCase):

    def test_local_anon_key_reaches_authentication(self):
        with patch(
            "backend.auth.supabase_auth.requests.get"
        ) as auth_request:
            with patch(
                "backend.memory.supabase_reader.requests.get"
            ) as data_request:
                with self.assertRaises(AuthenticationError):
                    fetch_project_context(
                        None,
                        supabase_url=LOCAL_SUPABASE_URL,
                        publishable_key=legacy_key("anon"),
                        project_id=PROJECT,
                        allow_local_memory=True,
                    )
                auth_request.assert_not_called()
                data_request.assert_not_called()

    def test_local_service_role_key_rejected(self):
        with self.assertRaises(ValueError):
            fetch_project_context(
                None,
                supabase_url=LOCAL_SUPABASE_URL,
                publishable_key=legacy_key("service_role"),
                project_id=PROJECT,
                allow_local_memory=True,
            )

    def test_hosted_legacy_key_still_rejected(self):
        with self.assertRaises(ValueError):
            fetch_project_context(
                None,
                supabase_url="https://example.supabase.co",
                publishable_key=legacy_key("anon"),
                project_id=PROJECT,
            )


if __name__ == "__main__":
    unittest.main()
