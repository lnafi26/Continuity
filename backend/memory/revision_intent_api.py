"""B4.6a: authenticated, syntax-only validation of user revision intents.

No database connection or mutation. This does not verify project
ownership or save a user confirmation. The migration and trusted
write API remain disabled.
"""

from datetime import datetime
from uuid import UUID

from flask import jsonify, request

from backend.memory.revision_write_service import (
    UserRevisionIntent,
    _prepare,
)

_ALLOWED_KEYS = frozenset({
    "assertion_id",
    "expected_head_id",
    "action",
    "structured_value",
    "effective_at",
    "evidence",
})

_REQUIRED_KEYS = _ALLOWED_KEYS - {"evidence"}
_MAX_REQUEST_BYTES = 20000


def parse_revision_intent(payload, route_project_id):
    """Validate structure only, without an authorization decision."""
    if type(payload) is not dict:
        raise ValueError("Expected a JSON object.")

    if (
        not _REQUIRED_KEYS.issubset(payload)
        or not set(payload).issubset(_ALLOWED_KEYS)
    ):
        raise ValueError("Missing or unsupported revision fields.")

    if type(payload["action"]) is not str:
        raise ValueError("Invalid revision action.")

    if type(payload["effective_at"]) is not str:
        raise ValueError("Invalid effective timestamp.")

    try:
        effective = datetime.fromisoformat(
            payload["effective_at"].replace("Z", "+00:00")
        )
    except ValueError:
        raise ValueError("Invalid effective timestamp.") from None

    evidence = payload.get("evidence", [])

    if type(evidence) is not list or len(evidence) > 20:
        raise ValueError("Invalid evidence collection.")

    pairs = []

    for entry in evidence:
        if (
            type(entry) is not dict
            or set(entry) != {"source_item_id", "role"}
        ):
            raise ValueError("Invalid evidence entry.")

        if type(entry["role"]) is not str:
            raise ValueError("Invalid evidence role.")

        pairs.append((
            entry["source_item_id"],
            entry["role"],
        ))

    intent = UserRevisionIntent(
        project_id=route_project_id,
        assertion_id=payload["assertion_id"],
        expected_head_id=payload["expected_head_id"],
        action=payload["action"],
        structured_value=payload["structured_value"],
        effective_at=effective,
        evidence=tuple(pairs),
    )

    # Reuse B4.4 command validation. Never invoke its write service.
    _prepare(intent)

    return intent


def register_revision_intent_validation(
    app,
    *,
    auth_ready,
    verified_user,
):
    """Register a non-persisting route on the existing Flask app.

    verified_user must validate the bearer token against Supabase Auth.
    Existing app error handlers translate authentication failures.
    """

    @app.post(
        "/memory/projects/<project_id>/revision-intents/validate"
    )
    def memory_revision_intent_validate(project_id):
        if not auth_ready():
            return jsonify(
                ok=False,
                error="Authentication service unavailable.",
            ), 503

        # Authentication precedes validation of untrusted input.
        user = verified_user()

        try:
            UUID(user)
        except (TypeError, AttributeError, ValueError):
            return jsonify(
                ok=False,
                error="Authentication service unavailable.",
            ), 503

        if request.mimetype != "application/json":
            return jsonify(
                ok=False,
                error="JSON request required.",
            ), 415

        size = request.content_length

        if size is None or size <= 0:
            return jsonify(
                ok=False,
                error="A bounded request body is required.",
            ), 411

        if size > _MAX_REQUEST_BYTES:
            return jsonify(
                ok=False,
                error="Revision request too large.",
            ), 413

        try:
            payload = request.get_json(silent=True)
            parse_revision_intent(payload, project_id)
        except (TypeError, ValueError):
            return jsonify(
                ok=False,
                error="Invalid revision intent.",
            ), 400

        # No assertion lookup, database write or confirmation occurs.
        response = jsonify(
            ok=True,
            validation="structure_only",
            persisted=False,
            ownership_checked=False,
            review_state_changed=False,
            confirmation_recorded=False,
        )

        response.headers["Cache-Control"] = "private, no-store"
        return response
