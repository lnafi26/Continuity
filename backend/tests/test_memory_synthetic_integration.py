"""Full memory route tests using fictional records and no network."""

import copy
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(
    0,
    str(Path(__file__).resolve().parents[1] / "auth"),
)

import server
from config import Config


FIXTURE = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "memory_lunar_observatory.json"
)

USER = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
PROJECT = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"

PATH = f"/memory/projects/{PROJECT}/context"


def configuration():
    return Config(
        google_client_id="",
        google_client_secret="",
        redirect_uri="http://localhost:8766/auth/google/callback",
        token_encryption_key="",
        database_url="",
        default_test_user_id="",
        supabase_url="https://example.supabase.co",
        supabase_publishable_key="sb_publishable_synthetic",
    )


def load_fixture():
    data = json.loads(FIXTURE.read_text())
    assert data["fixture_type"] == "fictional_test_data_only"
    return data


def reply(data):
    response = Mock(status_code=200)
    response.json.return_value = data
    return response


def synthetic_responses(data):
    return [
        reply([data["project"]]),
        reply(data["events"]),
        reply(data["actions"]),
        reply(data["source_links"]),
    ]


class SyntheticMemoryIntegrationTests(unittest.TestCase):

    def setUp(self):
        self.client = server.app.test_client()
        self.fixture = load_fixture()

    def call_route(self, data):
        with (
            patch.object(server, "config", configuration()),
            patch(
                "backend.memory.supabase_reader.verify_access_token",
                return_value=USER,
            ) as auth,
            patch(
                "backend.memory.supabase_reader.requests.get",
                side_effect=synthetic_responses(data),
            ) as get,
        ):
            response = self.client.get(
                PATH,
                headers={
                    "Authorization": "Bearer fictional-test-token"
                },
            )

        return response, auth, get

    def test_full_route_assembles_fictional_project(self):
        original = copy.deepcopy(self.fixture)

        response, auth, get = self.call_route(
            self.fixture
        )

        self.assertEqual(response.status_code, 200)

        result = response.json["context"]

        self.assertEqual(
            result["project"]["name"],
            "Fictional Lunar Research Observatory",
        )

        self.assertEqual(result["counts"]["events"], 3)
        self.assertEqual(result["counts"]["open_actions"], 2)
        self.assertEqual(result["counts"]["source_links"], 2)

        self.assertEqual(
            [event["id"] for event in result["recent_events"]],
            ["101", "102", "103"],
        )

        self.assertEqual(
            [
                event["source_link_status"]
                for event in result["recent_events"]
            ],
            [
                "confirmed",
                "pending",
                "link_not_in_snapshot",
            ],
        )

        for event in result["recent_events"]:
            self.assertEqual(
                event["evidence_verification"],
                "not_verified",
            )

        self.assertEqual(
            result["retrieval"]["completeness"],
            "bounded_partial",
        )

        self.assertEqual(
            result["kind"],
            "derived_read_only",
        )
        self.assertFalse(result["persisted"])

        self.assertIn(
            "no-store",
            response.headers["Cache-Control"],
        )

        auth.assert_called_once()
        self.assertEqual(get.call_count, 4)

        for index, call in enumerate(get.call_args_list):
            self.assertEqual(
                call.kwargs["params"]["user_id"],
                "eq." + USER,
            )

            if index == 0:
                self.assertEqual(
                    call.kwargs["params"]["id"],
                    "eq." + PROJECT,
                )
            else:
                self.assertEqual(
                    call.kwargs["params"]["project_id"],
                    "eq." + PROJECT,
                )

            self.assertTrue(
                call.args[0].startswith(
                    "https://example.supabase.co/rest/v1/"
                )
            )

        self.assertEqual(self.fixture, original)

    def test_cross_project_record_rejected(self):
        data = copy.deepcopy(self.fixture)

        data["events"][0]["project_id"] = (
            "ffffffff-ffff-4fff-8fff-ffffffffffff"
        )

        response, auth, get = self.call_route(data)

        self.assertEqual(response.status_code, 404)
        self.assertEqual(
            response.json["error"],
            "Project not found or inaccessible.",
        )

        auth.assert_called_once()
        self.assertEqual(get.call_count, 4)


if __name__ == "__main__":
    unittest.main()
