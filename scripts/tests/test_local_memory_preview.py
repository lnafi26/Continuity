import base64
import json
import unittest
from pathlib import Path

from scripts.preview_local_memory import (
    API,
    BACKEND,
    FRONTEND,
    browser_config,
    public_key_from_status,
)


def example_key(role):
    def encode(value):
        return base64.urlsafe_b64encode(
            json.dumps(value).encode()
        ).decode().rstrip("=")

    return (
        encode({"alg": "HS256"})
        + "."
        + encode({"role": role})
        + ".synthetic-signature"
    )


class LocalMemoryPreviewTests(unittest.TestCase):
    def test_browser_configuration_is_local_only(self):
        config = browser_config(example_key("anon"))
        self.assertIn(API, config)
        self.assertIn(BACKEND, config)
        self.assertIn("CONTINUITY_MEMORY_API_BASE", config)
        self.assertIn('oauthBaseUrl": ""', config)
        self.assertEqual(FRONTEND, "http://127.0.0.1:8000")

    def test_status_accepts_local_anon(self):
        key = example_key("anon")
        result = public_key_from_status(
            f'API_URL="{API}"\nANON_KEY="{key}"\n'
        )
        self.assertEqual(result, key)

    def test_rejects_other_supabase_environment(self):
        with self.assertRaises(ValueError):
            public_key_from_status(
                'API_URL="https://example.supabase.co"\n'
                f'ANON_KEY="{example_key("anon")}"\n'
            )

    def test_rejects_privileged_key(self):
        with self.assertRaises(ValueError):
            browser_config(example_key("service_role"))

    def test_auth_callback_defers_supabase_calls(self):
        source = (
            Path(__file__).resolve().parents[2]
            / "frontend/assets/js/continuity-live-observatory.js"
        ).read_text()

        callback = source.split(
            "host.supabaseDb?.auth?.onAuthStateChange?.",
            1
        )[1]

        self.assertIn("host.setTimeout(() =>", callback)
        self.assertIn("version === generation", callback)
        self.assertIn("section.hidden = true", callback)


if __name__ == "__main__":
    unittest.main()
