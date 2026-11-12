import base64
import json
import unittest

from backend.memory.local_staging_boundary import (
    LOCAL_SUPABASE_URL,
    approved_local_memory_config,
    is_public_api_key,
)


def example_key(role):
    def encode(value):
        raw = json.dumps(value).encode()
        return base64.urlsafe_b64encode(raw).decode().rstrip("=")

    return (
        encode({"alg": "HS256", "typ": "JWT"})
        + "."
        + encode({"role": role})
        + ".example-signature"
    )


class LocalMemoryBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.anon = example_key("anon")

    def test_disabled_by_default(self):
        self.assertFalse(
            approved_local_memory_config(
                LOCAL_SUPABASE_URL, self.anon
            )
        )

    def test_exact_local_endpoint_requires_opt_in(self):
        self.assertTrue(
            approved_local_memory_config(
                LOCAL_SUPABASE_URL,
                self.anon,
                enabled=True,
            )
        )

    def test_rejects_service_role(self):
        self.assertFalse(
            is_public_api_key(example_key("service_role"))
        )

    def test_rejects_secret_api_key(self):
        self.assertFalse(
            is_public_api_key("sb_secret_example")
        )

    def test_rejects_malformed_key(self):
        self.assertFalse(is_public_api_key("not-a-key"))

    def test_rejects_other_local_ports(self):
        self.assertFalse(
            approved_local_memory_config(
                "http://127.0.0.1:54321",
                self.anon,
                enabled=True,
            )
        )

    def test_rejects_localhost_alias(self):
        self.assertFalse(
            approved_local_memory_config(
                "http://localhost:21955",
                self.anon,
                enabled=True,
            )
        )

    def test_rejects_remote_endpoint(self):
        self.assertFalse(
            approved_local_memory_config(
                "https://example.supabase.co",
                self.anon,
                enabled=True,
            )
        )

    def test_rejects_url_with_extra_components(self):
        for suffix in ("/auth/v1", "?redirect=1", "#fragment"):
            with self.subTest(suffix=suffix):
                self.assertFalse(
                    approved_local_memory_config(
                        LOCAL_SUPABASE_URL + suffix,
                        self.anon,
                        enabled=True,
                    )
                )


if __name__ == "__main__":
    unittest.main()
