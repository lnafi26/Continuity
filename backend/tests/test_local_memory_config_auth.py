import unittest
from unittest.mock import patch, Mock

from backend.auth.config import Config
from backend.auth.supabase_auth import (
    AuthenticationUnavailable,
    verify_access_token,
)
from backend.memory.local_staging_boundary import (
    LOCAL_SUPABASE_URL,
)

USER_ID = "00000000-0000-4000-8000-000000000001"
LOCAL_KEY = "sb_publishable_testonly"
HOSTED_URL = "https://example.supabase.co"


def configuration(url, key, enabled=False):
    return Config(
        google_client_id="",
        google_client_secret="",
        redirect_uri="",
        token_encryption_key="",
        database_url="",
        default_test_user_id="",
        supabase_url=url,
        supabase_publishable_key=key,
        allow_local_memory=enabled,
    )


class LocalMemoryConfigurationTests(unittest.TestCase):
    def test_local_disabled_by_default(self):
        self.assertFalse(
            configuration(LOCAL_SUPABASE_URL, LOCAL_KEY).auth_ready
        )

    def test_local_explicit_opt_in(self):
        self.assertTrue(
            configuration(
                LOCAL_SUPABASE_URL, LOCAL_KEY, True
            ).auth_ready
        )

    def test_local_mode_cannot_target_hosted(self):
        self.assertFalse(
            configuration(HOSTED_URL, LOCAL_KEY, True).auth_ready
        )

    def test_local_mode_rejects_secret_key(self):
        self.assertFalse(
            configuration(
                LOCAL_SUPABASE_URL, "sb_secret_example", True
            ).auth_ready
        )

    def test_hosted_mode_remains_available(self):
        self.assertTrue(
            configuration(HOSTED_URL, LOCAL_KEY).auth_ready
        )

    def test_local_auth_uses_exact_endpoint(self):
        response = Mock()
        response.status_code = 200
        response.json.return_value = {"id": USER_ID}

        with patch(
            "backend.auth.supabase_auth.requests.get",
            return_value=response,
        ) as get:
            result = verify_access_token(
                "Bearer synthetic-test-token",
                supabase_url=LOCAL_SUPABASE_URL,
                publishable_key=LOCAL_KEY,
                allow_local_memory=True,
            )

        self.assertEqual(result, USER_ID)
        self.assertEqual(
            get.call_args.args[0],
            LOCAL_SUPABASE_URL + "/auth/v1/user",
        )
        self.assertFalse(
            get.call_args.kwargs["allow_redirects"]
        )

    def test_local_auth_rejected_without_opt_in(self):
        with patch(
            "backend.auth.supabase_auth.requests.get"
        ) as get:
            with self.assertRaises(AuthenticationUnavailable):
                verify_access_token(
                    "Bearer synthetic-test-token",
                    supabase_url=LOCAL_SUPABASE_URL,
                    publishable_key=LOCAL_KEY,
                )
            get.assert_not_called()

    def test_local_auth_rejects_other_ports(self):
        with patch(
            "backend.auth.supabase_auth.requests.get"
        ) as get:
            with self.assertRaises(AuthenticationUnavailable):
                verify_access_token(
                    "Bearer synthetic-test-token",
                    supabase_url="http://127.0.0.1:54321",
                    publishable_key=LOCAL_KEY,
                    allow_local_memory=True,
                )
            get.assert_not_called()


if __name__ == "__main__":
    unittest.main()
