"""Validation-only revision API tests. No database or network."""

import unittest

from flask import Flask, jsonify, request

from backend.auth.supabase_auth import AuthenticationError
from backend.memory.revision_intent_api import (
    register_revision_intent_validation,
)

USER = "11111111-1111-4111-8111-111111111111"
PROJECT = "33333333-3333-4333-8333-333333333333"
ASSERTION = "44444444-4444-4444-8444-444444444444"
SOURCE = "55555555-5555-4555-8555-555555555555"

PATH = f"/memory/projects/{PROJECT}/revision-intents/validate"


def valid_payload():
    return {
        "assertion_id": ASSERTION,
        "expected_head_id": None,
        "action": "propose",
        "structured_value": {"decision": "Proceed"},
        "effective_at": "2026-11-17T18:00:00Z",
        "evidence": [{
            "source_item_id": SOURCE,
            "role": "supports",
        }],
    }


class RevisionIntentApiTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.ready = True
        self.identity = USER
        self.auth_calls = 0

        def verify():
            self.auth_calls += 1
            if request.headers.get("Authorization") != "Bearer valid":
                raise AuthenticationError("Authentication required.")
            return self.identity

        register_revision_intent_validation(
            self.app,
            auth_ready=lambda: self.ready,
            verified_user=verify,
        )

        @self.app.errorhandler(AuthenticationError)
        def unauthorized(_exc):
            return jsonify(
                ok=False,
                error="Authentication required.",
            ), 401

        self.client = self.app.test_client()

    def post(self, data=None):
        return self.client.post(
            PATH,
            json=valid_payload() if data is None else data,
            headers={"Authorization": "Bearer valid"},
        )

    def test_success_reports_validation_only(self):
        response = self.post()
        self.assertEqual(response.status_code, 200)

        self.assertEqual(response.json, {
            "ok": True,
            "validation": "structure_only",
            "persisted": False,
            "ownership_checked": False,
            "review_state_changed": False,
            "confirmation_recorded": False,
        })

        self.assertEqual(
            response.headers["Cache-Control"],
            "private, no-store",
        )
        self.assertEqual(self.auth_calls, 1)

    def test_missing_bearer_denied(self):
        response = self.client.post(PATH, json=valid_payload())
        self.assertEqual(response.status_code, 401)

    def test_unconfigured_auth_denied_before_verification(self):
        self.ready = False
        self.assertEqual(self.post().status_code, 503)
        self.assertEqual(self.auth_calls, 0)

    def test_untrusted_identity_denied(self):
        self.identity = "forged"
        self.assertEqual(self.post().status_code, 503)

    def test_authority_fields_cannot_be_supplied(self):
        forbidden = {
            "user_id": USER,
            "project_id": PROJECT,
            "actor_type": "user",
            "confirmed_by": USER,
            "confirmed_at": "2026-11-17T18:00:00Z",
            "recorded_at": "2026-11-17T18:00:00Z",
            "version_number": 1,
        }

        for key, value in forbidden.items():
            with self.subTest(key=key):
                data = valid_payload()
                data[key] = value
                self.assertEqual(self.post(data).status_code, 400)

    def test_missing_expected_head_denied(self):
        data = valid_payload()
        del data["expected_head_id"]
        self.assertEqual(self.post(data).status_code, 400)

    def test_invalid_actions_and_timestamps_denied(self):
        for change in (
            {"action": "agent-confirm"},
            {"effective_at": "2026-11-17T18:00:00"},
            {"effective_at": "not-a-time"},
        ):
            with self.subTest(change=change):
                data = valid_payload()
                data.update(change)
                self.assertEqual(self.post(data).status_code, 400)

    def test_untrusted_evidence_denied(self):
        entries = (
            [{"source_item_id": SOURCE, "role": "verified"}],
            [
                {"source_item_id": SOURCE, "role": "supports"},
                {"source_item_id": SOURCE, "role": "supports"},
            ],
            [{"source_item_id": SOURCE, "role": "supports",
              "verified": True}],
        )

        for evidence in entries:
            with self.subTest(evidence=evidence):
                data = valid_payload()
                data["evidence"] = evidence
                self.assertEqual(self.post(data).status_code, 400)

    def test_invalid_project_uuid_denied(self):
        response = self.client.post(
            "/memory/projects/invalid/revision-intents/validate",
            json=valid_payload(),
            headers={"Authorization": "Bearer valid"},
        )
        self.assertEqual(response.status_code, 400)

    def test_oversized_body_denied(self):
        data = valid_payload()
        data["structured_value"] = {"text": "x" * 22000}
        self.assertEqual(self.post(data).status_code, 413)

    def test_non_json_body_denied(self):
        response = self.client.post(
            PATH,
            data="not json",
            headers={"Authorization": "Bearer valid"},
            content_type="text/plain",
        )
        self.assertEqual(response.status_code, 415)

    def test_other_http_methods_denied(self):
        self.assertEqual(self.client.get(PATH).status_code, 405)
        self.assertEqual(self.client.delete(PATH).status_code, 405)


if __name__ == "__main__":
    unittest.main()
