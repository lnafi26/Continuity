import unittest
from unittest.mock import Mock, patch

from backend.auth.supabase_auth import AuthenticationError
from backend.memory.supabase_reader import (
    MemoryReadUnavailable,
    fetch_project_context,
)

USER = "7fbd542e-4cab-48fa-988d-23f68faac503"
PROJECT = "81c7e765-ea89-4519-91fc-c7aaaf8cc802"
URL = "https://example.supabase.co"
KEY = "sb_publishable_synthetic"
HEADER = "Bearer synthetic-session"


def request_context(**kwargs):
    options = dict(
        supabase_url=URL,
        publishable_key=KEY,
        project_id=PROJECT,
    )
    options.update(kwargs)
    return fetch_project_context(HEADER, **options)


def reply(data, status=200):
    response = Mock(status_code=status)
    response.json.return_value = data
    return response


def records(owner=USER):
    return [
        reply([{
            "id": PROJECT,
            "user_id": owner,
            "name": "Fictional Lunar Observatory",
            "summary": "Imaginary research.",
            "origin": "user",
        }]),
        reply([{
            "id": 1,
            "user_id": USER,
            "project_id": PROJECT,
            "event_type": "decision",
            "title": "Prototype approved",
            "event_date": "2026-10-31T12:00:00Z",
            "source_item_id": None,
            "user_edited": False,
        }]),
        reply([]),
        reply([]),
    ]


class MemoryReaderTests(unittest.TestCase):

    @patch(
        "backend.memory.supabase_reader.verify_access_token",
        return_value=USER,
    )
    @patch("backend.memory.supabase_reader.requests.get")
    def test_authenticated_project_snapshot(self, get, verify):
        get.side_effect = records()
        result = request_context()

        self.assertEqual(result["project"]["id"], PROJECT)
        self.assertEqual(result["counts"]["events"], 1)
        self.assertFalse(result["persisted"])
        self.assertEqual(
            result["retrieval"]["completeness"],
            "bounded_partial",
        )
        verify.assert_called_once()
        self.assertEqual(get.call_count, 4)

        for call in get.call_args_list:
            self.assertEqual(call.kwargs["headers"]["apikey"], KEY)
            self.assertEqual(
                call.kwargs["headers"]["Authorization"], HEADER
            )
            self.assertFalse(call.kwargs["allow_redirects"])
            self.assertEqual(call.kwargs["params"]["user_id"],
                             "eq." + USER)
            self.assertEqual(call.kwargs["timeout"], 8)
            self.assertTrue(call.args[0].startswith(
                URL + "/rest/v1/"
            ))

    @patch(
        "backend.memory.supabase_reader.verify_access_token",
        side_effect=AuthenticationError("No session"),
    )
    @patch("backend.memory.supabase_reader.requests.get")
    def test_missing_auth_blocks_reads(self, get, verify):
        with self.assertRaises(AuthenticationError):
            request_context()
        get.assert_not_called()

    @patch(
        "backend.memory.supabase_reader.verify_access_token",
        return_value=USER,
    )
    @patch("backend.memory.supabase_reader.requests.get")
    def test_project_not_found_fails_closed(self, get, verify):
        get.return_value = reply([])
        with self.assertRaises(LookupError):
            request_context()
        self.assertEqual(get.call_count, 1)

    @patch(
        "backend.memory.supabase_reader.verify_access_token",
        return_value=USER,
    )
    @patch("backend.memory.supabase_reader.requests.get")
    def test_cross_user_project_rejected(self, get, verify):
        get.side_effect = records(
            "77777777-7777-4777-8777-777777777777"
        )
        with self.assertRaises(PermissionError):
            request_context()
        self.assertEqual(get.call_count, 1)

    @patch(
        "backend.memory.supabase_reader.verify_access_token"
    )
    @patch("backend.memory.supabase_reader.requests.get")
    def test_invalid_project_id_blocks_network(self, get, verify):
        with self.assertRaises(ValueError):
            request_context(project_id="not-a-uuid")
        verify.assert_not_called()
        get.assert_not_called()

    @patch(
        "backend.memory.supabase_reader.verify_access_token",
        return_value=USER,
    )
    @patch("backend.memory.supabase_reader.requests.get")
    def test_upstream_error_fails_closed(self, get, verify):
        get.return_value = reply([], status=503)
        with self.assertRaises(MemoryReadUnavailable):
            request_context()

    @patch(
        "backend.memory.supabase_reader.verify_access_token",
        return_value=USER,
    )
    @patch("backend.memory.supabase_reader.requests.get")
    def test_malformed_response_rejected(self, get, verify):
        get.return_value = reply({"unexpected": "object"})
        with self.assertRaises(MemoryReadUnavailable):
            request_context()

    @patch(
        "backend.memory.supabase_reader.verify_access_token"
    )
    @patch("backend.memory.supabase_reader.requests.get")
    def test_untrusted_host_rejected(self, get, verify):
        with self.assertRaises(ValueError):
            request_context(
                supabase_url="https://example.supabase.co.evil.test"
            )
        verify.assert_not_called()
        get.assert_not_called()


    @patch(
        "backend.memory.supabase_reader.verify_access_token",
        return_value=USER,
    )
    @patch("backend.memory.supabase_reader.requests.get")
    def test_partial_links_do_not_claim_no_association(
        self, get, verify
    ):
        responses = records()

        responses[1].json.return_value[0][
            "source_item_id"
        ] = "fictional-older-source"

        get.side_effect = responses

        result = request_context()
        event = result["recent_events"][0]

        self.assertEqual(
            event["source_link_status"],
            "link_not_in_snapshot",
        )
        self.assertEqual(
            event["evidence_verification"],
            "not_verified",
        )
        self.assertEqual(
            result["retrieval"]["completeness"],
            "bounded_partial",
        )

    @patch(
        "backend.memory.supabase_reader.verify_access_token",
        return_value=USER,
    )
    @patch("backend.memory.supabase_reader.requests.get")
    def test_mismatched_event_owner_fails_closed(
        self, get, verify
    ):
        responses = records()

        responses[1].json.return_value[0][
            "user_id"
        ] = "77777777-7777-4777-8777-777777777777"

        get.side_effect = responses

        with self.assertRaises(PermissionError):
            request_context()

        self.assertEqual(get.call_count, 4)


    @patch(
        "backend.memory.supabase_reader.verify_access_token",
        return_value=USER,
    )
    @patch("backend.memory.supabase_reader.requests.get")
    def test_every_query_is_project_scoped(self, get, verify):
        get.side_effect = records()
        request_context()

        self.assertEqual(get.call_count, 4)

        for index, call in enumerate(get.call_args_list):
            params = call.kwargs["params"]
            self.assertEqual(params["user_id"], "eq." + USER)

            if index == 0:
                self.assertEqual(params["id"], "eq." + PROJECT)
            else:
                self.assertEqual(
                    params["project_id"], "eq." + PROJECT
                )


if __name__ == "__main__":
    unittest.main()
